#!/bin/bash
set -e

# ═════════════════════════════════════════════════════════════════
# Phase 2C Health Monitor: Periodic service health checks
# Polls /health endpoints every 5s, logs status, alerts on failures
# ═════════════════════════════════════════════════════════════════

LOG_FILE="/var/log/phase2c-health.log"
INTERVAL=5
SUCCESSES=0
FAILURES=0

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Phase 2C health monitor" | tee -a "$LOG_FILE"

while true; do
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

  # Check Ollama service
  OLLAMA_HEALTH=$(curl -s -m 5 http://localhost:11434/api/tags 2>&1)
  OLLAMA_STATUS="✓"
  if [ -z "$OLLAMA_HEALTH" ]; then
    OLLAMA_STATUS="✗"
    FAILURES=$((FAILURES + 1))
  else
    SUCCESSES=$((SUCCESSES + 1))
  fi

  # Check App service
  APP_HEALTH=$(curl -s -m 5 http://localhost:5173/health 2>&1)
  APP_STATUS="✓"
  if ! echo "$APP_HEALTH" | grep -q "ok\|healthy\|true" 2>/dev/null; then
    APP_STATUS="✗"
    FAILURES=$((FAILURES + 1))
  else
    SUCCESSES=$((SUCCESSES + 1))
  fi

  # Check SLA Monitor service
  SLA_HEALTH=$(curl -s -m 5 http://localhost:9000/api/status 2>&1)
  SLA_STATUS="✓"
  if [ -z "$SLA_HEALTH" ]; then
    SLA_STATUS="✗"
    FAILURES=$((FAILURES + 1))
  else
    SUCCESSES=$((SUCCESSES + 1))
  fi

  # Log status
  TOTAL=$((SUCCESSES + FAILURES))
  UPTIME_PCT=$((SUCCESSES * 100 / TOTAL))
  LOG_LINE="[$TIMESTAMP] Ollama: $OLLAMA_STATUS | App: $APP_STATUS | SLA: $SLA_STATUS | Uptime: $UPTIME_PCT% ($SUCCESSES/$TOTAL)"
  echo "$LOG_LINE" | tee -a "$LOG_FILE"

  # Alert on critical failure
  if [ "$FAILURES" -ge 3 ]; then
    echo "[$TIMESTAMP] ALERT: Multiple service failures detected" | tee -a "$LOG_FILE"
    exit 1
  fi

  sleep "$INTERVAL"
done
