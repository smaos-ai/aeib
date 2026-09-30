# AEIB Target Architecture & Evolution Roadmap (v0.3+)
## Resolving the 10 Prototype Boundaries via the Three-Layer Substrate

**Standard:** Agent Execution Integrity Benchmark (AEIB)  
**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus)  
**Classification:** Post-v0.2 Architectural Roadmap  
**Scope:** Formal engineering blueprint mapping the 10 prototype limitations to concrete kernel, cryptographic, and hardware primitives.

---

## 🗺️ The Three-Layer Target Substrate

The 10 acknowledged limitations of the v0.2 synthetic prototype map into three distinct production layers:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              THE THREE-LAYER TARGET SUBSTRATE                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER A: KERNEL & PHYSICAL WIRE ENFORCEMENT                                            │
│ • Item 1: Real Socket Interception (eBPF XDP/TC)                                       │
│ • Item 2: Real Out-of-Band Ledger Probes (PostgreSQL/DuckDB bitemporal)                │
│ • Item 3: Physical Retry Suppression (BPF LSM bprm_check_security)                     │
│ • Item 9: MCP Sidecar Integration (Pre-dispatch Admissible(a) gate)                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER B: CRYPTOGRAPHIC & STANDARDS CONFORMANCE                                         │
│ • Item 4: Strict RFC 8785 JCS Compliance (Byte-exact UTF-16 code-unit key sort)        │
│ • Item 5: RFC 9052 COSE_Sign1 Envelopes (CBOR application/scitt-statement+cose)        │
│ • Item 6: IETF SCITT Integration (RFC 9943 Transparency Service & RFC 9942 proofs)     │
│ • Item 10: HSM / KMS Key Management (PKCS#11 & FIPS 140-2 Level 3, ML-DSA-65)         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER C: SUBSTRATE ATTESTATION & STATUTORY BINDING                                     │
│ • Item 7: Hardware Attestation (TRACE, Intel TDX TDREPORT, AMD SEV-SNP 64-byte nonce) │
│ • Item 8: DORA Incident Class Mapping (CDR (EU) 2024/1772 & EBA DPM 4.0 RT.01.01)     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ 1. Layer A: Kernel & Physical Wire Enforcement (Items 1, 2, 3, 9)

### 1.1 Real Socket Interception & Retry Suppression (Items 1 & 3)
* **Architecture**: Replaces userspace Python middleware with eBPF XDP/TC driver-level hooks (`xdp_drop.c`) and BPF LSM (`bprm_check_security`).
* **Operational Invariant**: When a transport socket drops (`HTTP 504`, `TCP RST`, or `stdio_broken_pipe`), the kernel driver physically drops unhedged retry packets before they reach userspace, freezing the loop at $T_0$.
* **Driver Mechanism**: Attaches to the network device interface at the driver or generic XDP layer, inspecting TCP state flags and aborting packet transmission on unverified retries.

### 1.2 Real Out-of-Band Ledger Probes (Item 2)
* **Architecture**: Replaces synthetic adapter mocks with direct queries to downstream registers (PostgreSQL/DuckDB bitemporal ledgers, core banking reconciliation APIs, or target OS accessibility trees).
* **Operational Invariant**: Uses the `idempotency_key_uuidv5` to query downstream transaction commit state, verifying physical execution state before releasing retries or granting clearance.

### 1.3 MCP Sidecar Integration (Item 9)
* **Architecture**: Embeds the pre-dispatch $\text{Admissible}(a)$ gate directly into an out-of-process MCP proxy sidecar wrapping stdio and HTTP transports (`mcp://...`).
* **Operational Invariant**: Evaluates context lineage, authority freshness, and blast radius before tool execution, passing only verified JSON-RPC payloads to downstream servers.

---

## 🔐 2. Layer B: Cryptographic & Standards Conformance (Items 4, 5, 6, 10)

### 2.1 RFC 8785 JCS Compliance (Item 4)
* **Architecture**: Implements strict, byte-exact JSON Canonicalization Scheme (JCS) parsers conforming to RFC 8785.
* **Operational Invariant**: Guarantees UTF-16 code-unit key sorting and IEEE 754 numeric normalization, deriving identical SHA-256 digests across Python, Rust, WASM, and Go environments.

### 2.2 RFC 9052 COSE_Sign1 Envelope (Item 5)
* **Architecture**: Transitions the receipt format from plain JSON into binary CBOR-encoded `application/scitt-statement+cose` objects.
* **Operational Invariant**: Includes protected header parameters (`alg`, `cty`, `iss`, `sub`), encapsulating payload claims in a standardized, tamper-evident cryptographic envelope.

### 2.3 IETF SCITT Integration (Item 6)
* **Architecture**: Integrates with an append-only Transparency Service conforming to IETF SCITT (RFC 9943) (e.g., Microsoft CCF or Linux Foundation Sigstore/Rekor).
* **Operational Invariant**: Registers COSE_Sign1 statements and returns an `application/scitt-receipt+cose` inclusion receipt (RFC 9942) containing verifiable Merkle tree inclusion proofs.

### 2.4 HSM / KMS Key Management (Item 10)
* **Architecture**: Binds signing keys to PKCS#11 Hardware Security Modules (HSM) or cloud KMS endpoints certified to FIPS 140-2/3 Level 3.
* **Operational Invariant**: Ensures Ed25519 and post-quantum ML-DSA-65 (FIPS 204) private signing keys remain non-exportable within hardware security boundaries.

---

## 🏛️ 3. Layer C: Substrate Attestation & Statutory Binding (Items 7, 8)

### 3.1 Hardware Attestation (TRACE, TDX, SEV-SNP) (Item 7)
* **Architecture**: Runs the verification runtime inside a Confidential Virtual Machine (CVM).
* **Operational Invariant**: The CPU hardware root-of-trust generates a cryptographically signed hardware quote (Intel TDX `TDREPORT` or AMD SEV-SNP attestation report), binding the 64-byte `REPORTDATA` nonce directly to the receipt payload hash.
* **Attestation Scope**: Proves execution integrity and memory isolation even if the host hypervisor or operating system is compromised.

### 3.2 DORA Incident Class Mapping (Item 8)
* **Architecture**: Connects execution receipts directly to the 7 materiality criteria of Commission Delegated Regulation (EU) 2024/1772.
* **Operational Invariant**: Pre-fills mandatory DORA Article 17 major ICT incident notifications and EBA DPM 4.0 Register of Information tables (`RT.01.01`–`RT.02.01`), linking technical socket failures directly to supervisory classification thresholds.
