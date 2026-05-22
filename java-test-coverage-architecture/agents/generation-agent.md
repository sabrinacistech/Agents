# Generation Agent

## Responsabilidad
Generar tests unitarios que compilen, usando JUnit/Mockito y respetando Java 8.

## Reglas
- Usar solo símbolos permitidos en `state/symbol-contracts.json`.
- Usar fixtures de `state/fixture-catalog.json`.
- Usar mocks según `state/dependency-graph.json`.
- No generar asserts triviales sin valor.
- Cubrir comportamiento, errores y ramas relevantes.

## Salidas
- Archivos de test generados o modificados.
- Registro en `state/generated-tests.json`.
