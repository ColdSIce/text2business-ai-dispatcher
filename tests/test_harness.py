from __future__ import annotations

import pytest

from text2business.harness import HarnessGuard
from text2business.models import RunLimits, TerminalState
from text2business.scenarios import SCENARIOS


def test_harness_ids_are_stable_for_same_request() -> None:
    first = HarnessGuard(SCENARIOS["full"])
    second = HarnessGuard(SCENARIOS["full"])
    assert first.run_id == second.run_id
    assert first.trace_id == second.trace_id


def test_harness_blocks_duplicate_tool_signature_and_limits() -> None:
    guard = HarnessGuard(SCENARIOS["full"], RunLimits(max_tool_calls=2, max_model_calls=1))
    guard.before_tool("lookup", {"id": "1"})
    with pytest.raises(RuntimeError, match="duplicate tool signature"):
        guard.before_tool("lookup", {"id": "1"})
    guard.before_tool("lookup", {"id": "2"}, proposal=True)
    with pytest.raises(RuntimeError, match="tool call limit"):
        guard.before_tool("lookup", {"id": "3"})
    guard.before_model("extract")
    with pytest.raises(RuntimeError, match="model call limit"):
        guard.before_model("draft")


def test_harness_blocks_timeout_and_calls_after_terminal_state() -> None:
    now = [0.0]
    guard = HarnessGuard(
        SCENARIOS["full"],
        RunLimits(max_run_seconds=1),
        clock=lambda: now[0],
    )
    now[0] = 2.0
    with pytest.raises(RuntimeError, match="run timeout"):
        guard.before_tool("lookup", {"id": "1"})
    metadata = guard.finish(TerminalState.FAILED)
    assert metadata.elapsed_ms == 2000
    with pytest.raises(RuntimeError, match="terminal state"):
        guard.before_model("extract")

