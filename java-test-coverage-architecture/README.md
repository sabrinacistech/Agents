# Java Test Coverage Agent Architecture (Lean Edition)

Multi-agent system that increases real unit-test coverage on Java microservices
from inside VS Code + GitHub Copilot. **Deterministic-first**, **incremental-first**,
**surgical-first**.

## Core principle

> The agent never invents symbols. It uses only classes, imports, constructors,
> methods, builders, fixtures, and commands that are verified by an
> `evidence-id`. No evidence ⇒ no test.

## Lean flow

```text
Coverage Orchestrator
        ↓
Repository Intelligence   (single agent — owns indexing, classification, dep-graph, contracts, stack profile)
        ↓
Incremental Planner       (git delta → affectedClasses → affectedTests → batch-plan)
        ↓
Surgical Generator        (AST patches only; templates/ for new files)
        ↓
Narrow Validator          (compile-graph pruning + per-class JaCoCo)
        ↓
Deterministic Repair      (repair-rules/* first; LLM only if escalated)
        ↓
Coverage Cache            (per-class .exec merge → coverage-delta)
        ↓
Reporting
```

## Layout

```text
agents/              Lean agents: orchestrator, repository-intelligence,
                     generation, validation, repair, planning, fixture,
                     mutation, reporting.
skills/              Procedures by domain (runtime, fixtures, planning,
                     generation, validation, repair, coverage, reporting).
schemas/             JSON Schemas not tied to state (e.g., ast-patch.schema.json).
state/               Persistent JSON states + state/index/ semantic index.
state/_schemas/      JSON Schemas (Draft-07) for state validation.
coverage-cache/      Per-class JaCoCo .exec + summaries (incremental).
repair-rules/        Deterministic repair rules (.rules files).
templates/           Deterministic test skeletons (junit5-mockito, springboot, webmvc, reactive).
docs/                Architecture notes and policies.
tools/python/        Deterministic pre-stage (POM, classpath, javap, JaCoCo, indexer).
MASTER_PROMPT.md     Lean master prompt with gates G1–G8.
```

## Mandatory pre-stage (Python)

Before any LLM call:

```bash
mvn -q -DskipTests package
python tools/python/run_pipeline.py \
   --repo . \
   --out docs/agents/java-test-coverage-architecture/state \
   --module <module> \
   --include-fqcn '^com\.acme\.' \
   --jacoco-xml target/site/jacoco/jacoco.xml
```

Produces the **semantic index** (`state/index/*`) and every derived contract.
LLM agents read only these JSON files. They never re-parse POMs, classpaths, or
`.java` sources. See [`docs/python-pipeline.md`](docs/python-pipeline.md).

## Gates (anti-hallucination)

| Gate | Blocks                                                                |
|------|-----------------------------------------------------------------------|
| G1   | Imports outside `import-whitelist.json`                               |
| G2   | Symbols without `evidence-id`                                         |
| G3   | Contracts derived from regex (bytecode/AST only)                      |
| G4   | Generated-sources not indexed when APs are declared                   |
| G5   | Generation without a valid `stack-profile.json`                       |
| G6   | AST lint on the projected patch result (pre-compile)                  |
| G7   | Re-application of a `hash(errorCode, symbolFQN, fixId)` already FAILED|
| G8   | Convergence (`coverageDelta == 0` × 2 or `compileFailRate > 0.5`)     |

## Modes

- `coverage` — maximize lines.
- `branch-coverage` — maximize branches.
- `mutation-hardening` — kill PIT survivors.

## Scope (orthogonal to mode)

- `single-file` (default in VS Code).
- `incremental` (`state/incremental-map.json` from `git diff`).
- `full` (only with explicit `--full`).

## Determinism vs LLM

| Done by code (Python / index / repair-rules) | Done by the LLM        |
|----------------------------------------------|------------------------|
| Imports, framework detection, dep graph      | Assertions             |
| Compile-error parsing, stack-trace parsing   | Edge-case selection    |
| Symbol resolution, classification            | Naming                 |
| AST patching, JaCoCo merge, delta            | Complex repair reasoning (escalated) |

See [`skills/00-runtime/deterministic-analysis-policy.md`](skills/00-runtime/deterministic-analysis-policy.md) and [`skills/00-runtime/minimal-context-policy.md`](skills/00-runtime/minimal-context-policy.md).

## Token budget

- Preferred per turn: **< 5k tokens**.
- Hard limit per turn: **10k tokens**.
- Aggregated in [`state/token-metrics.json`](state/token-metrics.json).

## State validation

All `state/*.json` validate against `state/_schemas/`. Atomic writes (`*.tmp` +
rename). SHA-256 fingerprints in `state/execution-state.json`.

## Quick start

1. Read [`docs/developer-guide.md`](docs/developer-guide.md).
2. Read [`MASTER_PROMPT.md`](MASTER_PROMPT.md).
3. Run the pre-stage: `python tools/python/run_pipeline.py …`.
4. From VS Code chat, paste [`Prompt_inicial.md`](Prompt_inicial.md) with your `mode` and `scope`.
5. Watch progress in `state/execution-state.json` and `state/_summaries/cycle-*.json`.
6. Final report from the Reporting Agent.
