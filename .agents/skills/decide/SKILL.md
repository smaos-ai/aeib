---
name: decide
description: Epistemic Adversarial Research & Categorical Decision Engine (v3.0). Formalizes the 3-Order Epistemic Triad — Category 1 CURRENT (O(1) Local Codebase Snapshot + Verified Humanity/Web SOTA via 8-Axis Orthogonal Keyword Tag Expansion), Category 2 MISSED (FCA Galois Differential Operator d(CURRENT) analyzing CURRENT only), and Category 3 NEXT (Higher-Order Synthesis Functor Phi(CURRENT, MISSED) with Submodular Coverage & Iterative Epistemic Contraction to 0 bps). Trigger on /decide, $decide, 'what we missed', or 'adversarial research'.
---

# `/decide` v3.0 — Categorical 3-Order Epistemic Engine (`CURRENT` $\to$ `MISSED` $\to$ `NEXT`)

The `/decide` v3.0 skill transforms the agent from single-shot autocomplete into a **Mathematically Grounded, Closed-Loop Epistemic Synthesis Engine** (`src/decide_categorical_epistemic_engine.py` & `tools/decide_v2_constant_time_snapshot.py`).

---

## 🏛️ I. Philosophical & Mathematical Foundation

Why do standard LLM prompts and naive "deep research" wrappers hit a quality ceiling?
1. **Single-Vector Mode Collapse**: A raw prompt projects onto a single dominant statistical cluster in the model's pre-training distribution, covering only $k_{\text{naive}} \approx 2$ conceptual attributes ($\binom{2}{2} + 2 = 3$ pairwise interaction edges).
2. **Premature Jumping to `NEXT`**: Standard agents try to brainstorm "what to build next" without first computing an exact constant-time snapshot of `CURRENT` ($\mathcal{C}_{\text{local}} \oplus \mathcal{C}_{\text{humanity}}$) and applying a strict boundary differential operator `MISSED` ($\mathcal{M} = \partial(\mathcal{C})$) onto `CURRENT` alone.

### The Three Mathematical Theorems of `/decide` v3.0
1. **Theorem 1 — Submodular Information Gain via 8-Axis Orthogonal Keyword Tag Expansion (`arXiv:2502.08557`, Nemhauser-Wolsey-Fisher)**:
   Expanding any research query across $D = 8$ mutually orthogonal keyword tag axes $K = \{k_1, \dots, k_8\}$ maximizes the monotone submodular mutual information function $F(K) = I(\Omega; X_K)$. Across $N = 28$ combined moat and invariant nodes, this resolves $\binom{28}{2} + 28 = 406$ pairwise cross-domain interaction edges versus $3$ edges in a single-shot prompt — a **$135\times$ ($\ge 100\times$) Pairwise Compositional Coverage Multiplier**.
2. **Theorem 2 — Formal Concept Analysis (FCA) Galois Boundary Operator (`MISSED` $= \partial(\text{CURRENT})$)**:
   `MISSED` operates **strictly on `CURRENT` only** ($\mathcal{C} = \mathcal{C}_{\text{local}} \oplus \mathcal{C}_{\text{humanity}}$). Over the incidence matrix $\mathcal{I} \subseteq \mathcal{O} \times \mathcal{A}$, $\partial(\mathcal{C})$ extracts three exact structural sets:
   - **Local Absorption Gaps**: $\text{Attr}(\mathcal{C}_{\text{humanity}}) \setminus \text{Attr}(\mathcal{C}_{\text{local}})$ (what humanity has solved in fresh 2025–2026 science that our codebase has not yet absorbed).
   - **Humanity Wire-Finality Flaws**: $\text{Attr}(\mathcal{C}_{\text{local}}) \setminus \text{Attr}(\mathcal{C}_{\text{humanity}})$ (where external papers/repos fail AEIB's cryptographic wire-finality, zero-mock, or Byzantine concurrency gates).
   - **Galois Frontier Voids**: $\mathcal{A}_{\text{universal}} \setminus (\text{Attr}(\mathcal{C}_{\text{local}}) \cup \text{Attr}(\mathcal{C}_{\text{humanity}}))$ (pairwise concept intersections that neither local code nor external literature has ever composed).
3. **Theorem 3 — Iterative Epistemic Contraction Functor (`NEXT` $= \Phi(\text{CURRENT}, \text{MISSED})$)**:
   `NEXT` embeds both `CURRENT` and `MISSED`. Across closed-loop iterations $t = 0, 1, \dots, T$, synthesizing concrete code countermeasures for $\mathcal{M}^{(t)}$ contracts the uncovered blind-spot mass $U(\mathcal{C}^{(t)}) \le (1 - \gamma)^t U(\mathcal{C}^{(0)})$ down to **$0\text{ bps}$**, anchored by an `Ed25519` signature over RFC 8785 JCS.

---

## 🔄 II. The 4-Stage Execution Protocol

Whenever `/decide` is invoked, execute these 4 stages in order:

### Stage 1: Construct Category 1 — `CURRENT` ($\mathcal{C} = \mathcal{C}_{\text{local}} \oplus \mathcal{C}_{\text{humanity}}$)
1. **$\mathcal{C}_{\text{local}}$ ($O(1)$ Constant-Time Codebase Snapshot)**:
   Run `python3 tools/decide_v2_constant_time_snapshot.py` and `python3 src/decide_categorical_epistemic_engine.py` to index all local modules, classes, `HALT_*` codes, and tests in $< 1\text{ ms}$.
2. **$\mathcal{C}_{\text{humanity}}$ (8-Axis Orthogonal Keyword Tag Web & Science Search)**:
   Deconstruct the problem into the **8 Orthogonal Keyword Tag Axes** (`AXIS_1_MATH_INFORMATION_THEORY`, `AXIS_2_SYSTEMS_KERNEL_SUBSTRATE`, `AXIS_3_CRYPTOGRAPHIC_WIRE_FINALITY`, `AXIS_4_DISTRIBUTED_DB_CONSISTENCY`, `AXIS_5_ADVERSARIAL_BYZANTINE_SECURITY`, `AXIS_6_REGULATORY_ACTUARIAL_GOVERNANCE`, `AXIS_7_CHINA_HIGH_THROUGHPUT_RUNTIMES`, `AXIS_8_WESTERN_OPEN_SOURCE_SYSTEMS`) and query live 2025–2026 arXiv, GitHub, and Chinese open-source labs to establish what humanity has already achieved today.

### Stage 2: Construct Category 2 — `MISSED` ($\mathcal{M} = \partial(\mathcal{C})$, Analyzing `CURRENT` Only!)
Apply the differential operator strictly to `CURRENT` (do not speculate about `NEXT` yet):
1. **5-Why Root-Cause Chain**: Trace `Why 1` (Symptom) $\to$ `Why 2` (Process Gap) $\to$ `Why 3` (Substrate/Indexing Gap) $\to$ `Why 4` (Single-Pass Limit) $\to$ `Why 5` (Root Mathematical/Architectural Fix).
2. **Pass 1 Critique (`What Humanity & External Papers Missed`)**: Audit $\mathcal{C}_{\text{humanity}}$ against wire-finality (`HTTP 504` drops), Bell-LaPadula taint, and TRACE citation-to-claim verification (`arXiv:2506.11763`).
3. **Pass 2 Critique (`What Our Local Codebase Missed` & `Galois Frontier Voids`)**: Identify the exact attributes in $\text{Attr}(\mathcal{C}_{\text{humanity}}) \setminus \text{Attr}(\mathcal{C}_{\text{local}})$ and the unpopulated Galois lattice meet points.

### Stage 3: Construct Category 3 — `NEXT` ($\mathcal{N} = \Phi(\mathcal{C}, \mathcal{M})$)
Synthesize the higher-order solution category by combining our existing codebase moats ($\mathcal{C}_{\text{local}}$), humanity's verified breakthroughs ($\mathcal{C}_{\text{humanity}}$), and the exact blind-spot countermeasures from $\mathcal{M}$:
1. Audit our own proposed `NEXT` code layer (Iteration 2 Self-Audit) for edge cases, float contamination, or bypass risks.
2. Implement the zero-mock Python/Rust modules and pytest suites so residual blind-spot mass contracts to $U(\mathcal{C}^{(T)}) = 0\text{ bps}$.

### Stage 4: Verification & Epistemic Calibration Gate
1. Run `python3 compliance/check_zone_boundary.py`, `python3 compliance/ast_purity.py .`, and `python3 compliance/no_mock_enforcer.py`.
2. Run `pytest tests/test_decide_categorical_epistemic_engine.py tests/test_decide_v2_constant_time_snapshot.py tools/epistemic_5why_loop.py -v`.
3. Enforce strict epistemic vocabulary: use permitted words (`observed`, `tested`, `evaluated`, `configured`, `under the stated model`, `prototype`, `scaffold`, `pre-production`) and zero banned words.
