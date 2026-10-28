# Standards Alignment & Runtime Evidence Architecture
## Reconstructable Evidence (ISO/IEC 42006), Open-Weight Governance & Continuous Monitoring

**Document Version:** 1.0  
**Effective Date:** September 2026  
**Scope:** ISO/IEC 42001 / 42006, EU AI Act (Arts. 12 & 14), DORA (Arts. 17 & 28), OCC/FRB SR 11-7  

---

## 1. Executive Summary: The Structural Governance Shift

Enterprise AI governance is undergoing an unavoidable structural migration: **from static, paper-based governance checklists to runtime-enforced, cryptographic execution telemetry.**

While early compliance efforts focused on pre-deployment risk questionnaires, model cards, and periodic evaluation benchmarks, autonomous tool-calling swarms operate dynamically at the network transport layer. When an agent dispatches mutating actions across banking APIs, ERP systems, or cloud infrastructure, static governance tools cannot answer the fundamental forensic question: **"Did the action actually execute, and what cryptographic evidence proves its finality?"**

SovereignNexus bridges this gap by decoupling intent governance (Layer 4) from consequence integrity (Layer 5), supplying the reconstructable execution receipts demanded by emerging international standards.

---

## 2. Open-Weight Model Risk (Concordia AI / Z.AI) & The Local Harness Moat

### 2.1 The Disappearance of Provider Guardrails
As organizations transition from centralized frontier APIs to self-hosted, open-weight models (e.g., Holo4-35B-A3B, Qwen-2.5, DeepSeek-V3, Llama-3.1) deployed on bare metal or sovereign cloud infrastructure:
* **The Perimeter Vanishes:** Cloud-provider moderation endpoints and trust layers disappear. The model weights execute directly within the enterprise boundary.
* **Non-Deterministic Tool Dispatch:** Open-weight models lack proprietary runtime fine-tuning against tool-aliasing, silent parameter mutation, and transport drop recovery.
* **The Local Harness Imperative:** Because governance cannot occur at an external API gateway, it must be enforced **at the local Layer 5 execution boundary**.

### 2.2 Layer 5 Local Membrane Enforcement
SovereignNexus deploys a local, out-of-band proxy/sidecar membrane directly around the open-weight agent runtime:
1. **Ex-Ante JCS Payload Canonicalization (RFC 8785):** Every parameter is normalized into a deterministic SHA-256 fingerprint before thread allocation.
2. **Fail-Closed State Quarantine (`dispatched_unconfirmed`):** When transport dropouts occur (such as HTTP 504 Gateway Timeouts), the local membrane intercepts the ambiguity, halts autonomous retries, and forces a quarantine state.
3. **Silicon-Level Namespace Isolation:** Ensures local open-weight swarms cannot execute unconfirmed side-effects outside approved network boundaries.

---

## 3. Saidot & "Reconstructable Evidence" vs. Paper Checklists

### 3.1 The Continuous GRC Disconnect
Governance platforms like Saidot have pioneered continuous risk management, risk inheritance, and policy lifecycle tracking under the EU AI Act. However, a critical technical disconnect exists:
* **GRC Platforms Track Policy Triggers:** They manage high-level risk classifications, regulatory mapping, and approval workflows.
* **The Socket Reality:** When an auditor, supervisory authority (e.g., BaFin, Czech National Bank), or internal risk committee investigates an operational failure, a policy trigger is not evidence. An auditor requires verifiable telemetry proving the exact payload transmitted, the socket-level response, and whether secondary commits occurred.

### 3.2 ISO/IEC 42006: Reconstructable Evidence
ISO/IEC 42006 establishes requirements for bodies providing audit and certification of artificial intelligence management systems. Under ISO 42006, audit findings cannot rest on unverified model logs or prompt histories; they require **reconstructable, tamper-evident records**.

SovereignNexus provides the missing technical primitive: **the underlying cryptographic telemetry feed.**
* **Ed25519-Signed SCITT Merkle Work Receipts:** Every dispatch produces an RFC 9162 / SCITT-compliant audit receipt binding the agent boot identity, RFC 8785 JCS payload hash, and transport wire status.
* **Automated Evidence Ingestion:** Platforms like Saidot ingest these immutable receipts via webhook/API, transforming abstract risk scores into mathematically auditable proof.

---

## 4. Developer Tooling Efficiency: The Jev Pattern & Typed Gating

Relying on heavy reasoning models to evaluate safety and policy before every tool execution introduces 1–3s latency and extreme token cost overhead. The success of specialized developer tooling (such as `jevgrep`) demonstrates that high-throughput agent reliability requires **sub-100ms, pre-execution typed gating**.

SovereignNexus embeds this exact pattern into its Layer 4 System 1 PEP membrane:
* **Sub-100ms Deterministic Gate:** Evaluates tool payloads against state invariants in `<0.05ms`.
* **Six-Disposition Typed Taxonomy:**
  1. `CONFIRMED`: Authorized for RFC 8785 canonicalization and socket dispatch.
  2. `REFUSED`: Halted ex-ante with **0 token egress** and 0 JVM thread allocation.
  3. `UNKNOWN`: Transport failure / HTTP 504; quarantined as `dispatched_unconfirmed`.
  4. `CONFLICT`: Idempotency key collision with mutated payload.
  5. `MISSING_EVIDENCE`: Required supervisor dual-signature permit missing.
  6. `INVALID_INPUT`: Schema mismatch or malformed structure.

---

## 5. Regulatory & Standards Alignment Matrix

| Regulation / Standard | Requirement / Article | Industry Gap | SovereignNexus / SMAOS Implementation |
|---|---|---|---|
| **ISO/IEC 42006** | Clause 9 & Audit Trajectory: Reconstructable evidence of system operations. | Models produce non-deterministic logs without cryptographic proof of execution. | Emits Ed25519-signed SCITT Merkle receipts binding RFC 8785 JCS payload digests to transport outcomes. |
| **EU AI Act** | Article 12: Automated recording of events (logging) across high-risk systems. | Application logs can be silently altered or deleted post-incident. | Immutably journals all state-changing dispatches with out-of-band SHA-256 evidence digests. |
| **EU AI Act** | Article 14: Human oversight & fail-closed operational halts. | Agents auto-retry after network drops, causing double-commits. | Forces `dispatched_unconfirmed` quarantine under HTTP 504, requiring explicit supervisor re-verification. |
| **DORA (EU 2022/2554)** | Article 17: ICT-related incident detection, classification, and reporting. | Silent API timeouts remain unclassified, leading to unreported operational anomalies. | Automatically classifies transport drops into deterministic incident journals formatted for audit review. |
| **DORA (EU 2022/2554)** | Article 28: Information register on third-party ICT service providers. | Manual tracking of third-party tool and API endpoints used by agents. | Generates automated, schema-compliant xBRL-CSV registers mapping every agent tool call to vendor entities. |
| **OCC / FRB SR 11-7** | Model Risk Management: Validation of model conceptual soundness and outcome analysis. | SR 11-7 validates model reasoning and data drift, but cannot prove network execution finality. | Complements SR 11-7 by acting as the physical Layer 5 measurement plane at the network socket. |

---

## 6. Tri-Jurisdictional Regulatory Alignment (EU + US + China)

By unifying European, American, and Chinese regulatory signals, SMAOS establishes the **only global tri-jurisdictional Layer 5 execution boundary**:

```text
                               GLOBAL JURISDICTIONAL CONVERGENCE
                                               │
             ┌─────────────────────────────────┼─────────────────────────────────┐
             ▼                                 ▼                                 ▼
   EU (ISO 42006 & DORA)            CHINA (TC260 v3.0)                 USA (NIST NCCoE)
 • Reconstructable Evidence       • 6-Month Human Approval Logs      • Action-Bound Ephemeral Identity
 • 504 State Quarantine           • Multi-Layer Tool Interception     • Payload-Bound Authority
 • Merkle SCITT Receipts          • Phased Privilege Escalation       • Single-Execution Finality
             │                                 │                                 │
             └─────────────────────────────────┼─────────────────────────────────┘
                                               │
                                               ▼
                              [SMAOS EXECUTION INTEGRITY LAYER]
                              • RFC 8785 JCS Payload Digest
                              • Action-Bound Idempotency (SHA-256)
                              • Local Bitemporal Ledger (agentacct.db)
                              • Deterministic State Probes
```

### 6.1 Action-Bound Ephemeral Mandates vs. Decaying Bearer Tokens (NIST NCCoE)
Traditional OAuth 2.0 / IAM bearer tokens grant broad, session-level capability that decays over autonomous agent reasoning loops. The NIST NCCoE project specification calls for **Action-Bound Identity**—binding authority strictly to `SHA-256(session_id + sequence + canonical_payload_hash)` with tight wall-clock TTLs.

### 6.2 Phased Privilege Escalation (China TC260 v3.0)
TC260 Appendix 2 mandates dynamic privilege tiering. An agent operates in a restricted sandbox until historical SCITT receipts prove deterministic execution fidelity (`outcome_verified == true`), dynamically unlocking higher-tier tools without code changes.

### 6.3 6-Month Reconstructable Log Retention (TC260 + ISO 42001 Cl. 9.2)
All human approvals, tool dispatches, and reconciliation probes are indexed into the local `agentacct.db` bitemporal ledger. Multinational institutions achieve 100% compliant, 6-month tamper-evident retention with **zero data egress to third-party clouds**.

---

## 7. Strategic Conclusion

By embedding open-weight runtime defenses, SCITT reconstructable evidence feeds, action-bound ephemeral identity, and sub-100ms typed pre-dispatch gating, SovereignNexus transforms compliance from a post-hoc liability into an automated, silicon-enforced operational moat.
