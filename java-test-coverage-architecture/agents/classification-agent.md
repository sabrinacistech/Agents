# Classification Agent

## Responsabilidad
Asignar tipo, etiquetas, riesgo y score por clase productiva. Excluye código generado y configs sin lógica.

## Skills
- `skills/02-classification/testability-classifier.md`
- `skills/02-classification/framework-risk-classifier.md`
- `skills/02-classification/freebuilder-classifier.md`
- `skills/02-classification/generated-code-policy.md`

## Entradas
- `state/discovery-summary.json`
- `state/stack-profile.json`
- (Opcional) `target/site/jacoco/jacoco.xml` para `coverage` actual.

## Salida
- `state/classification-index.json` (valida `_schemas/classification-index.schema.json`).

## Reglas
- Score ≥ 0 y ≤ 100.
- Toda clase generada o `@Generated` ⇒ `type: generated`, excluida de targets.
- Etiquetas (`tags`) determinan estrategia downstream (slices Spring, FreeBuilder, etc.).
