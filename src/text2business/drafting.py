from __future__ import annotations

import json
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

    SYSTEM_PROMPT = (
        "Write a concise Russian customer-service draft from confirmed fields only. "
        "Do not change priority, SLA, action or identifiers. Never promise engineer "
        "arrival or capacity. Return only the supplied JSON schema."
    )

    def __init__(self, client: StructuredGatewayClient) -> None:
        self.client = client

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
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=json.dumps(payload, ensure_ascii=False),
                response_model=DraftResponse,
            )
            return DraftResponse.model_validate_json(raw)
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
