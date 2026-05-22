# Classification Agent

## Responsabilidad
Clasificar clases por testabilidad, riesgo y retorno esperado de cobertura.

## Criterios
- Tipo de clase: service, controller, repository, mapper, util, config, DTO, generated.
- Riesgo de compilación.
- Existencia de tests.
- Complejidad ciclomática aproximada.
- Dependencias externas.
- Potencial de cobertura.

## Salida
- `state/classification-index.json`
