# Метрики

## Ключевая цель

- полное время человеческого триажа `<= 2 минут` против текущих примерно `12 минут`;
- SLA в продукте означает время до первого содержательного ответа диспетчера.

## Качество

- accuracy/coverage извлечённых полей и evidence;
- accuracy customer/site/asset resolution;
- accuracy repeat detection отдельно для open и closed <= 30 дней;
- доля повторных обращений как косвенная метрика качества поддержки;
- accuracy P1–P4, SLA deadline, action и capacity feasibility;
- dispatcher override rate и причины;
- unsafe applied action rate: целевое значение `0`.

## Выполнение

- p50/p95 end-to-end latency;
- clarification/handoff/approval rate;
- gateway schema failure и deterministic fallback rate;
- tool/model call count и limit violation rate;
- proposal acceptance/rejection rate и время review.

В прототипе regression pass rate проверяет Pytest, а счётчики и reason codes видны в `CaseResult`. Production telemetry и dashboard не входят в scope.
