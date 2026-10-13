from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Protocol

from pydantic import ValidationError

from text2business.gateway import GatewayError, StructuredGatewayClient
from text2business.models import (
    Asset,
    CapacityAssessment,
    Decision,
    DraftResponse,
    PriorityAssessment,
    Site,
    SlaAssessment,
)
from text2business.proposal import deterministic_response
from text2business.prompts import DEFAULT_DRAFTING_PROMPT


_UNCONFIRMED_PROMISE_PATTERNS = (
    re.compile(r"(?:инженер|специалист|мастер).{0,40}(?:гарантированно\s+)?приед", re.IGNORECASE),
    re.compile(r"(?:выезд|визит|слот).{0,30}(?:подтвержд|забронир|назначен)", re.IGNORECASE),
    re.compile(r"будет\s+на\s+объекте\s+(?:сегодня|завтра|к\s+\d)", re.IGNORECASE),
    re.compile(r"(?:устраним|починим|восстановим).{0,30}(?:до|к)\s+\d{1,2}[:.]\d{2}", re.IGNORECASE),
)


def validate_draft_safety(draft: DraftResponse) -> None:
    """Reject model text that turns informational capacity into a customer promise."""

    if any(pattern.search(draft.body) for pattern in _UNCONFIRMED_PROMISE_PATTERNS):
        raise ValueError("draft contains an unconfirmed visit or resolution promise")


class ResponseDrafterPort(Protocol):
    """Boundary for producing editable customer-facing text after the decision."""

    def draft(
        self,
        *,
        asset: Asset | None,
        site: Site | None,
        priority: PriorityAssessment | None,
        sla: SlaAssessment | None,
        capacity: CapacityAssessment | None,
        decision: Decision,
        clarification: str | None,
        on_model_call: Callable[[str], None] | None = None,
    ) -> DraftResponse:
        """Draft text without changing any field of the deterministic result."""


class DeterministicResponseDrafter:
    """Network-free truthful response template used by default and as fallback."""

    def draft(
        self,
        *,
        asset: Asset | None,
        site: Site | None,
        priority: PriorityAssessment | None,
        sla: SlaAssessment | None,
        capacity: CapacityAssessment | None,
        decision: Decision,
        clarification: str | None,
        on_model_call: Callable[[str], None] | None = None,
    ) -> DraftResponse:
        del on_model_call
        return deterministic_response(
            asset,
            site,
            priority,
            sla,
            capacity,
            clarification=clarification,
            handed_off=decision.action.value == "handoff_to_dispatcher",
        )


class GatewayResponseDrafter:
    """Optional second model call constrained to a validated response schema."""

    SYSTEM_PROMPT = DEFAULT_DRAFTING_PROMPT

    def __init__(
        self,
        client: StructuredGatewayClient,
        *,
        system_prompt: str | None = None,
    ) -> None:
        self.client = client
        self.system_prompt = system_prompt or self.SYSTEM_PROMPT

    def draft(
        self,
        *,
        asset: Asset | None,
        site: Site | None,
        priority: PriorityAssessment | None,
        sla: SlaAssessment | None,
        capacity: CapacityAssessment | None,
        decision: Decision,
        clarification: str | None,
        on_model_call: Callable[[str], None] | None = None,
    ) -> DraftResponse:
        callback = on_model_call or (lambda _name: None)
        callback("response_draft")
        payload = {
            "asset": asset.model_dump(mode="json") if asset else None,
            "site": site.model_dump(mode="json") if site else None,
            "priority": priority.model_dump(mode="json") if priority else None,
            "sla": sla.model_dump(mode="json") if sla else None,
            "capacity": capacity.model_dump(mode="json") if capacity else None,
            "decision": decision.model_dump(mode="json"),
            "clarification": clarification,
        }
        try:
            raw = self.client.complete_json(
                system_prompt=self.system_prompt,
                user_prompt=json.dumps(payload, ensure_ascii=False),
                response_model=DraftResponse,
            )
            draft = DraftResponse.model_validate_json(raw)
        except (GatewayError, ValidationError):
            fallback = deterministic_response(
                asset,
                site,
                priority,
                sla,
                capacity,
                clarification=clarification,
                handed_off=decision.action.value == "handoff_to_dispatcher",
            )
            return fallback.model_copy(
                update={"warnings": [*fallback.warnings, "MODEL_DRAFT_FALLBACK"]}
            )
        try:
            validate_draft_safety(draft)
        except ValueError:
            fallback = deterministic_response(
                asset,
                site,
                priority,
                sla,
                capacity,
                clarification=clarification,
                handed_off=decision.action.value == "handoff_to_dispatcher",
            )
            return fallback.model_copy(
                update={"warnings": [*fallback.warnings, "UNSAFE_MODEL_DRAFT_BLOCKED"]}
            )
        return draft
