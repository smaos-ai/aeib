# PILOT 3: School Access Control (Identity + Attendance)
**Regulatory Deadline:** Dec 2, 2027 (Annex III, Essential Service)  
**Complexity Level:** L1→L2→L3→L4→L5→L6→L8→L7 + Temporal Durability  
**KARP Classification:** Article 6(2) High-Risk (Education, Biometric Access)

---

## 1. Risk Classification & Regulatory Mapping

### Article 6(2) Analysis
This pilot falls under **Article 6(2) high-risk category**: AI system used to verify identity + determine access rights to restricted facility. School building access combines two high-risk elements:
- **Biometric identification:** Face/voice verification (GDPR Article 9 special category)
- **Access control decision:** Authority delegated to AI to deny entry (potential discrimination)

### Annex III Scope
- **Section 2 (Education):** AI systems used in educational facility access and monitoring
- **Timeline:** Dec 2, 2027 (compliance deadline, 19 months from Phase 1 close)
- **Regulatory Bodies:** National education authorities, data protection authorities (DPA)
- **Special Constraint:** 48-hour workflow (verification window) + network failure recovery

### Failure Impact
- **False Positive (deny legitimate student):** Lockout from classes, attendance penalties
- **False Negative (admit unauthorized person):** Safety breach, facility access by non-students
- **Network Failure:** Building access blocked if central system down (Temporal durability required)
- **Biometric Bias:** Systematic failure to recognize students from specific ethnic groups (GDPR Article 9 violation)

---

## 2. Use Case Narrative

### Context
A secondary school (500 students) requires 48-hour enrollment verification (student ID + attendance record) before granting building access. Current process: manual admin check (2 minutes per student, 1-2 hour bottleneck at morning entry). Goal: Real-time verification (5 seconds) with network-resilient fallback (Temporal checkpoints).

### Workflow (Happy Path)
1. Student arrives at school entrance
2. Biometric scanner (face/voice) captures identity data
3. SMAOS L1-L8 orchestration:
   - **L1 (Policy):** Verify student is in current enrollment list (policy rule: "must have active_status=enrolled")
   - **L2 (Retrieval):** Look up student record in school DB + attendance history (last 48 hours)
   - **L3 (Gates):** Check attendance threshold (policy: "must have attended ≥80% of scheduled days in last 7 days" OR "must be within 48-hour enrollment grace period")
   - **L4 (Orchestration):** Multi-step verification:
     - Extract biometric features (face embedding, voice signature)
     - Match to student photo/voice sample in school DB (threshold: 95%+ confidence)
     - Verify enrollment status in Temporal checkpoint (fault-tolerant cache)
   - **L5 (Communication):** Return structured decision (grant/deny + reason + escalation)
   - **L6 (FreeToken):** Validate inference cost (<1¢ per access attempt)
   - **Temporal Durability:** Cache enrollment + biometric data at school gateway; survive 24-hour network outage by using last-known-good state
   - **L8 (Proof):** Log every access attempt in AP2 ledger (who, when, decision, reason)
   - **L7 (RAGAS):** Baseline on 100 known-student + 20 unauthorized-person scenarios
4. Decision: Grant (unlock door) | Deny (log attempt + alert) | Escalate-to-Admin (uncertain biometric)
5. Physical consequence: Door unlock → student enters (or remains locked + admin notified)

### Failure Scenarios
1. **Network Down (24-hour outage):** Temporal checkpoint activates; use cached enrollment + last-known-good biometric; all accesses logged locally
2. **Biometric Ambiguous:** Face confidence 70-90% → Escalate to admin (visual + manual ID check)
3. **Student Not in Cache:** New student enrolled <24 hours ago → Escalate (no local data yet)
4. **Attendance Below Threshold:** Mark student "pending review" → can still enter, but admin notified for follow-up
5. **Unauthorized Person with Spoofed Biometric:** Fail to recognize as student → Deny + log + alert
6. **Clock Skew (Temporal checkpoint stale):** Last update >48 hours old → Escalate (refresh from network if available)

---

## 3. Success Metrics

| Metric | Target | Verification |
|--------|--------|--------------|
| **Biometric Accuracy** | 98%+ (correctly identify 98% of enrolled students) | Daily accuracy check on 50 test students |
| **False Reject Rate** | <2% (incorrectly deny legitimate students) | Weekly audit of denied-access logs |
| **False Accept Rate** | <0.5% (incorrectly grant unauthorized access) | Monthly testing with decoy/impersonation attempts |
| **Latency** | <5 seconds end-to-end (biometric capture → decision) | Timestamp logs from door sensors |
| **Uptime** | 99.9% (max 43s downtime/month) | Health check every 10 seconds |
| **Temporal Durability** | Survive 24-hour network outage without access denial | Simulate network failure; verify local decisions logged + synced on recovery |
| **Attendance Threshold Accuracy** | 100% (correctly calculate 7-day attendance %) | Compare AI calculation to manual audit |
| **Bias Detection** | Zero disparate impact by race/gender | Monthly analysis of false-reject rates by student demographic |

---

## 4. SMAOS Layer Alignment

| Layer | Role | Implementation |
|-------|------|-----------------|
| **L1: Policy Routing** | Enrollment status check, attendance threshold | Policy rules: "must have active_status=enrolled AND (attendance_7day >= 0.80 OR enrolled_within_48h)" |
| **L2: Knowledge Retrieval** | Student biometric profile, enrollment record, attendance history | pgvector: biometric embeddings; Temporal cache: last-known-good enrollment + attendance (48-hour window) |
| **L3: Permit Gates** | Biometric threshold enforcement, attendance verification | Gate rule: "block if biometric_confidence < 95% AND not_escalated"; "block if attendance < 80% AND not_exempted" |
| **L4: Orchestration** | Biometric verification + enrollment check + attendance lookup | LangGraph: extract biometric → retrieve student profile → check enrollment → verify attendance → decide |
| **L5: Communication** | Structured access decision (grant/deny/escalate + reason) | MCP server: School Access Agent (input: biometric data → output: JSON decision + confidence + escalation reason) |
| **L6: FreeToken Validation** | Cost control (1¢/access attempt) | Verify biometric processing + DB lookup fit budget |
| **Temporal Durability** | Network-resilient operation (48-hour cache, checkpoint recovery) | Local SQLite + sync queue; if network down, use cached enrollment + biometric; replay sync log on recovery |
| **L8: Proof (AP2 Ledger)** | Immutable access log (who accessed when, decision, reason) | Sign every access attempt; digest in git (GDPR audit trail) |
| **L7: RAGAS Baseline** | Verification decision quality | Compare AI decision to consensus of school admin + security on 100 student + 20 impersonation scenarios |

---

## 5. Regulatory Deadline & Compliance

- **Phase 1 Close:** May 31, 2027 (pilot production-ready, 1 school with 500 students, 1+ month data)
- **Annex III Deadline:** Dec 2, 2027 (7 months for compliance audit)
- **DPA Submission:** Dec 1, 2027 (1 day before deadline, Data Protection Impact Assessment)
  - Dossier: Biometric processing policy, consent evidence, bias audit, 6-month access log
  - Evidence: AP2 ledger (all access attempts), RAGAS report, fairness metrics

---

## 6. Failure Modes & Human Escalation

| Failure Mode | Trigger | Escalation Path | Owner |
|--------------|---------|-----------------|-------|
| Biometric confidence <95% | Ambiguous face/voice match | Escalate to on-site admin (visual + manual ID verification) | School office staff |
| Attendance <80% AND no exception | Student missing classes | Mark "pending review"; log attempt; allow access; admin follows up same day | Attendance officer |
| Network down >24 hours | Loss of connectivity to enrollment server | Use Temporal checkpoint (cached enrollment); all decisions logged locally; sync on recovery | IT admin + network ops |
| Temporal checkpoint stale | Last DB update >48 hours old | Attempt network refresh; if still down, escalate to admin (manual enrollment verification) | IT admin |
| False rejection detected | Student reports wrongful denial | Audit AP2 ledger; extract biometric confidence, enrollment status, attendance data; adjust policy if systematic | Security admin + bias auditor |
| Unauthorized person denied | Intruder correctly rejected (security works) | Log success; notify security team; no escalation needed | Security officer |
| Unauthorized person granted (false accept) | Impersonator successfully enters | Immediate incident response: identify impersonator, review biometric logs, adjust threshold, retrain (if systematic bias) | CISO + biometrics team |

---

## 7. Proof Collection (What We Measure)

- **AP2 Ledger:** All 250,000+ access attempts (May 31, 2027 - Dec 2, 2027, ~2000/school day) with:
  - Student ID, timestamp, decision (grant/deny/escalate), reason (enrollment OK, attendance OK, biometric conf, policy match)
  - Biometric confidence score, face/voice embedding hash (for audit without storing raw biometric)
  - Temporal checkpoint state (online vs. offline), enrollment/attendance age
  - Admin escalation resolution (if any)
  
- **RAGAS Report:** 120-scenario golden set (100 enrolled students, 20 impersonation attempts)
  - Q: "Student enrolled Oct 1, attended 85% of days, shows up Oct 8 at 8am — grant?" → Expected: Grant → Model: Grant ✓
  - Q: "Unauthorized person with deepfake video — grant?" → Expected: Deny → Model: Deny ✓
  - Accuracy target: 98%+ on biometric identification, 90%+ on attendance logic
  
- **Fairness Audit:** Monthly disparate impact analysis
  - False-reject rate for White students: 1.8%, Asian: 2.1%, Black: 3.5% → Delta >5%? Investigate
  - Root cause: photo quality bias (certain students' photos worse), lighting conditions, embedding model drift?
  
- **Temporal Durability Test:** Quarterly network outage simulation
  - Disable network for 24 hours; verify school can still grant/deny access using cached data
  - Verify all decisions logged locally; sync to AP2 ledger on recovery
  - Zero false positives during outage (only false negatives if enrollment data missing)
  
- **Latency Histogram:** P50, P95, P99 access decision time
  - Target: P95 <5 seconds

---

## 8. Success Criteria (KARP Submission)

- ✅ L1→L8→L7 + Temporal durability flow processes 250,000+ real access attempts without major incident
- ✅ AP2 ledger captures all access attempts (immutable GDPR audit trail)
- ✅ RAGAS baseline 98%+ biometric + 90%+ enrollment/attendance logic
- ✅ Fairness audit shows <1.25x disparate impact by protected class
- ✅ Temporal durability survives 24-hour simulated network outage (all decisions logged + synced)
- ✅ 99.9% uptime over 6-month pilot period
- ✅ Zero false accepts in 20-person impersonation challenge test
- ✅ Annex III DPIA + compliance dossier generated

---

## 9. Integration with SMAOS Infrastructure

**Database Schema:**
- `access_attempts` table: student_id, timestamp, decision, biometric_conf, attendance_pct, ledger_hash
- `enrollment` table: student_id, status, enrollment_date, last_updated, temporal_checkpoint_version
- `temporal_cache` table: student_id, cached_enrollment_json, cached_attendance_pct, cache_timestamp (local SQLite, synced hourly)

**MCP Server:** School Access Agent (input: biometric data + network status → output: decision + confidence + escalation)

**LangGraph Node:** `school_access_control` orchestrates L1→L3→L4→L5 with Temporal fallback logic

**Temporal Durability Implementation:**
- On network unavailable: Use local SQLite cache (student enrollments + attendance, max 48h old)
- Queue all decisions for sync on recovery
- If cache empty (new student <48h), escalate to admin
- On network restore: Replay sync queue to AP2 ledger (idempotent by timestamp + student_id)

**FreeToken:** 500 students × 2 attempts/day = 1000 accesses/day × 0.01¢ = ~$0.10/day = $30/month

---

## 10. GDPR Special Considerations

**Biometric Data Processing:** Face/voice embeddings are special category data (GDPR Article 9).

- **Lawful Basis:** School security + legitimate interest (child safety)
- **Consent:** Obtain explicit consent from parents/guardians at enrollment
- **Retention:** Delete biometric embeddings 12 months after graduation (right to be forgotten)
- **Access Log (AP2 Ledger):** Retain for 3 years (audit trail), then anonymize/delete

**Data Protection Impact Assessment (DPIA):**
- Conducted before Phase 1 close (May 31, 2027)
- Submitted to DPA by Dec 1, 2027 (before Annex III deadline)
- Key finding: Biometric processing necessary for security; mitigations: encryption, bias audits, access controls

---

## 11. Long-Tail Risk: Impersonation via Deepfake

**Scenario:** Unauthorized person uses deepfake video/audio to spoof biometric system.

**Mitigation (L-in-loop anti-spoofing):**
- Require liveness detection (eye blink, head movement, voice variation across multiple phrases)
- Confidence threshold: >98% for biometric acceptance (requires high-quality spoof to bypass)
- Escalate if confidence 95-98% (manual verification)

**Detection:** If deepfake successfully bypasses:
1. Campus security (human monitoring) should catch unauthorized person
2. AP2 ledger logs biometric confidence score; post-incident audit reveals anomaly
3. Retrain model on failed-spoof case; adjust threshold if needed

**Response:** Block future spoofing by tightening liveness requirement (e.g., multi-angle face capture)
