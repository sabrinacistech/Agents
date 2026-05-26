"""context_pack_builder.py — Build minimal per-SUT context packs for LLM agents.

Reads state/batch-plan.json and, for each planned SUT, performs a surgical extraction
from the JSON state layer (stack-profile, classification-index, dependency-graph,
fixture-catalog, symbol-contracts, coverage-targets, import-whitelist).

Writes one compact JSON per SUT to: state/context-packs/<safe_fqcn>.json

The context-pack is the ONLY artifact LLM agents are allowed to consume.
No agent may open raw source code, pom.xml, build.gradle, or jacoco.xml.

Step 16 in run_pipeline.py  (--skip context).

Usage:
    python context_pack_builder.py --out state/
    python context_pack_builder.py --out state/ --sut com.example.MyService
    python context_pack_builder.py --out state/ --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import atomic_write_json, fail, load_json, validate  # noqa: E402

SCHEMA_NAME = "context-pack"

FORBIDDEN_ACTIONS = [
    "READ_SOURCE_CODE",
    "READ_POM",
    "READ_JACOCO_XML",
    "READ_CLASSPATH",
    "READ_BYTECODE",
    "INVENT_SYMBOL",
    "INVENT_IMPORT",
    "RETURN_RAW_JAVA",
    "CALL_UNLISTED_METHOD",
    "INSTANTIATE_UNLISTED_TYPE",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_fqcn(fqcn: str) -> str:
    """Convert FQCN to a filesystem-safe filename stem."""
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", fqcn)


def load_optional(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception as exc:
        print(f"[WARN] Could not load {path}: {exc}", file=sys.stderr)
        return None


# ── Extractors ────────────────────────────────────────────────────────────────

def extract_stack(stack_profile: dict | None) -> dict:
    """Build minimal stack block from stack-profile.json (first module wins)."""
    if not stack_profile:
        return {
            "javaVersion": "unknown",
            "testFramework": "junit5",
            "mockFramework": "mockito",
        }

    modules = stack_profile.get("modules", [])
    mod = modules[0] if modules else {}

    test_info = mod.get("test", {})
    mock_info = mod.get("mock", {})
    assert_info = mod.get("assert", {})
    di_info = mod.get("di", {})

    return {
        "javaVersion": stack_profile.get("java", "unknown"),
        "testFramework": test_info.get("framework", "junit5"),
        "testVersion": test_info.get("version", ""),
        "mockFramework": mock_info.get("framework", "mockito"),
        "mockVersion": mock_info.get("version", ""),
        "assertFramework": assert_info.get("framework", "assertj"),
        "springEnabled": bool(di_info.get("spring", False)),
        "springBootVersion": di_info.get("springBoot", None),
        "springSlices": di_info.get("slices", []),
        "namespaceStyle": _detect_namespace(stack_profile),
        "annotationProcessors": mod.get("annotationProcessors", []),
    }


def _detect_namespace(stack_profile: dict) -> str:
    processors = []
    for mod in stack_profile.get("modules", []):
        processors.extend(mod.get("annotationProcessors", []))
    joined = " ".join(processors).lower()
    if "jakarta" in joined:
        return "jakarta"
    if "javax" in joined:
        return "javax"
    return "none"


def extract_classification(classification_index: dict | None, fqcn: str) -> dict:
    if not classification_index:
        return {}
    for entry in classification_index.get("classes", []):
        if entry.get("fqcn") == fqcn:
            return {
                "type": entry.get("type"),
                "risk": entry.get("risk"),
                "score": entry.get("score"),
                "cyclomatic": entry.get("cyclomatic"),
                "tags": entry.get("tags", []),
            }
    return {}


def extract_coverage(coverage_targets: dict | None, sut: str, batch_items: list[dict]) -> dict:
    """Build coverage block: aggregate totals + per-target detail for this SUT."""
    sut_target_ids = {item["targetId"] for item in batch_items if item["sut"] == sut}
    targets_out: list[dict] = []
    total_lines = 0
    total_branches = 0

    if coverage_targets:
        for t in coverage_targets.get("targets", []):
            if t.get("sut") == sut and t.get("id") in sut_target_ids:
                ml = t.get("missedLines", 0)
                mb = t.get("missedBranches", 0)
                total_lines += ml
                total_branches += mb
                targets_out.append({
                    "targetId": t["id"],
                    "method": t.get("method", ""),
                    "missedLines": ml,
                    "missedBranches": mb,
                    "branchId": t.get("branchId", None),
                    "score": t.get("score"),
                })

    return {
        "totalMissedLines": total_lines,
        "totalMissedBranches": total_branches,
        "targets": targets_out,
    }


def extract_symbol_contract(
    symbol_contracts_dir: Path,
    fqcn: str,
) -> tuple[list[dict], list[dict]]:
    """Return (constructors, methods) from per-FQCN contract file."""
    contract_path = symbol_contracts_dir / f"{safe_fqcn(fqcn)}.json"
    contract = load_optional(contract_path)
    if not contract:
        return [], []

    constructors = [
        {
            "evidenceId": c["evidenceId"],
            "visibility": c.get("visibility", "public"),
            "params": c.get("params", []),
            "throws": c.get("throws", []),
        }
        for c in contract.get("constructors", [])
    ]

    methods = [
        {
            "evidenceId": m["evidenceId"],
            "name": m["name"],
            "returnType": m.get("returnType", "void"),
            "params": m.get("params", []),
            "throws": m.get("throws", []),
            "usable": bool(m.get("usable", True)),
        }
        for m in contract.get("methods", [])
        if m.get("usable", True)
    ]

    return constructors, methods


def extract_dependencies(dependency_graph: dict | None, fqcn: str) -> tuple[list, list, dict]:
    """Return (dependencies, collaboratorUsage, springStrategy) for this SUT."""
    if not dependency_graph:
        return [], [], {}

    for graph in dependency_graph.get("graphs", []):
        if graph.get("sut") == fqcn:
            deps = [
                {
                    "name": d["name"],
                    "type": d["type"],
                    "injection": d["injection"],
                    "final": d.get("final", False),
                }
                for d in graph.get("dependencies", [])
            ]
            collab = graph.get("collaboratorUsage", [])
            spring = graph.get("springStrategy", {})
            return deps, collab, spring

    return [], [], {}


def enrich_deps_with_strategy(
    dependencies: list[dict],
    fixture_catalog: dict | None,
) -> list[dict]:
    """Attach instantiationStrategy from fixture-catalog to each dependency."""
    if not fixture_catalog:
        return dependencies

    type_to_strategy: dict[str, str] = {
        f["type"]: f["strategy"]
        for f in fixture_catalog.get("fixtures", [])
    }

    enriched = []
    for dep in dependencies:
        d = dict(dep)
        d["instantiationStrategy"] = type_to_strategy.get(dep["type"], "mock")
        enriched.append(d)
    return enriched


def extract_fixtures(
    fixture_catalog: dict | None,
    dependencies: list[dict],
    batch_items: list[dict],
    sut: str,
) -> list[dict]:
    """Extract fixtures relevant to this SUT's dependencies and batch fixture IDs."""
    if not fixture_catalog:
        return []

    dep_types = {d["type"] for d in dependencies}
    batch_fixture_ids: set[str] = set()
    for item in batch_items:
        if item["sut"] == sut:
            batch_fixture_ids.update(item.get("fixtureIds", []))

    relevant: list[dict] = []
    for fix in fixture_catalog.get("fixtures", []):
        if fix["type"] in dep_types or fix["id"] in batch_fixture_ids:
            relevant.append({
                "id": fix["id"],
                "type": fix["type"],
                "strategy": fix["strategy"],
                "builderEvidence": fix.get("builderEvidence"),
                "constructorEvidence": fix.get("constructorEvidence"),
                "factoryEvidence": fix.get("factoryEvidence"),
                "values": fix.get("values", {}),
                "variants": fix.get("variants", []),
                "cycleSafe": fix.get("cycleSafe", True),
            })
    return relevant


def extract_allowed_imports(
    import_whitelist: dict | None,
    stack: dict,
) -> list[str]:
    """Return a curated list of safe FQCNs the agent may use as imports."""
    always_allowed = [
        "org.junit.jupiter.api.Test",
        "org.junit.jupiter.api.BeforeEach",
        "org.junit.jupiter.api.AfterEach",
        "org.junit.jupiter.api.Assertions",
        "org.junit.jupiter.api.extension.ExtendWith",
        "org.junit.Test",
        "org.junit.Before",
        "org.junit.After",
        "org.mockito.Mockito",
        "org.mockito.Mock",
        "org.mockito.InjectMocks",
        "org.mockito.junit.jupiter.MockitoExtension",
        "org.mockito.junit.MockitoJUnitRunner",
        "org.assertj.core.api.Assertions",
        "org.hamcrest.MatcherAssert",
        "org.hamcrest.Matchers",
        "java.util.Optional",
        "java.util.List",
        "java.util.Map",
        "java.util.Set",
        "java.util.Arrays",
        "java.util.Collections",
    ]

    if stack.get("springEnabled"):
        always_allowed += [
            "org.springframework.boot.test.context.SpringBootTest",
            "org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest",
            "org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest",
            "org.springframework.boot.test.mock.mockito.MockBean",
            "org.springframework.test.web.servlet.MockMvc",
            "org.springframework.beans.factory.annotation.Autowired",
        ]

    # Add project-local allowed FQCNs from the whitelist (source + dep origin only)
    if import_whitelist:
        for entry in import_whitelist.get("classes", []):
            if entry.get("origin") in ("source", "dep"):
                fqcn = entry.get("fqcn", "")
                if fqcn and fqcn not in always_allowed:
                    always_allowed.append(fqcn)

    return sorted(set(always_allowed))


# ── Pack builder ──────────────────────────────────────────────────────────────

def build_pack(
    fqcn: str,
    mode: str,
    batch_items: list[dict],
    stack_profile: dict | None,
    classification_index: dict | None,
    dependency_graph: dict | None,
    fixture_catalog: dict | None,
    coverage_targets: dict | None,
    import_whitelist: dict | None,
    symbol_contracts_dir: Path,
) -> dict:
    """Assemble the minimal context-pack for one SUT."""
    stack = extract_stack(stack_profile)
    classification = extract_classification(classification_index, fqcn)
    coverage = extract_coverage(coverage_targets, fqcn, batch_items)
    constructors, methods = extract_symbol_contract(symbol_contracts_dir, fqcn)
    deps_raw, collab_usage, spring_strategy = extract_dependencies(dependency_graph, fqcn)
    dependencies = enrich_deps_with_strategy(deps_raw, fixture_catalog)
    fixtures = extract_fixtures(fixture_catalog, deps_raw, batch_items, fqcn)
    allowed_imports = extract_allowed_imports(import_whitelist, stack)

    pack: dict = {
        "schemaVersion": 1,
        "sut": fqcn,
        "mode": mode,
        "stack": stack,
        "coverage": coverage,
        "constructors": constructors,
        "methods": methods,
        "dependencies": dependencies,
        "collaboratorUsage": collab_usage,
        "fixtures": fixtures,
        "allowedImports": allowed_imports,
        "forbidden": FORBIDDEN_ACTIONS,
    }

    if classification:
        pack["classification"] = classification

    if spring_strategy:
        pack["springStrategy"] = spring_strategy

    return pack


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Build per-SUT context packs from the JSON state layer.\n"
            "Output: state/context-packs/<safe_fqcn>.json\n"
            "These packs are the ONLY JSON the LLM agents may read."
        )
    )
    ap.add_argument(
        "--out",
        required=True,
        help="State directory (contains batch-plan.json and other state files)",
    )
    ap.add_argument(
        "--sut",
        default=None,
        help="Build pack for a single FQCN only (default: all SUTs in batch-plan.json)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print each pack to stdout instead of writing files",
    )
    args = ap.parse_args()

    state_dir = Path(args.out).resolve()
    packs_dir = state_dir / "context-packs"
    contracts_dir = state_dir / "symbol-contracts"

    # ── Load batch plan (required) ────────────────────────────────────────────
    batch_plan_path = state_dir / "batch-plan.json"
    if not batch_plan_path.exists():
        fail(f"batch-plan.json not found in {state_dir} — run coverage_planner.py first")
    batch_plan = load_json(batch_plan_path)
    mode: str = batch_plan.get("mode", "coverage")
    batch_items: list[dict] = batch_plan.get("items", [])

    # ── Collect unique SUTs ───────────────────────────────────────────────────
    if args.sut:
        suts = [args.sut]
    else:
        seen: dict[str, bool] = {}
        suts = [
            seen.setdefault(item["sut"], item["sut"])  # type: ignore[func-returns-value]
            for item in batch_items
            if item["sut"] not in seen
        ]
        suts = list(seen.keys())

    if not suts:
        print("[INFO] No SUTs found in batch-plan.json — nothing to build.", file=sys.stderr)
        return 0

    # ── Load shared state files (optional — warn but don't fail) ─────────────
    stack_profile = load_optional(state_dir / "stack-profile.json")
    classification_index = load_optional(state_dir / "classification-index.json")
    dependency_graph = load_optional(state_dir / "dependency-graph.json")
    fixture_catalog = load_optional(state_dir / "fixture-catalog.json")
    coverage_targets = load_optional(state_dir / "coverage-targets.json")
    import_whitelist = load_optional(state_dir / "import-whitelist.json")

    if not stack_profile:
        print("[WARN] stack-profile.json missing — stack block will use defaults", file=sys.stderr)

    # ── Build and write one pack per SUT ─────────────────────────────────────
    errors = 0
    packs_dir.mkdir(parents=True, exist_ok=True)

    for fqcn in suts:
        try:
            pack = build_pack(
                fqcn=fqcn,
                mode=mode,
                batch_items=batch_items,
                stack_profile=stack_profile,
                classification_index=classification_index,
                dependency_graph=dependency_graph,
                fixture_catalog=fixture_catalog,
                coverage_targets=coverage_targets,
                import_whitelist=import_whitelist,
                symbol_contracts_dir=contracts_dir,
            )
        except Exception as exc:
            print(f"[ERROR] Building pack for {fqcn}: {exc}", file=sys.stderr)
            errors += 1
            continue

        try:
            validate(SCHEMA_NAME, pack)
        except Exception as exc:
            print(f"[WARN] Schema validation failed for {fqcn}: {exc}", file=sys.stderr)

        if args.dry_run:
            import json
            print(f"\n=== context-pack: {fqcn} ===")
            print(json.dumps(pack, ensure_ascii=False, indent=2))
        else:
            out_path = packs_dir / f"{safe_fqcn(fqcn)}.json"
            atomic_write_json(out_path, pack)
            print(f"[OK] {fqcn} → {out_path.relative_to(state_dir.parent)}")

    if errors:
        print(f"\n[FAIL] {errors} pack(s) failed to build.", file=sys.stderr)
        return 1

    print(f"\n[DONE] {len(suts)} context pack(s) written to {packs_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
