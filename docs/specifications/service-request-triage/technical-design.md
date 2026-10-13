# Триаж сервисного обращения — Technical Design

**Статус:** Implemented

**Дата:** 2026-10-13

**Основание:** [approved requirements](requirements.md)

## 1. Цели дизайна

- Реализовать один объяснимый вертикальный срез от обращения до результата триажа.
- Сохранить все бизнес-решения детерминированными и тестируемыми.
- Добавить CRM identity, все три SLA, repeat для открытых/закрытых заявок,
  capacity и ручной priority override.
- Гарантировать отсутствие реальных изменений корпоративных систем.
- Уложить common path в ≤2 минут человеческого триажа.

## 2. Non-goals

- Production CRM/ticketing integrations и выполнение proposed changes.
- База данных, очередь, event bus, distributed workflow или микросервисы.
- Отказоустойчивое/durable выполнение, HA/DR, autoscaling, backpressure и
  гарантированная обработка очереди при пиках нагрузки.
- Маршрутизация инженеров, booking слотов и оптимизация расписания.
- Бинарные вложения, OCR и speech-to-text.
- Production auth/RBAC, holiday calendar и долговременное хранение audit log.

## 3. Базовое состояние до реализации

Текущий Python 3.12 пакет — локальный модульный монолит:

```text
CLI -> run_case()
    -> DeterministicExtractor
    -> MockCorporateTools(JSON)
    -> priority/SLA rules
    -> dry-run ticket proposal
    -> CaseResult + trace
```

Сильные стороны, которые сохраняются:

- строгие Pydantic v2 contracts с `extra="forbid"`;
- read-only JSON fixtures;
- bounded harness: 8 tools, 2 model calls, 1 proposal;
- deterministic tests без сети и платной модели;
- evidence и безопасный trace.

Подлежащие замене ограничения:

- `IncomingRequest.sender` не является trusted CRM identity;
- customer дублируется внутри `Site`, отдельной модели нет;
- `Ticket` не содержит lifecycle timestamps и SLA deadline;
- lookup возвращает только открытые tickets;
- SLA parser поддерживает только `60 minutes / 24x7`;
- priority не различает безопасность, растущую температуру и надёжность резерва;
- нет repeat/capacity/review status/override моделей;
- старый контракт изменения заявки не использует бизнес-модель proposal;
- missing contract приводит к exception вместо контролируемого результата.

## 4. Выбранная архитектура

Один процесс и одна последовательная orchestration-функция. Слои разделены
интерфейсами, но остаются в одном Python package:

```text
CLI / Streamlit
      |
      v
Application workflow + HarnessGuard
      |
      +--> ExtractorPort --------> deterministic fake | Finland gateway
      +--> CorporateDataPort ----> read-only JSON adapter
      +--> deterministic domain services
      |      identity resolution
      |      site/asset resolution
      |      repeat classification
      |      priority + override
      |      SLA calendar
      |      capacity assessment
      |      decision policy
      +--> ProposalPlanner ------> typed dry-run proposal only
      |
      v
CaseResult + safe trace
```

### Почему так

- Один bounded request не требует распределённого состояния.
- Ports позволяют заменить fixture или extractor без изменения бизнес-правил.
- Чистые domain functions дают детерминированные unit tests.
- Последовательный trace проще объяснить на интервью и проверить в evals.

### 4.1 Наглядный end-to-end пример

Вход от CRM и расшифровки звонка:

```json
{
  "source_request_id": "call-2026-08-13-0042",
  "channel": "call_transcript",
  "received_at": "2026-08-13T16:40:00+03:00",
  "identity": {
    "customer_id": "C-101",
    "contact_id": "CONTACT-17",
    "source": "crm_telephony",
    "verified": true
  },
  "text": "Дмитровский объект, снова ХУ-17. Температура 8,3 и растёт. Резервная камера есть, но не уверены, что выдержит товар. Нужен человек сегодня до 19:00."
}
```

Поток обработки:

```text
trusted CRM metadata                       untrusted transcript
          |                                        |
          +----------------+-----------------------+
                           v
                 LLM structured extraction
                 (model call 1, no tools)
                           |
                           v
                 Pydantic ExtractedFacts
                 + evidence + confidence
                           |
                           v
                   bounded orchestrator
                           |
       +-------------------+---------------------------+
       | exact typed read-tools, called by application |
       v                                               v
customer -> site -> asset -> contract -> tickets -> capacity
                           |
                           v
      deterministic repeat + priority + SLA + decision rules
                           |
                           v
             typed dry-run TicketChangeProposal
                           |
                           v
                 response drafting template
                 or model call 2 (no tools)
                           |
                           v
                    CaseResult + trace
```

Model call 1 возвращает только проверяемые факты:

```json
{
  "site": {
    "value": "Дмитровский объект",
    "evidence": "Дмитровский объект",
    "confidence": 0.94,
    "provenance": "message"
  },
  "asset": {
    "value": "ХУ-17",
    "evidence": "ХУ-17",
    "confidence": 1.0,
    "provenance": "message"
  },
  "symptoms": [
    {
      "value": "temperature_rising: 8.3 C",
      "evidence": "Температура 8,3 и растёт",
      "confidence": 0.98,
      "provenance": "message"
    }
  ],
  "backup_status": {
    "value": "uncertain",
    "evidence": "Резервная камера есть, но не уверены, что выдержит товар",
    "confidence": 0.55,
    "provenance": "message"
  },
  "desired_deadline": {
    "value": "2026-08-13T19:00:00+03:00",
    "evidence": "сегодня до 19:00",
    "confidence": 0.96,
    "provenance": "message"
  },
  "previous_contact": {
    "value": true,
    "evidence": "снова ХУ-17",
    "confidence": 0.90,
    "provenance": "message"
  }
}
```

После schema validation приложение само вызывает tools:

| Шаг | Typed tool | Результат |
|---|---|---|
| 1 | `get_customer(C-101)` | `СеверФуд` |
| 2 | `find_sites(C-101, "Дмитровский объект")` | единственный `S-MSK-01` |
| 3 | `find_assets(S-MSK-01, "ХУ-17")` | единственный `A-1001`, criticality high |
| 4 | `get_contract(S-MSK-01)` | Gold, 60 минут, 24×7 |
| 5 | `find_tickets(C-101, S-MSK-01, A-1001)` | одна открытая `T-884`, SLA deadline 16:55 |
| 6 | `get_capacity(refrigeration, Moscow)` | ближайшее время 17:20 |

Обычный код получает результат:

- repeat: `OPEN`, update `T-884`;
- SLA: исходный deadline `16:55` сохраняется, до нарушения 15 минут;
- priority: `P2`, потому что температура растёт, asset critical, резерв ненадёжен;
- requested time `19:00` не меняет SLA/priority, capacity успевает, но не
  превращается в обещание выезда;
- action: `UPDATE_EXISTING`;
- review status: `READY_FOR_REVIEW`;
- proposal: dry-run, `expected_version=1`, реальной записи нет.

Карточка диспетчера показывает: исходные цитаты, найденные сущности, P2,
действующий SLA 16:55, риск нарушения, repeat к `T-884`, доступность 17:20,
предлагаемый payload и черновик ответа. Диспетчер проверяет её, а система ничего
не отправляет и не записывает.

## 5. Границы модулей

| Модуль | Ответственность | Не делает |
|---|---|---|
| `models.py` | Pydantic contracts, enums, validators и комментарии к семантике | Бизнес-вычисления |
| `extractor.py` | Извлечение фактов и evidence через единый `ExtractorPort` | Entity resolution и решения |
| `repository.py` | `CorporateDataPort` и read-only JSON adapter | Приоритет, SLA и выбор действия |
| `resolution.py` | Trusted identity, site и asset candidates | Никаких fuzzy guesses вне scope |
| `repeat.py` | Классификация open/closed repeat | Изменение tickets |
| `priority.py` | Рассчитанный priority и валидированный override | SLA и scheduling |
| `sla.py` | Gold/Standard/Basic deadlines | Прибытие инженера |
| `capacity.py` | Feasibility и deterministic ordering inputs | Booking/оптимизация |
| `decision.py` | Review status, action, automation assessment и reason codes | Внешняя запись |
| `proposal.py` | Idempotent `TicketChangeProposal` | Выполнение proposal |
| `workflow.py` | Порядок вызовов, early exits, result и trace | Скрытые business rules |
| `harness.py` | Run IDs, limits и terminal state | Domain decisions |
| `app.py` / `cli.py` | Представление одного и того же `CaseResult` | Собственная бизнес-логика |

Для прототипа допустимо сначала сохранить меньше файлов, если эти границы
остаются явными функциями и не образуется второй pipeline.

## 6. Source of truth и invariants

### Source of truth

- Корпоративные сущности: `corporate.json`, загружаемый один раз как immutable
  `CorporateData` на run.
- Извлечённые факты: validated `ExtractedFacts`, но не канонические customer/site/asset.
- Канонические сущности: только результат typed repository lookup.
- Priority/SLA/repeat/capacity: только deterministic domain services.
- Итог: один `CaseResult`; UI не пересчитывает правила самостоятельно.

### Invariants

1. Один вход создаёт один bounded run и один terminal result.
2. Не более одного `TicketChangeProposal` на run.
3. Proposal всегда `dry_run=true` и `requires_human_confirmation=true`.
4. Без trusted/подтверждённого customer, уникального site/asset и валидного
   contract proposal отсутствует.
5. LLM не получает corporate tools и не выбирает сущности или решения.
6. P1 всегда `NEEDS_DISPATCHER_REVIEW`, но безопасный proposal допустим.
7. Открытый repeat сохраняет исходный SLA; закрытый repeat создаёт новый SLA.
8. Repeat status сам по себе не повышает priority.
9. Customer requested time и capacity не меняют contractual SLA или priority.
10. Fixture bytes до и после run идентичны.

## 7. Доменная модель

Каждый класс и enum получает docstring. Каждое неочевидное поле получает
`Field(description=...)`; обязательно документируются timezone, единицы,
trusted/untrusted origin и `null` semantics.

### 7.1 Вход и evidence

| Модель | Основные поля | Комментарий |
|---|---|---|
| `TrustedContactIdentity` | `customer_id`, `contact_id?`, `source`, `verified` | Metadata доверенного канала. `verified=false` не даёт права на proposal. |
| `IncomingRequest` | `source_request_id`, `channel`, `received_at`, `identity?`, `sender_display?`, `text`, `attachment_text?` | `source_request_id` стабилизирует idempotency; текст и display name недоверенные. |
| `EvidenceFact[T]` | `value`, `evidence`, `confidence`, `provenance` | Evidence — точный фрагмент источника; confidence не заменяет rules. |
| `ExtractedFacts` | customer/site/asset/problem/symptoms/requested time/backup status/previous contact/suspicious instruction | Nullable structured interpretation до lookup. |

### 7.2 Корпоративные данные

| Модель | Основные поля | Комментарий |
|---|---|---|
| `Customer` | `customer_id`, `name`, `aliases` | Канонический tenant-like scope для поиска. |
| `Site` | `site_id`, `customer_id`, `address`, `region`, `timezone` | IANA timezone обязательна. |
| `Asset` | `asset_id`, `site_id`, `local_code`, `asset_type`, `criticality`, `service_group` | `local_code` уникален только внутри site. |
| `Contract` | `contract_id`, `site_id`, `plan`, `response_sla`, `service_window`, `coverage` | SLA относится к первичному содержательному ответу. |
| `Ticket` | `ticket_id`, `asset_id`, `created_at`, `closed_at?`, `status`, `summary`, `version`, `sla_deadline`, `last_contact_at` | Terminal ticket неизменяем; version нужна для stale check. |
| `ServiceCapacity` | `service_group`, `region`, `next_available_at` | Информационная доступность, не reservation. |
| `CorporateData` | `current_time`, collections above | Полностью validated read-only snapshot. |

### 7.3 Assessments и результат

| Модель | Основные поля | Комментарий |
|---|---|---|
| `RepeatAssessment` | `kind`, `related_ticket_id?`, `repeat_after_resolution`, `contact_count`, `reason_codes` | `kind`: none/open/closed. |
| `PriorityAssessment` | `calculated`, `effective`, `reason_codes`, `override?` | Calculated никогда не перезаписывается. |
| `PriorityOverride` | `priority`, `reason`, `actor`, `changed_at` | Reason непустой; SLA не меняет. |
| `SlaAssessment` | `contract_id`, `kind`, `deadline`, `timezone`, `reason_codes`, `source_ticket_id?` | Open repeat ссылается на исходный ticket SLA. |
| `CapacityAssessment` | `service_group`, `region`, `next_available_at`, `requested_by?`, `feasibility`, `reason_codes` | `feasibility`: available/requested_time_unconfirmed/unknown. |
| `Decision` | `action`, `review_status`, `automation_assessment`, `reason_codes`, `explanation` | Один итоговый business outcome. |
| `TicketChangeProposal` | `idempotency_key`, `expected_version`, `operation`, `target_ticket_id?`, `related_ticket_id?`, `payload`, constants | Никогда не исполняется в MVP. |
| `CaseResult` | request, facts, candidates, resolved entities, assessments, decision, proposal?, response, questions, warnings, trace | Единственный UI/CLI contract. |

### 7.4 Enums

- `Action`: `CREATE_NEW`, `UPDATE_EXISTING`, `REQUEST_CLARIFICATION`,
  `HANDOFF_TO_DISPATCHER`, `REQUIRES_ADDITIONAL_APPROVAL`.
- `ReviewStatus`: `READY_FOR_REVIEW`, `NEEDS_CLARIFICATION`,
  `NEEDS_DISPATCHER_REVIEW`.
- `AutomationAssessment`: `POTENTIALLY_AUTOMATABLE`, `HUMAN_REQUIRED`.
- `RepeatKind`: `NONE`, `OPEN`, `CLOSED`.
- `BackupStatus`: `CONFIRMED`, `UNCERTAIN`, `UNAVAILABLE`, `UNKNOWN`.
- `SlaKind`: `CALENDAR_MINUTES`, `BUSINESS_HOURS`, `NEXT_BUSINESS_DAY`.
- `TerminalState`: `COMPLETED`, `NEEDS_USER_INPUT`, `HANDED_OFF`, `FAILED`.

## 8. Typed repository/tool contracts

Разрешённый реестр содержит только bounded typed operations:

1. `get_customer(customer_id)` — exact lookup trusted identity.
2. `find_sites(customer_id, query)` — candidates только внутри customer scope.
3. `find_assets(site_id, query)` — candidates только внутри resolved site.
4. `get_contract(site_id)` — один contract или explicit missing.
5. `find_tickets(customer_id, site_id, asset_id)` — open и recent closed tickets.
6. `get_capacity(service_group, region)` — одна capacity record или explicit unknown.
7. `propose_ticket_change(input)` — pure dry-run echo/validation, без записи.

Каждый input/output — отдельная строгая Pydantic model. Tool не выбирает
priority, SLA, repeat kind или final action. Customer-provided IDs никогда не
используются напрямую без проверки scope.

## 9. Workflow

### 9.1 Последовательность

1. Валидировать `IncomingRequest`; создать stable run/trace IDs.
2. Извлечь факты через `ExtractorPort`; проверить evidence coverage.
3. Проверить suspicious instructions. LLM output остаётся данными.
4. Разрешить customer:
   - verified identity → exact customer lookup;
   - identity отсутствует → показать candidates, `NEEDS_DISPATCHER_REVIEW`, без proposal;
   - CRM/text conflict → `NEEDS_DISPATCHER_REVIEW`, без proposal.
5. Разрешить site и asset внутри подтверждённого scope; неоднозначность даёт
   один следующий блокирующий вопрос.
6. Получить contract, tickets и capacity.
7. Классифицировать repeat.
8. Рассчитать priority и SLA.
9. Оценить capacity и customer requested time без изменения priority/SLA.
10. Применить decision policy.
11. Если policy разрешает — сформировать максимум один dry-run proposal.
12. Сформировать draft response и terminal `CaseResult`.

### 9.2 Decision policy

| Условие | Review status | Proposal |
|---|---|---|
| Уникальные данные, P2–P4 | `READY_FOR_REVIEW` | Да |
| P1 при полных данных | `NEEDS_DISPATCHER_REVIEW` | Да |
| Нет trusted/подтверждённой identity | `NEEDS_DISPATCHER_REVIEW` | Нет |
| Неоднозначный site/asset | `NEEDS_CLARIFICATION` | Нет |
| CRM/text conflict или prompt injection | `NEEDS_DISPATCHER_REVIEW` | Нет |
| Более одной открытой заявки | `NEEDS_DISPATCHER_REVIEW` | Нет |
| Missing contract / tool failure | `NEEDS_DISPATCHER_REVIEW` | Нет |
| Coverage/cost exception | `NEEDS_DISPATCHER_REVIEW` + `REQUIRES_ADDITIONAL_APPROVAL` | Нет |

## 10. Repeat algorithm

1. Repository фильтрует только exact customer + site + asset.
2. Tickets сортируются по `created_at DESC`, затем `ticket_id` для стабильности.
3. Если открытых >1 — fail closed.
4. Если открытая одна:
   - `RepeatKind.OPEN`;
   - action `UPDATE_EXISTING`;
   - SLA берётся из ticket, не пересчитывается;
   - фиксируется новый contact timestamp;
   - repeat не меняет priority.
5. Если открытых нет, выбирается самая свежая closed с `closed_at` не старше
   30 календарных дней от `received_at`:
   - `RepeatKind.CLOSED`;
   - action `CREATE_NEW`;
   - `related_ticket_id` указывает на неё;
   - SLA рассчитывается заново.
6. Иначе `RepeatKind.NONE` и `CREATE_NEW`.

В MVP метрики вычисляются по eval dataset, а не сохраняются в отдельное хранилище.

## 11. Priority и override

Чистая функция принимает asset criticality и актуальные facts. Надёжность
резерва задаётся enum `BackupStatus`, а не выводится из порога confidence:

- P1: safety threat или полный отказ без резерва;
- P2: растущая температура, critical asset или надёжность резерва не подтверждена;
- P3: malfunction + подтверждённый резерв + нет немедленного product risk;
- P4: informational/noncritical.

Число температуры без допустимого диапазона — evidence, но не самостоятельный
порог. Repeat flag и customer requested time не входят в priority function.

`apply_priority_override()` принимает исходный assessment и `PriorityOverride`.
Пустая причина отклоняется. Trace хранит calculated/effective priority и reason.

## 12. SLA calendar

Используется стандартный `zoneinfo`, без внешней библиотеки:

- Gold: `received_at + 60 minutes`, 24×7.
- Standard: добавить 4 рабочих часа внутри 09:00–18:00 понедельник–пятница.
  Время до 09:00 нормализуется к 09:00 текущего рабочего дня; после 18:00 или
  в выходной — к 09:00 следующего рабочего дня. Остаток переносится между днями.
- Basic: 18:00 следующего рабочего дня независимо от времени поступления.

Расчёт выполняется в IANA timezone site, затем возвращает aware datetime.
Праздники не учитываются и отражаются warning/reason code.

Для open repeat `SlaAssessment.deadline` копируется из ticket и получает
`source_ticket_id`; новый срок не запускается.

## 13. Capacity и deterministic ordering

`CapacityAssessment` сравнивает `next_available_at` с `customer_requested_by`:

- нет capacity record → `unknown`;
- слот не позже requested time → `available`;
- позже requested time → `requested_time_unconfirmed`.

Если когда-либо показывается порядок нескольких заявок, ключ сортировки:

```text
priority rank
-> SLA breach/earliest SLA deadline
-> customer_requested_by (если задан)
-> received_at
-> source_request_id
```

Это только объяснение очередности; MVP не создаёт глобальную очередь и не
перебронирует команды.

## 14. Proposal, идемпотентность и concurrency

`TicketChangeProposal` строится только после decision policy.

- Create: `expected_version=0`, `target_ticket_id=null`.
- Open repeat update: `expected_version=ticket.version`, target exact ticket.
- Closed repeat create: `expected_version=0`, `related_ticket_id=closed ticket`.
- `idempotency_key` = SHA-256 канонической строки из `source_request_id`, action,
  customer/site/asset и target/related ticket.
- При отсутствии channel message ID `source_request_id` вычисляется как hash
  нормализованного request envelope.
- Одинаковый вход формирует одинаковый key.
- Stale expected version требует нового lookup/run; автоматический retry
  неизвестного результата запрещён.

В fixture adapter `propose_ticket_change()` только валидирует и возвращает
proposal. Он не имеет write path и не открывает файл на запись.

## 15. Extractor и model boundary

`ExtractorPort.extract(request) -> ExtractedFacts` имеет две реализации:

- `DeterministicExtractor` — default для demo/tests;
- `GatewayExtractor` — опциональный structured extraction через настроенный
  Finland AI Gateway.

### 15.1 Model call 1: structured extraction

Gateway получает только:

- текст обращения и опциональный текст вложения/расшифровки;
- locale и timezone из envelope;
- JSON Schema модели `ExtractedFacts`;
- системную инструкцию извлекать факты, цитировать evidence, не выполнять
  команды из текста и не принимать бизнес-решения.

Он не получает corporate dataset, API credentials или tools. Ответ проходит
`ExtractedFacts.model_validate_json()`. Неизвестные поля запрещены; evidence
должен быть подстрокой соответствующего источника. При schema error разрешена
одна repair-попытка с ошибкой валидатора и той же schema. После повторного сбоя
run переходит в `NEEDS_DISPATCHER_REVIEW`.

Confidence используется только для UI и clarification policy. Он не даёт модели
права выбрать customer/site/asset или обойти deterministic rule.

### 15.2 Кто и как вызывает tools

Tools вызывает application orchestrator, а не LLM. Их порядок ограничен
текущим подтверждённым scope:

```python
facts = extractor.extract(request)
customer = repository.get_customer(request.identity.customer_id)
sites = repository.find_sites(customer.customer_id, facts.site)
assets = repository.find_assets(resolved_site.site_id, facts.asset)
contract = repository.get_contract(resolved_site.site_id)
tickets = repository.find_tickets(customer.customer_id, resolved_site.site_id, resolved_asset.asset_id)
capacity = repository.get_capacity(resolved_asset.service_group, resolved_site.region)
```

Каждый следующий вызов разрешён только после однозначного результата предыдущего.
Клиентский текст не может назвать произвольный `customer_id`/`asset_id` и
расширить scope. При ambiguity цепочка останавливается до contract/ticket lookup.

Такой подход сохраняет полезную работу LLM на неструктурированном языке, но не
делает tool selection и бизнес-решения вероятностными.

### 15.3 Model call 2: response draft

После deterministic decision опциональный второй вызов получает только
редактированную итоговую карточку:

- подтверждённые customer/site/asset labels;
- effective priority и reason summary;
- contractual SLA deadline;
- capacity feasibility без обещания;
- выбранное action и clarification question при наличии.

Он возвращает `DraftResponse` по schema: `subject?`, `body`, `warnings[]`.
Draft не может изменить `CaseResult`; UI всегда показывает его как редактируемый
черновик. Если вызов недоступен, используется deterministic template.

### 15.4 Общие ограничения model path

Gateway path:

- допускает максимум один schema-repair retry;
- не может выбирать customer/site/asset, priority, SLA, repeat или action;
- при timeout/schema error возвращает controlled degraded result.

Gateway разрешается только по HTTPS и явному hostname allowlist; OpenRouter может
быть включён осознанно через `openrouter.ai`. Draft response
может использовать тот же gateway вторым и последним model call; deterministic
template остаётся fallback.

### 15.5 Защита от циклов

Workflow — конечный directed pipeline, а не свободный agent loop. LLM не может
самостоятельно повторно вызвать себя или tool. Harness дополнительно применяет:

- максимум 2 model calls, включая одну extraction repair-попытку;
- максимум 8 tool calls и один proposal;
- один вызов каждого логического lookup step на run;
- запрет повторного вызова с той же сигнатурой `tool + canonical input`;
- общий wall-clock deadline run и отдельные timeout для model/tool call;
- terminal state после первого завершённого decision;
- отсутствие recursive workflow invocation и automatic retry неизвестного
  результата.

Нарушение budget, повтор сигнатуры или deadline завершает run кодом
`RUN_LIMIT_EXCEEDED`/`LOOP_DETECTED`/`RUN_TIMEOUT`, без proposal после ошибки.

### 15.6 Circuit breakers на следующем этапе

В MVP нет cross-run circuit breaker: локальный процесс не хранит надёжное
состояние между запросами, а реальные пороги без telemetry были бы выдуманными.
Границы `GatewayClient` и будущих внешних repository adapters проектируются так,
чтобы breaker добавлялся без изменения domain services.

Production breaker для каждой внешней зависимости должен иметь состояния
`CLOSED -> OPEN -> HALF_OPEN`, rolling failure/timeout/latency metrics,
настраиваемый cooldown, ограниченные probe requests и отдельные reason codes.

- Gateway extraction failure: fail closed в dispatcher review.
- Gateway drafting failure: deterministic template fallback.
- Contract/ticketing failure: fail closed, proposal запрещён.
- Capacity failure: основной triage продолжается с `feasibility=unknown`.

Пороги определяются после измерения реальной нагрузки и закрепляются load/failure
tests; breaker state, transitions и rejected calls попадают в metrics/alerts.

## 16. Errors и degraded behavior

Ожидаемые бизнес-ошибки не бросают необработанные exceptions. Они становятся
typed `Decision`, warnings и terminal state.

| Failure | Результат |
|---|---|
| Invalid request schema | Ошибка валидации до run; UI показывает поля |
| Extractor timeout/schema error | Ручная проверка; raw input сохранён, tools не расширяются |
| Missing customer/site/asset | Clarification или dispatcher review |
| Missing contract | Dispatcher review, SLA отсутствует |
| Repository parse/corruption | `FAILED`, без proposal |
| Capacity missing | Основной triage продолжается, feasibility `unknown` |
| Proposal validation failure | `FAILED`, без partial result, кроме trace до ошибки |
| Harness limit | `FAILED` с reason code `RUN_LIMIT_EXCEEDED` |

Capacity — единственная необязательная зависимость: её отказ не скрывает основной
результат. Contract/ticket lookup fail closed, потому что влияет на действие.

## 17. Security, privacy и audit

- Allowlist tools задаётся кодом; shell/SQL/arbitrary HTTP/dynamic code отсутствуют.
- Identity scope проверяется перед site/asset/ticket lookup.
- Customer text, attachments и model output никогда не интерпретируются как tool instructions.
- Trace redaction запрещает secrets, chain-of-thought и полные provider payloads.
- `sender_display` и raw text не используются как authorization signal.
- Demo logs не содержат полный текст по умолчанию; UI показывает его локально.
- Fixture hash до/после scenario подтверждает отсутствие записи.

## 18. UI state

Streamlit — тонкий renderer поверх `CaseResult`:

1. Ввод: scenario picker или форма request + trusted CRM identity.
2. Summary: review status, action, effective priority, SLA deadline.
3. Evidence: компактная таблица facts/source/confidence.
4. Corporate context: customer, site, asset, contract, repeat и capacity.
5. Proposal: payload и явная маркировка «только предложение».
6. Response: редактируемый draft, но без кнопки внешней отправки.
7. Details: tools/reason codes/trace через progressive disclosure.

Error/loading/empty/ambiguous/P1/ready states различимы текстом и иконкой, не
только цветом. Все controls доступны с клавиатуры; timestamps показывают timezone.

Priority override — отдельное действие диспетчера с обязательным reason. Оно
пересчитывает только proposal/draft в памяти и добавляет trace event.

## 19. Observability и метрики

Каждый run пишет structured summary:

- `run_id`, `trace_id`, terminal/review status;
- latency total и по extraction/tools/rules;
- tool/model/proposal counts;
- reason codes без raw PII;
- calculated/effective priority и override flag;
- repeat kind, SLA kind и capacity feasibility.

Offline eval агрегирует:

- scenario pass rate;
- field accuracy/evidence coverage;
- resolution/decision/SLA accuracy;
- false merge и missed repeat;
- repeat contact / repeat after resolution / contacts per asset;
- unsafe proposal rate, target `0`;
- measured human triage time, target ≤2 минут.

## 20. Performance и limits

- Fixture загружается один раз на run; dataset мал, lookup O(n) допустим.
- Не более 8 tool calls, 2 model calls и 1 proposal.
- Все network calls имеют explicit timeout; retry только один для schema repair.
- UI не блокирует result из-за недоступной capacity.
- Для локального deterministic path целевой p95 ≤1 секунды; gateway budget
  задаётся отдельно и не влияет на двухминутный human KPI.

## 21. Граница надёжности и путь развития

### Что гарантирует MVP

- Один run выполняется синхронно в одном процессе.
- Harness ограничивает объём работы и не допускает бесконечный loop.
- Ошибка доступной зависимости превращается в контролируемый результат, пока
  сам процесс жив.
- Idempotency key делает повторное предложение распознаваемым, но не является
  гарантией надёжной доставки или exactly-once выполнения.

### Чего MVP не гарантирует

- Run теряется при падении или перезапуске процесса.
- Нет durable run state, resume, automatic retry и manual replay.
- Нет ingress queue, buffering, per-customer quotas и backpressure.
- Нет горизонтальных workers, leader election, HA, disaster recovery и SLO.
- Пиковая нагрузка может увеличить latency или привести к отказу запроса.
- Внешнее изменение заявки не выполняется, поэтому delivery semantics
  (`at-least-once`/`exactly-once`) не реализуются и не заявляются.

### Эволюционный путь после прототипа

Переход выполняется только при появлении реальной интеграции или измеренной
нагрузки, небольшими последовательными шагами:

1. **Измерить нагрузку:** latency, concurrency, error rate, размер payload и
   длительность model/tool calls; определить SLO и capacity budget.
2. **Сохранить run:** durable `RunRecord` с состоянием, входным fingerprint,
   terminal result и audit events; восстановление после restart.
3. **Добавить admission control:** bounded ingress queue, per-customer limits,
   backpressure и явный `retry_after`, без неограниченного накопления; добавить
   cross-run circuit breakers на gateway и внешние adapters.
4. **Разделить workers:** stateless API + horizontally scalable workers;
   leases/timeouts и контролируемые retry только для идемпотентных шагов.
5. **Надёжно выполнять реальные изменения:** transactional outbox/inbox,
   idempotency на стороне ticketing, reconciliation и manual replay неизвестных
   результатов. Это требуется только если dry-run когда-либо станет write path.
6. **Закрыть эксплуатацию:** dead-letter/manual-review path, dashboards,
   alerts, load/soak tests, backup/restore и disaster-recovery rehearsal.

Триггеры перехода: real ticketing write path, необходимость переживать restart,
несколько одновременных диспетчеров, p95 выше согласованного budget или
наблюдаемые пики, которые один bounded worker не обслуживает.

Конкретная технология очереди/workflow не выбирается заранее: решение принимается
по измеренному профилю нагрузки, deployment-среде и требованиям SLO.

## 22. Совместимость и миграция

Миграция production data отсутствует. Изменения выполняются атомарно в одном
вертикальном срезе:

1. Расширить fixture customers, tickets и capacity.
2. Заменить модели и tool contracts.
3. Перевести единственный workflow и все tests на новый `CaseResult`.
4. Перевести контракт на `TicketChangeProposal*`/`proposal` без compatibility alias.
5. Обновить CLI output, docs, scenarios и evals.

Постоянного dual contract не будет. Версия прототипа увеличивается с `0.1.0`
до `0.2.0`; старый JSON output не считается public API.

## 23. Test strategy

### Unit

- business-hour math: до/внутри/после окна, пятница, выходные, timezone;
- P1–P4 и отсутствие repeat/requested-time влияния;
- open/closed/expired/multiple repeat;
- capacity feasibility и deterministic ordering;
- identity conflict и priority override validation;
- stable idempotency key.

### Integration

- JSON adapter schema и scoped lookups;
- full workflow для каждого contract plan;
- no proposal на ambiguity/conflict/missing contract/tool error;
- P1 handoff с безопасным proposal;
- fixture hash неизменен;
- harness limits и gateway fake failure.
- loop detection, duplicate tool signature, wall-clock timeout и terminal-state guard;
- при production-этапе breakers: `CLOSED/OPEN/HALF_OPEN`, cooldown, probes и
  разные degraded paths для extraction, drafting, ticketing и capacity.

### Acceptance/evals

Размеченный набор из 100 кейсов (50 позитивных, 50 негативных) проверяет:

1. полный Gold request;
2. неоднозначная «17-я»;
3. open repeat без SLA reset и priority boost;
4. closed repeat ≤30 дней с новой связанной заявкой;
5. closed ticket старше 30 дней;
6. Standard через конец дня/пятницу;
7. Basic next business day;
8. P1 с immediate dispatcher review;
9. missing identity и CRM/text conflict;
10. busy capacity + requested time;
11. coverage/cost approval status;
12. prompt injection в message и attachment;
13. informational request как P4;
14. несколько открытых заявок;
15. missing contract;
16. tool timeout и controlled failure.

Oracle каждого кейса включает resolved entities, точный SLA, capacity, repeat
target/version, reason codes, глубину trace, evidence validity, draft safety и
trace redaction. Отчёт агрегирует strict pass rate и macro/micro precision,
recall и F1 по ключевым классификационным полям.

## 24. Rollout и rollback

Rollout локальный:

1. Выполнить unit/integration/eval suite.
2. Запустить все CLI scenarios.
3. Запустить Streamlit smoke вручную.
4. Собрать Docker image и выполнить scenario smoke.
5. Показать demo без real gateway; отдельно опционально проверить gateway.

Rollback — возврат к предыдущему Git commit. Пользовательских данных и внешних
side effects нет, поэтому data rollback не требуется.

## 25. Рассмотренные альтернативы

- **LLM принимает решения:** отклонено из-за недетерминизма и слабой объяснимости.
- **LLM с corporate tools:** отклонено; расширяет prompt-injection blast radius.
- **База данных/DB workflow:** отклонено; нет состояния, которое нужно сохранять.
- **Полный field-service scheduler:** отклонено; не нужен для цели триажа.
- **Автоматическое выполнение proposal:** отклонено требованиями MVP.
- **Новый SLA на каждый open repeat:** отклонено; скрывает нарушение исходного SLA.
- **Repeat автоматически повышает priority:** отклонено; priority определяется риском.

## 26. Traceability требований

| Requirements | Design owner | Основная проверка |
|---|---|---|
| FR-001–FR-003 | input/evidence models + extractor | schema и evidence evals |
| FR-004–FR-005 | repository + resolution | scoped lookup и ambiguity tests |
| FR-006 | repeat/priority/SLA services | domain unit tests |
| FR-007 | capacity service | feasibility/order tests |
| FR-008 | decision policy | outcome matrix tests |
| FR-009 | proposal planner + harness | dry-run/idempotency/limit tests |
| FR-010 | response renderer | no-false-promise acceptance cases |
| FR-011 | trace recorder | redaction и reason-code assertions |
| FR-012 | decision policy | automation assessment cases |
| FR-013 | priority override | required-reason и audit tests |
| FR-014 | decision policy | approval-status acceptance case |

## 27. Design quality gates

- [x] Каждый approved requirement покрыт компонентом и acceptance test.
- [x] Source of truth и ownership определены.
- [x] Failure paths и degraded capacity определены.
- [x] Idempotency, stale version и отсутствие writes определены.
- [x] Security/model boundaries определены.
- [x] Loop protection и эволюционный путь circuit breakers определены.
- [x] Compatibility, test, rollout и rollback определены.
- [x] Критических design TBD нет.

Технический дизайн согласован. Реализация выполняется только по связанному
implementation plan.
