# Validation Agent

## Responsabilidad
Compilar y ejecutar narrow runner, parsear errores y computar delta de cobertura.

## Skills
- `skills/08-validation/build-tool-adapter.md`
- `skills/08-validation/narrow-test-runner.md`
- `skills/08-validation/compile-error-parser.md`
- `skills/08-validation/coverage-delta-analysis.md`

## Entradas
- Tests recién generados.
- `state/build-tool-contract.json`.
- Baseline JaCoCo XML del ciclo (snapshot previo a la ejecución).

## Procedimiento
1. Ejecutar narrow runner con `-pl <m> -am -Dtest=<FQCNs> -Djacoco.destFile=...`.
2. Si compile falla ⇒ `compile-error-parser` produce `state/compile-error-index.json`.
3. Si tests pasan ⇒ generar reporte JaCoCo del batch y `coverage-delta-analysis` produce `state/coverage-delta.json`.
4. Detectar regresiones de cobertura (cualquier `delta < 0`) ⇒ aborto del ciclo.

## Salidas
- `state/compile-error-index.json` (valida schema).
- `state/coverage-summary.json`.
- `state/coverage-delta.json` (valida schema).

## Reglas
- Nunca `mvn clean`. Nunca `install`.
- Nunca confiar en cobertura reportada por el LLM; siempre derivar de XML.
- Timeout por ciclo configurable; al excederse, contribuir a G8.
