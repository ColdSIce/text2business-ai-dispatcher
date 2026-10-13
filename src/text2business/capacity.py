from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from text2business.models import (
    Asset,
    CapacityAssessment,
    CapacityFeasibility,
    EvidenceFact,
    ServiceCapacity,
    Site,
)


def parse_requested_deadline(
    fact: EvidenceFact | None,
    received_at: datetime,
    site_timezone: str,
) -> datetime | None:
    """Resolve an extracted ISO or simple Russian relative deadline in site time."""

    if fact is None:
        return None
    raw = str(fact.value)
    try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed.astimezone(ZoneInfo(site_timezone))
    except ValueError:
        pass

    match = re.search(r"сегодня\s+до\s+(\d{1,2}):(\d{2})", f"{raw} {fact.evidence}", re.IGNORECASE)
    if match:
        local = received_at.astimezone(ZoneInfo(site_timezone))
        return local.replace(
            hour=int(match.group(1)),
            minute=int(match.group(2)),
            second=0,
            microsecond=0,
        )
    return None


def assess_capacity(
    asset: Asset,
    site: Site,
    capacity: ServiceCapacity | None,
    requested_by: datetime | None,
) -> CapacityAssessment:
    """Compare informational availability with a request without making a promise."""

    if capacity is None:
        return CapacityAssessment(
            service_group=asset.service_group,
            region=site.region,
            next_available_at=None,
            customer_requested_by=requested_by,
            feasibility=CapacityFeasibility.UNKNOWN,
            reason_codes=["CAPACITY_UNKNOWN"],
        )
    if requested_by is not None and capacity.next_available_at > requested_by:
        feasibility = CapacityFeasibility.REQUESTED_TIME_UNCONFIRMED
        reasons = ["CAPACITY_AFTER_CUSTOMER_REQUEST", "NO_VISIT_PROMISE"]
    else:
        feasibility = CapacityFeasibility.AVAILABLE
        reasons = ["CAPACITY_AVAILABLE", "NO_VISIT_PROMISE"]
    return CapacityAssessment(
        service_group=asset.service_group,
        region=site.region,
        next_available_at=capacity.next_available_at,
        customer_requested_by=requested_by,
        feasibility=feasibility,
        reason_codes=reasons,
    )
