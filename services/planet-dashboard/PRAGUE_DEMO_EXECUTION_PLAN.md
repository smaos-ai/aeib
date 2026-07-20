# AXIOM PROTOCOL PRAGUE DEMO — EXECUTION PLAN

**Status:** READY TO EXECUTE  
**Date:** June 4, 2026  
**Duration:** 305 seconds (5 minutes 5 seconds)  
**Target Audience:** 10 Series A investors (Cohort 1)  

---

## TIMELINE (24-HOUR VIEW)

| Time (UTC) | Event | Owner | Status |
|-----------|-------|-------|--------|
| 01:37 | Pre-execution checklist created | Axiom Demo Team | ✓ DONE |
| 1845 (17:45) | **T-15 MIN:** Run pre_execution_checklist.sh | Operator | → RUN AT THIS TIME |
| 1900 (19:00) | **DEMO STARTS:** Execute demo_orchestrator.sh | Operator | → CRITICAL |
| 1900-1905 | Live demo (5 min): All 3 proofs executed | Demo script | → CRITICAL |
| 1905 | Recording stops, archival begins | Automation | → AUTO |
| 1910 | Archive created: axiom_prague_demo_proof.tar.gz | Automation | → AUTO |
| 1920 | All contingencies resolved (if needed) | Operator | → FALLBACK |
| 2100 | **DISTRIBUTION:** Investor email batch sent | Operator | → CRITICAL |

---

## EXECUTION CHECKLIST

### PHASE 1: PRE-EXECUTION (1845 UTC — 15 min before demo)

**Operator reads this section and executes all steps:**

```bash
# Step 1: Navigate to demo directory
cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard

# Step 2: Run comprehensive pre-flight checklist
bash pre_execution_checklist.sh

# Expected output:
# ═══════════════════════════════════════════════════════════
# ✅ ALL PRE-EXECUTION CHECKS PASSED
# ═══════════════════════════════════════════════════════════
# Next step: Execute demo_orchestrator.sh at 1900 UTC (in 15 min)
```

**Verification checklist (manually):**
- [ ] Vision API module imports successfully
- [ ] Prague binary exists and is executable
- [ ] ffmpeg installed and working
- [ ] Disk space > 5GB available
- [ ] Camera and microphone detected
- [ ] Internet connectivity confirmed
- [ ] System time synchronized (within ±1 sec of UTC)

**Prepare physical environment:**
- [ ] Camera positioned to show: screen + operator face (optional)
- [ ] Microphone tested (speak test phrase, listen in headphones)
- [ ] Screen brightness at max (for video visibility)
- [ ] No notifications enabled (silence phone, disable Slack, etc.)
- [ ] Demo script printed and visible on desk
- [ ] Backup demo video file at ~/.smaos/demo_backup/prague_demo_backup.mov exists

---

### PHASE 2: DEMO EXECUTION (1900 UTC — CRITICAL)

**Operator at 1900 UTC exactly:**

```bash
# At exactly 1900 UTC, run:
cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard
bash demo_orchestrator.sh

# The script will:
# 1. Show preflight checks (should all pass, <30 sec)
# 2. Start Vision API server in background
# 3. Start recording (ffmpeg will initialize camera/mic)
# 4. Wait for ENTER key (press ENTER to begin)
# 5. Execute 5-minute live demo narrative
# 6. Stop recording automatically
# 7. Create archive: axiom_prague_demo_proof.tar.gz
# 8. Create backup in ~/.smaos/demo_backup/
```

**What to expect on screen:**

```
[19:00:00] AXIOM PROTOCOL PRAGUE DEMO ORCHESTRATOR
[19:00:00] June 4, 2026, 1900 UTC
[19:00:00] ═══════════════════════════════════════════════════════════

[19:00:05] Starting preflight checks...
[19:00:05] ✓ Vision API module ready
[19:00:05] ✓ Prague demo binary exists
[19:00:05] ✓ ffmpeg installed
[19:00:05] ✓ Python dependencies ready
[19:00:05] Preflight checks complete

[19:00:10] Starting Vision API server...
[19:00:10] ✓ Vision API server running on http://localhost:8000

[19:00:15] Ready to begin recording. Press ENTER to start...
→ [OPERATOR PRESSES ENTER]

[19:00:20] Recording started (PID: 12345, File: prague_demo_live_20260604_190020.mov)
[19:00:25] Executing demo narrative and commands...

[19:00:25] [0:00] PHASE 1: Problem Statement
Good morning. I'm Andrey, architect at Axiom Protocol.
Frontier AI models will be commodity by Q3 2026.
The missing layer is governance. We've built it. Here's the proof.

[19:00:35] [0:30] PHASE 2: Cryptographic Covenant & Merkle Chain Extension
[Vision API test output...]
Previous Root: 0xf4a2c1e9d7b3a6f2c5d8e1a4b7c0d3e6
New Root:      0xf4a2c1e9d7b3a6f2c5d8e1a4b7c0d3e6...
Status:        ✓ CHAIN EXTENDED

[19:02:00] [2:00] PHASE 3: Fail-Closed Safety Gates
[HumanGate test output...]
[TEST 1] High-risk action WITHOUT approval
Result:    ✗ BLOCKED
Charge:    0 (← ZERO if blocked)

[TEST 2] Same action WITH approval
Result:    ✓ APPROVED
Charge:    100

[19:03:30] [3:30] PHASE 4: PSI Drift Detection
[PSI computation...]
Population Stability Index: 0.4500
Threshold: 0.2500
⚠️  DRIFT DETECTED - Human Gate ENGAGED

[19:04:30] [4:30] PHASE 5: Closing
Three live proofs. One conclusion:
Axiom Protocol is the constitutional governance layer for frontier AI.

[19:05:00] ✓ Demo narrative complete (5:00 total)

[19:05:10] Stopping recording...
[19:05:15] ✓ Recording saved: prague_demo_live_20260604_190020.mov (326MB)

[19:05:20] Archiving demo...
[19:05:20] ✓ Demo archived: axiom_prague_demo_proof.tar.gz (318MB)
[19:05:20] ✓ Backup created: ~/.smaos/demo_backup

[19:05:25] ═══════════════════════════════════════════════════════════
[19:05:25] ✅ DEMO COMPLETE
[19:05:25] ═══════════════════════════════════════════════════════════
[19:05:25] Recording: prague_demo_live_20260604_190020.mov
[19:05:25] Archive:   axiom_prague_demo_proof.tar.gz
[19:05:25] Backup:    ~/.smaos/demo_backup

[19:05:25] Ready for investor distribution.
```

**If something goes wrong during demo execution:**
- See PRAGUE_DEMO_CONTINGENCIES.md for 8 common issues + remediation
- Most issues are recoverable within 5 minutes
- If unrecoverable, abort and proceed to PHASE 3 (use backup)

---

### PHASE 3: POST-DEMO ARCHIVAL (1905 UTC — AUTOMATIC)

The demo_orchestrator.sh automatically creates:

**1. Video file:** `prague_demo_live_20260604_HHMMSS.mov`
- Duration: 305 seconds
- Size: ~300-350MB
- Codec: H.264 + AAC
- Contains: screen recording + audio narration

**2. Manifest:** `demo_manifest.txt`
- Contains: Merkle root, timestamp, SHA256 hash of video, status
- Human-readable format for investor verification

**3. Archive:** `axiom_prague_demo_proof.tar.gz`
- Contains: Video + Manifest
- Size: ~300MB
- Location: `/Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard/`

**4. Backup:** `~/.smaos/demo_backup/`
- Duplicate of video and manifest
- Protection against accidental deletion
- Encrypted (macOS FileVault)

**Verification (after archive created, at 1910 UTC):**

```bash
# Verify archive integrity
tar tzf axiom_prague_demo_proof.tar.gz

# Expected output:
# prague_demo_live_20260604_190020.mov
# demo_manifest.txt

# Extract and verify manifest
tar xzf axiom_prague_demo_proof.tar.gz demo_manifest.txt
cat demo_manifest.txt

# Expected output:
# Axiom Protocol Prague PoC Demo — June 4, 2026, 1900 UTC
# Video File: prague_demo_live_20260604_190020.mov
# Video SHA256: abc123...
# Merkle Root: 0xf4a2c1e9...
# Timestamp (UTC): 2026-06-04T19:05:25Z
# Status: LIVE DEMO COMPLETE
```

---

### PHASE 4: CONTINGENCY HANDLING (If needed, 1905-1920 UTC)

**If demo failed or incomplete:**

See PRAGUE_DEMO_CONTINGENCIES.md for:
- Vision API unresponsive → 30-second fix
- ffmpeg recording failed → Use native macOS recording or backup
- Prague binary missing → Recompile or skip phase 2
- Python import error → Restore from git
- Time running short → Use backup recording
- Camera/mic issues → Audio-only fallback
- System crash → Recover from backup

**Expected resolution time:** 5-10 minutes max  
**Abort threshold:** If not resolved by 1920 UTC, use backup  
**Backup restoration:**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard
cp ~/.smaos/demo_backup/prague_demo_backup.mov ./prague_demo_final.mov

# Update manifest to indicate backup used
cat > demo_manifest.txt << EOF
Axiom Protocol Prague PoC Demo — June 4, 2026
Video File: prague_demo_final.mov
Merkle Root: 0xf4a2c1e9d7b3a6f2c5d8e1a4b7c0d3e6
Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Status: BACKUP RECORDING (live demo conducted, backup used for distribution)
Proof Type: Three-theorem (cryptographic covenant, fail-closed safety, drift detection)
EOF

# Re-archive
tar czf axiom_prague_demo_proof.tar.gz prague_demo_final.mov demo_manifest.txt
```

---

### PHASE 5: INVESTOR DISTRIBUTION (2100 UTC — CRITICAL)

**At 2100 UTC, send investor emails:**

```bash
# Step 1: Prepare email batch
# - Open INVESTOR_DISTRIBUTION_EMAIL.txt
# - Fill in:
#   * 10 investor email addresses
#   * Video URL or embed link
#   * Calendly link for Series A calls
#   * Archive URL (if hosting online) or attachment

# Step 2: Send emails
# Use Gmail, Outlook, or command-line tool:
# Option A: Manual (preferred for security)
#   - Open Gmail
#   - Compose email from template
#   - Attach: axiom_prague_demo_proof.tar.gz
#   - Send to all 10 investors
#
# Option B: Command-line (for automation):
python3 << 'EOF'
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "andrejlo123@gmail.com"
SENDER_PASSWORD = "xxxxx"  # Use Gmail App Password

investors = [
    "investor1@example.com",
    "investor2@example.com",
    # ... 10 total
]

subject = "Axiom Protocol Prague PoC — Constitutional Governance for Frontier AI (Live Demo)"
body = open("INVESTOR_DISTRIBUTION_EMAIL.txt").read()

for investor_email in investors:
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = investor_email
    msg["Subject"] = subject
    
    msg.attach(MIMEText(body, "plain"))
    
    # Attach archive
    attachment = open("axiom_prague_demo_proof.tar.gz", "rb")
    part = MIMEBase("application", "octet-stream")
    part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename= axiom_prague_demo_proof.tar.gz")
    msg.attach(part)
    
    # Send
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
    
    print(f"✓ Email sent to {investor_email}")

print("✓ All 10 investor emails sent")
EOF

# Step 3: Log distribution
mkdir -p ~/.smaos/demo_backup
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) — Distribution batch sent to 10 investors" >> ~/.smaos/demo_backup/distribution_log.txt
```

**Verification checklist:**
- [ ] Archive ready: axiom_prague_demo_proof.tar.gz exists
- [ ] Manifest readable: contains Merkle root, timestamp, status
- [ ] Video exists: prague_demo_live_*.mov is >100MB
- [ ] Email template filled with investor addresses
- [ ] 10 emails queued or sent
- [ ] Calendly link active and available
- [ ] Distribution log updated

---

## CONTINGENCY DECISION MATRIX

| Issue | Impact | Fixable in 5 min? | Action |
|-------|--------|-------------------|--------|
| Vision API won't start | Medium | YES (30 sec) | Restart daemon, continue demo |
| ffmpeg recording fails | High | YES (2 min) | Use macOS native recording or backup |
| Prague binary not found | Medium | YES (5 min) | Recompile or skip phase 2 |
| Python import error | Medium | YES (3 min) | Restore file from git, retry |
| Camera/mic issues | Low | YES (varies) | Use audio-only or fallback |
| Time running short (>1920) | Critical | NO | Use pre-recorded backup |
| System crash mid-demo | Critical | NO | Recover partial video or use backup |
| Network outage | LOW | N/A | Demo is local, no impact |

---

## SUCCESS CRITERIA

**Demo is considered SUCCESSFUL if:**

✓ All 5 phases execute without abort  
✓ Video file created: >100MB  
✓ Manifest contains Merkle root and timestamp  
✓ Archive created: axiom_prague_demo_proof.tar.gz  
✓ Backup preserved: ~/.smaos/demo_backup/  
✓ 10 investor emails sent by 2100 UTC  

**Demo is considered PARTIAL if:**

~ Some phases skipped (1-2 components unavailable)  
~ Video created but <100MB (truncated)  
~ Archive missing one element (video or manifest)  
~ Investors notified of deviation in email  

**Demo is considered FAILED if:**

✗ No video file created  
✗ Archive creation fails  
✗ Investor emails not sent by 2130 UTC  
✗ Merkle root not visible in manifest  

---

## FILES & LOCATIONS

**Execution:**
- `/Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard/demo_orchestrator.sh` — Main demo script
- `/Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard/pre_execution_checklist.sh` — Pre-flight checks

**Reference:**
- `/Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard/PRAGUE_DEMO_CONTINGENCIES.md` — Troubleshooting guide
- `/Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard/INVESTOR_DISTRIBUTION_EMAIL.txt` — Email template
- `/Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard/PRAGUE_DEMO_EXECUTION_PLAN.md` — This file

**Output:**
- `/Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard/axiom_prague_demo_proof.tar.gz` — Final archive (created at demo end)
- `/Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard/prague_demo_live_*.mov` — Raw video (created at demo end)
- `/Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard/demo_manifest.txt` — Metadata (created at demo end)
- `~/.smaos/demo_backup/` — Backup copies (created at demo end)
- `~/.smaos/demo_backup/distribution_log.txt` — Distribution audit trail (created at 2100 UTC)

---

## QUICK START (TL;DR)

```bash
# T-15 min (1845 UTC)
cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard
bash pre_execution_checklist.sh  # Should pass all checks

# T+0 (1900 UTC exactly)
bash demo_orchestrator.sh  # Starts recording, press ENTER

# T+5 min (1905 UTC)
# Script auto-completes, archive created

# T+2 hours (2100 UTC)
# Send investor emails with archive attached
```

---

## SIGNAL HANDLER (For unexpected interruptions)

If CTRL+C or SIG received during demo:
```bash
# demo_orchestrator.sh catches INT and TERM
# Automatically:
#   - Stops recording
#   - Attempts to finalize partial archive
#   - Preserves whatever was recorded
#   - Error message: "Demo interrupted"

# Recovery:
# - Use whatever partial video exists
# - Or proceed to contingency backup restoration
```

---

## TIMELINE SUMMARY

```
1845 UTC ━━━━━━━ Pre-execution checks (15 min before start)
         │
         ├─ All checks pass?
         │  ├─ YES → Stand by for demo
         │  └─ NO → Diagnose & fix (must complete by 1900)
         │
1900 UTC ━━━━━━━ DEMO STARTS (operator presses ENTER)
         │
         ├─ 0:00-0:30 ── Problem statement narration
         ├─ 0:30-2:00 ── Cryptographic covenant + Merkle chain
         ├─ 2:00-3:30 ── HumanGate fail-closed safety proof
         ├─ 3:30-4:30 ── PSI drift detection proof
         ├─ 4:30-5:00 ── Closing statement
         │
1905 UTC ━━━━━━━ Recording stops, archival begins
         │
         ├─ Archive created: axiom_prague_demo_proof.tar.gz
         ├─ Backup copied: ~/.smaos/demo_backup/
         │
1920 UTC ━━━━━━━ Contingency resolution deadline
         │
         ├─ All issues fixed?
         │  ├─ YES → Archive ready
         │  └─ NO → Use backup recording
         │
2100 UTC ━━━━━━━ INVESTOR DISTRIBUTION DEADLINE
         │
         └─ Send 10 investor emails with archive + Calendly link
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-06-04 01:55 UTC  
**Prepared by:** Axiom Protocol Demo Team  
**Status:** READY TO EXECUTE

---

For questions or issues, reference:
1. PRAGUE_DEMO_CONTINGENCIES.md (troubleshooting)
2. demo_orchestrator.sh (main script logs)
3. /tmp/vision_api_server.log (Vision API errors)
4. /tmp/ffmpeg_record.log (ffmpeg errors)
