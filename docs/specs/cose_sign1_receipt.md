# RFC 9052 `COSE_Sign1` & RFC 9942/9943 SCITT Receipt Envelope Specification

## 1. Scope & Epistemic Boundary
This specification defines the cryptographic receipt envelope emitted by **Station 3** of the Agent Execution Integrity Boundary (AEIB / SMF `v1.0.0-rc.3`), evaluated under the stated model.

## 2. Envelope Structure (`COSE_Sign1`)
Every consequential tool execution or deterministic halt produces a canonical `COSE_Sign1` receipt envelope coupled with an IETF SCITT (RFC 9942 / RFC 9943) append-only Merkle inclusion proof:

- **Protected Header**:
  - `alg`: `-8` (`EdDSA` over Curve25519 per RFC 9052 / RFC 8032).
  - `pqc_agility_slot`: `-49` (`ML-DSA-65` per FIPS 204 / draft-ietf-cose-dilithium).
  - `kid`: Decentralized key identifier (`did:key:...`) bound to the tenant namespace (`AT66`).
- **Payload (RFC 8785 JCS Canonical JSON, Integer Minor Units Only)**:
  - `operation_id`: Deterministic idempotency identifier.
  - `attempted_model_proposal`: Content-Addressed Action Identifier (`action_caid`), verb, and target resource.
  - `boundary_authorization_state`: Sponsor key ID, delegation certificate ID, policy epoch, verdict (`ALLOW` / `DENY` / `HOLD`), and rejection reason.
  - `observed_target_consequence`: Finality disposition (`CONFIRMED` / `REFUTED` / `EFFECT_INDETERMINATE`).
- **SCITT Transparency Receipt (`rfc9942_receipt`)**:
  - Domain-separated binary Merkle tree (`0x00` leaf prefix, `0x01` internal node prefix per RFC 9162).
  - Signed tree head (`root_hash_b64`, `tree_size`, `leaf_index`, `inclusion_path`).
