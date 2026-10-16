# AEIB Production Assurance Package v1.1
## Agent Execution Integrity Boundary — Production Assurance Dossier

> **EPISTEMIC & REGULATORY NOTICE:**
> This dossier compiles technical evidence, structural architecture, state-machine specifications, and test evaluation records for the Agent Execution Integrity Boundary (AEIB v1.1).
> AEIB produces operation-level cryptographic evidence that may support an institution's AI governance, audit, and operational-resilience programs. It does not by itself confer statutory compliance with the EU AI Act (Regulation (EU) 2024/1689), DORA (Regulation (EU) 2022/2554), or US Banking Guidance (SR 26-2). Operation requires the deploying entity to configure and maintain boundary enforcement within their own infrastructure and provide an authenticated target status receiver for reconciliation.

---

### Section 1: Release Identity & Artifact Manifest

* **Release Tag:** `v1.1.0-temporal-standing`
* **Release Target Architecture:** Java 21 LTS / GraalVM Native Runtime & Python 3.14 Reference Verifier
* **Cryptographic Primitives:**
  * Canonicalization: RFC 8785 JSON Canonicalization Scheme (JCS)
  * Signature Scheme: Strict Ed25519 (RFC 8032)
  * Action Idempotency Anchor: SHA-256 over RFC 8785 canonical mutation parameters (`CAID`)
  * Serialization / Enveloping: RFC 8785 JCS (Primary) & RFC 9052 COSE_Sign1 / RFC 8949 CBOR (Secondary Profile)
* **Core Artifact Manifest:**

| Artifact Component | File Path | Digest (SHA-256) / Status |
| :--- | :--- | :--- |
| EO-1 Pre-Dispatch Interlock | `src/eo1_write_before_execute.py` | Observed in local test harness |
| RFC 8785 Canonicalizer | `src/jcs_canonicalizer.py` | 25/25 RFC 8785 conformance vectors verified |
| Single-Use Durable Authority Store | `v1.1-roadmap/tier1_durable_executor.py` | Fsync-backed restart persistence verified |
| 14 Assessment Rehearsals | `tests/test_assessment_rehearsal_14.py` | 14/14 local execution tests passing |
| 5-Arm Comparative Benchmark | `benchmarks/aeib_execution_integrity/run_5arm_benchmark.py` | 500 episodes / 15 fault vectors evaluated |
| Sealed Evidence Pack | `artifacts/aeib-pilot-evidence-pack-v1.1.0.tar.gz` | `13bc5143ac7c51722a2dd2d3d02df7641405eb54e3f59d9b0fc1e2c96c5c9655` |
| Standalone Evidence Verifier | `tools/verify_phase3_evidence.py` | Standalone clean-room CLI verifier |
| Grounded DORA Incident Exporter | `tools/export_dora_art17_evidence.py` | Separates operational evidence, classification, and filing |

---

### Section 2: Grounded Physical & Logical Topology

The operational boundary is evaluated as an explicit network and process gate situated strictly between untrusted agent execution environments and protected core financial systems.

```
+-------------------------------------------------------------------------------+
| ZONE 1: Untrusted Agent Execution Domain (LLM / Framework / Orchestrator)    |
|   - Generates untrusted CandidateAction proposals                             |
|   - May experience stochastic prompt drift, hallucinated args, or tool abuse   |
|   - Zero direct network egress to Zone 3 core services                        |
+---------------------------------------+---------------------------------------+
                                        | CandidateAction JSON
                                        v
+-------------------------------------------------------------------------------+
| ZONE 2: Agent Execution Integrity Boundary (AEIB Appliance / Gateway)        |
|   - Station 0: Zero-allocation parameter admission and typing validation       |
|   - Station 1: Temporal standing check & single-use ticket burn (fsync)      |
|   - Station 2: EO-1 Write-Ahead Ledger commit (`DISPATCH_INTENT` Ed25519)     |
|   - Station 3: Physical Socket Dispatch with L7 wire fault latching          |
|   - Station 4: Bounded Out-of-Band Reconciliation (`refund_status_v1`)        |
|   - Station 5: Hash-chained continuity receipt emission (`CONTINUITY_RECEIPT`)|
+---------------------------------------+---------------------------------------+
                                        | Authenticated Dispatch (X-AEIB-CAID)
                                        v
+-------------------------------------------------------------------------------+
| ZONE 3: Core Enterprise Infrastructure (Payment Rails / Core Banking / DB)   |
|   - Primary authoritative ledger                                              |
|   - Exposes transactional mutation endpoints (e.g. POST /v1/refunds)          |
|   - Exposes authenticated read-only status receiver (POST /v1/refund_status)   |
+-------------------------------------------------------------------------------+
```

---

### Section 3: Trust Boundaries & 3-Tier Hierarchy

AEIB establishes an explicit trust hierarchy that strictly prevents lower-trust agent claims from impersonating boundary-enforced or target-attested states:

```
[ LEVEL 1: Agent-Signed Context ]
  - Scope: Untrusted prompt text, internal reasoning tokens, ephemeral rationale.
  - Assurance: Low. Stripped before hashing; cannot satisfy Level 2 or Level 3 gates.
         |
         v
[ LEVEL 2: Boundary-Signed Evidence ]
  - Scope: Pre-dispatch `DISPATCH_INTENT` and `CONTINUITY_RECEIPT` hash-chain records.
  - Assurance: High. Signed by AEIB boundary Ed25519 private key after local fsync.
         |
         v
[ LEVEL 3: Target-Attested Reconciliation ]
  - Scope: Target core banking receiver confirmations (`refund_status_v1`).
  - Assurance: Authoritative. Attested directly by the downstream primary ledger.
```

---

### Section 4: Threat Model & Consequence-Weighted Classification

Rather than relying on misleading aggregate accuracy pass-rates, AEIB stratifies execution risks into three consequence-weighted operational tiers:

```
+-------------------------------------------------------------------------------+
| TIER A: Zero-Tolerance / Irreversible External Mutations                      |
| Examples: Financial disbursements, refunds, account debits, wire transfers.   |
| Boundary Requirement:                                                         |
|   - Commit pre-dispatch intent to immutable ledger before socket allocation.  |
|   - Zero blind retries under transport ambiguity (HTTP 504 / TCP RST).        |
|   - Latch immediately into `EFFECT_INDETERMINATE`.                            |
|   - Require target-attested reconciliation or human review before re-dispatch.|
+-------------------------------------------------------------------------------+
| TIER B: Recoverable Review Cost / Bounded Uncertainty                         |
| Examples: Policy escalations, transport timeouts, ambiguous status queries.   |
| Boundary Requirement:                                                         |
|   - Preserve uncertainty (`disposition: EFFECT_INDETERMINATE`).              |
|   - Enforce bounded probe budget (`ProbeBudget: 1`) against primary ledger.   |
|   - Route to human step-up queue upon probe exhaustion without guessing.      |
+-------------------------------------------------------------------------------+
| TIER C: Observability & Read-Only Queries                                     |
| Examples: Account balance reads, transaction history queries, policy checks.   |
| Boundary Requirement:                                                         |
|   - Pass-through telemetry projection to OpenTelemetry collectors.            |
|   - Strictly isolated: Telemetry failures cannot alter enforcement decisions. |
+-------------------------------------------------------------------------------+
```

---

### Section 5: State Machine & Lifecycle Transitions

```
[Proposal Received]
       |
       v
[Station 0: Schema & Parameter Validation]
       |
       +---> Invalid Scheme / Host / Path Traversal ----> REJECTED (Fail-Closed)
       v
[Station 1: Authority Standing Check]
       |
       +---> Stale / Revoked / Already Consumed --------> HALTED (Zero Egress Bytes)
       v
[Station 2: EO-1 Write-Ahead Ledger Commit]
       |
       +---> Disk Full / IO Error ----------------------> HALTED (Zero Wire Access)
       v
[Station 3: Physical Dispatch]
       |
       +---> HTTP 200 OK -------------------------------> RECONCILED (Success Receipt)
       |
       +---> HTTP 504 / TCP RST / Timeout
             |
             v
[LATCHED: EFFECT_INDETERMINATE (retry_safe: false)]
             |
             v
[Station 4: Target Reconciliation Probe (Budget: 1)]
             |
             +---> Target Confirms COMMITTED -----------> RECONCILED (Success Receipt)
             |
             +---> Target Confirms NOT_FOUND -----------> CLEARED_FOR_RETRY
             |
             +---> Inconclusive / Probe Timeout --------> ESCALATED (Human Resolution Queue)
```

---

### Section 6: The `refund_status_v1` Target Contract

To resolve post-dispatch transport ambiguity without blind mutation attempts, downstream services implement an authenticated status contract:

```yaml
contract_id: "urn:aeib:contract:refund_status:v1"
request:
  method: "POST"
  path: "/v1/refund_status"
  headers:
    X-AEIB-CAID: "sha256:<64-hex>"
    Authorization: "Bearer <service-token>"
  body:
    caid: "sha256:<64-hex>"
    operation_id: "string"

response:
  status_code: 200
  body:
    caid: "sha256:<64-hex>"
    operation_id: "string"
    target_state: "COMMITTED | NOT_FOUND | PENDING | ROLLED_BACK"
    settled_at: "ISO-8601 UTC timestamp or null"
    receiver_signature: "base64 Ed25519 signature over canonical status"
```

---

### Section 7: The 14 Assessment Rehearsals

The AEIB test harness exercises 14 fault-injection assessment rehearsals to evaluate operational resilience under controlled failure modes:

| # | Rehearsal Scenario | Fault Injection Mechanism | Observed Evaluation Outcome |
| :--- | :--- | :--- | :--- |
| **01** | Fresh-checkout reproduction | Clean environment build from pinned commits | 100% reproduction across all test suites |
| **02** | Positive control | Valid ticket, reachable mock core banking target | Dispatch succeeds; `CONTINUITY_RECEIPT` emitted |
| **03** | Stale / revoked authority | Stale policy epoch or burned single-use ticket | Immediate halt; `0` bytes transmitted |
| **04** | Check-to-dispatch race | Revocation token processed mid-flight before socket | Interlock catches latch; dispatch aborted |
| **05** | Concurrent ticket use | 10 concurrent threads attempt single ticket burn | Exactly 1 succeeds; 9 rejected fail-closed |
| **06** | Restart after consumption | Process restart after ticket consumption | Consumed state retained; reuse blocked |
| **07** | Crash around intent persistence | Unfulfilled `DISPATCH_INTENT` on startup | Startup recovery latches `EFFECT_INDETERMINATE` |
| **08** | Target commits, response lost | Simulated HTTP 504 after primary database commit | Out-of-band probe resolves state; zero duplicates |
| **09** | Target never becomes observable | Primary replica lag and timeout probe exhaustion | Remains latched; escalates to human review |
| **10** | Forged target evidence | Mismatched `operation_id` in reconciliation payload | Reconciliation rejected; latch preserved |
| **11** | Halt before/after dispatch | Emergency Andon-cord flag activated | Future dispatches refused; history preserved |
| **12** | Evidence-store outage | Write-ahead ledger storage made unwritable | Dispatch halted fail-closed before socket open |
| **13** | Tampered evidence pack | 1-bit flip in historical continuity receipt | Public key verification detects tampering |
| **14** | Restore from backup | Restore ledger and state directory from backup | Latched operations preserved; replay refused |

*Evaluation Result:* 14/14 tests passing (`pytest tests/test_assessment_rehearsal_14.py`).

---

### Section 8: Standalone Offline Verifiers

AEIB provides clean-room, zero-dependency offline verifiers in both Python 3 and Java 21 to enable independent verification of evidence archives without running the boundary runtime:

1. **Python Clean-Room Verifier:** `tools/verify_phase3_evidence.py`
   * Recomputes RFC 8785 JCS canonical bytes for all receipts and manifests.
   * Validates Ed25519 signatures against embedded or provided PEM public keys.
   * Asserts physical transport invariants (e.g. `bytes_received == 0` on rejected dispatches).
2. **Java 21 / GraalVM Verifier:** `aeib-native-runtime/aeib-verifier/`
   * Implements strict RFC 8785 canonicalization and Ed25519 verification.
   * Evaluated across cross-language differential test suites (`benchmarks/jvm_native_diff_engine.py`) with 0-byte divergence observed.

---

### Section 9: Operational Runbooks

The operational runbook suite defines deterministic procedures for runtime event handling:

* **RB01 (Uncertain Mutation Triage):** Procedure for triaging `EFFECT_INDETERMINATE` latches when automated probes are exhausted.
* **RB02 (Compromise Quarantine):** Rapid isolation and credential revocation for suspected agent key compromise.
* **RB03 (Storage IO Fail-Closed):** Immediate fail-closed halt protocol upon disk persistence or ledger write failures.
* **RB04 (Key Rotation & SPKI Anchoring):** Boundary Ed25519 key rotation with Subject Public Key Info (SPKI) continuity tracking.
* **RB05 (Policy Epoch Advance):** Epoch advancement protocol that instantaneously invalidates all pre-issued single-use tickets.

---

### Section 10: DORA & EU AI Act Grounded Regulatory Crosswalk

AEIB maps technical execution evidence to specific statutory requirements without claiming absolute conformity:

```
+-------------------------------------------------------------------------------+
| EU AI ACT (Regulation (EU) 2024/1689)                                         |
|   - Article 12 (Record-Keeping & Logging): Automatic immutable logging of     |
|     events over the AI system lifecycle via Ed25519-signed hash chains.      |
|   - Article 14 (Human Oversight): Bounded uncertainty preservation and        |
|     deterministic routing to human review upon probe exhaustion.              |
|   - Article 15 (Accuracy, Robustness & Cybersecurity): Resilience against      |
|     prompt injection, tool parameter tampering, and post-dispatch wire faults.|
+-------------------------------------------------------------------------------+
| DORA (Regulation (EU) 2022/2554)                                              |
|   - Article 17 (ICT Incident Management & Classification): Standardized       |
|     export separating operational evidence from internal incident assessment.|
|     4-hour clock explicitly documented as running from major-incident         |
|     classification, not from initial HTTP timeout.                            |
|   - Note: DORA Article 28 (Register of Information) is explicitly excluded    |
|     from AEIB scope as an entity-level governance artifact.                   |
+-------------------------------------------------------------------------------+
```

---

### Section 11: 5-Arm Comparative Benchmark Evidence

Evaluated across 500 deterministic episodes and 15 fault vectors (`seed=42`):

| Metric / Parameter | Arm 1: Naive Retry | Arm 2: Prompt Drift | Arm 3: Server Stable | Arm 4: Stable + Probe | Arm 5: AEIB v1.1 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Total Evaluated Episodes** | 500 | 500 | 500 | 500 | 500 |
| **Observed Duplicate Mutations** | 302 | 187 | 0 | 0 | **0** |
| **Duplicate Mutation Rate** | 60.4% | 37.4% | 0.0% | 0.0% | **0.0%** |
| **Unresolved Episodes (Limbo)** | 0 | 0 | 198 (39.6%) | 0 | **0** |
| **EO-1 Pre-Dispatch Journal** | No | No | No | No | **Yes (500 entries)** |
| **Signed Continuity Receipts** | No | No | No | No | **Yes (368 receipts)** |
| **Offline Verifiability** | No | No | No | No | **Yes (Ed25519 JCS)** |
| **Crash-Safe Recovery** | No | No | No | No | **Yes (Startup Latch)** |
| **95% Rule-of-Three Bound** | N/A | N/A | N/A | N/A | **<= 0.6%** |

---

### Section 12: Production Assumptions, Operational Limitations, and Epistemic Boundary Notice

1. **Deployer Infrastructure Responsibility:** AEIB operates as an architectural boundary. Deploying institutions must host the boundary appliance in an isolated network segment (Zone 2) with locked firewall rules preventing direct egress from agent containers (Zone 1) to financial APIs (Zone 3).
2. **Target Idempotency & Reconciliation Prerequisite:** Downstream APIs must support idempotent mutation handling (e.g. via `X-AEIB-CAID`) and provide an authenticated target reconciliation status endpoint (`refund_status_v1`).
3. **Scaffolding Boundaries:** eBPF filters and hardware enclave attestation modules in the repository represent structural scaffolding and do not provide live kernel or TDX hardware attestation unless compiled and executed on supported target hardware.
4. **Consistency Model:** The saga compensation and reconciliation workflows provide *eventual consistency* via asynchronous queues, NOT atomic two-phase commit (2PC) distributed rollbacks.
5. **Absence of Absolute Claims:** All metrics and performance characteristics reported in this dossier reflect observed execution under the stated simulation and fault injection model. They do not constitute statutory warranties or conformity certifications.
