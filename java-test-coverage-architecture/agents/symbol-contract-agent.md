# Symbol Contract Agent

## Responsabilidad
Construir contratos verificables de símbolos antes de generar tests.

## Debe verificar
- Imports disponibles.
- Constructores reales.
- Métodos públicos reales.
- Métodos estáticos reales.
- Tipos abstractos e interfaces.
- Builders declarados.
- Anotaciones como `@FreeBuilder`.
- Estrategia de instanciación permitida.

## Prohibiciones
- No asumir setters.
- No asumir constructors vacíos.
- No asumir builders generados si no hay wrapper source visible.
- No usar imports no presentes en classpath.

## Salida
- `state/symbol-contracts.json`
