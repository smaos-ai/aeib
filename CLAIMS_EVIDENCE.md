# Claims & Grounded Evidence Mapping

**Specification:** Agent Evidence Interlock Boundary (AEIB v0.4.0)  
**Status:** Review Candidate & Reproducibility Package  
**Governance Standard:** Zero-Mock Purity & Epistemic Calibration

---

## 1. Verified Implementation Claims

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

## 2. Explicit Epistemic Corrections & Calibrated Language

To ensure absolute adherence to scientific integrity, the following language adjustments are strictly enforced:

### Regulatory Context (FTC, DORA, EU AI Act)
* **FTC Inquiries**: The reported FTC investigations into AI labs increase the importance of defensible agent controls and truthful safety claims. They do *not* establish a universal legal rule that deployers are directly liable for all agent actions.
* **EU DORA Article 17**: Requires an entity-wide ICT incident management and notification process. AEIB contributes cryptographic timeline evidence and technical state traces; it does *not* itself satisfy DORA compliance.
* **EU AI Act Article 50**: Governs transparency obligations for AI systems and AI-generated content. AEIB execution receipts do *not* automatically satisfy Article 50 disclosure duties.
* **Unverified Threat Identifiers**: Names such as `CVE-2026-82533`, `GitSpawn`, `Plugin4Shell`, and `PixelLeak` are classified as unverified external references and are excluded from executive claims until authoritative vendor advisories are published.

### Empirical Test Measurements
* **Probe Invocation**: "Exactly one upstream probe request was issued per effect in the tested concurrency scenario." (Avoids claiming uncompromised target database truth).
* **Duplicate Suppression**: "No duplicate retry was issued by the controlled gateway in the tested scenario." (Avoids claiming remote APIs did not experience duplicate side effects).
