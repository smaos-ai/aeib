# Rest of Execution: Complete Roadmap (Sep 1, 2026 - Dec 31, 2027)
## Phase 1 Completion → Series A → Phase 2A-2C Full Delivery

---

## EXECUTIVE SUMMARY

| Period | Focus | Key Milestones | ARR |
|--------|-------|----------------|-----|
| **Sep 1 - May 31, 2027** | Phase 1 finalization | KARP (Sep 16) → Series A (Dec) → 3 pilots (Nov-Jan) | €10M-€12M |
| **Jun 1 - Jul 31, 2027** | Phase 2A (Intent + Egress) | L3B bootstrap → L4/egress → L8 logging | €15M-€20M |
| **Jul 1 - Sep 30, 2027** | Phase 2B (Federated GaaS) | Consensus → MCP → L8 sync (parallel with 2A) | €30M-€50M |
| **Oct 1 - Dec 31, 2027** | Phase 2C (Compliance) | Exporter → policy learning → KMS (parallel) | €100M-€150M |

**Total Effort:** 4,650 LOC remaining + 102 tests (16 months, solo engineer, TDD)

---

## TIMELINE: 16-MONTH EXECUTION CALENDAR

### **PHASE 1: COMPLETION (Sep 1, 2026 - May 31, 2027)**

#### **Sep 1-15: KARP Finalization**
- Week 1 (Sep 1-7): File verification, Series A customization, pilot CTOs contacted
- Week 2 (Sep 8-14): Final KARP polish, Series A deck+model ready
- Status: 95% complete → 100% by Sep 15
- Deliverable: KARP bundle ready (11 files, 144 KB)

#### **Sep 16-22: KARP Submission** 🎯
- Sep 16, 9:00 AM CET: Email KARP to romana.cernikova@karp-kv.cz
- Sep 22: KARP deadline (6-day buffer)
- Timeline: Approval expected Oct 1-15
- Deliverable: €120k CZK funding approval (60% immediate)

#### **Oct 1-31: Series A Outreach** 🎯
- Oct 1: 50 warm intro emails sent (customized per VC)
- Oct 1-20: First investor meetings (10-15 confirmations expected)
- Oct 20: Follow-up round to non-responders
- Timeline: 5-10 LOIs expected by Oct 31
- Deliverable: Investor momentum, term sheet negotiations start

#### **Nov 1 - Jan 31: 3-Pilot Execution** 🎯
- **Hotel Credit Scoring:** 150+ approvals, fairness audit
  - Nov 1-14: Data loading (1k guest records)
  - Nov 15-28: Policy deployment
  - Nov 29-Dec 5: Soft launch (10-30 approvals)
  - Dec 6-26: Production (100+ approvals)
- **Glass Factory Safety:** 50+ designs, 0% false negative
  - Nov 1-14: CAD schema finalization
  - Nov 15-28: Manufacturing integration
  - Nov 29-Dec 5: Soft launch (20-30 designs)
  - Dec 6-26: Production (30+ designs, zero failures)
- **School Biometric Access:** 2k+ access attempts, 99.9% uptime, 48h resilience
  - Nov 1-14: Enrollment (500 students)
  - Nov 15-28: Hardware deploy (biometric scanners)
  - Nov 29-Dec 5: Soft launch (100+ access attempts)
  - Dec 6-26: Production (2k+ attempts), 48-hour network outage test
- Timeline: 2,200+ decisions logged, AP2 ledger growing
- Deliverable: Real data, regulatory proof, customer testimonials

#### **Dec 1-31: Series A Close** 🎯
- Dec 1-15: Final due diligence (investor calls, pilot CTOs as references)
- Dec 15-20: Term sheet negotiation
- Dec 20-31: Legal + funding close
- Timeline: €3.5M-€10M capital expected
- Deliverable: €3.5M-€10M Series A capital in bank by year-end

#### **Feb 1 - May 31: Phase 1 Delivery**
- Feb-May: Final Phase 1 polish (RAGAS 87%+, regression testing, documentation)
- May 31: Phase 1 complete (€10M-€12M ARR from 3 pilots)
- Deliverable: Harness + 3 pilots live + Annex IV dossier + KARP final report

---

### **PHASE 2A: INTENT VERIFICATION + EGRESS CONTROLS (Jun 1 - Jul 31, 2027)**

#### **Jun 1-10: L3B Bootstrap Integration**
- Status: L3B middleware already done (Sep 1, 2026 bootstrap)
- Action: Code review + finalize L1→L3B→L4 glue
- Deliverable: L3B ready for L4 hook

#### **Jun 11-25: L4 Hook + Egress Controls Core (1,100 LOC)**
- L4 Tool Execution Hook (100 LOC, TDD)
  - Tests: route to L3B, enrich intent hash, fail-closed
  - Implementation: L4 orchestration callback integration
  - Timeline: Jun 11-15 (5 days)
- Egress Controls Core (1000 LOC, 6-layer, TDD)
  - Tests: block unlisted, allow whitelisted, rate limit, DNS rebinding, timeout
  - Implementation: YAML parser → DNS → DNSSEC → TLS → rate limit → kernel
  - Timeline: Jun 15-20 (6 days)

#### **Jun 26-Jul 10: L8 Metadata + Testing (250 LOC)**
- L8 Egress Decision Logging (200 LOC)
  - Tests: record decision, KMS signature, immutable audit trail
  - Implementation: AP2 ledger schema for egress decisions
  - Timeline: Jun 20-25 (5 days)
- Test Suite + Regression (250 LOC)
  - 27 new tests (L4 hook, egress, L8 logging)
  - 97 Phase 1 regression tests (0 regressions)
  - Load test: 100 concurrent, &lt;1ms latency p99
  - Timeline: Jun 26-Jul 10 (2 weeks)

#### **Jul 31: Phase 2A Delivery** 🎯
- Deliverable: 2,300 LOC complete, 27+ tests passing, €15M-€20M ARR
- Status: Intent verification + egress controls live, &lt;1ms latency
- Impact: Pre-execution governance + data residency compliance

---

### **PHASE 2B: FEDERATED GAAS (Jul 1 - Sep 30, 2027) [PARALLEL WITH 2A]**

#### **Jul 1-14: Byzantine Consensus Framework (400 LOC)**
- Tests: 3-region voting, 2/3 majority, Byzantine leader, timeout recovery
- Implementation: ConsensusVote, ConsensusGateway, propose/aggregate/merkle logic
- Timeline: Jul 1-14 (2 weeks)

#### **Jul 15-21: MCP Consensus Gateway (300 LOC)**
- Tests: /propose routing, /vote aggregation, /finalize commit
- Implementation: HTTP endpoints, async vote collection, TLS mTLS
- Timeline: Jul 15-21 (1 week)

#### **Jul 22-28: AP2 Ledger Sync (300 LOC)**
- Tests: 3-region atomic append, Merkle root consistency, divergence recovery
- Implementation: Regional ledger replication, sync_ledger, reconciliation
- Timeline: Jul 22-28 (1 week)

#### **Jul 29-Sep 30: Integration + Load Testing (300+ LOC)**
- Tests: 20 test cases (Byzantine, network, load), L1→L8 end-to-end
- Implementation: 100 concurrent, 1000 decisions/sec, p99 &lt;2s
- Timeline: Jul 29-Sep 30 (5 weeks)

#### **Sep 30: Phase 2B Delivery** 🎯
- Deliverable: 1,500 LOC complete, 20+ tests passing, €30M-€50M ARR
- Status: Federated GaaS live, 3-region consensus, 50+ gateways
- Impact: Multi-region governance, Byzantine fault tolerance

---

### **PHASE 2C: COMPLIANCE AUTOMATION (Oct 1 - Dec 31, 2027) [PARALLEL WITH 2A+2B]**

#### **Oct 1-14: L8 Dossier Exporter (200 LOC)**
- Tests: feed 100+ decisions, Annex III format, KMS signature
- Implementation: AP2 ledger query, dossier input pipeline
- Timeline: Oct 1-14 (2 weeks)

#### **Oct 15-28: Policy Learning Model (250 LOC)**
- Tests: train on 100 decisions (92%+ accuracy), predict new, feature importance
- Implementation: PolicyModel, fit_policy, predict_compliance, explain_decision
- Timeline: Oct 15-28 (2 weeks)

#### **Oct 29-Nov 7: KMS Integration (100 LOC)**
- Tests: dossier signed, signature verifiable
- Implementation: Ed25519 signing, PKIX envelope, verification
- Timeline: Oct 29-Nov 7 (1 week)

#### **Nov 8-Dec 31: Test Suite + Compliance Validation (300+ LOC)**
- Tests: 55+ integration tests (Annex III/IV/I, RAGAS 87%+, multi-language)
- Implementation: CAC 3.0 / CAICT 16/70 mapping, compliance validation
- Load: 2,200+ Phase 1 + 100M+ Phase 2B decisions → &lt;60s generation
- Timeline: Nov 8-Dec 31 (8 weeks)

#### **Dec 31: Phase 2C Delivery** 🎯
- Deliverable: 850 LOC complete, 55+ tests passing, €100M-€150M ARR
- Status: Compliance automation live, 500+ deployments, Annex dossiers
- Impact: Auto-regulatory proof, policy learning, multi-language support

---

## PARALLEL EXECUTION STREAMS (Jun-Dec 2027)

```
Jun 1  ─────────────────────────────  Jul 31: Phase 2A (2,300 LOC, 8 weeks)
       L3B bootstrap (done) → L4/egress → L8 logging

Jul 1  ──────────────────────────────  Sep 30: Phase 2B (1,500 LOC, 12 weeks)
       [PARALLEL]  Consensus → MCP → L8 sync → integration

Oct 1  ────────────────────────────  Dec 31: Phase 2C (850 LOC, 12 weeks)
       [PARALLEL]  Exporter → policy learning → KMS → tests
```

**All 3 phases run in parallel. Zero inter-phase dependencies. Solo engineer: 130 LOC/week with TDD.**

---

## RESOURCE ALLOCATION (Sep 2026 - Dec 2027)

### **Human Resources**
- **Solo Engineer:** Andrei Leukhin (100% through May 2027)
- **Runway:** Series A capital (€3.5M-€10M, closes Dec 2026)
- **Hiring:** Post-Series A (Phase 2A start)
  - 1x VP Engineering (Jun 2027)
  - 1x Sales lead (Jul 2027)
  - 2x Backend engineers (Aug 2027)

### **Infrastructure**
- **Colibri local inference:** RTX 4060 (€8k, in-hand)
- **Phase 1 pilots:** Running in production (Nov-Dec 2026)
- **Phase 2A-C:** Kubernetes deployment (Jun 2027+)
- **Regional gateways:** 50+ by Sep 2027 (Phase 2B)

### **Capital**
- **KARP funding:** €120k CZK (Oct 2026)
- **Series A:** €3.5M-€10M (Dec 2026)
- **BIC Plzeň Phase 2:** 1M CZK (Mar 2027 expected)

---

## CRITICAL PATH DEPENDENCIES

### **BLOCKING (Must Complete First)**
- KARP submission (Sep 16) → Oct approval → Phase 1 credibility
- Series A close (Dec 2026) → funding for Phase 2 team
- Phase 1 delivery (May 31, 2027) → pilot proof for Phase 2

### **OPTIONAL BLOCKING (Phase-Internal)**
- Phase 2A: L3B bootstrap (done) → L4 hook (Jun 11) → rest of Phase 2A
- Phase 2B: Consensus (Jul 1) → MCP (Jul 15) → L8 ledger (Jul 22)
- Phase 2C: Exporter (Oct 1) → policy learning (Oct 15) → KMS (Oct 29)

### **NON-BLOCKING (Can Start on Schedule)**
- Phase 2A, 2B, 2C all start independently (no cross-phase dependencies)

---

## QUARTERLY MILESTONES

| Quarter | Phase | Revenue | Key Metrics | Status |
|---------|-------|---------|------------|--------|
| **Q3 2026** | Phase 1 Final | €10M-€12M | KARP submitted, Series A fundraising | In progress |
| **Q4 2026** | Phase 1 → Series A | €10M-€12M | 3 pilots live (2.2k decisions), €3.5M-€10M capital raised | Target |
| **Q1 2027** | Phase 1 Complete | €10M-€12M | Phase 1 delivery (May 31), Annex IV dossier ready | Target |
| **Q2 2027** | Phase 2A | €15M-€20M | Intent verification + egress controls live | Target |
| **Q3 2027** | Phase 2A+2B | €30M-€50M | Federated GaaS (50+ gateways), consensus proven | Target |
| **Q4 2027** | Phase 2A+2B+2C | €100M-€150M | Compliance automation, 500+ deployments, Annex dossiers | Target |

---

## SUCCESS METRICS (Dec 31, 2027)

✅ **Delivery:** All 4,650 LOC implemented + 102 tests passing  
✅ **Revenue:** €100M-€150M ARR (10x Phase 1 baseline)  
✅ **Customers:** 500+ deployments (EU 200, US 150, China 100+)  
✅ **Regulatory:** CAC 3.0 + EU AI Act Annex III/I compliance proven  
✅ **Team:** 1 engineer Phase 1-2C, 10-person team by Phase 2C end  
✅ **Moat:** Intent verification + federated consensus (6-12 month competitive advantage)  
✅ **Series B Ready:** €100M+ ARR, 500+ customers, regulatory proof, strong team narrative

---

## WHAT'S NOT IN SCOPE (2028+)

❌ **Phase 3:** Further optimization, additional verticals, global expansion  
❌ **Phase 3:** Enterprise support teams, professional services, managed SaaS  
❌ **Phase 3:** IPO preparation, strategic partnerships beyond Phase 2C  

**Note:** Phase 3 roadmap starts Jan 2028, beyond this execution plan (2026-2027).

---

## HOW TO USE THIS ROADMAP

**For Investors:** Show this timeline in Series A pitch (€3.5M-€10M to hit €100M+ ARR by Dec 2027)  
**For Team:** Share with new hires (VP Eng, sales) when they start (Jun-Jul 2027)  
**For Tracking:** Update every Friday (week status, blockers, next week forecast)  
**For Course Corrections:** Revisit every quarter (Q3/Q4 2026, Q1-Q4 2027)

---

**Status:** 📋 Complete execution roadmap locked (Sep 2026 - Dec 2027)  
**Next Step:** Choose start date (now Sep 1 vs. postpone KARP to Oct/Nov)  
**Generated:** Sep 1, 2026