"""state_validator.py — validate every state JSON against its schema."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import SCHEMAS_DIR


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True, help="state dir")
    args = ap.parse_args()
    try:
        import jsonschema  # type: ignore
    except ImportError:
        print("[FAIL] pip install jsonschema", file=sys.stderr)
        return 3
    state_dir = Path(args.state).resolve()
    rc = 0
    for schema_file in SCHEMAS_DIR.glob("*.schema.json"):
        name = schema_file.stem.replace(".schema", "")
        target = state_dir / f"{name}.json"
        if not target.exists():
            print(f"[SKIP] {name}.json missing")
            continue
        try:
            with target.open("r", encoding="utf-8") as f:
                data = json.load(f)
            with schema_file.open("r", encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(data, schema)
            print(f"[OK]   {target.name}")
        except Exception as e:
            print(f"[FAIL] {target.name}: {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
