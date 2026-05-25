# GitHub Copilot Workspace Instructions
# Java Test Coverage Agent — Anti-Hallucination Rules

> **IMPORTANT**: These instructions apply to ALL Copilot suggestions in this workspace.
> They enforce the same gates (G1–G9) as the LLM agent pipeline.
> Violating these rules produces tests that fail to compile or introduce hallucinated symbols.

---

## ABSOLUTE PROHIBITIONS — never do these

### 1. No invented imports (G1 — Import Whitelist)
- **NEVER** suggest an import that does not appear in `state/import-whitelist.json` or `state/index/imports.json`.
- If you don't know whether an import is valid → **omit it** and mark `// TODO: verify import`.
- Do NOT infer imports from class names, from training data, or from what "seems right."

### 2. No uninspected symbols (G2 — Symbol Evidence)
- Every `new X(...)`, `X.staticMethod(...)`, `obj.method(...)` MUST have an entry in
  `state/symbol-contracts/<fqcn>.json` or `state/index/methods.json`.
- If you are not sure a constructor or method exists → **use Mockito mock as fallback**.
- Do NOT complete method calls you cannot verify from the state files above.

### 3. No interface instantiation (Architecture Rule)
- **NEVER** write `new SomeInterface()` or `new AbstractClass()`.
- For FreeBuilder interfaces: use `InterfaceName.Builder` ONLY if documented in the contract.
- For unknown types: use `Mockito.mock(Type.class)`.

### 4. No invented builders / factories
- Do NOT suggest `Type.builder().field(x).build()` unless `@Builder` (Lombok) or the
  FreeBuilder pattern is confirmed in `state/symbol-contracts/<fqcn>.json`.
- Do NOT suggest `Mappers.getMapper(X.class)` unless the generated impl is confirmed.

### 5. No `@Ignore` / `@Disabled`
- Never silence a test with `@Ignore`, `@Disabled`, `assume*`, or a caught exception that swallows the failure.
- A test that doesn't run is not a test.

### 6. No non-determinism
- Never use `Thread.sleep(N)` without a comment citing why it's unavoidable.
- Never use `new Random()` or `Math.random()` without a fixed seed.
- Never use `LocalDateTime.now()`, `Instant.now()`, or `new Date()` without a `Clock` mock.

### 7. No modification of production code
- Test generation MUST NOT modify files under `src/main/java/`.
- If a class is untestable as-is, suggest extraction/refactor but do NOT apply it automatically.

### 8. No full-file context loading
- Do NOT suggest loading entire POMs, entire JaCoCo XML, or entire stack traces into prompts.
- Reference `state/index/` files and `state/symbol-contracts/` instead.

---

## REQUIRED BEFORE ACCEPTING A SUGGESTION

Run the AST linter before accepting any generated test method or class:

```bash
python tools/python/test_linter.py --file <path/to/TestFile.java> \
  --whitelist state/import-whitelist.json \
  --contracts state/symbol-contracts/
```

If the linter reports G1 (import) or G2 (symbol) violations → **reject the suggestion**.

---

## WHERE TO LOOK FOR VALID SYMBOLS

| What you need           | Where to look                                     |
|-------------------------|---------------------------------------------------|
| Valid imports           | `state/import-whitelist.json` → `packages[]`      |
| Class exists?           | `state/index/classes.json` → look up FQCN         |
| Constructor signature   | `state/symbol-contracts/<fqcn>.json` → `constructors[]` |
| Method exists?          | `state/index/methods.json` → `methods[fqcn]`      |
| Builder strategy        | `state/symbol-contracts/<fqcn>.json` → `instantiation` |
| Framework annotations   | `state/index/annotations.json` → `classes[fqcn]` |
| Test dependencies (DI)  | `state/dependency-graph.json` → `classes[fqcn]`  |
| Fixture builders        | `state/fixture-catalog.json`                      |

---

## GATE REFERENCE (G1–G9)

| Gate | What it checks                              | Trigger                         |
|------|---------------------------------------------|---------------------------------|
| G1   | Import in whitelist                         | Every import in generated test  |
| G2   | Symbol in contract (evidence-id required)   | Every `new`, method call        |
| G3   | Bytecode-first resolution                   | `target/classes` present        |
| G4   | Generated sources indexed                   | Annotation processors detected  |
| G5   | Stack profile declared                      | Before any generation           |
| G6   | AST linter passes before compile            | Every proposed test              |
| G7   | Failure memory not blocking the fix         | Repair attempts                  |
| G8   | No 2 consecutive zero-delta cycles          | Orchestrator convergence check  |
| G9   | JDT/Copilot diagnostics normalised to index | VS Code error squiggles          |

---

## WHEN COPILOT SUGGESTS SOMETHING YOU CANNOT VERIFY

```java
// PATTERN: symbol not in index — use mock instead
// ❌ Don't: new UnverifiedService(dep1, dep2)
// ✅ Do:    UnverifiedService sut = Mockito.mock(UnverifiedService.class);
//           // TODO: verify symbol in state/symbol-contracts/com.acme.UnverifiedService.json
```

---

## TEMPLATE SELECTION (Phase 5)

Choose the test template from `templates/` based on the SUT archetype:

| SUT type (from `state/classification-index.json`) | Template                          |
|----------------------------------------------------|-----------------------------------|
| `@RestController`, `@Controller`                   | `templates/webmvc-test.java`      |
| `@Service`, `@Component`, `@Repository`            | `templates/junit5-mockito.java`   |
| Reactive (`Mono`, `Flux`, `@ReactiveController`)   | `templates/reactive-test.java`    |
| `@SpringBootTest` integration tests                | `templates/springboot-test.java`  |

The LLM (and Copilot) completes **only** the `@Test` method bodies and assertions.
The skeleton (imports, class declaration, `@ExtendWith`, mocks) comes from the template.

---

## EVIDENCE-ID COMMENT REQUIREMENT

Every generated `@Test` method MUST end with an evidence comment:

```java
@Test
void testProcessName_happyPath() {
    // arrange
    when(collaborator.fetch("id")).thenReturn(fixture);
    // act
    String result = sut.processName("id");
    // assert
    assertThat(result).isEqualTo("expected");
    // evidence: sym:com.acme.FooService#processName:e7a1, ctor:com.acme.FooService:b3c1
}
```

If you cannot cite an evidence-id → the symbol is unverified → **remove that line**.

---

*These rules are enforced by the agent pipeline. Copilot suggestions that violate them
will be rejected by the test linter (G6) and will not be committed.*
