# Week 1 Decision Tree: Capital Acquisition Execution (May 25-31, 2026)

**Status:** OPERATIONAL BLUEPRINT  
**Go/No-Go Authority:** Your decision on each gate  
**Success Metric:** All 3 critical paths advance by May 31

---

## CRITICAL PATH: Czech s.r.o. Incorporation → Grant Submissions

### DAY 1-2 (May 25-26): Czech Entity Registration [BLOCKER]

**Hard Prerequisite:** CzechInvest grant cannot be submitted without Czech s.r.o. registration

**Actions:**
- [ ] Contact Czech Chamber of Commerce (komora.cz) — request expedited s.r.o. registration
  - Required docs: Your passport, local address, business plan (use CZECHINVEST_STAGE1_GRANT.md excerpt)
  - Target: 24-48 hour turnaround
- [ ] Parallel: Create CzechInvest account (www.czechinvest.org)
  - Email: Your email
  - Company name: SovereignNexus s.r.o.
  - Project: "Enterprise 4.0 — AI Agent Orchestration"

**Go/No-Go Gate (End of Day 2):**
```
✓ PASS: Czech s.r.o. registration confirmed (receipt #___) 
        + CzechInvest account active
        → PROCEED to Day 3 grant submission

✗ FAIL: Registration delayed beyond 48 hours
        → ESCALATE to lawyer/expedited service
        → If not resolved by EOD May 26: Consider alternative entity (delay risk)
```

**Blocker Resolution:**
- Backup: If Czech Chamber slow, contact regional office directly or use lawyer service (€200-300 cost, 1-day turnaround)
- Assumption: You have valid passport + Prague address. If not, resolve immediately.

---

### DAY 3 (May 27): Nebius AI Discovery Award Submission

**Deadline:** June 15 (submit by June 10 for review buffer)

**Actions:**
- [ ] Create Nebius account (https://nebius.com)
  - Email: Your email
  - Enable 2FA
  - Verify account active
  
- [ ] Prepare submission package:
  - NEBIUS_DISCOVERY_AWARD_ANNEX.md (complete)
  - Technical spec: "Night Cycle Evolution Engine" (2-3 pages)
    - Use case: Autonomous molecular hypothesis evaluation
    - Triple substrate: Local edge (M3 Pro) + Nebius H100 burst + SovereignNexus O(1) orchestration
  - Your founder bio (LinkedIn link + 1-page summary)
  - Expected outcome: 10,000+ molecular hypotheses evaluated in 6 months

- [ ] Submit to awards@nebius.com
  - Subject: "SovereignNexus: Night Cycle Evolution Engine — AI Discovery Award Application"
  - Attach: PDF of NEBIUS_DISCOVERY_AWARD_ANNEX.md + technical spec + bio

**Go/No-Go Gate (End of Day 3):**
```
✓ PASS: Nebius submission confirmation received (email + reference #___)
        + Application tracking in CRM
        → PROCEED to hardware validation

✗ FAIL: Nebius account blocked / email unresponsive
        → ESCALATE to Nebius support (check spam folder, use contact form)
        → Deadline still June 15 — 12 days buffer remains
```

---

### DAY 4-5 (May 28-29): CzechInvest Grant Submission

**Deadline:** June 30 (submit by June 10 for review buffer)

**Actions:**
- [ ] Download CzechInvest Stage 1 application form
  - Portal: www.czechinvest.org → Technology & Innovation → Enterprise 4.0
  - Form: "PoC Stage (Stages 1-3)"

- [ ] Compile submission package:
  - CZECHINVEST_STAGE1_GRANT.md (complete — copy into form)
  - KPI_DASHBOARD.md (prove O(1) invariants with metrics)
  - PRAGUE_POC_RUNBOOK.md (hardware specs for 3x Mac Studio M3 Pro)
  - 3-year financial model (Excel: revenue, COGS, EBITDA, breakeven Q3 2028)
  - Your CV + CTO hiring plan (1 page)
  - Bank account details (for grant wire)

- [ ] Submit via CzechInvest portal
  - Confirm: "Received" email received
  - Record: Application ID, submission timestamp, amount (€200K)

**Go/No-Go Gate (End of Day 5):**
```
✓ PASS: CzechInvest application submitted + confirmation
        + Tracking in capital roadmap
        → BOTH GRANTS IN FLIGHT (€293K at risk)

✗ FAIL: Application validation error / missing docs
        → Fix immediately and resubmit same day
        → Deadline: June 10 — 6 days buffer (manageable)
```

---

## PARALLEL TRACK A: Hardware Validation (May 27-28)

### DAY 5-6 (May 27-28): Prague Desk Lab PoC Air-Gap Verification [GO/NO-GO GATE]

**Critical:** If 6/6 checks fail → **NO-GO for investor demos** (fail-closed)

**Prerequisite:** 3x Apple Silicon M3 Pro nodes available and powered on

**Actions (on each node):**

Run validation script from PRAGUE_POC_RUNBOOK.md:
```bash
./prague_pre_demo_checklist.sh
```

**6-Point Checklist (All must PASS):**

1. **Network Isolation**
   - WiFi disconnected from all nodes ✓
   - No external connections on listening ports ✓
   - Verified: `lsof -i -P -n | grep ESTABLISHED` returns empty

2. **Git Remote Disabled**
   - No git origin configured ✓
   - Verified: `git remote -v` returns empty

3. **Cloud SDK Audit**
   - No AWS/Azure/GCP/Nebius SDKs in binary ✓
   - Verified: `strings ./siss-orchestrator | grep -iE "aws|azure|gcp"`

4. **Binary Integrity**
   - SHA256 hash verified ✓
   - Verified: `shasum -a 256` matches expected hash

5. **Agent Startup**
   - 50 agents initialize successfully ✓
   - Verified: `cargo run --release -- --agents 50` completes <10s

6. **Latency Baseline**
   - Dispatch latency 47µs mean (P99 <100µs) ✓
   - Verified: `curl http://127.0.0.1:8080/api/metrics/dispatch-latency | jq '.p99_us'`

**Go/No-Go Gate (Critical):**
```
✓ ALL 6/6 PASS on all 3 nodes
  → PROCEED to demo rehearsal (May 29-30)
  → Investor demo scheduled for Week 2

✗ ANY CHECK FAILS on any node
  → HALT investor commitments immediately
  → Debug the failure (network, hardware, or binary issue)
  → Re-test before proceeding
  → If not resolved by May 29: Inform investors of 1-week demo delay
```

**Risk Cascade:**
- If network isolation fails → Investor will question sovereignty guarantee → Deal risk
- If latency fails → Proof of O(1) compromised → Technical credibility lost
- If binary tampered → Security audit needed → Timeline impact

---

## PARALLEL TRACK B: Demo Rehearsal & HITL Flow (May 29-30)

### DAY 7-8 (May 29-30): Chaos Injection & φ+ Eval Court Rehearsal

**Prerequisite:** Day 5-6 hardware validation all passed (6/6)

**Actions:**

Rehearse 5-minute live demo sequence (practice until <6 minutes consistent):

**Step 1: Setup (30s)**
- Show 50 agents healthy on dashboard
- Display dispatch latency: 47µs mean, 89µs P99

**Step 2: Conflicting Agent Injection (30s)**
- Curl: `POST /api/chaos/inject {scenario: agent_conflict, target: agent-010}`
- Watch logs: Two agents propose mutations to same symbol
- System detects: Symbol intersection → CapsuleCommitActor blocks both

**Step 3: φ+ Eval Court Veto Flow (2min)**
- Dashboard shows: "Pending Human Veto: 1 review"
- Display two pending capsules:
  - Capsule A (Agent-001): Add logging (Low impact)
  - Capsule B (Agent-002): Refactor return type (High impact, 15 callers affected)
- Operator review: "APPROVE_A_REJECT_B"
- Cryptographic signature: HMAC-SHA256 signed with operator key
- Result: Capsule A commits, Capsule B rejected + logged

**Step 4: Recovery Verification (2min)**
- Agent B receives rejection reason
- System state: 50 agents healthy, MTTR <5s, no data loss
- Final metric: Cross-chain sync cost = 0.8 (safe, <2.0 threshold)

**Go/No-Go Gate (End of Day 8):**
```
✓ Demo runs <6 minutes consistently
  + HITL veto flow executes flawlessly
  + All metrics visible and credible
  → PROCEED to investor outreach (Week 2)

✗ Demo exceeds 6 minutes or veto flow stutters
  → Debug and fix before Day 9
  → Practice 2+ more times until confident
  → If not confident by May 31: Delay first investor call 1 week (calendar risk)
```

---

## PARALLEL TRACK C: Pitch Deck Production (May 25-31)

### DAY 1-7: Async Visual Deck Creation

**Owner:** You (design) or designer/contractor

**Deliverable:** 40-50 slide visual deck based on SERIES_A_PITCH_OUTLINE.md

**Slides Required:**
1. Title (SovereignNexus logo, €3.5M ask, date)
2-3. Problem + Market (€8.2B TAM, constraints)
4. Solution (triple substrate diagram)
5-6. Proof (O(1) math + HITL veto flow screenshot)
7. GTM (18-month timeline)
8. Use of funds (€3.5M breakdown)
9. Team (Founder + CTO/VP Sales hiring plan)
10. Financials (3-year model, breakeven Q3 2028)
11. Investment thesis + risk mitigation
12. Closing statement

**Tools:** Figma, Keynote, PowerPoint, or design contractor (Upwork: €300-800 for polish)

**Go/No-Go Gate (End of Day 7):**
```
✓ Deck v1 complete (40+ slides, professional quality)
  → Ready for first investor call
  
⚠ Deck 70% complete
  → Acceptable for internal review; finalize by June 2

✗ Deck <50% complete
  → Schedule contractor help immediately (cost: €500-1K)
  → Risk: First investor call may lack visual credibility
```

---

## PARALLEL TRACK D: VC CRM & Warm Introductions (May 29-31)

### DAY 5-7: Investor Targeting & Outreach Prep

**Actions:**

- [ ] Create investor CRM spreadsheet:
  - Columns: VC Name | Fund Size | Decision Maker | Warm Intro Source | Email | Phone | Interest Level | Meeting Scheduled
  - Rows: 10 Tier-1 EU VCs + 5 corporate development targets

- [ ] Tier 1 (GDPR/Sovereignty Focus):
  - Headline (Berlin) — AI infrastructure
  - Firstminute Capital (London) — Enterprise AI
  - Notion Capital (London) — DevTools + Infrastructure
  - Earlybird VC (Berlin) — Deep tech + crypto expertise
  - German VC (research LinkedIn)

- [ ] Tier 2 (Strategic):
  - SAP Ventures — Enterprise software partnerships
  - Siemens Venture Capital — Industrial IoT
  - Philips Ventures — HealthTech

- [ ] Identify warm intro sources:
  - Personal network (founders, advisors)
  - LinkedIn connections (mutual friends)
  - CzechInvest network (ask during grant submission)
  - Nebius contacts (after award notification)

- [ ] Draft outreach email (template in EXECUTION_TIMELINE_30DAYS.md):
  - Personalize for each VC's focus (e.g., "You invested in X, this is why SovereignNexus is relevant")
  - Attach: 1-page executive summary + link to pitch deck
  - CTA: "Available for 60-minute overview + live demo on [dates]"

**Go/No-Go Gate (End of Day 7):**
```
✓ CRM populated with 10 Tier-1 VCs
  + 3+ warm intro sources identified
  + Draft email template ready
  → PROCEED to investor outreach Week 2

✗ CRM <5 entries or no warm intros identified
  → Expand search to secondary networks
  → Risk: Cold outreach has 5-10% response rate vs. 40%+ for warm intros
  → Delay first calls to June 5 (find intros)
```

---

## DECISION MATRIX: Week 1 Success Criteria

| Track | Go/No-Go Gate | Pass Criteria | Fail Response |
|-------|---------------|---------------|--------------|
| **Czech s.r.o.** | Day 2 | Registration confirmed | Escalate to lawyer (24h delay) |
| **Nebius Grant** | Day 3 | Submission confirmed | Resubmit immediately (11-day buffer) |
| **CzechInvest Grant** | Day 5 | Submission confirmed | Resubmit immediately (6-day buffer) |
| **Hardware Validation** | Day 6 | 6/6 air-gap checks PASS | Debug failure (1-2 day delay) |
| **Demo Rehearsal** | Day 8 | <6 min, flawless veto flow | Practice 2+ more times (1-2 day delay) |
| **Pitch Deck** | Day 7 | 40+ slides, ready | Contractor help (+€500-1K, 2-3 day delay) |
| **VC CRM** | Day 7 | 10 VCs + 3 warm intros | Expand network (+2-3 days research) |

---

## PARALLEL EXECUTION SUMMARY

**Week 1 Timeline (May 25-31):**

```
MAY 25 (Day 1)  │ S.r.o. registration START      │ Pitch deck production START
                │ CzechInvest account creation    │ VC research START
                │
MAY 26 (Day 2)  │ ✓ S.r.o. registration CONFIRM   │ Pitch deck 20% complete
                │ ✓ CzechInvest account READY     │ VC CRM: 5 entries
                │
MAY 27 (Day 3)  │ Nebius award submission START   │ Hardware validation START
                │ Nebius account creation         │ (6/6 air-gap checks)
                │                                 │
MAY 28 (Day 4)  │ ✓ Nebius SUBMITTED             │ Hardware validation COMPLETE
                │ CzechInvest prep BEGIN          │ (GO/NO-GO decision)
                │
MAY 29 (Day 5)  │ ✓ CzechInvest SUBMITTED         │ Demo rehearsal START
                │ VC outreach email READY         │ Pitch deck 70% complete
                │                                 │
MAY 30 (Day 6)  │                                 │ Demo rehearsal PRACTICE #2-3
                │                                 │ VC CRM POPULATED (10 VCs)
                │
MAY 31 (Day 7)  │ ✓ WEEK 1 COMPLETE              │ ✓ Demo rehearsal <6 min
                │   (All 3 grants in flight)      │ ✓ Pitch deck READY
                │                                 │ ✓ VC CRM + warm intros READY
```

---

## Week 1 Success: You Own These Deliverables by May 31

- ✅ Czech s.r.o. registered (legal entity)
- ✅ Nebius AI Discovery Award submitted (€100K cloud credits at stake)
- ✅ CzechInvest Stage 1 grant submitted (€200K at stake)
- ✅ 3x Apple Silicon M3 Pro nodes: 6/6 air-gap checks PASS
- ✅ Demo rehearsed: <6 minutes, HITL veto flow flawless
- ✅ Pitch deck ready: 40-50 slides, professional quality
- ✅ VC CRM populated: 10 VCs + 3 warm intros identified
- ✅ Investor outreach email template ready: personalized for top 3 VCs

---

**Status: READY FOR EXECUTION**  
**Start: May 25 (Today)**  
**Go/No-Go Authority: Your decision on each gate**  
**Next Review: May 31 (Week 1 complete or escalate blockers)**
