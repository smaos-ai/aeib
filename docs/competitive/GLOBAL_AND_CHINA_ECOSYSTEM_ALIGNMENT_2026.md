# Global & China Agent Execution Security & Standards Landscape (2025–2026)
## Interoperability, GitHub Ecosystem & Regulatory Validation for AEIB v1.1

> **EPISTEMIC & OPERATIONAL NOTICE:**
> Evaluated under the stated architectural model. This document synthesizes verified 2025–2026 open-source repositories, regional standards (China CAICT / ATH-1.0, EU CEN-CENELEC EN 18286, US IETF ACTA/SCITT), and durable execution engines (Temporal, Restate, DBOS) to establish calibrated technical positioning and integration boundaries for AEIB v1.1.

---

### 1. China & APAC AI Agent Standards & Open Source (2025–2026)

#### 1.1 CAICT (MIIT) AI Agent Evaluation Standards & ATH-1.0
The **China Academy of Information and Communications Technology (CAICT)**, operating under the Ministry of Industry and Information Technology (MIIT) and coordinating with the Artificial Intelligence Industry Alliance (AIIA) and ITU-T SG17/SG21, expanded its AI evaluation standards in 2025–2026 from static content filtering to multi-step autonomous execution:

1. **ATH-1.0 (Agent Trust Handshake Protocol 1.0)**
   * **Repository / Spec:** `https://github.com/ath-protocol/agent-trust-handshake-protocol`
   * **Consortium:** Initiated by CAICT alongside Huawei, Tencent, China Telecom, and academic partners.
   * **Technical Scope:** Defines a cross-platform handshake protocol for multi-agent ecosystems addressing four operational pillars:
     1. *Agent Identity Authentication* (cryptographic identity binding across organizational boundaries).
     2. *Fine-Grained Permission Control* (scoped delegation and dynamic privilege attenuation).
     3. *Data Sovereignty & Context Boundaries* (preventing unauthorized memory/context exfiltration).
     4. *Behavior Traceability* (verifiable action logging across multi-agent call chains).
   * **AEIB v1.1 Alignment:** AEIB's Zone 1 / Zone 2 separation and Ed25519 / RFC 8785 JCS decision receipts map directly to the ATH-1.0 *Behavior Traceability* and *Permission Control* verification layers, while adding post-dispatch transport ambiguity latching (`EFFECT_INDETERMINATE`) and `refund_status_v1` target reconciliation.

2. **CAICT Trusted AI Agent Testbed & Stage-Specific Risk Standards**
   * **Reference Portal:** `http://www.caict.ac.cn` & ITU-T SG17 *Security Requirements of AI Agents*.
   * **Technical Scope:** Evaluates autonomous agents across four lifecycle execution stages:
     * *Perception:* Indirect prompt injection and untrusted data ingestion defenses (`AT48`).
     * *Planning:* Task decomposition integrity, loop prevention, and hallucinated tool parameters (`AT42–AT46`).
     * *Memory:* Cross-session state contamination and temporal staleness (`TemporalMemoryDigest` / `STALE_DONT_TRUST_YET`).
     * *Action:* OS/API execution boundary adherence, MCP protocol conformance (`MCP01`), reconnection stability, and sandbox containment.

#### 1.2 Ant Group, Alibaba, Tencent, & Huawei Open-Source Ecosystems on GitHub

| Organization / Ecosystem | Project & URL | Verified Architectural Scope | AEIB v1.1 Interoperability & Boundary Analysis |
| :--- | :--- | :--- | :--- |
| **Ant Group** | **Agent3σ-Canary** (`Agent3Sigma-Canary`)<br>`https://github.com/antgroup/Agent3Sigma-Canary` | Open-source runtime security evaluation and canary stress-testing framework for AI agents under adversarial runtime conditions, privilege escalation attempts, and tool manipulation. | **High Synergy:** Complements AEIB's deterministic 500-episode fault-injection harness (`benchmarks/aeib_execution_integrity/`) with adversarial semantic/tool-layer test vectors. |
| **Alibaba (Cloud Native)** | **Higress (AI & MCP Gateway)**<br>`https://github.com/higress-group/higress` | Envoy-based cloud-native API gateway with dedicated MCP server hosting, unified auth, rate-limiting, and traffic observability. | **North-South Routing vs. L7 Finality:** Higress handles MCP routing and OAuth validation; AEIB enforces pre-dispatch `EO-1` intent persistence, `T_n` microsecond standing checks, and `EFFECT_INDETERMINATE` wire latching behind or inline with Higress. |
| **Alibaba** | **Alibaba Agent Sandbox (`abx`)**<br>`https://github.com/Alibaba-Agent-Sandbox/agent-sandbox` | Isolated execution environments, CLI (`abx`), and SDKs exposing container/microVM sandbox controls as MCP tools for untrusted code execution. | **Zone 1 Containment:** Provides OS/container isolation for Zone 1 agent compute, while AEIB governs Zone 2 -> Zone 3 external transactional mutations. |
| **Linux Foundation / Solo.io / Alibaba / Huawei** | **agentgateway**<br>`https://github.com/agentgateway/agentgateway` | Rust-based data plane designed for LLM routing, MCP tool federation, and Agent-to-Agent (A2A) traffic with OIDC/mTLS authentication and tool RBAC. | **Wire-Level Interop:** AEIB v1.1 integrates as the high-consequence mutation verifier emitting RFC 8785 JCS + Ed25519 receipts for state-mutating tool calls. |
| **Community / Global Fault Injection & Firewalls** | **agent-chaos** (`https://github.com/deepankarm/agent-chaos`)<br>**pipelock** (`https://github.com/luckyPipewrench/pipelock`)<br>**kubernetes-sigs/agent-sandbox** (`https://github.com/kubernetes-sigs/agent-sandbox`) | `agent-chaos` injects transport/semantic faults into agent loops; `pipelock` acts as an inline MCP egress firewall scanning for SSRF/exfiltration and emitting signed runtime receipts. | **Independent Convergence:** Confirms industry convergence on inline MCP egress gating and signed execution receipts, while AEIB uniquely binds pre-dispatch `EO-1` journals to post-dispatch `refund_status_v1` target reconciliation. |

---

### 2. Global Standards & GitHub Implementations (2025–2026)

#### 2.1 CEN/CENELEC EN 18286 vs. ISO/IEC 42001 (EU AI Act Articles 17 & 40)

* **CEN/CENELEC EN 18286:2026 (Quality Management System for EU AI Act Regulatory Purposes)**
  * **Standard Body:** CEN-CENELEC Joint Technical Committee 21 (JTC 21) under European Commission Standardization Request M/593 (`https://ec.europa.eu/growth/tools-databases/enorm/mandate/593_en`).
  * **Regulatory Function:** Specifically drafted to address **Article 17 (Quality Management System)** of the EU AI Act (Regulation (EU) 2024/1689) for high-risk AI systems. Once cited in the Official Journal of the European Union (OJEU), conformance with EN 18286 supports a rebuttable presumption of conformity under **Article 40** of the EU AI Act.
* **Contrast with ISO/IEC 42001:2023 (AIMS)**
  * **ISO/IEC 42001** (`https://www.iso.org/standard/81230.html`) is a horizontal, organization-wide management system standard built on Annex SL (Plan-Do-Check-Act). It governs macro-level organizational AI policy, but **does not by itself confer EU AI Act Article 40 presumption of conformity**.
  * **EN 18286** is product-and-lifecycle-specific, directly mapping the statutory clauses of EU AI Act Article 17—including technical design verification (Art. 17(1)(b)), examination/testing/validation procedures (Art. 17(1)(d)), automatic event logging (Art. 12), human oversight gates (Art. 14), cybersecurity resilience (Art. 15), post-market monitoring (Art. 72), and serious incident reporting (Art. 73).

#### 2.2 IETF ACTA, IETF SCITT, RFC 8785 (JCS), and RFC 9052 (`COSE_Sign1`)

1. **JSON / RFC 8785 JCS / Ed25519 Receipt Track:**
   * **`draft-farley-acta-signed-receipts`** (`https://datatracker.ietf.org/doc/draft-farley-acta-signed-receipts/`): Defines a portable JSON decision receipt canonicalized via **RFC 8785 (JCS)** and signed with **Ed25519** (RFC 8032) for MCP tool calls, but stops at pre-dispatch decision signing without post-dispatch wire fault latching or target reconciliation.
   * **`draft-marques-asqav-compliance-receipts`** (`https://datatracker.ietf.org/doc/draft-marques-asqav-compliance-receipts/`): Profiles signed action receipts for EU AI Act Articles 12 & 26 and DORA ICT incident auditability.
2. **CBOR / `COSE_Sign1` / SCITT Transparency Track:**
   * **RFC 9052 (`COSE_Sign1`)**, **RFC 9942 (COSE Merkle Tree Proofs)**, and **RFC 9943 (SCITT Architecture)** (`https://datatracker.ietf.org/doc/rfc9943/`): Provide binary CBOR signing and append-only transparency log inclusion proofs. AEIB v1.1 natively supports both primary RFC 8785 JCS + Ed25519 receipts and secondary RFC 9052 `COSE_Sign1` wrapping (`v1.1-roadmap/rfc9052_cose_profile.py`).

#### 2.3 Durable Execution Engines vs. L7 Wire-Level Transport Ambiguity Latching

| System & URL | Persistence Mechanism | Behavior Under External L7/L4 Wire Ambiguity (`HTTP 504` / `TCP RST`) | Architectural Contrast with AEIB v1.1 |
| :--- | :--- | :--- | :--- |
| **Temporal**<br>`https://github.com/temporalio/temporal` | Workflow event history cluster; Activities execute outside deterministic sandbox. | Default Activity retry policy automatically re-executes failed/timed-out Activities, assuming downstream idempotency. | Temporal optimizes for workflow availability; AEIB v1.1 enforces fail-closed `EFFECT_INDETERMINATE` latching (`retry_safe: false`) and bounded `refund_status_v1` target reconciliation. |
| **Restate**<br>`https://github.com/restatedev/restate` | Distributed journal (`ctx.run`) logging RPC inputs and step completions. | If an external non-Restate HTTP call drops with `HTTP 504` before `ctx.run` commits completion, standard replay re-invokes the external call unless custom reconciliation is built. | AEIB models uncooperative external wire drops as a first-class state transition with signed restraint/indeterminate receipts and `ProbeBudget: 1`. |
| **DBOS**<br>`https://github.com/dbos-inc/dbos-transact-py` | Workflow steps wrapped in PostgreSQL transactions (`@DBOS.step`). | Achieves local DB rollback, but external HTTP side effects interrupted before step completion row commit face split-brain on recovery replay. | AEIB couples `EO-1` pre-dispatch intent journaling with deterministic startup recovery into `EFFECT_INDETERMINATE` without blind resending. |
