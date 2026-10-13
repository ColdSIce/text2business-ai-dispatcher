from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st
from pydantic import ValidationError

from text2business.drafting import GatewayResponseDrafter
from text2business.evals import execute_eval_cases
from text2business.extractor import GatewayExtractor
from text2business.gateway import GatewayConfig, GatewayError, StructuredGatewayClient
from text2business.models import (
    CaseResult,
    EvalCase,
    EvalRun,
    IncomingRequest,
    Priority,
    PriorityOverride,
    TrustedContactIdentity,
)
from text2business.scenarios import EVAL_CASES, EVAL_DATASET
from text2business.prompts import DEFAULT_DRAFTING_PROMPT, DEFAULT_EXTRACTION_PROMPT
from text2business.workflow import apply_dispatcher_priority_override, run_case


def _value(value: object | None) -> str:
    """Return a compact display value for enums and nullable result fields."""

    if value is None:
        return "—"
    return str(getattr(value, "value", value))


def _dataset_rows(cases: list[EvalCase]) -> list[dict[str, Any]]:
    """Flatten dataset metadata for the read-only catalogue table."""

    return [
        {
            "ID": case.case_id,
            "Кейс": case.title,
            "Тип": "Позитивный" if case.polarity == "positive" else "Негативный",
            "Категория": case.category,
            "Ожидаемое действие": case.expected.action.value,
            "Приоритет": _value(case.expected.priority),
            "Повтор": _value(case.expected.repeat_kind),
            "Proposal": "да" if case.expected.expects_proposal else "нет",
        }
        for case in cases
    ]


def _run_rows(runs: list[EvalRun]) -> list[dict[str, Any]]:
    """Flatten execution history without dropping the underlying full results."""

    return [
        {
            "Статус": "PASS" if run.passed else "FAIL",
            "Кейс": run.case_title,
            "ID": run.case_id,
            "Действие": run.result.decision.action.value,
            "Приоритет": _value(run.result.priority.effective if run.result.priority else None),
            "Время, мс": run.result.run.elapsed_ms,
            "Tools": run.result.run.tool_calls,
            "Models": run.result.run.model_calls,
            "Запущен": run.executed_at.strftime("%H:%M:%S"),
        }
        for run in runs
    ]


def _fact_rows(result: CaseResult) -> list[dict[str, Any]]:
    """Flatten evidence facts for a dispatcher-readable table."""

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
                    "Источник": fact.provenance.value,
                }
            )
    return rows


def _render_trace(result: CaseResult) -> None:
    """Show the safe ordered trace of one execution, step by step."""

    counters = st.columns(4)
    counters[0].metric("Run", result.run.run_id.removeprefix("run_")[:8])
    counters[1].metric("Tool calls", result.run.tool_calls)
    counters[2].metric("Model calls", result.run.model_calls)
    counters[3].metric("Время", f"{result.run.elapsed_ms} мс")

    st.caption(
        f"Terminal state: `{result.run.terminal_state.value}` · "
        f"Trace ID: `{result.run.trace_id}`"
    )
    for event in result.trace:
        with st.expander(
            f"{event.step}. {event.kind.value.upper()} · {event.name}",
            expanded=event.step == 1,
        ):
            left, right = st.columns(2)
            with left:
                st.markdown("**Вход шага**")
                st.json(event.input)
            with right:
                st.markdown("**Результат шага**")
                st.json(event.output)


def _render_result(
    result: CaseResult,
    *,
    allow_override: bool = False,
    state_key: str = "custom_result",
) -> None:
    """Render one complete triage result without adding business rules in the UI."""

    status = result.decision.review_status.value
    if status == "ready_for_review":
        st.success("Готово к проверке диспетчером")
    elif status == "needs_clarification":
        st.warning("Нужно уточнение клиента")
    else:
        st.error("Требуется ручная проверка диспетчера")

    summary = st.columns(4)
    summary[0].metric("Действие", result.decision.action.value)
    summary[1].metric(
        "Приоритет",
        _value(result.priority.effective if result.priority else None),
    )
    summary[2].metric(
        "SLA ответа",
        result.sla.deadline.strftime("%d.%m %H:%M %Z") if result.sla else "—",
    )
    summary[3].metric("Повтор", _value(result.repeat.kind if result.repeat else None))

    st.subheader("Извлечённые факты и evidence")
    rows = _fact_rows(result)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("Факты не извлечены")

    with st.expander("Корпоративный контекст", expanded=True):
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
        st.warning(f"Следующий вопрос: {result.clarification_questions[0]}")

    st.subheader("Предлагаемое изменение заявки")
    if result.proposal:
        st.warning("DRY RUN — корпоративная система не изменяется")
        st.json(result.proposal.model_dump(mode="json"))
    else:
        st.info("Предложение не сформировано из-за блокирующего условия")

    st.subheader("Черновик ответа")
    st.text_area(
        "Текст можно редактировать; он не отправляется автоматически",
        value=result.draft_response.body,
        height=130,
        key=f"draft-{state_key}-{result.run.trace_id}",
    )

    if allow_override and result.priority:
        with st.expander("Исправить приоритет"):
            selected = st.selectbox(
                "Итоговый приоритет",
                options=list(Priority),
                index=list(Priority).index(result.priority.effective),
                key=f"priority-{state_key}",
            )
            reason = st.text_input("Причина изменения (обязательно)", key=f"reason-{state_key}")
            if st.button("Применить исправление", key=f"override-{state_key}"):
                try:
                    override = PriorityOverride(
                        priority=selected,
                        reason=reason,
                        actor="local-dispatcher",
                        changed_at=datetime.now(tz=result.request.received_at.tzinfo),
                    )
                    st.session_state[state_key] = apply_dispatcher_priority_override(
                        result, override
                    )
                    st.rerun()
                except (ValidationError, ValueError) as exc:
                    st.error(f"Исправление не применено: {exc}")

    if result.warnings:
        with st.expander(f"Предупреждения ({len(result.warnings)})"):
            for warning in result.warnings:
                st.warning(warning)


def _store_eval_runs(runs: list[EvalRun]) -> None:
    """Prepend new runs to the in-memory UI history and select the newest one."""

    history = list(st.session_state.get("eval_runs", []))
    st.session_state["eval_runs"] = [*reversed(runs), *history]
    if runs:
        st.session_state["selected_execution_id"] = runs[-1].execution_id


def _execute_case_ids(case_ids: list[str]) -> None:
    """Execute selected dataset IDs in canonical dataset order."""

    selected = [case for case in EVAL_DATASET.cases if case.case_id in case_ids]
    if not selected:
        st.warning("Выберите хотя бы один кейс")
        return
    with st.spinner(f"Выполняю кейсы: {len(selected)}…"):
        runs = execute_eval_cases(selected)
    _store_eval_runs(runs)
    passed = sum(run.passed for run in runs)
    if passed == len(runs):
        st.success(f"Готово: {passed}/{len(runs)} PASS. Результаты добавлены во вкладку «Запуски».")
    else:
        st.error(f"Есть расхождения: {passed}/{len(runs)} PASS.")


def _render_dataset_tab() -> None:
    """Render dataset catalogue, case details and execution controls."""

    st.header("Тестовый датасет")
    st.write(EVAL_DATASET.description)
    positive = sum(case.polarity == "positive" for case in EVAL_DATASET.cases)
    negative = sum(case.polarity == "negative" for case in EVAL_DATASET.cases)
    metrics = st.columns(4)
    metrics[0].metric("Версия", EVAL_DATASET.version)
    metrics[1].metric("Кейсов", len(EVAL_DATASET.cases))
    metrics[2].metric("Позитивных", positive)
    metrics[3].metric("Негативных", negative)

    polarity = st.radio(
        "Показать",
        ["Все", "Позитивные", "Негативные"],
        horizontal=True,
    )
    polarity_value = {
        "Все": None,
        "Позитивные": "positive",
        "Негативные": "negative",
    }[polarity]
    visible_cases = [
        case
        for case in EVAL_DATASET.cases
        if polarity_value is None or case.polarity == polarity_value
    ]

    st.dataframe(
        _dataset_rows(visible_cases),
        width="stretch",
        hide_index=True,
    )

    st.subheader("Посмотреть кейс")
    case_id = st.selectbox(
        "Кейс",
        options=[case.case_id for case in visible_cases],
        format_func=lambda value: f"{EVAL_CASES[value].title} · {value}",
    )
    case = EVAL_CASES[case_id]
    st.caption(case.description)
    request_col, expected_col = st.columns([3, 2])
    with request_col:
        st.markdown("**Входное обращение**")
        st.code(case.request.text, language=None)
        with st.expander("Полный request JSON"):
            st.json(case.request.model_dump(mode="json"))
    with expected_col:
        st.markdown("**Ожидаемый результат**")
        st.json(case.expected.model_dump(mode="json"))
        if st.button("▶ Запустить этот кейс", type="primary", width="stretch"):
            _execute_case_ids([case_id])

    st.subheader("Пакетный запуск")
    selected_ids = st.multiselect(
        "Выберите кейсы",
        options=list(EVAL_CASES),
        default=["full", "duplicate", "p1", "injection"],
        format_func=lambda value: EVAL_CASES[value].title,
    )
    selected_button, positive_button, negative_button, all_button = st.columns(4)
    if selected_button.button("Запустить выбранные", width="stretch"):
        _execute_case_ids(selected_ids)
    if positive_button.button("Все позитивные", width="stretch"):
        _execute_case_ids(
            [case.case_id for case in EVAL_DATASET.cases if case.polarity == "positive"]
        )
    if negative_button.button("Все негативные", width="stretch"):
        _execute_case_ids(
            [case.case_id for case in EVAL_DATASET.cases if case.polarity == "negative"]
        )
    if all_button.button("Запустить все", type="primary", width="stretch"):
        _execute_case_ids(list(EVAL_CASES))


def _render_runs_tab() -> None:
    """Render execution history and a drill-down with one trace per run."""

    st.header("Запуски")
    runs: list[EvalRun] = list(st.session_state.get("eval_runs", []))
    if not runs:
        st.info("Запусков пока нет. Выберите кейсы во вкладке «Тестовый датасет».")
        return

    passed = sum(run.passed for run in runs)
    summary = st.columns(3)
    summary[0].metric("Выполнений", len(runs))
    summary[1].metric("PASS", passed)
    summary[2].metric("FAIL", len(runs) - passed)
    st.dataframe(_run_rows(runs), width="stretch", hide_index=True)

    by_id = {run.execution_id: run for run in runs}
    default_id = st.session_state.get("selected_execution_id", runs[0].execution_id)
    if default_id not in by_id:
        default_id = runs[0].execution_id
    execution_id = st.selectbox(
        "Открыть выполнение",
        options=list(by_id),
        index=list(by_id).index(default_id),
        format_func=lambda value: (
            f"{'✅' if by_id[value].passed else '❌'} "
            f"{by_id[value].case_title} · {by_id[value].executed_at:%H:%M:%S}"
        ),
    )
    st.session_state["selected_execution_id"] = execution_id
    run = by_id[execution_id]

    if st.button("Повторить этот запуск"):
        _execute_case_ids([run.case_id])

    result_tab, trace_tab, raw_tab = st.tabs(["Результат", "Trace", "Полный JSON"])
    with result_tab:
        if run.passed:
            st.success("Все ожидания совпали")
        else:
            st.error("Есть расхождения с датасетом")
        st.dataframe(
            [
                {
                    "Проверка": item.name,
                    "Ожидалось": _value(item.expected),
                    "Получено": _value(item.actual),
                    "Статус": "PASS" if item.passed else "FAIL",
                }
                for item in run.assertions
            ],
            width="stretch",
            hide_index=True,
        )
        _render_result(run.result)
    with trace_tab:
        _render_trace(run.result)
    with raw_tab:
        st.json(run.model_dump(mode="json"))


def _render_manual_tab() -> None:
    """Render an ad-hoc request form and its result with trace."""

    st.header("Свободный ввод")
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
            with st.spinner("Извлекаю факты и проверяю корпоративный контекст…"):
                st.session_state["custom_result"] = run_case(request)
        except (ValidationError, ValueError) as exc:
            st.error(f"Некорректный вход: {exc}")

    result = st.session_state.get("custom_result")
    if isinstance(result, CaseResult):
        result_tab, trace_tab = st.tabs(["Результат", "Trace"])
        with result_tab:
            _render_result(result, allow_override=True)
        with trace_tab:
            _render_trace(result)


def _render_prompt_lab_tab() -> None:
    """Render per-case prompt overrides and guarded private-gateway executions."""

    st.header("Prompt Lab")
    st.write(
        "Промпты влияют только на извлечение фактов и текст ответа. "
        "Приоритет, SLA, повтор, capacity и решение всегда считает код."
    )

    try:
        config = GatewayConfig.from_env()
    except (GatewayError, ValueError) as exc:
        config = None
        st.info(
            "Private AI Gateway не настроен — промпты можно редактировать, "
            "но model-run пока недоступен."
        )
        with st.expander("Как включить model-run"):
            st.code(
                "export AI_GATEWAY_BASE_URL=https://gateway.example/v1\n"
                "export AI_GATEWAY_API_KEY=...\n"
                "export AI_GATEWAY_MODEL=...",
                language="bash",
            )
            st.caption(str(exc))
    else:
        st.success(f"Gateway готов · model `{config.model}` · секрет не показывается")

    case_id = st.selectbox(
        "Кейс для тюнинга",
        options=list(EVAL_CASES),
        format_func=lambda value: (
            f"{'+' if EVAL_CASES[value].polarity == 'positive' else '−'} "
            f"{EVAL_CASES[value].title}"
        ),
        key="prompt-case",
    )
    case = EVAL_CASES[case_id]
    left, right = st.columns(2)
    with left:
        st.markdown("**Вход кейса**")
        st.code(case.request.text, language=None)
    with right:
        st.markdown("**Ожидаемый результат**")
        st.json(case.expected.model_dump(mode="json"))

    extraction_prompt = st.text_area(
        "System prompt · extraction",
        value=DEFAULT_EXTRACTION_PROMPT,
        height=210,
        key=f"extraction-prompt-{case_id}",
        help="Должен вернуть ExtractedFacts с точными evidence-цитатами.",
    )
    drafting_prompt = st.text_area(
        "System prompt · response drafting",
        value=DEFAULT_DRAFTING_PROMPT,
        height=150,
        key=f"drafting-prompt-{case_id}",
        help="Работает только после детерминированного решения и не может его менять.",
    )

    st.caption(
        "Override хранится только в текущей UI-сессии. Глобальные defaults находятся "
        "в `src/text2business/prompts.py`. После тюнинга кейса прогоните весь датасет."
    )
    selected_button, regression_button = st.columns(2)
    run_selected = selected_button.button(
        "Запустить кейс с этими промптами",
        type="primary",
        disabled=config is None,
        width="stretch",
    )
    run_regression = regression_button.button(
        "Прогнать весь датасет с этими промптами",
        disabled=config is None,
        width="stretch",
    )
    if run_selected or run_regression:
        assert config is not None
        client = StructuredGatewayClient(config)
        extractor = GatewayExtractor(client, system_prompt=extraction_prompt)
        drafter = GatewayResponseDrafter(client, system_prompt=drafting_prompt)
        cases = EVAL_DATASET.cases if run_regression else [case]
        with st.spinner(f"Model-run: {len(cases)} кейсов…"):
            runs = execute_eval_cases(
                cases,
                extractor=extractor,
                drafter=drafter,
                execution_mode="gateway",
                extraction_prompt=extraction_prompt,
                drafting_prompt=drafting_prompt,
            )
        _store_eval_runs(runs)
        passed = sum(run.passed for run in runs)
        if passed == len(runs):
            st.success(f"Model-run: {passed}/{len(runs)} PASS. Откройте вкладку «Запуски».")
        else:
            st.error(f"Model-run: {passed}/{len(runs)} PASS. Смотрите expected vs actual и trace.")


def main() -> None:
    """Render the local eval console without moving business rules into the UI."""

    st.set_page_config(
        page_title="Text2Business Eval Console",
        page_icon="🧭",
        layout="wide",
    )
    st.title("Text2Business · Eval Console")
    st.caption(
        "Датасет → выполнение → проверка ожиданий → trace. "
        "Все предложения остаются dry-run."
    )

    dataset_tab, runs_tab, prompt_tab, manual_tab = st.tabs(
        ["1 · Тестовый датасет", "2 · Запуски", "3 · Prompt Lab", "Свободный ввод"]
    )
    with dataset_tab:
        _render_dataset_tab()
    with runs_tab:
        _render_runs_tab()
    with prompt_tab:
        _render_prompt_lab_tab()
    with manual_tab:
        _render_manual_tab()


if __name__ == "__main__":
    main()
