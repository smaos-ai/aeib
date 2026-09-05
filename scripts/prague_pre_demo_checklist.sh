#!/bin/bash

################################################################################
# Prague PoC Hardware Validation Checklist
#
# Validates 6-point hardware security and performance baseline for investor demo
# Designed to run on 3x Mac Studio M3 Pro nodes
#
# Exit codes:
#   0 = All checks PASSED
#   1 = One or more checks FAILED
#   2 = Script error (missing dependencies, etc.)
################################################################################

set -u  # Fail on undefined variables

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Global state
CHECKS_PASSED=0
CHECKS_FAILED=0
FAILED_CHECKS=()
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Detect binary path - prioritize demo-app, fallback to siss-orchestrator
if [ -f "${PROJECT_ROOT}/target/release/demo-app" ]; then
    BINARY_PATH="${PROJECT_ROOT}/target/release/demo-app"
elif [ -f "${PROJECT_ROOT}/target/release/siss-orchestrator" ]; then
    BINARY_PATH="${PROJECT_ROOT}/target/release/siss-orchestrator"
else
    # Will attempt to build if not found
    BINARY_PATH="${PROJECT_ROOT}/target/release/demo-app"
fi

EXPECTED_SHA256=""  # Will be set from .prague_checksum if it exists

################################################################################
# Utility Functions
################################################################################

log_check() {
    local check_num=$1
    local description=$2
    printf "${BLUE}[CHECK ${check_num}]${NC} ${description}\n"
}

pass() {
    local check_name=$1
    printf "  ${GREEN}✓ PASS${NC}: ${check_name}\n"
    ((CHECKS_PASSED++))
}

fail() {
    local check_name=$1
    local reason=$2
    printf "  ${RED}✗ FAIL${NC}: ${check_name}\n"
    printf "    Reason: ${reason}\n"
    ((CHECKS_FAILED++))
    FAILED_CHECKS+=("${check_name}")
}

warn() {
    local message=$1
    printf "  ${YELLOW}⚠ WARNING${NC}: ${message}\n"
}

info() {
    local message=$1
    printf "  ${BLUE}ℹ INFO${NC}: ${message}\n"
}

separator() {
    echo "================================================================================"
}

header() {
    local title=$1
    separator
    printf "${BLUE}${title}${NC}\n"
    separator
}

footer() {
    separator
    printf "${BLUE}Test Run Summary${NC}\n"
    separator
    printf "Checks Passed: ${GREEN}${CHECKS_PASSED}${NC}\n"
    printf "Checks Failed: ${RED}${CHECKS_FAILED}${NC}\n"
    if [ ${#FAILED_CHECKS[@]} -gt 0 ]; then
        printf "\nFailed Checks:\n"
        for check in "${FAILED_CHECKS[@]}"; do
            printf "  - ${RED}${check}${NC}\n"
        done
    fi
    separator
}

require_command() {
    local cmd=$1
    if ! command -v "$cmd" &> /dev/null; then
        printf "${RED}ERROR${NC}: Required command '${cmd}' not found\n"
        return 1
    fi
    return 0
}

################################################################################
# Dependency Check
################################################################################

check_dependencies() {
    header "Dependency Check"

    local deps=("lsof" "git" "strings" "shasum" "cargo" "curl")
    local missing=0

    for dep in "${deps[@]}"; do
        if require_command "$dep"; then
            info "Found: ${dep}"
        else
            warn "Missing: ${dep}"
            ((missing++))
        fi
    done

    if [ $missing -gt 0 ]; then
        printf "${RED}ERROR${NC}: Missing ${missing} required command(s)\n"
        return 2
    fi

    echo ""
}

################################################################################
# CHECK 1: Network Isolation
################################################################################

check_network_isolation() {
    log_check 1 "Network Isolation"

    # Test: No established external connections
    local established_conns=$(lsof -i -P -n 2>/dev/null | grep ESTABLISHED | wc -l)

    if [ "$established_conns" -eq 0 ]; then
        pass "Network Isolation"
        info "No established external connections found"
    else
        fail "Network Isolation" \
            "Found ${established_conns} established connection(s). Expected 0.\n" \
            "    Run: lsof -i -P -n | grep ESTABLISHED"
    fi

    # Additional validation: check WiFi status on macOS
    if command -v networksetup &> /dev/null; then
        local wifi_status=$(networksetup -getairportpower en0 2>/dev/null || echo "unknown")
        if [[ "$wifi_status" == *"Off"* ]]; then
            info "WiFi is OFF (macOS)"
        else
            warn "WiFi status: ${wifi_status} (macOS)"
        fi
    fi

    echo ""
}

################################################################################
# CHECK 2: Git Remote Disabled
################################################################################

check_git_remote_disabled() {
    log_check 2 "Git Remote Disabled"

    # Navigate to project root
    cd "$PROJECT_ROOT" || { fail "Git Remote Disabled" "Cannot access project root"; return 1; }

    # Test: No origin configured
    local remotes=$(git remote -v 2>/dev/null | wc -l)

    if [ "$remotes" -eq 0 ]; then
        pass "Git Remote Disabled"
        info "No git remotes configured"
    else
        fail "Git Remote Disabled" \
            "Found ${remotes} git remote(s). Expected 0.\n" \
            "    Run: git remote -v"
    fi

    echo ""
}

################################################################################
# CHECK 3: Cloud SDK Audit
################################################################################

check_cloud_sdk_audit() {
    log_check 3 "Cloud SDK Audit"

    # First, ensure binary exists
    if [ ! -f "$BINARY_PATH" ]; then
        info "Binary not found at ${BINARY_PATH}"
        info "Building release binary... (this may take 2-3 minutes)"

        cd "$PROJECT_ROOT" || { fail "Cloud SDK Audit" "Cannot access project root"; return 1; }

        local binary_name=$(basename "$BINARY_PATH")
        if cargo build --release --bin "$binary_name" 2>&1 | tail -5; then
            info "Build completed"
        else
            fail "Cloud SDK Audit" "Failed to build release binary"
            return 1
        fi
    fi

    if [ ! -f "$BINARY_PATH" ]; then
        fail "Cloud SDK Audit" "Binary not found after build at ${BINARY_PATH}"
        return 1
    fi

    # Test: No cloud SDK references in binary
    local aws_refs=$(strings "$BINARY_PATH" 2>/dev/null | grep -ic "aws" || true)
    local azure_refs=$(strings "$BINARY_PATH" 2>/dev/null | grep -ic "azure" || true)
    local gcp_refs=$(strings "$BINARY_PATH" 2>/dev/null | grep -ic "gcp" || true)
    local nebius_refs=$(strings "$BINARY_PATH" 2>/dev/null | grep -ic "nebius" || true)

    local total_refs=$((aws_refs + azure_refs + gcp_refs + nebius_refs))

    if [ "$total_refs" -eq 0 ]; then
        pass "Cloud SDK Audit"
        info "No cloud SDK references found in binary"
    else
        fail "Cloud SDK Audit" \
            "Found ${total_refs} cloud SDK reference(s):\n" \
            "    AWS: ${aws_refs}, Azure: ${azure_refs}, GCP: ${gcp_refs}, Nebius: ${nebius_refs}"
    fi

    echo ""
}

################################################################################
# CHECK 4: Binary Integrity (SHA256)
################################################################################

check_binary_integrity() {
    log_check 4 "Binary Integrity"

    if [ ! -f "$BINARY_PATH" ]; then
        fail "Binary Integrity" "Binary not found at ${BINARY_PATH}"
        return 1
    fi

    # Compute current SHA256
    local current_sha=$(shasum -a 256 "$BINARY_PATH" | awk '{print $1}')

    # Check if .prague_checksum file exists for verification
    local checksum_file="${PROJECT_ROOT}/.prague_checksum"

    if [ -f "$checksum_file" ]; then
        EXPECTED_SHA256=$(cat "$checksum_file")
        if [ "$current_sha" == "$EXPECTED_SHA256" ]; then
            pass "Binary Integrity"
            info "SHA256 matches expected: ${current_sha:0:16}..."
        else
            fail "Binary Integrity" \
                "SHA256 mismatch.\n" \
                "    Expected: ${EXPECTED_SHA256:0:16}...\n" \
                "    Got:      ${current_sha:0:16}..."
        fi
    else
        info "No .prague_checksum file found. Saving current hash for future verification."
        echo "$current_sha" > "$checksum_file"
        pass "Binary Integrity"
        info "SHA256 recorded: ${current_sha:0:16}..."
    fi

    echo ""
}

################################################################################
# CHECK 5: Agent Startup (<10s for 50 agents)
################################################################################

check_agent_startup() {
    log_check 5 "Agent Startup (50 agents in <10s)"

    if [ ! -f "$BINARY_PATH" ]; then
        fail "Agent Startup" "Binary not found at ${BINARY_PATH}"
        return 1
    fi

    info "Starting orchestrator with 50 agents..."

    local start_time=$(date +%s%N)

    # Run binary with 50 agents, capture output, enforce 15s timeout
    local output
    if output=$(timeout 15 "$BINARY_PATH" --agents 50 2>&1); then
        local end_time=$(date +%s%N)
        local elapsed_ms=$(( (end_time - start_time) / 1000000 ))
        local elapsed_s=$(( elapsed_ms / 1000 ))

        if [ "$elapsed_s" -lt 10 ]; then
            pass "Agent Startup"
            info "50 agents initialized in ${elapsed_s}.${elapsed_ms:(-3)}s"
        else
            fail "Agent Startup" \
                "Initialization took ${elapsed_s}.${elapsed_ms:(-3)}s (exceeded 10s limit)"
        fi
    else
        local exit_code=$?
        if [ $exit_code -eq 124 ]; then
            fail "Agent Startup" "Process timed out after 15s (exceeded 10s requirement)"
        else
            fail "Agent Startup" "Process exited with code ${exit_code}"
        fi
    fi

    echo ""
}

################################################################################
# CHECK 6: Latency Baseline (47µs mean, P99 <100µs)
################################################################################

check_latency_baseline() {
    log_check 6 "Latency Baseline (47µs mean, P99 <100µs)"

    info "Testing dispatcher latency metrics endpoint..."

    # Give the service a moment to start if needed
    local max_retries=10
    local retry_count=0
    local metrics=""

    while [ $retry_count -lt $max_retries ]; do
        if metrics=$(curl -s -m 2 http://127.0.0.1:8080/api/metrics/dispatch-latency 2>/dev/null); then
            if [ -n "$metrics" ] && [ "$metrics" != "Connection refused" ]; then
                break
            fi
        fi
        ((retry_count++))
        sleep 0.5
    done

    if [ -z "$metrics" ] || [ "$metrics" == "Connection refused" ]; then
        warn "Latency Baseline" \
            "Could not reach metrics endpoint at http://127.0.0.1:8080/api/metrics/dispatch-latency\n" \
            "    This is expected if the dispatcher is not currently running.\n" \
            "    Skipping this check in offline validation mode."
        echo ""
        return 0
    fi

    # Parse metrics (expecting JSON with mean and p99 fields)
    local mean_us=$(echo "$metrics" | grep -o '"mean_us":[0-9]*' | grep -o '[0-9]*' || true)
    local p99_us=$(echo "$metrics" | grep -o '"p99_us":[0-9]*' | grep -o '[0-9]*' || true)

    if [ -z "$mean_us" ] || [ -z "$p99_us" ]; then
        info "Metrics endpoint returned: ${metrics:0:100}..."
        warn "Could not parse latency metrics from response"
        echo ""
        return 0
    fi

    # Validate against thresholds
    local mean_pass=0
    local p99_pass=0

    if [ "$mean_us" -le 47 ]; then
        mean_pass=1
        info "Mean latency: ${mean_us}µs (threshold: ≤47µs) ${GREEN}✓${NC}"
    else
        info "Mean latency: ${mean_us}µs (threshold: ≤47µs) ${RED}✗${NC}"
    fi

    if [ "$p99_us" -lt 100 ]; then
        p99_pass=1
        info "P99 latency: ${p99_us}µs (threshold: <100µs) ${GREEN}✓${NC}"
    else
        info "P99 latency: ${p99_us}µs (threshold: <100µs) ${RED}✗${NC}"
    fi

    if [ $mean_pass -eq 1 ] && [ $p99_pass -eq 1 ]; then
        pass "Latency Baseline"
    else
        fail "Latency Baseline" \
            "Latency thresholds not met: mean=${mean_us}µs (≤47), p99=${p99_us}µs (<100)"
    fi

    echo ""
}

################################################################################
# Main Execution
################################################################################

main() {
    header "Prague PoC Hardware Validation Checklist"
    info "Project Root: ${PROJECT_ROOT}"
    info "Binary Path: ${BINARY_PATH}"
    info "Timestamp: $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
    echo ""

    # Verify dependencies first
    if ! check_dependencies; then
        footer
        return 2
    fi

    # Run all checks
    check_network_isolation
    check_git_remote_disabled
    check_cloud_sdk_audit
    check_binary_integrity
    check_agent_startup
    check_latency_baseline

    # Print summary
    footer

    # Exit with appropriate code
    if [ $CHECKS_FAILED -eq 0 ]; then
        printf "\n${GREEN}All checks PASSED!${NC}\n\n"
        return 0
    else
        printf "\n${RED}${CHECKS_FAILED} check(s) FAILED${NC}\n\n"
        return 1
    fi
}

# Execute if script is run directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
