from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from text2business.models import Contract, Site, SlaAssessment, SlaKind, Ticket


BUSINESS_START = time(9, 0)
BUSINESS_END = time(18, 0)


def _next_weekday(day: datetime, *, include_current: bool) -> datetime:
    candidate = day if include_current else day + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def _normalize_business_start(value: datetime) -> datetime:
    """Move an instant to the first available minute of the business calendar."""

    if value.weekday() >= 5:
        day = _next_weekday(value, include_current=True)
        return day.replace(hour=9, minute=0, second=0, microsecond=0)
    if value.time() < BUSINESS_START:
        return value.replace(hour=9, minute=0, second=0, microsecond=0)
    if value.time() >= BUSINESS_END:
        day = _next_weekday(value, include_current=False)
        return day.replace(hour=9, minute=0, second=0, microsecond=0)
    return value


def add_business_hours(value: datetime, hours: int) -> datetime:
    """Add weekday 09:00-18:00 business hours, carrying remainder across days."""

    current = _normalize_business_start(value)
    remaining = timedelta(hours=hours)
    while remaining:
        end = current.replace(hour=18, minute=0, second=0, microsecond=0)
        available = end - current
        if remaining <= available:
            return current + remaining
        remaining -= available
        current = _normalize_business_start(end)
    return current


def next_business_day_close(value: datetime) -> datetime:
    """Return 18:00 of the next Monday-Friday day in the same timezone."""

    day = _next_weekday(value, include_current=False)
    return day.replace(hour=18, minute=0, second=0, microsecond=0)


def calculate_sla(
    received_at: datetime,
    site: Site,
    contract: Contract,
    *,
    open_repeat_ticket: Ticket | None = None,
) -> SlaAssessment:
    """Calculate a contractual response deadline or preserve an open ticket SLA."""

    zone = ZoneInfo(site.timezone)
    local_received = received_at.astimezone(zone)
    if contract.plan == "Gold":
        kind = SlaKind.CALENDAR_MINUTES
    elif contract.plan == "Standard":
        kind = SlaKind.BUSINESS_HOURS
    else:
        kind = SlaKind.NEXT_BUSINESS_DAY

    if open_repeat_ticket is not None:
        return SlaAssessment(
            contract_id=contract.contract_id,
            kind=kind,
            response_sla=contract.response_sla,
            deadline=open_repeat_ticket.sla_deadline.astimezone(zone),
            timezone=site.timezone,
            reason_codes=["OPEN_REPEAT", "ORIGINAL_SLA_PRESERVED"],
            source_ticket_id=open_repeat_ticket.ticket_id,
        )

    if contract.plan == "Gold":
        deadline = local_received + timedelta(minutes=60)
        reasons = ["CONTRACT_SLA", "SERVICE_WINDOW_24X7"]
    elif contract.plan == "Standard":
        deadline = add_business_hours(local_received, 4)
        reasons = ["CONTRACT_SLA", "FOUR_BUSINESS_HOURS", "WEEKDAYS_ONLY"]
    elif contract.plan == "Basic":
        deadline = next_business_day_close(local_received)
        reasons = ["CONTRACT_SLA", "NEXT_BUSINESS_DAY_18_00", "WEEKDAYS_ONLY"]
    else:  # pragma: no cover - protected by the Contract literal
        raise ValueError(f"unsupported contract plan: {contract.plan}")

    return SlaAssessment(
        contract_id=contract.contract_id,
        kind=kind,
        response_sla=contract.response_sla,
        deadline=deadline,
        timezone=site.timezone,
        reason_codes=reasons,
    )
