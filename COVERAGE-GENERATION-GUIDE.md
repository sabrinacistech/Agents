# Guía de Generación de Coverage con Agentes LLM

Guía paso a paso para generar tests de cobertura en microservicios Java usando el pipeline determinista + Claude Code como agente LLM.

---

## Índice

1. [Arquitectura general](#1-arquitectura-general)
2. [Prerrequisitos](#2-prerrequisitos)
3. [Estructura del proyecto](#3-estructura-del-proyecto)
4. [Phase 0 — Pipeline determinista](#4-phase-0--pipeline-determinista)
   - [Opción A: Git Bash (start.sh)](#opción-a-git-bash-startsh)
   - [Opción B: PowerShell (run_agents.ps1)](#opción-b-powershell-run_agentsps1)
5. [Interpretar la salida del pipeline](#5-interpretar-la-salida-del-pipeline)
6. [Phase 1+ — Generación LLM con Claude Code](#6-phase-1--generación-llm-con-claude-code)
7. [Qué hace Claude en cada fase](#7-qué-hace-claude-en-cada-fase)
8. [Archivos generados](#8-archivos-generados)
9. [Gates anti-alucinación](#9-gates-anti-alucinación)
10. [Modos de cobertura](#10-modos-de-cobertura)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Arquitectura general

El sistema se divide en dos etapas estrictamente separadas:

```
┌─────────────────────────────────────────────────────┐
│  PHASE 0 — Pipeline Determinista (Python + Maven)   │
│                                                     │
│  pom.xml → bytecode → JaCoCo → state/*.json         │
│  (sin LLM, 100% reproducible)                       │
└─────────────────────────┬───────────────────────────┘
                          │ context-packs/
                          ▼
┌─────────────────────────────────────────────────────┐
│  PHASE 1-10 — Agentes LLM (Claude Code)             │
│                                                     │
│  Lee state/*.json → genera patch descriptors JSON   │
│  → test_patch_applier.py escribe los .java          │
│  → mvn compile/test → repair si falla               │
└─────────────────────────────────────────────────────┘
```

**Principio central**: el agente no inventa símbolos. Cada import, constructor, método o builder que usa debe tener un `evidence-id` verificado en el contrato.

---

## 2. Prerrequisitos

### Software requerido

| Herramienta | Versión mínima | Verificación |
|---|---|---|
| Java JDK | 11+ (21 recomendado) | `java -version` |
| Maven | 3.9+ | `mvn --version` |
| Python | 3.9+ | `python --version` |
| Git | cualquiera | `git --version` |
| Claude Code CLI | última | `claude --version` |

### Variables de entorno

`JAVA_HOME` debe estar configurado y `$JAVA_HOME/bin` en el `PATH` (necesario para `javap`, que hace el escaneo de bytecode).

```powershell
# Verificar en PowerShell
$env:JAVA_HOME
javap -version
```

### Repositorios necesarios

```
C:\repo\Agents\                           ← este repositorio
C:\repo\multi-clusters\<tu-proyecto>\     ← proyecto Java objetivo
```

El proyecto Java debe tener `pom.xml` en su raíz y estar compilado (tener `target/classes/`).

---

## 3. Estructura del proyecto

```
C:\repo\Agents\
├── agents/
│   └── start.sh                          ← Entry point Git Bash
├── run_agents.ps1                        ← Entry point PowerShell
├── java-test-coverage-architecture/
│   ├── BOOT.md                           ← Punto de arranque para el agente LLM
│   ├── MASTER_PROMPT.md                  ← Contrato técnico (gates, schemas)
│   ├── agents/                           ← Prompts de agentes LLM
│   │   ├── coverage-orchestrator.md
│   │   ├── test-intent-agent.md
│   │   ├── test-body-agent.md
│   │   ├── repair-agent.md
│   │   └── reporting-agent.md
│   ├── tools/python/                     ← Pipeline determinista (35 scripts)
│   │   ├── run_pipeline.py               ← Orquestador principal
│   │   ├── bootstrap.py                  ← Auto-detección de parámetros
│   │   ├── test_patch_applier.py         ← Escribe .java desde JSON patches
│   │   ├── test_linter.py                ← Gate G6: validación pre-compile
│   │   └── ...
│   ├── state/_schemas/                   ← JSON Schemas (Draft-07)
│   ├── repair-rules/                     ← Reglas deterministas de reparación
│   └── templates/                        ← Skeletons de clases de test
└── java-test-coverage-architecture_execution_<proyecto>_<fecha>/
    ├── state/                            ← Artefactos JSON producidos
    │   ├── context-packs/               ← Input curado para el LLM
    │   ├── symbol-contracts/            ← Contratos por FQCN
    │   ├── index/                       ← Índice semántico
    │   └── _summaries/                  ← Resúmenes de ciclos
    └── runs/                            ← Archivos de log por ejecución
```

---

## 4. Phase 0 — Pipeline determinista

Esta fase analiza el proyecto Java y produce todos los artefactos JSON que el agente LLM consumirá. **Es obligatoria antes de cualquier fase LLM.**

### Opción A: Git Bash (start.sh)

Desde Git Bash en `C:\repo\Agents`:

```bash
bash agents/start.sh --target=../multi-clusters/<tu-proyecto>
```

**Parámetros disponibles:**

```bash
# Modo básico (detecta todo automáticamente)
bash agents/start.sh --target=../multi-clusters/cluster-status-service

# Con modo de cobertura específico
bash agents/start.sh --target=../multi-clusters/cluster-status-service --coverage-mode=branch-coverage

# Análisis incremental desde un commit
bash agents/start.sh --target=../multi-clusters/cluster-status-service --since=HEAD~1

# Solo un SUT específico
bash agents/start.sh --target=../multi-clusters/cluster-status-service --sut=com.company.service.ClusterStatusService
```

**Modos de cobertura (`--coverage-mode`):**

| Modo | Descripción |
|---|---|
| `coverage` | Maximiza cobertura de líneas (default) |
| `branch-coverage` | Maximiza cobertura de ramas y caminos |
| `mutation-hardening` | Endurece tests con análisis de mutantes PIT |

### Opción B: PowerShell (run_agents.ps1)

Desde PowerShell en `C:\repo\Agents`:

```powershell
# Mínimo (proyecto ya compilado con JaCoCo corrido)
.\run_agents.ps1

# Compilar + correr JaCoCo automáticamente
.\run_agents.ps1 -Repo "C:\repo\multi-clusters\cluster-status-service" -Build -WithJaCoCo

# Con JaCoCo pre-existente
.\run_agents.ps1 `
  -Repo "C:\repo\multi-clusters\cluster-status-service" `
  -JaCoCoXml "C:\repo\multi-clusters\cluster-status-service\target\site\jacoco\jacoco.xml" `
  -CoverageMode coverage

# Análisis incremental
.\run_agents.ps1 -Since HEAD~1

# Generar context-packs compactos (menos tokens para el LLM)
.\run_agents.ps1 -Build -WithJaCoCo -Compact
```

**Parámetros completos de run_agents.ps1:**

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `-Repo` | string | `C:\repo\multi-clusters\cluster-status-service` | Raíz del proyecto Java |
| `-StateDir` | string | `java-test-coverage-architecture\state` | Directorio de salida JSON |
| `-Module` | string | `.` | Nombre del módulo Maven |
| `-Build` | switch | — | Corre `mvn -DskipTests package` antes |
| `-WithJaCoCo` | switch | — | Corre `mvn test` y genera JaCoCo |
| `-JaCoCoXml` | string | — | Ruta a jacoco.xml pre-existente |
| `-Since` | string | — | Git ref para análisis incremental |
| `-Sut` | string | — | Restringe a un único FQCN |
| `-CoverageMode` | string | `coverage` | `coverage`, `branch-coverage`, `mutation-hardening` |
| `-Compact` | switch | — | También escribe packs compactos |
| `-SkipSteps` | string | — | Steps a saltear (ver lista abajo) |

**Steps disponibles para `-SkipSteps`:**
```
pom  archetype  generated  classpath  stack
bytecode  source  jacoco  index  classification
deps  fixtures  planning  incremental  validate  context
```

### Qué hace el pipeline internamente (16 steps)

| Step | Script | Produce |
|---|---|---|
| 1 | `pom_parser.py` | `build-tool-contract.json` |
| 2 | `archetype_detector.py` | `archetype-profile.json` |
| 3 | `generated_code_scanner.py` | `generated-code-index.json` |
| 4 | `classpath_resolver.py` | `import-whitelist.json` |
| 5 | `stack_profile_detector.py` | `stack-profile.json` |
| 6 | `bytecode_scanner.py` | `symbol-contracts/<fqcn>.json` (uno por clase) |
| 7 | `source_symbol_enricher.py` | enriquece contratos con metadata de fuente |
| 8 | `jacoco_parser.py` | `coverage-targets.json` |
| 9 | `semantic_index_writer.py` | `index/{classes,methods,imports,dependencies,annotations}.json` |
| 10 | `classification_analyzer.py` | `classification-index.json` |
| 11 | `dependency_graph_extractor.py` | `dependency-graph.json` |
| 12 | `fixture_catalog_builder.py` | `fixture-catalog.json` |
| 13 | `coverage_planner.py` | `batch-plan.json` |
| 14 | `incremental_map_writer.py` | `incremental-map.json` (solo con `--since`) |
| 15 | `state_validator.py` | valida todos los JSON contra schemas |
| 16 | `context_pack_builder.py` | `context-packs/<fqcn>.json` (input para el LLM) |

---

## 5. Interpretar la salida del pipeline

### Salida exitosa

```
{"tool":"run_pipeline","status":"OK","durationMs":25521,"exitCode":0}
[OK]  Pipeline completado. Revisá .../state/ para los JSON de estado.
```

### Artefactos clave producidos

El directorio de ejecución se crea automáticamente con el formato:
```
java-test-coverage-architecture_execution_<proyecto>_<YYYYMMDD>/
```

Dentro de `state/`:

| Archivo | Significado |
|---|---|
| `batch-plan.json` | Lista priorizada de SUTs a testear (`items=8` significa 8 clases) |
| `context-packs/<fqcn>.json` | Input curado por clase para el agente LLM |
| `coverage-targets.json` | Líneas/ramas sin cobertura según JaCoCo |
| `fixture-catalog.json` | Fixtures y estrategias de instanciación disponibles |
| `classification-index.json` | Tipo de cada clase (controller, service, component, etc.) |
| `dependency-graph.json` | Grafo de dependencias entre clases |

### Interpretar el `batch-plan.json`

```json
{
  "cycle": 2,
  "items": 8,
  "scores": [-25..15],
  "mode": "coverage"
}
```

- `cycle`: número del ciclo actual (incrementa si ya hubo generación previa)
- `items`: cantidad de clases a testear en este ciclo
- `scores`: rango de prioridad (mayor = más urgente)

### Estados `[SKIP]` esperados (no son errores)

Los siguientes `[SKIP]` en la salida son **normales** — esos archivos los produce el LLM en fases posteriores:

```
[SKIP] discovery-summary.json    ← escrito por LLM Discovery agent
[SKIP] execution-state.json      ← escrito por LLM orchestrator
[SKIP] generated-tests.json      ← escrito por LLM Generation agent
[SKIP] failure-memory.json       ← escrito por LLM Repair agent
[SKIP] mutation-intelligence.json← modo mutation-hardening opt-in
[SKIP] compile-error-index.json  ← solo si hay errores de compilación
[SKIP] coverage-summary.json     ← se actualiza después de cada ciclo
[SKIP] coverage-delta.json       ← invocación separada con --mode delta
```

---

## 6. Phase 1+ — Generación LLM con Claude Code

Con el pipeline determinista completo, Claude Code actúa como **Coverage Orchestrator** y genera los tests.

### Paso 1: Abrir Claude Code en VS Code

Desde el terminal integrado de VS Code (o cualquier terminal), posicionado en `C:\repo\Agents`:

```bash
claude
```

O usar el panel lateral de Claude Code si tenés la extensión instalada.

### Paso 2: Iniciar el orchestrator

En el chat de Claude Code, pegá el siguiente prompt ajustando las rutas:

```
Lee y ejecutá @java-test-coverage-architecture/BOOT.md como Coverage Orchestrator.

Phase 0 ya está completa. El estado está en:
  C:\repo\Agents\java-test-coverage-architecture_execution_<proyecto>_<fecha>\state\

Parámetros:
  repo:         C:\repo\multi-clusters\<tu-proyecto>
  module:       <nombre-del-modulo>
  includeFqcn:  ^com\.<tu-groupId>\.
  mode:         coverage
  writeTests:   false
  coverageGoal:
    lines: 0.80

Saltá Phase 0 (ya ejecutada y validada). Arrancá en Phase 1 — Discovery.
```

> **`writeTests: false`** hace que Claude proponga los tests en el chat para revisión antes de escribirlos. Cambiarlo a `true` cuando estés conforme con la calidad.

El símbolo `@` hace que Claude Code lea el archivo directamente del filesystem.

### Paso 3: Confirmar cada fase

La primera vez que corrés un proyecto, Claude pedirá confirmación antes de avanzar entre fases. Desde el segundo ciclo avanza automáticamente salvo que falle un gate.

Para cada fase Claude mostrará:
- Evidencia recolectada
- Estados creados/actualizados (con path y hash SHA-256)
- Gates evaluados (PASS/FAIL)
- Próxima fase

### Paso 4: Revisar y aprobar los tests

Con `writeTests: false`, Claude muestra cada test propuesto en el chat. Podés:

```
# Aprobar y escribir todo
"Todo bien, escribí los tests"

# Aprobar clase por clase
"Aprobá solo ClusterStatusServiceTest, el de LogSanitizerTest necesita revisión"

# Pedir corrección antes de escribir
"El test del servicio no mockea el repository, corregilo"
```

### Paso 5: Activar escritura

Cuando estés conforme:

```
Escribí todos los tests aprobados en src/test/java y corré la compilación
```

Claude ejecuta automáticamente:
1. `test_patch_applier.py` → escribe los `.java` en `src/test/java/`
2. `test_linter.py` → validación pre-compile (gate G6)
3. `mvn compile -Dtest=<TestClass>` → compilación estrecha por clase
4. Si falla → repair-agent → nuevo intento
5. `mvn test -Dtest=<TestClass>` → ejecución

### Paso 6: Reporte final

Al terminar, el `reporting-agent` emite un reporte con:

```
- Cobertura before/after por clase (derivada de JaCoCo XML)
- Lista de tests generados con evidence-ids
- Tests descartados (con razón: G1_IMPORT, G2_NO_EVIDENCE, etc.)
- Reparaciones aplicadas (failure-memory)
- Regresiones detectadas
- Recomendaciones para el próximo ciclo
```

---

## 7. Qué hace Claude en cada fase

| Fase | Qué hace Claude | Lee | Escribe |
|---|---|---|---|
| 1. Discovery | Consolida clasificación, dependencias, contratos, stack | `context-packs/`, `classification-index.json`, `dependency-graph.json` | `discovery-summary.json` |
| 2. Stack Profile | Ya en `state/stack-profile.json` | `stack-profile.json` | — |
| 3. Classification | Ya en `state/classification-index.json` | `classification-index.json` | — |
| 4. Symbol Contract | Ya en `state/symbol-contracts/` | `symbol-contracts/<fqcn>.json` | — |
| 5. Fixtures | Ya en `state/fixture-catalog.json` | `fixture-catalog.json` | — |
| 6. Planning | Ya en `state/batch-plan.json` | `batch-plan.json` | `execution-state.json` |
| 7. Test Intent | Planifica casos de test por SUT | `context-packs/<fqcn>.json` | `state/_patches/intent-<tc>.json` |
| 8. Test Body | Genera patch descriptor JSON (no Java) | context-pack + intent | `state/_patches/<TestClass>.patch.json` |
| 9. Validation | Aplica patches, compila, ejecuta | `_patches/*.patch.json` | `.java` en `src/test/java/` |
| 10. Repair | Corrige errores (determinista primero, LLM si escala) | `compile-error-index.json` | `_patches/repair-<TestClass>.patch.json` |
| 11. Reporting | Consolida resultados y delta de cobertura | `coverage-delta.json`, todos los resultados | `_summaries/cycle-N.json` |

### Flujo de generación de un test

```
context-pack/<Fqcn>.json
        │
        ▼
test-intent-agent
  → planifica casos de test (JSON intent, no Java)
        │
        ▼
test-body-agent
  → genera patch descriptor JSON con methods[], fields[], imports[]
        │
        ▼
state/_patches/<TestClass>.patch.json
        │
        ▼
test_patch_applier.py
  → escribe src/test/java/.../<TestClass>.java
        │
        ▼
test_linter.py  (gate G6)
  → detecta imports inválidos, símbolos sin evidence-id
        │
        ├── FAIL → descarta sin compilar
        └── PASS
              │
              ▼
mvn compile -Dtest=<TestClass>
              │
              ├── FAIL → compile_error_parser.py → repair-agent → retry
              └── PASS
                    │
                    ▼
mvn test -Dtest=<TestClass>
                    │
                    └── generated-tests.json (status: VALIDATED)
```

---

## 8. Archivos generados

### Durante el pipeline (Phase 0)

```
state/
├── build-tool-contract.json      ← versión Java, groupId, módulo
├── archetype-profile.json        ← BGBA parent, javax vs jakarta, JUnit 4 vs 5
├── generated-code-index.json     ← clases excluidas (Lombok, MapStruct, etc.)
├── import-whitelist.json         ← imports permitidos (del classpath real)
├── stack-profile.json            ← frameworks detectados con versiones
├── symbol-contracts/
│   └── com.company.Foo.json      ← contratos por FQCN (constructores, métodos, builders)
├── coverage-targets.json         ← líneas/ramas sin cobertura según JaCoCo
├── index/
│   ├── classes.json              ← FQCN → {kind, modifiers, annotations, parents}
│   ├── methods.json              ← FQCN → [{name, params, returnType, evidenceId}]
│   ├── imports.json              ← paquetes y clases del classpath
│   ├── dependencies.json         ← grafo de dependencias
│   └── annotations.json         ← anotaciones por clase y método
├── classification-index.json     ← component=6, controller=1, service=2, etc.
├── dependency-graph.json         ← suts, dependencias, clientes externos
├── fixture-catalog.json          ← estrategias de instanciación (constructor, mock)
├── batch-plan.json               ← lista priorizada de SUTs a testear
└── context-packs/
    └── com.company.Foo.json      ← input curado para el LLM (por SUT)
```

### Durante la fase LLM

```
state/
├── execution-state.json          ← estado del ciclo actual, checkpoints
├── _patches/
│   ├── FooTest.patch.json        ← patch descriptor (generado por test-body-agent)
│   └── repair-FooTest.patch.json ← patch de reparación
├── generated-tests.json          ← metadata de tests aplicados
├── failure-memory.json           ← historial de intentos de reparación por SUT
├── coverage-summary.json         ← cobertura después del ciclo LLM
├── coverage-delta.json           ← delta respecto al baseline
└── _summaries/
    ├── cycle-1.json              ← resumen compacto del ciclo
    └── last-failure.json         ← detalle del último gate que falló
```

### Tests escritos en el proyecto Java

```
<tu-proyecto>/src/test/java/
└── com/company/
    ├── FooServiceTest.java       ← generado por test_patch_applier.py
    ├── BarControllerTest.java
    └── ...
```

---

## 9. Gates anti-alucinación

El sistema tiene 9 gates que bloquean el avance si detectan contenido inválido:

| Gate | Qué detecta | Acción |
|---|---|---|
| **G1** | Import fuera de `import-whitelist.json` | Descarta el test sin compilar |
| **G2** | Símbolo sin `evidence-id` en el contrato | BLOCKED — no genera |
| **G3** | Contratos derivados de regex (no bytecode/AST) | Fuerza re-análisis |
| **G4** | Código autogenerado no indexado | Excluye del universo SUT |
| **G5** | Generación sin `stack-profile.json` válido | BLOCKED_PRE_STAGE_MISSING |
| **G6** | Violaciones detectadas por `test_linter.py` | Descarta antes de `javac` |
| **G7** | Re-aplicación de fix ya fallido | BLOCKED (anti-loop) |
| **G8** | Delta de cobertura = 0 por 2 ciclos consecutivos | Para el ciclo |
| **G9** | `javac` falla después de N intentos de reparación | Escala a revisión humana |

---

## 10. Modos de cobertura

### `coverage` (default)

Maximiza líneas cubiertas. Prioriza clases con menor cobertura actual.

```bash
bash agents/start.sh --target=../mi-proyecto
# o
bash agents/start.sh --target=../mi-proyecto --coverage-mode=coverage
```

### `branch-coverage`

Maximiza cobertura de ramas (if/else, switch, ternario). Genera casos adicionales para cada camino lógico.

```bash
bash agents/start.sh --target=../mi-proyecto --coverage-mode=branch-coverage
```

### `mutation-hardening`

Corre PIT mutation testing, detecta mutantes sobrevivientes y genera tests que los maten. Requiere el plugin `pitest-maven` en el `pom.xml`.

```bash
bash agents/start.sh --target=../mi-proyecto --coverage-mode=mutation-hardening
```

---

## 11. Troubleshooting

### El pipeline falla en el step de bytecode (`bytecode_scanner.py`)

**Causa:** `javap` no está en el PATH.

```powershell
# Verificar
javap -version

# Solución: agregar JAVA_HOME\bin al PATH
$env:PATH += ";$env:JAVA_HOME\bin"
```

### `[ERR] state/semantic-index.json — missing`

**Causa:** versión antigua de `state_validator.py`. Ya corregido — `semantic-index.schema.json` es un schema de definiciones para `state/index/`, no un archivo de estado directo.

### El pipeline termina con `BLOCKED_PRE_STAGE_MISSING`

**Causa:** faltan artefactos obligatorios de Phase 0.

```bash
# Verificar cuál falta
cat state/_summaries/last-failure.json

# Rerrer el pipeline completo
bash agents/start.sh --target=../mi-proyecto
```

### Claude genera un test con un import que no existe

El gate G1 lo bloqueará automáticamente. Si aparece en el chat como propuesta, responder:

```
Ese import no está en import-whitelist.json. Descartalo y revisá el context-pack.
```

### Error de compilación después de aplicar el test

Claude activa el `repair-agent` automáticamente. Si falla más de 2 veces con el mismo error, reporta `BLOCKED` y escala a revisión humana. Podés guiar la reparación:

```
El error es que ClusterStatusRepository es una interfaz, no se puede instanciar directamente. 
Usá @MockBean en lugar de new.
```

### Los tests compilan pero fallan en runtime

Verificar que el `application.properties` de test tenga la configuración necesaria. El `stack-profile.json` indica si el proyecto usa `@SpringBootTest` (contexto completo) o `@WebMvcTest` (slice).

### El pipeline tarda más de lo esperado

- Verificar que `target/classes/` exista (el proyecto está compilado)
- No correr `mvn clean` entre ciclos — invalida el caché de bytecode
- Usar `--sut <FQCN>` para analizar solo la clase que necesitás

### Ver el log completo de una ejecución

```bash
# Logs de la última ejecución
ls java-test-coverage-architecture_execution_<proyecto>_<fecha>/runs/

# Log de Maven compile
cat java-test-coverage-architecture_execution_.../runs/<timestamp>/mvn-package.log

# Log del pipeline Python
cat java-test-coverage-architecture_execution_.../runs/<timestamp>/bootstrap.log
```

---

## Referencia rápida

```bash
# Ejecución completa mínima (Git Bash)
bash agents/start.sh --target=../multi-clusters/cluster-status-service

# Ejecución completa mínima (PowerShell)
.\run_agents.ps1 -Repo "C:\repo\multi-clusters\cluster-status-service" -Build -WithJaCoCo

# Iniciar el agente LLM (desde Claude Code)
# Pegar en el chat:
#   Lee @java-test-coverage-architecture/BOOT.md como Coverage Orchestrator.
#   Phase 0 completa. Estado en: C:\repo\Agents\java-test-coverage-architecture_execution_...\state\
#   mode: coverage | writeTests: false | Arrancá en Phase 1 — Discovery.

# Validar el estado manualmente
.venv/Scripts/python.exe java-test-coverage-architecture/tools/python/state_validator.py \
  --state java-test-coverage-architecture_execution_<proyecto>_<fecha>/state

# Aplicar un patch manualmente
.venv/Scripts/python.exe java-test-coverage-architecture/tools/python/test_patch_applier.py \
  --patch state/_patches/FooServiceTest.patch.json \
  --repo C:\repo\multi-clusters\<tu-proyecto>

# Correr linter sobre un test generado
.venv/Scripts/python.exe java-test-coverage-architecture/tools/python/test_linter.py \
  --file C:\repo\multi-clusters\<tu-proyecto>\src\test\java\...\FooServiceTest.java \
  --state java-test-coverage-architecture_execution_.../state
```
