# Correcciones Implementadas

Historial de correcciones aplicadas a la arquitectura `java-test-coverage-architecture`.

---

## Partes A.1, A.2, A.3 — Infraestructura determinista del pipeline

**Fecha:** 2026-05-26  
**Alcance:** `tools/python/stack_profile_detector.py` (nuevo), `tools/python/classification_analyzer.py` (nuevo), `tools/python/run_pipeline.py` (actualizado)

### A.1 — `stack_profile_detector.py`

**Objetivo:** detectar el stack de testing del proyecto Java de forma totalmente determinista
a partir de los `pom.xml` — sin LLM, sin red, sin suposiciones.

**Detecta por módulo Maven:**

| Campo | Qué detecta |
|-------|-------------|
| `test.framework` | JUnit 5 (artifactIds: `junit-jupiter*`, `junit-platform*`, `junit-vintage-engine`) o JUnit 4 (`junit:junit`) |
| `test.version` | versión de JUnit |
| `mock.framework` | Mockito (`mockito-core`, `mockito-junit-jupiter`) |
| `mock.features` | `mockito-inline` (artifactId explícito) · `powermock` (cualquier `powermock-*`) |
| `assert.framework` | AssertJ (`assertj-core`) → Hamcrest (`hamcrest-*`) → `junit-builtin` |
| `di.spring` | `spring-test` o `spring-boot-starter-test` |
| `di.springBoot` | versión de Spring Boot (del parent POM) |
| `testcontainers` | cualquier `org.testcontainers:*` |
| `annotationProcessors` | Lombok, FreeBuilder, MapStruct, Immutables, AutoValue |
| `namespace` | `jakarta` si Spring Boot ≥ 3, `javax` si < 3, `unknown` si indeterminado |

**Herencia:** cada módulo hereda del root POM los ajustes que no define localmente.

**`spring-boot-starter-test`:** implica automáticamente JUnit 5, Mockito y AssertJ.

**Actualización de schema:** agrega retrocompatiblemente `namespace` y `testcontainers`
al objeto de módulo en `state/_schemas/stack-profile.schema.json` si están ausentes.

**Presets:** genera `presets.imports.allowed` / `presets.imports.forbidden` según namespace.

```bash
python tools/python/stack_profile_detector.py --repo <repo-java> --out state
```

### A.2 — `classification_analyzer.py`

**Objetivo:** clasificar clases Java sin LLM usando reglas estáticas sobre anotaciones y metadatos.

**Fuentes de entrada (en orden de preferencia):**
1. `state/index/classes.json` + `state/index/annotations.json` (post `semantic_index_writer`)
2. `state/symbol-contracts/*.json` directamente (fallback si el índice está vacío)
3. `state/generated-code-index.json` — exclusiones
4. `state/coverage-targets.json` — datos de cobertura (opcional)

**Reglas de clasificación (por prioridad):**

| Prioridad | Condición | Tipo asignado |
|-----------|-----------|---------------|
| 1 | FQCN en `excludedFqcns` / `excludedPackages` | `generated/excluded` |
| 2 | `@RestController`, `@Controller`, `@ControllerAdvice`, `@FeignClient` | `controller` |
| 3 | `@Service` | `service` |
| 4 | `@Repository` | `repository` |
| 5 | `@Component` | `component` |
| 6 | `@Configuration`, `@SpringBootApplication` | `configuration` |
| 7 | `@Mapper` | `mapper` |
| 8 | `kind=interface` o modificador `abstract` | `non-instantiable` |
| 9 | `kind=record` | `data-carrier` |
| 10 | `kind=enum` | `enum` |
| 11 | Sufijo del nombre (`Controller`, `Service`, `Repository`, etc.) | según sufijo |
| 12 | Ninguna regla aplicó | `component` |

**Clases de test** (sufijo `Test`, `Tests`, `IT`, `Spec`) son ignoradas — no son SUTs.

**Métricas deterministas por clase:**

| Métrica | Valores | Ejemplo |
|---------|---------|---------|
| `testabilityRisk` | low · medium · high | `controller` → medium, `configuration` → high |
| `coverageValue` | low · medium · high | `service` → high, `data-carrier` → low |
| `recommendedTemplate` | path o null | `controller` → `templates/webmvc-test.java` |
| `reasons` | array de strings | `["@Service annotation detected"]` |

**Schema:** actualiza retrocompatiblemente `state/_schemas/classification-index.schema.json`
para incluir todos los tipos nuevos y los campos de métricas.

```bash
python tools/python/classification_analyzer.py --out state
python tools/python/classification_analyzer.py --out state --contracts state/symbol-contracts
```

### A.3 — `run_pipeline.py` actualizado

**Nuevo orden del pipeline (12 pasos):**

```
 1. pom_parser              → state/build-tool-contract.json
 2. archetype_detector      → state/archetype-profile.json
 3. generated_code_scanner  → state/generated-code-index.json
 4. classpath_resolver      → state/import-whitelist.json
 5. stack_profile_detector  → state/stack-profile.json          ← NUEVO
 6. bytecode_scanner        → state/symbol-contracts/<fqcn>.json (si --module)
 7. source_symbol_enricher  → enriquece contratos
 8. jacoco_parser           → state/coverage-targets.json        (si --jacoco-xml)
 9. semantic_index_writer   → state/index/
10. classification_analyzer → state/classification-index.json    ← NUEVO
11. incremental_map_writer  → state/incremental-map.json         (si --since)
12. state_validator         → valida todo
```

**Nuevas opciones `--skip`:** `stack` y `classification`

### Validación

```
python -m py_compile tools/python/stack_profile_detector.py
                     tools/python/classification_analyzer.py
                     tools/python/run_pipeline.py
→ ALL SYNTAX OK

python tools/python/state_validator.py --state state
→ 19 × [OK], exit 0  (ninguna regresión de schema)
```

---

## Mejora 3 — Corrección y refuerzo de `.github/copilot-instructions.md`

**Fecha:** 2026-05-26  
**Alcance:** `.github/copilot-instructions.md`, `docs/vscode-copilot-execution-guide.md`

### Problemas corregidos

#### 1. Comando del linter incorrecto

**Antes:**
```bash
python tools/python/test_linter.py --file <path/to/TestFile.java> \
  --whitelist state/import-whitelist.json \
  --contracts state/symbol-contracts/
```

**Después:**
```bash
python tools/python/test_linter.py \
  --test-file <path/to/TestFile.java> \
  --whitelist state/import-whitelist.json \
  --contracts state/symbol-contracts/ \
  --stack-profile state/stack-profile.json
```

`--file` no existe en `test_linter.py` (el argumento real es `--test-file`).  
`--stack-profile` es el objetivo arquitectónico para G5; incluye NOTE indicando que
la implementación en `test_linter.py` es una mejora pendiente (mejora 9).

#### 2. "AST linter" → "static pre-compile linter"

`test_linter.py` usa regex, no un AST real. Eliminada toda referencia a "AST linter":
- Sección "REQUIRED BEFORE ACCEPTING A SUGGESTION"
- Gate G6 en la tabla de referencia
- Pie de página del documento

#### 3. Reglas FreeBuilder explícitas

Agregadas reglas que antes estaban implícitas o ausentes:

| Prohibición | Razón |
|-------------|-------|
| `new TypeName_Builder()` | Clase generada interna; no debe usarse directamente |
| `new TypeName_Builder(...)` | Ídem |
| Setters inventados (`.setPersonCommonData(...)`, etc.) | Solo los de `builders[].setters[]` del contrato son válidos |

La única forma permitida de FreeBuilder: `new TypeName.Builder()` y solo si el contrato lo confirma.

#### 4. Reglas de framework según `state/stack-profile.json` (G5)

Tabla explícita agregada con 8 combinaciones:

| Framework / feature | Condición en stack-profile.json |
|---------------------|----------------------------------|
| JUnit 5 (`org.junit.jupiter.*`) | JUnit 5 declarado |
| JUnit 4 (`org.junit.*`) | JUnit 4 declarado |
| `@Mock`, `MockitoExtension` | Mockito disponible |
| `Mockito.mockStatic(...)` | `mockito-inline` disponible |
| PowerMock | PowerMock disponible |
| `@SpringBootTest` | Spring Test disponible |
| `javax.*` | Namespace `javax` (no `jakarta`) |
| `jakarta.*` | Namespace `jakarta` (no `javax`) |
| AssertJ / Hamcrest | Listado como dependencia permitida |

#### 5. Aclaración de `state/symbol-contracts.json` como manifest

Agregado en la tabla "WHERE TO LOOK FOR VALID SYMBOLS":

> `state/symbol-contracts.json` ← manifest only; no method defs

Y en la regla 2: aclaración explícita de que los contratos reales están en
`state/symbol-contracts/<fqcn>.json`, no en el manifest.

#### 6. `state/stack-profile.json` en la tabla de lookup

Agregada la fila:

| Available frameworks | `state/stack-profile.json` → declared deps, `presets` |

#### 7. Sección "CORRECTIVE PATTERNS" ampliada

Se añadieron tres patrones nuevos documentados con ✅/❌:
- Import no whitelisted
- FreeBuilder `_Builder` vs `.Builder()`
- Setter inventado
- Framework no disponible en el stack

### Validación

Todos los criterios de aceptación verificados programáticamente:

| Criterio | Resultado |
|----------|-----------|
| No contiene `--file <path` | ✅ 0 matches |
| No contiene `AST linter` | ✅ 0 matches |
| No contiene `symbol-contract.json` (singular) | ✅ 0 matches |
| Contiene `--test-file` | ✅ 2 matches |
| Contiene `--stack-profile state/stack-profile.json` | ✅ 1 match |
| Contiene `symbol-contracts/<fqcn>.json` | ✅ 11 matches |
| Contiene `manifest` | ✅ 2 matches |
| Contiene `static pre-compile linter` | ✅ 2 matches |
| Contiene `stack-profile.json` (regla G5) | ✅ 11 matches |
| Contiene `_Builder` (prohibición) | ✅ 5 matches |
| G6 con "pre-compile linter passes before compile" | ✅ 1 match |
| `builders[].setters[]` (setters rule) | ✅ 5 matches |
| `mockito-inline` (mock inline rule) | ✅ 2 matches |
| `javax`/`jakarta` rule | ✅ 3 matches |

### Pendientes detectados

- **Mejora 9 pendiente:** `test_linter.py` no implementa aún `--stack-profile`.
  Debe agregarse para que G5 (stack profile declared) sea validado en tiempo de lint.
  Hasta entonces, el flag está documentado como objetivo y el NOTE indica cómo
  ejecutar sin él temporalmente.

---

## Corrección 3 (anterior) — Distinción entre [SKIP] legítimo y [ERR] por ausencia requerida

**Fecha:** 2026-05-26  
**Alcance:** `tools/python/state_validator.py`

### Problema

`validate_standard_schemas()` trataba **cualquier** archivo de estado ausente como
`[SKIP] <name>.json missing (generated at runtime by pipeline)`, sin distinción.
Esto ocultaba fallos reales: si el pipeline Python no producía `import-whitelist.json`
(por ejemplo, por un error en `classpath_resolver.py`), el validador lo ignoraba
silenciosamente en lugar de fallar.

### Solución: `_RUNTIME_OPTIONAL` dict

Se introdujo un diccionario `_RUNTIME_OPTIONAL` que mapea cada nombre de schema a la
razón por la que su archivo puede estar ausente legítimamente:

```python
_RUNTIME_OPTIONAL: dict[str, str] = {
    # Escritos por agentes LLM (fase posterior al pipeline Python)
    "batch-plan":            "written by LLM Planning agent",
    "classification-index":  "written by LLM Classification agent",
    "compile-error-index":   "written by compile_error_parser when compilation fails",
    "coverage-summary":      "written by jacoco_parser after a JaCoCo run",
    "coverage-delta":        "written by jacoco_parser --mode delta (separate invocation)",
    "dependency-graph":      "written by LLM Dependency Graph agent",
    "discovery-summary":     "written by LLM Discovery agent",
    "execution-state":       "written by LLM orchestrator",
    "failure-memory":        "written by LLM Repair agent across cycles",
    "fixture-catalog":       "written by LLM Fixture agent",
    "generated-tests":       "written by LLM Generation agent",
    "mutation-intelligence": "written by LLM Mutation agent",
    "stack-profile":         "written by LLM Stack Profile agent",
    # Escritos condicionalmente por el pipeline Python
    "coverage-targets":      "requires --jacoco-xml flag",
    "incremental-map":       "requires --since flag",
}
```

**Archivos ausentes en `_RUNTIME_OPTIONAL`** → `[SKIP] <name>.json — <motivo>`  
**Archivos ausentes fuera del dict** → `[ERR]  state/<name>.json — missing; must be produced by the Python pipeline` + exit 1

### Archivos requeridos (no están en `_RUNTIME_OPTIONAL`)

| Archivo | Escrito por | Step |
|---------|-------------|------|
| `build-tool-contract.json` | `pom_parser.py` | Step 1 |
| `archetype-profile.json` | `archetype_detector.py` | Step 2 |
| `generated-code-index.json` | `generated_code_scanner.py` | Step 3 |
| `import-whitelist.json` | `classpath_resolver.py` | Step 4 |

### Resultados de validación

**Test A — repo completo (todos los archivos presentes):**
```
python tools/python/state_validator.py --state state
# 19 × [OK], 0 × [SKIP], EXIT CODE: 0
```

**Test B — post-pipeline Python (solo 4 obligatorios presentes):**
```
# Solo: build-tool-contract, archetype-profile, generated-code-index, import-whitelist
python tools/python/state_validator.py --state /tmp/test-state-dir
# 4 × [OK], 15 × [SKIP] con motivo específico, EXIT CODE: 0
```

**Test C — falta un archivo obligatorio (`import-whitelist.json`):**
```
rm /tmp/test-state-dir/import-whitelist.json
python tools/python/state_validator.py --state /tmp/test-state-dir
# [ERR]  state/import-whitelist.json — missing; must be produced by the Python pipeline
# EXIT CODE: 1
```

---

## Correcciones 1 y 2 — Validación de estados y symbol contracts

**Fecha:** 2026-05-25  
**Alcance:** `state/*.json`, `state/_schemas/*.schema.json`, `tools/python/state_validator.py`

---

### Corrección 1 — Cobertura completa de schemas y archivos de estado

**Problema:** Varios archivos `state/*.json` no tenían schema asociado en `state/_schemas/`, y otros
schemas referenciaban archivos que no existían, provocando `[SKIP]` o comportamiento ambiguo.

**Cambios realizados:**

#### Schemas nuevos creados (`state/_schemas/`)

| Schema | Archivo de estado validado | Notas |
|--------|---------------------------|-------|
| `coverage-summary.schema.json` | `state/coverage-summary.json` | `lineCoverage`/`branchCoverage` como `number\|null` |
| `discovery-summary.schema.json` | `state/discovery-summary.json` | Soporta tanto top-level como per-module `sourceRoots` |
| `generated-tests.schema.json` | `state/generated-tests.json` | `status` enum: PROPOSED/VALIDATED/DISCARDED/COMMITTED |

#### Archivos de estado nuevos creados (`state/`)

| Archivo | Motivo | Contenido inicial |
|---------|--------|-------------------|
| `state/archetype-profile.json` | Referenciado en agents pero no existía | `{"schemaVersion": 1, "modules": []}` |
| `state/generated-code-index.json` | Schema existía sin archivo | `{"schemaVersion": 1, "module": "", "generators": [], ...}` |
| `state/import-whitelist.json` | Schema existía sin archivo (gate G1) | `{"schemaVersion": 1, "module": "", "packages": [], "classes": []}` |

#### Archivos de estado actualizados (`state/`)

| Archivo | Corrección |
|---------|-----------|
| `state/coverage-summary.json` | Añadido `"schemaVersion": 1` |
| `state/discovery-summary.json` | Añadido `"schemaVersion": 1` y `"root": "."` |
| `state/generated-tests.json` | Añadido `"schemaVersion": 1` |

#### Archivos auxiliares sin schema (documentados como `[INFO]`)

Los siguientes archivos `state/*.json` no tienen schema porque son estado auxiliar gestionado
internamente por el pipeline — se reportan con `[INFO]` (no error):

- `state/module-progress.json` — progreso por módulo, escrito por `run_pipeline.py`
- `state/symbol-contracts.json` — manifest del directorio `symbol-contracts/`
- `state/telemetry.json` — métricas de ejecución internas

---

### Corrección 2 — Reescritura de `tools/python/state_validator.py`

**Problema original:**
1. Solo aceptaba `--state`; la documentación referenciaba `--state-dir`.
2. `symbol-contract.schema.json` intentaba validar `state/symbol-contract.json` (no existe);
   debía validar `state/symbol-contracts/*.json` (un archivo por FQCN).
3. Los archivos sin schema no generaban ninguna salida (silencio ambiguo).
4. Formato de salida inconsistente.

**Solución implementada:**

#### Argumento dual `--state` / `--state-dir`

```python
ap.add_argument("--state",    default=None)
ap.add_argument("--state-dir", dest="state_dir", default=None)
# --state-dir tiene prioridad; si ambos se pasan, se emite [WARN]
```

#### `_SPECIAL_SCHEMAS` — excepción para `symbol-contract`

```python
_SPECIAL_SCHEMAS: frozenset[str] = frozenset({"symbol-contract"})
```

El schema `symbol-contract.schema.json` no se mapea a `state/symbol-contract.json`.
En su lugar, `validate_symbol_contracts()` itera `state/symbol-contracts/*.json`.

#### `validate_symbol_contracts()` — validación del directorio

- Directorio inexistente → `[INFO] ... not found; skipping`
- Directorio vacío → `[INFO] ... has no contract files yet`
- Cada archivo válido → `[OK]   state/symbol-contracts/<fqcn>.json`
- Cada archivo inválido → `[ERR]` con path del schema y razón detallada
- Exit code 1 si al menos un contrato es inválido

#### `report_auxiliary_files()` — archivos sin schema

Detecta automáticamente todo `state/*.json` que no tenga un `*.schema.json` correspondiente
y emite `[INFO] state/<file>.json has no schema; treated as auxiliary state`.

#### Formato de salida estandarizado

| Prefijo | Significado |
|---------|-------------|
| `[OK]   state/<file>.json` | Archivo válido contra su schema |
| `[SKIP] <name>.json missing (generated at runtime by pipeline)` | Schema existe pero el archivo se genera en runtime |
| `[INFO] ...` | Auxiliar sin schema, directorio vacío, o condición no bloqueante |
| `[ERR]  state/<file>.json` | Inválido — incluye path del schema y razón |
| `[WARN] ...` | Advertencia no bloqueante (ej: ambos `--state` y `--state-dir`) |
| `[FAIL] ...` | Error fatal (directorio no encontrado, dependencia faltante) |

---

### Resultados de validación

#### Test 1 — Compilación sintáctica

```
python -m py_compile tools/python/state_validator.py
# → Syntax OK (sin salida = éxito)
```

#### Test 2 — `--state state`

```
python tools/python/state_validator.py --state state
```

```
[OK]   state/archetype-profile.json
[OK]   state/batch-plan.json
[OK]   state/build-tool-contract.json
[OK]   state/classification-index.json
[OK]   state/compile-error-index.json
[OK]   state/coverage-delta.json
[OK]   state/coverage-summary.json
[OK]   state/coverage-targets.json
[OK]   state/dependency-graph.json
[OK]   state/discovery-summary.json
[OK]   state/execution-state.json
[OK]   state/failure-memory.json
[OK]   state/fixture-catalog.json
[OK]   state/generated-code-index.json
[OK]   state/generated-tests.json
[OK]   state/import-whitelist.json
[OK]   state/incremental-map.json
[OK]   state/mutation-intelligence.json
[OK]   state/stack-profile.json
[INFO] state/symbol-contracts/ has no contract files yet
[INFO] state/module-progress.json has no schema; treated as auxiliary state
[INFO] state/symbol-contracts.json has no schema; treated as auxiliary state
[INFO] state/telemetry.json has no schema; treated as auxiliary state
EXIT CODE: 0
```

19 schemas validados correctamente. Sin `[SKIP]` injustificados. Sin `[ERR]`.

#### Test 3 — `--state-dir state` (alias)

```
python tools/python/state_validator.py --state-dir state
```

Salida idéntica al Test 2. EXIT CODE: 0.

#### Test 4 — Validación negativa (contrato inválido)

```bash
# Crear contrato inválido (falta campo obligatorio 'fqcn')
echo '{"schemaVersion": 1}' > state/symbol-contracts/Invalid.json
python tools/python/state_validator.py --state state
```

```
[ERR]  state/symbol-contracts/Invalid.json
       schema: state/_schemas/symbol-contract.schema.json
       reason: 'fqcn' is a required property
[OK]   state/archetype-profile.json
...
EXIT CODE: 1
```

```bash
# Eliminar el archivo inválido → vuelve a pasar
rm state/symbol-contracts/Invalid.json
python tools/python/state_validator.py --state state
# EXIT CODE: 0
```

---

### Criterios de aceptación — verificados ✓

| # | Criterio | Estado |
|---|----------|--------|
| 1 | `--state state` pasa sin errores | ✓ EXIT 0 |
| 2 | `--state-dir state` pasa sin errores | ✓ EXIT 0 |
| 3 | No más `[SKIP] symbol-contract.json missing` | ✓ Eliminado |
| 4 | `symbol-contracts/` vacío → mensaje informativo, sin error | ✓ `[INFO]` |
| 5 | `Invalid.json` con `{"schemaVersion":1}` → detectado y falla | ✓ EXIT 1 |
| 6 | `archetype-profile`, `generated-code-index`, `import-whitelist` tienen schema y archivo | ✓ Todos `[OK]` |
| 7 | Archivos sin schema tratados como auxiliares | ✓ `[INFO]` |

---

## Correcciones anteriores (Sesión 2)

### Bugs críticos en Python

- **`cycle_summarizer.py`** — `_extract_coverage_delta()` siempre retornaba 0; corregido para
  leer la ruta correcta `totals.lines.delta` desde `coverage-delta.json`.

- **`semantic_index_writer.py`** — `build_dependencies_index()` solo leía formato legacy
  (`classes: {}`); los agentes LLM escriben formato schema-canonical (`graphs: []`).
  Corregido para soportar ambos formatos.

### Bugs en `bytecode_scanner.py`

- `DESC_RE.match(nxt)` era invocado dos veces (en el `if` y para `.group(1)`).
  Corregido guardando el resultado en `desc_match`.

### Estado `state/*.json` — 12 archivos corregidos

Todos los archivos de estado fueron corregidos para validar contra sus schemas. Detalles en el
historial de commits.

### Documentación

- `tools/python/README.md` — reemplazada referencia a `freebuilder_scanner.py` (no existe)
  por `source_symbol_enricher.py`; añadidos los 15 scripts reales.
- `MASTER_PROMPT.md` — añadida documentación de modo standalone vs embedded.
- `skills/08-validation/build-tool-adapter.md` — Gradle explícitamente marcado como NO soportado;
  código de abort: `BLOCKED_GRADLE_NOT_SUPPORTED_IN_PIPELINE`.

---

## Correcciones anteriores (Sesión 1)

### Bugs en Python

- **`bytecode_scanner.py`** — `from datetime import datetime, timezone` movido a top-level;
  doble llamada a `DESC_RE.match()` corregida.
- **`incremental_map_writer.py`** — `import hashlib` movido a top-level.
- **`stacktrace.py`** — `import os` movido a top-level.
- **`jacoco_parser.py`** — variable muerta `cxty` eliminada; comentario contradictorio eliminado.
- **`source_symbol_enricher.py`** — `annotations.add(ann); changed = True` separado en dos líneas.

### Schema nuevo

- **`state/_schemas/incremental-map.schema.json`** — creado (estaba referenciado en
  `incremental_map_writer.py` como `"$schemaRef"` pero el archivo no existía).
