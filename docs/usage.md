# Как пользоваться

## Интерфейс диспетчера

```bash
streamlit run src/text2business/app.py
```

Выберите готовый сценарий или свободный ввод. Интерфейс показывает evidence, найденный контекст, приоритет, SLA, capacity, решение, dry-run proposal, черновик ответа и trace. Приоритет можно переопределить только с обязательной причиной; рассчитанное значение сохраняется.

## CLI

```bash
python -m text2business.cli --list-scenarios
python -m text2business.cli --scenario full
python -m text2business.cli --scenario duplicate
python -m text2business.cli --scenario closed_repeat
python -m text2business.cli --scenario p1
python -m text2business.cli --scenario injection
```

JSON содержит `facts`, `resolution`, `repeat`, `priority`, `sla`, `capacity`, `decision`, `proposal`, `draft_response`, `warnings` и `trace`. `proposal=null` означает, что без уточнения или ручного решения безопасного изменения нет.

## Опциональный AI Gateway

По умолчанию используется детерминированный extractor. Для private OpenAI-compatible gateway задайте:

```bash
export AI_GATEWAY_BASE_URL=https://gateway.example/v1
export AI_GATEWAY_API_KEY=...
export AI_GATEWAY_MODEL=...
export TEXT2BUSINESS_EXTRACTOR=gateway
```

Публичный OpenRouter отклоняется. Секреты в trace не записываются.
