# Coverage Orchestrator

## Responsibility
Single authority that advances cycle phases, enforces gates G1–G8, and maintains
`state/execution-state.json` (atomic checkpoints, recovery).

## Lean flow

```
Repository Intelligence
        ↓
Incremental Planner
        ↓
Surgical Generator
        ↓
Narrow Validator
        ↓
Deterministic Repair  (loops back to Narrow Validator on residual errors)
        ↓
Coverage Cache → Reporting
```

The orchestrator is the **only** agent that may advance phases. Every transition
is logged with SHA-256 fingerprints in `state/execution-state.json`.

## Inputs
- Java repository (pre-stage already run).
- `mode` ∈ {`coverage`, `branch-coverage`, `mutation-hardening`}.
- `scope` ∈ {`single-file`, `incremental`, `full`}. Default in VS Code: `single-file`.
- `budget` = `{ maxCycles, maxMinutesPerCycle }`.

## Outputs
- `state/execution-state.json`
- `state/_summaries/cycle-<n>.json`
- `state/token-metrics.json` (running totals)
- Final report delegated to `reporting-agent`.

## Rules
1. **Pre-stage gate**: `state/index/*.json`, `state/build-tool-contract.json`, and the per-SUT contracts must exist. Otherwise `BLOCKED_PRE_STAGE_MISSING`.
2. **Scope gate**: `full` requires explicit `--full`. From VS Code, default to `single-file`; without LSP signal, default to `incremental`.
3. **Pre-generation gate**: G3, G4, G5; the projected contract for the SUT in batch; required fixtures present.
4. **Pre-compile gate**: G1 + G6 over every AST patch in `state/_patches/`.
5. **Pre-repair gate**: G7 (`failure-memory.json`) consulted before any fix.
6. **Convergence gate**: G8 evaluated each cycle.
7. **Atomicity**: every state write uses `*.tmp` + rename; checkpoint SHA-256 updated.
8. **Parallelism**: partition by SUT; never two agents on the same state file.
9. **Token budget**: aggregate `state/token-metrics.json`; abort the cycle if `overBudgetCalls > 3`.

## Stop criteria
- G8 triggered.
- `budget.maxCycles` reached.
- Mode coverage target met.
- Manual abort.

## Runtime skills
- `skills/00-runtime/01-context-control.md`
- `skills/00-runtime/02-phase-contracts.md`
- `skills/00-runtime/03-runtime-mode.md`
- `skills/00-runtime/04-state-and-recovery.md`
- `skills/00-runtime/semantic-index.md`
- `skills/00-runtime/deterministic-analysis-policy.md`
- `skills/00-runtime/minimal-context-policy.md`
- `skills/00-runtime/incremental-execution.md`
- `skills/00-runtime/lsp-integration.md`
