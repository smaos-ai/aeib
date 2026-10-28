# Authority Freshness Contract & Verification Matrix
## Tri-Jurisdictional Runtime Governance Specification (EU ISO 42006 / US NIST NCCoE / China TC260 v3.0)

**Document Version:** 1.0 (September 2026)  
**Standard Classification:** Normative Engineering Contract & Regulatory Mapping  
**Category:** Agent Execution Integrity  
**Tagline:** *“Actions are claims. Outcomes are evidence.”*  

---

## 1. The Core Invariant

$$\text{authorized write} \neq \text{persisted write} \neq \text{correct outcome}$$

Standard enterprise IAM (OAuth 2.0 bearer tokens, AWS IAM session keys) fails for autonomous agents because it grants **session-level privilege** that persists across uncoordinated reasoning loops. 

The **Authority Freshness Contract** decouples long-lived sessions from socket dispatches, replacing bearer tokens with **Action-Bound Ephemeral Mandates (AP2)**.

---

## 2. The 4-Tier State Verification Matrix

Every Model Context Protocol (MCP) tool execution must transition through four explicit, verifiable tiers before an action is classified as complete:

```text
┌────────────────┐      ┌──────────────────┐      ┌───────────────────┐      ┌────────────────────┐
│   TIER 1       │      │     TIER 2       │      │      TIER 3       │      │       TIER 4       │
│   Read-Only    │ ───► │ Write-Authorized │ ───► │  Write-Persisted  │ ───► │  Outcome-Observed  │
│ (Low Blast/RAG)│      │  (System 1 PEP)  │      │ (Socket ACK/200)  │      │ (Physical Ledger)  │
└────────────────┘      └──────────────────┘      └───────────────────┘      └────────────────────┘
```

| Tier | Lifecycle State | Verification Requirement | Forensic Evidence | Failure Disposition |
|---|---|---|---|---|
| **Tier 1: Read-Only** | Low-blast data retrieval (queries, searches). | Baseline agent identity verification. | Tool call log | `INVALID_INPUT` if unparseable |
| **Tier 2: Write-Authorized** | Pre-dispatch policy & threshold clearance. | Sub-100ms System 1 typed gating; RFC 8785 JCS canonicalization. | Signed pre-dispatch receipt | `REFUSED` (0 token/API egress) |
| **Tier 3: Write-Persisted** | Socket transmission & target acknowledgement. | HTTP 200/201 response with matching idempotency key. | Transport ACK or TCP receipt | `DISPATCHED_UNCONFIRMED` on 504 |
| **Tier 4: Outcome-Observed** | Verified physical downstream consequence. | Deterministic post-condition state probe (e.g. database query). | Ed25519 SCITT Merkle Receipt | `INCOMPLETE` / `CONFLICT` |

---

## 3. The Authority Freshness Contract ($\Delta\text{Auth}$)

### 3.1 Mathematical Definition
Authority Freshness measures the wall-clock latency between intent verification and physical execution:

$$\Delta\text{Auth} = t_n - t_0$$

Where:
* **Valid Time ($t_0$):** The UTC timestamp when the agent evaluated policy invariants and verified authorization.
* **Transaction Time ($t_n$):** The UTC timestamp when the network packet was transmitted across the physical socket.

### 3.2 Contractual Constraints
1. **Strict Freshness Ceiling:** For financial and state-mutating actions, $\Delta\text{Auth} \le 100\text{ ms}$. If $\Delta\text{Auth} > 100\text{ ms}$, the authorization token expires ex-ante, and the request is refused.
2. **Clock Skew Mitigation:** Runtimes must synchronize against hardware PTP/NTP sources. Timestamps are paired with **monotonically increasing 64-bit sequence counters** to prevent time-of-check to time-of-use (TOCTOU) manipulation.
3. **Action-Bound Nonce:** The idempotency key is cryptographically bound to the canonical payload:
   $$\text{IdempotencyKey} = \text{SHA-256}(\text{session\_id} \mathbin{\Vert} \text{step\_sequence} \mathbin{\Vert} \text{JCS\_Hash}(\text{arguments}))$$
4. **Instant Revocation:** If a supervisory revocation signal is received within $[t_0, t_n]$, the sidecar membrane drops the socket immediately with 0 token egress.

---

## 4. Tri-Jurisdictional Regulatory Alignment Matrix

By unifying the requirements of the EU, US, and Chinese governance frameworks, SMAOS operates as a single, globally certified Layer 5 execution boundary:

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

### 4.1 Comparative Regulatory Mapping

| Jurisdiction & Framework | Specific Mandate | How SMAOS Enforces Compliance |
|---|---|---|
| **EU: ISO/IEC 42006** | Clause 9: Reconstructable evidence of system operations. | Emits Ed25519-signed SCITT Merkle receipts binding canonical payload hashes to physical wire outcomes. |
| **EU: DORA (EU 2022/2554)** | Article 17: ICT-related incident classification; Article 28: Register of Information. | Deterministically traps HTTP 504 timeouts into `dispatched_unconfirmed`; auto-compiles xBRL-CSV registers. |
| **USA: NIST NCCoE** | AI Agent Standards Initiative: Action-Bound Ephemeral Identity. | Replaces session OAuth bearer tokens with payload-bound single-use nonces ($\text{IdempotencyKey}$). |
| **China: TC260 Framework 3.0** | Clause 5.3: 6-Month Human Approval & Dispatch Retention. | Indexes all agent traces into local `agentacct.db` bitemporal ledger with **0 cloud data egress**. |
| **China: TC260 Appendix 2** | Dynamic Phased Privilege Promotion for Autonomous Agents. | Enforces 4-Tier Verification Matrix; promotes agents from Tier 1 to Tier 4 based on Authority Freshness fidelity. |

---

## 5. Global Commercial Pitch (EU + US + China)

For Chief Information Security Officers and Enterprise Risk Committees operating across multinational jurisdictions:

> *"Multinational operations cannot maintain separate AI safety stacks for European DORA audits, US NIST Agent Identity requirements, and Chinese TC260 approval retention rules.
> 
> Your policy engines and prompt guardrails govern intent, but **SMAOS provides the underlying Layer 5 Execution Integrity Boundary**. It converts every Model Context Protocol (MCP) tool call into a cryptographically signed, action-bound receipt that simultaneously satisfies ISO 42006 audits in Frankfurt, NIST NCCoE agent identity in New York, and TC260 6-month human approval log mandates in Shanghai."*

---

## 6. Risk Register & Mitigations

1. **MCP Protocol Drift:** Abstracted behind an internal JSON-RPC 2.0 normalization adapter layer in `diagnostic_normalizer.py`.
2. **Clock Skew:** Enforced monotonically increasing sequence counters paired with Ed25519-signed UTC timestamps.
3. **Privacy & Data Egress:** Implemented zero-knowledge redaction and selective disclosure over local SCITT receipts.
4. **Human Gate Bottleneck:** Tiered blast-radius approvals triggered only when Authority Freshness drops below threshold ($\Delta\text{Auth} > 100\text{ ms}$) or state ambiguity is detected.
