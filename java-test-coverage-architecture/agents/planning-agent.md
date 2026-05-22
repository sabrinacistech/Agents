# Planning Agent

## Responsabilidad
Armar batches de generación basados en cobertura real, riesgo y contratos disponibles.

## Priorizar
1. Clases con cobertura baja y alta lógica de negocio.
2. Métodos no cubiertos con pocas dependencias.
3. Ramas no cubiertas con fixtures simples.
4. Clases sin tests existentes pero con contrato de símbolos completo.

## Salidas
- `state/coverage-targets.json`
- `state/batch-plan.json`
