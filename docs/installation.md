# Установка

## Локально

Нужен Python `3.12.x`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
pytest
streamlit run src/text2business/app.py
```

Детерминированный режим не требует модели, базы данных или секретов. Настройка OpenRouter или другого allowlisted gateway описана в [инструкции по использованию](usage.md#опциональный-ai-gateway).

## Docker

CLI:

```bash
docker build -t text2business-demo .
docker run --rm text2business-demo --scenario full
```

UI:

```bash
docker run --rm -p 8501:8501 --entrypoint streamlit text2business-demo run src/text2business/app.py --server.address=0.0.0.0
```
