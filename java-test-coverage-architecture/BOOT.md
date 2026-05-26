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
  --out          state \
  --module       <module> \
  --include-fqcn '<regex>' \
  --jacoco-xml   <ruta-al-repo-java>/target/site/jacoco/jacoco.xml \
  --coverage-mode <coverage|branch-coverage|mutation-hardening>
```

### Salidas obligatorias

- `state/build-tool-contract.json`
- `state/archetype-profile.json`
- `state/generated-code-index.json`
- `state/import-whitelist.json`
- `state/symbol-contracts/<fqcn>.json` (uno por SUT)
- `state/coverage-targets.json` (si hay `jacoco.xml`)

**Si cualquiera de estos JSON falta o no valida contra su schema ⇒ abortar con `BLOCKED_PRE_STAGE_MISSING`.** Los agentes nunca leen POMs, classpath crudo, `javap` ni `jacoco.xml` directamente: consumen solo los JSON.

> Los `state/*.json` **no se versionan**. El directorio queda con un `.gitkeep` y los esquemas en `state/_schemas/`. `run_pipeline.py` los crea (escritura atómica `*.tmp` + rename) en el primer ciclo. Ver `.gitignore`.

---

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

Ejecutar las fases en orden estricto:

```text
discovery → stack-profile → classification → symbol-contract
        → dependency-graph → fixtures → planning
        → generation (test-intent → test-body)
        → validation → repair → reporting
```

Para CADA fase:

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

Reporte de `reporting-agent` con:

- cobertura before/after por clase (derivada de XML),
- lista de tests generados con sus `evidence-ids`,
- tests descartados con `reason` (`G1_*`, `G2_*`, `TQG_*`, etc.),
- fixes aplicados (`failure-memory`),
- regresiones (si las hubo),
- riesgos y siguientes pasos.

---

## Arranque

Empezá por **Phase 0** (auto-detección con `bootstrap.py` o ejecución manual de `run_pipeline.py`). Luego avanzá a **Phase 1 (Discovery)** según el procedimiento.
