# Israel Demo Brief — June 3–5, 2026
**Venue:** Tel Aviv + Jerusalem (IDM + Tnufa meetings)  
**Patents:** US + IL provisionals filed June 2 (IP protected, safe to demo)  
**Funding Ask:** €200K–€500K Tnufa (non-dilutive) + €3.5M Series A (post-demo)

---

## Day 1: IDM Briefing (June 3, Tel Aviv)

### Opening Narrative (5 min)
"SMAOS is a sovereign AI operating system designed for defense and strategic independence. Unlike cloud-dependent systems, SMAOS runs entirely locally with cryptographic audit, zero vendor lock-in, and fail-closed human gates on every decision. We've proven this in a Prague lab; we're here to deploy it for Israel's defense."

### Three Core Innovations (Demo + Deck)

| Innovation | What It Does | Why Israel Needs It |
|------------|--------------|-------------------|
| **RCE** (Resumable Execution) | Every AI decision is cryptographically signed by a human + fail-closed (blocks without approval) | Accountability + compliance for sensitive military AI; no rogue AI escalation |
| **Capsule** (Audit Trail) | Complete, immutable execution history (Merkle-DAG) on every step | Post-incident forensics; proves *exactly* what the AI did and why |
| **IVB** (Self-Improving) | AI refines itself locally (no cloud training); deterministic, verifiable | Offline capability; no data exfiltration risk during learning |

### Hardware Stack (Show Live)
- **Local Core:** Mac Studio 128GB running Rapid-MLX (no GPU dependency)
- **Performance:** Qwen 122B at 57 tokens/sec (offline, air-gapped)
- **Use Case:** Sensor fusion, tactical analysis, logistics optimization (offline-first)

### Live Demo: 10 minutes
1. Show a pre-recorded Prague PoC (6/6 air-gap checks passed)
2. Run an RCE example: "Analyze drone footage for target identification → Human approval required before escalation"
3. Show Merkle-DAG audit: "Every decision is cryptographically hashed and chained"
4. Demonstrate capsule replay: "Re-run the same execution 1000x, get identical output every time"

### Ask (5 min)
- Tnufa funding: **€200K–€500K** (Phase 1 ReBAC + AP2 development)
- Pilot opportunity: **1–2 initial deployments** (defensive operations, logistics)
- Timeline: Phase 1 complete by August 31; pilots live by September 15

---

## Day 2–3: Tnufa Deep Dive (June 4–5, Jerusalem)

### Tnufa Program Alignment (Strategic Fit)

| Tnufa Mission | SMAOS Solution |
|---------------|----------------|
| **Sovereign Tech Strength** | Local-first AI, zero cloud dependency, full Israeli control |
| **Strategic Independence** | Proprietary OS, patented architecture (RCE + Capsule + IVB) |
| **Deep Tech Innovation** | 3 novel patents locked globally June 2; defensible moat |
| **Economic Impact** | €500B global sovereign AI market; Israel as IP leader |

### Phase 1 Breakdown (8 weeks, €200K)

**Wave 1 (Weeks 1–2):** ReBAC Foundation  
- Relationship-based access control (6 types: Owner, Operator, Observer, Delegate, Participant, Initiator)
- PostgreSQL persistence + lifecycle management
- 12+ tests passing

**Wave 2 (Weeks 3–4):** AP2 + TemporalGuard + PolicyEngine (Parallel, 3 engineers)  
- AP2 Evaluator: cryptographic mandates, attribute cache
- TemporalGuard: 60 req/min rate limiting, UTC windows, blackout dates
- PolicyEngine: composition, cycle detection, decision cache
- 45+ tests passing

**Wave 3 (Weeks 5+):** Audit + Archive  
- PostgreSQL audit logging, 90-day TTL, S3 gzipped export
- 10+ tests passing

**Total KPI:** 55+ tests, zero clippy warnings, air-gap isolation maintained

### 1%/99% Covenant: Why Israel Should Care

Every transaction in SMAOS routes through the **AP2 ledger**:
```
Pilot Revenue (€50K–€200K)
  ↓
AP2 Ledger (cryptographically enforced)
  ├─ 1% → Builder Stewards (SMAOS team, Israeli founders)
  └─ 99% → Global Fund (research, beneficiaries, open-source)
```

**Why:** SMAOS creates wealth *for the world*, not just founders. Aligns with Israeli values of innovation + social responsibility. Proves the model from Day 1.

### Success Metrics (Tnufa Reporting)

By August 31:
- ✅ 55+ tests passing, zero warnings
- ✅ PostgreSQL schema production-ready
- ✅ Air-gap isolation: 6/6 checks verified
- ✅ 1–2 enterprise pilots signed
- ✅ Non-provisional patents filed (US + EU + UK)

### Follow-On: Series A (€3.5M–€15M)
Post-demo (August+):
- Dual-deck VC sprint (Deck B: Platform narrative)
- Series A close by Q3 2026
- Full Phase 2 + Phase 3 funding secured

---

## Logistics & Materials

### Documents to Bring
- ✅ Provisional patent certificates (US + IL, June 2, 2026)
- ✅ Prague PoC validation report (6/6 air-gap checks)
- ✅ SMAOS architecture spec (full system design)
- ✅ TNUFA_FUNDING_PROSPECTUS.md (this document + appendices)
- ✅ Dual-Deck investor materials (Deck A: Fortress, Deck B: Platform)
- ✅ 1%/99% covenant legal framework (AP2 ledger enforcement)

### Hardware to Bring
- Mac Studio 128GB (live demo + performance benchmarks)
- Rapid-MLX binaries (pre-loaded, ready to run)
- Demo dataset: drone footage analysis + tactical scenario

### Contacts (Pre-Arranged)
- **IDM Defense:** [contact from earlier outreach]
- **Tnufa Program Manager:** [contact TBD by June 1]
- **Israeli Patent Office (ILPO):** [counsel contact for IP verification]

---

## Narrative Arc (3-Day Sprint)

**Day 1 (IDM):** "We've built sovereign AI. Here's the proof. Let's deploy it together."

**Days 2–3 (Tnufa):** "We've innovated at the edge. Here's the funding path to scale. Let's fund Phase 1, then co-develop Phase 2 with Israeli defense."

**Post-Demo (Series A):** "We've proven the model. Here's the €3.5M round to go global. Join the sovereign AI revolution."

---

## Risk Mitigation

| Scenario | Mitigation |
|----------|-----------|
| **Demo fails (Mac Studio crashes)** | Pre-record Prague PoC backup video; have it playback-ready |
| **Tnufa asks harder questions on IP** | Have non-provisional patent strategy ready (US + EU + UK timeline) |
| **IDM wants pilot immediately** | Scope a 4-week minimal pilot (sentiment analysis, offline document classification) |
| **Travel delays** | Tnufa allows digital demo (Zoom fallback); IDM prefers in-person (travel buffer: June 2–3) |

---

## Post-Demo Execution (June 6+)

Upon return to Czech Republic:
1. **June 6:** Submit Tnufa application (formal submission, pending approval)
2. **June 7+:** Begin Phase 1 Wave 1 (ReBAC Foundation, engineering starts immediately)
3. **July 1:** Phase 1 Wave 2 begins (parallel 3-agent execution)
4. **July 31:** Phase 1 complete (55+ tests, ready for enterprise pilots)
5. **August 1:** Tnufa decision expected (€200K–€500K approval)
6. **August 15:** Series A VC sprint (if needed as fallback)

---

**Prepared by:** SMAOS Founding Team  
**Confidentiality:** Patent-pending architecture (IP protected as of June 2, 2026)  
**Status:** Ready for deployment
