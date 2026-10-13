from __future__ import annotations

from text2business.evals import execute_eval_cases
from text2business.scenarios import EVAL_DATASET


def test_eval_dataset_is_versioned_unique_and_covers_major_risks() -> None:
    case_ids = [case.case_id for case in EVAL_DATASET.cases]
    categories = {case.category for case in EVAL_DATASET.cases}

    assert EVAL_DATASET.version == "1.0.0"
    assert len(case_ids) == 11
    assert len(case_ids) == len(set(case_ids))
    assert {"happy_path", "repeat", "sla", "priority", "identity", "security"} <= categories
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

    assert len(positive_runs) == 5
    assert len(negative_runs) == 6
    assert all(run.passed for run in [*positive_runs, *negative_runs])
    no_proposal = {"ambiguous", "missing_identity", "conflict", "approval", "injection"}
    assert all(
        run.result.proposal is None
        for run in negative_runs
        if run.case_id in no_proposal
    )
