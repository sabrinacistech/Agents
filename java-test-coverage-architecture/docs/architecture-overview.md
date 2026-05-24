# Architecture Overview

## Capas

1. **Orquestación** — Coverage Orchestrator; única autoridad para avanzar fases y aplicar gates G1–G8.
2. **Discovery técnico** — shape del repo, build tool, classpath, generated sources.
3. **Stack Profile** — frameworks de test/mock/assert/DI y annotation processors con versión.
4. **Clasificación** — tipo, etiquetas, riesgo, score por clase.
5. **Contratos de símbolos** — un archivo por SUT con `evidence-id`; whitelist de imports a nivel módulo.
6. **Grafo de dependencias** — DI, métodos invocados por colaborador, excepciones, estrategia Spring.
7. **Catálogo de fixtures** — datos deterministas, variantes por modo.
8. **Planning** — JaCoCo XML + ROI + tamaño dinámico de batch.
9. **Generation** — solo símbolos verificados; cita `evidence-id` en cada test.
10. **Validation** — narrow runner + parser de errores + delta JaCoCo derivado de XML.
11. **Repair** — matriz determinística + failure-memory (G7).
12. **Reporting** — evidencia citable, XML adjuntos, validación de consistencia.

## Decisión clave

La generación depende de tres tipos de evidencia, todos versionados con hash SHA-256:

- `state/import-whitelist.json` (qué imports pueden existir).
- `state/symbol-contracts/<fqcn>.json` (qué símbolos existen y cómo se usan).
- `state/fixture-catalog.json` (cómo construir datos válidos).

Si cualquiera falta o está desactualizado para un SUT, el Orchestrator NO permite generar tests para ese SUT.

## Aislamiento por SUT

El paralelismo se hace por SUT: nunca dos agentes sobre el mismo archivo de estado. Esto evita race conditions y permite escalar Generation/Validation horizontalmente sin comprometer atomicidad.

## Recuperación

`state/execution-state.json` mantiene `checkpoints[]` con hash por archivo. Tras un crash, el sistema vuelve al `lastGoodCheckpoint` y reanuda. Estados con hash inconsistente se degradan, no se aceptan.
