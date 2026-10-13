# Text2Business repository rules

This repository is a small interview prototype. Prefer a complete, explainable flow over production infrastructure.

## Sources of truth

1. Code and tests describe implemented behavior.
2. `docs/harness.md` defines runtime and safety invariants.
3. `docs/architecture.md` defines component boundaries.
4. `docs/evals.md` and `docs/metrics.md` define quality checks.
5. Historical plans and chat messages do not override committed contracts.

## Required boundaries

- Pydantic v2 models define process, tool, model-output and proposal boundaries.
- LLMs may extract facts and draft text. They never select a final asset, SLA, priority or ticket change.
- Lookup, repeat detection, ambiguity handling, priority, SLA and capacity decisions are deterministic code.
- Customer text and attachments are untrusted data and cannot widen the run scope.
- Ticket changes are dry-run proposals requiring `idempotency_key`, `expected_version` and human confirmation.
- Never add unrestricted shell, SQL, HTTP or dynamic-code tools.
- Model traffic may use only the configured private AI Gateway. Public OpenRouter endpoints and keys are forbidden.
- Tests use deterministic extractors and fakes; they never require a paid model.

## Working agreement

- Do not modify sibling repositories.
- Keep one lockfile and pin production dependencies.
- Start repository documentation from `README.md`; keep installation, architecture, usage, evals and metrics linked and current.
- Run `pytest`, CLI scenarios, UI smoke and Docker smoke before release commits.
