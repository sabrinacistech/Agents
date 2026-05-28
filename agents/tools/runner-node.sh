#!/usr/bin/env bash
# =============================================================================
#  tools/runner-node.sh — Node.js coverage runner
#
#  Strategy: injects coverage flags and output paths via ENVIRONMENT VARIABLES
#  and CLI flags — never edits package.json or installs global packages.
#
#  Supports:
#    • Jest  (--coverage --coverageDirectory flags)
#    • Vitest (--coverage CLI flag + VITEST_COVERAGE_REPORTER env)
#    • nyc/Istanbul standalone (via NYC_* env vars)
# =============================================================================
set -euo pipefail

# ── Parse arguments forwarded by start.sh ────────────────────────────────────
TARGET_PATH=""; OUTPUT_PATH=""; AGENTS_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target=*)     TARGET_PATH="${1#--target=}";    shift ;;
    --output=*)     OUTPUT_PATH="${1#--output=}";    shift ;;
    --agents-dir=*) AGENTS_DIR="${1#--agents-dir=}"; shift ;;
    *) shift ;;
  esac
done

source "${AGENTS_DIR}/lib/utils.sh"

REPORT_DIR="${OUTPUT_PATH}/node/$(timestamp)"
mkdir -p "${REPORT_DIR}"

log_section "Node.js Coverage Runner"
log_info "Target      : ${TARGET_PATH}"
log_info "Reports →   : ${REPORT_DIR}"

# ── Detect package manager ────────────────────────────────────────────────────
if [[ -f "${TARGET_PATH}/pnpm-lock.yaml" ]]; then
  PKG_MGR="pnpm"
elif [[ -f "${TARGET_PATH}/yarn.lock" ]]; then
  PKG_MGR="yarn"
else
  PKG_MGR="npm"
fi
log_info "Package manager: ${PKG_MGR}"

# ── Detect test runner via package.json ───────────────────────────────────────
detect_test_runner() {
  local pkg="${TARGET_PATH}/package.json"
  if grep -q '"jest"'   "${pkg}" 2>/dev/null; then echo "jest";   return; fi
  if grep -q '"vitest"' "${pkg}" 2>/dev/null; then echo "vitest"; return; fi
  if grep -q '"mocha"'  "${pkg}" 2>/dev/null; then echo "mocha";  return; fi
  echo "jest"   # safe default
}

TEST_RUNNER="$(detect_test_runner)"
log_info "Test runner: ${TEST_RUNNER}"

# ── Resolve which npm script to call ─────────────────────────────────────────
SCRIPT="test"
if grep -q '"test:coverage"' "${TARGET_PATH}/package.json" 2>/dev/null; then
  SCRIPT="test:coverage"
elif grep -q '"test:ci"' "${TARGET_PATH}/package.json" 2>/dev/null; then
  SCRIPT="test:ci"
fi
log_info "npm script: ${PKG_MGR} run ${SCRIPT}"

# ── Build runner-specific extra flags ────────────────────────────────────────
#
#  Key principle: all coverage flags are passed as EXTRA ARGS after "--"
#  (the standard npm/yarn/pnpm passthrough separator).  The project's own
#  test script is not changed.
# ─────────────────────────────────────────────────────────────────────────────
EXTRA_FLAGS=()
case "${TEST_RUNNER}" in
  jest)
    EXTRA_FLAGS+=(
      "--coverage"
      "--coverageDirectory=${REPORT_DIR}/html"
      "--coverageReporters=html"
      "--coverageReporters=lcov"
      "--coverageReporters=text-summary"
    )
    ;;
  vitest)
    EXTRA_FLAGS+=("--coverage")
    ;;
  mocha)
    # mocha delegates to nyc; control via env vars below
    ;;
esac

# ── NYC env vars (safe for all runners; ignored when nyc is not present) ─────
export NYC_OUTPUT_DIR="${REPORT_DIR}/.nyc_output"
export NYC_REPORT_DIR="${REPORT_DIR}/html"
export NYC_CWD="${TARGET_PATH}"

log_info "Running coverage (output redirected — no project files modified)"
echo ""

(
  cd "${TARGET_PATH}"

  "${PKG_MGR}" run "${SCRIPT}" -- "${EXTRA_FLAGS[@]}" \
    2>&1 | tee "${REPORT_DIR}/node-output.log" || {
      log_warn "Test run exited with non-zero status (coverage data may still be complete)."
    }
)

echo ""
log_success "HTML report : ${REPORT_DIR}/html"
log_success "LCOV report : ${REPORT_DIR}/html/lcov-report/index.html"
log_success "Run log     : ${REPORT_DIR}/node-output.log"
