from __future__ import annotations

from text2business.models import (
    Action,
    AutomationAssessment,
    Decision,
    Priority,
    ReviewStatus,
)


def clarification_decision(code: str, explanation: str) -> Decision:
    """Create a fail-closed decision requesting one blocking clarification."""

    return Decision(
        action=Action.REQUEST_CLARIFICATION,
        review_status=ReviewStatus.NEEDS_CLARIFICATION,
        automation_assessment=AutomationAssessment.HUMAN_REQUIRED,
        reason_codes=[code],
        explanation=explanation,
    )


def handoff_decision(code: str, explanation: str) -> Decision:
    """Create a fail-closed dispatcher handoff with no automatic eligibility."""

    return Decision(
        action=Action.HANDOFF_TO_DISPATCHER,
        review_status=ReviewStatus.NEEDS_DISPATCHER_REVIEW,
        automation_assessment=AutomationAssessment.HUMAN_REQUIRED,
        reason_codes=[code],
        explanation=explanation,
    )


def final_decision(
    action: Action,
    priority: Priority,
    *,
    requires_additional_approval: bool = False,
) -> Decision:
    """Build the final create/update decision after all deterministic checks."""

    if requires_additional_approval:
        return Decision(
            action=Action.REQUIRES_ADDITIONAL_APPROVAL,
            review_status=ReviewStatus.NEEDS_DISPATCHER_REVIEW,
            automation_assessment=AutomationAssessment.HUMAN_REQUIRED,
            reason_codes=["COVERAGE_OR_COST_APPROVAL_REQUIRED"],
            explanation="Требуется дополнительное согласование покрытия или стоимости.",
        )
    if priority == Priority.P1:
        return Decision(
            action=action,
            review_status=ReviewStatus.NEEDS_DISPATCHER_REVIEW,
            automation_assessment=AutomationAssessment.HUMAN_REQUIRED,
            reason_codes=["P1_IMMEDIATE_DISPATCHER_REVIEW"],
            explanation="Критическая заявка немедленно передана диспетчеру.",
        )
    return Decision(
        action=action,
        review_status=ReviewStatus.READY_FOR_REVIEW,
        automation_assessment=AutomationAssessment.POTENTIALLY_AUTOMATABLE,
        reason_codes=["TRUSTED_IDENTITY", "UNIQUE_SCOPE", "CONTRACT_SLA_READY"],
        explanation="Триаж завершён; предложение готово к проверке диспетчером.",
    )
