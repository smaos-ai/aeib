#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# SOVEREIGN OS — PRODUCTION HEALTH CHECK & MONITORING LOOP
# Runs every 60 seconds, monitors all 6 services + OpenTelemetry traces
# Auto-triggers rollback if critical failures detected
# ═══════════════════════════════════════════════════════════════════════════

set -e

INTERVAL=60
LOG_FILE="/var/log/sovereign/healthcheck.log"
STATE_FILE="/var/lib/sovereign/state.json"
EXEC_LOG="/Users/andriileukhin/Documents/SovereignNexus/EXEC_LOG.json"

mkdir -p /var/log/sovereign /var/lib/sovereign

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ═════════════════════════════════════════════════════════════
# 1. HEALTH CHECK FUNCTIONS
# ═════════════════════════════════════════════════════════════

check_vision_api() {
  if curl -s -m 3 http://localhost:8000/health | jq -e '.status == "healthy"' > /dev/null 2>&1; then
    echo "✅ Vision API"
    return 0
  else
    echo "❌ Vision API"
    return 1
  fi
}

check_dashboard() {
  if curl -s -m 3 -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "200"; then
    echo "✅ Dashboard"
    return 0
  else
    echo "❌ Dashboard"
    return 1
  fi
}

check_ollama() {
  if curl -s -m 3 http://localhost:11434/api/tags | jq -e '.models | length > 0' > /dev/null 2>&1; then
    echo "✅ Ollama LLM"
    return 0
  else
    echo "❌ Ollama LLM"
    return 1
  fi
}

check_vault() {
  if curl -s -m 3 http://localhost:8200/v1/sys/health | jq -e '.initialized' > /dev/null 2>&1; then
    echo "✅ Vault"
    return 0
  else
    echo "❌ Vault"
    return 1
  fi
}

check_prometheus() {
  if curl -s -m 3 -o /dev/null -w "%{http_code}" http://localhost:9090/-/healthy | grep -q "200"; then
    echo "✅ Prometheus"
    return 0
  else
    echo "❌ Prometheus"
    return 1
  fi
}

check_jaeger() {
  if curl -s -m 3 -o /dev/null -w "%{http_code}" http://localhost:16686 | grep -q "200"; then
    echo "✅ Jaeger"
    return 0
  else
    echo "❌ Jaeger"
    return 1
  fi
}

# ═════════════════════════════════════════════════════════════
# 2. OPENTELEMETRY TRACE MONITORING
# ═════════════════════════════════════════════════════════════

check_trace_latency() {
  # Query Prometheus for p99 latency over last 5 minutes
  LATENCY=$(curl -s 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))' | \
    jq -r '.data.result[0].value[1]' 2>/dev/null || echo "0")

  LATENCY_MS=$(echo "$LATENCY * 1000" | bc -l 2>/dev/null || echo "0")

  if (( $(echo "$LATENCY_MS < 1000" | bc -l) )); then
    echo "✅ Latency p99: ${LATENCY_MS%.*}ms"
    return 0
  else
    echo "⚠️  Latency p99: ${LATENCY_MS%.*}ms (>1s threshold)"
    return 1
  fi
}

# ═════════════════════════════════════════════════════════════
# 3. STATE SNAPSHOT (MERKLE-ROOTED)
# ═════════════════════════════════════════════════════════════

snapshot_state() {
  TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  # Collect state from all services
  cat > "$STATE_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "services": {
    "vision_api": $(curl -s http://localhost:8000/health 2>/dev/null || echo '{"status":"unknown"}'),
    "dashboard": $(curl -s -m 2 http://localhost:3000/api/health 2>/dev/null || echo '{"status":"unknown"}'),
    "ollama": $(curl -s http://localhost:11434/api/tags 2>/dev/null | jq '.models | length' || echo '0'),
    "vault": $(curl -s http://localhost:8200/v1/sys/health 2>/dev/null | jq '.initialized' || echo 'false'),
    "prometheus": "up",
    "jaeger": "up"
  }
}
EOF

  # Merkle-root the state snapshot (SHA256)
  STATE_HASH=$(sha256sum "$STATE_FILE" | cut -d' ' -f1)

  # Append to EXEC_LOG
  echo "{\"timestamp\": \"$TIMESTAMP\", \"event\": \"healthcheck\", \"state_hash\": \"$STATE_HASH\"}" >> "$EXEC_LOG"

  echo "✅ State snapshot: $STATE_HASH"
}

# ═════════════════════════════════════════════════════════════
# 4. AUTO-ROLLBACK TRIGGER
# ═════════════════════════════════════════════════════════════

trigger_rollback() {
  echo "$RED[$(date -u +%T)] CRITICAL FAILURE DETECTED — TRIGGERING ROLLBACK$NC" | tee -a "$LOG_FILE"

  if [ -f ./rollback.sh ]; then
    bash ./rollback.sh
  else
    echo "⚠️  rollback.sh not found — manual intervention required"
  fi
}

# ═════════════════════════════════════════════════════════════
# 5. MAIN HEALTH CHECK LOOP
# ═════════════════════════════════════════════════════════════

main() {
  echo "═══════════════════════════════════════════════════════════"
  echo "SOVEREIGN OS — HEALTH CHECK ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
  echo "═══════════════════════════════════════════════════════════"

  FAILURES=0

  # Check all services
  check_vision_api || ((FAILURES++))
  check_dashboard || ((FAILURES++))
  check_ollama || ((FAILURES++))
  check_vault || ((FAILURES++))
  check_prometheus || ((FAILURES++))
  check_jaeger || ((FAILURES++))

  # Check trace latency
  check_trace_latency || ((FAILURES++))

  # Snapshot state
  snapshot_state

  echo ""

  # Decision logic
  if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✅ ALL SYSTEMS HEALTHY${NC}" | tee -a "$LOG_FILE"
    echo "" >> "$LOG_FILE"
  elif [ $FAILURES -le 2 ]; then
    echo -e "${YELLOW}⚠️  DEGRADED (${FAILURES} issues, recovering)${NC}" | tee -a "$LOG_FILE"
    echo "" >> "$LOG_FILE"
  else
    echo -e "${RED}❌ CRITICAL (${FAILURES} failures)${NC}" | tee -a "$LOG_FILE"
    trigger_rollback
  fi
}

# ═════════════════════════════════════════════════════════════
# 6. LOOP RUNNER (runs every 60 seconds)
# ═════════════════════════════════════════════════════════════

if [ "$1" == "once" ]; then
  main
else
  while true; do
    main
    sleep $INTERVAL
  done
fi
