# AEIB v0.2 — Known Limitations & Operational Boundaries

**Status:** Synthetic prototype for engineering review  
**Standard:** Agent Execution Integrity Benchmark (AEIB v0.2.0 / v0.2.1)  
**Format Designation:** `AEIB_JSON_ED25519_PROTOTYPE`  
**Author:** Andrii Leukhin, Independent Researcher, SovereignNexus project  

> **Operational Boundary Notice:**  
> This package is a synthetic research prototype designed to explore execution integrity and ambiguity resolution. It is not a production system, not integrated with live banking or ERP infrastructure, and not a certified compliance solution.

---

## 1. Summary of Implemented vs. Unimplemented Scope

### What Is Implemented
* **Deterministic UUIDv5 Idempotency Key Derivation:** Derived from canonical payload digest before dispatch.
* **Deterministic JSON Subset Serialization:** Sorted keys, compact separators (not RFC 8785 validated).
* **Ed25519 Receipt Signing:** Asymmetric signature lifecycle binding payload and evidence digests.
* **7-State Disposition Taxonomy:** Normative state machine (`OUTCOME_VERIFIED`, `DISPATCHED_UNCONFIRMED`, `RECONCILIATION_NOT_FOUND`, etc.).
* **Transport-to-Disposition Mapping Contract:** Priority-ordered YAML rule contract.
* **Zero-Dependency Offline Verifier (`aeib_verify.py`):** Standalone verification of signatures, hashes, and mapping rules.
* **8 Canonical Synthetic Fault Scenarios:** Complete test vectors with signed receipts and JSONL evidence files.

### What Is Not Implemented (High-Level)
* Real socket-level transport interception (eBPF / raw sockets)
* Real out-of-band ledger probes against live database clusters
* Physical runtime retry suppression in live agent orchestrators
* Formal RFC 8785 (JCS) compliance certification
* Binary RFC 9052 COSE_Sign1 envelope formatting
* IETF SCITT Transparency Service registration (RFC 9943)
* Hardware attestation (TRACE, Intel TDX, AMD SEV-SNP)
* DORA `incident_class` enumeration mapping
* Production MCP sidecar proxy
* Hardware HSM / KMS PKCS#11 key management

---

## 2. The Six Operational & Systems Limitation Domains

To preempt reviewer objections and clearly delineate the boundary between benchmark prototype and production infrastructure, the following six operational domains are explicitly out of scope for v0.2:

### Domain 1: Distributed Coordination & Multi-Node State
* **No Distributed Concurrency Locks:** There is no shared coordination layer (e.g., Redis, etcd, Consul). If two independent agent instances concurrently dispatch identical mutating requests across multiple worker nodes, the prototype cannot coordinate distributed in-progress locks.
* **No Multi-Tool Saga / 2PC Rollback Coordinator:** The prototype evaluates single, isolated tool-call actions. It does not provide automated multi-step saga compensation, distributed two-phase commits (2PC), or state rollbacks across heterogeneous tool chains (e.g., reverting an API debit if a subsequent database write drops).

### Domain 2: Protocol & Transport Coverage
* **No Streaming / SSE / Bidirectional JSON-RPC Handling:** The prototype assumes discrete, atomic request-response payloads. It does not handle Server-Sent Events (SSE), chunked HTTP transfer encodings, token-by-token streaming, or partial tool response assembly.
* **No Network Protocol Interception Outside HTTP/stdio:** Protocols such as gRPC, raw TCP/TLS sockets, WebSockets, Kafka message brokers, and database wire protocols (PostgreSQL libpq) are not intercepted or parsed.

### Domain 3: Identity, PKI & Cryptographic Lifecycle
* **No PKI, Key Rotation, or Certificate Revocation (CRL/OCSP):** Signing relies on static, local ephemeral Ed25519 key files in `public-keys/`. There is no key rotation lifecycle, certificate revocation mechanism, or X.509 / DID (Decentralized Identifier) trust anchor integration.
* **No Agent Delegation Proofs (SPIFFE / RFC 7515 / AER-1 Chains):** The `actor` and `session_id` fields are plain strings. The prototype does not cryptographically verify the multi-agent delegation tree (e.g., Human → Primary Agent → Sub-Agent tool invocation) using signed JWTs, SPIFFE IDs, or verifiable credentials.

### Domain 4: Language Runtimes & Client SDKs
* **No Production Polyglot SDKs:** The verification harness and normalizer exist exclusively in Python. There are no production-grade client libraries or runtime filters for Java (Spring Boot / LangChain4j), TypeScript / Node.js, Go, or Rust.
* **No Model-Agnostic Context Injector:** The prototype does not integrate into agent prompt orchestration frameworks (e.g., AutoGen, CrewAI, LangGraph) to automatically inject quarantine instructions into model context windows.

### Domain 5: Operational Tooling & Governance Integration
* **No Operational Triage UI or Human-in-the-Loop (HITL) Queue:** When an action enters `DISPATCHED_UNCONFIRMED`, there is no operational dashboard, admin console, or incident alerting webhook (Jira, ServiceNow, PagerDuty) to allow human risk officers to inspect, unquarantine, or resolve transactions.
* **No Dynamic Upstream PDP Integration:** The prototype does not expose hooks or gRPC/REST endpoints to query external Policy Decision Points (e.g., Open Policy Agent, Permit.io, WitnessAI) in real time before wire dispatch.

### Domain 6: Storage, Archival & Regulatory Egress
* **No Immutable Long-Term WORM Storage:** Receipts and evidence records are appended to local flat files (`receipts.jsonl`, `transport.jsonl`). There is no integration with compliant WORM (Write Once, Read Many) storage, S3 Object Lock, or tamper-evident distributed databases to satisfy 5-year regulatory retention floors.
* **No Live Supervisory Regulatory Dispatch:** While DORA Annex II pre-fill templates exist as static JSON outputs, there is no automated filing mechanism, validation against national competent authority (NCA) gateways, or automated packaging into validated xBRL-CSV regulatory archives.

---

## 3. Strategic Rationale: Preempting Objections & Guiding Review

* **Preempts Objections Before They Arrive:** By explicitly stating that distributed concurrency locks, multi-step sagas, PKI key rotation, and polyglot SDKs are out of scope for v0.2, you eliminate the risk of reviewers framing these missing features as "flaws." Instead, they are recognized as intentional design boundaries of a benchmark prototype.
* **Defines the Production Horizon Roadmap:** Each limitation domain maps directly to the target production architecture:
  - **Domains 1 & 2 (Distributed State & Protocols):** Handled by the eBPF XDP/TC kernel driver and bitemporal ledger probes.
  - **Domain 3 (PKI & Delegation):** Handled by HSM/KMS PKCS#11 keys and SPIFFE/Verifiable Credential delegation trees.
  - **Domain 4 (Polyglot SDKs):** Handled by native runtime filters (e.g., `ProofOrStopFilter.java` for Spring WebClient).
  - **Domains 5 & 6 (Operational UI & WORM Storage):** Handled by the Triage Queue Cockpit, S3 Object Lock, and IETF SCITT transparency services.

---

## 4. What This Prototype Does Not Claim

* **No Regulatory Compliance Certification:** Running this test harness provides empirical proof of software execution logic. It does not constitute legal counsel or certified compliance under EU DORA, the EU AI Act, or ISO/IEC 42006.
* **No Production Readiness:** Not hardened for high concurrency, multi-tenant deployment, or zero-downtime operations.
* **No Adversarial Tamper Resistance Beyond Hash Chains:** Defends against post-hoc receipt modification via Ed25519 signatures, but does not prevent a root-privileged host from suppressing writes or corrupting memory without hardware attestation.
* **No Live Ledger Interaction:** Evaluated against synthetic fixtures, not live clearing networks or production core banking systems.

---

## 5. What This Prototype Conclusively Demonstrates

1. **The Invariant:** An ambiguous post-dispatch outcome (`HTTP 504`) can be deterministically captured as a verifiable, signed disposition (`DISPATCHED_UNCONFIRMED`) with `retry_permitted: false`, rather than triggering an unhedged speculative retry.
2. **The Mapping Contract:** Priority-ordered YAML rules deterministically bind messy transport observations to normative operational dispositions.
3. **Independent Auditability:** Receipt signatures, evidence hashes, and mapping contract consistency can be completely validated offline by independent reviewers with zero dependencies.

### Domain 7: Tool Call Execution Synchronicity
* **Synchronous Mutating Tool Calls Only:** This benchmark strictly evaluates synchronous mutating tool calls where the remote procedure executes and commits within the lifecycle of the single HTTP request-response cycle. It does **not** evaluate asynchronous task lifecycles (e.g., long-running tasks returning `PENDING`, polling status endpoints, webhook callbacks, or `EXPIRED`/`CANCELLED` states). Formal tracking of asynchronous dispositions is deferred to future work.

## Conformance Disclaimers

- AAC conformance is untested against official conformance vectors.
- AEB conformance is untested against official conformance vectors.
- AER-1 conformance is untested against the -04 conformance runner.
- Prior-art citations are informational and do not constitute conformance claims.
