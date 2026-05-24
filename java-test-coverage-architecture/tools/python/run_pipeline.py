"""run_pipeline.py — orchestrate the deterministic Python pre-stage.

Runs:
  1. pom_parser              -> state/build-tool-contract.json
  2. archetype_detector      -> state/archetype-profile.json
  3. generated_code_scanner  -> state/generated-code-index.json
  4. classpath_resolver      -> state/import-whitelist.json
  5. bytecode_scanner        -> state/symbol-contracts/<fqcn>.json   (per module if --include given)
  6. jacoco_parser (targets) -> state/coverage-targets.json          (if jacoco.xml exists)
  7. state_validator         -> validates everything

After this, the LLM only consumes state/*.json. Token consumption drops because
no agent re-parses POMs, classpath, javap output or jacoco XML.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_step(args: list[str]) -> int:
    print(f"\n$ python {' '.join(str(a) for a in args)}")
    return subprocess.call([sys.executable, *[str(a) for a in args]])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True, help="state dir")
    ap.add_argument("--module", default=None, help="restrict to one module name")
    ap.add_argument("--include-fqcn", default=".*", help="regex filter for bytecode scan")
    ap.add_argument("--jacoco-xml", default=None, help="path to jacoco.xml (optional)")
    ap.add_argument("--coverage-mode", default="coverage", choices=["coverage", "branch-coverage", "mutation-hardening"])
    ap.add_argument("--skip", nargs="*", default=[], help="step names to skip (pom, archetype, generated, classpath, bytecode, jacoco, validate)")
    args = ap.parse_args()

    rc = 0
    if "pom" not in args.skip:
        rc |= run_step([HERE / "pom_parser.py", "--repo", args.repo, "--out", args.out])
    if "archetype" not in args.skip:
        rc |= run_step([HERE / "archetype_detector.py", "--repo", args.repo, "--out", args.out])
    if "generated" not in args.skip:
        rc |= run_step([HERE / "generated_code_scanner.py", "--repo", args.repo, "--out", args.out])
    if "classpath" not in args.skip:
        cp_args = [HERE / "classpath_resolver.py", "--repo", args.repo, "--out", args.out]
        if args.module:
            cp_args += ["--module", args.module]
        rc |= run_step(cp_args)
    if "bytecode" not in args.skip and args.module:
        rc |= run_step(
            [HERE / "bytecode_scanner.py", "--repo", args.repo, "--out", args.out,
             "--module", args.module, "--include", args.include_fqcn]
        )
    if "jacoco" not in args.skip and args.jacoco_xml:
        rc |= run_step(
            [HERE / "jacoco_parser.py", "--mode", "targets", "--xml", args.jacoco_xml,
             "--out", str(Path(args.out) / "coverage-targets.json"),
             "--coverage-mode", args.coverage_mode]
        )
    if "validate" not in args.skip:
        rc |= run_step([HERE / "state_validator.py", "--state", args.out])
    print("\nDone." if rc == 0 else "\nDone with errors.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
