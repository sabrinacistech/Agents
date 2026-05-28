# Compile Graph Pruning (Validation Skill)

## Goal
Compile and validate only the minimum set of classes affected by the change.
Slash latency, slash JVM warm-up cost, slash JaCoCo execution time.

## Pruned compile set

For each generated/repaired test `T` targeting SUT `S`:

```
compileSet(T, S) = { T } ∪ { S } ∪ directDeps(S)
```

Where `directDeps(S)` is the **one-hop** outgoing closure of `S` in
`state/index/dependencies.json` (kinds `uses`, `injects`, `extends`, `implements`,
`throws`, `returns`, `param`). No transitive expansion unless `T` references a
transitive symbol explicitly (detected via the AST of `T`).

## Maven invocation

```bash
mvn -o -pl <module> -am \
    -Dtest=<TestFqcn> \
    -DfailIfNoTests=false \
    -Dcheckstyle.skip=true -Dspotbugs.skip=true -Denforcer.skip=true \
    -Djacoco.destFile=target/jacoco-<patchId>.exec \
    test
```

Rules:

- **never** `mvn clean`,
- **never** `install`,
- always `-o` (offline) — the classpath is already resolved by the pre-stage,
- `-pl <module>` confines the build to the affected module,
- `-Dtest=<FQCN>` confines surefire to the single test class.

## Partial JaCoCo

- Output `target/jacoco-<patchId>.exec` per patch (never overwrite the baseline).
- The Coverage Cache (`skills/11-coverage/coverage-cache.md`) merges
  `target/jacoco-<patchId>.exec` into the per-class cache and computes the delta
  against the baseline. No global report regeneration.

## Compile error narrowing

`tools/python/compile_error_parser.py` emits `state/compile-error-index.json` with:

```json
{
  "file": "src/test/java/.../FooTest.java",
  "line": 42,
  "code": "cannot find symbol",
  "symbolFQN": "org.mockito.Mock",
  "suggestedRule": "imports.rules#org.mockito.Mock"
}
```

The Repair Engine consumes this index; the LLM never parses raw `javac` output.

## Skip conditions (fast path)

Skip compile entirely when:

- Patch is `AddImport` only and the FQN is already in `state/import-whitelist.json` **and** JDT.LS (Phase 8) reports no diagnostics for the target file.
- Patch is `ReplaceAssertion` and the new assertion uses symbols already in the projected contract.

These shortcuts are recorded as `compileStatus: "SKIPPED_FAST_PATH"` in the cycle summary.

## Anti-patterns

- Building the whole reactor on every patch.
- Running JaCoCo full-report after each test.
- Re-resolving the classpath from `pom.xml` between patches.
- Compiling transitive deps when only one collaborator is touched.
