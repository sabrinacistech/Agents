# Java Test Coverage Agent Architecture - Optimized

Arquitectura optimizada de agentes y skills para generar cobertura de tests unitarios en microservicios Java, con foco en Java 8, Maven/Gradle, Mockito, JUnit, JaCoCo y proyectos con FreeBuilder.

## Objetivo

Generar, validar y reparar tests unitarios evitando alucinaciones del LLM. La arquitectura prioriza evidencia real del código antes de generar tests.

## Principio central

> El agente no debe inventar símbolos. Solo puede usar clases, imports, constructores, métodos, builders, fixtures y comandos previamente verificados.

## Flujo principal

```text
discovery
  -> classification
  -> symbol-contract
  -> dependency-graph
  -> fixture-catalog
  -> planning
  -> generation
  -> validation
  -> repair
  -> reporting
```

## Estructura

```text
agents/              Agentes orquestadores por fase
skills/              Capacidades reutilizables por dominio
state/               Contratos JSON persistentes entre fases
docs/                Documentación de uso y decisiones de arquitectura
MASTER_PROMPT.md     Prompt principal para ejecutar la arquitectura
```

## Optimizaciones incluidas

1. Symbol Contract Agent para evitar imports, setters, constructors y builders inventados.
2. Dependency Graph Agent para construir mocks y dependencias reales.
3. Fixture Agent para centralizar datos de prueba válidos.
4. Build Tool Adapter para comandos Maven/Gradle verificables.
5. Compile Error Parser para reparación determinística.
6. FreeBuilder strategy reforzado.
7. JaCoCo XML como fuente de planificación de cobertura.
8. Runtime simplificado para reducir ruido contextual.
9. Mutation testing como modo opcional posterior, no como fase obligatoria.

## Modos sugeridos

```text
mode: coverage              Subir cobertura de líneas.
mode: branch-coverage       Subir cobertura de ramas y paths alternativos.
mode: mutation-hardening    Endurecer tests críticos con mutation testing.
```
