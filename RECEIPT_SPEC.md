# AEIB Continuity Receipt Specification (v1.0)

**Status:** Draft Standard / Reference Baseline (`v1.0.0-rc.1`)  
**Canonicalization:** RFC 8785 JSON Canonicalization Scheme (JCS)  
**Signature Primitive:** Ed25519 (RFC 8032) / COSE_Sign1 (RFC 9052 / RFC 9943 SCITT)  
**Hash Primitive:** SHA-256 (FIPS 180-4)

---

## 1. Scope & Problem Statement

When an autonomous agent or tool-calling runtime dispatches a state-mutating request over an unreliable network boundary and encounters a post-dispatch wire fault (such as an HTTP `504 Gateway Timeout` or a TCP connection reset `RST` after bytes leave the socket), the physical execution state of the downstream target is unknown at the caller boundary.

Under the stated model, coercing a post-dispatch transport fault into either a boolean `CONFIRMED` or `FAILED` state creates two distinct failure modes:
1. **False Confirmation (`CONFIRMED`)**: Recording unverified downstream state transitions that may never have settled.
2. **Unsafe Speculative Retry (`FAILED` → Retry)**: Re-dispatching non-idempotent or partially settled operations, resulting in duplicate side effects or financial double-execution.

The **AEIB Continuity Receipt** defines a deterministic, offline-verifiable cryptographic envelope that binds the observed transport disposition—specifically latching `EFFECT_INDETERMINATE` upon post-dispatch wire ambiguity—to an append-only SHA-256 hash chain and an Ed25519 signature over RFC 8785 canonical JSON bytes.

---

## 2. Wire-Fault Settlement States

Every post-dispatch evaluation at Station 2 (`EffectReconciler`) resolves to one of three mutually exclusive settlement dispositions before ledger append at Station 3 (`ContinuousLedger`):

| Settlement State | Observed Wire Condition | Retry Policy | Downstream State Assumption |
| :--- | :--- | :--- | :--- |
| `EFFECT_APPLIED` | Complete HTTP `2xx` response with verified state acknowledgment | Halted (Completed) | Target state transition observed |
| `EFFECT_REJECTED_PRE_COMMIT` | Pre-dispatch refusal or explicit target rollback confirmation | Permitted under policy | Target state unmodified |
| `EFFECT_INDETERMINATE` | Post-dispatch `504 Gateway Timeout`, socket read timeout, or TCP `RST` | **Fail-Closed (`retry_safe: false`)** | Unknown until out-of-band probe |

---

## 3. Canonical Payload & Receipt Schema

An AEIB Continuity Receipt JSON document consists of top-level routing metadata, a structured `signature` block, and a Base64-encoded `signedStatement` whose decoded UTF-8 bytes MUST strictly satisfy **RFC 8785 (JCS)** (lexicographical UTF-16 code unit key ordering, no extraneous whitespace, ECMAScript number serialization).

### 3.1 Decoded `signedStatement` (RFC 8785 Canonical JSON)

```json
{"chainTip":"SXptsl9LzsXDeq2/dJliEsMiIWhr4mMgAgP9Q9C6wKs=","epoch":1000,"keyId":"test-key-gate4","operationId":"OP-GATE4-REAL"}
```

Where `chainTip` is computed deterministically over the previous receipt tip, epoch, operation identifier, and canonical payload hash:

$$\text{chainTip}_n = \text{Base64}\left(\text{SHA-256}\left(\text{chainTip}_{n-1} \parallel \text{epoch}_n \parallel \text{operationId}_n \parallel \text{payloadHash}_n\right)\right)$$

### 3.2 Outer Receipt Envelope (`receipt.json`)

```json
{
  "operationId": "OP-GATE4-REAL",
  "epoch": 1000,
  "chainTip": "SXptsl9LzsXDeq2/dJliEsMiIWhr4mMgAgP9Q9C6wKs=",
  "signatureAlgorithm": "Ed25519",
  "hashAlgorithm": "SHA-256",
  "signature": {
    "ed25519Signature": "tXZS4vr2PsoSbppiwLRvziex53/CnwM5bfNKOFTlDXKzuyEplzJISQG1MIFh4o+ro5/Sw10Vf+7Wbx+ccz17Dw==",
    "keyId": "test-key-gate4",
    "keyEpoch": 1000
  },
  "signedStatement": "eyJjaGFpblRpcCI6IlNYcHRzbDlMenNYRGVxMi9kSmxpRXNNaUlXaHI0bU1nQWdQOVE5QzZ3S3M9IiwiZXBvY2giOjEwMDAsImtleUlkIjoidGVzdC1rZXktZ2F0ZTQiLCJvcGVyYXRpb25JZCI6Ik9QLUdBVEU0LVJFQUwifQ=="
}
```

---

## 4. Independent 4-Step Offline Verification Algorithm

Any independent verifier (`com.aeib.verifier.ReceiptVerifier` on JVM/GraalVM or `smaos_verify.wasm` in air-gapped environments) MUST evaluate a candidate receipt and Ed25519 SubjectPublicKeyInfo (SPKI) PEM public key by executing the following four deterministic steps in order:

1. **Bounded Input & Strict Parsing**:
   - Reject receipt inputs exceeding `65,536` bytes or public key inputs exceeding `8,192` bytes.
   - Parse the JSON envelope with trailing-token rejection enabled (`FAIL_ON_TRAILING_TOKENS`). Verify presence and non-null types of `operationId`, `epoch`, `chainTip`, `signatureAlgorithm` (`"Ed25519"`), `hashAlgorithm` (`"SHA-256"`), `signature` (`ed25519Signature`, `keyId`, `keyEpoch`), and Base64 `signedStatement`.
2. **Pinned RFC 8785 JCS Canonicalization Check**:
   - Base64-decode `signedStatement` into raw byte array $S_{\text{raw}}$.
   - Parse $S_{\text{raw}}$ as JSON and re-serialize using an RFC 8785 JCS canonicalizer to produce $S_{\text{jcs}}$.
   - Assert byte-exact equality: $S_{\text{raw}} = S_{\text{jcs}}$. If any whitespace, key ordering, or numeric formatting diverges by a single byte, reject immediately (`INVALID`).
3. **Statement-to-Envelope Field Binding**:
   - Extract `operationId`, `epoch`, `chainTip`, and `keyId` from the parsed `signedStatement` JSON object.
   - Assert exact equality against the outer envelope fields (`root.operationId == stmt.operationId`, `root.epoch == stmt.epoch`, `root.chainTip == stmt.chainTip`, and `root.signature.keyId == stmt.keyId`).
4. **Ed25519 Cryptographic Signature Verification**:
   - Decode `signature.ed25519Signature` from Base64 into a 64-byte Ed25519 signature $\sigma$.
   - Verify $\text{Ed25519\_Verify}(\text{PK}_{\text{SPKI}}, S_{\text{raw}}, \sigma) = \text{true}$ over the exact canonical bytes $S_{\text{raw}}$.

---

## 5. Reference CLI Execution

```bash
./gradlew clean test --no-daemon --stacktrace
./aeib-native-runtime/aeib-verifier/build/install/aeib-verifier/bin/aeib-verifier \
  --receipt aeib-native-runtime/build/test-results/receipt.json \
  --public-key aeib-native-runtime/build/test-results/ledger-public.pem
```
