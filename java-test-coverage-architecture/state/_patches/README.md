# state/_patches — AST Patch Rollback Store (Phase 4)

Stores reversible diffs for every AST patch applied by the Generation Agent.

## Purpose

When Generation emits `InsertMethod`/`AddImport`/`AddMock`/`ReplaceAssertion`/`AddField`/`AddAnnotation`
patches (Phase 4 surgical generation), the patch applier writes a `.diff` file here
**before** modifying the test file. If validation (G1/G6/compile) fails, the orchestrator
rolls back by applying the inverse diff.

## File naming

```
<cycle>-<sut_slug>-<patch_id>.diff
```

Example: `003-com.acme.FooService-p0014.diff`

## Lifecycle

1. Generation Agent emits patch JSON via `skills/07-generation/ast-patch-generation.md`.
2. `tools/python/ast_patcher.py` writes diff here, then applies the patch.
3. Validation (G6 linter → compile → JaCoCo) runs.
4. On success: diff is kept for audit; orchestrator registers in `execution-state.json`.
5. On failure: `ast_patcher.py --rollback <diff>` restores the file; diff is deleted.

## Retention policy

- Successful patches: kept until `state/_summaries/cycle-N.json` is written (then archived).
- Failed patches: deleted immediately after rollback.
- Maximum: 500 diffs. Older successful diffs are purged by the orchestrator at cycle end.

## Atomicity

Diffs are written with `*.tmp` + rename, same as all other state files.
