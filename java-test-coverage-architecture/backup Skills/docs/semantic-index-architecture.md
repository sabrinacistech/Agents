# Semantic Index Architecture

> Single source of structural truth for the lean architecture. Built once per
> relevant change by `tools/python/run_pipeline.py`, consumed by all agents via
> O(1) JSON lookups.

## Motivation

Before this layer, multiple agents independently parsed Java to extract the
same metadata: discovery looked at POMs and structure, classification re-read
sources for framework detection, dependency-graph rebuilt the graph from AST,
symbol-contract called `javap`/JavaParser again, and stack-profile repeated
work. Aggregate cost: O(agents × files). Now: O(files), once.

## Solution

```
┌──────────────────────┐
│  Python pre-stage    │  javap + JavaParser + SymbolSolver
│  tools/python/       │──┐
└──────────────────────┘  │  (atomic write + SHA-256 fingerprints)
                          ▼
                ┌─────────────────────┐
                │  state/index/*.json │
                └────────┬────────────┘
                         │ O(1) lookups
                         ▼
              Repository Intelligence
                         ↓
   (classification, dep-graph view, symbol contracts, stack profile,
    import whitelist, generated-code index)
```

## Files

- `classes.json` — `{ fqcn, file, kind, modifiers, supertypes[], interfaces[] }`.
- `methods.json` — `{ fqcn, name, descriptor, params[], return, modifiers, throws[] }`.
- `imports.json` — `{ file, imports[{ fqn, static, onDemand }] }`.
- `dependencies.json` — nodes `{ fqcn }` and edges `{ from, to, kind }` with
  `kind ∈ {extends, implements, uses, injects, throws, returns, param}`.
- `annotations.json` — `{ target, annotations[{ fqn, attrs }] }`.

Each file validates against `state/_schemas/index/*.schema.json`.

## Determinism

- 100% deterministic construction. No LLM.
- Precedence: bytecode (`javap -p -s -c`) → AST (JavaParser+SymbolSolver) →
  `target/generated-sources/` fallback.
- Reproducible: two runs over the same source tree produce byte-exact JSON
  (stable ordering by FQCN).

## Invalidation

- Per file: `execution-state.json.indexFingerprints[file] = sha256(file)`.
- If `target/classes/<fqcn>.class` is newer than the indexed entry → re-resolve
  that class.
- Schema `version` bump → full reindex.

## Relationship to derived contracts

Repository Intelligence projects the index into:

- `state/classification-index.json` (kind, framework labels, risk, score).
- `state/dependency-graph.json` (filtered view of `dependencies.json`).
- `state/symbol-contracts/<fqcn>.json` (projected methods + evidence-ids).
- `state/import-whitelist.json` (whitelisted FQNs).
- `state/stack-profile.json` (framework versions from `build-tool-contract.json`).
- `state/generated-code-index.json` (CXF/OpenAPI/AP-generated FQCNs).

Contracts are **derived** from the index, never the reverse.

## Risks and mitigations

| Risk                                | Mitigation                                              |
|-------------------------------------|---------------------------------------------------------|
| Index out of sync with sources      | Fingerprints + `BLOCKED_INDEX_STALE`                    |
| `state/index/` growth on big repos  | Optional `.json.zst` compression                        |
| Schema evolution                    | `version` field + pre-stage migration                   |
| Two sources of truth                | Contracts derive from index; never the other direction  |
