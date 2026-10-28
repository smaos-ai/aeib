# arXiv Preprint Outline: Post-Dispatch Execution Integrity for Autonomous Agents

**Title:** Post-Dispatch Execution Integrity: Reconciling Ambiguous Transport Faults in Autonomous Agent Systems  
**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus project)  
**Target Category:** arXiv `cs.CR` (Cryptography and Security) / `cs.SE` (Software Engineering)  
**Target Length:** 6–8 pages (IEEE / ACM two-column format)  
**Source Revision:** `git:release/v0.2.0` (`f1ff34fb`)  
**Status:** Submission-Safe Pre-Submission Research Structure

---

## 📄 Abstract (Submission-Safe)
Autonomous agents increasingly invoke mutating remote procedures through gateways and external enterprise systems. When a downstream service commits a mutation but the response is lost—for example, after a gateway timeout—the caller observes transport failure without knowing whether execution occurred. A retry may therefore produce a second mutation, particularly when agent-driven semantic drift changes the effective idempotency identity.

We present the Agent Execution Integrity Benchmark (AEIB), a protocol and evaluation harness for representing and reconciling this post-dispatch ambiguity. AEIB defines a seven-state disposition taxonomy, a deterministic transport-to-disposition mapping contract, an execution boundary that freezes retries after ambiguous faults, and Ed25519-signed receipts that bind dispatch observations to authoritative probe results. We implement an offline verifier and evaluate AEIB against a reproducible control matrix. Across 500 deterministic episodes (seed 42), naive retry and semantic-drift baselines produced duplicate mutations in 100% and 62.8% of runs respectively, while a stable-key baseline produced none (leaving 99 unresolved drops). Under the same post-commit timeout fault, AEIB produced zero duplicate mutations across all 500 episodes (Rule-of-Three 95% upper bound of 0.60%).

> **Definitive Release Statement:**  
> AEIB Enterprise v1.0 is a review distribution containing the locally verified v0.2.4 core and experimental enterprise extensions. The core evaluates post-dispatch ambiguity using a SQLite/PostgreSQL fault-injection harness and explicit disposition rules. The package also includes prototype identity, telemetry, chaos-testing, and deep-stack integration components. These extensions are not production-validated or independently reproduced. The release makes no claim of regulatory certification, universal exactly-once execution, or production banking safety.

---

## 🏛️ Section 1: Introduction (The Verification Gap)
* **The Three-Layer Architecture**:
  1. *Layer 1 (Governance)*: Policy decision points, tool allowlisting (P0 Security, Delinea, Saviynt).
  2. *Layer 2 (Harness)*: Sandboxing, process isolation, default timeouts (Docker, gVisor).
  3. *Layer 3 (Post-Dispatch Verification)*: Execution recording, cryptographic receipts, out-of-band state reconciliation (AEIB).
* **The Verification Gap**: Pre-dispatch authorization evaluates whether an agent *had permission* to dispatch an action, but provides zero evidence of what occurred downstream when the transport severs mid-flight.
* **The Concrete Operational Sequence**:
  1. Mutation is dispatched (`POST /debit`).
  2. Server commits to ledger.
  3. Response is lost (HTTP 504 / TCP RST).
  4. Agent sees a timeout.
  5. Retry changes the effective request identity (semantic drift).
  6. A second mutation commits (duplicate debit).
* **Explicit Contributions**:
  - Disposition model: seven-state disposition taxonomy.
  - Mapping contract: priority-ordered transport-to-disposition evaluation.
  - Verifiable receipts: Ed25519-signed receipts verified offline.
  - Control and fault benchmark: $C_0, C_1, C_2$ matrix and AEIB fault benchmark.
  - Public unmocked artifacts: on-disk SQLite binary evidence and adversarial falsification suite.

---

## 💥 Section 2: Problem and Threat Model
* **The HTTP 504 Ambiguity Trap**: Server commits mutation to persistent storage, but socket drops 5ms post-commit before client receives HTTP 200 OK.
* **Formal Definitions**:
  - Logical Intent ($I$)
  - Dispatch Attempt ($A_{I, k}$)
  - Transport Observation ($T$)
  - Downstream Mutation ($M$)
  - Authoritative Probe ($Q$)
  - Semantic Drift
  - Safety Invariant: $\forall I, \quad \text{LedgerCommits}(I) \le 1$.
* **System Assumptions**:
  - Reachable and trustworthy probe.
  - Queryable idempotency identity.
  - Execution boundary can freeze retries.
  - Accurate outcome reporting by the ledger.
  - Receipt signer private key protected within the local environment.

---

## ⚙️ Section 3: Protocol and Taxonomy
* **Seven-State Disposition Taxonomy**:
  1. `OUTCOME_VERIFIED`: HTTP success response whose payload is validated, or an authoritative probe confirming the matching commit. Retry: Prohibited. Terminal.
  2. `DISPATCHED_UNCONFIRMED`: Ambiguous transport fault (504, TCP RST, EOF). Required evidence: transport observation, such as an HTTP 504 or recorded connection failure. Retry: Prohibited (Frozen). Non-terminal quarantine.
  3. `RECONCILIATION_NOT_FOUND`: Authoritative source, under the benchmark’s consistency and query assumptions, confirms that no matching mutation exists. Retry: Permitted under policy. Terminal.
  4. `RECONCILIATION_FAILED`: Downstream record found but payload hash diverges. Retry: Prohibited. Terminal.
  5. `RECONCILIATION_CONFLICT`: Conflicting records under same idempotency key. Retry: Prohibited. Terminal.
  6. `CONTEXT_POLICY_VIOLATION`: Refused pre-dispatch by policy engine. Retry: Prohibited. Terminal.
  7. `AUTHORITY_NOT_BOUND`: Delegation credential expired or unmeasured. Retry: Prohibited. Terminal.
* **Precision on `RECONCILIATION_NOT_FOUND`**: Signifies the authoritative source, under the benchmark’s consistency and query assumptions, confirms that no matching mutation exists downstream, not merely that a query timed out or returned empty.

---

## 📜 Section 4: Implementation
* **Documented Canonical JSON Subset**: Lexicographical key sorting, compact delimiters (`:`, `,`), UTF-8 encoding.
* **Payload Digest ($H$)**: $\text{SHA-256}(\text{CanonicalJSON}(P))$.
* **Deterministic Idempotency Key Derivation**: $\text{UUIDv5}(\text{Namespace}_{\text{AEIB}}, \text{"urn:aeib:payload:"} \parallel H)$.
* **Retry Lock**: Sets `retry_permitted: false` upon transport fault interception.
* **Authoritative Probe Interface**: Issues idempotent query against `GET /operations/{id}`.
* **Receipt Structure & Signing**: Structured JSON receipt with Ed25519 signature over JCS signable view.
* **Offline Verifier (`aeib_verify.py`)**: Standalone cryptographic verification tool.

---

## 🔬 Section 5: Evaluation
* **Empirical Control Matrix ($N=50$ Trials)**:
  - $C_0$ (Naive Client Retry): 100.0% duplicate rate ($50/50$ safety violations).
  - $C_1$ (Gateway + Stable Key): 0.0% duplicate rate ($0/50$). Deduplicated by gateway cache.
  - $C_2$ (Gateway + Semantic Drift): 100.0% duplicate rate ($50/50$ safety violations).
  - AEIB Post-Commit 504: 0.0% duplicate rate ($0/50$), 100% verified receipts.
  - AEIB Non-Commit Controls ($N=20$): 0.0% false `OUTCOME_VERIFIED` results ($0/20$).
* **Scope and Environmental Boundary**: The benchmark evaluates a deterministic local fault model with a SQLite ledger, an in-process gateway/fault injector, and a defined semantic-drift retry behavior. It does not establish equivalent rates for arbitrary agents, gateways, databases, network stacks, or production deployments.
* **Latency Overhead**:
  - Mean: 9.6 ms, p95: 11.0 ms in the local harness.
  - Explicit boundary: Includes in-process dispatch, 5ms post-commit delay, 504 interception, OOB probe, Ed25519 signing, and receipt serialization.
* **Canonical Single-Run Listing**: Ground-truth SQLite ledger rows (`tx_id=1` -> 9900, `tx_id=2` -> 9800) under C0, vs. single commit under AEIB.
* **Checks Supporting Concrete Local Execution and Falsifiability**:
  - Absence of common mocking APIs: static AST analysis confirms zero usage of `unittest.mock`, `MagicMock`, or `patch`.
  - On-disk SQLite ledger: binary file `ledger.db` inspected directly with standalone `sqlite3` CLI. Each run explicitly resets state (`store.reset_ledger()`).
  - Deterministic fault injection: explicit ASGI middleware component.
  - Cryptographic tamper sensitivity: all attempted one-bit payload tampering and one-byte signature corruption cases rejected with `InvalidSignature`.
  - Fail-closed negative controls: 20 uncommitted trials produce `RECONCILIATION_NOT_FOUND` with zero false `OUTCOME_VERIFIED` outcomes.
  - Suite composition: 20 tests total (15 baseline tests + 5 falsifiability checks).

---

## 🗄️ Section 6: Authoritative Probe Architecture & Database Reference Interface
* **Evaluated Store**: SQLite in WAL mode with strict ACID transactions.
* **Reference Interface**: `PostgresOutcomeProbeAdapter` querying `SELECT status FROM transaction_ledger WHERE idempotency_key = $1;`.
* **Honest Scope**: SQLite WAL is the evaluated empirical engine; PostgreSQL distributed cluster testing is an ongoing milestone.

---

## 🌐 Section 7: Related Work
* **Idempotency and Exactly-Once Limitations**: Two Generals problem, FLP impossibility, RFC 7231, RFC 8785.
* **Distributed-Systems Failure Semantics**: Transactional Outbox, Saga orchestrators.
* **Receipts and Transparency Systems**: IETF SCITT (`draft-ietf-scitt-architecture-08`, `draft-birkholz-scitt-receipts-02`), AER-1 (`draft-zambo-aer1-00`), Salmon EVI.
* **Agent Authorization and Runtime Controls**: P0 Security, Delinea, Saviynt.
* **Hardware-Backed Attestation**: TRACE project, AMD SEV-SNP, Intel SGX.
* **Categorical Difference**: AEIB operates strictly at the boundary between a dispatched mutating action and authoritative outcome reconciliation under transport ambiguity.

---

## ⚠️ Section 8: Limitations and Conclusion
* **Prominent Limitations**:
  - Synthetic test environment and local fault injection.
  - Single database engine evaluated (SQLite WAL).
  - Experimental prototype; no production deployment.
  - No universal exactly-once mathematical proof.
  - Non-compliance disclaimer: Requirements such as DORA Article 17 and EU AI Act Article 14 motivate operational evidence; this work makes no compliance or certification claim. AEIB produces evidence that may support assessment activities; it does not determine regulatory applicability or certify compliance.
  - Documented canonical JSON subset rather than formal RFC 8785 certification.
  - Security depends on signer private key protection and probe authority.
* **Conclusion**: Reconciling post-dispatch transport ambiguity with pre-dispatch canonicalization, retry freezing, out-of-band state reconciliation, and cryptographic attestation demonstrates zero duplicate mutations across reported deterministic trials.

---

## 📌 Artifact Integrity & Reproducibility
* Git Commit: `f1ff34fb` (Branch: `release/v0.2.0`).
* Manifest: `benchmarks/fault_injection/results/IMMUTABLE_BENCHMARK_MANIFEST.json`.
* Binary Ledger: `benchmarks/fault_injection/results/ledger.db`.
