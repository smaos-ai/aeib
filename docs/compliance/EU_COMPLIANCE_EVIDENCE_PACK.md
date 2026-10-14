# AEIB Compliance Evidence Pack: Financial Execution Integrity & Operational Resilience

**Document Identifier:** `AEIB-COMPLIANCE-EVIDENCE-PACK-v1.0`  
**Classification:** Technical Evidence Dossier & Evaluation Benchmark Baseline  
**Scope:** Agent Execution Integrity Boundary (AEIB), Out-of-Band Wire Gateway, Financial Settlement Gates  
**Status:** Evaluated Specification & Test-Verified Baseline (`v1.0.0-rc.1` / `v1.1-roadmap`)  
**Date:** October 2026  

---

> ### Mandatory Buyer-Facing Notice
> **"AEIB produces technical evidence that may support your AI-governance, audit, and operational-resilience program. It does not by itself make an AI system compliant with the EU AI Act, GDPR, or DORA. Integration requires the customer to operate an AEIB boundary in their own environment and provide an authenticated target-side status endpoint for reconciliation."**

---

## 1. Executive Summary & Epistemic Notice

Autonomous artificial intelligence agents powered by Large Language Models (LLMs) are increasingly deployed across banking, payment processing, and corporate finance workflows. These agents interact with critical settlement systems—initiating customer refunds, processing credit facility drawdowns, executing SEPA/SWIFT wire disbursements, and modifying core account ledgers.

However, LLMs operate as **probabilistic, non-deterministic reasoning engines**. They exhibit cognitive vulnerabilities that are fundamentally incompatible with financial accounting standards:
* **Prompt Injection & Reasoning Drift:** Adversarial instructions or context contamination induce agents to issue unauthorized payments, hallucinate credit limits, or substitute transaction beneficiaries.
* **The Post-Hoc Interpretability Trap:** Frontier models frequently generate eloquent, plausible-sounding natural-language rationales for erroneous or malicious actions.
* **Transport Ambiguity Failure Modes:** When a network socket drops (`HTTP 504 Gateway Timeout` or `TCP RST`) after an agent transmits a transaction payload, standard agent SDKs trigger uncoordinated retry storms, causing duplicate disbursements and unclassified ledger anomalies.
* **Post-Hoc Telemetry Gaps:** Traditional observability architectures emit logs after an event completes. If an agent process crashes mid-syscall during socket dispatch, mutations execute downstream with zero local record.

The **Agent Execution Integrity Boundary (AEIB)** is an out-of-process, deterministic wire gateway deployed between autonomous agent runtimes and downstream mutating target endpoints. AEIB operates on a foundational architectural principle: **treat the AI model as an unalignable black box and govern the physical consequences of its tool invocations at the network wire boundary**.

```text
┌─────────────────────────┐          ┌───────────────────────────────────┐          ┌─────────────────────────┐
│   Agent Runtime Host    │          │  AEIB Wire Gateway & Interlock    │          │ Downstream Banking Core │
│   (Zone 1: Untrusted)   │ ───────► │  (Zone 2: Deterministic Boundary) │ ───────► │   (Zone 3: Target API)  │
│                         │          │                                   │          │                         │
│ • Probabilistic LLM     │          │ • Dead Salmons Reasoning Strip    │          │ • Payment Gateways      │
│ • Tool Call Proposals   │          │ • RFC 8785 JCS CAID Derivation    │          │ • Settlement Mainframe  │
│ • Ephemeral Thoughts    │          │ • Single-Use Ticket Burn Gate     │          │ • Status Probe Endpoint │
└─────────────────────────┘          │ • Evidence-Before-Effect (EO-1)   │          └─────────────────────────┘
                                     │ • EFFECT_INDETERMINATE Latch      │
                                     │ • Bounded Probe Reconciler        │
                                     └─────────────────┬─────────────────┘
                                                       │ Emits Detached
                                                       ▼ Signed Receipts
                                     ┌───────────────────────────────────┐
                                     │ Standalone Offline Verifier       │
                                     │ (Zone 4: Zero-Egress Auditor)     │
                                     │                                   │
                                     │ • Pinned Ed25519 Public Key       │
                                     │ • Sequential SHA-256 Hash Chain   │
                                     │ • Air-Gapped Verification Engine  │
                                     └───────────────────────────────────┘
```

### Epistemic & Linguistic Boundaries

Per the SovereignNexus Architectural Directives (`AGENTS.md` §1), this document is authored under a strict epistemic lock:
* **Permitted Epistemic Classifications:** The statements, metrics, and capabilities described herein represent configurations that have been **observed**, **tested**, **evaluated**, or **configured** **under the stated model**, or represent an active **prototype** or structural **scaffold**.
* **Prohibited Marketing Overclaims:** AEIB explicitly rejects unverified marketing claims or assertions of flawless operation. No runtime system operating over distributed networks can provide absolute invulnerability. All capabilities described herein are limited to behavior observed under the stated evaluation models.
* **Regulatory Stance:** AEIB is a software component and runtime evidence generator. It does not confer automatic compliance. Any determination of conformity with the EU AI Act (Regulation (EU) 2024/1689), GDPR (Regulation (EU) 2016/679), or DORA (Regulation (EU) 2022/2554) remains the legal responsibility of the deploying financial institution and its designated compliance officers.

---

## 2. The Before vs. After Customer Refund / Payment Architecture

To understand the operational and regulatory necessity of AEIB, consider a high-volume financial use case: **Autonomous Customer Refund Processing**.

### The "Before" Architecture: Unbounded Agent Integration (Status Quo)

In typical agent deployments (e.g., using raw LangChain, AutoGen, CrewAI, or direct OpenAI/Anthropic tool calling), the agent interacts directly with banking APIs or passes through a standard HTTP proxy:

```text
[Customer Chat / Dispute]
           │
           ▼
┌────────────────────────────────────────────────────────────────────────┐
│ UNBOUNDED AGENT RUNTIME (Python / Node.js)                             │
│ • System Prompt + Tool Definitions                                     │
│ • LLM generates JSON-RPC: `issue_refund(amount=150.00, cust_id=101)`  │
│ • LLM includes internal chain-of-thought in payload arguments          │
└────────────────────────────────────────────────────────────────────────┘
           │ Direct Outbound HTTPS Call
           │ (Bearer token exposed in agent memory space)
           ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PUBLIC INTERNET / CORPORATE WAN                                        │
│ • Transient Network Jitter / Packet Loss                               │
│ • Server processes refund, but TCP connection drops before ACK         │
└────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────────────────────┐
│ DOWNSTREAM PAYMENT GATEWAY / CORE BANKING                              │
│ • Executes payment mutation: €150.00 debited from merchant account     │
│ • Transmits HTTP 200 OK, but client socket drops                       │
└────────────────────────────────────────────────────────────────────────┘
```

#### Observed Failure Modes in the "Before" Architecture:
1. **Unchecked Ephemeral Reasoning Ingestion:** The LLM injects natural-language rationales (`_reasoning: "Customer was upset, authorized exception credit"`) into the mutating API call. If an attacker injects text into the customer chat, the model passes adversarial instructions directly to the target API.
2. **Blind Retry Storms on Transport Drops:** The payment server debits the merchant account and commits the refund. However, a transient gateway timeout (`HTTP 504`) or TCP reset (`TCP RST`) severs the socket before the agent receives the HTTP response. The agent SDK catches the socket exception, assumes the transaction failed, and executes an automated exponential backoff retry. The agent issues the refund 3 times, causing €450.00 to be disbursed for a single €150.00 claim.
3. **Mid-Syscall Ghost Mutations:** If the agent host experiences an unhandled out-of-memory (OOM) error or container eviction while the socket write syscall is in flight, the packet departs the network interface card (NIC), but the local agent runtime terminates before writing a log. Post-hoc audit logs show zero record of why funds left the bank.
4. **Time-of-Check to Time-of-Use (TOCTOU) Action Mutation:** A policy gate approves an intent to refund €150.00. Between the policy check and the socket dispatch, non-deterministic sub-agents modify payload parameters to €15,000.00 or alter the beneficiary IBAN.
5. **PII and PCI-DSS Data Leakage:** Unredacted customer IBANs, Primary Account Numbers (PANs), and personal identifiers are transmitted to third-party cloud logging platforms (Datadog, Splunk) for post-hoc debugging, triggering GDPR Article 33 and PCI-DSS non-compliance findings.

---

### The "After" Architecture: AEIB Governed Financial Action Boundary

With AEIB deployed, the agent is physically isolated in Zone 1. All mutating actions must pass through the AEIB 4-Station deterministic wire pipeline in Zone 2:

```text
[Customer Dispute]
        │
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ ZONE 1: AGENT RUNTIME SANDBOX (Untrusted Mind)                         │
│ • LLM generates CandidateAction proposal                               │
│ • Proposes wire mutation via localhost socket to AEIB Gateway         │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ ZONE 2: AEIB WIRE GATEWAY & LOCAL IMMUTABLE LOG                        │
│                                                                        │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ STATION 0: ADMISSION & SANITIZATION                                │ │
│ │ • "Dead Salmons" Filter: Strips `_reasoning`, `chain_of_thought`   │ │
│ │ • Sensitive Data Sanitizer: Flags unredacted IBAN/PAN fail-closed  │ │
│ │ • RFC 8785 JSON Canonicalization Scheme (JCS) Normalization        │ │
│ └──────────────────────────────────┬─────────────────────────────────┘ │
│                                    │ Purified Canonical Parameters     │
│                                    ▼                                   │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ STATION 1: DISPATCH INTERLOCK & AUTHORITY TICKET BURN              │ │
│ │ • Computes deterministic CAID: SHA-256(RFC8785(wire_payload))      │ │
│ │ • Standing Predicate: Target allowlist + Policy Epoch verification │ │
│ │ • Spend Ceiling Interlock: If amount > ceiling -> STEP_UP halt     │ │
│ │ • Burns single-use DispatchAuthorizationTicket (replay protection) │ │
│ │ • Evidence-Before-Effect (EO-1): Signs pre-dispatch intent journal │ │
│ └──────────────────────────────────┬─────────────────────────────────┘ │
│                                    │ Dispatches with Idempotency-Key   │
│                                    ▼                                   │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ STATION 2: EFFECT RECONCILER (Transport Ambiguity Latch)           │ │
│ │ • Socket write executed with `Idempotency-Key: <CAID>`             │ │
│ │ • If HTTP 504 / TCP RST -> Latches EFFECT_INDETERMINATE            │ │
│ │ • Enforces `retry_safe: false` (blocks agent retry storms)         │ │
│ │ • Queries authenticated status endpoint under strict ProbeBudget: 1│ │
│ │ • Resolves state to CONFIRMED or REFUTED; escalates if unresolved  │ │
│ └──────────────────────────────────┬─────────────────────────────────┘ │
│                                    │ Reconciled Wire Truth             │
│                                    ▼                                   │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ STATION 3: CONTINUOUS IMMUTABLE LEDGER                             │ │
│ │ • Appends transaction to monotonic SHA-256 hash chain             │ │
│ │ • Signs canonical ContinuityReceipt statement with Ed25519         │ │
│ │ • Emits detached receipt for offline verification                  │ │
│ └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ ZONE 3: TARGET FINANCIAL INFRASTRUCTURE                                │
│ • Validates `Idempotency-Key` (CAID) on mutate endpoint                │
│ • Exposes dedicated, authenticated `/v1/payments/{id}/status` endpoint │
└────────────────────────────────────────────────────────────────────────┘
```

#### Observed Properties in the "After" Architecture:
* **Deterministic Idempotency:** Every transaction carries an `Idempotency-Key` equal to the 64-hex SHA-256 digest of the canonical RFC 8785 payload bytes (`CAID`).
* **Suppression of Blind Retries:** If the wire connection drops post-dispatch, AEIB latches `EFFECT_INDETERMINATE` with `retry_safe: false`. The agent cannot retry until Station 2 executes an authenticated target status reconciliation.
* **Crash-Resilient Intent Logging:** Station 1 writes an `EO-1` pre-dispatch intent record to disk before invoking the network socket write. A crash mid-syscall is detected and resolved upon process restart via `recover_from_crash()`.
* **Zero-Egress Auditability:** Complete action receipts can be extracted and verified on an air-gapped machine in Zone 4 using standalone verification binaries without external network connectivity.

---

## 3. Complete Data-Flow Diagram

The following sequence diagram illustrates the lifecycle of a financial transaction under nominal dispatch, STEP_UP escalation, and transport fault reconciliation.

```mermaid
sequenceDiagram
    autonumber
    participant Agent as Zone 1: Agent Runtime
    participant Gate as Zone 2: AEIB Gateway (St. 0 & 1)
    participant Reconciler as Zone 2: AEIB Reconciler (St. 2)
    participant Ledger as Zone 2: AEIB Ledger (St. 3)
    participant Approver as Human Risk Officer (Dual-Control)
    participant Target as Zone 3: Target Financial API
    participant Auditor as Zone 4: Standalone Offline Verifier

    %% SCENARIO A: NOMINAL DISPATCH UNDER POLICY CEILING
    rect rgb(240, 248, 255)
    Note over Agent, Target: Scenario A: Nominal Customer Refund (<= Policy Ceiling)
    Agent->>Gate: tools/call issue_refund(amount=150.00, _reasoning="...", token="...")
    Gate->>Gate: Station 0: Strip ephemeral reasoning ("Dead Salmons" filter)
    Gate->>Gate: Station 0: Scrub & validate PII/IBAN patterns
    Gate->>Gate: Station 1: Compute CAID = SHA-256(RFC8785(wire_bytes))
    Gate->>Gate: Station 1: Verify Standing (target allowlist, active epoch, amount <= ceiling)
    Gate->>Gate: Station 1: Burn single-use DispatchAuthorizationTicket
    Gate->>Ledger: Station 1: EO-1 Write-Before-Execute (fsync DISPATCH_INTENT journal)
    Gate->>Reconciler: Forward dispatch with Idempotency-Key: CAID
    Reconciler->>Target: POST /v1/refunds (Idempotency-Key: <CAID>)
    Target-->>Reconciler: HTTP 200 OK (Transaction Committed)
    Reconciler->>Ledger: Commit disposition CONFIRMED
    Ledger->>Ledger: Append to SHA-256 chainTip & sign with Ed25519
    Ledger-->>Gate: Emit ContinuityReceipt (envelope + signature)
    Gate-->>Agent: tools/call response: CONFIRMED (Receipt attached)
    end

    %% SCENARIO B: STEP_UP DUAL-CONTROL ESCALATION
    rect rgb(255, 250, 240)
    Note over Agent, Approver: Scenario B: High-Value Refund (> Policy Ceiling)
    Agent->>Gate: tools/call issue_refund(amount=15000.00)
    Gate->>Gate: Station 1: Amount €15,000 > Ceiling €5,000 -> Halt STEP_UP_REQUIRED
    Gate-->>Agent: Error: STEP_UP_REQUIRED (ChallengeNonce issued)
    Gate->>Approver: Push RFC 9470 Step-Up Challenge (CIBA / WebAuthn prompt)
    Approver->>Approver: Inspect purified canonical action & CAID
    Approver->>Gate: Submit Ed25519-signed HumanStepUpAssertion
    Gate->>Gate: Verify approver signature, role ACR level, burn nonce against replay
    Gate->>Ledger: Mint signed STEP_UP_AUDIT_RECEIPT
    Gate->>Target: Authorized Dispatch (Idempotency-Key: <CAID>)
    Target-->>Gate: HTTP 200 OK
    Gate->>Ledger: Mint final CONFIRMED ContinuityReceipt
    end

    %% SCENARIO C: TRANSPORT WIRE FAULT & BOUNDED RECONCILIATION
    rect rgb(255, 240, 245)
    Note over Agent, Target: Scenario C: Transport Fault (HTTP 504 / TCP RST)
    Agent->>Gate: tools/call issue_refund(amount=450.00)
    Gate->>Gate: Authorize & Burn Ticket; Log EO-1 Intent
    Gate->>Reconciler: Dispatch POST /v1/refunds
    Reconciler->>Target: Socket Write departed NIC...
    Target--xReconciler: Connection Drops (HTTP 504 Gateway Timeout / TCP RST)
    Reconciler->>Reconciler: Wire Interlock latches EFFECT_INDETERMINATE (retry_safe: false)
    Note over Reconciler, Target: Execute Bounded Out-of-Band Status Probe (ProbeBudget: 1)
    Reconciler->>Target: GET /v1/payments/status?caid=<CAID>
    alt Case 1: Target Confirms Execution
        Target-->>Reconciler: HTTP 200 {status: "SETTLED", tx_id: "tx_998"}
        Reconciler->>Ledger: Update disposition to CONFIRMED
        Ledger-->>Gate: Mint RESOLUTION_RECEIPT (disposition: CONFIRMED)
        Gate-->>Agent: Result: CONFIRMED (reconciled out-of-band)
    else Case 2: Target Status Endpoint Times Out / Unreachable
        Target--xReconciler: HTTP 504 Timeout on Status Probe
        Reconciler->>Ledger: Preserve uncertainty: PRESERVED_UNCERTAINTY
        Ledger-->>Gate: Mint ContinuityReceipt (disposition: EFFECT_INDETERMINATE)
        Gate-->>Agent: Halt: EFFECT_INDETERMINATE (escalated to Human Ops)
    end
    end

    %% OFFLINE AUDIT
    rect rgb(245, 245, 245)
    Note over Ledger, Auditor: Standalone Offline Verification (Air-Gapped)
    Ledger-->>Auditor: Ingest ContinuityReceipt JSON stream + Public Key
    Auditor->>Auditor: Assert SHA-256 + Ed25519 algorithms
    Auditor->>Auditor: Verify Ed25519 signature over canonical RFC 8785 bytes
    Auditor->>Auditor: Re-canonicalize JSON statement & check byte equality
    Auditor->>Auditor: Assert SHA-256(prior_receipt) == receipt.statement.chainTip
    Auditor-->>Auditor: Output: VERIFIED (Exit Code 0)
    end
```

---

## 4. Trust-Boundary & Network Domain Diagram

AEIB enforces strict network segregation across four logical execution zones. Network access controls and routing rules are configured to prevent untrusted agents from bypassing the governance interlock.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 ZONE ARCHITECTURE                                      │
├────────────────────────────────────────┬───────────────────────────────────────────────┤
│ ZONE 1: AGENT RUNTIME SANDBOX          │ ZONE 2: AEIB WIRE GATEWAY & LOCAL JOURNAL     │
│ (Untrusted Mind Domain)                │ (Integrity & Governance Domain)               │
│                                        │                                               │
│ • Framework: LangChain / AutoGen / MCP │ • Station 0: Admission & Filter Gate          │
│ • Process: Standard user-space runtime │ • Station 1: Dispatch Interlock & Ticket Burn │
│ • Network Policy:                      │ • Station 2: Effect Reconciler & Wire Trap    │
│   - Localhost unix socket / loopback   │ • Station 3: Continuous Ledger & HSM Key      │
│   - Zero outbound egress to Internet   │ • Local Storage: Append-Only SQLite / DuckDB  │
│   - Zero direct egress to Zone 3 APIs  │ • Network Policy: Outbound HTTPS strictly to  │
│                                        │   allowlisted Zone 3 endpoints only           │
├────────────────────────────────────────┼───────────────────────────────────────────────┤
│ ZONE 3: TARGET FINANCIAL MAIN FRAME    │ ZONE 4: OFFLINE AUDITOR STATION               │
│ (Settlement Domain)                    │ (Zero-Egress Verification Domain)             │
│                                        │                                               │
│ • Production Core Banking APIs         │ • Air-gapped forensic workstation             │
│ • SEPA / SWIFT / Stripe / Adyen Gateways│ • Standalone CLI: Java 21 / Python 3 / WASM  │
│ • Mandatory Status Reconciliation API  │ • Pinned Operator Ed25519 Public Key          │
│ • Network Policy:                      │ • Network Policy: Strictly disconnected       │
│   - Ingress permitted strictly from    │   (`connect-src 'none'`)                      │
│     static Zone 2 Gateway IPs          │ • Zero dependency on live JVM or cloud APIs   │
└────────────────────────────────────────┴───────────────────────────────────────────────┘
```

### Trust Boundary Interface Definitions:

| Boundary Interface | Source $\to$ Destination | Protocol & Data Exchange | Applied Defenses & Governance Invariants |
| :--- | :--- | :--- | :--- |
| **Boundary A (Admission)** | Zone 1 $\to$ Zone 2 | Local JSON-RPC / MCP `tools/call` over stdio or loopback socket. | Ingests unverified agent proposals. Station 0 strips ephemeral reasoning keys (`_reasoning`, `chain_of_thought`), normalizes UTF-8 JSON via RFC 8785 JCS, and scans for unredacted PII/IBAN patterns fail-closed. |
| **Boundary B (Dispatch Interlock)** | Zone 2 Internal | Memory-mapped inter-station transfer (`CandidateAction` $\to$ `ExecutionTicket`). | Enforces single-use ticket evaluation. Verifies policy epoch freshness, target URI allowlisting, and parameter spend limits. Signs `EO-1` pre-dispatch intent to persistent journal before allocating network buffer. |
| **Boundary C (Wire Egress)** | Zone 2 $\to$ Zone 3 | TLS 1.3 / HTTPS POST to mutating payment endpoints. | Injects deterministic `Idempotency-Key: <CAID>`. Traps socket drops, TCP RST, and HTTP 504 timeouts. Immediately latches `EFFECT_INDETERMINATE` with `retry_safe: false` to suppress uncoordinated client retries. |
| **Boundary D (Reconciliation)** | Zone 2 $\to$ Zone 3 | TLS 1.3 / HTTPS GET to primary status endpoint. | Restricts status queries to strict `ProbeBudget: 1`. Queries target transaction identity (`operationId`, `caid`) out-of-band to establish whether mutation committed. Resolves to `CONFIRMED`, `REFUTED`, or `PRESERVED_UNCERTAINTY`. |
| **Boundary E (Audit Export)** | Zone 2 $\to$ Zone 4 | Detached file export (`.json` receipt streams / `.csv` ledger dumps). | Transports cryptographic receipts containing Base64-encoded canonical RFC 8785 bytes, Ed25519 signatures, and monotonic SHA-256 hash chains. Verified offline without ambient credentials or network egress. |

---

## 5. Asset & Adversary Register

### 5.1 Asset Register

| Asset ID | Asset Name | Description & Security Sensitivity | Integrity / Confidentiality Model |
| :--- | :--- | :--- | :--- |
| **AST-01** | **Ed25519 Ledger Private Key** | Used by Station 3 to sign `ContinuityReceipt` records and pre-dispatch intent logs. | High Confidentiality / High Integrity. Stored in hardware HSM, KMS enclave, or memory-locked vault; strictly non-exportable. |
| **AST-02** | **Authority Ticket Private Key** | Used by human risk officers and policy engines to sign `DispatchAuthorizationTicket` and `HumanStepUpAssertion` tokens. | High Confidentiality / High Integrity. Maintained out-of-band from agent execution memory. |
| **AST-03** | **Continuous Hash Chain Tip** | Monotonic 32-byte SHA-256 state linking every operational receipt sequentially back to genesis. | Public Readability / Tamper-Evident Append-Only Integrity. Any mutation or truncation breaks downstream chain verification. |
| **AST-04** | **Candidate Action ID (CAID)** | 64-hex character SHA-256 digest computed over RFC 8785 canonical bytes of the mutating request. | Collision-Resistant Public Identifier. Serves as the deterministic idempotency anchor across Zone 1, 2, and 3. |
| **AST-05** | **Customer Ledger Balance & Funds** | Fiat currency balances in corporate bank accounts subject to agent disbursement authority. | Critical Financial Integrity. Protected against unauthorized debit, duplicate disbursement, or limit circumvention. |
| **AST-06** | **Customer Financial Identifiers** | Sensitive customer data including IBANs, PANs, SWIFT BICs, and personal names. | High Confidentiality. Redacted in-memory; prevented from leaking into audit receipts or external logging platforms. |

---

### 5.2 Adversary Taxonomy

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                ADVERSARY TAXONOMY                                      │
├──────────────────────┬──────────────────────────────────┬──────────────────────────────┤
│ ADVERSARY PROFILE    │ CAPABILITIES & ASSUMED ACCESS    │ TARGETED ATTACK VECTORS      │
├──────────────────────┼──────────────────────────────────┼──────────────────────────────┤
│ ADV-01: Malicious /  │ Crafts adversarial prompts,      │ • Indirect prompt injection  │
│ Drifting LLM Agent   │ manipulates context windows,     │ • Hallucinated spend amounts │
│                      │ leaks reasoning into wire calls. │ • TOCTOU parameter drift     │
├──────────────────────┼──────────────────────────────────┼──────────────────────────────┤
│ ADV-02: Adversarial  │ Injects mid-stream TCP resets,   │ • Post-commit timeout drop   │
│ Network Transport    │ drops HTTP response packets,     │ • Blind retry stampede       │
│                      │ delays ACKs to trigger timeouts. │ • Duplicate disbursements    │
├──────────────────────┼──────────────────────────────────┼──────────────────────────────┤
│ ADV-03: Host Failure │ Sudden kernel panic, hardware    │ • Mid-syscall execution loss │
│ or Power Loss        │ reset, or out-of-memory kill     │ • Unrecorded wire mutation   │
│                      │ during socket write syscall.     │ • Phantom payment generation │
├──────────────────────┼──────────────────────────────────┼──────────────────────────────┤
│ ADV-04: Sub-Agent    │ Proxies tasks across delegation  │ • Multi-hop scope inflation  │
│ Delegation Attacker  │ trees; attempts confused deputy  │ • Spend ceiling bypass       │
│                      │ attacks across agent boundaries. │ • Audience substitution      │
├──────────────────────┼──────────────────────────────────┼──────────────────────────────┤
│ ADV-05: Contradictory│ Upstream target reports false or │ • Specification gaming       │
│ Target Status Oracle │ delayed state, or read replica   │ • Phantom confirmation       │
│                      │ provides stale transaction data. │ • DoS probe amplification    │
└──────────────────────┴──────────────────────────────────┴──────────────────────────────┘
```

---

### 5.3 Threat Vectors & Wire Gate Mitigations Matrix

| Threat Vector | Root Cause Mechanism | AEIB Wire Gate Mitigation | Test Vector & Verification Evidence |
| :--- | :--- | :--- | :--- |
| **Prompt Injection Parameter Tampering** | Attacker injects instructions into dispute context, altering payment amount or recipient IBAN. | `ForkAndFlushContextBoundary` strips natural-language reasoning. Station 1 evaluates `StandingPredicate` against static allowlists and burns ticket. | `test_04_target_allowlist_violation_rejected` |
| **TOCTOU Action Mutation** | Agent modifies payload parameters between authorization evaluation and socket dispatch. | `DecisionToDispatchAuthorityGate`: Re-computes SHA-256 over exact wire payload bytes; asserts `actionDigest == sha256:CAID(wire_bytes)`. | `test_priority_p0_decision_to_dispatch_authority_ticket_gate` |
| **Blind Retry Duplicate Spend** | HTTP 504 timeout occurs post-commit; naive SDK initiates automated retries. | Wire fault interlock catches socket exception, latches `EFFECT_INDETERMINATE`, flags `retry_safe: false`, and blocks subsequent attempts. | `test_08_http_504_reconciles_to_confirmed_under_probe_budget_1` |
| **Mid-Syscall Process Crash** | Host crashes after bytes depart NIC but before logging completes. | `EO-1` Write-Before-Execute: Pre-dispatch intent is fsynced to disk prior to socket write. `recover_from_crash()` reconciles state upon restart. | `test_13_crash_recovery_resynchronization` |
| **Sub-Agent Privilege Inflation** | Intermediate agent delegates task to higher-privilege agent to bypass spend ceilings. | `DelegationAttenuationGate`: Enforces monotonic caveat narrowing ($\text{ChildScope} \subseteq \text{ParentScope}$) across delegation chains. | `test_gap8_cross_agent_delegation_chain_verification_and_scope_attenuation` |
| **Target Status Ambiguity & DoS** | Target status probe fails or returns inconsistent state across read replicas. | `Station2EffectReconciler`: Enforces `ProbeBudget: 1`. Preserves uncertainty fail-closed (`PRESERVED_UNCERTAINTY`) without triggering probe storms. | `test_10_target_status_outage_preserves_uncertainty_no_blind_retry` |
| **PII & IBAN Exposure in Receipts** | Financial audit logs expose personal identifiers, violating GDPR and PCI-DSS. | In-memory pattern scrubber flags raw IBANs/PANs; `Ed25519BbsSelectiveRedactor` enables salted SHA-256 field commitments for selective redaction. | `test_signal1_credential_vault_gate_opaque_ref_and_raw_secret_rejection` |

---

## 6. Action Authorization Model

The AEIB Action Authorization Model enforces that no mutating wire event occurs without deterministic, ex-ante mathematical authorization bound to the exact payload bytes.

### 6.1 Exact RFC 8785 JCS CAID Derivation

In distributed systems, JSON payloads with identical semantic meaning can produce divergent cryptographic hashes due to differences in key ordering, whitespace formatting, and floating-point representations. AEIB eliminates serialization ambiguity by enforcing strict **RFC 8785 (JSON Canonicalization Scheme — JCS)** normalization.

The **Candidate Action ID (CAID)** is formally defined as:
$$\text{CAID} = \text{SHA-256}(\text{RFC 8785 JCS}(\text{PurifiedCandidateAction}))$$

```python
# Reference Implementation: Canonical CAID Derivation
import hashlib
import json
from canonicaljson import encode_canonical_json  # RFC 8785 implementation

def compute_canonical_caid(purified_payload: dict) -> str:
    # 1. Serialize using RFC 8785 rules:
    #    - Keys sorted lexicographically by UTF-16 code units
    #    - No whitespace between tokens (: and ,)
    #    - Strict IEEE 754 float formatting
    canonical_bytes = encode_canonical_json(purified_payload)
    
    # 2. Derive 64-hex SHA-256 digest
    return hashlib.sha256(canonical_bytes).hexdigest()
```

Before socket transmission, Station 1 recomputes the SHA-256 digest over the outgoing socket buffer. If a single byte, whitespace character, or parameter value diverges from the authorized CAID, dispatch terminates fail-closed with `TOCTOU_PAYLOAD_MUTATION`.

---

### 6.2 Single-Use Ticket Burn Architecture

To prevent replay attacks and race conditions, authorization is granted via a cryptographically sealed, single-use `DispatchAuthorizationTicket`:

```json
{
  "decisionId": "dec_9a4f2c018b3e",
  "operationId": "op_refund_cust_101",
  "principalId": "did:key:z6MkpTHRexample",
  "targetIdentity": "https://api.bank.internal/v1/payments/refunds",
  "actionDigest": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "policyEpoch": 1,
  "manifestDigest": "sha256:4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
  "expiresAt": 1774000300,
  "singleUse": true,
  "signatureHex": "4a7b3c...64_byte_ed25519_hex..."
}
```

#### Ticket Evaluation Invariants:
1. **Single-Use Replay Check:** Station 1 maintains a concurrent, thread-safe set of consumed decision identifiers (`burnedDecisions`). If `ticket.decisionId` is already present, the ticket is rejected immediately as `REPLAY_DETECTED`.
2. **Expiration Enforcement:** The ticket is evaluated against host time ($T_{\text{eval}} \le \text{expiresAt}$). Default validity window is configured to 300 seconds.
3. **Epoch Alignment:** The ticket's `policyEpoch` must match the active operational epoch of the AEIB boundary.
4. **Target Identity Pinning:** The requested target URL must match `ticket.targetIdentity` bit-for-bit.
5. **Cryptographic Signature Verification:** The Ed25519 signature over the canonical statement of the ticket is verified against the operator authority public key.
6. **Atomic Burn:** Upon passing all checks, `ticket.decisionId` is committed to `burnedDecisions` prior to releasing socket write locks.

---

### 6.3 Standing Predicate Evaluation

The `StandingPredicate` is a pure boolean function:
$$f(\text{PurifiedPayload}, \text{OperationalPolicy}) \to \{\text{True}, \text{False}\}$$

It evaluates hard policy constraints:
* `target_uri` must exist within the static `allowed_targets` list.
* `amount_cents` must be a non-negative integer.
* `amount_cents` must not exceed `max_amount_cents_limit` (configured spend ceiling).
* Required schema fields must be present and type-conformant.

Natural-language justifications or persuasive context generated by the LLM are stripped prior to evaluation. Prose cannot alter the boolean standing verdict.

---

## 7. Retention, Redaction & The "Dead Salmons" Filter Policy

### 7.1 The "Dead Salmons" Filter: Stripping Ephemeral Reasoning

In 2009, neuroimaging researchers (Bennett et al.) conducted an fMRI study on a dead Atlantic salmon. By applying standard, uncorrected statistical tests to random MRI noise, they observed statistically significant "brain activity" in the deceased fish. The study demonstrated the hazard of **multiple-comparisons false positives and unconstrained post-hoc rationalization**.

In autonomous AI systems, an analogous phenomenon occurs: **The LLM Rationalization Trap**. When prompted or operating under optimization pressure, LLMs routinely generate articulate, convincing rationales explaining why a high-risk or policy-violating action is necessary. 

If governance systems ingest natural-language explanations into cryptographic hashes or policy evaluation engines:
1. Adversarial instructions hidden within reasoning fields pollute the cryptographic digest.
2. Attackers can execute prompt injections that bypass rule filters by framing malicious actions as emergency overrides.
3. Hash consistency breaks across reasoning iterations because LLM chain-of-thought outputs are inherently non-deterministic.

AEIB enforces the **Dead Salmons Filter Policy** via `ForkAndFlushContextBoundary`. At Station 0, the boundary recursively purges all ephemeral reasoning keys from the candidate action payload:

```python
EPHEMERAL_REASONING_FIELDS = {
    "_reasoning",
    "chain_of_thought",
    "rationale",
    "explanation",
    "thought_process",
    "internal_monologue"
}
```

Only the purified parameter tree (the actual wire parameters that will be written to the network socket) is admitted into RFC 8785 JCS canonicalization and CAID derivation.

---

### 7.2 In-Memory PII & Financial Identifier Sanitization

Financial audit receipts must comply with data protection regulations (GDPR Article 5(1)(c) Data Minimisation, Article 17 Right to Erasure, and PCI-DSS Requirement 3.4). Transmitting raw International Bank Account Numbers (IBANs) or cardholder Primary Account Numbers (PANs) in persistent ledger receipts creates substantial compliance exposure.

AEIB enforces **In-Memory Sanitization** prior to receipt minting:
1. **Regex Pattern Scanners:** Outgoing payloads are evaluated against strict regex filters:
   * **IBAN Filter:** `\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b`
   * **PAN / Credit Card Filter:** Luhn-validated 13-19 digit numeric patterns.
   * **Credential Token Filter:** `Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*`
2. **Fail-Closed Violation Latch:** If an unapproved payload contains unredacted raw credentials or cleartext account numbers where opaque handles were expected, Station 0 halts dispatch with `UNREDACTED_IBAN` or `RAW_BEARER_TOKEN`.
3. **Selective Redaction via Salted SHA-256 Commitments (`Ed25519BbsSelectiveRedactor` Prototype):**
   * Sensitive fields ($k_i, v_i$) are committed as salted SHA-256 digests:
     $$C_i = \text{SHA-256}(\text{salt}_i \parallel \text{RFC8785}(k_i) \parallel \text{RFC8785}(v_i))$$
   * Station 3 signs the root commitment tree.
   * When sharing receipts with external auditors or supervisory authorities, sensitive fields (e.g., `user_iban`, `customer_email`) can be fully redacted by withholding the raw value and salt. The auditor verifies the presence and integrity of the redacted field within the root signature without learning the cleartext personal data.

---

## 8. Human-Approval Model (STEP_UP / Dual-Control)

Autonomous agency must be bounded by financial risk parameters. AEIB implements a multi-tiered authorization and escalation hierarchy governed by the **Four-Eyes Principle (Dual-Control)**.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        FINANCIAL ACTION ESCALATION LATTICE                             │
├───────────────────┬──────────────────────────┬─────────────────────────────────────────┤
│ TRANSACTION TIER  │ NOTIONAL THRESHOLD       │ REQUIRED GOVERNANCE DISPOSITION         │
├───────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ Tier 1: Micro     │ Amount <= EUR 500        │ Automated Single-Use Ticket Burn        │
│                   │ (Within operational cap) │ (Autonomous dispatch under active epoch)│
├───────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ Tier 2: Elevated  │ EUR 500 < Amount <= 5000 │ Single Human Risk Officer Step-Up       │
│                   │                          │ (RFC 9470 CIBA Push / WebAuthn Sign)    │
├───────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ Tier 3: High-Value│ Amount > EUR 5000        │ Mandatory Dual-Control (Maker-Checker)  │
│                   │ OR Out-of-Grant Target   │ (Two independent cryptographic permits) │
└───────────────────┴──────────────────────────┴─────────────────────────────────────────┘
```

### 8.1 The Cross-App Step-Up Escalation Protocol

When an agent proposes an action that breaches its configured spending ceiling (e.g., attempting a refund of €15,000 against a €5,000 autonomous limit), Station 1 halts execution with `STEP_UP_REQUIRED`.

Execution cannot proceed until a human approver submits a cryptographically signed `HumanStepUpAssertion` adhering to RFC 9470 (OAuth 2.0 Step-Up Authentication) and OpenID Client-Initiated Backchannel Authentication (CIBA):

```json
{
  "assertionType": "HUMAN_STEP_UP_ASSERTION",
  "version": "1.0",
  "statement": {
    "actionCaid": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "sourceApp": "agent://support-refund-service",
    "targetApp": "banking://core-settlement-engine",
    "acrLevel": "urn:sovereign:acr:hardware-token:dual-control",
    "challengeNonce": "nonce_7f1c9a4b2e8d",
    "approverPrincipal": "did:key:z6MkuSeniorRiskOfficer1",
    "decisionEpoch": 1,
    "issuedAt": 1774000000,
    "expiresAt": 1774000300
  },
  "signatureHex": "7c2d1a...64_byte_ed25519_signature..."
}
```

#### Step-Up Gate Verification Protocol (`CrossAppStepUpEscalationGate`):
1. **CAID Invariant:** The assertion's `actionCaid` must match the exact RFC 8785 JCS CAID of the pending candidate action.
2. **Authentication Context Class Reference (ACR):** The approver must authenticate using a certified hardware token (e.g., FIDO2 / WebAuthn) meeting the required ACR level.
3. **Time Window Gating:** Assertions outside the active approval window ($T_{\text{eval}} > \text{expiresAt}$) fail-closed with `STEP_UP_TIMEOUT`.
4. **Single-Use Challenge Nonce Burn:** The `challengeNonce` is burned in the boundary ledger; replaying a previously signed approval triggers `STEP_UP_REPLAY_BLOCKED`.
5. **Audit Evidence Minting:** Upon verification, the gate mints a signed `STEP_UP_AUDIT_RECEIPT` linking the human approver identity, the agent action CAID, and the resulting dispatch authorization.

---

## 9. Receipt Specification, Offline Verifier Instructions, and Test Vectors

The primary technical evidence artifact emitted by AEIB is the **ContinuityReceipt**.

### 9.1 ContinuityReceipt Schema Specification

The receipt consists of an envelope encapsulating metadata, a canonical statement, raw Base64-encoded canonical RFC 8785 bytes, and a 64-byte Ed25519 signature:

```json
{
  "version": "1.0",
  "hashAlgorithm": "SHA-256",
  "signatureAlgorithm": "Ed25519",
  "keyId": "key_aeib_station3_2026_01",
  "statement": {
    "actionCaid": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "chainTip": "0000000000000000000000000000000000000000000000000000000000000000",
    "effectDisposition": "CONFIRMED",
    "epoch": 1,
    "sequenceNumber": 1,
    "targetUri": "https://api.bank.internal/v1/payments/refunds",
    "timestampUtc": "2026-10-14T08:00:00.000Z"
  },
  "rawSignedStatement": "eyJhY3Rpb25DYWlkIjoiZTNiMGM0NDI5OGZjMWMxNDlhZmJmNGM4OTk2ZmI5MjQyN2FlNDFlNDY0OWI5MzRjYTQ5NTk5MWI3ODUyYjg1NSIsImNoYWluVGlwIjoiMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwIiwiZWZmZWN0RGlzcG9zaXRpb24iOiJDT05GSVJNRUQiLCJlcG9jaCI6MSwic2VxdWVuY2VOdW1iZXIiOjEsInRhcmdldFVyaSI6Imh0dHBzOi8vYXBpLmJhbmsuaW50ZXJuYWwvdjEvcGF5bWVudHMvcmVmdW5kcyIsInRpbWVzdGFtcFV0YyI6IjIwMjYtMTAtMTRUMDg6MDA6MDAuMDAwWiJ9",
  "signature": "MIGbMBAGByqGSM49AgEGBSuBBAAKA0IABExyXk...64_byte_ed25519_base64..."
}
```

---

### 9.2 Offline Verification Algorithm

The verification algorithm is deterministic, side-effect free, and executes in $\mathcal{O}(1)$ time. An offline verifier (implemented in Java, Python, Rust, or WASM) MUST execute the following four steps in exact order:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ OFFLINE VERIFIER EXECUTION SEQUENCE                                   │
├────────────────────────────────────────────────────────────────────────┤
│ 1. ALGORITHM GATING:                                                   │
│    • Assert envelope.hashAlgorithm == "SHA-256"                        │
│    • Assert envelope.signatureAlgorithm == "Ed25519"                   │
│    • IF UNSUPPORTED -> HALT(UNSUPPORTED_ALGORITHM)                     │
│                                                                        │
│ 2. CRYPTOGRAPHIC SIGNATURE CHECK:                                      │
│    • Decode envelope.signature (64 raw bytes)                          │
│    • Decode envelope.rawSignedStatement (raw canonical bytes)          │
│    • Verify Ed25519 signature over rawSignedStatement using caller-    │
│      supplied public key for envelope.keyId                            │
│    • IF INVALID -> HALT(INVALID_SIGNATURE)                             │
│                                                                        │
│ 3. STRUCTURAL CANONICALIZATION & DIGEST CHECK:                         │
│    • Re-serialize envelope.statement using RFC 8785 JCS into           │
│      recomputedCanonicalBytes                                          │
│    • Assert rawSignedStatement == recomputedCanonicalBytes             │
│    • IF UNEQUAL -> HALT(PAYLOAD_DIGEST_MISMATCH)                       │
│                                                                        │
│ 4. MONOTONIC HASH CHAIN CONTINUITY:                                    │
│    • Compute priorHash = SHA-256(raw_bytes_of_prior_receipt_envelope)  │
│    • Assert envelope.statement.chainTip == priorHash                   │
│    • IF UNEQUAL -> HALT(CHAIN_TIP_BROKEN)                             │
│                                                                        │
│ RETURN: VERIFIED (Exit Code 0)                                         │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 9.3 Offline Verifier CLI Instructions

AEIB receipts can be verified without network connectivity across three distinct runtimes:

#### A. Java 21 Standalone Verifier (`aeib-verifier.jar`)
```bash
# Verify single receipt against pinned public key
java -jar bin/aeib-verifier.jar \
  --receipt receipts/refund_001.json \
  --public-key keys/station3_pub.hex

# Verify full sequential ledger chain
java -jar bin/aeib-verifier.jar \
  --chain-dir receipts/epoch_1/ \
  --public-key keys/station3_pub.hex
```

#### B. Python 3 Reference Verifier (`aeib_verify.py`)
```bash
python3 aeib_verify.py \
  --receipt receipts/refund_001.json \
  --public-key keys/station3_pub.hex \
  --strict-jcs
```

#### C. Air-Gapped Browser WASM Verifier (`smaos-verify.html`)
1. Open `smaos-verify.html` in any modern web browser (Firefox, Chromium, Safari).
2. The browser operates under a strict Content Security Policy (`connect-src 'none'`), prohibiting outbound network traffic.
3. Drag and drop the `.json` receipt stream and the operator public key. The embedded WASM module (`ed25519-dalek`) verifies signature validity and chain continuity locally.

---

### 9.4 Concrete Test Vectors

The test suite evaluates 4 core receipt vectors to establish falsifiable verification evidence:

#### Test Vector 1: Nominal Customer Refund Receipt (`TV-01`)
* **Input Payload:** `{"amount_cents": 15000, "currency": "EUR", "payment_id": "pay_505"}`
* **Computed CAID:** `6c1000b080058b73ad6b5cb5d9ad8b2f909dcfe4c64b5840d829141f23fe7f86`
* **Statement Bytes (RFC 8785 JCS):**
  `{"actionCaid":"6c1000b080058b73ad6b5cb5d9ad8b2f909dcfe4c64b5840d829141f23fe7f86","chainTip":"0000000000000000000000000000000000000000000000000000000000000000","effectDisposition":"CONFIRMED","epoch":1,"sequenceNumber":1,"targetUri":"https://api.bank.internal/v1/payments/refunds","timestampUtc":"2026-10-14T08:00:00.000Z"}`
* **Expected Verifier Exit Code:** `0` (`VERIFIED`)

#### Test Vector 2: Reconciled Wire Ambiguity Receipt (`TV-02`)
* **Input Condition:** Socket drops via `TCP RST` after wire bytes depart NIC. Out-of-band probe to `/v1/payments/status` returns `{status: "SETTLED"}` under `ProbeBudget: 1`.
* **Effect Disposition:** `CONFIRMED`
* **Receipt Flag:** `reconciliation_attempts: 1`, `retry_safe: false`
* **Expected Verifier Exit Code:** `0` (`VERIFIED`)

#### Test Vector 3: Tampered Action Digest (`TV-03-NEG`)
* **Attack Modification:** Attacker modifies `envelope.statement.actionCaid` from `6c10...` to `ffff...`.
* **Observed Outcome:** Re-canonicalization digest mismatch.
* **Expected Verifier Exit Code:** `2` (`PAYLOAD_DIGEST_MISMATCH`)

#### Test Vector 4: Broken Hash Chain Linkage (`TV-04-NEG`)
* **Attack Modification:** Attacker deletes receipt sequence number 2 from the epoch folder.
* **Observed Outcome:** `receipt[3].statement.chainTip != SHA-256(receipt[1])`.
* **Expected Verifier Exit Code:** `4` (`CHAIN_TIP_BROKEN`)

---

## 10. Incident, Reconciliation & Recovery Workflow

In banking networks, transport uncertainty is a physical certainty. Network partitions, firewall timeouts, load balancer resets, and core banking batch locks routinely sever active TCP sockets.

### 10.1 The 3 Financial Ambiguity Rules

AEIB strictly operationalizes three invariant rules upon encountering transport failure:

1. **Rule 1: Content-Addressed Idempotency Key:** Every mutating call carries an `Idempotency-Key` equal to the canonical payload CAID.
2. **Rule 2: Blind Retries Strictly Forbidden:** If a connection fails mid-flight, automated retries are blocked immediately. The state is latched to `EFFECT_INDETERMINATE`.
3. **Rule 3: Single-Attempt Primary Status Reconciliation:** AEIB initiates an out-of-band status query under a strict `ProbeBudget: 1`.

```text
┌────────────────────────────────────────────────────────────────────────┐
│ TRANSPORT FAULT RESOLUTION WORKFLOW                                    │
├────────────────────────────────────────────────────────────────────────┤
│ Wire Dispatch: POST /v1/payments/refunds (Idempotency-Key: CAID)      │
│                                │                                       │
│                                ▼                                       │
│              [HTTP 504 Timeout or TCP RST Injected]                    │
│                                │                                       │
│                                ▼                                       │
│          Latch State: EFFECT_INDETERMINATE (retry_safe: false)         │
│          Enforce ProbeBudget: 1                                        │
│                                │                                       │
│                                ▼                                       │
│          TargetStatusClient: GET /v1/payments/status?caid=CAID         │
│                                │                                       │
│        ┌───────────────────────┼───────────────────────┐               │
│        ▼                       ▼                       ▼               │
│ [Status: COMMITTED]    [Status: NOT_FOUND]     [Probe Times Out / 500] │
│        │                       │                       │               │
│        ▼                       ▼                       ▼               │
│ Update Disposition:    Update Disposition:     Preserve Uncertainty:   │
│ CONFIRMED              REFUTED                 PRESERVED_UNCERTAINTY   │
│ Emit RESOLUTION_RECEIPT Permit Safe Retry      Halt & Push Alert to    │
│ Downstream Commit = 1  Downstream Commit = 0   Human Risk Dashboard    │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 10.2 Crash Recovery Playbook (`recover_from_crash`)

If an AEIB gateway host experiences unexpected power loss or kernel termination:
1. **Pre-Dispatch Journal Scan:** Upon restart, Station 1 scans the persistent journal for operations recorded in the `INTENT_COMMITTED` state that lack a terminal `ContinuityReceipt`.
2. **Authoritative Reconciliation:** For each pending operation, Station 2 queries the customer-provided `TargetStatusClient` using the recorded CAID and operation ID.
3. **Terminal Resynchronization:**
   * If the target confirms execution, Station 3 commits a `CONFIRMED` receipt.
   * If the target reports the transaction never existed, Station 3 commits a `REFUTED` receipt.
   * If the target remains unreachable, the operation is locked in `PRESERVED_UNCERTAINTY` and routed to the manual operations console.

---

## 11. Deployment Assumptions and Residual Risks

To preserve epistemic honesty, the technical boundaries of AEIB must be clearly documented:

1. **Host Operating System Integrity:** AEIB assumes the integrity of the underlying host kernel, memory space, and hypervisor. If an adversary achieves Ring 0 root execution on the host running AEIB, they can inspect runtime memory. Hardware attestation (TDX/SEV) and eBPF LSM filtering remain **structural scaffolding** per `AGENTS.md` §5 and are not active CI-enforced controls on standard Linux hosts.
2. **Customer Target Status Endpoint Requirement:** AEIB reconciliation relies on the customer operating an authenticated target-side status query endpoint (`GET /status?caid=...`) capable of querying settlement status by idempotency key. If a downstream banking target executes mutations non-deterministically without idempotency support, AEIB preserves `EFFECT_INDETERMINATE` and halts.
3. **Ledger Key Custody:** A local hash chain signed by an operator key detects post-hoc tampering, but cannot prevent a compromised operator who holds the private signing key from signing an alternate forked chain. High-assurance deployments must isolate the Ed25519 signing key inside an HSM or KMS, and anchor periodic hash tips using RFC 3161 Trusted Timestamping or multi-party witness co-signing.
4. **Saga Compensation Model:** The AEIB saga compensator provides **eventual consistency** via asynchronous message queues. It does not provide atomic, distributed Two-Phase Commit (2PC) rollback across external banking providers.

---

## 12. EU AI Act Evidence Mapping

The European Union Artificial Intelligence Act (Regulation (EU) 2024/1689) imposes strict technical requirements on High-Risk AI Systems (Annex III), including AI deployed in credit evaluation, insurance underwriting, and critical infrastructure.

> **Epistemic Notice:** AEIB does not by itself confer statutory compliance with the EU AI Act. It generates technical, cryptographic, and operational evidence that deployers can submit to notified bodies, auditors, and national competent authorities to support compliance assessments under Articles 12, 14, and 15.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                            EU AI ACT EVIDENCE MAPPING                                  │
├─────────────────────┬─────────────────────────────────┬────────────────────────────────┤
│ STATUTORY ARTICLE   │ REGULATORY REQUIREMENT          │ AEIB TECHNICAL EVIDENCE        │
├─────────────────────┼─────────────────────────────────┼────────────────────────────────┤
│ **Article 12**      │ High-risk AI systems shall      │ • Monotonic SHA-256 hash-chain │
│ (Record-Keeping &   │ technically allow for the       │   receipts emitted by St. 3    │
│ Traceability)       │ automatic recording of events   │ • Binds action CAID, epoch,    │
│                     │ ('logs') over their lifecycle.  │   target URI, and disposition  │
│                     │ Ensuring traceability of system │ • Standalone offline verifier  │
│                     │ decisions and execution states. │   detects tampering or omission│
├─────────────────────┼─────────────────────────────────┼────────────────────────────────┤
│ **Article 14**      │ High-risk AI systems shall be   │ • STEP_UP dual-control gates   │
│ (Human Oversight)   │ designed to enable natural      │   halt high-value disbursements│
│                     │ persons to oversee execution,   │ • Hardware-backed CIBA / FIDO2 │
│                     │ intervene, override decisions,  │   human assertion verification │
│                     │ or trigger an emergency halt.   │ • Andon cord emergency freeze  │
│                     │                                 │ • Ambiguity latching prevents  │
│                     │                                 │   machine-speed runaway loops  │
├─────────────────────┼─────────────────────────────────┼────────────────────────────────┤
│ **Article 15**      │ Systems shall achieve resilience│ • Out-of-band wire gateway     │
│ (Accuracy,          │ against errors, faults, and     │   segregates untrusted model   │
│ Robustness &        │ adversarial manipulation        │ • "Dead Salmons" filter strips │
│ Cybersecurity)      │ (prompt injection, tool abuse,  │   injected reasoning strings   │
│                     │ network transport drops).       │ • TOCTOU action ticket burn    │
│                     │                                 │ • Wire fault interlock blocks  │
│                     │                                 │   blind retry stampedes        │
└─────────────────────┴─────────────────────────────────┴────────────────────────────────┘
```

---

## 13. DORA (Digital Operational Resilience Act) Evidence Mapping

The Digital Operational Resilience Act (Regulation (EU) 2022/2554) and its accompanying Regulatory Technical Standards (RTS 2024/1772) mandate rigorous ICT risk management, major incident reporting, and third-party vendor oversight for financial entities across the European Union.

> **Epistemic Notice:** AEIB does not by itself confer statutory compliance with DORA. AEIB generates machine-readable incident classification dossiers, forensic execution timelines, and vendor information register entries that support the financial entity's operational resilience program.

### 13.1 DORA Article 17: Incident Classification & Timeline Reconstruction

Under RTS 2024/1772 Article 17, financial entities must classify ICT-related incidents according to quantitative impact criteria (transactions affected, financial loss, data integrity breach) and submit an initial notification within **4 hours** of classifying a major incident.

When an autonomous agent encounters a severed network connection during a transaction, naive retry loops hide the failure or trigger double spending. AEIB immediately classifies the incident and exports a structured audit dossier:

```json
{
  "dora_rts_classification": "4h_major_incident",
  "incident_category": "INTEGRITY_AND_AVAILABILITY_AMBIGUITY",
  "incidents": [
    {
      "incidentId": "INC-AEIB-2026-0881",
      "operationId": "op_refund_cust_101",
      "actionCaid": "6c1000b080058b73ad6b5cb5d9ad8b2f909dcfe4c64b5840d829141f23fe7f86",
      "payloadScrubbed": "EUR 150.00 to [REDACTED_IBAN]",
      "wireStatus": 504,
      "sdkClaim": "CONFIRMED",
      "enforcedDisposition": "EFFECT_INDETERMINATE",
      "reconciliationAttempted": true,
      "flag": "VERIFIED_TRANSPORT_AMBIGUITY"
    }
  ],
  "telemetrySource": "aeib_wire_gateway_station2",
  "pciDssSanitization": "ACTIVE_ZERO_EGRESS",
  "timeline": [
    {"timestamp": "2026-10-14T08:00:00.012Z", "event": "EO_1_INTENT_COMMITTED"},
    {"timestamp": "2026-10-14T08:00:00.015Z", "event": "SOCKET_DISPATCH_INITIATED"},
    {"timestamp": "2026-10-14T08:00:05.018Z", "event": "TRANSPORT_TIMEOUT_HTTP_504"},
    {"timestamp": "2026-10-14T08:00:05.020Z", "event": "LATCH_EFFECT_INDETERMINATE"},
    {"timestamp": "2026-10-14T08:00:05.105Z", "event": "PROBE_BUDGET_1_DISPATCHED"}
  ]
}
```

---

### 13.2 DORA Article 28(3): Information Register Candidate Export (`RT.01.03`)

Under DORA Article 28(3), financial entities must maintain an updated Register of Information regarding all contractual arrangements on the use of ICT third-party services. The European Supervisory Authorities (EBA, EIOPA, ESMA) require standardized xBRL-CSV templates (`RT.01.01` through `RT.01.03`).

AEIB includes an automated exporter (`DoraIts2024ZipExporter`) generating candidate `RT.01.03` ICT vendor registry rows certifying fail-closed operational exit capabilities:

```csv
ContractRef,ProviderName,ICTServiceType,Criticality,ExitStrategy,DisasterRecoveryTested
CTR-SMAOS-001,SovereignNexus,S17,Critical,Documented_FailClosed_WireInterlock,Verified_2026_10_14
```

* **ICT Service Type `S17`:** Automated execution gateway and transaction integrity monitoring.
* **Exit Strategy:** Formally documented fail-closed interlock suppressing uncoordinated traffic upon network severance.

---

## 14. Pilot Delivery Scope: 30–60 Day Observe-Only Financial Boundary Pilot

To allow financial institutions, compliance officers, and risk committees to evaluate AEIB without disrupting production payment pipelines, SovereignNexus offers a structured **30–60 Day Observe-Only Financial Boundary Pilot**.

### 14.1 Operational Architecture: "Shadow Mode" Boundary

During the pilot, AEIB operates in **Passive Tap & Evaluation Mode (Observe-Only)**:
* AEIB is deployed adjacent to an existing customer refund, disbursement, or customer support agent workflow.
* Agent tool invocations are mirrored or proxied through AEIB in observe-only posture.
* AEIB executes Station 0 sanitization, derives CAID hashes, and evaluates policy epochs and spend ceilings without blocking production traffic.
* In synthetic staging environments, fault-injection harnesses evaluate AEIB's resilience against injected HTTP 504 timeouts, TCP resets, and prompt injections.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             PILOT DELIVERY TIMELINE                                    │
├─────────────┬──────────────────────────┬───────────────────────────────────────────────┤
│ PHASE       │ DURATION & FOCUS         │ MILESTONE OBJECTIVES & DELIVERABLES           │
├─────────────┼──────────────────────────┼───────────────────────────────────────────────┤
│ **Phase 1** │ **Days 1–15**            │ • Environment discovery & network topology map│
│             │ Architectural Setup &    │ • Deploy AEIB in Zone 2 shadow container      │
│             │ Shadow Scaffolding       │ • Configure Dead Salmons filter & PII regexes │
│             │                          │ • Establish baseline latency benchmarking     │
├─────────────┼──────────────────────────┼───────────────────────────────────────────────┤
│ **Phase 2** │ **Days 16–30**           │ • Deploy synthetic fault-injection harness    │
│             │ Fault Injection &        │ • Inject 500 simulated HTTP 504 / TCP RSTs    │
│             │ Bounded Reconciliation   │ • Calibrate `ProbeBudget: 1` status probe     │
│             │                          │ • Evaluate zero duplicate commit verification │
├─────────────┼──────────────────────────┼───────────────────────────────────────────────┤
│ **Phase 3** │ **Days 31–45**           │ • Configure financial spend ceiling thresholds│
│             │ Spend Ceilings &         │ • Implement RFC 9470 CIBA human step-up flows │
│             │ Dual-Control Evaluation  │ • Test single-use nonce burn & replay defense │
│             │                          │ • Verify risk officer approval UX & latency   │
├─────────────┼──────────────────────────┼───────────────────────────────────────────────┤
│ **Phase 4** │ **Days 46–60**           │ • Ingest 10,000 live shadow transactions      │
│             │ Audit Dossier &          │ • Execute air-gapped verification in Zone 4   │
│             │ Compliance Pack Handover │ • Generate DORA Article 17 gap reports        │
│             │                          │ • Deliver final Compliance Evidence Dossier   │
└─────────────┴──────────────────────────┴───────────────────────────────────────────────┘
```

---

### 14.2 Pilot Prerequisites & Customer Requirements

To execute the pilot, the customer provides:
1. **Isolated Execution Environment:** A containerized Linux instance (x86_64 or ARM64, 4 vCPU, 8 GB RAM) for Zone 2 gateway hosting.
2. **Target Status Reconciliation Endpoint:** An authenticated test endpoint on the target payment system capable of querying transaction state by `operationId` or `Idempotency-Key` (CAID).
3. **Designated Risk Officers:** 1–2 risk or compliance team members to participate in Phase 3 human step-up evaluation.

---

### 14.3 Pilot Success & Acceptance Gates

The pilot is evaluated against four objective, test-verified acceptance criteria:

1. **Gate 1: Zero Duplicate Disbursements:** Under 500 injected post-dispatch transport drops (`HTTP 504` / `TCP RST`), AEIB must demonstrate zero duplicate transactions committed downstream.
2. **Gate 2: Microsecond-Scale Wire Latency:** Under standard operation, the added dispatch latency introduced by Stations 0, 1, and 3 must not exceed $p95 \le 1.5\text{ ms}$.
3. **Gate 3: Cross-Language Offline Verifier Parity:** All evaluated receipts emitted during the pilot must achieve bit-exact verification parity across the standalone Java 21 CLI, the Python 3 reference script, and the air-gapped browser WASM verifier.
4. **Gate 4: Automated DORA Incident Export:** All simulated transport failures must be classified according to DORA RTS criteria and exported as valid machine-readable incident dossiers (`dora_art17_gap_report.json`).

---

### 14.4 Formal Exit Criteria

Upon completion of Phase 4, the pilot concludes with:
* Delivery of the complete, signed cryptographic receipt ledger covering all pilot episodes.
* Delivery of the customer-tailored DORA Article 17 / Article 28(3) and EU AI Act Article 12, 14, 15 compliance evidence mapping.
* Executive presentation to the customer's Chief Information Security Officer (CISO), Chief Risk Officer (CRO), and Internal Audit Committee.
* Optional transition path to active inline enforcement mode under institutional software licensing.

---

**SovereignNexus Research & Architecture Working Group**  
*Verification Scripts & Test Suites:* `tests/test_governed_financial_action_boundary.py`  
*Cryptographic Core:* `FOUR_STATION_INTERFACES.java` / `unified_governance_stack.py`  
*Formal Threat Model:* `docs/AEIB_FORMAL_THREAT_MODEL_v1.1.md`  
*Continuity Receipt Spec:* `docs/AEIB-RECEIPT-SPEC.md`
