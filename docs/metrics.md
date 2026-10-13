# Метрики

## Бизнес

- доля корректно маршрутизированных заявок;
- доля корректно найденных повторных обращений;
- среднее время до предложения действия;
- доля заявок, потребовавших уточнения или диспетчера;
- нарушения SLA из-за ошибочной классификации.

## Технические

- extraction field accuracy и evidence coverage;
- site/asset resolution accuracy;
- decision accuracy по regression dataset;
- unsafe auto-action rate — целевое значение `0`;
- p50/p95 latency;
- model schema failure и gateway fallback rate;
- среднее число tool calls на run.

В текущем прототипе regression pass rate собирается через Pytest, а tool calls и решения видны в `trace`. Production telemetry не входит в scope.

