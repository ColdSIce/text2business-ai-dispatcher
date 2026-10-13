# Как пользоваться

## Интерфейс диспетчера

```bash
streamlit run src/text2business/app.py
```

Вкладка «Тестовый датасет» показывает позитивные и негативные кейсы, точный вход
и ожидаемый результат. Можно запустить кейс, группу или весь набор. Во вкладке
«Запуски» для каждого выполнения доступны expected vs actual, полный результат
и явный переключатель «Trace шагов». Trace сначала показывает таблицу всех шагов
с результатами, затем полный input/output каждого раскрываемого шага. «Свободный
ввод» предназначен для ручной проверки заявки.

## Тюнинг промптов

Вкладка «Prompt Lab» позволяет выбрать кейс, изменить русские системные промпты
извлечения и черновика ответа и запустить выбранный кейс либо весь regression dataset. Model-run доступен
только при настроенном private AI Gateway. Override живёт в UI-сессии и сохраняется
в истории конкретного запуска.

Defaults для code review находятся в `src/text2business/prompts.py`. Конструкторы
`GatewayExtractor(..., system_prompt=...)` и
`GatewayResponseDrafter(..., system_prompt=...)` принимают явный override.
Промпт не может менять детерминированные priority, SLA, repeat или decision rules.

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
export AI_GATEWAY_ALLOWED_HOSTS=gateway.example
export TEXT2BUSINESS_EXTRACTOR=gateway
```

Gateway обязан использовать HTTPS, а hostname — входить в явный allowlist.
Публичные OpenRouter/OpenAI/Anthropic/Google endpoints отклоняются. Секреты и
прямые контактные данные в trace редактируются.
