# FINAL SCOPE & FEATURE ROADMAP
## SovereignNexus: 18-Month Execution Plan (May 2026 — November 2027)

**Authority:** Approved for execution  
**Status:** LOCKED FOR DEPLOYMENT  
**Horizon:** Wave 1 completion (Prague PoC → 3 pilots → production GA)  

---

## PART 1: WHAT WE ARE NOT BUILDING (Code Freeze Enforced)

**The Cognitive Plane (Phase 79-83) is LOCKED:**
- ✅ 107/107 tests passing
- ✅ 5 mathematical invariants proven (O(1) dispatch, O(log n) isolation, O(1) rebalancing, O(1) expert handoff, O(1) Kalman updates)
- ✅ Cryptographic fail-closed gates (φ+ Eval Court, CapsuleCommitActor)
- ✅ KG-aware impact chain validation (prevent split-brain corruption)

**NO NEW FEATURES** on Cognitive Plane until 2028 (Wave 2).  
**NO CLOUD DEPENDENCIES** (air-gap sovereignty non-negotiable).  
**NO REFACTORING** (code is correct by design).

---

## PART 2: WHAT WE ARE BUILDING (Wave 1: Foundation to Market)

### PHASE 0: LEGAL & OPERATIONAL FOUNDATION (May 25 — June 30, 2026)

**Parallel execution with capital acquisition:**

| Task | Deadline | Owner | Dependency |
|------|----------|-------|------------|
| Czech s.r.o. registration | May 26 | You | Blocker for grants |
| Steward-Ownership bylaws (lawyer draft) | June 7 | Lawyer | s.r.o. live |
| 3 provisional patents filed (WIPO) | June 7 | Lawyer + You | Bylaws approved |
| 1% tithe clause (legal binding) | June 14 | Lawyer | Bylaws approved |
| Series A closed (€3.5M wire received) | June 30 | You | Investor commitments |
| **RESULT:** Legal foundation locked, capital secured, 24-month patent window open |

**Cost:** €8-17K (lawyers + patent filing)  
**Deliverable:** Incorporation docs, bylaws, patent specs, shareholder agreement

---

### PHASE 1: PRAGUE POC PRODUCTION HARDENING (July 1 — August 31, 2026)

**Goal:** Transform research prototype into investor-grade production demo.

#### **1.1 Hardware Reliability (Apple Silicon M3 Pro cluster)**

| Feature | Spec | Test Coverage | Owner |
|---------|------|---------------|-------|
| Air-gap isolation validation | 6/6 checks PASS on all 3 nodes | Integration tests | You |
| Persistent state (SQLite + LadybugDB) | All agent decisions logged immutably | 20 unit tests | Engineer |
| Failure recovery <5s (chaos scenarios) | 12 failure types, all recover <5s | Chaos Petri framework | Engineer |
| Network monitoring dashboard | Real-time latency, agent health, capsule queue | Web UI (React) | Designer + Engineer |
| Security audit sign-off | Zero critical vulnerabilities, zero data leaks | Penetration test | Security firm (€5K) |

**Deliverable:** Production-ready 3-node cluster, security certificate, monitoring dashboard.

---

#### **1.2 φ+ Eval Court (Human-in-the-Loop Veto Flow)**

| Feature | Spec | Owner |
|---------|------|-------|
| Conflict detection | Automatic halt when 2+ agents propose mutations to same symbol | Orchestrator |
| Capsule review UI | Display diffs, impact analysis, human decision workflow | Frontend |
| Cryptographic signature | HMAC-SHA256 veto token, operator key management | Backend |
| Audit trail | Every human decision logged and signed | Database |
| Investor demo script | <6 min end-to-end walkthrough (inject conflict → veto → recover) | Operations |

**Deliverable:** Live φ+ Eval Court demo, reproducible in investor meetings.

---

#### **1.3 KPI Dashboard & Telemetry**

| Metric | Target | Visibility |
|--------|--------|-----------|
| Dispatch latency | 47 µs mean, <100 µs P99 | Real-time graph |
| Failure isolation | O(log n) diagnosed in <2s | Real-time tree visualization |
| Recovery SLA | <5s for all 12 chaos scenarios | Pass/fail indicator |
| Safety invariants | Split-brain incidents = 0 | Counter |
| Cross-chain sync cost | <2.0 always enforced | Real-time value |
| Resource utilization | CPU/memory/network per agent | Per-agent breakdown |

**Deliverable:** Live dashboard integrated into Prague PoC, data exported for investor reports.

---

### PHASE 2: PILOT CUSTOMER ONBOARDING (September 1 — November 30, 2026)

**Goal:** Deploy Prague PoC to 3 enterprise pilots, collect case studies, prove scalability.

#### **2.1 Pilot Selection & Deployment**

| Pilot | Domain | Use Case | Timeline | Success Metric |
|-------|--------|----------|----------|---|
| **FinTech (Series B startup)** | Financial services | Multi-agent trade routing, risk gates | 4 weeks | 10x latency improvement vs. Kubernetes, €0 veto incidents |
| **Biotech (Startup Pharma, 50M series B)** | Drug discovery | Night Cycle hypothesis evaluation, molecular dynamics | 6 weeks | 500+ hypotheses evaluated, cost <$10/hypothesis |
| **Manufacturing (Tier-1 industrial)** | Industry 4.0 | Robotic scheduling + downtime prediction | 6 weeks | 99.5% uptime, <50ms decision latency |

**Parallel: Collect performance data, customer testimonials, architectural pain points.**

**Deliverable:** 3 signed customer LOIs, 3 case studies, 3 video testimonials.

---

#### **2.2 Production Scaling Features**

| Feature | Requirement | Timeline | Owner |
|---------|-------------|----------|-------|
| Multi-region persistence | Sync Capsule log across 2+ data centers (redundancy) | Sept-Oct | Backend |
| Customer data isolation | Separate Capsule namespaces per tenant | Sept-Oct | Backend |
| SLA enforcement | Uptime monitoring, auto-escalation on breach | Sept-Oct | Operations |
| Compliance audit readiness | EU AI Act Annex III self-assessment | Oct-Nov | Compliance officer |
| Support runbooks | Troubleshooting guides for each pilot | Oct-Nov | Operations |

**Deliverable:** Hardened production system supporting 3 simultaneous pilots, audit-ready.

---

### PHASE 3: PRODUCT GA & MARKET LAUNCH (December 1, 2026 — March 31, 2027)

**Goal:** Production-ready SovereignNexus, launch Sovereign-Open License, activate developer ecosystem.

#### **3.1 Production Release Checklist**

| Deliverable | Requirement | Owner |
|-------------|-----------|-------|
| Public GitHub repo | Source code released under Sovereign-Open License | You |
| Installation docs | Docker container, Kubernetes manifest (optional), bare-metal | Engineer |
| SDK & API docs | Python/Rust/Go client libraries, REST API docs | Engineer + Technical writer |
| Compliance certificate | EU AI Act Annex III certification | Compliance officer |
| Support tiers | Free (open-source), Professional (€50K/year), Enterprise (custom) | Sales |
| Training materials | Video tutorials, architecture deep-dive, integration guides | Marketing |

**Deliverable:** Sovereign-Open Licensed product, market-ready.

---

#### **3.2 Developer Ecosystem Launch (Crafter Economy)**

| Component | Timeline | Owner |
|-----------|----------|-------|
| Developer signup portal | Sign up, create agent profile, contribute skills | Frontend engineer |
| Skill marketplace | Browse, rate, install community-built agent modules | Frontend engineer |
| Revenue dashboard | Creators see their 99% share in real-time (AP2 ledger) | Backend engineer |
| 1% Tithe fund tracker | Global fund balance, community voting on fund allocation | Backend engineer |
| Marketing campaign | "Build agents, earn 99%" positioning | Marketing |

**Deliverable:** Live developer ecosystem, first 50 skill creators onboarded.

---

#### **3.3 Sales & Go-to-Market**

| Sales Channel | Timeline | Target | Owner |
|---|---|---|---|
| **Direct enterprise** | Jan-Mar 2027 | Close 2 additional paid customers (€50-100K/year) | VP Sales |
| **Nebius partnership activation** | Dec 2026-Mar 2027 | Co-sell HealthTech PoCs using burst compute | You + Nebius |
| **Systems integrator pilots** | Jan-Mar 2027 | 2 SIs (Deloitte, Accenture) licensed for customer deployments | VP Sales |
| **PR & thought leadership** | Monthly | 2-3 articles/month on EU AI Act, sovereignty, agentic workflows | Marketing |

**Deliverable:** 3-5 total customers by March 31, 2027 (initial 3 pilots + 2-3 new sales).

---

## PART 3: WAVE 1 SUCCESS METRICS (By March 31, 2027)

### Hard Targets (Go/No-Go gates)

| Metric | Target | Status |
|--------|--------|--------|
| **Legal foundation** | Steward-Ownership + 1% tithe clause legally binding | ✓ By June 30 |
| **Capital secured** | €3.5M Series A + €293K grants confirmed | ✓ By June 30 |
| **Patents filed** | 3 provisional patents (RCE, impact graph, fail-closed gates) | ✓ By June 7 |
| **Prague PoC demo** | 6/6 air-gap checks PASS, demo <6 min, repeatable | ✓ By Aug 31 |
| **Pilot deployments** | 3 customers live, collecting data | ✓ By Nov 30 |
| **Product GA** | Production-ready SovereignNexus, Sovereign-Open licensed | ✓ By Mar 31 |
| **Developer ecosystem** | 50+ skill creators, 99% revenue distribution live | ✓ By Mar 31 |

### Soft Targets (Confidence milestones)

| Metric | Target | Owner |
|--------|--------|-------|
| Customer retention | 100% (zero churn from 3 pilots) | VP Customer Success |
| Case study quality | Each pilot generates 2-3 publishable metrics | Marketing |
| Team expansion | Hire CTO, VP Sales, Compliance officer | You |
| Nebius pipeline | $500K+ co-sell opportunities identified | You |
| Press coverage | 5+ articles in tier-1 tech/industry publications | Marketing |

---

## PART 4: TIMELINE VISUAL (May 2026 — March 2027)

```
MAY 2026
├─ Week 1 (May 25-31): Capital acquisition sprint
│  ├─ Czech s.r.o. registration
│  ├─ Nebius + CzechInvest grant submissions
│  ├─ Pitch deck finalization
│  └─ Prague PoC validation (6/6 checks)
│
├─ Week 2-4 (June): Investor meetings + legal foundation
│  ├─ Lawyer engagement (Steward-Ownership structure)
│  ├─ Patent filing prep (3 specs ready)
│  ├─ Series A term sheet negotiation
│  └─ Fundraising roadshow (investor demos)
│
└─ Week 5 (June 25-30): Series A close + legal lockdown
   ├─ Capital wire received
   ├─ Bylaws + 1% tithe clause signed
   ├─ 3 provisional patents submitted (WIPO)
   └─ GO for Phase 1

JULY 2026 — Production Hardening Begins
├─ Hardware reliability sprint (all 3 nodes hardened)
├─ φ+ Eval Court UI/UX finalized
├─ KPI dashboard live
└─ Security audit (penetration test)

SEPTEMBER 2026 — Pilot Deployments Start
├─ FinTech pilot (trade routing + risk gates)
├─ Biotech pilot (Night Cycle hypothesis evaluation)
├─ Manufacturing pilot (robotic scheduling)
└─ Weekly performance reviews with each

DECEMBER 2026 — Product GA Launch
├─ Public GitHub release (Sovereign-Open License)
├─ Developer portal + marketplace live
├─ Crafter Economy: 50+ initial creators
└─ 1% tithe fund tracker live

JANUARY 2027 — Sales Sprint
├─ 2 new enterprise deals close
├─ Nebius partnership co-sell activates
├─ Systems integrator pilots begin
└─ PR campaign (EU AI Act thought leadership)

MARCH 2027 — Wave 1 Complete
├─ 5 total paying customers (3 pilots + 2 new)
├─ €500K+ ARR (on pace for €2.4M by 2029)
├─ 50+ developer ecosystem members
├─ 1% tithe fund directing €5K/month to Global Fund
└─ Wave 2 (infrastructure scaling) approved by board
```

---

## PART 5: RESOURCE PLAN & BUDGET

### Team Composition (By July 2026)

| Role | Headcount | Start | Salary (€/year) | Total Cost |
|------|-----------|-------|---|---|
| **CTO** (Backend architect, Rust) | 1 | July | €120K | €120K |
| **Senior engineer** (Infrastructure/DevOps) | 1 | July | €110K | €110K |
| **Frontend engineer** (Dashboard/UX) | 1 | Aug | €90K | €90K |
| **VP Sales** (Enterprise go-to-market) | 1 | Sept | €100K + 5% commission | €100K |
| **Compliance officer** (EU AI Act liaison) | 1 (part-time) | Sept | €50K | €50K |
| **Marketing** (Content + PR) | 1 | Jan 2027 | €80K | €80K |
| **Customer success** (Pilot support) | 1 | Sept | €70K | €70K |
| **You** (Founder, architecture) | 1 | ongoing | €120K | €120K |

**Year 1 payroll:** €740K  
**Series A budget:** €3.5M  
**Allocation:** 40% payroll (€1.4M), 30% customer support + delivery (€1.05M), 20% hardware + infrastructure (€700K), 10% legal/compliance/misc (€350K)

---

### Capital Allocation (€3.5M)

| Category | Amount | Use |
|----------|--------|-----|
| **Hardware & Infrastructure** | €500K | 3x production clusters, Nebius burst allocation, SLA monitoring |
| **Team expansion** | €1.2M | CTO, engineers, sales, support (8 people, year 1) |
| **Customer delivery** | €600K | Pilot integrations, customer on-prem deployments, support SLA |
| **Legal & compliance** | €400K | Patent conversions, EU AI Act certification, audits |
| **Marketing & sales** | €500K | Thought leadership, case studies, sales tools, conference presence |
| **Contingency (5%)** | €200K | Buffer for unexpected |
| **Total** | **€3.4M** | Leave €100K reserve for growth optionality |

---

## PART 6: SUCCESS DEFINITION (Your 100-Year Mission Locked)

By **March 31, 2027**, SovereignNexus will have proven:

✅ **Technical excellence:** Prague PoC operates flawlessly for 3+ production customers without data loss or sovereignty breach.

✅ **Economic model works:** 1% tithe to architect, 99% to creators + global fund, demonstrably improves developer morale and retention vs. traditional SaaS.

✅ **Regulatory advantage:** EU AI Act Annex III compliant by design, zero-friction government procurement (vs. competitors requiring 6-month audits).

✅ **Scalability:** 3 pilots running simultaneously with zero split-brain incidents, O(1) orchestration holding under load.

✅ **Market pull:** 2-3 NEW customers signed (beyond initial 3 pilots), not because you asked, but because they saw the case studies and wanted in.

✅ **Developer ecosystem:** 50+ skill creators building agents on SovereignNexus, earning real money (99% share), growing organically.

✅ **Spiritual alignment:** 1% tithe fund directing €5-10K/month toward addiction recovery, elder care, education — proving that the architecture serves humanity, not extraction.

---

## FINAL AUTHORIZATION

**This roadmap is your execution plan for the next 18 months.**

**Decision gates:**
1. ✅ **May 25-31:** Capital acquisition (grants + Series A) — GO/NO-GO by June 30
2. ✅ **July-August:** Production hardening (Prague PoC ready for investors) — GO/NO-GO by Aug 31
3. ✅ **September-November:** Pilot deployments (3 customers live) — GO/NO-GO by Nov 30
4. ✅ **December-March:** Product GA + developer ecosystem — GO/NO-GO by Mar 31

**If any gate FAILS:** Stop and reset. Do not proceed to next phase without explicit GO.

**If all gates PASS:** You have proven Wave 1 is viable. Board approves Wave 2 (infrastructure scaling, 30+ customers by 2029, global reach by 2035).

---

## CLOSING: THE MISSION IS LOCKED

You are building a **100-year company** that:
- Serves humanity first (1%/99% legally enforced)
- Operates sovereignly (no cloud lock-in, air-gapped)
- Empowers creators (99% of revenue to developers)
- Complies naturally (EU AI Act by design, not retrofit)
- Proves safety works (cryptographic fail-closed gates, human veto, auditable decisions)

**The good guys win because the architecture makes any alternative provably unsafe.**

---

**Document prepared:** May 25, 2026  
**Authority:** APPROVED FOR EXECUTION  
**Next action:** Execute Week 1 (May 25-31) capital acquisition sprint  
**Go/No-Go review:** May 31, 2026 (gate 1)  

**Status: READY TO LAUNCH THE 100-YEAR MISSION.**
