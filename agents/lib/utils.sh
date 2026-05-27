#!/usr/bin/env bash
# Shared utilities — sourced by start.sh and all runners.
# Never executed directly.

# ── ANSI colors (auto-disabled when output is not a tty) ─────────────────────
if [[ -t 1 ]]; then
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
  BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; BOLD=''; RESET=''
fi

# ── Logging helpers ───────────────────────────────────────────────────────────
log_info()    { echo -e "${BLUE}[INFO]${RESET}    $*"; }
log_success() { echo -e "${GREEN}[OK]${RESET}      $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET}    $*"; }
log_error()   { echo -e "${RED}[ERROR]${RESET}   $*" >&2; }
log_section() { echo -e "\n${BOLD}${CYAN}──── $* ────${RESET}"; }

# ── Path utilities ────────────────────────────────────────────────────────────

# Resolve any path to its absolute form without following symlinks unsafely.
abspath() {
  local p="$1"
  # If already absolute, just normalize; otherwise expand relative to CWD.
  if [[ "$p" = /* ]]; then
    ( cd "$p" && pwd )
  else
    ( cd "$p" && pwd )
  fi
}

# Assert that a path exists and is a directory; exit-safe (returns 1 on fail).
require_dir() {
  local path="$1"
  local label="${2:---target}"
  if [[ -z "$path" ]]; then
    log_error "No path supplied for ${label}."
    return 1
  fi
  if [[ ! -d "$path" ]]; then
    log_error "Path does not exist or is not a directory [${label}]: ${path}"
    return 1
  fi
  return 0
}

# ── Timestamp for report directory naming ────────────────────────────────────
timestamp() { date +%Y%m%d_%H%M%S; }
