# Evals

Источник истины — `src/text2business/data/eval_cases.json`. В каждом кейсе явно
заданы вход, тип (`positive`/`negative`) и ожидаемые action, review status,
priority, repeat, proposal и terminal state.

Regression-набор покрывает 11 сценариев: 5 позитивных и 6 негативных.

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

В Eval Console можно фильтровать набор, запускать один кейс, позитивную/негативную
группу или весь набор. Для каждого выполнения показываются expected vs actual,
PASS/FAIL и отдельный trace. Автотесты прогоняют обе группы: `pytest`.
