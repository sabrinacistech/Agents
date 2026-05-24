# Python pipeline (tools/python)

Procesos deterministas que el LLM **no** debe ejecutar a mano: parseos de POM, classpath, bytecode, JaCoCo XML y errores de compilación. Generan los `state/*.json` que consume el LLM.

## Por qué

- **Tokens**: el LLM lee solo JSON compacto, no POMs/XML/log/javap.
- **Velocidad**: paralelizable y cacheable por mtime/SHA.
- **Determinismo**: cero invención en la capa de evidencia.

## Scripts

| Script | Salida (`state/`) |
|--------|-------------------|
| `pom_parser.py` | `build-tool-contract.json` |
| `archetype_detector.py` | `archetype-profile.json` |
| `generated_code_scanner.py` | `generated-code-index.json` |
| `classpath_resolver.py` | `import-whitelist.json` |
| `bytecode_scanner.py` | `symbol-contracts/<fqcn>.json` |
| `jacoco_parser.py` | `coverage-targets.json` / `coverage-delta.json` |
| `compile_error_parser.py` | `compile-error-index.json` |
| `freebuilder_scanner.py` | (anexa a contracts) |
| `test_linter.py` | reporte G1+G6 (stdout / exit code) |
| `state_validator.py` | valida cualquier `state/*.json` contra `state/_schemas/` |
| `run_pipeline.py` | orquesta discovery → archetype → generated → classpath → symbols → jacoco |

## Requisitos

```bash
pip install -r tools/python/requirements.txt
```

Java/Maven en `PATH`. Para multi-módulo Maven, el repo debe haber pasado al menos un `mvn -DskipTests package` para tener `target/classes` y `target/generated-sources`.

## Uso (típico)

```bash
# Pre-build una sola vez por commit
mvn -q -DskipTests package

# Bootstrap de evidencia (segundos en repos chicos, minutos en grandes)
python tools/python/run_pipeline.py --repo . --out docs/agents/java-test-coverage-architecture/state

# El LLM ahora consume solo state/*.json
```

## Caché

Cada script computa SHA-256 de sus entradas y, si la salida JSON existe con el mismo hash, **no recomputa**. La caché vive en `state/_cache/<script>.cache.json`.

## Convención de errores

- Exit code 0: éxito y JSON válido contra schema.
- Exit code 2: bloqueo recuperable (falta `target/classes`, contrato OpenAPI inexistente, etc.).
- Exit code 3: schema inválido (bug del script).
- stderr humano-legible; stdout JSON cuando aplica.
