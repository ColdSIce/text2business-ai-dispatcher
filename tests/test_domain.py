from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from text2business.capacity import assess_capacity
from text2business.models import (
    Asset,
    BackupStatus,
    CapacityFeasibility,
    Contract,
    EvidenceFact,
    ExtractedFacts,
    Priority,
    PriorityOverride,
    Provenance,
    ServiceCapacity,
    Site,
)
from text2business.priority import apply_priority_override, assess_priority
from text2business.sla import add_business_hours, calculate_sla, next_business_day_close


SITE = Site(
    site_id="S-1",
    customer_id="C-1",
    address="Москва",
    region="Moscow",
    timezone="Europe/Moscow",
)
ASSET = Asset(
    asset_id="A-1",
    site_id="S-1",
    local_code="ХУ-1",
    asset_type="unit",
    criticality="medium",
    service_group="refrigeration",
)


def _fact(value: str | bool | float) -> EvidenceFact:
    return EvidenceFact(
        value=value,
        evidence=str(value),
        confidence=1,
        provenance=Provenance.MESSAGE,
    )


@pytest.mark.parametrize(
    ("received", "expected"),
    [
        ("2026-08-14T17:00:00+03:00", "2026-08-17T12:00:00+03:00"),
        ("2026-08-17T07:00:00+03:00", "2026-08-17T13:00:00+03:00"),
        ("2026-08-15T12:00:00+03:00", "2026-08-17T13:00:00+03:00"),
    ],
)
def test_business_hour_math(received: str, expected: str) -> None:
    assert add_business_hours(datetime.fromisoformat(received), 4).isoformat() == expected


def test_next_business_day_close_skips_weekend() -> None:
    value = datetime.fromisoformat("2026-08-14T17:00:00+03:00")
    assert next_business_day_close(value).isoformat() == "2026-08-17T18:00:00+03:00"


def test_calculate_basic_sla() -> None:
    contract = Contract(
        contract_id="K",
        site_id="S-1",
        plan="Basic",
        response_sla="next business day",
        service_window="09:00-18:00 local time, Monday-Friday",
        coverage=[],
    )
    result = calculate_sla(datetime.fromisoformat("2026-08-14T17:00:00+03:00"), SITE, contract)
    assert result.deadline.isoformat() == "2026-08-17T18:00:00+03:00"


def test_priority_uses_explicit_backup_status_not_confidence_threshold() -> None:
    facts = ExtractedFacts(
        problem=_fact("malfunction"),
        backup_status=EvidenceFact(
            value=BackupStatus.CONFIRMED,
            evidence="confirmed",
            confidence=0.51,
            provenance=Provenance.MESSAGE,
        ),
    )
    assert assess_priority(ASSET, facts).effective == Priority.P3


def test_priority_override_preserves_calculated_value_and_requires_reason() -> None:
    assessment = assess_priority(
        ASSET,
        ExtractedFacts(problem=_fact("malfunction"), backup_status=_fact("confirmed")),
    )
    override = PriorityOverride(
        priority=Priority.P2,
        reason="Риск для соседней камеры",
        actor="dispatcher-1",
        changed_at=datetime.fromisoformat("2026-08-13T16:45:00+03:00"),
    )
    updated = apply_priority_override(assessment, override)
    assert updated.calculated == Priority.P3
    assert updated.effective == Priority.P2
    with pytest.raises(ValidationError):
        PriorityOverride(
            priority=Priority.P2,
            reason="",
            actor="dispatcher-1",
            changed_at=override.changed_at,
        )


def test_capacity_does_not_modify_other_assessments() -> None:
    capacity = ServiceCapacity(
        service_group="refrigeration",
        region="Moscow",
        next_available_at=datetime.fromisoformat("2026-08-14T11:00:00+03:00"),
    )
    requested = datetime.fromisoformat("2026-08-13T19:00:00+03:00")
    result = assess_capacity(ASSET, SITE, capacity, requested)
    assert result.feasibility == CapacityFeasibility.REQUESTED_TIME_UNCONFIRMED
