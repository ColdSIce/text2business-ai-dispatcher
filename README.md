# Text2Business AI Dispatcher

Прототип сокращает ручной триаж сервисной заявки: извлекает факты с evidence, сверяет их с корпоративными данными, детерминированно считает повтор, приоритет, SLA и доступность команды, а затем готовит безопасное предложение для диспетчера. Реальных изменений во внешних системах нет.

## Документация

- [Установка](docs/installation.md)
- [Как пользоваться](docs/usage.md)
- [Архитектура](docs/architecture.md)
- [Сущности и модели](docs/domain-model.md)
- [Agent harness](docs/harness.md)
- [Evals](docs/evals.md)
- [Метрики](docs/metrics.md)
- [Требования](docs/specifications/service-request-triage/requirements.md)
- [Технический дизайн](docs/specifications/service-request-triage/technical-design.md)
- [План реализации](docs/specifications/service-request-triage/implementation-plan.md)

## Быстрый запуск

Нужен Python `3.12.x`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
streamlit run src/text2business/app.py
```

CLI и тесты:

```bash
python -m text2business.cli --scenario full
pytest
```

Docker:

```bash
docker build -t text2business-demo .
docker run --rm text2business-demo --scenario full
```

## Что реализовано

- 11 сценариев, CLI и Streamlit-интерфейс диспетчера;
- детерминированный fallback и опциональная structured extraction через private AI Gateway;
- типизированные read-only инструменты над mock CRM/asset/ticket/capacity данными;
- repeat detection для открытых и недавно закрытых тикетов;
- правила P1–P4, Gold/Standard/Basic SLA и проверка желаемого времени по capacity;
- только dry-run `TicketChangeProposal` с обязательным подтверждением человека;
- лимиты, дедлайн, защита от циклов, безопасный trace и regression tests.

## Границы прототипа

Один процесс и синхронное выполнение. Нет очередей, durable execution, HA/DR, autoscaling, праздничного календаря и реальных CRM-записей. Путь развития зафиксирован в [техническом дизайне](docs/specifications/service-request-triage/technical-design.md).
