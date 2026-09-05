# Pax Silica Partnership Roadmap — Phase 3 Stream 9

**Date:** June 4, 2026  
**Phase:** 3 Beta Launches  
**Stream:** 9 (Israel Market Entry)  
**Status:** Specification Phase  
**Partnership Start:** July 1, 2026 (subject to Series A close)  
**Budget Allocation:** €10K (from Stream 9 €30K total)  

---

## Executive Summary

**Mission:** Establish technical + commercial partnership with Pax Silica to accelerate Israeli sovereign AI market entry while preserving Axiom Protocol's IP and covenant.

**Strategic Positioning:** Combine Axiom's governance + cryptographic enforcement with Pax Silica's Israeli defense/intelligence relationships → Uncontested market position in sovereign AI for civil defense + security tech.

**Revenue Model:** 3% of Israeli ARR (Year 1 est. €50K–100K) → Pax Silica as distribution partner.

---

## 1. Pax Silica Overview

### 1.1 Company Profile

**Focus:** Israeli sovereign AI infrastructure for defense + security applications  
**Stage:** Pre-seed (as of Jun 2026)  
**Investors:** Yozma Fund, Israeli Defense Ministry (grants)  
**Advantage:** Deep relationships with IDF, Mossad, Shin Bet  
**Risk:** Regulatory sensitivity (ITAR export controls, Israeli security clearances)  

---

### 1.2 Strategic Fit

| Dimension | Axiom | Pax Silica | Combined |
|---|---|---|---|
| **Governance** | Cryptographic enforcement, decentralized | Centralized auth (Israeli state standard) | Hybrid: local governance layer + state integration |
| **Cryptography** | Post-quantum, open standard | Israeli classification standard | Upgrade to hybrid (quantum-safe + classified) |
| **Go-to-Market** | Creator/community segment | Government/defense segment | Full stack: creators → enterprises → state |
| **IP** | Open-source + Swiss Foundation | Proprietary + Israeli government | Joint IP with clear boundaries (see below) |

---

## 2. Technical Integration Points

### 2.1 Shared Infrastructure

**Compute & Storage:**
- Axiom: EU cloud (Nebius), local-first, open deployment
- Pax Silica: Israeli air-gapped servers, TEMPEST-compliant, classified networks
- Integration: VPN tunnel (IPsec) between Nebius + Tel Aviv, encrypted handshake for policy sync

**Cryptographic Standards:**
- Axiom: ChaCha20, post-quantum (ML-KEM + ML-DSA)
- Pax Silica: SHA-256, RSA-4096 (Israeli defense standard as of 2026)
- Integration: Dual-stack mode — Axiom protocol uses post-quantum internally, bridge layer translates to RSA-4096 for state operations

**Data Schema Alignment:**
- Axiom: `SovereignIdentity` (Ethereum-compatible, Optimism L2)
- Pax Silica: `StateIdentity` (Israeli PKI-based, hardware token)
- Integration: Mapping layer — SovereignIdentity can delegate to StateIdentity for government-sponsored actions

**Audit Trail Interoperability:**
- Both systems log to Merkle chains (different root stores)
- Daily cross-chain verification: Axiom audit roots signed by Pax Silica, vice versa
- Quarterly public report: "Governance Audit Fusion" (combined Merkle proof)

### 2.2 Integration Architecture

```
Creator Layer (Axiom)
    ↓
Creator Dashboard → AP2 Ledger → Settlement Engine
    ↓
[INTEGRATION BOUNDARY]
    ↓
Civil Defense Layer (Pax Silica)
    ↓
ReBAC + Temporal Guard → Policy Decision → Merkle Audit
    ↓
[INTEGRATION BRIDGE]
    ↓
Israeli State Integration (IDF/Mossad)
    ↓
State cryptographic handoff → Classified networks
```

**Bridge Design:**
- **Inbound:** State mandates fed to ReBAC via API (time-windowed, revocable)
- **Outbound:** Policy decisions exported to classified network (gzipped, signed, air-gap safe)
- **Fallback:** If bridge fails, systems revert to local-only mode (no state compromise)

---

## 3. IP Protection & Trade Secret Frameworks

### 3.1 Shared IP Model

**Axiom IP (Protected):**
- Core protocol (AP2 Ledger, ReBAC engine, cryptographic proofs)
- Creator settlement mechanics (1%/99% split)
- Swiss Foundation governance layer

**Pax Silica IP (Protected):**
- State authentication & authorization
- Classified protocol extensions (not disclosed)
- Defense-specific compliance frameworks

**Joint IP (Shared, Confidential):**
- Bridge API (integration points, documented)
- Dual-stack crypto mode (post-quantum ↔ RSA translation)
- Audit trail fusion (daily cross-chain verification)

**Open Source (Published):**
- Integration tests + example code (non-classified)
- Merkle chain verification library (open standard)
- Creator SDK (existing, unchanged)

### 3.2 Trade Secret Framework

**Classification:**
```
LEVEL 1 (Open): Creator SDK, audit verification library
LEVEL 2 (Confidential): Bridge API, dual-crypto stack design
LEVEL 3 (Secret): State integration details, classified protocol extensions
LEVEL 4 (Classified): IDF/Mossad operational parameters
```

**Protection Mechanisms:**
- **Encrypted repos:** Pax Silica IP stored in private GitHub + hardware security module (HSM) key management
- **Access control:** Only Axiom + Pax Silica engineers with Israeli security clearance can access Level 3+
- **Audit trail:** All IP access logged, quarterly review
- **NDA + IP Agreement:** Signed before Jul 1 (dependency for partnership start)
- **Escrow:** If partnership ends, IP returns to original owner + 2-year non-compete

### 3.3 Provisional Patent Alignment

**Patent Strategy:**
- Axiom: File provisional patent on core ReBAC + AP2 mechanism (May 2026, already done)
- Pax Silica: File provisional patent on state integration bridge (Jul 2026)
- Joint Patent: Dual-crypto translation layer (optional, lower priority)

**Enforcement:**
- Axiom retains exclusive license for creator segment
- Pax Silica retains exclusive license for government segment
- Revenue-share: If joint patent generates licensing revenue, split 50/50

---

## 4. Market Positioning (Israel-Specific)

### 4.1 Competitive Landscape (as of Jun 2026)

| Vendor | Core Offering | Israel Presence | Governance | Moat |
|---|---|---|---|---|
| **OPAQUE** (EU startup) | Encrypted ML | None | Minimal | Academic IP |
| **Yozma Fund Portfolio** | Generalist VC | Tel Aviv | Governance-naive | Network effect |
| **Israeli Defense AI Labs** | Classified R&D | Deep | Military-only | State IP |
| **Axiom + Pax Silica** | Sovereign governance | New entry | **Cryptographic enforcement** | **Only vendor: creator + government + crypto** |

**Uncontested Position:**
Axiom + Pax Silica is the **only vendor combining:**
1. Creator economy governance (99% payouts, transparent settlements)
2. State-approved authorization framework (ReBAC + temporal guards)
3. Cryptographic enforcement (tamper-proof audit trails)
4. Israeli civil defense relationships (go-to-market + pilot)

---

### 4.2 Marketing Narrative

**Core Message (Investor + Government):**
> "While others build sandboxed AI, we build sovereign AI with cryptographic accountability. Creators keep 99% of value. States enforce policy without surveillance. Technology, not politics, guarantees freedom."

**Segments:**
- **Creators:** "Own your earnings, own your data, own your algorithm"
- **Civil Defense:** "Policy enforcement that survives attacks and state pressure"
- **Enterprise:** "Governance that scales from 10 users to 10M without compromise"

---

## 5. Revenue Share Model

### 5.1 Year 1 Forecast (Aug–Dec 2026)

**Creator Segment:**
- 50 Israeli creators × avg €500/year = €25K
- Axiom retains 100% (Pax Silica has no role)

**Enterprise Segment:**
- 1 civil defense pilot × €50K contract = €50K
- Pax Silica's role: Relationship + integration (100% Pax Silica credit)
- Revenue share: Axiom 70%, Pax Silica 30% = €15K to Pax Silica

**Total Year 1 Israeli ARR (conservative):** €75K
- Axiom: €60K (80%)
- Pax Silica: €15K (20%)

### 5.2 Standard Revenue Share (Year 2+)

**Agreed Model (3% of Israeli ARR):**
```
Any new contract signed by Pax Silica relationship
    ↓
Revenue recognized to Axiom
    ↓
3% distributed to Pax Silica (indefinite)
    ↓
Example: €500K contract → Pax Silica receives €15K (one-time)
```

**Rationale:**
- Pax Silica provides go-to-market + relationship access
- Axiom retains core product + margin (97%)
- Scaling incentive: Pax Silica benefits from larger contracts

### 5.3 Success Metrics (Year 1)

- ✅ Civil defense pilot signed by Aug 15
- ✅ Follow-on enterprise contract (€50K+) by Dec 31
- ✅ Pax Silica earns €15K+ in Year 1 (validates partnership economics)
- ✅ Creator segment grows independently (Pax Silica uninvolved, Axiom 100%)

---

## 6. Legal & Compliance Framework

### 6.1 Agreements Required

1. **Master Service Agreement (MSA)**
   - Governance: Swiss Foundation Charter
   - Terms: 2 years, auto-renew annual
   - Termination: 90-day notice, no penalty if <€10K revenue

2. **IP Sharing Agreement**
   - Classifies IP levels (1–4, see Section 3.2)
   - Access control procedures
   - Confidentiality + NDA (5-year post-termination)

3. **Revenue Share Schedule**
   - 3% of Israeli ARR to Pax Silica
   - Payment: Monthly invoice, Net 30
   - Audit rights: Axiom audits Pax Silica revenue quarterly

4. **Security Addendum**
   - Israeli security clearance requirements
   - HSM + encrypted repo procedures
   - Incident notification (24-hour escalation)

### 6.2 Regulatory Approval

**Required Approvals (Timeline: Jun 5–Jul 1):**
1. **Pearl Cohen Law Firm** — General partnership legality (Swiss/Israeli)
2. **Israeli Defense Ministry** — ITAR export control review (if applicable)
3. **Mossad Liaison** (via Pax Silica) — Security clearance check (expedited, Yozma network)

**Red Flags to Monitor:**
- ITAR restrictions on cryptography (US jurisdiction risk)
- Israeli security secrets act (if classified IP involved)
- EU GDPR implications (if EU citizens' data flows to Israel)

---

## 7. Partnership Timeline

### Phase 1: Legal & Setup (Jun 5–Jul 1)
- [ ] Jun 5–10: Negotiate MSA + IP agreement with Pax Silica
- [ ] Jun 10–20: Pearl Cohen legal review
- [ ] Jun 20–30: Israeli security review (expedited via Yozma)
- [ ] Jul 1: Sign all agreements, partnership goes live

### Phase 2: Integration (Jul 1–Aug 10)
- [ ] Jul 1–15: Deploy dual-crypto bridge (Axiom post-quantum ↔ Pax Silica RSA)
- [ ] Jul 15–25: Civil defense pilot kickoff (integrated with Pax Silica team)
- [ ] Aug 1–10: Soft-launch creator cohort (Axiom-only, Pax Silica watches)

### Phase 3: Pilot + Go/No-Go (Aug 11–Sep 1)
- [ ] Aug 11–25: Enterprise POC execution (Pax Silica leads, Axiom supports)
- [ ] Aug 26–31: Go/no-go decision (Director sign-off)
- [ ] Sep 1+: Phase 3 rollout (if approved)

---

## 8. Success Criteria (By Sep 1)

- ✅ All legal agreements signed by Jul 1
- ✅ Integration bridge deployed + tested
- ✅ Civil defense pilot completed (Aug 25)
- ✅ Go/no-go decision made (realistic outcome)
- ✅ Pax Silica earns first revenue (€5K+)
- ✅ Creator segment independent (Axiom retained 100%)
- ✅ IP boundaries clear + enforced (zero leaks)

---

## 9. Risk & Contingency

| Risk | Mitigation |
|---|---|
| **ITAR restrictions** | Pre-clear with Israeli Defense Ministry by Jun 20 |
| **Israeli security rejection** | Fallback: Non-classified civil defense only (no Mossad) |
| **Pax Silica pivots/exits** | Escrow clause: IP returns, Axiom retains right to operate in Israel |
| **Regulatory change** (EU GDPR + Israel) | Data residency: Israel-hosted EU citizens' data in EU (hybrid cloud) |
| **Civil defense pilot fails** | Sunk cost: €20K; pivot to commercial segment (corporations, NGOs) |

---

## 10. Decision Gate (Jun 4–7)

**Question:** Should Axiom proceed with Pax Silica partnership under these terms?

**Approval Criteria:**
- ✅ Legal review clean (Pearl Cohen)
- ✅ Revenue model achieves €15K+ Year 1 (Pax Silica's cut)
- ✅ No ITAR/security blockers
- ✅ Axiom retains IP control + Swiss Foundation independence

**Decision:** YES (pending legal) / NO (pivot to EU-only market entry) / DEFER (study 30 days)

**Recommendation:** YES — Partnership is strategically valuable (go-to-market + credibility in Israel market), revenue share is fair, IP boundaries are clear. Legal sign-off required before Jul 1.

