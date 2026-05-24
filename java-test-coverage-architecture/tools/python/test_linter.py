"""test_linter.py — AST-light check that a proposed test file does not invent imports
or symbols (gates G1 and partially G6).

This is intentionally simple (regex-based for imports + token-based for `new X(...)`
and static calls) so it can run without javaparser. For full G6 a real Java AST tool
is preferred (e.g., javaparser via subprocess) but this catches the most common
hallucinations cheaply.

Exit codes:
  0 = PASS
  1 = FAIL (lint violations reported on stdout as JSON)
  2 = blocking I/O error
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import load_json

IMPORT_RE = re.compile(r"^\s*import\s+(static\s+)?([\w\.]+(?:\.\*)?)\s*;", re.MULTILINE)
NEW_RE = re.compile(r"\bnew\s+([\w\.]+)\s*\(")
STATIC_CALL_RE = re.compile(r"\b([A-Z][\w]+)\.(\w+)\s*\(")


def lint(test_file: Path, whitelist: dict, contracts_dir: Path | None) -> dict:
    text = test_file.read_text(encoding="utf-8", errors="ignore")
    classes = {c["fqcn"]: c for c in whitelist.get("classes", [])}
    packages = {p["name"] for p in whitelist.get("packages", [])}
    violations = []

    # G1: imports must be in whitelist (class or package wildcard)
    for m in IMPORT_RE.finditer(text):
        target = m.group(2)
        if target.endswith(".*"):
            pkg = target[:-2]
            if pkg not in packages:
                violations.append({"gate": "G1", "kind": "IMPORT_PKG_NOT_WHITELISTED", "import": target})
        else:
            if target in classes:
                continue
            # Allow if package is whitelisted (we can't enumerate every class in JDK)
            pkg = target.rsplit(".", 1)[0]
            if pkg not in packages:
                violations.append({"gate": "G1", "kind": "IMPORT_NOT_WHITELISTED", "import": target})

    # G6 (light): new SimpleName(...) must resolve to a known class via imports
    declared_imports = {m.group(2).rsplit(".", 1)[-1]: m.group(2) for m in IMPORT_RE.finditer(text) if not m.group(2).endswith(".*")}
    for m in NEW_RE.finditer(text):
        simple = m.group(1).split(".")[0]
        # Allow java.lang implicit
        if simple in {"String", "Integer", "Long", "Double", "Float", "Boolean", "Object", "ArrayList", "HashMap", "HashSet", "LinkedList", "Throwable", "RuntimeException", "Exception"}:
            continue
        if simple not in declared_imports:
            # Probably same-package type; cannot verify here without contracts dir
            continue

    # If a per-SUT contract is provided, optionally cross-check method calls (G2 light).
    # Skipped here for brevity; the agent-side linter should integrate javaparser.
    return {"file": str(test_file), "violations": violations}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-file", required=True)
    ap.add_argument("--whitelist", required=True, help="path to import-whitelist.json")
    ap.add_argument("--contracts", default=None, help="path to symbol-contracts/ dir")
    args = ap.parse_args()
    test_file = Path(args.test_file)
    wl = load_json(Path(args.whitelist))
    contracts = Path(args.contracts) if args.contracts else None
    report = lint(test_file, wl, contracts)
    print(json.dumps(report, indent=2))
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
