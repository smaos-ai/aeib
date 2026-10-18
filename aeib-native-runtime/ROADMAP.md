# AEIB Architecture Roadmap

## v1.0.0-rc.1 (Current Release Candidate — Commit `b2166a3f`)
- Java 21 LTS runtime baseline (`aeib-native-runtime`).
- **Station 0:** Manifest integrity gating with local pin verification (`Station0AdmissionGate`).
- **Station 1:** Dispatch interlock with RFC 8785 canonical CAID generation (`Rfc8785Canonicalizer`).
- **Station 2:** Effect reconciler with bounded probe budgets and single-flight coalescing (`Station2EffectReconciler`).
- **Station 3:** Continuous ledger with Ed25519 hash-chain receipts (`Station3ContinuousLedger`).
- **Station 4:** Standalone CLI verifier (`com.aeib.verifier.VerifierCli`) and Python 3 cross-language reference verifier (`benchmarks/jvm_native_diff_engine.py`) requiring a caller-supplied public key for the receipt's `keyId`.
- Zero-network runtime container verification harness (`aeib-reproducibility/gate3/`).

---

## v1.1 Candidate Backlog (Research & Specification Candidates Only)

> **Epistemic Rule:**  
> *v1.0 proves only what hosted CI and independent reproduction demonstrate. v1.1 specifies only what can be tested. Research informs design; it never becomes a claim.*  
> Do not claim compatibility, conformance, certification, or alignment with any of the items below until a formal specification, test suite, and verifiable evidence artifact exist.

### 1. Core Runtime & Schema Specification Candidates
- **Multi-tier memory binding**
- **Retrieval provenance policy**
- **Procedural-memory write admission**
- **Upstream context-decision reference** (`contextDecisionRef = SHA-256(canonical signed decision)`)
- **Diagnostic interlock decision fields** (`interlockDecisionReason` constrained enum)

### 2. Extended Standards & Cryptography Candidates (Gaps 5–10)
Detailed architectural analysis is maintained in [`../v1.1-roadmap/EXTENDED_RESEARCH_GAPS_5_10.md`](../v1.1-roadmap/EXTENDED_RESEARCH_GAPS_5_10.md):
- **Gap 5 — TA-14 or equivalent external examination:** Pre-dispatch admissibility challenge vectors.
- **Gap 6 — AEIM v1.2.0 (`EO-1` Evidence-Before-Effect) review:** Pre-dispatch `DISPATCH_INTENT` ledger signing prior to socket mutation write (extending `v1.0.0-rc.1` post-reconciliation receipt emission).
- **Gap 7 — GAAT telemetry projection review:** OpenTelemetry span attribute projection from `ContinuityReceipt` fields.
- **Gap 8 — Hybrid `Ed25519 + ML-DSA-65` signature profile:** Fast-path `Ed25519` turn receipts paired with FIPS 204 `ML-DSA-65` batch epoch roots.
- **Gap 9 — MMR ledger evaluation (LICITRA-MMR):** $O(\log N)$ Merkle Mountain Range inclusion proofs evaluated against linear SHA-256 hash chains.
- **Gap 10 — External transparency registration (IETF SCITT profile):** Asynchronous out-of-band Issuer / Transparency Service registration contract.
- **CCS interoperability review**
- **dspy-security-bench evaluation review**
- **AIUC-1 certification pathway**

### Explicitly Out of Scope for v1.0.0-rc.1
All v1.1 candidates listed above are unimplemented or deferred outside the `v1.0.0-rc.1` release boundary and do not alter `v1.0.0-rc.1` claims or release criteria.
