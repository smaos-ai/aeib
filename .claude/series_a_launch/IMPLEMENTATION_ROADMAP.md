# SMAOS UniCredit Pilot: IMPLEMENTATION ROADMAP
**Our 4-Week Execution Plan (Oct 1-31, 2026)**

---

## WEEK 1: INTEGRATION & DATA ONBOARDING

### Day 1-2: Environment Setup
- **Task:** Docker container deployed to UniCredit staging
- **Owner:** Infrastructure (you)
- **Output:** `docker run smaos-treasury:v1` runs on internal network
- **Checklist:**
  - [ ] Dockerfile finalized (512MB RAM limit, local inference)
  - [ ] Internal registry push (artifact ready)
  - [ ] Network security rules (internal VPN only, no egress)
  - [ ] Logging configured (ELK/Splunk ingestion)

### Day 2-3: API Wiring
- **Task:** SMAOS REST API ↔ Murex/RWA system integration
- **Owner:** Backend engineer (you)
- **Output:** Real data flowing through the gate
- **Checklist:**
  - [ ] Murex API client (RWA feed polling every 30s)
  - [ ] CAR calculation payload schema
  - [ ] Trade execution callback (block/approve feedback to Murex)
  - [ ] Error handling (timeout, network failure, invalid data)

### Day 3-4: Historical Data Load
- **Task:** 3 months of trade history loaded for shadow testing
- **Owner:** Data engineer (you)
- **Output:** 10,000+ historical trades in system
- **Checklist:**
  - [ ] Data extraction script (from Murex or data warehouse)
  - [ ] Schema mapping (date, counterparty, amount, RWA, CAR)
  - [ ] Bulk insert (SQLite or PostgreSQL)
  - [ ] Validation query (row counts, data quality checks)

### Day 4-5: Basel III Rule Engine Config
- **Task:** CAR rules configured to match UniCredit's regulatory framework
- **Owner:** Compliance engineer (you)
- **Output:** CAR calculator ±0.01% match to internal system
- **Checklist:**
  - [ ] Risk weighting table (counterparty ratings, asset classes)
  - [ ] CAR formula: (Tier 1 + Tier 2) / RWA ≥ 8%
  - [ ] CET1 buffer: ≥ 10.5% (your threshold)
  - [ ] Stress testing (apply 5%, 10%, 20% market shocks)
  - [ ] Reconciliation run (daily CAR %).

### Day 5: Live Dashboard (Read-Only)
- **Task:** CRO sees live CAR meter + trade list
- **Owner:** Frontend engineer (you)
- **Output:** http://[staging]:3000/dashboard (real-time data)
- **Checklist:**
  - [ ] CRO login (temporary credentials)
  - [ ] CAR % meter (live updating)
  - [ ] Trade list (latest 50, color-coded by risk)
  - [ ] Network isolation badge (shows airgap status)

**Week 1 Verification:** CAR calculations match Murex ±0.01%, all systems logging, no data gaps.

---

## WEEK 2-3: SHADOW MODE (READ-ONLY MONITORING)

### Day 8-10: Shadow Execution Loop
- **Task:** System observes all trades, logs decision, does NOT block
- **Owner:** Backend + DevOps (you)
- **Output:** 100% audit trail without impacting trading
- **Checklist:**
  - [ ] Gate logic wired but **disabled** (logging only)
  - [ ] For each trade: log (timestamp, counterparty, amount, CAR impact, decision)
  - [ ] False positive tracking (how many "would block" vs. "actually risky")
  - [ ] Dashboard update: "This trade would trigger veto if enabled"

### Day 10-14: Weekly Compliance Reports
- **Task:** Generate shadow-mode report (what would have been blocked)
- **Owner:** Compliance + Analytics (you)
- **Output:** Weekly PDF + JSON export
- **Checklist:**
  - [ ] % of daily trades flagged as high-risk
  - [ ] Breakdown by policy (CAR breach, liquidity threshold, counterparty limit)
  - [ ] False positive rate (flagged but actually compliant)
  - [ ] Latency report (P50, P99 gate-to-decision time)
  - [ ] Network isolation proof (0 Kbps outbound, 100% airgapped)

### Day 14-18: Feedback & Refinement
- **Task:** Trader UX feedback, rule tuning
- **Owner:** PM + Engineering (you)
- **Output:** Refined rules, zero false positives
- **Checklist:**
  - [ ] Trader feedback session (is the dashboard clear?)
  - [ ] Rule adjustments (sensitivity, thresholds)
  - [ ] Re-run shadow mode (measure improvement)
  - [ ] Final accuracy report (±0.01% CAR match confirmed)

**Week 2-3 Verification:** Shadow mode runs for 10+ trading days, zero blocking, 100% audit accuracy, traders understand dashboard.

---

## WEEK 4: GO-LIVE & FIRST AUTHORIZED TRADE

### Day 22-24: Veto Gate Activation
- **Task:** System goes LIVE (now blocks high-risk trades)
- **Owner:** DevOps + Backend (you)
- **Output:** Gate enforcement active, CRO authorization required
- **Checklist:**
  - [ ] Disable "logging only" mode
  - [ ] Enable veto card rendering (Pane 2, center)
  - [ ] Ed25519 key setup (CRO loads private key into dashboard)
  - [ ] Kill switch live (CRO can halt all in-flight trades)
  - [ ] Rollback plan documented (if needed)

### Day 24-26: First Trade Walkthrough
- **Task:** Supervised first authorized trade with CRO
- **Owner:** You + CRO + Architect (training session)
- **Output:** Veto gate → authorization → execution → proof ledger
- **Checklist:**
  - [ ] Trade submitted (e.g., "Sell €50M corporate bonds")
  - [ ] System flags (if CAR-impacting): red veto card appears
  - [ ] CRO review: shows Basel III impact + legal citation
  - [ ] CRO authorize: clicks "Authorize & Sign"
  - [ ] Ed25519 signature generated + verified (live in UI)
  - [ ] Trade executes
  - [ ] Proof receipt exported to compliance system (PDF + JSON + sig)

### Day 26-28: Proof Ledger Verification
- **Task:** Regulatory-grade audit trail export
- **Owner:** Compliance engineer (you)
- **Output:** JSON + PDF ready for BaFin/ECB audit
- **Checklist:**
  - [ ] Export format (schema, timestamp, sig, merkle root)
  - [ ] Verification script (anyone can re-verify signature)
  - [ ] Compliance team sign-off (format acceptable)
  - [ ] Archive strategy (daily backups, immutable storage)

### Day 28-31: Production Readiness
- **Task:** Final QA, go/no-go decision
- **Owner:** QA + Compliance + CTO (you)
- **Output:** Decision: proceed to production Nov 1, or extend shadow mode
- **Checklist:**
  - [ ] All 4 weeks of data packaged
  - [ ] Metrics dashboard final (CAR accuracy, latency, uptime)
  - [ ] SLA signed (99.95% uptime, <300ms latency)
  - [ ] Support runbook written (escalation, incident response)
  - [ ] CRO sign-off email: "We're ready for production"

**Week 4 Verification:** First trade authorized and executed, proof ledger verified, compliance cleared for production.

---

## DEPLOYMENT CHECKLIST (By Role)

### Backend Engineer (You)
- [ ] **Week 1:** Murex API client, CAR calculator, SQLite schema
- [ ] **Week 2:** Shadow-mode logging, no blocking
- [ ] **Week 3:** Feedback loop, rule tuning
- [ ] **Week 4:** Live gate, kill switch, test first trade

### DevOps / Infrastructure (You)
- [ ] **Week 1:** Docker build & push, network rules, ELK logging
- [ ] **Week 2:** Monitoring dashboard, health checks
- [ ] **Week 3:** Load testing (1000 trades/day, latency <300ms)
- [ ] **Week 4:** Production cutover plan

### Frontend Engineer (You)
- [ ] **Week 1:** CRO dashboard, CAR meter, airgap status badge
- [ ] **Week 2:** Report generation UI, feedback form
- [ ] **Week 3:** UX refinement based on trader input
- [ ] **Week 4:** Proof ledger export UI, final polish

### Compliance / Data Engineer (You)
- [ ] **Week 1:** Historical data load, validation queries
- [ ] **Week 2:** Weekly report generation, false positive analysis
- [ ] **Week 3:** Rule tuning recommendations
- [ ] **Week 4:** Final audit trail verification, archive setup

### CRO / Subject Matter Expert (UniCredit)
- [ ] **Week 1:** Validation that CAR calculations match internal system
- [ ] **Week 2:** Review weekly shadow reports, feedback on rules
- [ ] **Week 3:** Attend UX feedback session
- [ ] **Week 4:** Authorize first trades, sign off on system

---

## BLOCKING DEPENDENCIES

| Blocker | Unblocked By | Risk |
|---------|--------------|------|
| Can't wire Murex API | UniCredit API spec + staging creds | **HIGH** — need by Day 2 |
| Can't load historical data | Data export from Murex or DW | **HIGH** — need by Day 3 |
| Can't tune CAR rules | UniCredit's risk weighting table | **HIGH** — need by Day 4 |
| Can't go live | CRO sign-off on shadow-mode report | **MEDIUM** — need by Day 22 |

**Risk Mitigation:** Day 1 kickoff call → all dependencies confirmed → no delay.

---

## CRITICAL SUCCESS FACTORS

1. **Data Accuracy:** CAR calculations must match Murex ±0.01%. Non-negotiable.
2. **Latency:** <300ms gate-to-decision. Traders notice slowdowns.
3. **Reliability:** 99.95% uptime during trading hours. One outage = trust lost.
4. **Auditability:** Every decision Ed25519-signed, verifiable by compliance team.
5. **UX Clarity:** CRO can authorize in <30 seconds. Veto card is self-explanatory.

---

## GO / NO-GO DECISION (Oct 31)

**GO If:**
- ✅ CAR accuracy ±0.01%
- ✅ Latency <300ms (P99)
- ✅ Zero unplanned failures
- ✅ CRO sign-off email sent
- ✅ Compliance cleared audit trail

**NO-GO If:**
- ✗ CAR mismatch >0.01%
- ✗ Latency >500ms
- ✗ Any compliance concern unresolved
- ✗ CRO requests changes to veto logic

**Action on NO-GO:** Extend shadow mode 1-2 weeks, fix root cause, retry go-live.

---

## RESOURCE ALLOCATION

**Total Effort:** ~160 hours (4 weeks, 1 full-time engineer + 0.5 FTE DevOps + 0.5 FTE Data)

**Budget Impact:** Included in Year 1 €500K fee (€200K implementation portion covers this)

**Timeline Risk:** 90% confidence we hit Oct 31 go-live. 10% risk of 1-week slip (CAR tuning complexity).

---

## READY TO EXECUTE?

All tasks above are **real, execution-ready, no speculation.**

Next move: **Sep 8-15 kickoff call with UniCredit CTO.**

We send this roadmap, they confirm Murex access + data export schedule, we start Day 1.
