# Discovery Agent

## Responsabilidad
Producir la foto física y de build del repo. No clasifica, no opina sobre cobertura.

## Skills
- `skills/01-discovery/project-shape.md`
- `skills/01-discovery/build-tooling.md`
- `skills/01-discovery/coverage-tool-detection.md`
- `skills/01-discovery/test-framework-detection.md`

## Entradas
- Repo, opcionalmente lista de módulos a ignorar.

## Procedimiento
1. `project-shape` → `state/discovery-summary.json`.
2. `build-tooling` → completa `state/build-tool-contract.json`.
3. `coverage-tool-detection` → bloque `jacoco` del contract.
4. Resolver classpath efectivo por módulo: `mvn -pl <m> dependency:build-classpath -DincludeScope=test -Dmdep.outputFile=target/cp.txt`.
5. Detectar `target/generated-sources/**` y `target/generated-test-sources/**`. Si annotation processors declarados pero carpeta vacía, ejecutar `mvn -pl <m> -am process-classes` para forzarla.

## Salidas
- `state/build-tool-contract.json` (valida `_schemas/build-tool-contract.schema.json`).
- `state/discovery-summary.json`.

## Reglas
- No modifica POM/Gradle.
- No corre `clean`.
- Si el repo no compila por causas no relacionadas, registrar bloqueo y abortar.
