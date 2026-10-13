# Отчёт полного eval-прогона

- Модель: `qwen/qwen3-30b-a3b-instruct-2507`
- Датасет: `src/text2business/data/eval_cases.json`, версия 3.0.0
- Кейсы: 28/100 PASS (28.0%)
- Проверки: 1243/1900 PASS (65.4%)
- SLA ≤30 с: 99/100 (99.0%)
- Latency p50/p95/p99: 11.5 / 21.6 / 27.3 с
- Максимум: 30.4 с
- Весь batch: 295.7 с

## Метрики по полям

| Поле | Accuracy | Macro F1 |
|---|---:|---:|
| action | 51.0% | 31.1% |
| review_status | 55.0% | 49.9% |
| priority | 44.0% | 26.7% |
| repeat_kind | 57.0% | 45.4% |
| resolved_customer_id | 75.0% | 70.8% |
| resolved_site_id | 76.0% | 74.4% |
| resolved_asset_id | 49.0% | 43.8% |
| sla_kind | 62.0% | 56.2% |
| capacity_feasibility | 56.0% | 45.1% |
| expects_proposal | 65.0% | 63.7% |
| terminal_state | 49.0% | 42.7% |
