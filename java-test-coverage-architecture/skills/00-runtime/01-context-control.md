# Context Control

> Companion skill to `skills/00-runtime/minimal-context-policy.md`. This file
> defines **what to load** per phase; `minimal-context-policy.md` defines **what
> never enters a prompt** plus token budgets.

## Loading rules

- Load **only** the skills for the active phase plus the projected contracts
  in scope (`stack-profile`, projected `symbol-contracts/_views/<batchId>.json`,
  whitelist subset).
- Historical state > 1 cycle ⇒ compress to `state/_summaries/cycle-<n>.json`.
- Never load full JaCoCo XML; pass `state/coverage-delta.json` instead.
- Never load full production source; pass fragments cited by `evidence-id`.
- Every agent declares its token budget and refuses to load more.

## Determinism vs LLM

Heavy work does not reach the LLM. Before assembling a prompt, validate against
`skills/00-runtime/deterministic-analysis-policy.md`:

- Imports, frameworks, dependencies, compile errors, stack traces ⇒ **outside**
  the prompt (already resolved through `state/index/` and
  `state/compile-error-index.json`).
- Only inside the prompt: target method, required collaborators, failing lines
  (not the whole file), minimal contracts, minimal fixtures.

## Surgical inputs

For generation and repair, prefer surgical inputs:

- target method + collaborator signatures (not the whole class),
- failing lines ± 2 lines (not the whole test file),
- fragments cited by `evidence-id` (not the whole contract).

See `skills/07-generation/ast-patch-generation.md` and
`skills/00-runtime/minimal-context-policy.md`.

## Anti-patterns
- "Load the whole repo just in case."
- "Re-include the full contract on every step."
- "Repeat MASTER_PROMPT.md in every subagent" (reference by name, never duplicate).
- "Paste the JaCoCo XML / POM / stack trace verbatim."
- "Include unrelated methods of the SUT."
