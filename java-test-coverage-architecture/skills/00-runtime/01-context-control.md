# Context Control

## Objetivo
Mantener el contexto del LLM enfocado en la fase actual. Evita ruido y reduce alucinación.

## Reglas
- Cargar **solo** los skills de la fase activa más los contratos vigentes (`stack-profile`, `import-whitelist`, `symbol-contracts/<sut>` actual).
- Estados históricos > 1 ciclo ⇒ comprimir a resumen (`state/_summaries/cycle-<n>.json`).
- No cargar JaCoCo XML completo en contexto; pasar el delta computado.
- No cargar código productivo completo; pasar solo los fragmentos referenciados por `evidence-id`.
- Cada agente declara su presupuesto máximo (tokens) y rechaza cargar más.

## Antipatrones
- "Cargar todo el repo por las dudas".
- "Reincluir el contrato global en cada paso".
- Repetir el MASTER_PROMPT entero en cada subagente (se referencia, no se copia).
