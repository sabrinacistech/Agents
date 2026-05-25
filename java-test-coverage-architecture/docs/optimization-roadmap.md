# Optimization Roadmap — Final State

> The previous additive roadmap (Phases 1–8) is **complete**. This document
> records the final lean architecture and the destructive cleanup that closed
> the migration.

## Final architecture

```
Coverage Orchestrator
        ↓
Repository Intelligence
        ↓
Incremental Planner
        ↓
Surgical Generator
        ↓
Narrow Validator
        ↓
Deterministic Repair
        ↓
Coverage Cache
        ↓
Reporting
```

## What changed (destructive cleanup)

### Deleted

- `agents/discovery-agent.md`
- `agents/classification-agent.md`
- `agents/dependency-graph-agent.md`
- `agents/symbol-contract-agent.md`
- `agents/stack-profile-agent.md`
- `skills/01-discovery/` (entire directory)
- `skills/02-classification/` (entire directory)
- `skills/03-symbol-contract/` (entire directory)
- `skills/04-dependency-graph/` (entire directory)

All responsibilities migrated into `agents/repository-intelligence-agent.md`
backed by `state/index/*` and `tools/python/`.

### Replaced

- `MASTER_PROMPT.md` — collapsed from an 11-step legacy flow into the 7-step
  lean flow with deterministic-first rules and token caps.
- `agents/coverage-orchestrator.md` — lean phase advancement.
- `agents/generation-agent.md` — AST patches only.
- `agents/validation-agent.md` — compile-graph pruning + Coverage Cache.
- `agents/repair-agent.md` — deterministic rules first.
- `skills/07-generation/unit-test-generation.md` — body conventions inside
  `InsertMethod`, not full files.
- `skills/00-runtime/01-context-control.md` — companion to the new
  minimal-context policy.

### Created

- `schemas/ast-patch.schema.json` — surgical patch schema.
- `skills/00-runtime/minimal-context-policy.md` — token budgets and
  prompt-content rules.
- `skills/00-runtime/deterministic-analysis-policy.md` — LLM vs code boundary.
- `skills/00-runtime/incremental-execution.md` — scope rules.
- `skills/00-runtime/semantic-index.md` — index usage contract.
- `skills/00-runtime/lsp-integration.md` — VS Code fast path.
- `skills/08-validation/compile-graph-pruning.md` — one-hop compile set.
- `skills/11-coverage/coverage-cache.md` — per-class merge protocol.
- `state/incremental-map.json` — change propagation.
- `state/token-metrics.json` — running token accounting.
- `state/index/*` — semantic index.
- `coverage-cache/` — per-class `.exec` cache.
- `repair-rules/*.rules` — deterministic repair rules.
- `templates/*.java` — deterministic test skeletons.

## Single source of truth

| Surface          | Source                                          |
|------------------|-------------------------------------------------|
| Symbols          | `state/index/classes.json` + `methods.json`     |
| Imports          | `state/index/imports.json`                      |
| Annotations      | `state/index/annotations.json`                  |
| Dependency graph | `state/index/dependencies.json`                 |
| Framework labels | derived from `annotations.json`                 |
| Build / classpath| `state/build-tool-contract.json`                |
| Stack profile    | derived by Repository Intelligence              |
| Coverage         | `coverage-cache/<fqcn>.exec` + `<fqcn>.json`    |
| Compile errors   | `state/compile-error-index.json`                |

## Token reduction (expected)

| Metric                                | Pre-cleanup | Lean      |
|---------------------------------------|-------------|-----------|
| Tokens per generated test (Service)   | 4k–8k       | 1.5k–3k   |
| Repository re-parses per cycle        | O(agents)   | 0         |
| `mvn` per file edit (VS Code)         | full module | `-Dtest=<one>` |
| Repair prompt size (typical)          | 1.5k–3k     | 0.3k–0.8k |
| Generation latency per test (warm)    | 30–90s      | 5–15s     |

## Preserved guarantees

- All eight gates G1–G8 unchanged in semantics, tightened in implementation.
- Atomic state writes (`*.tmp` + rename) on every file.
- Evidence-id traceability on every emitted line.
- Per-SUT isolation for parallel execution.
- Recovery via `state/execution-state.json` checkpoints.
