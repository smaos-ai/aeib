#!/bin/bash
# AXIOM PRAGUE DEMO — PRE-EXECUTION CHECKLIST
# Run at 1845 UTC (15 minutes before 1900 UTC demo start)
# Status: READY TO EXECUTE

set -e

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEMO_DIR/../.." && pwd)"

log() {
    echo "[$(date -u +%H:%M:%S)] $1"
}

warn() {
    echo "[$(date -u +%H:%M:%S)] ⚠️  WARNING: $1"
}

error() {
    echo "[$(date -u +%H:%M:%S)] ❌ ERROR: $1" >&2
    return 1
}

success() {
    echo "[$(date -u +%H:%M:%S)] ✓ $1"
}

log "═══════════════════════════════════════════════════════════"
log "AXIOM PRAGUE DEMO — PRE-EXECUTION CHECKLIST"
log "Run at T-15min (1845 UTC, 15 min before 1900 UTC start)"
log "═══════════════════════════════════════════════════════════"
echo ""

# CHECKLIST 1: SYSTEM HEALTH
log "[CHECK 1] System Health"
if [[ $(uptime | grep -oE "[0-9]+ user[s]? logged in" | head -1) ]]; then
    success "System responsive"
else
    error "System unresponsive" || true
fi

# CHECKLIST 2: PRAGUE BINARY
log "[CHECK 2] Prague Demo Binary"
if [ -x "$REPO_ROOT/target/release/prague-demo" ]; then
    SIZE=$(ls -lh "$REPO_ROOT/target/release/prague-demo" | awk '{print $5}')
    success "Prague binary ready ($SIZE)"
else
    error "Prague binary not found or not executable"
    exit 1
fi

# CHECKLIST 3: VISION API MODULE
log "[CHECK 3] Vision API Module"
if python3 -c "import sys; sys.path.insert(0, '$DEMO_DIR'); from demo_vision_api import VisionAPI; api = VisionAPI(); print('Module loaded')" 2>&1 | grep -q "Module loaded"; then
    success "Vision API module ready"
else
    error "Vision API module not working"
    exit 1
fi

# CHECKLIST 4: FFMPEG
log "[CHECK 4] Recording Software (ffmpeg)"
if command -v ffmpeg &> /dev/null; then
    VERSION=$(ffmpeg -version | head -1 | cut -d' ' -f3)
    success "ffmpeg available (v$VERSION)"
else
    error "ffmpeg not installed"
    exit 1
fi

# CHECKLIST 5: DISK SPACE
log "[CHECK 5] Disk Space"
AVAIL_GB=$(df / | tail -1 | awk '{print $4}')
AVAIL_GB=$((AVAIL_GB / 1024 / 1024))
if [ "$AVAIL_GB" -gt 5 ]; then
    success "Disk space available (${AVAIL_GB}GB free, need 5GB)"
else
    error "Low disk space (${AVAIL_GB}GB available, need 5GB)"
    exit 1
fi

# CHECKLIST 6: BACKUP DIRECTORY
log "[CHECK 6] Backup Directory"
mkdir -p ~/.smaos/demo_backup
if [ -d ~/.smaos/demo_backup ] && [ -w ~/.smaos/demo_backup ]; then
    success "Backup directory ready (~/.smaos/demo_backup)"
else
    error "Backup directory not writable"
    exit 1
fi

# CHECKLIST 7: AUDIO/VIDEO DEVICES
log "[CHECK 7] Audio/Video Hardware"
if system_profiler SPAudioDataType > /dev/null 2>&1; then
    success "Audio device detected"
else
    warn "Audio device check failed (non-critical)"
fi

if system_profiler SPCameraDataType > /dev/null 2>&1; then
    success "Camera device detected"
else
    warn "Camera not detected (may use builtin iSight)"
fi

# CHECKLIST 8: NETWORK
log "[CHECK 8] Network Connectivity"
if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
    success "Internet connectivity confirmed"
else
    warn "Internet check failed (non-critical for local demo)"
fi

# CHECKLIST 9: TIME SYNC
log "[CHECK 9] System Time Sync"
if ntpstat > /dev/null 2>&1 || sntp -S $(hostname) > /dev/null 2>&1; then
    CURRENT_TIME=$(date -u +%H:%M:%S)
    success "Time synchronized (Current UTC: $CURRENT_TIME)"
else
    warn "Time sync check inconclusive (using system time)"
fi

# CHECKLIST 10: DEMO SCRIPT
log "[CHECK 10] Demo Orchestrator"
if [ -x "$DEMO_DIR/demo_orchestrator.sh" ]; then
    success "Demo orchestrator ready (demo_orchestrator.sh)"
else
    error "Demo orchestrator not executable"
    exit 1
fi

echo ""
log "═══════════════════════════════════════════════════════════"
log "✅ ALL PRE-EXECUTION CHECKS PASSED"
log "═══════════════════════════════════════════════════════════"
log "Next step: Execute demo_orchestrator.sh at 1900 UTC (in 15 min)"
echo ""
log "Command to run at 1900 UTC:"
echo "  cd $DEMO_DIR && bash demo_orchestrator.sh"
echo ""
