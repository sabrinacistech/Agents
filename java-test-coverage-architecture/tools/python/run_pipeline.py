"""run_pipeline.py — orchestrate the deterministic Python pre-stage.

Runs:
  1. pom_parser              -> state/build-tool-contract.json
  2. archetype_detector      -> state/archetype-profile.json
  3. generated_code_scanner  -> state/generated-code-index.json
  4. classpath_resolver      -> state/import-whitelist.json
  5. bytecode_scanner        -> state/symbol-contracts/<fqcn>.json   (per module if --include given)
  6. source_symbol_enricher  -> enrich contracts with FreeBuilder/source-only semantics
  7. jacoco_parser (targets) -> state/coverage-targets.json          (if jacoco.xml exists)
  8. semantic_index_writer   -> state/index/{classes,methods,imports,dependencies,annotations}.json  [Phase 1]
  9. incremental_map_writer  -> state/incremental-map.json           (if --since provided)           [Phase 3]
 10. state_validator         -> validates everything

After this, the LLM only consumes state/*.json. Token consumption drops because
no agent re-parses POMs, classpath, javap output or jacoco XML.

Phase 1 (semantic index): step 8 projects all prior state into state/index/ so
agents query a single consistent index instead of re-reading raw sources —
eliminating O(agents × files) redundant reads.

Phase 3 (incremental): step 9 computes changed/affected scope from git diff when
--since is provided; orchestrator uses this to narrow compilation and JaCoCo runs.
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
    ap.add_argument("--coverage-mode", default="coverage",
                    choices=["coverage", "branch-coverage", "mutation-hardening"])
    ap.add_argument("--since", default=None,
                    help="git ref (commit/branch/tag) to compute incremental scope from "
                         "(e.g. HEAD~1, main). Enables Phase 3 incremental map.")
    ap.add_argument("--full-index", action="store_true",
                    help="Force full semantic index rebuild even if fingerprints match")
    ap.add_argument("--skip", nargs="*", default=[],
                    help="step names to skip: pom, archetype, generated, classpath, "
                         "bytecode, source, jacoco, index, incremental, validate")
    args = ap.parse_args()

    rc = 0

    # ── Step 1: POM / build tool contract ────────────────────────────────────
    if "pom" not in args.skip:
        rc |= run_step([HERE / "pom_parser.py", "--repo", args.repo, "--out", args.out])

    # ── Step 2: Archetype detection ───────────────────────────────────────────
    if "archetype" not in args.skip:
        rc |= run_step([HERE / "archetype_detector.py", "--repo", args.repo, "--out", args.out])

    # ── Step 3: Generated code scanner ───────────────────────────────────────
    if "generated" not in args.skip:
        rc |= run_step([HERE / "generated_code_scanner.py", "--repo", args.repo, "--out", args.out])

    # ── Step 4: Classpath resolver → import-whitelist.json ───────────────────
    if "classpath" not in args.skip:
        cp_args = [HERE / "classpath_resolver.py", "--repo", args.repo, "--out", args.out]
        if args.module:
            cp_args += ["--module", args.module]
        rc |= run_step(cp_args)

    # ── Step 5: Bytecode scanner → symbol-contracts/<fqcn>.json ─────────────
    if "bytecode" not in args.skip and args.module:
        rc |= run_step(
            [HERE / "bytecode_scanner.py", "--repo", args.repo, "--out", args.out,
             "--module", args.module, "--include", args.include_fqcn]
        )

    # ── Step 6: Source symbol enricher (FreeBuilder, Lombok, etc.) ───────────
    if "source" not in args.skip:
        source_args = [HERE / "source_symbol_enricher.py", "--repo", args.repo, "--out", args.out]
        if args.module:
            source_args += ["--module", args.module]
        rc |= run_step(source_args)

    # ── Step 7: JaCoCo parser → coverage-targets.json ────────────────────────
    if "jacoco" not in args.skip and args.jacoco_xml:
        rc |= run_step(
            [HERE / "jacoco_parser.py", "--mode", "targets", "--xml", args.jacoco_xml,
             "--out", str(Path(args.out) / "coverage-targets.json"),
             "--coverage-mode", args.coverage_mode]
        )

    # ── Step 8 [Phase 1]: Semantic index writer ───────────────────────────────
    # Projects all prior state into state/index/ — eliminates O(agents×files) reads.
    if "index" not in args.skip:
        idx_args = [HERE / "semantic_index_writer.py", "--out", args.out]
        if args.full_index:
            idx_args.append("--full")
        rc |= run_step(idx_args)

    # ── Step 9 [Phase 3]: Incremental map writer ──────────────────────────────
    # Computes changedFiles → affectedClasses → affectedTests scope from git diff.
    # Only runs when --since is supplied (skipped in CI full runs by default).
    if "incremental" not in args.skip and args.since:
        inc_args = [
            HERE / "incremental_map_writer.py",
            "--repo", args.repo,
            "--out", args.out,
            "--since", args.since,
        ]
        if args.module:
            inc_args += ["--module", args.module]
        rc |= run_step(inc_args)

    # ── Step 10: State validator ──────────────────────────────────────────────
    if "validate" not in args.skip:
        rc |= run_step([HERE / "state_validator.py", "--state", args.out])

    print("\nDone." if rc == 0 else "\nDone with errors.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
