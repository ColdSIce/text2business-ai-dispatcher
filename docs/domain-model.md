# Сущности и модели

Все внешние границы описаны строгими Pydantic-моделями с `extra="forbid"`. Неизвестное поле считается ошибкой, а не молча отбрасывается.

## Вход и извлечённые данные

| Модель | Назначение |
|---|---|
| `IncomingRequest` | Канал, отправитель, timezone-aware время, клиентский текст и опциональный текст вложения. |
| `EvidenceFact` | Значение, точная цитата, confidence и provenance одного факта. |
| `ExtractedFacts` | Клиент, объект, оборудование, проблема, симптомы, срок, резерв, прошлое обращение и признак небезопасной инструкции. |

## Корпоративные сущности

| Модель | Назначение |
|---|---|
| `Site` | Объект обслуживания и его часовой пояс. |
| `Asset` | Оборудование, принадлежащее одному объекту. |
| `Contract` | SLA, сервисное окно и покрытие объекта. |
| `Ticket` | Открытая заявка с версией для optimistic concurrency. |
| `CorporateData` | Read-only набор тестовых объектов, оборудования, договоров и заявок. |

`SiteMatch` и `AssetMatch` содержат кандидата и явные причины совпадения. Они отделены от resolved-сущности: наличие кандидата не означает, что система имеет право его выбрать.

## Tool contracts

Каждый mock-tool имеет отдельные input/output модели:

- `FindSiteInput` / `FindSiteOutput`;
- `FindAssetsInput` / `FindAssetsOutput`;
- `GetContractInput` / `GetContractOutput`;
- `FindOpenTicketsInput` / `FindOpenTicketsOutput`;
- `TicketMutationInput` / `TicketMutationOutput`.

Tools возвращают данные, но не принимают бизнес-решение.

## Решение и SLA

| Модель | Назначение |
|---|---|
| `PriorityAssessment` | Приоритет `P1–P4` и reason codes. |
| `SlaAssessment` | Применимый SLA и рассчитанный deadline. |
| `Decision` | Одно действие: создать, обновить, уточнить или передать диспетчеру. |
| `CaseResult` | Итог: факты, кандидаты, resolved-данные, решение, mutation, ответ и trace. |

## Когда возникает mutation

`TicketMutationInput` формируется только когда одновременно выполнены условия:

1. Нет prompt injection или конфликта scope.
2. Клиент и объект определены однозначно.
3. Оборудование определено однозначно внутри объекта.
4. Договор найден, SLA можно рассчитать.
5. Найдено не более одной открытой заявки.

Если открытых заявок нет, предлагается `create_new` с `expected_version=0`. Если найдена ровно одна, предлагается `update_existing` с её текущей версией. Любая неоднозначность, отсутствие договора или несколько тикетов приводят к уточнению либо передаче диспетчеру без mutation.

В прототипе `dry_run` типизирован как `Literal[True]`: передать `false` невозможно даже случайно. JSON-хранилище никогда не изменяется.

## Harness и trace

| Модель | Назначение |
|---|---|
| `RunLimits` | Максимум tools, model calls и mutations. |
| `RunMetadata` | `run_id`, `trace_id`, terminal state и фактические счётчики. |
| `TraceEvent` | Один безопасный шаг extraction/tool/rule/mutation без chain-of-thought. |

