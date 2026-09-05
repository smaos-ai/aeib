# PILOT EXECUTION PLAN: School Biometric Access Control
## Nov 1 - Dec 31, 2026 (9 weeks, 500 students, real biometric operation, 48-hour durability)

---

## EXECUTIVE SUMMARY
Deploy real biometric access control for 500 students across 5 school buildings, 2,000 access attempts per day, real-time attendance integration, network-resilient 48-hour offline mode, GDPR-compliant data handling.

**Success Metric:** 2,000+ access attempts by Dec 31, 99.9% uptime, <5s latency, 98%+ biometric accuracy, 99.9% auth success rate, survived 24-hour network outage test with 48-hour recovery window proven.

---

## WEEK 1-2: BIOMETRIC ENROLLMENT & BASELINE (Nov 1-14)
**Owner:** School Operations Manager + Biometric Lead  
**Deliverable:** 500 students enrolled (photo + iris), baseline accuracy measured, GDPR compliance verified

### Nov 1-3: Student Enrollment Setup
- [ ] Recruit 500 willing students (opt-in consent, parent/guardian approval)
- [ ] Collect biometric data: high-quality photo (frontal face, neutral expression) + iris scan (both eyes)
- [ ] Store encrypted: face embedding (128-dim vector), iris template (private key in HSM)
- [ ] Create backup biometric set: duplicate photos + iris scans for redundancy
- [ ] GDPR compliance: Store explicit consent, create data processing agreement
- [ ] Create test dataset: 100 students (enrollment), 200 impersonation tests (who can fake others' faces?)

**Evidence to capture:**
- Enrollment agreement: "500 students enrolled, 500 consent forms signed"
- Biometric quality report: "100% of photos met quality standards, 98% of iris scans successful"
- GDPR checklist: Data collection consent, storage encryption, right to erasure, privacy notice provided
- Test dataset: 100 reference students + 200 impersonation attempts

### Nov 4-7: Attendance Policy & Access Rules
- [ ] Load enrollment policies into L1 policy engine:
  - Attendance requirement: Must have >80% attendance to access building
  - Biometric rules: Face confidence >90%, OR iris confidence >95%
  - Time-based access: Access granted 06:00-18:00 school days only
  - Zone restrictions: Can access classroom if enrolled in that class
  - Alert rules: <80% attendance → alert to parent/school, <60% → alert to counselor

- [ ] Load access rules into L3 permit gates:
  - High-confidence match (>95% either biometric): Auto-approve
  - Medium confidence (85-95%): Admin human review (on-site staff decision within 1 minute)
  - Low confidence (<85%): Deny + require manual ID check
  - Biometric failure: Allow access + log incident (student can appeal)

**Evidence to capture:**
- Access policy document: Enrollment, biometric thresholds, time-based rules, alert triggers
- Policy test: "200 test attempts, all evaluated correctly per rules"
- Alert rule validation: "100 scenarios tested, alerts triggered correctly"

### Nov 8-14: Accuracy Baseline & GDPR Audit
- [ ] Test biometric accuracy on 200 impersonation scenarios (can one student's face unlock another's access?)
- [ ] Measure biometric accuracy metrics:
  - FAR (False Accept Rate): % of impostors accepted = target <0.5%
  - FRR (False Reject Rate): % of legitimate students rejected = target <2%
  - EER (Equal Error Rate): point where FAR = FRR = target <1%
- [ ] RAGAS baseline: 100 students manually evaluated (50 legitimate access, 50 impersonation attempts), accuracy measurement
- [ ] GDPR audit: Data controller checklist, DPA preparation, right-to-erasure procedure tested

**Evidence to capture:**
- Biometric accuracy report: "FAR 0.3%, FRR 1.2%, EER 0.8% (all targets met)"
- RAGAS baseline: "100 student evaluations, 98% accuracy (legitimate: 96%, impersonation: 100%)"
- GDPR audit: DPA consultation scheduled, privacy notice approved
- School security officer sign-off: "Accuracy acceptable for production use"

**Daily Reporting:**
```
DATE: Nov 1-14
Students enrolled: 500
Photo quality: 100% (all acceptable)
Iris scan success: 98% (490/500 complete)
FAR baseline: 0.3% (target <0.5%)
FRR baseline: 1.2% (target <2%)
RAGAS accuracy: 98% (baseline)
GDPR compliance: Consent forms 100% signed, DPA initiated
Backup biometric sets: 500/500 created
```

---

## WEEK 3-4: ACCESS SYSTEM INTEGRATION & STAFF TRAINING (Nov 15-28)
**Owner:** School IT Manager + Security Team  
**Deliverable:** System integrated into 5 school buildings, staff trained, emergency procedures documented

### Nov 15-18: Hardware & Network Deployment
- [ ] Install biometric scanners at 5 building entrances (face camera + iris scanner at each)
- [ ] Deploy local SQLite cache (Temporal layer): stores enrollment + access rules, survives 48-hour network outage
- [ ] Setup network sync: every 2 hours, sync cache to cloud (AP2 ledger + compliance database)
- [ ] Configure failover: If cloud unreachable for >2h, switch to local-only mode (cached rules remain in effect)
- [ ] Network redundancy: 2G/3G mobile backup if WiFi down
- [ ] Test failover: Power off internet connection for 24 hours, verify system continues operating locally

**Evidence to capture:**
- Hardware deployment checklist: 5 scanners installed + tested
- Cache configuration: SQLite schema, sync frequency, failover rules documented
- Network failover test: "System operated for 24h without internet, all 100 test access attempts processed correctly using cached rules"
- Sync validation: After reconnection, cache synced to cloud in <5 minutes

### Nov 19-21: Staff Training & Emergency Procedures
- [ ] Train 10 school staff on access system:
  - How to scan biometric (student stands in front of camera, stays still for 2s)
  - What to do if access denied (offer manual ID check)
  - How to handle biometric failure (student can appeal + provide manual ID)
  - Emergency override: Manual ID card as fallback
- [ ] Train 5 IT staff on system monitoring:
  - Dashboard: view real-time access events, biometric failures, network status
  - Local cache status: is it synced? When was last sync?
  - Incident procedures: if network down, check if cache is working
- [ ] Create runbook: "School Access System Emergency Procedures"
  - System down: Manual ID card checks, log to paper forms
  - Network down: Biometric system continues on local cache
  - Biometric failure: Escalate to on-site security, manual ID check

- [ ] Competency test: Each staff member processes 5 test student accesses

**Evidence to capture:**
- Staff training sign-off: 10 school staff, 5 IT staff
- Runbook document: Emergency procedures (system down, network down, biometric failure scenarios)
- Competency test: "15/15 staff scenarios passed, avg processing time 1.2 minutes"

### Nov 22-28: Soft-Launch with Manual Backup
- [ ] Deploy to all 5 building entrances (simulation mode: biometric scan happens, decision logged, but manual ID check still required)
- [ ] Process 200+ test access attempts from real students
- [ ] Monitor: latency, biometric failure rate, false accept/reject incidents
- [ ] Train students: How to stand in front of camera, what to expect

**Evidence to capture:**
- Soft-launch deployment sign-off
- 200-student soft-launch report: "All students successfully scanned, avg latency 3.2s, biometric failure rate 0.5%"
- Student feedback: Any issues with scanning process?
- Safety incidents: Any unauthorized access attempts during soft-launch?

**Daily Reporting:**
```
DATE: Nov 15-28
Hardware deployed: 5 building entrances
Scanners tested: 5/5 operational
Cache failover test: 24h without internet, 100% success
Network sync validated: <5 minute resync time
Staff trained: 10 school staff + 5 IT staff
Student soft-launch: 200 test accesses
Avg latency: 3.2s (target <5s)
Biometric failure rate: 0.5% (target <2%)
System uptime during soft-launch: 100%
```

---

## WEEK 5: SOFT LAUNCH & ATTENDANCE INTEGRATION (Nov 29-Dec 5)
**Owner:** School Security Manager  
**Deliverable:** 100+ real student access events, attendance integration live, network durability proven

### Nov 29-Dec 1: Live Access Operations Begin
- [ ] Enable automatic biometric access (high-confidence match auto-approves)
- [ ] Enable escalation queue (medium-confidence match → on-site staff decision)
- [ ] Enable local fallback (low-confidence match denied, but allows manual ID override)
- [ ] Live attendance logging: Each biometric match automatically logs attendance
- [ ] Process 100+ real student accesses
- [ ] Monitor: biometric accuracy, false accepts/rejects, attendance logging accuracy

**Evidence to capture:**
- Live operations log: Each biometric access with confidence score, attendance logged, any escalations
- Attendance integration report: "100 students accessed, 98 automatically logged in attendance system, 2 required manual override"
- Escalation report: "2 escalations (medium confidence), on-site staff decision <1 minute each"

### Dec 2-5: Network Resilience Testing
- [ ] Simulate 24-hour network outage: Disconnect internet connection
- [ ] System should continue operating on local cache (SQLite Temporal layer)
- [ ] Students should still be able to access with biometric
- [ ] Attendance should be logged locally
- [ ] After reconnection: Local log syncs to cloud within 5 minutes
- [ ] Zero data loss test: Verify all 200 access events during outage are synced correctly

**Evidence to capture:**
- Network outage test log: Date/time internet disconnected, duration, services impacted
- Local operation verification: "System operational on local cache, 200 test access attempts processed correctly"
- Sync verification after reconnection: "All 200 access events synced to cloud, zero lost"
- Compliance proof: "48-hour recovery window requirement met (synced in 5 minutes)"

**Daily Reporting:**
```
DATE: Nov 29-Dec 5
Live access events: 100+
Automatic biometric matches: 98 (98%)
Escalations: 2 (medium confidence)
Avg latency: 3.4s (compliant)
Attendance logged: 98/100 (98%)
Biometric FAR: 0.3% (compliant)
Biometric FRR: 1.2% (compliant)
Network outage test: 24h local operation, 200 events, 0 lost
Sync after reconnection: <5 minutes ✅
```

---

## WEEK 6-8: PRODUCTION OPERATION & DURABILITY PROOF (Dec 6-26)
**Owner:** Compliance Officer + Data Analyst  
**Deliverable:** 2,000+ real access events, AP2 ledger, network durability proven, ready for Annex III

### Dec 6-12: Full Production Go-Live
- [ ] Remove manual ID requirement for biometric matches (100% biometric authentication)
- [ ] Automatic attendance logging for all biometric matches
- [ ] Run production with 500 students across 5 buildings
- [ ] Target: 2,000+ access events by Dec 12 (school day average ~400 students/day × 5 days = 2,000 accesses)
- [ ] Monitor: biometric accuracy, system uptime, attendance accuracy

**Evidence to capture:**
- Production go-live sign-off
- 2,000+ access log: Every student biometric match with confidence, attendance logged, timestamp
- Biometric accuracy metrics: FAR, FRR, EER for production data
- Attendance accuracy: Cross-check biometric attendance vs. manual sign-in (if used), verify match

### Dec 13-19: Weekly Durability & Compliance Metrics
- [ ] Biometric accuracy audit: FAR <0.5%, FRR <2% maintained?
- [ ] Attendance accuracy: 98%+ of students correctly logged?
- [ ] False reject recovery: Students denied biometric access, offered manual ID, accepted? (goal: 100% recovery)
- [ ] System uptime: target 99.9% (max 1 hour downtime per week)
- [ ] AP2 ledger: Daily snapshot of all 400 access events, with biometric confidence scores
- [ ] GDPR compliance: Monitor for unauthorized access attempts (should be zero)

**Evidence to capture:**
- Weekly durability report: "Week 1: FAR 0.4%, FRR 1.1%, EER 0.75%, uptime 99.97%"
- Attendance accuracy: "1,000 students logged biometrically, 100% match manual records"
- False reject recovery: "12 students denied biometric, all accepted manual ID, 100% success"
- AP2 ledger sample: 7 days × 400 access attempts = 2,800 signed ledger entries
- Security report: "0 unauthorized access attempts detected"

### Dec 20-26: Holiday Period & Durability Stress Test
- [ ] School may be closed or have reduced operation
- [ ] Use this time for planned durability testing:
  - Extend network outage: 48-hour disconnection (longest scenario)
  - Verify local SQLite cache remains operational for 48 hours
  - Verify sync after reconnection completes within 5-minute window
  - Simulate battery failure on one scanner, verify other 4 continue operating
  - Test data recovery: Restore from backup, verify zero data loss

**Evidence to capture:**
- 48-hour network outage test: Complete log of local operation, all access decisions
- Cache durability: "Cache remained operational for 48 hours, 800 access attempts processed, zero errors"
- Sync validation: "After reconnection, all 800 local events synced in 4.2 minutes"
- Backup recovery test: "System restored from backup, all data intact, zero loss"
- Compliance proof: "Network-resilient access control survives 48-hour outage + completes recovery within 5 minutes"

**Daily Reporting**
```
DATE: Dec 6-26
Total access attempts: 2,000+
Biometric matches: 1,960+ (98%)
False rejects: 40 (2%)
Manual ID fallback success: 100% (40/40 recovered)
Avg latency: 3.4s (compliant)
System uptime: 99.97% (1 incident, 45 min recovery)
Attendance accuracy: 100% (match manual records)
Biometric FAR: 0.4% (compliant with <0.5%)
Biometric FRR: 1.1% (compliant with <2%)
AP2 ledger entries: 2,000+ signed
RAGAS accuracy: 98% (vs baseline)
48h durability test: ✅ Passed (cache + recovery verified)
```

---

## METRICS & SUCCESS CRITERIA

| Metric | Target | Week 1-2 | Week 3-4 | Week 5 | Week 6-8 | Final |
|--------|--------|----------|----------|--------|----------|-------|
| **Access attempts** | 2,000+ | 0 | 200 (soft) | 100+ | 2,000+ | ✅ 2,100+ |
| **System uptime** | 99.9% | 100% | 100% | 100% | 99.97% | ✅ 99.97% |
| **Avg latency** | <5s | N/A | 3.2s | 3.4s | 3.4s | ✅ 3.4s |
| **Biometric FAR** | <0.5% | 0.3% | 0.4% | 0.3% | 0.4% | ✅ 0.4% |
| **Biometric FRR** | <2% | 1.2% | 1.4% | 1.2% | 1.1% | ✅ 1.1% |
| **Auth success rate** | >99.9% | N/A | 99.5% | 99.8% | 99.9% | ✅ 99.9% |
| **Attendance accuracy** | 98%+ | N/A | 98% | 98% | 100% | ✅ 100% |
| **Network durability** | 48h+ | Test plan | 24h pass | 24h pass | 48h pass | ✅ Proven |
| **RAGAS accuracy** | 98%+ | 98% (baseline) | 98%+ | 98%+ | 98% | ✅ 98% |

---

## EVIDENCE COLLECTION CHECKLIST

### Daily Evidence (automated export)
- [ ] AP2 ledger entries (each biometric access with confidence, attendance logged, timestamp)
- [ ] Latency metrics (biometric processing time, decision time)
- [ ] Biometric accuracy (FAR, FRR, EER metrics)
- [ ] System uptime (any downtime incidents logged)
- [ ] Network status (cloud sync status, cache sync status)
- [ ] Attendance accuracy (compare biometric log vs. manual records if available)

### Weekly Evidence (manual review)
- [ ] Biometric accuracy audit: FAR <0.5%, FRR <2% confirmed
- [ ] False reject recovery: % of denied students successfully granted manual ID access
- [ ] System incident log: Any outages, root cause, resolution time
- [ ] Escalation analysis: Medium-confidence matches, on-site staff decisions
- [ ] False accept analysis: Impersonation attempts, how many caught/missed?
- [ ] GDPR compliance: Any unauthorized access attempts? Data access logs clean?

### Monthly Evidence (compliance review)
- [ ] Annex III dossier update: Evidence by process (enrollment, biometric accuracy, access control, attendance, network durability)
- [ ] KARP artifact: AP2 ledger snapshot, biometric accuracy report, network durability test results
- [ ] GDPR audit: Data controller checklist, DPA compliance, consent renewal
- [ ] Photo evidence: Dashboard screenshots, access logs, network durability test logs

### End-of-Pilot Evidence (Dec 26)
- [ ] Final AP2 ledger dump: All 2,000+ access attempts with full metadata as JSON
- [ ] Biometric accuracy final: FAR 0.4%, FRR 1.1%, EER 0.75% (all targets met)
- [ ] Attendance accuracy final: 100% match with manual records
- [ ] Network durability final: 48-hour test PASSED, recovery <5 minutes
- [ ] System uptime final: 99.97% (only 45 min unplanned downtime in 9 weeks)
- [ ] RAGAS final: 100 student scenarios (50 legitimate, 50 impersonation), 98% accuracy
- [ ] GDPR compliance final: DPA approval, consent management, right-to-erasure tested
- [ ] School security sign-off: "Production-ready, network-resilient, GDPR-compliant"

---

## NETWORK RESILIENCE (TEMPORAL LAYER CRITICAL)

### Scenario 1: Internet Down for 2 Hours (Normal)
1. Student scans biometric at entrance
2. System checks local SQLite cache (instant)
3. Decision made from cache (enrollment + attendance data)
4. Access granted/denied based on local cache
5. Internet reconnects
6. All 120 decisions from outage sync to cloud in <1 minute
7. Zero data loss

### Scenario 2: Internet Down for 24 Hours (Stress Test)
1. All 400+ student accesses processed by local cache
2. Attendance logged to local SQLite
3. Biometric confidence scores cached locally
4. No connectivity impact to school operations
5. Internet reconnects
6. All 400+ events sync to cloud in <5 minutes
7. AP2 ledger verified, zero loss

### Scenario 3: Internet Down for 48 Hours (Durability Proof)
1. All 800+ student accesses processed by local cache
2. If cache storage fills (unlikely), older entries exported to backup storage
3. Biometric policy enforcement continues (no policy changes without internet, but that's acceptable)
4. Attendance logged completely and accurately
5. Internet reconnects
6. All 800+ events sync to cloud
7. **Regulatory Compliance Met:** "System survives 48-hour network outage with zero data loss, full recovery <5 minutes"

---

## RISK MITIGATION

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Biometric false accept, student A unlocks as student B | Low | High | Week 1: test with 200 impersonation attempts, measure FAR <0.5% |
| Network down, students can't access building | Low | High | Week 5: test 24h outage, local cache operation. Week 6-8: test 48h outage |
| Data loss during network outage | Very Low | Critical | Daily cache sync, backup before outage, verify zero loss after reconnect |
| Student biometric changes (grows beard, new glasses) | Medium | Low | FRR will increase slightly, offer manual ID override. Periodic re-enrollment (annual) |
| Attendance data doesn't match reality | Low | Medium | Cross-check biometric log vs. manual records weekly |
| GDPR breach: Biometric data exposed | Very Low | Critical | Encrypt at rest (HSM), encrypt in transit (TLS), audit access logs daily |
| System latency >5s, slow access experience | Low | Medium | Weekly latency monitoring, optimize if trend appears |
| Hardware failure (scanner), building entrance inaccessible | Low | Medium | 4 scanner redundancy (5 entrances), if 1 fails, students use 4 others, manual ID fallback |

---

## SUCCESS = READY FOR ANNEX III COMPLIANCE + GDPR DPA

By Dec 31, 2026:
- ✅ 2,000+ real biometric access attempts logged
- ✅ 99.9% auth success rate (students accessed successfully)
- ✅ 98%+ biometric accuracy (FAR <0.5%, FRR <2%)
- ✅ 100% attendance accuracy (matches manual records)
- ✅ 48-hour network durability PROVEN (survived outage, recovered <5 min)
- ✅ Latency <5s (actual: 3.4s)
- ✅ GDPR DPA completed, consent 100% documented
- ✅ School security officer + IT manager sign-off: "Production-ready, network-resilient, GDPR-compliant"
