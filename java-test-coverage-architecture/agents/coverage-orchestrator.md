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
3. Antes de compilar, exigir G1 (whitelist) y G6 (static pre-compile linter) sobre cada test propuesto.
4. Antes de aplicar fix, consultar G7 (failure-memory).
5. Tras cada ciclo, evaluar G8 (convergencia).
6. Escritura atómica en `state/` (`*.tmp` + rename); actualizar `checkpoints[]` con SHA-256.
7. Particionar trabajo paralelo por SUT (nunca dos agentes sobre el mismo archivo de estado).

## Compresión de historial de ciclos (Phase 5)

Al **finalizar cada ciclo** (después de Reporting), invocar:

```bash
python tools/python/cycle_summarizer.py --state state/ --cycle <N> --mode <mode>
```

Esto escribe `state/_summaries/cycle-<N>.json` con un resumen compacto.

**Regla de contexto**: en ciclos posteriores, el Orchestrator carga únicamente:
- Los últimos **2** summaries (`cycle-N.json`, `cycle-(N-1).json`).
- El estado completo del ciclo **actual** solamente.
- **Nunca** los archivos crudos de ciclos anteriores (generated-tests.json, compile-error-index.json, coverage-delta.json de ciclos pasados).

Esto mantiene el presupuesto de contexto O(1) independiente del número de ciclos.

## Rollback via patches (Phase 4)

Patches en `state/_patches/` son escritos por `tools/python/ast_patcher.py` antes de
modificar cada test. Si la validación falla: `ast_patcher.py --rollback <diff>`.

## Criterios de parada
- G8 activado.
- `budget.maxCycles` alcanzado.
- Objetivo de cobertura del modo alcanzado.
- Aborto manual.

## Phase → Tool → State

Tabla canónica del trabajo determinista que antes vivía en agentes degradados
(`planning-agent`, `fixture-agent`, `validation-agent`). Cada fila describe la
fase, la herramienta Python que la materializa y el estado que produce. El
orquestador invoca las herramientas; no hay agente LLM intermedio.

| Phase                | Tool (`tools/python/`)            | State producido                                                  |
|----------------------|-----------------------------------|------------------------------------------------------------------|
| Discovery            | `pom_parser.py`                   | `state/build-tool-contract.json`                                 |
| Archetype            | `archetype_detector.py`           | `state/archetype-profile.json`                                   |
| Generated code       | `generated_code_scanner.py`       | `state/generated-code-index.json`                                |
| Classpath / whitelist| `classpath_resolver.py`           | `state/import-whitelist.json`                                    |
| Stack profile        | `stack_profile_detector.py`       | `state/stack-profile.json`                                       |
| Symbol contracts     | `bytecode_scanner.py` + `source_symbol_enricher.py` | `state/symbol-contracts/<fqcn>.json`               |
| Coverage targets     | `jacoco_parser.py --mode targets` | `state/coverage-targets.json`                                    |
| Semantic index       | `semantic_index_writer.py`        | `state/index/{classes,methods,imports,dependencies,annotations}.json` |
| Classification       | `classification_analyzer.py`      | `state/classification-index.json`                                |
| Dependency graph     | `dependency_graph_extractor.py`   | `state/dependency-graph.json`                                    |
| Fixtures             | `fixture_catalog_builder.py`      | `state/fixture-catalog.json`                                     |
| Planning             | `coverage_planner.py`             | `state/batch-plan.json`                                          |
| Incremental scope    | `incremental_map_writer.py`       | `state/incremental-map.json`                                     |
| State validation     | `state_validator.py`              | (no artifact; gate before LLM stage)                             |
| Context packs        | `context_pack_builder.py`         | `state/context-packs/<safe_fqcn>.json` (+ `-compact/` opcional)  |
| Generation (LLM)     | `test-intent-agent` + `test-body-agent` | patch JSON → `tools/python/test_patch_applier.py`          |
| Pre-compile lint     | `test_linter.py`                  | gate G6 (no artifact)                                            |
| Narrow validation    | `narrow_test_runner.py` + `compile_error_parser.py` | `state/_summaries/build-output.log` + `state/compile-error-index.json` + `state/coverage-delta.json` |
| Repair (LLM)         | `repair-agent`                    | nuevo patch JSON                                                 |
| Cycle summary        | `cycle_summarizer.py`             | `state/_summaries/cycle-<N>.json`                                |
| Reporting (LLM)      | `reporting-agent`                 | reporte final                                                    |

Reglas heredadas (antes vivían en los stubs `planning-agent` / `fixture-agent`
/ `validation-agent`):

- **Planning**: excluir targets sin `hasContract` o `hasFixtures`; ordenar por
  ROI (`skills/06-planning/coverage-roi-planning.md`); batch dinámico por
  `compileFailRate` histórico; en `branch-coverage` nunca dos targets del mismo
  SUT en un batch.
- **Fixtures**: estrategia en orden builder verificado → constructor → factory
  → mock pasivo; variantes mínimas `default`, `boundary` (solo
  `branch-coverage`), `null-optional`, `empty-collections`; nada de
  `LocalDateTime.now()` sin `Clock` controlado.
- **Validation**: nunca `mvn clean` ni `install`; siempre derivar cobertura del
  XML; cualquier `delta < 0` aborta el ciclo; timeout configurable contribuye a
  G8.
