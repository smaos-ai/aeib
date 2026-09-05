# DEMO EXECUTION QUICK START — June 4, 1900 UTC

**Status:** Ready to execute ✅  
**Duration:** 5 minutes exactly  
**Setup time:** 30 minutes (1830–1900 UTC)  
**Output:** Cryptographically signed 5-minute proof of constitutional governance

---

## QUICK COMMAND SEQUENCE

### [1830–1900] SETUP PHASE (30 min)

```bash
# 1. Navigate to demo directory
cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard

# 2. Make orchestrator executable
chmod +x demo_orchestrator.sh

# 3. Open text editor with script (in second monitor/window)
# See: DEMO_FINAL_MASTER_ORCHESTRATION.md (Part 2.1–2.5)

# 4. Verify all systems ready
./demo_orchestrator.sh --preflight

# Expected output:
# ✓ Vision API module ready
# ✓ Prague demo binary exists
# ✓ ffmpeg installed
# ✓ Python dependencies ready

# 5. Manual verification (5 min)
echo "Open browser to these in background:"
echo "  - Dashboard: http://localhost:8501 (will start auto with demo)"
echo "  - Vision API health: curl http://localhost:8000/v1/health"
```

### [1900] EXECUTE DEMO (5 min)

```bash
# START RECORDING + EXECUTION
# Exact timing: This script handles everything

cd /Users/andriileukhin/Documents/SovereignNexus/services/planet-dashboard
./demo_orchestrator.sh

# Output during execution (watch terminal):
# [19:00:00] Starting recording (305 seconds)...
# [19:00:02] Executing demo narrative and commands...
# [19:00:00] PHASE 1: Problem Statement
# [19:00:30] PHASE 2: Cryptographic Covenant
# [19:02:00] PHASE 3: Fail-Closed Safety Gates
# [19:03:30] PHASE 4: PSI Drift Detection
# [19:04:30] PHASE 5: Closing
# [19:05:00] Stopping recording...
# ✓ Demo archived: axiom_prague_demo_proof.tar.gz
```

### [1905–1915] POST-DEMO (10 min)

```bash
# 1. Verify recording quality
RECORDING=$(ls -t prague_demo_live_*.mov | head -1)
du -h "$RECORDING"  # Should be ~250-300MB
ffplay -autoexit -window_title "QA" "$RECORDING" &

# 2. Verify archive
ls -lh axiom_prague_demo_proof.tar.gz

# 3. Verify manifest signed + locked
cat demo_manifest.txt

# 4. Backup already created by orchestrator
ls -la ~/.smaos/demo_backup/

echo "✅ DEMO READY FOR INVESTOR DISTRIBUTION"
```

---

## WHAT IF SOMETHING GOES WRONG?

### Recording Failed
```bash
# Kill processes
pkill -f ffmpeg
pkill -f streamlit

# Reset + retry
rm prague_demo_live_*.mov axiom_prague_demo_proof.tar.gz
sleep 10

# Re-run orchestrator from scratch
./demo_orchestrator.sh
```

### Vision API Not Responding
```bash
# Check if server is running
curl -s http://localhost:8000/v1/health | jq .status

# If not, kill and restart
pkill -f "python.*vision_api"
sleep 2

# Run orchestrator again (it restarts Vision API)
./demo_orchestrator.sh
```

### Audio Out of Sync
```bash
# Use backup recording (orchestrator creates one)
cp ~/.smaos/demo_backup/prague_demo_live_*.mov ./
tar czf axiom_prague_demo_proof.tar.gz \
  prague_demo_live_*.mov \
  demo_manifest.txt
```

### Out of Time (Need to Start ASAP)
```bash
# Option 1: Skip preflight, go straight to recording
./demo_orchestrator.sh 2>&1 | grep -A 100 "Ready to begin"

# Option 2: Run in background, capture output
nohup ./demo_orchestrator.sh > demo_execution.log 2>&1 &

# Monitor progress
tail -f demo_execution.log
```

---

## CHECKLIST (Execute in order)

**Before 1830:**
- [ ] Read: DEMO_FINAL_MASTER_ORCHESTRATION.md (complete context)
- [ ] Read: This file (quick start)
- [ ] Test: `python3 -c "from vision_api import VisionAPI; VisionAPI()"`
- [ ] Verify: `ls -lh target/release/prague-demo`
- [ ] Verify: `which ffmpeg` (installed)

**1830–1900 (Setup):**
- [ ] `chmod +x demo_orchestrator.sh`
- [ ] Run: `./demo_orchestrator.sh --preflight`
- [ ] Verify all output shows ✓
- [ ] Open Streamlit dashboard (browser)
- [ ] Test iOS Shortcut on secondary device (tap "Run")
- [ ] Set screen resolution to 1920×1080
- [ ] Adjust lighting, clear background

**1900 (Execute):**
- [ ] `./demo_orchestrator.sh` (press ENTER when ready)
- [ ] Record for exactly 5 minutes
- [ ] Follow narration script (in Part 2.1–2.5 of master doc)
- [ ] Demonstrate all three proofs:
  1. Merkle chain extension (cryptographic covenant)
  2. HumanGate blocking high-risk without approval
  3. PSI drift gauge triggering auto-gate

**1905–1910 (QA):**
- [ ] Playback recording: `ffplay -autoexit prague_demo_live_*.mov`
- [ ] Verify: 1920×1080, 30fps, clear audio
- [ ] Verify: All three sections visible + readable
- [ ] Verify: Merkle root shown for ≥3 seconds at end
- [ ] Verify: Final signature visible
- [ ] Check file size: `du -h prague_demo_live_*.mov` (~250MB)

**1910–1915 (Archival):**
- [ ] Archive created: `ls -lh axiom_prague_demo_proof.tar.gz`
- [ ] Manifest signed: `cat demo_manifest.txt`
- [ ] Backup created: `ls ~/.smaos/demo_backup/`
- [ ] Ready for distribution

---

## SCRIPT OUTPUTS EXPLAINED

### Vision API Server Log
```
[19:00:00] Vision API server ready on http://localhost:8000
```
✓ Server started successfully

### Recording Start
```
[19:00:02] Recording started (PID: 12345, File: prague_demo_live_20260604_190002.mov)
```
✓ ffmpeg is capturing

### Demo Phases
```
[19:00:00] PHASE 1: Problem Statement
[19:00:30] PHASE 2: Cryptographic Covenant
[19:02:00] PHASE 3: Fail-Closed Safety Gates
[19:03:30] PHASE 4: PSI Drift Detection
[19:04:30] PHASE 5: Closing
```
✓ Each phase executing on schedule

### Archive Created
```
✓ Demo archived: axiom_prague_demo_proof.tar.gz (280M)
✓ Backup created: ~/.smaos/demo_backup
```
✓ Archival locked, ready for distribution

---

## FILE LOCATIONS

| File | Location | Purpose |
|------|----------|---------|
| Orchestrator | `services/planet-dashboard/demo_orchestrator.sh` | Main execution script |
| Master Doc | `.claude/DEMO_FINAL_MASTER_ORCHESTRATION.md` | Full details + contingencies |
| This Doc | `.claude/DEMO_EXECUTION_QUICK_START.md` | Quick reference (you are here) |
| Recording | `prague_demo_live_YYYYMMDD_HHMMSS.mov` | Output video (~250MB) |
| Archive | `axiom_prague_demo_proof.tar.gz` | Distribution package |
| Backup | `~/.smaos/demo_backup/` | Fallback copy |

---

## EXPECTED FINAL STATE (1920 UTC)

```
✅ prague_demo_live_20260604_190002.mov (280MB, 5:00 duration)
✅ axiom_prague_demo_proof.tar.gz (282MB, signed)
✅ demo_manifest.txt (Merkle root locked)
✅ ~/.smaos/demo_backup/ (full backup)
✅ All tests passed (HumanGate, drift detection, Merkle extension)
✅ Ready for investor email distribution
```

---

## TIMING REFERENCE

| Time | Event | Action |
|------|-------|--------|
| 1830 | Setup begin | Read docs, test systems |
| 1855 | Final preflight | Run `demo_orchestrator.sh --preflight` |
| 1900 | Demo start | Press ENTER to begin recording |
| 1905 | Demo end | Recording stops automatically |
| 1910 | QA verification | Playback + audio sync check |
| 1915 | Archival complete | Files locked + backup created |

**Total time from start to distribution-ready:** 45 minutes

---

## SUCCESS = ✅ ALL OF THESE

- [ ] Recording: exactly 5:00 ± 2 seconds
- [ ] Quality: 1920×1080, 30fps, clear audio, properly synced
- [ ] Content: All three proofs clearly demonstrated
- [ ] Signatures: Merkle root + Ed25519 visible + verifiable
- [ ] Files: Archive created + backup exists
- [ ] Ready: Next step is sending to investors

**If all are ✅, you are done.**

---

## INVESTOR HANDOFF

Once demo is archived:

```bash
# Send to investors
ARCHIVE="axiom_prague_demo_proof.tar.gz"
MANIFEST="demo_manifest.txt"

# Email template (personalize per investor):
cat <<EOF

Subject: Axiom Protocol — Live Demo (5 min, cryptographically signed)

Dear [Investor Name],

Please find attached our Prague PoC demonstration of constitutional governance in action.

This 5-minute recording shows:
1. Cryptographic covenant enforcement (Merkle-rooted settlement)
2. Fail-closed safety gates (HumanGate blocking high-risk decisions)
3. Drift detection (PSI monitoring with auto-engagement)

All artifacts are Ed25519-signed and Merkle-locked.

Available for 15-minute call this week.

Best regards,
Andrey
Axiom Protocol

---
Attachments: $ARCHIVE (282MB), $MANIFEST
EOF

# Send via email client
# (Include in Series A batch, June 4, 2100 UTC)
```

---

**READY?**

1. Read full master doc: `.claude/DEMO_FINAL_MASTER_ORCHESTRATION.md`
2. Run quick preflight: `./demo_orchestrator.sh --preflight`
3. Execute at 1900 UTC: `./demo_orchestrator.sh`
4. Verify + archive (10 min)
5. Ship to investors

🌍⚖️🔐
