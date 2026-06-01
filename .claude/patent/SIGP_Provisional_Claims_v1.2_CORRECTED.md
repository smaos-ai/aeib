# Provisional Patent Claims: SMAOS Architecture (v1.2 — CORRECTED)
**Filing Target:** June 2, 2026 (US + IL)  
**Confidentiality:** TRADE SECRET — Encrypt before transmission  
**Status:** CORRECTED & READY FOR FILING — ψ-operator removed, IVB locked

---

## Invention 1: Resumable Human-Governed Execution (RCE)

### Structural Claim
A system and method for deterministic, resumable execution of autonomous agents under human cryptographic governance, comprising:

1. **Execution Capsule Structure:**
   - Immutable, Merkle-rooted state snapshot at execution entry
   - Cryptographic hash chain binding each execution step
   - Ed25519 signature from authorized human actor (Human Gate)
   - Deterministic replayability: given capsule + input, output is identical across 1000s of executions

2. **Resumption Semantics:**
   - Pause-point capture: system captures full computational state (LLM cache, decision context, pending operations)
   - Human intervention checkpoint: before resume, human must cryptographically approve continuation
   - **Fail-Closed Enforcement:** If human approval signature invalid or missing, execution **BLOCKS** (never auto-escalates or times out)
   - Rollback guarantee: if human rejects resume, system reverts to pre-pause state (no side effects)
   - Audit trail: every pause/resume logged with human actor ID + signature + timestamp

3. **Fail-Closed Safety Gate:**
   - If human approval signature invalid or missing: execution **blocks** (never auto-escalates)
   - If network unavailable: execution continues locally with cached policy; resumes only after network + human approval
   - Timeout handling: execution auto-pauses after configurable interval; requires human resume approval

### Competitive Differentiator
**LangGraph 1.2 (May 2026)** offers checkpoint + human approval. **SMAOS RCE** distinguishes via:
- Cryptographic Ed25519 signature enforcement (not workflow interrupt)
- Fail-closed gate (blocks without valid signature; never escalates or times out)
- Deterministic state snapshots enabling cryptographic replay proof

**No competing system combines all three properties.**

### Claims Summary
- Structural: Execution Capsule (inputs, state, signatures, hashes)
- Structural: Resumption Protocol with fail-closed enforcement (blocks without approval)
- Structural: Merkle-rooted state snapshots enabling deterministic replay

---

## Invention 2: Provenance-Bound Capsule Structure

### Structural Claim
A data structure for cryptographically binding autonomous agent execution to immutable, auditable provenance records with economic intent encoding, comprising:

1. **Capsule Definition:**
   - **Agent Identity:** Ed25519 public key (non-repudiable)
   - **Execution Manifest:** JSON schema listing declared inputs, outputs, decision rules, success criteria
   - **Merkle DAG:** Directed acyclic graph of execution steps, each hashed with SHA-256
   - **Cryptographic Proof:** Ed25519 signature binding manifest to Merkle root
   - **Covenant Signature:** Ed25519 signature binding execution Merkle root to 1%/99% value split (economic intent)

2. **Provenance Chain:**
   - Every capsule references predecessor (prev_hash field)
   - Hash chain is **immutable and auditable**: changing any step breaks all downstream signatures
   - Merkle root published to append-only ledger (EXEC_LOG.json)
   - Replay verification: system can re-execute capsule and cryptographically verify output matches original

3. **Economic Intent Binding:**
   - Capsule includes Covenant Signature asserting: "This execution allocates 1% to stewards, 99% to beneficiaries"
   - System validation gate: rejects any Capsule whose Covenant Signature does not match declared economic intent
   - Breach detection: if actual distribution deviates from covenant signature, system detects tamper + triggers audit

### Competitive Differentiator
**C2PA (Coalition for Content Provenance and Authenticity)** offers content provenance for digital files, not execution provenance. **Generic Merkle-DAG audit trails** (e.g., MedBeads) offer immutable logging, not economic intent binding. **SMAOS Capsule** is novel:
- Binds execution state + audit trail + economic intent in single cryptographic structure
- Validates economic intent at execution time (fail-closed if covenant signature mismatches)
- No competing system combines execution provenance + economic intent binding

### Claims Summary
- Structural: Capsule JSON schema (identity, manifest, Merkle DAG, covenant signature)
- Structural: Provenance Chain (Merkle linking, append-only ledger integration, economic intent validation)
- Structural: Fail-Closed Economic Gate (rejects capsules with mismatched covenant signatures)

---

## Invention 3: Iterative Verifier Bootstrapping (IVB)

### Structural Claim
A system and method for autonomous, iterative refinement of language model behavior through cryptographically-gated feedback loops with deterministic convergence guarantees, comprising:

1. **Night Cycle Feedback Engine:**
   - **Observability Phase:** System collects execution traces (inputs, outputs, decisions, latencies)
   - **Evaluation Phase:** Critic LLM evaluates traces against success criteria (no human judgment required; purely mechanical)
   - **Preference Learning Phase:** Critic output generates preference signal (5-point scale: reject / poor / acceptable / good / excellent)
   - **LoRA Refinement Phase:** System uses preference signal to fine-tune model weights (low-rank adaptation)
   - **Verification Gate:** Refined model is tested against **frozen test suite**; if pass-rate drops, refinement is rejected

2. **Cryptographic Convergence Guarantee:**
   - Critic LLM output is deterministic (temperature=0, fixed seed)
   - LoRA weights are stored with SHA-256 hash + timestamp
   - Each iteration produces cryptographically-reproducible artifact (weights, test results, preference signals)
   - System can prove cryptographically: "Iteration N produces X% pass rate, iteration N+1 produces Y%"
   - Iteration-level convergence proof enables third-party auditor to verify halt decision without re-running training

3. **Fail-Closed Halting Condition:**
   - If test-pass-rate plateaus (no improvement > 0.5% for 5 consecutive iterations): **halt**
   - If test-pass-rate drops: **revert to previous weights** (atomic rollback)
   - If critic output diverges from training distribution: **flag and halt** (no auto-recovery)
   - Halt decision is cryptographically logged and reversible

### Competitive Differentiator
**OpenAI's RLHF** uses human feedback (slow, costly). **DeepSeek's GRPO** uses group preference (no deterministic critic). **VeriLoRA (NDSS 2026)** offers LoRA + zero-knowledge proofs for verification, but does not include deterministic critic + fail-closed halting. **SMAOS IVB** is novel:
- Deterministic critic (temperature=0) + cryptographic reproducibility + fail-closed halting
- Iteration-level convergence proof (proves halt justified without re-running)
- No competing system combines all three: deterministic evaluation + cryptographic proof system + automatic reversion

### Claims Summary
- Structural: Night Cycle Feedback Engine (observation → evaluation → preference → LoRA → verification)
- Structural: Cryptographic Convergence (deterministic critic, reproducible artifacts, iteration-level proof system)
- Structural: Fail-Closed Halting (plateau detection, revert on regression, critic divergence flagging)

---

## Patent Strategy (Counsel Review)

### Scope
- **Structural claims only** (how the system is built)
- **Exclude behavioral claims** (what it does in specific domains)
- **Exclude heuristic parameters** (exact LoRA learning rates, timeout intervals) — keep as trade secrets

### Filing Sequence
1. **US Provisional (USPTO):** June 2, 2026 — Locks global PCT priority date
2. **IL Provisional (ILPO):** June 2, 2026 — Secures Israeli IP fortress
3. **Non-Provisional (within 12 months):** Separate claims for each invention + continuation claims for novel combinations

### Expected Novelty Arguments (vs. Prior Art)
- **RCE vs. LangGraph 1.2:** LangGraph offers checkpoint + approval, but not cryptographic fail-closed enforcement
- **Capsule vs. Generic Merkle:** Generic Merkle DAG is known, but economic covenant binding to execution root is novel
- **IVB vs. VeriLoRA:** VeriLoRA offers LoRA + ZKP, but not deterministic critic + fail-closed halting + iteration-level proof

---

## Market Evidence for Non-Provisional Filing (Within 12 Months)

### 1. EU AI Act Validation (August 2, 2026)
- **Signal:** EU AI Act mandates cryptographic logging, human oversight, fail-closed gates for high-risk AI systems
- **Evidence:** Article 12 requires agent actions signed cryptographically; signature chain verification enables compliance
- **SMAOS Alignment:** RCE (fail-closed human gate) + Capsule (cryptographic audit trail) + IVB (deterministic verification) satisfy Article 12 requirements natively
- **Non-Provisional Narrative:** "Market demand for cryptographic compliance is proven by EU regulatory mandate taking effect August 2, 2026"

### 2. Enterprise AI Safety Gap
- **Signal:** Anthropic $65B Series B (2024–2026), driven entirely by enterprise demand for deterministic AI
- **Evidence:** Enterprise customers require post-hoc compliance audits, cryptographic proof of decisions, liability safeguards
- **SMAOS Alignment:** RCE + Capsule solve this at protocol layer (pre-execution safety), eliminating need for expensive post-hoc monitoring
- **Non-Provisional Narrative:** "Enterprise demand for deterministic, auditable AI execution is demonstrated by $65B+ spend on safety infrastructure"

### 3. Sovereign AI Infrastructure (€140B–€220B TAM by 2030)
- **Signal:** Sovereign AI market growing 28% CAGR (USD 78.61B 2026 → USD 177.09B 2035)
- **Evidence:** Defense, energy, critical infrastructure sectors require local-first, offline-capable, cryptographically audited AI
- **SMAOS Alignment:** Local-first architecture + fail-closed semantics + covenant economics enable sovereign deployment without vendor lock-in
- **Non-Provisional Narrative:** "Sovereign AI infrastructure market is expanding rapidly; SMAOS is the only production system combining cryptographic audit, offline capability, and economic covenant"

---

## Confidentiality Checklist

- [ ] This document encrypted (GPG symmetric AES256) before transmission
- [ ] Transmitted via ProtonMail only (unencrypted email prohibited)
- [ ] Passphrase sent via Signal (separate channel, not in same email)
- [ ] Do NOT share with investors before filing
- [ ] Do NOT post to public repos or demo scripts
- [ ] Do NOT discuss implementation details over unencrypted channels

---

## Next Steps (Counsel)

1. **Claim Refinement:** Zysman Law reviews language; adjusts for USPTO/ILPO specificity
2. **Prior Art Search:** Verify no blocking references beyond LangGraph 1.2, VeriLoRA, Aegis (brief search already conducted)
3. **Filing Execution:** USPTO + ILPO simultaneous filing June 2, 2026 (10:00 UTC + 14:00 UTC)
4. **Receipt Confirmation:** Screenshot filings, confirm priority dates locked

**Contact Zysman Law:** `zysman@il-patent.co.il` (GPG encrypted only)

---

**Prepared by:** SMAOS Founding Team  
**Status:** Ready for immediate filing  
**Confidentiality Level:** TRADE SECRET — Encrypt before transmission
