# Pilot Deal Term Sheet — SovereignNexus × [Prime Partner]
**Version:** 1.0 Draft (Negotiation Starting Position)  
**Date:** [INSERT]  
**Parties:**
- **Provider:** SovereignNexus Ltd. (Ireland) — Andrii Leukhin, CEO
- **Customer:** [Rafael Advanced Defense Systems / Elbit Systems / IAI-ELTA] — [Name], [Title]

**Governing Law:** Israeli law (with US export control addendum governed by US federal law)  
**Jurisdiction:** Tel Aviv District Court  
**Status:** DRAFT — For Discussion Only. Not binding until countersigned.

---

## 1. Engagement Summary

| Parameter | Value |
|-----------|-------|
| Engagement Type | Proof of Concept (PoC) with Option for Production License |
| PoC Duration | 90 days from Effective Date |
| PoC Fee | €[180,000 / 240,000 / 300,000] (select tier) |
| Production Option | Customer may elect to license for production within 12 months of PoC completion |
| Effective Date | [INSERT] |
| Target LOI Signature | Sep 30, 2026 |

---

## 2. Scope of Work

### 2.1 PoC Deliverables (SovereignNexus obligations)

| # | Deliverable | Timeline |
|---|-------------|---------|
| D1 | Behavioral Firewall deployment on Customer test environment | Day 1-14 |
| D2 | Integration with [identified Customer AI pipeline] | Day 7-30 |
| D3 | Governance Capsule configuration (audit trail, deterministic replay) | Day 14-45 |
| D4 | Anomaly detection baseline calibration | Day 30-60 |
| D5 | PoC results report + production readiness assessment | Day 85-90 |

### 2.2 Customer Obligations

- Provide test environment (air-gapped or secure enclave) with agreed API access
- Designate Technical Champion (primary integration contact) within 5 business days of Effective Date
- Provide 2x integration engineers for joint work (Day 1-30)
- Security clearance/vetting of SovereignNexus personnel who require on-site access (if applicable)
- Timely review of deliverables (10 business day SLA per deliverable)

### 2.3 Out of Scope

- Source code transfer (explicitly excluded)
- Classified data processing by SovereignNexus personnel
- Re-export of technology to third parties (prohibited)
- Integration beyond the single agreed AI pipeline (requires separate SOW)

---

## 3. PoC Success Criteria

*To be jointly agreed and appended as Exhibit A no later than 14 days after Effective Date.*

**Proposed baseline metrics:**

| Metric | Target |
|--------|--------|
| Audit trail coverage | 100% of AI decision events captured |
| Governance overhead latency | <15ms per decision event (p99) |
| Deterministic replay accuracy | 100% replay fidelity on test dataset |
| False-positive mission block rate | <0.1% on agreed test scenarios |
| System availability | 99.5% uptime during PoC period |

**PoC Success:** All 5 metrics met → Customer may exercise Production Option.  
**Partial Success:** 3/5 metrics met → 30-day extension at no additional charge.  
**PoC Failure:** <3/5 metrics met → Customer receives 50% fee refund; no production option.

---

## 4. Fees and Payment

### 4.1 PoC Fee Schedule

| Milestone | Amount | Trigger |
|-----------|--------|---------|
| Contract signature | 40% of PoC fee | Within 5 business days of signing |
| Milestone 1 complete (D3 delivered) | 40% of PoC fee | Customer acceptance of D3 |
| PoC completion (D5 delivered + accepted) | 20% of PoC fee | Customer acceptance of final report |

**Invoice currency:** EUR  
**Payment terms:** Net 15 days from invoice date  
**Late payment:** 1.5% per month on overdue balances

### 4.2 Production License (Optional, Customer Election)

*Exercisable within 12 months of PoC completion date.*

| License Tier | Annual Fee | Scope |
|-------------|-----------|-------|
| **Standard** | €480,000/yr | 1 deployment unit, unlimited users, standard SLA |
| **Enterprise** | €720,000/yr | Up to 5 deployment units, 24/7 SLA, dedicated support |
| **Framework** | €1,200,000/yr | Unlimited deployment units, preferred supplier status, roadmap input |

**PoC fee credit:** 100% of PoC fee credited against Year 1 production license if elected within 12 months.

### 4.3 BIRD Foundation Co-Application (Optional)

If Customer elects to pursue BIRD Foundation joint application:
- SovereignNexus agrees to co-apply as US-side partner
- BIRD grant (up to $4M) allocated: 50% Customer R&D, 50% SovereignNexus development
- PoC fee reduced by 25% if BIRD application is submitted within 60 days of contract signature
- BIRD application costs (filing + US counsel) split equally

---

## 5. Intellectual Property

### 5.1 SovereignNexus IP (Protected)

The following remain exclusively owned by SovereignNexus and are NOT transferred:
- Source code, object code, algorithms, models
- Governance capsule architecture and Merkle-DAG audit chain
- Behavioral firewall rule engine
- Any improvements, derivatives, or modifications made by SovereignNexus during PoC

**License granted:** Non-exclusive, non-transferable, non-sublicensable right to USE the software in binary/API form within Customer's facilities for the PoC period only.

### 5.2 Customer IP (Protected)

- Customer's existing data, systems, operational data remain exclusively Customer's
- Audit logs and governance outputs generated during PoC reside on Customer infrastructure
- SovereignNexus does not retain, copy, or transmit Customer data outside Customer's environment
- SovereignNexus personnel sign Customer's standard NDA and data handling agreement

### 5.3 Joint Outputs

- PoC results report (D5): jointly owned; each party may reference independently
- Integration specifications developed jointly: jointly owned; each party has unrestricted right to use
- Publications/presentations: require mutual written consent

### 5.4 Source Code Escrow (If Required)

*Customer may request source code escrow as release-condition security.*
- Provider: Escrow Associates (or mutually agreed escrow agent)
- Release conditions: SovereignNexus insolvency OR cessation of support obligations
- Escrow cost: split equally

---

## 6. Export Control and Compliance

### 6.1 ITAR/EAR Representations

SovereignNexus represents:
- Technology is classified under EAR jurisdiction (not ITAR)
- No USML (US Munitions List) items included in scope
- Dual-use classification: EAR99 or AT-controlled (as applicable)
- DCMA Basic Exchange Agreement (BEA) coverage for US-Israel technology transfer filed by [DATE]

Customer represents:
- Technology will be used solely within Customer's facilities for agreed purposes
- No re-export or transfer to third parties without written consent + export license review
- Customer is not on any denied party list (OFAC, BIS, DDTC)

### 6.2 Israeli DECA Compliance

- Customer is responsible for any Israeli DECA notification requirements for imported defense-relevant technology
- SovereignNexus will provide reasonable documentation to support Customer's DECA filings

### 6.3 Data Sovereignty

- All Customer data processed during PoC remains in Customer-controlled infrastructure (Israeli territory or IDF-approved environment)
- SovereignNexus has zero access to Customer operational data
- Audit logs generated are Customer property and reside in Customer environment

---

## 7. Confidentiality

- **Mutual NDA:** 5-year term from Effective Date
- **Scope:** All technical, commercial, and operational information exchanged
- **Exceptions:** Publicly known information; independently developed; legally required disclosure (with prior notice)
- **Survival:** Confidentiality obligations survive termination

---

## 8. Term and Termination

| Scenario | Consequence |
|----------|-------------|
| PoC completes successfully | Customer may elect Production Option; no default termination |
| Customer terminates for convenience | Customer pays 100% of fees earned to date; no refund of paid milestones |
| Customer terminates for cause (SovereignNexus material breach, not cured in 30 days) | 50% refund of fees paid |
| SovereignNexus terminates for cause (non-payment, breach of IP/export terms) | All fees paid retained; technology access terminated immediately |
| Force majeure >90 days | Either party may terminate; pro-rated refund of prepaid fees |

---

## 9. Liability

- **Cap:** Total liability capped at 100% of PoC fees paid (for each party)
- **Exclusions:** Neither party liable for indirect, consequential, punitive damages
- **Carve-outs from cap:** IP infringement claims; export control violations; data breach caused by gross negligence

---

## 10. Signature Block

**SovereignNexus Ltd.**  
Signed: ___________________________  
Name: Andrii Leukhin  
Title: CEO  
Date: ___________________________  

**[Customer Legal Name]**  
Signed: ___________________________  
Name: ___________________________  
Title: ___________________________  
Date: ___________________________  

---

## Exhibit A — PoC Success Criteria (To Be Agreed Within 14 Days of Effective Date)

*[Joint completion required]*

## Exhibit B — Technical Architecture Overview

*[Attach: SovereignNexus behavioral firewall + governance capsule technical brief — defense variant]*

## Exhibit C — Export Control Documentation

*[Attach: DCMA BEA confirmation; EAR classification determination; denied party screening certificates]*

## Exhibit D — Security Accreditation Requirements

*[Customer to specify: required clearance levels, physical access protocols, equipment handling requirements]*
