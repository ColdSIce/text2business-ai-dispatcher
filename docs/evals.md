# Evals

Источник истины — `src/text2business/data/eval_cases.json`. В каждом кейсе явно
заданы вход, fixture/failure setup, тип (`positive`/`negative`) и полный oracle:
action, review status, сущности, priority, repeat, SLA, capacity, proposal/version,
reason codes, terminal state, evidence/draft/trace safety.

Regression-набор покрывает 16 сценариев: 6 позитивных и 10 негативных.

| Класс | Проверка |
|---|---|
| Happy path | Новый тикет и dry-run proposal. |
| Неоднозначность | Уточнение без proposal. |
| Открытый повтор | Update существующего тикета, исходный SLA сохранён. |
| Закрытый повтор | Новый связанный тикет в окне 30 дней. |
| SLA | Gold, Standard business hours и Basic next business day. |
| P1 | Немедленный ручной review, без автоматического применения. |
| P4 | Информационный запрос не считается неисправностью. |
| Identity/conflict | Missing identity и CRM/text mismatch fail closed. |
| Capacity | Желаемое время не обещается при занятой команде. |
| Approval | Отдельный статус без выдуманного workflow согласования. |
| Injection | Message и attachment блокируются до модели и tools. |
| Failure paths | Missing contract, multiple open tickets и timeout tool. |

Инварианты: evidence действительно встречается в источнике, неоднозначность не
скрывается, repeat/priority/SLA/capacity считает код, модель не вызывает tools,
корпоративный JSON не меняется, небезопасный model draft блокируется, trace
редактирует секреты и объясняет финальное решение.

В Eval Console можно фильтровать набор, запускать один кейс, позитивную/негативную
группу или весь набор. Для каждого выполнения показываются expected vs actual,
PASS/FAIL и отдельный trace. Автотесты прогоняют обе группы: `pytest`.
