---
name: decide
description: Epistemic Adversarial Research & Decision Engine (v2.0). Executes Stage 0 O(1) Constant-Time Codebase Snapshot, Stage 1 Separated Independent Multi-Vector Search (arXiv, Western GitHub, China Open-Source), Stage 2 5-Why Root-Cause & Set-Theoretic Delta Alignment, and Stages 3-4 Two-Iteration Layered Self-Critique ('What We Missed' on external claims AND on our own proposed code layer). Trigger on /decide, $decide, 'what we missed', or 'adversarial research'.
---

# /decide v2.0 — O(1) Codebase Snapshot, 5-Why & Two-Iteration Epistemic Decision Engine

The `/decide` v2.0 skill switches the agent from passive autocomplete into a **Recursive, Self-Auditing Thinking Agent**. It eliminates two classic failure modes in AI-assisted engineering:
1. **Context-Blind Wheel Reinvention**: Searching the web without knowing in constant time ($O(1)$) what moats, classes, `HALT_*` codes, and tests already exist in our local repository.
2. **Single-Pass Critique Fallacy**: Critiquing external papers in Iteration 1, but failing to run a second adversarial pass (Iteration 2) against our *own* newly proposed integration layer.

## 🧠 Core Operating Philosophy
1. **Stage 0 First ($O(1)$ Self-Knowledge Snapshot)**: Before external synthesis, consult the precomputed AST Moat & Symbol Index (`python3 tools/decide_v2_constant_time_snapshot.py`) to know in $< 1\text{ ms}$ what `src/`, `compliance/`, `tools/`, and `tests/` already enforce.
2. **Strict Separation of Internal vs. External State**: Query external ecosystems (**Academic arXiv/IETF**, **Western GitHub**, **Chinese Open-Source Labs**) *independently* of local naming conventions so external discovery is never biased by local jargon, then compute the exact set-theoretic delta:
   - $\text{Covered } (A \cap B)$: Already enforced in AEIB (do not rebuild).
   - $\text{True Gap } (B \setminus A)$: High-signal external primitive to layer onto Station 1/2/3.
   - $\text{Overclaim } (B_{\text{unverified}})$: Reject claims lacking reproducible code or cryptographic wire receipts.
3. **5-Why + Two-Iteration Layered Critique**:
   - **Iteration 1 ("What We Missed" in External SOTA)**: Critique external findings against AEIB wire-finality invariants.
   - **Iteration 2 ("What We Missed" in Our Proposed Layer)**: Critique the candidate code layer we just designed until residual structural conflicts $\Delta_2 = 0$.
4. **Epistemic Calibration**: Permitted words: `"observed"`, `"tested"`, `"evaluated"`, `"configured"`, `"under the stated model"`, `"prototype"`, `"scaffold"`, `"pre-production"`. Banned words: `"guaran[t]eed"`, `"bullet[p]roof"`, `"enterprise-[g]rade"`, `"production-[s]afe"`, `"100% [s]ecure"`, `"unassail[a]ble"`, `"im[m]une"`, `"unhack[a]ble"`, `"bank-[g]rade"`, `"production-[r]eady"`, `"proven universal[l]y"`.

---

## 🔄 The 5-Stage Recursive Execution Pipeline

When `/decide` is invoked, execute these 5 stages sequentially:

### Stage 0: O(1) Constant-Time Codebase Snapshot (`What We Have`)
Run or query `tools/decide_v2_constant_time_snapshot.py` (`ConstantTimeCodebaseSnapshot.query_o1(keyword)`) to retrieve in $O(1)$ time:
- Existing Python/Rust modules, classes, and functions across the 6 AEIB Moat Categories.
- Existing `HALT_*` and `ERR_*` fail-closed enforcement codes.
- Existing primary citations (`arXiv:*`, `RFC *`) already wired into tests.

### Stage 1: Separated Independent Multi-Vector Search (`What Exists Outside`)
Deconstruct the query into 3 orthogonal external vectors (executed independently of Stage 0 to avoid confirmation bias):
- **Vector A (Academic & Formal Proofs)**: Search arXiv, ACM, IEEE, NeurIPS, OSDI, VLDB, and IETF drafts.
- **Vector B (Western GitHub & Systems)**: Search active Rust/C++/Python repositories (e.g., `GitNexus`, `Codebase-Memory`, `Ripwire`, `Tetragon`, `TigerBeetle`).
- **Vector C (Chinese Open-Source & High-Throughput Runtimes)**: Search DAMO/Alibaba (`AgentScope 2.0`, `OpenCodeReview`, `LocAgent`), Ant Group (`AgentAegis`), Tsinghua (`ACID-Agent`), Fudan, and DeepSeek/Qwen ecosystems.

### Stage 2: 5-Why Root-Cause Chain & Set-Theoretic Alignment Delta
Run a **5-Why Root-Cause Analysis** (`Why 1` Symptom $\to$ `Why 2` Process Gap $\to$ `Why 3` Indexing/Substrate Gap $\to$ `Why 4` Single-Pass Limit $\to$ `Why 5` Root Architectural Fix) and classify every external finding into:
1. `[ALREADY_COVERED_IN_LOCAL_MOAT]` — Map to exact local file and symbol.
2. `[CANDIDATE_ADDITIVE_LAYER]` — Identify which Station (1, 2, or 3) it layers onto.
3. `[REJECTED_UNVERIFIED_OVERCLAIM]` — Strike unverified vendor/benchmark claims.

### Stage 3: Iteration 1 Critique — `### 🔍 WHAT WE MISSED: PASS 1 (External SOTA Audit)`
Critique the external candidates against 4 failure traps:
1. **Prior Art Collision**: Who published the underlying math first?
2. **Wire-Finality & Concurrency Race**: How does the external tool behave on `HTTP 504` timeouts, clock drift, or 1,000-agent bursts?
3. **Provenance & Taint Blindness**: Does it trust unverified LLM narration (`AI_GENERATED_UNVERIFIED`) or allow silent approval bypasses?
4. **Premise Falsification**: Which assumptions in the prompt or external paper fail under adversarial conditions?

### Stage 4: Iteration 2 Critique — `### 🔍 WHAT WE MISSED: PASS 2 (Self-Audit on Our Proposed Layer)` & Code Delivery
Before writing or committing code, audit *our own proposed integration layer*:
1. Identify at least 2 concrete edge cases, type bugs, or bypass risks in our draft design.
2. Harden the code (integer basis points/minor units, Ed25519 signatures, RFC 8785 JCS, zero mocks).
3. Run `pytest`, `compliance/ast_purity.py`, `compliance/no_mock_enforcer.py`, and re-index the $O(1)$ Codebase Snapshot.
