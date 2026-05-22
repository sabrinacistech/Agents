# Architecture Overview

Esta arquitectura separa control de flujo, verificación estructural y generación. La mejora principal frente a una arquitectura solo basada en prompts es la introducción de contratos verificables antes de generar tests.

## Capas

1. Orquestación.
2. Discovery técnico.
3. Clasificación de testabilidad.
4. Contratos de símbolos.
5. Grafo de dependencias.
6. Catálogo de fixtures.
7. Planificación por cobertura real.
8. Generación controlada.
9. Validación y reparación.
10. Reportería con evidencia.

## Decisión clave

La generación depende de `state/symbol-contracts.json`, `state/dependency-graph.json` y `state/fixture-catalog.json`. Si esos estados están incompletos, el agente debe bloquear generación o elegir un objetivo de menor riesgo.
