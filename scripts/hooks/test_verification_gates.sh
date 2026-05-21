#!/bin/bash
# Phase 39: Verification Gate Tests
# Tests for PreToolUse and PostToolUse hooks (fail-closed invariant validation)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRE_GATE="$SCRIPT_DIR/pre_tool_use_verification_gate.sh"

echo "=== Phase 39 Verification Gate Test Suite ==="
echo ""

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Test function
test_gate() {
    local test_name="$1"
    local input="$2"
    local expected_code="$3"
    
    # Run gate and capture exit code (don't fail on non-zero)
    bash "$PRE_GATE" "$input" >/dev/null 2>&1
    local exit_code=$?
    
    if [[ $exit_code -eq $expected_code ]]; then
        echo "✅ PASS: $test_name (exit $exit_code)"
        ((TESTS_PASSED++))
    else
        echo "❌ FAIL: $test_name (expected $expected_code, got $exit_code)"
        ((TESTS_FAILED++))
    fi
}

# PreToolUse Gate Tests
echo "--- PreToolUse Verification Gate Tests ---"

# Destructive command tests (should fail with code 2)
test_gate "Reject: rm -rf" "rm -rf /important/data" 2
test_gate "Reject: DROP TABLE" "DROP TABLE users" 2
test_gate "Reject: git reset --hard" "git reset --hard HEAD" 2
test_gate "Reject: Command injection" "cat file; \$(malicious)" 2
test_gate "Reject: LD_PRELOAD injection" "LD_PRELOAD=/lib/malicious.so /usr/bin/bash" 2

# Safe commands (should pass with code 0)
test_gate "Allow: Safe cargo command" "cargo test --lib" 0
test_gate "Allow: Safe echo command" "echo 'hello world'" 0
test_gate "Allow: Safe git add" "git add src/file.rs" 0
test_gate "Allow: Safe file operations" "cat /etc/hostname" 0
test_gate "Allow: Empty input" "" 0

echo ""
echo "=== Test Results ==="
echo "PASSED: $TESTS_PASSED"
echo "FAILED: $TESTS_FAILED"
echo ""

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo "✅ All verification gate tests passed!"
    exit 0
else
    echo "❌ Some verification gate tests failed!"
    exit 1
fi
