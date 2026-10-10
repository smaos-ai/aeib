# AEIB Threat Model (`v1.0.0-rc.1` & `v0.2.0 / v0.4.0` Baseline)

**Version:** `v1.0.0-rc.1` (Java 21 Native Runtime & Verifier) & `v0.2.0 / v0.4.0` (Python Baseline)  
**Scope:** Agent Evidence Interlock Boundary (AEIB) — Wire-Level Evidence Contamination, Ambiguous Transport Reconciliation & Receipt Verification

> **Final Bounded Claim (`v1.0.0-rc.1`):**  
> **AEIB v1.0.0-rc.1 is a Java 21-compatible deterministic execution-integrity runtime for agentic systems. It is designed to verify a pinned manifest, evaluate candidate actions locally before dispatch without external I/O, represent ambiguous transport outcomes as `EFFECT_INDETERMINATE`, resolve uncertainty through declared semantic reconciliation with bounded probe budgets, and produce tamper-evident RFC 8785–bound Ed25519 hash-chain receipts. The standalone verifier requires the caller to supply the public key associated with the receipt’s `keyId`. AEIB does not claim universal exactly-once execution across uncooperative targets, provide external SCITT anchoring, implement automatic key lookup, validate memory or retrieval provenance, or claim regulatory compliance. Hosted branch/tag CI has executed (`38055110173`, `38055279949`); independent third-party reproduction from the signed tag remains pending.**

---

## 1. The Core Threat: Evidence Contamination & Ambiguous Wire Outcomes

When an AI agent dispatches a mutating tool call (payment, database write, API state change) and the downstream system responds ambiguously (HTTP 504 timeout, TCP RST, partial write, or mid-flight socket drop), the runtime must decide what state transition to record and whether retries are permitted.

**The Flawed Assumption:**
> *"If the Ed25519 signature is valid and the local sandbox ran cleanly, the receipt proves the external outcome."*

**The Observed Failure Mode:** Local sandboxes isolate compute, but when a downstream gateway times out after committing a side effect, naive harnesses either retry blindly (causing duplicate mutations) or emit a signed receipt asserting `verdict: "executed"` without target-side reconciliation.

The signature is verified under the supplied public key, yet the receipt is operationally false.

---

## 2. Threat Categories Evaluated Under the Stated Model

### T1 — Fabricated Confirmation / Blind Retry on Wire Ambiguity

| Property | Detail |
|:---------|:-------|
| **Trigger** | HTTP 504 / TCP RST / read timeout during mutating tool call |
| **Failure** | Harness signs `CONFIRMED` without downstream ACK or issues an unhedged retry |
| **Impact** | Duplicate mutations, phantom inventory, audit trail contamination |
| **Evaluation** | `v1.0.0-rc.1`: `Gate4IntegrationTest` & `Station2EffectReconciler` transition to `EFFECT_INDETERMINATE` and enforce single-flight probe reconciliation; `v0.4.0`: `DISPATCHED_UNCONFIRMED` lockout latch |

### T2 — Signature-Without-Substance

| Property | Detail |
|:---------|:-------|
| **Trigger** | Valid Ed25519 signature over an unverified or tampered statement |
| **Failure** | Downstream reviewers treat signature presence alone as proof of target settlement |
| **Impact** | Unsubstantiated operational timeline records |
| **Evaluation** | `v1.0.0-rc.1`: `ReceiptVerifier` & `VerifierCli` verify raw RFC 8785 signed bytes, payload digest equality, and caller-supplied public key (`13/13` vectors); `v0.4.0`: `toxic_receipt_detector.py` property-level check |

### T3 — In-Transit or Post-Hoc Payload Modification

| Property | Detail |
|:---------|:-------|
| **Trigger** | Compromised proxy, faulty middleware, or post-hoc JSON key/whitespace reformatting |
| **Failure** | Action parameters (`amount`, `targetUri`, `operationId`) or receipt fields altered |
| **Impact** | Unauthorized parameter mutation or broken hash-chain continuity |
| **Evaluation** | Strict RFC 8785 JCS canonicalization (`Rfc8785Canonicalizer` / `encode_jcs`), SHA-256 `chainTip` continuity check, and Ed25519 signature verification (`PAYLOAD_DIGEST_MISMATCH` / `INVALID_SIGNATURE`) |

### T4 — Unbounded Probe Storm / Stale Reconciliation Replay

| Property | Detail |
|:---------|:-------|
| **Trigger** | Concurrent worker retries or repeated probe invocations after a transport timeout |
| **Failure** | Retry storm overwhelms degraded target endpoint or keeps an indeterminate operation alive indefinitely |
| **Impact** | Cascading target exhaustion or replay of stale state |
| **Evaluation** | `v1.0.0-rc.1`: `SingleFlightCoalescer` ($N=1$ upstream probe per effect) and operation-scoped `ProbeBudget` enforcing `probeTimeout`, `maxProbesPerMinute`, `maxConcurrentProbes`, and absolute `reconciliationDeadline` |

---

## 3. Container Presence vs. Property-Level Sufficiency

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  CONTAINER PRESENCE VS. PROPERTY SUFFICIENCY                │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTAINER PRESENCE                                                          │
│   "Is a JSON trace file present? Is an Ed25519 signature attached?"         │
│   → Only demonstrates that a log string was serialized and signed.          │
├─────────────────────────────────────────────────────────────────────────────┤
│ PROPERTY-LEVEL SUFFICIENCY (AEIB Architectural Scope)                       │
│   "Did the runtime represent socket timeout as EFFECT_INDETERMINATE?"       │
│   "Was reconciliation bounded by a declared policy and probe budget?"       │
│   "Does rawSignedStatement match RFC 8785 JCS bytes under the supplied key?"│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Mitigations Implemented in `v1.0.0-rc.1` (Java 21 Native Runtime)

1. **Station 0/1 — Pinned Manifest & Local Candidate Admission (`Station0AdmissionGate`):** Verifies the pinned manifest and evaluates candidate actions locally before network dispatch without external I/O. Computes a deterministic Content-Addressed Action Identifier (`CAID`) via RFC 8785 JCS and SHA-256.
2. **Station 2 — Ambiguity Representation & Bounded Semantic Reconciliation (`Station2EffectReconciler`, `SingleFlightCoalescer`):** Represents ambiguous transport outcomes as `EFFECT_INDETERMINATE`. Resolves uncertainty against target-provided semantic state under AEIB’s declared reconciliation policy (`CONFIRMED`, `REFUTED`, `CONFLICT`, `EFFECT_INDETERMINATE`). The `reconciliationDeadline` in `ProbeBudget` is bound to the operation creation time so callers cannot extend probing indefinitely.
3. **Station 3 — RFC 8785–Bound Ed25519 Hash-Chain Receipts (`Station3ContinuousLedger`, `Ed25519ProofEngine`):** Serializes the receipt statement via stateless RFC 8785 JCS, links the SHA-256 `chainTip` of the prior receipt in the epoch, and signs the canonical UTF-8 bytes with Ed25519.
4. **Station 4 — Standalone Offline Verifier (`ReceiptVerifier`, `VerifierCli`):** Standalone verifier designed for offline verification (independence requires separate execution and evidence). Requires the caller to supply the PEM X.509 SPKI Ed25519 public key associated with the receipt’s `keyId`, enforces input size bounds (`1 MiB` receipt, `64 KiB` public key, non-symlink regular files), verifies the Ed25519 signature over the raw signed bytes, and re-canonicalizes the statement via RFC 8785 to detect any structural tampering.

---

## 5. Mitigations Implemented in `v0.2.0 / v0.4.0` (Python Baseline)

The Python baseline (`src/aeib_v040_engine.py` and `toxic_receipt_detector.py`) evaluates a 5-stage verification pipeline across the four threat categories:

1. **JCS Digest Integrity (`src/jcs_canonicalizer.py`)** → addresses T3
2. **Signature Envelope Presence (`src/cose_signer.py`, `src/cose_verifier.py`)** → addresses T2
3. **Canonicalization Guard (RFC 8785 UTF-16 code unit sorting)** → addresses T3
4. **Timestamp Freshness** → addresses T4
5. **Effect-Integrity Classification (`DISPATCHED_UNCONFIRMED` latch)** → addresses T1

The Python pipeline enforces the following evaluation order:

```
INVALID_INPUT → MISSING_EVIDENCE → CONFLICT → REFUSED → CONFIRMED → UNKNOWN
```

`UNKNOWN` (`DISPATCHED_UNCONFIRMED` / `EFFECT_INDETERMINATE`) is the fail-closed terminus when no affirmative target-provided semantic state confirms the external effect.

---

## 6. Explicit Non-Claims & Threat Boundaries for `v1.0.0-rc.1`

* **No Universal Exactly-Once Execution Across Uncooperative Targets:** If a downstream target provides neither idempotency keys nor a queryable status interface, AEIB cannot resolve whether a severed request mutated remote state; it records `EFFECT_INDETERMINATE` and halts fail-closed.
* **Caller-Supplied Public Key Responsibility:** The standalone verifier does not perform automatic key lookup, PKI certificate chain validation, or OCSP/CRL revocation checks. The caller/auditing environment must supply the authentic public key corresponding to `keyId` out-of-band.
* **No External SCITT Anchoring:** Receipts are hash-chained locally within an epoch; `v1.0.0-rc.1` does not anchor receipts to an external IETF SCITT transparency log.
* **No Memory or Retrieval Provenance Validation:** `v1.0.0-rc.1` does not authenticate upstream RAG chunks, context-window compaction steps, or procedural-memory writes.
* **No Host Root / Kernel Compromise Protection:** Software Ed25519 keys and local JVM memory are not protected against a compromised host kernel or root attacker; eBPF and TEE files in the repository are structural scaffolds only.

---

## 7. v1.1 Backlog: Threat & Specification Candidates Only (Out of Scope for `v1.0.0-rc.1`)

The following 13 items (including procedural-memory write threats `TM-12` / `TM-13`, post-quantum hybrid signing, and external transparency anchoring) are **out of scope for `v1.0.0-rc.1`** and are retained strictly as **v1.1 research or specification candidates**:

1. `Multi-tier memory binding`
2. `Retrieval provenance policy`
3. `Procedural-memory write admission`
4. `Upstream context-decision reference`
5. `Diagnostic interlock decision fields`
6. `External transparency registration`
7. `Hybrid Ed25519 + ML-DSA-65 signature profile`
8. `CCS interoperability review`
9. `GAAT telemetry projection review`
10. `MMR ledger evaluation`
11. `dspy-security-bench evaluation review`
12. `TA-14 or equivalent external examination`
13. `AIUC-1 certification pathway`

Do not claim compatibility, conformance, certification, or alignment with any of these until a formal specification, test suite, and evidence exist.
