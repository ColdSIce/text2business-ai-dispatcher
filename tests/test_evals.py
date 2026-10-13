from __future__ import annotations

from text2business.evals import calculate_eval_metrics, execute_eval_cases
from text2business.scenarios import EVAL_DATASET


def test_eval_dataset_is_versioned_unique_and_covers_major_risks() -> None:
    case_ids = [case.case_id for case in EVAL_DATASET.cases]
    categories = {case.category for case in EVAL_DATASET.cases}

    assert EVAL_DATASET.version == "3.0.0"
    assert len(case_ids) == 100
    assert len(case_ids) == len(set(case_ids))
    assert len({case.request.source_request_id for case in EVAL_DATASET.cases}) == 100
    assert len({case.request.text for case in EVAL_DATASET.cases}) >= 90
    assert {
        "happy_path",
        "repeat",
        "sla",
        "priority",
        "identity",
        "security",
        "failure",
    } <= categories
    assert {case.polarity for case in EVAL_DATASET.cases} == {"positive", "negative"}


def test_all_packaged_eval_cases_match_declared_expectations() -> None:
    runs = execute_eval_cases(EVAL_DATASET.cases)

    failures = {
        run.case_id: [item.name for item in run.assertions if not item.passed]
        for run in runs
        if not run.passed
    }
    assert failures == {}
    assert all(run.result.trace for run in runs)


def test_positive_and_negative_suites_are_both_executable() -> None:
    positive = [case for case in EVAL_DATASET.cases if case.polarity == "positive"]
    negative = [case for case in EVAL_DATASET.cases if case.polarity == "negative"]

    positive_runs = execute_eval_cases(positive)
    negative_runs = execute_eval_cases(negative)

    assert len(positive_runs) == 50
    assert len(negative_runs) == 50
    assert all(run.passed for run in [*positive_runs, *negative_runs])
    assert all(
        (run.result.proposal is not None) == case.expected.expects_proposal
        for case, run in zip(negative, negative_runs, strict=True)
    )


def test_metrics_report_exposes_precision_recall_and_safety() -> None:
    runs = execute_eval_cases(EVAL_DATASET.cases)
    report = calculate_eval_metrics(runs)

    assert report.cases == 100
    assert report.case_pass_rate == 1
    assert report.assertion_pass_rate == 1
    assert report.unsafe_proposals == 0
    assert report.unsafe_drafts == 0
    assert report.unredacted_traces == 0
    assert all(metric.macro_f1 == 1 for metric in report.classification)

    first = runs[0]
    broken_assertions = [
        assertion.model_copy(update={"actual": "handoff_to_dispatcher", "passed": False})
        if assertion.name == "action"
        else assertion
        for assertion in first.assertions
    ]
    broken = first.model_copy(update={"passed": False, "assertions": broken_assertions})
    degraded = calculate_eval_metrics([broken, *runs[1:]])
    action = next(metric for metric in degraded.classification if metric.field == "action")

    assert degraded.case_pass_rate == 0.99
    assert action.accuracy == 0.99
    assert action.macro_precision < 1
    assert action.macro_recall < 1
