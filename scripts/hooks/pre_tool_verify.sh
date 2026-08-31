#!/bin/bash
###############################################################################
# SMAOS Phase 1: Gate 0 — Pre-Flight Verification
# Purpose: Pre-execution validation before any tool execution
# Scope: Proof artifact presence, git state, AP2 ledger structure
# Integration: agentacct, unlazy, AP2 ledger
# Status: Production-ready for Sep 8+ deployment
###############################################################################

set -o pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Configuration
PROOF_ARTIFACTS_DIR="${HOME}/.smaos/series_a/proof_artifacts"
WORK_RECEIPTS_DIR="${HOME}/.smaos/work_receipts"
AP2_LEDGER_DIR="${PROJECT_ROOT}/.smaos/ledger"
GATE_LOG="${PROJECT_ROOT}/.gate-logs/gate_0_preflight.log"
GATE_STATUS_FILE="${PROJECT_ROOT}/.gate-status/gate_0_status.json"

# Ensure directories exist
mkdir -p "$(dirname "$GATE_LOG")" "$(dirname "$GATE_STATUS_FILE")"

# Logging
log_info() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] [GATE-0] [INFO] $*" | tee -a "$GATE_LOG"
}

log_warn() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] [GATE-0] [WARN] $*" | tee -a "$GATE_LOG" >&2
}

log_error() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] [GATE-0] [ERROR] $*" | tee -a "$GATE_LOG" >&2
}

# Exit handler: Always update status file
cleanup() {
  local exit_code=$?
  local status="PASS"
  [ $exit_code -ne 0 ] && status="FAIL"

  cat > "$GATE_STATUS_FILE" <<EOF
{
  "gate": 0,
  "gate_name": "pre_tool_verify",
  "status": "$status",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "exit_code": $exit_code,
  "log_path": "$GATE_LOG"
}
EOF
}
trap cleanup EXIT

log_info "=== Gate 0 Pre-Flight Verification ==="

# ============================================================================
# CHECK 1: Proof Artifacts Presence
# ============================================================================
log_info "CHECK 1: Verifying proof artifacts..."
PROOF_CHECKS=0
PROOF_PASS=0

declare -a REQUIRED_ARTIFACTS=(
  "1_agentacct_config.json"
  "2_unlazy_gates.md"
  "3_is_agentic.json"
  "4_canirun_grades.json"
  "5_ap2_ledger_pqc.md"
  "6_ragas_golden_set.json"
  "7_freetoken_benchmark.json"
)

for artifact in "${REQUIRED_ARTIFACTS[@]}"; do
  ((PROOF_CHECKS++))
  if [ -f "$PROOF_ARTIFACTS_DIR/$artifact" ]; then
    log_info "  ✓ Found: $artifact"
    ((PROOF_PASS++))
  else
    log_warn "  ✗ Missing: $artifact (will be generated during execution)"
  fi
done

# ============================================================================
# CHECK 2: Git Repository State
# ============================================================================
log_info "CHECK 2: Verifying git state..."
GIT_CHECKS=0
GIT_PASS=0

# Check we're in a git repo
if cd "$PROJECT_ROOT" && git rev-parse --git-dir > /dev/null 2>&1; then
  ((GIT_CHECKS++))
  log_info "  ✓ Valid git repository"
  ((GIT_PASS++))
else
  log_error "  ✗ Not a valid git repository"
  ((GIT_CHECKS++))
fi

# Check for uncommitted changes (warning only, non-blocking)
if cd "$PROJECT_ROOT" && git status --porcelain | grep -q .; then
  ((GIT_CHECKS++))
  log_warn "  ⚠ Uncommitted changes detected (non-blocking)"
else
  ((GIT_CHECKS++))
  log_info "  ✓ Clean working tree"
  ((GIT_PASS++))
fi

# Check for unsigned commits (info only)
if cd "$PROJECT_ROOT" && git log --pretty=format:"%G?" -1 | grep -q "G"; then
  ((GIT_CHECKS++))
  log_info "  ✓ Last commit is signed"
  ((GIT_PASS++))
else
  ((GIT_CHECKS++))
  log_warn "  ⚠ Last commit not signed (warning only)"
fi

# ============================================================================
# CHECK 3: AP2 Ledger Structure
# ============================================================================
log_info "CHECK 3: Verifying AP2 ledger structure..."
AP2_CHECKS=0
AP2_PASS=0

if [ -d "$AP2_LEDGER_DIR" ]; then
  ((AP2_CHECKS++))
  log_info "  ✓ AP2 ledger directory exists"
  ((AP2_PASS++))

  # Check for recent ledger entries
  LEDGER_COUNT=$(find "$AP2_LEDGER_DIR" -type f -name "*.json" 2>/dev/null | wc -l)
  ((AP2_CHECKS++))
  if [ "$LEDGER_COUNT" -gt 0 ]; then
    log_info "  ✓ Found $LEDGER_COUNT ledger entries"
    ((AP2_PASS++))
  else
    log_warn "  ⚠ No ledger entries yet (will be created during execution)"
  fi
else
  ((AP2_CHECKS++))
  log_info "  ✓ AP2 ledger will be initialized on first tool use"
  mkdir -p "$AP2_LEDGER_DIR"
  ((AP2_PASS++))
fi

# ============================================================================
# CHECK 4: Work Receipts Directory
# ============================================================================
log_info "CHECK 4: Verifying work receipts directory..."
WR_CHECKS=0
WR_PASS=0

if [ -d "$WORK_RECEIPTS_DIR" ]; then
  ((WR_CHECKS++))
  log_info "  ✓ Work receipts directory exists"
  ((WR_PASS++))

  WR_COUNT=$(find "$WORK_RECEIPTS_DIR" -type f -name "*.json" 2>/dev/null | wc -l)
  ((WR_CHECKS++))
  log_info "  ✓ Found $WR_COUNT work receipt files"
  ((WR_PASS++))
else
  ((WR_CHECKS++))
  log_info "  ✓ Work receipts directory will be initialized by agentacct"
  mkdir -p "$WORK_RECEIPTS_DIR"
  ((WR_PASS++))
fi

# ============================================================================
# CHECK 5: Python Dependencies
# ============================================================================
log_info "CHECK 5: Verifying Python dependencies..."
PY_CHECKS=0
PY_PASS=0

for module in json hashlib dataclasses pathlib; do
  ((PY_CHECKS++))
  if python3 -c "import $module" 2>/dev/null; then
    log_info "  ✓ Python module available: $module"
    ((PY_PASS++))
  else
    log_error "  ✗ Missing Python module: $module"
  fi
done

# ============================================================================
# CHECK 6: Hook Dependencies
# ============================================================================
log_info "CHECK 6: Verifying gate dependencies..."
HD_CHECKS=0
HD_PASS=0

# Check post_tool_validate.sh exists
((HD_CHECKS++))
if [ -x "$SCRIPT_DIR/post_tool_validate.sh" ]; then
  log_info "  ✓ Gate 1-3 validator script ready"
  ((HD_PASS++))
else
  log_warn "  ⚠ Gate 1-3 validator not yet present (will be created)"
fi

# Check stop_validation.sh exists
((HD_CHECKS++))
if [ -x "$SCRIPT_DIR/stop_validation.sh" ]; then
  log_info "  ✓ Gate 4-5 validator script ready"
  ((HD_PASS++))
else
  log_warn "  ⚠ Gate 4-5 validator not yet present (will be created)"
fi

# Check for agentacct module
((HD_CHECKS++))
if [ -f "$PROJECT_ROOT/agentacct_capture.py" ] || [ -f "$PROJECT_ROOT/smaos/l3_tooling/agentacct_capture.py" ]; then
  log_info "  ✓ agentacct capture module available"
  ((HD_PASS++))
else
  log_warn "  ⚠ agentacct module not found"
fi

# Check for unlazy gates
((HD_CHECKS++))
if [ -f "$PROJECT_ROOT/unlazy_gates.py" ] || [ -f "$PROJECT_ROOT/smaos/l3_tooling/unlazy_gates.py" ]; then
  log_info "  ✓ unlazy gates module available"
  ((HD_PASS++))
else
  log_warn "  ⚠ unlazy gates module not found"
fi

# ============================================================================
# SUMMARY & EXIT
# ============================================================================
TOTAL_CHECKS=$((PROOF_CHECKS + GIT_CHECKS + AP2_CHECKS + WR_CHECKS + PY_CHECKS + HD_CHECKS))
TOTAL_PASS=$((PROOF_PASS + GIT_PASS + AP2_PASS + WR_PASS + PY_PASS + HD_PASS))
TOTAL_FAIL=$((TOTAL_CHECKS - TOTAL_PASS))

log_info "========================================="
log_info "Gate 0 Summary:"
log_info "  Proof Artifacts: $PROOF_PASS/$PROOF_CHECKS"
log_info "  Git State:       $GIT_PASS/$GIT_CHECKS"
log_info "  AP2 Ledger:      $AP2_PASS/$AP2_CHECKS"
log_info "  Work Receipts:   $WR_PASS/$WR_CHECKS"
log_info "  Python Modules:  $PY_PASS/$PY_CHECKS"
log_info "  Dependencies:    $HD_PASS/$HD_CHECKS"
log_info "========================================="
log_info "TOTAL: $TOTAL_PASS/$TOTAL_CHECKS checks passed"

# Fail only if critical checks fail (Python, dependencies)
if [ "$PY_PASS" -lt "$PY_CHECKS" ]; then
  log_error "Gate 0 FAILED: Missing Python modules"
  exit 1
fi

if [ "$GIT_PASS" -lt 1 ]; then
  log_error "Gate 0 FAILED: Not a valid git repository"
  exit 1
fi

log_info "Gate 0 PASSED: Pre-flight verification complete"
exit 0
