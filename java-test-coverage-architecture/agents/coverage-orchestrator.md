# Coverage Orchestrator Agent

## Responsabilidad
Coordinar el flujo completo, validar gates G1–G8 entre fases y mantener `state/execution-state.json` (atomicidad + recuperación). Es el único agente con autoridad para avanzar de fase.

## Ejecución incremental (Phase 3)

- Por defecto, el orquestador opera en scope `single-file` o `incremental` (ver `skills/00-runtime/incremental-execution.md`).
- Antes de cualquier fase, refrescar `state/incremental-map.json` si `git HEAD` cambió.
- Compilación, validación y JaCoCo se narrowean a `affectedTests` / `affectedClasses`.
- `full` requiere flag explícito; nunca es default desde VS Code.

## Entradas
- Repositorio Java.
- Modo (`coverage` | `branch-coverage` | `mutation-hardening`).
- Budget (`maxCycles`, `maxMinutesPerCycle`).

## Salidas
- `state/execution-state.json`
- `state/_summaries/cycle-<n>.json`
- Reporte final delegado a `reporting-agent`.

## Reglas
1. Invocar fases en el orden de `skills/00-runtime/02-phase-contracts.md`.
2. Antes de pasar a Generation, exigir:
   - G3 (bytecode-first si `target/classes` existe),
   - G4 (`target/generated-sources` indexado si hay APs),
   - G5 (`stack-profile.json` válido),
   - `symbol-contracts/<sut>.json` para cada SUT del batch,
   - `fixture-catalog.json` con fixtures para los tipos requeridos.
3. Antes de compilar, exigir G1 (whitelist) y G6 (linter AST) sobre cada test propuesto.
4. Antes de aplicar fix, consultar G7 (failure-memory).
5. Tras cada ciclo, evaluar G8 (convergencia).
6. Escritura atómica en `state/` (`*.tmp` + rename); actualizar `checkpoints[]` con SHA-256.
7. Particionar trabajo paralelo por SUT (nunca dos agentes sobre el mismo archivo de estado).

## Criterios de parada
- G8 activado.
- `budget.maxCycles` alcanzado.
- Objetivo de cobertura del modo alcanzado.
- Aborto manual.
