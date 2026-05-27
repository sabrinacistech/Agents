#!/usr/bin/env bash
# =============================================================================
#  tools/runner-java.sh — Java/Maven coverage runner
#
#  Pipeline (BOOT.md / java-test-coverage-architecture):
#    Step 1 — mvn -q -DskipTests package   → compile project + resolve classpath
#    Step 2 — mvn test                      → run tests, let pom.xml JaCoCo config
#                                             generate target/site/jacoco/jacoco.xml
#    Step 3 — python bootstrap.py           → Python pre-stage determinístico
#                                             produce state/*.json para agentes LLM
#
#  Nada del proyecto destino es modificado (no se toca pom.xml ni build.gradle).
# =============================================================================
set -euo pipefail

# ── Parse arguments forwarded by start.sh ────────────────────────────────────
TARGET_PATH=""; OUTPUT_PATH=""; AGENTS_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target=*)     TARGET_PATH="${1#--target=}";     shift ;;
    --output=*)     OUTPUT_PATH="${1#--output=}";     shift ;;
    --agents-dir=*) AGENTS_DIR="${1#--agents-dir=}";  shift ;;
    *) shift ;;
  esac
done

source "${AGENTS_DIR}/lib/utils.sh"

# ── Paths derived from agents/ root ──────────────────────────────────────────
ARCH_DIR="${AGENTS_DIR}/../java-test-coverage-architecture"
ARCH_DIR="$(cd "${ARCH_DIR}" && pwd)"          # absolute, no ..
TOOLS_PYTHON="${ARCH_DIR}/tools/python"
STATE_DIR="${ARCH_DIR}/state"

# Per-run archive directory (for logs + a snapshot of the state produced)
RUN_DIR="${OUTPUT_PATH}/java/$(timestamp)"
mkdir -p "${RUN_DIR}"

log_section "Java/Maven Coverage Runner"
log_info "Target          : ${TARGET_PATH}"
log_info "Architecture    : ${ARCH_DIR}"
log_info "State dir       : ${STATE_DIR}"
log_info "Run archive     : ${RUN_DIR}"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Resolve Maven executable
# ─────────────────────────────────────────────────────────────────────────────
log_section "Step 1 — Maven: compile (skip tests)"

MVN_CMD=""
if [[ -f "${TARGET_PATH}/mvnw" ]]; then
  MVN_CMD="${TARGET_PATH}/mvnw"
  chmod +x "${MVN_CMD}"
  log_info "Using Maven wrapper: ./mvnw"
elif command -v mvn &>/dev/null; then
  MVN_CMD="mvn"
  log_info "Using system mvn: $(mvn --version | head -1)"
elif command -v mvn.cmd &>/dev/null; then
  MVN_CMD="mvn.cmd"
  log_info "Using Windows mvn.cmd"
else
  log_error "No Maven executable found (tried: mvnw, mvn, mvn.cmd)."
  exit 1
fi

# Compile source + test-compile; skip test execution.
# This populates target/classes, target/test-classes and the .m2 cache
# so the Python classpath resolver can read the full dependency tree.
(
  cd "${TARGET_PATH}"
  "${MVN_CMD}" -q -DskipTests package \
    --batch-mode --no-transfer-progress \
    2>&1 | tee "${RUN_DIR}/mvn-package.log"
)
log_success "Compilation OK"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Run tests → JaCoCo XML
# ─────────────────────────────────────────────────────────────────────────────
log_section "Step 2 — Maven: verify (tests + JaCoCo report via pom.xml)"
log_info "Usando 'verify' para que JaCoCo ejecute su fase 'report' (bound a verify, no a test)."
log_info "Expected output: target/site/jacoco/jacoco.xml"

# mvn verify  = compile + test-compile + test + package + verify
# -DskipITs   = omite integration tests, corre solo unit tests
(
  cd "${TARGET_PATH}"
  "${MVN_CMD}" verify -DskipITs \
    --batch-mode --no-transfer-progress \
    2>&1 | tee "${RUN_DIR}/mvn-test.log"
)

JACOCO_XML="${TARGET_PATH}/target/site/jacoco/jacoco.xml"
if [[ -f "${JACOCO_XML}" ]]; then
  log_success "JaCoCo XML generated: ${JACOCO_XML}"
  cp "${JACOCO_XML}" "${RUN_DIR}/jacoco.xml"
else
  log_warn "jacoco.xml not found at ${JACOCO_XML}"
  log_warn "Tests may have no JaCoCo plugin configured. Continuing without XML."
fi

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Python pre-stage (bootstrap.py)
# ─────────────────────────────────────────────────────────────────────────────
log_section "Step 3 — Python pre-stage (bootstrap.py)"

# ── Resolve Python interpreter ────────────────────────────────────────────────
# Detection order (first match wins):
#   1. venv inside agents/          (portable, created once per team)
#   2. venv at repo root            (legacy location)
#   3. py   — Python Launcher for Windows (py.exe, most reliable on Win)
#   4. python                       (system Python, skips Win-Store stub)
#   5. python3                      (Linux/Mac)
# Windows Store stubs (python / python3 that open the Store) are detected by
# running --version and checking for exit code 9009 or empty output.

_python_works() {
  # Returns 0 if the interpreter actually runs (not a Store stub).
  local cmd="$1"
  local out
  out="$("${cmd}" --version 2>&1)" || return 1
  [[ "${out}" == Python* ]] || return 1
  return 0
}

PYTHON_CMD=""
# 1. venv inside agents/
if [[ -x "${AGENTS_DIR}/.venv/Scripts/python" ]]; then
  PYTHON_CMD="${AGENTS_DIR}/.venv/Scripts/python"
elif [[ -x "${AGENTS_DIR}/.venv/bin/python" ]]; then
  PYTHON_CMD="${AGENTS_DIR}/.venv/bin/python"
# 2. venv at repo root
elif [[ -x "${AGENTS_DIR}/../.venv/Scripts/python" ]]; then
  PYTHON_CMD="$(cd "${AGENTS_DIR}/.." && pwd)/.venv/Scripts/python"
elif [[ -x "${AGENTS_DIR}/../.venv/bin/python" ]]; then
  PYTHON_CMD="$(cd "${AGENTS_DIR}/.." && pwd)/.venv/bin/python"
# 3. py launcher (Windows — most reliable, never a Store stub)
elif command -v py &>/dev/null && _python_works py; then
  PYTHON_CMD="py"
# 4. python (system, works on Windows when Store alias is disabled)
elif command -v python &>/dev/null && _python_works python; then
  PYTHON_CMD="python"
# 5. python3 (Linux/Mac)
elif command -v python3 &>/dev/null && _python_works python3; then
  PYTHON_CMD="python3"
else
  log_error "No Python interpreter found or all available ones are Windows Store stubs."
  log_error "Soluciones:"
  log_error "  1. Instalá Python desde https://python.org (marcá 'Add to PATH')"
  log_error "  2. O deshabilitá los alias de la Store:"
  log_error "     Configuración > Aplicaciones > Alias de ejecución de aplicaciones"
  log_error "     → desactivá python.exe y python3.exe"
  exit 1
fi
log_info "Python: ${PYTHON_CMD} ($(${PYTHON_CMD} --version 2>&1))"

# ── Ensure dependencies are installed ────────────────────────────────────────
REQUIREMENTS="${TOOLS_PYTHON}/requirements.txt"
if [[ -f "${REQUIREMENTS}" ]]; then
  log_info "Checking Python dependencies..."
  "${PYTHON_CMD}" -m pip install -q -r "${REQUIREMENTS}" 2>&1 \
    | tee "${RUN_DIR}/pip-install.log" | grep -E "^(Installing|Requirement already)" || true
fi

# ── Run bootstrap.py (auto-detects module, groupId, jacoco-xml) ───────────────
log_info "Running: bootstrap.py --repo ${TARGET_PATH} --out ${STATE_DIR}"

(
  cd "${ARCH_DIR}"
  "${PYTHON_CMD}" "${TOOLS_PYTHON}/bootstrap.py" \
    --repo "${TARGET_PATH}" \
    --out  "${STATE_DIR}" \
    2>&1 | tee "${RUN_DIR}/bootstrap.log"
)
BOOTSTRAP_EXIT=${PIPESTATUS[0]}

# ── Archive a snapshot of state/*.json produced ───────────────────────────────
if [[ -d "${STATE_DIR}" ]]; then
  cp -r "${STATE_DIR}" "${RUN_DIR}/state-snapshot"
  log_success "State snapshot: ${RUN_DIR}/state-snapshot/"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
log_section "Coverage Pipeline — Summary"
log_info  "Run archive     : ${RUN_DIR}/"
log_info  "  mvn-package.log  — Maven compile log"
log_info  "  mvn-test.log     — Maven test + JaCoCo log"
log_info  "  bootstrap.log    — Python pipeline log"
log_info  "  state-snapshot/  — state/*.json producidos (listos para agentes LLM)"
[[ -f "${RUN_DIR}/jacoco.xml" ]] && log_success "  jacoco.xml       — reporte de cobertura JaCoCo"

if [[ ${BOOTSTRAP_EXIT} -eq 0 ]]; then
  log_success "Pipeline completado. Revisá ${STATE_DIR}/ para los JSON de estado."
else
  log_warn "Pipeline terminó con errores (exit ${BOOTSTRAP_EXIT})."
  log_warn "Revisá ${RUN_DIR}/bootstrap.log para el detalle."
  exit ${BOOTSTRAP_EXIT}
fi
