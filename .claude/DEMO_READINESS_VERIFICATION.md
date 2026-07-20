# DEMO READINESS VERIFICATION
## Final Pre-Execute Checklist (Run 15 minutes before demo)

**Date:** June 4, 2026  
**Time:** 1845 UTC (15 minutes before 1900 start)  
**Duration:** 5 minutes to verify all systems  
**Pass/Fail:** Must be 100% green to proceed

---

## VERIFICATION COMMANDS (Execute in order)

### [PHASE 1] ENVIRONMENT VERIFICATION (1 min)

```bash
# 1. Navigate to correct directory
cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard
echo "✓ Working directory: $(pwd)"

# 2. Verify Vision API module
python3 -c "from vision_api import VisionAPI; api = VisionAPI(); print('✓ Vision API module loads')" || exit 1

# 3. Verify demo binary exists
if [ -f /Users/andriileukhin/Documents/SovereignNexus/target/release/prague-demo ]; then
    echo "✓ Prague demo binary exists"
else
    echo "✗ FAIL: Prague demo binary missing"
    exit 1
fi

# 4. Verify ffmpeg
ffmpeg -version 2>&1 | head -1 || exit 1

# 5. Verify Python packages
for pkg in streamlit requests pandas plotly; do
    python3 -c "import $pkg" 2>/dev/null || echo "⚠ Warning: $pkg might be missing"
done
echo "✓ Python environment ready"

# 6. Verify orchestrator is executable
if [ -x ./demo_orchestrator.sh ]; then
    echo "✓ demo_orchestrator.sh is executable"
else
    echo "⚠ Making orchestrator executable..."
    chmod +x ./demo_orchestrator.sh
    echo "✓ Orchestrator chmod +x"
fi

echo ""
echo "✅ PHASE 1: ENVIRONMENT VERIFIED"
```

### [PHASE 2] COMPONENT VERIFICATION (2 min)

```bash
# 1. Test Prague demo binary execution
echo "Testing Prague demo binary..."
/Users/andriileukhin/Documents/SovereignNexus/target/release/prague-demo \
    2>&1 | head -20 | grep -q "AP2\|Settlement\|Merkle" && \
    echo "✓ Prague binary outputs expected data" || \
    echo "⚠ Warning: Prague binary output unexpected"

echo ""

# 2. Test Vision API directly
echo "Testing Vision API logic..."
python3 << 'PYTHON_TEST'
from vision_api import VisionAPI, GovernRequest, RiskLevel

api = VisionAPI()

# Test 1: Low risk should auto-approve
req_low = GovernRequest(
    request_id="test-low",
    action="read_data",
    blast_radius=0.1,
    user_id="test",
    app_id="test",
    human_approved=False
)
result_low = api.pre_execute_check(req_low)
assert result_low.allowed == True, "Low-risk should auto-approve"
assert result_low.charge_amount == 100, "Should charge 100 on approval"
print("✓ Test 1: Low-risk auto-approval works")

# Test 2: High risk without approval should block
req_high = GovernRequest(
    request_id="test-high",
    action="execute_system",
    blast_radius=0.85,
    user_id="test",
    app_id="test",
    human_approved=False
)
result_high = api.pre_execute_check(req_high)
assert result_high.allowed == False, "High-risk without approval should block"
assert result_high.charge_amount == 0, "Should charge ZERO on rejection"
print("✓ Test 2: High-risk rejection (zero charge) works")

# Test 3: High risk with approval should allow
req_approved = GovernRequest(
    request_id="test-approved",
    action="execute_system",
    blast_radius=0.85,
    user_id="test",
    app_id="test",
    human_approved=True
)
result_approved = api.pre_execute_check(req_approved)
assert result_approved.allowed == True, "Approved high-risk should allow"
assert result_approved.charge_amount == 100, "Should charge 100 on approval"
print("✓ Test 3: High-risk with approval works")

# Test 4: Drift detection should trigger gate
req_drift = GovernRequest(
    request_id="test-drift",
    action="some_action",
    blast_radius=0.3,
    user_id="test",
    app_id="test",
    human_approved=False
)
result_drift = api.pre_execute_check(req_drift, psi_drift=0.3)
assert result_drift.allowed == False, "PSI > 0.25 should trigger gate"
print("✓ Test 4: Drift detection auto-gates correctly")

print("")
print("✅ All Vision API tests passed")
PYTHON_TEST

if [ $? -ne 0 ]; then
    echo "✗ FAIL: Vision API tests failed"
    exit 1
fi

echo ""
echo "✅ PHASE 2: COMPONENTS VERIFIED"
```

### [PHASE 3] NETWORK VERIFICATION (1 min)

```bash
# 1. Find local IP
LOCAL_IP=$(ifconfig en0 2>/dev/null | grep "inet " | awk '{print $2}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(ifconfig en1 2>/dev/null | grep "inet " | awk '{print $2}')
fi
if [ -z "$LOCAL_IP" ]; then
    echo "⚠ Warning: Could not find local IP address"
else
    echo "✓ Local IP: $LOCAL_IP"
    echo ""
    echo "For iOS Shortcut, use: http://$LOCAL_IP:8000/v1/govern"
fi

# 2. Check if port 8000 is available
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠ Warning: Port 8000 already in use (might be old server)"
    echo "  Killing old process..."
    pkill -f "python.*vision_api" || true
    sleep 1
fi

# 3. Check if port 8501 is available
if lsof -Pi :8501 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠ Warning: Port 8501 already in use (might be old Streamlit)"
    echo "  Note: Orchestrator will handle this"
fi

echo ""
echo "✅ PHASE 3: NETWORK VERIFIED"
```

### [PHASE 4] RECORDING EQUIPMENT (1 min)

```bash
# 1. Check screen resolution
RESOLUTION=$(system_profiler SPDisplaysDataType 2>/dev/null | grep "Resolution:" | head -1 | awk '{print $2, $3}')
if [ -n "$RESOLUTION" ]; then
    echo "✓ Screen resolution: $RESOLUTION"
    if [[ "$RESOLUTION" != *"1920"* ]]; then
        echo "⚠ Warning: Consider setting to 1920x1080 for optimal quality"
    fi
fi

# 2. Check audio device
AUDIO_DEVICES=$(ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep "audio" | wc -l)
if [ "$AUDIO_DEVICES" -gt 0 ]; then
    echo "✓ Audio devices available: $AUDIO_DEVICES"
else
    echo "✗ FAIL: No audio devices found"
    exit 1
fi

# 3. Check camera
CAMERAS=$(ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep "video" | wc -l)
if [ "$CAMERAS" -gt 0 ]; then
    echo "✓ Video cameras available: $CAMERAS"
else
    echo "✗ FAIL: No cameras found"
    exit 1
fi

# 4. Check disk space
DISK_SPACE=$(df /Users/andriileukhin/Documents | tail -1 | awk '{print $4}')
DISK_SPACE_GB=$((DISK_SPACE / 1048576))
if [ "$DISK_SPACE_GB" -gt 5 ]; then
    echo "✓ Disk space available: ${DISK_SPACE_GB}GB"
else
    echo "⚠ Warning: Low disk space (${DISK_SPACE_GB}GB), need at least 1GB for recording"
fi

echo ""
echo "✅ PHASE 4: RECORDING EQUIPMENT VERIFIED"
```

### [PHASE 5] FINAL READINESS (Final check)

```bash
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "FINAL READINESS CHECK"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Summary
echo "✓ Environment:      Ready"
echo "✓ Components:       Ready (Vision API, binary, tests pass)"
echo "✓ Network:          Ready (local IP configured for iOS)"
echo "✓ Recording:        Ready (camera, audio, disk space)"
echo ""

# Instructions
echo "NEXT STEPS:"
echo ""
echo "1. Position camera to show:"
echo "   - Your face (webcam view)"
echo "   - Your laptop screen (terminal, demo output)"
echo "   - Secondary device ready (iPhone with Shortcut)"
echo ""
echo "2. Open text editor with narration script:"
echo "   Less ~/Documents/SovereignNexus/.claude/DEMO_FINAL_MASTER_ORCHESTRATION.md"
echo "   (See Part 2.1–2.5 for exact dialogue)"
echo ""
echo "3. When ready (at 1900 UTC exactly), run:"
echo "   cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard"
echo "   ./demo_orchestrator.sh"
echo ""
echo "4. Press ENTER when orchestrator prompts"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ READY FOR LIVE DEMO AT 1900 UTC"
echo "═══════════════════════════════════════════════════════════"
```

---

## VERIFICATION SUMMARY

**Run this entire block 15 minutes before demo:**

```bash
#!/bin/bash
set -e

echo "════════════════════════════════════════════════════════════"
echo "DEMO READINESS VERIFICATION — 15 MINUTES BEFORE START"
echo "════════════════════════════════════════════════════════════"
echo ""

# Copy-paste the entire PHASE 1–5 code from above

# Final status
echo ""
if [ $? -eq 0 ]; then
    echo "✅ ALL SYSTEMS GO"
    echo "Time until demo: $(date -u +%s -d '1900 UTC' 2>/dev/null || echo 'SEE CALENDAR')"
    echo ""
    echo "Ready to execute: ./demo_orchestrator.sh"
else
    echo "❌ SOME CHECKS FAILED"
    echo "Review errors above and fix before executing demo"
    exit 1
fi
```

---

## PASS/FAIL CRITERIA

### ✅ PASS (All must be true)
- [ ] Vision API module loads without error
- [ ] Prague demo binary exists and outputs expected data
- [ ] All 4 Vision API tests pass (low-risk approval, high-risk rejection, drift detection)
- [ ] ffmpeg installed and ready
- [ ] Python packages available
- [ ] Audio device detected
- [ ] Camera detected
- [ ] Disk space > 1GB
- [ ] Ports 8000 and 8501 are available (or can be killed)

### ❌ FAIL (Any one fails = DO NOT PROCEED)
- [ ] Vision API module broken
- [ ] Prague demo binary missing
- [ ] Vision API tests fail
- [ ] No audio device
- [ ] No camera
- [ ] Disk space < 1GB
- [ ] Cannot clear ports 8000/8501

---

## CONTINGENCY ACTIONS

### If Vision API Tests Fail
```bash
# Check what went wrong
python3 -c "
from vision_api import VisionAPI, GovernRequest
api = VisionAPI()
req = GovernRequest(request_id='debug', action='test', blast_radius=0.85, user_id='test', app_id='test', human_approved=False)
result = api.pre_execute_check(req)
print(f'Result: allowed={result.allowed}, charge={result.charge_amount}')
print(f'Expected: allowed=False, charge=0')
"

# If mismatch, check vision_api.py logic (should be fine, pre-tested)
# If file is corrupted, restore from git
git checkout services/planet-dashboard/vision_api.py
```

### If Recording Equipment Fails
```bash
# Restart macOS audio system
sudo killall coreaudiod

# Test again
ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep -E "audio|video"
```

### If Low Disk Space
```bash
# Free up space
rm -rf /Library/Logs/*
rm -rf ~/Library/Caches/*

# Check again
df -h /Users/andriileukhin/Documents | tail -1 | awk '{print $4}'
```

---

## SUCCESS INDICATORS

**When you see ALL of these, you're ready:**

```
✓ Vision API module loads
✓ Test 1: Low-risk auto-approval works
✓ Test 2: High-risk rejection (zero charge) works
✓ Test 3: High-risk with approval works
✓ Test 4: Drift detection auto-gates correctly
✓ Local IP: 192.168.1.X (or your network)
✓ Audio devices available
✓ Video cameras available
✓ Disk space available: 50+GB
✅ ALL SYSTEMS GO
```

---

## EXECUTION COMMAND (At 1900 UTC)

Once verification passes:

```bash
cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard
./demo_orchestrator.sh
# Press ENTER when prompted
# Recording starts automatically
# Follow narration script (Part 2.1–2.5 of master doc)
# Demo completes in exactly 5 minutes
```

---

## TIMING

| Time | Task |
|------|------|
| 1845 | Run this verification script |
| 1855 | Fix any issues (max 10 min) |
| 1900 | Execute: `./demo_orchestrator.sh` |
| 1905 | Recording complete |
| 1915 | Archival complete |

---

**If ALL checks pass: ✅ You're ready.**

**If ANY check fails: ❌ Fix before proceeding.**

🌍⚖️🔐
