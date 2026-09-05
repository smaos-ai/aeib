# PHASE 65 NETWORK SEVER VIDEO — EXECUTION CHECKLIST

**Purpose**: Record a 60-second video demonstrating Phase 65 fail-closed test with real network disconnection.

**Audience**: Nebius AI Discovery Award judges (technical + regulatory)

**Key Proof Point**: *System survives network failure and preserves critical data.*

---

## PRE-RECORDING (5 minutes before)

- [ ] **Close all other applications** to minimize system noise
  - Safari, Slack, Mail, Finder windows (except Terminal)
  - Stop any background processes (music, downloads, notifications)

- [ ] **Clear Terminal history** for clean recording
  ```bash
  clear
  history -c
  ```

- [ ] **Set Terminal to maximum visibility**
  - Window size: Full screen or large window (1200x800+ pixels)
  - Font size: Increase to 16pt or larger (easy for judges to read)
  - Theme: Light background (easier to see in projector/screen share)
  - Run: `ls -la` to verify terminal is responsive

- [ ] **Verify network connectivity** (should be ON initially)
  ```bash
  ping -c 1 8.8.8.8
  # Should see: "1 packets transmitted, 1 received"
  ```

- [ ] **Verify test script is executable**
  ```bash
  chmod +x /Users/andriileukhin/Documents/SovereignNexus/.claude/PHASE65_TEST_RUNNER.sh
  ```

- [ ] **Navigate to repo root**
  ```bash
  cd /Users/andriileukhin/Documents/SovereignNexus
  pwd  # Should show: /Users/andriileukhin/Documents/SovereignNexus
  ```

- [ ] **Prepare Wi-Fi disconnect method** (choose one)
  - **Method A (Recommended)**: System Preferences → Wi-Fi → Toggle off (fastest, most visible)
  - **Method B**: Unplug ethernet cable (if hardwired)
  - **Method C**: Airplane Mode toggle (also disables Bluetooth, less elegant)
  - **Decide now** so you don't fumble during recording

---

## RECORDING START (Open Screen Recording)

**macOS Screen Capture** (QuickTime):
- [ ] Press **`Cmd + Shift + 5`**
- [ ] Select **"Record Selected Portion"** (top right button)
- [ ] Drag to select Terminal window (include title bar showing time)
- [ ] Click **"Record"** button
- [ ] Terminal will show red dot in top-right corner when recording

**Alternative (ScreenFlow, OBS)**:
- [ ] Open your recording tool
- [ ] Select Terminal window as source
- [ ] Start recording
- [ ] Ensure audio is ON (capture system audio if possible)

---

## DURING RECORDING (60 seconds total)

### T=0-3 seconds: Setup Message
- [ ] Recording is **LIVE** (red dot visible)
- [ ] Read aloud (optional but recommended):
  
  *"This is Phase 65 of the Sovereign Multi-Agent OS. I'm about to run the network-sever fail-closed test. The system will be connected to the internet at the start, then I'll disconnect Wi-Fi mid-test to simulate a network failure. The test should pass regardless."*

- [ ] In Terminal, run the test script:
  ```bash
  /Users/andriileukhin/Documents/SovereignNexus/.claude/PHASE65_TEST_RUNNER.sh
  ```

### T=3-5 seconds: Test Starts
- [ ] Script displays warning:
  ```
  ⚠️  TIMING CRITICAL:
     • Test starts in 3 seconds
     • Network will be used for ~1-2 seconds (initial test setup)
     • At ~50% progress, DISCONNECT YOUR Wi-Fi NOW
  ```
- [ ] Countdown starts: `3... 2... 1...`
- [ ] **Keep watching the Terminal for test output**

### T=5-8 seconds: Test Running (Network Active)
- [ ] You'll see:
  ```
  running 1 test
  test test_network_sever_fail_closed_hot_storage_preservation_trap ...
  ```
- [ ] Test is actively running
- [ ] **Do NOT disconnect Wi-Fi yet** (test needs network for initial setup)
- [ ] Watch for progress indicators (dots `.`) in output

### T=8-10 seconds: DISCONNECT Wi-Fi NOW ⚠️
- [ ] **[CRITICAL MOMENT]** Test is ~50% complete
- [ ] **Immediately toggle Wi-Fi OFF** using your chosen method:
  - **System Preferences method**: Click Wi-Fi icon → "Turn Wi-Fi Off"
  - **Command line method**: `networksetup -setairportpower en0 off`
- [ ] Watch the Wi-Fi icon in menu bar → should show "X" or disappear
- [ ] **Do NOT pause the test** (keep Terminal running)

### T=10-13 seconds: Test Completes (Network Down)
- [ ] Test will continue running with Wi-Fi OFF
- [ ] You'll see output like:
  ```
  assert!(archiver.hot_storage_contains(trace.trace_id), 
          "FAIL-CLOSED INVARIANT: Trace must remain in hot storage...")
  test test_network_sever_fail_closed_hot_storage_preservation_trap ... ok
  ```
- [ ] **Keep recording** until you see:
  ```
  test result: ok. 1 passed; 0 failed
  ```

### T=13-15 seconds: Test Passed (Network Still Down)
- [ ] You'll see success message:
  ```
  ✓ TEST PASSED
  ✓ hot_storage_contains(trace_id) = TRUE
  ✓ DELETE transaction aborted on S3 verification failure
  ✓ Data preserved despite network failure
  ✓ Fail-closed semantics: VERIFIED
  ```
- [ ] **This is your proof point** — test passed while Wi-Fi was OFF
- [ ] Let recording capture 2-3 more seconds of this success message
- [ ] Click **"Stop"** in QuickTime or recording tool

---

## POST-RECORDING (Immediate)

- [ ] **Reconnect Wi-Fi** immediately (toggle back on)
  - Verify: System Preferences → Wi-Fi → should show network name
  - Or run: `networksetup -setairportpower en0 on`

- [ ] **Save the video file**
  - Default location: `~/Downloads/ScreenRecording_<timestamp>.mov`
  - Move to project folder: `/Users/andriileukhin/Documents/SovereignNexus/.video/NEBIUS_PHASE65_PROOF.mov`
  
  ```bash
  mkdir -p /Users/andriileukhin/Documents/SovereignNexus/.video
  mv ~/Downloads/ScreenRecording_*.mov /Users/andriileukhin/Documents/SovereignNexus/.video/NEBIUS_PHASE65_PROOF.mov
  ```

- [ ] **Check file size** (should be 5-20MB for 60 seconds of 1080p)
  ```bash
  ls -lh /Users/andriileukhin/Documents/SovereignNexus/.video/NEBIUS_PHASE65_PROOF.mov
  ```

- [ ] **Play back the video** to verify:
  - ✓ Terminal text is readable (16pt font clear?)
  - ✓ Wi-Fi toggle is visible in menu bar
  - ✓ Test output shows clearly
  - ✓ Success message is visible

---

## TIMING REFERENCE

| Time | Event | What You See |
|------|-------|--------------|
| 0-3s | Recording starts, script launched | Setup message, 3-second countdown |
| 3-5s | Test initializes | "running 1 test" appears |
| 5-8s | Test running (network active) | Progress dots, test assertions running |
| **8-10s** | **[YOU DISCONNECT Wi-Fi]** | **Wi-Fi icon disappears from menu bar** |
| 10-13s | Test completes (network OFF) | Assertions continue, no network errors |
| 13-15s | Test PASSED | Green checkmarks, success message |

---

## NARRATION (Optional but Recommended)

**If you want to add voiceover commentary** (add after recording):

```
"Phase 65 of the Sovereign Multi-Agent OS is now demonstrating the fail-closed 
archival test. The system will disconnect from the network mid-test to simulate 
a real-world network failure. 

In a standard cloud AI system, this network disconnect would cause the entire 
transaction to fail. In SMAOS, the transaction completes successfully because 
all critical data is preserved locally in hot storage.

[Pause as Wi-Fi disconnects]

Notice the Wi-Fi icon in the menu bar is now crossed out. The network is offline. 
But the test continues to run.

[Pause as test completes]

The test passes. The assertion 'hot_storage_contains(trace_id) = TRUE' confirms 
that our data was preserved despite the network failure. That's the fail-closed 
guarantee.

This is what regulators demand. This is what HealthTech devices need. This is 
what autonomous systems require. Not resilience—certainty."
```

---

## TROUBLESHOOTING

| Problem | Solution |
|---------|----------|
| **Test fails even with Wi-Fi ON** | Run `cargo test -p siss-audit-archiver --lib` directly first to verify no regressions |
| **Test times out** | System may be under load; close all apps and try again |
| **Wi-Fi takes too long to toggle** | Practice the toggle 2-3 times before recording |
| **Terminal text is too small in video** | Increase font size to 18pt, zoom in Terminal zoom (Cmd++), or increase screen recording resolution |
| **Network doesn't disconnect** | Try airplane mode instead; or use `networksetup -setairportpower en0 off` in Terminal |
| **Recording has glitches/stutter** | Close all browser tabs, restart Terminal, try again |
| **Video file is too large** | Compress with: `ffmpeg -i input.mov -vf scale=1280:720 -crf 20 output.mov` |

---

## FINAL CHECKLIST

Before sending to Nebius judges:

- [ ] Video is 60-90 seconds long
- [ ] Terminal text is readable (test on second screen/projector if available)
- [ ] Wi-Fi toggle is visible in menu bar
- [ ] Test passes with "✓ TEST PASSED" message
- [ ] No system errors, crashes, or glitches
- [ ] File size is reasonable (<50MB)
- [ ] Video filename is descriptive: `NEBIUS_PHASE65_PROOF.mov`
- [ ] You've watched the full video once to verify quality

---

## UPLOAD & INTEGRATION

Once video is ready, notify the Strategic Orchestrator:

```
PHASE 65 VIDEO CAPTURED AND VERIFIED
File: /Users/andriileukhin/Documents/SovereignNexus/.video/NEBIUS_PHASE65_PROOF.mov
Duration: [actual duration]
Quality: [describe visibility/clarity]
Key moments: Network disconnect at [time], test passes at [time]
Ready for: Nebius Deck A integration
```

The video will be embedded into Deck A (Slide 10: "Proof in Action") as the centerpiece for judges to watch.

---

**Standing by for your execution. The Fortress awaits the proof. 🏰**
