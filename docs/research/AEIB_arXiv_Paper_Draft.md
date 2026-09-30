# Post-Dispatch Execution Integrity: Reconciling Ambiguous Transport Faults in Autonomous Agent Systems

**Authors:** Andrii Leukhin (Independent Researcher, SovereignNexus Project)  
**Target Category:** arXiv `cs.CR` (Cryptography and Security) / `cs.SE` (Software Engineering)  
**Target Format:** IEEE / ACM two-column conference/journal format (6–8 pages)  
**Source Revision:** `git:release/v0.2.0` (`f1ff34fb`)  
**Artifact Repository:** `benchmarks/fault_injection/`  

---

## Abstract

Autonomous agents increasingly invoke mutating remote procedures through gateways and external enterprise systems. When a downstream service commits a mutation but the response is lost—for example, after a gateway timeout—the caller observes transport failure without knowing whether execution occurred. A retry may therefore produce a second mutation, particularly when agent-driven semantic drift changes the effective idempotency identity.

We present the Agent Execution Integrity Benchmark (AEIB), a protocol and evaluation harness for representing and reconciling this post-dispatch ambiguity as an extension of OWASP LLM06 (Excessive Agency) mitigations. AEIB defines a seven-state disposition taxonomy, a deterministic transport-to-disposition mapping contract, an execution boundary that enforces a CMU Frozen Cascade (`retry_permitted = false`) after ambiguous faults, and Ed25519-signed receipts that bind dispatch observations to authoritative probe results. We implement an offline verifier and evaluate AEIB against a reproducible control matrix. Across 50 trials, naive retry and semantic-drift baselines produced duplicate mutations in 100% of runs, while a stable-key baseline produced none. Under the same post-commit timeout fault, AEIB produced no duplicate mutations, verified 50 of 50 receipts, and produced zero false `OUTCOME_VERIFIED` results across 20 non-commit controls. The measured AEIB overhead was 9.28 ms mean and 9.97 ms at p95 in the local harness. These results are limited to the tested synthetic environment and do not constitute a production-readiness, standards-compliance, or regulatory-certification claim.

---

## 1. Introduction: The Post-Dispatch Verification Gap

Modern autonomous agent frameworks (e.g., LangChain, AutoGen, CrewAI, OpenAI Assistant SDKs) decouple decision logic from deterministic execution by embedding tool invocation in an iterative reasoning loop:
$$\text{Thought} \longrightarrow \text{Action (Tool Call)} \longrightarrow \text{Observation} \longrightarrow \text{Next Step}$$

Enterprise security architectures address agent autonomy by deploying Layer 1 Governance (authorization gates, P0 Security, IAM role attenuation) and Layer 2 Sandboxing (gVisor, microVMs, egress firewalls). These controls evaluate pre-dispatch admissibility:
$$\text{Admissible}(a) \in \{\text{PERMIT}, \text{DENY}\}$$

However, pre-dispatch authorization guarantees only that the agent possessed permission to dispatch an action. It provides zero evidence regarding what occurred downstream when the network transport drops mid-flight. Consider the following concrete operational failure sequence:

1. **Mutation is dispatched:** The agent issues an authorized mutating remote call (`POST /debit`).
2. **Server commits:** The downstream service executes the business logic and successfully commits the transaction to its ledger.
3. **Response is lost:** The transport connection drops (e.g., an intermediate reverse proxy emits an HTTP 504 Gateway Timeout or tears down the TCP socket) before the acknowledgment reaches the caller.
4. **Agent sees a timeout:** The agent HTTP stack catches a transport-level error and reports a failure observation into the agent reasoning context.
5. **Retry changes the effective request identity:** Interpreting the timeout as non-execution, the agent loop re-attempts the operation. Due to stochastic context reconstruction (semantic drift), the agent generates a fresh client UUID, alters JSON whitespace, or rephrases transaction metadata.
6. **A second mutation commits:** Because the deduplication identity changed, conventional gateway idempotency filters treat the retry as a distinct operation, resulting in a duplicate state mutation (e.g., a double debit).

In the tested harness, the AEIB protocol prevents retries after an ambiguous post-dispatch fault, reconciles through an authoritative operation endpoint, and produces verifiable signed evidence without modifying the ledger engine.

### Contributions
1. **Disposition Model:** A formal seven-state disposition taxonomy for classifying post-dispatch outcomes.
2. **Mapping Contract:** A deterministic priority contract mapping transport observations and probe results to normative dispositions.
3. **Verifiable Receipts:** Ed25519-signed execution receipts binding transport observations to authoritative probe outcomes, verified via an offline tool.
4. **Control and Fault Benchmark:** A reproducible control matrix ($C_0, C_1, C_2$) demonstrating the boundary conditions of gateway deduplication under semantic drift, alongside an AEIB fault benchmark.
5. **Empirical Artifacts:** Public, unmocked run manifests, on-disk SQLite binary evidence, and falsification suites.

---

## 2. Problem and Threat Model

### 2.1 Formal Definitions
* **Logical Intent ($I$):** The semantic objective generated by an agent (e.g., *"Transfer 100 EUR to Account B"*), uniquely identified by an intent identifier.
* **Dispatch Attempt ($A_{I, k}$):** The $k$-th wire transmission attempting to execute intent $I$, containing payload $P_k$ and HTTP headers $H_k$.
* **Transport Observation ($T$):** The raw network or gateway signal returned to the caller, $T \in \{\text{HTTP 200}, \text{HTTP 504}, \text{TCP RST}, \text{EOF}, \dots\}$.
* **Downstream Mutation ($M$):** A state transition committed to persistent storage by the target service.
* **Authoritative Probe ($Q$):** An idempotent, out-of-band query against the target system's authoritative state store to ascertain the ground truth of intent $I$.
* **Semantic Drift:** Variations introduced into payload serialization $P_k$ or headers $H_k$ across successive retry attempts $k > 1$ due to non-deterministic agent context reconstruction.
* **Safety Invariant:** For any logical intent $I$, at most one downstream mutation may commit:
  $$\forall I, \quad \text{LedgerCommits}(I) \le 1$$

### 2.2 Explicit System Assumptions
1. **Reachable and Trustworthy Probe:** An out-of-band reconciliation endpoint or database query is available and reflects authoritative ledger state.
2. **Queryable Idempotency Identity:** The downstream service indexes operations by an intent identifier, deterministic idempotency key, or logical transaction ID.
3. **Execution Boundary Interception:** The interceptor resides on the egress path and can freeze further outbound retries upon detecting transport ambiguity.
4. **Accurate Outcome Reporting:** The target service reports truthful commit statuses (`COMMITTED`, `NOT_FOUND`, `CONFLICT`).
5. **Key Protection:** The receipt signing private key is protected within the execution environment.

---

## 3. Protocol and Taxonomy

We define a seven-state disposition taxonomy and evaluate it using seven synthetic conformance scenarios, supplemented by a 50-trial control matrix and a 50-trial AEIB fault benchmark.

| Disposition State | Entry Condition | Retry Permitted? | Required Evidence | Terminal Behavior |
| :--- | :--- | :---: | :--- | :--- |
| `OUTCOME_VERIFIED` | HTTP success response whose payload is validated, or an authoritative probe confirming the matching commit | **No** | HTTP 200 payload hash or authoritative probe commit record | Terminal (Success) |
| `DISPATCHED_UNCONFIRMED` | Ambiguous transport fault (504, TCP RST, EOF) | **No** (Frozen) | Transport observation, such as an HTTP 504 or recorded connection failure | Non-terminal (Quarantine) |
| `RECONCILIATION_NOT_FOUND` | Authoritative source, under the benchmark’s consistency and query assumptions, confirms that no matching mutation exists | **Yes** (Policy gate) | Authoritative probe confirmation that no matching mutation exists | Terminal (Safe to retry) |
| `RECONCILIATION_FAILED` | Target record found but payload hash diverges | **No** | Hash divergence record between dispatch and store | Terminal (Audit alert) |
| `RECONCILIATION_CONFLICT` | Conflicting records under same idempotency key | **No** | Multiple transaction IDs or concurrency conflict | Terminal (Locked) |
| `CONTEXT_POLICY_VIOLATION` | Action rejected pre-dispatch by policy engine | **No** | Policy enforcement denial log | Terminal (Refused) |
| `AUTHORITY_NOT_BOUND` | Delegation credential expired or unmeasured | **No** | Cryptographic token verification failure | Terminal (Refused) |

> **Definition Note on `RECONCILIATION_NOT_FOUND`:** This state explicitly signifies that the authoritative source, under the benchmark’s consistency and query assumptions, confirms that no matching mutation exists downstream. It must not be inferred merely because a generic query returned an empty set or timed out.

---

## 4. Implementation

The AEIB prototype consists of the following components:

```text
[ Pre-Dispatch ]           [ Wire Egress ]         [ Fault Intercept ]       [ OOB Probe ]          [ Offline Verification ]
Canonical JSON Subset ──► UUIDv5 Idempotency ──► Trap HTTP 504 / RST ──► GET /operations/{id} ──► Ed25519 Signed Receipt
Payload Digest (H)        Header Injected        Freeze Retries           Authoritative State     Verified Offline
```

1. **Documented Canonical JSON Subset:** Enforces deterministic key ordering (lexicographical sorting), compact delimiters (`:`, `,`), and standard UTF-8 encoding. It provides deterministic hashing for the tested payloads without asserting full formal JCS-compatible certification.
2. **Payload Digest ($H$):** Computes $H = \text{SHA-256}(\text{CanonicalJSON}(P))$.
3. **Deterministic Idempotency Key Derivation:** Computes a UUIDv5 anchored to a dedicated AEIB namespace:
   $$K = \text{UUIDv5}(\text{Namespace}_{\text{AEIB}}, \text{"urn:aeib:payload:"} \parallel H)$$
   This key is injected into the outbound `Idempotency-Key` header, binding transport deduplication directly to canonical payload content.
4. **Retry Lock:** Upon encountering a 504, TCP RST, or connection drop, the interceptor marks the execution context with `retry_permitted: false`, preventing the agent runtime from dispatching speculative retries.
5. **Authoritative Probe Interface:** Dispatches an idempotent query against `GET /operations/{id}` to verify commit state.
6. **Receipt Structure & Signing:** Generates a structured JSON receipt binding `unsigned_payload`, `unsigned_payload_hash`, `idempotency_key`, `disposition`, `retry_permitted`, and `transport_evidence_hash`. Signs the signable view using Ed25519.
7. **Offline Verifier:** `aeib_verify.py` provides standalone, zero-dependency cryptographic verification of receipts, checking signatures, digest linkages, and schema compliance.

---

## 5. Evaluation

### 5.1 The Control Matrix Benchmark
We evaluated four execution conditions in a local deterministic harness under identical post-commit 504 fault injection (a synthetic 5 ms delay followed by socket severance immediately following database commit). Naive retry ($C_0$) and semantic-drift retry ($C_2$) each violated the at-most-one-commit invariant in 50 of 50 trials (100.0% duplicate rate). A stable-key gateway baseline ($C_1$) violated it in 0 of 50 trials (0.0% duplicate rate), establishing that the benchmark does not model idempotency as inherently ineffective. Under the same post-commit 504 fault, AEIB produced 0 duplicate mutations in 50 trials (0.0% duplicate rate) and verified 50 of 50 signed receipts. In 20 non-commit controls, AEIB produced 0 false `OUTCOME_VERIFIED` results, resolving strictly to `RECONCILIATION_NOT_FOUND`. These results characterize the tested implementation and fault model; they do not establish production-wide or universal exactly-once guarantees.

| Condition / Baseline | Trials | Safety Violations | Duplicate Rate | False Verification | Resolution |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **$C_0$ (Naive Client Retry)** | 50 | 50 | **100.0%** | N/A | Duplicate ledger commit |
| **$C_1$ (Gateway + Stable Key)** | 50 | 0 | **0.0%** | N/A | Deduplicated by gateway cache |
| **$C_2$ (Gateway + Semantic Drift)** | 50 | 50 | **100.0%** | N/A | Duplicate ledger commit |
| **AEIB Post-Commit 504** | 50 | 0 | **0.0%** | **0.0%** ($0/50$) | Authoritative probe & signed receipt |
| **AEIB Non-Commit Controls** | 20 | 0 | **0.0%** | **0.0%** ($0/20$) | Resolved to `RECONCILIATION_NOT_FOUND` |

> **Scope and Environmental Boundary:** The benchmark evaluates a deterministic local fault model with a SQLite ledger, an in-process gateway/fault injector, and a defined semantic-drift retry behavior. It does not establish equivalent rates for arbitrary agents, gateways, databases, network stacks, or production deployments.
>
> **Semantic-Drift Scope Qualification:** $C_0$ and $C_2$ demonstrate failure under the benchmark's specific semantic-drift model (context reconstruction mutating UUIDs, formatting whitespace, or metadata); they do not establish that all LLM agents or all enterprise gateways behave identically. Rather, they establish the boundary condition where conventional gateway deduplication breaks down once representation identity is lost.

### 5.2 Single-Run Ledger and Transcript Listing
To demonstrate the concrete failure mode, Listing 1 shows the single-run ledger and transcript from trial `I-001`. Under $C_0$, the backend committed debit `D-001`, but transport severance returned an HTTP 504. The client retried, committing duplicate debit `D-002`. Under AEIB, the 504 was trapped, retries were frozen, and the out-of-band probe reconciled `I-001` to `OUTCOME_VERIFIED` with zero duplicate debits.

```text
======================= C0 TRIAL I-001: DUPLICATE MUTATION =======================
[Ledger Commit 1] tx_id=1, intent_id=I-001, debit_id=D-001, amount=100.0, balance=9900.0
[Wire Fault]      HTTP 504 Gateway Timeout injected 5ms post-commit
[Client Retry]    Agent retries with intent_id=I-001, new key K-001-retry
[Ledger Commit 2] tx_id=2, intent_id=I-001, debit_id=D-002, amount=100.0, balance=9800.0
Result: 2 committed debits for 1 logical intent (Safety Violation).

====================== AEIB TRIAL I-001: RECONCILED BOUNDARY =====================
[Ledger Commit 1] tx_id=1, intent_id=I-001, debit_id=D-001, amount=100.0, balance=9900.0
[Wire Fault]      HTTP 504 Gateway Timeout intercepted by AEIB sidecar
[State Machine]   Entered DISPATCHED_UNCONFIRMED; retry_permitted=False
[Probe Execution] GET /operations/I-001 -> status=COMMITTED, commit_count=1
[State Machine]   Transitioned to OUTCOME_VERIFIED; emitted Ed25519 signed receipt
Result: 1 committed debit; zero duplicates; receipt verified offline.
```

### 5.3 Latency & Overhead Analysis

**Statistical Confidence:** Applying the Rule-of-Three to the 0/50 duplicate rate yields a 95% confidence upper bound failure rate of <5.8%. For the 0/20 false positive rate, the upper bound is <13.8%.

**Test Environment:** The local test harness utilizes an SQLite 3.53.1 bitemporal ledger, in-memory socket, `GET /operations/{id}` query, N=50 sample size, and standard numpy 95th percentile method.

The final tagged release measured 9.22 ms mean and 9.59 ms p95, measured from client dispatch through the 5 ms post-commit delay, 504 interception, authoritative probe, canonical payload hashing, Ed25519 signing, and receipt assembly.

### 5.4 Checks Supporting Concrete Local Execution and Falsifiability
To provide verifiable confidence that the benchmark evaluates concrete components and empirical state rather than synthetic stubs, we execute a 20-test validation suite:
1. **Absence of Common Mocking APIs:** Static AST analysis of the benchmark suite confirms zero usage of standard mocking APIs (`unittest.mock`, `MagicMock`, `patch`).
2. **On-Disk SQLite Ledger:** The ledger persists rows to an on-disk SQLite binary database (`ledger.db`) whose tables and debit records can be inspected independently with the standard `sqlite3` CLI. Each benchmark run explicitly resets state (`store.reset_ledger()`) to establish clean ground truth.
3. **Deterministic Fault Injection:** The fault injector is an explicit, deterministic ASGI middleware component rather than an unmonitored external network anomaly.
4. **Cryptographic Tamper Sensitivity:** Receipt tampering tests cause independent signature verification to fail: all attempted one-bit payload tampering and one-byte signature corruption cases were rejected by the verifier with `InvalidSignature`.
5. **Fail-Closed Negative Controls:** In 20 uncommitted control trials, the non-commit path was exercised, with all 20 trials strictly producing `RECONCILIATION_NOT_FOUND` and zero false `OUTCOME_VERIFIED` results.
6. **Suite Composition:** The 20 tests comprise the 15 baseline tests (6 deterministic control matrix tests in `test_control_matrix.py` and 9 eBPF quarantine controller tests in `test_ebpf_controller.py`) plus the 5 falsifiability checks in `test_falsifiability.py`.

---

## 6. Authoritative Probe Architecture & Database Reference Interface

In the reported benchmark, the authoritative probe is evaluated against a local SQLite store in Write-Ahead Logging (WAL) mode with strict ACID balance enforcement. The probe queries `operations` and `debit_ledger` tables using standard SQL transactions.

To support enterprise distributed deployments, AEIB specifies the `PostgresOutcomeProbeAdapter` interface for PostgreSQL backends. This adapter queries transaction status using parameterized SQL:
```sql
SELECT status, commit_timestamp, transaction_id 
FROM transaction_ledger 
WHERE idempotency_key = $1;
```
This work validates the probe protocol against the local SQLite store; evaluation against distributed production PostgreSQL clusters constitutes an ongoing research milestone.

---

## 7. Related Work

* **Idempotency and Exactly-Once Limitations:** Distributed systems research has established that exactly-once semantics across unreliable networks cannot be solved at the transport layer alone (Two Generals Problem, FLP impossibility). IETF specifications (RFC 7231, JCS-compatible) and modern API gateways provide idempotency caching based on header keys and payload hashes. AEIB demonstrates the boundary conditions where agentic semantic drift causes representation divergence, defeating gateway caches.
* **Distributed-Systems Failure Semantics:** Traditional distributed patterns such as the Transactional Outbox and Saga Orchestrators coordinate multi-step transactions across trusted internal microservices. AEIB addresses the distinct client-side problem where an autonomous agent invokes an external third-party interface across an untrusted network.
* **Receipts and Transparency Systems:** IETF Internet-Drafts such as `draft-ietf-scitt-architecture` and `draft-birkholz-scitt-receipts` define supply chain transparency and receipt models. `draft-zambo-aer1` specifies Agent Execution Receipts. AEIB provides a concrete transport-to-disposition mapping contract and retry-control protocol that feeds structured receipts into downstream transparency ledgers.
* **Agent Authorization and Runtime Controls:** Runtime governance systems (such as P0 Security, Delinea, and Saviynt) enforce pre-dispatch policy allowlisting. AEIB operates downstream of these systems, addressing post-dispatch transport ambiguity.
* **Hardware-Backed Attestation:** Projects such as TRACE and confidential computing architectures (AMD SEV-SNP, Intel SGX) provide hardware-rooted execution attestation within enclaves. AEIB operates as a lightweight software protocol focused on transport-level reconciliation, orthogonal to hardware enclaves.

---

## 7. Prior Art & Interoperability Targets
AEIB aims for conceptual alignment with emerging literature and standards. The following frameworks are cited as **informational prior art and interoperability targets**, rather than formally tested standards in this benchmark:
- **AER-1 / AEB:** Agent Execution Receipt and Agent Execution Boundary concepts.
- **AAC:** Agent Action Capsule structures.
- **CAID:** Causal Action Identifiers for semantic identity.
- **EffectMatch & EMILIA:** Frameworks for deterministic side-effect reconciliation.
- **GRIP:** Gateway Receipt Integrity Protocols.

## 8. Limitations and Conclusion

### 8.1 Limitations
1. **Synthetic Benchmark Environment:** Evaluated in a local harness with simulated post-commit network faults.
2. **Single Database Engine Evaluated:** The reported benchmark uses SQLite WAL mode; multi-node distributed database clusters (PostgreSQL, CockroachDB) remain to be tested under production load.
3. **No Production Deployment:** This work presents an experimental prototype and evaluation harness; it is not a production service.
4. **No Universal Exactly-Once Proof:** AEIB demonstrates zero duplicate mutations under the tested harness and assumptions; it does not constitute a formal proof of universal safety across arbitrary failure topologies.
5. **No Standards or Compliance Certification:** Regulatory requirements (such as DORA Article 17 or EU AI Act Article 14) motivate the need for durable operational evidence; this work makes no compliance or certification claim. AEIB produces evidence that may support assessment activities; it does not determine regulatory applicability or certify compliance.
6. **Canonical JSON Subset:** Implements a documented canonical JSON subset rather than formal JCS-compatible conformance certification.
7. **Security Assumptions:** Receipt integrity depends on secure local storage of the Ed25519 signing key and the trustworthiness of the authoritative probe.

### 8.2 Conclusion
The "Retry or Else" assumption in autonomous AI agent architectures is fundamentally unsafe under post-dispatch transport ambiguity. When agents suffer semantic drift during retry loops, conventional API gateways fail to deduplicate transactions, resulting in duplicate mutations. By enforcing pre-dispatch canonicalization, retry freezing, out-of-band state reconciliation, and cryptographic attestation, AEIB demonstrates zero duplicate mutations and zero false positive outcome verifications across the reported deterministic trials.

---

## Artifact Availability and Reproducibility

* **Repository:** `https://github.com/SovereignNexus/smaos` (Branch: `release/v0.2.0`, Target Tag: `v0.2.2`)
* **Component Commit Provenance:**
  - Control Benchmark Commit: `68575eaa8067935ef19b783af508ff89c4d03c28`
  - AEIB Execution Boundary Commit: `bd0d845b8c57fa8d90fa35599ebdb9c54f8fce0d`
  - Adversarial Falsifiability Commit: `f1ff34fbac7694cac81a2b1af14eef504a922a0f`
* **Master Release Manifest:** `benchmarks/fault_injection/results/RELEASE_MANIFEST_v0.2.2.json`
* **Single Run Evidence Hash:** `8ba5b43c40664b5f8c8c953a331477338abfc3e80696f7cfb5d52beaab2d46de`
* **On-Disk SQLite Database:** `benchmarks/fault_injection/results/ledger.db`
* **Replication Commands:**
  ```bash
  # Run the complete 20-test validation suite (incorporating the 15 baseline tests + 5 falsifiability proofs)
  PYTHONPATH=. .venv/bin/pytest benchmarks/fault_injection/test_falsifiability.py benchmarks/fault_injection/tests/test_control_matrix.py tests/test_ebpf_controller.py -v

  # Run the 50-trial benchmark matrix
  PYTHONPATH=. .venv/bin/python benchmarks/fault_injection/client_matrix.py --runs 50
  ```
