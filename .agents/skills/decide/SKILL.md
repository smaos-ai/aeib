---
name: decide
description: Epistemic Adversarial Research, Cross-Hemisphere Council, & 5-Stage Recursive Parallel Evidence-Producing Decision Engine (v5.1). Formalizes CURRENT -> MISSED(CURRENT) -> BRAINSTORM -> NEXT with Multi-Flag Join-Semilattice Composition, T4+ Mutation-Killed Oracles (MLReproMutate), CAVEAT Correlated-Error Discounting, POIROT Citation Echo Deduplication, Epistemic Half-Life Decay, RuleTrek AST Rule Dependency Graphs (arXiv:2610.19698), Dossier Persistent Research Ledger, FlowSearch Knowledge DAG (arXiv:2510.08521), AgentDisCo Critic-Generator (arXiv:2605.11732), OpenSaC Search-as-Code (arXiv:2610.25779), WebSwarm Recursive Delegation (arXiv:2607.08662), Argus Jigsaw Assembly (arXiv:2605.16217), the Decide | Ask | Defer 3-Action Policy (arXiv:2610.04542), Asymmetric Evidence Dominance (arXiv:2605.00914), and 10 Action Modes (including --falsify, --deep, --security, --release, --compliance) plus the --full / --all standing preset (§V) that bundles deep+research+benchmark+falsify+security+build+release into one budgeted run. Trigger on /decide, $decide, 'what we missed', 'did we achieve SOTA', or 'adversarial research'.
---

# `/decide` v5.1 — 5-Stage Recursive Parallel Evidence-Producing Decision Engine & Meta-Hardened Council

The `/decide` v5.1 skill (`src/decide_v51_meta_hardening_engine.py`, `src/decide_v5_recursive_evidence_engine.py`, `tools/ruletrek_cross_model_decide_engine.py`, `src/decide_evaluation_rate_and_decay_solver.py`, `src/decide_autonomous_query_research_engine.py`, `tools/cross_hemisphere_council_decide.py`, & `src/decide_categorical_epistemic_engine.py`) upgrades `/decide` into a **Meta-Hardened 5-Stage Recursive Parallel Evidence-Producing Decision Engine**.

Every `/decide` execution returns four mandatory artifacts inside a signed JSON/Markdown envelope:
1. **A decision-ready recommendation** (`VALIDATED_RECOMMENDATION` | `CONDITIONAL_RECOMMENDATION` | `CONDITIONAL_NO` | `HOLD` | `ASK`)
2. **Validated typed evidence with provenance (`T0`–`T4`)**
3. **Explicit unresolved questions & contradictions (`DossierResearchLedger`)**
4. **Reproducible counterexamples & executable falsification vectors (`--falsify`)**

---

## 🏛️ I. Mathematical & Scientific Foundations (Laws 1–7)

1. **Law 1 — Submodular Information Gain via 8-Axis Orthogonal Keyword Tag Expansion & CELF IG-Search (`arXiv:2502.08557`, `arXiv:2604.15148`)**:
   Expands any query across $D = 8$ orthogonal keyword axes and prunes redundant search branches via Lazy Greedy CELF (`src/decide_evaluation_rate_and_decay_solver.py`), pairing top-$k$ `SQLite FTS5 BM25` retrieval (`src/hypersu_fts.py`, `0.3656ms` `p95` at $100\text{k}$ facts) with reversible `ContextCartArchivalForgettingEngine` observation compression (`arXiv:2610.10590v1`).
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
   Prevents Shannon Data Processing Inequality handoff loss across multi-hop reasoning by requiring content-addressed raw evidence spans (`caid` + character offsets verified by `AtomicClaimRouter`) at every subagent handoff.
8. **Law 8 — Multi-Flag Join-Semilattice Composition (`src/decide_v51_meta_hardening_engine.py`)**:
   When multiple flags are invoked simultaneously (e.g., `/decide --research --deep --compliance --security --falsify --benchmark`), `MultiFlagLatticeComposer` composes the join-semilattice union of all mode obligations ($\bigvee_{m \in \text{Flags}} \mathcal{O}(m)$) so zero constraints are dropped.
9. **Law 9 — `T4+` Mutation-Killed Oracle Verification (`MLReproMutate` & `The Verification Horizon`, 2026)**:
   Prevents vacuous `T4` tests by injecting synthetic boundary and cryptographic mutants into the invariant under test (`MutationKilledOracleVerifier`), requiring a `10000 bps` (`100%`) mutant kill rate (`qualifies_as_t4_plus = True`).
10. **Law 10 — `CAVEAT` Pre-Training Error-Correlation Discounting, `POIROT` Origin Deduplication, & Epistemic Half-Life (`CaveatAndPoirotMetaAuditor`)**:
    Collapses secondary citation echo-chambers sharing a `root_origin_caid`, discounts correlated LLM agreement via $N_{\text{eff}} = N / (1 + (N - 1)\rho_{\text{corr}})$, requires a non-LLM orthogonal witness whenever $\rho_{\text{corr}} \ge 0.30$, and halts on expired supply-chain/CVE half-life ($\tau_{1/2}$).
11. **Law 11 — 6-State Model Integrity Layer & Signed Decision Metadata (`src/model_integrity_layer_and_bio_aeib_gate.py`)**:
    Treats every LLM output as an untrusted probabilistic proposal carrying a signed `ModelDecisionEnvelopeV1` (`prompt_digest`, `response_digest`, `retrieval_digest`, atomic `evidence` spans, `uncertainty`, `taint`, and `policy`), evaluated across 5 runtime health layers (`model_liveness`, `output_validity`, `evidence_integrity`, `behavioral_drift_and_circuit_breaker`, `calibration_auditor`) into 6 explicit states (`VERIFIED`, `PROVISIONAL`, `DEGRADED`, `UNTRUSTED`, `QUARANTINED`, `UNKNOWN`).
12. **Law 12 — Bio-Agentic Execution Boundary: Silicon to Carbon (`BioAEIBExecutionGate`)**:
    Extends `EO1` to non-compensable physical/wet-lab actions via `GenomicScittReceiptEngine` (`bio_caid` FASTA digest + AlphaFold rigid-domain boundary check + pathogen homology screen), `WetLabJidokaStateMachine` (microfluidic quench valve latching `EFFECT_INDETERMINATE` on thermal/pH/mass-spec drift), `BioStochasticAcidReagentEscrow` (24h TCC physical reagent quota lock), and `BioAdmissibilityAndTaintGate` (blocking `TIER_2` preprint-tainted contexts from physical synthesis without PI RFC 9470 step-up).
13. **Law 13 — DIR Anti-Scaffold Bisector, Fail-Closed Grounding, & Hardened `x402` Escrow (`src/dir_antiscaffold_and_x402_escrow_engine.py`)**:
    Enforces multi-statement AST stub detection (`DirAntiScaffoldAndScopeBisector.inspect_source_for_scaffolds`), behavioral differential probing on corrupted inputs (`probe_callable_for_static_scaffold`), ecosystem primitive reuse vs. signed `ParallelOutOfScopeTrackSpec` routing, fail-closed integer-bps grounding receipts (`FailClosedGroundedHealthMonitor`), and `PreDispatchIntentInterlock`-backed `x402` payment escrow (`HardenedX402EscrowInterceptor`) with SIWx URL binding, per-intent cap, cumulative epoch wallet-drain (`smurfing`) cap, and `challenge_nonce` replay defense.
14. **Law 14 — Unified Anti-Scaffold Falsifier & Out-of-Scope Delivery (`src/anti_scaffold_falsifier.py`)**:
    Enforces a 4-tier scope routing protocol (`PreFlightScopeDecoupler`) that traps when an LLM substitutes complex or out-of-scope subsystems with mocks or hardcoded stubs, generating signed RFC 8785 `ParallelOutOfScopeTrackSpec` manifests, while running AST wheel-reinvention detection (`PriorArtLinter`), multi-seed/multi-scale dynamic execution variance verification (`LiveExperimentOracle`), and differential mutation falsifiers (`DifferentialMutationFalsifier`).
15. **Law 15 — Track 1 Core Loop Lock & Calibrated Guards (`src/aeib_track1_and_calibrated_guards.py`)**:
    Locks the core execution loop under `canonical_json_v1` (strict float and non-string key rejection), `BootVerifiedEo1EscrowGate` (AT57b Bell-LaPadula pure taint boundary with RFC 9470 step-up override, AT58 pre-socket escrow reservation and indeterminate hold blocking timeout-smurfing, G3 boot replay recomputing action and entry CAIDs with Ed25519 signature checks on every row, G4 cross-process `fcntl.flock`, and G6 destructive zero-dollar mutation cap), `GoldenDatasetCalibratedMonitor` (empirical Precision, Recall, F1, FPR, FNR, MCC calibration escalating to human if $F1 < 0.90$ or $FNR > 0.0$), `ZeroTrustSupplyChainGatekeeper` (72-hour release cooldown and pre-session frozen plugin registry checks), and `CognitiveFlightRecorder` (hash-chained OpenTelemetry decision spans bound to multimodal evidence hyperedge digests).
16. **Law 16 — Tri-Track Parallel Prize Competition, Defect Verification Gate, & Hardened Agentic Commerce Infrastructure (`src/gemma_developer_agent_engine.py`, `src/huntr_agent_vulnerability_scanner.py`, `src/coinbase_x402_agent_gateway.py`)**:
    Operationalizes AEIB execution integrity across three high-impact monetization tracks: Track Alpha (Google Gemma 4 Developer Agent Kaggle Competition, $110k prize pool, Nov 12, 2026 deadline: submodular BM25 degree-penalized retrieval, Toyota Jidoka ContractTree inspection, bounded repair $B \le 3$ with out-of-scope bisection, and Station 1 Pre-Dispatch Intent Latch); Track Beta (Huntr AI/ML Bug Bounty & Adversarial Red-Teaming, up to $50k per critical flaw: 6-phase defect verification gate with null-hypothesis fresh disproving verifiers and Ed25519 offline receipts); and Track Gamma (Coinbase CDP & x402 Hardened Agent Gateway, $10k–$50k grant track: pre-socket escrow reservation, SIWx URL/path/method binding, HTTP 504 indeterminate hold preventing duplicate payments, and multi-agent velocity quotas preventing smurfing). Requires $T4+$ mutation-adequacy kill ratios ($\ge 90\%–100\%$) across all tracks.
17. **Law 17 — Provenance-Bounded Action Gate (PBAG) & Pre-Fetch Hypothesis Latching for Scientific & Genomic Workflows (`src/bio_variant_contract.py`, `src/bio_evidence_gate.py`)**:
    Enforces deterministic variant coordinate contracts (`GRCh37` vs `GRCh38` assembly chromosome lengths across chr1..chr22, chrX, chrY, chrM) with Tan et al. parsimonious left-alignment trimming; 9-vector anti-scaffold bio-mutation oracle (`probe_variant_verifier`) that halts if any mutated genomic coordinate passes; 4-tier biological scope decoupling (`BioScopeGate`) that immediately fails closed with `CapabilityUnavailableError` on T3 wet-lab actuators (`crispr.transfect`, `opentrons.pipette`, `dna.synthesize_oligo`, `clinical.issue_diagnosis`); 7 typed biological source contracts (dbSNP, AlphaGenome Atlas, ENCODE cCREs, JASPAR DeepTF, UCSC PhastCons, AlphaFold DB, Reactome) requiring mandatory sub-score unpacking; `BioEvidenceScorer` emitting strictly `SUPPORTS | REFUTES | UNKNOWN` with integer basis points (0..10000 bps) and banned clinical overclaim filter; `BioContextCart` SHA-256 lossless raw-byte archiving with $\le 500$ token compact cards; and `EO1BioEvidenceLatch` with POSIX `fcntl.flock` + `F_FULLFSYNC` enforcing pre-fetch hypothesis timestamping to prevent retroactive hypothesis fabrication (HARKing), sealed into clean-room reproducible Ed25519-signed bundles ($T4+$ mutation-adequacy kill ratio $\ge 90\%$).

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
| `/decide --full` (alias `--all`) | Standing preset = `--deep --research --benchmark --falsify --security --repo --build --release`, see §V | One notebook artifact: what changed, measured numbers, FIXED / OPEN / NEEDS-USER-DECISION |

---

## 🔄 III. The 5-Stage Execution Protocol

1. **Stage 1 — Decompose & Extract RuleTrek Graph**: Classify query (`architecture`, `security`, `compliance`, `performance`, `release`), apply `RuleTrekDependencyGraphExtractor`, and check `ConstantTimeCodebaseSnapshot` ($\mathcal{C}_{\text{local}}$).
2. **Stage 2 — Parallel 7-Lane Evidence Sweep**: Execute parallel lanes across Academic (`arXiv`), Standards (`IETF`/`NIST`/`MCP`), Security (`CVE`/`NVD`), Open Source (`GitHub`), Industry, Local Repo, and Adversarial Red-Team into `DossierResearchLedger`.
3. **Stage 3 — Typed Claim Extraction (`T0`–`T4`)**: Rank claims strictly by `T4_FORMAL_OR_EXECUTABLE_ORACLE` > `T3_REPRODUCED_COUNTEREXAMPLE` > `T2_VALIDATED_PRIMARY_SOURCE` > `T1_CITATION` > `T0_MODEL_ASSERTION`.
4. **Stage 4 — Adversarial Disproof (`--falsify`)**: Attempt to falsify the primary recommendation and convert the strongest counterargument into an executable `FalsificationVector` pytest check.
5. **Stage 5 — Decision Synthesis & Verification Gate**: Adjudicate via `DecideV5EvidenceEngine` (`src/decide_v5_recursive_evidence_engine.py`), sign the canonical JCS envelope with Ed25519, and run the mandatory `AGENTS.md` verification harness.

---

## 🧪 IV. Pre-Market / Release Reality Audit (`--release`, or any "before market" request)
Run these lanes in parallel. Audit lanes are read-only and write only to `scratch/`; fix lanes own disjoint files.
1. **Module reality:** full pytest run; AST-classify every `src/` module as REAL / SCAFFOLD_LABELED / MISLABELED / STUB / ORPHAN / DEAD, with file:line.
2. **Real-class benchmark:** drive the *real* class (never a simulation) against a real local target with seeded faults; include a negative control that must fail; report Wilson 95% CIs and the costs (e.g. INDETERMINATE count, latency).
3. **Claims & evidence:** scan external materials for numbers, customers and compliance claims; recompute EVIDENCE_MANIFEST hashes; scan for tracked secrets.
4. **Market & frontier:** competitors (incl. China), verify cited papers by arXiv ID, buyer blockers; mark search-summary-only items UNVERIFIED.
5. **Red team:** forgery, replay, tamper/rollback, canonicalization differentials, oversize/DoS against verifiers, ledgers, payment gates and IPC.
Then: one fix lane per broken component (disjoint ownership, regression test fails on old code, mutation gate on all module tests), re-run the full suite and red-team scripts, and produce a go/no-go artifact that separates FIXED / OPEN / NEEDS-USER-DECISION. Launch at most 2–3 writer subagents at once (larger batches hit quota limits).

**Orchestration protocol (AGENTS.md §7):**
1. Decompose → for each lane: owned files + reverse-import test closure; overlapping closures ⇒ serialize or `Workspace: share`.
2. Brief each lane as a typed slice (grep-verified symbols, evidence path, gates, ≤B=3 repair rounds).
3. ≤3 writers at once; read-only research lanes may run alongside.
4. On each receipt: re-run that lane's tests + mutation gate yourself if the number will be reported.
5. Integration: full suite → §4 harness → red-team scripts → update the go/no-go artifact (FIXED / OPEN / NEEDS-USER-DECISION).

---

## 🧭 V. `--full` Standing Preset (the user's recurring request, so it never has to be retyped)

`/decide --full <one-line question>` is the same request as the long multi-paragraph prompt: "research web/science/China/industry leaders, what did we miss, did we reach SOTA, falsify, benchmark, security threats today, architecture blind spots, implement + harden + clean code + open code review, recheck the whole project, final picture". The preset carries those obligations **once, in a fixed order**. Long repeated prompts do not add obligations. Under the cited sources they make things worse: compliance drops as the instruction count rises (arXiv:2507.11538, best model 68% at 500 instructions; arXiv:2509.21051), and reasoning degrades with input length (arXiv:2402.14848). Prompt repetition helps only *non-reasoning* models (arXiv:2512.14982). Optional knob: `--budget=S|M|L` (default M).

| Step | Obligation | S | M | L |
| :--- | :--- | :--- | :--- | :--- |
| 0. Scope gate | Restate the request as ≤7 numbered, testable sub-goals. Name every requested skill/tool that does **not** apply (e.g. genomics skills on a software repo) and skip it with one line of reason. Ask only if a sub-goal is ambiguous *and* costly. | ✔ | ✔ | ✔ |
| 1. CURRENT | `git status` / HEAD. Check for a concurrent session (recent mtimes on files you did not touch). Reuse prior artifacts and verified citations instead of re-researching (epistemic half-life). Report the last measured suite numbers with their date. | ✔ | ✔ | ✔ |
| 2. MISSED (research) | Run read-only lanes in parallel (max 3): **academic** (`literature-search-arxiv`, `literature-search-openalex`; bioRxiv / Europe PMC only for life-science topics), **industry + China** (official model cards and repos), **security threats** (primary advisories / CVEs). Each lane returns a table marked CONFIRMED / UNVERIFIED-SUMMARY-ONLY / NOT FOUND / MISMATCH. Science skills: run each skill script with the skill directory as cwd (`cd <skill_dir> && uv run scripts/...`); in zsh use a shell function, not a string variable, for the command; for InterPro aggregates (`group_by`, `interpro_status`) use `fetch ... --limit 1` (`count` returns 0 for them). | 1 lane | 2 | 3 |
| 3. Falsify "SOTA / next level" | Score against explicit criteria, not adjectives: independent reproduction · public external benchmark · hosted CI on a clean machine · red-team scripts held · mutation ≥90% on all module tests · no fabricated fallbacks · zero-egress rule. Any unmet criterion ⇒ the answer is "not demonstrated", with the list. | ✔ | ✔ | ✔ |
| 4. Build (only evidence-backed items) | Fix only items that have a failing test, script or file:line. Run `tools/parallel_lane_partitioner.py` before dispatching writers (max 3). Never edit files another live session owns; report them as NEEDS-USER-DECISION. Every fix ships with a regression test that fails on the old code. | top 1–2 | top 3–5 | all |
| 5. Harden | Red-team every touched boundary (forgery, replay, tamper, oversize, canonicalization divergence). Run the mutation gate over **all** tests of each modified module. | touched only | ✔ | ✔ |
| 6. Verify | Run the AGENTS.md §4 harness. Run the full `pytest tests/` only if `src/` changed or the budget is L (it takes about 8 min of CPU and burns credits). | targeted tests | §4 harness | §4 + full suite |
| 7. Final picture | Write **one** artifact `DECIDE_FULL_<topic>.md`: verdict, commits, every number with its command, citations table, FIXED / OPEN / NEEDS-USER-DECISION, and a cost note (lanes, subagents, full-suite runs). Do not re-summarize it in chat. If asked to sync to an external notebook (NotebookLM, notebook.google.com, Google Docs) and no connector exists, write one self-contained upload-ready markdown file in the artifact dir, give its path, and state that nothing was synced. | ✔ | ✔ | ✔ |

**Credit discipline (applies to every budget):** one orchestrator chat per repo (a second chat on the same tree doubles ingestion and causes lane conflicts). Prefer commands over subagents for anything a script can answer. Redirect verbose output to `/tmp` and read only summaries. Do not restart research that an artifact from the last 7 days already verified. Stop and report when the remaining items are all NEEDS-USER-DECISION.
