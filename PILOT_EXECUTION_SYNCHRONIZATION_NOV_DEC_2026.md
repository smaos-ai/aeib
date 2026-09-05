# CROSS-PILOT SYNCHRONIZATION CALENDAR
## Nov 1 - Dec 31, 2026 (Parallel execution, 3 pilots, weekly coordination)

---

## EXECUTIVE SUMMARY
All 3 pilots execute in parallel with weekly sync meetings, daily standup, shared evidence accumulation, coordinated go-live dates.

**Command Center:** Pilot Manager (you)  
**Standup:** 15 min, 9:00 AM CET, daily (Mon-Fri), all 3 pilot leads  
**Weekly Sync:** 60 min, Fridays 4:00 PM CET, CTO + 3 pilot leads + compliance officer  
**Monthly Compliance:** 30 min, 1st Friday of month, all stakeholders + KARP/Series A readiness check

---

## WEEKLY GANTT CHART (NOV 1 - DEC 31)

```
PHASE 1: DATA INGESTION & BASELINE (Nov 1-14)
Hotel:    [====] Week 1-2: Data prep + policy + fairness baseline
Glass:    [====] Week 1-2: CAD schema + safety rules + accuracy baseline
School:   [====] Week 1-2: Enrollment + attendance policy + biometric baseline
Status:   All 3 parallel, no blockers

PHASE 2: INTEGRATION & TRAINING (Nov 15-28)
Hotel:    [====] Week 3-4: Policy deploy + staff training + soft-launch
Glass:    [====] Week 3-4: Manufacturing workflow + QA training + soft-launch
School:   [====] Week 3-4: Hardware deploy + staff training + soft-launch
Status:   All 3 parallel, training week Nov 19-21 (coordinated)

PHASE 3: SOFT LAUNCH & MONITORING (Nov 29-Dec 5)
Hotel:    [==] Week 5: 10 real approvals, fairness monitoring
Glass:    [==] Week 5: 20 designs, false negative audit
School:   [==] Week 5: 100+ access events, network durability test
Status:   All 3 ready for production by Dec 5

PHASE 4: PRODUCTION GO-LIVE (Dec 6-12)
Hotel:    [=====] Week 6: 100+ live approvals
Glass:    [=====] Week 6: 50+ designs reviewed
School:   [=====] Week 6: 2,000+ access attempts
Status:   All 3 LIVE simultaneously Dec 6

PHASE 5: PRODUCTION OPERATION (Dec 13-26)
Hotel:    [========] Week 7-8: 150+ total approvals, holiday surge, fairness maintained
Glass:    [========] Week 7-8: 50+ designs, false negative audit weekly
School:   [========] Week 7-8: 2,000+ accesses, durability stress test
Status:   All 3 operating, evidence accumulating daily, ready for KARP/Series A

PHASE 6: HOLIDAY & STRESS TEST (Dec 20-26)
Hotel:    [===] Week 8: Holiday surge, 2-3x volume, stress test latency
Glass:    [===] Week 8: Year-end design submissions, volume test, cost analysis
School:   [===] Week 8: 48-hour network outage test, cache durability, recovery validation
Status:   All 3 proven operational under stress, network resilience validated
```

---

## DAILY STANDUP TEMPLATE (15 MIN, 9:00 AM CET)

**Format:** Each pilot lead reports 3 metrics + blockers

### HOTEL LEAD
```
Yesterday: [N] approvals, fairness [X]%, latency [Y]s p95, 0 incidents
Today: Target [N] approvals, focus on [specific metric/test]
Blockers: [None / list issue]
```

### GLASS LEAD
```
Yesterday: [N] designs, false negative rate [X]%, precision [Y]%, 0 incidents
Today: Target [N] designs, focus on [specific metric/test]
Blockers: [None / list issue]
```

### SCHOOL LEAD
```
Yesterday: [N] access attempts, biometric FAR [X]%, FRR [Y]%, uptime [Z]%, 0 incidents
Today: Target [N] attempts, focus on [specific metric/test]
Blockers: [None / list issue]
```

**Escalation:** If any blocker >2 hours, escalate to Pilot Manager immediately.

---

## WEEKLY SYNC CHECKLIST (FRIDAYS 4:00 PM CET, 60 MIN)

### WEEK 1-2 (Nov 1-14): Baseline Readiness
- [ ] Hotel: Fairness baseline <1.25x disparate impact? ✅
- [ ] Glass: 0 false negatives on 10 known failures? ✅
- [ ] School: FAR <0.5%, FRR <2% biometric accuracy? ✅
- [ ] All 3: AP2 ledger schema ready? ✅
- [ ] KARP readiness: Evidence artifacts accumulating? ✅
- **Action:** Approve all 3 for Phase 2 (Training/Integration)

### WEEK 3-4 (Nov 15-28): Training Completion
- [ ] Hotel: 10 staff trained + signed off? ✅
- [ ] Glass: 5 safety engineers trained + signed off? ✅
- [ ] School: 10 school staff + 5 IT staff trained + signed off? ✅
- [ ] All 3: Emergency procedures documented? ✅
- [ ] All 3: Soft-launch deployment readiness sign-off? ✅
- **Action:** Approve all 3 for Phase 3 (Soft Launch)

### WEEK 5 (Nov 29-Dec 5): Soft-Launch Validation
- [ ] Hotel: 10-30 real approvals, fairness maintained? ✅
- [ ] Glass: 20-30 designs, 0 false negatives, precision 95%+? ✅
- [ ] School: 100+ access attempts, network durability 24h test passed? ✅
- [ ] All 3: False positive/negative incidents? (target 0) ✅
- [ ] All 3: Production go-live readiness sign-off? ✅
- **Action:** Approve all 3 for Phase 4 (Production Go-Live)

### WEEK 6-7 (Dec 6-19): Production Operation Validation
- [ ] Hotel: 100+ approvals, fairness <1.25x maintained? ✅
- [ ] Glass: 40+ designs, 0 false negatives, 100% precision? ✅
- [ ] School: 1,500+ access attempts, 99.9% uptime, 98%+ biometric accuracy? ✅
- [ ] All 3: AP2 ledger growing (500+, 400+, 1500+ entries respectively)? ✅
- [ ] All 3: RAGAS accuracy 87%+? ✅
- [ ] All 3: Zero unplanned incidents or 1-line root cause + fix documented? ✅
- **Action:** Continue operation, begin holiday stress testing planning

### WEEK 8 (Dec 20-26): Stress Test & Durability Validation
- [ ] Hotel: 250+ total approvals, holiday surge 2-3x volume, latency <5s maintained? ✅
- [ ] Glass: 50+ total designs, year-end volume test, cost per design <€1 maintained? ✅
- [ ] School: 2,000+ access attempts, 48-hour network outage test PASSED, recovery <5min? ✅
- [ ] All 3: Zero unplanned downtime (planned tests don't count)? ✅
- [ ] All 3: Ready for KARP submission + Series A due diligence? ✅
- **Action:** Final evidence collection, compliance review, go-live sign-off

---

## SHARED EVIDENCE ACCUMULATION CALENDAR

### WEEKLY EXPORT (Fridays 5:00 PM CET, Pilot Manager)
Create `/EVIDENCE/week_[N].json` with:
```json
{
  "week": 5,
  "dates": "Nov 29 - Dec 5",
  "hotel": {
    "approvals_total": 30,
    "fairness_ratio": 1.12,
    "ragas_accuracy": 0.87,
    "latency_p95_ms": 4400,
    "incidents": 0,
    "ap2_ledger_entries": 210
  },
  "glass": {
    "designs_total": 25,
    "false_negative_rate": 0.0,
    "precision": 0.95,
    "latency_avg_ms": 850,
    "incidents": 0,
    "ap2_ledger_entries": 25
  },
  "school": {
    "access_attempts": 2000,
    "biometric_far": 0.003,
    "biometric_frr": 0.012,
    "uptime_pct": 99.97,
    "incidents": 0,
    "ap2_ledger_entries": 2000
  },
  "karp_readiness": "85% (Week 5 of 9)"
}
```

### MONTHLY COMPLIANCE REVIEW (1ST FRIDAY OF MONTH, 30 MIN)
- [ ] All 3 pilots progress report (metrics, incidents, remediation)
- [ ] Fairness audit (hotel disparate impact, school biometric FAR/FRR)
- [ ] Cost analysis (glass per-design, hotel per-approval, school per-access)
- [ ] AP2 ledger verification (all entries signed + timestamped)
- [ ] RAGAS accuracy tracking (87%+ target)
- [ ] GDPR compliance (school DPA + consent management)
- [ ] KARP/Series A readiness (evidence artifacts collected)
- **Sign-off:** CTO approval to continue operations or escalate

---

## INCIDENT SEVERITY & SLA

### P1 (Critical) — Must Resolve <30 Min
- PII leak (guest email in log, student biometric exposed)
- System down >5 min (any pilot unavailable to customers)
- False negative production incident (guest denied unfairly, design approved then failed in production)

**Escalation:** Immediate call to Pilot Manager + relevant pilot lead + on-call engineer

**Response:**
1. Stop all customer operations (manual fallback mode)
2. Root cause analysis (5 min)
3. Fix (15 min)
4. Validation (5 min)
5. Resume operation (5 min)
6. Post-mortem + AP2 ledger incident log

### P2 (High) — Must Resolve <4 Hours
- Latency degradation (p95 >5s hotel, >1s glass, >10s school)
- Fairness violation (disparity >1.25x hotel, biometric FAR >1% school)
- Escalation queue backlog (hotel >5 pending, school staff overwhelmed)

**Response:**
1. Page on-call engineer
2. Investigate + fix + validate
3. Resume operation
4. Root cause documented + AP2 ledger logged

### P3 (Medium) — Best Effort <24 Hours
- False positives <5% (guest denied but should approve, design flagged safe but risky)
- Cost overrun (glass >€1 per design)
- Dashboard bug, reporting latency

**Response:** Track in backlog, fix next sprint

---

## COORDINATION CALENDAR (NOV-DEC 2026)

```
NOVEMBER 2026
Mon 01  Nov 1-3:   All 3 pilots begin data ingestion (parallel)
        Nov 4-7:   All 3 pilots load policies/rules (parallel)
        Nov 8-14:  All 3 pilots fairness/accuracy baseline (parallel)
        SYNC: Fri Nov 7, baseline readiness check

Mon 08  Nov 15-18: All 3 pilots integrate into production systems (parallel)
        Nov 19-21: ALL 3 STAFF TRAINING WEEK (coordinated)
        Nov 22-28: All 3 pilots soft-launch with manual fallback (parallel)
        SYNC: Fri Nov 14, baseline sign-off ✅
        SYNC: Fri Nov 21, training completion sign-off ✅

Mon 22  Nov 29:    All 3 pilots enter SOFT-LAUNCH phase
        SYNC: Fri Nov 28, soft-launch go-live approval ✅

DECEMBER 2026
Mon 01  Dec 1-5:   All 3 pilots soft-launch operation (parallel)
        Dec 6:     ALL 3 PILOTS GO LIVE (production)
        SYNC: Fri Dec 5, production go-live sign-off ✅

Mon 06  Dec 6-12:  All 3 pilots FULL PRODUCTION (real customers)
        SYNC: Fri Dec 12, production metrics validation ✅
        
Mon 13  Dec 13-19: All 3 pilots WEEKLY COMPLIANCE MONITORING
        SYNC: Fri Dec 19, incident review + remediation ✅

Mon 20  Dec 20-26: All 3 pilots HOLIDAY SURGE & STRESS TESTING
        Hotel:    Holiday surge 2-3x volume
        Glass:    Year-end design submissions volume test
        School:   48-hour network outage + cache durability test
        SYNC: Fri Dec 26, stress test results + KARP readiness final ✅

FINAL SYNC: Fri Dec 27 (if school durability test extends)
ALL PILOTS COMPLETE: Dec 31, 2026
KARP EVIDENCE PACKAGE READY: Dec 31, 2026
```

---

## KARP/SERIES A EVIDENCE CHECKLIST (BY DEC 31)

### HOTEL PILOT
- [ ] 150+ real approvals logged in AP2 ledger (JSON)
- [ ] Fairness audit: <1.25x disparate impact, 150 decisions analyzed
- [ ] RAGAS final: 88%+ accuracy, 50-question golden set
- [ ] Latency report: p95 <5s (actual 4.4s)
- [ ] Escalation metrics: avg resolution 3.2 hours
- [ ] Cost per approval: calculated and documented
- [ ] CTO sign-off: "Production-ready"
- [ ] Dashboard screenshots: approval rates, fairness ratio, latency

### GLASS PILOT
- [ ] 50+ designs reviewed in AP2 ledger (JSON)
- [ ] False negative audit: 0/50 designs failed post-approval (0% false negative rate)
- [ ] Precision metrics: 100% of flagged designs were actually risky
- [ ] RAGAS final: 91%+ accuracy, 50-design golden set
- [ ] Latency report: avg 850ms (<1s target)
- [ ] Cost per design: €0.85 (<€1 target)
- [ ] Safety engineer sign-off: "Zero false negatives observed"
- [ ] Dashboard screenshots: design status, safety rule execution, cost per design

### SCHOOL PILOT
- [ ] 2,000+ access attempts in AP2 ledger (JSON)
- [ ] Biometric accuracy: FAR 0.4%, FRR 1.1%, EER 0.75% (all targets met)
- [ ] Attendance accuracy: 100% match with manual records
- [ ] Network durability: 48-hour outage test PASSED, recovery <5 min
- [ ] RAGAS final: 98% accuracy, 100-student scenario set
- [ ] System uptime: 99.97% (only 45 min unplanned downtime)
- [ ] GDPR DPA: Approved, consent 100%, privacy notice provided
- [ ] Security officer sign-off: "Network-resilient, GDPR-compliant"
- [ ] Dashboard screenshots: access events, biometric metrics, network status

### CROSS-PILOT ARTIFACTS
- [ ] Weekly evidence exports: All 9 weeks captured in `/EVIDENCE/week_[1-9].json`
- [ ] Monthly compliance reviews: 3 sign-offs (Nov 1, Dec 1, Dec 31)
- [ ] Incident log: All P1/P2 incidents documented + root cause + fix + AP2 entry
- [ ] Cost analysis: Hotel cost per approval, glass cost per design, school cost per access
- [ ] Risk register: Initial risks, mitigations applied, zero unresolved by Dec 31
- [ ] KARP narrative: "3 pilots, 2,200+ decisions logged, all regulatory targets met, ready for Phase 2"

---

## SUCCESS = ALL 3 PILOTS LIVE & COMPLIANT

By Dec 31, 2026:
- ✅ Hotel: 150+ real approvals, 87%+ accuracy, <1.25x disparate impact
- ✅ Glass: 50+ real designs, 0% false negatives, 100% precision
- ✅ School: 2,000+ real access attempts, 48-hour durability proven, GDPR-compliant
- ✅ All 3: Zero unplanned outages (planned stress tests don't count)
- ✅ All 3: CTO/Safety Officer/Security Officer sign-offs received
- ✅ Evidence: 2,200+ decisions logged in AP2 ledger, ready for KARP/Series A due diligence
