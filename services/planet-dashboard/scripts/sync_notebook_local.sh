#!/usr/bin/env bash
# Personal mode: Local-first, zero cloud escalation
set -euo pipefail

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NOTEBOOK_DIR="$HOME/.smaos/notebook_exports"
SNAPSHOT_DIR="$NOTEBOOK_DIR/state_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$SNAPSHOT_DIR"

# Snapshot current state
cp ~/.smaos/exec/EXEC_LOG.private.json "$SNAPSHOT_DIR/" 2>/dev/null || true
cp -r ~/.smaos/capsules/ "$SNAPSHOT_DIR/" 2>/dev/null || true

# Compute integrity
SNAPSHOT_COUNT=$(find "$NOTEBOOK_DIR" -type f | wc -l)
INTEGRITY=$(find "$NOTEBOOK_DIR" -type f -exec sha256sum {} + | sha256sum | cut -d' ' -f1)

# Log to EXEC_LOG
echo "$TIMESTAMP | NOTEBOOK_SYNC_COMPLETE | files:$SNAPSHOT_COUNT | integrity:$INTEGRITY | location:$NOTEBOOK_DIR" >> ~/.smaos/exec/EXEC_LOG.private.json

echo "✅ Notebook sync complete"
echo "📁 Snapshots: $SNAPSHOT_DIR"
echo "📊 Files: $SNAPSHOT_COUNT"
echo "🔐 Integrity: $INTEGRITY"
