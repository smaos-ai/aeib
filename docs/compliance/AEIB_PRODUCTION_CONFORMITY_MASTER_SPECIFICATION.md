# AEIB Production Execution & Conformity Master Specification
**Standardized Technical Evidence, Architectural Invariants, and Calibrated EU Regulatory Crosswalk**

```text
Document Version : 1.1.0-rc.1
Release Baseline : v1.0.0-rc.3 (Locked) / Track B v1.1 Sequence
Status           : Locked Architectural & Regulatory Specification
Working Branch   : feat/v1.1-temporal-standing
Last Updated     : 2026-10-15
Epistemic Notice : Evaluated under the stated model. AEIB sells technical execution
                   evidence, not legal certification.
```

---

## Executive Summary & Epistemic Notice

> **Mandatory Buyer-Facing & Regulatory Notice (AGENTS.md §1 & §5)**:
> AEIB produces verifiable technical evidence that may support a deployer's AI governance, risk management, and operational resilience filings under the EU AI Act (Regulation (EU) 2024/1689 as amended by Regulation (EU) 2026/1744) and DORA (Regulation (EU) 2022/2554). It does not by itself certify an AI system as compliant. Compliance is a deployer-level legal obligation requiring institutional quality management, human staffing, and authenticated target-side infrastructure. Under the stated model, all claims represent observed and evaluated properties backed by correlated cryptographic receipts and reproducible test vectors.

---

## Section 1: Locked Product Scope (AEIB v1.0 Core)

### 1.1 Bounded Operational Objective
AEIB delivers one governed, fail-closed execution boundary specifically engineered for consequential financial mutations (e.g., customer refunds, supplier payouts, credit adjustments). It provides deterministic interception between an agentic reasoning loop and external financial wire sockets.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   SECTION 1: LOCKED PRODUCT SCOPE (AEIB v1.0 CORE)                     │
├──────────────────────────┬─────────────────────────────────────────────────────────────┤
│ BOUNDED OBJECTIVE        │ Deliver one governed, fail-closed execution boundary        │
│                          │ for consequential financial mutations (refunds/payments).   │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ EXCLUDED SCOPE           │ No general policy language, identity provider, multi-tenant │
│                          │ SaaS control plane, or universal AI compliance platform.    │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ CTRL-01 INVARIANT        │ Evaluates canonical CandidateAction (CAID), principal,       │
│ (Exact Action Auth)      │ delegation scope, target URI, and active policy_epoch at Tn. │
│                          │ Rejects malformed and oversized payloads via RFC 8785 JCS.  │
└──────────────────────────┴─────────────────────────────────────────────────────────────┘
```

### 1.2 Core Production Controls (CTRL-01 through CTRL-07)

| Control ID | Core Control | Operational & Cryptographic Invariant | Definition of Done |
| :--- | :--- | :--- | :--- |
| **`CTRL-01`** | **Exact Action Authorization** | Evaluates canonical `CandidateAction` ($\text{CAID}$), principal, delegation scope, target URI, and active `policy_epoch` at $T_n$. | Versioned JSON schema; deterministic RFC 8785 JCS digest; malformed/oversized payload rejection. |
| **`CTRL-02`** | **Durable Dispatch Intent (EO-1)** | Persists and flushes (`fsync`) a signed `DISPATCH_INTENT` record to durable storage before allocating an external socket. | Process crash before, during, and after intent persistence recovers deterministically without unlogged mutations. |
| **`CTRL-03`** | **Persistent Single-Use Authority** | Consumes a single-use `DispatchAuthorizationTicket` atomically prior to external I/O. | Concurrent reuse, replay, expiration, and daemon restart tests confirm zero duplicate ticket execution (`AT34`). |
| **`CTRL-04`** | **Governed HTTP/MCP Executor** | Executes only the exact approved canonical payload against an allowlisted target endpoint. | Any drift between approved digest and wire payload aborts socket creation (`NOT_DISPATCHED`). |
| **`CTRL-05`** | **Uncertain-Outcome Latching** | Classifies post-dispatch transport failures (`HTTP 504`, `TCP RST`, timeout) as `EFFECT_INDETERMINATE` with `retry_safe: false`. | Station 2 Wire Latch blocks automated retries when transport state is ambiguous (`AT35`). |
| **`CTRL-06`** | **Bounded Target Reconciliation** | Queries authoritative target status using a versioned `TargetEvidenceContract` under a strict `ProbeBudget`. | Enforces per-operation probe ceilings; validates against `refund_status_v1.schema.json` (`REC-01`–`REC-05`). |
| **`CTRL-07`** | **Operation-Bound Receipt & Verifier** | Mints RFC 8785 JCS canonical JSON receipts signed with Ed25519, chained via SHA-256, and verified offline. | Cross-language verifier vectors (Java 21 CLI, Python 3, standalone WASM) pass with zero network egress. |

### 1.3 Locked Section 1.2 Scope Exclusions (v1.1+ Backlog)
To protect the release baseline against scope drift, the following features are **explicitly excluded** from v1.0 core release claims:
- General-purpose multi-agent orchestration platforms or task routing frameworks.
- Inline natural language Data Loss Prevention (DLP) or semantic intent-context fusion gates.
- Behavioral anomaly baseline scoring or heuristic drift detection.
- Live kernel eBPF LSM enforcement modules and hypervisor-edge sidecars (treated strictly as structural scaffolding).
- Universal multi-tenant SaaS control planes.

---

## Section 2: Mandatory Architectural & Epistemic Corrections

### 2.1 Enforced Stage-Dependent Human Stop & Halt State Machine
To eliminate state-machine corruption and evidence-override ambiguity, AEIB enforces four distinct runtime stages with non-negotiable resolution semantics:

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                ENFORCED STAGE-DEPENDENT HALT SEMANTICS                                           │
├───────────────────────────────┬─────────────────────────────────┬───────────────────────────────┬────────────────┤
│ RUNTIME STAGE WHEN STOP OCCURS│ ENFORCED AEIB HALT STATE        │ PERMITTED LEDGER STATE        │ OPERATOR ACTIONS│
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┼────────────────┤
│ 1. Reliably prior to external │ HALT_BEFORE_DISPATCH            │ Dispatch prevented; zero      │ [Acknowledge   │
│    socket write               │                                 │ bytes transmitted.            │  Denial],      │
│                               │                                 │ Terminal: NOT_DISPATCHED      │ [Revoke]       │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┼────────────────┤
│ 2. After socket write         │ HALT_AFTER_AMBIGUOUS_DISPATCH   │ Retries frozen. Outcome       │ [Request Addl  │
│    initiated; outcome unknown │                                 │ preserved strictly as         │  Reconciliation│
│    (e.g., HTTP 504 / TCP RST) │                                 │ EFFECT_INDETERMINATE.         │ [Escalate]     │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┼────────────────┤
│ 3. Target confirms mutation   │ HALT_AFTER_CONFIRMED_EXTERNAL_  │ Dispatches frozen. Mutation   │ [Initiate      │
│    succeeded via mTLS probe   │ EFFECT                          │ recorded as RESOLVED_CONFIRMED│  Compensating  │
│                               │                                 │                               │  Reversal]     │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┼────────────────┤
│ 4. Target confirms rejection  │ HALT_AFTER_CONFIRMED_EXTERNAL_  │ Dispatches frozen. Mutation   │ [Close Incident│
│    or reversal via probe      │ EFFECT                          │ recorded as RESOLVED_REFUTED. │  Record]       │
└───────────────────────────────┴─────────────────────────────────┴───────────────────────────────┴────────────────┘
```

#### Enforced Governance Rule: Prohibition of `[APPROVE OVERRIDE]`
> **`[APPROVE OVERRIDE]` is strictly prohibited.** No human button, dashboard toggle, or supervisory UI control may declare an ambiguous external mutation "succeeded" or "failed" without attaching authenticated target evidence or executing a separate, audited administrative compensating transaction. Ambiguity is preserved until target facts are verified.

### 2.2 Banned Assertions and Explicit Exclusions
To ensure technical integrity and prevent misleading representations, the following assertions are barred from all AEIB documentation:
- Claims of automatic **"EU AI Act Certification"** or **"DORA Certification."**
- Claims of **"Universal Exactly-Once Execution"** across unreliable distributed networks.
- Hardware enclave attestation claims (Intel TDX / AMD SEV-SNP) until physical hardware quotes are integrated.
- Merkle Mountain Range (LICITRA-MMR) accumulators or COSE_Sign1 / SCITT claims until cryptographic profiles are finalized.
- Zero-Knowledge (ZK-R1CS) compliance proofs.

### 2.3 Competitive Gap Hypothesis (Defensible Stance)

> **Competitive gap hypothesis**: Based on public materials reviewed on current archive dates, we did not find documented evidence that the evaluated products combine exact pre-dispatch action binding, durable dispatch intent (EO-1), post-dispatch transport-ambiguity handling (EFFECT_INDETERMINATE), and target-attested financial reconciliation (refund_status_v1). This is a review gap, not proof that no competitor possesses these capabilities.

The evaluation below reviews publicly documented architectural profiles as of Q4 2026 across relevant infrastructure classes:

| Infrastructure Category | Representative Platforms | Exact Pre-Dispatch Action Binding (`CAID` / RFC 8785) | Durable Dispatch Intent (`EO-1` `fsync` Pre-Socket) | Post-Dispatch Transport Ambiguity Latching (`EFFECT_INDETERMINATE`) | Target-Attested Reconciliation (`refund_status_v1` Contract) | Documented Focus & Boundary Distinction |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Durable Execution & Workflow Orchestration** | Temporal, Restate, DBOS | Configurable payload passing; general workflow state | Workflow history journaled; does not bind external socket creation directly | Activity failure triggers automated retry policies unless explicitly configured with custom non-retryable errors | Relies on custom developer-written activity compensation logic; no standard target evidence contract | Focuses on workflow completion across microservices; assumes downstream services handle idempotency keys or custom compensating workflows. |
| **Agent Observability & Evaluator Firewalls** | LangSmith, AgentOps, Portkey, NeMo Guardrails | Evaluates natural language or prompt context; token-level tracing | Asynchronous telemetry dispatch; no pre-socket flush barrier | Telemetry records transport error; does not latch execution boundary to prevent subsequent tool invocations | Observes agent reasoning traces; no cryptographic target status verification | Focuses on LLM prompt/response evaluation, token accounting, and behavioral guardrails; operates out-of-band or via application wrappers. |
| **API Gateways & Ingress Controllers** | Kong, Envoy, Cloudflare API Shield | Inspects HTTP headers and rate limits; token bucket filtering | No persistent dispatch intent log prior to upstream proxy write | Returns HTTP 504 / 502 upstream error to client; does not track downstream state ambiguity | Does not perform out-of-band status probes against external target endpoints | Focuses on perimeter traffic routing, TLS termination, rate-limiting, and generic header-based idempotency. |
| **AEIB Execution Interlock** | AEIB Station 1–3 Boundary | **Enforced**: Deterministic RFC 8785 JCS canonical hash (`CAID`) validated at microsecond $T_n$ | **Enforced**: Signed `DISPATCH_INTENT` flushed to durable log before socket allocation | **Enforced**: Terminal latching on transport drop (`HTTP 504`, `TCP RST`); `retry_safe: false` | **Enforced**: Out-of-band `refund_status_v1` probe under strict `ProbeBudget: 1` before retry authorization | Delivers a specialized fail-closed wire boundary specifically for consequential financial mutations. |

*Epistemic boundary notice: This comparison reflects publicly available technical documentation and public specifications as of October 2026. Different architectural components may be combined or configured by deployers to achieve equivalent properties under custom engineering models.*

### 2.4 Calibrated Three-Tier Trust Hierarchy

To avoid overstating the epistemic authority of cryptographic receipts, AEIB classifies all generated evidence into three strictly separated tiers:

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   CALIBRATED THREE-TIER TRUST HIERARCHY                                         │
├─────────┬──────────────────────────┬──────────────────────────────────────────┬─────────────────────────────────┤
│ TIER    │ ATTESTATION LEVEL        │ WHAT IT PROVES                           │ WHAT IT DOES NOT PROVE          │
├─────────┼──────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────┤
│ Level 1 │ Agent-Signed             │ Proves an internal signer inside the     │ Does not establish that the     │
│         │                          │ agent runtime signed a record or action  │ agent signer was uncompromised  │
│         │                          │ intent at timestamp T_0.                 │ or free from prompt injection.  │
├─────────┼──────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────┤
│ Level 2 │ Boundary-Signed          │ Proves an independent, controlled        │ Does not by itself establish    │
│         │ (AEIB Station 1/3)       │ boundary observed, evaluated standing,  │ external target-side state or   │
│         │                          │ or authorized a socket dispatch.         │ downstream wire completion.     │
├─────────┼──────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────┤
│ Level 3 │ Target-Attested          │ Proves an authenticated target reported  │ Subject to the target's key     │
│         │ (Receiver-Attested)      │ an operation-specific status under a     │ custody, API contract fidelity, │
│         │                          │ versioned evidence contract.             │ and implementation trust model. │
└─────────┴──────────────────────────┴──────────────────────────────────────────┴─────────────────────────────────┘
```

- **Level 1 (Agent-Signed)**: Proves an internal signer inside the agent runtime signed a record. Does not establish that the signer was uncompromised.
- **Level 2 (Boundary-Signed)**: Proves a controlled boundary observed or authorized a dispatch (e.g., AEIB Station 1/3 receipts). Does not by itself establish target-side effect.
- **Level 3 (Target-Attested / Receiver-Attested)**: Proves an authenticated target reported an operation-specific status under a versioned evidence contract. Subject to the target's key custody, API contract, and implementation trust model.

### 2.5 MCP Transport & Protocol Policy

When operating as a Model Context Protocol (MCP) tool-call interlock, AEIB enforces strict protocol version pinning, negotiation validation, and parameter binding:

```yaml
mcp_transport_policy:
  require_protocol_version_header: true
  accepted_versions: ["2025-06-18"] # Pinned to official MCP specification version
  version_source: initialization_negotiation
  mismatch_behavior: reject
  body_binding: canonical_action_digest # CAID computed over parsed and canonicalized parameters
```

1. **Protocol Version Pinning**: All MCP tool dispatches must negotiate and declare protocol version `2025-06-18`. Unknown, unnegotiated, or deprecated protocol headers trigger immediate pre-dispatch rejection (`MCP_PROTOCOL_VERSION_UNSUPPORTED`).
2. **Initialization Negotiation Validation**: Protocol version is extracted strictly from the authenticated initialization negotiation handshake, not from transient request headers.
3. **Canonical Body Binding**: The candidate action ID ($\text{CAID}$) is computed directly over the parsed and RFC 8785 JCS canonicalized tool arguments, binding the boundary decision immutably to the wire payload.

---

## Section 3: Target Evidence Contract (`refund_status_v1`)

To resolve an `EFFECT_INDETERMINATE` state to `RESOLVED_CONFIRMED` or `RESOLVED_REFUTED`, Station 2 reconciliation probes require target responses to satisfy the versioned schema defined in [`contracts/refund_status_v1.schema.json`](file:///Users/andriileukhin/Documents/SovereignNexus/contracts/refund_status_v1.schema.json):

1. **Operation Binding**: The response `operation_id` and `idempotency_key` must match the original pre-dispatch `DISPATCH_INTENT`.
2. **Cryptographic Authentication**: Evidence must be delivered over verified mTLS or bear a valid 64-byte Ed25519 signature from a pinned target SubjectPublicKeyInfo (`target_spki_digest`).
3. **Exact Parameter Parity**: The unredacted `amount_minor_units`, `currency`, and `recipient_binding` must match the pre-dispatch canonical $\text{CAID}$ hash.
4. **Fail-Closed Uncertainty**: Any timeout, malformed payload, or conflicting status field (`PENDING`, `UNKNOWN`) keeps the state strictly as `EFFECT_INDETERMINATE` under an operational `RECONCILIATION_HOLD`.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                  TARGET RECONCILIATION CONTRACT RESOLUTION MAPPING                     │
├───────────────────────────────┬──────────────────────────────────┬─────────────────────┤
│ TARGET STATUS IN CONTRACT     │ AEIB BOUNDARY RESOLUTION         │ RETRY SAFETY        │
├───────────────────────────────┼──────────────────────────────────┼─────────────────────┤
│ SETTLED                       │ RESOLVED_CONFIRMED               │ retry_safe: true    │
│ REVERSED / REJECTED           │ RESOLVED_REFUTED                 │ retry_safe: false   │
│ PENDING / UNKNOWN             │ EFFECT_INDETERMINATE (LATCHED)   │ retry_safe: false   │
│ MALFORMED / TIMEOUT / PROBE_E │ EFFECT_INDETERMINATE (LATCHED)   │ retry_safe: false   │
└───────────────────────────────┴──────────────────────────────────┴─────────────────────┘
```

---

## Section 4: Calibrated EU Regulatory & Standards Crosswalk (2026–2027)

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   CALIBRATED REGULATORY & STANDARDS BOUNDARY MATRIX                    │
├──────────────────────────┬─────────────────────────────────────────────────────────────┤
│ REGULATORY PROVISION     │ AEIB TECHNICAL EVIDENCE vs. DEPLOYER OBLIGATION             │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Art. 17 & EN 18286:2026  │ • AEIB: Reproducible build provenance & post_market_...jsonl│ │ (Quality Management)     │ • Deployer: Complete organizational QMS procedures.         │
│                          │   (DORA Art. 17 ICT reports are NEVER mapped as AI Act QMS).│ ├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Art. 12 (Logging &       │ • AEIB: Tamper-evident Ed25519 ContinuityReceipt chains.    │ │ Record-Keeping)          │ • Deployer: 10-year archival retention infrastructure.      │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Art. 14 (Human Oversight)│ • AEIB: Deterministic stage-dependent HaltSignal & AIBs.   │ │                          │ • Deployer: Operator staffing, training, and legal authority.│
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Art. 15 (Security &      │ • AEIB: Pre-execution blocks, wire-fault latching, AT40–46.│ │ Robustness)              │ • Deployer: Host OS hardening, zero-day kernel defense.     │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Art. 10 (Data            │ • AEIB: Consequential field schema & JCS parameter binding.  │ │ Governance)              │ • Deployer: Training dataset curation, bias & GDPR checks. │
└──────────────────────────┴─────────────────────────────────────────────────────────────┘
```

### 4.1 EN 18286:2026 Scope Boundary
Commission Implementing Decision (EU) 2026/2274 establishes a presumption of conformity **strictly for Article 17 QMS lifecycle processes**. It does not certify Layer 7 payload binding, microsecond $T_n$ revalidation, or wire proxy correctness. AEIB supplies the un-tamperable runtime inputs that feed into the deployer's QMS repository.

### 4.2 Regulatory Regime Isolation
- **EU AI Act Article 73**: Serious incident reporting operates under a 15-day reporting clock to national market surveillance authorities and the EU AI Office.
- **DORA Article 17**: Major ICT-related incident classification operates under a 4-hour initial notification window to financial supervisory authorities (EBA, ECB, national competent authorities).
These regimes are maintained as parallel, un-conflated reporting pathways.

### 4.3 Article 10 Parameter Binding vs. Dataset Governance
AEIB enforces strict runtime parameter schemas via RFC 8785 JCS $\text{CAID}$ digests and separates execution-bound fields from redacted operator briefs. It makes no claim that runtime parameter gating satisfies Article 10 training and validation data governance.

### 4.4 Bounded Regulatory Mapping (DORA & EU AI Act)

To ensure strict compliance with epistemic boundaries, AEIB's regulatory mapping defines both its positive contribution and explicit non-claims:

- **AEIB Role**: AEIB produces operation-level evidence (pre-execution restraint records, dispatch intent, reconciliation traces) that a financial entity or deployer can associate with its own ICT third-party management, incident-management, and compliance processes.
- **What AEIB Does NOT Do**: It does not maintain the DORA Register of Information, perform vendor due diligence, warrant Article 15 system-wide conformity, or automate regulatory filings.

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                       BOUNDED REGULATORY CAPABILITY & SCOPE ENVELOPE                            │
├───────────────────────────────┬─────────────────────────────────┬───────────────────────────────┤
│ REGULATORY REGIME             │ WHAT AEIB PROVIDES              │ WHAT AEIB DOES NOT DO         │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┤
│ DORA (Regulation (EU)         │ • Microsecond pre-dispatch intent│ • Does NOT maintain entity-   │
│ 2022/2554)                    │   persistence and receipt chains.│   level Register of Info.     │
│ Articles 17 & 28              │ • Cryptographic transport traces│ • Does NOT conduct supplier   │
│                               │   supporting incident timelines.│   due diligence or audits.    │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┤
│ EU AI Act (Regulation (EU)    │ • Article 12 event logging with │ • Does NOT warrant system-wide│
│ 2024/1689)                    │   RFC 8785 canonical hashes.    │   conformity with Art. 15.    │
│ Articles 12, 14, 15           │ • Article 14 deterministic stop │ • Does NOT automate legal     │
│                               │   and stage-dependent halt.     │   filings or CE marking.      │
│                               │ • Pre-execution restraint logs. │ • Does NOT perform dataset QMS│
└───────────────────────────────┴─────────────────────────────────┴───────────────────────────────┘
```

---

## Section 5: Integrated Architectural Controls & Operational Runbooks

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   INTEGRATED ARCHITECTURAL GAPS & CONTROL MATRIX                       │
├──────────────────────────┬─────────────────────────────────────────────────────────────┤
│ COMPONENT / GAP          │ ENFORCED RUNTIME INVARIANT & TEST COVERAGE                  │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ refund_status_v1         │ • Strict mTLS or pinned pubkey authentication.              │ │ Schema Contract          │ • operation_id + idempotency_key match to DISPATCH_INTENT.  │
│                          │ • Parameter parity (amount_minor_units, currency, recipient)│ │                          │   must match pre-dispatch CAID digest unredacted.           │
│                          │ • Malformed/timed-out responses remain EFFECT_INDETERMINATE.│ ├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Gap 4: Delegation Gate   │ • Scope Narrowing: Subagent exceeding scope returns         │ │ (AT39)                   │   DELEGATION_SCOPE_EXCEEDED pre-dispatch.                   │
│                          │ • Cascade Revocation: Parent revocation at Δ invalidates    │ │                          │   child grant at Tn.                                        │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Gap 5: Boundary Prompt   │ • Prompt injection attempts to alter IBAN, amount, target   │ │ Injection Suite          │   URI, or policy epoch trigger immediate pre-dispatch     │
│ (AT40–AT46)              │   CAID mismatch, allowlist, or epoch rejection.             │ │                          │ • Injecting "human_approved": true or text "status": "SETTLED"│
│                          │   is ignored; boundary requires cryptographic step-up ticket│ │                          │   and out-of-band target reconciliation.                    │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Gap 6: Operational       │ • RB-01: Uncertain mutation triage (AIB -> status probe).  │ │ Runbooks                 │ • RB-02: Compromise quarantine (HaltSignal execution).      │
│ (RB-01 to RB-05)         │ • RB-03: Disk EIO fail-closed storage protection.           │ │                          │ • RB-04: Ed25519 signing key rotation & SPKI anchoring.    │
│                          │ • RB-05: Freeze & signed policy epoch rollback.            │ ├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Gap 7: Post-Market       │ • Append-only, hash-chained post_market_evidence.jsonl     │ │ Telemetry Stream         │   exporting operational metrics (unresolved ops, denial     │
│                          │   reasons, resolution times) for EU AI Act Art. 72.         │ └──────────────────────────┴─────────────────────────────────────────────────────────────┘
```

### 5.1 Immunity to Prompt-Injected Reasoner Compromise (`AT40`–`AT46`)
Even if an attacker gains total control of the LLM generation loop via indirect prompt injection, the execution boundary enforces physical separation:
- Natural-language declarations such as `"human_approved": true` or `"status": "SETTLED"` in model outputs are ignored.
- All consequential socket writes require a valid cryptographic `DispatchAuthorityTicket` signed by an authorized key.
- Recipient and amount modifications trigger immediate `ACTION_DIGEST_MUTATED` failure at $T_n$.

### 5.2 Monotonic Delegation Attenuation (`AT39`)
Subagent delegation chains enforce strict containment: $\text{Scope}_{\text{child}} \subseteq \text{Scope}_{\text{parent}}$. Every delegation hop binds `(principal_id, parent_grant_id, child_grant_id, delegation_scope, policy_epoch)`. Revoking a parent grant at $\Delta$ immediately invalidates all child subagent capabilities down the entire delegation tree.

### 5.3 Fail-Closed Storage & Cryptographic Maintenance (`RB-01`–`RB-05`)
- **`RB-01` (Uncertain Mutation Triage)**: Triages `EFFECT_INDETERMINATE` records via automated status probe, falling back to dual-control manual investigation.
- **`RB-02` (Compromise Quarantine)**: Trips Andon cord, writing signed state to disk and dropping subsequent socket attempts.
- **`RB-03` (Storage Protection)**: On storage I/O errors (`EIO`) or disk exhaustion, blocks consequential socket allocation fail-closed.
- **`RB-04` (Signing Key Rotation)**: Rotates Ed25519 keypair, updating SPKI anchor in continuous ledger while preserving historical verification.
- **`RB-05` (Epoch Rollback)**: Advances policy epoch to invalidate all outstanding pre-granted tickets upon policy violation.

---

## Section 6: Master Test Matrix & Verification Status

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        MASTER TEST MATRIX EXECUTION STATUS                             │
├──────────────────────────┬──────────────────────────┬──────────────────────────────────┤
│ TEST GROUP               │ VECTOR IDS               │ CURRENT STATUS                   │
├──────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Pre-Execution Prevention │ AT30 – AT35 (PEP-01..06) │ VERIFIED & LOCKED (PASS 6/6)     │
│ Enforced Halt & Step-Up  │ AT36 – AT38 (HALT-01..03)│ VERIFIED & LOCKED (PASS 3/3)     │
│ Delegation Attenuation   │ AT39 (DEL-01)            │ VERIFIED & LOCKED (PASS 1/1)     │
│ Target Status Contract   │ REC-01 (REC-01..05)      │ VERIFIED & LOCKED (PASS 5/5)     │
│ Boundary Prompt Injection│ AT40 – AT46 (INJ-01..07) │ QUEUED (Phase 3)                 │
│ Operational Runbooks     │ RB-01 – RB-05            │ QUEUED (Phase 3)                 │
└──────────────────────────┴──────────────────────────┴──────────────────────────────────┘
```

### 6.1 Phase 1 Attestation Record (Locked Baseline)
- **Test File**: [`tests/test_pre_execution_prevention.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tests/test_pre_execution_prevention.py)
- **Evidence Record**: [`docs/compliance/pre_execution_evidence.yaml`](file:///Users/andriileukhin/Documents/SovereignNexus/docs/compliance/pre_execution_evidence.yaml)
- **Source Commit**: `6bd91b1e`
- **Result**: **6/6 Passed** (`PEP-01` to `PEP-06` / `AT30` to `AT35`). Zero external wire calls observed across all denied scenarios.
- **Evidence Package**: `dist/aeib-pilot-evidence-pack-v1.1.0-rc.1.tar.gz` (SHA-256: `c80cdb6b2ba8a7768fbb42782ca669c180904b930c764f5bb9d8cddce2d046fd`).

### 6.2 Phase 2 Attestation Record (Enforced Halt, Delegation & Reconciliation)
- **Test File**: [`tests/test_enforced_halt_and_delegation.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tests/test_enforced_halt_and_delegation.py)
- **Evidence Bundles**:
  - `artifacts/phase2/AT36_HALT_BEFORE_DISPATCH_evidence.json`
  - `artifacts/phase2/AT37_HALT_AFTER_AMBIGUOUS_DISPATCH_evidence.json`
  - `artifacts/phase2/AT38_SUPERVISORY_STEP_UP_evidence.json`
  - `artifacts/phase2/AT39_DELEGATION_SCOPE_EXCEEDED_evidence.json`
  - `artifacts/phase2/REC01_TARGET_RECONCILIATION_SETTLED_evidence.json`
- **Result**: **9/9 Passed** (Phase 2 tests). Verified with standalone verifier `tools/verify_phase2_evidence.py --check-jcs-conformance` (25/25 RFC 8785 vectors passing). Zero un-attested state transitions observed.

---

## Section 7: Three Commercial Pilot Patterns

AEIB is packaged for production pilot validation across financial and regulated enterprises using three non-disruptive deployment patterns:

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THREE COMMERCIAL PILOT PATTERNS                                 │
├──────────────────────────┬────────────────────────────────────┬─────────────────────────────────┤
│ PILOT PATTERN            │ OPERATIONAL MECHANISM              │ PRIMARY VALUE ARTIFACT          │
├──────────────────────────┼────────────────────────────────────┼─────────────────────────────────┤
│ 1. Observe-Then-Enforce  │ Passive sidecar evaluation; logs   │ Comparative baseline telemetry; │
│                          │ WOULD_BLOCK without dropping I/O;  │ drift analysis before policy    │
│                          │ flips to fail-closed on confidence.│ enforcement lock.               │
├──────────────────────────┼────────────────────────────────────┼─────────────────────────────────┤
│ 2. Pre-Execution         │ Intercepts unauthorized mutations  │ Cryptographically signed denial │
│    "Restraint Records"   │ prior to socket allocation; records│ receipts proving prevention of  │
│                          │ zero bytes sent to downstream wire.│ out-of-policy mutations.        │
├──────────────────────────┼────────────────────────────────────┼─────────────────────────────────┤
│ 3. Target-Attested       │ Resolves HTTP 504 / TCP RST via    │ Level 3 Target Evidence bundles;│
│    Reconciliation        │ out-of-band authenticated probe    │ eliminates blind retry storms   │
│                          │ under single-probe budget.         │ and financial double-execution. │
└──────────────────────────┴────────────────────────────────────┴─────────────────────────────────┘
```

### 7.1 Pattern 1: Observe-Then-Enforce (Risk-Free Deployment)
To facilitate seamless pilot adoption in tier-1 banking architectures, AEIB supports a two-phase rollout:
1. **Observation Mode (Phase A)**: AEIB runs as a transparent Layer 7 proxy or container sidecar. It parses candidate actions, evaluates temporal standing, checks parameter binding, and computes candidate action digests ($\text{CAID}$). If an invariant is violated, AEIB logs a `WOULD_BLOCK` telemetry event and signed shadow receipt, but allows the downstream socket to proceed. This generates a baseline drift report without impacting live transactions.
2. **Enforcement Mode (Phase B)**: Once baseline operational parameters and false-positive rates are confirmed at zero across evaluation runs, the boundary is switched to fail-closed enforcement for designated high-consequence tools (`refund_customer`, `disburse_payout`). Any standing violation or expired authority aborts socket creation before byte transmission.

### 7.2 Pattern 2: Pre-Execution "Restraint Records"
Compliance and internal audit teams require evidence not only of actions taken, but of actions successfully prevented. For every arrested mutation:
1. **Zero External I/O**: The transport interceptor confirms zero TCP packets and zero HTTP bytes were emitted to the external network interface.
2. **Cryptographic Proof of Prevention**: AEIB mints a tamper-evident pre-execution restraint record containing the exact rejected candidate action, principal, active epoch, evaluated reason code (`AT30_EXPIRED_AUTHORIZATION`, `AT31_STALE_EPOCH_BLOCKED`, `AT32_REVOKED_AUTHORIZATION`, `AT33_ACTION_DIGEST_MUTATED`, `AT34_REPLAY_DETECTED`, `AT35_UNALLOWLISTED_TARGET`), and boundary Ed25519 signature.
3. **Audit Utility**: Supplies verifiable evidence under EU AI Act Article 14 (human oversight) and Article 15 (cybersecurity resilience), demonstrating that the boundary arrested out-of-bounds agent behavior before external side effects occurred.

### 7.3 Pattern 3: Target-Attested Reconciliation
When network partitions or server timeouts (`HTTP 504 Gateway Timeout`, `TCP RST`, connection drop) leave transaction state ambiguous:
1. **Automated Latching**: Station 2 classifies the event as `EFFECT_INDETERMINATE` with `retry_safe: false`, arresting agent retry loops.
2. **Bounded Out-of-Band Probe**: AEIB executes an authenticated query against the target provider's status endpoint using the versioned [`contracts/refund_status_v1.schema.json`](file:///Users/andriileukhin/Documents/SovereignNexus/contracts/refund_status_v1.schema.json) contract under a strict `ProbeBudget: 1`.
3. **Cryptographic Resolution**:
   - If the target returns `SETTLED`, the mutation is recorded as `RESOLVED_CONFIRMED` with a Level 3 target-attested receipt.
   - If the target returns `REVERSED` or `REJECTED`, the state transitions to `RESOLVED_REFUTED`.
   - If the target is unreachable or returns malformed status, the state remains latched under `RECONCILIATION_HOLD`, generating an Action Intelligence Brief (AIB) for dual-control operator review.

