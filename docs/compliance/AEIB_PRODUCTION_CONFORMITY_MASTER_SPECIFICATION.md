# AEIB Production Execution & Conformity Master Specification
**Standardized Technical Evidence, Architectural Invariants, and Calibrated EU Regulatory Crosswalk**

```text
Document Version : 1.1.0-rc.1
Release Baseline : v1.0.0-rc.3 (Locked) / Track B v1.1 Sequence
Status           : Locked Architectural & Regulatory Specification
Working Branch   : feat/v1.1-production-boundary
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
│ Enforced Halt & Step-Up  │ AT36 – AT38 (HALT-01..03)│ READY FOR ATTESTATION            │
│ Target Status Contract   │ REC-01 – REC-05          │ READY FOR ATTESTATION            │
│ Delegation Attenuation   │ AT39 (DEL-01)            │ QUEUED (Phase 2)                 │
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
