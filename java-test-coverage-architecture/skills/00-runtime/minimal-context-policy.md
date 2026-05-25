# Minimal Context Policy (Runtime Skill)

> Hard rule: **the LLM only sees what it strictly needs to reason**. Everything else
> stays out of the prompt. This skill is the contract every agent honors when
> building a request.

## What MUST be in the prompt

For each unit of work (one test method / one repair / one assertion), include only:

- **target method** — signature + body, taken from `state/index/methods.json`.
- **collaborators** — for each one referenced by the target: type FQN + invoked
  method signatures only (no class bodies). Derived from `state/index/dependencies.json`.
- **minimal contract** — the subset of `state/symbol-contracts/<sut>.json` whose
  symbols are referenced by the target (projection, not the full contract).
- **failing lines** — for repair: only the lines flagged in
  `state/compile-error-index.json` for this file, with ±2 lines of context. Never
  the whole test file.
- **required imports** — the whitelist subset matching the symbols actually used
  (from `state/import-whitelist.json`).
- **fixture references** — fixture **ids** from `state/fixture-catalog.json`. The
  generator/repairer cites the id; the deterministic patcher resolves it.

## What MUST NOT be in the prompt

| Forbidden                                       | Use instead                                   |
|-------------------------------------------------|-----------------------------------------------|
| Full repository / file trees                    | `state/incremental-map.json`                  |
| `pom.xml` / `build.gradle`                      | `state/build-tool-contract.json`              |
| `target/site/jacoco/jacoco.xml`                 | `state/coverage-delta.json` (scoped)          |
| Full stack traces                               | Parsed cause in `compile-error-index.json`    |
| Whole test files when only one method changes   | AST patch with `InsertMethod` / `ReplaceAssertion` |
| Whole `symbol-contracts/<fqcn>.json`            | Projection `_views/<batchId>.json`            |
| Unrelated methods of the SUT                    | Filter by `state/incremental-map.json#affectedTests` |
| Full generated test classes already on disk     | Diff against current file (lines around anchor) |
| Re-pasting MASTER_PROMPT.md                     | Reference by name; never duplicate            |

## Token budgets

| Channel                       | Preferred | Hard limit |
|-------------------------------|-----------|------------|
| Surgical Generator per method | < 1.5k    | 5k         |
| Deterministic Repair fallback | < 0.8k    | 3k         |
| Assertion completion          | < 0.5k    | 2k         |
| **Total per turn**            | **< 5k**  | **10k**    |

If a request would exceed the **preferred** budget, split the unit of work. If it
would exceed the **hard** limit, refuse and return a planning error; the orchestrator
must subdivide before retrying.

## Instrumentation

Every LLM call records to `state/token-metrics.json`:

```json
{ "phase": "generation|repair", "agent": "<name>", "tokensIn": 0, "tokensOut": 0,
  "evidenceCount": 0, "patchId": "<id>", "outcome": "ok|over_budget|split" }
```

Aggregated metrics drive convergence decisions (G8) and the performance dashboard.

## Anti-patterns

- "Include the whole file, just in case."
- "Repeat the SUT contract on every turn."
- "Paste the stack trace verbatim."
- "Send the JaCoCo XML so the LLM can decide."
- "Reuse the same prompt for ten different methods."
