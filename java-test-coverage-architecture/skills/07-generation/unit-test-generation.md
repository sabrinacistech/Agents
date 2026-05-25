# Unit Test Generation (Surgical Mode)

> Conventions for the **body** the LLM places inside `InsertMethod` /
> `ReplaceAssertion` ops. Output is always an AST patch
> (`schemas/ast-patch.schema.json`); never a whole file (except `createsFile: true`,
> which uses a `templates/` skeleton).

## Preconditions
- `state/stack-profile.json` valid (G5).
- `state/import-whitelist.json` current (G1).
- Projected contract `state/symbol-contracts/_views/<batchId>.json` available (G2).
- Required fixtures present in `state/fixture-catalog.json`.

## Body conventions (inside `InsertMethod.source`)

Use AAA shape. Keep it under ~25 lines.

```java
@Test
void shouldReturnEmpty_whenIdMissing() {
    // Arrange  — fixtures resolved by the patcher via fixture ids
    when(barRepo.findById(1L)).thenReturn(Optional.empty());

    // Act
    Optional<Bar> result = sut.findById(1L);

    // Assert
    assertThat(result).isEmpty();
    verify(barRepo).findById(1L);

    // evidence-ids:
    //   sym:com.acme.FooService#findById(Long):e7a1
    //   sym:com.acme.BarRepository#findById(Long):a3c2
}
```

## Rules
- One scenario per `InsertMethod` op (happy / branch / exception).
- Naming: `should<Behavior>_when<Condition>` or `methodName_condition_expected`.
- One Act invocation per test.
- Assertion library follows `stack-profile` (AssertJ if present, JUnit otherwise).
- Stubs only for methods the SUT actually invokes (cross-check `state/dependency-graph.json`).
- Forbidden: `Thread.sleep`, `System.out`, non-fixed dates, unseeded randomness, wildcard imports, `@Ignore` / `@Disabled`.
- `evidence-id` block is mandatory at the end of each method body.

## Cite, don't import

`AddImport` ops are emitted by the deterministic patcher, not by the LLM.
The LLM body uses simple names that **must** map to symbols in the projected
contract / whitelist. Anything outside that surface is rejected by G1/G6
before write.

## Anti-patterns
- Returning whole class bodies inside `InsertMethod.source`.
- Generating multiple `@Test` methods in a single op.
- Inventing collaborators not present in the projected dep-graph.
- Stubbing collaborators that aren't actually invoked.
- Omitting the evidence-id block.
