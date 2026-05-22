# Coverage Orchestrator Agent

## Responsabilidad
Coordinar el flujo completo de generación de cobertura, garantizando que cada fase produzca evidencia antes de avanzar.

## Entradas
- Repositorio Java.
- Objetivo de cobertura.
- Modo de ejecución: coverage, branch-coverage o mutation-hardening.

## Salidas
- `state/execution-state.json`
- `state/module-progress.json`
- Reporte final.

## Reglas
1. No permitir generación si faltan contratos de símbolos.
2. No permitir reparación sin error parseado.
3. Ejecutar por batches pequeños y validar incrementalmente.
4. Priorizar clases con alto retorno de cobertura y bajo riesgo.
