# GDPR DATA PROCESSING AGREEMENT
## SovereignNexus Platform — Standard Contractual Clauses (SCCs)

**Document Version:** 1.0  
**Effective Date:** June 4, 2026  
**Status:** Ready for Legal Review (Pearl Cohen LLP)  
**Jurisdiction:** EU (GDPR) + International (SCCs for third-country transfers)

---

## 1. EXECUTIVE SUMMARY

This Data Processing Agreement (DPA) establishes the legal framework for processing personal data on behalf of customers under the EU General Data Protection Regulation (GDPR). The agreement incorporates:

- **Article 28 Data Processing Terms** — Processing instructions, sub-processor authorization
- **Standard Contractual Clauses (SCCs)** — EU Commission Decision 2021/914 for international data transfers
- **Data Protection Impact Assessment (DPIA)** — Risk identification and mitigation
- **Subprocessor Management** — Transparent disclosure and consent mechanisms
- **Data Subject Rights** — Access, deletion, portability, explanation procedures

**Parties:**
- **Controller:** Customer (deploying agents via SovereignNexus platform)
- **Processor:** Axiom Protocol / SovereignNexus (data processing service provider)
- **Jurisdiction:** EU (GDPR) applies; SCCs govern non-EU transfers

---

## 2. DEFINITIONS (GDPR Article 28 Alignment)

| Term | Definition | Regulatory Reference |
|------|-----------|----------------------|
| **Personal Data** | Information relating to an identified or identifiable natural person | GDPR Art. 4(1) |
| **Processing** | Any operation on personal data (collection, storage, use, disclosure, deletion) | GDPR Art. 4(2) |
| **Controller** | Customer who determines purposes and means of processing | GDPR Art. 4(7) |
| **Processor** | Axiom Protocol (SovereignNexus), processes data per Controller instructions | GDPR Art. 4(8) |
| **Subprocessor** | Third party authorized to process on behalf of Processor | GDPR Art. 28(2) |
| **Data Subject** | Individual to whom personal data relates | GDPR Art. 4(1) |
| **Capsule** | Encrypted agent state bundle (task, context, result) — may contain personal data | SISS v2.0 |

---

## 3. SCOPE OF DATA PROCESSING

### 3.1 Data Categories Processed

**Tier 1 (Non-Personal, Public)**
- Agent metadata (ID, creation date, capability list)
- System metrics (latency, throughput, availability)
- Aggregate performance analytics
- **No GDPR restrictions** — processed freely

**Tier 2 (Internal, Pseudo-Anonymized)**
- Agent state logs (learning history, skill progression)
- System performance data (error rates, SLA compliance)
- Audit trail summaries (transaction counts, not identity)
- **Limited GDPR restrictions** — may require anonymization assessment

**Tier 3 (Confidential, May Contain Personal Data)**
- Capsules (encrypted agent state bundles) — may contain customer PII
- User identity information (email, organizational affiliation)
- Task descriptions (may reference individuals)
- **Full GDPR restrictions apply** — encryption, access control, deletion upon request

**Tier 4 (Restricted, Special Category Data)**
- Biometric data (if behavioral profiling performed)
- Health data (if processing health-related tasks)
- Racial/ethnic origin (if inferred from agent behavior)
- **Explicit consent required** — Article 9 GDPR

### 3.2 Processing Activities

| Activity | Legal Basis | Duration | Purpose |
|----------|-------------|----------|---------|
| **Capsule Storage** | Contract (Art. 6(1)(b)) | Until deletion request | Provide SovereignNexus service |
| **Encryption** | Legitimate interest (Art. 6(1)(f)) | Continuous | Security & confidentiality |
| **Audit Logging** | Legal obligation (Art. 6(1)(c)) | 7 years | Regulatory compliance |
| **Performance Analysis** | Legitimate interest (Art. 6(1)(f)) | 90 days | Service improvement |
| **Subprocessor Access** | Contract (Art. 28) | As needed | Technical infrastructure |

### 3.3 Data Subjects Affected

- **Primary:** Agent system operators (organizational staff using the platform)
- **Secondary:** End-users referenced in capsule data (clients, constituents, stakeholders)
- **Incidental:** Third-party references in agent task descriptions

---

## 4. DATA PROCESSOR OBLIGATIONS (GDPR Article 28)

### 4.1 Processing Instructions

**Axiom Protocol commits to processing personal data ONLY as instructed by Controller, specifically:**

1. **Encryption:** All Tier 3/4 data encrypted at rest (AES-256-GCM) and in transit (TLS 1.3)
2. **Access Control:** RBAC per customer namespace — isolation enforced
3. **Audit Trail:** HMAC-SHA256 signed audit entries — tamper detection enabled
4. **Retention:** 30-day default, configurable per customer, deletion on request
5. **Sub-processing:** Only authorized subprocessors listed in Appendix A
6. **No Secondary Use:** Processor cannot use data for its own purposes (except service improvement with anonymization)

### 4.2 Confidentiality Obligations

**All Axiom Protocol staff accessing personal data are bound to:**
- Confidentiality agreements (NDA + data protection addendum)
- Annual GDPR & security training (minimum 4 hours)
- Need-to-know access (principle of least privilege)
- Secure credential management (no hardcoded passwords, MFA required)

### 4.3 Technical & Organizational Measures

**Security Controls (per GDPR Article 32):**

```
1. Encryption
   ├─ At Rest: AES-256-GCM (all capsules)
   ├─ In Transit: TLS 1.3 (all API endpoints)
   ├─ Key Management: Vault integration (roadmap Q3 2026)
   └─ Test: Quarterly encryption key audit

2. Access Control
   ├─ RBAC: Admin, Analyst, Operator, Reader roles
   ├─ Namespace Isolation: Customer A cannot query Customer B
   ├─ API Keys: Rotated every 90 days
   ├─ MFA: Planned for Q3 2026 (authentication framework update)
   └─ Test: Monthly permission matrix validation

3. Audit & Monitoring
   ├─ Immutable Audit Trail: HMAC-signed entry logs
   ├─ Tamper Detection: Signature verification on read
   ├─ Real-time Alerting: High-risk access attempts
   └─ Test: Weekly integrity verification

4. Network Security
   ├─ VPC Isolation: EU data in EU VPC (Ireland region)
   ├─ Security Groups: Minimal allowed ports (443 HTTPS only for API)
   ├─ DDoS Protection: Cloudflare + AWS Shield
   └─ Test: Quarterly penetration testing

5. Personnel Security
   ├─ Background Checks: All access-level staff vetted
   ├─ Conflict of Interest: Annual declaration
   ├─ Exit Procedures: Credential revocation within 24 hours
   └─ Test: Annual access review
```

### 4.4 Data Protection Impact Assessment (DPIA)

**Conducted:** June 3, 2026  
**Risk Level:** MEDIUM (high-risk AI system with encryption mitigations)

**High-Risk Processing Identified:**
- Behavioral profiling (agent learning history) → Mitigation: Explicit data minimization, opt-out option
- Capsule encryption key management → Mitigation: Vault integration planned, audit trail enforcement
- Third-party subprocessor access → Mitigation: Subprocessor contracts in place, data processing agreements signed

**DPIA Conclusion:** Processing is lawful with implemented mitigations. No processing activity identified that would trigger prohibition or require supervisory authority consultation.

---

## 5. STANDARD CONTRACTUAL CLAUSES (SCCS) — INTERNATIONAL TRANSFERS

### 5.1 Legal Framework

**Regulation:** EU Commission Decision 2021/914 (Standard Contractual Clauses for controllers/processors)

**Scope:** Any transfer of personal data from EU to non-EU countries (e.g., US cloud infrastructure, Israeli development team)

### 5.2 Module Structure

**SovereignNexus uses Module Two (Controller-to-Processor transfer):**

```
EU Customer (Controller)
    ↓ [Data Processing Agreement + SCCs]
Axiom Protocol (Processor)
    ↓ [Subprocessor Agreement + SCCs]
Subprocessors (e.g., AWS, GCP, cloud providers)
```

### 5.3 Clause-by-Clause Alignment

| Clause | Requirement | SovereignNexus Compliance |
|--------|-----------|--------------------------|
| **C1.1** | Personal data transferred clearly identified | ✓ Appendix A: Capsule data definition |
| **C1.2** | Processing purposes specified | ✓ Service delivery, security, audit logging |
| **C1.3** | Duration of processing | ✓ 30-day default, customer-configurable |
| **C2.1** | Processor only processes per instructions | ✓ API-enforced instruction model |
| **C2.2** | Processor ensures confidentiality | ✓ NDA + annual training |
| **C2.3** | Technical & organizational measures | ✓ Section 4.3 detailed above |
| **C3.1** | Sub-processor authorization required | ✓ Appendix A: approved subprocessors list |
| **C3.2** | Prior written authorization for new subprocessors | ✓ Customer consent mechanism in place |
| **C4.1** | International transfer based on legal adequacy | ✓ Onward transfers to adequacy-confirmed countries |
| **C5.1** | Data subject rights mechanisms | ✓ Section 6 below |
| **C9.1** | Liability & indemnification | ✓ Section 7 below |

### 5.4 Onward Transfers to Third Countries

**Current Subprocessors (approved for data transfer):**

| Entity | Location | Purpose | Data Sensitivity | SCC Status |
|--------|----------|---------|------------------|-----------|
| Amazon Web Services (AWS) | US (Dublin region for EU data) | Cloud infrastructure, data storage | Tier 3 (encrypted) | ✓ Executed |
| Cloudflare | US (global CDN) | DDoS protection, content delivery | Tier 1/2 (no personal data) | ✓ Executed |
| GitHub (Microsoft) | US | Source code repository (no customer data) | Tier 1 | ✓ Executed |
| HashiCorp (Vault cloud) | US (planned Q3 2026) | Encryption key management | Tier 4 (keys only) | ⏳ Pending |

**Transfer Guarantee:** All onward transfers include SCCs or Binding Corporate Rules (BCRs).

---

## 6. DATA SUBJECT RIGHTS & PROCEDURES

### 6.1 Right to Access (GDPR Article 15)

**Procedure:**
1. Data subject submits request via privacy@axiomprotocol.com
2. Axiom Protocol verifies identity (email confirmation)
3. Capsule data exported in JSON format within **48 hours**
4. Format: Standard, machine-readable, transferable

**Example Export:**
```json
{
  "capsule_id": "uuid-1234",
  "created_at": "2026-06-01T10:00:00Z",
  "agent_id": "agent-567",
  "task_description": "Process customer inquiry",
  "personal_data_fields": {
    "customer_name": "[encrypted]",
    "customer_email": "[encrypted]"
  },
  "encryption_key_hash": "sha256-abc123..."
}
```

### 6.2 Right to Deletion (GDPR Article 17)

**Procedure:**
1. Data subject (or authorized agent) submits deletion request
2. Axiom Platform identifies all capsules linked to data subject
3. Encryption keys deleted securely (cryptographic shredding)
4. Audit log entry created (deletion timestamp, authority)
5. Confirmation sent within **7 days**

**Implementation:** No file shredding required — key deletion is sufficient (AES-256 ciphertext becomes unrecoverable).

### 6.3 Right to Portability (GDPR Article 20)

**Procedure:**
1. Data subject requests data export
2. All personal data extracted in JSON format
3. Delivered within **30 days** in machine-readable format (CSV/JSON)
4. Suitable for import to competing platform (schema documented)

**Example Portability Export:**
```json
{
  "export_date": "2026-06-15T14:30:00Z",
  "data_subject": "john.doe@example.com",
  "capsules": [...],
  "preferences": {...},
  "audit_events": [...]
}
```

### 6.4 Right to Explanation (GDPR Article 22 + EU AI Act Article 13)

**Procedure:**
1. Data subject requests explanation of automated decision
2. Axiom Protocol provides decision log entry (JSON):
   - Input state
   - Feature contributions
   - Confidence score
   - Human review verdict (if applicable)
   - Appeal instructions

**Example Decision Log:**
```json
{
  "decision_id": "decision-999",
  "decision_type": "capsule_commit_approval",
  "timestamp": "2026-06-15T10:00:00Z",
  "data_subject": "john.doe@example.com",
  "input_state": {...},
  "model_inference": {
    "feature_contributions": {"feature_1": 0.7, "feature_2": 0.3},
    "confidence": 0.92
  },
  "human_judge_verdict": "APPROVE",
  "judge_reasoning": "High confidence, routine task, no safety concerns",
  "appeal_instructions": "Reply within 7 days to privacy@axiomprotocol.com"
}
```

### 6.5 Objection & Appeal Procedures

| Right | Objection Mechanism | Timeline | Authority |
|------|-------------------|----------|-----------|
| **Data Retention** | Opt-out of non-essential processing | Immediate | Customer |
| **Automated Decision** | Appeal to human judge (φ+ Eval Court) | 7 days | Judge panel |
| **Cross-customer Access** | Request rejection, escalate to CISO | 24 hours | Security Officer |
| **Data Breach** | Notification + right to legal remedy | See Section 9 | Legal team |

---

## 7. LIABILITY & INDEMNIFICATION

### 7.1 Processor Liability (GDPR Article 82)

**Axiom Protocol (Processor) is liable for damages where:**
- Processing violates GDPR
- Unauthorized disclosure of personal data
- Failure to implement security measures
- Breach of confidentiality obligations

**Liability Cap:** Limited to amount of processing contract, unless:
- Intentional violation or gross negligence (liability unlimited)
- Data breach resulting from processor failure

### 7.2 Indemnification

**Axiom Protocol indemnifies Customer (Controller) for:**
- Third-party claims alleging data breach due to processor negligence
- Regulatory fines (GDPR Article 83) where breach is processor responsibility
- Legal defense costs

**Customer responsibility:**
- Compliance with data minimization (Art. 5(1)(c))
- Lawful processing basis (Art. 6) established by Controller
- Data subject consent (if required)

### 7.3 Insurance

**Axiom Protocol maintains:**
- Cyber liability insurance: €5M coverage (minimum)
- Errors & omissions: €2M coverage
- Professional indemnity: €2M coverage

---

## 8. BREACH NOTIFICATION & RESPONSE

### 8.1 Data Breach Definition (GDPR Article 33)

**Triggers immediate notification (within 72 hours to DPA):**
- Unauthorized access to encrypted capsules (decryption required)
- Deletion or corruption of audit trail
- Loss of encryption key material
- Compromised TLS certificate
- Cross-customer access breach (RBAC bypass)

**Does NOT trigger notification (not legally a breach):**
- Encrypted data compromised (ciphertext only, key not exposed)
- Audit log accessed without modification (read-only)
- Network attempt blocked by firewall
- Non-personal data leaked (aggregate metrics only)

### 8.2 Notification Procedure

**Axiom Protocol → GDPR Authority (within 72 hours):**
1. Breach description (what, when, how)
2. Categories of personal data affected
3. Likely consequences for data subjects
4. Measures taken or proposed to address breach
5. Data Protection Officer contact

**Axiom Protocol → Customer (within 24 hours):**
1. Incident summary
2. Estimated personal data affected
3. Immediate remediation steps
4. Ongoing investigation status
5. Contact for questions (SOC team)

**Customer → Data Subjects (within 7 days, if high risk):**
1. Nature of breach in plain language
2. Likely consequences
3. Steps they should take (change passwords, monitor credit, etc.)
4. Contact information for more info
5. No blame language (avoid "we apologize" to minimize liability)

### 8.3 Example Breach Scenario

**Scenario:** TLS certificate expires, allowing MITM attack. Data encrypted, but attacker gains cert key.

**Notification timeline:**
- **T+0 (detection):** Certificate expiration alert fires. SOC team notified.
- **T+2 hours:** Certificate revoked, new one issued, TLS re-established. Audit log confirms scope (3 customers, 120 capsules).
- **T+4 hours:** Initial assessment: encrypted data only (AES-256), ciphertext exposed but key not compromised.
- **T+24 hours:** Customer notification sent (incident details, no user notification required due to encryption).
- **T+48 hours:** GDPR DPA notification (if no personal data readable in ciphertext, severity = LOW).
- **T+72 hours:** Post-incident review scheduled; root cause (cert renewal automation failure) identified.

---

## 9. INTERNATIONAL REGULATORY COMPLIANCE

### 9.1 GDPR (EU) — Fully Compliant

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Article 28 (Processor obligations) | ✓ Compliant | This DPA document |
| Article 32 (Security measures) | ✓ Compliant | Encryption, RBAC, audit trail |
| Article 33 (Breach notification) | ✓ Compliant | 72-hour procedure documented |
| Article 34 (Data subject notification) | ✓ Compliant | Plain-language notification template |
| Article 82 (Liability) | ✓ Compliant | Insurance + indemnification clauses |

**Supervisory Authority:** Austrian Data Protection Authority (APD) — **unless customer specifies local DPA**

### 9.2 eIDAS Regulation (EU) — Cryptographic Standards Met

**Regulation:** Regulation (EU) No 910/2014 (electronic identification, authentication, trust services)

| eIDAS Requirement | SovereignNexus Alignment |
|---|---|
| Advanced electronic signature (Art. 26) | ✓ Ed25519 signatures meet ETSI standards |
| Secure electronic document (Art. 3.1) | ✓ Merkle-DAG + HMAC tamper detection |
| Timestamping (Art. 36) | ⏳ Planned integration (trusted timestamping Q4 2026) |
| Qualified electronic seal (Art. 41) | ⏳ Requires certification by trusted service provider |

**Current Status:** Pathway to eIDAS certification identified. Not yet certified, but cryptographic foundations exceed requirement.

### 9.3 NIS2 Directive (EU) — Incident Response Plan

**See:** Section 10 (separate document: `NIS2_INCIDENT_RESPONSE_PLAN.md`)

### 9.4 ISO 27001:2022 — Security Management

**See:** Section 11 (separate document: `ISO_27001_GAP_ANALYSIS.md`)

---

## 10. SUBPROCESSOR MANAGEMENT

### 10.1 Approved Subprocessors

**Current List (as of June 4, 2026):**

| Name | Type | Purpose | Data Access | SCC Executed |
|------|------|---------|-------------|--------------|
| AWS Ireland | Cloud Infra | Storage, compute | Tier 3 (encrypted) | ✓ Yes |
| Cloudflare | CDN | Content delivery | Tier 1/2 only | ✓ Yes |
| GitHub / Microsoft | Code Repo | Source control | None (no data) | ✓ Yes |
| HashiCorp (Vault) | Key Management | Encryption key storage | Tier 4 (keys only) | ⏳ Pending |

### 10.2 Adding New Subprocessors

**Process:**
1. Axiom Protocol identifies need for new subprocessor (e.g., backup provider)
2. Security assessment: vendor vetting, SCC review, data access limitations
3. **At least 30 days prior notice** to Customer
4. Customer has right to object within **30 days**
5. If Customer objects, Axiom Protocol either:
   - Finds alternative subprocessor
   - Terminates DPA (mutual agreement)

**Current Pending:** HashiCorp Vault (target integration date: Q3 2026). All customers will receive 30-day notice before activation.

### 10.3 Subprocessor Contracts

**Mandatory terms in all subprocessor agreements:**
- Same data protection obligations as this DPA
- SCCs (if subprocessor in third country)
- Audit rights (Axiom Protocol can audit subprocessor)
- Incident notification (72-hour requirement)
- Deletion upon request (same as main DPA)

---

## 11. TERM & TERMINATION

### 11.1 Effective Date

**This DPA is effective as of:** June 4, 2026

**Binding on:** First customer data processed after June 4

### 11.2 Termination

**Termination Triggers:**
1. **Customer-initiated:** Notice of 30 days, deletion of all capsules within 7 days
2. **Axiom-initiated:** Notice of 90 days (only if customer materially breaches), cure period 30 days
3. **Mutual agreement:** Immediate upon written agreement
4. **Regulatory directive:** Immediate, if required by law (e.g., GDPR enforcement action)

**Post-Termination Obligations:**
- All personal data deleted or returned within **14 days**
- Subprocessors instructed to delete/return same timeline
- Audit log retained for **7 years** (regulatory requirement)
- No secondary processing allowed

---

## 12. LEGAL REVIEW & APPROVAL

### 12.1 Recommended Review Timeline

| Reviewer | Role | Deadline | Status |
|----------|------|----------|--------|
| **Pearl Cohen LLP** | GDPR Counsel | June 10 | ⏳ Pending |
| **Customer (DPA signer)** | Controller | June 15 | ⏳ Pending |
| **Axiom Legal** | Processor | June 15 | ⏳ Pending |
| **DPA / Competent Authority** | Regulatory | June 20 | ⏳ Pending (advisory only) |

### 12.2 Sign-Off

This DPA is **READY FOR LEGAL REVIEW** and requires formal execution by:

**For Axiom Protocol / Processor:**
- Name: _________________________
- Title: _________________________
- Date: _________________________
- Signature: _________________________

**For Customer / Controller:**
- Name: _________________________
- Title: _________________________
- Date: _________________________
- Signature: _________________________

---

## APPENDIX A: DATA PROCESSING DETAILS

### A.1 Categories of Personal Data

| Category | Examples | Sensitivity |
|----------|----------|-------------|
| **Identification Data** | Name, email, user ID | Tier 3 |
| **Behavioral Data** | Agent learning history, task completion logs | Tier 2/3 |
| **Interaction Data** | Capsule contents, task descriptions | Tier 3 |
| **System Data** | IP address, browser type, device info | Tier 1/2 |
| **Special Categories** | Health data, biometric patterns (if present) | Tier 4 |

### A.2 Categories of Data Subjects

| Category | Description | Approx. Volume |
|----------|-------------|-----------------|
| **Customers** | Organizational staff using SovereignNexus | 100-500 |
| **End-users** | Individuals referenced in agent tasks | 1,000-10,000 |
| **Third parties** | Incidental references (clients, partners) | Unknown |

### A.3 Processing Operations

| Operation | Frequency | Purpose | Legal Basis |
|-----------|-----------|---------|-------------|
| **Encryption** | Real-time | Security | Art. 6(1)(f) |
| **Audit logging** | Real-time | Compliance | Art. 6(1)(c) |
| **Access control** | Real-time | Security | Art. 6(1)(f) |
| **Deletion** | On request | Data subject right | Art. 17 |
| **Analytics** | Daily | Service improvement | Art. 6(1)(f) |

### A.4 International Transfers

| Destination | Mechanism | Data Sensitivity | Status |
|-------------|-----------|------------------|--------|
| **USA (AWS Dublin)** | SCC Module 2 + Adequacy decision via Dublin region | Tier 3 (encrypted) | ✓ Active |
| **USA (Cloudflare)** | SCC + Data minimization (no personal data) | Tier 1 only | ✓ Active |
| **Israel (Dev Team)** | Adequacy agreement pending | Encrypted logs only | ⏳ Planned Q3 |

---

## APPENDIX B: STANDARD CONTRACTUAL CLAUSE TEMPLATE

**This section contains the legal text of the Standard Contractual Clauses (SCC) for international transfers, Module Two (Controller-Processor).**

```
STANDARD CONTRACTUAL CLAUSES
(Controller to Processor)
– Module Two –

[Full SCC text as per EU Commission Decision 2021/914 inserted here]

Clause 1: Purpose and Scope
1.1 The purpose of these standard contractual clauses ("Clauses") is to ensure 
    compliance with Article 28 GDPR when personal data is transferred 
    internationally.

1.2 The Processor agrees to process personal data solely on instructions 
    from the Controller, in accordance with GDPR, and these Clauses.

[Clauses 2-15: Standard Contractual Clauses as per Commission Decision 2021/914]

Clause 16: Departure from the Standard Contractual Clauses
The Processor may not invoke a departure from the Clauses except in 
exceptional circumstances when required by EU or Member State law.

Execution Date: June 4, 2026
Controller: [Customer Name]
Processor: Axiom Protocol Inc.
```

**Note:** Full SCC text to be finalized by legal counsel (Pearl Cohen LLP) per EU Commission Decision 2021/914.

---

## APPENDIX C: CUSTOMER NOTIFICATION TEMPLATE

**This template is used for data subject requests and breach notifications:**

```
SUBJECT: Your Data Processing Request — SovereignNexus Platform

Dear [Data Subject Name],

[Choose appropriate section below]

SECTION A: RIGHT TO ACCESS RESPONSE
Your request to access personal data processed by SovereignNexus has been received.
We are compiling your capsule data and will deliver it in JSON format within 48 hours.
Attached: Your data export (capsule_export_[date].json)

SECTION B: RIGHT TO DELETION RESPONSE
Your request to delete personal data has been received.
We have identified [N] capsules linked to your identity and will delete the associated 
encryption keys within 7 days. After deletion, your data will be permanently unrecoverable.
Action taken: Deletion initiated [timestamp]

SECTION C: DATA BREACH NOTIFICATION
A data breach has occurred affecting the SovereignNexus platform. We are writing to inform 
you of the incident and steps we are taking.
Breach details: [description]
Your data: [what was exposed]
Measures taken: [immediate steps]
What you should do: [recommendations]

For questions, contact: privacy@axiomprotocol.com
Data Protection Officer: dpo@axiomprotocol.com

Sincerely,
Axiom Protocol Data Protection Team
```

---

**END OF GDPR DPA DOCUMENT**

**Document Status:** Ready for Pearl Cohen LLP Legal Review  
**Next Steps:** 
1. Send to Pearl Cohen for final review (target June 10)
2. Customer signature (target June 15)
3. Publication on website (target June 20)
4. Implementation: Immediately upon execution (all new contracts after June 20 must reference this DPA)

**Retained By:** Legal & Compliance Team  
**Last Updated:** June 4, 2026
