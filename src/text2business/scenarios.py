from __future__ import annotations

from importlib.resources import files

from text2business.models import EvalCase, EvalDataset, IncomingRequest


def load_eval_dataset() -> EvalDataset:
    """Load and validate the packaged, human-reviewable regression dataset."""

    path = files("text2business").joinpath("data/eval_cases.json")
    return EvalDataset.model_validate_json(path.read_bytes())


EVAL_DATASET = load_eval_dataset()
EVAL_CASES: dict[str, EvalCase] = {case.case_id: case for case in EVAL_DATASET.cases}

# Backward-compatible read-only request map used by the CLI and existing callers.
SCENARIOS: dict[str, IncomingRequest] = {
    case.case_id: case.request for case in EVAL_DATASET.cases
}
