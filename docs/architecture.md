# Архитектура

```text
IncomingRequest + trusted CRM identity
  -> bounded synchronous harness
  -> pre-extraction safety scan of message + attachment
  -> deterministic extractor OR allowlisted OpenAI-compatible Gateway extractor
  -> typed read-only repository tools
  -> deterministic identity/scope/repeat/priority/SLA/capacity policies
  -> dry-run TicketChangeProposal
  -> optional response drafting
  -> CaseResult + evidence + redacted trace + final decision event
```

LLM выполняет только две допустимые задачи: structured extraction с точными
цитатами и опциональный черновик ответа. Все default-промпты написаны на русском.
Код всегда проверяет evidence, блокирует неподтверждённые обещания выезда и сам
принимает финальные решения.

Prompt defaults вынесены в `prompts.py`; UI может передать case-specific override
только этим двум LLM-компонентам. Каждый model eval хранит snapshot использованных
prompts рядом с expected vs actual и trace, поэтому сравнение воспроизводимо.

`JsonCorporateRepository` имитирует CRM, реестр объектов и оборудования, договоры, тикеты и загрузку команд. Все границы описаны строгими Pydantic-моделями. Единственная write-like операция — чистая функция `propose_ticket_change`; JSON не меняется.

Прототип синхронный и однопроцессный. Очереди, durable execution, retries внешних записей, HA/DR и autoscaling не реализованы. Следующий production-шаг: bounded ingress queue, идемпотентные workers, outbox/inbox, reconciliation, persistent run state и circuit breakers `CLOSED/OPEN/HALF_OPEN` вокруг gateway и внешних адаптеров.

Подробности: [сущности](domain-model.md), [harness](harness.md), [технический дизайн](specifications/service-request-triage/technical-design.md).
