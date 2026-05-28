#!/usr/bin/env bash
# =============================================================================
#  agents/start.sh — Portable test-coverage entry point
#
#  Design: "Caso 3 — start corre dentro de agents/"
#    • This script and all runners live exclusively inside agents/.
#    • The project to analyse is passed via --target; it is NEVER modified.
#    • Portability: clone agents/ anywhere, point --target at any project.
# =============================================================================
set -euo pipefail

# ── Locate agents/ root regardless of the caller's working directory ─────────
AGENTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${AGENTS_DIR}/lib/utils.sh"

# ── Internal constants ────────────────────────────────────────────────────────
readonly VERSION="1.0.0"
readonly TOOLS_DIR="${AGENTS_DIR}/tools"
readonly REPO_ROOT="${AGENTS_DIR}/.."

# ── Usage / help ──────────────────────────────────────────────────────────────
usage() {
  cat <<EOF

${BOLD}agents/start.sh${RESET}  —  Portable coverage/analysis entry point  v${VERSION}

${BOLD}USAGE${RESET}
  ./agents/start.sh --target=<path>  [options]
  ./agents/start.sh -t <path>        [options]

${BOLD}REQUIRED${RESET}
  -t, --target <path>
  -t, --target=<path>    Absolute or relative path to the project to analyse.
                         The project files are ${BOLD}never${RESET} modified.

${BOLD}OPTIONS${RESET}
  -o, --output <path>    Override the execution output directory.
                         Default: java-test-coverage-architecture_execution_<project>_<YYYYMMDD>/
      --dry-run          Detect project type and print the runner that would
                         be used, then exit without running anything.
  -v, --version          Print version and exit.
  -h, --help             Show this help and exit.

${BOLD}SUPPORTED PROJECT TYPES${RESET}
  java-maven  →  detects pom.xml            →  tools/runner-java.sh
  node        →  detects package.json       →  tools/runner-node.sh
  python      →  detects requirements.txt,
                           setup.py, or
                           pyproject.toml   →  tools/runner-python.sh

${BOLD}EXAMPLES${RESET}
  # Analyse a Node project using an absolute path
  ./agents/start.sh --target=/home/alice/workspace/my-app

  # Analyse a Maven project using a relative path
  ./agents/start.sh -t ../services/payments-service

  # Write reports to a custom directory
  ./agents/start.sh --target=/opt/apps/api --output=/tmp/ci-reports

  # Preview what would run without actually running it
  ./agents/start.sh --target=./sample-project --dry-run

EOF
}

# ── Argument parsing ──────────────────────────────────────────────────────────
TARGET_PATH=""
OUTPUT_PATH=""   # computed from project name + date after --target is known
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--target)
      [[ -z "${2:-}" ]] && { log_error "--target requires a value."; usage >&2; exit 1; }
      TARGET_PATH="$2"; shift 2 ;;
    --target=*)
      TARGET_PATH="${1#--target=}"; shift ;;
    -o|--output)
      [[ -z "${2:-}" ]] && { log_error "--output requires a value."; usage >&2; exit 1; }
      OUTPUT_PATH="$2"; shift 2 ;;
    --output=*)
      OUTPUT_PATH="${1#--output=}"; shift ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    -v|--version)
      echo "agents/start.sh v${VERSION}"; exit 0 ;;
    -h|--help)
      usage; exit 0 ;;
    -*)
      log_error "Unknown option: $1"; usage >&2; exit 1 ;;
    *)
      # Positional arg — treat as --target if TARGET_PATH is still empty
      if [[ -z "${TARGET_PATH}" ]]; then
        TARGET_PATH="$1"; shift
      else
        log_error "Unexpected positional argument: $1"; usage >&2; exit 1
      fi ;;
  esac
done

# ── Validate --target ─────────────────────────────────────────────────────────
if [[ -z "${TARGET_PATH}" ]]; then
  log_error "Missing required argument: --target"
  usage >&2
  exit 1
fi

require_dir "${TARGET_PATH}" "--target" || exit 1
TARGET_PATH="$(abspath "${TARGET_PATH}")"

# ── Compute execution folder (project name + date) if not overridden ──────────
if [[ -z "${OUTPUT_PATH}" ]]; then
  PROJECT_NAME="$(basename "${TARGET_PATH}")"
  TODAY="$(date +%Y%m%d)"
  OUTPUT_PATH="${REPO_ROOT}/java-test-coverage-architecture_execution_${PROJECT_NAME}_${TODAY}"
fi
mkdir -p "${OUTPUT_PATH}"
OUTPUT_PATH="$(abspath "${OUTPUT_PATH}")"

# ── Project type detection ────────────────────────────────────────────────────
detect_project_type() {
  local dir="$1"

  [[ -f "${dir}/pom.xml" ]]                                       && { echo "java-maven"; return; }
  [[ -f "${dir}/package.json" ]]                                  && { echo "node";       return; }
  [[ -f "${dir}/requirements.txt" || \
     -f "${dir}/setup.py"         || \
     -f "${dir}/pyproject.toml"   ]]                              && { echo "python";     return; }

  echo "unknown"
}

# ── Banner ────────────────────────────────────────────────────────────────────
log_section "agents/start.sh  v${VERSION}"
log_info "Target project  : ${TARGET_PATH}"
log_info "Output base dir : ${OUTPUT_PATH}"

PROJECT_TYPE="$(detect_project_type "${TARGET_PATH}")"
log_info "Detected type   : ${BOLD}${PROJECT_TYPE}${RESET}"

# ── Map type → runner script ──────────────────────────────────────────────────
case "${PROJECT_TYPE}" in
  java-maven) RUNNER="${TOOLS_DIR}/runner-java.sh"   ;;
  node)       RUNNER="${TOOLS_DIR}/runner-node.sh"   ;;
  python)     RUNNER="${TOOLS_DIR}/runner-python.sh" ;;
  unknown)
    log_error "Could not detect a supported project type inside: ${TARGET_PATH}"
    log_error "Expected one of: pom.xml | package.json | requirements.txt | setup.py | pyproject.toml"
    exit 1 ;;
esac

if [[ ! -f "${RUNNER}" ]]; then
  log_error "Runner script not found: ${RUNNER}"
  log_error "Ensure the agents/tools/ directory is intact."
  exit 1
fi

# ── Dry-run short-circuit ─────────────────────────────────────────────────────
if [[ "${DRY_RUN}" == true ]]; then
  log_success "[DRY-RUN] Detected type '${PROJECT_TYPE}' — would invoke: ${RUNNER}"
  exit 0
fi

# ── Delegate to the runner ────────────────────────────────────────────────────
chmod +x "${RUNNER}"
log_info "Invoking runner: ${RUNNER}"
echo ""

# exec replaces this process so the runner's exit code propagates directly.
exec "${RUNNER}" \
  --target="${TARGET_PATH}" \
  --output="${OUTPUT_PATH}" \
  --agents-dir="${AGENTS_DIR}"
