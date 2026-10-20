# Key Management & Cryptographic Custody Policy
## Cryptographic Lifecycle, HSM Custody, Multi-Party Quorum & Post-Quantum Transition

> **Regulatory Reference:** DORA (Regulation (EU) 2022/2554) Article 9(4)(c); EBA Guidelines on ICT and Security Risk Management; NIST SP 800-57 Part 1; NSA CNSA 2.0  
> **Classification:** Pre-Production Security & Cryptographic Policy  
> **Epistemic Notice:** This policy codifies the key management controls and custody specifications evaluated under the stated model of our local execution boundary prototype.

---

### 1. Key Inventory & Classification

AEIB employs a tiered cryptographic key hierarchy separating root organizational authority from ephemeral execution credentials.

| Key Classification | Algorithm / Primitive | Storage / Custody Location | Rotation Cadence | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Root Sponsor Key** | Ed25519 (`alg: -8`) / ML-DSA-65 (`alg: -49`) | Dedicated FIPS 140-3 Level 3 HSM or KMS Enclave | 365 days / On compromise | Signs `RootSponsorPolicy`, issues subagent delegation certificates. |
| **Station 1 Gate Key** | Ed25519 (`alg: -8`) | Host OS Memory with `zeroize` protection | 90 days | Signs WAL entries, CAID admissibility receipts, Merkle leaves. |
| **Station 2 Sidecar Key** | Ed25519 (`alg: -8`) | Host Proxy Memory (ephemeral) | 30 days | Generates RFC 9449 DPoP proofs (`jkt` sender-constraint). |
| **SCITT Transparency Key**| Ed25519 (`alg: -8`) | Hardware Security Module / Sealed Enclave | 180 days | Signs RFC 9052 `COSE_Sign1` receipts and Merkle root quotes. |
| **Subagent Session Key** | Ed25519 (`alg: -8`) | Guest MicroVM RAM (ephemeral) | Per session ($\le 1\text{ hour}$) | Proposes wire action payloads; holds zero financial spend authority. |

---

### 2. Key Generation & Cryptographic Purity

* **Source of Entropy:** All key generation must derive from a verified cryptographic pseudorandom number generator (CSPRNG) backed by operating system entropy (`/dev/urandom` / `getrandom(2)` on Linux, `SecRandomCopyBytes` on macOS).
* **Zero-Mock Policy:** In accordance with [`AGENTS.md`](file:///Users/andriileukhin/Documents/SovereignNexus/AGENTS.md), fake signatures (`mock_signature`), stubbed hashes, or hardcoded private key bytes are prohibited in both production modules and test suites. All tests execute real cryptographic operations via `cryptography.hazmat` (Python) or `ed25519-dalek` (Rust).
* **Canonical Encoding:** All inputs to signing operations are serialized strictly in compliance with RFC 8785 JSON Canonicalization Scheme (JCS) with UTF-16 code unit sorting to ensure byte-level deterministic signatures across heterogeneous runtimes.

---

### 3. Custody, Memory Protection & Multi-Party Quorum

#### 3.1 Memory Protection & Zeroization
* Key material loaded into daemon memory must be allocated in non-swappable pages (`mlock(2)`).
* Rust implementations utilize the `zeroize` crate (`zeroize::ZeroizeOnDrop`) to overwrite private scalar bytes with zeroes upon termination.
* Core dumps and memory crash artifacts are configured to exclude cryptographic memory buffers (`MADV_DONTDUMP`).

#### 3.2 Multi-Party Quorum for Privileged Operations
Privileged governance operations require multi-party threshold authorization (2-of-3 quorum):
* **Un-latching a `HALT_*` State (`SupervisorRecoveryWarrant`):**  
  Releasing a locked execution gateway requires digital signatures from at least two authorized supervisors (e.g., CISO Delegate + Lead Infrastructure Engineer).
* **Policy Epoch Increment (`policy_epoch`):**  
  Deploying a new policy epoch that invalidates previous delegations requires dual cryptographic authorization.
* **Emergency Revocation:**  
  Publishing a revocation notice for a compromised `did:key` requires quorum sign-off before Station 1 updates its local rejection cache.

---

### 4. Key Revocation & Compromise Response

If a private key is compromised or suspected of exposure:

1. **Immediate Revocation Broadcast:**  
   The Security Officer broadcasts an Ed25519-signed `RevocationNotice` containing the compromised public key thumbprint (`jkt = base64url(sha256(JCS(jwk)))`).
2. **Station 1 Rejection Cache Update:**  
   Station 1 inserts the revoked thumbprint into its local in-memory denylist and increments the active `policy_epoch`. Any token presenting the revoked key or issued under the prior epoch is rejected immediately fail-closed.
3. **Escrow Liquidation / Freeze:**  
   Any in-flight operations authorized by the compromised key that reside in `EFFECT_INDETERMINATE` are placed into frozen status pending manual administrative review.
4. **Key Replacement & Re-issuance:**  
   A new key pair is generated inside the HSM/KMS; root policy certificates are regenerated and distributed.

---

### 5. Post-Quantum Cryptographic (PQC) Agility Roadmap

In alignment with the NSA Commercial National Security Algorithm Suite 2.0 (CNSA 2.0) guidelines and IETF draft specifications:

* **Cryptographic Bill of Materials (CBOM):**  
  AEIB maintains an automated CycloneDX 1.6 CBOM ([`evidence/cbom.json`](file:///Users/andriileukhin/Documents/SovereignNexus/evidence/cbom.json)) cataloging all active primitives (`Ed25519`, `SHA-256`, `RFC-8785-JCS`, `RFC-9162-Merkle`).
* **Hybrid Dual-Signature Envelopes:**  
  AEIB defines the composite envelope profile (`draft-ietf-jose-pq-composite-sigs` / `COSE_ALG_COMPOSITE_ED25519_ML_DSA_65 = -65537`), combining classical Ed25519 (`alg: -8`) with post-quantum lattice signature **ML-DSA-65 (`alg: -49`)** (NIST FIPS 204).
* **Standards-Tracking Status:**  
  In environments lacking external C-lattice libraries (`liboqs`), ML-DSA-65 is explicitly classified as an architectural transition target, while Ed25519 provides active local enforcement.
