# AEIB Continuity Receipt Specification (v1.0)

- **Status:** Frozen (`RC1`)
- **Standard Track:** RFC 8785 (JCS) / RFC 8032 (Ed25519)
- **Hash Primitive:** SHA-256 (FIPS 180-4)

---

## 1. Abstract

An **AEIB Continuity Receipt** is a tamper-evident, detached cryptographic proof recording the authorization, dispatch, and reconciled target state of an autonomous agent mutation. Under the stated model, it allows third-party auditors to evaluate and verify execution integrity offline without runtime JVM dependencies or ambient network authority.

---

## 2. Canonical Statement Schema

The statement subject to cryptographic signing MUST be serialized using **RFC 8785 (JSON Canonicalization Scheme — JCS)**. Property keys MUST be sorted lexicographically by UTF-16 code units. Whitespace outside string literals is strictly prohibited.

### 2.1 Statement Payload Fields

```json
{
  "actionCaid": "<64-hex SHA-256 digest of canonical CandidateAction>",
  "chainTip": "<64-hex SHA-256 hash or Base64 digest of preceding receipt in epoch>",
  "effectDisposition": "<CONFIRMED | REFUTED | CONFLICT | EFFECT_INDETERMINATE>",
  "epoch": 1000,
  "sequenceNumber": 1,
  "targetUri": "<RFC 3986 URI string>",
  "timestampUtc": "<ISO-8601 UTC timestamp: YYYY-MM-DDTHH:MM:SS.NNNZ>"
}
```

> **Note on Compact Station 3 Profile (`v1.0.0-rc.1`):** In the minimal Station 3 runtime profile (`com.aeib.runtime.Station3ContinuousLedger`), the signed statement binds `{"chainTip","epoch","keyId","operationId"}` in strict RFC 8785 key order (`chainTip` $\to$ `epoch` $\to$ `keyId` $\to$ `operationId`). Both full and compact statement profiles undergo identical RFC 8785 byte-equality and Ed25519 signature verification.

---

## 3. Receipt Envelope Structure

The envelope bundles the metadata, canonical statement object, Base64-encoded RFC 8785 bytes, and Ed25519 signature:

```json
{
  "version": "1.0",
  "hashAlgorithm": "SHA-256",
  "signatureAlgorithm": "Ed25519",
  "keyId": "<UTF-8 string identifying public verification key>",
  "statement": {
    "actionCaid": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "chainTip": "0000000000000000000000000000000000000000000000000000000000000000",
    "effectDisposition": "EFFECT_INDETERMINATE",
    "epoch": 1000,
    "sequenceNumber": 1,
    "targetUri": "https://api.example.internal/v1/disbursements",
    "timestampUtc": "2026-10-10T12:00:00.000Z"
  },
  "rawSignedStatement": "<Base64-encoded RFC 8785 canonical bytes>",
  "signature": "<Base64-encoded 64-byte Ed25519 signature>"
}
```

---

## 4. Verification Algorithm

An independent verifier (implemented in any language) MUST execute the following steps in strict order:

1. **Algorithm Gating**:
   - Assert `envelope.hashAlgorithm == "SHA-256"`.
   - Assert `envelope.signatureAlgorithm == "Ed25519"`.
   - Fail immediately if unsupported (`UNSUPPORTED_ALGORITHM`).
2. **Cryptographic Signature Verification**:
   - Decode `envelope.signature` from Base64 (must be exactly 64 bytes).
   - Decode `envelope.rawSignedStatement` (or `envelope.signedStatement` in the compact profile) from Base64 into raw canonical bytes.
   - Verify the Ed25519 signature over `rawSignedStatement` using the caller-supplied public key corresponding to `envelope.keyId`.
   - `IF INVALID -> FAIL(INVALID_SIGNATURE)`.
3. **Structural Integrity & Non-Tampering**:
   - Compute the SHA-256 digest over `envelope.rawSignedStatement`.
   - Deserialize `envelope.rawSignedStatement` into an abstract map and re-canonicalize `envelope.statement` using RFC 8785 (JCS) into `canonicalStatementBytes`.
   - Assert `envelope.rawSignedStatement EQUALS canonicalStatementBytes` byte-for-byte.
   - `IF UNEQUAL -> FAIL(PAYLOAD_DIGEST_MISMATCH)`.
4. **Hash-Chain Continuity (if prior receipt provided)**:
   - Compute SHA-256 over the raw prior receipt envelope bytes and format as a lowercase 64-character hex string (`computedPriorHash`).
   - Assert `computedPriorHash EQUALS envelope.statement.chainTip`.
   - `IF UNEQUAL -> FAIL(CHAIN_TIP_BROKEN)`.
5. **PASS**:
   - Return `VERIFIED`.
