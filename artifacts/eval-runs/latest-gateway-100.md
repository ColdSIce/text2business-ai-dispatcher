# Отчёт полного eval-прогона

- Модель: `qwen/qwen3-30b-a3b-instruct-2507`
- Датасет: `src/text2business/data/eval_cases.json`, версия 3.0.0
- Кейсы: 96/100 PASS (96.0%)
- Проверки: 1842/1900 PASS (96.9%)
- SLA ≤30 с: 100/100 (100.0%)
- Latency p50/p95/p99: 10.2 / 19.0 / 20.5 с
- Максимум: 26.0 с
- Весь batch: 264.2 с

## Метрики по полям

| Поле | Accuracy | Macro F1 |
|---|---:|---:|
| action | 96.0% | 95.9% |
| review_status | 96.0% | 94.5% |
| priority | 96.0% | 94.8% |
| repeat_kind | 96.0% | 96.3% |
| resolved_customer_id | 98.0% | 96.0% |
| resolved_site_id | 97.0% | 95.7% |
| resolved_asset_id | 96.0% | 95.6% |
| sla_kind | 96.0% | 95.6% |
| capacity_feasibility | 96.0% | 97.0% |
| expects_proposal | 96.0% | 96.0% |
| terminal_state | 96.0% | 92.2% |
