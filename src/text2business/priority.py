from __future__ import annotations

from text2business.models import (
    Asset,
    BackupStatus,
    ExtractedFacts,
    Priority,
    PriorityAssessment,
    PriorityOverride,
)


def _is_true(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.casefold() == "true")


def _backup_status(facts: ExtractedFacts) -> BackupStatus:
    if facts.backup_status is None:
        return BackupStatus.UNKNOWN
    try:
        return BackupStatus(str(facts.backup_status.value))
    except ValueError:
        return BackupStatus.UNKNOWN


def assess_priority(asset: Asset, facts: ExtractedFacts) -> PriorityAssessment:
    """Calculate P1-P4 from current operational risk, never from repeat status."""

    backup = _backup_status(facts)
    safety = bool(facts.safety_threat and _is_true(facts.safety_threat.value))
    outage = bool(facts.complete_outage and _is_true(facts.complete_outage.value))
    rising = bool(facts.temperature_rising and _is_true(facts.temperature_rising.value))
    has_problem = bool(
        facts.problem
        or facts.symptoms
        or facts.temperature_c
        or facts.temperature_rising
        or facts.complete_outage
        or facts.safety_threat
    )
    informational = bool(
        facts.informational_request and _is_true(facts.informational_request.value)
    )

    if informational and not has_problem:
        calculated = Priority.P4
        reasons = ["INFORMATIONAL_REQUEST"]
    elif not has_problem:
        calculated = Priority.P4
        reasons = ["INFORMATIONAL_OR_NONCRITICAL"]
    elif safety:
        calculated = Priority.P1
        reasons = ["SAFETY_THREAT"]
    elif outage and backup != BackupStatus.CONFIRMED:
        calculated = Priority.P1
        reasons = ["COMPLETE_OUTAGE", "BACKUP_NOT_CONFIRMED"]
    elif rising:
        calculated = Priority.P2
        reasons = ["TEMPERATURE_RISING"]
    elif asset.criticality == "high":
        calculated = Priority.P2
        reasons = ["HIGH_CRITICALITY"]
    elif backup != BackupStatus.CONFIRMED:
        calculated = Priority.P2
        reasons = ["BACKUP_NOT_CONFIRMED"]
    else:
        calculated = Priority.P3
        reasons = ["MALFUNCTION", "BACKUP_CONFIRMED", "NO_IMMEDIATE_PRODUCT_RISK"]

    return PriorityAssessment(
        calculated=calculated,
        effective=calculated,
        reason_codes=reasons,
    )


def apply_priority_override(
    assessment: PriorityAssessment,
    override: PriorityOverride,
) -> PriorityAssessment:
    """Apply an auditable human override while preserving the calculated value."""

    return assessment.model_copy(
        update={
            "effective": override.priority,
            "override": override,
            "reason_codes": [*assessment.reason_codes, "DISPATCHER_OVERRIDE"],
        }
    )
