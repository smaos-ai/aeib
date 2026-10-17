# AEIB External Verifiability & Post-Quantum Cryptographic Agility Specification (October 2026)

**Status:** Evaluated Reference Profile (October 2026)  
**Scope:** Directive 2 (IETF SCITT RFC 9942 / RFC 9943 + RFC 9052 `COSE_Sign1` + OpenTelemetry GenAI Interop) & Directive 4 (NSA CNSA 2.0 / 2027 PQC Readiness, RFC 9964 COSE ML-DSA, Hybrid Composite PQ/T Signatures, and CycloneDX 1.6 CBOM)  
**Implementation Module:** [`src/cbom_and_scitt_otel_exporter.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/cbom_and_scitt_otel_exporter.py)  
**Verification Suite:** [`tests/test_scitt_otel_and_pqc_cbom_agility.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tests/test_scitt_otel_and_pqc_cbom_agility.py)  
**Generated CBOM Artifact:** [`evidence/cbom.json`](file:///Users/andriileukhin/Documents/SovereignNexus/evidence/cbom.json)

---

## 1. Executive Summary & Epistemic Boundaries

Under the stated model, the Agent Execution Integrity Boundary (AEIB) addresses two structural requirements for autonomous agent execution telemetry and long-horizon cryptographic verifiability:

1. **Elimination of Host-Local Ledger Trust (Directive 2):** Rather than requiring an external auditor to trust a mutable local `ledger.jsonl` file on the agent host, AEIB encodes Station 1 (pre-execution admission) and Station 3 (post-execution settlement) receipts as RFC 9052 `COSE_Sign1` (CBOR Tag 18) signed statements, registers them in an RFC 9943 SCITT Transparency Service backed by an RFC 9162 SHA-256 binary Merkle tree, attaches RFC 9942 binary COSE Receipts (`394` `receipts`, `395` `vds=1`, `396` `vdp`), and exports the resulting Transparent Statement and Merkle inclusion metadata directly inside OpenTelemetry GenAI `execute_tool` spans (`gen_ai.operation.name = "execute_tool"`).
2. **Post-Quantum Cryptographic Agility & CycloneDX 1.6 CBOM (Directive 4):** To align with the NSA CNSA 2.0 timeline (2027 mandate for CNSA 2.0 post-quantum algorithms across national security systems) and IETF RFC 9964 (`ML-DSA` for JOSE and COSE), AEIB implements a strict COSE algorithm registry and produces an Ed25519-signed **CycloneDX 1.6 Cryptographic Bill of Materials (`evidence/cbom.json`)** cataloging every cryptographic primitive, parameter set, execution environment, and NIST quantum security category active in the runtime.

### Epistemic Boundary Declaration

In accordance with `AGENTS.md`:
- In runtime environments where only Python standard library (`hashlib`) and `cryptography` (`OpenSSL`) are installed without external `liboqs` C-extensions, **Ed25519 (`alg = -8`)**, **SHA-256**, **SHAKE-256**, **RFC 8785 JCS**, and **RFC 9162 SHA-256 Merkle trees** are executed natively using real cryptographic primitives (`cryptography.hazmat.primitives.asymmetric.ed25519` and `hashlib`).
- The **ML-DSA-65 (`alg = -49`)** and **Composite `Ed25519 + ML-DSA-65` (`alg = -65537`)** post-quantum slots are explicitly tracked in the algorithm negotiation table and tagged in `evidence/cbom.json` with their exact `implementationLevel` and `executionEnvironment` (`scaffold` when an external C-lattice provider such as `liboqs` or OpenSSL 3.5+ `EVP_PKEY_ML_DSA_65` is absent, or active `software` when detected at runtime).
- Zero fake or simulated signatures are ever emitted: if a caller requests signing or verification with an algorithm whose native cryptographic provider is unavailable or downgraded, the gate halts fail-closed (`HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG`).

---

## 2. Directive 2: IETF SCITT (RFC 9942 / RFC 9943) + RFC 9052 `COSE_Sign1` + OpenTelemetry GenAI Interop

### 2.1 Why Local `ledger.jsonl` Files Are Insufficient for External Auditors

A hash-chained JSONL file stored on the same host as the agent runtime remains vulnerable to whole-file truncation or tail-rewriting by a privileged host process prior to external export. IETF SCITT (**RFC 9943**, *An Architecture for Trustworthy and Transparent Digital Supply Chains*, and **RFC 9942**, *COSE Receipts for Verifiable Data Structures*) solves this by anchoring each signed statement in an external append-only Merkle tree and returning a compact, cryptographically verifiable inclusion receipt.

### 2.2 Binary `COSE_Sign1` Transparent Statement Construction

For every tool execution evaluated at Station 1 and Station 3:

1. **Canonical Receipt Serialization (RFC 8785 JCS):**
   The receipt dictionary is serialized into deterministic UTF-8 bytes via [`encode_jcs()`](file:///Users/andriileukhin/Documents/SovereignNexus/src/jcs_canonicalizer.py#L166-L179), and its SHA-256 content-addressable identifier (`payload_caid`) is computed.
2. **Issuer Signing (`COSE_Sign1`, CBOR Tag 18, RFC 9052):**
   [`RFC9052CoseSigner`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/rfc9052_cose_profile.py#L354-L418) signs the JCS payload over the canonical `Sig_structure`:
   ```text
   Sig_structure = ["Signature1", body_protected, external_aad, payload_bytes]
   ```
   with Protected Header `1 (alg): -8 (EdDSA)` and Unprotected Header `4 (kid): <issuer_kid>`.
3. **SCITT Transparency Service Registration (RFC 9943 / RFC 9942):**
   [`SCITTTransparencyService.issue_binary_cose_receipt()`](file:///Users/andriileukhin/Documents/SovereignNexus/tools/verify_cose_scitt_receipts.py#L235-L283) verifies the issuer's signature against the registration policy, appends the `COSE_Sign1` bytes to the RFC 9162 binary Merkle tree (`leaf_hash = SHA-256(0x00 || statement_cbor)`, `node_hash = SHA-256(0x01 || left || right)`), and signs the 32-byte Merkle root inside an RFC 9942 COSE Receipt (`Tag 18`) containing:
   - **Protected Header `1` (`alg`):** `-8` (`EdDSA`)
   - **Protected Header `4` (`kid`):** `scitt-ts:<service_id>`
   - **Protected Header `395` (`vds`):** `1` (`RFC9162_SHA256` Verifiable Data Structure)
   - **Unprotected Header `396` (`vdp`):** Verifiable Data Structure Proof map:
     - `-1` (`tree-size`): total leaf count $N$
     - `-2` (`leaf-index`): 0-based leaf position $m$
     - `-3` (`inclusion-path`): array of 32-byte sibling hashes (`[+ bstr]`)
   - **Payload:** 32-byte RFC 9162 Merkle tree root hash (`bstr .size 32`)
4. **Transparent Statement Assembly:**
   [`append_receipt_to_signed_statement()`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/rfc9052_cose_profile.py#L732-L789) embeds the binary COSE Receipt into the outer statement's **Unprotected Header `394` (`receipts`)** without mutating the issuer's protected headers or payload signature.

### 2.3 OpenTelemetry GenAI `execute_tool` Span Schema

[`SCITTAnchoredOTelGate.record_tool_execution_span()`](file:///Users/andriileukhin/Documents/SovereignNexus/src/cbom_and_scitt_otel_exporter.py) emits a standardized OpenTelemetry GenAI telemetry span (`gen_ai.operation.name = "execute_tool"`) carrying both the standard `gen_ai.*` semantic conventions and the `aeib.scitt.*` transparency attributes:

| Attribute Key | Type | Description |
| :--- | :--- | :--- |
| `gen_ai.operation.name` | `string` | Always `"execute_tool"` per OpenTelemetry GenAI semantic conventions |
| `gen_ai.tool.name` | `string` | Identifier of the tool or actuator invoked |
| `gen_ai.tool.call.id` | `string` | Deterministic execution correlation ID |
| `aeib.station.id` | `string` | `"station_1_pre_exec"` or `"station_3_post_exec"` |
| `aeib.receipt.caid_sha256` | `string` | 64-hex SHA-256 digest of the RFC 8785 JCS receipt payload |
| `aeib.crypto.cose_alg` | `int` | IANA COSE algorithm ID (`-8` for `EdDSA`) |
| `aeib.scitt.service_id` | `string` | SCITT Transparency Service identifier |
| `aeib.scitt.vds` | `int` | `1` (RFC 9162 SHA-256 binary Merkle tree per RFC 9942) |
| `aeib.scitt.merkle_root_sha256` | `string` | 64-hex RFC 9162 Merkle root signed by the Transparency Service |
| `aeib.scitt.leaf_index` | `int` | 0-based leaf index in the SCITT log (`VDP[-2]`) |
| `aeib.scitt.tree_size` | `int` | SCITT Merkle tree size at registration (`VDP[-1]`) |
| `aeib.scitt.transparent_statement_b64` | `string` | Standard Base64 encoding of the Tag 18 Transparent Statement |
| `aeib.scitt.receipt_cose_b64url` | `string` | Base64url (no padding) encoding of the Tag 18 Transparent Statement |

### 2.4 Offline External Auditor Verification (`iFixAi` Workflow)

An external verifier (such as an `iFixAi` audit node) holding **only** the exported OpenTelemetry span and the pinned SCITT Merkle root (`expected_merkle_root_hex`) calls [`SCITTAnchoredOTelGate.verify_otel_span_against_external_scitt_root()`](file:///Users/andriileukhin/Documents/SovereignNexus/src/cbom_and_scitt_otel_exporter.py). This function:
1. Confirms `gen_ai.operation.name == "execute_tool"` and validates the COSE algorithm header via `COSEAlgorithmRegistry`.
2. Decodes the embedded binary `COSE_Sign1` Transparent Statement from the span without reading any local `ledger.jsonl` file.
3. Executes [`verify_binary_transparent_statement()`](file:///Users/andriileukhin/Documents/SovereignNexus/tools/verify_cose_scitt_receipts.py#L334-L528) to verify the issuer's Ed25519 signature, the Transparency Service's Ed25519 signature over the receipt, Protected Header `395 == 1`, and the RFC 9162 Merkle inclusion path in Unprotected Header `396`.
4. Verifies that the cryptographically reconstructed Merkle root matches both `span["attributes"]["aeib.scitt.merkle_root_sha256"]` and the auditor's pinned `expected_merkle_root_hex`, and that the inner payload matches `aeib.receipt.caid_sha256`.

---

## 3. Directive 4: CNSA 2.0 / 2027 PQC Mandate, RFC 9964 COSE ML-DSA, & CycloneDX 1.6 CBOM

### 3.1 IANA COSE Algorithm Identifiers & Hybrid PQ/T Profile

[`COSEAlgorithmRegistry`](file:///Users/andriileukhin/Documents/SovereignNexus/src/cbom_and_scitt_otel_exporter.py) codifies the official IANA COSE Algorithm Identifiers from RFC 9053 and **RFC 9964** (*Use of ML-DSA in JOSE and COSE*):

| Constant | IANA COSE `alg` ID | Primitive & Parameter Set | Classical / NIST Quantum Security | Runtime Status in Stdlib + `OpenSSL` Profile |
| :--- | :--- | :--- | :--- | :--- |
| `COSE_ALG_EDDSA` | `-8` | Ed25519 (RFC 8032 / RFC 9053) | 128-bit classical / Category 0 | Active (`cryptography.hazmat` native) |
| `COSE_ALG_ESP256` | `-9` | ECDSA P-256 + SHA-256 (RFC 9053) | 128-bit classical / Category 0 | Cataloged (non-default) |
| `COSE_ALG_ML_DSA_44` | `-48` | FIPS 204 `ML-DSA-44` (RFC 9964) | 128-bit classical / NIST Category 2 | PQC target profile (requires lattice provider) |
| `COSE_ALG_ML_DSA_65` | `-49` | FIPS 204 `ML-DSA-65` (RFC 9964, CNSA 2.0 baseline) | 192-bit classical / NIST Category 3 | PQC target profile (requires lattice provider) |
| `COSE_ALG_ML_DSA_87` | `-50` | FIPS 204 `ML-DSA-87` (RFC 9964, CNSA 2.0 high) | 256-bit classical / NIST Category 5 | PQC target profile (requires lattice provider) |
| `COSE_ALG_COMPOSITE_ED25519_ML_DSA_65` | `-65537` | Non-separable Composite `Ed25519 + ML-DSA-65` (`draft-ietf-jose-pq-composite-sigs`) | 128-bit classical + NIST Category 3 | Hybrid PQ/T profile (Ed25519 active + ML-DSA-65 slot) |

### 3.2 Non-Separable Composite PQ/T Signature Envelope (`Ed25519 + ML-DSA-65`)

To prevent stripping attacks during the classical-to-PQC transition, AEIB defines a domain-separated composite signature commitment schedule aligned with `draft-ietf-jose-pq-composite-sigs`:
- **Transcript Pre-Hashing:** Both component signers bind to a shared SHAKE-256 (64-byte) and SHA-256 domain-separated message transcript over the canonical `Sig_structure`:
  $$\text{Transcript} = \text{ASCII}(\text{"AEIB-COMPOSITE-ED25519-MLDSA65-V1"}) \parallel \text{SHAKE256}_{512}(\text{Sig\_structure})$$
- **Strict Negotiation (`COSEAlgorithmRegistry.negotiate_cose_alg`):**
  - Unknown algorithm identifiers, `alg = 0` (`none`), or legacy SHA-1 / RSA algorithms immediately raise a fail-closed `HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG` error.
  - Requesting `-48`, `-49`, `-50`, or `-65537` when `require_active_provider=True` and no runtime C-lattice backend (`liboqs` or OpenSSL 3.5+ `ML-DSA`) is present halts fail-closed (`HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG`) rather than substituting a simulated signature.

### 3.3 CycloneDX 1.6 Cryptographic Bill of Materials (`evidence/cbom.json`)

[`CycloneDX16CBOMGenerator`](file:///Users/andriileukhin/Documents/SovereignNexus/src/cbom_and_scitt_otel_exporter.py) inspects the live Python runtime (`ssl.OPENSSL_VERSION`, `cryptography.__version__`, and lattice provider availability) and writes a deterministic **CycloneDX 1.6** manifest to [`evidence/cbom.json`](file:///Users/andriileukhin/Documents/SovereignNexus/evidence/cbom.json):

- **Top-Level Fields:**
  - `bomFormat`: `"CycloneDX"`
  - `specVersion`: `"1.6"`
  - `serialNumber`: deterministic `urn:uuid:...` derived from the canonical component inventory
  - `version`: `1`
- **Cryptographic Asset Components (`type: "cryptographic-asset"`):**
  1. `crypto/alg/ed25519-cose-alg--8`: Active Ed25519 (`alg = -8`, `primitive: "signature"`, `implementationLevel: "software"`, `classicalSecurityLevel: 128`, `nistQuantumSecurityCategory: 0`).
  2. `crypto/alg/sha256-fips180-4`: Active SHA-256 (`primitive: "hash"`, `parameterSetIdentifier: "256"`, `classicalSecurityLevel: 256`, `nistQuantumSecurityCategory: 1`).
  3. `crypto/alg/shake256-fips202`: Active SHAKE-256 XOF (`primitive: "xof"`, `parameterSetIdentifier: "256"`, `classicalSecurityLevel: 256`, `nistQuantumSecurityCategory: 2`).
  4. `crypto/protocol/rfc8785-jcs`: Active RFC 8785 JSON Canonicalization Scheme (`assetType: "protocol"`).
  5. `crypto/protocol/rfc9162-rfc9942-merkle-vds-1`: Active RFC 9162 / RFC 9942 SHA-256 Binary Merkle Tree (`assetType: "protocol"`, `vds = 1`).
  6. `crypto/alg/ml-dsa-65-cose-alg--49`: FIPS 204 `ML-DSA-65` (`alg = -49`, `primitive: "signature"`, `parameterSetIdentifier: "65"`, `classicalSecurityLevel: 192`, `nistQuantumSecurityCategory: 3`, tagged with its exact runtime `implementationLevel` and `executionEnvironment`).
  7. `crypto/alg/composite-ed25519-mldsa65`: Hybrid Composite `Ed25519 + ML-DSA-65` (`alg = -65537`, `primitive: "combiner"`, `nistQuantumSecurityCategory: 3`).
- **Cryptographic Attestation (`attestation_signature`):**
  The entire CBOM payload (excluding the signature block itself) is canonicalized via [`encode_jcs()`](file:///Users/andriileukhin/Documents/SovereignNexus/src/jcs_canonicalizer.py#L166-L179), hashed with SHA-256, and signed with a real Ed25519 private key so any downstream auditor can verify the CBOM's integrity via `CycloneDX16CBOMGenerator.verify_cbom_manifest()`.
