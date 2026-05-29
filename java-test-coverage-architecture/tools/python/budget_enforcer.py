"""budget_enforcer.py — runtime enforcement of execution-state budget.

`execution-state.json` declares `budget.maxCycles` and `budget.maxMinutesPerCycle`
but until now no tool checked them at runtime. This module closes that gap so
runaway cycles abort by construction, not by LLM convention.

Subcommands
-----------
  check  → verify current state is within budget; exits 0 (ok) or 2 (exceeded)
  tick   → increment cycle counter and stamp cycleStartedAt
  reset  → clear cycleStartedAt (used at end of cycle)

Usage
-----
  python tools/python/budget_enforcer.py check --state state/execution-state.json
  python tools/python/budget_enforcer.py tick  --state state/execution-state.json
  python tools/python/budget_enforcer.py reset --state state/execution-state.json

Exit codes
----------
  0  within budget
  2  budget exceeded (caller MUST abort current cycle)
  3  malformed state (missing required fields)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import atomic_write_json, emit_tool_summary  # noqa: E402

EXIT_OK = 0
EXIT_EXCEEDED = 2
EXIT_MALFORMED = 3

DEFAULT_MAX_CYCLES = 20
DEFAULT_MAX_MINUTES_PER_CYCLE = 10


def _load(state_path: Path) -> dict:
    if not state_path.exists():
        return {"schemaVersion": 1, "cycle": 0, "budget": {}}
    return json.loads(state_path.read_text(encoding="utf-8"))


def check(state_path: Path) -> tuple[int, dict]:
    state = _load(state_path)
    budget = state.get("budget", {}) or {}
    cycle = int(state.get("cycle", 0))
    max_cycles = int(budget.get("maxCycles", DEFAULT_MAX_CYCLES))
    max_minutes = float(budget.get("maxMinutesPerCycle", DEFAULT_MAX_MINUTES_PER_CYCLE))

    # `cycle` is the 1-based number of the cycle currently in progress: cycle_runner
    # ticks it at cycle entry (tick BEFORE check), and test_patch_applier reads it
    # mid-cycle. Blocking on strictly-greater-than means cycles 1..maxCycles run and
    # the (maxCycles+1)th is refused — no off-by-one provided callers tick first.
    if cycle > max_cycles:
        return EXIT_EXCEEDED, {
            "ok": False, "reason": "maxCycles", "cycle": cycle, "maxCycles": max_cycles,
        }

    started = state.get("cycleStartedAt")
    if started is not None:
        elapsed_min = (time.time() - float(started)) / 60.0
        if elapsed_min > max_minutes:
            return EXIT_EXCEEDED, {
                "ok": False, "reason": "maxMinutesPerCycle",
                "elapsedMinutes": round(elapsed_min, 2), "maxMinutesPerCycle": max_minutes,
                "cycle": cycle,
            }

    return EXIT_OK, {
        "ok": True, "cycle": cycle, "maxCycles": max_cycles,
        "maxMinutesPerCycle": max_minutes,
    }


def tick(state_path: Path) -> tuple[int, dict]:
    state = _load(state_path)
    state["cycle"] = int(state.get("cycle", 0)) + 1
    state["cycleStartedAt"] = time.time()
    atomic_write_json(state_path, state)
    return EXIT_OK, {"ok": True, "cycle": state["cycle"], "cycleStartedAt": state["cycleStartedAt"]}


def reset(state_path: Path) -> tuple[int, dict]:
    state = _load(state_path)
    state.pop("cycleStartedAt", None)
    atomic_write_json(state_path, state)
    return EXIT_OK, {"ok": True, "cycle": int(state.get("cycle", 0))}


_DISPATCH = {"check": check, "tick": tick, "reset": reset}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Enforce execution-state.json budget at runtime.")
    p.add_argument("action", choices=list(_DISPATCH))
    p.add_argument("--state", required=True, type=Path,
                   help="Path to state/execution-state.json")
    args = p.parse_args(argv)

    try:
        rc, payload = _DISPATCH[args.action](args.state)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        emit_tool_summary("budget_enforcer", "MALFORMED", error=str(e))
        return EXIT_MALFORMED

    status = "OK" if rc == EXIT_OK else "EXCEEDED"
    emit_tool_summary("budget_enforcer", status, **payload)
    return rc


if __name__ == "__main__":
    sys.exit(main())
