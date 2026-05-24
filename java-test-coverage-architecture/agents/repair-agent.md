# Repair Agent

## Responsabilidad
Aplicar reparaciones determinísticas según causa raíz parseada. Respeta G7 (failure-memory).

## Skills
- `skills/09-repair/repair-decision-matrix.md`
- `skills/09-repair/failure-memory.md`
- `skills/09-repair/retry-policy.md`

## Entradas
- `state/compile-error-index.json`
- `state/symbol-contracts/*.json` (para reemplazos verificados)
- `state/import-whitelist.json`
- `state/failure-memory.json`

## Procedimiento
1. Por cada error, derivar `fixId` candidato desde `repair-decision-matrix.md`.
2. Calcular `hash(errorCode, symbolFQN, fixId)`; si está marcado `FAILED` en `failure-memory.json` ⇒ G7 prohíbe el fix.
3. Aplicar fix (editar archivo de test). Re-correr G1 + G6 antes de pedir nueva compilación.
4. Registrar resultado en `failure-memory.json`.
5. Máximo 2 intentos por test (retry-policy).

## Salidas
- Tests reparados o descartados.
- `state/failure-memory.json` actualizado.

## Reglas
- Nunca inventar símbolos para "reparar".
- Nunca silenciar tests (`@Ignore`/`@Disabled`).
- Nunca bajar asserts para forzar pase.
