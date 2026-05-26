# state/_schemas/protocols/

Schemas que describen **contratos de mensajería** entre subsistemas (LLM ↔ patcher, agente ↔ agente), no estados persistentes en disco.

A diferencia de `state/_schemas/*.schema.json` (que se mapean 1-a-1 con un `state/<name>.json` y son validados automáticamente por `tools/python/state_validator.py`), los schemas en este subdirectorio:

- No tienen un `state/<name>.json` correspondiente.
- Validan objetos efímeros (responses LLM, payloads transportados).
- Quedan fuera del scan automático del validator (`glob("*.schema.json")` no es recursivo).

## Contenido

- `patch-descriptor.schema.json` — formato canónico de patch que producen `test-body-agent` y `repair-agent`, y que consume `tools/python/test_patch_applier.py`. Documentado en [`docs/agent-json-protocol.md`](../../../docs/agent-json-protocol.md).
