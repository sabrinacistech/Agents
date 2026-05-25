# Surgical Generator (Generation Agent)

## Responsibility
Emit **AST patches** that add or modify the minimum amount of test code needed to
exercise a target. Patches conform to `schemas/ast-patch.schema.json`.

## Output contract

Every emission is an AST patch:

```json
{
  "patchId": "p-<hash>",
  "targetFile": "src/test/java/com/acme/FooServiceTest.java",
  "sutFqcn": "com.acme.FooService",
  "createsFile": false,
  "evidenceIds": ["sym:com.acme.FooService#findById(Long):e7a1"],
  "tokenCost": 1240,
  "ops": [
    { "op": "AddImport", "fqn": "org.junit.jupiter.api.Test" },
    { "op": "AddMock", "type": "com.acme.BarRepository", "name": "barRepo" },
    { "op": "InsertMethod", "anchor": { "kind": "endOfClass" },
      "source": "@Test\nvoid shouldReturnEmpty_whenIdMissing() { /* … */ }" }
  ]
}
```

Allowed ops: `InsertMethod`, `ReplaceAssertion`, `ReplaceStatement`, `AddImport`,
`AddMock`, `InsertAnnotation`.

`createsFile: true` is permitted **only** when the test class does not yet exist;
in that case the patch references a template from `templates/` (selected
deterministically from `classification-index.json`).

## Inputs (minimal context — see `skills/00-runtime/minimal-context-policy.md`)

- target method (signature + body) from `state/index/methods.json`,
- collaborator signatures (one-hop) from `state/dependency-graph.json`,
- projected contract `state/symbol-contracts/_views/<batchId>.json`,
- whitelist subset from `state/import-whitelist.json`,
- fixture **ids** from `state/fixture-catalog.json` (the patcher resolves them),
- runtime mode (`coverage` | `branch-coverage` | `mutation-hardening`).

**Never** include: the full SUT class, the full test file, the POM, the JaCoCo
XML, or unrelated methods.

## Procedure

1. Pull the next item from `state/batch-plan.json`.
2. Choose template if `createsFile` (function of `classification-index.json`); otherwise edit-in-place.
3. Emit ops. The LLM produces only:
   - `InsertMethod.source` (the test body),
   - `ReplaceAssertion.replacement` (the new assertion),
   - method names matching `should<Behavior>_when<Condition>`.
4. The patcher (`tools/python/ast_patcher.py`) projects the result, runs G1 (whitelist) + G6 (AST lint) over the projection, and either writes or rejects.
5. Persist `state/generated-tests.json` with `{ testClass, sut, evidenceIds, patchId, status }`.
6. Record cost in `state/token-metrics.json`.

## Hard rules

- **No full-file generation** in edit-in-place mode.
- **No symbol without `evidenceId`**.
- **No `@Ignore` / `@Disabled`**.
- **No `Thread.sleep`, no unseeded randomness, no `now()` without `Clock`**.
- **No irrelevant stubs** — cross-checked against `state/dependency-graph.json`.
- **Token budget**: preferred < 1.5k per method; hard limit 5k.

## Skills

- `skills/07-generation/ast-patch-generation.md` (output spec)
- `skills/07-generation/unit-test-generation.md` (AAA conventions for the body)
- `skills/07-generation/mockito-strategy.md`
- `skills/07-generation/test-quality-gate.md`
- `skills/07-generation/freebuilder-test-strategy.md`
- `skills/07-generation/java-8-compatibility.md` (only when `java == 1.8`)

## Gates owned

- **G1** (whitelist) — validated by the patcher before write.
- **G2** (evidence) — checked per op.
- **G6** (AST lint) — runs on the projected patch result.

## Anti-patterns

- Emitting the whole test class to "be safe".
- Including unrelated methods of the SUT in the prompt.
- Pasting the JaCoCo XML or POM as context.
- Generating patches that span more than one test method.
- Re-sending the full symbol contract on every method.
