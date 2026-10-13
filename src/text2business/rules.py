from __future__ import annotations

import re
from datetime import timedelta

from text2business.models import (
    Asset,
    Contract,
    ExtractedFacts,
    IncomingRequest,
    PriorityAssessment,
    SlaAssessment,
)


def assess_priority(asset: Asset, facts: ExtractedFacts) -> PriorityAssessment:
    backup = facts.backup_available
    has_backup = bool(backup and backup.value is True)
    if asset.criticality == "high" and not has_backup:
        return PriorityAssessment(priority="P1", reason_codes=["HIGH_CRITICALITY", "NO_BACKUP"])
    if asset.criticality == "high" or not has_backup:
        return PriorityAssessment(priority="P2", reason_codes=["ELEVATED_OPERATIONAL_RISK"])
    return PriorityAssessment(priority="P3", reason_codes=["BACKUP_AVAILABLE", "MEDIUM_CRITICALITY"])


def calculate_sla(request: IncomingRequest, contract: Contract) -> SlaAssessment:
    match = re.fullmatch(r"(\d+) minutes", contract.response_sla)
    if not match or contract.service_window != "24x7":
        raise ValueError("This vertical slice supports only a 24x7 minute-based SLA")
    deadline = request.received_at + timedelta(minutes=int(match.group(1)))
    return SlaAssessment(
        contract_id=contract.contract_id,
        response_sla=contract.response_sla,
        deadline=deadline,
        reason_codes=["CONTRACT_SLA", "SERVICE_WINDOW_24X7"],
    )

