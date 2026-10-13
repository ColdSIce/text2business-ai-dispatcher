# Agent harness

## Scope

Один входящий запрос создаёт один ограниченный run с неизменяемой целью: разобрать одну сервисную заявку и предложить максимум одну ticket mutation.

## Pipeline

1. Валидировать типизированный вход.
2. Извлечь факты и evidence.
3. Остановиться при prompt injection или конфликте scope.
4. Вызвать только allowlisted типизированные read-tools.
5. Остановиться при неоднозначном site или asset.
6. Детерминированно найти дубликат, приоритет и SLA.
7. Сформировать максимум одну dry-run mutation.
8. Вернуть один терминальный результат и безопасный trace.

## Limits

- максимум 8 tool calls;
- максимум 2 model calls, включая одну schema-repair попытку;
- одна заявка и одна mutation на run;
- mutation всегда требует idempotency key, expected version и подтверждение человека;
- повтор mutation после неизвестного результата запрещён.

## Trust and model boundary

Клиентский текст, attachment и tool data считаются данными, а не инструкциями. Внешняя модель опциональна; единственный разрешённый маршрут — `AI_GATEWAY_BASE_URL`. Публичные OpenRouter hosts и ключи запрещены.

В trace не попадают секреты, chain-of-thought и полные provider payloads. Для демо trace содержит только факты, вызванные tools, reason codes и подтверждённые результаты.

DBOS, PostgreSQL, Redis, streaming и recovery workflow из LastRoom сознательно не перенесены: они не дают ценности четырёхчасовому локальному прототипу без реальных side effects.

