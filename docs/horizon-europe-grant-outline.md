# Horizon Europe Grant Proposal Outline
## "Sovereign AI Governance: Structural Compliance Infrastructure for the EU AI Act"
**Programme:** Horizon Europe — Cluster 4 (Digital, Industry and Space)
**Call:** HORIZON-CL4-2026-HUMAN-01 (Human-Centric AI)
**Budget requested:** €2,000,000
**Duration:** 36 months (Jan 2027 – Dec 2029)
**Lead applicant:** SovereignNexus (Irish EU subsidiary)
**Submission deadline:** Nov 15, 2026

---

## 1. Executive Summary

This project delivers open, production-grade reference infrastructure for EU AI Act compliance, with particular focus on Articles 13 (transparency), 14 (human oversight), and 17 (quality management / fail-closed governance). The AXIOM Capsule architecture — developed and battle-tested in production — provides the structural patterns that make compliance a native property of AI systems rather than an auditing afterthought.

The project produces:
1. An open-source compliance reference library (Rust, TypeScript bindings) implementing Articles 9–23
2. A formal verification framework that proves fail-closed properties hold under adversarial conditions
3. A deployed reference implementation in 3 EU Member State government agencies
4. A technical contribution to the EU AI Act Code of Practice (Article 56)

**Impact:** Reduce the cost of EU AI Act compliance for SME AI developers from €200K+ (current estimate for bespoke integration) to under €5K (using the reference library).

---

## 2. Problem Statement

### 2.1 The Compliance Integration Burden

The EU AI Act (Regulation 2024/1689) requires high-risk AI systems to implement:
- Risk management systems (Art. 9)
- Signed audit trails with 6-month minimum retention (Art. 12)
- Per-decision explainability for deployers (Art. 13)
- Fail-closed human oversight with structured appeal mechanisms (Art. 14)
- Quality management ensuring the safest outcome on failure (Art. 17)
- Cybersecurity controls aligned with NIS2 (Art. 23)

For AI systems not designed with these requirements from the ground up, satisfying them requires deep architectural changes. Estimates from EU AI Act impact assessments (European Commission, 2024) indicate compliance costs of €200K–€500K per system for existing large-scale AI deployments.

### 2.2 The SME Gap

SMEs developing AI systems in Europe cannot afford these compliance costs. This drives one of two outcomes:
1. SMEs misclassify their systems as lower risk (creating regulatory liability)
2. SMEs avoid EU markets entirely (capital and talent flight to the US and Asia)

Neither outcome is compatible with the EU's stated goal of becoming the global leader in trustworthy AI.

### 2.3 The Reference Infrastructure Gap

The EU AI Office has guidance documents but no production-grade reference implementations. When a startup asks "show me what Article 14 looks like in code," there is no answer. This project fills that gap.

---

## 3. Proposed Solution

### 3.1 AXIOM Compliance Reference Library (Open Source)

We will extract and generalize the core compliance mechanisms from the AXIOM codebase into a standalone, open-source library:

**Module 1: Governance Core (Article 9, 14, 17)**
- `HumanOversightGate` — fail-closed approval gate with configurable timeout
- `CovenantFirewall` — policy enforcement engine with structural deny-on-error
- `RiskManagementRecord` — runtime risk tracking and mitigation logging

**Module 2: Transparency Layer (Article 13, 12)**
- `AuditLogEntry` — HMAC-SHA256 chained log with 180-day retention floor
- `TransparencyRecord` — per-deployment capabilities/limitations/data sources declaration
- Decision explainability serializer — feature contribution attribution per decision

**Module 3: Security Layer (Article 23 + NIS2 Art. 21)**
- AES-256-GCM capsule encryption
- mTLS configuration templates
- Certificate lifecycle management
- Namespace isolation enforcement patterns

**Module 4: GDPR Integration (for simultaneous GDPR + AI Act compliance)**
- `ConsentRecord` with `PurposeBasis` legal basis tracking
- Right-to-erasure via cryptographic key deletion
- Right-to-portability JSON export

**Language support:** Rust (primary), TypeScript bindings (Month 6), Python bindings (Month 12)

### 3.2 Formal Verification Framework

We will develop formal proofs (using TLA+ and/or Coq) that the fail-closed properties of the Covenant Firewall and HumanOversightGate are invariant under:
- Byzantine fault conditions
- Adversarial timing attacks
- Partial network failures

This addresses the gap between "we claim this is fail-closed" and "we can prove this is fail-closed." For EU government procurement, the latter is a qualitatively different assurance.

### 3.3 Deployed Reference Implementations

We will deploy the reference library in 3 EU Member State government agency AI systems as part of the project:
- Germany: 1 federal agency (BSI or federal IT service)
- France: 1 DINUM-linked agency
- Spain: AESIA itself (AI supervisory authority using the reference implementation for its own oversight work)

Each deployment produces a case study documenting the compliance gap before AXIOM and the evidence of compliance after.

### 3.4 EU AI Act Code of Practice Contribution

We will submit the formal verification framework and reference library as a technical contribution to the EU AI Office's AI Act Code of Practice process (Article 56 GPAI Code; Article 96 for high-risk AI guidance). The goal is for the fail-closed governance pattern to become an explicitly endorsed compliance path.

---

## 4. Work Plan

### WP1: Architecture Extraction and Open-Source Release (Months 1–6)
- M1.1: Extract compliance modules from AXIOM codebase into standalone library
- M1.2: Write test suite covering all Article 9–23 obligation surfaces
- M1.3: TypeScript bindings and developer documentation
- M1.4: First open-source release (v0.1.0) on GitHub + EU Open Source Observatory

### WP2: Formal Verification (Months 4–12)
- M2.1: TLA+ specification of HumanOversightGate invariants
- M2.2: TLA+ specification of Covenant Firewall deny-on-error invariant
- M2.3: Coq proof of audit trail tamper-detection completeness
- M2.4: Publication in IEEE/ACM venue on AI governance formal methods

### WP3: Member State Deployments (Months 9–24)
- M3.1: Germany deployment — BSI federal pilot (3-month evaluation, 12-month production)
- M3.2: France deployment — DINUM agency pilot
- M3.3: Spain deployment — AESIA internal governance layer
- M3.4: Case study publications for each deployment

### WP4: EU AI Office Engagement and Code of Practice (Months 6–36)
- M4.1: Submit reference library to EU AI Office consultation
- M4.2: Technical guidance note co-authored with EU AI Office staff
- M4.3: Contribution to AI Act Code of Practice annex (Article 56/96)
- M4.4: Annual workshop for EU AI Act national authorities (practical compliance training)

### WP5: Dissemination and Ecosystem Building (Months 12–36)
- M5.1: Developer documentation portal (axiom-compliance.eu)
- M5.2: Training materials for SME AI developers (5-language coverage)
- M5.3: Integration with European AI testing and experimentation facilities (AI TEFs)
- M5.4: Open standard proposal to CEN/CENELEC for AI governance layer interoperability

---

## 5. Budget Breakdown

| Work Package | Personnel | Equipment | Travel | Other | Total |
|---|---|---|---|---|---|
| WP1: Architecture extraction + OSS | €350,000 | €20,000 | €5,000 | €25,000 | €400,000 |
| WP2: Formal verification | €280,000 | €10,000 | €15,000 | €20,000 | €325,000 |
| WP3: Member State deployments | €420,000 | €80,000 | €40,000 | €60,000 | €600,000 |
| WP4: EU AI Office engagement | €180,000 | €0 | €30,000 | €15,000 | €225,000 |
| WP5: Dissemination | €150,000 | €10,000 | €20,000 | €20,000 | €200,000 |
| Project management + audit | €200,000 | €0 | €10,000 | €40,000 | €250,000 |
| **TOTAL** | **€1,580,000** | **€120,000** | **€120,000** | **€180,000** | **€2,000,000** |

---

## 6. Consortium

**Lead:** SovereignNexus (Ireland) — architecture, formal verification, open-source library
**Partner 1:** [German university TBD — Technische Universität Berlin / DFKI] — formal verification WP2, Germany deployment WP3
**Partner 2:** [French research lab TBD — Inria] — France deployment, DINUM relationships
**Partner 3:** AESIA (Spain) — Spain deployment, regulatory authority perspective on WP4

Note: Consortium finalization by Sep 30, 2026. AESIA participation pending formal expression of interest.

---

## 7. Impact Statement

### 7.1 Expected Outcomes

| Outcome | Target | Measurement |
|---|---|---|
| Open-source library downloads | 10,000 in Year 1 | GitHub metrics |
| SME AI developers using library | 500 by project end | Self-reported via developer survey |
| Reduction in per-system compliance cost | From €200K to <€5K | External audit of 10 SME cases |
| EU government deployments | 3 (DE, FR, ES) | Signed contracts |
| AI Act Code of Practice contributions | 1 technical annex | EU AI Office publication |
| Academic publications | 4 (formal verification + deployments) | Published papers |

### 7.2 Strategic Alignment

This project directly supports:
- **EU AI Strategy 2021** — "AI made in Europe that can be trusted"
- **AI Act recital 47** — "SMEs should be supported in their compliance efforts"
- **Digital Compass 2030** — EU as global leader in trustworthy AI
- **NIS2 Directive** — Cybersecurity baseline for essential entities using AI

### 7.3 Sustainability Beyond Grant

The open-source library will be maintained as a public good by SovereignNexus. Commercial government contracts (Section 5 of `regulatory-moat-strategy.md`) fund continued development. The grant provides the credibility and network to convert commercial pilots to multi-year contracts.

---

## 8. Submission Checklist

- [ ] Technical proposal (Part B): This document expanded to 30 pages
- [ ] Financial capacity evidence: Irish subsidiary incorporation docs
- [ ] Ethics self-assessment: Article 14 fail-closed mechanism — no additional ethics concerns
- [ ] Data management plan: All project data stored EU-only; open-access publications
- [ ] Consortium agreement: In negotiation with TU Berlin / DFKI, Inria, AESIA
- [ ] Letters of support: EU AI Office (request by Aug 15), BSI (request by Sep 1), AESIA (request by Sep 15)
- [ ] Submission portal: ec.europa.eu/info/funding-tenders/opportunities/portal

**Internal deadline for draft complete:** Nov 1, 2026
**Final review:** Nov 10, 2026
**Submission:** Nov 15, 2026 (system deadline; submit by Nov 12 for buffer)
