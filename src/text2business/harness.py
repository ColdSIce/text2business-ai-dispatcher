from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable

from text2business.models import IncomingRequest, JsonValue, RunLimits, RunMetadata, TerminalState


class HarnessGuard:
    """Per-request budgets, deadline and terminal-state guard for bounded execution."""

    def __init__(
        self,
        request: IncomingRequest,
        limits: RunLimits | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limits = limits or RunLimits()
        fingerprint = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        self.run_id = f"run_{fingerprint[:16]}"
        self.trace_id = f"trace_{fingerprint[16:32]}"
        self.tool_calls = 0
        self.model_calls = 0
        self.proposal_calls = 0
        self._seen_tool_signatures: set[str] = set()
        self._clock = clock
        self._started_at = clock()
        self._finished = False

    @property
    def remaining_model_calls(self) -> int:
        """Return the remaining model-call budget for fallback selection."""

        return max(0, self.limits.max_model_calls - self.model_calls)

    def _check_active(self) -> None:
        if self._finished:
            raise RuntimeError("run already reached a terminal state")
        if self._clock() - self._started_at > self.limits.max_run_seconds:
            raise RuntimeError("run timeout exceeded")

    def before_tool(
        self,
        name: str,
        payload: dict[str, JsonValue],
        *,
        proposal: bool = False,
    ) -> None:
        """Consume a unique tool-call slot and reject repeated call signatures."""

        self._check_active()
        if self.tool_calls >= self.limits.max_tool_calls:
            raise RuntimeError("tool call limit exceeded")
        if proposal and self.proposal_calls >= self.limits.max_proposals:
            raise RuntimeError("proposal limit exceeded")
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        signature = hashlib.sha256(f"{name}|{canonical}".encode()).hexdigest()
        if signature in self._seen_tool_signatures:
            raise RuntimeError("duplicate tool signature detected")
        self._seen_tool_signatures.add(signature)
        self.tool_calls += 1
        if proposal:
            self.proposal_calls += 1

    def before_model(self, name: str) -> None:
        """Consume one model-call slot before an external request is attempted."""

        self._check_active()
        if self.model_calls >= self.limits.max_model_calls:
            raise RuntimeError(f"model call limit exceeded before {name}")
        self.model_calls += 1

    def finish(self, terminal_state: TerminalState) -> RunMetadata:
        """Seal the run exactly once and return immutable execution metadata."""

        if self._finished:
            raise RuntimeError("run already reached a terminal state")
        elapsed_ms = max(0, round((self._clock() - self._started_at) * 1000))
        self._finished = True
        return RunMetadata(
            run_id=self.run_id,
            trace_id=self.trace_id,
            terminal_state=terminal_state,
            tool_calls=self.tool_calls,
            model_calls=self.model_calls,
            proposal_calls=self.proposal_calls,
            elapsed_ms=elapsed_ms,
            limits=self.limits,
        )
