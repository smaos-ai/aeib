---
name: decide
description: Epistemic Adversarial Research & Cross-Hemisphere Council Decision Engine (v3.2). Formalizes CURRENT -> MISSED(CURRENT) -> BRAINSTORM -> NEXT with the Decide | Ask | Defer 3-Action Policy (arXiv:2610.04542), 3-Tier Ask Resolution Router (Parent O(1) Snapshot -> Live Web/GitHub Probe -> Developer Clarification Schema), Asymmetric Evidence Dominance defeating the 32.3% Oracle Gap (arXiv:2605.00914), Typed Cross-Critique (arXiv:2609.08016), and Weighted Partial MaxSAT synthesis. Trigger on /decide, $decide, 'what we missed', or 'adversarial research'.
---

# `/decide` v3.2 — Categorical Epistemic Engine & Cross-Hemisphere `Decide | Ask | Defer` Council

The `/decide` v3.2 skill transforms the agent from single-shot autocomplete into a **Mathematically Grounded, Cross-Hemisphere Multi-Model Epistemic Council & `Ask` Router** (`tools/cross_hemisphere_council_decide.py`, `tools/current_missed_next_calculus.py`, `src/decide_categorical_epistemic_engine.py`, & `tools/decide_v2_constant_time_snapshot.py`).

---

## 🏛️ I. Philosophical & Mathematical Foundation

### The Five Mathematical & Empirical Laws of `/decide` v3.2
1. **Law 1 — Submodular Information Gain via 8-Axis Orthogonal Keyword Tag Expansion (`arXiv:2502.08557`, Nemhauser-Wolsey-Fisher)**:
   Expanding any research query across $D = 8$ mutually orthogonal keyword tag axes $K = \{k_1, \dots, k_8\}$ maximizes the monotone submodular mutual information function $F(K) = I(\Omega; X_K)$. Across $N = 28$ combined moat and invariant nodes, this resolves $\binom{28}{2} + 28 = 406$ pairwise cross-domain interaction edges versus $3$ edges in a single-shot prompt — a **$135\times$ ($\ge 100\times$) Pairwise Compositional Coverage Multiplier**.
2. **Law 2 — Formal Concept Analysis (FCA) Galois Boundary Operator (`MISSED` $= \partial(\text{CURRENT})$)**:
   `MISSED` operates **strictly on `CURRENT` only** ($\mathcal{C} = \mathcal{C}_{\text{local}} \cup \mathcal{C}_{\text{humanity\_today}}$). Over the incidence matrix $\mathcal{I} \subseteq \mathcal{O} \times \mathcal{A}$, $\partial(\mathcal{C})$ extracts:
   - **Local Absorption Gaps**: $\text{Attr}(\mathcal{C}_{\text{humanity}}) \setminus \text{Attr}(\mathcal{C}_{\text{local}})$
   - **Humanity Wire-Finality Flaws**: $\text{Attr}(\mathcal{C}_{\text{local}}) \setminus \text{Attr}(\mathcal{C}_{\text{humanity}})$
   - **Galois Frontier Voids**: $\mathcal{A}_{\text{universal}} \setminus (\text{Attr}(\mathcal{C}_{\text{local}}) \cup \text{Attr}(\mathcal{C}_{\text{humanity}}))$
3. **Law 3 — Cross-Hemisphere `Decide | Ask | Defer` Policy Divergence & 3-Tier `Ask` Router (`arXiv:2610.04542`, Oct 2026)**:
   Across 200 incomplete-evidence states, `Qwen` (China) and `Gemini`/`GPT` (USA) diverge on action selection in **137 of 200 states** (and 37 of 50 in incomplete-evidence subsets): `Qwen` selects `ASK` up to 80% of the time under low evidence while `Gemini`/`GPT` jump straight to `DECIDE`. Instead of dropping `Qwen`'s `ASK` queries, `ThreeTierAskResolutionRouter` routes every `ModelAskQuery` through a 3-Tier hierarchy before synthesis:
   - **Tier 1 (`PARENT_O1_SNAPSHOT`)**: Instant $O(1)$ hash-table lookup against `CurrentCategorySnapshot` / `ConstantTimeCodebaseSnapshot` if the question asks about our existing codebase, moats, or invariants.
   - **Tier 2 (`WEB_SEARCH_PROBE`)**: Deterministic live web/arXiv/GitHub probe if the question asks about external 2026 SOTA or empirical failure rates (e.g., `arXiv:2609.37475` `60.527%` Invalid Commit Rate on action-only binding).
   - **Tier 3 (`PENDING_DEVELOPER` Schema Escalation)**: Emits a structured `developer_questions_schema` (and `to_ask_question_modal_payload()`) when only the human developer pair can decide an architectural deployment branch.
4. **Law 4 — Asymmetric Evidence Dominance Defeating the 32.3% Oracle Gap (`arXiv:2605.00914`, Bertalanič & Fortuna, ACM CAIS 2026; `arXiv:2609.08016`, Chen Qian, CMU)**:
   Unguided multi-agent debate suffers from **85.5% Sycophantic Conformity**, **32.3% Consensus Collapse (Oracle Gap)**, **2.1×–3.4× Token Inflation**, and superficial tone-driven dissent (`arXiv:2609.08016`). In `CrossHemisphereEpistemicCouncil`:
   - **Asymmetric Evidence Dominance**: A single minority model (`1 against 3`, e.g., `deepseek-v4-pro+perplexity-sonar`) backed by a verified deterministic counterexample or primary source URL (`has_verified_counterexample_or_url=True`) mathematically overrides $N$ unverified majority votes (`unique_minority_insights_preserved`, `oracle_gap_prevented=True`).
   - **Typed Cross-Critique (`TypedCrossCritiqueTuple`)**: Rhetorical tone (`HOSTILE` / `FRIENDLY`) without a deterministic counterexample witness never flips a model's position.
5. **Law 5 — Weighted Partial MaxSAT & Non-Dilutable Conflict Register Contraction (`NEXT` $= \Phi(\text{CURRENT}, \text{MISSED}, \text{BRAINSTORM})$)**:
   `WeightedPartialMaxSatSynthesizer` (`tools/current_missed_next_calculus.py`) enforces every conflict in `NonDilutableConflictRegister` (`arXiv:2610.12360`) and every verified minority counterexample as a **Hard Clause**, contracting residual blind-spot mass $U(\mathcal{C}^{(t)}) \to 0\text{ bps}$ and emitting an `Ed25519`-signed RFC 8785 JCS receipt.

---

## 🔄 II. The 5-Stage Execution Protocol

Whenever `/decide` is invoked, execute these 5 stages in order:

### Stage 1: Construct Category 1 — `CURRENT` ($\mathcal{C} = \mathcal{C}_{\text{local}} \oplus \mathcal{C}_{\text{humanity}}$)
1. **$\mathcal{C}_{\text{local}}$ ($O(1)$ Constant-Time Codebase Snapshot)**: Query `ConstantTimeCodebaseSnapshot` in $< 1\text{ ms}$.
2. **$\mathcal{C}_{\text{humanity}}$ (8-Axis Orthogonal Keyword Tag Web & Science Search)**: Expand the query across all 8 orthogonal tag axes and search live 2025–2026 arXiv, GitHub, and Chinese open-source labs.

### Stage 2: Construct Category 2 — `MISSED` ($\mathcal{M} = \partial(\mathcal{C})$, Analyzing `CURRENT` Only!)
Apply `MissedDifferentialOperator.analyze_current_only` strictly to `CURRENT` to extract `local_absorption_gaps`, `humanity_wire_finality_flaws`, and `galois_frontier_voids`.

### Stage 3: Construct Category 2.5 — `BRAINSTORM` ($\mathcal{B} = \Psi(q_{\text{expanded}}, \mathcal{C}, \mathcal{M})$)
Evaluate the expanded query across the 4 heterogeneous China + USA frontier agent profiles (`DeepSeek-R1`, `Qwen-Max`, `Gemini-Pro`, `Perplexity-Sonar`):
1. Identify **Convergent Validated Hypotheses** (backed by primary citations and reproducible tests) using **GLS Diversity-Weighted + FCA Galois Meet Synthesis** (Locked Pair Decision `A2`).
2. Identify **Divergent Trade-Off Forks** and format them into the `DeveloperPairDecisionQuestion` schema. Per Locked Pair Decision `A1` & `A3`:
   - Default synthesis combines `Qwen-Max` autonomous SQLite WAL multi-hop replanning with `Perplexity-Sonar` 2-hop TRACE citation verification (`arXiv:2506.11763`) and pair-decision schema gating.
   - **Auto-Trigger Interactive `ask_question` Modal (`A3`)**: Whenever China (`Qwen`/`DeepSeek`) and USA (`Gemini`/`Perplexity`) models propose divergent architectural branches on a Galois lattice trade-off in `/decide`, automatically invoke the interactive `ask_question` modal with `DeveloperPairDecisionQuestion.to_ask_question_payload()` so the developer pair can choose the exact synthesis branch before locking Category 3 (`NEXT`).

### Stage 4: Construct Category 3 — `NEXT` ($\mathcal{N} = \Phi(\mathcal{C}, \mathcal{M}, \mathcal{B})$)
Synthesize the higher-order solution category by combining `CURRENT`, `MISSED`, and the resolved `BRAINSTORM` hypotheses, auditing our own proposed `NEXT` code layer until $U(\mathcal{C}^{(T)}) = 0\text{ bps}$.

### Stage 5: Verification & Epistemic Calibration Gate
Run `python3 compliance/check_zone_boundary.py`, `python3 compliance/ast_purity.py .`, `python3 compliance/no_mock_enforcer.py`, and `pytest tests/test_decide_categorical_epistemic_engine.py -v`.
