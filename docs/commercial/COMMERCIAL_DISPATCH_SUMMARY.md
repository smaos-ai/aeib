# Agent Execution Integrity Benchmark (AEIB v0.2.0)
## Prototype Architecture & Diagnostic Deployment Overview

**Initiative:** SovereignNexus (Independent Research Initiative • Czech Republic incorporation pending)  
**Lead Researcher:** Andrii Leukhin (Prague × LPNU IKNI)  
**Format Designation:** `AEIB_JSON_ED25519_PROTOTYPE`  
**Operational Scope:** Synthetic staging traces & local simulation only. Not a certified compliance product.

---

### 1. The Operational Problem: Ambiguous Post-Dispatch Outcomes

In many current multi-agent and automated workflow deployments, orchestrators do not have a unified pattern for handling ambiguous post-dispatch outcomes. When an agent dispatches a state-mutating command (e.g., funds disbursement, database commit, or ERP entitlement change) and the transport layer encounters an HTTP 504 Gateway Timeout or dead socket:

1. **Uncertain State**: The caller cannot distinguish between "request never reached server," "request executed but response dropped," and "request failed downstream."
2. **Retry Risk**: Without explicit boundary controls, workflows may attempt uncoordinated retries, risking duplicate transactions or requiring extensive manual reconciliation.
3. **Audit Disconnect**: Standard client-side logs capture model intent rather than network transport reality, leaving an evidentiary gap during internal risk reviews and supervisory audits.

---

### 2. Stakeholder Value (Defensible Stance)

* **Platform & Backend Engineers**: Provides a deterministic 7-disposition state machine that intercepts transport timeouts (HTTP 504) and halts further automated execution under `DISPATCHED_UNCONFIRMED` until an authoritative out-of-band probe resolves state.
* **CISOs & Operational Risk Teams**: Emits Ed25519-signed receipts and local queryable evidence that can support internal review of ambiguous executions and help demonstrate controls under DORA and the EU AI Act.
* **External IT Auditors**: Enables independent verification of receipt signature integrity, evidence bindings, and mapping-rule consistency using an offline verifier (`python3 verifier/aeib_verify.py`) without accessing production systems.

---

### 3. Integration Modes: Current Prototype vs. Production Roadmap

| Integration Mode | Current Status | Description & Operational Flow |
| :--- | :---: | :--- |
| **Mode 1: Offline Trace Audit** | *Prototype Design / Staging* | Ingests historical JSONL execution traces from staging environments to identify unquarantined 504 timeouts and evaluate them against the AEIB disposition taxonomy. |
| **Mode 2: Local Sidecar Proxy** | *Target Pilot Milestone* | The planned deployment pattern for pilots: a lightweight local proxy that transparently intercepts tool calls, injects idempotency keys, traps transport timeouts, and coordinates out-of-band state reconciliation. *(The current v0.2 package demonstrates the cryptographic and mapping logic for this pattern).* |
| **Mode 3: Native Runtime Filter** | *Reference Implementation* | Illustrative reference filters (such as `ProofOrStopFilter.java` for Spring Boot WebClient) demonstrating how host runtimes can enforce fail-closed invariants on socket drops. Production-grade SDKs will follow pilot validation. |

---

### 4. Step-by-Step Execution Lifecycle (AEIB Invariant)

```text
    AGENT DISPATCH (T_0)                     TRANSPORT (ΔN)                       DOWNSTREAM (T_n)
┌─────────────────────────┐               ┌─────────────────────────┐           ┌─────────────────────────┐
│ Agent initiates tool    │  ══════════►  │ Transport drops         │           │ Adapter probes target   │
│ mutation                │               │ HTTP 504 / Dead Socket  │           │ ledger using handle     │
└────────────┬────────────┘               └────────────┬────────────┘           └────────────┬────────────┘
             │                                         │                                     │
             ▼                                         ▼                                     ▼
     [ Deterministic Hash ]                    [ Quarantine Trap ]                   [ Disposition Mint ]
     • Deterministic JSON                      • Trapped into                        • If present: OUTCOME_VERIFIED
       (sorted keys, compact;                    DISPATCHED_UNCONFIRMED              • If absent: RECONCILIATION_NOT_FOUND
        not RFC 8785 validated)                • Blocks automated retry              • Ed25519 Receipt Emitted
     • UUIDv5 Idempotency Key
```

1. **Pre-Dispatch Preparation**: The action payload is serialized using a deterministic JSON subset (sorted keys, compact separators; not RFC 8785 validated) to generate a stable SHA-256 digest and an injected UUIDv5 idempotency key.
2. **Wire Transmission**: The request traverses the transport network.
3. **Transport Failure Interception**: If an HTTP 504 or socket reset occurs, the execution is trapped into **`DISPATCHED_UNCONFIRMED`**. The engine is designed to block automated retries for this action until state is authoritatively resolved.
4. **Adapter-Based Reconciliation**: An out-of-band probe queries the target register using the UUIDv5 key:
   - If state persisted $\to$ Resolves to `OUTCOME_VERIFIED`.
   - If state absent $\to$ Resolves to `RECONCILIATION_NOT_FOUND`, safely enabling controlled rollback or re-dispatch.
5. **Cryptographic Evidence Sealing**: An Ed25519-signed receipt is generated locally, binding the transport status, probe result, and normative disposition rule.

---

### 5. Explicit Operational Limits & Disclaimers

* **Synthetic Prototype**: The current AEIB v0.2.0 package operates strictly on synthetic benchmark vectors and simulated transport outcomes.
* **Adapter Dependency**: Out-of-band verification relies on target-side query adapters. Target systems must expose queryable idempotency handles or transaction registries.
* **No Compliance Certification**: This prototype is a research tool to support internal audit trails. It does not certify statutory compliance with DORA, ISO 42001, or the EU AI Act.
