# Architecture Overview (Lean Edition)

## Layers

1. **Orchestration** — Coverage Orchestrator. Sole authority for phase
   advancement and gate enforcement (G1–G8).
2. **Repository Intelligence** — single agent that projects the deterministic
   semantic index into classification, dependency graph, symbol contracts,
   import whitelist, and stack profile. Replaces the deleted discovery /
   classification / dependency-graph / symbol-contract / stack-profile agents.
3. **Incremental Planner** — derives `state/incremental-map.json` from `git diff`
   and `state/index/dependencies.json`. Builds the batch plan only over
   `affectedTests`.
4. **Surgical Generator** — emits AST patches (`schemas/ast-patch.schema.json`).
   Uses `templates/` when a new test class is required. Never rewrites whole
   files.
5. **Narrow Validator** — compiles only `{ test, SUT, directDeps(SUT) }` and
   runs JaCoCo per patch. See `skills/08-validation/compile-graph-pruning.md`.
6. **Deterministic Repair Engine** — applies `repair-rules/*.rules` before any
   LLM call. The LLM fallback is reserved for `escalateToLLM(<reason>)` cases.
7. **Coverage Cache** — `coverage-cache/<fqcn>.exec` and `<fqcn>.json` merged
   atomically, producing `state/coverage-delta.json` without full rebuilds.
8. **Reporting** — final summary citing every `evidence-id`, attaching deltas.

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
Deterministic Repair  (loops back to Narrow Validator)
        ↓
Coverage Cache → Reporting
```

## Key decisions

### Semantic index as the single source of structural truth

`state/index/{classes,methods,imports,dependencies,annotations}.json` is built
once by `tools/python/run_pipeline.py` and consumed by every agent. No agent
re-parses Java. See `docs/semantic-index-architecture.md`.

### Three evidence stores feed generation

- `state/import-whitelist.json` (what imports may exist).
- `state/symbol-contracts/<fqcn>.json` (what symbols exist and how).
- `state/fixture-catalog.json` (how to build valid data).

If any is missing or stale for an SUT, the Orchestrator refuses to generate.

### Per-SUT isolation

Parallelism is per-SUT; no two agents share a state file. This avoids races and
lets Generation/Validation scale horizontally without breaking atomicity.

### Recovery

`state/execution-state.json` holds `checkpoints[]` with per-file hashes. After
a crash, the system restarts at `lastGoodCheckpoint`. Inconsistent hashes are
degraded, never accepted.

### Token discipline

Per-turn budget: **< 5k preferred**, **10k hard limit**. Anything that can be
computed by code (imports, framework detection, dep graph, error parsing,
symbol resolution) is computed by code. See
`skills/00-runtime/deterministic-analysis-policy.md` and
`skills/00-runtime/minimal-context-policy.md`.

### Surgical output

Every emitted change is an AST patch validated against
`schemas/ast-patch.schema.json`. Full-file output is allowed **only** when
`createsFile: true`, in which case the patch wraps a deterministic template
from `templates/`.

### Incremental coverage

`coverage-cache/` keeps per-class `.exec` files; JaCoCo merges happen at the
patch level. The full module report is regenerated only on `--full` or a
baseline refresh.

### VS Code / LSP fast path

When VS Code is active, the Validator may skip `mvn compile` if JDT.LS reports
no diagnostics for the target file (see `skills/00-runtime/lsp-integration.md`).
CI runs never rely on LSP.
