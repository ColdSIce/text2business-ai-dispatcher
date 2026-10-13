from text2business.models import Action, TerminalState
from text2business.scenarios import SCENARIOS
from text2business.workflow import run_case


def test_full_request_produces_explainable_create_dry_run() -> None:
    result = run_case(SCENARIOS["full"])

    assert result.resolved_site is not None
    assert result.resolved_site.site_id == "S-MSK-01"
    assert result.resolved_asset is not None
    assert result.resolved_asset.asset_id == "A-1003"
    assert result.decision.action == Action.CREATE_NEW
    assert result.priority is not None and result.priority.priority == "P3"
    assert result.sla is not None
    assert result.sla.deadline.isoformat() == "2026-08-13T17:40:00+03:00"
    assert result.mutation is not None
    assert result.mutation.dry_run is True
    assert result.mutation.proposal.expected_version == 0
    assert result.mutation.proposal.requires_human_confirmation is True
    assert len(result.mutation.proposal.idempotency_key) == 64
    assert result.run.terminal_state == TerminalState.COMPLETED
    assert result.run.tool_calls == 5
    assert result.run.model_calls == 0
    assert [event.name for event in result.trace] == [
        "deterministic_extraction",
        "find_customer_or_site",
        "find_assets",
        "get_contract",
        "find_open_tickets",
        "business_rules",
        "create_or_update_ticket",
    ]


def test_ambiguous_site_requests_clarification_without_mutation() -> None:
    result = run_case(SCENARIOS["ambiguous"])

    assert result.facts.asset is not None
    assert result.facts.asset.value == "ХУ-17"
    assert result.decision.action == Action.REQUEST_CLARIFICATION
    assert result.resolved_site is None
    assert {match.site.site_id for match in result.site_candidates} == {
        "S-MSK-01",
        "S-EKB-02",
    }
    assert result.mutation is None
    assert result.clarification_questions == ["Уточните точный адрес объекта."]
    assert result.run.terminal_state == TerminalState.NEEDS_USER_INPUT


def test_duplicate_updates_existing_ticket_in_dry_run() -> None:
    result = run_case(SCENARIOS["duplicate"])

    assert result.resolved_site is not None
    assert result.resolved_site.site_id == "S-MSK-01"
    assert result.resolved_asset is not None
    assert result.resolved_asset.asset_id == "A-1001"
    assert [ticket.ticket_id for ticket in result.open_tickets] == ["T-884"]
    assert result.decision.action == Action.UPDATE_EXISTING
    assert result.priority is not None and result.priority.priority == "P2"
    assert result.mutation is not None
    assert result.mutation.proposal.expected_version == 1
    assert result.mutation.proposal.operation == Action.UPDATE_EXISTING
    assert result.mutation.dry_run is True


def test_prompt_injection_is_data_and_cannot_call_tools() -> None:
    result = run_case(SCENARIOS["injection"])

    assert result.facts.suspicious_instruction is not None
    assert result.decision.action == Action.HANDOFF_TO_DISPATCHER
    assert result.mutation is None
    assert result.run.terminal_state == TerminalState.HANDED_OFF
    assert result.run.tool_calls == 0
    assert [event.name for event in result.trace] == [
        "deterministic_extraction",
        "untrusted_input_guard",
    ]
