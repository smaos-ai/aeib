#!/bin/bash
# Phase 39: PreToolUse Verification Gate
# Fail-closed security hook that intercepts tool invocations and blocks destructive commands
# Exit code 2 = destructive command detected and blocked (fail-closed)
# Exit code 0 = command passed verification

set -u

# Destructive command patterns (whitelist of patterns to reject)
readonly DESTRUCTIVE_PATTERNS=(
    "rm -rf"
    "rm -rf /"
    "dd if=/dev/zero"
    "dd if=/dev/random"
    "mkfs"
    "mkfs\."
    "format -Full"
    "DROP TABLE"
    "DROP DATABASE"
    "DROP SCHEMA"
    "TRUNCATE TABLE"
    "DELETE FROM"
    ":!rm"
    "git reset --hard"
    "git clean -fd"
    "git push --force"
    "force-push"
    "git worktree remove"
)

# Malicious environment injection patterns
readonly ENV_INJECTION_PATTERNS=(
    "LD_PRELOAD"
    "LD_LIBRARY_PATH"
    "DYLD_INSERT_LIBRARIES"
    "DYLD_LIBRARY_PATH"
    "__LIBC"
)

# Get tool input from environment or parameter
TOOL_INPUT="${1:-${TOOL_INPUT:-}}"

# If no input provided, pass verification (defensive)
if [[ -z "$TOOL_INPUT" ]]; then
    exit 0
fi

# Check for destructive commands
for pattern in "${DESTRUCTIVE_PATTERNS[@]}"; do
    if [[ "$TOOL_INPUT" =~ $pattern ]]; then
        echo "🚨 SECURITY GATE BLOCKED: Destructive command pattern detected: $pattern" >&2
        echo "   Tool Input: $TOOL_INPUT" >&2
        echo "   Status: REJECTED (fail-closed)" >&2
        exit 2
    fi
done

# Check for environment variable injection
for pattern in "${ENV_INJECTION_PATTERNS[@]}"; do
    if [[ "$TOOL_INPUT" =~ $pattern ]]; then
        echo "🚨 SECURITY GATE BLOCKED: Dangerous environment variable: $pattern" >&2
        echo "   Tool Input: $TOOL_INPUT" >&2
        echo "   Status: REJECTED (fail-closed)" >&2
        exit 2
    fi
done

# Check for command injection attempts
if [[ "$TOOL_INPUT" =~ \$\( ]] || [[ "$TOOL_INPUT" =~ \`[^\`]*\` ]] || [[ "$TOOL_INPUT" =~ \|\s*sh ]]; then
    echo "🚨 SECURITY GATE BLOCKED: Command injection pattern detected" >&2
    echo "   Tool Input: $TOOL_INPUT" >&2
    echo "   Status: REJECTED (fail-closed)" >&2
    exit 2
fi

# Verification passed
exit 0
