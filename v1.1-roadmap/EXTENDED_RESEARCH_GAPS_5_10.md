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

