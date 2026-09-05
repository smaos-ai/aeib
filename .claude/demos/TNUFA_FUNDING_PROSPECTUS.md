# SMAOS + Israeli Innovation Authority (Tnufa) — Funding Prospectus
**Prepared for:** Israel Defense Ministry + Tnufa Program Managers  
**Date:** June 3–5, 2026  
**Status:** Confidential — Patent-Pending (US + IL provisionals filed June 2, 2026)

---

## Executive Summary

SMAOS (Sovereign Multi-Agent Operating System) is seeking **€200K–€500K** non-dilutive funding from the **Israeli Innovation Authority (Tnufa) Deep Tech program** to accelerate Phase 1 development of the Behavioral Firewall (ReBAC + AP2 Policy Engine) while preserving 100% founder equity and maintaining the 1%/99% covenant alignment with Israeli sovereign values.

**Why Tnufa?**
- ✅ Non-dilutive (no equity given away)
- ✅ Aligns with Israeli strategic tech sovereignty mission
- ✅ Fast-track approval (8-week cycle vs. VC 6-month diligence)
- ✅ Supports dual-HQ strategy (Czech operations, Israeli IP fortress)

---

## The SMAOS Architecture: Three Patented Innovations

### 1. **Resumable Human-Governed Execution (RCE)**
Deterministic, resumable execution of autonomous agents under human cryptographic governance. Each execution step is:
- Immutable (Merkle-rooted state snapshot)
- Cryptographically signed (Ed25519 human authorization)
- Fail-closed (blocks without human approval, never escalates)
- Fully auditable (every pause/resume logged with timestamp + actor ID)

**Strategic Value:** Solves enterprise compliance + defense sector accountability requirements that cloud-dependent systems cannot meet.

### 2. **Provenance-Bound Capsule Structure**
Cryptographically-sealed execution capsules that bind:
- Agent identity (Ed25519 public key)
- Execution manifest (inputs, outputs, decision rules)
- Merkle DAG (complete audit trail of every step)
- Covenant Signature (economic intent: 1% stewards, 99% beneficiaries)

**Strategic Value:** First production system combining deterministic execution + economic covenant + immutable audit in a single structure.

### 3. **Iterative Verifier Bootstrapping (IVB)**
Deterministic critic-driven LoRA refinement with:
- Mechanical evaluation (no human subjectivity; temperature=0)
- Cryptographic reproducibility (SHA-256 hashes on every iteration)
- Fail-closed halting (revert if test-pass-rate drops)

**Strategic Value:** Self-improving AI without extraction risk; scales intelligence locally without cloud dependency.

---

## Why Israel? (Sovereign AI Strategic Alignment)

**1. Defense Sovereignty**
- SMAOS enables offline-first, air-gapped AI for Israeli defense (IDM, Unit 8200 equivalent)
- No dependency on cloud providers; full local control over sensitive AI execution
- Cryptographic audit trail meets strictest compliance standards

**2. Dual-HQ IP Protection**
- SMAOS operations: Czech Republic (EU hub, cost-effective, R&D talent)
- SMAOS IP: Israeli Trust (AI fortress, sovereign IP protection, strategic asset)
- Provisional patents filed in both jurisdictions (June 2, 2026) lock global priority date

**3. Crafter Economy (Decentralized Value)**
- 1%/99% covenant hardcoded: 1% to builders, 99% to global beneficiaries
- Aligns with Israeli values of innovation + social impact
- Creates distributed economic network (no monopoly extraction)

**4. Rapid-MLX (Apple Silicon Local Inference)**
- 96GB Mac Studio runs Qwen 122B at 57 tokens/sec locally
- SMAOS + Rapid-MLX = sovereign AI without Nvidia/cloud vendor lock-in
- Czech R&D lab + Israeli deployment strategy proven in 6/6 air-gap checks

---

## Tnufa Funding Ask: Phase 1 Behavioral Firewall (June–August 2026)

### Budget Breakdown

| Line Item | Amount | Purpose |
|-----------|--------|---------|
| **Hardware** | €15K | Mac Studio M3 Ultra 128GB (local inference) |
| **Team (2 engineers, 8 weeks)** | €80K | Phase 25 development (ReBAC + AP2 + TemporalGuard) |
| **Infrastructure** | €20K | PostgreSQL cloud (audit logging), S3 archive, testing |
| **Legal + IP** | €30K | Non-provisional patent filings (US + EU + UK), IP counsel |
| **Travel + Pilot Deployment** | €40K | Israel demo execution, initial enterprise pilot setup |
| **Contingency (10%)** | €15K | Supply chain, timeline buffers |
| **TOTAL** | **€200K** | Phase 1 complete (worst case: €500K for acceleration) |

### Success Metrics (Tnufa KPIs)

| Metric | Target | Timeline |
|--------|--------|----------|
| **Tests Passing** | 55+ (ReBAC + AP2 + Temporal + PolicyEngine + Audit) | July 31 |
| **PostgreSQL Schema** | Production-ready, audited | July 15 |
| **Cryptographic Verification** | Ed25519 signing on all mutations; Merkle chain integrity verified | July 31 |
| **Air-Gap Isolation** | 6/6 checks passed (no network calls, local-only execution) | June 30 |
| **First Enterprise Pilot** | 1–2 pilots signed (IDM or EU enterprise) | August 15 |

---

## Use of Funds: Phase 1 Development (Wave 1→3)

### **Wave 1 (Sequential, weeks 1–2): ReBAC Foundation**
- Task 1: Relationship-based access control (Owner, Operator, Observer, Delegate, Participant, Initiator)
- PostgreSQL persistence: relationship lifecycle, audit trail, index optimization
- Tests: 12+
- **Cost:** €25K (1 engineer, hardware, PostgreSQL setup)

### **Wave 2 (Parallel, weeks 3–4): AP2 + TemporalGuard + PolicyEngine**
- Task 2: AP2 Evaluator (attribute cache, 5-min freshness, immediate invalidation)
- Task 3: TemporalGuard (60 req/min rate limiting, UTC time windows, blackout dates)
- Task 4: PolicyEngine composition (3-phase evaluation, cycle detection, decision cache)
- Tests: 15 + 12 + 18 = 45+
- **Cost:** €80K (parallel 3-agent execution)

### **Wave 3 (Sequential, week 5): Audit + Archive**
- Task 5: Audit logging (PostgreSQL hot storage), 90-day TTL, S3 gzipped export
- Tests: 10+
- **Cost:** €20K (audit infrastructure, S3 integration)

### **Post-Phase 1 (Week 6–8):** Enterprise Pilot + Non-Provisional Patents
- Deploy first enterprise pilot (IDM or EU defense)
- File non-provisional patents (US + EU + UK)
- **Cost:** €40K (pilot deployment, legal counsel)

---

## Covenant Alignment: 1%/99% Economic Intent

Every transaction in SMAOS routes through the **AP2 (Agent Payment Protocol) ledger**, which cryptographically enforces the 1%/99% split:

```
Enterprise Pilot Revenue ($50K–$150K) 
  ↓
AP2 Ledger (cryptographically signed)
  ├─ 1% → Builder Stewards (SMAOS team)
  └─ 99% → Global Fund (beneficiaries, open-source developers, community)
```

**Why Tnufa aligns with this:** Israeli Innovation Authority funds Israeli founders who create value *for the world*, not just for themselves. The 1%/99% covenant proves SMAOS embodies this principle from Day 1.

---

## Risk Mitigation & Contingencies

| Risk | Probability | Mitigation |
|------|-------------|-----------|
| **Supply chain delay (Mac Studio)** | Medium | Pre-order by June 2; fallback to EU distributor (Alza) |
| **PostgreSQL tuning complexity** | Low | 2-week buffer in Wave 1; sqlx prepare() pre-validates schema |
| **Enterprise pilot stalls** | Medium | Parallel Series A VC sprint (€3.5M fallback) activated by July 1 |
| **Non-provisional patent delays** | Low | File with expedited counsel; provisional date already locked June 2 |

---

## Post-Tnufa Roadmap (Phase 2, August–December 2026)

With Tnufa funding, Phase 1 completes by July 31. Then:

1. **Phase 2a (Weeks 9–12):** Sovereign Search Router (SSR) + Local-First Cache
2. **Phase 2b (Weeks 13–16):** Multi-Agent Mode (Capsule federation, swarm coordination)
3. **Series A Close (Q3 2026):** €3.5M–€15M from Tier-1 VCs + strategic defense/energy investors

**Total 2026 Roadmap Value Creation:**
- 3 patented innovations (RCE, Capsule, IVB) locked globally
- First production Behavioral Firewall (ReBAC + AP2) deployed
- 1–3 enterprise pilots live (IDM or EU defense)
- €200K–€500K non-dilutive funding + €3.5M Series A = €3.7M–€4M year-end runway

---

## Tnufa Contact & Timeline

**Application Submission:** June 6, 2026 (immediately post-patent filing)  
**Expected Decision:** August 1, 2026 (8-week review cycle)  
**Funding Disbursement:** August 15, 2026  
**Phase 1 Completion:** July 31 (parallel to funding decision)

**Contact:** Andrej Leukhin, Founder  
Email: andrejlo123@gmail.com  
Phone: [on request during Israel meeting]

---

## Appendices

### A. Patent Filing Certificates (June 2, 2026)
- US Provisional (USPTO) — RCE + Capsule + IVB claims
- IL Provisional (ILPO) — Same claims, Israeli IP fortress filing

### B. Prague PoC Validation Report (May 27–28, 2026)
- 6/6 air-gap isolation checks ✅
- Deterministic replay verified (1000+ execution runs identical output)
- Cryptographic audit trail immutable (no mutation without Ed25519 signature)

### C. SMAOS Architecture Spec
- Full system design: governance plane, execution plane, storage plane
- PostgreSQL schema (normalized, indexed for audit compliance)
- API contracts (trait-driven, test-gated)

### D. 1%/99% Covenant Legal Framework
- AP2 ledger cryptographic enforcement
- Global Fund beneficiary distribution (open-source, research, community)
- Tnufa alignment with Israeli social impact mandate

---

**Prepared by:** SMAOS Founding Team  
**Confidentiality:** TRADE SECRET — Encrypt before transmission  
**Status:** Ready for Israeli Innovation Authority (Tnufa) submission
