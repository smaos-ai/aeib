# Sovereign Governance Substrate — Bounded Evidence & Limitations Specification

**Standard:** Sovereign Multi-Agent OS (SMAOS) / AEIB v0.2.0 Synthetic Prototype  
**Format Designation:** `AEIB_JSON_ED25519_PROTOTYPE`  
**Status:** Canonical Scope Boundary & Non-Warranty Declarations  
**Last Updated:** September 2026  

---

## ⚠️ Mandatory Scope Disclaimers for Reviewing Engineers & Architects

1. **Prototype Designation**: All receipts emitted by the benchmark harness use the `AEIB_JSON_ED25519_PROTOTYPE` format designation.
2. **Deterministic Serialization (Not RFC 8785 Validated)**: Payloads are serialized using a deterministic JSON subset (sorted keys, compact separators). This is an engineering precursor, not a formal RFC 8785 (JCS) compliance certification.
3. **Synthetic Data Boundary**: All test runs and conformance receipts operate strictly on synthetic benchmark fixtures and simulated transport outcomes. This is an engineering review prototype, not a production security control.
4. **Adapter Dependency for Live Reconciliation**: Out-of-band verification relies on target-side query adapters. True exactly-once semantics require downstream services to enforce idempotency keys.
5. **No Compliance Certification**: The substrate provides evidence collection mechanisms to assist internal audit and risk reviews. It does not certify statutory compliance with EU DORA, the EU AI Act, or ISO/IEC 42006.

---

## 🏛️ 1. The 3-Layer Code Core (`STAR v1.0` Seed)

To ensure zero external dependencies, air-gapped security (`network_mode: "none"`), and 100% local portability, the production-safe code core is constrained to three immutable layers:

```text
┌─────────────────────────────────────────────────────────────┐
│                 STAR v1.0 — THE DECADAL CORE                │
├─────────────────────────────────────────────────────────────┤
│  1. PARSE   ──► Tree-sitter AST parser (logic, not text)     │
│  2. PROVE   ──► Merkle DAG root + Ed25519 SCITT receipt     │
│  3. GATE    ──► Pre-execution intercept (no receipt = block)│
└─────────────────────────────────────────────────────────────┘
```

1. **PARSE (AST Logic Grounding)**: Converts tool dispatches, source mutations, and policy expressions into typed abstract syntax trees (ASTs), eliminating prompt-injection string ambiguities.
2. **PROVE (Cryptographic Lineage)**: Generates canonical RFC 8785 JCS SHA-256 Merkle DAG roots signed with Ed25519 keys and persisted to an embedded, append-only SQLite ledger (`agentacct.db`).
3. **GATE (Fail-Closed Execution Control)**: Intercepts tool traffic at the wire/kernel boundary *before* external side effects occur. Execution is blocked unless a valid cryptographic receipt is presented.

---

## 🛡️ 2. The Bounded Compliance & Evidence Envelope

When delivered to enterprise CISOs, auditors, and regulatory bodies, this substrate enforces an **evidence-first, non-certification** posture:

### A. Vendor Data Contribution (DORA Art. 28)
* Pre-filled DORA Register of Information templates (xBRL-CSV format) are provided strictly as a **vendor data contribution** to assist financial entities with their internal ICT third-party risk assessments (Regulation (EU) 2022/2554, Art. 28(3)).
* Delivery of these templates does not constitute an automatic supervisory filing or direct regulatory submission to the EBA, ESMA, or national competent authorities (NCAs).

### B. The `Capability ≠ Authority` Invariant
* Possessing the technical capability (e.g., API key, network socket, tool definition) to invoke an action does **not** grant the agent operational authority to execute it.
* Pre-execution gates require explicit, cryptographically verifiable policy receipts or human-in-the-loop authorization tokens prior to state mutation.

### C. Uncertainty Preservation (`verdict: UNKNOWN`)
* When an external action encounters transport ambiguity (HTTP 504 Gateway Timeout, TCP RST drop, network partition), the harness overrides false success assumptions.
* The action state is locked as `verdict: UNKNOWN` with `retry_held: true` ($\Delta = 0$ conservation math), preventing duplicate payment disbursements, orphaned state changes, and toxic retry storms.

### D. 4-Part Falsifiable Claim Structure
Every technical claim asserted by this harness adheres to a falsifiable scientific specification:
* **Claim**: Explicit operational invariant (e.g., zero false `CONFIRMED` receipts under HTTP 504 transport failure).
* **Falsifier Condition**: The exact observable condition that proves the claim false (e.g., any signed `CONFIRMED` receipt emitted without a downstream transaction commit).
* **Frozen Result**: Deterministic, bit-exact test outcome reproducible in a container running with `network_mode: "none"`.
* **Verification Hash**: RFC 8785 JCS SHA-256 digest pinning the input fixture, execution trace, and output verdict.

---

## 📋 3. Standard Non-Claims & Statutory Disclaimers

To maintain strict compliance and pre-empt auditor nitpicks, the following scope boundaries are non-negotiable:

### 1. No Statutory Compliance Certification
* Running this test harness, benchmark, or verifier provides **cryptographic and empirical proof of software execution logic**. It does **not** constitute legal counsel, formal statutory interpretation, or regulatory certification under the **EU AI Act (Regulation (EU) 2024/1689)** or **DORA (Regulation (EU) 2022/2554)**.
* Formal conformity assessments under EU AI Act Annex VI remain the legal responsibility of the deploying organization.

### 2. Provisional Draft Alignment
* Technical references to emerging standards (including IETF SCITT Architecture, COSE/CBOR receipts, and draft Agent Action Capsule profiles) represent **informed architectural design inputs**.
* They must not be construed as finalized, published ISO, IEEE, or IETF normative standards.

### 3. Independent Offline Verification
* The verification runtime executes **100% offline-first** on local hardware or bare metal with zero telemetry tax.
* Verifying proofs requires no cloud API keys, no network egress (`network_mode: "none"`), and no proprietary vendor database access.

### 4. Synthetic Baselines vs. Live Production Systems
* The public benchmark evaluates synthetic fault vectors and standardized test fixtures.
* Live enterprise reconciliation (e.g., real-time PostgreSQL `txid_status` probes, Apache Kafka committed offset lookups, Stripe idempotency verification) is scoped and configured per client deployment environment.
