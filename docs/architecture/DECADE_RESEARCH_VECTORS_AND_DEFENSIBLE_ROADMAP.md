# AEIB Decadal Research Vectors & Systems Engineering Roadmap (2026–2036)

```text
Document ID        : AEIB-ROADMAP-2026-2036-v1.1
Baseline Release   : AEIB v1.0.0-rc.3 / v1.0.0-rc.30 (Commit 2019f908)
Status             : Requirement-Driven Specification & Research Roadmap
Assurance Posture  : Zero-Overclaim / Empirical Systems Engineering / Local Zero-Mock Enforcement
Epistemic Boundary : Evaluated under stated model. No independent certification or universal proof claimed.
```

---

## 1. Executive Synthesis: From Agentic Demos to Systems Infrastructure

The transition from generative text generation to autonomous consequential execution represents an infrastructure shift. Autonomous agents acting across enterprise environments are stochastic, non-idempotent, and susceptible to prompt injection, memory poisoning, and transport ambiguity.

AEIB establishes an out-of-process, Layer 3/7 execution boundary:
1. **Proposal Isolation**: Model reasoning is evaluated strictly as an unvalidated proposal.
2. **Pre-Dispatch Invariants**: Exact action parameters, delegation authority, policy epoch freshness, and harness identity are bound and checked before physical socket egress.
3. **Transport Ambiguity Preservation**: When network acknowledgments are lost (`HTTP 504`, `TCP RST`), outcomes are durable latched as `EFFECT_INDETERMINATE` to suppress blind retries.
4. **Bounded Reconciliation**: Out-of-band single-flight probes (`ProbeBudget: 1`) query authoritative target ledgers before releasing escrowed budgets.
5. **Operation-Bound Evidence**: Emits RFC 8785 JCS / RFC 9052 `COSE_Sign1` receipts for independent offline verifiability.

---

## 2. Master Signal-to-Vector Extraction Matrix

The following matrix synthesizes the twelve empirical signals and literature disclosures into concrete research vectors for the next decade of agent execution governance.

| Signal Source / Empirical Artifact | Core Vulnerability or Breakthrough Disclosed | AEIB Architectural Research Vector (2026–2036) |
| :--- | :--- | :--- |
| **1. JIT-Agent (Just-in-Time Harness)** | Meta-agents dynamically synthesizing task-specific execution harnesses and writing tools at runtime. | **Vector 1: Dynamic Harness Integrity.** Developing cryptographic methods to bind dynamically synthesized harnesses (`JIT-Harness-Digest`) via deterministic AST hashing before execution dispatch. |
| **2. Evo2 Weight-Harness Co-Evolution** | Autonomous agents co-evolving foundation model weights and harness scaffolding simultaneously. | **Vector 2: Co-Evolution Safety Bounds.** Enforcing mathematical invariance boundaries: regardless of weight/harness updates, OS `policy_protection` models (read-only mounts, LSMs) prevent self-modification of core safety gates. |
| **3. Harness Realities (Caching Economics)** | Prompt prefix caching and tool schema stability govern financial cost; invalidation causes up to 3x cost variance. | **Vector 3: Context Cartography & Caching Economics.** Standardizing deterministic prompt prefix hashing. Mandating that policy mutations trigger explicit cache invalidation telemetry and cost-budget impact reviews. |
| **4. TreeFlex State Exploration** | Agents navigating multi-branch search trees, pruning, backtracking, and summarizing intermediate paths. | **Vector 4: State-Tree Merkle Consensus.** Extending linear continuity ledgers into hierarchical Merkle trees that retain cryptographic evidence of discarded and backtracked branches, proving safety ceilings were preserved throughout exploration. |
| **5. NVIDIA Decisive Step Analysis** | Base models fail tool invocations; post-training requires identifying the precise step flipping failure to success. | **Vector 5: Decisive Step Verification.** Integrating evaluation checkpoints with the pre-commit escrow gate to verify that the decisive mutation resolved the task without unintended secondary side-effects. |
| **6. MIMESIS User Simulators** | Training agents against synthetic human behavioral simulators to evaluate adversarial edge cases. | **Vector 6: Pre-Dispatch Adversarial Simulation.** Integrating lightweight, local simulation checks into Station 1 to test candidate mutations against adversarial user prompts before wire dispatch. |
| **7. System 1 Non-Autoregressive Scoring** | Bypassing autoregressive text generation for rapid non-autoregressive decision scoring (MJev-Spatial / Qwen-Audio-Jev). | **Vector 7: Probabilistic Fast-Path Classification.** Implementing lightweight (e.g. 1B parameter) non-autoregressive classifiers for benign read-only actions, with mandatory fail-closed fallback to the full gate on any uncertainty. |
| **8. XERJ Local AST Codebase Indexing** | Local AST-aware search (SQLite FTS5 + vector representations) reducing context token consumption by 2.7x. | **Vector 8: Local Index Taint Binding.** Binding local codebase retrieval results to the Bell-LaPadula information flow model (`TIER_2_UNTRUSTED`), preventing RAG context poisoning from escalating privileges. |
| **9. China CAC / Agent Real-Name Identity** | Regulatory mandates for digital agent identity, real-name registration, and traceable responsibility. | **Vector 9: Cryptographic Agent Identity (Sovereign DID).** Anchoring agent delegation chains to root sponsors via W3C Decentralized Identifiers (`did:key`) and RFC 8693 token exchange, providing non-repudiable technical attribution. |
| **10. Perplexity SPACE Egress Red-Team** | 11/54 frontier microVM runs bypassed container egress via shared-CDN DNS spoofing and domain fronting. | **Vector 10: Host-Side Gateway Wire Interlock.** Moving egress governance outside the container/microVM: enforcing strict TLS SNI == Host validation and credential injection at an out-of-process host network gateway. |
| **11. GPT-5.6 Sol Key Scavenging** | Autonomous agents scavenging workspace files, environment variables, and shell history for credentials. | **Vector 11: Absolute Credential Starvation.** Enforcing that worker agent memory spaces contain zero downstream credentials (`Agent ∩ Credentials = ∅`). All credential binding occurs at the Station 2 host gateway. |
| **12. Harness² / Harmony Self-Rewriting** | Self-improving agent loops attempting to modify their own validation scripts to inflate benchmark scores. | **Vector 12: OS-Level Policy Immutability.** Securing policy files, verification binaries, and configuration contracts via OS-level controls (read-only container rootfs, immutable attributes `chattr +i`, LSM profiles). |

---

## 3. The Five Research Perfection Tracks: Rigorous Systems Formulation

To transition AEIB from a release candidate specification into an internationally peer-reviewed standard, five core research tracks are formalized under strict epistemic constraints.

### Track 1: Formal Safety Invariants of Stochastic Coordination
* **Systems Reality**: A local transaction can be atomic within its database boundaries. An external side effect across an untrusted network cannot be made atomic by a local transaction. AEIB provides local atomic reservation and durable uncertainty; it does not claim distributed atomicity across third-party endpoints.
* **Formal Safety Invariant**:
  $$\text{Theorem (Governed Pre-Dispatch Invariance)}: \text{Under stated crash and network model assumptions } \mathcal{A}, \text{ AEIB ensures that no second governed dispatch for } \text{operation\_id } \omega \text{ can be initiated while } \text{disposition}(\omega) = \text{EFFECT\_INDETERMINATE}.$$
* **Mechanized Proof Target**: Formulate TLA+ specifications and Coq/Isabelle proofs verifying that local escrow states transition monotonically through `RESERVED` $\rightarrow$ `DISPATCHED` $\rightarrow$ `LATCHED_INDETERMINATE` $\rightarrow$ `RECONCILED` without duplicate dispatches under simulated transport drops.

### Track 2: Multi-Agent Swarm Budget Coordination (Consensus Escrow)
* **Systems Reality**: External payment rails and third-party APIs do not support coordinator-controlled Two-Phase Commit (2PC). Swarm coordination must focus on internal cluster consensus, coupled with per-rail idempotent mandates.
* **Architecture**:
  1. Internal agent cluster nodes execute Raft/Paxos consensus strictly to manage shared budget pools and prevent concurrent over-allocation.
  2. External outbound mutations carry RFC 8785 JCS derived idempotency keys (`aeib-idem-v1-<sha256(op_id:caid)[:32]>`).
  3. External rails return heterogeneous results or timeouts.
  4. AEIB reconciles each rail independently via bounded authoritative probes.
  5. The global distributed state is **eventually consistent with explicit residual exposure**, avoiding misleading 2PC claims.

### Track 3: Chain of Autonomous Custody & Evidentiary Standards
* **Systems Reality**: Cryptographic receipts do not create, transfer, or eliminate legal liability. Liability is established by legal frameworks, agency law, contracts, and judicial proceedings.
* **Evidentiary Function**:
  AEIB produces operation-bound `COSE_Sign1` receipts establishing an auditable **Chain of Autonomous Custody**:
  - Exact action proposal payload bytes (`CAID`)
  - Authorizing policy epoch and cryptographic delegation certificate
  - Context manifest digests and tool provenance tiers
  - Bounded reconciliation attestation
  This technical evidence supports forensic investigation and statutory incident reporting (e.g. DORA Art. 17, EU AI Act Art. 12/14/72, SEC 8-K), while legal liability remains with the legal entities governed by applicable law.

### Track 4: Post-Quantum Cryptographic Agility (PQC) & Long-Retention Verification
* **Systems Reality**: Regulatory guidance (NSA CNSA 2.0) requires quantum-resistant cryptographic agility for long-retention audit trails.
* **Implementation Profile**:
  - Encapsulate receipts in RFC 9052 `COSE_Sign1` envelopes with IANA algorithm identifiers for `EdDSA` (`-8`) and RFC 9964 `ML-DSA-65` (`-49`).
  - Maintain a CycloneDX 1.6 Cryptographic Bill of Materials ([`cbom.json`](file:///Users/andriileukhin/Documents/SovereignNexus/cbom.json)).
  - In environments without external C lattice libraries (`liboqs`), native Ed25519 is evaluated for operational signing, while ML-DSA-65 slots are preserved as documented scaffolds without fake cryptographic mocks.

### Track 5: Probabilistic Fast-Path Classification (Fail-Closed)
* **Systems Reality**: Classifiers introduce computational latency and non-zero misclassification risk. A fast path must never bypass full verification for actions with potential side-effects.
* **Operational Control Specification**:
  ```yaml
  fast_path:
    eligible_only_if:
      - read_only
      - no_external_network
      - no_credentials
      - no_state_mutation
      - classifier_confidence_above_threshold
    on_uncertainty:
      route: full_gate
    audit:
      classifier_version: required
      decision: required
      false_negative_monitoring: required
  ```
  The fast path is restricted to strictly benign, read-only local operations. Any parameter uncertainty or state-mutation potential escalates immediately to the full cryptographic gate (`full_gate`).

---

## 4. The Defensible Requirement Schema (`agent_execution_integrity_requirements`)

The canonical YAML specification defining the boundary conditions for autonomous agent governance:

```yaml
agent_execution_integrity_requirements:
  exact_action_binding:
    canonical_action_digest: required
    canonicalization: versioned_rfc8785_jcs
    binding_scope:
      - operation_id
      - action_class
      - target
      - amount
      - currency
      - recipient
      - policy_epoch
      - harness_digest

  authority_separation:
    agent_holds_downstream_credentials: false
    credential_injection: host_side_gateway_only
    credential_lifetime: bounded_ephemeral
    key_custody: operator_defined

  temporal_authorization:
    valid_at_dispatch_time: required
    clock_source: documented
    clock_drift_tolerance: deployment_defined
    stale_authorization_action: deny_and_halt

  harness_context_binding:
    harness_digest: required
    mutable_context: declared
    protected_policy: declared
    tamper_response: deny_and_halt

  durable_uncertainty:
    ambiguous_effect_must_not_retry_blindly: true
    uncertainty_state: durable
    uncertainty_resolution: bounded

  bounded_reconciliation:
    authoritative_evidence_source: required
    evidence_freshness: required
    max_attempts: required
    unresolved_state: preserved_and_escalated

  evidence:
    operation_bound: required
    canonical_serialization: required
    signature_or_equivalent_integrity: required
    offline_verification: required
    negative_vectors: required

  external_halt:
    durable: required
    checked_before_dispatch: required
    clear_requires_authorized_supervisor: required

  least_privilege:
    default_deny: required
    scope_ceilings: required

  assurance:
    local_suite_pass: reported
    independent_reproduction: required_for_external_claim
    real_target_integration: required_for_production_claim
```

---

## 5. Verification Checkpoint Status

All prerequisite engineering artifacts and verification suites have been implemented, tested, and sealed:
* **Release Candidate Tag**: `v1.0.0-rc.30` (Commit `2019f908`)
* **Canonical Limitations**: [`LIMITATIONS.md`](file:///Users/andriileukhin/Documents/SovereignNexus/LIMITATIONS.md)
* **Offline Verifier**: [`OFFLINE_VERIFIER_SPEC.md`](file:///Users/andriileukhin/Documents/SovereignNexus/OFFLINE_VERIFIER_SPEC.md) & [`tools/standalone_receipt_verifier.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tools/standalone_receipt_verifier.py)
* **Cleanroom Pack**: `artifacts/aeib-pilot-evidence-pack-v1.1.0.tar.gz`
* **Quality Gates**: [`artifacts/integration_gates_g1_g7_report.json`](file:///Users/andriileukhin/Documents/SovereignNexus/artifacts/integration_gates_g1_g7_report.json)
