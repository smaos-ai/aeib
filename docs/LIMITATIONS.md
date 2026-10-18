# AEIB Operational Limitations & Residual Risk Disclosure

**Document Status:** Canonical Limitations & Boundary Disclosure (October 2026)  
**Applicability:** All AEIB Deployments (v1.0.0-rc.3 / v1.0.0-rc.11 / v1.1 Roadmap)  
**Epistemic Notice:** This system operates under a strict epistemic boundary. All capabilities, mitigations, and bounds described herein are **observed**, **tested**, **evaluated**, and **configured** **under the stated model**. AEIB provides a deterministic execution boundary for consequential agent mutations; it does not eliminate all operational risks.

---

## 1. Physical Perimeter & Trust Boundary

The Agent Execution Integrity Boundary (AEIB) enforces runtime constraints at **Layer 3 (Wire & Ledger Plane)** and **Layer 2.5 (Local In-Process Pre-Dispatch Interlock)**. It mediates communication between the untrusted agent runtime (LLM reasoning loops, subagent hierarchies, MCP client tools) and external stateful targets (banking endpoints, database servers, payment rails, cloud APIs).

```
+---------------------------------------------------------------------------------------+
|                                    HOST MACHINE                                       |
|                                                                                       |
|  [ Untrusted Agent Runtime ]                         [ AEIB Boundary ]                |
|  +-----------------------+                           +-----------------------------+  |
|  | LLM Planning Loop     |  Internal RPC / IPC       | Station 1: Pre-Dispatch     |  |
|  | Subagent Workers      | ------------------------> | - Conjunctive 5-Term Gate   |  |
|  | MCP Client Tools      |                           | - RFC 8785 JCS CAID Binding |  |
|  +-----------------------+                           +--------------+--------------+  |
|             |                                                       |                 |
|             | (Attempts direct socket egress                        v                 |
|             |  if container isolation is missing!)   +-----------------------------+  |
|             x - - - - - - - - - - - - - - - - - - -  | Station 2: Network Sidecar  |  |
|                                                      | - Zero-Credential Proxy     |  |
|                                                      | - EFFECT_INDETERMINATE Latch|  |
|                                                      | - ProbeBudget: 1 Reconcile  |  |
|                                                      +--------------+--------------+  |
|                                                                     |                 |
+---------------------------------------------------------------------|-----------------+
                                                                      | Outbound TLS
                                                                      v (Signed Headers)
                                                       +-----------------------------+
                                                       | Authoritative External Target|
                                                       | (Payment Rail / Bank API)   |
                                                       +-----------------------------+
```

### 1.1 Structural Scaffolding vs. Active Enforcement
Deploying operators must distinguish between fully verified runtime logic and architectural scaffolding:
- **Active Enforced Logic:** Station 1 conjunctive pre-dispatch interlock, RFC 8785 JCS canonicalization, Ed25519 cryptographic signing, deterministic idempotency key derivation, `EFFECT_INDETERMINATE` transport latching, single-flight probe reconciliation (`ProbeBudget: 1`), and spend quota escrow tracking (`AT56`–`AT64`).
- **Structural Scaffolding (`SCAFFOLD_ONLY`):** The eBPF socket filters in `ebpf/` and the Confidential VM attestation routines in `hardware_attestation/` provide structural interfaces and blueprints. They do not provide live kernel-level or hardware-enforced protection unless compiled and loaded onto a compatible Linux kernel with eBPF LSM enabled and AMD SEV-SNP / Intel TDX hardware attestation drivers present.

---

## 2. Attack Vectors & Operational Limitations

### 2.1 Proxy Bypass Vectors
- **Limitation:** The Station 2 sidecar binds to an ephemeral loopback socket (`127.0.0.1`). If the host environment does not enforce strict network namespace isolation (e.g., via Docker container network modes, Kubernetes NetworkPolicies, or kernel iptables/eBPF routing), a compromised agent process or malicious script could initiate direct outbound TCP/TLS connections to external APIs, entirely bypassing AEIB.
- **Prerequisite:** Production deployments must enforce network egress restrictions at the OS/container runtime level, ensuring that the agent process can only route outbound traffic through the AEIB loopback proxy port.

### 2.2 Browser Trust Assumptions
- **Limitation:** When agents interact with web browsers or desktop GUI interfaces (e.g., via Playwright, Puppeteer, or Chrome Extensions), AEIB governs the backend tool-dispatch boundary but cannot inspect client-side DOM manipulation.
- **Exposure:** AEIB cannot prevent:
  - Malicious DOM script injection or cross-site scripting (XSS) within the browser instance.
  - Compromised browser extensions modifying DOM elements before the agent reads them.
  - UI clickjacking or deceptive styling misleading an agent visual parser.
  - Human-in-the-loop social engineering where a user confirms a poisoned prompt in an interactive chat session.

### 2.3 Target Semantics & Idempotency Compliance
- **Limitation:** AEIB's deduplication and retry protections rely on external targets adhering to standard HTTP and idempotency semantics.
- **Exposure:**
  - If a downstream target API silently ignores `Idempotency-Key` headers and executes duplicate mutations on repeated HTTP POST requests, AEIB's deterministic key binding cannot force the target to behave idempotently.
  - If a target API lacks a reliable read/probe endpoint (e.g., `GET /refunds/{id}` or `GET /checkout_sessions/{id}`) to query in-flight transaction status, AEIB cannot automatically resolve an `EFFECT_INDETERMINATE` latch, requiring manual human investigation.
  - If an upstream target experiences internal database corruption or non-atomic state updates, AEIB receipts document the outbound wire payload and observed transport return, but cannot repair downstream inconsistency.

### 2.4 Cryptographic Key Custody Models
- **Limitation:** AEIB signs receipts and authorizations using Ed25519 private keys. In prototype and software-only deployments, private keys reside in host memory or environment configurations.
- **Exposure:** If the host machine, container host, or root user space is compromised, in-memory signing keys can be exfiltrated. Production security requires delegating key storage to a hardware security module (HSM), Cloud KMS, or a hardware-isolated Trusted Execution Environment (TEE).

---

## 3. Bounded Residual Risk: 5 Reduced Risks vs. 8 Un-Eliminatable Residual Risks

AEIB provides bounded risk mitigation rather than universal protection. Deployments must evaluate the 5 reduced risks against the 8 un-eliminatable residual risks:

### 3.1 The 5 Reduced Risks

| Risk Category | Pre-Boundary Baseline Failure Mode | AEIB Mitigated Posture | Verified Test / Evidence |
| :--- | :--- | :--- | :--- |
| **1. Ambiguous Transport Retry Duplication** | HTTP 504 / TCP RST causes naive agent retry loops to fire duplicate charges or payouts. | Station 2 traps transport ambiguity in `EFFECT_INDETERMINATE`, blocks naive retries, and executes bounded `ProbeBudget: 1` status inquiry. | Deterministic 500-episode harness: 0 duplicate mutations observed across 302 blocked retries. |
| **2. Uncoordinated Parallel Write Collisions** | Multi-agent clusters execute concurrent writes to shared records, creating race conditions and state corruption. | Station 1 requires disjoint write partitions and pre-dispatch intent locking before mutation dispatch. | `tests/test_opencode_codemode_and_hotreload.py` |
| **3. Post-Execution Audit Deniability** | Ad-hoc text logs and trace spans can be deleted, truncated, or modified post-hoc. | RFC 8785 JCS canonicalization + Ed25519 signing + optional RFC 9942 SCITT Merkle receipts provide tamper-evident non-repudiation. | `tests/test_phase4_scitt_cose_cli.py` |
| **4. Sybil Rotator Quota Evasion** | Agents spawn ephemeral subagents or rotate identifiers to bypass local velocity caps. | `RootSponsorQuotaTree` aggregates all subagent spend into root sponsor 5h Sprint and 7d Epoch pools (`AT56`). | `tests/test_sybil_rotator_and_smurfing.py` |
| **5. Untrusted Context / Tool Taint Escalation** | Indirect prompt injection via untrusted tools tricks LLM into executing high-consequence mutations. | Bell-LaPadula taint tracking degrades session consequence ceiling (`AT57b`, `AT64`) upon ingesting Tier-2 tool outputs. | `tests/test_at64_rail_interop_and_mcp_tool_taint.py` |

### 3.2 The 8 Un-Eliminatable Residual Risks

1. **Compromised Signing Keys:**
   - If an attacker obtains root sponsor private keys or Station 1 signing keys, they can mint valid authorizations. Cryptography cannot distinguish between authorized usage and unauthorized usage with legitimate keys.
2. **Compromised Target API:**
   - If the remote banking server, payment gateway, or cloud API is malicious or internally compromised, it can acknowledge receipts without settling funds, or mutate internal state outside the wire contract.
3. **Compromised Host / Kernel:**
   - If the underlying operating system kernel or hypervisor running AEIB is compromised, an attacker can alter memory, tamper with running Python/Rust processes, or manipulate loopback socket traffic.
4. **Bad Policy Configuration:**
   - If administrators configure excessive financial velocity ceilings, disable taint checks, or misclassify untrusted tools as system-pinned, AEIB will faithfully enforce the flawed configuration.
5. **Human Approval Error (Rubber-Stamping):**
   - For high-consequence actions requiring Step-Up authorization, if the human supervisor approves a poisoned request without due diligence, AEIB executes the authorized action.
6. **Target-Side Settlement Failure:**
   - Downstream payment rails may experience delayed settlement failures, chargebacks, or manual clawbacks days after an HTTP 200 OK receipt is issued. AEIB tracks wire-level settlement finality, not banking system insolvency.
7. **Legal & Regulatory Noncompliance:**
   - While AEIB generates evidence packages aligned with DORA Article 17, DORA Article 28(3), and EU AI Act Articles 12–17 (`EN 18286`), the existence of technical receipts does not constitute legal certification or compliance immunity.
8. **Loss of Availability (Fail-Closed Trapping):**
   - AEIB is architected to prioritize safety and integrity over availability. Under ambiguous network faults, missing signatures, or corrupted ledgers, AEIB halts execution fail-closed. This deliberate design choice means transient network degradation can result in blocked transactions until reconciliation completes.
