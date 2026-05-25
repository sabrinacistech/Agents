# Repository Intelligence Agent

> Single source of truth for repository structure, classification, dependency graph,
> framework detection, and symbol contracts. Replaces the deleted
> `discovery-agent`, `classification-agent`, `dependency-graph-agent`,
> `symbol-contract-agent`, and `stack-profile-agent`.

## Responsibility

Materialize every contract that downstream phases need, by **projection** from the
deterministic semantic index. No LLM. No source re-parsing.

## Inputs
- `state/index/{classes,methods,imports,dependencies,annotations}.json` (built by `tools/python/run_pipeline.py`).
- `state/build-tool-contract.json` (from the pre-stage).
- `state/incremental-map.json` (Incremental Planner output).

## Outputs
- `state/classification-index.json` — class kind, framework labels, risk, score.
- `state/dependency-graph.json` — view of `index/dependencies.json` filtered by `affectedClasses`.
- `state/symbol-contracts/<fqcn>.json` — projection of `index/{classes,methods,annotations}.json` for each SUT in scope.
- `state/import-whitelist.json` — derived from `index/imports.json` ∪ classpath.
- `state/stack-profile.json` — versions of JUnit, Mockito, AssertJ, Spring, Lombok, FreeBuilder, MapStruct, Immutables, AutoValue.
- `state/generated-code-index.json` — CXF/OpenAPI/AP-generated FQCNs excluded from SUT selection.

## Procedure

1. Validate `state/index/*.json` against `state/_schemas/index/*.schema.json`. On staleness, request incremental reindex from the pre-stage; do **not** parse Java.
2. **Classification**: derive labels by looking up annotations in `index/annotations.json` (`@RestController`, `@Service`, `@Repository`, `@Configuration`, `@Entity`, `@SpringBootApplication`, JAX-RS, reactive types, etc.). Score = pure function of dependency fan-out + missed coverage from `coverage-targets.json`.
3. **Dependency graph view**: filter `index/dependencies.json` to `affectedClasses ∪ targetSUTs` with one-hop closure.
4. **Symbol contracts**: for each SUT, project methods/constructors/fields with their `evidence-id`. The id is a stable hash over `(fqcn, descriptor, source)`.
5. **Import whitelist**: union of FQNs reachable from `index/imports.json` + classpath entries declared in `build-tool-contract.json`.
6. **Stack profile**: read framework versions from `build-tool-contract.json#dependencies`; fail with `BLOCKED_NO_STACK_PROFILE` if a test/mock/assertion library is missing.
7. **Generated-code exclusion**: CXF / OpenAPI / Lombok-generated FQCNs are tagged in `generated-code-index.json` and **excluded from SUT selection**, but allowed as collaborator types.

## Rules

- No LLM call. The only allowed LLM use is **disambiguation** between two equally-valid framework labels (e.g. Spring MVC + Spring WebFlux in the same module); even then, evidence ids must be cited.
- Idempotent: same index + same scope ⇒ byte-identical outputs.
- Respects `affectedClasses` when scope is `single-file` or `incremental`. Full projection only on `--full`.
- Atomic writes for every output (`*.tmp` + rename); fingerprints recorded in `execution-state.json`.

## Gates owned

- **G3** (bytecode-first) — inherited from the index.
- **G4** (generated-sources indexed) — inherited from the index.
- **G5** (stack-profile valid) — emitted here.

## Anti-patterns

- Re-parsing `.java` "just to be safe" when the index already has the info.
- Producing full contracts for the whole module when scope is `single-file`.
- Emitting a contract without `evidence-id` per symbol.
- Inferring frameworks from package or file names instead of `index/annotations.json`.
