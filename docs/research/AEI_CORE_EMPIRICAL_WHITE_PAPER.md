# Post-Dispatch Integrity in Autonomous Agent Workflows: Empirical Evaluation of the AEI Core Middleware Prototype

**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus Project)  
**Date:** October 2026  
**Artifact Revision:** `aei_core_middleware-v0.3.0-prototype`  
**Test Suite:** `tests/test_aei_core_middleware.py`, `tests/test_aei_adversarial.py`  

---

## 1. Control Objective & Failure Mode Formulation

Autonomous agent architectures (such as ReAct loops, LangGraph state machines, or tool-calling models) interact with external systems by invoking mutating network procedures (`POST /transfer`, `tools/call`, database writes). 

### The Post-Dispatch Ambiguity Gap
When a client application dispatches a mutating network request, three distinct failure topologies can occur across the transport boundary:
1. **Pre-Commit Failure ($F_{\text{pre}}$):** The network drops before reaching the downstream server. The mutation never occurs.
2. **Deterministic Server Rejection ($F_{\text{rej}}$):** The downstream server rejects the payload (e.g., HTTP 400 or 422). No mutation occurs.
3. **Post-Commit Transport Severance ($F_{\text{post}}$):** The downstream server receives the request, executes the transaction, and commits changes to its persistent datastore. However, the return path experiences an abnormal termination (HTTP 504 Gateway Timeout, connection reset, or proxy drop).

In failure mode $F_{\text{post}}$, the agent client observes only a transport-level error. Because the caller lacks visibility into downstream execution state, standard agent exception-handling policies default to speculative, blind retries. If the agent loop re-dispatches the action, a second mutation occurs, causing duplicate transactions and reconciliation drift.

Furthermore, when agent loops re-prompt the LLM following an exception, **semantic drift** frequently occurs: the model alters the idempotency key or rephrases arguments, rendering downstream deduplication caches ineffective.

The **AEI Core Middleware** (`src/aei_core_middleware.py`) prototype was built to evaluate a minimal software boundary that intercepts ambiguous transport outcomes, freezes speculative retries, queries an authoritative out-of-band probe, and cryptographically signs the final disposition.

---

## 2. Experimental Architecture

The evaluated prototype operates as a middleware wrapper around agent tool calls:

```
[ Agent Tool Call ]
       │
       ▼
[ Pre-Dispatch Guard ] ──(Duplicate or Drifted Key?)──► [ Block Re-dispatch ]
       │
       ▼
[ Transport Execution ] ──(HTTP 504 / Drop)──► [ Freeze Loop: UNKNOWN ]
       │                                                 │
       │ (200 OK)                                        ▼
       │                                     [ Authoritative OOB Probe ]
       ▼                                                 │
[ CONFIRMED Receipt ]                         ┌──────────┴──────────┐
                                              ▼                     ▼
                                     [ Row Found ]          [ Row Absent ]
                                              │                     │
                                     [ OUTCOME_VERIFIED ]  [ RECONCILIATION_NOT_FOUND ]
                                     (retry_permitted=F)   (retry_permitted=T)
```

### Components Evaluated:
1. **`AeiCoreMiddleware`**: Interposes between the agent loop and downstream callables.
2. **`@aei_guard`**: Python decorator wrapping standard tool functions.
3. **Out-of-Band (OOB) Probe Adapter**: Direct query mechanism inspecting datastore ground truth using the original `idempotency_key`.
4. **Deterministic Sealer & Offline Verifier**: Formats disposition statements using RFC 8785 JSON Canonicalization Scheme (JCS) and signs them with Ed25519.

---

## 3. Empirical Test Results

The prototype was subjected to five automated adversarial and stress test suites (`tests/test_aei_adversarial.py`).

| Test Vector | Evaluated Scenario | Unprotected Baseline Outcome | AEI Guarded Prototype Outcome | Result |
| :--- | :--- | :--- | :--- | :--- |
| **T1: Blind Retry Storm** | 50 rapid retry attempts following a post-commit HTTP 504 drop | 50 duplicate mutations | Exactly 1 mutation committed; 49/49 retries intercepted before wire | **PASS** |
| **T2: Idempotency-Key Drift** | Agent re-prompts after drop and alters key from `v1` to `v2` for same `action_id` | Duplicate mutation executed under drifted key | `IdempotencyKeyDriftError` raised; 0 duplicate mutations | **PASS** |
| **T3: Evidence Tampering** | 1-byte modification of canonical payload, altered SHA-256 digest, or flipped signature bits | Silent acceptance of tampered audit logs | 100% of tampered records rejected with `ValueError` or `InvalidSignature` | **PASS** |
| **T4: Probe Outage** | Out-of-band probe itself times out or encounters network partition | Speculative blind retry executed | Fail-closed quarantine: marked `PROBE_OUTAGE_HOLD`, `retry_permitted=False` | **PASS** |
| **T5: Decorator Integration** | Multi-turn agent loop calling decorated tool function under post-commit loss | Agent loop executes duplicate debit on turn 2 | Turn 2 blocked with `DuplicateExecutionBlockedError`; server mutations = 1 | **PASS** |

### Statistical Bounds:
Under the sample sizes tested in the local testbed ($N=50$ for retry storm iterations, $N=20$ for negative/outage controls):
* The observed rate of duplicate mutations under post-commit loss was $0/50$. Applying the Rule of Three, this provides an approximate 95% upper bound of **$5.8\%$** for the underlying failure probability under this specific local trial model.
* The observed rate of unhandled probe failures was $0/20$, yielding an approximate 95% upper bound of **$15.0\%$**.
* *These empirical bounds reflect local testbed conditions and do not establish universal zero-failure guarantees.*

---

## 4. Mapping to Regulatory Expectations

The AEI Core prototype investigates technical mechanisms that map to emerging regulatory and governance frameworks without claiming certified compliance:

* **DORA (Digital Operational Resilience Act - Regulation EU 2022/2554):**
  - *Article 17 (Incident Classification & Reporting):* Requires financial entities to record, log, and classify major ICT-related incidents. Halting ambiguous agent states and logging signed disposition receipts provides structured diagnostic data for incident response timelines.
  - *RTS on ICT Risk Management (EBA/RTS/2024/1772):* Emphasizes data integrity and prevention of duplicate processing across communication disruptions.
* **EU AI Act (Regulation EU 2024/1689):**
  - *Article 12 (Record-Keeping):* Mandates technical logging capabilities for high-risk AI systems to ensure traceability throughout the system lifecycle. The JCS + Ed25519 disposition records provide an immutable, post-hoc audit trail of tool decisions.

*Disclaimer: Implementation of this prototype does not constitute formal certification, legal advice, or guaranteed compliance with EU DORA, the EU AI Act, or GDPR.*

---

## 5. Prototype Limitations & Production Guidance

To maintain rigorous scientific and engineering boundaries, the prototype's current limitations must be distinguished from production requirements:

### Current Prototype Limitations
1. **In-Memory Concurrency Scope:** The current middleware tracks `disposition_history` and `action_to_key` mappings within a single Python process memory space. It does not synchronize state across multi-node agent worker clusters.
2. **Synchronous Probe Latency:** The OOB probe runs synchronously within the exception handling block. High-latency database queries will add operational delay to agent cycle times.
3. **Static Key Management:** Signing keys are generated locally or loaded from flat files; there is no integration with Hardware Security Modules (HSMs) or automated key rotation lifecycles.
4. **Transport Protocols:** Currently evaluated against simulated HTTP and standard socket drops; WebSockets, gRPC streaming, and bidirectional JSON-RPC transports are unverified.

### Production Guidance for Systems Engineers
* **Distributed State Synchronization:** In multi-node agent deployments, the `action_to_key` and disposition registries must be backed by a high-availability distributed lock and store (e.g., Redis with Redlock, etcd, or PostgreSQL with advisory locks).
* **Asynchronous Reconciliation Queues:** If downstream database probes take longer than typical agent SLA thresholds ($>200\text{ ms}$), the action should be placed in an asynchronous dead-letter or human-in-the-loop (HITL) triage queue rather than blocking worker threads.
* **Cryptographic Key Infrastructure:** Production deployments should delegate Ed25519 signing to managed cloud KMS (AWS KMS, GCP Cloud KMS, Azure Key Vault) or PKCS#11 HSMs with audited access policies.
