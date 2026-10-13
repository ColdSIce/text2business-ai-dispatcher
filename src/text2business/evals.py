from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import JsonValue

from text2business.drafting import ResponseDrafterPort, validate_draft_safety
from text2business.extractor import ExtractorPort, validate_evidence
from text2business.models import (
    ClassificationMetrics,
    EvalAssertion,
    EvalCase,
    EvalMetricsReport,
    EvalRun,
)
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
    max_workers: int = 1,
) -> list[EvalRun]:
    """Execute independent bounded cases, retaining stable dataset order."""

    if max_workers < 1:
        raise ValueError("max_workers must be positive")

    def execute(case: EvalCase) -> EvalRun:
        return execute_eval_case(
            case,
            extractor=extractor,
            drafter=drafter,
            execution_mode=execution_mode,
            extraction_prompt=extraction_prompt,
            drafting_prompt=drafting_prompt,
        )

    if max_workers == 1 or len(cases) < 2:
        return [execute(case) for case in cases]
    with ThreadPoolExecutor(max_workers=min(max_workers, len(cases))) as pool:
        return list(pool.map(execute, cases))


CLASSIFICATION_FIELDS = (
    "action",
    "review_status",
    "priority",
    "repeat_kind",
    "resolved_customer_id",
    "resolved_site_id",
    "resolved_asset_id",
    "sla_kind",
    "capacity_feasibility",
    "expects_proposal",
    "terminal_state",
)


def _metric_label(value: JsonValue) -> str:
    """Normalize nullable and boolean JSON labels for readable metric output."""

    if value is None:
        return "∅"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _classification_metrics(
    field: str,
    expected: list[str],
    actual: list[str],
) -> ClassificationMetrics:
    """Calculate exact single-label macro/micro precision, recall and F1."""

    labels = sorted(set(expected) | set(actual))
    precisions: list[float] = []
    recalls: list[float] = []
    f1_scores: list[float] = []
    total_tp = total_fp = total_fn = 0
    for label in labels:
        true_positive = sum(
            expected_value == label and actual_value == label
            for expected_value, actual_value in zip(expected, actual, strict=True)
        )
        false_positive = sum(
            expected_value != label and actual_value == label
            for expected_value, actual_value in zip(expected, actual, strict=True)
        )
        false_negative = sum(
            expected_value == label and actual_value != label
            for expected_value, actual_value in zip(expected, actual, strict=True)
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1_scores.append(f1)
        total_tp += true_positive
        total_fp += false_positive
        total_fn += false_negative

    samples = len(expected)
    accuracy = sum(left == right for left, right in zip(expected, actual, strict=True))
    accuracy = accuracy / samples if samples else 0.0
    micro_precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if micro_precision + micro_recall
        else 0.0
    )
    count = len(labels)
    return ClassificationMetrics(
        field=field,
        samples=samples,
        labels=labels,
        accuracy=accuracy,
        macro_precision=sum(precisions) / count if count else 0.0,
        macro_recall=sum(recalls) / count if count else 0.0,
        macro_f1=sum(f1_scores) / count if count else 0.0,
        micro_precision=micro_precision,
        micro_recall=micro_recall,
        micro_f1=micro_f1,
    )


def calculate_eval_metrics(runs: list[EvalRun]) -> EvalMetricsReport:
    """Aggregate exact, classification and safety metrics for UI comparison."""

    assertion_maps = [
        {assertion.name: assertion for assertion in run.assertions}
        for run in runs
    ]
    classification: list[ClassificationMetrics] = []
    for field in CLASSIFICATION_FIELDS:
        selected = [items[field] for items in assertion_maps if field in items]
        classification.append(
            _classification_metrics(
                field,
                [_metric_label(item.expected) for item in selected],
                [_metric_label(item.actual) for item in selected],
            )
        )

    all_assertions = [assertion for run in runs for assertion in run.assertions]
    passed_cases = sum(run.passed for run in runs)
    passed_assertions = sum(assertion.passed for assertion in all_assertions)
    proposal_assertions = [
        items["expects_proposal"] for items in assertion_maps if "expects_proposal" in items
    ]
    draft_assertions = [items["draft_safe"] for items in assertion_maps if "draft_safe" in items]
    trace_assertions = [
        items["trace_redacted"] for items in assertion_maps if "trace_redacted" in items
    ]
    return EvalMetricsReport(
        cases=len(runs),
        passed_cases=passed_cases,
        case_pass_rate=passed_cases / len(runs) if runs else 0.0,
        assertions=len(all_assertions),
        passed_assertions=passed_assertions,
        assertion_pass_rate=(
            passed_assertions / len(all_assertions) if all_assertions else 0.0
        ),
        classification=classification,
        unsafe_proposals=sum(
            item.expected is False and item.actual is True for item in proposal_assertions
        ),
        unsafe_drafts=sum(item.actual is False for item in draft_assertions),
        unredacted_traces=sum(item.actual is False for item in trace_assertions),
    )
