# Java Test Coverage Agent Architecture

Arquitectura de agentes y skills para generar tests unitarios en microservicios Java con **cero invención de paquetes/clases**, soportando Java 8+, Maven/Gradle, JUnit 4/5, Mockito, AssertJ, JaCoCo y proyectos con FreeBuilder/Lombok/MapStruct/Immutables/AutoValue.

## Principio central

> El agente no inventa símbolos. Solo puede usar clases, imports, constructores, métodos, builders, fixtures y comandos verificados con `evidence-id`. Si no hay evidencia, no se genera el test.

## Flujo

```text
discovery → stack-profile → classification → symbol-contract
        → dependency-graph → fixtures → planning → generation
        → validation → repair → reporting
```

## Estructura

```text
agents/              Agentes por fase (incluye stack-profile-agent y mutation-agent)
skills/              Procedimientos accionables por dominio
state/               Estados JSON persistentes
state/_schemas/      JSON Schemas Draft-07 (validación obligatoria)
docs/                Notas de arquitectura y políticas
tools/python/        Pre-stage determinista (parsea POM/classpath/javap/JaCoCo)
MASTER_PROMPT.md     Prompt principal con gates G1–G8
```

## Pre-stage Python (obligatorio)

Antes de cualquier ciclo LLM, correr el pipeline determinista que produce todos los `state/*.json`. Esto **reduce drásticamente los tokens** consumidos y acelera la generación (ver [`docs/performance-tuning.md`](docs/performance-tuning.md) y [`docs/python-pipeline.md`](docs/python-pipeline.md)).

```bash
mvn -q -DskipTests package
python tools/python/run_pipeline.py \
   --repo . \
   --out docs/agents/java-test-coverage-architecture/state \
   --module <module> \
   --include-fqcn '^com\.acme\.' \
   --jacoco-xml target/site/jacoco/jacoco.xml
```

## BGBA archetypes

Detección automática de `bgba-parent-pom`, `bgba-parent-paas-java-8` y `bgba-parent-paas-java-21` con reglas derivadas (`javax` vs `jakarta`, JaCoCo heredado vs manual, JUnit 4 vs 5). Ver [`docs/archetype-policy.md`](docs/archetype-policy.md) y la skill [`archetype-detection`](skills/01-discovery/archetype-detection.md).

## Código autogenerado

CXF (`wsdl2java`), OpenAPI Generator, Lombok, FreeBuilder, MapStruct, Immutables y AutoValue se detectan y excluyen del universo de SUT vía [`generated-code-exclusion`](skills/01-discovery/generated-code-exclusion.md) → `state/generated-code-index.json`.

## Gates anti-alucinación

| Gate | Qué bloquea |
|------|-------------|
| G1 | Imports fuera de `import-whitelist.json` |
| G2 | Símbolo sin `evidence-id` en contrato |
| G3 | Contratos derivados de regex (forzar bytecode/AST) |
| G4 | Generated sources no indexados con APs declarados |
| G5 | Generation sin `stack-profile.json` válido |
| G6 | Linter AST pre-compile sobre el test |
| G7 | Re-aplicación de fix ya fallido |
| G8 | Convergencia (delta=0 o compile-fail-rate alto) |

## Modos

- `coverage` — maximiza líneas.
- `branch-coverage` — maximiza ramas y caminos.
- `mutation-hardening` — endurece tests con PIT sobre mutantes sobrevivientes.

## Validación de estados

Todos los `state/*.json` validan contra schemas en `state/_schemas/`. Escritura atómica (`*.tmp` + rename) y hashes SHA-256 en `state/execution-state.json`.

## VS Code + GitHub Copilot

Para ejecutar desde Visual Studio Code, usar la guía [`docs/vscode-copilot-execution-guide.md`](docs/vscode-copilot-execution-guide.md) y las instrucciones de proyecto en `.github/copilot-instructions.md`. La arquitectura ahora incluye controles específicos para diagnósticos JDT/Copilot: imports no resueltos, `new Interface()`, uso directo de `Type_Builder` y setters/métodos inventados.

## Cómo arrancar

1. Leer la [Guía del Desarrollador](docs/developer-guide.md).
2. Leer `MASTER_PROMPT.md`.
3. Correr el pre-stage Python (`tools/python/run_pipeline.py`).
4. Ejecutar Orchestrator con `mode` y `budget` pegando `Prompt_inicial.md` en el chat.
5. Validar cada test generado con `tools/python/test_linter.py` antes de compilar.
6. Inspeccionar `state/execution-state.json` y los `state/_summaries/cycle-*.json` para progreso.
7. Reporte final emitido por `reporting-agent`.
