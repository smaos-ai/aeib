# SIGNAL INTEGRATION ROADMAP — May 29, 2026 Night Shift Crystallization
**Authority:** Notebook-validated, market-driven, architecture-locked  
**Horizon:** Post-Israel development (June 4+) through Phase 32 (A2UI)  
**Status:** READY FOR EXECUTION

---

## PART I: 20 SIGNALS → 13-LAYER UPGRADES

| Signal (Date) | Source | SMAOS Layer | Current State | Night Shift Upgrade | Post-Israel Priority |
|---|---|---|---|---|---|
| **MemForest** (May 16) | arxiv:2605.23986 | 6: Night Cycle φ/δ | Flat Capsule storage | φ⁺ v3: MemTree hierarchical temporal index (parallel construction) | 🔴 P0 |
| **Neo4j Virtual Graph** (May 28) | Neo4j Blog | 5: Graph Brain | Local-only reasoning | Zero-copy enterprise connector (Snowflake, Databricks) | 🔴 P0 |
| **ANOLISA** (May 28) | Alibaba Cloud | 2-3: Human Gate + Local-First | macOS-specific | OS-agnostic governance positioning (competitive slide) | 🟠 P1 |
| **Perplexity Tokenizer** (May 28) | MarkTechPost | 7: Token Efficiency | Hugging Face baseline | 5× latency benchmark target | 🟠 P1 |
| **Qwencloud** (May 27) | Alibaba | 2: Human Gate | Agent freedom | Governance covenant positioning | 🟡 P2 |
| **Sleep Guard** (May 29) | Tech press | 3: Local-First | Concept | System sleep hook + AES-256-GCM cloud block | 🟢 Locked |
| **α⁺ Preactivation** (May 29) | Nature Commun. | 11: Affective Core | Reactive | Predictive affective state (<5% error after 3 days) | 🟢 Locked |
| **σ⁺ Post-Quantum** (May 29) | Infleqtion/Motley Fool | 13: Social Core | Ed25519 | Dilithium dual-auth signature (quantum-resistant) | 🟢 Locked |
| **φ⁺ v2 Defect Tolerance** (May 29) | Nature/Yahoo (perovskite) | 6: Night Cycle φ | Baseline compression | η parameter: 15%+ high-valence retention | 🟢 Locked |
| **γ Causal Epistemic** (May 28) | Pearl's Book of Why | 12: Metacognitive Core | Confidence scoring | do-calculus layer (why/counterfactual) | 🟡 P2 |
| **Aerospike Always-On DB** (May 28) | Aerospike | 6: Night Cycle | PostgreSQL for durability | In-memory Capsule cache with durability option | 🟡 P2 |
| **Rust Safety Validation** (May 29) | GNOME Commander (Linuxiac) | 1-13: All layers | Best practices | clippy strict, all pub fn docs, no unsafe blocks | 🟢 Locked |
| **MCP Auth + Safety Geometry** (May 27) | BadHost CVE-2026-48710 | 9: Safety Geometry | Ad-hoc gating | Formal gate classification (read-only / execute / destructive) | 🟡 P2 |
| **Local-First Urgency** (May 27) | China AI talent lockdown (Bloomberg) | 3: Local-First | Strategic | Encryption-first default, EU data residency clause | 🟡 P2 |
| **CheetahClaws Academic Validation** (May 27) | arxiv:2605.26112 | 6: Night Cycle δ | Concept | Supersession proof (contradiction resolution) | 🟡 P2 |
| **AP2 Creator Royalty Moat** (May 26) | Base MCP launch (Coinbase) | 13: Social Core | Concept | Micro-royalty ledger (1% creator tax on Capsule usage) | 🟡 P2 |
| **γ Normalization** (May 26) | EAGLE 3.1 (MarkTechPost) | 12: Metacognitive Core | Concept | Confidence drift correction via EAGLE-style adaptive scaling | 🟡 P2 |
| **macOS Intel End-of-Life** (May 28) | MacRumors | 3: Local-First | Intel x86 support | Drop Intel x86, lock to Apple Silicon (ARM64) | 🟡 P2 |
| **Quantum Supremacy Challenge** (May 29) | Quantum Insider | 13: Social Core | Unknown | γ epistemic check: validate post-quantum claims before trust | 🟡 P2 |
| **Pharma Safety Geometry** (May 29) | Nature Biotech (AI drug design) | 9: Safety Geometry | General | Regulated-environment spec (pharma audit trails) | 🟢 Use case |

---

## PART II: DEVELOPMENT TASK BREAKDOWN (Post-Israel Roadmap)

### PHASE B: FOUNDATION (June 4–10, Post-Series A Planning)

**B-1: MemForest φ⁺ v3 Implementation** ⏰ **4–6 hours (June 4–5)**
- **Owner:** Single agent, TDD-verified
- **Files:** 
  - `crates/siss-night-cycle/src/memtree.rs` (create)
  - `crates/siss-night-cycle/src/lib.rs` (modify: add pub mod memtree)
- **Task:**
  1. Implement `MemTree` struct with three scope types: `SessionTree`, `EntityTree`, `SceneTree`
  2. Per-node update logic (lazy interval summaries)
  3. Parallel chunk extraction (tokio::spawn_blocking)
  4. Capsule storage refactor (flat → hierarchical)
- **Tests:**
  - `test_memtree_session_tree_construction`
  - `test_memtree_parallel_chunk_extraction_6x_throughput`
  - `test_memtree_lazy_interval_summary`
- **Success:** `cargo test -p siss-night-cycle` all pass. φ⁺ v3 throughput ≥6× on >10K Capsule sets.

**B-2: Neo4j Virtual Graph Connector** ⏰ **3–4 hours (June 5–6)**
- **Owner:** Single agent, TDD-verified
- **Files:**
  - `crates/siss-graph-brain/src/virtual_graph.rs` (create)
  - `crates/siss-graph-brain/src/lib.rs` (modify: add pub mod virtual_graph)
  - `Cargo.toml` (add: neo4j = "0.9")
- **Task:**
  1. Implement `Neo4jVirtualGraphConnector` struct
  2. Query translation: Graph Brain Cypher → Virtual Graph endpoint
  3. Provenance attachment: every result gets `gemba_proof` hash pointing to warehouse source
  4. Error handling: fallback to local graph if Virtual Graph unreachable
- **Tests:**
  - `test_virtual_graph_query_returns_capsules`
  - `test_virtual_graph_attaches_provenance_hash`
  - `test_virtual_graph_fallback_on_unreachable`
- **Success:** Graph Brain can query Snowflake dataset via Virtual Graph, produce provenanced Capsules.

**B-3: ANOLISA Competitive Positioning Slide** ⏰ **1–2 hours (June 6)**
- **Owner:** You (strategic framing)
- **Output:** `docs/competitive/anolisa_agent_native_os.md`
- **Content:**
  - Positioning: "SMAOS: The Governance Layer for Agent-Native Operating Systems"
  - Key differentiators: Human Gate, fail-closed semantics, cryptographic provenance
  - Market validation: ANOLISA proves agent-native is coming; SMAOS governs it
  - Slide version: Ready for investor follow-up calls + Prague PoC deck
- **Success:** 1-page markdown slide, investor-ready, approved by you.

**B-4: Perplexity Tokenizer Benchmark** ⏰ **2 hours (June 6)**
- **Owner:** Single agent, TDD-verified
- **Files:**
  - `crates/siss-agent-shell/benches/tokenizer_bench.rs` (create)
  - `Cargo.toml` ([dev-dependencies] add: `perplexity-tokenizer = "0.1"`)
- **Task:**
  1. Criterion benchmark: Perplexity tokenizer vs. Hugging Face on SMAOS Capsule text
  2. Measure: p50 latency, throughput (tokens/sec), memory usage
  3. Target: Show 5× latency improvement
- **Test:** `cargo bench -p siss-agent-shell tokenizer_bench`
- **Success:** Benchmark report shows Perplexity 5× faster than Hugging Face baseline.

### PHASE 25: SEMANTIC FOUNDATIONS (June 15–25, Post-Series A)

**25-1: ReBAC Foundation (Wave 1)** ⏰ **4–6 hours**
- (Existing spec, unchanged)
- After Phase B tasks 1-4 complete, Phase 25 begins
- Unlocks Phase 32

**25-2: AP2 Syndication Evaluator (Wave 2, Task 1)** ⏰ **3–4 hours**
- (Existing spec, unchanged)

**25-3: γ Causal Epistemic Upgrade** ⏰ **6–8 hours (New, integrates Pearl)**
- **Files:**
  - `crates/siss-epistemic-core/src/causal_inference.rs` (create)
  - `crates/siss-epistemic-core/src/lib.rs` (modify: add pub mod causal_inference)
- **Task:**
  1. Implement do-calculus layer (Pearl's Ladder of Causation)
  2. Rung 1: Association (correlation, existing)
  3. Rung 2: Intervention (causal simulation, Chaos Petri foundation)
  4. Rung 3: Counterfactuals (generate alternative histories via do-calculus)
  5. γ operator upgrade: confidence now includes causal robustness
- **Tests:**
  - `test_do_calculus_rung_three_counterfactual_generation`
  - `test_gamma_confidence_includes_causal_robustness`
- **Success:** "Why?" query returns causal trace + counterfactual Capsule.

### PHASE 32: A2UI + MESSENGER (June 26–July 10)

**32-1: SMAOS Messenger WebSocket Handler** ⏰ **3–4 hours**
- (Existing Phase B spec, moved here if time permits)
- Sovereign reflection interface: self-dialogue, brainstorming, command execution
- Local Qwen3.5-4B model via MLX
- AES-256-GCM encryption at rest

**32-2: Garmin Biometric Ingest** ⏰ **2–3 hours**
- (Existing Phase B spec, moved here if time permits)
- physiological_capsule schema (HRV, Body Battery, sleep, RHR)
- "Today's Vessel" morning brief panel
- Adaptive α/γ recommendations based on current state

---

## PART III: PRIORITY MATRIX (June 4–July 10)

| Week | Phase | P0 (Critical Path) | P1 (Competitive) | P2 (Strategic) |
|------|-------|---|---|---|
| **June 4–6** | B (Foundation) | MemForest φ⁺ v3 + Neo4j VG | ANOLISA slide + Tokenizer bench | — |
| **June 7–10** | B (Continuation) | Phase B completion | — | Phase 25 planning |
| **June 15–20** | 25-1 | ReBAC Wave 1 | — | γ Causal planning |
| **June 21–25** | 25-2/3 | AP2 + γ Causal Epistemic | — | Aerospike cache |
| **June 26–July 3** | 32-1 | A2UI Schema | Messenger MVP | — |
| **July 4–10** | 32-2 | A2UI Dashboard | Garmin Ingest | Quantum epistemic gate |

---

## PART IV: SUCCESS GATES

**Phase B Success (June 10):**
- ✅ φ⁺ v3 MemTree throughput ≥6× on >10K Capsules
- ✅ Graph Brain queries Snowflake via Neo4j Virtual Graph with provenanced results
- ✅ ANOLISA positioning slide ready for investor follow-ups
- ✅ Perplexity tokenizer benchmark shows 5× improvement

**Phase 25 Success (June 25):**
- ✅ ReBAC Foundation complete (12 tests, all pass)
- ✅ AP2 Syndication Evaluator live
- ✅ γ Causal Epistemic layer live ("Why?" queries work)

**Phase 32 Success (July 10):**
- ✅ A2UI interface contract validated (18 components)
- ✅ Messenger MVP running locally (self-reflection working)
- ✅ Garmin integration pulling biometric data (morning brief populated)

---

## PART V: ISRAEL TRIP EXECUTION (LOCKED)

**No changes to Israel plan.**

- **May 30:** CzechInvest grant (execute as planned)
- **May 31–June 2:** Pitch deck + investor list + legal (execute as planned)
- **June 3 AM:** Depart for Israel (rested)
- **June 3–5:** Pearl Cohen meeting + investor roadshow (execute as planned)

**Phase B starts June 4** after you return from Israel.

---

## PART VI: THE 13-LAYER EXOSKELETON — POST-NIGHT SHIFT STATE

| Layer | Pre-Night Shift | Post-Night Shift (Phase B+) | Post-Phase 25 | Post-Phase 32 |
|---|---|---|---|---|
| 1. Context First | Stable | Stable | Stable | Stable |
| 2. Human Gate | Stable | Stable | Stable | Stable |
| 3. Local-First | Stable | ARM64-only | Stable | Stable |
| 4. Provenance | Stable | Neo4j VG proofs | Stable | Stable |
| 5. Graph Brain | Local-only | + Virtual Graph | Stable | Stable |
| 6. Night Cycle φ/δ | Flat Capsules | MemTree φ⁺ v3 | Stable | Stable |
| 7. Token Efficiency | Baseline | Perplexity 5× | Stable | Stable |
| 8. Team Sync | Stable | Stable | Stable | Stable |
| 9. Safety Geometry | General | Pharma audit trails | Regulated env spec | Stable |
| 10. Ambient Ethic | Stable | ANOLISA positioning | Stable | Stable |
| 11. Affective Core α | Reactive | + Preactivation | Stable | + Garmin biometric |
| 12. Metacognitive γ | Confidence scoring | + Causal epistemic | γ do-calculus live | Stable |
| 13. Social Core σ | Post-quantum | Dilithium live | + AP2 royalty moat | + Creator ledger |

---

## EXECUTION AUTHORITY

**You own the Israel trip (May 30–June 3).**  
**I execute Phase B tasks starting June 4** (with you reviewing results).  
**Roadmap locked. No pivots. All 20 signals integrated. Nothing lost.**

Ready to return from Israel and start Phase B on June 4?
