# Extended Research Gaps 5–10: Standards & Architecture Candidate Mapping (`v1.1`)

> **Epistemic Boundary Notice:**  
> *Research informs design; it never becomes a claim.*  
> The frameworks, drafts, and benchmarks below (TA-14 SCGA, AEIM v1.2.0, Apple GAAT, OpenA2A / MTC, LICITRA-MMR, and IETF SCITT Agent Profile) are recorded strictly as **v1.1 research and specification candidates**. AEIB `v1.0.0-rc.1` does not claim compatibility, conformance, certification, or formal alignment with any of these specifications until a dedicated specification, test suite, and verifiable evidence artifact exist.

---

## 1. Architectural Candidate Matrix (Gaps 5–10)

| Gap ID | External Research / Draft Reference | Core Technical Mechanism | `v1.0.0-rc.1` Baseline Boundary | `v1.1` Specification / Test Candidate |
| :--- | :--- | :--- | :--- | :--- |
| **Gap 5** | **TA-14 SCGA Exam v0.6** *(Admissible Computation)* | Authority and standing must be evaluated before compute or network commitment. | `Station0AdmissionGate` verifies pinned manifest digest locally before dispatch without external I/O. | Candidate external examination harness for pre-commitment admissibility vectors. |
| **Gap 6** | **AEIM v1.2.0** *(T01–T12 & EO-1 Evidence-Before-Effect)* | Binary boundary tests requiring durable evidence commitment prior to external mutation (`EO-1`). | `Gate4IntegrationTest` tests socket severing (`INDETERMINATE`), 1 status probe, and post-reconciliation `ContinuityReceipt` signing. | Pre-dispatch signed intent staging (`PRE_DISPATCH_COMMITTED` ledger entry prior to socket write) to evaluate `EO-1` strictly. |
| **Gap 7** | **Apple GAAT** *(Governance-Aware Agent Telemetry / OTel)* | Projects governance state (`CAID`, `disposition`, `probe_budget`) into OpenTelemetry span attributes. | `ContinuityReceipt` and `ReconciledState` expose deterministic fields in memory and JSON receipts. | Candidate `aeib-telemetry` OTel span attribute projection mapping (`gaat.*` namespace review). |
| **Gap 8** | **Post-Quantum Agent Identity** *(OpenA2A & Merkle Tree Certificates)* | Hybrid `Ed25519 + ML-DSA-65` (FIPS 204) signatures for long-horizon non-repudiation. | Single-algorithm `Ed25519` (RFC 8032) over RFC 8785 JCS statement bytes (`64 B` signature). | Two-tier signing candidate: `Ed25519` on the hot path + `ML-DSA-65` over periodic batch epoch roots. |
| **Gap 9** | **LICITRA-MMR Ledger** *(Merkle Mountain Range)* | $O(\log N)$ append-only inclusion and consistency proofs over historical receipt streams. | Linear SHA-256 hash chain (`chainTip = SHA-256(prevTip || eventBytes)` in `Station3ContinuousLedger`). | Candidate MMR accumulator evaluation for sub-linear history verification without full chain replay. |
| **Gap 10** | **IETF SCITT Agent Profile** *(Transparency Service Registration)* | Separates **Issuer** (Agent Operator) from **Transparency Service** (Evidence Custodian). | Offline receipt verification via caller-supplied public key (`ledger-public.pem`); no external SCITT network anchoring. | Asynchronous out-of-band SCITT receipt registration profile (`COSE_Sign1` / transparency receipt attachment). |

---

## 2. Detailed Technical Analysis & `v1.0.0-rc.1` vs. `v1.1` Distinction

### Gap 5: TA-14 SCGA Admissible Computation
* **Design Principle:** Computational or network side-effects should not be initiated unless the governing manifest and standing are verified prior to execution.
* **Current `v1.0.0-rc.1` Implementation:** `Station0AdmissionGate` and `Station1DispatchInterlock` evaluate the pinned manifest and derive the RFC 8785 Content-Addressed Action Identifier (`CAID`) locally in memory with zero network egress.
* **`v1.1` Candidate Scope:** Package a reproducible challenge vector suite for independent TA-14 examination without claiming pre-existing certification.

### Gap 6: AI Execution Assurance Benchmark (AEIM v1.2.0 — `EO-1`)
* **Design Principle:** `EO-1` (*Evidence-Before-Effect*) requires that an immutable record of intent be committed before the external mutating socket write occurs, preventing unlogged side-effects if the process crashes mid-syscall.
* **Critical Epistemic Calibration for `v1.0.0-rc.1`:** In `v1.0.0-rc.1` (`Gate4IntegrationTest.java`), the runtime dispatches the HTTP POST (`INDETERMINATE`), reconciles via `Station2EffectReconciler`, and then appends `EventPhase.RECONCILED` to `Station3ContinuousLedger` to mint the `ContinuityReceipt`. Therefore, `v1.0.0-rc.1` demonstrates **post-fault reconciliation and receipt binding**, whereas strict **pre-dispatch receipt commitment (`EO-1`)** requires appending and signing a `DISPATCH_INTENT` ledger event *before* `dispatcher.dispatch(postReq)` is invoked—scheduled as a testable `v1.1` enhancement.

### Gap 7: Governance-Aware Agent Telemetry (GAAT / OpenTelemetry)
* **Design Principle:** Telemetry spans should carry structured, deterministic governance attributes (`aeib.caid`, `aeib.disposition`, `aeib.probe_budget.remaining`, `aeib.key_id`) for inline policy observability.
* **`v1.1` Candidate Scope:** Specify a pure-data mapping from `ContinuityReceipt` and `ReconciledState` records to OpenTelemetry span attributes without introducing outbound network dependencies into `ai.sovereign.aeib.core`.

### Gap 8: Post-Quantum Agent Identity (`Ed25519 + ML-DSA-65`)
* **Design Principle:** Combine classical `Ed25519` (`64 B` signature, low verification latency) with NIST FIPS 204 `ML-DSA-65` (`3,309 B` signature) to mitigate future quantum key-compromise against long-lived audit archives.
* **`v1.1` Candidate Scope:** Evaluate a hybrid epoch-anchor profile where individual turn receipts remain compact `Ed25519` envelopes and every $K$-turn epoch root is co-signed with `ML-DSA-65`.

### Gap 9: LICITRA-MMR (Merkle Mountain Range) Ledger
* **Design Principle:** Replace $O(N)$ linear hash-chain traversal with an append-only Merkle Mountain Range (MMR) supporting $O(\log N)$ inclusion proofs.
* **`v1.1` Candidate Scope:** Benchmark MMR peak bagging and inclusion proof serialization against `Station3ContinuousLedger` linear SHA-256 chaining.

### Gap 10: IETF SCITT AI Agent Execution Profile
* **Design Principle:** Decouple the runtime **Issuer** (`Station3ContinuousLedger`) from an external **Transparency Service** that countersigns registration timestamps.
* **`v1.1` Candidate Scope:** Define an optional, asynchronous out-of-band transparency registration adapter while keeping core `Station4` verification strictly offline and air-gapped.

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


