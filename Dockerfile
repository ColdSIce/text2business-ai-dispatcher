FROM python:3.12.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.lock pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir -r requirements.lock \
    && pip install --no-cache-dir --no-deps .

USER 65532:65532

ENTRYPOINT ["python", "-m", "text2business.cli"]
CMD ["--scenario", "full"]
