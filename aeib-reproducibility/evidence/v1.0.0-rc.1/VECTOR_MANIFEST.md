# AEIB Receipt Verification Vector Manifest (`v1.0.0-rc.1`)

- **Target A:** JVM standalone verifier (`com.aeib.verifier.VerifierCli` / `ReceiptVerifier`)
- **Target B:** Independent Python 3 reference implementation (`benchmarks/jvm_native_diff_engine.py` / `src/jcs_canonicalizer.py`)
- **Source Vector Definition:** `aeib-native-runtime/aeib-verifier/src/test/resources/vectors/manifest.json`

> **Calibrated Summary Statement:**  
> *All 14 tested vectors (13 manifest conformance vectors + 1 Gate 4 live socket-fault receipt) produced matching verdicts across the JVM verifier and the independent Python 3 reference implementation and, except for the intentionally non-canonical vector (`non-canonical-statement`), zero canonical-byte divergence (`0 B`).*  
> *(Note: Target A in `v1.0.0-rc.1` is the OpenJDK 21 JVM verifier; a GraalVM native-image binary is not built or invoked in the `v1.0.0-rc.1` test suite.)*

---

## 1. Vector Table & Canonical-Byte Divergence Expectations

| # | Vector ID | Expected Verdict & Exit Code | Expected Canonical JCS Divergence | Vector Specification & Rationale |
| :---: | :--- | :--- | :---: | :--- |
| 0 | `gate4-live-receipt` (`receipt.json`) | `ACCEPT` (exit `0`) | `0 B` | Live receipt emitted by `Gate4IntegrationTest` after socket severing (`INDETERMINATE`) and single-flight status probe reconciliation. |
| 1 | `valid` | `ACCEPT` (exit `0`) | `0 B` | Conforming Ed25519-signed receipt with strict RFC 8785 `signedStatement` verified under the supplied public key. |
| 2 | `tampered-statement` | `REJECT` (exit `2`) | `0 B` | Root `operationId` modified (`OP-TAMPERED-999`) while `signedStatement` remains canonical (`OP-VEC-001`); rejected at statement-to-root binding check. |
| 3 | `tampered-signature` | `REJECT` (exit `2`) | `0 B` | Single-byte corruption in `signature.ed25519Signature` with canonical `signedStatement`; rejected at Ed25519 verification. |
| 4 | `wrong-key` | `REJECT` (exit `2`) | `0 B` | Caller supplies a valid SPKI Ed25519 public key that does not correspond to the signing private key; rejected at Ed25519 verification. |
| 5 | `unknown-keyid` | `REJECT` (exit `2`) | `0 B` | Root `signature.keyId` diverges from `signedStatement.keyId`; rejected at `keyId` binding check. |
| 6 | **`non-canonical-statement`** | **`REJECT` (exit `2`)** | **`71 B` (Intentional > 0)** | **Intentionally non-canonical `signedStatement`:** Base64 payload decodes to `{"chainTip":"...",  "epoch": 1000, "keyId": "test-key-alpha", "operationId": "OP-VEC-001"}` (`133 B` with extraneous spaces after commas/colons) vs. RFC 8785 canonical form (`126 B` without extraneous whitespace), shifting `71` byte positions. Both JVM and Python verifiers reject with exit code `2` at Step 1 (`Arrays.equals(signedStatement, reCanonicalBytes)`). |
| 7 | `missing-keyid` | `REJECT` (exit `3`) | `0 B` | `signature.keyId` omitted; rejected by strict schema parser prior to canonicalization. |
| 8 | `malformed-json` | `REJECT` (exit `3`) | `0 B` | Truncated/unparseable JSON syntax; rejected at JSON parse boundary with input exit code `3`. |
| 9 | `trailing-token` | `REJECT` (exit `3`) | `0 B` | Trailing characters after root JSON object closure; rejected by strict single-value JSON parser with exit code `3`. |
| 10 | `oversized-receipt` | `REJECT` (exit `3`) | `0 B` | Receipt file exceeds the `1 MiB` (`1,048,576 B`) bounded reader limit (`ReceiptFileReader.MAX_RECEIPT_BYTES`). |
| 11 | `missing-receipt` | `REJECT` (exit `3`) | `0 B` | Non-existent receipt path supplied to verifier; rejected with input exit code `3`. |
| 12 | `missing-public-key` | `REJECT` (exit `3`) | `0 B` | Non-existent public key path supplied to verifier; rejected with input exit code `3`. |
| 13 | `directory-as-receipt` | `REJECT` (exit `3`) | `0 B` | Directory path supplied instead of regular file (`Files.isRegularFile` check fails with exit code `3`). |
