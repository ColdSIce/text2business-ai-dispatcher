# Text2Business repository rules

This repository is a small interview prototype. Prefer a complete, explainable flow over production infrastructure.

## Sources of truth

1. Code and tests describe implemented behavior.
2. `docs/harness.md` defines runtime and safety invariants.
3. `docs/architecture.md` defines component boundaries.
4. `docs/evals.md` and `docs/metrics.md` define quality checks.
5. Historical plans and chat messages do not override committed contracts.

## Required boundaries

- Pydantic v2 models define process, tool, model-output and mutation boundaries.
- LLMs may extract facts and draft text. They never select a final asset, SLA, priority or mutation.
- Lookup, deduplication, ambiguity handling, priority and SLA are deterministic code.
- Customer text and attachments are untrusted data and cannot widen the run scope.
- Mutations are dry-run only and require `idempotency_key`, `expected_version`, a proposed payload and human confirmation.
- Never add unrestricted shell, SQL, HTTP or dynamic-code tools.
- Model traffic may use only the configured Finland AI Gateway. Public OpenRouter endpoints and keys are forbidden.
- Tests use deterministic extractors and fakes; they never require a paid model.

## Working agreement

- Do not modify LastRoom or sibling repositories.
- Keep one lockfile and pin production dependencies.
- Update README navigation and the relevant document whenever behavior, architecture, evals, metrics or usage changes.
- Run `pytest`, the CLI scenarios and Docker smoke test before release commits.

