#!/usr/bin/env bash
# =============================================================================
#  tools/runner-java.sh — Java/Maven coverage runner
#
#  Strategy: invokes JaCoCo via Maven's plugin goal injection.
#    • NEVER edits pom.xml — the plugin is called inline via CLI.
#    • All output lands in agents/outputs/java/<timestamp>/, not in the project.
#    • Works with either the project's mvnw wrapper or a system-level mvn.
# =============================================================================
set -euo pipefail

# ── Parse arguments forwarded by start.sh ────────────────────────────────────
TARGET_PATH=""; OUTPUT_PATH=""; AGENTS_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target=*)    TARGET_PATH="${1#--target=}";    shift ;;
    --output=*)    OUTPUT_PATH="${1#--output=}";    shift ;;
    --agents-dir=*) AGENTS_DIR="${1#--agents-dir=}"; shift ;;
    *) shift ;;
  esac
done

source "${AGENTS_DIR}/lib/utils.sh"

# ── Per-run report directory (timestamped, inside agents/outputs/) ────────────
REPORT_DIR="${OUTPUT_PATH}/java/$(timestamp)"
mkdir -p "${REPORT_DIR}"

log_section "Java/Maven Coverage Runner"
log_info "Target      : ${TARGET_PATH}"
log_info "Reports →   : ${REPORT_DIR}"

# ── Resolve Maven executable (wrapper wins over global) ──────────────────────
MVN_CMD=""
if [[ -f "${TARGET_PATH}/mvnw" ]]; then
  MVN_CMD="${TARGET_PATH}/mvnw"
  chmod +x "${MVN_CMD}"
  log_info "Using Maven wrapper: ./mvnw"
elif command -v mvn &>/dev/null; then
  MVN_CMD="mvn"
  log_info "Using system mvn: $(mvn --version | head -1)"
elif command -v mvn.cmd &>/dev/null; then
  # Windows — Maven is installed as mvn.cmd
  MVN_CMD="mvn.cmd"
  log_info "Using Windows system mvn.cmd"
else
  log_error "No Maven executable found (tried: mvnw, mvn, mvn.cmd)."
  log_error "Install Maven or add mvnw to the project root."
  exit 1
fi

# ── Run JaCoCo without touching pom.xml ──────────────────────────────────────
#
#  How the no-pom-edit technique works:
#    1. jacoco:prepare-agent  → attaches the JaCoCo Java agent at JVM startup.
#    2. test                  → runs the project's existing unit tests.
#    3. jacoco:report         → generates HTML/XML reports from the .exec file.
#
#  Key flags:
#    -Djacoco.destFile   → write .exec data file into agents/outputs/, not target/.
#    -Djacoco.reportPath → write HTML report into agents/outputs/.
#    --batch-mode        → non-interactive (CI-friendly).
# ─────────────────────────────────────────────────────────────────────────────
log_info "Running: jacoco:prepare-agent + test + jacoco:report"
log_info "(No pom.xml modification — plugin invoked via CLI goal injection)"
echo ""

(
  cd "${TARGET_PATH}"

  "${MVN_CMD}" \
    org.jacoco:jacoco-maven-plugin:prepare-agent \
    test \
    org.jacoco:jacoco-maven-plugin:report \
    "-Djacoco.destFile=${REPORT_DIR}/jacoco.exec" \
    "-Djacoco.outputDirectory=${REPORT_DIR}/html" \
    --batch-mode \
    --no-transfer-progress \
    2>&1 | tee "${REPORT_DIR}/maven-output.log"
)

echo ""
log_success "HTML report : ${REPORT_DIR}/html/index.html"
log_success "Exec data   : ${REPORT_DIR}/jacoco.exec"
log_success "Build log   : ${REPORT_DIR}/maven-output.log"
