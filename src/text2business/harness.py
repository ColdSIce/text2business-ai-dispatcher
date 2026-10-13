from __future__ import annotations

import hashlib

from text2business.models import IncomingRequest, RunLimits, RunMetadata, TerminalState


class HarnessGuard:
    """Per-request guardrail state for the local demo harness."""

    def __init__(self, request: IncomingRequest, limits: RunLimits | None = None) -> None:
        self.limits = limits or RunLimits()
        fingerprint = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        self.run_id = f"run_{fingerprint[:16]}"
        self.trace_id = f"trace_{fingerprint[16:32]}"
        self.tool_calls = 0
        self.model_calls = 0
        self.mutation_calls = 0

    def before_tool(self, *, mutation: bool = False) -> None:
        if self.tool_calls >= self.limits.max_tool_calls:
            raise RuntimeError("tool call limit exceeded")
        if mutation and self.mutation_calls >= self.limits.max_mutations:
            raise RuntimeError("mutation limit exceeded")
        self.tool_calls += 1
        if mutation:
            self.mutation_calls += 1

    def before_model(self) -> None:
        if self.model_calls >= self.limits.max_model_calls:
            raise RuntimeError("model call limit exceeded")
        self.model_calls += 1

    def finish(self, terminal_state: TerminalState) -> RunMetadata:
        return RunMetadata(
            run_id=self.run_id,
            trace_id=self.trace_id,
            terminal_state=terminal_state,
            tool_calls=self.tool_calls,
            model_calls=self.model_calls,
            mutation_calls=self.mutation_calls,
            limits=self.limits,
        )

