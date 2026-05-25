# Deterministic Repair Engine (Repair Agent)

## Responsibility
Resolve compile failures and runtime test failures using **deterministic rules
first**. The LLM is invoked only when a rule explicitly returns
`escalateToLLM(<reason>)`.

## Repair pipeline

```
compile-error-index.json
        ↓
repair-rules/*.rules   (deterministic match → AST patch via ast_patcher.py)
        ↓
Narrow Validator       (re-compile pruned set)
        ↓
[still failing?]
        ↓ yes
repair-rules check     → if rule said escalateToLLM, call LLM with minimal context
        ↓
Narrow Validator       (one more attempt)
        ↓
[still failing?]       → mark failure-memory.json#FAILED, drop the patch
```

Maximum 2 deterministic attempts + 1 LLM fallback per test. After that, the
patch is rolled back (`state/_patches/<patchId>.diff`) and the failure recorded.

## Rule files (`repair-rules/`)

- `imports.rules` — missing/ambiguous imports.
- `mockito.rules` — strict stubbing, matchers, void-method stubs.
- `spring.rules` — bean wiring, slices, profiles.
- `junit.rules` — runner/extension, lifecycle migration.
- `builders.rules` — FreeBuilder, Lombok `@Builder`, generated code.

## Inputs
- `state/compile-error-index.json` (already parsed; the LLM never sees raw errors).
- `state/symbol-contracts/<fqcn>.json` for verified replacements.
- `state/import-whitelist.json`.
- `state/failure-memory.json`.

## Procedure
1. For each entry in `compile-error-index.json`, match against `repair-rules/*.rules`.
2. If a rule matches and is not `escalateToLLM`, apply the AST patch via `tools/python/ast_patcher.py`. Skip the LLM.
3. If the rule is `escalateToLLM(<reason>)`, prepare an LLM prompt with **minimal context** (see `skills/00-runtime/minimal-context-policy.md`):
   - failing lines ±2 lines,
   - parsed cause from `compile-error-index.json`,
   - projected contract subset,
   - rule reason.
4. Compute `hash(errorCode, symbolFQN, fixId)`. If FAILED in `failure-memory.json`, G7 forbids the fix.
5. Apply, re-validate via Narrow Validator (pruned compile).
6. Record `{ errorCode, symbolFQN, fixId, result }` in `failure-memory.json`.

## Outputs
- Patched tests or rollback diffs in `state/_patches/`.
- Updated `state/failure-memory.json`.

## Rules
- **No symbol invention** to "fix" an error.
- **No silencing** (`@Ignore`/`@Disabled`).
- **No assertion weakening** to force a pass.
- **No raw error parsing** in the LLM — always go through `compile-error-index.json`.
- LLM budget: < 0.8k tokens preferred, 3k hard.

## Skills
- `skills/09-repair/repair-decision-matrix.md`
- `skills/09-repair/failure-memory.md`
- `skills/09-repair/retry-policy.md`

## Gates owned
- **G7** (failure-memory) — every fix consults it; no re-application of FAILED hashes.
