#!/bin/bash
# Phase 29: Lean 4 Verification PreToolUse Gate
#
# This hook enforces the Correctness Doctrine before tool execution:
# If a /verify skill was invoked but tests are failing, block code writes.
# If a /spec skill output exists, verify /implement references it.
#
# Exit codes:
# 0 = Allow execution
# 2 = Block (Fail-Closed mandate)

set -e

# Parse stdin JSON
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // {}')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

# Check if we're in a /verify context
if [ -f ".claude/verify_context.txt" ]; then
    VERIFY_STATUS=$(cat ".claude/verify_context.txt")

    # If verification is in progress and we try to modify code, check test status
    if [[ "$TOOL_NAME" =~ ^(Write|Edit)$ ]]; then
        # Run tests to see current status
        if cargo test --all 2>&1 | grep -q "test result: FAILED"; then
            # Tests are failing - block writes until /verify completes
            echo '{
                "continue": false,
                "stopReason": "Verification gate: Tests are failing. Complete /verify before writing more code.",
                "decision": "block"
            }'
            exit 2
        fi
    fi
fi

# Check if /spec output exists for this feature
SPEC_FILE="spec.md"
if [ ! -f "$SPEC_FILE" ]; then
    if [[ "$TOOL_NAME" =~ ^(Write|Edit)$ ]]; then
        # Writing code without a spec - warn (not block, but discourage)
        echo '{
            "systemMessage": "⚠️  No spec.md found. Run /spec before writing code to avoid vibe coding."
        }'
    fi
fi

# Allow execution by default
echo '{"continue": true}'
exit 0
