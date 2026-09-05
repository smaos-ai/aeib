# Letter of Intent — SovereignNexus Israeli Defense Partnership

**Effective Date:** June 20, 2026  
**Pilot Period:** 90 days from execution  
**Territory:** Israel (+ authorized allies under framework)  

---

## 1. PARTIES

**SovereignNexus Ltd.** ("Provider")  
A cryptographic governance and swarm attestation platform provider.

**[DEFENSE PARTNER NAME]** ("Customer")  
A governmental, quasi-governmental, or authorized defense contractor entity operating within Israeli jurisdiction.

---

## 2. EXECUTIVE SUMMARY

This Letter of Intent establishes a 90-day pilot engagement for evaluation and integration of SovereignNexus's deterministic AI governance platform. The platform provides:

- **Merkle-DAG cryptographic proof** of AI execution state (immutable, tamper-detectable)
- **Swarm consensus attestation** with <0.5ms latency
- **Pre-execution governance** (decisions logged before action, not after)
- **Air-gapped deployment** (no internet dependency, secure enclaves)

---

## 3. SCOPE OF ENGAGEMENT — PILOT (NON-BINDING)

### 3.1 Measurable Objectives
- ✅ **Merkle-DAG Integrity:** Zero tamper detections in 90-day period; 100% append-only enforcement
- ✅ **Swarm Consensus Latency:** <0.5ms median, <2ms p99 for N-1 attestation
- ✅ **Uptime SLA:** 99.9% availability (max 2.16 hours downtime per month)
- ✅ **Audit Trail Completeness:** 100% of AI decisions logged pre-execution

### 3.2 Pilot Deliverables
| Deliverable | Timeline | Status |
|---|---|---|
| System deployment (dev environment) | Week 1 | Pending |
| Integration with Customer AI systems | Week 2-3 | Pending |
| First attestation chain generated | Week 3 | Pending |
| Monthly compliance audit | Weeks 4, 8, 12 | Pending |
| Final PoC report | Week 13 | Pending |

### 3.3 Resource Commitment
- **Provider:** 1 FTE engineer + access to cryptographic infrastructure
- **Customer:** 1 security officer (oversight) + 1 systems admin (integration)

---

## 4. TECHNICAL SPECIFICATIONS

### 4.1 Deployment Topology
```
[Secure Enclave (Air-Gapped)]
  ├─ SovereignNexus Runtime
  ├─ Merkle-DAG Ledger (append-only)
  ├─ Ed25519 Signing Module
  └─ Swarm Attestation Engine

[Attestation Output]
  ├─ Cryptographic Proof (Merkle root + signature)
  ├─ Decision Log (pre-execution)
  └─ Audit Trail (immutable, tamper-evident)
```

### 4.2 Export Compliance
- **Classification:** ECCN 5D002.c.1 (encryption software for non-military use)
- **License Exception:** ENC (license exception for encryption)
- **OFAC Status:** ✅ Israel cleared (no sanctions implications)
- **ITAR Status:** ✅ Not controlled (no classified defense articles)
- **EAR Status:** ✅ License Exception ENC applies
- **Filing Status:** ✅ No export license required for this classification

**Certification:** This product has been reviewed and classified under U.S. Department of Commerce regulations. Israel is not a sanctioned jurisdiction. No export license is required.

---

## 5. INTELLECTUAL PROPERTY RIGHTS (BINDING)

### 5.1 SovereignNexus IP
- Provider retains all intellectual property in the platform
- Customer receives a **non-exclusive, non-transferable license** for the pilot period
- No source code is transferred; only compiled binaries and API access

### 5.2 Customer IP
- Customer retains all rights to data processed through the platform
- Data is encrypted at rest; Provider has no read access
- Customer may request deletion of data at end of pilot (or continuation)

### 5.3 Confidentiality
- Both parties agree to hold confidential all technical and business information
- Confidentiality obligations survive termination by 2 years
- **Exception:** Publicly disclosed security flaws (CVEs) are not confidential

---

## 6. TERM & TERMINATION (BINDING)

### 6.1 Pilot Term
- **Start Date:** Upon execution of this LOI
- **Duration:** 90 days
- **Auto-Renewal:** No; requires mutual written agreement for continuation

### 6.2 Termination Rights
Either party may terminate the pilot with **15 days' written notice** if:
- Material technical failures occur (>4 hours unplanned downtime in any week)
- Security breach or vulnerability is discovered and cannot be remediated
- Regulatory compliance cannot be achieved

### 6.3 Continuation Path
Upon successful pilot completion, parties may negotiate a **Commercial Agreement** for:
- Expanded deployment (production environment)
- Multi-year license term
- SLA guarantees and support commitments

---

## 7. MANDATORY AIR-GAPPED OPERATION (BINDING)

The system **MUST operate in an air-gapped environment** with the following requirements:

### 7.1 Isolation Requirements
- ✅ No internet connectivity (no DNS, HTTPS, or external API calls)
- ✅ No cloud synchronization (all data remains on-premises)
- ✅ No remote attestation (signing occurs locally, no TPM cloud escrow)
- ✅ Physical isolation from non-defense networks (separate subnet, no bridging)

### 7.2 Data Ingress/Egress
- **Ingress:** USB, secure courier, or airgapped Sneakernet protocols only
- **Egress:** Audit reports exported via encrypted USB or secure courier
- **Attestation Output:** Merkle proofs and signatures exported for external verification

### 7.3 Compliance Verification
- Monthly security assessments to verify air-gap isolation
- No exceptions permitted during pilot period

---

## 8. REPRESENTATIONS & WARRANTIES (BINDING)

**Provider represents that:**
- The platform is free from known security vulnerabilities (as of delivery date)
- The platform complies with ECCN 5D002.c.1 classification
- No export license is required for delivery to Israel
- The platform is designed to prevent tampering and enforce cryptographic integrity

**Customer represents that:**
- It is authorized to receive defense technology under Israeli law
- It will maintain air-gapped operation as specified
- It will not re-export or transfer the technology to unauthorized parties

**DISCLAIMER:** This platform is provided AS-IS. Provider disclaims all warranties of merchantability or fitness for a particular purpose. Customer assumes all risk of use.

---

## 9. FINANCIAL TERMS (NON-BINDING)

### 9.1 Pilot Pricing
- **Pilot Fee:** €0 (zero cost engagement for mutual evaluation)
- **Support:** Included (business hours support via secure email)
- **Infrastructure:** Provider supplies on-premises hardware (or Customer may use own; TBD)

### 9.2 Continuation Pricing (Post-Pilot)
To be negotiated based on:
- Number of AI decisions per month
- Number of swarm nodes
- Uptime SLA requirements
- Support level (24/7 vs. business hours)

**Estimated Range:** €15k–€50k/month (for production deployment)

---

## 10. GOVERNING LAW & DISPUTE RESOLUTION (BINDING)

- **Governing Law:** Laws of the State of Israel
- **Dispute Forum:** Israeli courts (Jerusalem District Court)
- **Mediation:** Before litigation, parties agree to 30-day good-faith mediation

---

## 11. SIGNATURE BLOCK

**FOR SOVEREIGNNEXUS LTD.:**

Signed: _______________________  
Name: _______________________  
Title: _______________________  
Date: _______________________  

**FOR [DEFENSE PARTNER]:**

Signed: _______________________  
Name: _______________________  
Title: _______________________  
Date: _______________________  

---

## APPENDIX A: REGULATORY TIMELINE

| Milestone | Deadline | Owner | Status |
|---|---|---|---|
| System deployment | June 30, 2026 | Provider | Pending |
| EU AI Act Article 10 (data governance) | July 31, 2026 | Both | Pending |
| NIS2 Vulnerability Disclosure Policy | Aug 31, 2026 | Provider | Pending |
| DCMA filing (if required) | July 15, 2026 | Provider | Completed |
| Pilot completion report | Sept 30, 2026 | Provider | Pending |

---

## APPENDIX B: ESCALATION CONTACTS

**SovereignNexus Technical Escalation:**  
[Engineer Name], VP Engineering: [Email] | [Phone]

**SovereignNexus Legal Escalation:**  
[Legal Contact], General Counsel: [Email] | [Phone]

**Customer Security Escalation:**  
[Name], Chief Information Security Officer: [Email] | [Phone]

---

**Document Version:** 1.0  
**Generated:** June 20, 2026  
**Validity:** 30 days from generation (requires refresh for extensions)
