# 🛡️ SovereignNexus / SMAOS: Air-Gapped AI Agent Wire-Truth Engine (`v0.2.4`)

> **Dual-Licensing & Release Architecture Statement:**  
> **SovereignNexus operates under a module-level dual-licensing boundary.**  
> **Zone 1 (Open Core)** is distributed under the **Apache License 2.0** and indexed on Zenodo under DOI [`pending-deposit`](https://doi.org/pending-deposit). It establishes an open, verifiable execution integrity specification, Noun/Verb CAID derivation, offline verifier, and 500-episode benchmark suite.  
> **Zone 2 (Enterprise Proprietary)** is governed by the **Sovereign Commercial License** and trade-secret protections. It contains high-concurrency database connection lease poolers, confidential hardware enclave wrappers, and automated regulatory compliance exporters.

[![Release](https://img.shields.io/badge/release-v0.2.4-blue.svg)](https://github.com/sovreignnexus/smaos/releases/tag/v0.2.4)
[![DOI](https://img.shields.io/badge/DOI-pending--deposit-lightgrey.svg)](https://zenodo.org)
[![License: Apache-2.0 (Zone 1)](https://img.shields.io/badge/Zone%201-Apache%202.0-green.svg)](LICENSE)
[![License: Commercial (Zone 2)](https://img.shields.io/badge/Zone%202-Commercial%20Proprietary-orange.svg)](ip-architecture.md)
[![Egress](https://img.shields.io/badge/egress-0%20bytes%20(air--gapped)-success.svg)](#privacy--zero-egress-invariant)

---

## 🏛️ Module-Level IP & Dual-Licensing Boundary Matrix

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

For full legal terms, clean import rules, and dependency architecture, see **[`ip-architecture.md`](ip-architecture.md)**.

---

## 🚨 The Problem: The "Omniscience Trap" & Speculative Retries

When an autonomous payment, ERP, or cloud agent dispatches a mutating tool call and the remote network connection drops with an **HTTP 504 Gateway Timeout** or **TCP RST**:
1. Standard agent frameworks (LangChain, AutoGen, CrewAI, native OpenAI Tool Calling) catch the transport exception and pass the error text back to the LLM prompt.
2. The LLM interprets the timeout as an unfulfilled task and executes a **speculative retry**.
3. **The Silent Failure:** If the remote system committed the write before the socket dropped, the speculative retry produces a **duplicate debit, double-provisioning, or ledger divergence**.
4. **The Semantic Drift Vulnerability:** Because LLM generation is stochastic, retried prompts rephrase natural language arguments, mutate JSON key ordering, or generate fresh client request IDs. Standard API gateway idempotency headers fail to recognize the duplicate request, resulting in duplicate mutations.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        FRAMEWORK COMPARISON: €400 MUTATING DEBIT                       │
├───────────────────────────────────┬────────────────────────────────────────────────────┤
│  UNPROTECTED FRAMEWORK            │  AEIB PROTECTED SUBSTRATE                          │
│  (LangChain / AutoGen / CrewAI)   │  (SovereignNexus Deterministic Wire Gate)          │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ 1. Agent dispatches €400 debit    │ 1. Agent dispatches €400 debit with UUIDv5 key     │
│ 2. DB commits; Balance = €600     │ 2. DB commits; Balance = €600                      │
│ 3. Network drops with HTTP 504    │ 3. Network drops with HTTP 504                     │
│ 4. Framework catches 504, prompts │ 4. Wire trap intercepts 504; halts execution       │
│    LLM: "Request timed out, retry"│ 5. Executes OOB probe against authoritative DB     │
│ 5. LLM blindly re-dispatches debit│ 6. Probe confirms commit; blocks duplicate retry   │
│ 6. DUPLICATE DEBIT COMMITTED!     │ 7. Receipt emitted with disposition: CONFIRMED     │
│                                   │                                                    │
│ Final Balance: €200.00            │ Final Balance: €600.00                             │
│ Duplicate Debits: 1               │ Duplicate Debits: 0                                │
│ Financial Loss: €400.00           │ Financial Loss: €0.00                              │
└───────────────────────────────────┴────────────────────────────────────────────────────┘
```

---

## ⚡ Zone 1: Open Core Capabilities (Apache 2.0)

Zone 1 provides the complete mathematical and protocol framework necessary to reproduce our research and verify agent execution integrity:

1. **Normative 15-Vector Mapping Contract (`docs/transport-to-disposition-mapping.yaml`)**:
   - Closed 7-disposition taxonomy (`OUTCOME_VERIFIED`, `DISPATCHED_UNCONFIRMED`, `RECONCILIATION_NOT_FOUND`, `RECONCILIATION_CONFLICT`, `PROBE_TIMEOUT`, `PROBE_EXCEPTION`, `READ_ONLY_REPLICA_REJECTED`).
   - Strict priority-ordered evaluation hierarchy binding transport wire observations to explicit retry policies.

2. **Cryptographic Noun/Verb CAID Derivation (`aei_core/`)**:
   - Computes deterministic Canonical Action Identifiers using RFC 8785 JSON Canonicalization Scheme (JCS) and SHA-256:
     $$\text{CAID} = H\Big(\text{Noun}_{\text{EntityID}} \parallel \text{Verb}_{\text{Action}} \parallel \text{JCS}(\text{Payload})\Big)$$
   - Prevents prompt semantic drift from generating fresh idempotency tokens across retries.

3. **Industrial-Protection-Inspired Governor (`src/protection_governor.py`)**:
   - Real-world grid protection principles applied to software execution governance:
     - **Probe-Failure Escalation Pattern**: Multi-tier cascade (primary $\to$ secondary $\to$ tertiary fallback).
     - **Manual Lockout Latch**: Irreversible trip into unconfirmed state requiring signed operator reset.
     - **Peer Cancellation Pattern**: Swarm-wide transfer tripping cancelling concurrent in-flight worker tasks.
     - **Retry-Oscillation Detector**: Halts cyclical retry loops before cascading failure.
     - **Payload-Integrity Differential Check**: Detects 1-byte ledger payload mismatches instantly.
     - **Execution Sequence / Disturbance Records**: High-resolution forensic records under EU AI Act Art. 12 & ISO/IEC 42001.
   - *Note on Analogy*: Software patterns inspired by protection principles; does not claim physical ANSI/IEEE/IEC standards equipment certification.

4. **Standalone Offline Verifiers (`aeib_verify.py` & `dist/smaos_verify.wasm`)**:
   - Standalone verifier checking cryptographic SCITT receipts with **0 bytes of cloud egress**.

5. **Benchmark Suite (`benchmarks/` & `tests/`)**:
   - 500-episode evaluation across 15 synthetic fault vectors under deterministic seed 42.
   - Zero-mock falsifiability test matrix validating algorithmic computation over hardcoded tables.

---

## 🏢 Zone 2: Enterprise Proprietary Capabilities (Commercial)

Zone 2 delivers high-throughput, hardened enterprise infrastructure for mission-critical production environments:

1. **Production PostgreSQL Prober (`aeib_postgresql_probe/pg_probe_adapter.py`)**:
   - Session-level statement timeouts (`options='-c statement_timeout=3000'`) avoiding autocommit traps.
   - Connection lease pooling preventing pool starvation under high virtual thread concurrency.
   - Sub-3ms B-tree `UNION ALL` index scans over compound ledger keys.
   - Active read-replica fencing (`SHOW transaction_read_only`) redirecting queries to primary writers.

2. **GRC Regulatory Exporters (`smaos_dora_kit.py`)**:
   - Automated EU DORA Chapter V (Art. 28 ICT Third-Party Risk Register) and Annex IV template compilers.
   - EU AI Act Article 14(4) and Article 12 compliance pack bundlers generating certified xBRL-CSV dossiers.

3. **Zero-RAM Hardware Security Module Enclave (`pkcs11_hsm_enclave.py`)**:
   - Cryptographic key custody locked into physical tokens (`CKA_EXTRACTABLE = CK_FALSE`).
   - Statutory 1-hour TTL CRO execution permits under EU AI Act Article 14(4) human oversight mandates.
   - Emergency hardware line-stop interlock halting signing at the silicon boundary.
   - Scaffolding for Intel TDX and AMD SEV-SNP confidential VM attestation.

4. **Multi-Tenant RLS & Context Propagation**:
   - Stack-bounded context propagation (`tenant_id`, `principal_did`) without thread-local leaks.

---

## ⚖️ Concise CISO & Legal Licensing FAQ

### Q1: Does using Zone 1 open-source code obligate us to open-source our enterprise software?
**No.** Zone 1 is licensed under **Apache 2.0** (a permissive, non-copyleft license). Incorporating Zone 1 verifiers, CAID utilities, or mapping contracts into your enterprise stack does not trigger copyleft requirements or obligate you to open-source your proprietary code.

### Q2: Can we verify execution receipts without exposing database state or PII to SovereignNexus?
**Yes.** The WASM verifier (`dist/smaos_verify.wasm`) and `aeib_verify.py` run **100% offline inside your security perimeter**, evaluating cryptographic signature chains with **0 bytes of cloud egress**.

### Q3: Why is the production database prober (`pg_probe_adapter.py`) in Zone 2?
Zone 1 defines the abstract probing contract, while Zone 2 contains the production-hardened implementation featuring connection lease pooling, defensive statement timeout enforcement (`statement_timeout=3000`), sub-3ms B-tree `UNION ALL` index query optimizations, and replica lag fencing for high-throughput enterprise databases.

### Q4: How does Zone 1 publication protect our organization against third-party patent litigation?
By publishing Zone 1 specifications and benchmark harnesses to Zenodo under DOI [`pending-deposit`](https://doi.org/pending-deposit), SovereignNexus establishes timestamped public prior art. Patent offices globally (USPTO, EPO, JPO) will reject competitor patent applications targeting these idempotency and state-probing mechanics.

---

## 🔬 Single-Command Reproduction Guide (30 Seconds)

To verify the core Zone 1 execution integrity benchmark under zero-mock conditions:

```bash
# Clone repository and execute benchmark directly with deterministic seed 42
python3 benchmarks/aeib_execution_integrity/run_episodes.py --seed 42
```

### Expected Benchmark Results:
```text
================================================================================
EXECUTION ARM                | DUPLICATES   | FAILURE RATE   | VERDICT
--------------------------------------------------------------------------------
1. Naive Retry Baseline      | 500 /500     | 100.0%         | ❌ 100.0% FAILURE
2. Payload-Derived Key       | 314 /500     |  62.8%         | ❌ 62.8% DRIFT FAILURE
3. Server-Side Stable Key    | 0   /500     |   0.0%         | ⚠️ UNRESOLVED DROPS
4. AEIB Sovereign Protocol   | 0   /500     |   0.0%         | ✅ 0 DUPLICATES (Simulated)
================================================================================
```
*(Note on Harness: Deterministic simulation of retry-duplication over 15 fault classes in an in-memory ledger; duplicate retry attempts blocked by AEIB logic. In-process verifier p99 latency is ~5–10 µs).* 

### Complete Deterministic Verification Suite:
```bash
# Run industrial-protection-inspired test matrix
pytest tests/test_industrial_protection_matrix.py tests/test_ansi_50bf_breaker_failure.py -v

# Run AST purity and zero-mock enforcement scans
python3 compliance/ast_purity.py .
python3 compliance/no_mock_enforcer.py

# Verify SCITT receipt chain under mapping contract
python3 aeib_verify.py --receipt-chain dist/sample_receipt_chain.json --contract docs/transport-to-disposition-mapping.yaml --strict
```

---

## ⚖️ Epistemic Boundary & Acknowledged Constraints

To maintain absolute scientific integrity, AEIB operates under these six explicit boundaries:
1. **Consistency Model**: Eventual consistency via saga compensation; no claims of atomic distributed 2PC rollback across heterogeneous third-party tools.
2. **Hardware Attestation**: PKCS#11 wrappers and confidential VM paths (`/dev/tdx_guest`, `/dev/sev-guest`) are structural prototypes/simulations, not live verified hardware attestation.
3. **Kernel Enforcement**: eBPF LSM/XDP hooks are documented as deferred research scaffolding until verified on a live Linux kernel LSM ring ($\ge 5.7$).
4. **Network Topology**: Toxiproxy simulates specific fault classes (HTTP 504, TCP RST, half-open drops), not asynchronous live WAN packet loss or split-brain partitions.
5. **Benchmark Scope**: Local Python adapters around external benchmark suites (`duplicate-side-effect-desk`, `ARIB`, $\tau^2$-bench) reflect local harness compatibility testing.
6. **Latency Metrics**: The ~0.86ms p50 latency metric applies strictly to the local in-memory Python runtime, with no generalization to distributed multi-tenant environments.

---

## 📬 Contact & Commercial Licensing

* **Lead Researcher**: Andrii Leukhin (Founder, SovereignNexus)
* **Email**: `andrejlo123@gmail.com`
* **Repository**: [https://github.com/sovreignnexus/smaos](https://github.com/sovreignnexus/smaos)
* **Open Core DOI**: [`pending-deposit`](https://doi.org/pending-deposit)
* **Enterprise Inquiries**: Contact via email for Zone 2 enterprise licensing, on-premise pilot deployments, or staging diagnostic audit agreements.
