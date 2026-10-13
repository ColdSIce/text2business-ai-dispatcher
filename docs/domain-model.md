# Сущности и модели

Все внешние границы — строгие Pydantic v2 модели с `extra="forbid"`. Каждая модель и нетривиальное поле имеют комментарий в коде.

| Группа | Модели | Назначение |
|---|---|---|
| Вход | `IncomingRequest`, `TrustedContactIdentity` | Один контакт и подтверждённая CRM-идентичность. |
| Извлечение | `EvidenceFact`, `ExtractedFacts` | Значение, точная цитата, confidence и provenance. |
| Корпоративные данные | `Customer`, `Site`, `Asset`, `Contract`, `Ticket`, `ServiceCapacity`, `CorporateData` | Read-only источник истины для решений. |
| Tool contracts | `FindCustomers*`, `FindSites*`, `FindAssets*`, `GetContract*`, `FindTickets*`, `GetCapacity*` | Типизированные запросы и ответы repository-tools. |
| Аналитика | `Resolution`, `RepeatAssessment`, `PriorityAssessment`, `SlaAssessment`, `CapacityAssessment` | Промежуточные детерминированные выводы с reason codes. |
| Решение | `Decision`, `PriorityOverride` | Действие, готовность к review и контролируемое переопределение приоритета. |
| Предложение | `TicketChangeProposal`, `TicketChangeProposalOutput` | Dry-run create/update; подтверждение человека обязательно. |
| Выполнение | `RunLimits`, `RunMetadata`, `TraceEvent`, `CaseResult` | Бюджеты, terminal state, trace и полный результат. |

`TicketChangeProposal` возникает только при подтверждённой CRM-идентичности, однозначных customer/site/asset, найденном договоре и безопасном решении. Для открытого повтора предлагается update с текущей версией и исходным SLA; для закрытого повтора до 30 дней — новый связанный тикет с новым SLA.

`dry_run` типизирован как `Literal[True]`. Реальную запись нельзя включить конфигурацией. P1 всегда помечается для немедленного review, но безопасное предложение может быть подготовлено.
