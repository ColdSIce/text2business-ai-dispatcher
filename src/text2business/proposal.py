from __future__ import annotations

import hashlib
import json

from text2business.models import (
    Action,
    Asset,
    CapacityAssessment,
    Customer,
    DraftResponse,
    ExtractedFacts,
    IncomingRequest,
    PriorityAssessment,
    RepeatAssessment,
    Site,
    SlaAssessment,
    Ticket,
    TicketChangeProposal,
)


def stable_source_request_id(request: IncomingRequest) -> str:
    """Return the channel ID or a stable digest of the normalized request envelope."""

    if request.source_request_id:
        return request.source_request_id
    payload = request.model_dump(mode="json", exclude={"source_request_id"})
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"derived-{hashlib.sha256(canonical.encode()).hexdigest()}"


def build_ticket_change_proposal(
    request: IncomingRequest,
    customer: Customer,
    site: Site,
    asset: Asset,
    facts: ExtractedFacts,
    priority: PriorityAssessment,
    sla: SlaAssessment,
    repeat: RepeatAssessment,
    *,
    open_ticket: Ticket | None,
) -> TicketChangeProposal:
    """Build one deterministic dry-run proposal from canonical entities."""

    action = Action.UPDATE_EXISTING if open_ticket else Action.CREATE_NEW
    target = open_ticket.ticket_id if open_ticket else None
    idempotency_parts = {
        "source_request_id": stable_source_request_id(request),
        "action": action,
        "customer_id": customer.customer_id,
        "site_id": site.site_id,
        "asset_id": asset.asset_id,
        "target_ticket_id": target,
        "related_ticket_id": repeat.related_ticket_id,
    }
    canonical = json.dumps(idempotency_parts, sort_keys=True, ensure_ascii=False)
    return TicketChangeProposal(
        idempotency_key=hashlib.sha256(canonical.encode()).hexdigest(),
        expected_version=open_ticket.version if open_ticket else 0,
        operation=action,
        target_ticket_id=target,
        related_ticket_id=(
            repeat.related_ticket_id if repeat.repeat_after_resolution else None
        ),
        proposed_payload={
            "customer_id": customer.customer_id,
            "site_id": site.site_id,
            "asset_id": asset.asset_id,
            "summary": str(facts.problem.value) if facts.problem else request.text,
            "priority": priority.effective,
            "sla_deadline": sla.deadline.isoformat(),
            "source_channel": request.channel,
            "source_request_id": stable_source_request_id(request),
            "repeat_after_resolution": repeat.repeat_after_resolution,
        },
    )


def deterministic_response(
    asset: Asset | None,
    site: Site | None,
    priority: PriorityAssessment | None,
    sla: SlaAssessment | None,
    capacity: CapacityAssessment | None,
    *,
    clarification: str | None = None,
    handed_off: bool = False,
) -> DraftResponse:
    """Create a truthful fallback response without promising an engineer visit."""

    if clarification:
        return DraftResponse(body=clarification)
    if handed_off or not all((asset, site, priority, sla)):
        return DraftResponse(body="Обращение передано диспетчеру для ручной проверки.")
    availability = ""
    if capacity and capacity.next_available_at:
        availability = " Доступность сервисной команды проверяется диспетчером."
    body = (
        f"Приняли обращение по {asset.local_code} на объекте {site.address}. "
        f"Предварительный приоритет — {priority.effective}; срок содержательного "
        f"ответа по договору — до {sla.deadline:%d.%m.%Y %H:%M %Z}."
        f"{availability} Предложение ожидает подтверждения диспетчера."
    )
    return DraftResponse(body=body)
