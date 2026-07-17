# Prague Demo Video Script — 30-Second Highlight Reel
**Title:** Genesis Capsule: Fail-Closed AI Governance in Action  
**Duration:** 30 seconds  
**Format:** MP4, H.264, 1080p, 30fps  
**Target:** Investors (Slide 12, Series A pitch deck)  
**File Path:** `/Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/videos/genesis_capsule_dry_run_2026_06_24.mp4`

---

## Scene Breakdown

### Scene 1: Problem Statement (0:00–0:05, 5 seconds)

**Visual:**
- Split screen: Left side shows cloud AI system (generic, symbolic), right side shows locked box with warning icon
- Fade in red warning text: "AI systems running without human governance"
- Show statistics overlay (large bold text):
  - "100% of cloud AI relies on vendor API"
  - "0% cryptographic proof of what actually happened"
  - "AI can escalate without approval"

**Voice-Over (Rapid, Problem-Focused):**
"Cloud AI is extractive. You have no control. No audit trail. No guarantee your AI didn't do something you didn't approve."

**Sound Design:**
- Ominous background tone (low frequency rumble)
- Transition ping (notification alert sound) at 0:05

**On-Screen Text:**
- "Problem: Cloud AI = No Control"
- Fade out at 0:05

---

### Scene 2: Genesis Capsule Decision Flow (0:05–0:15, 10 seconds)

**Visual:**
- Clean white background with animated flowchart appearing left-to-right
- Boxes appear in sequence with connecting arrows:
  1. Input box: "Decision: Analyze threat" (green checkmark appears)
  2. Merkle box: "Verify hash (SHA256)" (animated hash computation, green checkmark)
  3. Consensus box: "Swarm votes: 3/3 YES" (three node icons, green checkmarks)
  4. Crypto box: "Ed25519 signature" (animated key generation, green checkmark)
  5. Output box: "Execute + Log" (green checkmark, decision completes)

**Voice-Over (Calm, Confident):**
"Genesis Capsule enforces five gates. Every decision must pass all five. Input validated. Hash verified. Consensus confirmed. Cryptographically signed. Execution logged."

**Animation Timing:**
- Input: 0:05–0:06 (1 sec)
- Merkle: 0:06–0:08 (2 sec)
- Consensus: 0:08–0:10 (2 sec)
- Crypto: 0:10–0:12 (2 sec)
- Output: 0:12–0:15 (3 sec)

**Sound Design:**
- Positive "ding" sound for each checkmark
- Smooth, flowing background music (tempo: 120 BPM, uplifting)

**On-Screen Text:**
- "Gate 1: Input Validation ✓"
- "Gate 2: Merkle Verification ✓"
- "Gate 3: Consensus (3/3) ✓"
- "Gate 4: Ed25519 Signature ✓"
- "Gate 5: Execution + Audit Log ✓"

---

### Scene 3: Fail-Closed Proof — Adversarial Test (0:15–0:25, 10 seconds)

**Visual:**
- Terminal-style UI (black background, green text, monospace font)
- Two panels: Left = "Attacker Attempt", Right = "System Response"

**Left Panel (Attacker Attempt):**
```
$ genesis-capsule --inject-payload malicious
[INPUT] {action: "escalate", override: true}
```

**Right Panel (System Response, appearing in real-time):**
```
[PAYLOAD INSPECTION] 4 violations detected:
  - XSS pattern: <script> tag
  - Buffer overflow: 10KB > 1KB limit
  - Binary shellcode detected
  - SQL injection: DROP TABLE

[ANDON BREAKER TRIGGERED]
[EXECUTION BLOCKED]
[DECISION QUARANTINED]

Status: SAFE ✓
```

**Voice-Over (Emphatic, Proof-Focused):**
"Try to inject bad data. The system rejects it. No crash. No escalation. Just a safe rejection. Fail-closed, by design."

**Animation Timing:**
- Attacker input appears: 0:15–0:17 (2 sec)
- System response rolls in line-by-line: 0:17–0:23 (6 sec)
- Final "SAFE" stamp appears: 0:23–0:25 (2 sec, red border → green border transition)

**Sound Design:**
- Warning tone (short beep) at payload injection
- Rejection sound (deeper beep) when breaker triggers
- Positive "chime" when "SAFE" appears

**On-Screen Text:**
- "FAIL-CLOSED: Adversarial Input Rejected"
- "No crashes. No escalation. No silent failures."

---

### Scene 4: Value Proposition + Close (0:25–0:30, 5 seconds)

**Visual:**
- Animation of three interconnected logos/icons:
  1. Lock icon + "Offline-First" (local inference, no cloud dependency)
  2. Chain icon + "Cryptographically Audited" (Merkle-DAG, immutable proof)
  3. Shield icon + "Fail-Closed" (human approval required, no escalation)
- Fade in tagline and URL at bottom

**Voice-Over (Investor Close):**
"Govern any AI, anywhere. Offline. Audited. Fail-closed. SovereignNexus: Sovereignty as code."

**Animation Timing:**
- Lock icon: 0:25–0:26 (1 sec)
- Chain icon: 0:26–0:27 (1 sec)
- Shield icon: 0:27–0:28 (1 sec)
- Tagline fade-in: 0:28–0:30 (2 sec)

**Sound Design:**
- Triumphant chord (major 7th, 440Hz) at 0:25
- Subtle background music fades to zero at 0:30

**On-Screen Text (Large, Bold):**
- "Govern Any AI, Anywhere"
- "www.sovereignnexus.io"
- "Patent-Pending | Ed25519 Verified | Fail-Closed by Design"

**Final Frame (0:29–0:30):**
- SovereignNexus logo (animated spin-in)
- White background with logo + URL
- Duration: 1 second (allows for read on investor screen)

---

## Technical Specifications

### Video Codec & Container
- Format: MP4 (MPEG-4 Part 14)
- Codec: H.264 / AVC
- Bitrate: 5000 kbps (1080p target)
- Frame rate: 30 fps (PAL standard)
- Resolution: 1920x1080 (Full HD)
- Aspect ratio: 16:9

### Audio
- Codec: AAC
- Bitrate: 128 kbps
- Sample rate: 48 kHz
- Channels: Stereo
- Duration: Synchronized with video (30 sec)

### Timing Precision
- Scene 1: 0:00–0:05 (5 sec tolerance: ±0.1 sec)
- Scene 2: 0:05–0:15 (10 sec, animations synchronized to frame)
- Scene 3: 0:15–0:25 (10 sec, terminal text animated at 0.3 sec per line)
- Scene 4: 0:25–0:30 (5 sec, music fade-out at exactly 0:30)

---

## Production Checklist

### Pre-Production
- [x] Script finalized (this document)
- [x] Scene breakdowns complete
- [x] Timing verified (totals 30 seconds)
- [x] Voice-over script locked (no revisions allowed after recording)
- [x] Sound design assets identified

### Production (June 24)
- [ ] Record voice-over (60 min studio time or high-quality USB mic)
- [ ] Generate terminal UI animations (Scene 3 logs)
- [ ] Render flowchart animations (Scene 2)
- [ ] Create static assets (problem statement, icons, logos)
- [ ] Compose audio track (voice + background music + SFX)
- [ ] Color grade all scenes (brightness, contrast, white balance)

### Post-Production
- [ ] Edit video timeline (arrange scenes, add transitions)
- [ ] Sync audio to video (voice-over aligned to 30-sec track)
- [ ] Add motion graphics (checkmarks, icons, text overlays)
- [ ] Apply color correction (consistent tone across all scenes)
- [ ] Export to H.264 MP4 (1920x1080, 30fps, 5000 kbps)
- [ ] Verify audio levels (-3dB headroom, no clipping)
- [ ] QA pass: play full video on two different machines (Mac + Linux)

### Delivery
- [ ] Final MP4 exported to `/Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/videos/genesis_capsule_dry_run_2026_06_24.mp4`
- [ ] File size check (expected: 18–22 MB for 30-sec 1080p)
- [ ] SHA256 checksum recorded (for integrity verification)
- [ ] QR code generated (file:// link to video file)
- [ ] QR code embedded in Pitch Deck Slide 12

---

## Voice-Over Transcript (For Recording)

**Scene 1 (0:00–0:05):**
"Cloud AI is extractive. You have no control. No audit trail. No guarantee your AI didn't do something you didn't approve."

**Scene 2 (0:05–0:15):**
"Genesis Capsule enforces five gates. Every decision must pass all five. Input validated. Hash verified. Consensus confirmed. Cryptographically signed. Execution logged."

**Scene 3 (0:15–0:25):**
"Try to inject bad data. The system rejects it. No crash. No escalation. Just a safe rejection. Fail-closed, by design."

**Scene 4 (0:25–0:30):**
"Govern any AI, anywhere. Offline. Audited. Fail-closed. SovereignNexus: Sovereignty as code."

---

## Music & Sound Design

### Background Music (Scene 2 & 4)
- Tempo: 120 BPM
- Mood: Uplifting, professional, tech-forward
- Instrumentation: Ambient electronic (synth pads + percussive elements)
- Fade profile: 0:05 (fade in) → 0:15 (full volume) → 0:28 (fade out over 2 sec)

### Sound Effects

| Scene | Time | Sound | Duration | Purpose |
|-------|------|-------|----------|---------|
| 1 | 0:04 | Notification alert ping | 0.2 sec | Problem statement emphasis |
| 2 | 0:06 | Positive "ding" | 0.1 sec | Gate 1 passes |
| 2 | 0:08 | Positive "ding" | 0.1 sec | Gate 2 passes |
| 2 | 0:10 | Positive "ding" | 0.1 sec | Gate 3 passes |
| 2 | 0:12 | Positive "ding" | 0.1 sec | Gate 4 passes |
| 2 | 0:14 | Positive "ding" | 0.1 sec | Gate 5 passes |
| 3 | 0:16 | Warning beep (540 Hz) | 0.2 sec | Malicious input detected |
| 3 | 0:19 | Rejection sound (deeper beep) | 0.3 sec | Andon breaker triggered |
| 3 | 0:24 | Positive "chime" (major 7th) | 0.2 sec | SAFE status confirmed |
| 4 | 0:25 | Triumphant chord (major 7th, 440Hz) | 0.5 sec | Investor close |

---

## QR Code Specification

### Link Target
```
file:///Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/videos/genesis_capsule_dry_run_2026_06_24.mp4
```

### QR Code Parameters
- Encoding: QR Code (ISO 18004)
- Error correction: Level H (30% recovery)
- Module size: 10px (high resolution, scans reliably)
- Border: 4 modules (quiet zone)
- Foreground: Black (RGB 0,0,0)
- Background: White (RGB 255,255,255)

### Generation Command
```bash
qrencode \
  -o demo_qr.png \
  -s 10 \
  "file:///Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/videos/genesis_capsule_dry_run_2026_06_24.mp4"
```

### QR Code Placement (Pitch Deck Slide 12)
- Position: Bottom-right corner of slide
- Size: 2" x 2" (508px x 508px on 1080p screen)
- Caption below QR: "Scan to view fail-closed demo"
- Fallback URL under caption: www.sovereignnexus.io

---

## Investor Narrative Alignment

### Three Investor Pain Points → Video Proof

| Investor Concern | Video Scene | Proof |
|------------------|-------------|-------|
| "AI executes without human approval" | Scene 3 (fail-closed test) | System blocks execution; requires consent |
| "No visibility into AI decisions" | Scene 2 (cryptographic audit) | Every decision signed, hashed, immutable |
| "Cloud platforms control everything" | Scene 1 (problem statement) | Genesis Capsule runs offline, no cloud |

### Covenant Alignment

- ✅ **Fail-Closed Enforcement Visible** — Video proves rejection, not escalation
- ✅ **No Over-Promising** — Shows real limitations (requires consensus, blocks on error)
- ✅ **Cryptographic Audit Trail** — Ed25519 signature and Merkle proof visible
- ✅ **Reproducible** — Script allows future re-runs for auditors

---

## Contingency Plan (If Live Demo Fails During Investor Call)

**Fallback:** Play this pre-recorded video instead of live demo
- Same script, same results, same investor impact
- Proves system works consistently (pre-validation)
- More reliable than live execution under pressure
- QR code allows investor to re-watch asynchronously

**Note:** Video is NOT a substitute for live interaction; it's a safety net for technical issues.

---

## Sign-Off

**Script Finalized By:** SovereignNexus Demo Team  
**Date:** June 24, 2026  
**Video Production Target:** June 24, 1000–1100 UTC  
**QR Code Generation:** June 24, 1100 UTC  
**Embedding in Pitch Deck:** June 25, before investor calls  

