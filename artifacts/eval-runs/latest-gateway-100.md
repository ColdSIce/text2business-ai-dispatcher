# Отчёт полного eval-прогона

- Модель: `qwen/qwen3-30b-a3b-instruct-2507`
- Датасет: `src/text2business/data/eval_cases.json`, версия 3.0.0
- Кейсы: 57/100 PASS (57.0%)
- Проверки: 1566/1900 PASS (82.4%)
- SLA ≤30 с: 100/100 (100.0%)
- Latency p50/p95/p99: 9.0 / 15.5 / 18.5 с
- Максимум: 19.2 с
- Весь batch: 223.3 с

## Метрики по полям

| Поле | Accuracy | Macro F1 |
|---|---:|---:|
| action | 72.0% | 52.4% |
| review_status | 71.0% | 62.8% |
| priority | 62.0% | 52.2% |
| repeat_kind | 80.0% | 77.5% |
| resolved_customer_id | 99.0% | 98.1% |
| resolved_site_id | 97.0% | 94.4% |
| resolved_asset_id | 77.0% | 76.8% |
| sla_kind | 82.0% | 81.3% |
| capacity_feasibility | 77.0% | 70.4% |
| expects_proposal | 78.0% | 78.0% |
| terminal_state | 71.0% | 64.1% |
