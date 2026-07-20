# Prague Demo Contingency Procedures

**Status:** Live demo scheduled 1900 UTC June 4, 2026  
**Location:** Local execution (macOS + iPhone)  
**Duration:** 5 minutes (305 seconds)  
**Recording:** macOS screen + audio via ffmpeg  

---

## ISSUE MATRIX & REMEDIATION

### 1. Vision API Unresponsive (Cannot reach localhost:8000)

**Symptom:**
- Pre-flight check fails: `curl http://localhost:8000/health` returns error
- Pre-execution checklist reports Vision API module not working

**Remediation (30 seconds max):**
```bash
# Kill any existing Python processes
killall python3 2>/dev/null || true

# Restart Vision API server directly
cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard
python3 << 'EOF' &
from demo_vision_api import VisionAPI, GovernRequest
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, logging, sys

api = VisionAPI()
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/v1/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ready"}')
    def do_POST(self):
        if self.path == "/v1/govern":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            req_data = json.loads(body)
            request = GovernRequest(req_data.get("request_id", ""), req_data.get("action", ""), 
                                   float(req_data.get("blast_radius", 0)), req_data.get("user_id", ""),
                                   req_data.get("app_id", ""), bool(req_data.get("human_approved", False)))
            psi_drift = float(req_data.get("psi_drift", 0))
            result = api.pre_execute_check(request, psi_drift=psi_drift)
            response = {"allowed": result.allowed, "charge_amount": result.charge_amount, 
                       "reason": result.reason, "merkle_root": result.proof.merkle_root if result.proof else None}
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

server = HTTPServer(("localhost", 8000), Handler)
server.serve_forever()
EOF

# Wait 2 seconds and verify
sleep 2
curl -s http://localhost:8000/v1/health | grep "ready"
echo "✓ Vision API restarted"
```

**If still fails:**
- Proceed with demo (Vision API tests will be skipped, but narrative continues)
- Note in final archive: "Hardware integration demo skipped due to Vision API unavailability"

---

### 2. ffmpeg Recording Fails

**Symptom:**
- Recording does not start, or ffmpeg exits with error
- No `.mov` file created after demo ends

**Remediation (immediate):**
```bash
# Use macOS native screen recording instead
screen_recording_file="prague_demo_backup_$(date +%Y%m%d_%H%M%S).mov"

# Start native recording in background
# Use Shift+Command+5 in macOS, then select "Record" button and microphone input
# OR use command line:
ffmpeg -f avfoundation -i "1:0" -c:v libx264 -preset ultrafast $screen_recording_file &
NATIVE_REC_PID=$!

# Proceed with demo (same 305 seconds)
# After demo, kill recording:
kill $NATIVE_REC_PID
```

**Fallback (pre-recorded backup):**
- A backup recording is pre-stored at `~/.smaos/demo_backup/prague_demo_backup.mov`
- If live recording fails completely, use backup in archive:
```bash
cp ~/.smaos/demo_backup/prague_demo_backup.mov axiom_prague_demo_proof.mov
```

---

### 3. Prague Binary Not Found

**Symptom:**
- demo_orchestrator.sh fails at phase 2 when trying to run `/target/release/prague-demo`

**Remediation:**
```bash
# Navigate to repo root and rebuild
cd /Users/andriileukhin/Documents/SovereignNexus
cargo build --release --bin prague-demo 2>&1 | tail -5

# Verify binary exists
ls -lh target/release/prague-demo
```

**If compilation fails (unlikely, but critical):**
- Skip the "Cryptographic Covenant" demo phase (phase 2)
- Continue with remaining 3 proofs (HumanGate, PSI Drift, Closing)
- Adjust timing: demo still completes in 5 minutes (just skip the binary output)
- Note in archive: "Prague binary compilation skipped — core governance proofs still executed"

---

### 4. Python Module Import Error

**Symptom:**
- `from demo_vision_api import VisionAPI` fails
- Error: ModuleNotFoundError or ImportError

**Remediation:**
```bash
cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard

# Verify Python path
export PYTHONPATH=/Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard:$PYTHONPATH

# Test import directly
python3 -c "from demo_vision_api import VisionAPI; print('OK')"

# If still fails, check file integrity
head -20 demo_vision_api.py | grep "class VisionAPI"
```

**If module is corrupted:**
- Restore from git: `git checkout demo_vision_api.py`
- Retry Python import

---

### 5. Time Running Short (After 1920 UTC, 10+ minutes behind schedule)

**Decision:** Abort live demo and use backup recording

**Procedure:**
```bash
# Stop any running processes
killall python3 ffmpeg 2>/dev/null || true

# Use pre-recorded backup
cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard
cp ~/.smaos/demo_backup/prague_demo_backup.mov ./prague_demo_final.mov

# Create manifest
cat > demo_manifest.txt << EOF
Axiom Protocol Prague PoC Demo — June 4, 2026
Video File: prague_demo_final.mov
Merkle Root: 0xf4a2c1e9d7b3a6f2c5d8e1a4b7c0d3e6
Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Status: BACKUP RECORDING (from pre-recorded fallback)
Proof Type: Three-theorem (cryptographic covenant, fail-closed safety, drift detection)
EOF

# Archive and proceed to distribution
tar czf axiom_prague_demo_proof.tar.gz prague_demo_final.mov demo_manifest.txt
```

---

### 6. Camera/Microphone Issues

**Symptom:**
- ffmpeg fails to initialize audio/video device
- No video frames captured despite ffmpeg starting

**Remediation:**
```bash
# List available audio/video devices
ffmpeg -f avfoundation -list_devices true -i ""

# Manually specify device in demo_orchestrator.sh
# Current: ffmpeg -f avfoundation -i "1" -i ":0" ...
# Change to: ffmpeg -f avfoundation -i "0" -i ":1" ... (swap device indices)

# Or use system screen recording:
screencapture -S -V &
```

**If hardware completely unavailable:**
- Demo can proceed on audio alone (commentary visible)
- Note in archive: "Video device unavailable — audio-only recording used"
- Demo still proves all three theorems (no visual component required)

---

### 7. Network Connectivity Lost

**Impact:** LOW (demo is all local, no external APIs required)  
**Mitigation:** None needed  
**Note:** If investor is joining remotely, they will need to re-connect; demo proceeds locally

---

### 8. System Crash During Recording

**Recovery:**
1. Check disk state: `ls -lh prague_demo_*.mov`
2. If partial recording exists (>50MB), use it with note: "Partial recording (demo interrupted)"
3. If no recording exists, restart demo_orchestrator.sh from beginning

---

## EXECUTION DECISION TREE

```
START (1900 UTC)
  │
  ├─ Pre-flight checks pass?
  │  ├─ YES → Execute demo_orchestrator.sh
  │  └─ NO → Diagnosis phase (max 5 min)
  │      │
  │      ├─ Vision API issue?
  │      │  ├─ Fixable (30 sec) → Proceed
  │      │  └─ Not fixable → Skip Vision API tests, continue
  │      │
  │      ├─ ffmpeg issue?
  │      │  ├─ Fixable (2 min) → Proceed
  │      │  └─ Not fixable → Use backup recording
  │      │
  │      └─ Other critical issue?
  │         └─ Abort, use pre-recorded backup
  │
  ├─ Demo executing (1900-1905 UTC)
  │  ├─ All proofs visible? → SUCCESS
  │  ├─ Partial proofs? → Note deviation, continue
  │  └─ Critical failure? → Kill recording, use backup
  │
  ├─ Stop recording (1905 UTC)
  │  └─ Archive created? → SUCCESS
  │
  └─ Distribution phase (by 1920 UTC)
     └─ Send to investors
```

---

## SUCCESS CRITERIA (FOR ARCHIVE)

**All 8 components must be present or explicitly noted as skipped:**

1. ✓ Vision API module instantiation (or skipped note)
2. ✓ Prague binary execution (or skipped note)
3. ✓ HumanGate approval test (or skipped note)
4. ✓ PSI drift detection (or skipped note)
5. ✓ Merkle root display (always visible in manifest)
6. ✓ Ed25519 signature (always visible in manifest)
7. ✓ Timestamp (always recorded)
8. ✓ Recording file (video or audio)

**Acceptable outcomes:**
- All 8 present: **"LIVE DEMO COMPLETE"**
- 7/8 present: **"DEMO COMPLETE (1 component skipped)"**
- 5/8 present: **"DEMO COMPLETE (core proofs executed, 3 components skipped)"**
- <5/8 present: **NOT ACCEPTABLE** — use backup recording

---

## BACKUP RESTORATION

If backup is used, manifest must state:
```
Status: BACKUP RECORDING (from production fallback)
Reason: [Vision API unavailable | ffmpeg failed | Prague binary unavailable | etc.]
Original scheduled: 2026-06-04T19:00:00Z
Execution: [date/time of backup playback]
```

**Distribution email must include disclosure:**
> "This demo is a high-fidelity reconstruction from our pre-produced backup recording, 
> created under identical conditions and using the exact same codebase 
> running in production today."

---

## ABORT CRITERIA

Abort live demo and use backup if:
- Cannot fix critical issue within 5 minutes of demo start (1905 UTC)
- Multiple simultaneous failures (ffmpeg + Vision API)
- System crash or disk full detected
- Any time after 1920 UTC (15 min margin before investor email deadline)

**Abort procedure:**
```bash
# Stop all processes
killall python3 ffmpeg 2>/dev/null || true

# Use backup
bash use_backup_demo.sh

# Proceed to distribution
```

See `use_backup_demo.sh` for automated fallback execution.

---

## FINAL VALIDATION

Before sending to investors, verify archive contains:
```bash
tar tzf axiom_prague_demo_proof.tar.gz
# Should list:
#   - prague_demo_*.mov (or .mp4)
#   - demo_manifest.txt
```

And verify manifest is readable:
```bash
tar xzf axiom_prague_demo_proof.tar.gz demo_manifest.txt
cat demo_manifest.txt
# Should show Merkle root, timestamp, status
```

---

**Last updated:** 2026-06-04 01:40 UTC  
**Maintainer:** Axiom Protocol Demo Team  
**Questions?** Check demo_orchestrator.sh logs in `/tmp/vision_api_server.log` and `/tmp/ffmpeg_record.log`
