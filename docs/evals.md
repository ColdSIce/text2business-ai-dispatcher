# Evals

Regression-набор покрывает 11 сценариев:

| Класс | Проверка |
|---|---|
| Happy path | Новый тикет и dry-run proposal. |
| Неоднозначность | Уточнение без proposal. |
| Открытый повтор | Update существующего тикета, исходный SLA сохранён. |
| Закрытый повтор | Новый связанный тикет в окне 30 дней. |
| SLA | Gold, Standard business hours и Basic next business day. |
| P1 | Немедленный ручной review, без автоматического применения. |
| Identity/conflict | Missing identity и CRM/text mismatch fail closed. |
| Capacity | Желаемое время не обещается при занятой команде. |
| Approval | Отдельный статус без выдуманного workflow согласования. |
| Injection | Handoff без вызова tools. |

Инварианты: evidence действительно встречается в источнике, неоднозначность не скрывается, repeat/priority/SLA/capacity считает код, модель не вызывает tools, корпоративный JSON не меняется, внешние записи отсутствуют, trace объясняет решение.

Запуск: `pytest`.
