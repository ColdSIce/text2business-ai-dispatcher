# Как пользоваться

```bash
python -m text2business.cli --list-scenarios
python -m text2business.cli --scenario full
python -m text2business.cli --scenario ambiguous
python -m text2business.cli --scenario duplicate
python -m text2business.cli --scenario injection
```

В JSON-результате отдельно показаны `facts`, кандидаты из mock-tools, `priority`, `sla`, `decision`, `mutation`, вопросы, предупреждения и `trace`.

`mutation` всегда `null` при неоднозначности или небезопасном вводе. В остальных случаях это только предложение с `dry_run=true`.

