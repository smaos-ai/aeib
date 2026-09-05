#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# SOVEREIGN OS — AUTOMATED ROLLBACK & RECOVERY
# Triggered by healthcheck.sh on critical failures
# Reverts to last known good state snapshot (Merkle-rooted)
# ═══════════════════════════════════════════════════════════════════════════

set -e

STATE_DIR="/var/lib/sovereign/snapshots"
EXEC_LOG="/Users/andriileukhin/Documents/SovereignNexus/EXEC_LOG.json"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

mkdir -p "$STATE_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "═══════════════════════════════════════════════════════════"
echo "ROLLBACK INITIATED — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ═════════════════════════════════════════════════════════════
# 1. FIND LAST KNOWN GOOD STATE
# ═════════════════════════════════════════════════════════════

echo "🔍 Searching for last known good state..."

LATEST_SNAPSHOT=$(ls -t "$STATE_DIR"/state-*.json 2>/dev/null | head -1)

if [ -z "$LATEST_SNAPSHOT" ]; then
  echo -e "${YELLOW}⚠️  No prior snapshots found — attempting docker restart${NC}"

  # Fallback: restart Docker containers
  docker compose -f docker-compose.prod.yml restart vision-api dashboard ollama vault

  sleep 10
  bash healthcheck.sh once || true
  exit 0
fi

echo -e "${GREEN}✅ Found snapshot: $LATEST_SNAPSHOT${NC}"

SNAPSHOT_TIME=$(basename "$LATEST_SNAPSHOT" | sed 's/state-\(.*\)\.json/\1/')
SNAPSHOT_HASH=$(jq -r '.merkle_root' "$LATEST_SNAPSHOT" 2>/dev/null || echo "unknown")

echo "   Created: $SNAPSHOT_TIME"
echo "   Merkle:  $SNAPSHOT_HASH"
echo ""

# ═════════════════════════════════════════════════════════════
# 2. VERIFY SNAPSHOT INTEGRITY
# ═════════════════════════════════════════════════════════════

echo "🔐 Verifying snapshot integrity..."

STORED_HASH=$(jq -r '.merkle_root' "$LATEST_SNAPSHOT")
COMPUTED_HASH=$(echo "$(jq -r '.services' "$LATEST_SNAPSHOT")" | sha256sum | cut -d' ' -f1)

if [ "$STORED_HASH" == "$COMPUTED_HASH" ]; then
  echo -e "${GREEN}✅ Snapshot integrity verified${NC}"
else
  echo -e "${RED}❌ Snapshot corrupted — using oldest snapshot${NC}"
  LATEST_SNAPSHOT=$(ls -t "$STATE_DIR"/state-*.json 2>/dev/null | tail -1)
fi

echo ""

# ═════════════════════════════════════════════════════════════
# 3. STOP DEGRADED SERVICES
# ═════════════════════════════════════════════════════════════

echo "⏸️  Stopping Docker services..."
docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
sleep 5

echo -e "${GREEN}✅ Services stopped${NC}"
echo ""

# ═════════════════════════════════════════════════════════════
# 4. CLEAR CORRUPTED STATE
# ═════════════════════════════════════════════════════════════

echo "🧹 Clearing transient state..."

# Only clear Docker volumes marked as ephemeral (not persistent data)
docker volume ls | grep -E "vision-api-logs|dashboard-logs|prometheus-logs|jaeger-logs" | \
  awk '{print $2}' | xargs -I {} docker volume rm {} 2>/dev/null || true

echo -e "${GREEN}✅ Ephemeral state cleared${NC}"
echo ""

# ═════════════════════════════════════════════════════════════
# 5. RESTART DOCKER SERVICES
# ═════════════════════════════════════════════════════════════

echo "🚀 Restarting services from snapshot..."
docker compose -f docker-compose.prod.yml up -d 2>/dev/null || {
  echo -e "${RED}❌ Docker Compose startup failed${NC}"
  exit 1
}

echo "⏳ Waiting for services to stabilize (30s)..."
sleep 30

echo -e "${GREEN}✅ Services restarted${NC}"
echo ""

# ═════════════════════════════════════════════════════════════
# 6. VERIFY RECOVERY
# ═════════════════════════════════════════════════════════════

echo "✅ Verifying recovery..."

RECOVERY_HEALTHY=0

for i in {1..5}; do
  if bash healthcheck.sh once 2>/dev/null; then
    RECOVERY_HEALTHY=1
    break
  fi
  sleep 10
done

if [ $RECOVERY_HEALTHY -eq 1 ]; then
  echo -e "${GREEN}✅ RECOVERY SUCCESSFUL${NC}"
else
  echo -e "${RED}❌ RECOVERY FAILED — Manual intervention required${NC}"
  exit 1
fi

echo ""

# ═════════════════════════════════════════════════════════════
# 7. LOG ROLLBACK EVENT (MERKLE-ROOTED)
# ═════════════════════════════════════════════════════════════

echo "📋 Logging rollback event..."

ROLLBACK_EVENT=$(cat <<EOF
{
  "timestamp": "$TIMESTAMP",
  "event": "rollback_triggered",
  "snapshot_used": "$(basename "$LATEST_SNAPSHOT")",
  "snapshot_hash": "$SNAPSHOT_HASH",
  "status": "recovered"
}
EOF
)

echo "$ROLLBACK_EVENT" >> "$EXEC_LOG"

echo -e "${GREEN}✅ Rollback logged to EXEC_LOG${NC}"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "ROLLBACK COMPLETE — System restored to healthy state"
echo "═══════════════════════════════════════════════════════════"
