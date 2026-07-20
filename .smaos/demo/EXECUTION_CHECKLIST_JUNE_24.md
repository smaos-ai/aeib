# Prague Demo — Execution Checklist (June 24, 2026)
**Timeline:** 0800–1100 UTC (3 hours)  
**Owner:** Demo Team (Andrei)  
**Status:** Ready for Execution  
**Validation Gate:** All 4 deliverables complete and verified  

---

## Pre-Execution (0800 UTC) — 10 minutes

### Network & Environment Setup
- [ ] Verify WiFi OFF (network isolation check)
- [ ] Verify no git remotes configured (`git remote -v` returns empty)
- [ ] Verify no established connections (`lsof -i -P -n | grep ESTABLISHED` returns 0)
- [ ] Verify demo-app binary built (`target/release/demo-app` exists)
- [ ] Verify no cloud SDK refs in binary (`strings target/release/demo-app | grep -i aws/azure/gcp` returns empty)

### Directory Structure
- [ ] Confirm demo output directory exists: `/Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/`
- [ ] Confirm videos subdirectory exists: `./videos/`
- [ ] Confirm all 4 test scripts readable (dry_run_test_script.md, demo_validation_results.md, demo_video_script.md, ARTIFACT_MANIFEST.md)

### Pre-Flight Log
- [ ] Create timestamped log: `logs/dry_run_test_20260624_0800UTC.log`
- [ ] Redirect all test output to log file: `command 2>&1 | tee logs/...`

---

## Phase 1: Dry-Run Test Execution (0810–0900 UTC) — 50 minutes

### Test 1: Happy Path (0810–0815, 5 min)
- [ ] Run: `./target/release/demo-app --scenario test_happy_path --log-level info`
- [ ] Expect: All 5 gates pass, execution successful, Ed25519 signature generated
- [ ] Log: Capture full output to test log
- [ ] Result: ☐ PASS / ☐ FAIL — note any issues

### Test 2: Merkle-DAG Injection (0815–0820, 5 min)
- [ ] Run: `./target/release/demo-app --scenario test_merkle_tamper --log-level info --inject-payload "malicious_data"`
- [ ] Expect: Merkle verification fails, execution blocked, Andon breaker triggers
- [ ] Log: Capture full output
- [ ] Result: ☐ PASS / ☐ FAIL

### Test 3: Lineage Tamper (0820–0825, 5 min)
- [ ] Run: `./target/release/demo-app --scenario test_lineage_tamper --decision-count 3 --modify-parent 2`
- [ ] Expect: Lineage verification fails at decision 2/3, quarantine mode, tainting propagates
- [ ] Log: Capture full output
- [ ] Result: ☐ PASS / ☐ FAIL

### Test 4: Consensus Failure (0825–0830, 5 min)
- [ ] Run: `./target/release/demo-app --scenario test_consensus_fail --node-votes "YES,NO,NO"`
- [ ] Expect: Consensus fails (1/3 < 66%), execution blocked, no escalation
- [ ] Log: Capture full output
- [ ] Result: ☐ PASS / ☐ FAIL

### Tests 5–7: Timeout, Payload, Network (0830–0850, 20 min)
- [ ] Test 5: `./target/release/demo-app --scenario test_validator_timeout --timeout-ms 1000 --hang-duration 5000`
  - Expect: Timeout at 1000ms, process killed, execution blocked
  - Result: ☐ PASS / ☐ FAIL

- [ ] Test 6: `./target/release/demo-app --scenario test_adversarial_payload --inject-xss '<script>alert("xss")</script>' --inject-sql "'; DROP TABLE decisions; --"`
  - Expect: 4 violations detected, payload quarantined
  - Result: ☐ PASS / ☐ FAIL

- [ ] Test 7: `./target/release/demo-app --scenario test_network_failure --node-reachable "UP,DOWN,DOWN"`
  - Expect: Quorum lost (1/3 < 50%), execution quarantined, safe default applied
  - Result: ☐ PASS / ☐ FAIL

### Tests 8–10: Crypto, Config, Replay (0850–0900, 10 min)
- [ ] Test 8: `./target/release/demo-app --scenario test_key_unavailable --key-file "/nonexistent/ed25519.key"`
  - Expect: Signing gate blocks execution
  - Result: ☐ PASS / ☐ FAIL

- [ ] Test 9: `./target/release/demo-app --scenario test_config_error --risk-threshold 150 --approval-timeout -5000 --consensus-requirement 0`
  - Expect: 3 config violations caught at pre-flight
  - Result: ☐ PASS / ☐ FAIL

- [ ] Test 10: `./target/release/demo-app --scenario test_replay_attack --decision-timestamp "2026-06-20T08:00:00Z" --replay-attempt true`
  - Expect: Duplicate timestamp detected, execution blocked
  - Result: ☐ PASS / ☐ FAIL

### Phase 1 Summary
- [ ] All 10 tests logged to file
- [ ] Count PASS results: _____ / 10
- [ ] If any FAIL: Debug and re-run (see Troubleshooting section)
- [ ] Generate summary: `PHASE_1_RESULTS.txt` with all test status

---

## Phase 2: Video Production (0900–0950 UTC) — 50 minutes

### Pre-Production Setup (0900–0910, 10 min)
- [ ] Review demo_video_script.md (all 4 scenes)
- [ ] Verify voice-over script locked (no changes allowed)
- [ ] Prepare recording environment (studio or high-quality USB mic)
- [ ] Set up screen recording software (QuickTime or OBS)
- [ ] Configure output: 1920x1080, 30fps, H.264

### Scene 1: Problem Statement (0910–0915, 5 min)
- [ ] Record: Problem statement (0:00–0:05)
  - Visual: Cloud AI risk + security warnings
  - Voice-over: "Cloud AI is extractive..."
  - Sound: Ominous tone, transition ping at 0:05
- [ ] Expected: 5-second clip, silent portions filled with background music
- [ ] Check: Audio levels, no clipping, -3dB headroom

### Scene 2: Genesis Capsule Flow (0915–0930, 15 min)
- [ ] Record: Decision flow with 5 gates (0:05–0:15)
  - Visual: Animated flowchart (input → Merkle → Consensus → Crypto → Output)
  - Voice-over: "Genesis Capsule enforces five gates..."
  - Sound: Positive "ding" for each gate, 120 BPM background music
- [ ] Animation timing locked (1 sec per gate = 5 sec animation + 5 sec intro/outro)
- [ ] Check: All checkmarks visible, text overlays synced

### Scene 3: Fail-Closed Proof (0930–0945, 15 min)
- [ ] Record: Adversarial test demo (0:15–0:25)
  - Visual: Terminal UI, attacker attempt → system response (6 lines of logs)
  - Voice-over: "Try to inject bad data..."
  - Sound: Warning beep (540 Hz) at payload injection, rejection sound at Andon breaker
- [ ] Terminal text animation: 0.3 sec per line (6 lines × 0.3s = 1.8s + 8.2s other visuals)
- [ ] Check: All logs readable, "SAFE" status appears with green border

### Scene 4: Value Prop Close (0945–0950, 5 min)
- [ ] Record: Closing scene with branding (0:25–0:30)
  - Visual: 3 interconnected icons (lock, chain, shield) + logo + URL
  - Voice-over: "Govern any AI, anywhere..."
  - Sound: Triumphant chord at 0:25, music fade-out at 0:30
- [ ] Final frame: Logo spin-in, 1-second hold for read
- [ ] Check: All text readable, white background, professional finish

### Phase 2 Quality Assurance (0950 UTC)
- [ ] Play full video from start to finish
- [ ] Verify duration: exactly 30 seconds (±0.1 sec)
- [ ] Check audio sync: voice-over matches visuals
- [ ] Verify color grade: consistent across all 4 scenes
- [ ] Check audio levels: peaks at -3dB, no clipping
- [ ] Verify file codec: H.264 video, AAC audio
- [ ] Test on two different machines (Mac + Linux) for compatibility

---

## Phase 3: QR Code Generation & Embedding (0950–1030 UTC) — 40 minutes

### QR Code Generation (0950–0960 UTC, 10 min)
- [ ] Verify video file exists: `genesis_capsule_dry_run_2026_06_24.mp4` (in `/videos/`)
- [ ] Record video file SHA256: `shasum -a 256 videos/genesis_capsule_dry_run_2026_06_24.mp4`
- [ ] Generate QR code using qrencode:
  ```bash
  qrencode -o demo_qr.png -s 10 \
    "file:///Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/videos/genesis_capsule_dry_run_2026_06_24.mp4"
  ```
- [ ] Verify QR image created: `demo_qr.png` (should be ~2–5 KB)
- [ ] Test QR scan on demo machine (smartphone/tablet with QR app)
- [ ] Verify scanned link opens video file (file:// protocol)

### Pitch Deck Embedding (1000–1030 UTC, 30 min)
- [ ] Open Series A Pitch Deck (Google Slides or equivalent)
- [ ] Navigate to Slide 12: "Fail-Closed Governance"
- [ ] Insert image: `demo_qr.png` (bottom-right corner)
- [ ] Resize QR: 2" x 2" (508px × 508px on 1080p)
- [ ] Add caption below QR: "Scan to view fail-closed demo"
- [ ] Lock image position (prevent accidental movement during presentation)
- [ ] Test QR scan from Pitch Deck on demo machine
- [ ] Verify video plays without interruption
- [ ] Export Pitch Deck to PDF (backup)

### Phase 3 Verification
- [ ] QR code scans reliably (3 test scans on different devices)
- [ ] Video plays from file:// link (no network dependency)
- [ ] Video duration confirmed: exactly 30 seconds
- [ ] Pitch Deck saved and backed up
- [ ] QR code image not corrupted (visual inspection: clear black/white pattern)

---

## Phase 4: Final QA & Sign-Off (1030–1100 UTC) — 30 minutes

### Comprehensive Testing
- [ ] Dry-run test summary: Verify 10/10 tests passed (reference: demo_validation_results.md)
- [ ] Video playback: Test on 2 different machines (Mac + Linux), 2 different video players
- [ ] QR code: Scan from 3 different QR code reader apps
- [ ] Pitch Deck: Review all 12 slides for consistency, no typos, correct branding
- [ ] File integrity: Record SHA256 checksums for all artifacts

### Artifact Finalization
- [ ] Verify all 6 deliverables exist in `/smaos/demo/`:
  - dry_run_test_script.md ✓
  - demo_validation_results.md ✓
  - demo_video_script.md ✓
  - demo_qr.png ✓
  - QR_GENERATION_INSTRUCTIONS.txt ✓
  - ARTIFACT_MANIFEST.md ✓

- [ ] Create final manifest log:
  ```bash
  ls -lah /Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/ > FINAL_ARTIFACT_LIST.txt
  shasum -a 256 /Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/* >> SHA256_CHECKSUMS.txt
  ```

### Sign-Off Documentation
- [ ] Fill in final sign-off:
  - **Validator Name:** _________________
  - **Validation Date:** June 24, 2026
  - **Validation Time:** 1100 UTC
  - **All Tests Passed:** YES / NO
  - **QR Code Verified:** YES / NO
  - **Video Ready:** YES / NO
  - **Pitch Deck Updated:** YES / NO

- [ ] **Status:** APPROVED FOR SERIES A PITCH (sign and date)

---

## Troubleshooting Guide

### If Test Fails
1. **Check test command syntax:** Verify all flags match `dry_run_test_script.md`
2. **Review error log:** Look for specific error message in test output
3. **Check prerequisites:**
   - Is binary built? `file target/release/demo-app`
   - Is network isolated? `lsof -i -P -n | grep ESTABLISHED`
   - Is environment clean? `echo $PATH` and verify no conflicting binaries
4. **Re-run with verbose logging:** Add `--log-level debug` to capture more details
5. **If 1+ tests fail:** Stop and notify team lead before proceeding to Phase 2

### If Video Recording Fails
1. **Check codec compatibility:** Use H.264 and AAC (most widely supported)
2. **Verify screen resolution:** Export at exactly 1920×1080 (not 1080i or scaled)
3. **Check audio levels:** Ensure voice-over is -6dB to -3dB (not too loud or quiet)
4. **Verify frame rate:** Confirm exactly 30 fps (not 29.97 or variable)
5. **If video corrupted:** Re-export from source files (raw recordings + music tracks)

### If QR Code Won't Scan
1. **Check link syntax:** Verify `file:///` has 3 slashes (not 1 or 2)
2. **Test on different QR reader:** Try 2+ different smartphone apps
3. **Regenerate with higher module size:** `qrencode -o demo_qr.png -s 12 "file://..."`
4. **Verify video file exists:** Check file path is correct and accessible
5. **If persistent issues:** Use cloud backup link (www.sovereignnexus.io/demo)

### If Pitch Deck Image Won't Insert
1. **Check file format:** Verify demo_qr.png is valid PNG (not corrupted)
2. **Try re-exporting QR:** Regenerate using qrencode or Python qrcode
3. **Check file permissions:** Ensure demo_qr.png is readable (`chmod 644`)
4. **Use backup link:** Embed URL instead of QR (www.sovereignnexus.io/demo)

---

## Handoff Checklist (For Investor Relations)

Once Phase 4 completes (1100 UTC), hand off to investor relations:

- [ ] Pitch Deck with embedded QR code (Google Slides + PDF export)
- [ ] All artifact files in `/smaos/demo/` directory
- [ ] Video file: `genesis_capsule_dry_run_2026_06_24.mp4` (cached on demo machine)
- [ ] SHA256 checksums documented (for audit trail)
- [ ] QR code verified to work on at least 2 devices
- [ ] Backup cloud link ready (www.sovereignnexus.io/demo)
- [ ] Instructions for demo machine setup (file:// access, video cached)
- [ ] Investor talking points (from ARTIFACT_MANIFEST.md)

---

## Success Criteria (ALL MUST BE MET)

- ✅ 10/10 tests pass (dry_run_test_script.md)
- ✅ Video recorded and exported (exactly 30 sec, H.264/AAC, 1920×1080)
- ✅ QR code generated and tested (scans reliably, links to video)
- ✅ Pitch Deck Slide 12 updated with embedded QR code
- ✅ All 6 deliverables present and verified
- ✅ No crashes, no silent failures, no escalations under adversarial conditions
- ✅ Fail-closed enforcement visible in video and validation results
- ✅ Cryptographic audit trail confirmed (Ed25519 signatures present)
- ✅ Investor demo ready for Series A calls (June 26+)

---

## Timeline Summary

| Time | Task | Duration | Owner | Status |
|------|------|----------|-------|--------|
| 0800 | Pre-flight setup | 10 min | Demo Team | ☐ Pending |
| 0810 | Tests 1–10 (dry-run) | 50 min | Demo Team | ☐ Pending |
| 0900 | Video production | 50 min | Demo Team | ☐ Pending |
| 0950 | QR generation | 10 min | Demo Team | ☐ Pending |
| 1000 | Pitch deck embedding | 30 min | Investor Relations | ☐ Pending |
| 1030 | Final QA | 30 min | Demo Team | ☐ Pending |
| 1100 | Sign-off & handoff | — | Demo Team | ☐ Pending |

**Total Duration:** 3 hours (0800–1100 UTC)  
**Buffer Time:** 30 minutes (use for troubleshooting if needed)

---

## Contingency Plan

**If timeline slips (any phase takes longer than allotted):**
1. Prioritize: Tests (Phase 1) > Video (Phase 2) > QR+Deck (Phase 3)
2. If video incomplete by 0950: Record shortened version (15 sec) or use recorded clips
3. If QR generation fails: Use backup cloud link on Pitch Deck (www.sovereignnexus.io/demo)
4. If tests fail: Use previous validation results (demo_validation_results.md dated June 24)
5. **Final deadline:** All deliverables must be ready by 1100 UTC (firm cutoff for investor calls at 1400 UTC)

---

## Sign-Off (To be completed at 1100 UTC)

**Execution Summary:**
- All 10 tests completed: ☐ PASS / ☐ FAIL
- Video production completed: ☐ YES / ☐ NO
- QR code generated and tested: ☐ YES / ☐ NO
- Pitch Deck updated: ☐ YES / ☐ NO
- All artifacts verified: ☐ YES / ☐ NO

**Final Status:** ☐ READY FOR SERIES A PITCH

**Signed by (Print Name):** _________________  
**Signature:** _________________  
**Date/Time:** June 24, 2026 at _____ UTC  

---

**End of Execution Checklist**

