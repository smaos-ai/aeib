# Agent Effect Integrity Benchmark (AEIB) — Technical Report v3
## Illustrative Control-Objective Mapping & Action vs. Outcome Defensible Specification

**Document Version:** 3.0 (September 2026)  
**Classification:** Scientific Benchmark Report & Defensible Prototype Specification  
**Author:** SovereignNexus Architecture Team  
**Focus:** Consequence Integrity (Layer 5), Policy Gating (Layer 4), Engineering Physics Verification  

> [!IMPORTANT]
> **Regulatory Disclaimer:**  
> SMAOS is designed to generate evidence that may support an organization’s internal control assessment. It does not certify compliance with ISO/IEC 42006, DORA, NIST guidance, or Chinese standards. ISO/IEC 42006 governs accreditation bodies, not software log formats. All standards mappings in this report represent illustrative control-objective crosswalks, not legal or conformity assessments.

---

## 1. Executive Summary & Defensible Product Scope

Our core product claim is anchored strictly on engineering physics:

> **Authorization is not persistence, and persistence is not a correct outcome.**  
> *(authorized write ≠ persisted write ≠ correct outcome)*

As autonomous agent workflows scale from read-only conversational interactions to mutating financial, cloud, and operational transactions, standard model evaluation metrics (MMLU, HumanEval, "vibe evals") become irrelevant to risk committees. 

What matters is **Consequence Integrity**: the physical measurement plane proving that an authorized action produced the exact downstream consequence expected, without silent parameter drift, double-execution over dropped sockets, or unreconstructable state corruption.

The **Agent Effect Integrity Benchmark (AEIB)** provides the open-source metrology suite to empirically evaluate agent execution harnesses under realistic network transport faults.

---

## 2. Cryptographic Architecture: Prototype vs. Production

To maintain strict scientific and technical honesty:

* **Current Prototype Implementation:**  
  The current local prototype computes a symmetric **HMAC-SHA-256 integrity tag** over RFC 8785 JCS canonicalized payload bytes using a local key (`signing_key`).
* **Production-Grade Requirements (Future Scope):**  
  Asymmetric Ed25519 digital signatures, Merkle-DAG inclusion proofs, and formal RFC 9162 / SCITT transparency ledger envelopes are production requirements that are not yet bundled into this local prototype.

---

## 3. The 5-Pillar Master Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          GOOGLE HARNESS STAGE V                             │
│                     (Meta-Debug & Internal Control Review)                  │
└──────────────────────────────────────▲──────────────────────────────────────┘
                                       │ HMAC-SHA-256 Integrity Receipts
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                    LAYER 5: CONSEQUENCE INTEGRITY (SMAOS)                   │
│  • Action vs. Outcome Verification ("Paris Hotel + Breakfast" State Check)   │
│  • Local Embedded OLAP (chDB / SQLite Local Trace Telemetry)                │
│  • Bitemporal Audit Memory (agentacct.db / RFC 8785 JCS Hashes)             │
└──────────────────────────────────────▲──────────────────────────────────────┘
                                       │ Standard MCP Payloads
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                   LAYER 4: POLICY ENFORCEMENT (OpenShell / Jev)            │
│  • Pre-Dispatch System 1 Typed Gate (Sub-100ms CONFIRMED/REFUSED)           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pillar 1: Action vs. Outcome Verification
* **The Principle:** OpenShell and Layer 4 policy engines verify whether an agent is *authorized to attempt* an action. SMAOS verifies whether the physical system *actually completed* the intended state change.
* **The "Paris Hotel + Breakfast" Test:**
  > *“'I selected Breakfast' is an action. 'The returned hotels are in Paris and include breakfast' is an outcome.”*
  * If a network timeout occurs mid-flight, Layer 5 treats the action as `dispatched_unconfirmed` until external reconciliation proves the outcome.

### Pillar 2: Owning Google's Harness Pipeline
Models are swappable commodities; the harness holds the operational moat. SMAOS embeds across the entire lifecycle:
* Intercepts at **Stage III (Trajectory)** to bind cryptographic idempotency and canonical hashes.
* Enforces at **Stage IV (Verification)** to quarantine transport ambiguities.
* Feeds **Stage V (Meta-Debug)** with local tamper-evident receipts for internal audit review.
* Documentation Line: *“SMAOS is the verification layer for the harness. It audits the harness, not the model.”*

### Pillar 3: Zero-Egress Local Observability (chDB / SQLite Embedded OLAP)
* Avoids streaming customer traces to third-party SaaS clouds.
* Uses an in-process analytical engine (**chDB** / SQLite) to run sub-millisecond SQL queries over local `.jsonl` trace receipts.

### Pillar 4: Standardizing on Model Context Protocol (MCP)
* Natively intercepts JSON-RPC 2.0 MCP tool calls (`tools/call`, `tools/list`, `resources/read`, `prompts/get`), including SDKs from Stainless and Forge.
* Wraps the 5-step lifecycle: (1) Pre-dispatch authority check $\rightarrow$ (2) Dispatch $\rightarrow$ (3) Post-condition state probe $\rightarrow$ (4) Outcome attestation $\rightarrow$ (5) Receipt emission.

### Pillar 5: Bitemporal Audit Memory
* Memory is indexed as an **Immutable Bitemporal Audit Ledger** (`agentacct.db`).
* Binds two immutable timestamps: **Valid Time ($t_0$)** and **Transaction Time ($t_n$)**, measuring **Authority Freshness** ($\Delta\text{Auth} = t_n - t_0$).

---

## 4. Empirical Evaluation: Illustrative Single-Run Demonstration

### 4.1 Reproducible Execution Metadata

```yaml
results_metadata:
  run_id: aeib-demo-20260928-001
  repository_commit: 8f22d549a6d2982ef246556fd0a060aefd75f7a0
  scenario_manifest: tests/scenarios/http_504_disconnect.json
  scenario_digest: sha256:70f3425e122ddf942617368f1b1fd7861f2bd21a1fdb5103ef8e31dd5ae003c4
  runner_version: v0.1.0-draft
  runtime: Python 3.12.3 / Linux 6.6
  backend_model: Holo4-35B-A3B (Synthetic API Fixture)
  random_seed: 42
  trial_count: 1
  raw_log_digest: sha256:2a28e6ad3124687cf58e6f0592de3389668cf22bb246287f28743712ad9e2199
  result_digest: sha256:1c1ac288a385b5ec0ac3b414243b27082ac32c0a998e8c1933dc8451836af2d6
```

### 4.2 Benchmark Results (Single-Run Test Vector)

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   AEIB FAULT-INJECTION (ILLUSTRATIVE SINGLE-RUN)                       │
├───────────────────────────────────┬──────────────────────────┬─────────────────────────┤
│ METRIC                            │ CLIENT A (NAIVE SDK)     │ CLIENT B (SMAOS HARNESS)│
├───────────────────────────────────┼──────────────────────────┼─────────────────────────┤
│ Transport Signal                  │ HTTP 504 Gateway Timeout │ HTTP 504 Gateway Timeout│
│ Internal State Classification     │ FAILED / NOT_SENT        │ DISPATCHED_UNCONFIRMED  │
│ Idempotency Key Handling          │ Regenerated fresh UUID   │ Preserved SHA-256 JCS   │
│ Autonomous Retry Action           │ Dispatched immediately   │ HALTED (Quarantined)    │
│ Out-of-Band Reconciliation Path   │ Skipped entirely         │ Triggered (/reconcile)  │
│ Backend Database Commits          │ 2 Commits (€100,000)     │ 1 Commit (€50,000)      │
│ Financial Divergence              │ 🚨 €50,000 Double-Spend  │ ✅ €0 Excess (Exact)    │
│ Authority Freshness Delta (ΔAuth) │ Unmeasured               │ 4.2 ms (Verified Fresh) │
│ Integrity Proof Emitted           │ NONE (Plaintext JSON)    │ HMAC-SHA-256 MAC Tag    │
└───────────────────────────────────┴──────────────────────────┴─────────────────────────┘
```

---

## 5. Illustrative Control-Objective Mapping (Not a Conformity Assessment)

| Standard / Framework | Illustrative Control Objective | Technical Primitive Provided |
|---|---|---|
| **ISO/IEC 42001** | Clause 8 & 9.2: Operation and internal audit trace evidence. | Emits HMAC-SHA-256 integrity tags binding canonical payload hashes to physical wire outcomes. |
| **DORA (EU 2022/2554)** | Article 17: ICT incident detection and classification. | Traps HTTP 504 timeouts into `dispatched_unconfirmed` state; logs transport anomalies for internal incident journals. |
| **NIST NCCoE** | AI Agent Identity: Action-bound ephemeral authorization. | Binds authority strictly to `SHA-256(session_id + sequence + canonical_payload_hash)` with tight wall-clock TTLs. |
| **China TC260 v3.0** | Clause 5.3: Append-only audit record retention. | Stores receipts locally in bitemporal `agentacct.db` with zero external cloud transmission. |

---

## 6. Strategic Takeaway

By anchoring claims to **engineering physics**, replacing probabilistic LLM-as-a-Judge evaluations with **deterministic state probes**, and maintaining absolute precision regarding cryptographic prototypes and regulatory scope, SMAOS delivers an unassailable, audit-ready technical foundation.
