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
| **2. Audit Privacy** | **W3C BBS+ Cryptosuites (`bbs-2023`)** (`w3c/vc-di-bbs`, selective disclosure commitments) | **Selective Receipt Redactor (`Ed25519BbsSelectiveRedactor` / `src/bbs_plus_redactable.py`)**: Commits salted per-field SHA-256 digests (`urn:ietf:params:scitt:bbs-2023-ed25519-jcs-2026`) signed under an Ed25519 root over RFC 8785 JCS. | Enables selective disclosure and redaction of PII (names, IBANs) from audit receipts without invalidating the root signature—resolving **EU AI Act Art. 12** (Immutable Logs) vs. **GDPR Art. 17** (Right to Erasure). | **Tested prototype** evaluated under deterministic RFC 8785 JCS commitment vectors. |
| **3. DORA Compliance** | **EBA DPM 4.0 ITS 2024/2956 (`dora.json`)** (xBRL-CSV Register of Information taxonomy) | **Automated xBRL-CSV Package Builder (`DoraXbrlCsvPackageBuilder` / `src/dora_annex_ii_prefill.py`)**: Directly auto-maps pinned agent/MCP capability manifests into EBA xBRL-CSV ZIP packages (`META-INF/reportPackage.json`, `reports/report.json`, `parameters.csv`, `RT.01.01.csv`–`RT.01.03.csv`). | Eliminates manual spreadsheet transcription for DORA Art. 28 ICT third-party register submissions while binding the ZIP package to an Ed25519-signed `manifest_signature.json`. | **Tested prototype** generating deterministic EBA DPM 4.0 xBRL-CSV archives. |
| **4. Offline Verification** | **Pure Rust Compiled to WASM** (`wasm-bindgen`, `ed25519-dalek` `verify_strict`, `sha2`) | **Zero-Dependency Static Verifier (`smaos-wasm-verifier/smaos-verify.html` + `smaos-verify.wasm`)**: Embeds compiled Rust/WASM cryptographic verification into a single self-contained HTML artifact (`Content-Security-Policy: connect-src 'none'`). | Executes local drag-and-drop receipt verification (`CAID` re-derivation, hash-chain continuity, and Ed25519 `verify_strict`) in `~400 ms` with **0 npm or cloud calls**. | **Tested local Rust/WASM artifact** verified under air-gapped browser/CLI execution. |
| **5. Diagnostic Wedge** | **`agent-threat-rules` (`ATR-2026-01932`)** & static MCP/IDE configuration schemas | **Local Environment Auditor (`GhostAtrDiagnosticScanner` / `ghost_audit_scanner.py`)**: Audits local developer and agent configurations (`.claude`, `cursor.json`, MCP server manifests) against `ATR-2026-01932` rules (`ATR-001` through `ATR-005`). | Computes the deterministic **CISO Governance Intensity Index (`GII`, `0–100`)** and emits an Ed25519-signed diagnostic posture receipt prior to runtime deployment. | **Tested local static scanner** with zero outbound network calls. |

### 7.2 11-Item Delivery Scope & 5 Moats Ecosystem Mapping

To avoid reinventing commodity components while focusing engineering on the execution finality and evidence-binding layer, each item in the **11-Item Delivery Scope** and **5 Moats** maps to audited open-source building blocks and verified local `SovereignNexus` symbols:

| # | Delivery Scope / Moat Item | Existing Open-Source Ecosystem (`GitHub` / Standards) | Local `SovereignNexus` Implementation & Test Symbols | Epistemic Status (`AGENTS.md` Calibration) |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Runtime Admissibility Gate & Wire-Fault Effect Integrity (`Moat 1`)** | `microsoft/agent-governance-toolkit` (in-process middleware contrast); RFC 8785 JCS | `Station0AdmissionGate`, `Station1DispatchInterlock`, `Station2EffectReconciler` (`EffectDisposition.EFFECT_INDETERMINATE`), `LicitraSentryProxyGate` | **Verified in `v1.0.0-rc.1` (`Gate4IntegrationTest`) & `v1.1` prototype** |
| **2** | **Offline WASM Verifier (`smaos-verify.wasm` — `Moat 2`)** | `RustCrypto/signatures` (`ed25519-dalek` `verify_strict`), `RustCrypto/hashes` (`sha2`), `wasm-bindgen`, `serde_json_canonicalizer` | `smaos-wasm-verifier/src/lib.rs` (`verify_receipt_signature`, `compute_jcs_caid`, `derive_action_caid`) + `smaos-wasm-verifier/smaos-verify.html` | **Verified local Rust/WASM crate (zero cloud/npm runtime dependencies)** |
| **3** | **BBS+ Redactable Passports (`Moat 3`)** | `w3c/vc-di-bbs` (W3C Data Integrity BBS Cryptosuite v2023), `docknetwork/crypto` (`bbs_plus` + `crypto-wasm`), `mattrglobal/bbs-signatures` | `Ed25519BbsSelectiveRedactor` (`unified_governance_stack.py`), `src/bbs_plus_redactable.py`, `src/bbs_plus_redactable.rs`, `src/bbs_signer.py` | **Tested prototype (salted SHA-256 commitments + Ed25519 root over RFC 8785 JCS)** |
| **4** | **Kernel-Enforced Admissibility (`eBPF XDP / BPF-LSM` — `Moat 4a`)** | `cilium/tetragon` (eBPF syscall/network enforcement), `landlock-lsm/landlock`, `yeet-src/agent-lock`, `aya-rs/aya` | `scripts/verify_bpf_lsm_lock.py` (4-axis diagnostic probe), `SmaosHclCompiler` (`TracingPolicy` emission), `ebpf/ebpf_lsm_agent_guard.c`, `ebpf/aeib_sock_filter.c` | **Structural scaffolding (`AGENTS.md` §5) unless loaded on a locked Linux CVM kernel** |
| **5** | **Hardware-Backed Attestation (`Intel TDX / AMD SEV-SNP` — `Moat 4b`)** | `virtee/sev`, `virtee/tdx`, `confidential-containers/trustee` (IETF RATS Verifier/KBS), `microsoft/TEE-Attestation-Verification` | `HardwareAttestationReceiptBinder` (`unified_governance_stack.py`), `src/hardware_attestation.rs`, `scripts/verify_bpf_lsm_lock.py` | **Structural scaffolding (`AGENTS.md` §5) unless executed on CVM enclave hardware** |
| **6** | **DORA Register of Information Export (`RT.01.01–RT.01.03` — `Moat 5`)** | `Arelle/Arelle` (open-source XBRL/xBRL-CSV processor), `FiorLab/dora-article-28-ict-third-party-register`, `cyr-ius/dora-report` | `DoraXbrlCsvPackageBuilder` (`unified_governance_stack.py`), `src/dora_annex_ii_prefill.py`, `tests/test_dora_annex_ii_prefill.py` | **Tested prototype generating EBA DPM 4.0 xBRL-CSV tables + Ed25519 manifest** |
| **7** | **Ghost Configuration Audit (`.claude`, `cursor.json`, MCP manifests)** | `agent-threat-rules` (`ATR-2026-01932`), `invariantlabs-ai/mcp-scan` (`snyk/agent-scan`), GitGuardian pre-commit AI hooks | `GhostAtrDiagnosticScanner` (`unified_governance_stack.py`), `ghost_audit_scanner.py`, `test_ghost_audit_scanner.py`, `TypedOwaspPreDispatchGate` | **Tested local static scanner (`GII` score) & pre-dispatch SSRF/traversal gate** |
| **8** | **STAR Protocol CLI & AST Baseline (Merkle-DAG Code Freeze)** | Python `ast` stdlib, `tree-sitter`, `intoto/in-toto` (supply-chain layout attestations) | `StarAstMerkleDagBaseline` (`unified_governance_stack.py`) — normalized `ast.dump` leaf digests + Merkle-DAG root + Ed25519 receipt | **Tested prototype ($O(1)$ Merkle root verification in `<1 ms`)** |
| **9** | **Declarative Governance DSL (`smaos.hcl`)** | HashiCorp HCL / Open Policy Agent (`open-policy-agent/opa`), `cilium/tetragon` `TracingPolicy` CRDs | `SmaosHclCompiler` (`unified_governance_stack.py`) compiling `policy "<name>"` blocks into Tetragon `TracingPolicy` + BPF map JSON + SCITT Action Capsule profiles | **Tested prototype compiler with RFC 8785 JCS `artifact_caid` binding** |
| **10** | **Copy-on-Write (CoW) Subgraph Sandboxing** | `tursodatabase/agentfs` (SQLite-backed CoW agent filesystem), `multikernel/branchfs` (FUSE atomic speculative branches), Linux `OverlayFS` | `CoWSubgraphSandbox` (`unified_governance_stack.py`) — SQLite `committed_state` + `branch_overlay` promoting only on `CONFIRMED` | **Tested prototype (atomically discards branch overlay on `EFFECT_INDETERMINATE`)** |
| **11** | **Zero-Knowledge / Blinded Compliance Proofs (`0%` Overclaim Rate)** | `succinctlabs/sp1` (Rust zkVM), `risc0/risc0` (RISC-V zkVM), `arkworks-rs`, `zcash/halo2` | `ZeroOverclaimComplianceProver` (`unified_governance_stack.py`) — finite-field R1CS verification ($A w \circ B w = C w \pmod p$) + salted SHA-256 commitments + Ed25519 journal | **Tested R1CS & blinded-commitment prototype (proves `overclaim_count == 0` without raw payloads)** |

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

To bridge distributed observability traces with cryptographic non-repudiation without introducing network egress into the core verifier, `v1.1` implements the `draft-palanisamy-scitt-aac-otel-00` mapping via `ScittOtelActionCapsuleCorrelator`:

* **Namespace & W3C Trace Context Binding:** Projects `org.agentactioncapsule.otel` attributes—specifically the 128-bit `trace_id` (32 lowercase hex characters), 64-bit `span_id` (16 lowercase hex characters), `trace_flags`, and W3C `traceparent` (`00-<trace_id>-<span_id>-<flags>`)—directly into the RFC 8785 canonical statement of the `ContinuityReceipt` chain.
* **Bidirectional Auditability:** Allows an SRE or auditor inspecting an OpenTelemetry span (`aeib.caid`, `aeib.disposition`, `aeib.chain_tip`) to locate the exact Ed25519-signed `ContinuityReceipt`, and conversely enables an offline receipt verifier to verify that the telemetry span identifiers were cryptographically bound at execution time.

### 8.4 Hardware Attestation Binding (`Intel TDX / AMD SEV-SNP` — `HardwareAttestationReceiptBinder`)

For deployments targeting Confidential Virtual Machines (CVMs), `v1.1` specifies `HardwareAttestationReceiptBinder` to bind hardware enclave quotes (formatted for Tinfoil / VirTEE / IETF RATS verifiers) into the `ContinuityReceipt` envelope:

* **Cryptographic Quote-to-Receipt Binding:** Computes `report_data_binding = SHA-256(JCS({receipt_caid, chain_tip, nonce}))` (64 bytes / 512 bits matching the Intel TDX v4 `TDREPORT` and AMD SEV-SNP `ATTESTATION_REPORT` `report_data` field width) and embeds the attestation quote digest, measurement register (`MRTD` / `RTMR` or `LAUNCH_DIGEST`), and `evidence_class` into the signed receipt.
* **Strict Epistemic & Scaffolding Calibration (`AGENTS.md` §5):** In accordance with `AGENTS.md` §5, when executed outside physical Intel TDX (`/dev/tdx_guest`) or AMD SEV-SNP (`/dev/sev-guest`) CVM hardware, `HardwareAttestationReceiptBinder` explicitly marks `evidence_class = "STRUCTURAL_SCAFFOLDING"` and `hardware_enforced = false`. It never claims live hardware enclave isolation on standard host kernels.

### 8.5 `0%` Overclaim ZK R1CS Proofs (`ZeroOverclaimComplianceProver`)

To enable an enterprise operator to prove to an external regulator that a batch of $N$ execution episodes contained **zero unverified completion claims (`0%` overclaim rate)** without disclosing proprietary tool payloads, `v1.1` implements finite-field Rank-1 Constraint System (R1CS) verification in `ZeroOverclaimComplianceProver`:

* **Boolean Overclaim Constraint per Episode $i$:** For each episode $i \in \{1, \dots, N\}$, let $c_i \in \{0, 1\}$ denote whether the agent claimed `CONFIRMED` completion and $v_i \in \{0, 1\}$ denote whether `Station2EffectReconciler` independently verified the target mutation (`CONFIRMED` with valid Ed25519 receipt). An overclaim occurs if and only if $c_i = 1 \land v_i = 0$.
* **Finite-Field R1CS Algebra ($\mathbb{F}_p$, $p = 2^{127} - 1$):** The prover constructs witness vector $w$ over prime field $\mathbb{F}_p$ and enforces the bilinear R1CS gate equation:
  $$A w \circ B w = C w \pmod p$$
  encoding three constraint families across all episodes:
  1. **Booleanity of $c_i$:** $c_i \cdot (1 - c_i) = 0 \pmod p$
  2. **Booleanity of $v_i$:** $v_i \cdot (1 - v_i) = 0 \pmod p$
  3. **Zero-Overclaim Orthogonality:** $c_i \cdot (1 - v_i) = 0 \pmod p$
* **Verifier Contract:** Any episode with $c_i = 1 \land v_i = 0$ violates constraint $c_i \cdot (1 - v_i) = 0$ ($1 \cdot 1 = 1 \neq 0 \pmod p$), causing `ZeroOverclaimComplianceProver` and `verify_proof()` to reject the batch fail-closed. The resulting proof binds the R1CS satisfaction digest, salted episode commitment Merkle root, and `overclaim_rate == 0.0` into an Ed25519-signed public journal.

