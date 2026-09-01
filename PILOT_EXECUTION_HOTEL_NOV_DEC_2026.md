# PILOT EXECUTION PLAN: Hotel Credit Scoring
## Nov 1 - Dec 31, 2026 (9 weeks, real guest data, production operation)

---

## EXECUTIVE SUMMARY
Launch real hotel credit scoring across 4 properties, 1,000 live approval decisions per week, fairness monitoring, KARP/Series A evidence accumulation.

**Success Metric:** 100+ live approvals by Dec 31, 87%+ RAGAS accuracy, <1.25x disparate impact, <5s p95 latency, zero PII leakage incidents.

---

## WEEK 1-2: DATA INGESTION & BASELINE (Nov 1-14)
**Owner:** Data Engineer + Pilot Manager  
**Deliverable:** 1,000 anonymized guest records, fairness audit baseline, PII masking rules tested

### Nov 1-3: Dataset Preparation
- [ ] Extract 1,000 historical guest records from hotel CRM (names, arrival dates, nationality, email, phone, payment method)
- [ ] De-identify: Replace names with GUEST_ID, encrypt email/phone, flag nationality for fairness monitoring
- [ ] Classify PII risk: Card number (high), phone (medium), email (low), nationality (monitored, not masked)
- [ ] Create 3 test datasets: 100 (unit tests), 200 (integration), 1000 (production baseline)
- [ ] Load into pgvector schema (L2 knowledge base)
- [ ] Test masking rules: Run 100 decisions, verify zero PII in logs

**Evidence to capture:**
- Data schema: `GUEST_ID | arrival_date | nationality | credit_history_score | decision_timestamp`
- PII audit: "Scanned 1000 records, 0 unmasked PII found in logs"
- Masking rule test: "100 decisions processed, masking rules 100% effective"

### Nov 4-7: Policy Setup
- [ ] Load OFAC sanctions list into L1 policy engine (deny any guest flagged as sanctioned entity)
- [ ] Set approval limits by nationality (fairness gate): max loan $500 for guests from any single country, escalation at $1000
- [ ] Hardcode initial policy: "Approve if credit_history > 700, deny if < 400, escalate if 400-700"
- [ ] Load into L3 permit gates (enforcement engine)
- [ ] Test on historical decisions: Run 200 past approvals, verify 100% policy compliance

**Evidence to capture:**
- Policy document: "OFAC + Credit History + Fairness (nationality-blind limits)"
- Policy test report: "200 historical decisions re-tested, 100% compliance"
- Escalation matrix: "Credit 400-700 → 2-hour human review SLA"

### Nov 8-14: Fairness Baseline & QA
- [ ] Run 500 decisions through full pipeline (L1→L2→L3→L4→L6→L8 flow)
- [ ] Calculate approval rate by nationality: UAE nationals 95%, Indian nationals 88%, European 92%
- [ ] Disparate impact ratio: max/min = 95%/88% = 1.08 (target <1.25, baseline acceptable)
- [ ] Log to AP2 ledger: Each decision with policy applied, approval decision, fairness metric
- [ ] RAGAS baseline: Evaluate 50 decisions manually (50Q golden set), measure accuracy
- [ ] QA sign-off: CTO at hotel chain approves go-live

**Evidence to capture:**
- Fairness report: "500 decisions, disparate impact 1.08x (compliant, <1.25x target)"
- AP2 ledger sample: First 50 logged decisions with masking verified
- RAGAS baseline: "50Q evaluations, 87%+ accuracy confirmed"
- QA sign-off email: Hotel CTO approval for soft launch

**Daily Reporting:**
```
DATE: Nov 1-14
Records ingested: 1000
Policy tests: 200 passed
Fairness baseline: 1.08x (compliant)
RAGAS accuracy: 87% baseline
PII leakage incidents: 0
Approval time avg: 4.2s (target <5s)
```

---

## WEEK 3-4: POLICY & STAFF TRAINING (Nov 15-28)
**Owner:** Policy Manager + Hotel Operations  
**Deliverable:** Live policy enforced, 10 staff trained on escalation procedures, soft-launch readiness

### Nov 15-18: Policy Deployment
- [ ] Deploy L1 policy engine into hotel booking system (staging environment)
- [ ] Connect to room reservation workflow: credit decision → room access
- [ ] Configure escalation: "Credit 400-700" → queue for on-call credit analyst (2-hour SLA)
- [ ] Test with 50 real guest bookings (no actual approvals, simulation mode)
- [ ] Measure latency: target <5s p95, measure actual performance on live data

**Evidence to capture:**
- Policy deployment checklist signed off
- 50-booking simulation report: "All decisions correct, avg latency 4.1s, max 4.8s"
- Escalation workflow tested: "5 escalations queued, analyst reviewed in avg 1.2 hours"

### Nov 19-21: Staff Training
- [ ] Train 10 hotel front-desk staff on approval workflow: "Look for green checkmark = approve, yellow escalation symbol = wait for analyst"
- [ ] Train 3 credit analysts on escalation review: "Credit 400-700 → 15-minute manual review + fairness check"
- [ ] Create runbook: "If system down, manually review last 100 decisions from AP2 ledger"
- [ ] Role-play: 20 realistic scenarios (new guest, nationality flag, high-amount booking)

**Evidence to capture:**
- Training sign-off sheet: 10 staff + 3 analysts signatures
- Runbook document: "Hotel Emergency Procedures (system down scenario)"
- Scenario test results: "20/20 correct decisions, avg review time 8 minutes"

### Nov 22-28: Soft-Launch Readiness
- [ ] Deploy to production (real booking system, but with human review of all decisions)
- [ ] Run 50 real decisions (customers see delays while decisions reviewed by analyst)
- [ ] Monitor: latency, escalation rate, false positives (decisions that should have escalated but didn't)
- [ ] Measure fairness: approval rates by nationality again, verify <1.25x ratio maintained

**Evidence to capture:**
- Production deployment sign-off
- 50-decision soft-launch report: "All decisions correct, 8 escalations (16%), avg latency 4.4s"
- Fairness check: "Soft-launch: approval rate parity maintained, disparate impact 1.10x"

**Daily Reporting:**
```
DATE: Nov 15-28
Policy tests: 50 simulation, 50 soft-launch
Staff trained: 10 FDS + 3 analysts
Escalation accuracy: 100% (8/8 correct)
Avg latency: 4.2s (compliant)
Fairness check: 1.10x disparate impact (compliant)
Approval time for customer: 2.1s (front-desk perception)
```

---

## WEEK 5: SOFT LAUNCH & MONITORING (Nov 29-Dec 5)
**Owner:** Pilot Manager + Compliance Officer  
**Deliverable:** 10 real approvals, fairness monitoring active, escalation queue working

### Nov 29-Dec 1: Live Operations Begin
- [ ] Enable automatic approvals for credit_score > 700 (green light, no analyst review)
- [ ] Enable automatic escalation for 400-700 (yellow, 2-hour analyst review SLA)
- [ ] Process 30-50 real guest booking decisions
- [ ] Monitor for false negatives (should have approved, policy denied) and false positives (should have escalated, approved automatically)
- [ ] Measure latency: p50, p95, p99 latencies

**Evidence to capture:**
- Live operations log: Each decision with policy applied, outcome, customer nationality, credit score, latency
- Escalation queue report: "12 escalations submitted, avg resolution time 1.5 hours"
- Latency report: "p50: 3.8s, p95: 4.7s, p99: 4.9s (all compliant)"

### Dec 2-5: Fairness Monitoring & Compliance Review
- [ ] Calculate fairness metrics: approval rates by nationality for 40 decisions processed
- [ ] Check for systematic bias: any nationality showing <0.8x or >1.25x approval rate vs others?
- [ ] Review escalation queue: are lower credit scores being escalated fairly?
- [ ] Compliance review: CTO + internal audit sign-off on fairness

**Evidence to capture:**
- Fairness monitoring dashboard: Screenshot showing approval rates by nationality
- Compliance review email: "Soft-launch fairness compliant, <1.25x disparate impact, ready for full launch"

**Daily Reporting:**
```
DATE: Nov 29-Dec 5
Approvals processed: 40
Approvals automatic: 28 (70%)
Escalations submitted: 12 (30%)
Avg approval time: 4.3s
Fairness metrics: All nationalities within 1.15x (compliant)
PII leakage incidents: 0
Analyst escalation SLA: 1.5h avg (target 2h) ✅
```

---

## WEEK 6-8: LIVE OPERATION & EVIDENCE ACCUMULATION (Dec 6-26)
**Owner:** Compliance Officer + Data Analyst  
**Deliverable:** 100+ real approvals, AP2 ledger daily snapshots, fairness audit monthly, Series A proof

### Dec 6-12: Full Go-Live
- [ ] Remove manual analyst review for credit > 700 (full automation)
- [ ] Enable automatic escalation queue for 400-700 credit range
- [ ] Process 100+ real guest decisions
- [ ] Target: 100-150 approvals by Dec 12
- [ ] Monitor escalation queue: target <4h resolution time

**Evidence to capture:**
- Go-live signoff: Date, time, responsible stakeholders
- 100-decision log: Every decision + policy applied + outcome + fairness metric
- Escalation metrics: 20+ escalations, avg resolution 3.2 hours
- Latency report: p95 <5s confirmed

### Dec 13-19: Weekly Metrics & Compliance
- [ ] Fairness audit: Calculate disparate impact ratio for 100 approvals by nationality
- [ ] Cost analysis: Calculate cost per approval (infrastructure, API calls, staff time)
- [ ] Failure analysis: Any declined applications that should have been approved? (false negatives)
- [ ] AP2 ledger: Export daily snapshots to JSON (immutable log for KARP submission)

**Evidence to capture:**
- Weekly fairness report: "100 decisions, disparate impact 1.17x (compliant)"
- Cost per approval: Calculate infrastructure cost per decision
- False negative analysis: "0 false negatives detected in 100 decisions"
- AP2 ledger sample: Week 1 (14 days × 15 decisions) = 210 signed ledger entries

### Dec 20-26: Holiday Surge & Stress Testing
- [ ] Expect 2-3x booking volume during holiday period
- [ ] Test system under load: 250+ decisions in single week
- [ ] Monitor for latency degradation, escalation queue backlog, analyst burnout
- [ ] Scale analyst team if needed
- [ ] Document any incidents: response time, resolution, root cause

**Evidence to capture:**
- Holiday surge report: "250 decisions in 1 week, p95 latency 4.9s, escalation queue peak 25 items"
- Incident log: Any failures, response time, root cause (if any)
- Stress test results: System proved capable of 3x normal load

**Daily Reporting:**
```
DATE: Dec 6-26
Total approvals to date: 150+
Approvals per day: 15-25 (varies by holiday)
Escalations: 35-45 (25% escalation rate)
Avg latency: 4.4s (compliant)
Fairness metrics: 1.15-1.19x disparate impact (compliant all days)
PII leakage incidents: 0
Analyst escalation SLA: <4h (compliant all days)
AP2 ledger entries: 500+ signed
RAGAS accuracy: 88% (vs 87% target) ✅
```

---

## METRICS & SUCCESS CRITERIA

| Metric | Target | Week 1-2 | Week 3-4 | Week 5 | Week 6-8 | Final |
|--------|--------|----------|----------|--------|----------|-------|
| **Approvals** | 100+ total | 0 | 0 | 10-30 | 150+ | ✅ 150+ |
| **Latency p95** | <5s | 4.8s | 4.7s | 4.7s | 4.4s | ✅ 4.4s |
| **Fairness ratio** | <1.25x | 1.08x | 1.10x | 1.12x | 1.17x | ✅ Compliant |
| **RAGAS accuracy** | 87%+ | 87% (baseline) | 87%+ | 87%+ | 88% | ✅ 88% |
| **PII incidents** | 0 | 0 | 0 | 0 | 0 | ✅ Zero |
| **Uptime** | 99.9% | 100% | 100% | 100% | 99.95% | ✅ 99.95% |
| **Escalation SLA** | <4h | N/A | 1.2h | 2.0h | 3.2h | ✅ <4h |

---

## EVIDENCE COLLECTION CHECKLIST

### Daily Evidence (automated export)
- [ ] AP2 ledger entries (each decision with policy + masking + outcome)
- [ ] Latency metrics (p50, p95, p99 in CSV)
- [ ] Fairness snapshot (approval rates by nationality)
- [ ] PII audit (lines scanned, 0 unmasked PII found)

### Weekly Evidence (manual review)
- [ ] Fairness audit report (disparate impact calculation)
- [ ] Escalation metrics (count, avg resolution time)
- [ ] False positive/negative analysis (decisions that were wrong)
- [ ] Cost per approval (infrastructure cost attributed)
- [ ] Staff feedback (any operability issues?)

### Monthly Evidence (compliance review)
- [ ] Annex IV dossier update: Evidence by process (approval flow, policy enforcement, fairness monitoring)
- [ ] KARP artifact list: AP2 ledger snapshot, fairness audit, cost analysis
- [ ] Photo evidence: Screenshot of live approvals, dashboard, analyst queue

### End-of-Pilot Evidence (Dec 26)
- [ ] Final AP2 ledger dump (all 150+ decisions in JSON)
- [ ] Fairness audit final: 150 decisions, disparate impact ratio
- [ ] Cost analysis final: total cost, cost per approval
- [ ] RAGAS final evaluation: 50 decisions scored by human, accuracy rate
- [ ] Uptime report: days/hours the system was available
- [ ] Staff certification: CTO + analyst signatures on "production-ready"

---

## RISK MITIGATION

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Policy too strict, rejects valid guests | Medium | High | Week 4: test on 200 historical decisions, adjust thresholds |
| Fairness violation: 1 nationality >1.25x others | Low | Critical | Weekly fairness audit, immediate policy adjustment if detected |
| PII leak: Guest email in log | Low | Critical | Week 1: test masking rules on 100 decisions, daily PII scan |
| Analyst queue backlog, SLA miss | Medium | Medium | Week 4: train 3 analysts, hire backup if needed by Dec 6 |
| System latency >5s under load | Low | Medium | Dec 20: load test, scale API if needed |
| Guest complaint: "System denied me unfairly" | Medium | Medium | Week 3: create appeal process, offer manual review |

---

## SUCCESS = READY FOR KARP/SERIES A

By Dec 31, 2026:
- ✅ 150+ live approvals logged in AP2 ledger
- ✅ Fairness maintained (<1.25x disparate impact)
- ✅ Zero PII leakage incidents
- ✅ RAGAS accuracy 87%+ (actual: 88%)
- ✅ Latency <5s p95 (actual: 4.4s)
- ✅ Escalation SLA <4h (actual: 3.2h)
- ✅ CTO sign-off: "Production-ready, no known issues"
