# arXiv Preprint Outline: Post-Dispatch Execution Integrity for Autonomous Agents

**Title:** Post-Dispatch Execution Integrity: Reconciling Ambiguous Transport Faults in Autonomous Agent Systems  
**Author:** Andrii Leukhin (Independent Researcher & Founder, SovereignNexus project)  
**Target Category:** arXiv `cs.CR` (Cryptography and Security) / `cs.SE` (Software Engineering)  
**Target Length:** 6–8 pages (IEEE / ACM two-column format)  
**Status:** Pre-Submission Research Structure (P1 Milestone)

---

## 📄 Abstract (Draft)
Autonomous multi-agent architectures increasingly dispatch mutating remote procedure calls (RPCs) across external enterprise interfaces. However, existing agent governance frameworks operate almost exclusively at the pre-dispatch authorization layer. When an authorized mutation encounters transport ambiguity—such as an HTTP 504 Gateway Timeout or TCP connection reset—the orchestrator cannot determine whether the state mutation succeeded downstream. Standard client-side retry policies risk catastrophic duplicate mutations (e.g., double-spend transfers, orphaned ledger records). 

This paper introduces the **Agent Execution Integrity Benchmark (AEIB)** and post-dispatch reconciliation protocol. AEIB defines a deterministic 7-state disposition taxonomy and enforceable mapping contract that intercepts post-dispatch transport faults, locks execution into `DISPATCHED_UNCONFIRMED`, and binds cryptographically signed Ed25519 receipts enforcing `retry_permitted: false`. We present an offline verifier and evaluation against 8 canonical wire-fault scenarios, demonstrating mathematical certainty against unhedged agent retries without requiring changes to downstream enterprise database engines.

---

## 🏛️ Section 1: Introduction (The Agent Stack & The Verification Gap)
* **The Three-Layer Agent Stack**:
  1. *Layer 1 (Governance)*: Policy decision points, tool allowlisting (P0, Delinea, Saviynt).
  2. *Layer 2 (Harness)*: Sandboxing, process isolation, default timeouts (Docker, gVisor, NVIDIA).
  3. *Layer 3 (Verification)*: Execution recording, cryptographic receipts, post-dispatch integrity (Salmon EVI, TRACE, AEIB).
* **The Core Thesis**: Pre-dispatch authorization proves an agent *had permission* to invoke a tool, but provides zero mathematical guarantee of *what actually transpired* when the wire drops.
* **The Post-Dispatch Ambiguity Gap**: When networks fail mid-flight, "unknown outcome" must be treated as a state to investigate, not permission to blind-retry.

---

## 💥 Section 2: Motivation & Problem Formulation
* **The HTTP 504 Ambiguity Trap**: Detailed walk-through of reverse-proxy dropouts where the server commits a mutation while the client receives a timeout.
* **Real-World Case Study (OpenAI–Hugging Face Incident 2026)**:
  - Demonstrates that authorization without verifiable execution evidence leads to severe audit disconnects and unmonitored lateral escalation.
* **Formal Threat Model**:
  - Unhedged retry storms.
  - Poisoned state mutations under network partitions.
  - Evidentiary gaps in supervisory audits (DORA Article 17, EU AI Act Article 14).

---

## ⚙️ Section 3: The AEIB Protocol & 7-State Taxonomy
* **Pre-Dispatch Preparation**:
  - Deterministic JSON argument normalization (sorted keys, compact separators).
  - SHA-256 payload digest binding: `unsigned_payload_hash`.
  - Deterministic UUIDv5 idempotency key injection prior to wire egress.
* **The 7-State Disposition Taxonomy**:
  1. `OUTCOME_VERIFIED`: Confirmed downstream commit.
  2. `DISPATCHED_UNCONFIRMED`: Ambiguous wire drop; retry locked.
  3. `RECONCILIATION_NOT_FOUND`: Probe confirmed transaction never reached downstream; safe to retry.
  4. `RECONCILIATION_FAILED`: Downstream state mismatch or payload corruption.
  5. `RECONCILIATION_CONFLICT`: Downstream collision under same idempotency key.
  6. `CONTEXT_POLICY_VIOLATION`: Refused pre-dispatch due to invalid authorization context.
  7. `AUTHORITY_NOT_BOUND`: Refused pre-dispatch due to expired delegation token.

---

## 📜 Section 4: Mapping Contract & Offline Verifier Architecture
* **Dynamic Priority Mapping**:
  - Formal priority hierarchy in `transport-to-disposition-mapping.yaml`.
  - Evaluation semantics: Downstream conflict (Priority 10) > Ambiguous drop (Priority 30) > Confirmed commit (Priority 50).
* **Cryptographic Provenance Envelope (`AEIB_JSON_ED25519_PROTOTYPE`)**:
  - Structure of the Ed25519-signed receipt binding transport observation and out-of-band probe digests.
* **The Offline Verifier (`aeib_verify.py`)**:
  - Zero-dependency verification algorithm validating asymmetric signatures, digest linkages, and manifest tamper-guards.

---

## 🔬 Section 5: Experimental Evaluation & Synthetic Benchmark
* **8 Canonical Conformance Scenarios**:
  - Full trace of Scenarios 01 through 07 (confirmed, ambiguous, probe-verified, reset, conflict, policy refusal, authority expiry).
* **Deterministic Reproducibility**:
  - Empirical verification that multiple runs generate bit-exact, duplicate-free evidence records.
* **Tamper Resilience**:
  - Invariant validation showing 100% failure rate when any byte of the mapping YAML or evidence JSONL is modified.

---

## 🌐 Section 6: Related Work & Categorical Placement
* **Execution Verification Platforms**:
  - Comparison with Salmon EVI (Archipelo): Contrasting Salmon's broad event provenance protocols (AEP/RCP) with AEIB's deep focus on post-dispatch wire drops.
* **Emerging IETF Specifications**:
  - `draft-marques-asqav-compliance-receipts`: Conceptual translation of AEIB dispositions into IETF compliance receipt fields.
  - IETF SCITT Architecture: Future transparency service registration.
* **Hardware Attestation**:
  - TRACE (Linux Foundation / OPAQUE / AMD / Intel / Microsoft): Comparing software-protocol receipts with hardware-attested enclave quotes.
* **Runtime Authorization Engines**:
  - Positioning AEIB downstream of P0 Security, Delinea, and Saviynt.

---

## ⚠️ Section 7: Limitations & Future Research Roadmap
* **Explicit Research Limitations**:
  - Synthetic test fixtures and local simulations only.
  - Deterministic JSON subset rather than formal RFC 8785 (JCS) certification.
  - Lack of DORA `incident_class` enumeration and 5-year retention storage.
* **Roadmap Milestones**:
  - P0: Minimal stdio sidecar interceptor.
  - P1: Real database probe adapters (PostgreSQL `txid_status`, SQLite).
  - P2/P3: Conceptual outbox dispatch and TEE hardware attestation bindings.

---

## 📌 Section 8: Conclusion & Open Artifacts
* Summary of contributions.
* Open-access conformance harness repository: `https://github.com/sovreignnexus/smaos` (Tag `v0.2.0`).
