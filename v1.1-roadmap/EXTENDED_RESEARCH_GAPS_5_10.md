# Extended Research Gaps 5–10: Standards & Architecture Candidate Mapping (`v1.1`)

> **Epistemic Boundary Notice:**  
> *Research informs design; it never becomes a claim.*  
> The frameworks, drafts, and benchmarks below (TA-14 SCGA, AEIM v1.2.0, Apple GAAT, OpenA2A / MTC, LICITRA-MMR, and IETF SCITT Agent Profile) are recorded strictly as **v1.1 research and specification candidates**. AEIB `v1.0.0-rc.1` does not claim compatibility, conformance, certification, or formal alignment with any of these specifications until a dedicated specification, test suite, and verifiable evidence artifact exist.

---

## 1. Architectural Candidate Matrix (Gaps 5–10)

| Gap ID | External Research / Draft Reference | Core Technical Mechanism | `v1.0.0-rc.2` Baseline Boundary | `v1.1` Specification / Test Candidate |
| :--- | :--- | :--- | :--- | :--- |
| **Gap 5** | **TA-14 SCGA (Admissible Computation)** | Authority and standing must be evaluated before compute or network commitment. | `Station0AdmissionGate` pins manifest digests locally before dispatch. | **Zero-Allocation Admission Hook:** O(1) standing evaluation (e.g., Cedar/OPA) before JCS cryptographic canonicalization begins. |
| **Gap 6** | **AEIM v1.2.0 (Agent Integrity Manifest)** | Machine-readable tool boundaries, identity constraints, and Evidence-Before-Effect (EO-1). | Pinned JSON capability schemas and post-dispatch `ContinuityReceipt`. | **Native AEIM Consumption:** Consume standardized AEIM schemas and flush `PRE_DISPATCH_COMMITTED` intent before socket I/O. |
| **Gap 7** | **Apple GAAT (Generative Agent Action Tokens)** | Telemetry binding an agent's reasoning trace to OS-level sandboxed actions. | `ContinuityReceipt` exposes deterministic event phases and dispositions. | **OTel Governance Projection:** Map receipt fields to OpenTelemetry semantic attributes (`gaat.*` telemetry). |
| **Gap 8** | **OpenA2A / MTC (Agent-to-Agent Contracts)** | Cryptographic identity, mutual trust contracts, and lateral delegation protocols. | Credential vaulting and RFC 8707 resource audience binding. | **A2A Delegation Verification:** Validate cross-agent authority chains (root principal $\to$ delegating agent $\to$ task scope). |
| **Gap 9** | **LICITRA-MMR (Merkle Mountain Range)** | $O(\log N)$ logarithmic append-only inclusion proofs for tamper-evident ledgers. | Linear SHA-256 hash chaining (`chainTip`) in `Station3ContinuousLedger`. | **MMR Accumulator:** Sub-linear historical verification without full chain replay for enterprise auditors. |
| **Gap 10** | **IETF SCITT & COSE (RFC 9942/9943)** | Standardized receipt formats and decoupled transparency service registration. | Custom RFC 8785 canonical JSON envelope signed with Ed25519. | **COSE_Sign1 Profile:** Output standard COSE receipts and provide asynchronous SCITT transparency anchoring. |

---

## 2. The Dramatic Pivot: Solving the Compute Exhaustion Blind Spot

The integration of **Admissible Computation (Gap 5)** addresses an observed architectural vulnerability in earlier models. AEIB excels at deterministic cryptographic operations (RFC 8785 JCS, Ed25519 signing). However, if an unauthorized agent or adversarial payload floods the boundary, processing those payloads through JCS canonicalization *before* rejecting them creates a CPU exhaustion vector.

To harden the boundary, `Station0AdmissionGate` incorporates a **zero-allocation, O(1) enforcement edge** ([`ZeroAllocationAdmissionHook`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/unified_governance_stack.py#L3635-L3685)). By evaluating the identity, scope, and standing predicate in microseconds via static sets and bitmasks before serialization, non-admissible payloads are dropped immediately. **Zero cryptographic compute is committed to an unauthorized request.**

---

## 3. The Compounding Advantages: v1.1 Defensible Moats

By synthesizing observed GitHub ecosystems, IETF drafts, and intergovernmental frameworks, AEIB’s next iteration transitions from a closed-loop cryptographic boundary into an interoperable governance primitive:

* **Native MCP Middleware Adapter:** Enterprises are standardizing on the Model Context Protocol (MCP) for tool exposure. AEIB evaluates a drop-in reverse proxy sitting directly in front of MCP servers ([`UberMcpRegistryGate`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/unified_governance_stack.py#L3300-L3360)). This interceptor pins tool identity, evaluates standing, and latches `EFFECT_INDETERMINATE` on wire faults without modifying upstream agent prompts or downstream tool code.
* **The Logarithmic Audit Moat (MMR):** Linear hash chains are mathematically sound but scale linearly in verification depth. Upgrading Station 3 to a **Merkle Mountain Range** ([`LicitraMmrLedger`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/unified_governance_stack.py#L250-L380)) allows independent auditors to verify receipts in $O(\log N)$ time, providing rapid compliance proofs for high-frequency workloads.
* **COSE/SCITT Transparency Anchoring:** Standardized receipt formats mitigate procurement friction. Wrapping the RFC 8785 statement in a standard **COSE_Sign1** envelope ([`ScittOtelActionCapsuleCorrelator`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/unified_governance_stack.py#L2400-L2480)) enables integration with SCITT transparency ledgers, decoupling the Issuer (Agent Operator) from the Transparency Service (Evidence Custodian).
* **Cross-Agent (A2A) Delegation Chains:** As multi-agent swarms emerge, governance must evaluate lateral delegation. AEIB evaluates not just single-agent standing, but the full cryptographic chain of custody ([`CrossAgentDelegationVerifier`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/unified_governance_stack.py#L3690-L3810)): verifying that root principals authorized delegating agents, and delegating agents attenuated task scope to worker agents before external mutations dispatch.

---

## 4. Detailed Technical Analysis & `v1.0.0-rc.2` vs. `v1.1` Distinction

### Gap 5: TA-14 SCGA Admissible Computation
* **Design Principle:** Computational or network side-effects should not be initiated unless the governing manifest and standing are evaluated prior to execution.
* **Current `v1.0.0-rc.2` Implementation:** `Station0AdmissionGate` and `Station1DispatchInterlock` evaluate the pinned manifest and derive the RFC 8785 Content-Addressed Action Identifier (`CAID`) locally in memory with zero network egress.
* **`v1.1` Prototype Scope:** `ZeroAllocationAdmissionHook` provides an $O(1)$ static edge check dropping unauthenticated callers or revoked standing before JCS byte canonicalization begins.

### Gap 6: AI Execution Assurance Benchmark (AEIM v1.2.0 — `EO-1`)
* **Design Principle:** `EO-1` (*Evidence-Before-Effect*) requires that an immutable record of intent be committed before the external mutating socket write occurs, preventing unlogged side-effects if the process crashes mid-syscall.
* **Critical Epistemic Calibration for `v1.0.0-rc.2`:** In `v1.0.0-rc.2` (`Gate4IntegrationTest.java`), the runtime dispatches the HTTP POST (`INDETERMINATE`), reconciles via `Station2EffectReconciler`, and then appends `EventPhase.RECONCILED` to `Station3ContinuousLedger` to mint the `ContinuityReceipt`. Therefore, `v1.0.0-rc.2` demonstrates **post-fault reconciliation and receipt binding**, whereas strict **pre-dispatch receipt commitment (`EO-1`)** requires appending and signing a `DISPATCH_INTENT` ledger event *before* `dispatcher.dispatch(postReq)` is invoked—scheduled as a testable `v1.1` enhancement.

### Gap 7: Governance-Aware Agent Telemetry (Apple GAAT / OpenTelemetry)
* **Design Principle:** Telemetry spans should carry structured, deterministic governance attributes (`aeib.caid`, `aeib.disposition`, `aeib.probe_budget.remaining`, `aeib.key_id`) for inline policy observability.
* **`v1.1` Prototype Scope:** Specify a pure-data mapping from `ContinuityReceipt` and `ReconciledState` records to OpenTelemetry span attributes (`gaat.*` namespace) without introducing outbound network dependencies into `ai.sovereign.aeib.core`.

### Gap 8: Post-Quantum Agent Identity & OpenA2A Delegation
* **Design Principle:** Combine classical `Ed25519` (`64 B` signature, low verification latency) with lateral delegation tracking and NIST FIPS 204 `ML-DSA-65` (`3,309 B` signature) for long-horizon receipt attribution.
* **`v1.1` Prototype Scope:** `CrossAgentDelegationVerifier` evaluates lateral delegation links with scope attenuation and epoch expiration; evaluated alongside two-tier signing candidates on epoch roots.

### Gap 9: LICITRA-MMR (Merkle Mountain Range) Ledger
* **Design Principle:** Replace $O(N)$ linear hash-chain traversal with an append-only Merkle Mountain Range (MMR) supporting $O(\log N)$ inclusion proofs.
* **`v1.1` Prototype Scope:** `LicitraMmrLedger` provides peak bagging, logarithmic inclusion proofs, and consistent hash ring routing.

### Gap 10: IETF SCITT AI Agent Execution Profile
* **Design Principle:** Decouple the runtime **Issuer** (`Station3ContinuousLedger`) from an external **Transparency Service** that countersigns registration timestamps.
* **`v1.1` Prototype Scope:** Define an asynchronous out-of-band transparency registration profile using standard `COSE_Sign1` envelopes while keeping core `Station4` verification strictly offline and air-gapped.

---

## 3. Unified Architectural Stack & Four Stakeholder Mental Models

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       THE AI GOVERNANCE UNIFIED STACK                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. REGULATORY CEILING (prEN 18282 / EU AI Act Art. 15)                      │
│     • Outcome-based cybersecurity controls & external compliance graphs     │
├─────────────────────────────────────────────────────────────────────────────┤
│  2. DISTRIBUTED LEDGER & REPLICATION (NoSQL / LICITRA-MMR)                  │
│     • Continuous hashing: Real-time tamper detection at every append        │
│     • Consistent hashing: Ring-0 partition routing across gateway nodes     │
│     • Merkle Anti-Entropy: O(log n) inclusion proofs & split-brain HALT     │
├─────────────────────────────────────────────────────────────────────────────┤
│  3. WIRE CONTROL & PROXY GATE (LICITRA-SENTRY / Write-Before-Execute)       │
│     • Ed25519 Execution Tickets: Exact payload binding to RFC 8785 CAID     │
│     • Write-Before-Execute: Pre-dispatch receipt is a condition of wire I/O │
│     • Default-Closed Wire Interception: Zero bypass to target sockets       │
├─────────────────────────────────────────────────────────────────────────────┤
│  4. RUNTIME FLOOR (Headroom-Class Proxy)                                    │
│     • Context compression, schema pruning, and token efficiency             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Mapping the Four Mental Models to Verified `v1.0.0-rc.1` Symbols & `v1.1` Targets

| Mental Model | Core Mechanism | Verified in `v1.0.0-rc.1` | Scheduled in `v1.1` / `v1.2` |
| :--- | :--- | :--- | :--- |
| **1. Wire Control Gate**<br>*(The Bank Teller Vault Rule)* | Side-effects require cryptographic payload binding to the RFC 8785 `CAID` before wire access. | `Station0AdmissionGate` + `Station1DispatchInterlock` compute `CAID = SHA-256(JCS(payload))` and enforce pre-dispatch standing in memory. | Out-of-process wire proxy gate (`LICITRA-SENTRY`) consuming single-use Ed25519 Execution Tickets + `PAD-016` Heartbeat chains. |
| **2. Write-Before-Execute**<br>*(The Immutable Deposit Slip)* | Governance evidence is committed as a precondition of wire execution; failed log writes abort dispatch fail-closed. | `Gate4IntegrationTest` verifies post-fault reconciliation (`INDETERMINATE` -> 1 probe -> `ContinuityReceipt`). | Strict `EO-1` pre-dispatch intent ledger append (`EventPhase.DISPATCH_INTENT`) prior to socket write. |
| **3. Continuous Hashing**<br>*(The Real-Time Immune System)* | Every `appendEvent()` and `generateReceipt()` extends and verifies the cryptographic hash chain in real time. | `Station3ContinuousLedger` computes `chainTip = SHA-256(prevTip \|\| eventBytes)` under `synchronized` lock and signs with Ed25519 (`Ed25519ProofEngine`). | `LICITRA-MMR` Merkle Mountain Range accumulator for $O(\log n)$ inclusion proofs over $10^6+$ events. |
| **4. Merkle Anti-Entropy**<br>*(Fail-Closed Causal Safety)* | Divergent state or ambiguous transport faults never resolve via Last-Write-Wins (LWW); they halt fail-closed. | `Station2EffectReconciler` + `DefaultSemanticStateEvaluator` latch `EffectDisposition.CONFLICT` or `EFFECT_INDETERMINATE` and block speculative retries. | Multi-gateway Merkle root anti-entropy comparison latching `EFFECT_INDETERMINATE` on partition divergence, plus `v1.2` CT-style Witnessed Signed Tree Heads. |

---

## 4. The 10-Signal Industry Convergence Matrix

> **Epistemic Calibration Notice:**  
> External industry observations, practitioner reports, and red-team write-ups are recorded below as architectural signals that inform AEIB test vectors and `v1.1` prototype primitives. Under the stated model, all claims remain strictly bounded by observed test outputs, offline-verifiable artifacts, and declared structural scaffolding constraints (`AGENTS.md` §§1, 5).

| Signal # | Industry Signal & External Reference | Observed Failure Mode / Architectural Problem | AEIB `v1.0.0-rc.1` Baseline Symbol | AEIB `v1.1` Prototype Class / Verification Artifact |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Tool Surface**<br>(`GridEx` & `Pryxor`) | Raw bearer tokens, API keys, or ambient credentials exposed in agent context or tool call payloads enable lateral exfiltration and unauthorized endpoint invocation. | `Station0AdmissionGate` (local pinned manifest digest verification before dispatch without external I/O) | `CredentialVaultGate` (`v1.1-roadmap/unified_governance_stack.py`): binds opaque `credential_ref` handles to allowed target URI scopes and halts fail-closed (`GovernanceHaltError`) if raw secrets or bearer patterns appear in payloads. |
| **2** | **Reasoning Isolation**<br>(`Fork-and-Flush`) | Unverified chain-of-thought or natural-language rationale fields leak into downstream wire payloads or contaminate deterministic action hashing. | `Station1DispatchInterlock` (`com.aeib.runtime.Station1DispatchInterlock`): constructs explicit RFC 8785 JCS `CAID` envelopes over typed `CandidateAction` fields and enforces strict epoch equality. | `ForkAndFlushContextBoundary` (`v1.1-roadmap/unified_governance_stack.py`): strips ephemeral reasoning fields (`_reasoning`, `chain_of_thought`, `rationale`, `explanation`) recursively before computing wire `CAID` and evaluating boolean standing. |
| **3** | **Specification Gaming**<br>(`AI Finds A Way`) | Agents optimize for self-reported completion metrics or fabricate success assertions when underlying target mutations fail, time out, or roll back. | `Station2EffectReconciler` & `ProbeBudget` (`com.aeib.runtime.Station2EffectReconciler`): queries target state via `TargetStatusClient` under bounded concurrency, rate limits, and reconciliation deadlines. | `AntiSpecGamingReconciler` (`v1.1-roadmap/unified_governance_stack.py`): reconciles `agent_self_report` against observed `target_state` under a bounded `probe_budget`, returning `REFUTED` or `EFFECT_INDETERMINATE` and incrementing `spec_gaming_alerts` when self-reports contradict target reality. |
| **4** | **Interpretability Crisis**<br>(`The Dead Salmons`) | Post-hoc natural-language explanations and activation heuristics exhibit false-positive correlations ("dead salmon" artifacts) and cannot serve as authorization gates. | `Jcs.canonicalize` (`ai.sovereign.aeib.core.Jcs`) & `Rfc8785Canonicalizer`: non-explanatory RFC 8785 JCS byte canonicalization over explicit wire parameters. | `ForkAndFlushContextBoundary.evaluate_boolean_standing`: evaluates authorization purely as a boolean predicate over flushed canonical wire parameters so persuasive prose cannot influence the dispatch verdict. |
| **5** | **Memory Staleness**<br>(`Cognitive Governance`) | Long-horizon agents act on cached retrieval state or stale policy epochs after upstream source state or authorization policies have mutated (`STALE_DONT_TRUST_YET`). | `Station1DispatchInterlock` (strict `proposedEpoch == currentEpoch` check on `CandidateAction`; memory/retrieval provenance explicitly out of scope in `v1.0.0-rc.1`). | `v1.1 TemporalMemoryDigest` (`v1.1-roadmap/unified_governance_stack.py`): binds `MemoryDigest = SHA-256(JCS({contextCaid, policyEpoch, sourceEpoch}))` and transitions to `STALE_DONT_TRUST_YET` (raising `GovernanceHaltError`) when active source or policy epochs advance. |
| **6** | **Wire Enforcement**<br>(`eBPF/LSM Profile`) | Application-layer wrappers can be bypassed if a compromised process invokes raw sockets or attempts unauthorized kernel `bpf(BPF_PROG_LOAD)` syscalls. | `ebpf/aeib_sock_filter.c` & `src/hardware_attestation.rs` (documented strictly as structural scaffolding in `CLAIMS_EVIDENCE.md` `CLM-08` and `AGENTS.md` §5). | `scripts/verify_bpf_lsm_lock.py`: 4-axis diagnostic probe inspecting `/sys/kernel/security/lsm`, negative `bpf(BPF_PROG_LOAD)` syscall rejection (`-EPERM`/`-EACCES`), pinned `/sys/fs/bpf` maps, and CVM devices. Documented strictly as structural scaffolding unless loaded on a locked Linux CVM kernel per `AGENTS.md` §5. |
| **7** | **Verification & Red-Teaming**<br>(`AI Goat 2.0` & `AnyJev`) | Prompt-injected tool calls exploit path traversal (`../`), disallowed URI schemes/hosts, or out-of-range numeric parameters prior to execution. | `Station0AdmissionGate` & `Station1DispatchInterlock` (pinned capability identifier and manifest digest checks prior to dispatch). | `TypedOwaspPreDispatchGate` (`v1.1-roadmap/unified_governance_stack.py`): deterministic typed pre-dispatch gate validating URI scheme/host allowlists, URL-decoded dot-segment traversal (`..`), and strict numeric type/range bounds before minting an `ExecutionTicket`. |
| **8** | **Epistemic Integrity**<br>(`The Klaritee Contrast`) | Vendor marketing materials frequently rely on unsubstantiated claims of absolute security rather than bounded, falsifiable, offline-verifiable artifacts. | `ReceiptVerifier` (`com.aeib.verifier.ReceiptVerifier`) & `VerifierCli`: standalone offline verifier enforcing RFC 8785 JCS re-canonicalization, root-to-statement field binding, and Ed25519 signature verification under caller-supplied SPKI public keys. | `CLAIMS_EVIDENCE.md` & `scripts/ci_claims_verifier.py`: explicit Overclaim Correction Matrix and automated on-disk symbol verification coupling every claim to a concrete test and exit-code contract. |
| **9** | **Implementation Gap**<br>(`GIRAI & WEF Reports`) | High-level AI governance frameworks define aspirational principles without cryptographic state-binding or tamper-evident runtime audit trails. | `Station3ContinuousLedger` (`com.aeib.runtime.Station3ContinuousLedger`) & `ContinuityReceipt`: sequential SHA-256 hash chain (`chainTip = SHA-256(prevTip \|\| eventBinding)`) signed with Ed25519 over RFC 8785 JCS statements. | `LicitraMmrLedger` & `LicitraSentryProxyGate` (`v1.1-roadmap/unified_governance_stack.py`): continuous hash-chain immune check on every append, $O(\log n)$ MMR inclusion proofs, and `PRE_DISPATCH_COMMITTED` Write-Before-Execute (`EO-1`) receipts. |
| **10** | **Post-Dispatch Wire Settlement**<br>(`AEIB Core`) | Mid-flight TCP RSTs, HTTP timeouts, or severed sockets leave side-effects in an ambiguous state where naive retries cause duplicate mutations. | `EffectDisposition.INDETERMINATE` (`EFFECT_INDETERMINATE`) terminal latching in `Station2EffectReconciler`, `DISPATCHED_UNCONFIRMED` lockout (`src/aeib_v040_engine.py`), and `Gate4IntegrationTest.java`. | `benchmarks/jvm_native_diff_engine.py` & `MerkleAntiEntropyReconciler`: cross-language differential verification asserting 0-byte canonical JCS divergence across JVM and Python verifiers and fail-closed `EFFECT_INDETERMINATE` latching on state divergence. |

### 4.1 Signal-by-Signal Architectural & Epistemic Calibration

1. **Signal 1 — Tool Surface (`GridEx` & `Pryxor`) $\rightarrow$ `Station0AdmissionGate` & `CredentialVaultGate`:**
   * **Observed Problem:** Tool-calling agents that receive raw bearer tokens or API keys in prompt context can be induced to exfiltrate credentials or invoke unintended hosts.
   * **Evaluated Mechanism:** `Station0AdmissionGate` verifies the pinned manifest digest locally before dispatch. In the `v1.1` prototype (`CredentialVaultGate`), agent payloads may only reference opaque `credential_ref` handles mapped to an allowed target URI prefix; any payload containing raw secret key names (`authorization`, `api_key`, `bearer`, `private_key`, etc.) or token regex patterns is rejected fail-closed before ticket minting.

2. **Signal 2 — Reasoning Isolation (`Fork-and-Flush`) $\rightarrow$ `Station1DispatchInterlock` & `ForkAndFlushContextBoundary`:**
   * **Observed Problem:** Mixing free-form LLM reasoning traces with structured tool parameters pollutes action hashes and allows prompt injection inside rationale strings to cross the execution boundary.
   * **Evaluated Mechanism:** `Station1DispatchInterlock` constructs a typed `CAID` envelope over `CandidateAction` fields. The `v1.1` `ForkAndFlushContextBoundary` explicitly strips ephemeral reasoning keys (`_reasoning`, `chain_of_thought`, `rationale`, `explanation`) at the context boundary so only canonical wire parameters enter RFC 8785 JCS `CAID` derivation.

3. **Signal 3 — Specification Gaming (`AI Finds A Way`) $\rightarrow$ `Station2EffectReconciler` (`ProbeBudget`) & `AntiSpecGamingReconciler`:**
   * **Observed Problem:** Under optimization pressure, agents can report task completion (`CONFIRMED`) even when the downstream system rejected, rolled back, or timed out on the mutation.
   * **Evaluated Mechanism:** `Station2EffectReconciler` never trusts agent self-reports; it queries `TargetStatusClient` under a strict `ProbeBudget`. The `v1.1` `AntiSpecGamingReconciler` directly cross-checks `agent_self_report` against `target_state` (`NOT_FOUND`, `ROLLED_BACK`, `TIMEOUT`), overriding false positive self-reports to `REFUTED` or `EFFECT_INDETERMINATE` and recording `spec_gaming_alerts`.

4. **Signal 4 — Interpretability Crisis (`The Dead Salmons`) $\rightarrow$ Non-Explanatory RFC 8785 JCS Packet Evaluation (`Jcs.canonicalize` / `ForkAndFlushContextBoundary`):**
   * **Observed Problem:** Borrowing from neuroimaging's "dead salmon" multiple-comparisons lesson, post-hoc interpretability probes and natural-language justifications can produce plausible-sounding rationales for unauthorized actions.
   * **Evaluated Mechanism:** AEIB treats agent explanations as non-authoritative metadata. `Jcs.canonicalize` and `ForkAndFlushContextBoundary.evaluate_boolean_standing` evaluate admissibility strictly as a deterministic function of canonical RFC 8785 wire bytes, ensuring that persuasive prose cannot alter the boolean standing verdict.

5. **Signal 5 — Memory Staleness (`Cognitive Governance`) $\rightarrow$ `v1.1 TemporalMemoryDigest` (`STALE_DONT_TRUST_YET` State Decay):**
   * **Observed Problem:** Cached RAG context or long-term agent memory decays as external facts and security policies evolve across turns.
   * **Evaluated Mechanism:** While `v1.0.0-rc.1` enforces `proposedEpoch == currentEpoch` in `Station1DispatchInterlock` and scopes out retrieval provenance, the `v1.1` `TemporalMemoryDigest` prototype cryptographically binds `(contextCaid, sourceEpoch, policyEpoch)` via RFC 8785 JCS + SHA-256. Any drift between bound and active epochs transitions the digest state to `STALE_DONT_TRUST_YET` and halts dispatch via `GovernanceHaltError`.

6. **Signal 6 — Wire Enforcement (`eBPF/LSM Profile`) $\rightarrow$ `scripts/verify_bpf_lsm_lock.py`:**
   * **Observed Problem:** In-process middleware can be bypassed if untrusted native code executes direct socket syscalls or loads rogue eBPF programs.
   * **Evaluated Mechanism & Scaffolding Boundary (`AGENTS.md` §5):** Code in `ebpf/` and `src/hardware_attestation.rs` is documented strictly as **structural scaffolding** unless loaded on a locked Linux CVM kernel with active BPF-LSM enforcement. `scripts/verify_bpf_lsm_lock.py` provides a 4-axis diagnostic probe (LSM/lockdown sysfs inspection, negative `bpf(BPF_PROG_LOAD)` syscall rejection `-EPERM`/`-EACCES`, pinned `/sys/fs/bpf` maps, and TDX/SEV-SNP/TPM PCR 11 device presence) that reports observed host kernel state without simulating enforcement on non-Linux or unlocked hosts.

7. **Signal 7 — Verification & Red-Teaming (`AI Goat 2.0` & `AnyJev`) $\rightarrow$ `TypedOwaspPreDispatchGate`:**
   * **Observed Problem:** Agent red-teaming suites demonstrate that adversarial inputs routinely trigger SSRF, dot-segment path traversal (`../`), and numeric boundary overflows in downstream tool adapters.
   * **Evaluated Mechanism:** `TypedOwaspPreDispatchGate` enforces a deterministic pre-dispatch contract—verifying URI scheme and host allowlists, inspecting both raw and URL-unquoted paths/payloads for `..` traversal sequences, and rejecting boolean-as-number or out-of-range numeric parameters—prior to minting an Ed25519 `ExecutionTicket`.

8. **Signal 8 — Epistemic Integrity (`The Klaritee Contrast`) $\rightarrow$ Offline-Verifiable Receipts (`ReceiptVerifier`) & Bounded Claims (`CLAIMS_EVIDENCE.md`):**
   * **Observed Problem:** Security posture degrades when systems rely on unsubstantiated claims of absolute security instead of reproducible, falsifiable verification tools.
   * **Evaluated Mechanism:** AEIB pairs its standalone offline verifier (`ReceiptVerifier` / `VerifierCli`, enforcing exit codes `0`, `1`, `2`, `3`, `4` over bounded inputs) with `CLAIMS_EVIDENCE.md`, explicitly documenting what AEIB does and does not claim under the stated model.

9. **Signal 9 — Implementation Gap (`GIRAI & WEF Reports`) $\rightarrow$ Ed25519-Signed `ContinuityReceipt` Hash Chains (`Station3ContinuousLedger`):**
   * **Observed Problem:** Global governance reports highlight a persistent gap between high-level policy checklists and verifiable runtime execution evidence.
   * **Evaluated Mechanism:** `Station3ContinuousLedger` bridges policy to runtime state by chaining every `LifecycleEvent` into `currentHashChainTip` via SHA-256 and signing the RFC 8785 canonical `ContinuityReceipt` statement with Ed25519 (`Ed25519ProofEngine`), extended in `v1.1` by `LicitraMmrLedger` ($O(\log n)$ inclusion proofs) and `LicitraSentryProxyGate` (`PRE_DISPATCH_COMMITTED` Write-Before-Execute).

10. **Signal 10 — Post-Dispatch Wire Settlement (`AEIB Core`) $\rightarrow$ `EFFECT_INDETERMINATE` Terminal Latching & Cross-Language Verification (`jvm_native_diff_engine.py`):**
    * **Observed Problem:** Distributed tool execution across unreliable networks produces ambiguous post-dispatch states when a connection drops after bytes leave the socket.
    * **Evaluated Mechanism:** Rather than permitting blind retries or silent failure, AEIB represents transport ambiguity as `EffectDisposition.INDETERMINATE` (`EFFECT_INDETERMINATE` / `DISPATCHED_UNCONFIRMED`), bounds reconciliation via `Station2EffectReconciler`, and verifies receipt determinism across Java 21 and Python 3 reference implementations via `benchmarks/jvm_native_diff_engine.py` (confirming `0 B` canonical JCS divergence across canonical test vectors).

---

## 5. The 7 Atomic Boundaries $\rightarrow$ 4-Station Mapping & 7-Milestone Marathon

### 5.1 Mapping the 7 Atomic Boundaries to Stations 0–3

| Station | Atomic Boundaries Enforced | Verified `v1.0.0-rc.1` Symbols | `v1.1` Prototype Extensions (`unified_governance_stack.py`) |
| :--- | :--- | :--- | :--- |
| **Station 0: Manifest Gate** | **(1) Provenance + (2) Intent** | `Station0AdmissionGate`, `Jcs.canonicalize` (`CAID`) | `CredentialVaultGate`, `TypedOwaspPreDispatchGate` |
| **Station 1: Dispatch Interlock** | **(3) Authority + (4) Standing** | `Station1DispatchInterlock` ($\text{GrantValid} \land \text{EpochFresh} \land \text{CAIDMatch} \land \text{ControlHealthy}$) | `ForkAndFlushContextBoundary`, `TemporalMemoryDigest`, `PAD016HeartbeatChain` |
| **Station 2: Effect Reconciler** | **(5) Enforcement + (6) Effect** | `Station2EffectReconciler`, `ProbeBudget`, `EffectDisposition.EFFECT_INDETERMINATE` | `LicitraSentryProxyGate`, `AntiSpecGamingReconciler`, `MerkleAntiEntropyReconciler` |
| **Station 3: Continuous Ledger** | **(7) Evidence** | `Station3ContinuousLedger`, `Ed25519ProofEngine`, `ReceiptVerifier` | `LicitraMmrLedger` ($O(\log n)$ MMR proofs), `WitnessedSignedTreeHead` (`v1.2`) |

### 5.2 The 7-Milestone Sequence

$$\text{[M1: The Tag]} \longrightarrow \text{[M2: Reproduction]} \longrightarrow \text{[M3: Real Target]} \longrightarrow \text{[M4: Review]} \longrightarrow \text{[M5: Pilot]} \longrightarrow \text{[M6: Standard]} \longrightarrow \text{[M7: Enterprise]}$$

* **M1 (`v1.0.0-rc.1` Tag & Hosted CI):** Tracked Gradle wrapper, clean JDK 21 test suite (`./gradlew clean test --no-daemon --stacktrace`), cross-language Python 3 receipt verification (`jvm_native_diff_engine.py`), and SLSA v2.1.0 Level 3 provenance (`38130019286`).
* **M2 (Separate-Party Reproduction — Gate 3):** Clean-room container reproduction (`aeib-reproducibility/gate3/docker-compose.yml` under `network_mode: none`) from signed tag `v1.0.0-rc.1` by a separate party.
* **M3–M7:** Real-target fault evaluation, independent security/staff review, Gate 5 observe-only pilot (`GATE5_OBSERVE_ONLY_PILOT_PROTOCOL.md`), receipt specification standardization (`AEIB-RECEIPT-SPEC.md`), and multi-gateway scale-out.

---

## 6. The 4-Theme Synthesis & Multi-Tier `MemoryDigest` Temporal Staleness Specification (`v1.1` Draft)

### 6.1 The 4-Theme Industry Synthesis

| Theme | External Signals | Core Architectural Lesson | AEIB `v1.0.0-rc.1` / `v1.1` Boundary Mapping |
| :--- | :--- | :--- | :--- |
| **Theme 1: Runtime Enforcement & Cryptographic Agility** | `Pryxor` (`GridEx`), `Cyron` (eBPF/LSM), Post-Quantum `ML-DSA-65` | Governing what an agent *does at the moment of execution* requires credential isolation, wire-level interception, and long-horizon signature agility. | `Station0AdmissionGate` + `CredentialVaultGate` (opaque `credential_ref`); `scripts/verify_bpf_lsm_lock.py` (4-axis BPF-LSM probe, documented as structural scaffolding unless loaded on a locked Linux CVM kernel); `Ed25519` + candidate `ML-DSA-65` epoch anchoring. |
| **Theme 2: Cognitive Governance & Memory as a Governance Surface** | `Cognitive Governance`, `Fork-and-Flush`, `The Dead Salmons` | Reasoning context is not fact (`Context != Fact`), explanations are non-identifiable, and cached memory decays as upstream facts or policies change. | `Station1DispatchInterlock` + `ForkAndFlushContextBoundary` (strips `_reasoning`, `chain_of_thought`, `rationale`, `explanation`) + `TemporalMemoryDigest` (`STALE_DONT_TRUST_YET` on epoch drift). |
| **Theme 3: Verification, Red-Teaming & Limits of Model-Internal Trust** | `AI Finds A Way` (26 cases), `AnyJev`, `AI Goat 2.0` | Agents game self-reported proxy metrics and adversarial inputs exploit untyped tool parameters; self-reports cannot substitute for target state. | `Station2EffectReconciler` (`ProbeBudget`) + `AntiSpecGamingReconciler` (target-state reconciliation overriding false `CONFIRMED` reports) + `TypedOwaspPreDispatchGate`. |
| **Theme 4: Macro Governance & The Institutional Execution Gap** | `GIRAI` (35/100 implementation score), `WEF`, `The Klaritee Contrast` | High-level policy frameworks and unsubstantiated claims of absolute security fail without offline-verifiable runtime execution receipts. | `Station3ContinuousLedger` (`ContinuityReceipt`), `ReceiptVerifier` (`VerifierCli`), `CLAIMS_EVIDENCE.md`, and `benchmarks/jvm_native_diff_engine.py`. |

### 6.2 Three-Tier Memory & Standing Isolation (`schemas/aeib-memory-digest-v1.1.schema.json`)

To prevent prompt injection or context drift from corrupting execution authority across multi-turn workflows, the `v1.1` `MemoryDigest` specification draft (`schemas/aeib-memory-digest-v1.1.schema.json` and `TemporalMemoryDigest` in `v1.1-roadmap/unified_governance_stack.py`) isolates state into three distinct tiers evaluated under the pre-dispatch standing predicate ($\text{GrantValid} \land \text{EpochFresh} \land \text{CAIDMatch}$):

1. **`EPHEMERAL_CONTEXT` (Model Reasoning Tier):** Transient chain-of-thought, scratchpad tokens, and natural-language rationales. Stripped at the boundary by `ForkAndFlushContextBoundary` prior to `CAID` derivation.
2. **`WORKSPACE_FACT` (Source State Tier):** Canonicalized retrieval or workspace state bound to `context_caid` and a monotonic `source_epoch`.
3. **`STANDING_GRANT` (Authorization Boundary Tier):** Policy and capability standing bound to a monotonic `policy_epoch` and optional `PAD-016` `heartbeat_pulse_hash`.

#### `MemoryDigest` Canonical Derivation & Temporal Decay State Machine

$$\text{MemoryDigest} = \text{SHA-256}\!\left(\text{JCS}\!\left(\{\texttt{"contextCaid"}: c,\ \texttt{"policyEpoch"}: e_p,\ \texttt{"sourceEpoch"}: e_s\}\right)\right)$$

| Bound Epochs $(e_s, e_p)$ vs. Active Epochs $(e_s^{\text{active}}, e_p^{\text{active}})$ | `status` | `dispatch_admissible` | Runtime Behavior (`TemporalMemoryDigest.assert_fresh_for_dispatch`) |
| :--- | :--- | :--- | :--- |
| $e_s = e_s^{\text{active}} \land e_p = e_p^{\text{active}}$ | `"FRESH"` | `true` | Returns 64-hex `memory_digest`; permits progression to ticket minting. |
| $e_s \neq e_s^{\text{active}}$ *(Upstream fact mutated)* | `"STALE_DONT_TRUST_YET"` | `false` | Raises `GovernanceHaltError`; forces ex-ante source re-verification. |
| $e_p \neq e_p^{\text{active}}$ *(Policy or grant epoch rotated)* | `"STALE_DONT_TRUST_YET"` | `false` | Raises `GovernanceHaltError`; blocks execution under stale standing. |

---

## 7. Open-Source Primitive Composition Matrix ("The Glue") & 11-Item Delivery Scope

> **Positioning Contrast vs. Vendor Middleware (`microsoft/agent-governance-toolkit`):**  
> *"Microsoft AGT governs runtime behavior inside its agent stack. SMAOS adds a portable, independently verifiable evidence boundary and authority chain that survives outside any vendor platform."*

### 7.1 Open-Source Primitive Composition Matrix ("The Glue")

Rather than re-implementing commodity cryptographic, kernel, or regulatory reporting primitives from scratch, SMAOS / AEIB acts as **deterministic architectural glue** that binds established open-source standards into a unified, offline-verifiable governance pipeline:

| Composition Domain | Open-Source Primitive / Standard | SMAOS / AEIB Composition Layer ("The Glue") | Architectural & Regulatory Outcome | Epistemic Boundary (`AGENTS.md`) |
| :--- | :--- | :--- | :--- | :--- |
| **1. Kernel Enforcement** | **Cilium Tetragon & BPF-LSM** (`execve` / `connect` hooks, `TracingPolicy` CRDs) | **Dual-Emission Policy Compiler (`SmaosHclCompiler`)**: Translates declarative `smaos.hcl` policies directly into Tetragon `TracingPolicy` rules (`SIGKILL` on un-cleared socket access) + BPF-LSM map JSON, paired with `scripts/verify_bpf_lsm_lock.py`. | Binds declarative capability grants to kernel-level socket and process execution rules under a single RFC 8785 JCS `artifact_caid`. | **Structural scaffolding (`AGENTS.md` §5)** unless loaded on a locked Linux CVM kernel with active BPF-LSM enforcement. |
| **2. Audit Privacy** | **Salted Field Commitments (Selective Disclosure Prototype)** (`w3c/vc-di-bbs` adjacent) | **Selective Receipt Redactor (`Ed25519BbsSelectiveRedactor` / `src/bbs_plus_redactable.py`)**: Commits salted per-field SHA-256 digests (`urn:ietf:params:scitt:bbs-2023-ed25519-jcs-2026`) signed under an Ed25519 root over RFC 8785 JCS. (Note: Prototype uses salted SHA-256 field commitments, NOT a pairing-friendly W3C BBS cryptosuite). | Enables selective disclosure and redaction of PII (names, IBANs) from audit receipts without invalidating the root signature; does not establish legal compliance with GDPR Art. 17 or official EU AI Act certification. | **Tested prototype** evaluated under deterministic RFC 8785 JCS commitment vectors. |
| **3. DORA Compliance** | **EBA DPM 4.0 ITS 2024/2956 (`dora.json`)** (xBRL-CSV Register of Information taxonomy) | **Automated xBRL-CSV Package Builder (`DoraXbrlCsvPackageBuilder` / `src/dora_annex_ii_prefill.py`)**: Directly auto-maps pinned agent/MCP capability manifests into EBA xBRL-CSV ZIP packages (`META-INF/reportPackage.json`, `reports/report.json`, `parameters.csv`, `RT.01.01.csv`–`RT.01.03.csv`). | Assists technical export for DORA Art. 28 ICT third-party registers while binding the ZIP package to an Ed25519-signed `manifest_signature.json`; does not establish official regulatory validation. | **Tested prototype** generating deterministic EBA DPM 4.0 xBRL-CSV archives. |
| **4. Offline Verification** | **Pure Rust Compiled to WASM** (`wasm-bindgen`, `ed25519-dalek` `verify_strict`, `sha2`) | **Zero-Dependency Static Verifier (`smaos-wasm-verifier/smaos-verify.html` + `smaos-verify.wasm`)**: Embeds compiled Rust/WASM cryptographic verification into a single self-contained HTML artifact (`Content-Security-Policy: connect-src 'none'`). | Executes local drag-and-drop receipt verification (`CAID` re-derivation, hash-chain continuity, and Ed25519 `verify_strict`) in `~400 ms` with **0 npm or cloud calls**. | **Tested local Rust/WASM artifact** verified under air-gapped browser/CLI execution. |
| **5. Diagnostic Wedge** | **`agent-threat-rules` (`ATR-2026-01932`)** & static MCP/IDE configuration schemas | **Local Environment Auditor (`GhostAtrDiagnosticScanner` / `ghost_audit_scanner.py`)**: Audits local developer and agent configurations (`.claude`, `cursor.json`, MCP server manifests) against `ATR-2026-01932` rules (`ATR-001` through `ATR-005`). | Computes the deterministic **CISO Governance Intensity Index (`GII`, `0–100`)** and emits an Ed25519-signed diagnostic posture receipt prior to runtime deployment. | **Tested local static scanner** with zero outbound network calls. |

### 7.2 11-Item Delivery Scope & 5 Moats Ecosystem Mapping

To avoid reinventing commodity components while focusing engineering on the uncertain-transport outcome classification and evidence-binding layer, each item in the **11-Item Delivery Scope** and **5 Moats** maps to audited open-source building blocks and verified local `SovereignNexus` symbols:

| # | Delivery Scope / Moat Item | Existing Open-Source Ecosystem (`GitHub` / Standards) | Local `SovereignNexus` Implementation & Test Symbols | Epistemic Status (`AGENTS.md` Calibration) |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Runtime Admissibility Gate & Wire-Fault Effect Integrity (`Moat 1`)** | `microsoft/agent-governance-toolkit` (in-process middleware contrast); RFC 8785 JCS | `Station0AdmissionGate`, `Station1DispatchInterlock`, `Station2EffectReconciler` (`EffectDisposition.EFFECT_INDETERMINATE`), `LicitraSentryProxyGate` | **Verified in `v1.0.0-rc.1` (`Gate4IntegrationTest`) & `v1.1` prototype** |
| **2** | **Offline WASM Verifier (`smaos-verify.wasm` — `Moat 2`)** | `RustCrypto/signatures` (`ed25519-dalek` `verify_strict`), `RustCrypto/hashes` (`sha2`), `wasm-bindgen`, `serde_json_canonicalizer` | `smaos-wasm-verifier/src/lib.rs` (`verify_receipt_signature`, `compute_jcs_caid`, `derive_action_caid`) + `smaos-wasm-verifier/smaos-verify.html` | **Verified local Rust/WASM crate (zero cloud/npm runtime dependencies)** |
| **3** | **Selective Disclosure Redactable Passports (`Moat 3`)** | `w3c/vc-di-bbs` adjacent selective disclosure paradigms | `Ed25519BbsSelectiveRedactor` (`unified_governance_stack.py`), `src/bbs_plus_redactable.py`, `src/bbs_plus_redactable.rs`, `src/bbs_signer.py` | **Tested prototype (salted SHA-256 field commitments + Ed25519 root over RFC 8785 JCS; not pairing BBS)** |
| **4** | **Candidate Kernel-Boundary Admissibility Policy (`eBPF XDP / BPF-LSM` — `Moat 4a`, Scaffold)** | `cilium/tetragon` (eBPF syscall/network enforcement), `landlock-lsm/landlock`, `yeet-src/agent-lock`, `aya-rs/aya` | `scripts/verify_bpf_lsm_lock.py` (4-axis diagnostic probe), `SmaosHclCompiler` (`TracingPolicy` emission), `ebpf/ebpf_lsm_agent_guard.c`, `ebpf/aeib_sock_filter.c` | **Structural scaffolding (`AGENTS.md` §5) unless loaded on a locked Linux CVM kernel** |
| **5** | **Hardware-Backed Attestation (`Intel TDX / AMD SEV-SNP` — `Moat 4b`)** | `virtee/sev`, `virtee/tdx`, `confidential-containers/trustee` (IETF RATS Verifier/KBS), `microsoft/TEE-Attestation-Verification` | `HardwareAttestationReceiptBinder` (`unified_governance_stack.py`), `src/hardware_attestation.rs`, `scripts/verify_bpf_lsm_lock.py` | **Structural scaffolding (`AGENTS.md` §5) unless executed on CVM enclave hardware** |
| **6** | **DORA Register of Information Export (`RT.01.01–RT.01.03` — `Moat 5`)** | `Arelle/Arelle` (open-source XBRL/xBRL-CSV processor), `FiorLab/dora-article-28-ict-third-party-register`, `cyr-ius/dora-report` | `DoraXbrlCsvPackageBuilder` (`unified_governance_stack.py`), `src/dora_annex_ii_prefill.py`, `tests/test_dora_annex_ii_prefill.py` | **Tested prototype generating EBA DPM 4.0 xBRL-CSV tables + Ed25519 manifest** |
| **7** | **Ghost Configuration Audit (`.claude`, `cursor.json`, MCP manifests)** | `agent-threat-rules` (`ATR-2026-01932`), `invariantlabs-ai/mcp-scan` (`snyk/agent-scan`), GitGuardian pre-commit AI hooks | `GhostAtrDiagnosticScanner` (`unified_governance_stack.py`), `ghost_audit_scanner.py`, `test_ghost_audit_scanner.py`, `TypedOwaspPreDispatchGate` | **Tested local static scanner (`GII` score) & pre-dispatch SSRF/traversal gate** |
| **8** | **STAR Protocol CLI & AST Baseline (Merkle-DAG Code Freeze)** | Python `ast` stdlib, `tree-sitter`, `intoto/in-toto` (supply-chain layout attestations) | `StarAstMerkleDagBaseline` (`unified_governance_stack.py`) — normalized `ast.dump` leaf digests + Merkle-DAG root + Ed25519 receipt | **Tested prototype ($O(1)$ Merkle root verification in `<1 ms`)** |
| **9** | **Declarative Governance DSL (`smaos.hcl`)** | HashiCorp HCL / Open Policy Agent (`open-policy-agent/opa`), `cilium/tetragon` `TracingPolicy` CRDs | `SmaosHclCompiler` (`unified_governance_stack.py`) compiling `policy "<name>"` blocks into Tetragon `TracingPolicy` + BPF map JSON + SCITT Action Capsule profiles | **Tested prototype compiler with RFC 8785 JCS `artifact_caid` binding** |
| **10** | **Copy-on-Write (CoW) Subgraph Sandboxing** | `tursodatabase/agentfs` (SQLite-backed CoW agent filesystem), `multikernel/branchfs` (FUSE atomic speculative branches), Linux `OverlayFS` | `CoWSubgraphSandbox` (`unified_governance_stack.py`) — SQLite `committed_state` + `branch_overlay` promoting only on `CONFIRMED` | **Tested prototype (atomically discards branch overlay on `EFFECT_INDETERMINATE`)** |
| **11** | **Blinded Compliance Proofs (`0%` Overclaim Rate)** | `succinctlabs/sp1` (Rust zkVM), `risc0/risc0` (RISC-V zkVM), `arkworks-rs`, `zcash/halo2` | `ZeroOverclaimComplianceProver` (`unified_governance_stack.py`) — finite-field R1CS verification ($A w \circ B w = C w \pmod p$) + salted SHA-256 commitments + Ed25519 journal | **Tested R1CS constraint-checking prototype (proves `overclaim_count == 0` without raw payloads; not a full ZK construction)** |

---

## 8. Post-v1.0 Roadmap Backlog — `v1.1` Scope Specifications

> **Freeze & Separation Discipline:**  
> To preserve the verification boundary of `v1.0.0-rc.1`, the five architectural extensions below are explicitly isolated to the **Post-v1.0 Roadmap Backlog (`v1.1` Scope)** and implemented as testable reference prototypes in `v1.1-roadmap/unified_governance_stack.py` (`v1.1-roadmap/test_unified_governance_stack.py`).

### 8.1 Station 1 5-Term Authorization Admissibility (`Station1FiveTermAdmissibilityGate`)

In `v1.0.0-rc.1`, `Station1DispatchInterlock` evaluates standing over grant validity, single-epoch equality, `CAID` matching, and control health. For `v1.1`, Station 1 expands into a strict **5-term conjunctive admissibility predicate** that separates policy epoch freshness from upstream source epoch freshness and enforces quantitative risk-profile envelopes prior to ticket minting:

$$\text{AuthorizationAdmissibility} = \text{GrantValid} \land \text{PolicyEpochFresh} \land \text{SourceEpochFresh} \land \text{ControlHealthy} \land \text{RiskProfileWithinGrantLimits}$$

* **Term 1 (`GrantValid`):** The capability identifier is present in the pinned grant, the grant is non-expired, and the RFC 8785 JCS `CAID` matches the bound candidate action.
* **Term 2 (`PolicyEpochFresh`):** The candidate action's bound `policy_epoch` equals the active `policy_epoch` ($e_p = e_p^{\text{active}}$).
* **Term 3 (`SourceEpochFresh`):** The candidate action's bound `source_epoch` equals the active `source_epoch` ($e_s = e_s^{\text{active}}$), preventing execution on stale workspace/retrieval state.
* **Term 4 (`ControlHealthy`):** The runtime control plane reports healthy telemetry and heartbeat standing (`PAD-016` pulse continuity and non-exhausted probe budgets).
* **Term 5 (`RiskProfileWithinGrantLimits`):** The action's quantitative risk score and notional impact stay within the grant's ceiling ($\text{risk\_score} \le \text{max\_risk\_score} \land \text{notional\_amount} \le \text{max\_notional\_amount}$).
* **Fail-Closed Behavior:** If any of the five terms evaluates to `false`, `Station1FiveTermAdmissibilityGate` halts execution (`GovernanceHaltError`) and records the exact failing conjuncts in the canonical audit trace.

### 8.2 Tripartite Memory Admissibility at the ~16k-Token KV Block Unit (`TripartiteKvBlockAdmissibilityGate`)

Rather than evaluating long-horizon agent memory at whole-conversation granularity—where a single poisoned turn invalidates the entire context or slips through coarse checksums—`v1.1` defines **Tripartite Memory Admissibility** at the **$\le 16,384$-token Key-Value (KV) block unit** (`MAX_KV_BLOCK_TOKENS = 16384`):

$$\text{MemoryAdmissible} = \text{BlockIntegrityValid} \land \text{ProvenanceValid} \land \text{EpochFresh} \land \text{GrantScopeValid}$$

* **Tripartite Tier Isolation:** Every KV block is classified into one of three tiers (`EPHEMERAL_CONTEXT`, `WORKSPACE_FACT`, `STANDING_GRANT`), where `EPHEMERAL_CONTEXT` blocks are never admissible for direct state restoration without promotion through a verified fact/grant boundary.
* **4-Term Block Predicate (`TripartiteKvBlockAdmissibilityGate`):**
  1. `BlockIntegrityValid`: $\text{token\_count} \in (0, 16384]$ and the recomputed RFC 8785 JCS block digest matches `kv_state_sha256`.
  2. `ProvenanceValid`: The block carries an Ed25519 provenance signature from a trusted issuer or anchors to a verified `ContinuityReceipt` hash-chain tip.
  3. `EpochFresh`: Both `(source_epoch, policy_epoch)` bound into the KV block header match the currently active `(active_source_epoch, active_policy_epoch)`.
  4. `GrantScopeValid`: The block's `grant_scope` is authorized for the target capability requesting KV cache restoration.

### 8.3 OpenTelemetry Correlation (`draft-palanisamy-scitt-aac-otel-00` — `ScittOtelActionCapsuleCorrelator`)

To bridge distributed observability traces with tamper-evident receipt attribution without introducing network egress into the core verifier, `v1.1` implements the `draft-palanisamy-scitt-aac-otel-00` mapping via `ScittOtelActionCapsuleCorrelator`:

* **Namespace & W3C Trace Context Binding:** Projects `org.agentactioncapsule.otel` attributes—specifically the 128-bit `trace_id` (32 lowercase hex characters), 64-bit `span_id` (16 lowercase hex characters), `trace_flags`, and W3C `traceparent` (`00-<trace_id>-<span_id>-<flags>`)—directly into the RFC 8785 canonical statement of the `ContinuityReceipt` chain.
* **Bidirectional Auditability:** Allows an SRE or auditor inspecting an OpenTelemetry span (`aeib.caid`, `aeib.disposition`, `aeib.chain_tip`) to locate the exact Ed25519-signed `ContinuityReceipt`, and conversely enables an offline receipt verifier to verify that the telemetry span identifiers were cryptographically bound at execution time.

### 8.4 Hardware Attestation Binding (`Intel TDX / AMD SEV-SNP` — `HardwareAttestationReceiptBinder`)

For deployments targeting Confidential Virtual Machines (CVMs), `v1.1` specifies `HardwareAttestationReceiptBinder` to bind hardware enclave quotes (formatted for Tinfoil / VirTEE / IETF RATS verifiers) into the `ContinuityReceipt` envelope:

* **Cryptographic Quote-to-Receipt Binding:** Computes `report_data_binding = SHA-256(JCS({receipt_caid, chain_tip, nonce}))` (64 bytes / 512 bits matching the Intel TDX v4 `TDREPORT` and AMD SEV-SNP `ATTESTATION_REPORT` `report_data` field width) and embeds the attestation quote digest, measurement register (`MRTD` / `RTMR` or `LAUNCH_DIGEST`), and `evidence_class` into the signed receipt.
* **Strict Epistemic & Scaffolding Calibration (`AGENTS.md` §5):** In accordance with `AGENTS.md` §5, when executed outside physical Intel TDX (`/dev/tdx_guest`) or AMD SEV-SNP (`/dev/sev-guest`) CVM hardware, `HardwareAttestationReceiptBinder` explicitly marks `evidence_class = "STRUCTURAL_SCAFFOLDING"` and `hardware_enforced = false`. It never claims live hardware enclave isolation on standard host kernels.

### 8.5 Blinded Compliance Constraint Checker (R1CS Prototype — `ZeroOverclaimComplianceProver`)

To demonstrate algebraic verification of an episode batch without disclosing raw payloads, `v1.1` implements a finite-field Rank-1 Constraint System (R1CS) constraint-checking prototype in `ZeroOverclaimComplianceProver` (note: this verifies constraint satisfaction over field $\mathbb{F}_p$; it is a constraint-checking prototype, not a complete zero-knowledge proving system):

* **Boolean Overclaim Constraint per Episode $i$:** For each episode $i \in \{1, \dots, N\}$, let $c_i \in \{0, 1\}$ denote whether the agent claimed `CONFIRMED` completion and $v_i \in \{0, 1\}$ denote whether `Station2EffectReconciler` independently verified the target mutation (`CONFIRMED` with valid Ed25519 receipt). An overclaim occurs if and only if $c_i = 1 \land v_i = 0$.
* **Finite-Field R1CS Algebra ($\mathbb{F}_p$, $p = 2^{127} - 1$):** The prover constructs witness vector $w$ over prime field $\mathbb{F}_p$ and enforces the bilinear R1CS gate equation:
  $$A w \circ B w = C w \pmod p$$
  encoding three constraint families across all episodes:
  1. **Booleanity of $c_i$:** $c_i \cdot (1 - c_i) = 0 \pmod p$
  2. **Booleanity of $v_i$:** $v_i \cdot (1 - v_i) = 0 \pmod p$
  3. **Zero-Overclaim Orthogonality:** $c_i \cdot (1 - v_i) = 0 \pmod p$
* **Verifier Contract:** Any episode with $c_i = 1 \land v_i = 0$ violates constraint $c_i \cdot (1 - v_i) = 0$ ($1 \cdot 1 = 1 \neq 0 \pmod p$), causing `ZeroOverclaimComplianceProver` and `verify_proof()` to reject the batch fail-closed. The resulting proof binds the R1CS satisfaction digest, salted episode commitment Merkle root, and `overclaim_rate == 0.0` into an Ed25519-signed public journal.

---

## 9. Policy-Driven Signal Activation & Signed Deployment Profile Contract (`SignedDeploymentProfileGate`)

> **Core Invariant:**  
> *Policy selects signals. Configuration binds them to action classes. The boundary evaluates before dispatch. The target performs the action. The boundary records evidence. The agent cannot alter its own authority.*

### 9.1 Baseline & Signal Activation Rules
The `v1.0` baseline provides the core dispatch-boundary primitives. A signed `DeploymentProfile` (`SignedDeploymentProfileGate` in [`unified_governance_stack.py`](unified_governance_stack.py)) determines which checks apply to which action classes, and the resulting configuration (`profileCaid = SHA-256(JCS(profile))` and `enabledSignals`) is recorded in receipts:

* **Signal 10 (`EFFECT_INDETERMINATE` reconciliation):** Enabled for **state-mutating** external dispatches (`state_mutating_http`, `state_mutating_mcp`) where transport ambiguity could leave the external effect unknown. Not applied to pure read-only calls (`read_only_query`) unless the deployment policy explicitly requires effect confirmation. `EFFECT_INDETERMINATE` is a state classification produced when an enabled mutating dispatch experiences an ambiguous transport outcome (`HTTP_504`, `TCP_RST`, `TIMEOUT`, `UNREADABLE_RESPONSE`), latching `retry_safe = false`.
* **Signals 8–9 (Receipt chain and offline verifier):** Enabled when the deployment profile requires operation-bound, offline-verifiable evidence (`receipt_chain_and_verifier: true`).
* **BPF-LSM Diagnostic & Hardware Attestation:** **Off by default** (`bpf_lsm_diagnostic: false`, `hardware_attestation: false`); structural scaffolding/diagnostic only in `v1.0`.

### 9.2 Policy-Driven Python Configuration Pattern
Importing governance classes does not by itself activate enforcement; the runtime evaluates an operator-signed profile before dispatch while the agent supplies only a `CandidateAction`:

```python
from v1_1_roadmap.unified_governance_stack import SignedDeploymentProfileGate

profile = {
    "action_class": "state_mutating_http",
    "credential_isolation": True,
    "strip_reasoning_fields": True,
    "epoch_freshness": True,
    "indeterminate_reconciliation": True,
    "probe_budget": 1,
    "human_step_up": "out_of_grant_only",
}
# Signed by the operator's Ed25519 policy key before runtime deployment.
# Pre-dispatch evaluation checks:
#   manifest_valid AND grant_valid AND policy_epoch_fresh
#   AND source_epoch_fresh AND control_healthy AND risk_within_grant_limits
```

---

## 10. Formal Ecosystem Integration Contracts (`v1.1` Prototype Implementations)

| Integration Surface | Standards & Research Basis (2025–2026) | Implemented Class (`unified_governance_stack.py`) | Enforced Contract & Failure Behavior |
| :--- | :--- | :--- | :--- |
| **1. NVIDIA Candidate-Action Integration** | NVIDIA NeMo Guardrails (`Execution Rails` & `IORails` tool-call/result structural verification) | [`NvidiaCandidateActionVerifier`](unified_governance_stack.py#L3015-L3125) | Verifies Ed25519-signed rail policy (`allowedRailStates`, `toolSchemas`), enforces strict argument type/key schemas (`int`/`str` with boolean-confusion rejection), fails closed (`CANDIDATE_ACTION_REJECTED`), and binds returned tool results via `tool_call_id` continuity (`IORAILS_RESULT_MISMATCH`). |
| **2. Uber / Enterprise MCP Registry Integration** | Official MCP Registry (`server.json`) + IETF `draft-sharif-mcps-secure-mcp-01` (RFC 8785 JCS + signed tool manifests) | [`UberMcpRegistryGate`](unified_governance_stack.py#L3128-L3225) | Verifies Ed25519 publisher signature over RFC 8785 JCS `server.json`, enforces local SHA-256 `manifestSha256` pinning (`MCP_DIGEST_PIN_MISMATCH`), checks `[issuedAtEpoch, expiresAtEpoch]` freshness (`MCP_MANIFEST_STALE`), and blocks revoked manifest digests or publisher keys (`MCP_MANIFEST_REVOKED`). |
| **3. Cross-App Action `STEP_UP` Escalation** | `RFC 9470` (OAuth 2.0 Step-Up Authentication Challenge) + OpenID CIBA + WebAuthn action-bound commitments | [`CrossAppStepUpEscalationGate`](unified_governance_stack.py#L3228-L3352) | Verifies hardware-backed human approver signature over `(actionCaid, sourceApp, targetApp, acrLevel, challengeNonce, expiresAtEpoch)`, enforces timeout window (`STEP_UP_TIMEOUT`), burns single-use `challengeNonce` against replay (`STEP_UP_REPLAY_BLOCKED`), and emits signed `STEP_UP_AUDIT_RECEIPT`. |
| **4. `iFixAi` & OWASP AIBOM Formal Mappings** | OWASP AIBOM Initiative + CycloneDX v1.6 (`ECMA-424` `machine-learning-model` / `mcp-server`) + OWASP Agentic Top 10 (`ASI01`–`ASI10`) | [`OwaspAibomAndIFixAiContractGate`](unified_governance_stack.py#L3355-L3450) | Validates CycloneDX 1.6 AIBOM schema (`bomFormat == "CycloneDX"`, `specVersion == "1.6"`), requires 64-hex SHA-256 digests on all model and MCP components (`AIBOM_UNPINNED_COMPONENT`), verifies zero failing `iFixAi` behavioral cases across `ASI01`–`ASI06`, and mints a signed `CI_CONTRACT_VERIFIED` admission receipt. |

---

## 11. External Landscape Context & Harness Anatomy Teardowns (MIT, OECD, Marques)

* **MIT AI Risk Initiative (Broad Landscape Context):** Expert-elicitation risk taxonomy covering catastrophic and societal concerns. Provides general risk background only; does **not** evaluate AEIB, specify runtime controls, or establish that AEIB mitigates listed risks. Strictly excluded from capability claims.
* **OECD Artificial Intelligence Papers No. 65 (Practitioner-Acknowledged Gap):** Empirical observation across sectors confirming agentic AI is in production while governance, oversight, and accountability frameworks remain immature. Documents that the governance gap is real, urgent, and practitioner-acknowledged at an intergovernmental level; describes the **problem space**; does **not** endorse or specify AEIB as the solution.
* **David Marques — Agent Harness Anatomy (Architectural Reference):** Source-grounded, commit-linked teardown of 9 production agent harnesses (`pi`, `aider`, `Cline`, `Goose`, `Codex CLI`, `OpenHands`, `OpenCode`, `Hermes`, `OpenClaw`). Validates the **"harness is where the design lives"** principle. Provides concrete reference implementations for studying approval-gate placement, turn loops, and state isolation—informing AEIB’s `v1.1` Gateway Adapter research (with Codex CLI and OpenHands as primary approval-gate analogues).
* **Buyer-Safe Boundary Formulation:**
  > *These artifacts provide context and design references. The OECD report documents practitioner-recognized governance needs; the harness teardowns offer source-grounded architectural comparisons across 9 production harnesses; the MIT report provides broad risk taxonomy. None validates AEIB, establishes market demand for AEIB, or changes the `v1.0.0-rc.3` scope.*
* **Frozen Release Baseline Invariant:**
  ```text
  The evidence remains the work: hosted CI, reproducible artifacts, 
  verifier vectors, benchmark evidence, and separate-party Gate 5 reproduction.
  ```

---

## 12. 2025–2026 Industry, Standards & GitHub Benchmark Synthesis

A systematic review of standards tracks, open-source repositories, and industry deployments across 2025–2026 demonstrates clear convergence on runtime execution governance:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                      2025–2026 AGENT EXECUTION GOVERNANCE LANDSCAPE                      │
├──────────────────────────┬───────────────────────────────────────┬──────────────────────┤
│ ECOSYSTEM LAYER          │ STANDARDS & OPEN-SOURCE BENCHMARKS    │ CORE MECHANISM       │
├──────────────────────────┼───────────────────────────────────────┼──────────────────────┤
│ 1. Agent Audit Trails    │ • draft-sharif-agent-audit-trail-01   │ RFC 8785 + Ed25519   │
│    & Rule Provenance     │ • draft-piehl-agent-rule-provenance-00│ hash-chained logs,   │
│                          │ • AAT Standard Specification          │ rule version pinning │
├──────────────────────────┼───────────────────────────────────────┼──────────────────────┤
│ 2. Pre-Dispatch Gates    │ • UC Berkeley SCGAgent                │ Pre-access checks,   │
│    & Authority Contracts │ • NVIDIA NeMo Guardrails (IORails)    │ tool schema pinning, │
│                          │ • OpenA2A / NHIM Mutual Trust (MTC)   │ candidate validation │
├──────────────────────────┼───────────────────────────────────────┼──────────────────────┤
│ 3. Wire Settlement &     │ • draft-ietf-httpapi-idempotency-key  │ Transport latching,  │
│    Ambiguity Latching    │ • Temporal / Restate Durable Execution│ single-probe budget, │
│                          │ • AEIB 4-Arm Benchmark Harness        │ no blind retries     │
├──────────────────────────┼───────────────────────────────────────┼──────────────────────┤
│ 4. Verifier Portability  │ • IETF draft-ietf-scitt-architecture  │ Multi-language JCS,  │
│    & Scalable Ledgers    │ • LICITRA-MMR (Merkle Mountain Range) │ O(log N) proofs,     │
│                          │ • Wasm air-gapped client verifiers    │ zero-egress audits   │
└──────────────────────────┴───────────────────────────────────────┴──────────────────────┘
```

### 12.1 Detailed Standards Track Analysis

1. **IETF Agent Audit Trail (`draft-sharif-agent-audit-trail`):**
   * Establishes a standard JSON-based audit trail format specifically for autonomous agent tool invocations and delegations.
   * Specifies deterministic **SHA-256 hash chaining** over **RFC 8785 JCS canonical bytes**, paired with Ed25519/ECDSA digital signatures.
   * Features privacy-conscious input/output redaction and tombstoning to reconcile tamper-evident audit logging with GDPR Article 17 (*Right to Erasure*).
2. **IETF Rule Provenance (`draft-piehl-agent-rule-provenance`):**
   * Solves the *"What rules were active when the model acted?"* dilemma.
   * Requires binding decisions explicitly to the versioned rule set, authorizer identity, and active epoch timestamp, preventing retroactive policy justification.
3. **IETF SCITT (`draft-ietf-scitt-architecture` & `draft-ietf-scitt-receipts`):**
   * Decouples the **Issuer** (the runtime gateway generating execution receipts) from the **Transparency Service** (the distributed ledger anchoring checkpoints).
   * Validates AEIB's architectural decision to keep Station 3 receipt minting local, zero-I/O, and air-gapped, while supporting optional asynchronous transparency log anchoring.
4. **IETF Idempotency-Key (`draft-ietf-httpapi-idempotency-key-header`):**
   * Formalizes client-driven idempotency headers (`Idempotency-Key`) for non-idempotent HTTP methods (`POST`, `PATCH`), standardizing how servers detect and reconcile duplicate requests.
5. **OpenA2A & Non-Human Identity Management (NHIM):**
   * Under the Linux Foundation, OpenA2A establishes **Agent Cards** with cryptographic Ed25519 keypairs and Mutual Trust Contracts (MTC) to prevent unauthorized lateral agent-to-agent delegation.
6. **LICITRA-MMR (Merkle Mountain Range):**
   * Implements append-only logarithmic accumulator trees for high-throughput execution ledgers, enabling $\mathcal{O}(\log N)$ inclusion proofs without requiring verifiers to traverse linear historical chains.

---

## 13. The "What We Missed" Strategic Gap Audit (5 Next-Generation Enhancements)

Comparing the current AEIB `v1.0.0-rc.3` frozen baseline against emerging 2025–2026 industry best practices reveals five high-value architectural enhancements for `v1.1`:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        THE 5 ARCHITECTURAL BLIND SPOTS AUDIT                           │
├──────────────────────────────┬─────────────────────────────────────────────────────────┤
│ 1. Pre-Dispatch Intent (EO-1)│ Current: Post-fault receipt minting                     │
│                              │ Gap: Durable DISPATCH_INTENT append before socket write │
├──────────────────────────────┼─────────────────────────────────────────────────────────┤
│ 2. Formal Rule Provenance    │ Current: profileCaid & policyEpoch in receipt           │
│                              │ Gap: (ruleId, ruleVersion, approverPubkey, ruleDigest)  │
├──────────────────────────────┼─────────────────────────────────────────────────────────┤
│ 3. Logarithmic Scaling (MMR) │ Current: Linear O(N) hash chain (Station 3)             │
│                              │ Gap: O(log N) Merkle Mountain Range inclusion proofs    │
├──────────────────────────────┼─────────────────────────────────────────────────────────┤
│ 4. Decoupled Notarization    │ Current: Caller-supplied local public key verification  │
│                              │ Gap: Asynchronous RFC 3161 TSA / SCITT log anchoring    │
├──────────────────────────────┼─────────────────────────────────────────────────────────┤
│ 5. Universal Gateway Adapter │ Current: In-process interceptors                        │
│                              │ Gap: Drop-in reverse proxy wrapping arbitrary harnesses │
└──────────────────────────────┴─────────────────────────────────────────────────────────┘
```

### Gap 1: Strict `EO-1` Pre-Dispatch Intent Staging (*Evidence-Before-Effect*)
* **The Blind Spot:** In `v1.0.0-rc.3`, the `ContinuityReceipt` is generated *after* dispatch and reconciliation (`EventPhase.RECONCILED`). If the host experiences a power failure, SIGKILL, or hypervisor crash while the socket write is executing, external state may have mutated without an on-disk record of the dispatched intent.
* **The v1.1 Enhancement:** Implement two-phase ledger progression:
  1. `EventPhase.DISPATCH_INTENT`: Written and flushed to disk (`fsync`) *before* the socket write begins.
  2. `EventPhase.RECONCILED`: Appended after wire return or reconciliation probe.
  * *Result:* Crash-consistent lineage under crash-fault models.

### Gap 2: Explicit Rule Provenance Binding (`draft-piehl-agent-rule-provenance`)
* **The Blind Spot:** `v1.0.0-rc.3` binds `profileCaid` and `policyEpoch`. However, auditors often demand forensic traceability to the human or security committee that approved specific policy clauses.
* **The v1.1 Enhancement:** Bind `RuleProvenance(ruleId, ruleVersion, approvedByPubkey, activeEpoch, clauseDigest)` into the pre-dispatch ticket and receipt statement, establishing mathematical non-repudiation of governing rules.

### Gap 3: Sub-Linear $\mathcal{O}(\log N)$ Proofs via Merkle Mountain Range (`LICITRA-MMR`)
* **The Blind Spot:** Linear hash chains (`chainTip = SHA-256(prevTip || eventBytes)`) require verifying $N$ sequential entries to prove that event $k$ was included. At $10^6$ actions, proof sizes and verification times grow linearly.
* **The v1.1 Enhancement:** Upgrade Station 3's backend accumulator to an append-only Merkle Mountain Range (MMR). Inclusion proofs scale to $\mathcal{O}(\log N)$ peak-bagged hashes, allowing external auditors to verify individual turns in microseconds without reading historical data.

### Gap 4: Asynchronous Transparency Service Notarization (IETF SCITT Profile)
* **The Blind Spot:** A local signing key can detect post-hoc modification, but an attacker with root access and possession of the private key could theoretically forge a split history (fork attack) if there are no external observers.
* **The v1.1 Enhancement:** Implement an asynchronous background witness thread (`WitnessedSthValidator`) that registers epoch roots with RFC 3161 Time Stamping Authorities or IETF SCITT transparency logs without blocking hot-path dispatches.

### Gap 5: Universal Gateway Adapter for Heterogeneous Agent Harnesses
* **The Blind Spot:** Integrating AEIB into diverse agent frameworks (Claude Code, OpenHands, Codex CLI, LangGraph, CrewAI) currently requires application-specific middleware hooks.
* **The v1.1 Enhancement:** Build a lightweight, local-loopback proxy (`AeibGatewayAdapter`) that implements standard OpenAI/Anthropic/MCP API formats, transparently intercepting tool dispatches and injecting idempotency keys and receipts out-of-band.

---

## 14. The 5 Defensible Architectural Moats (v1.0 Baseline $\rightarrow$ v1.1 Evolution)

These five pillars define AEIB's distinct position relative to forensic-only logging libraries, prompt guardrails, and cloud IAM platforms:

```text
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                      THE 5 DEFENSIBLE ARCHITECTURAL MOATS                   │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ MOAT 1: PRE-DISPATCH STANDING & WRITE-BEFORE-EXECUTE (EO-1)                 │
 │ • The network socket never opens unless an immutable intent ticket is bound │
 │   to the RFC 8785 JCS CAID, verified, and staged.                           │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ MOAT 2: TRANSPORT AMBIGUITY RESOLUTION & NO BLIND RETRIES                   │
 │ • HTTP 504 / TCP RST latches EFFECT_INDETERMINATE fail-closed.              │
 │ • Automated retries through the governed path are blocked (ProbeBudget: 1). │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ MOAT 3: ZERO-EGRESS MULTI-LANGUAGE VERIFIER PARITY                          │
 │ • Bit-exact parity across Java 21, Python 3, and browser WebAssembly.      │
 │ • Complete offline verifiability without external API or cloud calls.       │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ MOAT 4: APPEND-ONLY RECOVERY LINEAGE & FORENSIC DISCREPANCY ATTRIBUTION     │
 │ • Ambiguous records are never erased or backfilled; recovery actions chain   │
 │   immutably from prior uncertain states with cryptographic lineage.         │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ MOAT 5: MACHINE-VERIFIABLE REGULATORY PROJECTION                            │
 │ • Direct, deterministic translation from operational receipts into official  │
 │   DORA Article 28(3) xBRL-CSV packages and EU AI Act Art. 12/14 logs.       │
 └─────────────────────────────────────────────────────────────────────────────┘
```

1. **Moat 1 — Pre-Dispatch Standing & Write-Before-Execute (`EO-1`):**  
   Prompt guardrails evaluate text *inside* the model; forensic loggers observe events *after* side-effects happen. AEIB enforces a pre-socket authorization interlock where cryptographic proof of authority is a physical prerequisite for network I/O.
2. **Moat 2 — Transport Ambiguity Resolution & Bounded Reconciliation:**  
   When external services time out, ordinary frameworks retry blindly, causing duplicate disbursements or conflicting state. AEIB formally models network uncertainty as `EFFECT_INDETERMINATE`, preventing uncoordinated retries through the governed boundary.
3. **Moat 3 — Zero-Egress Multi-Language Verifier Parity:**  
   Receipts are self-contained cryptographic artifacts verified offline via RFC 8785 JCS and Ed25519. Verifiers in Java, Python, and standalone WebAssembly produce identical verdicts with zero external network dependencies.
4. **Moat 4 — Append-Only Recovery Lineage:**  
   Rather than rewriting history or pretending transactions never occurred, AEIB maintains an immutable record of all dispatches, linking subsequent recovery actions cryptographically to the original uncertain event.
5. **Moat 5 — Machine-Verifiable Regulatory Projection:**  
   Operational receipts map directly to formal compliance formats (such as DORA xBRL-CSV and EU AI Act logging requirements), providing machine-generated evidence for external auditors without relying on generative text summaries.

---

## 15. The 11 Production Coding Harnesses Architecture (arXiv:2609.00006)

Empirical examination of 11 production coding agent harnesses (*Claude Code, Codex CLI, OpenHands, Aider, Pi, OpenClaw*, and related environments) reveals critical structural principles for agent execution engineering:

1. **The "Harness-Over-Model" Shift:**  
   Zero surveyed production harnesses rely on heavyweight orchestrator abstractions (e.g., generic agent DAG frameworks) or vector embeddings for local codebase comprehension. Production systems utilize **hand-rolled asynchronous state loops**, **deterministic lexical search** (`ripgrep`), **concrete AST parsers** (`tree-sitter`), and **explicit, strongly-typed tool-calling contracts**. Model weights are interchangeable commodities; execution authority, safety invariants, and operational boundaries reside exclusively within the harness.
2. **The "Vibe-Compliance" Failure Mode:**  
   Client-side or developer-controlled settings (e.g., local IDE permission toggles, `.claude/settings.json`, `.cursorrules`) function merely as client-side "permission theater." Untrusted agent processes can manipulate environment variables, spawn unmonitored sub-processes, or self-report speculative task completion (`CONFIRMED`). Robust runtime governance demands an **out-of-model, operator-signed policy interlock positioned strictly at the socket boundary**.
3. **Reasoning vs. Wire Payload Contamination:**  
   Frontier reasoning models frequently emit natural-language thoughts (`_reasoning`, `chain_of_thought`, `rationale`) alongside structured tool parameters. If these ephemeral tokens leak into wire dispatches, they alter the RFC 8785 Content-Addressed Action Identifier (`CAID`) and create non-deterministic action hashes. Harnesses must recursively strip non-binding thoughts prior to canonicalization.
4. **The `EO-1` Pre-Dispatch Logging Gap:**  
   Conventional logging architectures emit audit records *after* a tool returns. If a process experiences a kernel crash, SIGKILL, or network socket drop mid-syscall, external systems may commit mutations while the host has zero record of the event. System assurance demands appending an **immutable intent receipt to a local durable ledger before invoking the socket write**.

---

## 16. Open-Source Primitive Composition Matrix ("The Glue Strategy")

Rather than rebuilding commodity components, AEIB composes established open-source and open-standard primitives into a unified, air-gapped, verifiable execution pipeline:

| Domain | Existing Open-Source Standard | AEIB Composition Layer ("The Glue") | Architectural / Regulatory Outcome | Epistemic Status |
| :--- | :--- | :--- | :--- | :--- |
| **Kernel Boundary** | Cilium Tetragon & BPF-LSM (`bpf()`) | `SmaosHclCompiler` (`smaos.hcl`) | Generates Tetragon `TracingPolicy` CRDs (`SIGKILL` on uncleared socket access) and pinned map JSONs. | Structural Scaffolding |
| **Audit Privacy** | W3C BBS+ Cryptosuites (`bbs-2023`) | `Ed25519BbsSelectiveRedactor` | Commits salted per-field SHA-256 digests under Ed25519 root; enables selective PII disclosure (GDPR Art. 17 vs EU AI Act Art. 12). | Tested Prototype |
| **DORA Compliance** | EBA DPM 4.0 (`dora.json`) | `DoraXbrlCsvPackageBuilder` & `smaos_dora_generator.py` | Automatically maps pinned manifests into EBA xBRL-CSV ZIP archives (`RT.01.01`–`RT.05.02`) with zero foreign-key errors. | Tested Prototype |
| **Offline Verification** | Pure Rust (`ed25519-dalek` / WASM) | `smaos_verify.wasm` & `verifier.html` | Drag-and-drop receipt verification in browser (<400 ms) with zero npm or cloud network dependencies (`connect-src 'none'`). | Verified Local Crate |
| **Code Freeze** | Python AST & Tree-sitter | `StarAstMerkleDagBaseline` | Normalizes AST token digests into Merkle-DAG roots for $\mathcal{O}(1)$ verification in <1 ms. | Tested Prototype |
| **Zero-Overclaim Proofs** | Finite-Field R1CS Constraint Systems | `ZeroOverclaimComplianceProver` | Constructs $Aw \circ Bw = Cw \pmod p$ constraints ($p = 2^{127}-1$) to prove 0% unverified completion claims without payload leakage. | Tested Prototype |

---

## 17. Immediate Go-To-Market Execution Protocol (`v1.0.0-rc.3` Baseline)

1. **Lock the `v1.0.0-rc.3` Candidate Baseline:**
   * Verify 1:1 identity alignment across `aeib-native-runtime/build.gradle` (`version = '1.0.0-rc.3'`), workflows (`aeib-verifier-1.0.0-rc.3.jar`), and release branch `release/v1.0-review-candidate`.
   * Confirm green execution across the full test matrix: `142/142` JVM unit tests, `56/56` Python tag tests (commit `7bfd43dc`), `14/14` differential verifier vectors (`0 B` JCS divergence), and `0 / 500` duplicate external writes under HTTP 504 fault injection.
2. **Package Gate 1–4 Verification Artifacts:**
   * Assemble the clean-room verification pack: `bom.json` (CycloneDX 1.6), `multiple.intoto.jsonl` (SLSA v1.1-compatible provenance), `gradle/verification-metadata.xml`, and the `EVIDENCE_MANIFEST.md` negative-test ledger (`NEG-01`–`NEG-08`).
3. **Deploy Gate 5 for External Reproduction:**
   * Distribute the air-gapped `smaos_verify.wasm` binary and `verifier.html` drag-and-drop runner to independent auditors, enterprise risk teams, and sandbox committees (ČAS / ČNB) to initiate separate-party Gate 5 reproduction.

---

## 18. Industry Open-Source Ecosystem Audit & Defensible Moats

### 18.1 Existing Commodity Tools to Leverage (Do Not Re-Invent From Scratch)

A rigorous audit of GitHub, CNCF, and IETF repositories confirms that several foundational primitives already exist with mature codebases and should be composed directly:

1. **Zero-Allocation Policy Evaluation (Station 0 Admission Edge):**
   * **Upstream Primitive:** **AWS Cedar (`cedar-policy` in Rust)** and **Common Expression Language (CEL)**.
   * **Observed Metrics:** Native in-process Cedar evaluation executes single-purpose authorization checks in **5 to 7 microseconds ($\mu\text{s}$)** when warm ($p50 \approx 0.2\text{--}0.6\text{ ms}$ under heavy concurrency), executing 20x to 80x faster than interpreted Rego.
   * **AEIB Integration:** Station 0 uses static AST evaluations via Cedar or compiled CEL predicates before allocating heap memory or calculating RFC 8785 JCS canonical bytes. Non-admissible requests drop in microseconds.
2. **Kernel-Level Socket Interception:**
   * **Upstream Primitive:** **Cilium Tetragon (`TracingPolicy` on `tcp_connect`)** and **Linux BPF-LSM (`BPF_PROG_TYPE_LSM` on `socket_connect`)**.
   * **Observed Metrics:** Hooks directly into kernel TCP connection initialization, synchronously executing `action: Sigkill` or returning `-EPERM` before network packet transmission.
   * **AEIB Integration:** Rather than maintaining proprietary kernel modules, AEIB compiles `smaos.hcl` policies directly into Tetragon CRDs and BPF-LSM maps (documented strictly as structural scaffolding per `AGENTS.md` §5).
3. **Vectorized Parsing & Anti-Parsing Bomb Defenses:**
   * **Upstream Primitive:** **`simdjson` (C++)** and **`simd-json` (Rust)**.
   * **Observed Metrics:** Uses AVX2/NEON vector instructions to produce flat tapes without recursive descent, preventing stack-overflow parsing bombs (`[[[[...]]]]`).
   * **AEIB Integration:** Paired with strict input ceilings (1 MiB max raw payload) and tape token limits to prevent linear tape exhaustion.
4. **Model Context Protocol (MCP) Middleware Layer:**
   * **Upstream Primitive:** **Solo.io `agentgateway`**, **IBM `mcp-context-forge`**, **`pipelock`**, and **`toolhive`**.
   * **AEIB Integration:** Acts as a drop-in middleware proxy intercepting JSON-RPC `tools/call` dispatches to attach AEIB standing evaluation and wire uncertainty latching.
5. **Transparency Ledgers & SCITT Reference:**
   * **Upstream Primitive:** **`microsoft/scitt-ccf-ledger`** and **`scitt-community/scitt-api-emulator`**.
   * **AEIB Integration:** Emits standard IETF COSE_Sign1 envelopes for asynchronous registration into CCF or SCITT emulator endpoints.
6. **Merkle Mountain Range (MMR) Ledgers:**
   * **Upstream Primitive:** **`ckb-merkle-mountain-range`** (Nervos Network audited Rust crate) and **`merkleberg`** (IETF MMRIVER-compliant async Rust crate).
   * **AEIB Integration:** Replaces linear hash-chain traversal with $O(\log N)$ peak-bagged inclusion proofs.

---

### 18.2 The 5 Defensible Moats: What Every Industry Gateway Missed

Every surveyed industry gateway (Solo.io agentgateway, Kong AI Gateway, Envoy AI Gateway, LiteLLM, Portkey, pipelock) treats AI agent interactions as ordinary HTTP RPC traffic. None address the execution finality physics of autonomous agents:

1. **Moat 1: Transport Ambiguity Latching (`EFFECT_INDETERMINATE`):**  
   Ordinary gateways treat HTTP 504 timeouts or TCP RST drops as generic failures and trigger blind exponential retries. If the downstream target committed the mutation before timing out, blind retries cause duplicate charges and corrupted state. AEIB latches `EFFECT_INDETERMINATE` with `retry_safe: false` and enforces the **3 Financial Ambiguity Rules** (UUIDv4 idempotency required, blind retry forbidden, single authenticated primary reconciliation probe required).
2. **Moat 2: Reasoning vs. Wire Payload Isolation (`Dead Salmons`):**  
   Frontier models leak natural-language thoughts (`_reasoning`, `chain_of_thought`) into tool arguments. Standard gateways pass these through, contaminating cryptographic hashes and opening injection vectors. AEIB's [`ForkAndFlushContextBoundary`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/unified_governance_stack.py#L765-L815) recursively strips non-binding thoughts before RFC 8785 JCS canonicalization.
3. **Moat 3: Pre-Dispatch Intent Barrier (`EO-1`):**  
   Standard logging architectures emit telemetry *after* execution. If a process crashes mid-syscall during the socket write, mutations occur with zero local record. AEIB enforces strict `EO-1` (*Evidence-Before-Effect*), writing a signed `DISPATCH_INTENT` ledger record before the socket write syscall begins.
4. **Moat 4: Dual-Epoch Memory Staleness Interlock:**  
   Agents frequently operate on cached RAG documents or tool outputs across turn boundaries after permissions or source policies have changed. AEIB's [`TemporalMemoryDigest`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/unified_governance_stack.py#L860-L895) binds context digests to both `source_epoch` and `policy_epoch`, halting fail-closed on `STALE_DONT_TRUST_YET` upon epoch divergence.
5. **Moat 5: Zero-Vendor-Egress Offline Verification:**  
   Enterprise governance platforms require streaming sensitive logs to third-party SaaS clouds. AEIB enables 100% offline, air-gapped receipt verification via [`smaos_verify.wasm`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/smaos_verify.wasm) running in-browser under `connect-src 'none'`.

---

## 19. MCP Governance Proxy & The Cryptographic Kill Switch Architecture

### 19.1 Protocol Interception vs. Policy & Evidence Boundary

Interception proxies in the Model Context Protocol (MCP) ecosystem (such as `mcp-governed-agents`, Solo.io `agentgateway`, and IBM `mcp-context-forge`) operate at the transport layer, intercepting JSON-RPC `tools/call` invocations. Rebuilding protocol parsers from scratch is an anti-pattern. AEIB explicitly decouples **protocol interception** from **cryptographic standing and evidence evaluation**:

1. **Interception Plane (`AEIB-MCP-Governance-Adapter`):**
   * Drops into the agent-server pipe using the standard stdio / SSE JSON-RPC loop.
   * Intercepts `tools/call` invocations with low observed latency overhead ($p95 \approx 51.8\,\mu\text{s}$ under the stated benchmark harness).
   * Freezes execution via JSON-RPC `Halt` before socket dispatch.
2. **Authorized Principal Binding (APB) & Transparency Invariance (T9.1):**
   * Enforces an out-of-band `AuthorizedPrincipalBinding` signed by the operator principal.
   * Confirms `(principal_id, agent_id, session_id, allowed_tools)` before admitting tool execution.
3. **Station 1 Authority Gate:**
   * Evaluates the single-use `DispatchAuthorizationTicket`, binding target URL, policy epoch, manifest digest, and wire payload `CAID`.
   * Enforces `Authorization: DENY` $\to$ `Execution: NOT_DISPATCHED` on any parameter or digest mismatch.
4. **Station 3 Continuous Evidence Minting:**
   * Emits an Ed25519-signed `ContinuityReceipt` anchoring the execution event to the append-only hash chain before resuming MCP response propagation.

### 19.2 The Three-Tier Kill Switch Taxonomy (AIGP-Σ Alignment)

Analysis of agent safety architectures distinguishes three distinct tiers of execution termination:

| Kill Switch Tier | Operational Mechanism | Trust Model & Failure Vulnerability | Latency Profile | AEIB v1.1 Architectural Implementation |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Remote Orchestrator Termination** | Cloud SaaS control-plane heartbeat / webhook calling agent process termination. | Vulnerable to network partition, DNS poisoning, telemetry evasion, and egress blocking. If agent drops connection, execution may continue unmonitored. | Network-dependent ($50\text{--}500\text{ ms}$). | Explicitly rejected as primary control; treated as advisory supervisory signal only. |
| **Tier 2: Local Process & System Veto** | OS-level signal (`SIGKILL`), container shutdown, or Tetragon BPF-LSM kprobe blocking. | Bound to host OS kernel integrity. Subordinate processes or compromised agents with elevated privileges may attempt signal masking. | Near-instantaneous ($<1\text{ ms}$). | `scripts/verify_bpf_lsm_lock.py` & Tetragon `TracingPolicy` CRDs (evaluated as structural scaffolding per `AGENTS.md` §5). |
| **Tier 3: Cryptographic Threshold Revocation (AIGP-Σ)** | Out-of-band $k$-of-$n$ signed `SignedHaltCommand` verified locally via RFC 8785 JCS without network access. | Zero network dependence. Operates fail-closed even under complete network isolation or compromised cloud orchestrators. Monotonic sequence numbers prevent replay. | Local signature verification ($<200\,\mu\text{s}$ warm). | `AigpSigmaCryptographicKillSwitch` in `v1.1-roadmap/unified_governance_stack.py` (§54). |

### 19.3 Consolidated v1.1 Technical Priority Matrix

| Priority | Component & Roadmap Target | Upstream / Reference Primitive | Technical Invariant & Verification Criteria | Epistemic & Operational Boundary |
| :--- | :--- | :--- | :--- | :--- |
| **P0** | **Decision-to-Dispatch Authority Gate** (`Station0AdmissionGate` / `DecisionToDispatchAuthorityGate`) | AWS Cedar (`cedar-policy`), CEL, RFC 8785 JCS | Single-use ticket burn, TOCTOU action digest match (`sha256:compute_caid(wire_payload)`), `Authorization: DENY` $\to$ `Execution: NOT_DISPATCHED`. | Implemented and evaluated in `unified_governance_stack.py` (§52). |
| **P0** | **MCP Governance Proxy Adapter** (`AeibMcpGovernanceAdapter`) | `mcp-governed-agents` (`github.com/chelof100/mcp-governed-agents`) | JSON-RPC `Halt` $\to$ `APB` check $\to$ Authority Ticket burn $\to$ Station 3 receipt mint $\to$ `Resume`. Observed $p95 \approx 51.8\,\mu\text{s}$ overhead in reference benchmarks. | Implemented and evaluated in `unified_governance_stack.py` (§53). |
| **P0** | **Delegation Attenuation & Scope Subtyping** (`DelegationAttenuationGate`) | Biscuit Tokens, Macaroons, IETF OAuth DPoP | Child agents cannot exceed parent scopes; strict monotonic attenuation; delegation chain cryptographic verification. | Implemented and evaluated in `unified_governance_stack.py` (§51). |
| **P1** | **AIGP-Σ Cryptographic Kill Switch** (`AigpSigmaCryptographicKillSwitch`) | AIGP-Σ Kill Switch Specification, Ed25519 Quorum | Offline $k$-of-$n$ threshold verification; monotonic sequence anti-replay; scoped or wildcard (`ALL`) fail-closed execution freeze. | Implemented and evaluated in `unified_governance_stack.py` (§54). |
| **P1** | **Five-Plane Enforcement Pipeline** (Admission, Dispatch, Effect, Ledger, Attestation) | Cilium Tetragon, JCS Canonicalizer, RFC 8785 | Strict ordering: Station 0 Admission $\to$ Station 1 Dispatch $\to$ Station 2 Effect Reconciliation $\to$ Station 3 Ledger $\to$ Station 4 Attestation. | Tested prototype in `unified_governance_stack.py` (§38–§42). |
| **P2** | **IETF SCITT Agent Profile (AIR) Translator** | `scitt-ccf-ledger`, `COSE_Sign1` (RFC 9052) | Maps AEIB `ContinuityReceipt` instances into RFC 9052 COSE_Sign1 Sig_structure envelopes (protected header, external AAD, payload hash). | Prototype specification candidate for v1.1 (non-conformance notice until cross-implementation tests pass). |
| **P2** | **Zero-Allocation Station 0 CEL Hook** | Google CEL-Rust / `cel-eval` | Sub-microsecond predicate evaluation before memory allocation or JCS canonicalization. | Scaffolding specification candidate for v1.1. |

---

## 20. Five-Plane Runtime Enforcement & MCP CVE Mitigation Matrix

### 20.1 The Five-Plane Runtime Enforcement Architecture

Autonomous agent execution traverses distinct abstraction boundaries. Rather than attempting to enforce all policies at a single ingress filter, AEIB defines a decoupled five-plane mediation pipeline:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        FIVE-PLANE RUNTIME ENFORCEMENT ARCHITECTURE                     │
├──────────────────────────┬─────────────────────────────────────────────────────────────┤
│ PLANE                    │ GOVERNANCE RESPONSIBILITY & MEDIATION                       │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 1. Reasoning Plane       │ Adjudicates task intent, evaluates policy standing, and     │
│                          │ computes single-use dispatch authority.                     │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 2. Network Enforcement   │ Realizes network egress decisions; drops non-allowlisted    │
│    Plane                 │ socket connections at the wire boundary.                    │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 3. Identity Enforcement  │ Enforces credential scoping and principal delegation        │
│    Plane                 │ attenuation across agent-to-agent (A2A) hops.               │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 4. Endpoint Enforcement  │ Enforces process sandboxing, capability manifests, and      │
│    Plane                 │ OS-level execution restrictions.                            │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 5. Data Enforcement      │ Controls data access patterns, purpose-binding checks,      │
│    Plane                 │ and local storage/memory boundaries.                        │
└──────────────────────────┴─────────────────────────────────────────────────────────────┘
```

* **The Stop-Anywhere Principle:** Policy evaluation occurs in the reasoning plane, but enforcement executes in whichever lower plane the candidate action crosses. A violation detected at the reasoning layer triggers an immediate fail-closed drop before wire or system mutation occurs.

### 20.2 MCP CVE Vulnerability Mitigation Matrix

Recent security audits indicate significant vulnerability exposure across production Model Context Protocol (MCP) tool servers. The observed failure modes map directly to AEIB Station 0 and Station 1 wire gates:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        MCP CVE VULNERABILITY MITIGATION MATRIX                         │
├──────────────────────────────┬──────────────────────────────────┬──────────────────────┤
│ VULNERABILITY CLASS          │ INDUSTRY PATTERN                 │ AEIB WIRE GATE FIX   │
├──────────────────────────────┼──────────────────────────────────┼──────────────────────┤
│ 1. Scope Bypass              │ CVE-2026-108586                  │ Station 0 Manifest   │
│                              │ Negated filter authorization     │ Gate drops non-pinned│
│                              │ bypass in tool claims.           │ capability URIs.     │
├──────────────────────────────┼──────────────────────────────────┼──────────────────────┤
│ 2. Session Hijacking         │ CVE-2026-67431                   │ CAID envelope binds  │
│                              │ Session ID not bound to owner;   │ `profileCaid` and    │
│                              │ privilege escalation.            │ `policyEpoch`.       │
├──────────────────────────────┼──────────────────────────────────┼──────────────────────┤
│ 3. SSRF & Credential Theft   │ CVE-2026-54688 / CVE-2026-61559  │ Opaque `grant://`    │
│                              │ Redirect SSRF stealing bearer    │ handles bound to     │
│                              │ tokens via `web_url_read`.       │ `credential_audience`.│
└──────────────────────────────┴──────────────────────────────────┴──────────────────────┘
```

### 20.3 AgentMesh Code Audit: Suzerain vs. Sovereign Mesh

Source code examination of Google AgentMesh (`cmd/sam-node/main.go`, `node.go`) clarifies the technical distinction between a centralized suzerainty mesh and an offline-verifiable execution boundary:

1. **Centralized Lifecycle Binding:** AgentMesh's data plane is peer-to-peer and encrypted, but node registry and operational identity depend on an external control plane. If identity renewal fails or connection to the central router drops for 3 minutes, `node.go` executes `os.Exit(1)` to terminate the node.
2. **The AEIB Contrast:** AEIB is structured as an air-gapped, offline-verifiable boundary. Dispatches emit detached cryptographic receipts (`RFC 8785 JCS + Ed25519` / `COSE_Sign1`), verified offline via standalone binaries or browser-based WebAssembly (`smaos_verify.wasm`, 195 KB) under `connect-src 'none'`, without external telemetry or SaaS control-plane dependencies.

---

## 21. Strategic Boundary Realignment & v1.1 Candidate Backlog

### 21.1 Technical Evaluation of Proposed v1.1 Research Candidates

The analysis of structural limitations in standard agent execution environments identifies three candidate research items for the `v1.1` specification backlog, isolated from the frozen `v1.0.0-rc.3` baseline:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        AEIB v1.1 CANDIDATE SPECIFICATION ROADMAP                       │
├──────────────────────────┬──────────────────────────────────────┬──────────────────────┤
│ CANDIDATE MODULE         │ THREAT / GAP ADDRESSED               │ AEIB v1.1 BOUNDARY   │
├──────────────────────────┼──────────────────────────────────────┼──────────────────────┤
│ 1. Cryptographic         │ "Asserted vs. Verified" Sponsor Gap  │ Evaluates multi-hop  │
│    Delegation Chaining   │ Intermediate sub-agent proxying for  │ AIP attenuation      │
│                          │ privilege escalation.                │ across delegation    │
│                          │                                      │ chains.              │
├──────────────────────────┼──────────────────────────────────────┼──────────────────────┤
│ 2. Intent-Context        │ Intent vs. Data Context Divide       │ Atomic evaluation of │
│    Fusion Gate           │ Approved tool intent containing      │ payload sensitivity  │
│                          │ unredacted PII/PCI payloads.         │ prior to JCS         │
│                          │                                      │ canonicalization.    │
├──────────────────────────┼──────────────────────────────────────┼──────────────────────┤
│ 3. Behavioral Anomaly    │ Insider Risk & Machine-Speed Loops   │ Latches frequency    │
│    Baselines             │ High-velocity micro-actions causing  │ spikes to            │
│                          │ state corruption.                    │ EFFECT_INDETERMINATE │
│                          │                                      │ (retry_safe: false). │
└──────────────────────────┴──────────────────────────────────────┴──────────────────────┘
```

1. **Cryptographic Delegation Chaining (`IETF AIP Alignment`):**
   * *Threat Addressed:* Sub-agent proxying where a low-privilege agent prompts a higher-privilege agent to perform unauthorized actions.
   * *AEIB v1.1 Scope:* Evaluates multi-hop delegation chains with explicit monotonic scope and budget attenuation (`DelegationAttenuationGate`), aligned with the IETF Agent Identity Protocol (`draft-prakash-aip-02`) candidate research.
2. **Intent-Context Fusion Gate:**
   * *Threat Addressed:* Mismatch where approved tool intent encapsulates unredacted confidential data or PII.
   * *AEIB v1.1 Scope:* Candidate specification evaluating action intent and payload data sensitivity as an atomic pre-dispatch decision. Requires native zero-egress DLP implementation, dedicated test suites, and direct AEIB-native benchmarking before any capability or performance assertions are established.
3. **Behavioral Anomaly Baselines:**
   * *Threat Addressed:* Insider risk and automated loops executing high-velocity micro-actions that cause system disturbance.
   * *AEIB v1.1 Scope:* Monitors call frequencies and out-of-window requests. When an anomaly is detected, the runtime routes the request to `EFFECT_INDETERMINATE` (`retry_safe: false`), halting execution and preventing automated retries across the governed boundary.

---

### 21.2 Locked Epistemic Boundaries & Comparative Rules

To maintain strict epistemic hygiene across all code, tests, and documentation:

1. **Google AgentMesh Comparative Boundary:**
   > "Google AgentMesh is relevant adjacent market and architectural context. AEIB addresses a narrower dispatch-boundary concern: pre-dispatch standing evaluation, explicit uncertain-transport classification, bounded operation-specific reconciliation, and operation-bound RFC 8785 + Ed25519 receipts. No compatibility, integration, endorsement, or equivalence with AgentMesh is established."
2. **External MCP Benchmark Reference Rule:**
   External benchmark metrics (such as the observed $p95 \approx 51.8\,\mu\text{s}$ latency for `mcp-governed-agents`) are recognized strictly as external reference measurements. They are not cited as AEIB runtime performance until verified through native AEIB benchmark suites.
3. **Browser Verifier Operational Scope:**
   The browser verifier (`verifier.html` + `smaos_verify.wasm`) verifies supplied receipts against caller-supplied public keys under stated verification procedures; it does not establish ledger completeness, non-repudiation, or target-side execution.
4. **Regulatory Sandbox Prerequisite Gate:**
   Regulatory submission dossiers (including ČAS / ČNB) remain paused until all prerequisite build, manifest reconciliation, and CI verification steps across the release candidate sequence are complete.

---

## 22. SOTA Architectural Directives & Phased Implementation Timeline

### 22.1 The 5 SOTA Architectural Directives (`v1.1` Backlog)

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        AEIB v1.1 SOTA ARCHITECTURAL DIRECTIVES                         │
├──────────────────────────┬─────────────────────────────────────────────────────────────┤
│ MODULE                   │ SOTA DIRECTIVE & FAILURE DEFENSE                            │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 1. MCP Governance        │ • Schema-Aware Stream Interception: Caches tool JSON        │
│    Adapter               │   Schemas and parses JSON-RPC tools/call in-memory.         │
│                          │ • Pins tool_schema_hash; drops mutated/unauthorized calls   │
│                          │   with -32602 error prior to socket transmission.           │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 2. Delegation Chain      │ • Monotonic Scope Attenuation (Macaroons / UCANs):          │
│    Attenuation           │   Appends cryptographically signed caveats across hops.     │
│                          │ • Mathematically restricts child permissions strictly       │
│                          │   narrow; triggers ANSI 86 Lockout on privilege expansion.  │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 3. SCITT AIR Profile     │ • Batched Merkle Anchoring & COSE_Sign1 Envelopes:           │
│    Translator            │   Mints local receipts in µs; flushes Merkle roots async.   │
│                          │ • Maps EFFECT_INDETERMINATE / DISPATCHED_UNCONFIRMED         │
│                          │   1:1 to SCITT pending_confirmation status.                 │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 4. Intent-Context        │ • Two-Tiered Hold-and-Scan AI DLP Architecture:             │
│    Fusion Gate           │   - Tier 1: Zero-allocation O(1) regex/Bloom secret scan.   │
│                          │   - Tier 2: Latches EFFECT_INDETERMINATE (Hold) for local   │
│                          │     zero-egress DSPM scan before releasing to socket.       │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 5. Cryptographic Kill    │ • Threshold Signature (TSS) & Kernel eBPF Enforcement:      │
│    Switch                │   Requires k-of-n signed HALT beacons (e.g., 2-of-3).       │
│                          │   eBPF LSM (sec_task_execve) severs socket paths at Ring 0  │
│                          │   (structural scaffolding per AGENTS.md §5).                │
└──────────────────────────┴─────────────────────────────────────────────────────────────┘
```

### 22.2 The 9 Defensible Capabilities & Testable Claims Framework

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                        AEIB DEFENSIBLE CAPABILITIES                          │
├──────────────────────────────────────────────────────────────────────────────┤
│  1. Exact action-level authorization binding                                 │
│  2. Explicit uncertain-transport classification (EFFECT_INDETERMINATE)       │
│  3. No-blind-retry rule for AEIB-governed mutations (retry_safe: false)      │
│  4. Operation-specific reconciliation evidence                               │
│  5. Bounded probe scheduling (ProbeBudget: 1 + rate/queue limits)            │
│  6. Portable RFC 8785 + Ed25519 receipts                                     │
│  7. Reproducible verifier vectors                                            │
│  8. Crash-safe evidence and recovery behavior                                │
│  9. Narrow, testable claims                                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 22.3 Prioritized Implementation Timeline (Phased Rollout)

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        AEIB v1.1 PRIORITIZED IMPLEMENTATION PHASES                     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 1: FOUNDATIONAL MOATS (WEEKS 1–3)                                                │
│ • Implement Delegation Chain Attenuation (Macaroon/UCAN caveat validation).            │
│ • Implement Intent-Context Fusion Gate (Tier 1 regex/Bloom + Tier 2 local DLP hold).   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 2: AUDIT & COMPLIANCE LAYER (WEEKS 4–6)                                          │
│ • Implement SCITT AIR Profile Translator (COSE_Sign1 + pending_confirmation mapping).  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 3: ECOSYSTEM & FAILSAFE (WEEKS 7–8)                                              │
│ • Integrate MCP Governance Proxy Adapter (Schema-aware tools/call interception).       │
│ • Implement Cryptographic Kill Switch (k-of-n TSS verifier + eBPF LSM HALT filter).    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```









