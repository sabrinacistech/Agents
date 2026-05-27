#!/usr/bin/env bash
# =============================================================================
#  tools/runner-python.sh — Python coverage runner
#
#  Strategy: uses pytest-cov / coverage.py; all output is redirected OUT of
#  the project tree.  No requirements.txt or pyproject.toml is modified.
#
#  COVERAGE_FILE env var tells coverage.py where to write its data file,
#  so the .coverage file never appears inside the target project directory.
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

REPORT_DIR="${OUTPUT_PATH}/python/$(timestamp)"
mkdir -p "${REPORT_DIR}"

log_section "Python Coverage Runner"
log_info "Target      : ${TARGET_PATH}"
log_info "Reports →   : ${REPORT_DIR}"

# ── Resolve Python interpreter: project venv wins over system ─────────────────
PYTHON_CMD="python3"
for candidate in \
  "${TARGET_PATH}/.venv/bin/python" \
  "${TARGET_PATH}/venv/bin/python"
do
  if [[ -x "${candidate}" ]]; then
    PYTHON_CMD="${candidate}"
    log_info "Using project venv: ${PYTHON_CMD}"
    break
  fi
done

# Fall back to system python3 / python
if [[ "${PYTHON_CMD}" == "python3" ]]; then
  if ! command -v python3 &>/dev/null; then
    if command -v python &>/dev/null; then
      PYTHON_CMD="python"
    else
      log_error "No Python interpreter found (tried: project venv, python3, python)."
      exit 1
    fi
  fi
  log_info "Using system interpreter: $(${PYTHON_CMD} --version 2>&1)"
fi

# ── Verify pytest-cov is available (without installing globally) ──────────────
if ! "${PYTHON_CMD}" -c "import pytest_cov" &>/dev/null; then
  log_warn "pytest-cov not found in the selected interpreter."
  log_warn "Install it inside the project venv: pip install pytest-cov"
  log_warn "Attempting to continue — pytest will try to run without coverage."
fi

# ── Determine the source package to measure coverage against ─────────────────
#    Heuristic: first directory that looks like a Python source package
SOURCE_DIR="${TARGET_PATH}"
for candidate in src lib; do
  if [[ -d "${TARGET_PATH}/${candidate}" ]]; then
    SOURCE_DIR="${TARGET_PATH}/${candidate}"
    log_info "Source root: ${SOURCE_DIR}"
    break
  fi
done

# ── Run pytest with coverage.py ───────────────────────────────────────────────
#
#  Key flags:
#    COVERAGE_FILE  → data file goes into agents/outputs/, not project root.
#    --cov          → tells pytest-cov what to measure.
#    --cov-report   → all three formats (html, xml, terminal) in one pass.
# ─────────────────────────────────────────────────────────────────────────────
log_info "Running pytest + coverage.py (zero project file mutations)"
echo ""

(
  cd "${TARGET_PATH}"

  COVERAGE_FILE="${REPORT_DIR}/.coverage" \
  "${PYTHON_CMD}" -m pytest \
    --cov="${SOURCE_DIR}" \
    --cov-report="html:${REPORT_DIR}/html" \
    --cov-report="xml:${REPORT_DIR}/coverage.xml" \
    --cov-report=term \
    -v \
    2>&1 | tee "${REPORT_DIR}/pytest-output.log" || {
      log_warn "pytest exited with non-zero status (some tests may have failed)."
      log_warn "Coverage data is still written if any tests ran."
    }
)

echo ""
log_success "HTML report  : ${REPORT_DIR}/html/index.html"
log_success "XML report   : ${REPORT_DIR}/coverage.xml  (suitable for CI/SonarQube)"
log_success "Data file    : ${REPORT_DIR}/.coverage"
log_success "Run log      : ${REPORT_DIR}/pytest-output.log"
