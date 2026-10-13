# Agent harness

Один входящий контакт создаёт один ограниченный run: разобрать заявку и подготовить максимум одно предложение изменения тикета.

## Конечный pipeline

1. До модели и tools проверить message и attachment на недоверенные инструкции.
2. Проверить trusted identity, извлечь факты и проверить каждую evidence-цитату.
3. Завершить run при injection, конфликте CRM/текста или неоднозначности.
4. Вызвать только allowlisted typed read-tools.
5. Кодом определить повтор, приоритет, SLA и capacity feasibility.
6. Выбрать create/update/clarification/handoff/approval.
7. Подготовить максимум один dry-run `TicketChangeProposal`.
8. Вернуть один terminal result и безопасный trace.

## Ограничители

- максимум 8 tool calls;
- максимум 2 model calls, включая schema repair или drafting;
- максимум 1 предложение на run;
- wall-clock deadline проверяется до и после каждого внешнего вызова и до success;
- повтор одинаковой tool-сигнатуры запрещён;
- после terminal state новые шаги запрещены;
- предложение содержит `idempotency_key`, `expected_version` и `requires_human_confirmation=true`.

Текст клиента и вложения считаются данными, а не инструкциями. Gateway опционален;
при ошибке extraction система безопасно передаёт заявку диспетчеру, а при ошибке
drafting или небезопасном обещании использует детерминированный текст.

В trace нет секретов, chain-of-thought и полных provider payload. Circuit breakers и надёжное возобновление — явно будущий production-слой, а не скрытая возможность прототипа.
