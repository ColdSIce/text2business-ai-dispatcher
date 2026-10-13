from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Provenance(StrEnum):
    MESSAGE = "message"
    ATTACHMENT = "attachment"
    INTERNAL_LOOKUP = "internal_lookup"
    ASSUMPTION = "assumption"


class TraceKind(StrEnum):
    EXTRACTION = "extraction"
    TOOL = "tool"
    RULE = "rule"
    MUTATION = "mutation"


class Action(StrEnum):
    CREATE_NEW = "create_new"
    UPDATE_EXISTING = "update_existing"
    REQUEST_CLARIFICATION = "request_clarification"
    HANDOFF_TO_DISPATCHER = "handoff_to_dispatcher"


class EvidenceFact(StrictModel):
    value: str | bool
    evidence: str
    confidence: float = Field(ge=0, le=1)
    provenance: Provenance


class ExtractedFacts(StrictModel):
    customer: EvidenceFact | None = None
    site: EvidenceFact | None = None
    asset: EvidenceFact | None = None
    problem: EvidenceFact | None = None
    backup_available: EvidenceFact | None = None


class IncomingRequest(StrictModel):
    channel: str
    sender: str
    received_at: datetime
    text: str = Field(min_length=1)
    attachment_text: str | None = None

    @field_validator("received_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("received_at must include a timezone")
        return value


class Site(StrictModel):
    site_id: str
    customer_id: str
    customer_name: str
    address: str
    timezone: str


class Asset(StrictModel):
    asset_id: str
    site_id: str
    local_code: str
    asset_type: str
    criticality: Literal["low", "medium", "high"]


class Contract(StrictModel):
    contract_id: str
    site_id: str
    plan: str
    response_sla: str
    service_window: str
    coverage: list[str]


class Ticket(StrictModel):
    ticket_id: str
    asset_id: str
    created_at: datetime
    status: str
    summary: str
    version: int = Field(ge=1)


class CorporateData(StrictModel):
    current_time: datetime
    sites: list[Site]
    assets: list[Asset]
    contracts: list[Contract]
    open_tickets: list[Ticket]


class SiteMatch(StrictModel):
    site: Site
    score: int = Field(ge=0)
    matched_by: list[str]


class AssetMatch(StrictModel):
    asset: Asset
    matched_by: list[str]


class FindSiteInput(StrictModel):
    query: str


class FindSiteOutput(StrictModel):
    matches: list[SiteMatch]


class FindAssetsInput(StrictModel):
    site_id: str
    query: str


class FindAssetsOutput(StrictModel):
    matches: list[AssetMatch]


class GetContractInput(StrictModel):
    site_id: str


class GetContractOutput(StrictModel):
    contract: Contract | None


class FindOpenTicketsInput(StrictModel):
    customer_id: str
    site_id: str
    asset_id: str


class FindOpenTicketsOutput(StrictModel):
    tickets: list[Ticket]


class PriorityAssessment(StrictModel):
    priority: Literal["P1", "P2", "P3", "P4"]
    reason_codes: list[str]


class SlaAssessment(StrictModel):
    contract_id: str
    response_sla: str
    deadline: datetime
    reason_codes: list[str]


class Decision(StrictModel):
    action: Action
    reason_codes: list[str]
    explanation: str
    requires_human_confirmation: bool


class TicketMutationInput(StrictModel):
    idempotency_key: str = Field(min_length=16)
    expected_version: int = Field(ge=0)
    operation: Literal[Action.CREATE_NEW, Action.UPDATE_EXISTING]
    proposed_payload: dict[str, JsonValue]
    dry_run: Literal[True] = True
    requires_human_confirmation: Literal[True] = True


class TicketMutationOutput(StrictModel):
    accepted: bool
    dry_run: Literal[True] = True
    proposal: TicketMutationInput
    warnings: list[str]


class TraceEvent(StrictModel):
    step: int = Field(ge=1)
    kind: TraceKind
    name: str
    input: dict[str, JsonValue]
    output: dict[str, JsonValue]


class CaseResult(StrictModel):
    request: IncomingRequest
    facts: ExtractedFacts
    site_candidates: list[SiteMatch]
    asset_candidates: list[AssetMatch]
    resolved_site: Site | None
    resolved_asset: Asset | None
    contract: Contract | None
    open_tickets: list[Ticket]
    priority: PriorityAssessment | None
    sla: SlaAssessment | None
    decision: Decision
    mutation: TicketMutationOutput | None
    draft_response: str
    clarification_questions: list[str]
    warnings: list[str]
    trace: list[TraceEvent]

