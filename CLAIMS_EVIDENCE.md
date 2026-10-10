# Claims & Grounded Evidence Mapping

**Specification:** Agent Evidence Interlock Boundary (AEIB v1.0.0-rc.1 & v0.4.0)  
**Status:** Review Candidate & Reproducibility Package  
**Governance Standard:** Zero-Mock Purity & Epistemic Calibration

## Final Bounded Claim (`v1.0.0-rc.1`)

> **AEIB v1.0.0-rc.1 is a Java 21-compatible deterministic execution-integrity runtime for agentic systems. In local and hosted CI evaluations, it verifies a pinned manifest, evaluates candidate actions locally before dispatch without external I/O, represents ambiguous transport outcomes as `EFFECT_INDETERMINATE`, resolves uncertainty through declared semantic reconciliation with bounded probe budgets, and produces tamper-evident RFC 8785–bound Ed25519 hash-chain receipts. The standalone verifier requires the caller to supply the public key associated with the receipt’s `keyId`. AEIB does not claim universal exactly-once execution across uncooperative targets, provide external SCITT anchoring, implement automatic key lookup, validate memory or retrieval provenance, or claim regulatory compliance. Independent reproduction from the signed release tag by a separate party remains pending.**

After independent reproduction passes, append only:
> **Independently reproduced from the signed release tag by a separate operator or CI runner.**

---

## 1. Overclaim Correction Matrix

Do not publish market totals, competitor funding, regulatory mandates, or benchmark claims as established facts without retaining primary sources and exact retrieval dates.

| Draft Claim | Corrected Claim |
| :--- | :--- |
| Market intelligence | Market intelligence is research context; primary-source verification is required before publication. |
| Competitor landscape | Adjacent vendor landscape; internal architectures and capability gaps require primary-source review. |
| AEIB moat | AEIB differentiation hypothesis; not an established moat. |
| Runtime binary integrity | Provides verifiable evidence linking an artifact to its build process; not absolute integrity. |
| Authoritative target state | Target-provided semantic state under AEIB’s declared reconciliation policy. |
| Mathematically confirmed | Signature verified under the supplied public key. |
| Offline independent verifier | Standalone verifier designed for offline verification; independence requires separate execution and evidence. |
| SLSA L2/L3 | SLSA provenance contract documented in `aeib-reproducibility/slsa/SLSA_INPUT_CONTRACT.md` and executed in hosted CI (`38055110173`, `38055279949`); independent third-party verification remains pending. |
| CCS / IETF / CAICT / GAAT alignment | Candidate interoperability or research references; no compatibility claim. |

---

## 2. Corrected Gate Matrix

| Gate | Status | Evidence required to close |
| :--- | :--- | :--- |
| **Gate 1 — Working core** | **Passed locally and in hosted CI** | Already satisfied by the cited hosted runs (`38055110173`, `38055279949`) |
| **Gate 2 — Reproducible artifacts** | **Passed in hosted CI** | Already satisfied by hosted artifacts (`aeib-reproducibility/evidence/v1.0.0-rc.1/`), subject to separate-party verification |
| **Gate 3 — Independent reproduction** | **Harness ready; reproduction pending** | Separate-party transcript (`third_party_verification_transcript.txt`) from signed tag `v1.0.0-rc.1`, image digest, receipt digest, and verifier exit codes |
| **Gate 4 — Real-target fault injection** | **Passed locally and in hosted CI** | Already satisfied by cited hosted Gate 4 evidence (`verifier_transcript.txt`) |
| **Gate 5 — Enterprise pilot** | **Not started** | Observe-only pilot, kill-switch drill, rollback test, and partner sign-off |

### Bounded Gate 3 Local Preflight Statement
> **AEIB v1.0.0-rc.1’s Gate 3 harness passed a local developer preflight in a Linux ARM64 container. The preflight verified source hashes, 14 receipt-vector verdicts across JVM and Python targets, Gate 4 counts of one mutation, one dispatch, one probe, and zero retry mutations, and verifier exit codes of 0 for the valid receipt and 2 for the tampered receipt. Gate 3 remains pending until a separate operator or CI runner reproduces the harness from signed tag `v1.0.0-rc.1` and publishes independent evidence.**

* **Cross-Language Target Qualification:** The differential check compares the **JVM verifier versus an independent Python 3 reference implementation** (no GraalVM native binary is built or invoked in `v1.0.0-rc.1`). All 14 tested vectors produced matching verdicts and, except for the intentionally non-canonical vector (`non-canonical-statement`, documented in `aeib-reproducibility/evidence/v1.0.0-rc.1/VECTOR_MANIFEST.md` with an expected 71-byte divergence), zero canonical-byte divergence (`0 B`).

---

## 3. Verified Implementation Claims — Python Baseline (v0.4.0)

The following claims are verified against on-disk symbols and pass automated verification via `scripts/ci_claims_verifier.py`:

| Claim ID | Functional Scope | On-Disk Source Symbol | Test Verification |
| :--- | :--- | :--- | :--- |
| **CLM-01** | Tycho Fail-Closed Gate | `src/aeib_v040_engine.py:EVALUATED_TYCHO_VERDICTS` | `tests/test_tycho_integration.py` |
| **CLM-02** | RFC 8785 JCS Canonicalization | `src/jcs_canonicalizer.py:encode_jcs` | `tests/test_jcs_canonicalizer.py` |
| **CLM-03** | Opt-In NFC Ingress Pre-Pass | `src/jcs_canonicalizer.py:normalize_nfc` | `tests/test_jcs_canonicalizer.py` |
| **CLM-04** | COSE Verifier JCS Delegation | `src/cose_verifier.py:encode_jcs` | `tests/test_cose_jcs_parity.py` |
| **CLM-05** | COSE Signer JCS Delegation | `src/cose_signer.py:encode_jcs` | `tests/test_cose_jcs_parity.py` |
| **CLM-06** | Appendix B Vector Parity | `tests/test_jcs_canonicalizer.py:TestRFC8785AppendixBVectors` | `tests/test_jcs_canonicalizer.py` |
| **CLM-07** | Signer/Verifier Round-Trip | `tests/test_cose_jcs_parity.py:TestSignVerifyRoundTrip` | `tests/test_cose_jcs_parity.py` |
| **CLM-08** | eBPF Socket State (Scaffold) | `ebpf/aeib_sock_filter.c:fault_events` | Documented Scaffold |
| **CLM-09** | Compaction Classifier Marker | `schemas/aeib-receipt-v0.4.0.json:aeib_compaction_safe_v2` | Schema Verified |
| **CLM-10** | Ed25519 Receipt Signing | `src/cose_signer.py:sign_trust_passport` | `tests/test_cose_jcs_parity.py` |
| **CLM-11** | Out-of-Band Outcome Probing | `src/sqlite_probe_adapter.py:SQLiteOutcomeProbeAdapter` | `tests/test_real_world_reconciliation.py` |
| **CLM-12** | Saga Reconciliation | `src/ocr_audit/saga_reconciler.py:SagaReconciler` | `tests/test_saga_compensation.py` |
| **CLM-16** | Transport Vocabulary | `src/aei_core_middleware.py:PROBE_OUTAGE_HOLD` | `tests/test_industrial_protection_matrix.py` |
| **CLM-17** | Unconfirmed Lockout Latch | `src/aeib_v040_engine.py:DISPATCHED_UNCONFIRMED` | `tests/test_industrial_protection_matrix.py` |
| **CLM-18** | Toxic Receipt Error Latch | `src/ocr_audit/core_proof_engine.py:ERR_DISPOSITION_TOXIC` | `tests/test_falsifiability_matrix.py` |

---

## 4. Verified Implementation Claims — Java 21 Native Runtime (v1.0.0-rc.1)

The following claims are verified against on-disk symbols in `aeib-native-runtime` and pass automated verification via `./gradlew clean test`:

| Claim ID | Functional Scope | On-Disk Source Symbol | Test Verification |
| :--- | :--- | :--- | :--- |
| **CLM-20** | Station 0/1 Pre-Dispatch Admissibility Gate | `com.aeib.runtime.Station0AdmissionGate` / `com.aeib.core.DomainRecords` | `DomainRecordsTest.java` |
| **CLM-21** | Deterministic CAID Generation (RFC 8785 JCS) | `com.aeib.verifier.Rfc8785Canonicalizer` / `com.aeib.crypto.CaidEngine` | `DomainRecordsTest.java`, `Rfc8785Canonicalizer.java` |
| **CLM-22** | Station 2 Single-Flight Coalescer & Absolute Deadline | `com.aeib.runtime.Station2EffectReconciler`, `SingleFlightCoalescer` | `MandatoryNegativeTestSuite.java`, `Gate4IntegrationTest.java` |
| **CLM-23** | Station 3 Operation Receipt & Ed25519 Signing | `com.aeib.crypto.Ed25519ProofEngine`, `com.aeib.core.DomainRecords.OperationReceipt` | `Gate4IntegrationTest.java` |
| **CLM-24** | Station 4 Standalone Offline Verifier Pipeline | `com.aeib.verifier.ReceiptVerifier`, `com.aeib.verifier.VerifierCli` | `VerifierCliTest.java` (13 deterministic test vectors) |
| **CLM-25** | Verifier Exit Code Contract | `com.aeib.verifier.VerifierCli` (0=valid, 1=usage, 2=crypto/binding, 3=input/format, 4=internal) | `VerifierCliTest.java`, `.github/workflows/aeib-rc-verify.yml` |
| **CLM-26** | Public Key Format Pinning | `com.aeib.verifier.PublicKeyReader` (PEM X.509 SPKI Ed25519; rejects raw 32B, SSH, certs) | `VerifierCliTest.java` |
| **CLM-27** | Verifier Input Bounds | `com.aeib.verifier.ReceiptFileReader` (1 MiB max receipt, 64 KiB max pubkey, regular non-symlink files) | `VerifierCliTest.java` |
| **CLM-28** | Gate 4 Live Dispatch & Offline Verify | `ai.sovereign.aeib.tests.Gate4IntegrationTest` (bounded `\r\n\r\n` header reads, 4 phases, 0 artificial counters) | `Gate4IntegrationTest.java` |

---

## 5. Explicit Epistemic Corrections & Calibrated Language

To maintain adherence to scientific integrity and epistemic boundaries under the stated model, the following distinctions are strictly observed:

### Cryptographic State Binding vs. Factual Truth
* **What a Cryptographic Hash Digest & Ed25519 Signature Demonstrate**:
  * *That this exact execution state was authorized under a declared manifest.*
  * *That this exact payload remained unaltered across execution turns.*
  * *That this receipt cryptographically binds to the declared operation statement and `keyId`, with the signature verified under the supplied public key.*
* **What a Cryptographic Hash Digest & Signature CANNOT Demonstrate**:
  * *Whether the underlying transaction content is factually accurate or true in the real world.*
  * *Whether the model's extraction from context was faithful or hallucinated.*
  * *Whether the external service correctly completed its internal business logic without unrecorded side effects.*

### Regulatory Context (FTC, DORA, EU AI Act)
* **FTC Inquiries**: The reported FTC investigations into AI labs increase the importance of defensible agent controls and truthful safety claims. They do *not* establish a universal legal rule that deployers are directly liable for all agent actions.
* **EU DORA Article 17**: Requires an entity-wide ICT incident management and notification process. AEIB contributes cryptographic timeline evidence and technical state traces; it does *not* itself satisfy DORA compliance.
* **EU AI Act Article 50**: Governs transparency obligations for AI systems and AI-generated content. AEIB execution receipts do *not* automatically satisfy Article 50 disclosure duties.
* **Unverified Threat Identifiers**: Names such as `CVE-2026-82533`, `GitSpawn`, `Plugin4Shell`, and `PixelLeak` are classified as unverified external references and are excluded from executive claims until primary-source vendor advisories are published.

### Empirical Test Measurements
* **Probe Invocation**: "Exactly one upstream probe request was issued per effect in the tested concurrency scenario." (Evaluates target-provided semantic state under AEIB’s declared reconciliation policy rather than claiming uncompromised target database truth).
* **Duplicate Suppression**: "No duplicate retry was issued by the controlled gateway in the tested scenario." (Avoids claiming remote APIs did not experience duplicate side effects).
* **Harness Observation**: "In the tested 500-episode deterministic harness (seed 42), 0 duplicate writes were observed in Arm 4." (Bounded strictly to the stated experimental conditions).

---

## 6. v1.1 Backlog: Candidates Only

The following 13 items are retained strictly as **research or specification candidates**, not v1.0.0-rc.1 commitments:

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

---

## 7. Five-Phase Governance Progression Status & Final Rule

| Phase | Milestone | Current Status |
| :--- | :--- | :--- |
| **Phase 1** | Local Developer & Container Pre-Flight | **PASSED** (19 Gradle tasks, 32 Pytest tests, 13 verifier vectors, 500 episodes) |
| **Phase 2** | Hosted CI Pipeline Execution | **EXECUTED** (Hosted branch/tag CI runs `38055110173`, `38055279949`) |
| **Phase 3** | Clean-Clone Independent Reproduction | **PENDING** (Awaiting independent third-party reproduction from signed tag `v1.0.0-rc.1`) |
| **Phase 4** | Bounded External Examination (e.g., TA-14) | **CANDIDATE / PENDING** (v1.1 candidate; no examiner engaged) |
| **Phase 5** | Formal Certification (e.g., AIUC-1) | **CANDIDATE / PENDING** (v1.1 candidate; future pathway) |

```text
v1.0 proves only what hosted CI and independent reproduction demonstrate.
v1.1 specifies only what can be tested.
Research informs design; it never becomes a claim.
No tag until branch CI passes.
No release claim until independent reproduction exists.
```
