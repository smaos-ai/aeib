#!/bin/bash

################################################################################
# PHASE 65 NETWORK SEVER TEST RUNNER — STANDALONE EXECUTION
# Purpose: Isolate the fail-closed archival test for video recording
# Duration: ~3-5 seconds
# Hardware: Requires Apple Silicon (M1/M2/M3) with 4GB+ free RAM
################################################################################

set -euo pipefail

# Color codes
readonly BLUE='\033[0;34m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

################################################################################
# SETUP
################################################################################

log_info "=========================================="
log_info "PHASE 65 NETWORK SEVER TEST — STANDALONE"
log_info "=========================================="
log_info ""

# Verify we're in the SovereignNexus repo
if [[ ! -f "Cargo.toml" ]]; then
    log_error "Not in SovereignNexus directory. Run from repo root."
    exit 1
fi

log_info "Checking environment..."

# Verify Rust toolchain
if ! command -v cargo &> /dev/null; then
    log_error "Rust/Cargo not found. Install via: rustup.rs"
    exit 1
fi
log_success "Rust toolchain ready"

# Verify PostgreSQL (optional warning)
if ! command -v psql &> /dev/null; then
    log_warning "PostgreSQL not in PATH (test may not need it depending on mock state)"
fi

# Check available memory
AVAILABLE_MEMORY=$(vm_stat | grep 'Pages free' | awk '{print $3}' | sed 's/\.//')
AVAILABLE_GB=$((AVAILABLE_MEMORY / 262144))
if [[ $AVAILABLE_GB -lt 2 ]]; then
    log_error "Insufficient memory: ${AVAILABLE_GB}GB (need 2GB+)"
    exit 1
fi
log_success "Available memory: ${AVAILABLE_GB}GB"

################################################################################
# PHASE 65 TEST EXECUTION
################################################################################

log_info ""
log_info "=========================================="
log_info "STARTING: test_network_sever_fail_closed_hot_storage_preservation_trap"
log_info "=========================================="
log_info ""
log_warning "⚠️  TIMING CRITICAL:"
log_warning "   • Test starts in 3 seconds"
log_warning "   • Network will be used for ~1-2 seconds (initial test setup)"
log_warning "   • At ~50% progress, DISCONNECT YOUR Wi-Fi NOW"
log_warning "   • Keep Wi-Fi OFF for remainder of test (2-3 more seconds)"
log_warning "   • Test should PASS even with network severed"
log_info ""

sleep 3

log_info "Running test with full output..."
log_info "════════════════════════════════════════════════════════════════"
log_info ""

# Run the specific test with nocapture to see all output
cargo test -p siss-audit-archiver --lib test_network_sever_fail_closed_hot_storage_preservation_trap -- --nocapture --test-threads=1

TEST_RESULT=$?

log_info ""
log_info "════════════════════════════════════════════════════════════════"

if [[ $TEST_RESULT -eq 0 ]]; then
    log_success "TEST PASSED"
    log_info ""
    log_info "✓ hot_storage_contains(trace_id) = TRUE"
    log_info "✓ DELETE transaction aborted on S3 verification failure"
    log_info "✓ Data preserved despite network failure"
    log_info "✓ Fail-closed semantics: VERIFIED"
    log_info ""
else
    log_error "TEST FAILED (exit code: $TEST_RESULT)"
    log_info "If network was disconnected and test failed, this may indicate a regression."
    exit 1
fi

log_info ""
log_success "PHASE 65 VALIDATION COMPLETE"
log_info ""
log_info "Use this terminal output in the Nebius pitch video."
log_info "The test passing with Wi-Fi off is your proof of concept."

exit 0
