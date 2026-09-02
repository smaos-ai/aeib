# SMAOS: UniCredit Treasury Pilot — DELIVERY SCOPE
**4-Week Sprint (Oct 1 - Oct 31, 2026)**

---

## WHAT WE DELIVER (Week-by-Week)

### WEEK 1: Integration & Data Onboarding
**What UniCredit Gets:**
- ✅ SMAOS container deployed in staging environment (Docker, 512MB RAM, local inference)
- ✅ API wired to UniCredit's RWA calculation engine (REST endpoint + streaming logs)
- ✅ Historical loan portfolio loaded (3 months of trades for shadow-mode testing)
- ✅ Basel III rule engine configured (CAR 8% minimum, CET1 tracking, liquidity buffer)
- ✅ Real-time CAR simulation dashboard (shows: current CAR%, projected CAR after each trade)

**Technical Handoff:**
- Staging URL: `http://[unicredit-internal-ip]:5000/api/governance`
- Dashboard: `http://[unicredit-internal-ip]:3000` (read-only, monitoring mode)
- Logs: Streamed to ELK stack or Splunk (your choice)
- No production impact yet (shadow mode only)

**Success Metric:** CAR calculations match UniCredit's internal system ±0.01%

---

### WEEK 2-3: Shadow Mode (Read-Only, No Blocking)
**What UniCredit Gets:**
- ✅ Live observation of all daily trades
- ✅ Audit trail for each trade (timestamp, counterparty, amount, CAR impact, veto gate decision)
- ✅ Weekly compliance report (how many trades would have been blocked, by policy)
- ✅ Performance metrics (latency, CPU/memory usage, network isolation verification)
- ✅ Trader UX feedback (UI changes based on trader input)

**What We Measure:**
- % of high-risk trades detected (should be 5-15% of daily volume)
- False positive rate (trades flagged but compliant)
- System latency (target: <300ms gate-to-decision)
- Network isolation proof (0 Kbps outbound, air-gapped verified)

**Success Metric:** Zero blocking (shadow mode), 100% audit trail accuracy, <300ms latency confirmed

---

### WEEK 4: Go-Live & First Authorized Trade
**What UniCredit Gets:**
- ✅ Veto gates ACTIVATED (system now blocks high-risk trades, requires CRO authorization)
- ✅ First trader uses the flow:
  1. Submits trade request (e.g., "Sell €50M corporate bonds")
  2. System flags if CAR-impacting (yes → veto gate appears)
  3. CRO sees Basel III Veto Card on dashboard
  4. CRO clicks "Authorize & Sign" (Ed25519 signature generated)
  5. Trade executes with immutable proof ledger entry
- ✅ Proof receipt exported to compliance system (PDF + JSON + cryptographic verification)
- ✅ All 4 weeks of data packaged for regulatory review

**What We Deliver:**
- Production-ready deployment (monitoring + alerting live)
- CRO dashboard access (personal login, Ed25519 key setup)
- 24/7 on-call support (Slack + email)
- Full audit trail (exportable for BaFin/ECB)

**Success Metric:** First authorized trade completes, proof ledger verified, CRO confirms workflow

---

## SYSTEM SPECIFICATIONS

### Frontend (Trader + CRO Dashboards)
```
Left Pane:      Intent Submission (trade details: counterparty, amount, instrument)
Center Pane:    Diamond Topology (parallel execution nodes, real-time status)
Right Pane:     Proof Ledger + CAR Meter + Kill Switch
```

### Backend Integration Points
```
IN:   RWA Feed (Murex/internal) → CAR calculation → Pre-execution gate check
OUT:  Veto decision (block/approve) → Trade execution system → Proof ledger
```

### Proof Ledger Schema (Real, Immutable, Ed25519-Signed)
```json
{
  "id": "receipt-20261001-trade-0042",
  "timestamp": "2026-10-01T14:23:45Z",
  "action": "veto.authorize",
  "trade": {
    "counterparty": "Goldman Sachs",
    "amount_eur": 50000000,
    "instrument": "Corporate Bond",
    "car_impact": "CAR: 10.15% → 9.98% (⚠️ below 10.5% threshold)"
  },
  "policy_triggered": "BASEL_III_CAR_BUFFER",
  "authorized_by": "CRO_ID_12345",
  "ed25519_signature": "base64...",
  "merkle_root": "sha256...",
  "verified": true
}
```

### Non-Functional Requirements
| Metric | Target | Proof Method |
|--------|--------|---|
| **CAR Calculation Accuracy** | ±0.01% match | Daily reconciliation report |
| **Gate Latency** | <300ms | Performance log timestamps |
| **Network Isolation** | 0 Kbps outbound | navigator.onLine + tcpdump |
| **Uptime** | 99.95% (trading hours) | Automated health checks |
| **Audit Trail Integrity** | 100% Ed25519 verified | Live verification button |

---

## WHAT WE DON'T DELIVER (Out of Scope)

- ✗ Integration with payment systems (settlement outside scope)
- ✗ Murex API development (you own Murex setup, we consume via REST)
- ✗ Trading algorithm changes (we gate, not modify)
- ✗ Regulatory filing (compliance team owns submission)
- ✗ Trader training beyond pilot week (your ops team leads)

---

## DEPLOYMENT ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    UniCredit Staging Environment                │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Trading Platform (Murex / Internal)                     │  │
│  │  └─ RWA/CAR calculation engine                           │  │
│  │  └─ REST API: GET /rwa/positions, POST /execute/trade    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         ↓ HTTPS (internal VPN)                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SMAOS Governance Container (Docker)                    │  │
│  │  ├─ Intent Classifier (Basel III rules engine)           │  │
│  │  ├─ Pre-Execution Gate (fail-closed veto)               │  │
│  │  ├─ Ed25519 Signing Service                             │  │
│  │  ├─ Proof Ledger (Merkle-DAG, SQLite)                   │  │
│  │  └─ REST API: POST /intent, GET /receipts               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         ↓                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Dashboards (React)                                      │  │
│  │  ├─ Trader dashboard (read-only during shadow mode)      │  │
│  │  ├─ CRO dashboard (veto gate, authorization)            │  │
│  │  └─ Compliance dashboard (audit trail export)           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         ↓                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Compliance System (ELK/Splunk)                          │  │
│  │  └─ Proof ledger stream (real-time ingestion)            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  🔐 SECURITY:                                                    │
│  • No cloud egress (all internal, air-gapped)                   │
│  • TLS 1.3 only (between SMAOS and trading platform)            │
│  • Ed25519 keys stored in HSM or SecureEnv (your choice)        │
│  • Proof ledger: SQLite + daily backup to compliance archive    │
└─────────────────────────────────────────────────────────────────┘
```

---

## SUCCESS = GO / NO-GO DECISION (Oct 31)

**GO Criteria (All Must Pass):**
- ✅ CAR calculations accurate to ±0.01%
- ✅ <300ms gate latency verified
- ✅ Zero unauthorized trades (kill switch never needed)
- ✅ 100% audit trail integrity (all Ed25519 sigs verified)
- ✅ CRO signed off (workflow usable, no show-stoppers)
- ✅ Compliance team cleared (audit trail export format correct)

**NO-GO Fallback:**
If any metric misses:
1. Extend shadow mode (1-2 weeks additional monitoring)
2. Identify & fix root cause
3. Restart go-live process
4. Adjust timeline for production deployment (Q1 2027)

---

## COMMERCIAL TERMS

**Year 1 Fee:** €500,000 (Oct 1, 2026 - Sep 30, 2027)
- Implementation & integration (Weeks 1-4): €200K
- Testing, validation, go-live (Weeks 5-8): €100K
- Year 1 support + updates: €125K
- Contingency buffer: €75K

**Year 2+:** €200K/year (maintenance + quarterly updates)

**Payment Schedule:**
- 25% upfront (Oct 1) = €125K
- 50% on go-live (Nov 1) = €250K
- 25% on 30-day production verification (Dec 1) = €125K

---

## NEXT STEP: KICK OFF (Sep 8-15)

**Call Attendees:**
- UniCredit CTO / VP Engineering
- Head of Treasury / Head of Risk
- Compliance DPA / Compliance Officer
- (SMAOS) Architect + Banking CRO Advisor

**What We Need from UniCredit:**
1. Trading platform tech stack (Murex version, internal APIs)
2. RWA/CAR calculation method (which regulatory framework: CRR, BASEL3.1, internal)
3. Sample 3-month trade history (CSV or API dump)
4. Staging environment access (Docker registry, internal DNS)
5. Ed25519 key management preference (HSM, SecureEnv, or SMAOS-managed)

**What We Deliver in 48 Hours:**
- Docker container (ready to deploy)
- Integration spec document (exact API contracts)
- Test data for shadow-mode validation

---

## THIS IS NOT A PROOF-OF-CONCEPT

This is **production-grade delivery** with:
- Real cryptographic signing (Ed25519, not mock)
- Real network isolation (air-gapped verified)
- Real CAR calculations (±0.01% accuracy)
- Real audit trail (immutable Merkle-DAG)
- Real veto gates (fail-closed, enforced)

By Oct 31, UniCredit will have a working, auditable, compliant governance system running on their infrastructure. Not a demo. Not a prototype. A system ready for regulatory inspection.

---

**Ready to sign?** Let's go to kickoff.
