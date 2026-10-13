from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any, TypeVar

from pydantic import BaseModel, JsonValue

from text2business.capacity import assess_capacity, parse_requested_deadline
from text2business.decision import clarification_decision, final_decision, handoff_decision
from text2business.drafting import (
    DeterministicResponseDrafter,
    GatewayResponseDrafter,
    ResponseDrafterPort,
)
from text2business.extractor import (
    DeterministicExtractor,
    ExtractorPort,
    GatewayExtractor,
    build_extractor_from_env,
)
from text2business.gateway import GatewayError
from text2business.harness import HarnessError, HarnessGuard
from text2business.models import (
    Action,
    Asset,
    AssetMatch,
    AutomationAssessment,
    CapacityAssessment,
    CaseResult,
    Contract,
    Customer,
    CustomerMatch,
    Decision,
    DraftResponse,
    ExtractedFacts,
    FindAssetsInput,
    FindCustomersInput,
    FindSitesInput,
    FindTicketsInput,
    GetCapacityInput,
    GetContractInput,
    GetCustomerInput,
    IncomingRequest,
    Priority,
    PriorityAssessment,
    PriorityOverride,
    RepeatAssessment,
    ReviewStatus,
    RunLimits,
    Site,
    SiteMatch,
    SlaAssessment,
    TerminalState,
    Ticket,
    TicketChangeProposal,
    TicketChangeProposalOutput,
    TraceEvent,
    TraceKind,
)
from text2business.priority import apply_priority_override, assess_priority
from text2business.proposal import build_ticket_change_proposal, deterministic_response
from text2business.redaction import sanitize_trace_value
from text2business.repeat import RepeatResolution, classify_repeat
from text2business.repository import JsonCorporateRepository, normalize_text
from text2business.resolution import resolve_unique_asset, resolve_unique_site
from text2business.sla import calculate_sla
from text2business.safety import scan_untrusted_instructions


ModelT = TypeVar("ModelT", bound=BaseModel)


class ToolExecutionError(RuntimeError):
    """Controlled failure raised by a typed repository/tool boundary."""


def _json_dict(model: BaseModel) -> dict[str, JsonValue]:
    return model.model_dump(mode="json")  # type: ignore[return-value]


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
            input=sanitize_trace_value(input_data),
            output=sanitize_trace_value(output_data),
        )
    )


def _call_tool(
    guard: HarnessGuard,
    trace: list[TraceEvent],
    name: str,
    payload: BaseModel,
    function: Callable[[Any], ModelT],
    *,
    proposal: bool = False,
) -> ModelT:
    input_data = _json_dict(payload)
    guard.before_tool(name, input_data, proposal=proposal)
    try:
        output = function(payload)
    except Exception as exc:
        guard.checkpoint()
        raise ToolExecutionError(f"{name} failed: {type(exc).__name__}") from exc
    guard.checkpoint()
    _trace(trace, TraceKind.PROPOSAL if proposal else TraceKind.TOOL, name, input_data, _json_dict(output))
    return output


def _customer_conflicts(customer: Customer, facts: ExtractedFacts) -> bool:
    if facts.customer_name is None:
        return False
    extracted = normalize_text(str(facts.customer_name.value))
    labels = [normalize_text(customer.name), *(normalize_text(alias) for alias in customer.aliases)]
    return not any(extracted == label for label in labels)


def _fact_is_true(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.casefold() == "true")


def run_case(
    request: IncomingRequest,
    *,
    extractor: ExtractorPort | None = None,
    repository: JsonCorporateRepository | None = None,
    drafter: ResponseDrafterPort | None = None,
    limits: RunLimits | None = None,
) -> CaseResult:
    """Run one bounded triage pipeline and return exactly one typed terminal result."""

    selected_repository = repository or JsonCorporateRepository()
    selected_extractor = extractor
    selected_drafter = drafter

    guard = HarnessGuard(request, limits)
    trace: list[TraceEvent] = []
    facts = ExtractedFacts()
    customer_candidates: list[CustomerMatch] = []
    site_candidates: list[SiteMatch] = []
    asset_candidates: list[AssetMatch] = []
    customer: Customer | None = None
    site: Site | None = None
    asset: Asset | None = None
    contract: Contract | None = None
    tickets: list[Ticket] = []
    repeat: RepeatAssessment | None = None
    repeat_resolution: RepeatResolution | None = None
    priority: PriorityAssessment | None = None
    sla: SlaAssessment | None = None
    capacity: CapacityAssessment | None = None
    proposal: TicketChangeProposalOutput | None = None
    clarification_questions: list[str] = []
    warnings: list[str] = []
    identity_verified = False

    def finish(
        decision: Decision,
        terminal_state: TerminalState,
        *,
        clarification: str | None = None,
        allow_model_draft: bool = True,
        enforce_deadline: bool = True,
    ) -> CaseResult:
        nonlocal warnings
        if not any(event.name == "final_decision" for event in trace):
            _trace(
                trace,
                TraceKind.RULE,
                "final_decision",
                {
                    "priority": priority.effective if priority else None,
                    "repeat": repeat.kind if repeat else None,
                },
                _json_dict(decision),
            )
        if not allow_model_draft:
            effective_drafter: ResponseDrafterPort = DeterministicResponseDrafter()
        elif selected_drafter is not None:
            effective_drafter = selected_drafter
        elif isinstance(selected_extractor, GatewayExtractor):
            effective_drafter = GatewayResponseDrafter(selected_extractor.client)
        else:
            effective_drafter = DeterministicResponseDrafter()
        if isinstance(effective_drafter, GatewayResponseDrafter) and guard.remaining_model_calls == 0:
            effective_drafter = DeterministicResponseDrafter()
            warnings.append("MODEL_BUDGET_EXHAUSTED: deterministic response template used")
        try:
            draft = effective_drafter.draft(
                asset=asset,
                site=site,
                priority=priority,
                sla=sla,
                capacity=capacity,
                decision=decision,
                clarification=clarification,
                on_model_call=guard.before_model,
            )
        except GatewayError:
            draft = deterministic_response(
                asset,
                site,
                priority,
                sla,
                capacity,
                clarification=clarification,
                handed_off=True,
            )
            warnings.append("MODEL_DRAFT_FAILED: deterministic response template used")
        if enforce_deadline:
            guard.checkpoint()
        warnings.extend(draft.warnings)
        return CaseResult(
            run=guard.finish(terminal_state, enforce_deadline=enforce_deadline),
            request=request,
            facts=facts,
            customer_candidates=customer_candidates,
            site_candidates=site_candidates,
            asset_candidates=asset_candidates,
            resolved_customer=customer,
            resolved_site=site,
            resolved_asset=asset,
            contract=contract,
            tickets=tickets,
            repeat=repeat,
            priority=priority,
            sla=sla,
            capacity=capacity,
            decision=decision,
            proposal=proposal,
            draft_response=draft,
            clarification_questions=clarification_questions,
            warnings=warnings,
            trace=trace,
        )

    try:
        suspicious = scan_untrusted_instructions(request)
        if suspicious is not None:
            facts = ExtractedFacts(suspicious_instruction=suspicious)
            _trace(
                trace,
                TraceKind.RULE,
                "pre_extraction_safety_scan",
                {
                    "message_length": len(request.text),
                    "attachment_length": len(request.attachment_text or ""),
                },
                {"suspicious_instruction": suspicious.model_dump(mode="json")},
            )
            warnings.append("Untrusted instruction detected before model/tool execution")
            return finish(
                handoff_decision(
                    "PROMPT_INJECTION_DETECTED",
                    "Инструкции внутри клиентских данных не могут управлять системой.",
                ),
                TerminalState.HANDED_OFF,
                allow_model_draft=False,
            )

        selected_extractor = selected_extractor or build_extractor_from_env()
        if selected_drafter is None and isinstance(selected_extractor, GatewayExtractor):
            selected_drafter = GatewayResponseDrafter(selected_extractor.client)
        facts = selected_extractor.extract(request, on_model_call=guard.before_model)
        guard.checkpoint()
        extraction_kind = (
            TraceKind.MODEL if isinstance(selected_extractor, GatewayExtractor) else TraceKind.EXTRACTION
        )
        _trace(
            trace,
            extraction_kind,
            "structured_extraction",
            {"channel": request.channel, "text_length": len(request.text)},
            _json_dict(facts),
        )

        if facts.suspicious_instruction is not None:
            warnings.append("Untrusted instruction detected; no corporate tool was called")
            return finish(
                handoff_decision(
                    "PROMPT_INJECTION_DETECTED",
                    "Инструкции внутри клиентского текста не могут управлять системой.",
                ),
                TerminalState.HANDED_OFF,
                allow_model_draft=False,
            )

        identity = request.identity
        if identity is None or not identity.verified:
            customer_query = (
                str(facts.customer_name.value)
                if facts.customer_name
                else request.sender_display or ""
            )
            matches = _call_tool(
                guard,
                trace,
                "find_customers",
                FindCustomersInput(query=customer_query),
                selected_repository.find_customers,
            )
            customer_candidates = matches.matches
            warnings.append("Trusted CRM customer ID is required before a proposal")
            if len(customer_candidates) != 1:
                return finish(
                    handoff_decision(
                        "TRUSTED_IDENTITY_MISSING",
                        "Клиента нельзя однозначно подтвердить без данных CRM.",
                    ),
                    TerminalState.HANDED_OFF,
                    allow_model_draft=False,
                )
            customer = customer_candidates[0].customer
        else:
            identity_verified = True
            customer_output = _call_tool(
                guard,
                trace,
                "get_customer",
                GetCustomerInput(customer_id=identity.customer_id),
                selected_repository.get_customer,
            )
            customer = customer_output.customer
            if customer is None:
                warnings.append("Trusted CRM customer ID was not found")
                return finish(
                    handoff_decision("CUSTOMER_NOT_FOUND", "Клиент из CRM не найден."),
                    TerminalState.HANDED_OFF,
                )
            if _customer_conflicts(customer, facts):
                warnings.append("CRM identity conflicts with the customer named in text")
                return finish(
                    handoff_decision(
                        "CRM_TEXT_CONFLICT",
                        "Клиент в тексте не совпадает с доверенной CRM identity.",
                    ),
                    TerminalState.HANDED_OFF,
                )

        site_query = str(facts.site_reference.value) if facts.site_reference else ""
        site_output = _call_tool(
            guard,
            trace,
            "find_sites",
            FindSitesInput(customer_id=customer.customer_id, query=site_query),
            selected_repository.find_sites,
        )
        site_candidates = site_output.matches
        site = resolve_unique_site(site_candidates)
        if site is None:
            question = "Уточните точный адрес объекта."
            clarification_questions.append(question)
            warnings.append("Site ambiguity was not resolved automatically")
            return finish(
                clarification_decision("SITE_AMBIGUOUS", "Объект нельзя выбрать однозначно."),
                TerminalState.NEEDS_USER_INPUT,
                clarification=question,
            )

        asset_query = str(facts.asset_reference.value) if facts.asset_reference else ""
        asset_output = _call_tool(
            guard,
            trace,
            "find_assets",
            FindAssetsInput(site_id=site.site_id, query=asset_query),
            selected_repository.find_assets,
        )
        asset_candidates = asset_output.matches
        asset = resolve_unique_asset(asset_candidates)
        if asset is None:
            question = "Уточните точный код оборудования."
            clarification_questions.append(question)
            warnings.append("Asset ambiguity was not resolved automatically")
            return finish(
                clarification_decision("ASSET_AMBIGUOUS", "Оборудование нельзя выбрать однозначно."),
                TerminalState.NEEDS_USER_INPUT,
                clarification=question,
            )

        contract_output = _call_tool(
            guard,
            trace,
            "get_contract",
            GetContractInput(site_id=site.site_id),
            selected_repository.get_contract,
        )
        contract = contract_output.contract
        if contract is None:
            warnings.append("Contract and SLA are unavailable")
            return finish(
                handoff_decision("CONTRACT_NOT_FOUND", "Договор обслуживания не найден."),
                TerminalState.HANDED_OFF,
            )

        tickets_output = _call_tool(
            guard,
            trace,
            "find_tickets",
            FindTicketsInput(
                customer_id=customer.customer_id,
                site_id=site.site_id,
                asset_id=asset.asset_id,
            ),
            selected_repository.find_tickets,
        )
        tickets = tickets_output.tickets
        repeat_resolution = classify_repeat(tickets, request.received_at)
        repeat = repeat_resolution.assessment
        if repeat_resolution.multiple_open:
            warnings.append("Multiple open tickets require manual selection")
            return finish(
                handoff_decision(
                    "MULTIPLE_OPEN_TICKETS",
                    "Найдено несколько открытых заявок по одному оборудованию.",
                ),
                TerminalState.HANDED_OFF,
            )

        capacity_output = _call_tool(
            guard,
            trace,
            "get_capacity",
            GetCapacityInput(service_group=asset.service_group, region=site.region),
            selected_repository.get_capacity,
        )

        priority = assess_priority(asset, facts)
        sla = calculate_sla(
            request.received_at,
            site,
            contract,
            open_repeat_ticket=repeat_resolution.open_ticket,
        )
        requested_by = parse_requested_deadline(
            facts.desired_deadline,
            request.received_at,
            site.timezone,
        )
        capacity = assess_capacity(asset, site, capacity_output.capacity, requested_by)
        _trace(
            trace,
            TraceKind.RULE,
            "domain_assessments",
            {"asset_id": asset.asset_id, "contract_id": contract.contract_id},
            {
                "repeat": repeat.model_dump(mode="json"),
                "priority": priority.model_dump(mode="json"),
                "sla": sla.model_dump(mode="json"),
                "capacity": capacity.model_dump(mode="json"),
            },
        )

        if contract.plan != "Gold":
            warnings.append("Holiday calendars are outside MVP; weekdays only")
        if repeat_resolution.open_ticket:
            remaining = sla.deadline - request.received_at.astimezone(sla.deadline.tzinfo)
            if remaining <= timedelta(0):
                warnings.append("SLA_BREACHED")
            elif remaining <= timedelta(minutes=30):
                warnings.append("SLA_AT_RISK")

        base_action = (
            Action.UPDATE_EXISTING if repeat_resolution.open_ticket else Action.CREATE_NEW
        )
        approval_required = bool(
            facts.requires_additional_approval
            and _fact_is_true(facts.requires_additional_approval.value)
        )
        if not identity_verified:
            decision = handoff_decision(
                "TRUSTED_IDENTITY_MISSING",
                "Расчёты предварительные; клиента должен подтвердить диспетчер по CRM.",
            )
        else:
            decision = final_decision(
                base_action,
                priority.effective,
                requires_additional_approval=approval_required,
            )

        if identity_verified and not approval_required:
            proposal_input = build_ticket_change_proposal(
                request,
                customer,
                site,
                asset,
                facts,
                priority,
                sla,
                repeat,
                open_ticket=repeat_resolution.open_ticket,
            )
            proposal = _call_tool(
                guard,
                trace,
                "propose_ticket_change",
                proposal_input,
                selected_repository.propose_ticket_change,
                proposal=True,
            )
            warnings.extend(proposal.warnings)

        terminal = (
            TerminalState.COMPLETED
            if decision.review_status == ReviewStatus.READY_FOR_REVIEW
            else TerminalState.HANDED_OFF
        )
        return finish(decision, terminal)
    except GatewayError as exc:
        warnings.append(str(exc))
        _trace(
            trace,
            TraceKind.RULE,
            "controlled_gateway_failure",
            {},
            {"error": type(exc).__name__},
        )
        return finish(
            handoff_decision("EXTRACTION_FAILED", "Извлечение не завершено; нужна ручная проверка."),
            TerminalState.FAILED,
            allow_model_draft=False,
            enforce_deadline=False,
        )
    except HarnessError as exc:
        proposal = None
        warnings.append(str(exc))
        _trace(
            trace,
            TraceKind.RULE,
            "controlled_harness_failure",
            {},
            {"error": type(exc).__name__, "reason_code": exc.reason_code},
        )
        return finish(
            handoff_decision(exc.reason_code, "Лимит выполнения достигнут; нужна ручная проверка."),
            TerminalState.FAILED,
            allow_model_draft=False,
            enforce_deadline=False,
        )
    except (ToolExecutionError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
        proposal = None
        warnings.append(str(exc))
        _trace(
            trace,
            TraceKind.RULE,
            "controlled_run_failure",
            {},
            {"error": type(exc).__name__},
        )
        return finish(
            handoff_decision("TOOL_EXECUTION_FAILED", "Внешняя проверка не завершена; нужна ручная проверка."),
            TerminalState.FAILED,
            allow_model_draft=False,
            enforce_deadline=False,
        )


def apply_dispatcher_priority_override(
    result: CaseResult,
    override: PriorityOverride,
) -> CaseResult:
    """Apply an in-memory dispatcher correction without creating an external write."""

    if result.priority is None:
        raise ValueError("priority is unavailable for override")
    updated_priority = apply_priority_override(result.priority, override)

    updated_proposal = result.proposal
    if updated_proposal is not None:
        payload = dict(updated_proposal.proposal.proposed_payload)
        payload["priority"] = updated_priority.effective
        proposal_model: TicketChangeProposal = updated_proposal.proposal.model_copy(
            update={"proposed_payload": payload}
        )
        updated_proposal = updated_proposal.model_copy(update={"proposal": proposal_model})

    action = (
        updated_proposal.proposal.operation
        if updated_proposal is not None
        else result.decision.action
    )
    must_handoff = (
        result.priority.calculated == Priority.P1
        or updated_priority.effective == Priority.P1
        or result.decision.action == Action.REQUIRES_ADDITIONAL_APPROVAL
    )
    updated_decision = result.decision.model_copy(
        update={
            "action": action,
            "review_status": (
                ReviewStatus.NEEDS_DISPATCHER_REVIEW
                if must_handoff
                else result.decision.review_status
            ),
            "automation_assessment": (
                AutomationAssessment.HUMAN_REQUIRED
                if must_handoff
                else result.decision.automation_assessment
            ),
            "reason_codes": [*result.decision.reason_codes, "PRIORITY_OVERRIDDEN"],
        }
    )
    updated_trace = [
        *result.trace,
        TraceEvent(
            step=len(result.trace) + 1,
            kind=TraceKind.REVIEW,
            name="dispatcher_priority_override",
            input={
                "priority": override.priority,
                "reason": override.reason,
                "actor": override.actor,
            },
            output={
                "calculated": updated_priority.calculated,
                "effective": updated_priority.effective,
            },
        ),
    ]
    updated_draft: DraftResponse = deterministic_response(
        result.resolved_asset,
        result.resolved_site,
        updated_priority,
        result.sla,
        result.capacity,
        handed_off=must_handoff,
    )
    return result.model_copy(
        update={
            "priority": updated_priority,
            "decision": updated_decision,
            "proposal": updated_proposal,
            "draft_response": updated_draft,
            "trace": updated_trace,
        }
    )
