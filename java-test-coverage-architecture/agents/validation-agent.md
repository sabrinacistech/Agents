# Validation Agent

## Responsabilidad
Validar compilación, ejecución de tests y delta de cobertura.

## Validaciones
- Narrow test run por clase o módulo.
- Build de test.
- JaCoCo XML.
- Errores de compilación.
- Failures de tests.

## Salidas
- `state/compile-error-index.json`
- `state/coverage-summary.json`
- `state/coverage-delta.json`
