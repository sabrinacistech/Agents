# BOOT — Punto único de arranque

Este archivo es **el único punto de entrada** para iniciar el sistema de agentes.
Cargalo (o pegalo en el chat) junto con `MASTER_PROMPT.md`, que actúa como contrato técnico (gates, schemas, división del trabajo).

> Asume que la arquitectura vive en `java-test-coverage-architecture/` y se ejecuta desde esa raíz. Si tu setup pone esta arquitectura embebida bajo otro path (`docs/agents/...`), ajustá las rutas relativas; el contenido del flujo es idéntico.

---

## Rol

Actuá como el **Coverage Orchestrator** definido en `MASTER_PROMPT.md` y `agents/coverage-orchestrator.md`. Cargá y aplicá obligatoriamente:

- `MASTER_PROMPT.md`
- `agents/coverage-orchestrator.md`
- `docs/python-pipeline.md`
- `docs/performance-tuning.md`
- `docs/archetype-policy.md`
- Los skills de la fase activa bajo `skills/**`
- Los schemas bajo `state/_schemas/**`

---

## Parámetros de ejecución

```yaml
repo:           <ruta o "workspace actual">
modules:        <"all" | lista de módulos Maven/Gradle>
mode:           <coverage | branch-coverage | mutation-hardening>
includeFqcn:    <regex, ej. '^com\.acme\.'>
budget:
  maxCycles:          10
  maxMinutesPerCycle: 10
coverageGoal:
  lines:    0.80      # opcional
  branches: 0.60      # opcional
writeTests:    false  # true = escribe en src/test/java; false = solo propone
```

Los parámetros `module`, `includeFqcn` y la ruta de JaCoCo pueden auto-detectarse vía `tools/python/bootstrap.py` (ver Phase 0).

---

## Phase 0 — Python pre-stage (OBLIGATORIO)

Antes de cualquier fase LLM, el pipeline determinista debe haber producido los `state/*.json` que los agentes consumen.

### Modo recomendado (auto-detección)

```bash
python tools/python/bootstrap.py --repo <ruta-al-repo-java>
```

`bootstrap.py` infiere `--module`, `--include-fqcn` (a partir de `<groupId>`) y `--jacoco-xml` (si existe `target/site/jacoco/jacoco.xml`), invoca `run_pipeline.py` y emite un único bloque JSON con `{module, includeFqcn, jacocoXml, statePath}` que el agente consume.

Usar `--dry-run` para imprimir los comandos sin ejecutarlos.

### Modo manual (override de parámetros)

Si necesitás controlar los parámetros explícitamente:

```bash
mvn -q -DskipTests package          # desde el repo Java
python tools/python/run_pipeline.py \
  --repo         <ruta-al-repo-java> \
  --out          ../.agent-state \
  --module       <module> \
  --include-fqcn '<regex>' \
  --jacoco-xml   <ruta-al-repo-java>/target/site/jacoco/jacoco.xml \
  --coverage-mode <coverage|branch-coverage|mutation-hardening>
```

> `../.agent-state` es el default cuando se ejecuta vía `run_agents.ps1` o `bootstrap.py`:
> los outputs se escriben en un directorio hermano del repo de la arquitectura. Sobrescribible
> con `-StateDir` / `--out` para apuntar a cualquier ubicación.

### Salidas obligatorias (lista canónica enforced por `validate_handoff.py`)

Archivos JSON (no-vacíos):

- `state/build-tool-contract.json`
- `state/archetype-profile.json`
- `state/generated-code-index.json`
- `state/import-whitelist.json`
- `state/stack-profile.json`
- `state/classification-index.json`
- `state/dependency-graph.json`
- `state/fixture-catalog.json`
- `state/batch-plan.json`

Directorios con al menos una entrada `*.json`:

- `state/symbol-contracts/`
- `state/context-packs-compact/`

Opcionales (si aplica):

- `state/coverage-targets.json` (cuando hay baseline JaCoCo)

`validate_handoff.py` corre tres chequeos: (a) presencia + tamaño>0 → si falla
emite `BLOCKED_PRE_STAGE_MISSING`; (b) cada JSON valida contra su schema en
`state/_schemas/` → si falla emite `BLOCKED_PRE_STAGE_INVALID`; (c) emite
`state/_summaries/handoff-summary.json` con los facts derivados. Los agentes
nunca leen POMs, classpath crudo, `javap` ni `jacoco.xml` directamente: consumen
sólo el handoff-summary + el context-pack compacto del SUT activo.

> Los outputs **no viven dentro del repo**. Por default se escriben en `../.agent-state/`
> (sibling del repo de la arquitectura), creado por `run_pipeline.py` en el primer ciclo
> con escritura atómica (`*.tmp` + rename). Lo único que persiste versionado bajo `state/`
> son los schemas (`state/_schemas/`). Ver `.gitignore`.

---

## Recuperación de fallos

Si una corrida se interrumpe (proceso killed, error de I/O, validador retorna
`BLOCKED_*`), el protocolo de recuperación vive en
[`skills/00-runtime/04-state-and-recovery.md`](skills/00-runtime/04-state-and-recovery.md).
Resumen operativo:

- `state/execution-state.json` registra `lastGoodCheckpoint` (cycle/phase) y
  los hashes SHA-256 vigentes.
- Para rebotar desde el último checkpoint sano: re-correr `run_pipeline.py`
  (idempotente; `run_pipeline.py` reusa la caché centralizada en `state/_summaries/cache.json`).
- Para reset duro: borrar la carpeta hermana `../.agent-state/` y re-correr
  Phase 0. Los schemas (`state/_schemas/`) viven dentro del repo y nunca se
  borran.

## Reglas duras

1. No inventar paquetes, clases, métodos, builders, setters, constructors ni imports.
2. Toda línea de cada test propuesto debe citar un `evidence-id` del contrato.
3. Aplicar los gates G1–G9 entre fases. Si un gate falla, NO avanzar: reportar y pedir decisión.
4. Escritura atómica en `state/` (`*.tmp` + rename). Hashes SHA-256 en `state/execution-state.json`.
5. Nunca editar `pom.xml` ni `build.gradle`. Nunca `mvn clean` / `install`.
6. Cobertura solo derivada de los JaCoCo XML reales (baseline + final).
7. Antes de proponer un test, pasarlo por `tools/python/test_linter.py`. Si tiene violaciones G1/G6, descartarlo sin invocar `javac`.
8. Respetar `state/generated-code-index.json#excludedFqcns` y `excludedPackages`: esas clases no son SUT.
9. Respetar `state/archetype-profile.json#implies` para `javax`/`jakarta`, JUnit y JaCoCo.

---

## Procedimiento

Post-audit 2026-05-28: las fases 1-7 (discovery → planning) fueron
**colapsadas en una única validación Python** (`validate_handoff.py`). El LLM
ya no las ejecuta como turnos separados — solo lee el resumen que produce.

```text
[DET] Phase 0:       run_pipeline.py  (16 steps, todo Python)
[DET] Handoff gate:  validate_handoff.py  ← reemplaza las viejas fases LLM 1-7
[LLM] Phase 8:       generation (test-intent → test-body)
[DET] Phase 9:       validation (test_linter → narrow runner)
[DET] Phase 10a:     repair determinista (repair_rules_compiler + ast_patcher)
[LLM] Phase 10b:     repair-agent (solo si determinista escaló)
[DET] Phase 11:      reporting (cycle_report_builder.py)
```

**Comando obligatorio antes de Generation**:

```bash
python tools/python/validate_handoff.py --state ../.agent-state/
```

Si la salida es `BLOCKED_PRE_STAGE_MISSING`, abortar y reportar
`state/_summaries/handoff-summary.json#missing`. Si es `READY`, el LLM
consume **solamente** `state/_summaries/handoff-summary.json` +
`state/context-packs-compact/<safe_fqcn>.json` por SUT. Está **prohibido**
re-leer los nueve JSONs originales de las fases 1-7.

Para CADA fase LLM (solo Generation y Repair):

- Listar las precondiciones verificadas (referenciando schemas).
- Mostrar los comandos exactos ejecutados y su salida resumida.
- Persistir el estado correspondiente y validarlo contra su JSON Schema.
- Esperar confirmación humana antes de saltar a la fase siguiente la primera vez; desde el segundo ciclo, avanzar automático salvo que falle un gate.

### Salida por fase

- Resumen de evidencia recolectada.
- Estados creados/actualizados (con path y hash SHA-256).
- Gates evaluados (PASS/FAIL).
- Próxima fase.

### Salida final

Reporte generado **determinísticamente** por `tools/python/cycle_report_builder.py` (ex-`reporting-agent`, migrado a Python — no requiere turno LLM). El archivo queda en `state/_summaries/cycle-<N>-report.json` y contiene:

- cobertura before/after por clase (derivada de XML),
- lista de tests generados con sus `evidence-ids`,
- tests descartados con `reason` (`G1_*`, `G2_*`, `TQG_*`, etc.),
- fixes aplicados (`failure-memory`),
- regresiones (si las hubo),
- riesgos y siguientes pasos.

```bash
python tools/python/cycle_report_builder.py \
  --sut-results state/sut-results.json \
  --coverage-delta state/coverage-delta.json \
  --cycle <N> --mode <coverage|branch-coverage|mutation-hardening> \
  --out state/_summaries/cycle-<N>-report.json
```

---

## Arranque

Empezá por **Phase 0** (auto-detección con `bootstrap.py` o ejecución manual de `run_pipeline.py`). Luego avanzá a **Phase 1 (Discovery)** según el procedimiento.
