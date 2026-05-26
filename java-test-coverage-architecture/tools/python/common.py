"""Shared helpers for tools/python/*.

Keep this dependency-light. Only stdlib + jsonschema + lxml.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

SCHEMAS_DIR = Path(__file__).resolve().parents[1].parent / "state" / "_schemas"


# ── Structured logging (P4.0) ─────────────────────────────────────────────────

def emit_tool_summary(
    tool: str,
    status: str,
    artifacts: list | None = None,
    duration_ms: int | None = None,
    **extra: Any,
) -> None:
    """Emit a single-line JSON tool summary on stdout.

    Intended as the LAST line printed by a tool's main() so callers (e.g.
    orchestrators) can parse one structured record per invocation.
    """
    payload: dict[str, Any] = {"tool": tool, "status": status}
    if artifacts is not None:
        payload["artifacts"] = artifacts
    if duration_ms is not None:
        payload["durationMs"] = int(duration_ms)
    for k, v in extra.items():
        if v is not None:
            payload[k] = v
    print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))


class _TimedRun:
    """Context manager that times a tool invocation and emits a summary on exit.

    Usage:
        with _TimedRun("my_tool") as tr:
            ...
            tr.set_status("FAIL")           # optional override
            tr.set_artifacts([...])         # optional
            tr.add("extraField", value)     # optional kv pair
    Emits emit_tool_summary(tool, status, artifacts, duration_ms, **extra)
    on __exit__. status is "FAIL" if an exception propagates, otherwise the
    last value set (default "OK").
    """

    def __init__(self, tool: str) -> None:
        self.tool = tool
        self.status: str = "OK"
        self.artifacts: list | None = None
        self.extra: dict[str, Any] = {}
        self._t0: float = 0.0

    def __enter__(self) -> "_TimedRun":
        self._t0 = time.perf_counter()
        return self

    def set_status(self, status: str) -> None:
        self.status = status

    def set_artifacts(self, artifacts: list) -> None:
        self.artifacts = artifacts

    def add(self, key: str, value: Any) -> None:
        self.extra[key] = value

    def __exit__(self, exc_type, exc, tb) -> bool:
        duration_ms = int((time.perf_counter() - self._t0) * 1000)
        if exc_type is None:
            status = self.status
        elif issubclass(exc_type, SystemExit):
            code = getattr(exc, "code", 0)
            if isinstance(code, int):
                status = self.status if code == 0 else "FAIL"
            else:
                status = "FAIL" if code else self.status
        else:
            status = "FAIL"
        try:
            emit_tool_summary(
                self.tool,
                status,
                artifacts=self.artifacts,
                duration_ms=duration_ms,
                **self.extra,
            )
        except Exception:
            pass
        return False


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=False)
    os.replace(tmp, path)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate(state_name: str, data: Any) -> None:
    """Validate `data` against state/_schemas/<state_name>.schema.json.
    No-op if jsonschema is not installed.
    """
    try:
        import jsonschema  # type: ignore
    except Exception:
        return
    schema_path = SCHEMAS_DIR / f"{state_name}.schema.json"
    if not schema_path.exists():
        return
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(data, schema)


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout
    )


def find_tool(name: str) -> str:
    p = shutil.which(name)
    if not p:
        raise FileNotFoundError(f"Tool not on PATH: {name}")
    return p


def cache_get(state_dir: Path, key: str, input_hashes: dict[str, str]) -> Any | None:
    cache_file = state_dir / "_cache" / f"{key}.cache.json"
    if not cache_file.exists():
        return None
    try:
        c = load_json(cache_file)
    except Exception:
        return None
    if c.get("inputs") == input_hashes:
        return c.get("output")
    return None


def cache_put(state_dir: Path, key: str, input_hashes: dict[str, str], output: Any) -> None:
    cache_file = state_dir / "_cache" / f"{key}.cache.json"
    atomic_write_json(cache_file, {"inputs": input_hashes, "output": output})


def fail(msg: str, code: int = 2) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)
    sys.exit(code)


def find_pom_modules(repo: Path) -> list[Path]:
    """Best-effort list of Maven module directories (root + children with pom.xml)."""
    poms = list(repo.rglob("pom.xml"))
    # Skip generated/build dirs
    poms = [p for p in poms if "target" not in p.parts and "build" not in p.parts]
    return [p.parent for p in poms]
