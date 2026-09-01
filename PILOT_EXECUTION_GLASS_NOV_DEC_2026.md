# PILOT EXECUTION PLAN: Glass Factory CAD Safety Review
## Nov 1 - Dec 31, 2026 (9 weeks, real manufacturing, 50+ designs reviewed)

---

## EXECUTIVE SUMMARY
Deploy AI-assisted CAD design safety review for automotive glass manufacturer, 50+ real designs by Dec 31, 99.5%+ false negative rate (<0.5% designs pass system but fail in production), 90%+ RAGAS accuracy.

**Success Metric:** 50+ designs reviewed, zero false negatives (no design passes system then fails in production), <1s latency per design, 95%+ precision, cost <€1 per design review.

---

## WEEK 1-2: CAD SCHEMA & SAFETY RULES (Nov 1-14)
**Owner:** Engineering Manager + Safety Lead  
**Deliverable:** 500 historical designs ingested, 14 safety checks automated, baseline accuracy measured

### Nov 1-3: CAD Dataset Preparation
- [ ] Extract 500 historical automotive glass designs from CAD system (2-year archive)
- [ ] Parse STL/STEP formats: material type, thickness, curvature, lamination layer, tempering spec
- [ ] Create anonymized dataset: replace design names with DESIGN_ID, strip customer IP
- [ ] Classify safety criticality: windshield (critical), side window (medium), interior light (low)
- [ ] Load into pgvector schema: vector embedding of design parameters
- [ ] Split: 100 (unit tests), 200 (integration), 500 (production baseline)

**Evidence to capture:**
- CAD schema: `DESIGN_ID | product_type | material | thickness_mm | curvature_radius | lamination_layers | tempering_temp | production_date`
- Anonymization report: "500 designs de-identified, zero IP in dataset"
- Criticality classification: "150 windshields (critical), 200 side windows (medium), 150 interior (low)"

### Nov 4-7: Safety Rule Automation
- [ ] Define 14 automated safety checks:
  1. Thickness within spec (windshield 4-5mm, tolerance ±0.2mm)
  2. Curvature radius within design limits
  3. Lamination layer count correct (windshield ≥2 layers)
  4. Tempering temperature within range (650-750°C)
  5. Surface defects <1mm (no visible cracks in scan)
  6. Edge finish smooth (no sharp edges, potential break points)
  7. Coating uniformity within spec
  8. Optical clarity (light transmission >89%)
  9. Material type matches intended application
  10. No delamination detected (ultrasonic check)
  11. Stress concentration factor <3.0
  12. Environmental resistance (salt spray test simulation)
  13. Impact resistance grade met (e.g., ANSI Z26.1)
  14. Dimensional accuracy (±0.5mm tolerance)

- [ ] Load checks into L3 permit gates (enforcement engine)
- [ ] Test on 200 historical designs: verify 100% check execution

**Evidence to capture:**
- Safety rules document: 14 checks with technical specs + tolerances
- Check execution test: "200 designs, all 14 checks executed, zero failures"
- Rule precision: "200 designs re-checked by human expert, agreement 98%"

### Nov 8-14: False Negative Baseline & Accuracy Measurement
- [ ] Run 500 historical designs through system
- [ ] Identify 10 designs that failed in production (real manufacturing failures)
- [ ] Verify system would have caught them: 10/10 flagged by safety checks (0% false negative rate on historical data)
- [ ] Calculate precision: # of designs flagged / # actually risky
- [ ] RAGAS baseline: Use golden set of 50 designs (25 safe, 25 risky), measure accuracy

**Evidence to capture:**
- False negative analysis: "500 historical designs tested, 10 known failures, 10/10 caught by system (0% false negative rate)"
- Precision baseline: "System flagged 45/500 designs, 40 confirmed risky = 89% precision"
- RAGAS baseline: "50 expert-reviewed designs, system accuracy 90%"
- Safety lead sign-off: "System accurate enough for production use"

**Daily Reporting:**
```
DATE: Nov 1-14
CAD designs ingested: 500
Safety checks automated: 14
False negative rate: 0% (0/10 known failures missed)
Precision: 89% (40/45 risky flags confirmed)
RAGAS accuracy: 90% (50Q baseline)
System latency: 850ms avg per design (target <1s)
```

---

## WEEK 3-4: MANUFACTURING INTEGRATION & VALIDATION (Nov 15-28)
**Owner:** Manufacturing Engineering + Quality Assurance  
**Deliverable:** System integrated into design approval workflow, 20 test designs reviewed, zero escalation delays

### Nov 15-18: Manufacturing Workflow Integration
- [ ] Connect system to CAD design approval workflow (pre-production gate)
- [ ] Configuration: Design uploaded → system analyzes → decision in <1s → results to engineer queue
- [ ] Setup escalation: "Risk confidence <70%" → queue for senior safety engineer (2-hour SLA)
- [ ] Test integration on 20 designs (no actual approvals yet, simulation)
- [ ] Measure latency: target <1s per design

**Evidence to capture:**
- Workflow integration checklist signed
- 20-design simulation: "All analyzed in <1s, avg 850ms, max 980ms"
- Escalation workflow: "3 escalations queued, senior engineer reviewed in avg 1.1 hours"

### Nov 19-21: QA & Safety Engineer Training
- [ ] Train 5 safety engineers on system workflow: "Green light = approve, yellow flag = review for <2 hours, red = reject immediately"
- [ ] Create runbook: "If system down, fall back to manual safety check (full CAD review, 8-hour turnaround)"
- [ ] Role-play scenarios: 15 realistic designs (edge cases, unusual materials, new curvature)
- [ ] Competency validation: Each engineer signs off on 5 test scenarios

**Evidence to capture:**
- Training sign-off: 5 safety engineers + QA manager
- Runbook: "Glass Design Emergency Procedures (system failure scenario)"
- Scenario test results: "15/15 correct decisions, avg review time 12 minutes"

### Nov 22-28: Soft-Launch Validation
- [ ] Deploy to production (real design submissions, but with human review of all recommendations)
- [ ] Process 20 real customer designs
- [ ] Monitor: accuracy (system agrees with human expert), false positives (safe design flagged as risky), false negatives (risky design approved)
- [ ] Measure performance: latency, escalation rate

**Evidence to capture:**
- Soft-launch deployment sign-off
- 20-design validation report: "All decisions correct, 0 false positives, 0 false negatives, avg latency 870ms"
- Safety engineer feedback: Any issues with workflow, confidence in system?

**Daily Reporting:**
```
DATE: Nov 15-28
CAD designs tested: 20 (soft-launch)
System accuracy: 100% (20/20 correct decisions)
False positive rate: 0% (0/20 safe designs wrongly flagged)
False negative rate: 0% (0/20 risky designs approved)
Escalations: 4/20 (20% escalation rate)
Avg latency: 870ms (compliant with <1s target)
Senior engineer SLA: 1.1h avg (compliant with 2h target)
```

---

## WEEK 5: SOFT LAUNCH & PERFORMANCE MONITORING (Nov 29-Dec 5)
**Owner:** Quality Assurance Lead  
**Deliverable:** 20+ real designs, performance baseline, ready for full automation

### Nov 29-Dec 1: Live Review Operations Begin
- [ ] Enable automatic safe approvals (high-confidence safe designs, engineer sign-off optional)
- [ ] Enable automatic escalation for uncertain designs (confidence 70-85%)
- [ ] Enable automatic rejection for risky designs (confidence >95% for safety issue)
- [ ] Process 25-35 real customer designs
- [ ] Monitor for false positives/negatives

**Evidence to capture:**
- Live operations log: Each design with safety check results, confidence scores, approval decision
- Escalation report: "8 escalations, avg resolution 1.5 hours"
- Performance metrics: latency, false positive/negative rate

### Dec 2-5: Safety Compliance Review
- [ ] Check if any approved designs later failed in production (false negatives during soft-launch)
- [ ] Safety lead review: Are safety checks catching all known risky patterns?
- [ ] Quality review: Cost per design, engineer time per review
- [ ] Sign-off: Senior safety engineer + QA manager approve full automation

**Evidence to capture:**
- Design review report: "25 designs approved, 0 failed in production during soft-launch"
- Cost analysis: Avg cost per design (labor + infrastructure)
- Safety sign-off: Email approval for full automation

**Daily Reporting:**
```
DATE: Nov 29-Dec 5
Designs processed: 30
Automatic approvals: 22 (73%)
Escalations submitted: 8 (27%)
Avg processing time: 850ms
False positive rate: 0%
False negative rate: 0% (no approved designs failed in production)
Senior engineer escalation SLA: 1.5h (compliant)
```

---

## WEEK 6-8: PRODUCTION OPERATION & EVIDENCE ACCUMULATION (Dec 6-26)
**Owner:** QA Lead + Data Analyst  
**Deliverable:** 50+ real designs reviewed, zero false negatives, AP2 ledger, cost analysis

### Dec 6-12: Full Production Go-Live
- [ ] Remove manual review requirement for automatic approvals (100% automated for high-confidence safe designs)
- [ ] Full escalation workflow for 70-85% confidence designs
- [ ] Automatic rejection for >95% risky designs (with engineer optional override)
- [ ] Process 100+ customer designs through system
- [ ] Target: 50+ designs approved by Dec 12
- [ ] Monitor for false negatives: any approved designs fail in production? (critical metric)

**Evidence to capture:**
- Production go-live sign-off
- 50+ design log: Every design analyzed, safety checks results, confidence, approval decision
- Escalation metrics: count, avg resolution time, engineer satisfaction
- False negative tracking: Zero approved designs should fail in production

### Dec 13-19: Weekly Safety & Cost Metrics
- [ ] False negative audit: Follow up on 30 designs approved last week, any production failures? (target 0)
- [ ] Precision analysis: Calculate PPV (positive predictive value) = # risky flags / # actually risky
- [ ] Cost per design: Track labor time, API costs, infrastructure
- [ ] Escalation effectiveness: # of escalated designs that were actually risky? (should be 100%)
- [ ] AP2 ledger: Export daily snapshots of all design decisions

**Evidence to capture:**
- Weekly safety report: "50 designs approved, 0 failed in production (0% false negative rate)"
- Precision metrics: "System flagged 8 designs as risky, 8 confirmed risky = 100% precision (week)"
- Cost analysis: Cost per design approval (target <€1)
- AP2 ledger sample: Week 1 (50 designs × all metadata) as JSON

### Dec 20-26: Year-End Volume & Stress Testing
- [ ] Expect peak design submission volume (year-end product launches)
- [ ] Test throughput: 50+ designs in single week
- [ ] Monitor system performance: latency degradation under load?
- [ ] Escalation queue: Any backlog of escalations waiting for engineer review?
- [ ] Incident log: Any system failures, false positives, false negatives?

**Evidence to capture:**
- Year-end surge report: "50+ designs in 1 week, avg latency 850ms, peak 960ms"
- Incident log: Any failures, how resolved, root cause
- Stress test: System proved capable of handling peak load

**Daily Reporting:**
```
DATE: Dec 6-26
Total designs reviewed: 50+
Designs per day: 7-9 (varies by submissions)
Automatic approvals: 35-40 (70-80%)
Escalations: 10-15 (20-30%)
Avg processing time: 850ms (compliant)
False negative rate: 0% (all approved designs passed production)
Precision: 100% (all flagged designs were risky)
Cost per design: €0.85 (compliant with <€1 target)
AP2 ledger entries: 500+ signed
RAGAS accuracy: 91% (vs 90% baseline)
```

---

## METRICS & SUCCESS CRITERIA

| Metric | Target | Week 1-2 | Week 3-4 | Week 5 | Week 6-8 | Final |
|--------|--------|----------|----------|--------|----------|-------|
| **Designs reviewed** | 50+ | 0 | 20 | 30 | 50+ | ✅ 50+ |
| **False negative rate** | 0% | 0% | 0% | 0% | 0% | ✅ 0% |
| **Precision** | 95%+ | 89% | 95% | 100% | 100% | ✅ 100% |
| **Latency avg** | <1s | 850ms | 870ms | 850ms | 850ms | ✅ 850ms |
| **Escalation SLA** | <2h | N/A | 1.1h | 1.5h | 1.8h | ✅ <2h |
| **Cost per design** | <€1 | N/A | €0.95 | €0.90 | €0.85 | ✅ €0.85 |
| **RAGAS accuracy** | 90%+ | 90% (baseline) | 90%+ | 90%+ | 91% | ✅ 91% |

---

## EVIDENCE COLLECTION CHECKLIST

### Daily Evidence (automated export)
- [ ] AP2 ledger entries (each design + safety checks + confidence + decision)
- [ ] Latency metrics (design processing time in milliseconds)
- [ ] Decision tracking (approved, escalated, rejected counts)
- [ ] Cost metrics (infrastructure cost attributed to each design)

### Weekly Evidence (manual review)
- [ ] False negative audit: Any approved designs fail in production? (TARGET: 0)
- [ ] Precision analysis: # risky flags / # actually risky
- [ ] Escalation metrics: count, avg resolution time, engineer feedback
- [ ] Cost per design calculation (labor + infrastructure)
- [ ] Incident log: Any system failures, how resolved

### Monthly Evidence (compliance review)
- [ ] Annex I dossier update: Evidence by process (design analysis, safety checking, false negative tracking)
- [ ] KARP artifact: AP2 ledger snapshot, precision metrics, cost analysis
- [ ] Photo evidence: Screenshots of dashboard, escalation queue, engineer interface

### End-of-Pilot Evidence (Dec 26)
- [ ] Final AP2 ledger dump: All 50+ designs with full metadata as JSON
- [ ] False negative audit final: Confirmation that 0 approved designs failed in production
- [ ] Precision final: All flagged designs were actually risky
- [ ] Cost analysis final: Total cost, cost per design
- [ ] RAGAS final: 50 expert-reviewed designs, accuracy 90%+
- [ ] Safety sign-off: Senior engineer signature on "production-ready, zero false negatives observed"

---

## RISK MITIGATION

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Safety check misses risky design (false negative) | Low | Critical | Week 1: test on 10 known failures, verify all caught. Weekly false negative audit |
| Check too sensitive, flags safe design as risky (false positive) | Medium | Medium | Week 3: manual review, adjust thresholds if >10% false positive rate |
| Escalation SLA missed, engineer queue backlog | Low | Medium | Week 4: hire 2nd safety engineer if needed, track escalation time daily |
| System latency >1s under peak load | Low | Medium | Dec 20: load test, optimize if needed |
| Cost per design >€1 | Low | Low | Track costs daily, optimize API calls if trend appears |
| Production design fails despite system approval (false negative in production) | Very Low | Critical | This is THE metric. If happens even once, halt pilot and investigate immediately |

---

## POST-PRODUCTION FALSE NEGATIVE PROTOCOL (CRITICAL)

If ANY approved design fails in production test:
1. **Immediate:** Halt all automatic approvals, switch to manual review for 48 hours
2. **Investigation:** Analyze design parameters, check which safety check should have caught it
3. **Fix:** Adjust safety rule or add new check to catch this pattern
4. **Validation:** Re-test on 20 designs to ensure fix works and doesn't introduce false positives
5. **Resume:** Return to automatic approval once root cause fixed and validated
6. **Report:** Document incident, fix, and validation in AP2 ledger as evidence of rapid response

---

## SUCCESS = READY FOR ANNEX I COMPLIANCE

By Dec 31, 2026:
- ✅ 50+ designs reviewed
- ✅ 0% false negative rate (no approved design failed in production)
- ✅ 100% precision (all flagged designs were risky)
- ✅ Latency <1s (actual: 850ms)
- ✅ Cost <€1 per design (actual: €0.85)
- ✅ RAGAS accuracy 90%+ (actual: 91%)
- ✅ Safety engineer sign-off: "Ready for full production, no known safety gaps"
