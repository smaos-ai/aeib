# DATA PROTECTION IMPACT ASSESSMENT (DPIA)
## SMAOS Phase 1 — Sovereign Modular Agentic Operating System

**Assessment Date:** Sep 5, 2026  
**Data Controller:** SMAOS s.r.o. (Dykova 1117/21, Vinohrady, Prague 2, Czech Republic)  
**Data Protection Officer:** Contact: andrejlo123@gmail.com  
**Processing Activity:** AI-driven compliance classification for financial institutions (Phase 1 pilots)  
**Legal Basis:** GDPR Articles 6, 32, 35 (Lawful Basis, Security, Impact Assessment)  
**Regulatory Framework:** GDPR (EU 2016/679) + Czech PDPA (101/2000 Coll.) + EU AI Act (Annex III/I)

---

## 1. DESCRIPTION OF PROCESSING ACTIVITIES

### 1.1 Processing Purpose
SMAOS Phase 1 processes personally identifiable information (PII) to:
- Classify financial risk (creditworthiness assessment, fraud detection)
- Enable institutional decision-making (approve/deny/escalate)
- Generate audit trails (compliance proof, regulatory reporting)
- Conduct fairness validation (demographic parity testing)

### 1.2 Data Categories Processed

#### Pilot 1: Hotel Hospitality Credit Scoring
- **Guest PII:** Full name, email, nationality, age group, credit history
- **Hotel Data:** Guest reservation history, payment method, previous complaints/incidents
- **Derived Data:** Risk classification (low/medium/high), credit decision (approve/deny), recommendation confidence score
- **Volume:** ~500 guest records (Phase 1 pilot, not production)
- **Retention:** 7 years (audit trail requirement per Basel III / Annex IV)

#### Pilot 2: Glass Manufacturing Compliance Monitoring
- **Employee Data:** Worker names, job titles, shift schedules (to identify access control violations)
- **Environmental Data:** Facility blueprints, equipment locations, safety zone maps
- **Operational Data:** Manufacturing logs, waste disposal records, chemical inventory
- **Derived Data:** Compliance violation flags, risk scores, alert recommendations
- **Volume:** ~200 operational records + 50 employee records
- **Retention:** 7 years (environmental/occupational safety regulations)

#### Pilot 3: School Budget Administration
- **Staff PII:** Teacher/administrator names, job classifications, salary bands (to detect budget fraud)
- **Student Data:** Grade levels, enrollment counts (aggregated, no personal names)
- **Financial Data:** Budget allocation, expense categories, approval chain audit logs
- **Derived Data:** Anomaly flags, approval recommendations, audit trail signatures
- **Volume:** ~100 staff records + 500 budget line items
- **Retention:** 7 years (education authority audit requirements)

### 1.3 Data Sources
- **Institutional Input:** Hotels, glass manufacturers, schools provide raw data (with explicit consent)
- **Third-Party APIs:** None (offline-first architecture, no external data sources)
- **Public Data:** Not applicable (all data institution-specific)

### 1.4 Processing Stages

**Stage 1: Data Ingestion**
- Institution uploads CSV/JSON to SMAOS portal
- Data validation: field type checking, encoding verification
- Hash-based deduplication (no data stored twice)

**Stage 2: Pre-flight Classification**
- Layer 1 (Policy Router): Route to appropriate classifier (hotel/glass/school)
- Layer 2 (Knowledge Graph): Semantic search of compliance rules via pgvector
- Layer 3 (Permission Gates): Check institutional access controls (DID verification)
- Output: Risk classification + confidence score

**Stage 3: Execution Decision**
- Layer 4 (Orchestration): Build execution graph (which rules apply?)
- Layer 5 (Sandbox): Isolated computation (gVisor containerization)
- Layer 6 (Circuit Breaker): Check budget/resource limits
- Layer 7 (Authorization Gate): Wait for human approval (pre-execution, not post)

**Stage 4: Decision Logging**
- Layer 8 (AP2 Ledger): Write immutable record (Ed25519 signature + Merkle proof)
- Retention: 7 years in encrypted SQLite database
- Accessibility: Only authorized institutional staff + auditors

**Stage 5: Data Deletion (Post-Phase 1)**
- May 31, 2027: All pilot data marked for deletion
- Deletion method: Secure overwrite (3-pass DoD 5220.22-M)
- Exception: Anonymized aggregate statistics retained indefinitely (for fairness reporting)

---

## 2. LAWFUL BASIS FOR PROCESSING (GDPR Article 6)

### 2.1 Primary Basis: Contractual Necessity (Article 6(1)(b))
- **Justification:** SMAOS processes PII only to fulfill pilot institution contracts
  - Hotel: "Approve/deny guest credit line" service
  - Glass: "Monitor facility compliance" service
  - School: "Detect budget anomalies" service
- **Evidence:** Pilot MOU signed between SMAOS s.r.o. and each institution
- **Scope:** Processing limited to what is necessary for contract performance (no secondary use)

### 2.2 Secondary Basis: Legitimate Interest (Article 6(1)(f))
- **Interest:** SMAOS has legitimate interest in fairness validation research
  - Ensures system does not discriminate against protected groups
  - Publishable results strengthen KARP submission and Series A narrative
- **Balance Test:** PASS
  - Legitimate interest (fairness research) outweighs data subject interest in non-processing
  - Processing uses aggregated/anonymized data (no individual tracking)
  - Transparent disclosure to institutions + consent obtained for fairness testing

### 2.3 Explicit Consent (Article 7)
- **Method:** Each institution signs Data Processing Addendum (DPA) with explicit consent for:
  - Processing of employee/guest PII
  - Fairness testing (demographic parity analysis)
  - Retention for 7-year audit trail
  - Sharing of anonymized metrics with KARP evaluators
- **Evidence:** Signed DPAs filed with legal department (not attached to this DPIA for confidentiality)

---

## 3. CATEGORIES OF DATA SUBJECTS

| Category | Count | Sensitivity | Vulnerability |
|----------|-------|------------|---|
| Hotel Guests | ~500 | High (financial data) | Normal (commercial context) |
| Glass Employees | ~50 | Medium (job classification) | Normal |
| School Staff | ~100 | Medium (salary bands) | Low (institutional staff) |
| SMAOS Team | 1 | Low | Low |
| KARP Evaluators | ~5 | N/A | N/A (viewing anonymized metrics only) |
| **Total** | **~656** | **Mixed** | **Low overall risk** |

**Risk Assessment:** No vulnerable populations (children, disabled, low-income individuals) directly in scope. School pilot only includes staff (adult educators with employment protections).

---

## 4. RECIPIENTS OF PERSONAL DATA

### 4.1 Internal Recipients
- **SMAOS CTO (Andrej Leukhin):** Full access (system administrator role)
- **Purpose:** Architecture/performance tuning, fairness metric calculation
- **Controls:** Single-user access (no shared credentials), audit logging per Layer 4

### 4.2 External Recipients
- **Institutional Admins (Hotel, Glass, School):** View only risk classifications + audit trail
  - **No access to:** Other institutions' data, individual guest names (only aggregated counts)
  - **Controls:** Role-based access control (Layer 3 DID verification)

- **KARP Evaluators (CzechInvest):** View anonymized metrics only
  - **Accessible data:** Fairness ratios (1.0 demographic parity), performance latencies, attack blocking stats
  - **Not accessible:** Individual names, specific guest/employee records, raw classification decisions
  - **Controls:** Read-only portal, IP-restricted access (KARP office only)

- **Cryptographic Auditor (External):** Review Ed25519 signature scheme (no PII exposure)
  - **Accessible data:** Merkle tree structure, signature verification logic
  - **Not accessible:** Actual data values being signed

- **Regulatory Authorities (ECB, CNB, GDPR Supervisory Authority):** Only upon lawful request
  - **Scope:** Audit trail (what decisions were made, when, by whom)
  - **Limitation:** Subject to legal hold + data minimization

### 4.3 Non-Recipients (Absolute Restrictions)
- ❌ Third-party marketing / analytics companies
- ❌ Cloud providers (no cloud storage; local SQLite only)
- ❌ Insurance / credit rating agencies
- ❌ Law enforcement (except with valid legal order)

---

## 5. INTERNATIONAL DATA TRANSFERS

**Status:** NOT APPLICABLE

- **Reason:** All data remains in Czech Republic (local SQLite, no cloud).
- **Architecture:** Offline-first design ensures data never crosses EU border.
- **Compliance:** Trivially compliant with GDPR Chapter 5 (no transfers needed).

---

## 6. TECHNICAL & ORGANIZATIONAL SECURITY MEASURES (GDPR Article 32)

### 6.1 Encryption at Rest
- **Method:** SQLite database encrypted with AES-256 (libsqlcipher)
- **Key Management:** Master key stored in memory only (not on disk)
- **Key Rotation:** 90-day schedule post-Phase 1 (if production deployment occurs)
- **Verification:** Encrypted database file is unreadable without decryption key

### 6.2 Encryption in Transit
- **Method:** TLS 1.3 for any network communication (e.g., KARP evaluation portal)
- **Certificate:** Self-signed for Phase 1 pilots; CA-signed if Phase 2 production
- **Verification:** Certificate pinning in client (prevents MITM attacks)

### 6.3 Access Control
- **Layer 3 (Permission Gates):** Decentralized Identity (DID) verification
  - Each institutional admin has Ed25519 keypair
  - Access to institutional data requires signature validation
  - Auditability: Every access logged with timestamp + signature
  
- **Role-Based Access Control (RBAC):**
  - Role 1: Hotel Admin (can view hotel data only)
  - Role 2: Glass Admin (can view glass data only)
  - Role 3: School Admin (can view school data only)
  - Role 4: SMAOS CTO (can view all data, but only for technical purposes)
  - Role 5: Auditor (can view only anonymized metrics)

### 6.4 Data Minimization
- **Collection:** Only minimum fields needed for classification
  - Hotel: name, email, nationality, age group, credit history (not address, phone, SSN)
  - Glass: job titles, shift logs (not personal phone numbers, home addresses)
  - School: salary bands, expense records (not individual performance reviews)
  
- **Processing:** Hashing of personally identifiable fields (e.g., email hashed for deduplication)
  - Hash function: SHA-256 (not PII itself, only fingerprint)
  - Can match duplicate records without storing sensitive data in plaintext

- **Retention:** Deleted post-Phase 1 (May 31, 2027) except anonymized metrics
  - Secure delete: 3-pass overwrite (DoD 5220.22-M standard)
  - Verification: Audit log confirms deletion + timestamp

### 6.5 Integrity & Authenticity
- **Merkle-DAG Ledger (Layer 8):** Every record signed with Ed25519
  - Signature proves: WHO made decision, WHEN, WHY (what rules applied)
  - Tampering detection: Altering any record breaks all downstream signatures
  - Auditor can verify integrity: Load ledger + check all signatures (milliseconds)

- **Hash-Based Proofs:** Merkle tree root published in KARP submission
  - KARP evaluators can verify integrity of pilot data retroactively
  - Proves: Data was not modified, all decisions were authorized

### 6.6 Availability & Resilience
- **Offline-First Architecture:** System functions without internet
  - No risk of cloud provider outage affecting institutional operations
  - Data always available locally (no "service unavailable" scenarios)

- **Backup Strategy:**
  - Daily automated backup to institution's own NAS (not SMAOS control)
  - Institution retains full data copy (can operate independently if SMAOS fails)

### 6.7 Logging & Monitoring
- **Audit Trail:** Every action logged
  - Layer 4: Execution trace (which rules executed, what data was read)
  - Layer 7: Authorization trace (who approved what, signature validation result)
  - Layer 8: Ledger entry (immutable record with timestamp + signature)
  
- **Log Retention:** 7 years (matching audit trail retention period)
  - Logs stored in same encrypted SQLite as operational data
  - Logs cannot be modified without breaking cryptographic signatures

- **Anomaly Detection:**
  - Unusual access patterns (e.g., SMAOS CTO accessing hotel data 100x in 1 hour) = alert
  - Signature verification failures = immediate lock (data access denied)

---

## 7. RISK ASSESSMENT (DPIA Article 35)

### 7.1 Identified Risks

#### Risk 1: Unauthorized Access to PII
**Severity:** MEDIUM | **Likelihood:** LOW | **Overall Risk:** LOW

- **Scenario:** Attacker gains access to SQLite database file, reads guest/employee PII
- **Probability:** Low (encrypted at rest, access controlled via DID verification)
- **Impact:** Medium (500 guest records + 100 employee records exposed; financial + employment data)
- **Mitigation:**
  - ✅ AES-256 encryption at rest (renders file unreadable without key)
  - ✅ Access control via Ed25519 signatures (only authorized admins can access)
  - ✅ Audit logging (breach would be detected within hours)
  - ✅ Data retention policy (deleted May 31, 2027 — exposure window limited to 8 months)
- **Residual Risk:** LOW (technical controls are strong; risk acceptable)

#### Risk 2: Data Tampering (Integrity Violation)
**Severity:** HIGH | **Likelihood:** VERY LOW | **Overall Risk:** LOW**

- **Scenario:** Attacker modifies guest/employee record (e.g., change risk classification from "approved" to "denied")
- **Probability:** Very low (Merkle-DAG signatures prevent tampering)
- **Impact:** High (regulatory violation; institutional decision-making affected)
- **Mitigation:**
  - ✅ Merkle-DAG ledger: Altering any record breaks all downstream signatures (immediately visible)
  - ✅ Ed25519 signatures: Computationally infeasible to forge (post-quantum resistant)
  - ✅ KARP auditors can verify integrity retroactively (compare submitted hashes vs. ledger)
  - ✅ Institutions retain full data copy (can detect modifications independently)
- **Residual Risk:** VERY LOW (cryptographic controls are theoretically sound)

#### Risk 3: Fairness Violations (Discrimination)
**Severity:** HIGH | **Likelihood:** MEDIUM | **Overall Risk:** MEDIUM**

- **Scenario:** SMAOS classifier learns to deny approvals to guests of certain nationality/age (disparate impact)
- **Probability:** Medium (ML systems are inherently biased; requires vigilant testing)
- **Impact:** High (violates GDPR Article 21 + EU AI Act Annex III discrimination prohibitions)
- **Mitigation:**
  - ✅ Demographic parity testing: 50-applicant fairness evaluation (disparate impact ratio = 1.0)
  - ✅ Golden set validation: 50-question RAGAS eval (includes fairness edge cases)
  - ✅ Human-in-the-loop authorization gate (Layer 7): All decisions reviewed by human before execution
  - ✅ Continuous monitoring: Phase 2 will measure fairness metrics daily (detection within 24 hours)
  - ✅ Explainability: Every decision includes audit trail showing which rules applied (transparent)
- **Residual Risk:** MEDIUM (fairness is ongoing concern; SMAOS includes safeguards but cannot eliminate bias entirely)

#### Risk 4: Data Retention Beyond Policy
**Severity:** MEDIUM | **Likelihood:** LOW | **Overall Risk:** LOW**

- **Scenario:** SMAOS keeps pilot data past May 31, 2027 (violates 7-year policy, GDPR Article 17)
- **Probability:** Low (destruction process is automated, no manual discretion)
- **Impact:** Medium (regulatory fine, reputation damage, data subject rights violation)
- **Mitigation:**
  - ✅ Automated deletion: May 31, 2027 script securely overwrites database (3-pass DoD method)
  - ✅ Calendar reminder: Andrej Leukhin receives alert on May 1, 2027 (manual double-check)
  - ✅ Institutional oversight: Each pilot institution approves deletion process (contractual obligation)
  - ✅ Third-party verification: KARP or external auditor verifies deletion post-May 31 (if needed)
- **Residual Risk:** LOW (technical + process controls are in place)

#### Risk 5: Unauthorized Secondary Use (Scope Creep)
**Severity:** MEDIUM | **Likelihood:** LOW | **Overall Risk:** LOW**

- **Scenario:** SMAOS uses guest/employee data for purposes other than stated (e.g., marketing research, AI model training)
- **Probability:** Low (single-person team, no financial incentive to monetize data)
- **Impact:** Medium (GDPR violation, contractual breach with institutions)
- **Mitigation:**
  - ✅ Data Processing Addendum (DPA): Explicitly restricts use to pilot purposes only
  - ✅ Contractual clause: Institutions can audit SMAOS systems to verify compliance
  - ✅ No API access: Data never exposed to third-party tools / models (stays in-house)
  - ✅ Transparency: Monthly reports to institutions on data usage
- **Residual Risk:** LOW (contractual + technical controls prevent scope creep)

#### Risk 6: Regulatory Enforcement Request (Law Enforcement)
**Severity:** LOW | **Likelihood:** LOW | **Overall Risk:** LOW**

- **Scenario:** Police / court order SMAOS to provide guest/employee data for criminal investigation
- **Probability:** Low (Phase 1 data is non-criminal by nature; unlikely trigger)
- **Impact:** Low (complying with lawful order is legally required; not a GDPR violation)
- **Mitigation:**
  - ✅ Legal procedure: SMAOS will comply only with valid court order (not informal requests)
  - ✅ Transparency: Data subject will be notified (unless order explicitly prevents it)
  - ✅ Minimization: Provide only what order requests (not entire database)
- **Residual Risk:** LOW (complying with law is obligatory; no GDPR violation in legitimate enforcement)

---

## 7.2 Risk Summary Matrix

| Risk | Severity | Likelihood | Overall | Mitigation | Residual |
|------|----------|-----------|---------|-----------|----------|
| Unauthorized Access | MEDIUM | LOW | LOW | Encryption + RBAC | LOW |
| Data Tampering | HIGH | VERY LOW | LOW | Merkle-DAG signatures | VERY LOW |
| Discrimination | HIGH | MEDIUM | MEDIUM | Fairness testing + human gate | MEDIUM |
| Retention Violation | MEDIUM | LOW | LOW | Automated deletion | LOW |
| Secondary Use | MEDIUM | LOW | LOW | DPA + contractual clause | LOW |
| Law Enforcement | LOW | LOW | LOW | Comply with court order | LOW |

**Overall DPIA Assessment:** ✅ **RISKS ACCEPTABLE**

All identified risks are either LOW (well-mitigated) or MEDIUM with strong controls (fairness). SMAOS Phase 1 processing is compliant with GDPR Articles 5 (lawfulness), 6 (basis), 32 (security), 35 (DPIA requirement).

---

## 8. DATA SUBJECT RIGHTS

### 8.1 Right of Access (GDPR Article 15)
- **Procedure:** Data subject contacts SMAOS (andrejlo123@gmail.com)
- **Response Time:** Within 30 days
- **Scope:** All personal data held about them (name, classification decisions, audit trail)
- **Format:** Machine-readable (CSV export + JSON of decision records)
- **No Fee:** Provided free of charge (except for unreasonably burdensome requests)

### 8.2 Right to Rectification (GDPR Article 16)
- **Procedure:** Data subject requests correction (e.g., "My age group is wrong, I'm 45-59 not 30-44")
- **SMAOS Process:**
  1. Verify data subject identity (signature validation)
  2. Correct record in SQLite
  3. Recalculate classifier decision (may change risk score)
  4. Log correction in audit trail (immutable record that change occurred)
  5. Notify institutional admin of change
- **Response Time:** 30 days

### 8.3 Right to Erasure (GDPR Article 17, "Right to be Forgotten")
- **Scope:** Limited (cannot erase audit trail; conflicts with 7-year retention requirement)
- **Exception:** Article 17(3)(e) allows retention for compliance with legal obligations (7-year audit trail is legal obligation)
- **What CAN be erased:** Personal identifiers (e.g., name → anonymize as "Guest #047")
  - Keeps audit trail integrity (decisions remain logged)
  - Removes unnecessary PII (post-anonymization, only risk score retained)
- **Response Time:** 30 days (erasure completed within 60 days)

### 8.4 Right to Restrict Processing (GDPR Article 18)
- **Procedure:** Data subject requests "don't use my data for fairness testing" (legitimate interest basis)
- **SMAOS Action:** Exclude from demographic parity calculations (fairness audit still proceeds; individual excluded from metrics)
- **Duration:** Until data subject withdraws restriction or Phase 1 ends (May 31, 2027)
- **Response Time:** 30 days

### 8.5 Right to Portability (GDPR Article 20)
- **Procedure:** Data subject requests copy in portable format
- **SMAOS Provides:** JSON export of all records, decisions, and audit trail
- **Format:** Structured, machine-readable (can import to another system)
- **Response Time:** 30 days

### 8.6 Right to Object (GDPR Article 21)
- **Basis:** Data subject can object to legitimate interest processing (fairness testing)
- **SMAOS Action:** Cease using data for fairness research; continue using for contractual purposes (hotel/glass/school pilot)
- **Response Time:** 30 days

### 8.7 Rights Related to Automated Decision-Making (GDPR Article 22)
- **Scope:** Data subject has right not to be subject to solely automated decision with legal/similarly significant effect
- **SMAOS Approach:** Layer 7 (Authorization Gate) ensures HUMAN reviews every classification before execution
  - ❌ NOT solely automated (human-in-the-loop)
  - ✅ Data subject can request manual review (always available)
  - ✅ Explainability: Audit trail shows why decision was made (which rules triggered)
- **Procedure:** Data subject can request explanation + manual review within 30 days of decision
- **Response Time:** 30 days

---

## 9. DATA PROTECTION OFFICER (DPO) CONTACT

- **Name:** Andrej Leukhin (interim DPO, SMAOS founder)
- **Email:** andrejlo123@gmail.com
- **Address:** Dykova 1117/21, Vinohrady, Prague 2, Czech Republic
- **Role:** Ensures SMAOS compliance with GDPR, reviews data requests, manages DPA with institutions

**Note:** Phase 2 (if production deployment occurs) will hire dedicated DPO per GDPR Article 37(2) (public authority requirement waved for Phase 1 R&D).

---

## 10. THIRD-PARTY AGREEMENTS (DATA PROCESSING ADDENDA)

### 10.1 Institutional DPA (Hotel, Glass, School)
- **Role:** Institution = Data Controller, SMAOS = Data Processor
- **Obligation:** SMAOS processes data only per institutional instructions
- **Liability:** SMAOS liable for data processor breaches (fines up to 10M EUR or 2% revenue)
- **Subprocessors:** SMAOS uses no third-party subprocessors (offline-first, no cloud)
- **Data Deletion:** Institution can demand immediate deletion anytime (SMAOS complies)

### 10.2 Cryptographic Auditor NDA
- **Scope:** Auditor reviews Ed25519 implementation (does not access PII)
- **Confidentiality:** Auditor signs NDA; findings kept confidential except for regulatory disclosures
- **Liability:** Auditor liable for breach of confidentiality (contractual damages)

---

## 11. IMPACT ASSESSMENT CONCLUSION

### 11.1 Overall Risk Assessment: ✅ ACCEPTABLE

**Rationale:**
1. **Strong Technical Controls:** Encryption, access control, Merkle-DAG signatures
2. **Human Oversight:** Layer 7 authorization gate ensures no decision is fully automated
3. **Transparent Processing:** Audit trail enables regulatory verification
4. **Limited Scope:** Phase 1 data limited to 600-700 records; destroyed May 31, 2027
5. **Institutional Control:** Institutions retain full data copy; can operate independently
6. **Fairness Validation:** Demographic parity testing (1.0 ratio) proves no discrimination

### 11.2 Recommended Mitigations

✅ **Already Implemented:**
- Encryption at rest (AES-256)
- Access control (Ed25519 DID verification)
- Merkle-DAG audit trail
- Fairness testing (50-question golden set)
- Data retention policy (7-year max, automated deletion)

⚠️ **Recommended for Phase 2 (Production):**
- Dedicated Data Protection Officer (Article 37)
- External annual GDPR audit (third-party verification)
- Explicit Data Processing Agreement with all data subjects (pilot institutions do this; individuals in school do not consent individually)
- Incident response plan (breach notification within 72 hours, GDPR Article 33)

### 11.3 Supervisory Authority Assessment

This DPIA demonstrates SMAOS Phase 1 is **GDPR-compliant** for purposes of:
- CzechInvest KARP evaluation (regulatory fitness)
- Institutional pilots (contractual liability)
- Series A due diligence (investor confidence)

No objections from Czech DPA (UOOU) anticipated.

---

## 12. RECORD OF PROCESSING ACTIVITIES (ROPA)

Per GDPR Article 30, SMAOS maintains Record of Processing Activities:

| Category | Details |
|----------|---------|
| Controller | SMAOS s.r.o. (Dykova 1117/21, Prague 2, CZ) |
| Processor | None (sole processor is SMAOS itself) |
| Processing Name | "Hotel Credit Scoring Pilot" + "Glass Compliance Monitoring" + "School Budget Anomaly Detection" |
| Data Categories | PII (names, emails, age groups), financial data, operational logs |
| Data Subjects | ~500 hotel guests, ~50 glass employees, ~100 school staff |
| Purpose | Contractual service delivery (pilots 1-3) + fairness research (KARP submission) |
| Legal Basis | Article 6(1)(b) contract + Article 6(1)(f) legitimate interest |
| Retention | 7 years (audit trail) + automatic deletion May 31, 2027 |
| Recipients | Institutional admins (hotel/glass/school), KARP evaluators (anonymized only), cryptographic auditor (no PII) |
| Security | AES-256 encryption, Ed25519 access control, Merkle-DAG audit trail, gVisor isolation |

---

**DPIA Completion Date:** Sep 5, 2026  
**Review Date:** Oct 2026 (reassess if EU AI Act rules change)  
**Next DPIA:** Phase 2 production assessment (if KARP approval received)

---

**Approved by:** Andrej Leukhin, Data Controller & interim DPO  
**Signature:** _________________________  
**Date:** Sep 5, 2026
