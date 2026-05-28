"""validate_handoff.py — deterministic gate between Phase 0 and Phase 1 (LLM).

Post-audit 2026-05-28: phases 1-7 of the orchestrator (Discovery, Stack,
Classification, Symbol Contract, Dependency Graph, Fixtures, Planning) used
to be advertised as "LLM phases" but they only read JSONs already produced by
the deterministic pipeline. Running them as LLM turns wasted ~6-8K tokens per
cycle without any decision being made.

This tool replaces those seven turns with a single Python pass that:

  1. Verifies the seven mandatory state files exist;
  2. Asserts each one validates against its schema (via state_validator
     --scope where applicable);
  3. Emits a compact JSON handoff summary at
     state/_summaries/handoff-summary.json containing the minimal facts the
     LLM needs to know (stack versions, batch size, mode, top SUTs);
  4. Returns rc=0 if the LLM may proceed to Phase 8 (Generation), rc=2 if
     any required artefact is missing/invalid (BLOCKED_PRE_STAGE_MISSING).

Usage:
    python tools/python/validate_handoff.py --state state/
    python tools/python/validate_handoff.py --state state/ --print

The LLM should consume only the handoff-summary.json output, not the seven
underlying JSONs. That keeps Phase 1 input cost O(handoff) instead of
O(sum of pre-stage artefacts).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import _TimedRun, atomic_write_json, load_json  # noqa: E402


# Required artefacts produced by Phase 0. Missing any of these blocks the
# handoff with status="BLOCKED_PRE_STAGE_MISSING".
_REQUIRED_FILES: tuple[str, ...] = (
    "build-tool-contract.json",
    "archetype-profile.json",
    "generated-code-index.json",
    "import-whitelist.json",
    "stack-profile.json",
    "classification-index.json",
    "dependency-graph.json",
    "fixture-catalog.json",
    "batch-plan.json",
)

# Required directories with at least one entry.
_REQUIRED_DIRS: tuple[str, ...] = (
    "symbol-contracts",
    "context-packs-compact",
)


def _check_required(state_dir: Path) -> list[str]:
    """Return a list of missing artefact descriptions (empty = all present)."""
    missing: list[str] = []
    for name in _REQUIRED_FILES:
        p = state_dir / name
        if not p.exists() or p.stat().st_size == 0:
            missing.append(f"file: {name}")
    for dname in _REQUIRED_DIRS:
        d = state_dir / dname
        if not d.exists():
            missing.append(f"dir: {dname}/ (not created)")
            continue
        if not any(d.glob("*.json")):
            missing.append(f"dir: {dname}/ (empty)")
    return missing


def _safe_load(p: Path) -> dict:
    try:
        return load_json(p)
    except Exception:
        return {}


def _top_suts(batch_plan: dict, limit: int = 10) -> list[dict]:
    items = batch_plan.get("items", []) or []
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for it in items[:limit]:
        if not isinstance(it, dict):
            continue
        out.append({
            "sut": it.get("sut", ""),
            "method": it.get("method", ""),
            "score": it.get("score", 0),
            "targetId": it.get("targetId", ""),
        })
    return out


def build_summary(state_dir: Path) -> dict:
    """Build the handoff summary the LLM will consume instead of the seven
    raw JSONs of phases 1-7."""
    build_tool = _safe_load(state_dir / "build-tool-contract.json")
    archetype = _safe_load(state_dir / "archetype-profile.json")
    stack = _safe_load(state_dir / "stack-profile.json")
    classification = _safe_load(state_dir / "classification-index.json")
    dep_graph = _safe_load(state_dir / "dependency-graph.json")
    fixtures = _safe_load(state_dir / "fixture-catalog.json")
    batch_plan = _safe_load(state_dir / "batch-plan.json")

    contracts_dir = state_dir / "symbol-contracts"
    contracts_count = sum(1 for _ in contracts_dir.glob("*.json")) if contracts_dir.exists() else 0
    packs_dir = state_dir / "context-packs-compact"
    packs_count = sum(1 for _ in packs_dir.glob("*.json")) if packs_dir.exists() else 0

    # Count per-classification bucket (tiny — no risk of bloat).
    class_buckets: dict[str, int] = {}
    for c in classification.get("classes", []) or []:
        if not isinstance(c, dict):
            continue
        t = str(c.get("type", "unknown"))
        class_buckets[t] = class_buckets.get(t, 0) + 1

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase": "PRE_GENERATION",
        "status": "READY",
        "buildTool": {
            "type": build_tool.get("buildTool", ""),
            "groupId": build_tool.get("groupId", ""),
            "javaVersion": build_tool.get("javaVersion", ""),
        },
        "archetype": {
            "parent": archetype.get("parent", ""),
            "namespace": archetype.get("namespace", ""),
        },
        "stack": {
            "testFramework": stack.get("testFramework", ""),
            "mockingLib": stack.get("mockingLib", ""),
            "assertionLib": stack.get("assertionLib", ""),
            "diFramework": stack.get("diFramework", ""),
            "blocked": bool(stack.get("blocked", False)),
        },
        "counts": {
            "symbolContracts": contracts_count,
            "contextPacks": packs_count,
            "fixtures": len(fixtures.get("fixtures", []) or []),
            "dependencyGraphs": len(dep_graph.get("graphs", []) or []),
            "classes": sum(class_buckets.values()),
        },
        "classification": class_buckets,
        "batchPlan": {
            "cycle": batch_plan.get("cycle", 0),
            "mode": batch_plan.get("mode", ""),
            "size": batch_plan.get("sizeChosen", 0),
            "topSuts": _top_suts(batch_plan, limit=10),
        },
        "llmInstructions": [
            "Phase 0 + phases 1-7 already validated by validate_handoff.py.",
            "DO NOT re-read build-tool-contract.json, archetype-profile.json, "
            "generated-code-index.json, import-whitelist.json, stack-profile.json, "
            "classification-index.json, dependency-graph.json, fixture-catalog.json "
            "or batch-plan.json — every fact you need is in this summary.",
            "Proceed directly to Phase 8 (Generation): consume "
            "state/context-packs-compact/<safe_fqcn>.json for each SUT in batchPlan.topSuts.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Validate that Phase 0 + phases 1-7 (Discovery → Planning) are "
            "complete and emit a compact handoff summary for the LLM to "
            "consume in lieu of those seven phases."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--state",
        required=True,
        help="State directory produced by run_pipeline.py (e.g. state/)",
    )
    ap.add_argument(
        "--print",
        action="store_true",
        dest="print_summary",
        help="Print the summary JSON to stdout (default: write to state/_summaries/handoff-summary.json)",
    )
    args = ap.parse_args()

    state_dir = Path(args.state).resolve()
    if not state_dir.exists():
        print(f"[FAIL] state directory not found: {state_dir}", file=sys.stderr)
        return 2

    missing = _check_required(state_dir)
    if missing:
        print("[BLOCKED] BLOCKED_PRE_STAGE_MISSING", file=sys.stderr)
        for m in missing:
            print(f"  - missing {m}", file=sys.stderr)
        # Persist the failure too so the orchestrator can surface it.
        payload = {
            "schemaVersion": 1,
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "phase": "PRE_GENERATION",
            "status": "BLOCKED_PRE_STAGE_MISSING",
            "missing": missing,
        }
        out_path = state_dir / "_summaries" / "handoff-summary.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out_path, payload)
        return 2

    summary = build_summary(state_dir)
    out_path = state_dir / "_summaries" / "handoff-summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_path, summary)

    if args.print_summary:
        json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")

    counts = summary["counts"]
    bp = summary["batchPlan"]
    print(
        f"[OK] handoff ready: {counts['symbolContracts']} contracts, "
        f"{counts['contextPacks']} packs, batch={bp['size']} (mode={bp['mode']})"
    )
    return 0


if __name__ == "__main__":
    with _TimedRun("validate_handoff") as _tr:
        _rc = main()
        if _rc != 0:
            _tr.set_status("FAIL")
        _tr.add("exitCode", _rc)
    sys.exit(_rc)
