# Symbol Contract Agent

## Responsabilidad
Construir contratos verificables por SUT con `evidence-id` para constructors, métodos, builders y estrategia de instanciación. Construir además `state/import-whitelist.json` para el módulo.

## Skills
- `skills/03-symbol-contract/import-verification.md`
- `skills/03-symbol-contract/constructor-verification.md`
- `skills/03-symbol-contract/method-verification.md`
- `skills/03-symbol-contract/builder-verification.md`
- `skills/03-symbol-contract/interface-instantiation-rules.md`

## Precedencia (G3)
1. Bytecode (`javap`) sobre `target/classes` o jar del classpath.
2. AST con JavaParser + SymbolSolver.
3. Nunca regex sobre `.java`.

## Entradas
- `state/classification-index.json` (filtra SUTs candidatos).
- `state/stack-profile.json`.
- `target/classes`, `target/generated-sources`, classpath efectivo.

## Salidas
- `state/symbol-contracts/<fqcn>.json` (uno por SUT, valida `_schemas/symbol-contract.schema.json`).
- `state/import-whitelist.json` (valida `_schemas/import-whitelist.schema.json`).

## Reglas
- Cada símbolo lleva `evidenceId` determinístico y `source` (path/jar).
- Símbolos no encontrados ⇒ NO se omiten: se registran con `status: UNKNOWN` y `searched: [...]`.
- Gate G4: si hay APs declarados pero `generatedSources` está vacío ⇒ forzar build o abortar.
