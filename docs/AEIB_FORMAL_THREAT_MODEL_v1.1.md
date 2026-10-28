# AEIB Formal Threat Model & Financial Ambiguity Contract (`v1.1`)

- **Specification Identifier:** `AEIB-THREAT-MODEL-1.1`
- **Scope:** Wire Boundary, MCP Tool Interception, Transport Ambiguity, Multi-Hop Delegation
- **Status:** Evaluated Specification & Architecture Baseline
- **Date:** October 2026

> **Epistemic Boundary Notice:**  
> This threat model describes defenses, boundaries, and failure modes *under the stated model*. It does not assert absolute security or universal prevention across uncooperative or malicious external banking targets. Structural components such as eBPF LSM and hardware attestation remain structural scaffolding per `AGENTS.md` §5.

---

## 1. Executive Summary & System Boundary

The **Agent Execution Integrity Boundary (AEIB)** is an out-of-process wire gateway positioned between autonomous agent frameworks and mutating external endpoints. 

It treats the AI model as an **unalignable black box** capable of non-deterministic reasoning drift, hallucinations, prompt injections, and specification gaming. Rather than attempting to control internal token generation, AEIB governs the **external physical consequences** of agent tool invocations at the network wire boundary.

```text
┌─────────────────┐      ┌──────────────────────────────┐      ┌──────────────────────┐
│  AI Agent Host  │ ──►  │    AEIB Wire Gate & Interlock│ ──►  │ Downstream Target APIs│
│ (Untrusted Mind)│      │  (Deterministic Truth Plane) │      │  (Mutating Banking)  │
└─────────────────┘      └──────────────────────────────┘      └──────────────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │ Immutable Continuous Ledger  │
                         │ (RFC 8785 JCS + Ed25519)     │
                         └──────────────────────────────┘
```

---

## 2. Asset Register & Security Domains

| Asset ID | Asset Name | Description & Security Sensitivity | Integrity / Confidentiality Model |
| :--- | :--- | :--- | :--- |
| **AST-01** | **Ed25519 Ledger Private Key** | Used by Station 3 to sign `ContinuityReceipt` records and pre-dispatch intent logs. | Private, air-gapped / HSM-isolated; strictly non-exportable. |
| **AST-02** | **Authority Ticket Private Key** | Used by operator/policy engines to mint `DispatchAuthorizationTicket` tokens. | Private, held outside agent execution process. |
| **AST-03** | **Continuous Hash Chain Tip** | Monotonic 32-byte SHA-256 state linking every operational receipt back to genesis. | Append-only, publicly readable, tamper-evident. |
| **AST-04** | **Candidate Action ID (CAID)** | SHA-256 digest computed over RFC 8785 canonical bytes of the mutating request. | Public, collision-resistant idempotency anchor. |
| **AST-05** | **Upstream Credential Handles** | Opaque `grant://` handles mapped to downstream banking API tokens. | Secret tokens stored in vault; agents receive only opaque handles. |

---

## 3. Trust Boundaries & Interaction Surfaces

1. **Boundary A (Agent Runtime $\to$ Station 0 Admission):**
   * *Untrusted Interface.* Ingestion of natural language reasoning, JSON-RPC `tools/call`, and tool arguments.
   * *Threats:* Prompt injection, schema poisoning, recursive JSON parsing bombs, credential leakage.
2. **Boundary B (Station 1 $\to$ Network Socket Dispatch):**
   * *Controlled Interlock.* Pre-dispatch ticket evaluation and `EO-1` intent commitment.
   * *Threats:* TOCTOU parameter substitution, expired tickets, replay attacks, policy epoch drift.
3. **Boundary C (Socket Write $\to$ Target Transport):**
   * *Unreliable Network.* Layer 4/7 transport over TCP/TLS.
   * *Threats:* HTTP 504 timeouts, TCP RST resets, dropped ACK packets, connection pool saturation.
4. **Boundary D (Station 2 $\to$ Primary Target Reconciliation):**
   * *Restricted Probe Channel.* Bounded out-of-band status query (`TargetStatusClient`).
   * *Threats:* Probe DoS amplification, stale read replicas, contradictory target self-reports.
5. **Boundary E (Station 3 $\to$ Offline Verifier):**
   * *Zero-Egress Audit Path.* Export of detached cryptographic receipts.
   * *Threats:* Receipt tampering, non-canonical serialization, signature forgery, PII leakage.

---

## 4. Threat Actor Profiles & Adversary Models

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                ADVERSARY TAXONOMY                                      │
├──────────────────────┬──────────────────────────────────┬──────────────────────────────┤
│ ADVERSARY PROFILE    │ CAPABILITIES & ASSUMED ACCESS    │ TARGETED ATTACK VECTORS      │
├──────────────────────┼──────────────────────────────────┼──────────────────────────────┤
│ ADV-01: Malicious /  │ Generates arbitrary tool calls,  │ • Parameter substitution     │
│ Drifting LLM         │ crafts prompt injections, leaks  │ • Specification gaming       │
│                      │ reasoning into wire payloads.    │ • Excessive call bursts      │
├──────────────────────┼──────────────────────────────────┼──────────────────────────────┤
│ ADV-02: Compromised  │ Returns malicious tool results,  │ • CVE-2026-108586 tag bypass │
│ MCP Tool Server      │ attempts SSRF redirects, hijacks │ • CVE-2026-67431 session grab│
│                      │ agent session handles.           │ • CVE-2026-54688 token leak  │
├──────────────────────┼──────────────────────────────────┼──────────────────────────────┤
│ ADV-03: Adversarial  │ Injects mid-stream TCP RST, drops│ • Blind retry stampede       │
│ Network Transport    │ HTTP responses, delays ACKs to   │ • Duplicate disbursements    │
│                      │ trigger client-side timeouts.    │ • Partition de-sync          │
├──────────────────────┼──────────────────────────────────┼──────────────────────────────┤
│ ADV-04: Sub-Agent    │ Proxies tasks across delegation  │ • Multi-hop scope expansion  │
│ Proxy Attacker       │ chains to bypass root approvals. │ • Budget cap circumvention   │
└──────────────────────┴──────────────────────────────────┴──────────────────────────────┘
```

---

## 5. Threat Vectors & Wire Gate Mitigations Matrix

| Threat Vector | Root Cause Mechanism | AEIB Wire Gate Mitigation | Test Vector & Defense |
| :--- | :--- | :--- | :--- |
| **TOCTOU Action Mutation** | Agent modifies payload between policy authorization and socket dispatch. | [`DecisionToDispatchAuthorityGate`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/p0-tier-one/DecisionToDispatchAuthorityGate.java): Verifies exact `actionDigest == sha256:CAID(wire_bytes)`. | `test_priority_p0_decision_to_dispatch_authority_ticket_gate` |
| **MCP Scope Bypass**<br>*(CVE-2026-108586)* | Filter tag negation expression (`not admin`) bypasses tool authorization. | [`McpSecurityHardeningGate`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/unified_governance_stack.py#L4488): Drops negated filters fail-closed; drops unpinned capability URIs. | `test_mcp_security_hardening_gate_cve_mitigations` |
| **MCP Session Hijacking**<br>*(CVE-2026-67431)* | Transport fails to bind active session to caller principal. | [`AeibMcpGovernanceAdapter`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/p0-tier-one/AeibMcpGovernanceAdapter.java): Enforces `AuthorizedPrincipalBinding` asserting `session_owner == caller`. | `test_aeib_mcp_governance_adapter_apb_halt_resume_loop` |
| **SSRF & Token Leaks**<br>*(CVE-2026-54688)* | Tool returns redirect to rogue endpoint, leaking bearer credentials. | Replaces raw secrets with opaque `grant://` handles bound strictly to allowlisted `credential_audience`. | `test_signal1_credential_vault_gate_opaque_ref_and_raw_secret_rejection` |
| **Sub-Agent Scope Escalation** | Intermediate agent proxies call to higher-privilege agent without scope attenuation. | [`DelegationAttenuationGate`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/p0-tier-one/DelegationAttenuationGate.java): Enforces monotonic caveat narrowing ($\text{Child} \subseteq \text{Parent}$). | `test_gap8_cross_agent_delegation_chain_verification_and_scope_attenuation` |
| **Transport Ambiguity Stampede** | 504 Timeout triggers blind automatic retries, causing duplicate disbursements. | Latches `EFFECT_INDETERMINATE` (`retry_safe: false`); mandates single-attempt primary reconciliation. | `test_01_probe_failure_escalation_cascade` |
| **Machine-Speed Loops** | Rogue agent issues thousands of micro-transactions per second. | [`BehavioralAnomalyInterlock`](file:///Users/andriileukhin/Documents/SovereignNexus/v1.1-roadmap/unified_governance_stack.py#L4442): Latches velocity bursts into `EFFECT_INDETERMINATE`. | `test_behavioral_anomaly_interlock_rate_burst_and_indeterminate_latch` |

---

## 6. The Financial Ambiguity Contract

In financial and transactional environments, network uncertainty is an inherent physical property of distributed systems. AEIB strictly codifies the **3 Financial Ambiguity Rules**:

### Rule 1: Mandatory Content-Addressed Idempotency Key
Every mutating request passing through the AEIB gate MUST include a deterministic idempotency anchor:
$$\text{Idempotency-Key} = \text{CAID} = \text{SHA-256}(\text{RFC 8785 JCS}(\text{wire\_payload}))$$
Requests lacking idempotency headers or using random unrepeatable nonces are rejected fail-closed at Station 1.

### Rule 2: Blind Retries Strictly Forbidden on Mid-Flight Drops
If an HTTP 504 Gateway Timeout, TCP RST, or socket drop occurs after wire bytes have been transmitted:
* The transaction state is immediately latched to **`EFFECT_INDETERMINATE`**.
* The transaction metadata sets **`retry_safe = false`**.
* All automated, uncoordinated client retries are blocked at the AEIB gate.

### Rule 3: Single-Attempt Primary Status Reconciliation
To resolve `EFFECT_INDETERMINATE`, AEIB initiates an out-of-band status probe against the primary target provider:
* **`ProbeBudget: 1`**: Restricted to exactly one status probe attempt per ambiguous dispatch to prevent target DoS amplification.
* **Authoritative Target Matching**: The probe queries operation-specific evidence (`operation_id`, `target_transaction_id`), not naive connection pings.
* If the primary confirms execution $\to$ `CONFIRMED`.
* If the primary confirms transaction never existed $\to$ `REFUTED` (retry allowed).
* If the status probe times out or target remains exhausted $\to$ Latch remains `EFFECT_INDETERMINATE`, escalating to dual-control human operator review.

---

## 7. Residual Risks & Epistemic Boundaries

1. **Hardware / Host OS Compromise:** If an attacker gains Ring 0 root access to the physical host running AEIB, they can compromise the memory space of the JVM or Python runtime. *Mitigation:* Documented strictly under the assumption of host OS integrity; hardware enclaves (TDX/SEV) remain structural scaffolding.
2. **Target Provider Non-Determinism:** If downstream financial targets commit transactions without logging an idempotency key or supporting status queries, AEIB preserves `EFFECT_INDETERMINATE` and halts. It does not synthesize phantom confirmations.
3. **Eventual Consistency in Saga Compensation:** The saga compensator provides *eventual consistency* via asynchronous queues, NOT atomic distributed 2-Phase Commit (2PC).

---

## 8. Verification & Audit Trail

All threat mitigations defined in this document are mapped 1:1 to executable test cases in [`tests/test_unified_governance_stack.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tests/test_unified_governance_stack.py), verified under the zero-mock AST purity scanner.
