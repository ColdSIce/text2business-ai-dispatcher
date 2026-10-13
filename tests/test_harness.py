import pytest

from text2business.harness import HarnessGuard
from text2business.models import RunLimits
from text2business.scenarios import SCENARIOS


def test_harness_ids_are_stable_for_same_request() -> None:
    first = HarnessGuard(SCENARIOS["full"])
    second = HarnessGuard(SCENARIOS["full"])

    assert first.run_id == second.run_id
    assert first.trace_id == second.trace_id


def test_harness_stops_excess_tool_and_mutation_calls() -> None:
    guard = HarnessGuard(
        SCENARIOS["full"], RunLimits(max_tool_calls=2, max_model_calls=0)
    )

    guard.before_tool(mutation=True)
    with pytest.raises(RuntimeError, match="mutation limit"):
        guard.before_tool(mutation=True)

    guard.before_tool()
    with pytest.raises(RuntimeError, match="tool call limit"):
        guard.before_tool()

