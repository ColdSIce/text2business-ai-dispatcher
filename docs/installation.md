# Установка

## Локально

Нужен Python `3.12.14`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
pytest
```

## Docker

```bash
docker build -t text2business-demo .
docker run --rm text2business-demo --scenario full
```

Внешняя модель, база данных и секреты для deterministic-режима не нужны.

