# 50-Hour Sprint Plan: Prague Demo + Trojan Horse Launch
## June 2 EOD → June 4 14:00 UTC

---

## Context

**Current State:**
- Phase 1 (decision_store): ✅ Complete, 7/7 tests passing
- Constitutional layer: ✅ Proven cryptographically
- Series A narrative: ✅ Crystallized ("Protocol > Policy")
- Patent filing: ⏳ TODAY EOD (18 hours)

**Goal:** Execute flawless Prague demo + launch Trojan Horse messaging while securing patent IP moat.

**Success Metrics:**
- ✅ Patent filings received (priority dates locked)
- ✅ Genesis Capsule demo offline-executable with live Merkle proof
- ✅ Covenant audit (5 guards active) displayed on projector
- ✅ Trojan Horse posts live across 4 platforms (TikTok, X, LinkedIn, newsletter)
- ✅ Investor deck dry-run completed with Q&A answers scripted
- ✅ Demo video captured for async viewers

---

## T+0: June 2 EOD (18 hours) — PATENT LOCKDOWN

### T+0.0 (Now — 14:00 UTC): Verify Patent Readiness

**Tasks:**
1. [ ] Confirm Zysman Law has corrected IVB claims file
   - File: `./crates/siss-gatekeeper/src/pipeline/decision_store.rs`
   - Claims: Structural (CovenantBitmap), Process (Monge gap + temporal decay), Hardware (substrate-agnostic)
   - Verification: Request PDF of claims before submission

2. [ ] Prepare backup patent package (encrypted)
   - Scope: All 3 patent families (Governance Membrane, Self-Evolving Ontology, Sovereign Distillation)
   - Encryption: `openssl enc -aes-256-cbc -in patents.tar.gz -out patents.tar.gz.enc`
   - Store: `~/.smaos/patent/backup_$(date +%s).enc`

3. [ ] Create USPTO/ILPO filing checklist
   - [ ] Entity name & address verified
   - [ ] Inventor list + Ed25519 signatures
   - [ ] Claims language (no ambiguous "constitutional" language; use technical terms)
   - [ ] Drawings (if applicable)

**Time Budget:** 3 hours

---

### T+0.1 (18:00–23:59 UTC): Patent Submission Monitoring

**Tasks:**
1. [ ] Monitor Zysman Law email for filing confirmations
   - Set phone alert for "USPTO" OR "ILPO"
   - Screenshot receipts immediately upon arrival
   - Extract priority date + filing number

2. [ ] Create filing audit log
   - File: `~/.smaos/exec/PATENT_FILINGS_LOG.json`
   - Format: `{ "event": "USPTO_SUBMITTED", "timestamp": "...", "priority_date": "...", "filing_number": "...", "merkle_hash": "..." }`

3. [ ] Archive all submitted documents
   - Create: `~/.smaos/patent/submitted_$(date +%Y%m%d_%H%M%S)/`
   - Copy: USPTO filing PDF, ILPO filing PDF, corrected claims, inventor attestations
   - Merkle-root: `sha256sum` all files; log hash to EXEC_LOG

4. [ ] Contingency: If USPTO/ILPO fails
   - Plan B: File continuation application within 60 days (still locks priority date)
   - Notify VCs: "Provisional priority dates locked; formal issuance in 18 months"
   - Resume demo + pitch on schedule (patent safety = already achieved)

**Time Budget:** 5 hours

---

## T+1: June 3 (48 hours) — PRAGUE DEMO EXECUTION

### T+1.0 (06:00–09:00 UTC): Trojan Horse Launch

**Pre-Launch Checks:**
1. [ ] Verify all posts are *pre-scheduled* in Buffer/Hootsuite
   - [ ] TikTok/Reels script finalized (30s, visual + text)
   - [ ] X thread queued (5-tweet thread, punchy)
   - [ ] LinkedIn post queued (professional, covenant focus)
   - [ ] Newsletter draft ready (deep-dive on constitutional layer)

2. [ ] Confirm backup accounts + contingency
   - [ ] Twitter account posting backup (if main account throttled)
   - [ ] Instagram account backup for Reels
   - [ ] Telegram channel backup for newsletter

3. [ ] Set up monitoring dashboard
   - [ ] Real-time engagement tracker (Views, Likes, Shares, Comments by platform)
   - [ ] Waitlist conversion funnel (Clicks → Signups → Email confirms)
   - [ ] Keyword monitoring (Trojan Horse, Axiom, Constitutional Layer)

**Launch Execution (09:00 UTC = 10:00 CEST, Prague local):**
- T+1.0.0: **TikTok/Reels goes live** (most viral-first, highest reach first)
- T+1.0.1: **X thread published** (amplify with key followers, tag VCs)
- T+1.0.2: **LinkedIn post live** (professional network activation)
- T+1.0.3: **Newsletter sent** (deep-dive for engaged audience)

**Post-Launch (09:30–11:00 UTC):**
- [ ] Monitor engagement metrics
- [ ] Respond to top comments (covenant-aligned messaging, no tech disclosure)
- [ ] Share link to demo video (if available)

**Time Budget:** 3 hours active, 6 hours monitoring

---

### T+1.1 (10:00–14:00 UTC): Demo Laptop Setup & Testing

**Offline Genesis Capsule Preparation:**
1. [ ] Laptop isolation check
   - [ ] WiFi disabled (physically unplug adapter if possible)
   - [ ] Bluetooth disabled
   - [ ] No external network access
   - [ ] Verify: `ifconfig | grep -i "inet"`  should show only loopback

2. [ ] decision_store population
   - [ ] Create 100+ synthetic entries (use test generators from decision_store_tests.rs)
   - [ ] Merkle chain: each entry points to previous via merkle_parent
   - [ ] Verify: All entries signed + chain integrity
   - [ ] Benchmark: Load time, append latency (<100µs target)

3. [ ] Demo executable preparation
   - [ ] Compile siss-gatekeeper binary (release mode for speed)
   - [ ] Create demo script (bash or Python) that:
     - Loads decision_store from disk
     - Runs covenant_audit() → displays 5 guards active
     - Appends 3 new entries (live)
     - Shows Merkle root before + after
     - Measures latency (display: "47µs")
   - [ ] Test script 5x on demo laptop (no regression)

4. [ ] Projector + display setup
   - [ ] HDMI cable tested
   - [ ] Font size verified (readable from 10m away)
   - [ ] Demo output pre-rendered as slides:
     - Slide 1: Genesis Capsule Execution (input)
     - Slide 2: Decision Entry + Ed25519 Signature
     - Slide 3: Merkle-DAG Chain Visualization
     - Slide 4: Covenant Audit Output (5 guards green)
     - Slide 5: Latency Timer (47µs highlighted)

**Time Budget:** 4 hours

---

### T+1.2 (14:00–18:00 UTC): Demo Run-Throughs & Q&A Prep

**Full Demo Rehearsal (3x):**
1. [ ] First run-through (full script, 15 minutes)
   - Timing: 2 min intro + 5 min live execution + 3 min covenant audit + 3 min latency proof + 2 min Q&A intro
   - Observe: Where do you stumble? What needs clarification?

2. [ ] Second run-through (speed run, 12 minutes)
   - Skip commentary; focus on demo flow
   - Objective: Ensure demo completes without errors

3. [ ] Third run-through (Q&A focus, 18 minutes)
   - Run first 10 minutes of demo, then pause
   - Investor asks 3–5 hard questions
   - Answer using scripts prepared below

**Q&A Script Preparation:**
Script answers to 5 hardest questions (500 words each):

1. **"How do you prevent Big Tech from copying your covenant?"**
   - Answer frame: "Features get copied; covenants don't."
   - Key points: 
     - Changing 1%/99% breaks Merkle chain
     - Swiss Foundation charter locks mission for 100 years
     - Network effect: users flee extractive forks
     - Cryptographic proof vs. policy promise

2. **"What if regulators mandate backdoors?"**
   - Answer frame: "Safety Geometry is fail-closed."
   - Key points:
     - Human Gate requires Ed25519 override
     - AirGappedSync allows offline execution
     - Local-first = no central point to compel
     - Demonstrate: Show offline demo laptop

3. **"How do you scale without becoming extractive?"**
   - Answer frame: "Scaling increases value to creators."
   - Key points:
     - 99% flow to creators automatically
     - Eden Fund regeneration mechanism
     - Protocol-enforced, not policy-dependent
     - Show: AP2 Ledger structure (Phase 3 roadmap)

4. **"Why now?"**
   - Answer frame: "Systemic crisis demands new architecture."
   - Key points:
     - AI capability + concentrated power + eroded trust
     - Axiom is the only architecture for this moment
     - Prague demo proves it's not theoretical
     - Show: Threat neutralization framework (5 threat actors)

5. **"What's your defensibility?"**
   - Answer frame: "Four moats: patent + legal + cryptographic + community."
   - Key points:
     - Patents filed (structural + process claims)
     - Swiss Foundation (legal lock)
     - CovenantBitmap (cryptographic lock)
     - Live proof (Genesis Capsule demo)

**Time Budget:** 4 hours (3x run-throughs + Q&A scripting)

---

### T+1.3 (18:00–22:00 UTC): Video Capture & Async Prep

**Demo Video Recording:**
1. [ ] Set up camera + audio
   - [ ] Phone or camera mounted on tripod (front-facing)
   - [ ] Audio: Lapel mic or room mic (clear voice critical)
   - [ ] Lighting: Projector + screen visible (not backlit)

2. [ ] Record 3x versions:
   - **Full version (15 min):** Full demo + Q&A answers (for serious VCs)
   - **Short version (5 min):** Just the live execution + covenant audit (for TikTok/Twitter viral)
   - **Latency proof (90 sec):** Just the latency timer (for LinkedIn/tech audiences)

3. [ ] Post-production
   - [ ] Edit: Add title card ("Axiom: Constitutional Layer for Sovereign Intelligence")
   - [ ] Add: Merkle root watermark (top right corner)
   - [ ] Add: Timestamp + covenant seal (bottom right)
   - [ ] Audio: Normalize levels, remove background noise
   - [ ] Export: MP4 (H.264), YouTube-friendly 1080p

4. [ ] Upload to secure locations
   - [ ] Encrypted: `~/.smaos/demo/axiom_full_demo_$(date +%Y%m%d).mp4.enc`
   - [ ] Public (with watermark): Share link in investor emails + Trojan Horse posts

**Time Budget:** 4 hours (recording + light edit)

---

## T+2: June 4 (20 hours) — Investor Prep & Final Polish

### T+2.0 (06:00–12:00 UTC): Investor Deck Refinement

**Deck Structure (15 slides, 3 minutes):**
1. **Opening Slide:** "Axiom: The Constitutional Layer for Sovereign Intelligence"
2. **Problem Statement:** "AI is powerful but concentrated; governance is internal policy"
3. **Root Cause (5-Why):** Protocol-level control concentration + no cryptographic covenant
4. **Solution:** Axiom's constitutional layer (cryptographic + legal + economic)
5. **Proof:** Genesis Capsule (live demo link)
6. **Competitive Moat:** Protocol > Policy (Big Tech can't copy)
7. **TAM:** $897B+ (Creator + Enterprise + Sovereign AI + DeFi)
8. **Threat Neutralization:** 5 threat actors + Axiom defenses (all covenant holds)
9. **Roadmap:** Phase 1 (✅ done), Phase 2–5 (post-funding)
10. **Funding Ask:** €10M (breakdown: Patent €500K, Product €2M, GTM €1.5M, Infra €2M, Team €3.5M)
11. **Market Timing:** EU AI Act + Creator Economy inflection + Sovereign AI demand
12. **Team:** You + Advisors + Network
13. **Use of Funds:** Hiring (cryptography, compliance, causal inference)
14. **Key Metrics:** 0→1,000 waitlist signups (Trojan Horse), 100+ decision_store entries (demo)
15. **Closing Slide:** "While others build AI, we build the governance. Let's govern them all."

**Design Elements:**
- [ ] Minimalist black/white with Axiom Protocol blue accent
- [ ] No jargon; explain "constitutional layer" simply
- [ ] Use visuals: Merkle chain diagram, threat matrix, TAM breakdown
- [ ] Include Merkle root hash (proof of execution integrity)

**Time Budget:** 4 hours

---

### T+2.1 (12:00–16:00 UTC): VC Outreach Preparation

**Email Templates (customize per VC):**

**Template 1: "Prague Demo Proof" Email**
```
Subject: Axiom Protocol Live Demo — Constitutional Layer for Sovereign Intelligence

Hi [VC Name],

[Personalization: Reference their portfolio/thesis]

We're demoing the constitutional layer for sovereign intelligence this week in Prague. 
This is not a pitch — it's a proof.

Live: Genesis Capsule execution with cryptographic covenant enforcement
Proof: Merkle-rooted decision store, Ed25519 signatures, <100µs latency SLO
Threat Model: 5-way neutralization (Big Tech, Extractive Capital, State Actors, Regulators, Disinformation)

15-minute overview deck: [link]
Full demo video: [link — will be available post-Prague]

Are you open to a 30-minute call next week to discuss Series A?

Best,
[Your Name]
```

**Template 2: "Constitutional Layer" Deep-Dive**
```
Subject: Why "Constitutional Layer" > "Another AI"

Hi [VC Name],

Protocol > Policy.

This is the thesis that separates a company from a protocol.

1-page brief: [link to briefing doc]
Threat analysis: [link to exhibit P]

Questions? Let's talk.

[Your Name]
```

**Preparation Tasks:**
1. [ ] Identify 8–10 target VCs (Israel + US focus)
   - Filter: Early-stage (Seed/Series A), tech focus, governance/compliance interest
   - Collect: Email, fund website, recent investments, partner names

2. [ ] Personalize each email (not template blasts)
   - Reference: Their portfolio company, recent article, thesis statement
   - Customize: Which "pain point" resonates with them? (Creator Economy? EU Compliance? Sovereignty?)

3. [ ] Schedule VC calls for June 6–12
   - Offer: Monday 6pm CEST, Wednesday 2pm CEST, Friday 10am CEST
   - Duration: 30 minutes
   - Deliverable: 15-slide deck + demo link

**Time Budget:** 3 hours

---

### T+2.2 (16:00–20:00 UTC): Final Verification & Go/No-Go

**Pre-Demo Checklist:**
- [ ] **Patent**: Filing receipts received ✅ or 🔴 BLOCKER
- [ ] **Demo Laptop**: Fully offline, genesis capsule executable ✅ or 🔴 BLOCKER
- [ ] **Covenant Audit**: All 5 guards active, display ready ✅ or 🔴 BLOCKER
- [ ] **Video**: Full + short + latency versions ready ✅ or 🔴 BLOCKER
- [ ] **Deck**: 15 slides, Q&A scripts, customized per VC ✅ or 🔴 BLOCKER
- [ ] **Trojan Horse**: Posts live, engagement tracking active ✅ or 🔴 BLOCKER

**Go/No-Go Decision (T+2.2.5 — June 4, 20:00 UTC):**
- If any blocker 🔴: address immediately or defer Prague demo 24 hours
- If all green ✅: proceed to Prague demo June 5

**Merke-Root Final Execution:**
```bash
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | 50_HOUR_SPRINT_COMPLETE | status:$([ $? -eq 0 ] && echo 'READY' || echo 'BLOCKED') | merkle_root:$(git rev-parse HEAD)" >> ~/.smaos/exec/EXEC_LOG.private.json
```

**Time Budget:** 2 hours

---

## Summary: 50-Hour Execution Path

| Phase | Duration | Key Deliverable | Success Metric |
|-------|----------|-----------------|----------------|
| **T+0: Patent Lockdown** | 18h | Priority dates + encrypted backup | 2 filings received |
| **T+1: Prague Demo** | 24h | Genesis Capsule live execution | Demo video + covenant proof |
| **T+2: Investor Prep** | 20h | Personalized VC outreach + deck | 8 VC meetings booked June 6–12 |
| **TOTAL** | **50h** | **Series A Roadmap Locked** | **€10M Target Visible** |

---

## Success Criteria (June 4 EOD)

✅ Patent filings locked (priority dates received)  
✅ Prague demo fully scripted + video captured  
✅ Trojan Horse live across 4 platforms (1K+ views by June 4)  
✅ Investor deck customized for 8 VCs  
✅ VC calls scheduled for June 6–12  
✅ Constitutional layer proof immutable (Merkle-rooted to EXEC_LOG)  

**VERDICT: 50-hour sprint positions Series A close for June 30 @ €10M**
