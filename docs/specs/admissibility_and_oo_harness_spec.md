# AEIB Technical Specification: Admissibility Triad, Polymorphic Descriptive OO-Harness, and Multi-Agent SPoF Detection

**Document Version:** `v1.1.0-preprod`  
**Status:** Evaluated and Configured Prototype Specification  
**Classification:** Core Governance & Boundary Protocol Specification  
**Epistemic Baseline:** Under the stated model, actions are proposed by guest models and decided by out-of-process deterministic governance harnesses.

---

## 1. Executive Summary & Epistemic Scope

This specification formalizes the Five Surviving Architectural Principles derived from the `/decide` adversarial epistemic audit:

1. **Polymorphic Descriptive OO-Policy Harness**: A two-tier architectural separation where base invariant evaluation remains invariant across all candidate models, while domain-specific execution policies (`FinancialTransferHarness`, `KnowledgeVaultCommitHarness`) dispatch via deterministic class polymorphism in $O(1)$ time ($<0.05\,\text{ms}$) with zero LLM token consumption on the enforcement path.
2. **Admissibility Triad Protocol**: Formalization of the decision vector $\text{Admissibility} = \langle \text{Evidence}, \text{Authority}, \text{Standing} \rangle$, producing four discrete, non-negotiable verdicts (`ALLOW`, `HOLD`, `DENY`, `ESCALATE`).
3. **Provenance Entropy Tagging**: Cryptographic tiering distinguishing human-signed inputs (`HUMAN_VERIFIED_SIGNED`), deterministic probe outputs (`DETERMINISTIC_PROBE`), and unverified synthetic model completions (`AI_GENERATED_UNVERIFIED`).
4. **Shared-Dependency SPoF Detection**: Graph analysis across concurrent agent deployment topologies, halting execution with `HALT_SHARED_DEPENDENCY_RISK` when parallel subagents share underlying vector databases, relational connection pools, or network conduits.
5. **Machine Identity Graph & Shadow Agent Breaker**: Machine credential validation enforcing Ed25519 cryptographic sponsor bindings and fail-closed rejection of unregistered, tampered, or revoked agent identities.

---

## 2. Principle 1: Polymorphic Descriptive OO-Policy Harness

### 2.1 Architectural Invariant: Base Harness Invariance

Candidate agent models (e.g., Anthropic Claude, OpenAI GPT, DeepSeek, Qwen) exhibit nondeterministic text generation and varying prompt sensitivity. Under the AEIB model, candidate models **never** evaluate their own authority, and natural-language prompts are **never** utilized as authorization gates.

The `BaseDescriptivePolicyHarness` provides an immutable contract across all execution environments:

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                     Candidate Action Proposal                          │
 └──────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │              BaseDescriptivePolicyHarness (Global Invariants)          │
 │  • Machine Identity Check: authority.machine_identity_id ∈ revoked?   │
 │  • Sponsor Signature Verification: Ed25519.verify(pubkey, auth_core)   │
 │  • Policy Epoch Verification: proposal.epoch == standing.epoch?        │
 │  • Capability Authorization: proposal.action_class ∈ authority.scopes? │
 └──────────────────────────────────┬─────────────────────────────────────┘
                                    │ (Passed Global Invariants)
                                    ▼
       ┌────────────────────────────┴────────────────────────────┐
       ▼                                                         ▼
 ┌───────────────────────────────┐       ┌───────────────────────────────┐
 │   FinancialTransferHarness    │       │  KnowledgeVaultCommitHarness  │
 │  • Min/Max Minor Unit Caps    │       │  • Provenance Tag Filter      │
 │  • Escrow Solvency Check      │       │  • Anti-Synthetic Pollution   │
 │  • Taint Tier vs Pinned IBAN  │       │  • Human Signature Step-Up    │
 └───────────────────────────────┘       └───────────────────────────────┘
```

### 2.2 Execution Complexity and Critical-Path Latency

- **Dispatch Latency:** $O(1)$ dictionary lookup by `action_class` followed by direct virtual method invocation.
- **Observed Execution Time:** $<0.05\,\text{ms}$ in benchmarked local Python runtimes.
- **Token Overhead:** $0$ prompt tokens, $0$ completion tokens.

---

## 3. Principle 2: The Admissibility Triad Protocol

### 3.1 Mathematical Formulation

Every mutation proposal is evaluated strictly as a 3-tuple:

$$\text{Verdict} = \mathcal{H}_{\text{policy}}\big( \mathbf{E}, \mathbf{A}, \mathbf{S}, \mathbf{P} \big)$$

Where:
- $\mathbf{E} = \langle \text{evidence\_id}, \text{precondition\_hashes}, \text{provenance\_tag}, \text{taint\_tier} \rangle$ represents **Admissible Evidence**.
- $\mathbf{A} = \langle \text{machine\_identity\_id}, \text{root\_sponsor\_id}, \text{allowed\_scopes}, \text{max\_amount}, \text{sig} \rangle$ represents **Applicable Authority**.
- $\mathbf{S} = \langle \text{active\_epoch}, \text{remaining\_budget}, \text{revoked\_ids}, \text{pinned\_payees} \rangle$ represents **Established Standing**.
- $\mathbf{P} = \langle \text{op\_id}, \text{action\_class}, \text{amount}, \text{target}, \text{epoch} \rangle$ represents the **Candidate Action Proposal**.

### 3.2 Discrete Verdict Space

1. **`ALLOW`**: All invariants satisfied; proposal proceeds to Station 1 Write-Ahead Log (WAL) latching.
2. **`HOLD`**: Invariants syntactically valid but transient conditions unsatisfied (e.g., `HOLD_INSUFFICIENT_ESCROW_BUDGET`). Transaction pauses until budget replenishment or outbox recovery.
3. **`DENY`**: Structural or cryptographic invariant violation (e.g., `ERR_MACHINE_IDENTITY_REVOKED`, `ERR_SHADOW_AGENT_UNREGISTERED_SPONSOR`, `ERR_MISSING_ADMISSIBLE_PRECONDITION_EVIDENCE`). Proposal is permanently rejected and logged to the non-repudiable audit trail.
4. **`ESCALATE`**: Context exhibits high risk (e.g., `TIER_2_UNTRUSTED` taint directed at unpinned payee, or unverified synthetic knowledge commit). Execution halts pending out-of-band Ed25519 human supervisor step-up.

---

## 4. Principle 3: Provenance Entropy Tagging

### 4.1 Provenance Hierarchy

| Provenance Tag | Source Description | Admissibility Scope |
|:---|:---|:---|
| `HUMAN_VERIFIED_SIGNED` | Cryptographically signed by verified human supervisor key. | Unrestricted entry into core knowledge vaults and configuration tables. |
| `DETERMINISTIC_PROBE` | Emitted by reproducible AST or database precondition probe. | Permitted as operational evidence for transient automated actions. |
| `AI_GENERATED_UNVERIFIED` | Raw generation from LLM or multi-agent chain without human review. | Strictly quarantined; rejected from core knowledge vaults with `ESCALATE`. |

### 4.2 Taint Monotonicity

Taint tiers are ordered over a lattice:

$$\text{TIER\_0\_PINNED} \prec \text{TIER\_1\_INTERNAL} \prec \text{TIER\_2\_UNTRUSTED}$$

Downstream operations cannot downgrade taint without an explicit, signed step-up warrant. Any attempt to disburse funds to an unpinned target while operating under $\text{TIER\_2\_UNTRUSTED}$ taint triggers `ESCALATE_TAINTED_UNPINNED_PAYEE_REQUIRES_HUMAN`.

---

## 5. Principle 4: Multi-Agent Shared-Dependency SPoF Detection

### 5.1 The "Common Conduit" Failure Mode

In multi-agent architectures, independent subagents may be provisioned with diverse model backends (e.g., Agent A on Claude, Agent B on GPT-4) to simulate redundancy. However, if both agents share an identical underlying vector database, database connection pool, or network conduit, an infrastructure failure or poisoning attack creates correlated failure across all agents.

### 5.2 Topological Audit Algorithm

Given a set of active agent nodes $\{N_1, N_2, \dots, N_k\}$, the `SharedDependencySpofAuditor` constructs pairwise collision sets:

$$\text{Collisions}_{\text{RAG}} = \big\{ (N_i, N_j) \mid i \neq j \land N_i.\text{rag\_uri} = N_j.\text{rag\_uri} \big\}$$
$$\text{Collisions}_{\text{DB}} = \big\{ (N_i, N_j) \mid i \neq j \land N_i.\text{pool\_uri} = N_j.\text{pool\_uri} \big\}$$
$$\text{Collisions}_{\text{Net}} = \big\{ (N_i, N_j) \mid i \neq j \land N_i.\text{conduit} = N_j.\text{conduit} \big\}$$

If $|\text{Collisions}| > 0$, the topology audit returns:
- `disposition`: `HALT_SHARED_DEPENDENCY_RISK`
- Full diagnostic report enumerating conflicting agent pairs.

---

## 6. Principle 5: Machine Identity Graph & Shadow Agent Breaker

### 6.1 Epistemic Rationale

Industry telemetry indicates machine identities outnumber human operators by more than 100 to 1. Unregistered autonomous agents ("shadow agents") spawn dynamic child subagents without cryptographically bound sponsor delegations.

### 6.2 Wire-Level Verification

Before any action reaches the domain harness:
1. `authority.machine_identity_id` is queried against `standing.revoked_identities`. If present, returns `ERR_MACHINE_IDENTITY_REVOKED`.
2. `authority.root_sponsor_id` is resolved in the trusted sponsor key registry. If missing, returns `ERR_SHADOW_AGENT_UNREGISTERED_SPONSOR`.
3. The authority payload is canonicalized using RFC 8785 JSON Canonicalization Scheme (JCS) and verified using Ed25519. If invalid, returns `ERR_INVALID_MACHINE_IDENTITY_SIGNATURE`.

---

## 7. Verification and Test Invariants

The reference implementation in `tools/aeib_surviving_principles_engine.py` and `scripts/verify_research_claims.py` enforces the following verified test cases:

1. **Shadow Agent Interception:** Unregistered sponsor credentials trigger fail-closed `ERR_SHADOW_AGENT_UNREGISTERED_SPONSOR`.
2. **Missing Precondition Evidence:** Actions lacking probe hashes trigger fail-closed `ERR_MISSING_ADMISSIBLE_PRECONDITION_EVIDENCE`.
3. **Tainted Unpinned Payee Escalation:** TIER 2 untrusted context attempting transfer to unpinned payee triggers `ESCALATE_TAINTED_UNPINNED_PAYEE_REQUIRES_HUMAN`.
4. **Nominal Triad Approval:** Full triad verification yields `ALLOW` with `llm_fallback_invoked == False`.
5. **Synthetic Knowledge Protection:** Unsigned AI outputs attempting vault commit trigger `ESCALATE_UNVERIFIED_SYNTHETIC_OUTPUT_REQUIRES_HUMAN_SIGN`.
6. **Parallel Topology SPoF:** Correlated multi-agent RAG vector dependencies trigger `HALT_SHARED_DEPENDENCY_RISK`.
7. **2-Hop Research Verification:** Academic claims are validated against arXiv, OpenAlex, and GitHub APIs, categorizing findings into `VERIFIED_PRIMARY_SOURCE`, `CONCEPT_VALID_SOURCE_UNCONFIRMED`, and `UNVERIFIED_QUARANTINED`.
