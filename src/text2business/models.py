from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class StrictModel(BaseModel):
    """Base contract that rejects unknown fields instead of silently ignoring them."""

    model_config = ConfigDict(extra="forbid")


class Provenance(StrEnum):
    """Origin of a fact shown to the dispatcher."""

    MESSAGE = "message"
    ATTACHMENT = "attachment"
    INTERNAL_LOOKUP = "internal_lookup"
    ASSUMPTION = "assumption"


class TraceKind(StrEnum):
    """Type of an explainability event in the ordered run trace."""

    EXTRACTION = "extraction"
    TOOL = "tool"
    RULE = "rule"
    MUTATION = "mutation"


class Action(StrEnum):
    """Closed set of business outcomes produced by deterministic rules."""

    CREATE_NEW = "create_new"
    UPDATE_EXISTING = "update_existing"
    REQUEST_CLARIFICATION = "request_clarification"
    HANDOFF_TO_DISPATCHER = "handoff_to_dispatcher"


class TerminalState(StrEnum):
    """Final harness state; runs are never left suspended between user turns."""

    COMPLETED = "completed"
    NEEDS_USER_INPUT = "needs_user_input"
    HANDED_OFF = "handed_off"


class EvidenceFact(StrictModel):
    """One extracted value with its source fragment, confidence and provenance."""

    value: str | bool | float
    evidence: str
    confidence: float = Field(ge=0, le=1)
    provenance: Provenance


class ExtractedFacts(StrictModel):
    """Structured interpretation of untrusted customer text before lookups."""

    customer: EvidenceFact | None = None
    site: EvidenceFact | None = None
    asset: EvidenceFact | None = None
    problem: EvidenceFact | None = None
    symptoms: list[EvidenceFact] = Field(default_factory=list)
    desired_deadline: EvidenceFact | None = None
    backup_available: EvidenceFact | None = None
    previous_contact: EvidenceFact | None = None
    suspicious_instruction: EvidenceFact | None = None


class IncomingRequest(StrictModel):
    """Validated request envelope accepted by the application workflow."""

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
    """Customer service location from the corporate registry."""

    site_id: str
    customer_id: str
    customer_name: str
    address: str
    timezone: str


class Asset(StrictModel):
    """Serviceable equipment installed at exactly one site."""

    asset_id: str
    site_id: str
    local_code: str
    asset_type: str
    criticality: Literal["low", "medium", "high"]


class Contract(StrictModel):
    """Service agreement that supplies SLA, service window and coverage."""

    contract_id: str
    site_id: str
    plan: str
    response_sla: str
    service_window: str
    coverage: list[str]


class Ticket(StrictModel):
    """Existing service ticket used for deterministic duplicate detection."""

    ticket_id: str
    asset_id: str
    created_at: datetime
    status: str
    summary: str
    version: int = Field(ge=1)


class CorporateData(StrictModel):
    """Read-only aggregate loaded from the local corporate JSON fixture."""

    current_time: datetime
    sites: list[Site]
    assets: list[Asset]
    contracts: list[Contract]
    open_tickets: list[Ticket]


class SiteMatch(StrictModel):
    """Candidate site plus deterministic score and explicit match reasons."""

    site: Site
    score: int = Field(ge=0)
    matched_by: list[str]


class AssetMatch(StrictModel):
    """Candidate asset plus the registry fields that matched the query."""

    asset: Asset
    matched_by: list[str]


class FindSiteInput(StrictModel):
    """Input contract for customer and site lookup."""

    query: str


class FindSiteOutput(StrictModel):
    """Output contract returning all ranked site candidates."""

    matches: list[SiteMatch]


class FindAssetsInput(StrictModel):
    """Input contract for an asset lookup restricted to one resolved site."""

    site_id: str
    query: str


class FindAssetsOutput(StrictModel):
    """Output contract returning matching assets without choosing one."""

    matches: list[AssetMatch]


class GetContractInput(StrictModel):
    """Input contract for retrieving the contract of one resolved site."""

    site_id: str


class GetContractOutput(StrictModel):
    """Output contract that explicitly represents a missing contract."""

    contract: Contract | None


class FindOpenTicketsInput(StrictModel):
    """Input contract for duplicate lookup within a confirmed business scope."""

    customer_id: str
    site_id: str
    asset_id: str


class FindOpenTicketsOutput(StrictModel):
    """Output contract returning all non-terminal matching tickets."""

    tickets: list[Ticket]


class PriorityAssessment(StrictModel):
    """Rule-derived priority and machine-readable reasons."""

    priority: Literal["P1", "P2", "P3", "P4"]
    reason_codes: list[str]


class SlaAssessment(StrictModel):
    """Rule-derived response SLA and timezone-aware deadline."""

    contract_id: str
    response_sla: str
    deadline: datetime
    reason_codes: list[str]


class Decision(StrictModel):
    """Final deterministic business decision before any mutation proposal."""

    action: Action
    reason_codes: list[str]
    explanation: str
    requires_human_confirmation: bool


class TicketMutationInput(StrictModel):
    """Safe proposal to create or update one ticket; live execution is impossible."""

    idempotency_key: str = Field(min_length=16)
    expected_version: int = Field(ge=0)
    operation: Literal[Action.CREATE_NEW, Action.UPDATE_EXISTING]
    proposed_payload: dict[str, JsonValue]
    dry_run: Literal[True] = True
    requires_human_confirmation: Literal[True] = True


class TicketMutationOutput(StrictModel):
    """Dry-run tool result confirming that only a proposal was accepted."""

    accepted: bool
    dry_run: Literal[True] = True
    proposal: TicketMutationInput
    warnings: list[str]


class TraceEvent(StrictModel):
    """Redacted, ordered evidence of extraction, tool, rule or mutation work."""

    step: int = Field(ge=1)
    kind: TraceKind
    name: str
    input: dict[str, JsonValue]
    output: dict[str, JsonValue]


class RunLimits(StrictModel):
    """Hard local ceilings applied independently of any future model gateway."""

    max_tool_calls: int = Field(default=8, ge=1)
    max_model_calls: int = Field(default=2, ge=0)
    max_mutations: Literal[1] = 1


class RunMetadata(StrictModel):
    """Run identity, terminal state and consumed harness counters."""

    run_id: str
    trace_id: str
    terminal_state: TerminalState
    tool_calls: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    mutation_calls: int = Field(ge=0)
    limits: RunLimits


class CaseResult(StrictModel):
    """Complete user-visible result joining evidence, lookups, decision and trace."""

    run: RunMetadata
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
