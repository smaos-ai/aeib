# IP Architecture & Dual-Licensing Boundary Specification

**Project:** SovereignNexus / SMAOS (Sovereign Multi-Agent Operating System)  
**Document Version:** 1.0.0  
**Status:** Locked & Authoritative  
**Open Core DOI:** [`pending-deposit`](https://doi.org/pending-deposit)  
**Primary Contact:** Andrii Leukhin (`andrejlo123@gmail.com`)  

---

## 1. Executive Summary

SovereignNexus establishes a deterministic, dual-zoned intellectual property (IP) architecture designed to simultaneously achieve two vital strategic goals:
1. **Public Prior Art Preemption (Zone 1 — Open Core)**: Block aggressive patent trolling and establish an open, mathematically verifiable execution integrity standard for autonomous agent workflows under the **Apache License 2.0**.
2. **Commercial Value Capture & Defensibility (Zone 2 — Enterprise Proprietary)**: Retain enterprise-grade, high-concurrency database connection pooling, confidential hardware attestation, and compliance export pipelines under a **Proprietary Commercial License**.

This dual-track model guarantees that enterprise CISOs, auditors, and platform engineers can inspect, verify, and embed the core execution boundary without fear of copyleft contamination, while proprietary production scaling technologies remain commercial assets of SovereignNexus.

---

## 2. Module-Level Separation Matrix

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                      MODULE-LEVEL IP & DUAL-LICENSING BOUNDARY MATRIX                       │
├───────────────────────────────┬───────────────────────────────┬─────────────────────────────┤
│ Operational Zone & License    │ Module / File Artifact        │ Strategic & Technical Scope │
├───────────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ **Zone 1: Open Core**         │ • `docs/transport-to-`        │ Normative 15-vector wire    │
│ (Apache License 2.0)          │   `disposition-mapping.yaml`  │ fault-to-disposition rules. │
│ DOI: `pending-deposit`│ • `src/aeib_core/` (or        │ RFC 8785 JCS payload        │
│                               │   `aei_core/`)                │ canonicalization & CAID     │
│                               │ • `src/protection_governor.py`│ derivation logic.           │
│                               │ • `aeib_verify.py` /          │ Industrial-protection-      │
│                               │   `dist/smaos_verify.wasm`    │ inspired pattern governor.  │
│                               │ • `benchmarks/` & `tests/`    │ Standalone offline verifier │
│                               │                               │ & 500-episode harness.      │
├───────────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ **Zone 2: Enterprise**        │ • `aeib_postgresql_probe/`    │ High-concurrency prober with│
│ (Proprietary / Trade Secret)  │   `pg_probe_adapter.py`       │ connection lease pooling.   │
│ Commercial License            │ • `smaos_dora_kit.py` & GRC   │ Automated DORA/EU AI Act    │
│                               │   Regulatory Exporters        │ prefill & xBRL-CSV bundler. │
│                               │ • `pkcs11_hsm_enclave.py`     │ HSM key custody & Intel TDX/│
│                               │ • Multi-Tenant RLS & Auth     │ AMD SEV-SNP attestation.    │
└───────────────────────────────┴───────────────────────────────┴─────────────────────────────┘
```

---

## 3. Zone 1: Open Core Specification (Apache 2.0)

Zone 1 comprises the foundational protocol specifications, cryptographic derivation engines, offline verification utilities, and reproducible scientific benchmarks. It is published under the permissive **Apache License 2.0** and indexed on Zenodo under DOI [`pending-deposit`](https://doi.org/pending-deposit).

### Technical Scope & Invariants
* **Normative Wire-to-Disposition Mapping Contract (`docs/transport-to-disposition-mapping.yaml`)**: The authoritative priority-ordered hierarchy translating 15 physical network and database faults into deterministic dispositions (`DISPATCHED_UNCONFIRMED`, `OUTCOME_VERIFIED`, `RECONCILIATION_NOT_FOUND`, `RECONCILIATION_CONFLICT`, `PROBE_TIMEOUT`, `PROBE_EXCEPTION`, `READ_ONLY_REPLICA_REJECTED`) and binding retry policies.
* **Cryptographic Action Identity (`aei_core/` / `src/aeib_core/`)**:
  - Implements the Canonical Action Identifier (CAID) using RFC 8785 JSON Canonicalization Scheme (JCS) and SHA-256:
    $$\text{CAID} = H\Big(\text{Noun}_{\text{EntityID}} \parallel \text{Verb}_{\text{Action}} \parallel \text{JCS}(\text{Payload})\Big)$$
  - Renders action identity invariant against LLM prompt formatting, dictionary key permutation, and semantic drift.
* **Industrial-Protection-Inspired Governor (`src/protection_governor.py`)**:
  - Encapsulates software-level execution safeguards inspired by grid protection principles:
    - *Probe-failure escalation pattern*: Multi-tier cascade from primary to secondary to tertiary fallback.
    - *Manual lockout latch*: Terminal state transition requiring authenticated operator signature to reset.
    - *Peer cancellation pattern*: Swarm-wide transfer tripping to halt in-flight companion actions.
    - *Retry-oscillation detector*: Sliding-window detection of cyclic retry loops.
    - *Payload-integrity differential check*: Instant trip on single-byte payload/ledger discrepancy.
    - *Execution sequence/fault/disturbance records*: High-resolution forensic telemetry under ISO/IEC 42001 and EU AI Act Art. 12.
* **Offline Verification Suite (`aeib_verify.py` & `smaos_verify.wasm`)**:
  - Cryptographically verifies SCITT receipt chains against mapping contracts with zero network calls and 0 bytes cloud egress.
* **Scientific Benchmark Suite (`benchmarks/` & `tests/`)**:
  - 500-episode reproducible benchmark (`run_episodes.py --seed 42`).
  - Zero-mock falsifiability test matrix (`tests/test_falsifiability_matrix.py`).
  - Two-phase saga compensation suite (`tests/test_saga_compensation.py`).

---

## 4. Zone 2: Enterprise Commercial Specification (Proprietary)

Zone 2 contains mission-critical, enterprise-grade runtime infrastructure designed for Tier-1 financial institutions, critical infrastructure operators, and regulated healthcare platforms. These components are licensed under the **SovereignNexus Commercial License** and are treated as protected trade secrets.

### Technical Scope & Commercial Assets
* **Production PostgreSQL Prober (`aeib_postgresql_probe/pg_probe_adapter.py`)**:
  - **Connection Lease Pooling**: Prevents connection exhaustion in high-concurrency agent environments through stack-bounded lease contexts and `@contextmanager get_connection()` guards.
  - **Session-Level Statement Timeout**: Enforces mandatory session-level isolation (`options='-c statement_timeout=3000'`) avoiding PostgreSQL `SET LOCAL` autocommit traps.
  - **Sub-3ms B-tree `UNION ALL` Optimizations**: Executes lightning-fast B-tree index scans over compound ledger keys without triggering expensive full table sequential scans.
  - **Read-Replica Fencing**: Actively inspects `SHOW transaction_read_only` to reject asynchronous replica stale reads and automatically redirect out-of-band verification to the primary writer.
* **Regulatory Exporters & DORA Sufficiency Engine (`smaos_dora_kit.py`)**:
  - Automated compliance generation pre-filling EU DORA Chapter V (Art. 28 ICT Third-Party Risk register) and Annex IV templates.
  - EU AI Act Article 14(4) and Article 12 compliance pack compiler generating certified xBRL-CSV regulatory archives.
* **Hardware Security Module Enclave (`pkcs11_hsm_enclave.py`)**:
  - **Zero-RAM Key Custody**: Private keys are locked into hardware tokens (`CKA_EXTRACTABLE = CK_FALSE`), accepting only 32-byte RFC 8785 digests across C-ABI boundaries.
  - **Statutory CRO Execution Permits**: Enforces 1-hour time-to-live windows and approver DID cryptographic binding under EU AI Act Art. 14(4).
  - **Emergency Hardware Line-Stop**: Immediate physical interlock tripping on anomalous drift detection.
  - **Confidential VM Attestation**: Scaffolding for Intel TDX (`/dev/tdx_guest`) and AMD SEV-SNP (`/dev/sev-guest`) measurement chains.
* **Multi-Tenant Row-Level Security (RLS) & Directory Bridge**:
  - Scoped value context propagation (JEP 506 / ScopedContext) binding tenant IDs and principal DIDs without thread-local memory leakage.

---

## 5. Legal Hygiene Protocols & Clean Import Rules

To preserve absolute legal separation and protect enterprise licensees from IP contamination, all developers, contributors, and subagents must adhere to the following four structural hygiene rules:

### Rule 1: Strictly Unidirectional Dependency
```
┌─────────────────────────────────┐
│     Zone 2: Enterprise          │  (Imports Zone 1 contracts, CAID,
│     (Commercial / Proprietary)  │   and verifier logic)
└────────────────┬────────────────┘
                 │
                 │   ALLOWED: Zone 2 imports Zone 1
                 ▼
┌─────────────────────────────────┐
│     Zone 1: Open Core           │  (Zero imports of Zone 2;
│     (Apache 2.0 Open Source)    │   100% standalone execution)
└─────────────────────────────────┘
```
* **Zone 2 may freely import Zone 1**: Enterprise adapters use the open mapping contract, JCS serialization, and disposition taxonomy.
* **Zone 1 MUST NEVER import Zone 2**: Core modules (`aei_core`, `src/protection_governor.py`, `aeib_verify.py`, benchmark runners) must execute completely standalone with zero imports of `aeib_postgresql_probe`, `smaos_dora_kit`, or `pkcs11_hsm_enclave`.
* **Automated CI Enforcement**: Any pull request introducing a circular or upward import from Zone 1 to Zone 2 is automatically rejected by AST compliance scanners.

### Rule 2: Explicit License Headers
* Every file belonging to Zone 1 must start with the standard Apache 2.0 header:
  ```python
  # Copyright 2026 SovereignNexus Project
  # Licensed under the Apache License, Version 2.0 (the "License");
  # you may not use this file except in compliance with the License.
  ```
* Every file belonging to Zone 2 must start with the Sovereign Commercial Notice:
  ```python
  # Copyright 2026 SovereignNexus. All Rights Reserved.
  # PROPRIETARY AND TRADE SECRET — UNAUTHORIZED COPYING, DISTRIBUTION,
  # OR DECOMPILATION STRICTLY PROHIBITED.
  ```

### Rule 3: Repository Packaging & Distribution Isolation
* Open-source distributions (`pip`, Zenodo archives, GitHub public tags) package **Zone 1 exclusively**.
* Commercial enterprise distributions (`dist/aeib-enterprise-v1.0.tar.gz`) package the combined runtime under commercial contract.

---

## 6. Strategic IP Protection & Prior Art Defense

By depositing Zone 1 core specifications, CAID derivation mechanics, out-of-band state probing abstractions, and empirical benchmarks onto **Zenodo** under permanent DOI [`pending-deposit`](https://doi.org/pending-deposit), SovereignNexus achieves:

1. **Immutable Prior Art Timestamps**: Zenodo deposits are preserved in CERN's high-assurance data centers and indexed by DataCite and CrossRef. This provides undeniable legal proof of prior art.
2. **Defensive Patent Invalidation**: Under 35 U.S.C. § 102 (US) and Article 54 EPC (Europe), any patent application filed by competitors covering deterministic agent post-dispatch reconciliation, Noun/Verb CAID derivation, or outbox state probing will be rejected for lack of novelty.
3. **Enterprise Freedom-to-Operate (FTO)**: Customers adopting SovereignNexus Zone 1 or Zone 2 technology are shielded by a robust, publicly verifiable body of prior art.

---

## 7. CISO & Legal Licensing FAQ

### Q1: Does using Zone 1 open-source code obligate us to open-source our enterprise software?
**No.** Zone 1 is distributed under the **Apache License 2.0**, which is a permissive, non-copyleft license. Incorporating Zone 1 mapping contracts, CAID utilities, or offline receipt verifiers into your internal microservices, agent frameworks, or proprietary applications does not obligate you to disclose or open-source your proprietary application code or database schemas.

### Q2: Can we verify execution receipts without exposing database state or PII to SovereignNexus?
**Yes.** Both the standalone Python verifier (`aeib_verify.py`) and the WebAssembly verifier (`dist/smaos_verify.wasm`) execute **100% offline inside your security perimeter**. They evaluate cryptographic hash chains and Ed25519 signatures locally with **0 bytes of external cloud egress**. No database records, customer PII, or internal tokens ever leave your infrastructure.

### Q3: Why is the production database prober (`pg_probe_adapter.py`) in Zone 2?
Zone 1 defines the abstract probing contract and offline verification semantics. Zone 2 contains the production-hardened, battle-tested implementation engineered for high-concurrency enterprise workloads. This includes connection lease pooling, defensive statement timeout enforcement (`statement_timeout=3000`), sub-3ms B-tree `UNION ALL` index scans, and active read-replica fencing to eliminate connection pool starvation and stale reads under heavy transaction volume.

### Q4: How does Zone 1 publication protect our organization against third-party patent litigation?
By publishing the Zone 1 specifications and benchmark harnesses to Zenodo under DOI [`pending-deposit`](https://doi.org/pending-deposit), SovereignNexus creates globally timestamped prior art. International patent offices (such as the USPTO, EPO, and JPO) actively search Zenodo and scientific preprint repositories. Any subsequent patent claim by third parties attempting to patent these core agent idempotency and state-probing mechanisms will be rejected as anticipated or obvious.

### Q5: How can our organization license Zone 2 Enterprise components?
Zone 2 enterprise modules are available via commercial subscription, including dedicated support SLAs, on-premise deployment assistance, and regulatory compliance audit guarantees. Contact **`andrejlo123@gmail.com`** to initiate an enterprise evaluation or staging diagnostic audit.
