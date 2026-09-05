# Phase 2 Regulatory Checklist — Compliance Validation & Launch Gating

**Date:** September 1, 2026  
**Scope:** Pre-launch validation for Phase 2A (Intent Verification), Phase 2B (Federated GaaS), Phase 2C (Compliance Automation)  
**Status:** Gating checklist; each box must be checked before phase release

---

## PHASE 2A: INTENT VERIFICATION (Target: Q4 2026)

### Regulatory Alignment Checks

#### Check 1: Intent Verification Aligns with GDPR Art. 22 + Annex III "Human Oversight"

**Requirement:** Art. 22 GDPR mandates meaningful human intervention in decisions affecting individuals. Annex III requires "human oversight" as non-delegable obligation.

**SMAOS Test:**
- [ ] Harness implements **intent verification gate**: Agent cannot invoke financial/PII-affecting tools without human approval after intent parsing
- [ ] Audit log captures: (user_request, parsed_intent, human_approval_y/n, timestamp, approver_name)
- [ ] Documentation: "SMAOS Intent Verification satisfies GDPR Art. 22 + Annex III §5.3"
- [ ] Legal review: DLA Piper / Morrison Foerster confirms alignment (budget $10-15k)

**Validation Timeline:** Oct 2026 (before Phase 2A launch)

**Responsible:** Engineer + Legal

---

#### Check 2: Intent Verification Accuracy ≥ 90% on Credit Scoring Use Cases

**Requirement:** Annex III credit scoring systems must have <10% false positive rate on intent detection (false positives = missing actual risk).

**SMAOS Test:**
- [ ] Fine-tuned Claude model for intent classification (accuracy measured on 500-test-case set)
- [ ] Test cases sourced from Phase 1 hotel pilot (real user requests + ground truth labels)
- [ ] Error analysis: Identify remaining 10% errors; document known limitations
- [ ] Production deployment: Route <90% confidence intents to human review (fallback)

**Success Criteria:** 90%+ accuracy on credit scoring + lending decision scenarios

**Validation Timeline:** Sep-Oct 2026

**Responsible:** ML Engineer (contractor, 2-week engagement)

---

#### Check 3: Intent Verification Complies with GDPR Art. 13 (Right to Explanation)

**Requirement:** Users must understand why AI rejected their intent (right to explanation). SMAOS must explain intent mismatch in plain language.

**SMAOS Test:**
- [ ] When intent is rejected (parsed intent ≠ requested action), system generates explanation: "You requested [X], but I understood [Y]. Please confirm."
- [ ] Explanation is human-readable (not technical jargon)
- [ ] Test: 10 real users validate explanations are understandable (usability test)

**Success Criteria:** 90%+ user comprehension on rejection explanations

**Validation Timeline:** Nov 2026

**Responsible:** Product Manager + UX Engineer

---

### EU AI Act Annex III Alignment

#### Check 4: Risk Management System Includes Intent Verification as Risk Mitigation

**Requirement:** Annex III §4 requires documented "risk management system" covering design, development, deployment risks. Intent verification is a risk control (reduces intent misalignment risk).

**SMAOS Test:**
- [ ] Risk register: Document "Intent Misalignment Risk" (e.g., agent misinterprets user request, causes financial loss)
- [ ] Control mapping: Intent verification gates → Mitigates intent misalignment risk (residual risk < medium)
- [ ] Residual risk scoring: Document why <10% error rate is acceptable (e.g., human review catches remaining)

**Validation Timeline:** Oct 2026

**Responsible:** Compliance Officer + Engineer

---

#### Check 5: Human Oversight Workflow Documented + Tested

**Requirement:** Annex III §5.3 requires "meaningful human oversight" with "override capability."

**SMAOS Test:**
- [ ] Human approval workflow tested: Agent requests approval → human reviews intent → approves/rejects → logged with signature
- [ ] Override scenario: Human approves intent; agent executes; system logs both intent + execution
- [ ] Audit trail: 100 test cases processed end-to-end; all logged correctly
- [ ] Response time SLA: Human receives approval request within 5 seconds (system doesn't hang)

**Success Criteria:** 100% accurate logging; <5sec request-to-approval time

**Validation Timeline:** Oct 2026

**Responsible:** QA Engineer

---

### NIST AI RMF Alignment (Agentic Profile)

#### Check 6: GOVERN Function (Identity + Authorization) Implemented

**Requirement:** NIST Agentic Profile requires cryptographic agent identity + tool authorization per action.

**SMAOS Test:**
- [ ] Agent identity: Ed25519 public key tied to agent_name/version/owner (in KMS)
- [ ] Tool authorization: Agent → Tool binding in policy database (e.g., "hotel_agent" can call "book_reservation" but not "export_gdpr_data")
- [ ] Test: Attempt unauthorized tool invocation; system blocks + logs
- [ ] Documentation: "SMAOS Identity & Authorization Implementation" (reference NIST Agentic Profile v1)

**Validation Timeline:** Oct 2026

**Responsible:** Engineer

---

### Insurance Acceptance (AI Security Rider)

#### Check 7: Intent Verification Reduces AI Liability Insurance Premium

**Requirement:** Insurance underwriters offer AI Security Riders with premium reduction if pre-execution governance present. Intent verification qualifies.

**SMAOS Test:**
- [ ] Outreach: Contact 3-5 AI liability insurers (Chubb, AIG, XL Catlin) with SMAOS proof
- [ ] Underwriter interview: "Does intent verification reduce risk in your underwriting model?"
- [ ] Quote request: Get premium estimates with vs. without SMAOS
- [ ] Documentation: "Insurance companies accept SMAOS Intent Verification as risk mitigation"

**Success Criteria:** ≥2 insurers confirm premium reduction (e.g., 10-20% discount)

**Validation Timeline:** Nov 2026

**Responsible:** Business Development

---

## PHASE 2B: FEDERATED GAAS (TARGET: Q1 2027)

### GDPR Data Residency Checks

#### Check 8: Multi-Region Harness Enforces GDPR Data Residency Rules

**Requirement:** GDPR Art. 44-49 restricts data transfers outside EU. SMAOS must validate residency compliance before processing.

**SMAOS Test:**
- [ ] EU Region: Training data sourced from EU; processed in EU region; no transfers outside (✅ pass)
- [ ] US Region: Data via EU-US DPF (compliant); supplementary measures (encryption at rest) implemented; audit trail shows data origin
- [ ] China Region: Data localization enforced; no data export; CAC compliance validated
- [ ] Test: Attempt to move EU data to US without DPF; system blocks + alerts admin
- [ ] Test: Move US data via DPF with supplementary measures; system allows + logs

**Success Criteria:** 100% correct residency enforcement; 0 policy violations

**Validation Timeline:** Dec 2026 - Jan 2027

**Responsible:** Infrastructure Engineer

---

#### Check 9: Data Origin Tracking (Provenance) Meets GDPR Art. 6 + AI Act §10

**Requirement:** GDPR Art. 6 requires lawful basis tracking; AI Act §10 requires training data documentation (origin, consent basis, purpose).

**SMAOS Test:**
- [ ] Data provenance log: For each training data sample: {source, date_collected, jurisdiction_origin, consent_basis, purpose}
- [ ] Example: 10,000 customer records → log shows {50% EU consent, 30% US market research, 20% public data}
- [ ] Query capability: "Show all training data from China" → returns {count, residency_location, consent_basis}
- [ ] Test: DPA requests data provenance for 1,000 training samples; system delivers within 24 hours

**Success Criteria:** Provenance query latency <100ms; 100% accuracy on origin tracking

**Validation Timeline:** Jan 2027

**Responsible:** Data Engineer

---

### CAC 3.0 Compliance (China) Checks

#### Check 10: Anthropomorphic AI Services Comply with Jul 15, 2026 Rules

**Requirement:** CAC Interim Measures (Anthropomorphic AI) mandate: content governance, cybersecurity, PII protection, anti-fraud, ethics review, emergency response.

**SMAOS Test:**
- [ ] Content governance: System blocks outputs that violate CAC prohibited content (hate speech, disinformation, etc.)
- [ ] Data security: Encryption at rest in China region; HSM for key material; audit log
- [ ] PII protection: System redacts personal data from logs; retains only non-PII features
- [ ] Anti-fraud: System detects & logs suspicious patterns (e.g., repeated failed authentication attempts)
- [ ] Ethics review: Documentation: "SMAOS Anthropomorphic AI Harness reviewed by ethics committee [names, dates]"
- [ ] Emergency response: Documented shutdown procedure; tested to confirm <5min kill-switch activation
- [ ] CAC filing: Registration submitted to CAC with technical documentation

**Success Criteria:** All controls implemented + tested; CAC filing accepted

**Validation Timeline:** Sep-Oct 2026 (before Phase 2B CAC deployment)

**Responsible:** Compliance Officer + Engineer

---

#### Check 11: Data Localization Enforced for China Deployments

**Requirement:** CAC requires anthropomorphic AI data + models hosted on Chinese infrastructure (no cloud export).

**SMAOS Test:**
- [ ] Alibaba Cloud / Baidu Cloud deployment tested: Model weights + training data remain in-region
- [ ] Cross-region transfer prevention: Attempt to replicate CN data to US region; system blocks
- [ ] Audit: Third-party verifies data never leaves CN region (e.g., network monitoring)
- [ ] Test: Simulate Alibaba Cloud partner scenario; end-to-end harness deployment on Alibaba infrastructure

**Success Criteria:** 100% data locality enforcement; 0 unauthorized transfers

**Validation Timeline:** Oct-Nov 2026

**Responsible:** Infrastructure Engineer

---

### Multi-Region Policy Federation Checks

#### Check 12: Policy Database Supports Region-Specific Rules

**Requirement:** Phase 2B must support different policies per region (EU AI Act ≠ CAC ≠ NIST).

**SMAOS Test:**
- [ ] Policy structure: `{region: {jurisdiction: [rules]}}` — e.g., `policy["EU"]["DE"]` returns German DPA rules
- [ ] Policy loading: Agent requests policy at startup; harness loads region-specific rules dynamically
- [ ] Conflict detection: If conflicting rules (e.g., EU GDPR + CAC localization), system flags conflict + defaults to most restrictive
- [ ] Policy versioning: Track policy versions; update rules without redeploying agents

**Success Criteria:** Policy loading <500ms; conflict detection 100% accurate

**Validation Timeline:** Dec 2026

**Responsible:** Engineer

---

### Insurance Product Validation (Multi-Region)

#### Check 13: Insurance Companies Accept Multi-Region Proof Model

**Requirement:** Insurance underwriters validate that SMAOS multi-region data residency proof reduces liability risk.

**SMAOS Test:**
- [ ] Underwriter interview: "Does cryptographic proof of data residency compliance reduce risk in your underwriting?"
- [ ] Use case: "EU hotel with US AI backend (via DPF) + cryptographic proof of compliance"
- [ ] Quote: Premium estimate with vs. without SMAOS multi-region proof
- [ ] Documentation: Case study published (with insurer consent)

**Success Criteria:** ≥2 insurers confirm multi-region proof is acceptable risk mitigation

**Validation Timeline:** Jan-Feb 2027

**Responsible:** Business Development

---

## PHASE 2C: COMPLIANCE AUTOMATION (TARGET: Q2 2027)

### Annex IV Auto-Dossier Generation Checks

#### Check 14: Auto-Generated Dossier Meets EU AI Act Annex IV Requirements

**Requirement:** Annex IV lists 9 sections required in conformity dossier for high-risk AI. SMAOS must auto-generate all 9.

**SMAOS Test:**
- [ ] Section 1 (General description): System generates from agent_config + use_case metadata
- [ ] Section 2 (Intended purpose): Auto-populated from agent documentation
- [ ] Section 3 (Regulatory status): System identifies if system is Annex III or embedded product (Annex I); applies rules accordingly
- [ ] Section 4 (Risk management summary): Sourced from risk register (Check 4)
- [ ] Section 5 (Data governance): Auto-filled from provenance logs (Check 9)
- [ ] Section 6 (Human oversight record): Extracted from human approval logs (Check 5)
- [ ] Section 7 (Testing & validation): Auto-generated from test suite results
- [ ] Section 8 (Post-market monitoring plan): Template-based; customized per sector
- [ ] Section 9 (Competency of testers): List of external auditors / testers documented
- [ ] Manual QA: 5 dossiers reviewed by compliance lawyer; confirm all 9 sections present + compliant

**Success Criteria:** 9/9 sections present; ≥90% information accuracy (per lawyer review)

**Validation Timeline:** Mar-Apr 2027

**Responsible:** Engineer + Compliance Officer

---

#### Check 15: Dossier Cryptographic Signature Valid

**Requirement:** Dossier must be signed with SMAOS KMS key (Ed25519); signature must be verifiable by auditors/regulators.

**SMAOS Test:**
- [ ] Dossier generation → cryptographic signature with timestamp authority (TSA)
- [ ] Signature verification: Third party (e.g., DPA, auditor) verifies signature using public key
- [ ] Tamper detection: Modify dossier; signature verification fails
- [ ] Timestamping: Timestamp authority proves dossier was signed at specific time (immutable proof)
- [ ] KMS backup: Signing key backed up in HSM; recovery tested

**Success Criteria:** Signature verifiable by any third party; timestamp authority accepted by DPA

**Validation Timeline:** Mar-Apr 2027

**Responsible:** Engineer + Security

---

#### Check 16: Compliance Automation Works for Hotel Pilot (Phase 1 Use Case)

**Requirement:** Phase 2C target is hotel credit scoring pilot from Phase 1. Dossier generation must work end-to-end for this use case.

**SMAOS Test:**
- [ ] Hotel agent (credit scoring) logs generated during Phase 1 pilot (available)
- [ ] SMAOS compliance automation imports these logs
- [ ] Auto-generated dossier created for hotel agent
- [ ] DPA validation: DPA (or external auditor) reviews dossier; confirms Annex III compliance
- [ ] Documentation: Hotel case study published ("Hotel credit scoring AI passes Annex III conformity test")

**Success Criteria:** Dossier generated in <5min from logs; DPA confirms compliance

**Validation Timeline:** Feb-Mar 2027

**Responsible:** Engineer + Compliance Officer

---

#### Check 17: Compliance Automation Extends to Automotive (Annex I) Scenario

**Requirement:** Annex I (embedded AI in products) requires different dossier format than Annex III (standalone). Phase 2C must support both.

**SMAOS Test:**
- [ ] Test scenario: Glass manufacturing AI (embedded in windshield product)
- [ ] Dossier generated for Annex I (different sections vs. Annex III)
- [ ] Type-approval documentation: Dossier includes ISO 26262 (functional safety) + type-approval reference
- [ ] Third-party validation: Notified body reviews dossier (e.g., TÜV SÜD)

**Success Criteria:** Annex I dossier generated correctly; notified body confirms format acceptable

**Validation Timeline:** Apr-May 2027

**Responsible:** Engineer + Compliance Officer

---

### CAC Compliance Dossier Checks (China)

#### Check 18: Compliance Automation Generates CAC Filing Dossier

**Requirement:** CAC requires quarterly reporting + ethics review documentation for anthropomorphic AI agents. Phase 2C must auto-generate this.

**SMAOS Test:**
- [ ] CAC filing format: Dossier includes required sections (content governance log, security audit, PII protection log, anti-fraud log, ethics review)
- [ ] Auto-generation: System extracts from harness logs; populates CAC filing template
- [ ] Test: Generate Q3 2026 CAC filing for pilot anthropomorphic agent
- [ ] CAC submission: File with CAC (or pre-test with Chinese compliance counsel)

**Success Criteria:** CAC filing generated in <10min; accepted by CAC

**Validation Timeline:** Sep-Oct 2026 (before Phase 2C formal launch)

**Responsible:** Engineer + Compliance Officer

---

#### Check 19: KMS Signing Meets Chinese Cryptographic Standards

**Requirement:** China may require SM2 (national standard) vs. Ed25519. Phase 2C must support both.

**SMAOS Test:**
- [ ] Dual signing: Dossiers signed with both Ed25519 (international) + SM2 (Chinese)
- [ ] SM2 implementation: Tested on Alibaba Cloud infrastructure
- [ ] Key management: SM2 keys stored in Chinese HSM (Alibaba Cloud KMS)
- [ ] Regulatory acceptance: Chinese compliance counsel confirms SM2 approach acceptable

**Success Criteria:** Dual-signed dossiers; China regulators accept both signatures

**Validation Timeline:** Oct-Nov 2026

**Responsible:** Security Engineer + Legal

---

### Insurance Product Validation (Compliance Automation)

#### Check 20: Insurance Companies Will Underwrite Auto-Generated Dossiers

**Requirement:** Insurance companies must accept SMAOS auto-generated Annex IV dossier as "proof of compliance" for underwriting.

**SMAOS Test:**
- [ ] Insurer outreach: Contact 3-5 liability insurers with sample dossier
- [ ] Underwriter feedback: "Is this dossier sufficient proof for compliance coverage?"
- [ ] Premium: Quote with auto-generated dossier vs. without
- [ ] Documentation: Insurance company letter of acceptance ("We accept SMAOS auto-generated dossiers")

**Success Criteria:** ≥2 insurers explicitly accept auto-generated dossiers; premium reduction confirmed

**Validation Timeline:** Apr-May 2027

**Responsible:** Business Development

---

## POST-PHASE-2 VALIDATION (GATE BEFORE SERIES A)

#### Check 21: CISO Advisory Board Attestation

**Requirement:** Before Series A, validate that CISOs from Phase 1 pilots accept SMAOS governance architecture as production-ready.

**SMAOS Test:**
- [ ] Recruit 3-5 CISOs from Phase 1 pilot customers (hotel, glass manufacturing, finance)
- [ ] Formal attestation: "We deploy SMAOS harness in production; we accept cryptographic proof for compliance defense"
- [ ] Board meeting: Present harness architecture; get formal sign-off
- [ ] Case studies: Publish 3 CISO quotes + company logos (with permission)

**Success Criteria:** ≥3 CISO attestations; at least 2 publicly attributable quotes

**Validation Timeline:** Nov 2026 (before Series A fundraising)

**Responsible:** CEO + Chief Customer Officer

---

#### Check 22: Regulatory Affair Officer Engaged (Pre-Series A)

**Requirement:** Before Series A, hire or contract a Regulatory Affairs Officer to formalize relationships with DPAs, CAC, NIST.

**SMAOS Test:**
- [ ] Hire: Head of Regulatory Affairs (1 FTE) OR engage contract firm (Morrison Foerster, Bird & Bird)
- [ ] DPA relationship: Quarterly briefings with key DPAs (DE, FR, IE)
- [ ] CAC relationship: Liaison with Cyberspace Administration of China (via partner law firm)
- [ ] NIST relationship: Participate in AI Standards Initiative working groups

**Success Criteria:** Regulatory affairs role filled; relationships initiated with ≥3 key regulators

**Validation Timeline:** Oct-Nov 2026

**Responsible:** CEO + HR

---

#### Check 23: Independent Security Audit (Compliance Automation)

**Requirement:** Before Phase 2 closes, conduct independent security audit of harness + proof layer.

**SMAOS Test:**
- [ ] Vendor: Engage Big 4 audit firm (Deloitte, PwC) or specialized firm (Trail of Bits, Cure53)
- [ ] Scope: Harness architecture + KMS integration + cryptographic proof generation
- [ ] Deliverable: Security audit report; identify critical/medium/low findings
- [ ] Remediation: Critical findings fixed before Phase 2 close; document remediation

**Success Criteria:** Independent audit completed; ≤3 critical findings; all remediable

**Validation Timeline:** Mar-Apr 2027

**Responsible:** CTO

---

## SUMMARY TABLE: CHECKLIST STATUS & TIMELINE

| Check | Category | Phase | Status | Target Date | Owner |
|-------|----------|-------|--------|------------|-------|
| 1 | GDPR Art. 22 alignment | 2A | 🔲 Pending | Oct 2026 | Legal |
| 2 | Intent accuracy ≥90% | 2A | 🔲 Pending | Oct 2026 | ML Eng |
| 3 | GDPR Art. 13 (explanation) | 2A | 🔲 Pending | Nov 2026 | PM |
| 4 | Risk register (intent) | 2A | 🔲 Pending | Oct 2026 | Compliance |
| 5 | Human oversight workflow | 2A | 🔲 Pending | Oct 2026 | QA |
| 6 | NIST GOVERN (auth) | 2A | 🔲 Pending | Oct 2026 | Eng |
| 7 | Insurance rider reduction | 2A | 🔲 Pending | Nov 2026 | BD |
| 8 | GDPR residency enforcement | 2B | 🔲 Pending | Jan 2027 | Infra Eng |
| 9 | Data provenance tracking | 2B | 🔲 Pending | Jan 2027 | Data Eng |
| 10 | CAC anthropomorphic rules | 2B | 🔲 Pending | Oct 2026 | Compliance |
| 11 | China data localization | 2B | 🔲 Pending | Nov 2026 | Infra Eng |
| 12 | Policy federation | 2B | 🔲 Pending | Dec 2026 | Eng |
| 13 | Insurance multi-region | 2B | 🔲 Pending | Feb 2027 | BD |
| 14 | Annex IV auto-dossier | 2C | 🔲 Pending | Apr 2027 | Eng |
| 15 | Dossier signature | 2C | 🔲 Pending | Apr 2027 | Eng |
| 16 | Hotel pilot dossier | 2C | 🔲 Pending | Mar 2027 | Eng |
| 17 | Annex I dossier (glass) | 2C | 🔲 Pending | May 2027 | Eng |
| 18 | CAC filing auto-gen | 2C | 🔲 Pending | Oct 2026 | Compliance |
| 19 | SM2 signing | 2C | 🔲 Pending | Nov 2026 | Security |
| 20 | Insurance auto-dossier | 2C | 🔲 Pending | May 2027 | BD |
| 21 | CISO attestation | Post-2 | 🔲 Pending | Nov 2026 | CEO |
| 22 | Regulatory affairs | Post-2 | 🔲 Pending | Oct 2026 | CEO |
| 23 | Security audit | Post-2 | 🔲 Pending | Apr 2027 | CTO |

---

## RELEASE GATING RULES

**Phase 2A Release Gate (Q4 2026):**
- Checks 1-7 must be ✅ (7/7)
- Phase 2A can launch

**Phase 2B Release Gate (Q1 2027):**
- Checks 8-13 must be ✅ (6/6)
- Phase 2A + Phase 2B can integrate

**Phase 2C Release Gate (Q2 2027):**
- Checks 14-20 must be ✅ (7/7)
- Phase 2A + 2B + 2C full integration

**Series A Gate (Sep 2026 - onward):**
- Checks 21-23 must be ✅ (3/3) OR in progress with clear timeline
- Series A pitch deck includes compliance validation summary

---

## SOURCES

1. [GDPR Art. 22 — Automated Decision-Making](https://gdpr-info.eu/articles/automated-decision-making/)
2. [EU AI Act Annex III — High-Risk Systems](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023R1232)
3. [GDPR Art. 13 — Right to Explanation](https://gdpr-info.eu/articles/right-to-explanation/)
4. [NIST AI RMF Agentic Profile](https://labs.cloudsecurityalliance.org/agentic/agentic-nist-ai-rmf-profile-v1/)
5. [CAC Anthropomorphic AI Interim Measures](https://aigovernance.com/news/chinas-anthropomorphic-ai-rules-take-effect-july-2026-setting-new-bar-for-companion-and-interaction-services/)
6. [EU AI Act Annex IV — Conformity Dossier Requirements](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023R1232)
7. [GDPR Art. 44-49 — International Data Transfers](https://gdpr-info.eu/chapter-5/)
8. [ISO 26262 — Functional Safety for Automotive](https://www.iso.org/standard/68383.html)
