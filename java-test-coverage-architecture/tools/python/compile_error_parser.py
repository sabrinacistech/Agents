"""compile_error_parser.py — parse Maven build log into state/compile-error-index.json."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from common import atomic_write_json, validate

ERROR_LINE = re.compile(
    r"^\[ERROR\]\s+(?P<file>[^:]+):\[(?P<line>\d+),(?P<col>\d+)\]\s+(?P<msg>.+)$"
)

PATTERNS = [
    ("E_PACKAGE_UNRESOLVED", re.compile(r"package\s+([\w\.]+)\s+does not exist")),
    ("E_INTERFACE_INSTANTIATION", re.compile(r"(\S+)\s+is abstract;\s+cannot be instantiated")),
    ("E_CONSTRUCTOR_UNRESOLVED", re.compile(r"constructor\s+(\S+)\s+in class\s+(\S+)\s+cannot be applied")),
    ("E_METHOD_UNRESOLVED", re.compile(r"cannot find symbol\s+method\s+(\w+)\(")),
    ("E_IMPORT_UNRESOLVED", re.compile(r"cannot find symbol\s+class\s+(\w+)")),
    ("E_TYPE_MISMATCH", re.compile(r"incompatible types:\s+(\S+)\s+cannot be converted to\s+(\S+)")),
    ("E_GENERIC_INFERENCE", re.compile(r"incompatible types:\s+inference variable")),
    ("E_VARARGS", re.compile(r"non-varargs call of varargs method")),
    ("E_OVERRIDE", re.compile(r"method does not override")),
    ("E_ACCESS", re.compile(r"(\S+)\s+has\s+(private|package)\s+access")),
]


def classify(msg: str) -> tuple[str, str | None]:
    for code, rx in PATTERNS:
        m = rx.search(msg)
        if m:
            return code, m.group(0)
    return "E_OTHER", None


def parse(log_path: Path, run_id: str) -> dict:
    errors = []
    eid = 0
    for raw in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = ERROR_LINE.match(raw)
        if not m:
            continue
        code, captured = classify(m.group("msg"))
        eid += 1
        errors.append(
            {
                "id": f"err:{eid:04d}",
                "code": code,
                "file": m.group("file"),
                "line": int(m.group("line")),
                "col": int(m.group("col")),
                "message": m.group("msg"),
                "symbolFQN": captured or "",
                "raw": raw,
            }
        )
    return {"schemaVersion": 1, "runId": run_id, "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--run", default="run-0")
    args = ap.parse_args()
    log = Path(args.log)
    if not log.exists():
        print("[FAIL] log not found", file=sys.stderr)
        return 2
    out = parse(log, args.run)
    validate("compile-error-index", out)
    atomic_write_json(Path(args.out), out)
    print(f"[OK] {len(out['errors'])} errors -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
