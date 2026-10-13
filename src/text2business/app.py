from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st
from pydantic import ValidationError

from text2business.models import (
    CaseResult,
    IncomingRequest,
    Priority,
    PriorityOverride,
    TrustedContactIdentity,
)
from text2business.scenarios import SCENARIOS
from text2business.workflow import apply_dispatcher_priority_override, run_case


def _fact_rows(result: CaseResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field_name in type(result.facts).model_fields:
        value = getattr(result.facts, field_name)
        facts = value if isinstance(value, list) else [value]
        for fact in facts:
            if fact is None:
                continue
            rows.append(
                {
                    "Поле": field_name,
                    "Значение": str(fact.value),
                    "Цитата": fact.evidence,
                    "Confidence": f"{fact.confidence:.0%}",
                    "Источник": fact.provenance,
                }
            )
    return rows


def _render_result(result: CaseResult) -> None:
    status = result.decision.review_status.value
    if status == "ready_for_review":
        st.success("Готово к проверке диспетчером")
    elif status == "needs_clarification":
        st.warning("Нужно уточнение клиента")
    else:
        st.error("Требуется ручная проверка диспетчера")

    summary = st.columns(4)
    summary[0].metric("Действие", result.decision.action.value)
    summary[1].metric("Приоритет", result.priority.effective if result.priority else "—")
    summary[2].metric(
        "SLA ответа",
        result.sla.deadline.strftime("%d.%m %H:%M %Z") if result.sla else "—",
    )
    summary[3].metric("Повтор", result.repeat.kind.value if result.repeat else "—")

    st.subheader("Извлечённые факты и evidence")
    rows = _fact_rows(result)
    st.dataframe(rows, use_container_width=True, hide_index=True) if rows else st.info(
        "Факты не извлечены"
    )

    st.subheader("Корпоративный контекст")
    st.json(
        {
            "customer": result.resolved_customer.model_dump(mode="json")
            if result.resolved_customer
            else None,
            "site": result.resolved_site.model_dump(mode="json")
            if result.resolved_site
            else None,
            "asset": result.resolved_asset.model_dump(mode="json")
            if result.resolved_asset
            else None,
            "contract": result.contract.model_dump(mode="json") if result.contract else None,
            "repeat": result.repeat.model_dump(mode="json") if result.repeat else None,
            "capacity": result.capacity.model_dump(mode="json") if result.capacity else None,
        }
    )

    if result.clarification_questions:
        st.subheader("Следующий вопрос")
        st.warning(result.clarification_questions[0])

    st.subheader("Предлагаемое изменение заявки")
    if result.proposal:
        st.warning("DRY RUN — корпоративная система не изменяется")
        st.json(result.proposal.model_dump(mode="json"))
    else:
        st.info("Предложение не сформировано из-за блокирующего условия")

    st.subheader("Черновик ответа")
    st.text_area(
        "Текст можно отредактировать вручную; он не отправляется автоматически",
        value=result.draft_response.body,
        height=140,
    )

    if result.priority:
        with st.expander("Исправить приоритет"):
            selected = st.selectbox(
                "Итоговый приоритет",
                options=list(Priority),
                index=list(Priority).index(result.priority.effective),
            )
            reason = st.text_input("Причина изменения (обязательно)")
            if st.button("Применить исправление"):
                try:
                    override = PriorityOverride(
                        priority=selected,
                        reason=reason,
                        actor="local-dispatcher",
                        changed_at=datetime.now(tz=result.request.received_at.tzinfo),
                    )
                    st.session_state["case_result"] = apply_dispatcher_priority_override(
                        result, override
                    )
                    st.rerun()
                except (ValidationError, ValueError) as exc:
                    st.error(f"Исправление не применено: {exc}")

    if result.warnings:
        st.subheader("Предупреждения")
        for warning in result.warnings:
            st.warning(warning)

    with st.expander("Trace и reason codes"):
        st.json(
            {
                "run": result.run.model_dump(mode="json"),
                "decision": result.decision.model_dump(mode="json"),
                "trace": [event.model_dump(mode="json") for event in result.trace],
            }
        )


def main() -> None:
    """Render the local dispatcher demo without adding UI-side business rules."""

    st.set_page_config(page_title="Text2Business Dispatcher", layout="wide")
    st.title("AI-assisted триаж сервисного обращения")
    st.caption("Система готовит объяснимое предложение. Все изменения — только dry-run.")

    mode = st.radio("Источник", ["Готовый сценарий", "Свободный ввод"], horizontal=True)
    request: IncomingRequest | None = None
    if mode == "Готовый сценарий":
        scenario = st.selectbox("Сценарий", sorted(SCENARIOS))
        st.code(SCENARIOS[scenario].text)
        if st.button("Запустить триаж", type="primary"):
            request = SCENARIOS[scenario]
    else:
        with st.form("request-form"):
            customer_id = st.text_input("CRM customer ID", value="C-101")
            contact_id = st.text_input("CRM contact ID", value="CONTACT-17")
            verified = st.checkbox("Identity подтверждена каналом", value=True)
            channel = st.selectbox("Канал", ["email", "call_transcript", "portal"])
            received_at = st.text_input(
                "Время получения ISO 8601",
                value="2026-08-13T16:40:00+03:00",
            )
            sender = st.text_input("Отображаемый отправитель", value="Андрей, СеверФуд")
            text = st.text_area("Обращение", height=160)
            submitted = st.form_submit_button("Запустить триаж", type="primary")
        if submitted:
            try:
                request = IncomingRequest(
                    channel=channel,
                    received_at=datetime.fromisoformat(received_at),
                    identity=(
                        TrustedContactIdentity(
                            customer_id=customer_id,
                            contact_id=contact_id or None,
                            source="local-demo",
                            verified=verified,
                        )
                        if customer_id
                        else None
                    ),
                    sender_display=sender or None,
                    text=text,
                )
            except (ValidationError, ValueError) as exc:
                st.error(f"Некорректный вход: {exc}")

    if request is not None:
        with st.spinner("Извлекаю факты и проверяю корпоративный контекст…"):
            st.session_state["case_result"] = run_case(request)

    result = st.session_state.get("case_result")
    if isinstance(result, CaseResult):
        _render_result(result)


if __name__ == "__main__":
    main()
