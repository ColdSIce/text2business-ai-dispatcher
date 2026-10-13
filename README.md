# Text2Business AI Dispatcher

Демонстрационный вертикальный срез: свободный текст сервисной заявки преобразуется в проверенные факты, корпоративные данные, детерминированное решение и безопасный dry-run создания тикета.

## Документация

- [Установка](docs/installation.md)
- [Как пользоваться](docs/usage.md)
- [Архитектура](docs/architecture.md)
- [Agent harness](docs/harness.md)
- [Evals](docs/evals.md)
- [Метрики](docs/metrics.md)

## Быстрый запуск

Требуется Python `3.12.14`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
python -m text2business.cli
pytest
```

Docker:

```bash
docker build -t text2business-demo .
docker run --rm text2business-demo
```

## Что работает

CLI содержит четыре сценария: полный запрос, неоднозначный запрос, повторное обращение и prompt injection.

Система:

1. Детерминированно извлекает факты вместе с evidence.
2. Через типизированные mock-tools находит объект, оборудование, договор и открытые заявки.
3. Обычным кодом определяет приоритет и дедлайн SLA.
4. Создаёт, обновляет, запрашивает уточнение или безопасно отказывается от действия.
5. Формирует mutation только как dry-run с `idempotency_key`, `expected_version` и подтверждением человека.
6. Возвращает проект ответа и последовательный trace.

LLM в этом срезе не используется. Корпоративные данные находятся в `src/text2business/data/corporate.json`. Реальных side effects нет.

## Границы

Это демонстрация, а не production-система. Пока не реализованы AI Gateway, Streamlit UI и полноценный календарь рабочих часов.
