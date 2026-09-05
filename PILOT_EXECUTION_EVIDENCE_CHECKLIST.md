# EVIDENCE COLLECTION CHECKLIST
## Daily, Weekly, Monthly, and End-of-Pilot (Nov 1 - Dec 31, 2026)

---

## EXECUTIVE SUMMARY
Automated + manual evidence collection for KARP submission (Sep 2026) and Series A due diligence (ongoing). Every decision logged in AP2 ledger, signed cryptographically, exportable for regulatory audit.

**Storage:** `/EVIDENCE/` directory, weekly JSON dumps, monthly compliance reviews, end-of-pilot comprehensive archive.

**Access Control:** Pilot Manager (read/write), CTO (read), Finance (read cost analysis), Compliance Officer (read).

---

## DAILY EVIDENCE (AUTOMATED, 11:59 PM CET)

### FORMAT: CSV EXPORTS (All Pilots)

**HOTEL_DAILY.csv (Nov 1-Dec 31)**
```
date,approvals_count,escalations_count,auto_approvals,manual_overrides,
avg_latency_ms,p95_latency_ms,approval_rate_pct,disparate_impact_ratio,
ragas_accuracy_pct,pii_incidents,uptime_pct,notes
2026-11-01,0,0,0,0,N/A,N/A,N/A,1.08,87,0,100,baseline_setup
2026-11-05,8,2,6,0,4200,4800,100,1.10,87,0,100,policy_testing
2026-12-06,15,3,12,0,4400,4700,95,1.15,88,0,99.9,production_go_live
2026-12-26,250,60,200,10,4400,4700,94,1.17,88,0,99.95,holiday_surge
```

**GLASS_DAILY.csv (Nov 1-Dec 31)**
```
date,designs_reviewed,designs_flagged_risky,designs_approved,escalations,
false_negative_count,false_positive_count,avg_latency_ms,
precision_pct,cost_per_design_eur,incidents,notes
2026-11-01,0,0,0,0,0,0,N/A,89,N/A,0,baseline_setup
2026-11-15,0,0,0,0,0,0,N/A,95,N/A,0,integration_test
2026-12-06,8,1,7,0,0,0,850,100,0.95,0,production_go_live
2026-12-26,50,10,40,0,0,0,850,100,0.85,0,year_end_volume
```

**SCHOOL_DAILY.csv (Nov 1-Dec 31)**
```
date,access_attempts,biometric_matches,biometric_failures,manual_overrides,
far_pct,frr_pct,avg_latency_ms,auth_success_rate_pct,attendance_accuracy_pct,
uptime_pct,network_incidents,cache_sync_status,notes
2026-11-01,0,0,0,0,0.3,1.2,N/A,N/A,N/A,100,0,N/A,enrollment_setup
2026-11-15,0,0,0,0,0.3,1.4,3200,N/A,N/A,100,0,N/A,hardware_test
2026-12-06,400,392,8,8,0.4,1.1,3400,99.9,100,99.9,0,synced,production_go_live
2026-12-26,2100,2058,42,42,0.4,1.1,3400,99.95,100,99.97,0,synced,holiday_operation
```

**Automated Export Schedule:**
- Hotel: 11:45 PM CET (end of business)
- Glass: 11:50 PM CET
- School: 11:55 PM CET
- Backup: Cloud sync every 2 hours (Temporal cache)

### DAILY CHECKLIST (PILOT MANAGER, 9:15 AM CET NEXT DAY)
- [ ] Hotel CSV received (approvals count, latency, fairness)
- [ ] Glass CSV received (designs count, false negatives, precision)
- [ ] School CSV received (access attempts, biometric metrics, uptime)
- [ ] Any incidents? (PII leak, false negative, downtime)
- [ ] Any values outside target range?
  - [ ] Hotel latency <5s? Fairness <1.25x?
  - [ ] Glass false negative = 0? Precision >95%?
  - [ ] School uptime 99.9%? FAR <0.5%, FRR <2%?
- [ ] If any issue: Escalate to Pilot Manager immediately (P1 protocol)

---

## AP2 LEDGER DAILY SNAPSHOT

**FORMAT:** JSON (immutable, signed with Ed25519)

**HOTEL_AP2_[DATE].json**
```json
{
  "date": "2026-12-06",
  "pilot": "hotel",
  "total_decisions": 15,
  "decisions": [
    {
      "decision_id": "HOTEL_20261206_001",
      "timestamp": "2026-12-06T08:30:45Z",
      "guest_id": "GUEST_12345",
      "nationality": "AE",
      "credit_score": 750,
      "ofac_check": "PASS",
      "policy_applied": "APPROVE_IF_CREDIT>700",
      "decision": "APPROVE",
      "approval_amount_usd": 500,
      "latency_ms": 4300,
      "ragas_score": 0.95,
      "fair_neutral_check": "PASS",
      "escalation": false,
      "pii_masked": true,
      "ed25519_signature": "ed25519_sig_[64_hex_chars]",
      "kms_key_id": "ap2-hotel-2026-sep"
    },
    ...
  ],
  "batch_ed25519_root": "merkle_root_hash",
  "timestamp_authority": "ECB_TSA_2026",
  "compression": "gzip"
}
```

**GLASS_AP2_[DATE].json**
```json
{
  "date": "2026-12-06",
  "pilot": "glass",
  "total_reviews": 8,
  "reviews": [
    {
      "design_id": "GLASS_20261206_001",
      "timestamp": "2026-12-06T09:15:20Z",
      "product_type": "windshield_automotive",
      "material": "tempered_laminated",
      "thickness_mm": 4.8,
      "curvature_radius_mm": 1200,
      "lamination_layers": 2,
      "checks_executed": 14,
      "checks_passed": 14,
      "safety_confidence": 0.98,
      "decision": "APPROVE",
      "latency_ms": 850,
      "ragas_score": 0.92,
      "escalation": false,
      "cost_eur": 0.85,
      "ed25519_signature": "ed25519_sig_[64_hex_chars]",
      "kms_key_id": "ap2-glass-2026-sep"
    },
    ...
  ],
  "batch_ed25519_root": "merkle_root_hash",
  "timestamp_authority": "NANDO_TSA_2026",
  "compression": "gzip"
}
```

**SCHOOL_AP2_[DATE].json**
```json
{
  "date": "2026-12-06",
  "pilot": "school",
  "total_attempts": 400,
  "attempts": [
    {
      "access_id": "SCHOOL_20261206_001",
      "timestamp": "2026-12-06T06:45:30Z",
      "student_id": "STUDENT_001",
      "biometric_type": "face+iris",
      "face_confidence": 0.97,
      "iris_confidence": 0.99,
      "combined_confidence": 0.98,
      "attendance_record": "enrolled_2026-09-01",
      "attendance_percentage": 92,
      "expected_location": "classroom_5B",
      "policy_check": "PASS",
      "decision": "APPROVE_ACCESS",
      "decision_latency_ms": 3400,
      "ragas_score": 0.98,
      "cache_sync_status": "synced",
      "network_status": "online",
      "ed25519_signature": "ed25519_sig_[64_hex_chars]",
      "kms_key_id": "ap2-school-2026-sep"
    },
    ...
  ],
  "batch_ed25519_root": "merkle_root_hash",
  "timestamp_authority": "DPA_TSA_2026",
  "cache_hit_rate": 0.99,
  "sync_latency_ms": 120,
  "compression": "gzip"
}
```

**Daily AP2 Export Schedule:**
- Hotel: 12:01 AM CET (automated)
- Glass: 12:02 AM CET (automated)
- School: 12:03 AM CET (automated)
- Cloud backup: 2 hours, with Ed25519 batch root merkle commitment to Git

**AP2 Verification (Weekly):**
- [ ] All daily JSON files signed + verified
- [ ] Batch merkle roots committed to public Git repo
- [ ] No gaps in decision IDs (no missing records)
- [ ] Timestamps monotonically increasing
- [ ] RAGAS scores tracked (all entries have accuracy metric)

---

## WEEKLY EVIDENCE SUMMARY (FRIDAYS 5:00 PM CET)

**EXPORT FORMAT:** Single `/EVIDENCE/week_[N].json` compiled by Pilot Manager

```json
{
  "week": 5,
  "dates": "2026-11-29 to 2026-12-05",
  "summary": {
    "phase": "soft_launch_validation",
    "all_pilots_on_track": true
  },
  "hotel": {
    "decisions_count": 30,
    "auto_approvals": 21,
    "escalations": 9,
    "approval_rate_pct": 100,
    "disparate_impact_ratio": 1.12,
    "disparate_impact_compliant": true,
    "ragas_accuracy_pct": 87,
    "latency_p50_ms": 3800,
    "latency_p95_ms": 4700,
    "latency_p99_ms": 4900,
    "latency_compliant": true,
    "pii_incidents": 0,
    "uptime_pct": 100.0,
    "incidents": 0,
    "ap2_entries": 210,
    "ap2_verified": true,
    "notes": "Soft-launch successful, fairness maintained, ready for production"
  },
  "glass": {
    "designs_count": 25,
    "risky_flags": 3,
    "false_negatives": 0,
    "false_positives": 0,
    "precision_pct": 100,
    "ragas_accuracy_pct": 90,
    "latency_avg_ms": 850,
    "latency_compliant": true,
    "cost_per_design_eur": 0.90,
    "cost_compliant": true,
    "incidents": 0,
    "ap2_entries": 25,
    "ap2_verified": true,
    "notes": "Zero false negatives maintained, ready for production"
  },
  "school": {
    "access_attempts": 2000,
    "biometric_matches": 1960,
    "biometric_failures": 40,
    "false_accept_rate_pct": 0.3,
    "false_reject_rate_pct": 1.2,
    "biometric_compliant": true,
    "auth_success_rate_pct": 99.8,
    "attendance_accuracy_pct": 98,
    "uptime_pct": 100.0,
    "network_durability_24h_test": "PASSED",
    "incidents": 0,
    "ap2_entries": 2000,
    "ap2_verified": true,
    "notes": "48-hour durability test scheduled next week"
  },
  "cross_pilot": {
    "total_decisions_logged": 2255,
    "total_ap2_entries": 2235,
    "karp_readiness_pct": 75,
    "all_targets_met": true
  },
  "compliance_sign_off": {
    "cto_approved": true,
    "cto_name": "CTO Name",
    "cto_signature_date": "2026-12-05",
    "notes": "All systems ready to proceed to production go-live"
  }
}
```

**Weekly Checklist (Pilot Manager, Fridays 5:00-5:30 PM CET):**
- [ ] Compile weekly JSON from daily CSVs + AP2 ledgers
- [ ] Verify all 3 pilots reporting (no missing data)
- [ ] Check all metrics against targets
- [ ] Flag any incidents for CTO review
- [ ] Get CTO sign-off (email or sync meeting)
- [ ] Commit to Git: `/EVIDENCE/week_[N].json`
- [ ] Upload to shared evidence drive (for Series A data room)

---

## MONTHLY COMPLIANCE REVIEW (1ST FRIDAY OF MONTH, 30 MIN)

**Participants:** Pilot Manager, CTO, Compliance Officer, Finance (if cost analysis)

**Agenda:**
1. Week-by-week metrics rollup (4 weeks → 1 month)
2. Incident review (any P1/P2?)
3. Fairness audit (hotel disparate impact, school biometric FAR/FRR)
4. Cost analysis (glass per-design, hotel per-approval, school per-access)
5. GDPR compliance (school DPA status, consent management)
6. RAGAS accuracy tracking (87%+ target)
7. AP2 ledger verification (all entries signed + auditable)
8. KARP/Series A readiness (% complete)

**Monthly Compliance Checklist:**
- [ ] Hotel: Disparate impact <1.25x for 100+ decisions? ✅
- [ ] Glass: False negative rate = 0% for 30+ designs? ✅
- [ ] School: FAR <0.5%, FRR <2% for 2000+ attempts? ✅
- [ ] All 3: RAGAS accuracy 87%+? ✅
- [ ] All 3: Zero unplanned outages (planned tests okay)? ✅
- [ ] Cost: Hotel [$/decision], Glass [€/design], School [$/attempt] trending downward?
- [ ] Compliance: GDPR DPA (school), fairness audit (all), security audit (all)
- [ ] Audit trail: 100% of decisions in AP2 ledger, signed + timestamped?
- [ ] Sign-off: CTO + Compliance Officer approve to continue?

**Output:** `/EVIDENCE/monthly_compliance_[MONTH]_[YEAR].md`

---

## END-OF-PILOT COMPREHENSIVE ARCHIVE (DEC 31, 2026)

**Directory Structure:**
```
/EVIDENCE/
├── hotel/
│   ├── HOTEL_FINAL_AP2_LEDGER.json (all 150+ decisions)
│   ├── HOTEL_FAIRNESS_AUDIT_FINAL.csv (disparate impact, 150 decisions)
│   ├── HOTEL_RAGAS_EVALUATION_FINAL.csv (88% accuracy, 50Q)
│   ├── HOTEL_COST_ANALYSIS_FINAL.csv (cost per approval)
│   ├── HOTEL_DASHBOARD_SCREENSHOTS.zip (approval rate, latency, fairness ratio)
│   └── HOTEL_CTO_SIGN_OFF.pdf (production-ready certification)

├── glass/
│   ├── GLASS_FINAL_AP2_LEDGER.json (all 50+ designs)
│   ├── GLASS_FALSE_NEGATIVE_AUDIT_FINAL.csv (0/50 false negatives)
│   ├── GLASS_PRECISION_METRICS_FINAL.csv (100% precision)
│   ├── GLASS_RAGAS_EVALUATION_FINAL.csv (91% accuracy, 50-design set)
│   ├── GLASS_COST_ANALYSIS_FINAL.csv (€0.85 per design)
│   ├── GLASS_DASHBOARD_SCREENSHOTS.zip (design status, safety rules, cost)
│   └── GLASS_SAFETY_ENGINEER_SIGN_OFF.pdf (zero false negatives observed)

├── school/
│   ├── SCHOOL_FINAL_AP2_LEDGER.json (all 2000+ accesses)
│   ├── SCHOOL_BIOMETRIC_ACCURACY_FINAL.csv (FAR 0.4%, FRR 1.1%, EER 0.75%)
│   ├── SCHOOL_ATTENDANCE_ACCURACY_FINAL.csv (100% match)
│   ├── SCHOOL_NETWORK_DURABILITY_TEST_FINAL.csv (48h test PASSED, recovery <5min)
│   ├── SCHOOL_RAGAS_EVALUATION_FINAL.csv (98% accuracy, 100-student set)
│   ├── SCHOOL_GDPR_DPA_APPROVAL.pdf (DPA approved)
│   ├── SCHOOL_DASHBOARD_SCREENSHOTS.zip (access events, biometric metrics, network)
│   └── SCHOOL_SECURITY_OFFICER_SIGN_OFF.pdf (network-resilient, GDPR-compliant)

├── cross_pilot/
│   ├── WEEK_1_BASELINE.json
│   ├── WEEK_2_BASELINE_COMPLETE.json
│   ├── WEEK_3_INTEGRATION.json
│   ├── WEEK_4_TRAINING.json
│   ├── WEEK_5_SOFT_LAUNCH.json
│   ├── WEEK_6_PRODUCTION_LIVE.json
│   ├── WEEK_7_COMPLIANCE.json
│   ├── WEEK_8_STRESS_TEST.json
│   ├── WEEK_9_FINAL.json
│   ├── MONTHLY_COMPLIANCE_NOV_2026.md
│   ├── MONTHLY_COMPLIANCE_DEC_2026.md
│   ├── INCIDENT_LOG_FINAL.csv (all P1/P2 incidents + root cause)
│   ├── COST_ANALYSIS_ROLLUP.csv (aggregate costs)
│   └── KARP_NARRATIVE_FINAL.md (3 pilots, 2200+ decisions, all targets met)

└── README.md (evidence collection methodology + audit trail)
```

**End-of-Pilot Checklist (Dec 31, 6:00 PM CET):**

### HOTEL
- [ ] AP2 ledger dump: All 150+ decisions, signed, verified
- [ ] Fairness audit: 150 decisions, disparate impact <1.25x ✅
- [ ] RAGAS final: 88%+ accuracy ✅
- [ ] Latency report: p95 <5s ✅
- [ ] Cost analysis: $ per approval, total cost
- [ ] Incident log: Zero unplanned outages, 0 PII leaks
- [ ] Dashboard proof: Screenshots of live operation
- [ ] CTO sign-off: Email/PDF "Production-ready, no known issues"

### GLASS
- [ ] AP2 ledger dump: All 50+ designs, signed, verified
- [ ] False negative audit: 0/50 designs failed post-approval ✅ (CRITICAL)
- [ ] Precision metrics: 100% of flagged designs were risky ✅
- [ ] RAGAS final: 91%+ accuracy ✅
- [ ] Latency report: avg 850ms <1s ✅
- [ ] Cost analysis: €0.85 per design <€1 ✅
- [ ] Incident log: Zero false negatives (critical metric)
- [ ] Dashboard proof: Screenshots of design reviews + safety rules
- [ ] Safety engineer sign-off: "Zero false negatives observed"

### SCHOOL
- [ ] AP2 ledger dump: All 2000+ accesses, signed, verified
- [ ] Biometric accuracy: FAR 0.4%, FRR 1.1% (all targets met) ✅
- [ ] Attendance accuracy: 100% match with manual records ✅
- [ ] Network durability: 48h test PASSED, recovery <5min ✅ (CRITICAL)
- [ ] RAGAS final: 98% accuracy ✅
- [ ] System uptime: 99.97% (only 45 min unplanned) ✅
- [ ] GDPR DPA: Approved, consent 100%, privacy notice provided ✅
- [ ] Incident log: Zero unplanned outages, zero data loss
- [ ] Dashboard proof: Screenshots of biometric events, uptime, network status
- [ ] Security sign-off: "Network-resilient, GDPR-compliant"

### CROSS-PILOT
- [ ] All 9 weekly evidence files: `/EVIDENCE/week_[1-9].json`
- [ ] All 3 monthly compliance reviews: Signed off ✅
- [ ] Incident log consolidated: All P1/P2 documented + fixed
- [ ] Cost rollup: Total cost per pilot, cost per decision
- [ ] KARP narrative: "3 pilots, 2200+ decisions, all regulatory targets met"

**Final Sign-Off Meeting (Dec 31, 6:00-7:00 PM CET):**
- [ ] Pilot Manager: All evidence collected, archive complete
- [ ] CTO: Code quality, zero defects, production-ready
- [ ] Compliance Officer: All regulatory targets met, GDPR/Annex III/I ready
- [ ] Finance: Cost analysis complete, budget reconciliation
- **Decision:** Ready for KARP submission + Series A due diligence? ✅

---

## AUDIT TRAIL METHODOLOGY

### Evidence Integrity (Chain of Custody)

1. **Daily Collection (Automated)**
   - Timestamp: 23:45-00:05 CET (pilot systems generate CSVs + AP2 ledger JSON)
   - Signature: Ed25519 signed by pilot system (private key in HSM)
   - Storage: Cloud + local backup (Temporal cache for school)

2. **Weekly Compilation (Manual)**
   - Timestamp: Fridays 17:00-17:30 CET (Pilot Manager)
   - Input: 7 daily CSVs + 7 daily AP2 JSON files
   - Computation: Aggregation + validation + new JSON file
   - Signature: CTO cryptographic approval (email thread)
   - Storage: Git commit with message "Week [N] evidence compiled and verified"

3. **Monthly Review (Manual)**
   - Timestamp: 1st Friday of month, 14:00-14:30 CET
   - Input: 4 weekly summaries + compliance checklist
   - Output: `/EVIDENCE/monthly_compliance_[MONTH].md`
   - Signature: CTO + Compliance Officer email sign-off
   - Storage: Git commit + shared drive

4. **End-of-Pilot Archive (Manual)**
   - Timestamp: Dec 31, 18:00-19:00 CET
   - Input: All 9 weeks + 3 months + daily/weekly/monthly evidence
   - Output: Comprehensive archive per above directory structure
   - Signature: CTO + Compliance Officer + Finance final sign-off
   - Storage: Encrypted archive + public Git repo (evidence references)

### Audit Compliance
- **Non-repudiation:** All decisions signed by Ed25519, timestamp authority (ECB/NANDO/DPA)
- **Immutability:** AP2 merkle roots committed to public Git, cannot be retroactively altered
- **Auditability:** Every daily CSV + weekly JSON + monthly review can be independently verified
- **Regulatory:** Evidence structure aligns with Annex III/I dossier requirements (9 sections per use case)

---

## SUCCESS = EVIDENCE READY FOR SUBMISSION

By Dec 31, 2026:
- ✅ 2,200+ decisions logged in AP2 ledger (all signed + timestamped)
- ✅ Weekly evidence summaries: 9 files, all metrics on target
- ✅ Monthly compliance reviews: 3 sign-offs, zero escalations
- ✅ Incident log: All issues <1% of total operations, fully documented
- ✅ KARP narrative: "3 pilots, 2200+ decisions, all regulatory targets met, ready for Phase 2"
- ✅ Series A ready: Evidence archive demonstrates governance, compliance, scale
