"""cycle_runner.py — wrap a single cycle of work with budget enforcement.

The audit on 2026-05-29 confirmed that `budget_enforcer.py` was never invoked.
The execution-state budget (maxCycles, maxMinutesPerCycle) was therefore
advisory only — a runaway repair loop could never abort by construction.

This runner closes that gap:

  1. `budget_enforcer tick`  — enter the cycle: increment the counter (so it is
     the 1-based number of the cycle about to run) and stamp start time.
  2. `budget_enforcer check` — abort with rc=2 if that cycle exceeds the budget
     (BUDGET_EXCEEDED). Checking AFTER tick blocks the (maxCycles+1)th cycle
     exactly — no off-by-one extra cycle (audit M1).
  3. Exec the user-supplied command.
  4. Always `budget_enforcer reset` — clear cycleStartedAt so the next cycle's
     elapsed-time check is correct, even if the command crashed.

tick/reset return codes are honored: a malformed state at tick aborts the cycle
rather than running blind (audit M2).

Exit code is the command's exit code, or one of:
  2 — budget exceeded before cycle started, or the inner command was missing
  3 — execution-state malformed (propagated from budget_enforcer)

Usage
-----
  python tools/python/cycle_runner.py \\
      --state ../.agent-state/execution-state.json \\
      -- python tools/python/gate_runner.py --state ../.agent-state ...

The `--` separator is required; everything after it is the command to run.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import _TimedRun  # noqa: E402

_ENFORCER = HERE / "budget_enforcer.py"


def _run_enforcer(action: str, state_path: Path) -> int:
    return subprocess.run(
        [sys.executable, str(_ENFORCER), action, "--state", str(state_path)],
        check=False,
    ).returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run a single cycle of work bracketed by budget_enforcer hooks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--state",
        required=True,
        type=Path,
        help="Path to execution-state.json (where the budget is declared).",
    )
    ap.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="The command to run for this cycle. Prefix with `--` to separate.",
    )
    args = ap.parse_args(argv)

    cmd = args.command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("[FAIL] no command supplied after --", file=sys.stderr)
        return 2

    # Enter the next cycle (tick), THEN verify it is within budget. Ticking
    # first makes `cycle` the 1-based number of the cycle about to run, so the
    # check blocks the (maxCycles+1)th cycle exactly (audit M1).
    trc = _run_enforcer("tick", args.state)
    if trc != 0:
        print(f"[FAIL] budget tick failed (rc={trc}); aborting cycle.", file=sys.stderr)
        _run_enforcer("reset", args.state)
        return trc

    crc = _run_enforcer("check", args.state)
    if crc != 0:
        print(f"[BLOCKED] budget exceeded for this cycle (rc={crc}); not running.",
              file=sys.stderr)
        _run_enforcer("reset", args.state)
        return crc

    try:
        proc = subprocess.run(cmd, check=False)
        cmd_rc = proc.returncode
    finally:
        rrc = _run_enforcer("reset", args.state)
        if rrc != 0:
            print(f"[WARN] budget reset failed (rc={rrc}); next cycle's "
                  f"elapsed-time check may be inaccurate.", file=sys.stderr)

    return cmd_rc


if __name__ == "__main__":
    with _TimedRun("cycle_runner") as _tr:
        _rc = main()
        if _rc != 0:
            _tr.set_status("FAIL")
        _tr.add("exitCode", _rc)
    sys.exit(_rc)
