# DCMA Filing Compliance Checklist
## Israel Defense Ministry Contract Preparation

**Project:** SovereignNexus / AXIOM Defense Governance System  
**Deadline:** Jul 1, 2026 (27 days from Jun 4, 2026)  
**Requirement:** Defense Information Systems Agency (DISA) compliance for Israeli defense ministry contracts  
**Responsible:** Legal counsel + Andrey Leukhin (crypto verification)  
**Escalation:** If any item fails → Request 30-day extension (Jul 1 → Aug 1)

---

## Compliance Checklist

### 1. Technology Classification Review
**Objective:** Determine classification level (Unclassified vs. CUI vs. Secret)  
**Status:** [ ] Not started

- [ ] **AXIOM core framework** (Rust, TypeScript, Ed25519, SHA256)
  - Classification: Unclassified (commodity cryptography, standard algorithms)
  - Justification: Ed25519 and SHA256 are public-domain algorithms; no military-specific modifications
  - Document: Technical classification memo

- [ ] **Defense Capsule module** (encrypted policy storage)
  - Classification: CUI (Controlled Unclassified Information)
  - Justification: Policy logic contains operational-security-relevant data; releasable to Israel under 10 USC § 2331
  - Document: CUI marking matrix, redaction plan (if needed)

- [ ] **Merkle auditing engine** (tamper-proof logs)
  - Classification: Unclassified (commodity blockchain pattern, no classified algorithms)
  - Justification: Uses standard cryptographic hashing; no defense-specific data embedded
  - Document: Algorithm whitepaper, peer-review reference

- [ ] **Government data connectors** (MoD API integration)
  - Classification: TBD (depends on Israeli MoD data classification)
  - Action: Coordinate with Israeli legal counsel on data flow classification
  - Document: Data flow diagram, classification agreement

**Owner:** Legal counsel  
**Deadline:** Jun 14, 2026

---

### 2. Export Control Screening
**Objective:** Confirm compliance with ITAR/EAR; verify Israel as authorized destination  
**Status:** [ ] Not started

- [ ] **Commodity Software Review (ECCN classification)**
  - Rust, TypeScript, standard libraries: ECCN EAR99 (no export license)
  - Ed25519/SHA256 cryptography: ECCN EAR99 (unclassified, commodity)
  - Defense Capsule: ECCN 3D001 candidate (review pending, likely EAR99 with CUI marking)
  - Document: Commodity classification letter

- [ ] **Israel as Authorized Destination**
  - Israel is Tier-1 US ally; no EAR or ITAR licensing required for unclassified tech
  - License Exception BAG (Publicly Available) applies to open-source components
  - CUI-marked Defense Capsule: Releasable under 22 CFR 125.1 (foreign military sales to NATO allies)
  - Document: Export authorization summary, CCATS reference (if obtained)

- [ ] **Reexport Compliance**
  - All subcontractors (Stripe, Redis, GitHub) are US-based; no reexport chain risk
  - Israeli end-user certification: Israeli MoD can receive and deploy without reexport restrictions
  - Document: Supplier compliance chain attestation

- [ ] **Technology Transfer Restrictions**
  - Source code can be released to Israeli MoD under contract with export compliance rider
  - Training and documentation: Standard (no controlled technical data embedded)
  - Security controls: Encryption keys, deployment architecture — all compliant
  - Document: Technology transfer agreement template

**Owner:** Andrey Leukhin (crypto review) + Legal counsel  
**Deadline:** Jun 20, 2026

---

### 3. Supply Chain Risk Assessment
**Objective:** Verify all dependencies are reviewed and compliant  
**Status:** [ ] Not started

- [ ] **Dependency Audit**
  - [ ] Cargo.lock (Rust dependencies): Run security audit
    - Command: `cargo audit`
    - Review for vulnerabilities, export-controlled crates, foreign ownership
  - [ ] package.json (TypeScript dependencies): Run npm security audit
    - Command: `npm audit`
    - Review for vulnerabilities, foreign ownership
  - [ ] System dependencies (OpenSSL, PostgreSQL, Redis): Vendor status check

- [ ] **Key Vendors (US-based, LOW risk)**
  - [ ] **Stripe** (payment processing)
    - Ownership: US public company (NASDAQ: STRP)
    - Export risk: No (financial services, exempt from ITAR/EAR)
    - Attestation: Standard vendor security certifications
  - [ ] **Redis** (in-memory data store)
    - Ownership: Redis Inc. (US, backed by Venture Capital)
    - Export risk: No (commodity open-source software)
    - Attestation: OSS license compliance, no classified algorithms
  - [ ] **GitHub** (source code repository)
    - Ownership: Microsoft (US)
    - Export risk: No (commodity development platform)
    - Attestation: Enterprise security agreement in place

- [ ] **Open Source Compliance**
  - [ ] MIT, Apache 2.0, BSD licenses: No export restrictions
  - [ ] GPL/AGPL review: Confirm no copyleft implications for proprietary modules
  - [ ] SBOM (Software Bill of Materials) generation: Document all components
    - Tool: `cargo tree`, npm package-lock.json
    - Deliverable: Complete SBOM for Israeli MoD review

**Owner:** Andrey Leukhin (engineering) + Legal counsel  
**Deadline:** Jun 18, 2026

---

### 4. Security Certification (NIST 800-53 Compliance)
**Objective:** Achieve required NIST control baseline  
**Status:** [ ] Not started  
**Current baseline:** 20/150 controls implemented; ~13% coverage

- [ ] **Access Control (AC) Family**
  - [ ] AC-2 Account management: Implement role-based access control (RBAC)
  - [ ] AC-3 Access enforcement: Policy-based authorization (Defense Capsule)
  - [ ] AC-6 Least privilege: Capability-based security model
  - Target: 6/12 controls → Effort: 3-5 days

- [ ] **Identification & Authentication (IA) Family**
  - [ ] IA-2 Authentication: MFA/certificate-based login
  - [ ] IA-4 Identifier management: Unique user identifiers per deployment
  - Target: 4/9 controls → Effort: 2-3 days

- [ ] **Audit & Accountability (AU) Family**
  - [ ] AU-2 Audit events: Log all policy decisions, access attempts
  - [ ] AU-12 Audit generation: Automated logging with tamper-proof storage
  - Target: 5/14 controls → Effort: 3-4 days

- [ ] **Cryptography (SC) Family**
  - [ ] SC-12 Cryptographic key establishment: FIPS 140-2 algorithms (Ed25519 compliant)
  - [ ] SC-13 Cryptographic protection: Data-at-rest and in-transit encryption
  - Target: 3/15 controls → Effort: 1-2 days (mostly existing)

- [ ] **Incident Response (IR) Family**
  - [ ] IR-4 Incident handling: Documented procedures for Israeli MoD
  - [ ] IR-8 Incident response plan: Escalation matrix, contact list
  - Target: 2/10 controls → Effort: 2 days

**NIST 800-171 Mapping (for CUI handling):**
- Defense Capsule module triggers NIST 800-171 requirements (CUI protection)
- Requires: Encryption, access controls, audit logging, incident response plan
- Current gap: 20/111 controls → Target: 40/111 controls (36% coverage) by Jun 25

**Owner:** Andrey Leukhin (architecture) + Security architect (if available)  
**Deadline:** Jun 25, 2026  
**Risk:** If NIST coverage <40%, negotiate phased compliance (baseline first, advanced controls post-pilot)

---

### 5. Subcontractor Vetting
**Objective:** Confirm all third-party vendors meet defense contract standards  
**Status:** [ ] Not started

- [ ] **Stripe Inc.**
  - Legal check: US public company, SEC filings available
  - Security: SOC 2 Type II certification, PCI DSS compliance
  - Export compliance: No ITAR/EAR restrictions (financial services)
  - Attestation needed: Vendor security questionnaire (VSQ), Standard contract rider
  - Risk: LOW

- [ ] **Redis Inc.**
  - Legal check: US private company, Series H funding ($110M)
  - Security: Security.md published; vulnerability disclosure policy in place
  - Export compliance: No ITAR/EAR restrictions (open-source software)
  - Attestation needed: Open-source license audit, SBOM declaration
  - Risk: LOW

- [ ] **GitHub (Microsoft)**
  - Legal check: US public company (parent: Microsoft, NASDAQ: MSFT)
  - Security: Enterprise security agreement (ESA) available; SOC 2 Type II
  - Export compliance: No ITAR/EAR restrictions (development platform)
  - Attestation needed: Data residency agreement (Israel deployment option available)
  - Risk: LOW

- [ ] **Subcontractor Approval Form**
  - [ ] Complete DLA Vendor Information (DD Form 1161)
  - [ ] Obtain DUNS number (if applicable)
  - [ ] Document subcontractor confidentiality/NDA commitments
  - Deliverable: Signed attestation from each vendor confirming export compliance awareness

**Owner:** Legal counsel + Procurement  
**Deadline:** Jun 22, 2026

---

### 6. Data Residency Verification
**Objective:** Confirm data storage and processing locations; assess key management requirements  
**Status:** [ ] Not started

- [ ] **Storage Location**
  - Primary: TBD (Israeli government cloud, AWS eu-west-1 Dublin, or hybrid)
  - Encryption keys: Decision gate — Israel-based keys vs. US-based keys
    - Option A: Keys hosted in Israel (higher sovereignty, slightly higher latency)
    - Option B: Keys hosted in US with Israeli delegation policy (lower latency, standard cross-border model)
  - Backup/disaster recovery: Specify geographic redundancy requirements
  - Document: Data residency agreement, key management architecture

- [ ] **Processing Location**
  - Defense Capsule policy evaluation: Specify location (Israel, EU, or US)
  - Audit logging: Location for tamper-proof logs
  - Backup operations: Geographic requirements
  - Document: Processing location matrix, latency requirements (<500ms target)

- [ ] **Israeli Data Protection Compliance**
  - [ ] Israeli Privacy Law (protection of privacy law, 1981): No personal data without consent
  - [ ] Protection of Privacy Regulations (encryption, security): Compliance checklist
  - [ ] MoD-specific data handling: Coordinate with Israeli legal counsel
  - Document: Israeli privacy law attestation letter

- [ ] **Encryption Key Management**
  - [ ] HSM (Hardware Security Module) deployment: Specify standard (FIPS 140-2, FIPS 140-3)
  - [ ] Key rotation policy: Annual rotation minimum
  - [ ] Access control: Multi-factor approval for key operations
  - Document: Key management plan per NIST SP 800-57

**Owner:** Andrey Leukhin (architecture) + Israeli legal counsel  
**Deadline:** Jun 28, 2026  
**Decision gate:** Which data residency model to propose to MoD? (Jun 15)

---

### 7. Legal Review (DLA/DD Form 254)
**Objective:** Obtain pre-negotiation agreement; review contract terms  
**Status:** [ ] Not started

- [ ] **DD Form 254 (Statement of Work for Defense Contracts)**
  - Requirement: Israeli MoD will provide DD Form 254 defining security requirements
  - Action: Review and acknowledge (US contractors cannot proceed without signed DD Form)
  - Timeline: Typically 2-3 weeks for Israeli government process
  - Document: Signed DD Form 254 return letter

- [ ] **Standard Defense Contract Rider**
  - [ ] DFARS clauses (Defense Federal Acquisition Regulation Supplement):
    - DFARS 252.204-7009 (Cost Accounting Standards)
    - DFARS 252.227-7013 (Data Rights)
    - DFARS 252.235-7009 (Whistleblower Protections)
  - [ ] FAR clauses (for subcontractor flow-down):
    - FAR 52.204-21 (Basic Safeguarding of CUI)
    - FAR 52.235-1 (Restrictions on Disclosure of Subcontractor Information)
  - Document: Pre-approved contract rider template

- [ ] **Export Compliance Rider**
  - [ ] Clause confirming ITAR/EAR compliance responsibility
  - [ ] Reexport control provisions (Israel as end-user, no further distribution)
  - [ ] Technology transfer restrictions (if source code provided)
  - Document: Export compliance rider (standard form)

- [ ] **Cybersecurity & Incident Response Addendum**
  - [ ] Incident notification timeline: 24-48 hours for Israeli MoD
  - [ ] Data breach response: Specify joint investigation procedures
  - [ ] Security certification: Confirm NIST 800-171 compliance (if CUI involved)
  - Document: Incident response SLA

- [ ] **Non-Disclosure Agreement (NDA)**
  - [ ] Israeli government NDA terms: Typically very restrictive (government classified data)
  - [ ] Subcontractor NDA: All suppliers must sign government-compatible NDAs
  - Document: NDA template aligned with Israeli government standards

**Owner:** External legal counsel (Israel defense contracts specialist)  
**Deadline:** Jun 30, 2026  
**Action:** Engage counsel by Jun 10 (20-day lead time)

---

## Timeline

| Phase | Dates | Owners | Deliverables | Status |
|-------|-------|--------|--------------|--------|
| Classification & Export Control | Jun 4-20 | Legal + Andrey | Tech classification memo, export authority summary | [ ] |
| Supply Chain & Subcontractor Review | Jun 4-22 | Andrey + Procurement | SBOM, vendor attestations | [ ] |
| NIST Compliance Baseline | Jun 10-25 | Andrey + Security | NIST 800-171 implementation roadmap | [ ] |
| Data Residency & Key Management | Jun 15-28 | Andrey + Israeli counsel | Data residency agreement, KM plan | [ ] |
| Legal Review & Contract Prep | Jun 10-30 | External counsel | DD Form 254, contract riders | [ ] |
| **DCMA FILING SUBMISSION** | **Jul 1, 2026** | All | Complete filing package | [ ] |

---

## Submission Package (Jul 1 deadline)

**To DISA/Israeli MoD Procurement:**

1. **Executive Summary** (1 page)
   - System overview, classification levels, compliance status

2. **Technology Classification Memo** (3 pages)
   - Component-by-component classification justification
   - CUI marking matrix (if applicable)

3. **Export Control Certification** (2 pages)
   - ECCN classifications, CCATS reference
   - Israel authorization statement

4. **Software Bill of Materials (SBOM)** (Appendix A)
   - Full dependency list, license audit, export compliance

5. **Subcontractor Attestations** (Appendix B)
   - Vendor security questionnaires, signed compliance declarations

6. **NIST 800-53/800-171 Compliance Matrix** (Appendix C)
   - Controls implemented, target baseline, roadmap for gaps

7. **Data Residency & Key Management Plan** (Appendix D)
   - Storage locations, encryption architecture, backup procedures

8. **Contract Rider Templates** (Appendix E)
   - DFARS clauses, export compliance, incident response SLA

---

## Success Criteria

- [ ] All 7 checklist items marked complete by Jul 1
- [ ] Zero critical compliance gaps (HIGH/CRITICAL risk items resolved)
- [ ] DCMA filing package submitted on time
- [ ] Feedback received from Israeli MoD/DISA by Sep 1 (decision expected Nov 1)

---

## Escalation Path

**If any item fails or reaches blocker status:**

1. **Day 1 (blocker identified):** Notify Andrey + Legal counsel
2. **Day 2:** Escalation meeting: assess impact, identify workaround
3. **Day 3:** Request 30-day extension to Jul 31 if required
   - Justification: Late government stakeholder engagement, additional security testing needed
   - Expected impact: Pilot PoC delayed Sep 1 → Oct 1 (non-critical, won't impact Series B)

**Risk tolerance:** Prefer on-time filing with minimal NIST coverage (20/150 controls, phased compliance plan) over late filing with full compliance.

---

## References

- [NIST SP 800-53](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf) — Security and Privacy Controls
- [NIST SP 800-171](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-171r2.pdf) — Protecting CUI in Non-Federal Systems
- [22 CFR Part 120-130](https://www.ecfr.gov/current/title-22/part-120) — ITAR International Traffic in Arms Regulations
- [EAR Part 730-774](https://www.ecfr.gov/current/title-15/part-730) — Export Administration Regulations
- [DFARS Clauses](https://www.dfars.mil/) — Defense Federal Acquisition Regulation Supplement
- [Israeli Defense Procurement](https://www.mod.gov.il/en) — Israeli Ministry of Defense procurement guidelines

---

**Document Version:** 1.0  
**Last Updated:** Jun 4, 2026  
**Next Review:** Jun 14, 2026 (mid-point check-in)
