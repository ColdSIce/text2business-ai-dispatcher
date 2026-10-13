# Архитектура

```text
IncomingRequest
  -> bounded harness run
  -> deterministic or optional gateway extractor
  -> typed mock-tools over corporate JSON
  -> deterministic resolution, deduplication, priority and SLA rules
  -> dry-run mutation planner
  -> CaseResult with evidence, decision, response draft and trace
```

LLM отвечает только за structured extraction и черновик ответа. Она не получает tools и не принимает финальные бизнес-решения.

Корпоративный JSON является read-only mock-хранилищем. Все tool inputs/outputs и итоговый результат описаны Pydantic-моделями. Реальные side effects отсутствуют.

