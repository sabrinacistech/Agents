"""gate_runner.py — deterministic gate evaluator for a candidate patch.

Implements three real gates today:

  G1 (IMPORT_WHITELIST) — `patch.imports` must be a subset of the context
                          pack's `allowedImports`. Compact packs expose this
                          as `imp` (either a flat array or a prefix-compressed
                          {prefixes, leaves} object).
  G5 (STACK_PROFILE)    — context-pack stack must contain no "unknown" values
                          and `blocked` must not be true.
  G6 (TEST_LINT)        — when --test-file is supplied, invoke test_linter.py.

Gates not yet implemented are reported with status "NOT_IMPLEMENTED" together
with a reason; never a false PASS.

Output JSON:

  {
    "schemaVersion": 1,
    "status": "PASS|FAIL|NOT_IMPLEMENTED",
    "gates": {
      "G1": {"status": "...", "blockedReason"?, ...},
      ...,
      "G8": {"status": "NOT_IMPLEMENTED", "reason": "..."}
    },
    "blockedReason": "G1_IMPORT_NOT_WHITELISTED|G5_STACK_UNKNOWN|G6_LINTER_FAIL|null"
  }

Persisted to state/_summaries/gates.json.

Usage
-----
  python tools/python/gate_runner.py --state state \\
      --patch patch.json --context-pack pack.json [--test-file path]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import _TimedRun  # noqa: E402

_NOT_IMPLEMENTED: dict[str, str] = {
    "G2": "symbol-contract evidence cross-check not implemented yet",
    "G4": "fixture/strategy validation not implemented yet",
    "G7": "narrow-test-run gating not implemented yet",
    "G8": "JaCoCo coverage delta gating not implemented yet",
}


# ── helpers ────────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _patch_imports(patch: dict) -> list[str]:
    if isinstance(patch.get("imports"), list):
        return [str(s) for s in patch["imports"]]
    if isinstance(patch.get("allowedImports"), list):
        return [str(s) for s in patch["allowedImports"]]
    return []


def _expand_compact_imports(imp: object) -> list[str]:
    if isinstance(imp, list):
        return [str(s) for s in imp]
    if isinstance(imp, dict):
        prefixes = imp.get("prefixes", []) or []
        leaves = imp.get("leaves", {}) or {}
        result: list[str] = []
        for key, vals in leaves.items():
            try:
                idx = int(key)
                prefix = prefixes[idx]
            except (ValueError, IndexError, TypeError):
                prefix = key
            for leaf in vals:
                if prefix:
                    result.append(f"{prefix}.{leaf}" if leaf else prefix)
                else:
                    result.append(leaf)
        return result
    return []


def _context_pack_imports(pack: dict) -> list[str]:
    if isinstance(pack.get("allowedImports"), list):
        return [str(s) for s in pack["allowedImports"]]
    if "imp" in pack:
        return _expand_compact_imports(pack["imp"])
    return []


def _context_pack_stack(pack: dict) -> tuple[list[str], bool]:
    """Return (stack_value_strings, blocked_flag)."""
    blocked = bool(pack.get("blocked", False) or pack.get("blk", False))
    stack_values: list[str] = []
    if isinstance(pack.get("stack"), dict):
        for v in pack["stack"].values():
            if v is None:
                continue
            stack_values.append(str(v))
    elif isinstance(pack.get("stk"), list):
        for v in pack["stk"]:
            if v is None:
                continue
            stack_values.append(str(v))
    return stack_values, blocked


# ── gate implementations ──────────────────────────────────────────────────────

def gate_g1(patch: dict, pack: dict) -> dict:
    patch_imports = set(_patch_imports(patch))
    allowed = set(_context_pack_imports(pack))
    if not patch_imports:
        return {"status": "PASS", "detail": "patch declares no imports"}
    missing = sorted(patch_imports - allowed)
    if missing:
        return {
            "status": "FAIL",
            "blockedReason": "G1_IMPORT_NOT_WHITELISTED",
            "missing": missing,
        }
    return {"status": "PASS", "checked": len(patch_imports)}


def gate_g5(pack: dict) -> dict:
    stack_values, blocked = _context_pack_stack(pack)
    if blocked:
        return {
            "status": "FAIL",
            "blockedReason": "G5_STACK_UNKNOWN",
            "reason": "context-pack is blocked",
        }
    unknown = [v for v in stack_values if v.lower() == "unknown"]
    if unknown:
        return {
            "status": "FAIL",
            "blockedReason": "G5_STACK_UNKNOWN",
            "unknownValues": unknown,
        }
    return {"status": "PASS", "checked": len(stack_values)}


def gate_g6(state_dir: Path, test_file: Path | None) -> dict:
    if test_file is None:
        return {"status": "SKIPPED", "reason": "no --test-file supplied"}
    linter = HERE / "test_linter.py"
    if not linter.exists():
        return {"status": "NOT_IMPLEMENTED", "reason": "test_linter.py missing"}
    if not test_file.exists():
        return {
            "status": "FAIL",
            "blockedReason": "G6_LINTER_FAIL",
            "reason": f"test file not found: {test_file}",
        }
    cmd = [
        sys.executable,
        str(linter),
        "--test-file", str(test_file),
        "--whitelist", str(state_dir / "import-whitelist.json"),
        "--contracts", str(state_dir / "symbol-contracts"),
        "--stack-profile", str(state_dir / "stack-profile.json"),
        "--index", str(state_dir / "index"),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception as exc:
        return {
            "status": "FAIL",
            "blockedReason": "G6_LINTER_FAIL",
            "reason": f"linter invocation failed: {exc}",
        }
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-20:]
        return {
            "status": "FAIL",
            "blockedReason": "G6_LINTER_FAIL",
            "exitCode": proc.returncode,
            "tail": tail,
        }
    return {"status": "PASS"}


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run deterministic gates G1..G8 over a candidate patch.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--state", default="state", help="State directory (default: state).")
    ap.add_argument("--patch", required=True, help="Path to the patch JSON.")
    ap.add_argument(
        "--context-pack",
        required=True,
        dest="context_pack",
        help="Path to the context-pack JSON (full or compact).",
    )
    ap.add_argument("--test-file", default=None, help="Path to the Java test file for G6.")
    args = ap.parse_args()

    state_dir = Path(args.state).resolve()

    try:
        patch = _load_json(Path(args.patch))
    except Exception as exc:
        print(f"[FAIL] cannot load patch: {exc}", file=sys.stderr)
        return 2
    try:
        pack = _load_json(Path(args.context_pack))
    except Exception as exc:
        print(f"[FAIL] cannot load context-pack: {exc}", file=sys.stderr)
        return 2

    test_file = Path(args.test_file).resolve() if args.test_file else None

    gates: dict[str, dict] = {}
    gates["G1"] = gate_g1(patch, pack)
    gates["G2"] = {"status": "NOT_IMPLEMENTED", "reason": _NOT_IMPLEMENTED["G2"]}
    gates["G4"] = {"status": "NOT_IMPLEMENTED", "reason": _NOT_IMPLEMENTED["G4"]}
    gates["G5"] = gate_g5(pack)
    gates["G6"] = gate_g6(state_dir, test_file)
    gates["G7"] = {"status": "NOT_IMPLEMENTED", "reason": _NOT_IMPLEMENTED["G7"]}
    gates["G8"] = {"status": "NOT_IMPLEMENTED", "reason": _NOT_IMPLEMENTED["G8"]}

    blocked_reason: str | None = None
    for key in ("G1", "G5", "G6"):
        g = gates.get(key, {})
        if g.get("status") == "FAIL":
            blocked_reason = g.get("blockedReason") or f"{key}_FAIL"
            break

    if blocked_reason:
        status = "FAIL"
    elif any(g.get("status") == "PASS" for g in gates.values()):
        status = "PASS"
    else:
        status = "NOT_IMPLEMENTED"

    report = {
        "schemaVersion": 1,
        "status": status,
        "gates": gates,
        "blockedReason": blocked_reason,
    }

    summaries = state_dir / "_summaries"
    summaries.mkdir(parents=True, exist_ok=True)
    out_path = summaries / "gates.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    with _TimedRun("gate_runner") as _tr:
        _rc = main()
        if _rc != 0:
            _tr.set_status("FAIL")
        _tr.add("exitCode", _rc)
    sys.exit(_rc)
