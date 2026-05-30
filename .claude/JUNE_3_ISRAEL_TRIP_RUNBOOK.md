# ISRAEL TRIP RUNBOOK — June 3-5, 2026
## SovereignNexus Series A Demonstration & Patent Filing

**Status:** Ready for execution  
**Owner:** Andrii Leukhin  
**Critical Dates:** June 3 (Zysman Law), June 4 (Defense + VC), June 5 (Debrief)  
**Decision Gates:** 3 binary gates at June 5 debrief (lead investor? defense pilot? patent on track?)

---

## TIMELINE AT A GLANCE

| Date | Time | Location | Duration | Objective |
|------|------|----------|----------|-----------|
| **June 3 (TUE)** | 10:00 AM | Zysman Law, Tel Aviv | 1.5 hours | **Patent filing meeting** — File US Provisional with all 3 claims |
| **June 4 (WED)** | 2:00 PM | Defense Ministry, Jerusalem | 1 hour | **Live demo** — Fail-closed governance + Night Cycle + Air-gap transfer |
| **June 5 (THU)** | 9:00 AM | VC Debrief, Tel Aviv | 1 hour | **Decision gates** — Lead investor? Defense pilot? Patent filed? |

**Travel:** Tel Aviv ↔ Jerusalem (90 min highway, 07:00 AM June 4 depart for 2 PM meeting)

---

## JUNE 3 — ZYSMAN LAW PATENT FILING

### Pre-Meeting Checklist (June 2, Evening)

- [ ] Print 3 copies: PROVISIONAL_PATENT_DRAFT.md (12 pages)
- [ ] USB drive with full crate source code (3 copies):
  - `crates/siss-gatekeeper/src/signer.rs`
  - `crates/siss-behavioral-firewall/src/ap2.rs`
  - `crates/siss-gatekeeper/src/attestation.rs`
  - `crates/siss-gatekeeper/src/sneakernet_ingress.rs`
  - `crates/siss-night-cycle/src/verifier.rs`
  - `crates/siss-decision-db/src/merkle.rs`
- [ ] Laptop with local builds ready (`cargo build --release`)
- [ ] Photos of Prague PoC air-gap setup (6 verification checks)
- [ ] Passport + travel documents
- [ ] Bank transfer details for Zysman Law retainer (if needed)

---

## JUNE 3 — 10:00 AM ZYSMAN LAW PATENT FILING SESSION (90 MIN)

**Segments:**
- 10:00-10:10: Opening & context (10 min)
- 10:10-10:35: Claim A (Human Gate) deep dive (25 min)
- 10:35-11:00: Claim B (Night Cycle) deep dive (25 min)
- 11:00-11:20: Claim C (Knowledge Capsule) deep dive (20 min)
- 11:20-11:30: Q&A & filing gates (10 min)

---

## JUNE 4 — DEFENSE MINISTRY LIVE DEMO

### Demo Script — 5 Segments (60 minutes)

#### 2:00 - 2:10 PM — Sovereign Context (10 min)
- SMAOS Overview: Cryptographic governance for autonomous AI in conflict zones
- 15-Layer Exoskeleton: Layer 6=Human Gate, Layer 7=Night Cycle, Layer 8=Air-Gap Capsule Transfer
- Problem: Standard AI requires cloud; we go local-first + cryptographic veto
- Every decision: 3-phase eval (ReBAC → AP2 → Governance) + human signature + Merkle audit

#### 2:10 - 2:22 PM — Live Inference (12 min)
- Demo: Rapid-MLX 160 tokens/sec on Apple Silicon M3
- Task request with no auth → 401 UNAUTHORIZED
- Human authorizes via Ed25519 signature (128 hex)
- Task executes with auth → 200 OK + decision logged to DECISION-DB

#### 2:22 - 2:35 PM — Human Gate (13 min)
- Fail-closed Ed25519 human signature required per task
- Nonce burn prevents replay attacks
- TTL (900 sec) prevents stale signatures
- Demo: Attempt replay → 400 BAD REQUEST (nonce already burned)
- Demo: Attempt stale signature (after 20 min) → 400 BAD REQUEST (TTL expired)

#### 2:35 - 2:45 PM — Night Cycle (10 min)
- Autonomous off-peak verification at 2 AM (no human in loop)
- Re-execute prior day's decisions deterministically
- Immutable append-only Merkle-chained audit log
- Failure pattern analysis: detects rule drift automatically
- Demo: View Merkle root, 24 audit entries, 3 bootstrap candidates

#### 2:45 - 3:00 PM — Air-Gap Capsule Transfer (15 min)
- Dual-custodian protocol: AI signs → USB → Guardian verifies & signs → Dual-signed
- Manifest hash binding prevents tampering
- Self-verification (no CA required)
- Prague PoC 6/6 air-gap validation checks
- Demo: Create capsule (unsigned), Guardian verifies & signs, Capsule ready for transmission

---

## JUNE 5 — DEBRIEF & 3 DECISION GATES (9:00 AM)

### Gate 1: Lead Investor Signal (20 min)
- Is there a lead investor ready for Series A?
- YES → ticket size + timeline (target close June 30)
- NO → Series Seed fallback, extend timeline to July

### Gate 2: Defense Ministry Pilot (20 min)
- Defense pilot opportunity with Israel Ministry of Defense?
- YES → scope pilot (technical, timeline, budget, export controls)
- NO → commercial defense pivot (private contractors, EU)
- MAYBE → follow-up meeting, accelerate Prague PoC

### Gate 3: Patent Filing Status (20 min)
- US Provisional filed with USPTO?
- YES → confirm priority date + receipt number
- NO → identify blockers, June 10 hard deadline
- NO (fundamental) → trade secret + design patent fallback

---

**End of Runbook — Ready for execution June 3-5, 2026**
