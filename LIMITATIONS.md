# AEIB v1.0.0-rc.1 & v0.2/v0.4 Baseline — Known Limitations & Operational Boundaries

**Status:** Review candidate and synthetic prototype for engineering review  
**Standard:** Agent Evidence Interlock Boundary (AEIB v1.0.0-rc.1 & v0.2.0 / v0.4.0 Baseline)  
**Format Designation:** `AEIB_JSON_ED25519_PROTOTYPE` / `AEIB-RECEIPT-SPEC v1.0 (RC1)`  
**Author:** Andrii Leukhin, Independent Researcher, SovereignNexus project  

> **Definitive Bounded Release Statement (`v1.0.0-rc.1`):**  
> **AEIB v1.0.0-rc.1 is a Java 21-compatible deterministic execution-integrity runtime for agentic systems. It is designed to verify a pinned manifest, evaluate candidate actions locally before dispatch without external I/O, represent ambiguous transport outcomes as `EFFECT_INDETERMINATE`, resolve uncertainty through declared semantic reconciliation with bounded probe budgets, and produce tamper-evident RFC 8785–bound Ed25519 hash-chain receipts. The standalone verifier requires the caller to supply the public key associated with the receipt’s `keyId`. AEIB does not claim universal exactly-once execution across uncooperative targets, provide external SCITT anchoring, implement automatic key lookup, validate memory or retrieval provenance, or claim regulatory compliance. Hosted branch/tag CI has executed (`38055110173`, `38055279949`); independent third-party reproduction from the signed tag remains pending.**
>
> *Baseline Context:* The distribution also retains the locally evaluated v0.2.4 / v0.4.0 Python core and experimental extensions (identity, telemetry, chaos-testing, and deep-stack scaffolds). These experimental extensions are not independently reproduced, and the release makes no claim of regulatory certification, universal exactly-once execution, or banking deployment readiness.

---

## 📊 Component Verification Status Matrix

| Component | Status |
| :--- | :--- |
| **Java 21 Native Runtime (`aeib-native-runtime/`)** | Evaluated in local and hosted CI (`38055110173`, `38055279949`) under the stated model |
| **Station 4 Standalone Offline Verifier (`com.aeib.verifier`)** | Standalone verifier designed for offline verification with caller-supplied public key (`13/13` vectors); independence requires separate execution and evidence |
| **Cross-Language Python 3 Verifier (`jvm_native_diff_engine.py`)** | Evaluated in local and hosted CI (`14/14` matched, `0 B` canonical JCS divergence) |
| **SLSA Provenance Contract (`SLSA_INPUT_CONTRACT.md`)** | Documented in `aeib-reproducibility/slsa/SLSA_INPUT_CONTRACT.md` and executed in hosted CI (`38055110173`, `38055279949`); independent third-party verification remains pending |
| **SQLite/PostgreSQL Python core (v0.2 / v0.4)** | Locally evaluated under stated fault model |
| **500-episode benchmark** | Report only with raw logs, seed (`42`), and exact harness |
| **Noun/Verb CAID** | Locally evaluated (`tests/test_ccs_conformance.py`, `com.aeib.crypto.CaidEngine`) |
| **PKCS#11 HSM Enclave** | Locally evaluated scaffold (`pkcs11_hsm_enclave.py`, Zero-RAM digest interface, un-exportable keys `CKA_EXTRACTABLE=False`, line-stop interlock) |
| **RFC 8785 JCS Canonicalization** | Locally and CI evaluated (`src/jcs_canonicalizer.py`, `com.aeib.verifier.Rfc8785Canonicalizer`) |
| **Saga Compensation (Claim C4)** | Locally evaluated (`tests/test_saga_compensation.py`, $\sum \Delta_{\text{net}} = 0.00$) |
| **Legacy JVM scaffold** | Design/prototype scaffold (`smaos-jvm-core/`) superseded by `aeib-native-runtime/` |
| **Toxiproxy chaos** | Experimental benchmark (`benchmarks/chaos_toxiproxy.py`) |
| **LLM drift loop** | Experimental benchmark (`benchmarks/llm_drift_loop.py`) |
| **eBPF LSM / Socket Filter** | Structural scaffold (`ebpf/aeib_sock_filter.c`, `ebpf/ebpf_lsm_agent_guard.c`) |
| **BBS+** | Experimental prototype (`src/bbs_plus_redactable.rs`, `WP2.md` roadmap) |
| **Multi-tenancy** | Prototype governor evaluated locally (`src/security/tenant_governor.py`) |
| **Regulatory mappings** | Informational only |
| **Independent third-party reproduction** | Pending (Gate 3 harness ready in `aeib-reproducibility/gate3/`; separate-party evidence pending) |

---

## 🎯 Strategic Framing (For Design Partners & Reviewers)

AEIB translates cryptographic action identity and post-dispatch reconciliation into bounded operational concepts: **declared action boundaries**, **quarantine of ambiguous effects**, and **purpose-linked evidence**.

These controls complement—not replace—policy, authorization, and human oversight:

* **Noun/Verb Ontology**: Maps tool calls to structured entities, decoupling action identity from prompt phrasing drift.
* **Staging Sandbox**: Quarantines ambiguous transport faults (e.g., HTTP 504) as `EFFECT_INDETERMINATE` or `DISPATCHED_UNCONFIRMED` rather than defaulting to blind retries.
* **Purpose-Linked Evidence**: Binds tenant, operation, and key identifiers (`keyId`) to verifiable receipts to support offline auditability under a caller-supplied public key.

---

## ⚖️ Epistemic Boundary Lock & Acknowledged Constraints

To maintain rigorous scientific integrity and prevent overclaiming, AEIB operates strictly under these **Six Acknowledged Boundaries & Constraints**:

1. **Consistency Model**: Documented strictly as eventual consistency via saga compensation and declared semantic reconciliation with bounded probe budgets. No claims of atomic distributed rollback or two-phase commit (2PC) across heterogeneous external tools.
2. **Hardware Attestation**: PKCS#11 wrappers and `/dev/tdx_guest` / `/dev/sev-guest` paths are explicitly documented as structural scaffolds and simulations, not live cryptographically verified Intel TDX or AMD SEV-SNP hardware attestation.
3. **Kernel Enforcement**: eBPF LSM/XDP hooks are documented as deferred/stubbed structural scaffolding until compiled, loaded into a live Linux kernel LSM ring ($\ge 5.7$), and stress-tested.
4. **Network Topology**: Loopback socket fault injection (`Gate4IntegrationTest`) and Toxiproxy socket severance are documented as simulating specific fault classes (HTTP 504 Gateway Timeout, TCP RST, half-open drops), not replicating live WAN asynchronous packet loss or split-brain partition behaviors.
5. **Benchmark Scope**: Local adapters around external suites (`duplicate-side-effect-desk`, `ARIB`, $\tau^2$-bench) are documented as local harness compatibility testing, not independent third-party audit validation.
6. **Latency Metrics**: The ~0.86 ms p50 latency in the Python baseline is strictly bounded to the in-memory verification loop on macOS ARM64, with no generalization to distributed or multi-tenant environments.

### Adopted Linguistic Discipline:
* **Permitted Vocabulary:** *"observed,"* *"tested,"* *"evaluated,"* *"configured,"* *"under the stated model,"* *"prototype,"* *"scaffold."*
* **Linguistic Enforcement:** All absolute or uncalibrated marketing terms (as enumerated in `AGENTS.md` Section 1) are strictly prohibited across code comments, documentation, specifications, and output.

---

## 1. Summary of Implemented vs. Unimplemented Scope

### What Is Implemented (`v1.0.0-rc.1` & `v0.2`/`v0.4` Baseline)
* **Java 21 Four-Station Deterministic Runtime (`aeib-native-runtime/`):** Station 0/1 pinned manifest verification and local candidate action admission without external I/O, Station 2 `EFFECT_INDETERMINATE` handling and single-flight semantic reconciliation with bounded probe budgets, Station 3 RFC 8785–bound Ed25519 hash-chain continuity receipts, and Station 4 standalone offline verifier requiring the caller to supply the public key associated with `keyId`.
* **Deterministic UUIDv5 & SHA-256 CAID Derivation:** Derived from canonical payload digest before dispatch.
* **Formal RFC 8785 JSON Canonicalization Scheme (JCS):** Byte-exact JCS canonicalizer (`src/jcs_canonicalizer.py`, `com.aeib.verifier.Rfc8785Canonicalizer`) configured to enforce whitespace elimination, UTF-16 code unit lexicographical key order, and IEEE 754 float determinism.
* **PKCS#11 Hardware Security Module (HSM) Enclave Scaffold:** Zero-RAM key exposure (caller passes only 32-byte digest), un-exportable keys (`CKA_EXTRACTABLE=CK_FALSE`), 1-hour TTL CRO execution permits (`CROExecutionPermit`), velocity throttle (50 ops/s), and emergency line-stop interlock (`pkcs11_hsm_enclave.py`).
* **Two-Phase Saga Compensation (Claim C4):** Deterministic compensating reversal transactions for ambiguous uncommitted drops, preserving the net balance invariant $\sum \Delta_{\text{net}} = 0.00$ under the stated model (`tests/test_saga_compensation.py`).
* **Ed25519 Receipt Signing & COSE_Sign1 Support:** Asymmetric signature lifecycle binding payload and evidence digests under caller-supplied public keys.
* **Disposition Taxonomy:** Normative state machines in Java 21 (`CONFIRMED`, `REFUTED`, `CONFLICT`, `EFFECT_INDETERMINATE`) and Python v0.4 (`OUTCOME_VERIFIED`, `DISPATCHED_UNCONFIRMED`, `RECONCILIATION_NOT_FOUND`, etc.).
* **Transport-to-Disposition Mapping Contract:** Priority-ordered YAML rule contract (`transport-to-disposition-mapping.yaml`).
* **Standalone Offline Verifiers (`com.aeib.verifier.VerifierCli` & `aeib_verify.py`):** Standalone verification of signatures, hashes, and mapping rules under a caller-supplied public key.
* **Canonical Fault Scenarios & Vectors:** Gate 4 live loopback socket fault tests plus 8 canonical synthetic fault scenarios and 15 fault vectors.

### What Is Not Implemented in `v1.0.0-rc.1` (High-Level)
* Universal exactly-once execution across uncooperative targets
* External IETF SCITT Transparency Service anchoring or public notary registration (RFC 9943)
* Automatic public key lookup, PKI directory resolution, or OCSP/CRL revocation distribution (the standalone verifier requires the caller to supply the public key associated with `keyId`)
* Memory binding, retrieval provenance validation, or procedural-memory write admission
* Real socket-level transport interception in live kernels (eBPF files in `ebpf/` are structural scaffolding)
* Physical hardware TEE attestation (Intel TDX / AMD SEV-SNP character devices are structural scaffolding)
* Out-of-band ledger probes against live multi-datacenter core banking clusters
* Heterogeneous multi-tool distributed 2PC rollback coordinators (beyond single-tool saga compensation)

---

## 2. v1.1 Backlog: Research & Specification Candidates Only (Out of Scope for `v1.0.0-rc.1`)

The following 13 items are explicitly out of scope for `v1.0.0-rc.1` and are retained strictly as **v1.1 research or specification candidates**, not current capabilities or commitments:

1. `Multi-tier memory binding`
2. `Retrieval provenance policy`
3. `Procedural-memory write admission`
4. `Upstream context-decision reference`
5. `Diagnostic interlock decision fields`
6. `External transparency registration`
7. `Hybrid Ed25519 + ML-DSA-65 signature profile`
8. `CCS interoperability review`
9. `GAAT telemetry projection review`
10. `MMR ledger evaluation`
11. `dspy-security-bench evaluation review`
12. `TA-14 or equivalent external examination`
13. `AIUC-1 certification pathway`

Do not claim compatibility, conformance, certification, or alignment with any of these until a formal specification, test suite, and evidence exist.

---

## 3. The Six Operational & Systems Limitation Domains

To clearly delineate the boundary between the evaluated runtime/benchmark package and full distributed infrastructure, the following six operational domains are bounded as follows:

### Domain 1: Distributed Coordination & Multi-Node State
* **Single-JVM / Local Process Concurrency Scope:** `SingleFlightCoalescer` and `ProbeCoalescer` coalesce concurrent probes within a single runtime process. There is no multi-node distributed lock coordinator (e.g., Redis, etcd, Consul) across independent cluster nodes.
* **No Multi-Tool 2PC Rollback Coordinator:** The v0.2.4 / v0.4.0 Python core locally evaluates single-tool saga compensation (Claim C4, eventual consistency via asynchronous queues). Neither the Python baseline nor `v1.0.0-rc.1` provides atomic distributed two-phase commits (2PC) across heterogeneous multi-party tool chains.

### Domain 2: Protocol & Transport Coverage
* **No Streaming / SSE / Bidirectional JSON-RPC Handling:** The runtime evaluates discrete request-response payloads. It does not handle Server-Sent Events (SSE), chunked streaming token assembly, or partial tool response reassembly.
* **No Network Protocol Interception Outside HTTP/stdio:** Protocols such as gRPC, WebSockets, Kafka message brokers, and raw database wire protocols are not parsed by the HTTP admission/reconciliation stations.

### Domain 3: Identity, PKI & Cryptographic Lifecycle
* **Caller-Supplied Public Key Requirement (No Automatic Key Lookup or PKI Hierarchy):** The standalone verifier (`com.aeib.verifier.VerifierCli` and `aeib_verify.py`) requires the caller to explicitly supply the Ed25519 public key (PEM X.509 SPKI) associated with the receipt's `keyId`. Automated key discovery, enterprise X.509 PKI root-of-trust hierarchies, cross-datacenter key rotation, and CRL/OCSP certificate revocation distribution are not implemented.
* **No Multi-Hop Agent Delegation Chain Verification:** The prototype does not verify multi-hop delegation trees (Human → Primary Agent → Sub-Agent) via external SPIFFE federation or W3C Verifiable Credential chains.

### Domain 4: Language Runtimes & Client SDKs
* **Reference Runtime & Verifier Scope:** `v1.0.0-rc.1` provides a Java 21 reference runtime and standalone CLI verifier (`aeib-native-runtime/`), a Python 3 standalone verifier (`aeib_verify.py` / `benchmarks/jvm_native_diff_engine.py`), and a Rust/WebAssembly verifier (`smaos-wasm-verifier/`). Native client SDKs for TypeScript/Node.js, Go, and turnkey framework auto-configuration modules remain out of scope.
* **No Model-Agnostic Context Injector:** The runtime does not mutate or inject prompts into upstream LLM orchestration context windows.

### Domain 5: Operational Tooling & Governance Integration
* **No Operational Triage UI or Human-in-the-Loop (HITL) Queue:** When an action enters `EFFECT_INDETERMINATE` or `DISPATCHED_UNCONFIRMED`, there is no graphical dashboard or ticketing webhook (Jira, ServiceNow, PagerDuty) built into the core runtime.
* **No External Network I/O in Station 0/1 Admission:** By design, Station 0/1 evaluates candidate actions locally against a pinned manifest without external I/O; it does not query remote Policy Decision Points over the network during pre-dispatch admission.

### Domain 6: Storage, Archival & Regulatory Egress
* **No Built-In Distributed WORM Storage Engine:** Receipts and evidence records are emitted as structured JSON/JSONL artifacts. Long-term WORM retention (e.g., S3 Object Lock) must be configured by the deploying operator.
* **No Live Supervisory Regulatory Dispatch:** While DORA Article 17 and 28(3) export scripts format technical traces into structured templates, AEIB does not perform automated filing to national competent authority (NCA) gateways or claim regulatory compliance.

### Domain 7: Tool Call Execution Synchronicity
* **Synchronous Request-Response Evaluation:** The benchmark and Gate 4 harness evaluate mutating tool calls within bounded request-response and probe-budget windows. Long-horizon multi-day asynchronous callback workflows remain outside the v1.0.0-rc.1 test scope.

---

## 4. What This Package Does Not Claim

* **No Regulatory Compliance Certification:** Running this test harness provides empirical evidence of software execution logic under the stated model. It does not constitute legal counsel or certified compliance under EU DORA, the EU AI Act, ISO/IEC 42006, or AIUC-1.
* **No Universal Exactly-Once Execution:** When a target system does not cooperate (no idempotency support and no status probe endpoint), AEIB cannot prevent target-side ambiguity; it records `EFFECT_INDETERMINATE` / `DISPATCHED_UNCONFIRMED` and halts fail-closed.
* **No Memory or Retrieval Provenance Validation:** AEIB v1.0.0-rc.1 binds candidate action parameters at the execution boundary; it does not validate upstream RAG retrieval provenance or multi-tier agent memory integrity.
* **No Adversarial Host Root Tamper Prevention:** Detached Ed25519 signatures detect post-hoc receipt modification under the supplied public key, but do not prevent a root-privileged host from suppressing writes prior to signing.

---

## 5. What Is Evaluated Under the Stated Model

1. **Uncertainty Representation:** An ambiguous post-dispatch transport outcome (`HTTP 504`, `TCP RST`, or socket timeout) is explicitly represented as `EFFECT_INDETERMINATE` (Java 21 v1.0.0-rc.1) or `DISPATCHED_UNCONFIRMED` (Python v0.4.0), blocking blind retries fail-closed.
2. **Declared Semantic Reconciliation:** Uncertain outcomes are evaluated against target-provided semantic state under AEIB's declared reconciliation policy and bounded probe budgets (`SingleFlightCoalescer` / `Station2EffectReconciler`).
3. **Standalone Offline Verification:** RFC 8785–bound Ed25519 hash-chain receipts can be verified offline using the standalone verifier (`com.aeib.verifier.VerifierCli` or `aeib_verify.py`) when the caller supplies the public key associated with `keyId`.

---

## 6. The Five Normative Bounded Clauses (500-Episode Baseline)

To maintain epistemic discipline during engineering review, the 500-episode Python benchmark explicitly codifies the following five operational boundaries:

1. **Configured 60% Semantic Drift Parameter**: The benchmark injects a configured ~62.8% (314/500 episodes) prompt semantic drift rate to evaluate how client-side argument hashing behaves under LLM rephrasing. In live deployments, drift rates vary with sampling temperature and prompt structure.
2. **Synthetic Ledger Endpoints**: All state transitions evaluate against a configured target-side in-memory / local PostgreSQL or SQLite relational ledger model under AEIB's declared reconciliation policy. Live core banking platforms (e.g., FIS, Finacle, Temenos) feature asynchronous batch clearing and multi-phase settlement windows.
3. **Local Single-Node Transaction Isolation**: Probe adapters execute against single-node PostgreSQL (`READ COMMITTED` / `REPEATABLE READ`) or SQLite. Globally distributed consensus engines introduce cross-datacenter replication lag that requires calibrated grace periods.
4. **Row-Lock Contention Isolation in Baseline**: The primary 500-episode harness measures serial transaction integrity. High-contention lock behavior under concurrent virtual-thread storms is evaluated separately in the concurrency test suites.
5. **Discrete Transport Severance vs. Nuanced Degradation**: Fault injection simulates discrete socket events (HTTP 504 Gateway Timeout, TCP RST packets, half-open drops) rather than partial WAN degradations such as asymmetric MTU blackholes.

---

## 7. Conformance Disclaimers & Epistemic Boundaries

- **Primary Claims Scope:** Primary claims are strictly bounded to the Final Bounded Claim in `CLAIMS_EVIDENCE.md`, the frozen receipt specification (`AEIB-RECEIPT-SPEC.md`), the versioned YAML mapping contract (`transport-to-disposition-mapping.yaml`), and the deterministic test suites executed in local and hosted CI (`38055110173`, `38055279949`).
- **Prior Art Acknowledgments:** Explicitly credits established patterns in literature and engineering:
  - Durable Outbox patterns and idempotent receivers.
  - Cryptographic evidence ledgers and append-only hash chains.
  - IETF `local_harness` nomenclature for evidence grading.
  - VERITAS OS `EFFECT_UNKNOWN` disposition and reconciliation models under transport-severance faults.
- **Interoperability & Standards References:** References to CCS, IETF (`draft-sahu-agent-action-receipts`, `draft-etcheverry-action-ref`), CAICT, and GAAT are candidate interoperability or research references only; no compatibility or conformance claim is made.
- **Applied Phrasing Calibrations:**
  1. *Failure Rate Phrasing:* C0 and C2 produced violations in 50/50 trials under this benchmark's specific fault model. This is not characterized as a universal failure rate across arbitrary distributed systems.
  2. *Literature Alignment:* `arXiv:2608.13900` ("Agentic Transaction") is cited strictly under Related Work as an emerging theoretical framework; AEIB claims no semantic atomicity, distributed 2PC, or ACID transaction properties.
- **Statistical Rule-of-Three Invariant:** The 0/50 observed duplicates in the 50-trial subset corresponds to a 95% confidence upper bound of 5.8% under the stated synthetic fault model (and $\le 0.60\%$ across the 500-episode seed-42 run).
- **Zero-Egress Verification Note:** The Gate 3 runtime verification container is configured with `network_mode: none` to enforce zero network egress during test execution, while Docker image construction may use network access to install OS-level packages. Independent third-party reproduction from the signed tag `v1.0.0-rc.1` remains pending.

---

## 8. Protocol Scope & Latent Communication Boundaries

AEIB is explicitly designed for structured agent execution payloads (MCP, JSON-RPC, REST/HTTP) where candidate actions serialize to canonical JSON under RFC 8785. It does not address latent-space inter-agent communication or direct KV-cache fusion mechanisms (e.g., Cache-to-Cache, arXiv:2510.03215).
