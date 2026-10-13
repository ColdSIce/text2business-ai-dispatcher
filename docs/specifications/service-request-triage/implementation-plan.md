# Триаж сервисного обращения — Implementation Plan

**Статус:** Implemented and verified

**Дата:** 2026-10-13

**Основание:** [requirements](requirements.md) и
[technical design](technical-design.md).

## 1. Prerequisites

- Requirements и technical design согласованы.
- Реальные внешние writes запрещены; fixture остаётся read-only.
- Python остаётся `3.12.*`, Pydantic — v2, один lockfile.
- Model path работает только через разрешённый gateway; tests используют fake.

## 2. Slice 1 — Domain contracts и fixtures

**Изменения**

- Расширить модели trusted identity, customer, ticket lifecycle, repeat,
  priority/SLA/capacity assessments, decision и proposal.
- Добавить customers, closed tickets, SLA deadlines и capacity в JSON fixture.
- Перевести code contract на `TicketChangeProposal*`.
- Добавить docstrings/field descriptions для сущностей и неочевидных полей.

**Зависимости:** approved requirements.

**Проверка:** Pydantic schema tests, fixture validation, `extra=forbid`.

**Удаляемый legacy:** старые модели изменения и `open_tickets`-only fixture shape.

**Оставшийся риск:** правила ещё не подключены к workflow.

## 3. Slice 2 — Deterministic domain services

**Изменения**

- Реализовать scoped entity resolution и read-only repository tools.
- Реализовать open/closed repeat с окном 30 дней.
- Реализовать P1–P4 и priority override с обязательной причиной.
- Реализовать Gold/Standard/Basic SLA через `zoneinfo`.
- Реализовать capacity feasibility и decision policy.
- Реализовать stable idempotency и typed proposal planner.

**Зависимости:** Slice 1.

**Проверка:** unit tests всех границ рабочего времени, repeat, priority,
capacity, decisions и idempotency.

**Удаляемый legacy:** монолитные `rules.py` и lookup-решения внутри workflow.

**Оставшийся риск:** end-to-end pipeline ещё не собран.

## 4. Slice 3 — LLM boundary и bounded harness

**Изменения**

- Ввести `ExtractorPort`, deterministic implementation и optional gateway extractor.
- Добавить structured extraction, evidence validation и одну repair-попытку.
- Добавить optional response drafting с deterministic fallback.
- Усилить harness: call budgets, duplicate tool signature, wall-clock deadline,
  terminal-state guard и безопасный trace.
- Валидировать gateway config: HTTPS, явный hostname allowlist и запрет public providers.

**Зависимости:** Slice 1.

**Проверка:** fake gateway success/schema failure/timeout; loop/limit tests;
никаких сетевых вызовов в default test run.

**Удаляемый legacy:** extractor без интерфейса и неограниченные повторные вызовы.

**Оставшийся риск:** production breaker/queue/durable execution сознательно не входят.

## 5. Slice 4 — End-to-end workflow и scenarios

**Изменения**

- Собрать последовательный workflow по design decision matrix.
- Добавить full, ambiguity, open repeat, closed repeat, SLA variants, P1,
  missing identity, conflict, busy capacity, approval и injection scenarios.
- Реализовать dispatcher priority override в памяти.
- Обновить CLI на единый `CaseResult`.

**Зависимости:** Slices 1–3.

**Проверка:** integration/eval suite, fixture digest до/после, стабильный trace.

**Удаляемый legacy:** старый `run_case()` и четыре узких ожидаемых результата.

**Оставшийся риск:** UI ещё не проверен человеком.

## 6. Slice 5 — Streamlit UI

**Изменения**

- Добавить scenario picker и форму обращения/trusted CRM identity.
- Показать status, facts/evidence, corporate context, repeat, priority/SLA,
  capacity, proposal, response, warnings и trace.
- Добавить локальный priority override с обязательной причиной.
- Отразить loading/error/ambiguous/P1/ready states без зависимости только от цвета.

**Зависимости:** Slice 4.

**Проверка:** import/smoke test и ручной desktop smoke на реальном содержимом.

**Удаляемый legacy:** нет; CLI остаётся диагностическим входом.

**Оставшийся риск:** mobile layout вне MVP.

## 7. Slice 6 — Документация, CI и release evidence

**Изменения**

- Обновить README, installation, usage, architecture, models, harness, evals и metrics.
- Зафиксировать зависимости в единственном lockfile.
- Добавить GitHub Actions для tests и CLI scenarios.
- Проверить CLI, Streamlit, Docker и отсутствие запрещённых gateway hosts.

**Зависимости:** Slices 1–5.

**Проверка:** `pytest`, все CLI scenarios, Streamlit startup smoke,
`docker build` и container scenario.

**Удаляемый legacy:** устаревшие названия/документация.

**Оставшийся риск:** real gateway и нагрузочные испытания требуют отдельной среды.

## 8. Migration и compatibility

- Production migration/backfill отсутствуют.
- Fixture меняется атомарно вместе с моделями и tests.
- Старый JSON CLI contract не сохраняется; версия проекта становится `0.2.0`.
- Compatibility aliases старых названий изменения не создаются.

## 9. Observability и operational checks

- Trace фиксирует model/tool/rule/proposal/review steps без chain-of-thought.
- Run metadata содержит budgets, latency и terminal state.
- Eval summary покрывает resolution, decisions, repeat, SLA и unsafe proposal rate.
- Надёжное выполнение, queues, HA и circuit breakers остаются documented next step,
  а не скрытой неполной реализацией.

## 10. Rollout и rollback

- Rollout: локальные tests → CLI scenarios → Streamlit smoke → Docker smoke.
- Gateway выключен по умолчанию и проверяется отдельно при наличии credentials.
- Rollback: возврат к предыдущему Git commit; data rollback не требуется.
- Реальные внешние действия отсутствуют на всех этапах.

## 11. Definition of Done

- Все FR-001–FR-014 реализованы и связаны с tests.
- Acceptance cases из requirements проходят детерминированно.
- Все модели документированы.
- UI демонстрирует полный поток и наглядный пример.
- Unsafe proposal rate в eval corpus равен `0`.
- Fixtures не изменяются во время run.
- README ведёт к установке, архитектуре, использованию, evals, метрикам и spec.
- CI, CLI, Streamlit и Docker проверки пройдены либо внешний gate явно указан.
