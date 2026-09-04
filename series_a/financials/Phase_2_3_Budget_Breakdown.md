# Phase 2+3 Budget Breakdown

**Document Date:** September 5, 2026  
**Fiscal Period:** Jun 2027 - Dec 2028 (19 months)  
**Total Budget:** €983,000 EUR

---

## PHASE 2 BUDGET (BIC Plzeň Funding)
**Period:** Jun 1 - Dec 31, 2027 (7 months)  
**Total:** €225,000 EUR

### Engineering (65%)
| Component | Allocation | Details |
|-----------|-----------|---------|
| Edge Hardware Integration | €85,000 | Jetson Thor + Cosmos 2.5 + ROS 2 setup (6 FTE-months) |
| Industrial Robotics (URDF/MuJoCo) | €35,000 | 6-DOF arm control + grasp verification (2 FTE-months) |
| Hardware-in-the-Loop Testing | €28,000 | Gazebo 11 + simulation harness (1.5 FTE-months) |
| Proof Layer Integration | €18,000 | agentacct + AP2 ledger for robotic actions (1 FTE-month) |
| **Subtotal Engineering** | **€166,000** | |

### Infrastructure & Operations (20%)
| Component | Allocation | Details |
|-----------|-----------|---------|
| AWS/GCP Cloud Testing Environment | €20,000 | Dev/staging for simulation validation |
| Hardware Procurement (test units) | €10,000 | Additional Jetson units for redundancy |
| CI/CD Pipeline (GitHub Actions + runners) | €5,000 | Real-time hardware testing automation |
| **Subtotal Ops** | **€35,000** | |

### Quality & Compliance (15%)
| Component | Allocation | Details |
|-----------|-----------|---------|
| RAGAS Testing Framework | €12,000 | Expand golden set to 100+ scenarios |
| Manual Verification (MMV) | €12,000 | Edge robotics testing + documentation |
| Security Audit (edge + crypto) | €1,000 | Code review + threat modeling |
| **Subtotal QA** | **€25,000** | |

---

## PHASE 3 BUDGET (Series A Funding)
**Period:** Jan 1 - Dec 31, 2028 (12 months)  
**Total:** €758,000 EUR

### Engineering (60%)
| Component | Allocation | Details |
|-----------|-----------|---------|
| Multi-Agent Swarm Architecture | €180,000 | @planner @compliance @evidence agents (9 FTE-months) |
| Agent-to-Agent Protocol (A2A) | €100,000 | CBOR serialization + Ed25519 signing (5 FTE-months) |
| Federated AP2 Ledger | €80,000 | Cross-org settlement via post-quantum ledger (4 FTE-months) |
| Chronicle Analysis (drift detection) | €60,000 | Goal divergence monitoring (3 FTE-months) |
| Continuous Verification Framework | €75,000 | RAGAS 87%+ on swarm decisions (3.5 FTE-months) |
| **Subtotal Engineering** | **€495,000** | |

### Infrastructure & Cloud (25%)
| Component | Allocation | Details |
|-----------|-----------|---------|
| Multi-Region Edge Deployment | €80,000 | EU data centers (Frankfurt, Amsterdam, Prague) |
| Kubernetes Orchestration (swarm) | €40,000 | Cross-datacenter AP2 consensus |
| KMS Integration (HSM backend) | €35,000 | Hardware security modules for key management |
| Monitoring & Observability (Datadog/New Relic) | €25,000 | Production swarm telemetry |
| **Subtotal Cloud** | **€180,000** | |

### Regulatory & Compliance (12%)
| Component | Allocation | Details |
|-----------|-----------|---------|
| EU AI Act Annex III Certification | €40,000 | DMA compliance audit + documentation |
| Annex I (Glass/Auto) Pilots | €25,000 | Real-world pilot execution |
| Chronicle Ledger Regulatory Filing | €15,000 | Post-quantum crypto certification |
| **Subtotal Compliance** | **€80,000** | |

### Go-to-Market (3%)
| Component | Allocation | Details |
|-----------|-----------|---------|
| Pilot Customer Success | €15,000 | UniCredit + Czech National Bank support |
| Marketing Collateral | €3,000 | Case studies, whitepapers |
| **Subtotal GTM** | **€18,000** | |

---

## FUNDING SOURCES

| Source | Amount | Status | Notes |
|--------|--------|--------|-------|
| BIC Plzeň (Phase 2) | €225,000 | Approved | 7 months: Jun-Dec 2027 |
| Series A Target | €758,000 | Pending | 12 months: Jan-Dec 2028 |
| **TOTAL** | **€983,000** | | 19-month roadmap |

---

## KEY FINANCIAL ASSUMPTIONS

1. **FTE Cost:** €75,000/year per senior engineer (loaded cost, EU-based)
2. **Hardware Procurement:** Jetson Thor Blackwell ~€35K per unit; 2-3 units budgeted
3. **Cloud Cost:** €800/month base + variable egress; €9,600/year assumed for Phase 2; €20,000/year for Phase 3 (federated)
4. **Testing & QA:** 15-20% of engineering budget (industry standard)
5. **Regulatory:** 10-12% for AI Act + post-quantum crypto compliance

---

## BURN RATE & RUNWAY

### Phase 2 (7 months)
- **Monthly Burn:** €32,143
- **Ending Cash Position:** Funded by BIC Plzeń

### Phase 3 (12 months)
- **Monthly Burn:** €63,167
- **Ending Cash Position:** Series A runway extended to Q3 2028

---

## STRETCH GOALS (if funding exceeds target)

- [ ] Additional robotics pilot (automotive manufacturing)
- [ ] Full federated swarm to 5+ institutions (vs. 3-pilot MVP)
- [ ] Post-quantum crypto hardening (NIST PQC migration)
- [ ] AI Act Annex III pre-certification (before Dec 2, 2027 enforcement)
