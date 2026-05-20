#!/usr/bin/env bash
# Deterministic Replay Engine
# Usage: claude-replay.sh <commit_or_index>
# Restores exact diff state, verifies tests, outputs audit trail
set -euo pipefail

TARGET="${1:?Usage: claude-replay.sh <commit_or_index>}"
LOG="EXEC_LOG.json"

if [[ ! -f "$LOG" ]]; then
  echo "❌ EXEC_LOG.json not found. Initialize ledger first."
  exit 1
fi

# Resolve target to commit hash
INDEX=$(jq -r ".[(${TARGET}-1)] // empty | .commit" "$LOG" 2>/dev/null || echo "")
if [[ -z "$INDEX" ]]; then INDEX="$TARGET"; fi

echo "🔄 Deterministic Replay: $INDEX"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Fetch commit metadata from ledger
ENTRY=$(jq -r ".[] | select(.commit == \"$INDEX\")" "$LOG" 2>/dev/null)

if [[ -z "$ENTRY" ]]; then
  echo "❌ Commit $INDEX not found in ledger. Available commits:"
  jq -r '.[] | "\(.commit) (\(.timestamp)) — \(.message)"' "$LOG"
  exit 1
fi

echo "$ENTRY" | jq '.'
echo ""

# Restore to commit
git checkout "$INDEX" 2>&1 | grep -v "^Updated\|^HEAD is now\|^Note:" || true

# Run test suite
echo ""
echo "🧪 Running test suite…"
if cargo test -q 2>/dev/null; then
  echo "✅ All tests PASS"
  TEST_MATCH="true"
else
  echo "⚠️  Tests failed (may be expected for historical state)"
  TEST_MATCH="false"
fi

# Show diff summary
echo ""
echo "📊 Diff Summary (vs parent):"
git diff --stat HEAD~1..HEAD | head -10

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Replay complete."
echo "   Commit: $INDEX"
echo "   Tests Match: $TEST_MATCH"
echo ""
echo "To return to main: git checkout main"
