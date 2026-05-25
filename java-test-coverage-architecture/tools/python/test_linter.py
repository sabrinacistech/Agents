"""test_linter.py — deterministic guardrails for generated Java tests.

Checks implemented:
* G1: every import/import static must be present in import-whitelist.json.
* G2-lite: `new X(...)` is rejected when X is an interface/abstract type or the
  contract says instantiation is not constructor-based.
* G2-lite: builder setters/method calls on variables with known contract types are
  rejected when the method is not enumerated in the contract.
* FreeBuilder guard: `new Interface()` and direct `Type_Builder` usage are blocked.

This is not a full Java compiler. It is a cheap pre-build gate designed to stop the
most common Copilot/LLM hallucinations before Maven/Gradle is invoked.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import load_json

IMPORT_RE = re.compile(r"^\s*import\s+(static\s+)?([\w\.]+(?:\.\*)?)\s*;", re.MULTILINE)
PACKAGE_RE = re.compile(r"^\s*package\s+([\w\.]+)\s*;", re.MULTILINE)
NEW_RE = re.compile(r"\bnew\s+([A-Z]\w*(?:\.[A-Z]\w*)?)\s*\(")
DIRECT_GENERATED_BUILDER_RE = re.compile(r"\bnew\s+([A-Z]\w+_Builder)\s*\(")
VAR_DECL_RE = re.compile(r"\b(?P<type>[A-Z]\w*(?:\.[A-Z]\w+)?(?:<[^;=]+>)?)\s+(?P<var>[a-zA-Z_]\w*)\s*(?:=|;)")
CALL_RE = re.compile(r"\b(?P<var>[a-zA-Z_]\w*)\.(?P<method>[a-zA-Z_]\w*)\s*\(")
STATIC_CALL_RE = re.compile(r"\b(?P<type>[A-Z]\w*)\.(?P<method>[a-zA-Z_]\w*)\s*\(")
ALLOWED_IMPLICIT = {
    "String", "Integer", "Long", "Double", "Float", "Boolean", "Object", "Short", "Byte", "Character",
    "RuntimeException", "Exception", "Throwable", "AssertionError", "IllegalArgumentException", "IllegalStateException",
    "ArrayList", "LinkedList", "HashMap", "HashSet", "List", "Map", "Set", "Optional", "Collections", "Arrays",
}
ALLOWED_CALLS = {
    "toString", "equals", "hashCode", "getClass", "size", "isEmpty", "contains", "add", "put", "get", "orElse", "orElseThrow",
}


def load_contracts(contracts_dir: Path | None) -> tuple[dict[str, dict], dict[str, dict]]:
    by_fqcn: dict[str, dict] = {}
    by_simple: dict[str, dict] = {}
    if not contracts_dir or not contracts_dir.exists():
        return by_fqcn, by_simple
    for p in contracts_dir.glob("*.json"):
        try:
            c = load_json(p)
        except Exception:
            continue
        fqcn = c.get("fqcn")
        if not fqcn:
            continue
        by_fqcn[fqcn] = c
        by_simple[fqcn.rsplit(".", 1)[-1]] = c
    return by_fqcn, by_simple


def method_names(c: dict) -> set[str]:
    out = {m.get("name") for m in c.get("methods", []) if m.get("usable", True)}
    for b in c.get("builders", []):
        out.update(s.get("name") for s in b.get("setters", []))
        out.add((b.get("build") or "build()").split("(")[0])
    return {x for x in out if x}


def resolve_type(type_name: str, imports: dict[str, str], same_pkg: str, contracts_by_fqcn: dict[str, dict], contracts_by_simple: dict[str, dict]) -> tuple[str | None, dict | None]:
    raw = re.sub(r"<.*>", "", type_name).strip()
    raw = raw.split(".")[0] if ".Builder" not in raw else raw
    simple = raw.split(".")[0]
    if raw in contracts_by_fqcn:
        return raw, contracts_by_fqcn[raw]
    if simple in imports and imports[simple] in contracts_by_fqcn:
        return imports[simple], contracts_by_fqcn[imports[simple]]
    candidate = f"{same_pkg}.{simple}" if same_pkg else simple
    if candidate in contracts_by_fqcn:
        return candidate, contracts_by_fqcn[candidate]
    if simple in contracts_by_simple:
        c = contracts_by_simple[simple]
        return c.get("fqcn"), c
    return None, None


def lint(test_file: Path, whitelist: dict, contracts_dir: Path | None) -> dict:
    text = test_file.read_text(encoding="utf-8", errors="ignore")
    classes = {c["fqcn"]: c for c in whitelist.get("classes", [])}
    packages = {p["name"] for p in whitelist.get("packages", [])}
    violations = []
    contracts_by_fqcn, contracts_by_simple = load_contracts(contracts_dir)

    pkg_m = PACKAGE_RE.search(text)
    same_pkg = pkg_m.group(1) if pkg_m else ""

    declared_imports = {}
    static_imports = set()
    for m in IMPORT_RE.finditer(text):
        is_static = bool(m.group(1))
        target = m.group(2)
        if is_static:
            static_imports.add(target)
        if target.endswith(".*"):
            pkg = target[:-2]
            if pkg not in packages:
                violations.append({"gate": "G1", "kind": "IMPORT_PKG_NOT_WHITELISTED", "import": target})
            continue
        declared_imports[target.rsplit(".", 1)[-1]] = target
        if target in classes:
            continue
        pkg = target.rsplit(".", 1)[0]
        if pkg not in packages:
            violations.append({"gate": "G1", "kind": "IMPORT_NOT_WHITELISTED", "import": target})

    for target in static_imports:
        owner = target.rsplit(".", 1)[0]
        if owner not in classes and owner.rsplit(".", 1)[0] not in packages:
            violations.append({"gate": "G1", "kind": "STATIC_IMPORT_NOT_WHITELISTED", "import": "static " + target})

    # Direct generated FreeBuilder usage: always forbidden unless explicit contract entry says so.
    for m in DIRECT_GENERATED_BUILDER_RE.finditer(text):
        violations.append({"gate": "G2", "kind": "DIRECT_GENERATED_BUILDER_FORBIDDEN", "symbol": m.group(1)})

    # Type map from local variable declarations.
    var_types: dict[str, tuple[str, dict | None, bool]] = {}
    for m in VAR_DECL_RE.finditer(text):
        typ = m.group("type").strip()
        var = m.group("var")
        is_builder = typ.endswith(".Builder") or typ == "Builder"
        owner = typ.replace(".Builder", "")
        fq, c = resolve_type(owner, declared_imports, same_pkg, contracts_by_fqcn, contracts_by_simple)
        if c:
            var_types[var] = (fq or owner, c, is_builder)

    for m in NEW_RE.finditer(text):
        typ = m.group(1)
        owner = typ.replace(".Builder", "")
        is_builder_ctor = typ.endswith(".Builder")
        fq, c = resolve_type(owner, declared_imports, same_pkg, contracts_by_fqcn, contracts_by_simple)
        if not c:
            if owner.split(".")[0] not in ALLOWED_IMPLICIT and owner.split(".")[0] in declared_imports:
                # Imported but no contract available: leave to compiler.
                pass
            continue
        inst = c.get("instantiation", {})
        kind = c.get("kind")
        if is_builder_ctor:
            builders = c.get("builders", [])
            if not any((b.get("entry") or "").endswith(f"{owner.split('.')[-1]}.Builder()") or ".Builder()" in (b.get("entry") or "") for b in builders):
                violations.append({"gate": "G2", "kind": "BUILDER_NOT_VERIFIED", "symbol": typ, "fqcn": c.get("fqcn")})
            continue
        if kind in {"interface", "abstract", "annotation"} or not inst.get("allowed", False) or inst.get("strategy") not in {"constructor", "concrete"}:
            violations.append({"gate": "G2", "kind": "INSTANTIATION_NOT_ALLOWED", "symbol": typ, "fqcn": c.get("fqcn"), "strategy": inst.get("strategy"), "reason": inst.get("reason")})

    for m in CALL_RE.finditer(text):
        var = m.group("var")
        meth = m.group("method")
        if meth in ALLOWED_CALLS or var not in var_types:
            continue
        fq, c, is_builder = var_types[var]
        allowed = method_names(c)
        if meth not in allowed:
            violations.append({"gate": "G2", "kind": "METHOD_NOT_IN_CONTRACT", "receiver": var, "receiverType": fq, "method": meth})

    for m in STATIC_CALL_RE.finditer(text):
        typ = m.group("type")
        meth = m.group("method")
        if typ in {"Mockito", "Assertions", "Assert", "Collections", "Arrays", "Optional"}:
            continue
        fq, c = resolve_type(typ, declared_imports, same_pkg, contracts_by_fqcn, contracts_by_simple)
        if c and meth not in method_names(c):
            # Permit nested Builder constructor-like entry handled elsewhere.
            violations.append({"gate": "G2", "kind": "STATIC_METHOD_NOT_IN_CONTRACT", "receiverType": fq, "method": meth})

    return {"file": str(test_file), "violations": violations}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-file", required=True)
    ap.add_argument("--whitelist", required=True)
    ap.add_argument("--contracts", default=None)
    args = ap.parse_args()
    test_file = Path(args.test_file)
    wl = load_json(Path(args.whitelist))
    contracts = Path(args.contracts) if args.contracts else None
    report = lint(test_file, wl, contracts)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
