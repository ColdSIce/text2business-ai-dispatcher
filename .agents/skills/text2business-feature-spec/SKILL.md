---
name: text2business-feature-spec
description: Create, review, or revise Text2Business feature specifications from verified requirements through technical design and an implementation plan. Use for product behavior, acceptance criteria, edge cases, architecture planning, and implementation readiness; do not use for small code-only fixes.
---

# Text2Business Feature Specification

## Load the workflow

1. Read `docs/specifications/SPECIFICATION_WORKFLOW.md` completely.
2. Read `docs/specifications/README.md`.
3. Read the target feature documents that already exist.
4. Inspect only the repository code, tests, data, and documentation relevant to the feature.

The workflow document is the detailed quality standard. Do not duplicate or weaken it here.

## Select the phase

- Research first when current behavior is unclear; separate facts from assumptions.
- While product behavior or acceptance criteria are unsettled, edit only `requirements.md`.
- Start `technical-design.md` only after critical product decisions are closed or explicitly deferred.
- Start `implementation-plan.md` only after the design covers the approved requirements.
- Change product code only after an explicit user request and a satisfied Definition of Ready.

State the active phase before material work.

## Project-specific invariants

- The prototype assists triage; it never performs a real external write.
- Use the business term “предлагаемое изменение заявки”; reserve “mutation” for existing code identifiers until an approved migration renames them.
- LLM output is untrusted structured extraction or draft text. Entity resolution, repeat detection, priority, SLA, capacity assessment, and the final action are deterministic.
- Every important fact has evidence and provenance. Every entity, model, enum, and non-obvious field has a semantic comment.
- Ask only product-contract questions, one meaningful decision at a time. Record safe assumptions instead of expanding the interview.

## Validate the phase

- Check for contradictions, stale status, unresolved critical decisions, and requirements without acceptance criteria.
- Check documentation links from the repository `README.md`.
- When implementation is later requested, also follow the verification scope in `AGENTS.md`.
