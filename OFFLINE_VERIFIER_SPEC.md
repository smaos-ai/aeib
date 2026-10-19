# AEIB Offline Receipt Verifier Specification

```text
Specification Version : 1.0.0-rc.3
Status                : Release Candidate Specification
Execution Model       : Standalone / Air-Gapped / Zero Network Egress
Trust Model           : Caller-Supplied Trust Anchors (No Implicit Discovery)
Canonicalization      : RFC 8785 JSON Canonicalization Scheme (JCS)
Cryptographic Suite   : Ed25519 (Pure RFC 8032 / cryptography.hazmat)
```

---

## 1. Purpose

The Standalone Offline Receipt Verifier is an independent, dependency-minimal utility designed to cryptographically verify AEIB operation receipts, continuity ledgers, and action bindings offline. 

It operates purely on static inputs (receipt files, ledger files, public key trust anchors) without network connectivity, live runtime daemons, or database handles. It enables auditors, compliance officers, and downstream systems to evaluate receipt validity in an isolated cleanroom environment.

---

## 2. Verification Pipeline

The verifier executes the following pipeline in strict sequential order. Failure at any stage halts verification immediately and returns a deterministic failure code.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      OFFLINE VERIFICATION PIPELINE                     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
          ┌──────────────────────────────────────────────────┐
          │ 1. Manifest & Schema Integrity Check             │
          │    Validate required fields: operation_id,       │
          │    disposition, signature/attestation.           │
          └────────────────────────┬─────────────────────────┘
                                   │ [Valid Schema]
                                   ▼
          ┌──────────────────────────────────────────────────┐
          │ 2. Canonical Serialization & CAID Recomputation  │
          │    Recompute SHA-256 over RFC 8785 JCS action    │
          │    payload. Assert exact match with claimed CAID.│
          └────────────────────────┬─────────────────────────┘
                                   │ [CAID Matches]
                                   ▼
          ┌──────────────────────────────────────────────────┐
          │ 3. Cryptographic Signature Verification          │
          │    Extract signature. Verify Ed25519 signature   │
          │    over canonical RFC 8785 JCS unsigned body.    │
          └────────────────────────┬─────────────────────────┘
                                   │ [Signature Valid]
                                   ▼
          ┌──────────────────────────────────────────────────┐
          │ 4. Trust Anchor & Algorithm Verification         │
          │    Verify algorithm is approved (Ed25519) and    │
          │    signing key matches trusted caller anchor.    │
          └────────────────────────┬─────────────────────────┘
                                   │ [Anchor Matches]
                                   ▼
          ┌──────────────────────────────────────────────────┐
          │ 5. Temporal Validity & Epoch Freshness           │
          │    Verify receipt timestamp is bounded within    │
          │    authorized epoch and drift limits.            │
          └────────────────────────┬─────────────────────────┘
                                   │ [Epoch Fresh]
                                   ▼
          ┌──────────────────────────────────────────────────┐
          │ 6. Evidence-Chain Linkage (Ledger Verification)  │
          │    If verifying ledger, assert prev_chain_tip    │
          │    links continuously; detect duplicate op_ids.  │
          └────────────────────────┬─────────────────────────┘
                                   │
                                   ▼
                   [PASS: Receipt Fully Verified]
```

### Detailed Verification Steps

1. **Manifest & Schema Integrity**: Validate JSON structure against the locked `agent_execution_integrity_requirements` schema. Verify required fields (`operation_id`, `disposition`, and cryptographic signature container) are present.
2. **Canonical Serialization**: Re-serialize the payload using RFC 8785 (JCS). Compute the SHA-256 digest (`sha256:<hex>`). Verify it matches the `canonical_action_digest` (CAID) bound in the receipt.
3. **Signature Verification**: Extract the signature and key identifier. Verify the cryptographic signature (Ed25519) over the exact JCS-serialized bytes using the public key from the provided Trust Anchor.
4. **Trust Anchor Binding & Algorithm Approval**: Verify the signing key identifier exists in the provided Trust Anchor and is authorized for the stated `action_class` and `policy_epoch`. Reject deprecated or unapproved algorithms.
5. **Temporal Validity**: Verify the receipt timestamp falls within the valid bounds of the `policy_epoch` and respects the configured clock drift tolerance.
6. **Evidence-Chain Linkage**: When evaluating a ledger stream (`ledger.jsonl`), verify that each entry's `prev_chain_tip` matches the computed tip of the preceding entry, and assert that no duplicate `operation_id` values exist across the sequence.

---

## 3. Negative Test Vectors (Must Reject)

The verifier is distributed with a test suite that demonstrates fail-closed behavior across all seven normative negative vectors:

| Vector ID | Negative Condition | Description | Expected Verifier Output |
| :--- | :--- | :--- | :--- |
| `NEG_01` | **Tampered Payload** | 1 byte mutated in the action payload (e.g. amount modified by 1 cent). | `FAIL: JCS_DIGEST_MISMATCH` |
| `NEG_02` | **Wrong Key** | Cryptographically valid signature, but generated by an unauthorized key outside the Trust Anchor. | `FAIL: UNTRUSTED_KEY_IDENTIFIER` |
| `NEG_03` | **Malformed Receipt** | Missing required schema fields (e.g. missing `operation_id` or malformed JSON). | `FAIL: SCHEMA_VALIDATION_ERROR` |
| `NEG_04` | **Stale Authority** | Timestamp or epoch falls outside the active authorized `policy_epoch` window. | `FAIL: TEMPORAL_VALIDITY_EXPIRED` |
| `NEG_05` | **Replayed Receipt** | Duplicate `operation_id` detected in the continuity ledger sequence. | `FAIL: OPERATION_ID_REPLAY_DETECTED` |
| `NEG_06` | **Broken Chain** | Ledger entry `prev_chain_tip` does not match the cryptographic digest of the prior record. | `FAIL: LEDGER_CHAIN_INTEGRITY_BROKEN` |
| `NEG_07` | **Algorithm Downgrade** | Receipt specifies a forbidden, weak, or deprecated algorithm (e.g. `none`, `MD5`, `SHA1-RSA`). | `FAIL: UNSUPPORTED_CRYPTO_ALGORITHM` |

---

## 4. Output Format

The verifier emits deterministic, machine-readable JSON:

```json
{
  "status": "PASS | FAIL",
  "operation_id": "op-test-001",
  "failure_code": null,
  "verified_at": "2026-10-19T04:30:00Z",
  "verifier_version": "1.0.0-rc.3"
}
```

In failure scenarios, `status` is set to `"FAIL"`, and `failure_code` contains the exact vector failure code:

```json
{
  "status": "FAIL",
  "operation_id": "op-test-001",
  "failure_code": "NEG_01: JCS_DIGEST_MISMATCH",
  "verified_at": "2026-10-19T04:30:00Z",
  "verifier_version": "1.0.0-rc.3"
}
```

---

## 5. Implementation Constraints

1. **Zero Network Egress**: The verifier must not make outbound network requests (DNS, HTTP, LDAP, OCSP, CRL). All trust anchors and schemas must be supplied via local file paths or standard input.
2. **Deterministic Execution**: Across identical inputs, the verifier must produce byte-identical canonical JSON output regardless of architecture (macOS Darwin ARM64, Linux x86_64).
3. **Zero-Mock Verification**: The verification engine and its test harness evaluate real Ed25519 keys (`cryptography.hazmat`) and real file I/O. No mocking frameworks or synthetic assertions are permitted.
