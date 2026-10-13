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

## Что считается в прототипе

Для 100 размеченных кейсов UI и `calculate_eval_metrics()` считают:

- strict case pass rate: кейс успешен, только если прошли все assertions;
- assertion pass rate;
- accuracy, macro precision/recall/F1 и micro precision/recall/F1 для action,
  review status, priority, repeat, customer/site/asset, SLA kind, capacity,
  решения о proposal и terminal state;
- число unexpected proposals, unsafe drafts и неотредактированных traces.

Macro-метрики нужны из-за редких критичных классов вроде P1 и handoff. Micro для
однозначной классификации совпадает с общей accuracy и показывает среднее качество
по всем примерам. Эти цифры сравнивают prompt-варианты на одном и том же наборе,
но не заменяют оценку на будущей выборке из реальных обращений.

## Выполнение

- p50/p95 end-to-end latency;
- clarification/handoff/approval rate;
- gateway schema failure и deterministic fallback rate;
- tool/model call count и limit violation rate;
- proposal acceptance/rejection rate и время review.

В прототипе regression и classification metrics проверяет Pytest, а UI показывает
их для текущего набора запусков. Production telemetry и dashboard не входят в scope.
