# AEIB Cryptographic Key Management Policy
**Regulatory Cross-Reference:** DORA (Regulation (EU) 2022/2554) Article 9(4)(c); NIST SP 800-57 Part 1 Rev. 5; BSI TR-02102-1; FIPS 186-5.
**Operational Scope:** Key generation, custody, rotation, revocation, and post-quantum cryptographic (PQC) agility across AEIB components.
**Status:** Configured and evaluated under operational testing procedures.

---

## 1. Cryptographic Architecture & Primitive Selection

AEIB enforces strict cryptographic purity across all execution boundaries:

| Key Role | Primitive / Algorithm | Parameter / Curve | Standard Citation | Storage Medium |
|---|---|---|---|---|
| **Station 1 Dispatch Signer** | Ed25519 (pure RFC 8032) | Edwards25519 ($2^{255}-19$) | FIPS 186-5, RFC 8032 | Memory-pinned (0o600 UDS) / TPM 2.0 |
| **Receipt Generation Signer** | Ed25519 (pure RFC 8032) | Edwards25519 ($2^{255}-19$) | FIPS 186-5, RFC 8032 | Offline Cold Vault / HSM |
| **Content Addressing (CAID)** | SHA-256 | 256-bit digest | FIPS 180-4, RFC 8785 JCS | In-memory / WAL |
| **Canonical Serialization** | RFC 8785 JCS | UTF-16 code unit sorting | RFC 8785 | Pure Python / Rust std |
| **Post-Quantum Candidate** | ML-DSA-65 | Matrix-LWE Lattice | FIPS 204 | Hardware Security Module |

> **Strict Rule**: Zero mock signatures (`mock_sig`), stub hashes, or hardcoded signature bypass gates are permitted anywhere in production or verification code.

---

## 2. Key Lifecycle Management

```
[ 1. Generation (CSPRNG / TPM) ]
             |
             v
[ 2. Custody & Multi-Party Quorum (2-of-3) ]
             |
             v
[ 3. Operational Use & Epoch Gating (30-day epoch) ]
             |
             v
[ 4. Scheduled Rotation / Emergency Revocation ]
             |
             v
[ 5. Secure Destruction (Cryptographic Erasure) ]
```

### 2.1 Key Generation
- All asymmetric keys must be generated using cryptographically secure pseudorandom number generators (CSPRNG) backed by OS entropy sources (`/dev/urandom` on POSIX or hardware TRNG).
- Key pairs must never be generated on external hosted services or third-party cloud orchestration platforms without hardware attestation.

### 2.2 Custody and Multi-Party Control
- **Operational Keys**: Accessible only to the local AEIB process running under a dedicated system user account. Filesystem permissions are locked to `0o600`.
- **Root and Authority Keys**: Protected under an $m$-of-$n$ threshold scheme requiring a strict 2-of-3 quorum of authorized security officers for administrative operations (revocation, root certificate updates).

### 2.3 Key Rotation Policy
1. **Station 1 Operational Dispatch Keys**: Rotated automatically every 30 days. Prior key enters a 7-day grace period for receipt verification only.
2. **Intermediate Authority Keys**: Rotated every 12 months.
3. **Policy Epoch Identifier**: Every key rotation increments the global `policy_epoch`. Transactions signed under expired epochs fail closed with `HALT_EXPIRED_POLICY_EPOCH`.

### 2.4 Emergency Revocation Protocol
In the event of suspected key exposure:
1. Two authorized officers sign a Revocation Certificate referencing the public key thumbprint.
2. The Revocation Certificate is distributed to all cluster nodes via the append-only outbox.
3. Station 1 nodes immediately blacklist the public key thumbprint in memory and record the revocation event in the Direct-I/O WAL.
4. Active capability tokens issued under that key are instantly invalidated.

---

## 3. Post-Quantum Cryptography (PQC) Agility Pathway

In alignment with NIST FIPS 204 and European cybersecurity roadmaps, AEIB implements a hybrid cryptographic envelope design:
- **Classical Layer**: Ed25519 (high-throughput, sub-millisecond wire verification).
- **Post-Quantum Layer**: ML-DSA-65 (FIPS 204 lattice-based signature candidate).
- **Dual-Verification Rule**: During the transition phase, receipts and capability warrants require valid signatures from both the classical and post-quantum signers before acceptance. If either signature verification fails, the transaction is rejected.

---

## 4. Verification and Compliance Audits

1. **Static AST Enforcement**: Verified continuously by `compliance/ast_purity.py` and `compliance/no_mock_enforcer.py` to ensure no mock keys exist in the repository.
2. **Zero-Dependency Verification**: Verified by `tools/standalone_offline_verifier.py`, enabling third-party auditors to authenticate signed receipts without installing external package dependencies.
3. **Hardware Storage Validation**: Physical external NVMe SSD cold vaults (`/Volumes/EXTssd`) provide air-gapped bit-for-bit mirrors for business continuity under DORA Article 12.
