from __future__ import annotations

import hashlib

from text2business.extractor import DeterministicExtractor
from text2business.models import (
    Action,
    CaseResult,
    Decision,
    FindAssetsInput,
    FindOpenTicketsInput,
    FindSiteInput,
    GetContractInput,
    IncomingRequest,
    JsonValue,
    TicketMutationInput,
    TraceEvent,
    TraceKind,
)
from text2business.rules import assess_priority, calculate_sla
from text2business.tools import MockCorporateTools


def _json_dict(model: object) -> dict[str, JsonValue]:
    return model.model_dump(mode="json")  # type: ignore[union-attr,return-value]


def _trace(
    events: list[TraceEvent],
    kind: TraceKind,
    name: str,
    input_data: dict[str, JsonValue],
    output_data: dict[str, JsonValue],
) -> None:
    events.append(
        TraceEvent(
            step=len(events) + 1,
            kind=kind,
            name=name,
            input=input_data,
            output=output_data,
        )
    )


def run_case(
    request: IncomingRequest,
    *,
    extractor: DeterministicExtractor | None = None,
    tools: MockCorporateTools | None = None,
) -> CaseResult:
    extractor = extractor or DeterministicExtractor()
    tools = tools or MockCorporateTools()
    trace: list[TraceEvent] = []

    facts = extractor.extract(request)
    _trace(
        trace,
        TraceKind.EXTRACTION,
        "deterministic_extraction",
        {"text": request.text},
        _json_dict(facts),
    )

    site_query = " ".join(
        str(fact.value) for fact in (facts.customer, facts.site) if fact is not None
    )
    site_input = FindSiteInput(query=site_query)
    site_output = tools.find_customer_or_site(site_input)
    _trace(trace, TraceKind.TOOL, "find_customer_or_site", _json_dict(site_input), _json_dict(site_output))

    top_score = site_output.matches[0].score if site_output.matches else 0
    top_sites = [match for match in site_output.matches if match.score == top_score]
    if len(top_sites) != 1 or top_score < 4:
        decision = Decision(
            action=Action.REQUEST_CLARIFICATION,
            reason_codes=["SITE_AMBIGUOUS"],
            explanation="Объект нельзя выбрать однозначно.",
            requires_human_confirmation=True,
        )
        return CaseResult(
            request=request,
            facts=facts,
            site_candidates=site_output.matches,
            asset_candidates=[],
            resolved_site=None,
            resolved_asset=None,
            contract=None,
            open_tickets=[],
            priority=None,
            sla=None,
            decision=decision,
            mutation=None,
            draft_response="Уточните, пожалуйста, адрес объекта.",
            clarification_questions=["Уточните точный адрес объекта."],
            warnings=["Ticket mutation was not attempted"],
            trace=trace,
        )

    site = top_sites[0].site
    asset_input = FindAssetsInput(
        site_id=site.site_id,
        query=str(facts.asset.value) if facts.asset else "",
    )
    asset_output = tools.find_assets(asset_input)
    _trace(trace, TraceKind.TOOL, "find_assets", _json_dict(asset_input), _json_dict(asset_output))
    if len(asset_output.matches) != 1:
        decision = Decision(
            action=Action.REQUEST_CLARIFICATION,
            reason_codes=["ASSET_AMBIGUOUS"],
            explanation="Оборудование нельзя выбрать однозначно.",
            requires_human_confirmation=True,
        )
        return CaseResult(
            request=request,
            facts=facts,
            site_candidates=site_output.matches,
            asset_candidates=asset_output.matches,
            resolved_site=site,
            resolved_asset=None,
            contract=None,
            open_tickets=[],
            priority=None,
            sla=None,
            decision=decision,
            mutation=None,
            draft_response="Уточните, пожалуйста, код оборудования.",
            clarification_questions=["Уточните точный код оборудования."],
            warnings=["Ticket mutation was not attempted"],
            trace=trace,
        )

    asset = asset_output.matches[0].asset
    contract_input = GetContractInput(site_id=site.site_id)
    contract_output = tools.get_contract(contract_input)
    _trace(trace, TraceKind.TOOL, "get_contract", _json_dict(contract_input), _json_dict(contract_output))
    if contract_output.contract is None:
        raise ValueError(f"No contract for site {site.site_id}")
    contract = contract_output.contract

    tickets_input = FindOpenTicketsInput(
        customer_id=site.customer_id,
        site_id=site.site_id,
        asset_id=asset.asset_id,
    )
    tickets_output = tools.find_open_tickets(tickets_input)
    _trace(trace, TraceKind.TOOL, "find_open_tickets", _json_dict(tickets_input), _json_dict(tickets_output))

    priority = assess_priority(asset, facts)
    sla = calculate_sla(request, contract)
    _trace(
        trace,
        TraceKind.RULE,
        "business_rules",
        {"asset_id": asset.asset_id, "contract_id": contract.contract_id},
        {"priority": priority.model_dump(mode="json"), "sla": sla.model_dump(mode="json")},
    )

    action = Action.UPDATE_EXISTING if tickets_output.tickets else Action.CREATE_NEW
    expected_version = tickets_output.tickets[0].version if tickets_output.tickets else 0
    explanation = (
        "Найдена одна открытая заявка по подтверждённому оборудованию."
        if tickets_output.tickets
        else "Объект и оборудование определены однозначно; открытых заявок нет."
    )
    decision = Decision(
        action=action,
        reason_codes=["SITE_UNIQUE", "ASSET_UNIQUE", "OPEN_TICKET_FOUND" if tickets_output.tickets else "NO_OPEN_TICKET"],
        explanation=explanation,
        requires_human_confirmation=True,
    )

    fingerprint = f"{request.model_dump_json()}|{action}|{asset.asset_id}"
    mutation_input = TicketMutationInput(
        idempotency_key=hashlib.sha256(fingerprint.encode()).hexdigest(),
        expected_version=expected_version,
        operation=action,
        proposed_payload={
            "customer_id": site.customer_id,
            "site_id": site.site_id,
            "asset_id": asset.asset_id,
            "summary": str(facts.problem.value) if facts.problem else request.text,
            "priority": priority.priority,
            "sla_deadline": sla.deadline.isoformat(),
            "source_channel": request.channel,
        },
    )
    mutation = tools.create_or_update_ticket(mutation_input)
    _trace(
        trace,
        TraceKind.MUTATION,
        "create_or_update_ticket",
        _json_dict(mutation_input),
        _json_dict(mutation),
    )

    draft_response = (
        f"Приняли обращение по {asset.local_code} на объекте {site.address}. "
        f"Предварительный приоритет — {priority.priority}; срок первичного ответа по договору — "
        f"до {sla.deadline:%d.%m.%Y %H:%M %Z}. Создание заявки ожидает подтверждения диспетчера."
    )
    return CaseResult(
        request=request,
        facts=facts,
        site_candidates=site_output.matches,
        asset_candidates=asset_output.matches,
        resolved_site=site,
        resolved_asset=asset,
        contract=contract,
        open_tickets=tickets_output.tickets,
        priority=priority,
        sla=sla,
        decision=decision,
        mutation=mutation,
        draft_response=draft_response,
        clarification_questions=[],
        warnings=mutation.warnings,
        trace=trace,
    )

