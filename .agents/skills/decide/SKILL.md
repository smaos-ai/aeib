---
name: decide
description: Epistemic Adversarial Research & Decision Engine. Intercepts queries using the cognitive trigger 'what we missed' to force an adversarial, multi-step thinking pipeline. Deconstructs queries into parallel research vectors, audits blind spots and prior art, executes multi-step synthesis, and delivers concrete runnable code roadmaps. Trigger on /decide, $decide, 'what we missed', or 'adversarial research'.
---

# /decide — Epistemic Adversarial Research & Decision Engine

The `/decide` skill intercepts user queries and switches the agent from generative autocomplete into an adversarial, multi-step **Thinking Agent** mode. It prevents AI sycophancy, premature convergence, and hallucinated confidence by mandating cross-vector verification and blind-spot auditing.

## 🧠 Core Operating Philosophy
1. **The "What We Missed" Mandate**: The model must actively search for counter-evidence, existing prior art, and structural failure modes before synthesizing answers.
2. **Parallel Vector Dispersal**: Every inquiry must be split into academic (arXiv/peer-reviewed), practical open-source (GitHub/implementations), and live industrial telemetry vectors.
3. **Epistemic Calibration**: Permitted words: "observed", "tested", "evaluated", "configured", "under the stated model", "prototype", "scaffold". Banned words: "guaranteed", "bulletproof", "enterprise-grade", "production-safe", "100% secure", "unassailable", "immune", "unhackable".

---

## 🔄 The 4-Phase Execution Pipeline

When `/decide` is invoked (or when the user asks "what we missed" / demands rigorous multi-step analysis), execute these 4 phases sequentially:

### Phase 1: Deconstruction & Multi-Vector Search
Split the user query into 3–5 distinct, independent research vectors. Run live search queries across each vector:
- **Vector A (Academic / Formal Proofs)**: Search arXiv, ACM, IEEE, NeurIPS, VLDB, and university technical reports for mathematical formulations and theoretical limits.
- **Vector B (GitHub / Open-Source Code)**: Search active repositories, commits, and issue trackers for production Rust/Python/Go implementations, real benchmarks, and latency profiles.
- **Vector C (Industry Telemetry / Standards)**: Search RFCs, W3C standards, regulatory directives (DORA, EU AI Act, CAC, NIST), and live outage postmortems.

### Phase 2: The "WHAT WE MISSED" Mandate (Adversarial Audit)
Before proposing any solution, output a dedicated section titled:
`### 🔍 WHAT WE MISSED (Blind Spots & Prior Art)`
Critique the Phase 1 findings against 4 ruthless criteria:
1. **Prior Art Collision**: Who has already built or published this? (Avoid reinventing existing wheels like `forked`, `Dendrite`, or `PERSIST`).
2. **Hidden Failure Modes & Asymmetric Risks**: What happens under network partitions, memory exhaustion, clock drift, malicious poisoning, or 504 timeouts?
3. **Contrarian & Independent Evidence**: What do independent benchmarks or opposing academic schools of thought demonstrate?
4. **Premise Falsification**: Are the user's initial assumptions or system constraints factually accurate?

### Phase 3: Multi-Step Quantitative Synthesis
Synthesize the verified evidence into structured tables, mathematical formulas, and state diagrams:
- Report exact numbers (e.g., latency in milliseconds, memory overhead, compression ratios).
- Mark any unverified metric or projection explicitly as `[UNVERIFIED / PROJECTION]`.
- Provide exact primary citations and dates.

### Phase 4: Concrete Execution Roadmap & Code Action Plan
Deliver runnable code and deterministic test fixtures:
- Provide drop-in Python/Rust source implementations.
- Write non-tautological test fixtures with negative controls and fault injection.
- Run local compliance checks (AST purity, zero-mock enforcer, zone boundaries).

---

## 🛠️ Usage Examples

```text
/decide How do we build an idempotent wire boundary for autonomous agents?
/decide what we missed in our KV-cache memory governance?
/decide audit multi-agent collusion risks in shared-ledger sagas
```
