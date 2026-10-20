# Post-Quantum Evidence Envelope (PQEE) — Specification v0

```text
Status       : Experimental Specification & Native Prototype Binding
Standards    : FIPS 204 (ML-DSA-65), RFC 8032 (Ed25519), RFC 8785 (JCS)
Role         : Post-quantum signature authenticity for long-retention evidence
```

---

## 1. Purpose & Scope

The Post-Quantum Evidence Envelope (PQEE) binds an AEIB canonical evidence statement to both a classical asymmetric signature and a post-quantum lattice-based digital signature.

```yaml
pqc_evidence_envelope:
  purpose: >
    Bind an AEIB evidence statement to both a classical
    and post-quantum signature.

  classical_signature:
    algorithm: Ed25519
    role: current interoperability and low-latency verification

  pqc_signature:
    algorithm: ML-DSA-65
    standard: FIPS 204
    role: post-quantum signature authenticity

  verification_rule: require_both_valid

  serialization:
    canonical_form: rfc8785_jcs
    hash: SHA-256
```

---

## 2. Verification Policy: `require_both_valid`

To establish dual-layer authenticity, a PQEE envelope is valid if and only if both signatures verify over the canonical statement bytes:

$$\text{Valid}(\text{envelope}) \iff \text{Verify}_{\text{Ed25519}}(pk_{\text{ed}}, m, \sigma_{\text{ed}}) \land \text{Verify}_{\text{ML-DSA-65}}(pk_{\text{ml}}, m, \sigma_{\text{ml}})$$

If either signature is missing, malformed, or fails cryptographic validation, the entire envelope is rejected fail-closed.

---

## 3. Crypto Bill of Materials (CBOM) Schema

Every PQEE envelope includes a machine-readable CBOM detailing the cryptographic algorithms and implementations employed:

```yaml
cbom:
  signature_scheme: hybrid-ed25519-mldsa65-v1
  classical_algorithm: Ed25519
  pqc_algorithm: ML-DSA-65
  pqc_standard: FIPS 204
  pqc_implementation: RustCrypto/ml-dsa-v0.1.1
  verification_policy: require_both_valid
  serialization_format: rfc8785_jcs
```

---

## 4. Cryptographic Limitations & Security Assumptions

1. **No Confidentiality**: Digital signatures provide integrity and non-repudiation of origin; they do not encrypt or protect payload secrecy.
2. **No Forward Secrecy**: Digital signatures do not provide forward secrecy. If private signing keys are compromised, historical signatures generated with those keys are subject to compromise.
3. **No Signer Integrity Proof**: Valid signatures demonstrate that the private key was possessed by the entity signing the payload; they do not prove that the underlying host OS or agent runtime was uncompromised.
4. **Lifecycle & Revocation**: PQEE does not replace rigorous operational key-rotation, CRL/OCSP revocation mechanisms, or secure hardware key-custody policies.
