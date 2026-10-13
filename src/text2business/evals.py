from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import JsonValue

from text2business.drafting import ResponseDrafterPort
from text2business.extractor import ExtractorPort
from text2business.models import EvalAssertion, EvalCase, EvalRun
from text2business.workflow import run_case


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

    result = run_case(case.request, extractor=extractor, drafter=drafter)
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
