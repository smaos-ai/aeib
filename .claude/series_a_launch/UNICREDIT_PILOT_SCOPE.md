# UniCredit Bank Pilot: SMAOS Treasury AI Governance Stack

**Target Date:** Q4 2026 (Oct-Dec)  
**Budget:** €500K annual license + implementation  
**Scope:** 1 internal AI system (treasury operations) + proof of Basel III compliance automation

---

## Executive Summary

**What:** SMAOS governance layer wraps UniCredit's existing AI/ML systems (trading algorithms, credit models, RFQ automation) with pre-execution gates, cryptographic audit trails, and Basel III Capital Adequacy Ratio (CAR) automation.

**Why Now:** 
- EU AI Act Annex I enforcement (Aug 2, 2028) requires pre-execution governance for embedded AI in critical infrastructure
- Basel III compliance burden rising: CARs require near-real-time recalculation on every high-risk trade
- Post-SVB/Credit Suisse crisis: regulators demand auditable AI decision-making in treasury operations

**Win:**
- **Regulatory:** Proof of pre-execution AI governance + immutable audit trail (SEC Rule 17a-4 compliant)
- **Operational:** Automated CAR calculation + veto gates = faster approvals + zero unauthorized trades
- **Cost:** ~€50K/year maintenance post-implementation vs. €300K/year compliance consulting

---

## Technical Fit

### What SMAOS Provides (Day 1)

| Layer | Capability | Compliance Artifact |
|-------|-----------|-------------------|
| **Pre-Execution Gates** | Block high-risk trades before execution | EU AI Act Article 13 (transparency) |
| **CAR Impact Detection** | Flag trades affecting 8% minimum CAR threshold | Basel III CRR/CRD IV alignment |
| **Intent Classification** | Counterparty rating, instrument type, amount → risk severity | NIST SP 800-53 CM-2 (policy-based access) |
| **Cryptographic Audit Trail** | Ed25519-signed proof of every decision + human veto | SEC Rule 17a-4 immutable records |
| **Human Veto Gate** | Trader clicks "Authorize" or "Revise" → signed receipt | EU AI Act Article 14 (human oversight) |
| **Kill Switch** | Immediate halt all in-flight trades | Operational resilience |

### Integration Points (Pilot Scope)

```
Existing UniCredit System
├─ Trading Platform (Murex/Numerix)
├─ Credit Models (internal MLP)
└─ RFQ Engine (external facing)
         ↓
   [SMAOS Governance Layer]
   ├─ Pre-execution gate intercept
   ├─ CAR calculator (real-time)
   ├─ veto.authorize / veto.revise flow
   └─ immutable proof ledger
         ↓
   ✓ Trade executed with proof
   ✓ Audit trail in compliance system
```

### Hardware + Deployment

- **On-Premises:** Single Docker container (512MB RAM, 1 CPU core) in UniCredit's Kafka cluster
- **No Cloud Egress:** Zero external API calls (all governance local)
- **Network:** Internal only (TCP/5000 to trading platform, read-only DB access)
- **Compliance:** Full data residency in EU (Frankfurt/Milan data centers)

---

## Pilot Workflow (4-week sprint)

### Week 1: Integration & Data Onboarding
- Deploy SMAOS sidecar in staging environment
- Wire to treasury trading platform logs
- Load 3 months of historical trades for CAR simulation
- Build Basel III rule engine (3 rules: amount threshold, counterparty rating, derivative type)

### Week 2-3: Live Testing (Read-Only)
- Run in shadow mode (observe, don't block)
- Measure: % of daily trades that would trigger veto gates
- Validate CAR calculations against existing system
- Collect performance metrics (latency, accuracy)

### Week 4: Production Cutover
- Enable veto gates (traders see "Authorize / Revise" on high-risk trades)
- Activate immutable audit logging
- Deploy to production (monitored)
- Train traders on new flow (~30 min per person)

### Post-Pilot: Expansion
- Extend to RFQ engine (external client-facing)
- Add credit model governance (loan underwriting)
- Automate regulatory reporting (MiFID II, EMIR)

---

## Compliance Mapping

| Regulation | Requirement | SMAOS Delivers | Proof |
|-----------|-----------|-------|------|
| **EU AI Act (Annex I, Aug 2028)** | Pre-execution safety gates for embedded AI | Veto gate halts trades before execution | Dashboard + signed receipt ledger |
| **Basel III (CRR/CRD IV)** | CAR ≥ 8% + governance | Real-time CAR recalc + approval workflow | Daily CAR report + audit trail |
| **SEC Rule 17a-4** | Immutable, non-repudiable audit logs | Ed25519-signed decisions, Merkle-rooted | Cryptographic verification on demand |
| **GDPR/NIS2** | Data residency + breach notification | On-prem deployment, no cloud egress | Infrastructure attestation |
| **MiFID II** | Algorithmic trading transparency | Decision ledger + trader override logs | Compliance data export |

---

## Commercial Terms

**License + Services Package:**
- **Year 1:** €500K (implementation + 1 year support)
  - Development (4 weeks): €200K
  - Testing + validation: €100K
  - Training + documentation: €75K
  - First-year support/SLAs: €125K

- **Year 2+:** €200K/year (maintenance + updates)

**Success Metrics (KPIs):**
- Zero unauthorized trades (kill switch tested monthly)
- CAR calculations within 0.01% of manual validation
- Trader adoption >95% within 60 days
- Audit trail 100% compliant with SEC Rule 17a-4

**SLA:**
- 99.95% uptime (treasury hours, EU time zones)
- <100ms gate latency (no trade delays)
- 24/7 on-call support (escalation to CTO)

---

## Competitive Advantage vs. Existing Solutions

| Solution | Gates | Audit Trail | CAR Auto | On-Prem | Ed25519 | Price |
|----------|-------|-------------|----------|---------|---------|-------|
| **SMAOS** | ✓ Pre-exec | ✓ Immutable | ✓ Yes | ✓ Yes | ✓ Yes | €500K |
| OneTrust | ○ Post-hoc | ○ Editable | ✗ No | ✗ SaaS | ✗ RSA | €400K |
| IBM PAIRS | ○ Reactive | ○ Database | ○ Plugin | ✗ Cloud | ✗ TLS | €800K |
| Collibra | ○ Metadata | ○ Audit log | ✗ No | ○ Hybrid | ✗ Standard | €600K |

**Differentiator:** Only solution combining fail-closed pre-execution gates + cryptographic proof + local deployment for banking.

---

## Next Steps

1. **Technical Kickoff:** CTO + Head of Treasury + Compliance DPA alignment (1 week)
2. **POC Agreement:** Sign pilot SOW + data access agreement (2 weeks)
3. **Integration Sprint:** Week 1-4 as above
4. **Go/No-Go Decision:** Week 4 performance review (Nov 30, 2026)
5. **Series A Narrative:** Case study + metrics for investor deck (Dec 2026)
