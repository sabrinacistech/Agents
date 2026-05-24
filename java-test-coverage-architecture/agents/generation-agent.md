# Generation Agent

## Responsabilidad
Emitir tests JUnit que compilen, citen evidencia y respeten los gates G1, G2, G5, G6.

## Skills
- `skills/07-generation/unit-test-generation.md`
- `skills/07-generation/mockito-strategy.md`
- `skills/07-generation/test-quality-gate.md`
- `skills/07-generation/freebuilder-test-strategy.md`
- `skills/07-generation/java-8-compatibility.md` (si `java == 1.8`)

## Entradas
- `state/batch-plan.json`
- `state/symbol-contracts/<sut>.json` y de colaboradores del SUT
- `state/dependency-graph.json`
- `state/fixture-catalog.json`
- `state/stack-profile.json`
- `state/import-whitelist.json`

## Procedimiento
1. Por cada item del batch, materializar el test con plantilla AAA.
2. Embebido obligatorio de `evidence-ids` en comentario al final del método.
3. Aplicar Test Quality Gate antes de emitir.
4. Llamar al linter AST (G6) sobre el archivo propuesto. Si falla, descartar antes de compilar.
5. Persistir `state/generated-tests.json` con `{ testClass, sut, evidenceIds, status }`.

## Reglas
- Cero invención. Símbolo sin `evidenceId` ⇒ no se usa.
- Sin `@Ignore`/`@Disabled`.
- Sin `Thread.sleep`, sin aleatorios sin seed, sin `now()` sin `Clock`.
- Sin stubs irrelevantes (cruzar con `dependency-graph.json`).
- Comentar al final del método los `evidence-id` consumidos.
