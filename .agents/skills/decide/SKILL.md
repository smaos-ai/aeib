---
name: decide
description: Epistemic Adversarial Research, Cross-Hemisphere Council, & 5-Stage Recursive Parallel Evidence-Producing Decision Engine (v5.0). Formalizes CURRENT -> MISSED(CURRENT) -> BRAINSTORM -> NEXT with RuleTrek AST Rule Dependency Graphs (arXiv:2610.19698), Dossier Persistent Research Ledger, FlowSearch Knowledge DAG (arXiv:2510.08521), AgentDisCo Critic-Generator (arXiv:2605.11732), OpenSaC Search-as-Code (arXiv:2610.25779), WebSwarm Recursive Delegation (arXiv:2607.08662), Argus Jigsaw Assembly (arXiv:2605.16217), the Decide | Ask | Defer 3-Action Policy (arXiv:2610.04542), Asymmetric Evidence Dominance (arXiv:2605.00914), and 10 Action Modes (including --falsify, --deep, --security, --release, --compliance). Trigger on /decide, $decide, 'what we missed', or 'adversarial research'.
---

# `/decide` v5.0 — 5-Stage Recursive Parallel Evidence-Producing Decision Engine & Cross-Hemisphere Council

The `/decide` v5.0 skill (`src/decide_v5_recursive_evidence_engine.py`, `tools/ruletrek_cross_model_decide_engine.py`, `src/decide_evaluation_rate_and_decay_solver.py`, `src/decide_autonomous_query_research_engine.py`, `tools/cross_hemisphere_council_decide.py`, & `src/decide_categorical_epistemic_engine.py`) upgrades `/decide` from a research synthesizer into a **5-Stage Recursive Parallel Evidence-Producing Decision Engine**.

Every `/decide` execution returns four mandatory artifacts inside a signed JSON/Markdown envelope:
1. **A decision-ready recommendation** (`VALIDATED_RECOMMENDATION` | `CONDITIONAL_RECOMMENDATION` | `CONDITIONAL_NO` | `HOLD` | `ASK`)
2. **Validated typed evidence with provenance (`T0`–`T4`)**
3. **Explicit unresolved questions & contradictions (`DossierResearchLedger`)**
4. **Reproducible counterexamples & executable falsification vectors (`--falsify`)**

---

## 🏛️ I. Mathematical & Scientific Foundations (Laws 1–7)

1. **Law 1 — Submodular Information Gain via 8-Axis Orthogonal Keyword Tag Expansion & CELF IG-Search (`arXiv:2502.08557`, `arXiv:2604.15148`)**:
   Expands any query across $D = 8$ orthogonal keyword axes and prunes redundant search branches via Lazy Greedy CELF (`src/decide_evaluation_rate_and_decay_solver.py`), achieving a **$35.78\times$ Evaluation Rate multiplier** and **$66.06\%$ token reduction**.
2. **Law 2 — Formal Concept Analysis (FCA) Galois Boundary Operator (`MISSED` $= \partial(\text{CURRENT})$)**:
   `MISSED` operates strictly on `CURRENT` ($\mathcal{C}_{\text{local}} \cup \mathcal{C}_{\text{humanity\_today}}$) to extract `local_absorption_gaps`, `humanity_wire_finality_flaws`, and `galois_frontier_voids`.
3. **Law 3 — RuleTrek AST Rule Dependency Graph Extraction (`arXiv:2610.19698`, Oct 2026)**:
   Before multi-model brainstorming, `RuleTrekDependencyGraphExtractor` (`tools/ruletrek_cross_model_decide_engine.py`) extracts explicit directed rule dependencies (`R1 -> R2 -> R3`) across multi-file repositories so parallel models do not violate cross-file statutory or RLS invariants.
4. **Law 4 — Recursive Parallel Ledger & Knowledge Flow (`Dossier`, `FlowSearch` `arXiv:2510.08521`, `AgentDisCo` `arXiv:2605.11732`, `OpenSaC` `arXiv:2610.25779`, `WebSwarm` `arXiv:2607.08662`, `Argus` `arXiv:2605.16217`)**:
   Replaces linear ReAct chains with `DossierResearchLedger` (tracking typed claims, contradictions, and gaps), triggering targeted branch searches on contradictions and enforcing the `vscode-team-kit` quality gate ($\ge 2$ independent sources for `HIGH` confidence).
5. **Law 5 — Cross-Hemisphere `Decide | Ask | Defer` Policy & 3-Tier `Ask` Router (`arXiv:2610.04542`)**:
   Routes every `ModelAskQuery` through Tier 1 (`PARENT_O1_SNAPSHOT`), Tier 2 (`WEB_SEARCH_PROBE`), and Tier 3 (`PENDING_DEVELOPER` interactive `ask_question` modal).
6. **Law 6 — Asymmetric Evidence Dominance & Typed Cross-Critique (`arXiv:2605.00914`, `arXiv:2609.08016`)**:
   A single minority model backed by a reproduced counterexample (`T3`/`T4`) or verified primary source (`T2`) overrides unverified majority consensus, defeating the 32.3% Oracle Gap and 85.5% sycophantic conformity.
7. **Law 7 — Four-Decay Mathematical Compensation (`SAKE` `arXiv:2602.09517`, `DPI` `arXiv:2604.02460`)**:
   Maintains `9821 bps` (`98.21%`) deep-hop evidence utilization via `SAKE` dual-anchoring and prevents Shannon Data Processing Inequality handoff loss by requiring content-addressed raw evidence spans (`caid`) at every subagent handoff.

---

## ⚙️ II. The 10 `/decide` Action Modes

| Command Mode | Purpose | Primary Output |
| :--- | :--- | :--- |
| `/decide` | General decision | Recommendation + typed evidence (`T0`–`T4`) + executable plan |
| `/decide --deep` | Full 7-lane recursive parallel sweep | Multi-lane primary sources (`Dossier` ledger), disproof vectors, synthesis |
| `/decide --security` | Threat-model & CVE decision | Attack trees, structural CVE fixtures, negative tests |
| `/decide --release` | Release readiness gate | Phase 0 / `rc.5-preprod` blocker audit, clean-room archive status |
| `/decide --research` | Global & China SOTA landscape | Verified papers (`arXiv`), standards (`RFC`/`ISO`/`EN 18286`), gap matrix |
| `/decide --build` | Implementation architecture | Module specs, interface contracts, verification loop |
| `/decide --falsify` | Attack a recommendation | Strongest counterargument + executable `FalsificationVector` |
| `/decide --compliance` | Regulatory crosswalk | `EN 18286:2026`, `DORA Art. 17`, `ECMA-424` CycloneDX CBOM |
| `/decide --benchmark` | Evaluation & DST design | Metrics, seeded fault schedules (`Limbo Prop 1`, `PARL`), baselines |
| `/decide --repo` | Repository-grounded audit | Clickable `file://` symbol/line evidence and test coverage |

---

## 🔄 III. The 5-Stage Execution Protocol

1. **Stage 1 — Decompose & Extract RuleTrek Graph**: Classify query (`architecture`, `security`, `compliance`, `performance`, `release`), apply `RuleTrekDependencyGraphExtractor`, and check `ConstantTimeCodebaseSnapshot` ($\mathcal{C}_{\text{local}}$).
2. **Stage 2 — Parallel 7-Lane Evidence Sweep**: Execute parallel lanes across Academic (`arXiv`), Standards (`IETF`/`NIST`/`MCP`), Security (`CVE`/`NVD`), Open Source (`GitHub`), Industry, Local Repo, and Adversarial Red-Team into `DossierResearchLedger`.
3. **Stage 3 — Typed Claim Extraction (`T0`–`T4`)**: Rank claims strictly by `T4_FORMAL_OR_EXECUTABLE_ORACLE` > `T3_REPRODUCED_COUNTEREXAMPLE` > `T2_VALIDATED_PRIMARY_SOURCE` > `T1_CITATION` > `T0_MODEL_ASSERTION`.
4. **Stage 4 — Adversarial Disproof (`--falsify`)**: Attempt to falsify the primary recommendation and convert the strongest counterargument into an executable `FalsificationVector` pytest check.
5. **Stage 5 — Decision Synthesis & Verification Gate**: Adjudicate via `DecideV5EvidenceEngine` (`src/decide_v5_recursive_evidence_engine.py`), sign the canonical JCS envelope with Ed25519, and run the mandatory `AGENTS.md` verification harness.
