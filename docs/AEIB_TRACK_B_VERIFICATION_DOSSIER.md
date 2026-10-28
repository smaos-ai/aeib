# AEIB Track B & BT12–BT18 Verification Dossier
## Web Mutation Finality & Physical Execution Controls

- **Document Version**: `1.0.0`
- **Release Status**: `Reported and ready for external reproduction`
- **Specification**: [`schemas/aeib-bench-web-v0.1.schema.json`](file:///Users/andriileukhin/Documents/SovereignNexus/schemas/aeib-bench-web-v0.1.schema.json) & [`schemas/aeib-pap-adapter-v0.1.json`](file:///Users/andriileukhin/Documents/SovereignNexus/schemas/aeib-pap-adapter-v0.1.json) (AEIB PAP adapter proposal)
- **Evaluation Harness**: [`src/track_b_harness.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/track_b_harness.py) & [`src/pap_adapter.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/pap_adapter.py)
- **Machine-Readable Results**: [`dist/track_b_verification_results.json`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/track_b_verification_results.json)
- **Comparative Baseline Report**: [`dist/track_b_comparative_baselines.json`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/track_b_comparative_baselines.json)
- **Forensic Demonstration Trace**: [`dist/decisive_demonstration_trace.json`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/decisive_demonstration_trace.json)
- **Classification**: Governed Technical Dossier for External Audit & Independent Reproduction

---

## 1. Locked Milestone Claim & Final Approved Status

### 1.1 Final Approved Status Text

```text
AEIB Track B v0.1 is a synthetic web-mutation finality benchmark and
reference control-plane implementation. Results are reported from the
producing environment and are prepared for independent reproduction.

The package reports target-ledger-grounded disposition matching, retry
suppression, schema/CAID invalidation, probe coalescing, and restart-latch
behavior under declared synthetic scenarios.

Independent reproduction, external target validation, real TinyFish
execution, PAP interoperability, deployment-specific egress testing, and
regulatory assessment remain pending.

The package does not establish universal exactly-once execution, absence of
remote duplicate effects, complete prompt-injection prevention, or
regulatory compliance.
```

### 1.2 Revised Locked Milestone Claim

> Under the declared synthetic and local physical evaluation harnesses, the AEIB gateway matched dispositions to a target-side ledger, withheld retry authority in tested ambiguous cases, and rejected the tested unauthorized egress, audience, delegation, and credential-handling cases. The local runtime experiment included real socket and HTTP behavior. Real-world efficacy across uncoordinated distributed systems, third-party APIs, and authenticated TinyFish cloud sessions remains subject to independent reproduction and provider-side validation.

### 1.3 The Strictly Bounded Approved Claims

All external communications and verification statements are strictly bounded by these empirical observations:
1. **"No duplicate retry was issued by the controlled gateway in the tested scenario."**  
   *(The tested local target recorded one commit and the gateway issued no second retry).*
2. **"The gateway preserved an ambiguous outcome after the tested transport fault."**  
   *(Freezes disposition fail-closed at `EFFECT_INDETERMINATE` with `retry_safe: false`).*
3. **"The verifier detected tampering in the tested tamper cases."**  
   *(Specifically for payload parameter mutation, signature byte tampering, and ledger state divergence against a trusted external anchor).*
4. **"The benchmark grades against target-side state rather than agent self-report."**  
   *(Target-side ledger oracle is programmatically isolated and queries strictly using the business key).*
5. **"The adapter is designed to integrate with existing identity and gateway controls."**  
   *(Positioned underneath identity tokens and prompt filters as a transport-level retry authority plane).*
6. **"Local TinyFish-compatible profile tests: reported passed. Real TinyFish cloud session: pending external validation."**

### 1.4 Epistemic Boundaries & Terminology Lock

- **Declared Context**: All results in this dossier are **reported by the producing environment** under the declared synthetic physical simulation harness and are **ready for external reproduction**.
- **Canonical Vocabulary**: The canonical disposition for confirmed effects is **`OUTCOME_CONFIRMED`**. The term `ACTION_CONFIRMED` is reserved for legacy compatibility only, because observing a tool action is fundamentally distinct from confirming its target effect.
- **Probe Authority Definition**: Synthetic probes are designated as **"declared target-side oracle probes under the synthetic benchmark model"**. The term *authoritative* is reserved exclusively for real provider status systems whose authority, freshness, tenant scope, and consistency guarantees are formally documented.
- **Not Established**: Universal distributed consensus (2PC/Paxos), real-world absence of remote side-effects across untrusted networks, complete prompt-injection prevention, deployment readiness, or regulatory certification.
- **Permitted Vocabulary**: Findings are strictly reported as *observed*, *tested*, *evaluated*, *configured*, and *under the stated model*.

---

## 2. Final Release Status Table & Release Blockers

### 2.1 Final Release Status Table

```text
Synthetic Track B: reported complete
BT12–BT18: reported complete
Baseline comparison: reported complete
Forensic trace: reported complete
Independent reproduction: pending
Real TinyFish integration: pending
PAP interoperability: pending
External target oracle: pending
Regulatory consultation: pending
Production deployment: not established
```

### 2.2 The 4 Release Blockers & Status

1. **Blocker 1: Real External Adapter Integration** (`PENDING`)  
   *Requirement*: Expand beyond the synthetic target to include at least:
   - One real remote API with `Idempotency-Key` header support.
   - One real remote API with an authoritative status query endpoint.
   - One browser-only workflow.
   - One real TinyFish remote browser session evaluating session persistence, credential isolation, and reconciliation under live network drops.
2. **Blocker 2: Comparative Baseline Evaluation** (`REPORTED COMPLETE`)  
   *Requirement*: Evaluate Track B scenarios across 5 distinct execution arms (Naive Retry, Standard SDK Retry, Gateway Without AEIB, Provider Idempotency Only, AEIB Adapter) and measure unsafe retries, duplicate dispatches, duplicate commits, false confirmations, probe count, latency, and operator interventions with explicit sample-size and seed metadata.  
   *Artifact*: [`dist/track_b_comparative_baselines.json`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/track_b_comparative_baselines.json).
3. **Blocker 3: Strict Oracle Independence** (`REPORTED COMPLETE`)  
   *Requirement*: Enforce programmatic assertions ensuring the target-side ledger oracle cannot access or inspect scenario expected dispositions, gateway results, fault labels, or test assertions. Queries must strictly use the business key string.  
   *Implementation*: [`MockTargetLedger.probe_state`](file:///Users/andriileukhin/Documents/SovereignNexus/src/track_b_harness.py#L72-L87) enforces type checking, rejects non-string queries, and asserts that no gateway disposition or test metadata is accessible.
4. **Blocker 4: Restart & Failure Trace Evidence** (`REPORTED COMPLETE`)  
   *Requirement*: Preserve a complete end-to-end trace with OS process IDs, timestamps, database snapshots, and cryptographic hashes proving durable latch recovery across process termination.  
   *Artifact*: [`dist/decisive_demonstration_trace.json`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/decisive_demonstration_trace.json).

---

## 3. Scope of Execution

All results reported in this dossier were produced under the following strictly defined environment:

```text
Execution Environment:   macOS Sonoma 14.x / Darwin 23.x (Apple Silicon)
OS / Clean-Room Model:   Clean-room local execution harness, no external network egress
Python Runtime:          CPython 3.11+ / Python 3.14.3
SQLite Engine:           SQLite 3.43.2+ (WAL mode enabled)
Browser / Provider:      MockTargetLedger / Synthetic Headless Wire Scaffold (TinyFish live browser pending)
Container Digest:        Pending external build
CPU Architecture:        Apple Silicon arm64 / aarch64
Locked Dependencies:     cryptography>=41.0.0 (Ed25519), jsonschema>=4.20.0, pytest>=7.4.0
Network Configuration:   Loopback / isolated synthetic wire fault injector (Zero Egress)
```

---

## 4. Independent Reproduction Matrix

To verify results across platforms while clearly distinguishing semantic conformance from bit-for-bit binary identity:

$$\text{Semantic Conformance} \neq \text{Byte-for-Byte Artifact Identity}$$

*Note: Bit-for-bit identity is reserved for a pinned container or fully pinned runtime environment. Across heterogeneous host environments, the evaluation asserts semantic conformance.*

| Environment | Platform | Runtime | Isolation Boundary | Purpose | Target | Status |
|:---|:---|:---|:---|:---|:---|:---|
| **Environment A** | macOS arm64 | Python 3.11+, local SQLite | Local development sandbox | Producer artifact generation | Bit-for-bit producing baseline | **Reported complete** |
| **Environment B** | Linux x86_64 container | Python 3.11 (Debian bookworm) | Network-isolated Docker container | Clean-room reviewer reproduction | Independent semantic reproduction | **Pending external run** |
| **Environment C** | FreeBSD / Windows WSL2 | Python 3.12+ | Alternate OS filesystem & libc | Portability & filesystem semantics audit | Negative-test reproduction | **Pending external run** |

---

## 5. Scenario Oracle Contract

The evaluation methodology strictly separates the gateway adapter from the declared target-side ledger oracle:

1. **What the Oracle Can Read**:
   - The isolated `business_key` string parameter passed explicitly to `probe_state(business_key: str)`.
2. **What the Oracle Cannot Read**:
   - Programmatically isolated from `gateway_state`, `expected_disposition`, `fault_label`, `test_assertion`, and `retry_decision`.
   - Enforced by explicit assertions in `MockTargetLedger.probe_state`:
     ```python
     assert isinstance(business_key, str), "Oracle accepts only business_key strings"
     assert not isinstance(business_key, dict), "Oracle cannot inspect structured execution payloads"
     assert "gateway_state" not in query_context
     assert "expected_disposition" not in query_context
     ```
3. **How Business Keys Are Generated**:
   - Deterministic candidate action binding (`tx_settlement_corp_2026_094` derived from candidate payload and business intent).
4. **How Target `commit_count` Is Persisted**:
   - Appended to target-side mutation records keyed strictly by `business_key`. Each mutation increments `commit_count`.
5. **How Probes Are Authenticated**:
   - Target ledger verifies probe credentials and queries transaction records without feedback from gateway state.

---

## 6. Comparative Baseline Evaluation (5 Execution Arms)

Evaluated via [`benchmarks/track_b_comparative_baselines.py`](file:///Users/andriileukhin/Documents/SovereignNexus/benchmarks/track_b_comparative_baselines.py) across all 11 Track B scenarios:

| Execution Arm | Unsafe Retries | Duplicate Dispatches | Target Duplicate Commits | False Confirmations | Reconciliation Probes | Operator Interventions | Observed Behavioral Profile |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **Arm 1: Naive Retry Loop** | **20** | **20** | **16** | **1** | 0 | 0 | Blind retries on error; high rate of duplicate target commits. |
| **Arm 2: Standard SDK Retry** | **2** | **2** | **2** | **1** | 0 | 0 | Retries 5xx timeouts; causes duplicates when keys are not stable. |
| **Arm 3: Gateway Without AEIB** | 0 | 0 | 0 | **1** | 0 | **10** | Swallows errors or accepts stale DOM banners; high operator burden. |
| **Arm 4: Provider Idempotency Only** | 0 | **10** | 0 | 0 | 0 | **10** | Server deduplicates, but lack of client probe leaves state unresolved. |
| **Arm 5: AEIB Adapter** | **0** | **0** | **0** | **0** | **9** | **0** | Latches uncertainty fail-closed; resolves state via 1 probe per fault. |

### 6.1 Baseline Metadata & Sample Size
```json
{
  "scenario_count": 11,
  "repetitions_per_scenario": 1,
  "seed": "seed:42",
  "target_model": "synthetic",
  "confidence_intervals": "not_applicable",
  "external_reproduction": false
}
```
*Methodology Note*: A single run demonstrates deterministic behavior under stated models; it does not establish a statistically stable rate such as "16 duplicate commits" beyond that run.

### 6.2 Failure Taxonomy & Architectural Insight
The evaluation strictly distinguishes three distinct failure modes:
$$\text{False Success} \neq \text{Unknown Outcome} \neq \text{Duplicate Effect}$$

> **Key Conclusion: Retry suppression alone is insufficient; the system must also prevent unsupported success claims.**

Arm 3 demonstrates that suppressing retries without effect-integrity verification results in **1 false confirmation** (accepting a stale DOM confirmation banner in B06) and **10 operator interventions**. Arm 4 proves that provider-side deduplication prevents duplicate commits on the backend but leaves the agent in an indeterminate state without an authoritative probe. Arm 5 resolves both failure modes simultaneously.

---

## 7. Comprehensive Scenario Matrix & Per-Scenario Probe Audit

### 7.1 Track B Scenario Matrix (18 Scenario IDs)

The suite contains **20 test cases covering 18 scenario IDs (B01–B11 and BT12–BT18)** plus 2 structural guard tests (schema conformance and oracle independence assertions):

| Scenario ID | Name / Description | Wire Phase | Wire Event | Canonical Gateway Disposition | Probe Reconciliation | Target Ground Truth | Target Commits | Retry Status & Fields |
|:---|:---|:---|:---|:---|:---|:---|:---:|:---|
| **B01** | Nominal Execution & Response Arrives | `post_response` | `HTTP_200_OK` | `OUTCOME_CONFIRMED` *(legacy: `ACTION_CONFIRMED`)* | `PROBE_NOT_ATTEMPTED` | `COMMITTED` | 1 | `retry_safe: false` (`effect_already_committed`) |
| **B02** | Response Lost Before Commit - Pre-body Drop | `pre_body` | `TCP_RST` | `EFFECT_INDETERMINATE` | `EFFECT_ABSENT_VIA_PROBE` | `NOT_FOUND` | 0 | `retry_safe: false` (`uncertainty_latched`) |
| **B03** | Response Lost After Commit - HTTP 504 | `post_commit` | `HTTP_504_GATEWAY_TIMEOUT` | `EFFECT_INDETERMINATE` | `EFFECT_CONFIRMED_VIA_PROBE` | `COMMITTED` | 1 | `retry_safe: false` (`uncertainty_latched`) |
| **B04** | Browser Killed After Click Submit | `post_click` | `FAULT_BROWSER_KILL_POST_COMMIT` | `EFFECT_INDETERMINATE` | `EFFECT_CONFIRMED_VIA_PROBE` | `COMMITTED` | 1 | `retry_safe: false` (`uncertainty_latched`) |
| **B05** | TCP Reset Mid-Request Body | `mid_body` | `TCP_RST` | `EFFECT_INDETERMINATE` | `EFFECT_ABSENT_VIA_PROBE` | `NOT_FOUND` | 0 | `retry_safe: false` (`uncertainty_latched`) |
| **B06** | Post-Commit Drop with Stale DOM Banner | `post_response` | `STALE_DOM_CONFIRMATION` | `EFFECT_INDETERMINATE` | `EFFECT_CONFIRMED_VIA_PROBE` | `COMMITTED` | 1 | `retry_safe: false` (`uncertainty_latched`) |
| **B07** | Pre-Dispatch Schema Validation Failure | `pre_dispatch` | `VALIDATION_FAILED` | `DISPATCH_REJECTED` | `PROBE_NOT_ATTEMPTED` | `NOT_FOUND` | 0 | `retry_safe: true` (`clean_rejection_no_effect`) |
| **B08** | Post-Commit Drop with HTTP 504 Timeout | `post_commit` | `HTTP_504_GATEWAY_TIMEOUT` | `EFFECT_INDETERMINATE` | `EFFECT_CONFIRMED_VIA_PROBE` | `COMMITTED` | 1 | `retry_safe: false` (`uncertainty_latched`) |
| **B09** | Post-Commit Connection Drop | `post_commit` | `FAULT_CONNECTION_DROP_POST_COMMIT` | `EFFECT_INDETERMINATE` | `EFFECT_CONFIRMED_VIA_PROBE` | `COMMITTED` | 1 | `retry_safe: false` (`uncertainty_latched`) |
| **B10** | Pre-Body Connection Drop | `pre_body` | `CONNECTION_DROP` | `EFFECT_INDETERMINATE` | `EFFECT_ABSENT_VIA_PROBE` | `NOT_FOUND` | 0 | `retry_safe: false` (`uncertainty_latched`) |
| **B11** | Post-Click TCP Reset | `post_click` | `FAULT_TCP_RST_POST_COMMIT` | `EFFECT_INDETERMINATE` | `EFFECT_CONFIRMED_VIA_PROBE` | `COMMITTED` | 1 | `retry_safe: false` (`uncertainty_latched`) |
| **BT12** | Duplicate Blind Retry Blocked Fail-Closed | `post_commit` | `UNCERTAINTY_LATCHED_RETRY_BLOCKED` | `EFFECT_INDETERMINATE` | `BLOCKED_PREVIOUSLY_LATCHED` | `COMMITTED` | 1 | **BLOCKED (0 duplicates)** |
| **BT13** | Probe Tampering Overridden by Ledger | `post_commit` | `HTTP_504_GATEWAY_TIMEOUT` | `EFFECT_INDETERMINATE` | `EFFECT_CONFIRMED_VIA_PROBE` | `COMMITTED` | 1 | Target Overrides Claim |
| **BT14** | Probe Disagreement Freezes Authority | `post_commit` | `HTTP_504_GATEWAY_TIMEOUT` | `RECONCILIATION_CONFLICT` | `RECONCILIATION_CONFLICT` | `COMMITTED` | 1 | `release: frozen_dual_control` |
| **BT15** | Target Ledger Unavailable Escalates | `post_commit` | `HTTP_504_GATEWAY_TIMEOUT` | `EFFECT_INDETERMINATE` | `PROBE_TIMEOUT` | `COMMITTED` | 1 | `escalation: human_operator` |
| **BT16** | Process Restart Recovery via Durable Ledger | `post_commit` | `UNCERTAINTY_LATCHED_RETRY_BLOCKED` | `EFFECT_INDETERMINATE` | `BLOCKED_PREVIOUSLY_LATCHED` | `COMMITTED` | 1 | Survives Memory Wipe |
| **BT17** | Browser Session & Context Isolation | `post_response` | `HTTP_200_OK` | `OUTCOME_CONFIRMED` *(legacy: `ACTION_CONFIRMED`)* | `PROBE_NOT_ATTEMPTED` | `COMMITTED` | 1 | Context Isolated |
| **BT18** | Schema & CAID Invalidation on Mutation | `post_response` | `HTTP_200_OK` | `OUTCOME_CONFIRMED` *(legacy: `ACTION_CONFIRMED`)* | `CAID_DIFFERENTIAL_VERIFIED` | `COMMITTED` | 1 | CAID Invalidated |

### 7.2 Explicit B01 Field Definitions
In accordance with verification criteria, B01 separates outcome, effect status, retry permission, and reason:
```json
{
  "outcome": "OUTCOME_CONFIRMED",
  "effect_status": "COMMITTED",
  "retry_safe": false,
  "retry_reason": "effect_already_committed",
  "release_authorization": "not_provided"
}
```
Here, `retry_safe: false` indicates that the action is terminal and already committed; it is **not** a synonym for state uncertainty.

### 7.3 Per-Effect Probe Audit Breakdown
The single-flight invariant is measured and enforced per `effect_id` (derived from `business_key`):

| Scenario Group | Scenario IDs | Wire Outcome | Probes Triggered | Audit Rationale |
|:---|:---|:---|:---:|:---|
| **Nominal Wire** | `B01` | `HTTP_200_OK` | **0** | Nominal execution completed; wire response authoritative. Probe not attempted. |
| **Pre-Dispatch Rejection** | `B07` | `VALIDATION_FAILED` | **0** | Rejected before wire dispatch; target untouched. Probe not attempted. |
| **Ambiguous Wire Faults** | `B02, B03, B04, B05, B06, B08, B09, B10, B11` | Transport drop / 504 / RST | **9** *(1 per scenario)* | Single-flight probe triggered exactly once per ambiguous effect to reconcile ground truth. |
| **Active Latch Retry** | `BT12` | `LATCHED_RETRY_BLOCKED` | **0** | Speculative retry rejected by active uncertainty latch; existing latch state reused without duplicate probe. |
| **Ledger Override** | `BT13` | `HTTP_504` Drop | **1** | Single-flight probe reconciles state, overriding tampered agent claim. |
| **Probe Disagreement** | `BT14` | Conflicting responses | **1** | Probe detects conflicting reports; freezes release under dual-control. |
| **Probe Timeout** | `BT15` | Probe unreachable | **1** | Probe times out; escalates to human operator without speculative retry. |
| **Post-Restart Retry** | `BT16` | Restarted instance | **0** | Latch restored from durable SQLite storage; blind retry rejected without probe re-run. |
| **Profile Isolation** | `BT17` | `HTTP_200_OK` | **0** | Isolated ephemeral and persistent profiles execute cleanly; no probe required. |
| **Payload Mutation** | `BT18` | Parameter change | **0** | New CAID generated; original latch untouched; no probe required. |

---

## 8. Complete Physical Demonstration Forensic Trace

Preserved in [`dist/decisive_demonstration_trace.json`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/decisive_demonstration_trace.json):

```text
[STEP 0] PRE-MUTATION SNAPSHOT
         Timestamp: 2026-10-07T14:40:21.849997Z | Monotonic: 73062323719000 ns
         Target State: EMPTY | commit_count: 0 | records: 0

[STEP 1] ACTION BINDING
         Candidate: PaymentDisbursement::AuthorizeAndDisburse
         CAID: caid:sha256:cd40498fa44474823f1cd70765d944a07f8531c4ed1126b5c833ffd04e166707
         Payload Hash: sha256:91bc7d853eeb11ff8cba996c5aaefbf38c2921a91e53a5180ce6d0ee3c9f2b84
         Payload Size: 184 bytes (RFC 8785 JCS canonicalized)

[STEP 2] TARGET EXECUTION & TRANSPORT DROP
         Target Backend committed mutation (commit_count = 1)
         Wire Telemetry: Response lost mid-flight (HTTP 504 Gateway Timeout)
         Gateway Disposition: EFFECT_INDETERMINATE | latch_engaged: true | retry_safe: false

[STEP 3] GATEWAY PROCESS TERMINATION & CONTEXT DELETION
         Simulated Process Crash: Volatile memory wiped, instance gw_proc1 deleted
         Durable Storage Hash: sha256:1a136ea54e3d64c017fe454045f061fdb49da39ea990033ad0fe184ecff8cf85

[STEP 4] GATEWAY PROCESS RESTART
         New instance gw_proc2 initialized from durable storage
         Latched CAIDs restored: 1 active latch (cd40498f... = true)

[STEP 5] AGENT SPECULATIVE BLIND RETRY DISPATCH
         Agent re-dispatches exact candidate action
         Gateway Result: REJECTED FAIL-CLOSED
         Wire Event: UNCERTAINTY_LATCHED_RETRY_BLOCKED
         Second gateway retry was rejected; target commit_count remained 1.

[STEP 6] SINGLE-FLIGHT RECONCILIATION PROBE (TARGET-SIDE ORACLE UNDER STATED MODEL)
         Probe Query: strictly using business_key (tx_settlement_corp_2026_094)
         Probe Result: COMMITTED | commit_count: 1
         Final Reconciliation: COMMITTED

================================================================================
DEMONSTRATION COMPLETE: 0 Duplicate Retries Permitted, Target Commit Count = 1
================================================================================
```

---

## 9. Negative Test Inventory

The test harness evaluates tamper detection and boundary enforcement across 10 negative conditions:

| Negative Test Condition | Harness Target | Observed Failure Mode | Handled Disposition |
|:---|:---|:---|:---|
| **Altered CAID** | `tests/test_aeib_bench_at15_at25.py::test_at24` | Payload parameter mutated by proxy | Dispatch rejected; payload hash divergence detected. |
| **Altered Tenant** | `tests/test_aeib_bench_at15_at25.py::test_at16` | Cross-tenant parameter injection | Rejection fail-closed; delegation scope violation. |
| **Altered Policy Epoch** | `tests/test_aeib_bench_at15_at25.py::test_at17, test_at23` | TOCTOU millisecond standing race | Candidate dispatch rejected fail-closed; epoch stale. |
| **Altered Schema** | `tests/test_track_b_scenarios.py::test_b07` | Missing required payload field | `VALIDATION_FAILED`; wire dispatch prevented (0 bytes sent). |
| **Altered Disposition** | `tests/test_track_b_scenarios.py::test_bt13` | Agent self-reports success on 504 | Target ledger state overrides agent claim. |
| **Altered Retry Flag** | `tests/test_track_b_scenarios.py::test_bt12, test_bt16` | Speculative retry on latched action | Rejected fail-closed; `UNCERTAINTY_LATCHED_RETRY_BLOCKED`. |
| **Deleted Evidence** | `tests/test_aeib_bench_at15_at25.py::test_at25` | Evidence journal entry pruned | Integrity verification fails against external anchor. |
| **Replayed Receipt** | `tests/test_aeib_bench_at15_at25.py::test_at19` | Expired/reused receipt presented | Receipt rejected; non-monotonic timestamp. |
| **Wrong Signing Key** | `tests/test_pap_adapter.py::test_tampered_receipt` | Ed25519 signature byte corrupted | Verification raises `InvalidSignature`; receipt rejected. |
| **Wrong Probe Result** | `tests/test_track_b_scenarios.py::test_bt14` | Probe disagreement / conflicting status | `RECONCILIATION_CONFLICT`; release authority frozen. |

---

## 10. Real-Integration Gate & TinyFish Context Profiles

### 10.1 Real-Integration Gate Status
```text
Local Socket/HTTP Physical Baseline: Reported passed (tests/test_live_physical_execution.py)
Local TinyFish-Compatible Profiles:   Reported passed (tenant isolation & destruction receipts)
Real External Uncoordinated API:      Pending external validation
Real TinyFish Cloud Session:          Pending external validation
PAP Interoperability:                 Pending external validation
```

### 10.2 First Live Target Experiment Specification
The immediate physical progression requires executing a live disposable test account exercising:
1. `business operation key`
2. `target status endpoint`
3. `audit-visible commit record`
4. `fault injection after commit`
5. `gateway restart`
6. `retry attempt`
7. `independent reconciliation`

### 10.3 TinyFish Browser Context Profiles Architecture
TinyFish web automation supports persistent browser profiles (`use_profile=True`, `profile_id`, `use_vault=True`) holding authentication cookies and local storage across sessions. 

Because persistent profiles expand the credential and cross-tenant leakage surface compared to ephemeral headless browsers, the live integration must track the following governance metadata fields:
- `profile_id`: Unique identifier of the browser context.
- `session_id`: Ephemeral execution session binding.
- `profile_owner`: Authorized delegating identity.
- `tenant`: Multi-tenant boundary partition.
- `allowed_origins`: Strict domain whitelist for navigation.
- `credential_scope`: Scoped vault secrets accessible to the profile.
- `profile_expiry`: TTL for session storage and cookies.
- `destruction_event`: Cryptographically recorded profile deletion receipt.

---

## 11. Personal Agent Protocol (PAP) Adapter Proposal Status

- **File**: [`schemas/aeib-pap-adapter-v0.1.json`](file:///Users/andriileukhin/Documents/SovereignNexus/schemas/aeib-pap-adapter-v0.1.json)
- **Status**: **AEIB PAP adapter proposal** (Draft extension namespace: `aeib_extension`, `pap-draft-2026-10`).
- **Standardization Boundary**: This document and schema represent an adapter proposal. They do **not** imply that fields such as `business_idempotency_key`, `caid`, or `reconciliation_probe` are standardized until the PAP steering group formally publishes the normative v0.1 specification.

---

## 12. Regulatory Governance Alignment & Boundaries

### 12.1 DORA Alignment Boundaries (Regulation (EU) 2022/2554)
- **Separation of Deliverables**:
  $$\text{DORA Incident Evidence (Art. 17)} \neq \text{DORA Register of Information (Art. 28(3))}$$
- **Timeline Attribution**: Major ICT-related incident reporting timelines (initial notification within 4 hours of classification / 24 hours of awareness, intermediate within 72 hours, final report within 1 month) derive strictly from **DORA Regulatory Technical Standards (RTS/ITS)**, not from AEIB requirements.
- **Scope Statement**:
  > AEIB can export evidence supporting DORA incident classification, timeline reconstruction, and reporting workflows.
- **Strict Non-Claim**: AEIB does **not** "satisfy" DORA Article 17 or Article 28(3) independently. Transport receipts do not populate the entire Register of Information. Compliance is determined solely by the regulated financial entity and competent supervisory authorities.

### 12.2 EU AI Act Alignment (Regulation (EU) 2024/1689, Article 14)
- AEIB exports raw forensic journals to support Article 14 human oversight and auditability. AEIB does not certify AI Act compliance.

---

## 13. Failure Modes Catalog & Storage Invariants

The durable latching subsystem is evaluated against six operational failure conditions:

1. **SIGKILL Mid-Flight**: Gateway killed immediately after wire dispatch. On restart, SQLite WAL recovery restores committed ledger state under the tested failure model; application-level retry lockout depends on the persisted state transition and startup validation. Speculative retries remain blocked.
2. **Abrupt Termination After Target Commit**: Gateway dies while receiving response. Target state is `COMMITTED`, but gateway state is unconfirmed. Restarts into `EFFECT_INDETERMINATE`; single-flight probe recovers committed state.
3. **Disk-Full Ordering Invariant**:
   The execution pipeline strictly enforces the following ordering:
   $$\text{Latch Journal Write} \longrightarrow \text{Durable Commit / fsync} \longrightarrow \text{Only Then Network Dispatch}$$
   If disk is full or storage fails, the dispatch is aborted fail-closed with **0 bytes dispatched** before wire transmission occurs.
4. **SQLite Recovery After Unclean Shutdown**: SQLite WAL recovery restores committed database pages; active locks must be verified at application startup.
5. **Corrupt or Rolled-Back Ledger**: Detecting ledger hash divergence requires a trusted baseline or external anchor; a hash stored in the same mutable database cannot independently prove tampering. On external anchor mismatch, the gateway enters a fail-closed lock.
6. **Concurrent Restart**: Mutex locks on durable database prevent simultaneous gateway instances from executing duplicate probes.

---

## 14. Publication Readiness Assessment

### 14.1 Suitable Now
- Internal architecture review.
- Independent reviewer reproduction.
- Synthetic benchmark publication.
- Technical consultation marked as non-certification.
- Zenodo deposit after final archive hash and manifest check.

### 14.2 Not Yet Suitable
- Production deployment claim.
- Regulatory compliance claim.
- Real-world exactly-once claim.
- “Authoritative” external effect claim.
- PAP interoperability claim.
- TinyFish security validation claim.
- Statistical industry benchmark claim.

---

## 15. Verification Reproducibility & Audit Runbook

To reproduce these reported results across environments:

```bash
# 1. Turnkey Track B Independent Reproduction Harness (4 gates, 100% passed)
python3 scripts/verify_track_b_reproduction.py

# 2. Track B Web Mutation Finality Test Suite (20 test cases covering 18 scenario IDs)
pytest tests/test_track_b_scenarios.py -v

# 3. Full 69-Test Core Verification Matrix (All 69 passed in 0.68s)
pytest tests/test_industrial_protection_matrix.py \
       tests/test_ansi_50bf_breaker_failure.py \
       tests/test_saga_compensation.py \
       tests/test_falsifiability_matrix.py \
       tests/test_track_b_scenarios.py \
       tests/test_aeib_mcp_egress_at30_at36.py \
       tests/test_aeib_mcp_egress_at37_at41.py \
       tests/test_live_physical_execution.py -v

# 4. Personal Agent Protocol (PAP) Adapter Test Suite (8 tests)
pytest tests/test_pap_adapter.py -v

# 5. Governance Boundary & Acceptance Test Matrices (25 tests)
pytest tests/test_aeib_bench_at15_at25.py tests/test_acceptance_test_12.py -v

# 6. P0 Durable Ledger Latch Survival Test Suite (5 tests)
pytest tests/test_p0_durable_ledger.py -v

# 7. Comparative Baseline Evaluation (5 Execution Arms, Seed 42)
python3 benchmarks/track_b_comparative_baselines.py

# 8. Physical Demonstration Trace Generator
python3 benchmarks/generate_demonstration_trace.py

# 9. Mandatory Compliance Verification Loop
python3 compliance/check_zone_boundary.py
python3 compliance/ast_purity.py .
python3 compliance/no_mock_enforcer.py
```

---

*This dossier documents observations from the producing environment and is submitted as a review candidate ready for independent external reproduction.*
