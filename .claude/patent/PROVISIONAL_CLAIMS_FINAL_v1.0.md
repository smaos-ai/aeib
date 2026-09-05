# Provisional Patent Claims: SMAOS Architecture (v1.0)
**Filing Target:** June 2, 2026 (US + IL)  
**Confidentiality:** TRADE SECRET — Encrypt before transmission  
**Status:** DRAFT — Ready for counsel review

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
   - Rollback guarantee: if human rejects resume, system reverts to pre-pause state (no side effects)
   - Audit trail: every pause/resume logged with human actor ID + signature + timestamp

3. **Fail-Closed Safety Gate:**
   - If human approval signature invalid or missing: execution **blocks** (never auto-escalates)
   - If network unavailable: execution continues locally with cached policy; resumes only after network + human approval
   - Timeout handling: execution auto-pauses after configurable interval; requires human resume approval

### Competitive Differentiator
**No existing system** offers deterministic resumption + cryptographic human gate + fail-closed semantics together. LangChain offers serialization; CrewAI offers callbacks; neither offers the trinity.

### Claims Summary
- Structural: Execution Capsule (inputs, state, signatures, hashes)
- Structural: Resumption Protocol (pause → human approval → resume semantics)
- Structural: Fail-Closed Gate (rejection = block, not escalation)

---

## Invention 2: Provenance-Bound Capsule Structure

### Structural Claim
A data structure for cryptographically binding autonomous agent execution to immutable, auditable provenance records, comprising:

1. **Capsule Definition:**
   - **Agent Identity:** Ed25519 public key (non-repudiable)
   - **Execution Manifest:** JSON schema listing declared inputs, outputs, decision rules, success criteria
   - **Merkle DAG:** Directed acyclic graph of execution steps, each hashed with SHA-256
   - **Cryptographic Proof:** Ed25519 signature binding manifest to Merkle root
   - **Covenant Signature:** Ed25519 signature binding execution to 1%/99% value split (economic intent)

2. **Provenance Chain:**
   - Every capsule references predecessor (prev_hash field)
   - Hash chain is **immutable and auditable**: changing any step breaks all downstream signatures
   - Merkle root published to append-only ledger (EXEC_LOG.json)
   - Replay verification: system can re-execute capsule and cryptographically verify output matches original

3. **Economic Intent Binding:**
   - Capsule includes Covenant Signature asserting: "This execution allocates 1% to stewards, 99% to beneficiaries"
   - Breach detection: if actual distribution deviates from covenant signature, system detects tamper + triggers audit

### Competitive Differentiator
**C2PA (Coalition for Content Provenance and Authenticity)** offers content provenance, not execution provenance. **Arize** offers model monitoring, not immutable execution binding. **SMAOS capsule** is novel: it binds execution + covenant + audit in a single cryptographic structure.

### Claims Summary
- Structural: Capsule JSON schema (identity, manifest, Merkle DAG, signatures)
- Structural: Provenance Chain (Merkle linking, append-only ledger integration)
- Structural: Covenant Signature (economic intent + tamper detection)

---

## Invention 3: Iterative Verifier Bootstrapping (IVB)

### Structural Claim
A system and method for autonomous, iterative refinement of language model behavior through cryptographically-gated feedback loops, comprising:

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
   - System can prove: "Iteration N produces X%, iteration N+1 produces Y%"

3. **Fail-Closed Halting Condition:**
   - If test-pass-rate plateaus (no improvement > 0.5% for 5 consecutive iterations): **halt**
   - If test-pass-rate drops: **revert to previous weights**
   - If critic output diverges from training distribution: **flag and halt** (no auto-recovery)

### Competitive Differentiator
**OpenAI's RLHF** uses human feedback, not automated critic. **DeepSeek's GRPO** uses group preference, not deterministic critic. **SMAOS IVB** is novel: deterministic critic + cryptographic reproducibility + fail-closed halting.

### Claims Summary
- Structural: Night Cycle Feedback Engine (observation → evaluation → preference → LoRA → verification)
- Structural: Cryptographic Convergence (deterministic critic, reproducible artifacts, proof system)
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

### Expected Novelty Arguments
- **RCE:** No prior art combines deterministic resumption + cryptographic human gate + fail-closed semantics
- **Capsule:** C2PA is for content; SMAOS capsule is for execution + covenant binding
- **IVB:** RLHF uses humans; IVB uses deterministic critic + cryptographic reproducibility

---

## Problem-Space Validation (Market Evidence for Non-Provisional)

The following market signals validate that SMAOS addresses a real, urgent, and rapidly expanding problem-space. These are **supporting evidence for the non-provisional patent application** (within 12 months), not new claims for the provisional:

### 1. Enterprise AI Safety Gap (Anthropic $65B Validation)
- **Signal:** Anthropic's $65B Series B valuation (2024–2026) driven entirely by enterprise demand for safe, deterministic AI
- **Evidence:** Enterprise customers require post-hoc monitoring, compliance audits, and liability safeguards for autonomous agent systems
- **SMAOS Alignment:** RCE + Capsule solve this at the protocol layer (pre-execution Safety Geometry), eliminating the need for expensive post-hoc monitoring
- **Non-Provisional Narrative:** "Market demand for deterministic, auditable AI execution is demonstrated by $65B+ enterprise spend on safety infrastructure"

### 2. Edge Computing & Quantum-Ready Inference (Topological States + Quantum Genome)
- **Signal:** Emergence of topological quantum computing (IBM, Google, IonQ) + quantum machine learning frameworks
- **Evidence:** Edge-local inference (Rapid-MLX, mobile quantum processors) requires deterministic, reproducible execution for cryptographic verification
- **SMAOS Alignment:** IVB's deterministic critic + Capsule's Merkle provenance enable quantum-safe, locally-verifiable inference chains
- **Non-Provisional Narrative:** "Quantum-era autonomous systems require cryptographic provenance + deterministic refinement to ensure post-quantum audit trails"

### 3. Local-First Sovereignty & Crafter Economy
- **Signal:** Quantum genome loading (DNA-as-data for bio-edge computing) + sovereign AI demand in EU (AI Act), Israel (national security), Ukraine (conflict zones)
- **Evidence:** Regions with strict data residency laws require local-first, non-cloud AI execution with offline-first fallback
- **SMAOS Alignment:** Personal Mode + local SQLite + air-gap isolation enable full sovereignty without vendor lock-in
- **Non-Provisional Narrative:** "Post-cloud computing requires sovereign, locally-verifiable agents; SMAOS architecture is the first production system combining deterministic execution, cryptographic audit, and 100% local control"

---

## Confidentiality Checklist

- [ ] Print this document on air-gapped machine only
- [ ] Encrypt with GPG (Zysman Law public key)
- [ ] Transmit via encrypted email (ProtonMail) or Signal
- [ ] Do NOT share with investors before filing
- [ ] Do NOT post to public repos or demo scripts
- [ ] Do NOT discuss implementation details over unencrypted channels

---

## Next Steps (Counsel)

1. **Claim Refinement:** Zysman Law reviews structural language; adjusts for USPTO/ILPO specificity
2. **Prior Art Search:** Verify no blocking references (especially C2PA, RLHF, LoRA literature)
3. **Economic Claim:** Add covenant signature patent (novel binding of execution to economic intent)
4. **Filing Execution:** USPTO + ILPO simultaneous filing June 2, 2026

**Contact Zysman Law:** `zysman@il-patent.co.il` (GPG encrypted only)
