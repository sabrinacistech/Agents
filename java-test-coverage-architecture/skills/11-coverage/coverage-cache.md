# Coverage Cache (Coverage Skill)

> Last stage of the lean architecture. Owns coverage merging and incremental
> delta computation. Eliminates full JaCoCo reruns.

## Layout

```
coverage-cache/
  baseline.exec               # snapshot from the last green full cycle (read-only)
  <fqcn>.exec                 # per-class merged exec file
  <fqcn>.json                 # per-class summary { line, branch, instruction, complexity }
  index.json                  # { fqcn -> sha256, lastUpdated, baselineHash }
```

The cache lives at the architecture root (not under `state/`) because it stores
binary JaCoCo `.exec` files. `state/` keeps pointers and summaries.

## Update protocol

After Narrow Validator emits `target/jacoco-<patchId>.exec`:

1. **Merge**: `java -jar jacococli.jar merge target/jacoco-<patchId>.exec coverage-cache/<fqcn>.exec --destfile coverage-cache/<fqcn>.exec.tmp` → atomic rename.
2. **Report (per class only)**: generate a class-scoped report into
   `coverage-cache/<fqcn>.json` using `jacococli report --classfiles target/classes/<path>`.
3. **Delta**: compare `coverage-cache/<fqcn>.json` against the previous snapshot
   recorded in `coverage-cache/index.json` → write `state/coverage-delta.json` with
   `lines`, `branches`, `instructions`, `complexity` (signed deltas).
4. **Index**: update `coverage-cache/index.json` with the new SHA-256 and timestamp.

## Invalidation

Per-class entries are invalidated when:

- the SUT source SHA-256 in `state/index/classes.json` changes,
- a dependency in `state/index/dependencies.json` whose `kind = injects|extends|implements` changes,
- the baseline is refreshed (full mode).

When invalidated, the `<fqcn>.exec` is dropped and the next narrow run re-seeds it.

## Baseline refresh

Only triggered by:

- explicit `--full` flag from the orchestrator,
- detected git tag / release boundary,
- staleness of `baseline.exec` older than configured `maxBaselineAgeDays`.

Otherwise the cache evolves incrementally forever — no full coverage rebuild.

## Read API

The Coverage Orchestrator and the Reporting Agent consume:

- `state/coverage-delta.json` — last patch's signed delta.
- `state/coverage-summary.json` — running totals (`covered`, `missed`, `pct`).
- `coverage-cache/index.json` — for staleness checks.

Never read raw `.exec` files from agents. The cache is the only surface.

## Anti-patterns

- Running `jacoco:report` on the whole module after each patch.
- Holding `.exec` in memory across runs (they live on disk).
- Recomputing baseline on every cycle.
- Mixing baseline and incremental exec files in the same destfile.
