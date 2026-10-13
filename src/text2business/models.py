from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class StrictModel(BaseModel):
    """Base contract that rejects unknown fields at every application boundary."""

    model_config = ConfigDict(extra="forbid")


class Provenance(StrEnum):
    """Origin of an extracted fact shown to the dispatcher."""

    MESSAGE = "message"
    ATTACHMENT = "attachment"
    INTERNAL_LOOKUP = "internal_lookup"
    ASSUMPTION = "assumption"


class BackupStatus(StrEnum):
    """Operational confidence in backup equipment, independent of model confidence."""

    CONFIRMED = "confirmed"
    UNCERTAIN = "uncertain"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class Priority(StrEnum):
    """Closed service priority scale ordered from most to least urgent."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class TicketStatus(StrEnum):
    """Ticket lifecycle statuses needed by repeat classification."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_CUSTOMER = "waiting_for_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Return whether the ticket must never be updated by this prototype."""

        return self in {self.RESOLVED, self.CLOSED, self.CANCELLED}


class RepeatKind(StrEnum):
    """Relationship between the incoming contact and prior tickets."""

    NONE = "none"
    OPEN = "open"
    CLOSED = "closed"


class SlaKind(StrEnum):
    """Supported deterministic response-deadline calculation modes."""

    CALENDAR_MINUTES = "calendar_minutes"
    BUSINESS_HOURS = "business_hours"
    NEXT_BUSINESS_DAY = "next_business_day"


class CapacityFeasibility(StrEnum):
    """Whether known service capacity can satisfy the customer's requested time."""

    AVAILABLE = "available"
    REQUESTED_TIME_UNCONFIRMED = "requested_time_unconfirmed"
    UNKNOWN = "unknown"


class Action(StrEnum):
    """Closed set of business actions proposed by deterministic decision policy."""

    CREATE_NEW = "create_new"
    UPDATE_EXISTING = "update_existing"
    REQUEST_CLARIFICATION = "request_clarification"
    HANDOFF_TO_DISPATCHER = "handoff_to_dispatcher"
    REQUIRES_ADDITIONAL_APPROVAL = "requires_additional_approval"


class ReviewStatus(StrEnum):
    """User-facing readiness of the triage result."""

    READY_FOR_REVIEW = "ready_for_review"
    NEEDS_CLARIFICATION = "needs_clarification"
    NEEDS_DISPATCHER_REVIEW = "needs_dispatcher_review"


class AutomationAssessment(StrEnum):
    """Informational future automation eligibility; never authorizes a write."""

    POTENTIALLY_AUTOMATABLE = "potentially_automatable"
    HUMAN_REQUIRED = "human_required"


class TraceKind(StrEnum):
    """Safe category for one ordered explainability event."""

    EXTRACTION = "extraction"
    MODEL = "model"
    TOOL = "tool"
    RULE = "rule"
    PROPOSAL = "proposal"
    REVIEW = "review"


class TerminalState(StrEnum):
    """Final harness state; a run cannot continue after one of these states."""

    COMPLETED = "completed"
    NEEDS_USER_INPUT = "needs_user_input"
    HANDED_OFF = "handed_off"
    FAILED = "failed"


class EvidenceFact(StrictModel):
    """One extracted value with an exact source quote, confidence and provenance."""

    value: str | bool | float = Field(description="Extracted value, not yet canonical data")
    evidence: str = Field(min_length=1, description="Exact fragment from the cited source")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence from 0 to 1")
    provenance: Provenance = Field(description="Source containing the evidence fragment")


class ExtractedFacts(StrictModel):
    """Nullable structured interpretation of untrusted customer-provided content."""

    customer_name: EvidenceFact | None = None
    site_reference: EvidenceFact | None = None
    asset_reference: EvidenceFact | None = None
    problem: EvidenceFact | None = None
    symptoms: list[EvidenceFact] = Field(default_factory=list)
    temperature_c: EvidenceFact | None = None
    temperature_rising: EvidenceFact | None = None
    safety_threat: EvidenceFact | None = None
    complete_outage: EvidenceFact | None = None
    desired_deadline: EvidenceFact | None = None
    backup_status: EvidenceFact | None = None
    previous_contact: EvidenceFact | None = None
    requires_additional_approval: EvidenceFact | None = None
    suspicious_instruction: EvidenceFact | None = None


class TrustedContactIdentity(StrictModel):
    """CRM identity metadata supplied by an authenticated communication channel."""

    customer_id: str = Field(min_length=1, description="Canonical CRM customer identifier")
    contact_id: str | None = Field(default=None, description="Optional canonical contact identifier")
    source: str = Field(min_length=1, description="Authenticated adapter that supplied the identity")
    verified: bool = Field(description="Whether the adapter authenticated this identity")


class IncomingRequest(StrictModel):
    """Validated envelope for exactly one customer contact and its trusted metadata."""

    source_request_id: str | None = Field(
        default=None,
        description="Stable channel message/call identifier; derived when absent",
    )
    channel: str = Field(min_length=1, description="Communication channel name")
    received_at: datetime = Field(description="Timezone-aware receipt timestamp")
    identity: TrustedContactIdentity | None = Field(
        default=None,
        description="Trusted CRM identity; free text must never substitute for it",
    )
    sender_display: str | None = Field(
        default=None,
        description="Untrusted sender label shown for context only",
    )
    text: str = Field(min_length=1, max_length=20_000, description="Untrusted request text")
    attachment_text: str | None = Field(
        default=None,
        max_length=50_000,
        description="Optional pre-extracted attachment or call transcript text",
    )

    @field_validator("received_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Reject timestamps whose absolute instant cannot be determined."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("received_at must include a timezone")
        return value


class Customer(StrictModel):
    """Canonical corporate customer that scopes every downstream lookup."""

    customer_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)


class Site(StrictModel):
    """Customer service location with region and IANA timezone."""

    site_id: str
    customer_id: str
    address: str
    region: str
    timezone: str


class Asset(StrictModel):
    """Serviceable equipment installed at one site and owned by one service group."""

    asset_id: str
    site_id: str
    local_code: str
    asset_type: str
    criticality: Literal["low", "medium", "high"]
    service_group: str


class Contract(StrictModel):
    """Service agreement that defines response SLA, service window and coverage."""

    contract_id: str
    site_id: str
    plan: Literal["Gold", "Standard", "Basic"]
    response_sla: str
    service_window: str
    coverage: list[str]


class Ticket(StrictModel):
    """Versioned service ticket used for repeat detection and SLA preservation."""

    ticket_id: str
    customer_id: str
    site_id: str
    asset_id: str
    created_at: datetime
    closed_at: datetime | None = None
    status: TicketStatus
    summary: str
    version: int = Field(ge=1, description="Optimistic concurrency version")
    sla_deadline: datetime = Field(description="Timezone-aware original response deadline")
    last_contact_at: datetime = Field(description="Timezone-aware most recent customer contact")

    @field_validator("created_at", "closed_at", "sla_deadline", "last_contact_at")
    @classmethod
    def require_ticket_timezone(cls, value: datetime | None) -> datetime | None:
        """Require an absolute instant for every ticket timestamp that is present."""

        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("ticket timestamps must include a timezone")
        return value


class ServiceCapacity(StrictModel):
    """Informational next availability for one service group in one region."""

    service_group: str
    region: str
    next_available_at: datetime

    @field_validator("next_available_at")
    @classmethod
    def require_capacity_timezone(cls, value: datetime) -> datetime:
        """Reject ambiguous availability timestamps."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("next_available_at must include a timezone")
        return value


class CorporateData(StrictModel):
    """Validated read-only snapshot of all corporate fixture collections."""

    current_time: datetime
    customers: list[Customer]
    sites: list[Site]
    assets: list[Asset]
    contracts: list[Contract]
    tickets: list[Ticket]
    capacities: list[ServiceCapacity]


class CustomerMatch(StrictModel):
    """Candidate customer and deterministic match evidence."""

    customer: Customer
    score: int = Field(ge=0)
    matched_by: list[str]


class SiteMatch(StrictModel):
    """Candidate site and deterministic match evidence within one customer scope."""

    site: Site
    score: int = Field(ge=0)
    matched_by: list[str]


class AssetMatch(StrictModel):
    """Candidate asset and deterministic match evidence within one site scope."""

    asset: Asset
    score: int = Field(ge=0)
    matched_by: list[str]


class GetCustomerInput(StrictModel):
    """Exact trusted customer lookup input."""

    customer_id: str


class GetCustomerOutput(StrictModel):
    """Exact trusted customer lookup output with explicit missing state."""

    customer: Customer | None


class FindCustomersInput(StrictModel):
    """Untrusted customer-name candidate search input."""

    query: str


class FindCustomersOutput(StrictModel):
    """All deterministic customer candidates; no candidate is implicitly selected."""

    matches: list[CustomerMatch]


class FindSitesInput(StrictModel):
    """Site lookup restricted to one confirmed customer."""

    customer_id: str
    query: str


class FindSitesOutput(StrictModel):
    """Ranked site candidates inside the confirmed customer scope."""

    matches: list[SiteMatch]


class FindAssetsInput(StrictModel):
    """Asset lookup restricted to one resolved site."""

    site_id: str
    query: str


class FindAssetsOutput(StrictModel):
    """Ranked asset candidates inside the resolved site scope."""

    matches: list[AssetMatch]


class GetContractInput(StrictModel):
    """Contract lookup input for one resolved site."""

    site_id: str


class GetContractOutput(StrictModel):
    """Contract lookup output with explicit missing state."""

    contract: Contract | None


class FindTicketsInput(StrictModel):
    """Exact ticket-history lookup within confirmed customer/site/asset scope."""

    customer_id: str
    site_id: str
    asset_id: str


class FindTicketsOutput(StrictModel):
    """All matching open and closed tickets, ordered newest first."""

    tickets: list[Ticket]


class GetCapacityInput(StrictModel):
    """Capacity lookup key derived from a canonical asset and site."""

    service_group: str
    region: str


class GetCapacityOutput(StrictModel):
    """Capacity lookup output with explicit unknown state."""

    capacity: ServiceCapacity | None


class RepeatAssessment(StrictModel):
    """Deterministic relationship to a matching open or recent closed ticket."""

    kind: RepeatKind
    related_ticket_id: str | None = None
    repeat_after_resolution: bool = False
    contact_count: int = Field(default=1, ge=1)
    reason_codes: list[str]


class PriorityOverride(StrictModel):
    """Auditable dispatcher correction that never erases calculated priority."""

    priority: Priority
    reason: str = Field(min_length=3, description="Required human explanation")
    actor: str = Field(min_length=1, description="Local dispatcher identifier")
    changed_at: datetime

    @field_validator("changed_at")
    @classmethod
    def require_override_timezone(cls, value: datetime) -> datetime:
        """Require an absolute override timestamp for auditability."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("changed_at must include a timezone")
        return value


class PriorityAssessment(StrictModel):
    """Rule-derived priority with an optional separately auditable override."""

    calculated: Priority
    effective: Priority
    reason_codes: list[str]
    override: PriorityOverride | None = None


class SlaAssessment(StrictModel):
    """Deterministic contractual response deadline in the site's timezone."""

    contract_id: str
    kind: SlaKind
    response_sla: str
    deadline: datetime
    timezone: str
    reason_codes: list[str]
    source_ticket_id: str | None = Field(
        default=None,
        description="Open ticket whose original SLA is preserved for a repeat",
    )


class CapacityAssessment(StrictModel):
    """Informational feasibility that never changes priority or contractual SLA."""

    service_group: str
    region: str
    next_available_at: datetime | None
    customer_requested_by: datetime | None
    feasibility: CapacityFeasibility
    reason_codes: list[str]


class Decision(StrictModel):
    """One deterministic business outcome and its human-review requirements."""

    action: Action
    review_status: ReviewStatus
    automation_assessment: AutomationAssessment
    reason_codes: list[str]
    explanation: str
    requires_human_confirmation: Literal[True] = True


class TicketChangeProposal(StrictModel):
    """Typed dry-run proposal to create or update one ticket; never a live write."""

    idempotency_key: str = Field(min_length=16)
    expected_version: int = Field(ge=0)
    operation: Literal[Action.CREATE_NEW, Action.UPDATE_EXISTING]
    target_ticket_id: str | None = None
    related_ticket_id: str | None = None
    proposed_payload: dict[str, JsonValue]
    dry_run: Literal[True] = True
    requires_human_confirmation: Literal[True] = True


class TicketChangeProposalOutput(StrictModel):
    """Validation result confirming that a proposal was accepted without execution."""

    accepted: bool
    proposal: TicketChangeProposal
    warnings: list[str]
    dry_run: Literal[True] = True


class DraftResponse(StrictModel):
    """Editable response text that cannot change the deterministic case result."""

    subject: str | None = None
    body: str
    warnings: list[str] = Field(default_factory=list)


class TraceEvent(StrictModel):
    """Redacted ordered record of extraction, tool, rule, proposal or review work."""

    step: int = Field(ge=1)
    kind: TraceKind
    name: str
    input: dict[str, JsonValue]
    output: dict[str, JsonValue]


class RunLimits(StrictModel):
    """Hard per-run ceilings that structurally prevent loops and runaway work."""

    max_tool_calls: int = Field(default=8, ge=1)
    max_model_calls: int = Field(default=2, ge=0)
    max_proposals: Literal[1] = 1
    max_run_seconds: float = Field(default=30.0, gt=0)


class RunMetadata(StrictModel):
    """Run identity, terminal state, consumed budgets and elapsed wall time."""

    run_id: str
    trace_id: str
    terminal_state: TerminalState
    tool_calls: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    proposal_calls: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    limits: RunLimits


class CaseResult(StrictModel):
    """Single user-visible result joining evidence, corporate context and decision."""

    run: RunMetadata
    request: IncomingRequest
    facts: ExtractedFacts
    customer_candidates: list[CustomerMatch]
    site_candidates: list[SiteMatch]
    asset_candidates: list[AssetMatch]
    resolved_customer: Customer | None
    resolved_site: Site | None
    resolved_asset: Asset | None
    contract: Contract | None
    tickets: list[Ticket]
    repeat: RepeatAssessment | None
    priority: PriorityAssessment | None
    sla: SlaAssessment | None
    capacity: CapacityAssessment | None
    decision: Decision
    proposal: TicketChangeProposalOutput | None
    draft_response: DraftResponse
    clarification_questions: list[str]
    warnings: list[str]
    trace: list[TraceEvent]
