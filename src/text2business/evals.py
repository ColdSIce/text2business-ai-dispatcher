from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import JsonValue

from text2business.drafting import ResponseDrafterPort, validate_draft_safety
from text2business.extractor import ExtractorPort, validate_evidence
from text2business.models import EvalAssertion, EvalCase, EvalRun
from text2business.redaction import contains_sensitive_value
from text2business.repository import JsonCorporateRepository
from text2business.workflow import run_case


class ToolFailureRepository(JsonCorporateRepository):
    """Eval-only adapter that deterministically fails the contract lookup."""

    def get_contract(self, payload: object) -> object:
        del payload
        raise TimeoutError("simulated contract service timeout")


def _repository_for_case(case: EvalCase) -> JsonCorporateRepository:
    """Build the explicit fixture profile declared by one labeled eval case."""

    if case.setup == "tool_failure":
        return ToolFailureRepository()
    repository = JsonCorporateRepository()
    if case.setup == "missing_contract":
        site_id = case.expected.resolved_site_id
        repository.data = repository.data.model_copy(
            update={
                "contracts": [
                    contract for contract in repository.data.contracts if contract.site_id != site_id
                ]
            }
        )
    elif case.setup == "multiple_open":
        asset_id = case.expected.resolved_asset_id
        original = next(
            ticket
            for ticket in repository.data.tickets
            if ticket.asset_id == asset_id and not ticket.status.is_terminal
        )
        duplicate = original.model_copy(
            update={"ticket_id": f"{original.ticket_id}-SECOND", "version": 2}
        )
        repository.data = repository.data.model_copy(
            update={"tickets": [*repository.data.tickets, duplicate]}
        )
    return repository


def _assertion(name: str, expected: JsonValue, actual: JsonValue) -> EvalAssertion:
    """Build one explicit comparison without hidden tolerance or fuzzy matching."""

    return EvalAssertion(
        name=name,
        expected=expected,
        actual=actual,
        passed=expected == actual,
    )


def execute_eval_case(
    case: EvalCase,
    *,
    extractor: ExtractorPort | None = None,
    drafter: ResponseDrafterPort | None = None,
    execution_mode: str = "deterministic",
    extraction_prompt: str | None = None,
    drafting_prompt: str | None = None,
) -> EvalRun:
    """Execute one dataset row and retain its complete trace for UI inspection."""

    result = run_case(
        case.request,
        extractor=extractor,
        drafter=drafter,
        repository=_repository_for_case(case),
    )
    try:
        validate_evidence(result.facts, case.request)
    except ValueError:
        evidence_valid = False
    else:
        evidence_valid = True
    try:
        validate_draft_safety(result.draft_response)
    except ValueError:
        draft_safe = False
    else:
        draft_safe = True
    trace_redacted = not contains_sensitive_value(
        [event.model_dump(mode="json") for event in result.trace]
    )
    proposal = result.proposal.proposal if result.proposal else None
    assertions = [
        _assertion("action", case.expected.action, result.decision.action),
        _assertion("review_status", case.expected.review_status, result.decision.review_status),
        _assertion(
            "priority",
            case.expected.priority,
            result.priority.effective if result.priority else None,
        ),
        _assertion(
            "repeat_kind",
            case.expected.repeat_kind,
            result.repeat.kind if result.repeat else None,
        ),
        _assertion("expects_proposal", case.expected.expects_proposal, result.proposal is not None),
        _assertion("terminal_state", case.expected.terminal_state, result.run.terminal_state),
        _assertion(
            "resolved_customer_id",
            case.expected.resolved_customer_id,
            result.resolved_customer.customer_id if result.resolved_customer else None,
        ),
        _assertion(
            "resolved_site_id",
            case.expected.resolved_site_id,
            result.resolved_site.site_id if result.resolved_site else None,
        ),
        _assertion(
            "resolved_asset_id",
            case.expected.resolved_asset_id,
            result.resolved_asset.asset_id if result.resolved_asset else None,
        ),
        _assertion(
            "sla_kind",
            case.expected.sla_kind,
            result.sla.kind if result.sla else None,
        ),
        _assertion(
            "sla_deadline",
            case.expected.sla_deadline.isoformat() if case.expected.sla_deadline else None,
            result.sla.deadline.isoformat() if result.sla else None,
        ),
        _assertion(
            "capacity_feasibility",
            case.expected.capacity_feasibility,
            result.capacity.feasibility if result.capacity else None,
        ),
        _assertion(
            "target_ticket_id",
            case.expected.target_ticket_id,
            proposal.target_ticket_id if proposal else None,
        ),
        _assertion(
            "proposal_expected_version",
            case.expected.proposal_expected_version,
            proposal.expected_version if proposal else None,
        ),
        _assertion(
            "decision_reason_codes_contains",
            True,
            set(case.expected.decision_reason_codes_contains)
            <= set(result.decision.reason_codes),
        ),
        _assertion(
            "minimum_trace_steps",
            True,
            len(result.trace) >= case.expected.minimum_trace_steps,
        ),
        _assertion("evidence_valid", case.expected.evidence_valid, evidence_valid),
        _assertion("draft_safe", case.expected.draft_safe, draft_safe),
        _assertion("trace_redacted", case.expected.trace_redacted, trace_redacted),
    ]
    executed_at = datetime.now(UTC)
    return EvalRun(
        execution_id=f"{case.case_id}-{executed_at:%Y%m%dT%H%M%S%f}-{uuid4().hex[:6]}",
        case_id=case.case_id,
        case_title=case.title,
        executed_at=executed_at,
        passed=all(item.passed for item in assertions),
        assertions=assertions,
        result=result,
        execution_mode=execution_mode,
        extraction_prompt=extraction_prompt,
        drafting_prompt=drafting_prompt,
    )


def execute_eval_cases(
    cases: list[EvalCase],
    *,
    extractor: ExtractorPort | None = None,
    drafter: ResponseDrafterPort | None = None,
    execution_mode: str = "deterministic",
    extraction_prompt: str | None = None,
    drafting_prompt: str | None = None,
) -> list[EvalRun]:
    """Execute selected cases in stable dataset order, one bounded run per case."""

    return [
        execute_eval_case(
            case,
            extractor=extractor,
            drafter=drafter,
            execution_mode=execution_mode,
            extraction_prompt=extraction_prompt,
            drafting_prompt=drafting_prompt,
        )
        for case in cases
    ]
