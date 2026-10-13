from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from text2business.models import RepeatAssessment, RepeatKind, Ticket


@dataclass(frozen=True)
class RepeatResolution:
    """Internal repeat result with the exact ticket selected for an action."""

    assessment: RepeatAssessment
    open_ticket: Ticket | None
    recent_closed_ticket: Ticket | None
    multiple_open: bool


def classify_repeat(
    tickets: list[Ticket],
    received_at: datetime,
    *,
    closed_window_days: int = 30,
) -> RepeatResolution:
    """Classify exact scoped history without raising priority or resetting SLA."""

    open_tickets = [ticket for ticket in tickets if not ticket.status.is_terminal]
    if len(open_tickets) > 1:
        return RepeatResolution(
            assessment=RepeatAssessment(
                kind=RepeatKind.OPEN,
                contact_count=len(tickets) + 1,
                reason_codes=["MULTIPLE_OPEN_TICKETS"],
            ),
            open_ticket=None,
            recent_closed_ticket=None,
            multiple_open=True,
        )
    if len(open_tickets) == 1:
        ticket = open_tickets[0]
        return RepeatResolution(
            assessment=RepeatAssessment(
                kind=RepeatKind.OPEN,
                related_ticket_id=ticket.ticket_id,
                contact_count=len(tickets) + 1,
                reason_codes=["SAME_CUSTOMER_SITE_ASSET", "OPEN_TICKET_FOUND"],
            ),
            open_ticket=ticket,
            recent_closed_ticket=None,
            multiple_open=False,
        )

    window = timedelta(days=closed_window_days)
    eligible_closed = [
        ticket
        for ticket in tickets
        if ticket.status.is_terminal
        and ticket.closed_at is not None
        and timedelta(0) <= received_at - ticket.closed_at <= window
    ]
    eligible_closed.sort(key=lambda item: (item.closed_at, item.ticket_id), reverse=True)
    if eligible_closed:
        ticket = eligible_closed[0]
        return RepeatResolution(
            assessment=RepeatAssessment(
                kind=RepeatKind.CLOSED,
                related_ticket_id=ticket.ticket_id,
                repeat_after_resolution=True,
                contact_count=len(tickets) + 1,
                reason_codes=["SAME_CUSTOMER_SITE_ASSET", "CLOSED_WITHIN_30_DAYS"],
            ),
            open_ticket=None,
            recent_closed_ticket=ticket,
            multiple_open=False,
        )

    return RepeatResolution(
        assessment=RepeatAssessment(
            kind=RepeatKind.NONE,
            contact_count=len(tickets) + 1,
            reason_codes=["NO_OPEN_OR_RECENT_CLOSED_TICKET"],
        ),
        open_ticket=None,
        recent_closed_ticket=None,
        multiple_open=False,
    )
