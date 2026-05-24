# repair-rules/ — Deterministic Repair Engine (Phase 6)

Reglas determinísticas aplicadas **antes** de invocar al LLM. Cada archivo agrupa
reglas por dominio.

| Archivo            | Dominio                                                  |
|--------------------|----------------------------------------------------------|
| `imports.rules`    | Imports faltantes / ambiguos.                            |
| `mockito.rules`    | Errores típicos de Mockito (`PotentialStubbingProblem`, etc.). |
| `spring.rules`     | Contexto Spring, bean wiring, slices.                    |
| `junit.rules`      | Runner/Extension, `@Test` mal anotado, lifecycle.        |
| `builders.rules`   | FreeBuilder / Lombok / generated builders.               |

## Formato

Cada línea no-comentario es una regla:

```
<errorPattern> => <action>(<args>)
```

Donde `errorPattern` matchea contra `state/compile-error-index.json[*].code|message`
y `action` está en el set:

- `addImport(<fqn>)`
- `removeImport(<fqn>)`
- `addAnnotation(<target>, <fqn>)`
- `wrapWith(lenient)` — para Mockito strict stubbing.
- `replaceCall(<from>, <to>)`
- `addMockBean(<type>)`
- `useBuilder(<fqn>)`
- `escalateToLLM(<reason>)` — fallback explícito.

## Pipeline de repair

1. Resolver causa raíz desde `state/compile-error-index.json` (ya parseado).
2. Buscar regla en `repair-rules/*.rules` por `errorCode` / patrón.
3. Aplicar acción vía `tools/python/ast_patcher.py` (mismo motor que generación).
4. Recompilar **scope incremental** (`-Dtest=<one>`).
5. Si persiste → segunda iteración determinística (max 2).
6. Si aún persiste y no está en `failure-memory.json#FAILED` → `escalateToLLM`.

## Invariantes

- El LLM **nunca** parsea errores ni stack traces.
- G7 (failure-memory) bloquea reaplicar fixes ya fallidos.
- Cada fix aplicado registra `{ errorCode, symbolFQN, fixId, result }` en
  `state/failure-memory.json`.

Ver `agents/repair-agent.md` y `skills/00-runtime/deterministic-analysis-policy.md`.
