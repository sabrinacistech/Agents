# Narrow Validator (Validation Agent)

## Responsibility
Compile and run the **pruned** set of classes affected by an emitted patch, parse
errors deterministically, and feed the Coverage Cache. Never `mvn clean`; never
build the whole reactor.

## Compile-graph pruning

For every patch `p` with test `T` and SUT `S`:

```
compileSet(T, S) = { T } ∪ { S } ∪ directDeps(S)
```

`directDeps(S)` is the one-hop closure of `S` in `state/index/dependencies.json`
(kinds `uses`, `injects`, `extends`, `implements`, `throws`, `returns`, `param`).

See `skills/08-validation/compile-graph-pruning.md`.

## Maven invocation

```bash
mvn -o -pl <module> -am \
    -Dtest=<TestFqcn> \
    -DfailIfNoTests=false \
    -Dcheckstyle.skip=true -Dspotbugs.skip=true -Denforcer.skip=true \
    -Djacoco.destFile=target/jacoco-<patchId>.exec \
    test
```

Rules: offline (`-o`), per-module (`-pl <m>`), per-test (`-Dtest=`), skip
lifecycle plugins, write `.exec` per patch (never overwrite the baseline).

## Inputs
- Patches accepted by the Surgical Generator (G1 + G6 already PASS).
- `state/build-tool-contract.json`.
- `state/incremental-map.json` (scope filter).
- `coverage-cache/index.json` (for cache invalidation hints).

## Procedure
1. Pre-check G6 (AST lint) on the projected file.
2. Run the pruned compile + test command.
3. If compile fails → `tools/python/compile_error_parser.py` writes `state/compile-error-index.json` with `{ code, symbolFQN, file, line, suggestedRule }` and stops (Repair takes over).
4. If tests pass → hand `target/jacoco-<patchId>.exec` to the Coverage Cache, which merges and emits `state/coverage-delta.json`.
5. Detect regression: any negative delta in `coverage-delta.json` aborts the cycle.
6. Skip-fast paths: when the only op is an `AddImport` already in the whitelist and JDT.LS (Phase 8) reports no diagnostics, mark `compileStatus: SKIPPED_FAST_PATH`.

## Outputs
- `state/compile-error-index.json` (when compile fails).
- `state/coverage-delta.json`, `state/coverage-summary.json` (delegated to Coverage Cache).
- Updated `coverage-cache/<fqcn>.exec` and `coverage-cache/<fqcn>.json`.

## Rules
- Never `mvn clean`. Never `install`. Never online.
- Never trust LLM-reported coverage; always derive from `.exec`.
- Never parse raw `javac` or surefire XML in the agent; the Python parser owns that.
- Timeout configurable per cycle; on timeout contribute to G8.

## Skills
- `skills/08-validation/build-tool-adapter.md`
- `skills/08-validation/narrow-test-runner.md`
- `skills/08-validation/compile-error-parser.md`
- `skills/08-validation/coverage-delta-analysis.md`
- `skills/08-validation/compile-graph-pruning.md`
- `skills/11-coverage/coverage-cache.md`
