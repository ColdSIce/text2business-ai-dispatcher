from __future__ import annotations

from datetime import datetime

from text2business.models import (
    Action,
    CapacityFeasibility,
    Priority,
    PriorityOverride,
    RepeatKind,
    ReviewStatus,
    TerminalState,
)
from text2business.repository import JsonCorporateRepository
from text2business.scenarios import SCENARIOS
from text2business.workflow import apply_dispatcher_priority_override, run_case


def test_full_request_produces_explainable_create_proposal() -> None:
    result = run_case(SCENARIOS["full"])

    assert result.resolved_customer and result.resolved_customer.customer_id == "C-101"
    assert result.resolved_site and result.resolved_site.site_id == "S-MSK-01"
    assert result.resolved_asset and result.resolved_asset.asset_id == "A-1003"
    assert result.decision.action == Action.CREATE_NEW
    assert result.decision.review_status == ReviewStatus.READY_FOR_REVIEW
    assert result.priority and result.priority.effective == Priority.P3
    assert result.sla and result.sla.deadline.isoformat() == "2026-08-13T17:40:00+03:00"
    assert result.repeat and result.repeat.kind == RepeatKind.NONE
    assert result.proposal and result.proposal.dry_run is True
    assert result.proposal.proposal.expected_version == 0
    assert result.proposal.proposal.requires_human_confirmation is True
    assert result.run.terminal_state == TerminalState.COMPLETED
    assert result.run.tool_calls == 7
    assert result.run.model_calls == 0


def test_ambiguous_site_requests_one_clarification_without_proposal() -> None:
    result = run_case(SCENARIOS["ambiguous"])

    assert result.decision.action == Action.REQUEST_CLARIFICATION
    assert result.decision.review_status == ReviewStatus.NEEDS_CLARIFICATION
    assert result.resolved_site is None
    assert {match.site.site_id for match in result.site_candidates} == {
        "S-MSK-01",
        "S-EKB-02",
    }
    assert result.proposal is None
    assert result.clarification_questions == ["Уточните точный адрес объекта."]
    assert result.run.terminal_state == TerminalState.NEEDS_USER_INPUT


def test_open_repeat_updates_ticket_without_sla_reset_or_priority_boost() -> None:
    result = run_case(SCENARIOS["duplicate"])

    assert result.repeat and result.repeat.kind == RepeatKind.OPEN
    assert result.repeat.related_ticket_id == "T-884"
    assert result.priority and result.priority.effective == Priority.P2
    assert result.sla and result.sla.deadline.isoformat() == "2026-08-13T16:55:00+03:00"
    assert result.sla.source_ticket_id == "T-884"
    assert result.proposal and result.proposal.proposal.operation == Action.UPDATE_EXISTING
    assert result.proposal.proposal.target_ticket_id == "T-884"
    assert result.proposal.proposal.expected_version == 1
    assert "SLA_AT_RISK" in result.warnings


def test_closed_repeat_creates_linked_ticket_with_new_basic_sla() -> None:
    result = run_case(SCENARIOS["closed_repeat"])

    assert result.repeat and result.repeat.kind == RepeatKind.CLOSED
    assert result.repeat.repeat_after_resolution is True
    assert result.priority and result.priority.effective == Priority.P3
    assert result.sla and result.sla.deadline.isoformat() == "2026-08-14T18:00:00+03:00"
    assert result.proposal and result.proposal.proposal.operation == Action.CREATE_NEW
    assert result.proposal.proposal.related_ticket_id == "T-771"
    assert result.proposal.proposal.expected_version == 0


def test_standard_sla_carries_work_across_weekend() -> None:
    result = run_case(SCENARIOS["standard"])

    assert result.contract and result.contract.plan == "Standard"
    assert result.sla and result.sla.deadline.isoformat() == "2026-08-17T12:00:00+05:00"


def test_p1_always_requires_dispatcher_but_keeps_safe_proposal() -> None:
    result = run_case(SCENARIOS["p1"])

    assert result.priority and result.priority.calculated == Priority.P1
    assert result.decision.review_status == ReviewStatus.NEEDS_DISPATCHER_REVIEW
    assert result.run.terminal_state == TerminalState.HANDED_OFF
    assert result.proposal is not None


def test_missing_identity_and_conflict_never_produce_proposal() -> None:
    missing = run_case(SCENARIOS["missing_identity"])
    conflict = run_case(SCENARIOS["conflict"])

    assert missing.proposal is None
    assert [match.customer.customer_id for match in missing.customer_candidates] == ["C-101"]
    assert "TRUSTED_IDENTITY_MISSING" in missing.decision.reason_codes
    assert conflict.proposal is None
    assert "CRM_TEXT_CONFLICT" in conflict.decision.reason_codes


def test_busy_capacity_is_visible_without_changing_sla_or_priority() -> None:
    result = run_case(SCENARIOS["busy_capacity"])

    assert result.capacity
    assert result.capacity.feasibility == CapacityFeasibility.REQUESTED_TIME_UNCONFIRMED
    assert result.capacity.customer_requested_by
    assert result.priority and result.priority.effective == Priority.P3
    assert result.sla and result.sla.deadline.isoformat() == "2026-08-14T18:00:00+03:00"


def test_additional_approval_is_status_only_without_proposal() -> None:
    result = run_case(SCENARIOS["approval"])

    assert result.decision.action == Action.REQUIRES_ADDITIONAL_APPROVAL
    assert result.decision.review_status == ReviewStatus.NEEDS_DISPATCHER_REVIEW
    assert result.proposal is None


def test_prompt_injection_cannot_call_corporate_tools() -> None:
    result = run_case(SCENARIOS["injection"])

    assert result.facts.suspicious_instruction is not None
    assert result.decision.action == Action.HANDOFF_TO_DISPATCHER
    assert result.proposal is None
    assert result.run.tool_calls == 0
    assert [event.name for event in result.trace] == ["structured_extraction"]


def test_runs_are_idempotent_and_fixture_is_unchanged() -> None:
    repository = JsonCorporateRepository()
    before = repository.source_digest
    first = run_case(SCENARIOS["full"], repository=repository)
    second = run_case(SCENARIOS["full"], repository=repository)
    after = JsonCorporateRepository().source_digest

    assert first.proposal and second.proposal
    assert first.proposal.proposal.idempotency_key == second.proposal.proposal.idempotency_key
    assert before == after


def test_dispatcher_override_keeps_calculated_priority_and_updates_proposal() -> None:
    result = run_case(SCENARIOS["full"])
    updated = apply_dispatcher_priority_override(
        result,
        PriorityOverride(
            priority=Priority.P2,
            reason="Подтверждён дополнительный риск",
            actor="dispatcher-1",
            changed_at=datetime.fromisoformat("2026-08-13T16:45:00+03:00"),
        ),
    )

    assert updated.priority and updated.priority.calculated == Priority.P3
    assert updated.priority.effective == Priority.P2
    assert updated.proposal
    assert updated.proposal.proposal.proposed_payload["priority"] == Priority.P2
    assert updated.trace[-1].name == "dispatcher_priority_override"
