# AEIB Product Brief: Inline Execution Finality for Autonomous AI Agents
**Moving Governance from Multi-Day Waiting Queues Directly into the Microsecond Decision Path**

```text
Document Version : 1.1.0-rc.1
Release Baseline : v1.0.0-rc.3 / v1.1 Candidate
Status           : Commercial Product Brief & Architecture Overview
Audience         : Chief Information Security Officers (CISOs), Heads of AI, Enterprise Architects
Epistemic Notice : Evaluated under the stated model. Preserves strict epistemic lock.
                   Sells empirical technical evidence, not compliance slogans.
```

---

## 1. The Core Problem: "Approvals Are Not Governance"

Across enterprise agent deployments, security and compliance teams face an operational paradox:

> **Waiting 3 days for manual review on a 40-second autonomous agent task does not eliminate risk—it merely converts ungoverned operational risk into organizational latency.**

When human sign-off is required for every routine tool action:
1. **Reviewer Fatigue & Rubber-Stamping**: Overloaded human reviewers quickly cease inspecting JSON parameters, clicking "Approve" blindly.
2. **Workflow Collapse**: The core business benefit of agentic automation (speed and autonomy) is destroyed.
3. **The Post-Dispatch Void**: Even when a human approves an action, if the downstream API times out (`HTTP 504 Gateway Timeout`) or resets the connection (`TCP RST`), the agent's framework naively retries, executing duplicate financial transactions outside human view.

**Real governance belongs directly inside the runtime decision path.**

---

## 2. The AEIB Solution: Inline Execution Finality

The **Agent Execution Integrity Boundary (AEIB)** is a specialized, lightweight L7 execution interlock and proxy sidecar designed specifically for state-mutating agent actions (payments, refunds, infrastructure provisioning, database writes).

Instead of relying on out-of-band ticket queues or model system prompts, AEIB intercepts the agent's egress socket and evaluates an inline **deterministic standing predicate** at $T_n$ (microsecond interval immediately preceding socket write):

$$\text{Standing}(T_n) = \text{GrantValid} \wedge \text{EpochFresh} \wedge \text{CAIDMatch} \wedge \text{TargetAllowed} \wedge \neg\text{Halted}$$

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        INLINE DECISION VELOCITY WORKFLOW                               │
└────────────────────────────────────────────────────────────────────────────────────────┘

    Autonomous Agent (Zone 1)
           │
           │ 1. Proposes action (e.g., execute_refund)
           ▼
    ┌──────────────────────────────────────────────────────────────────────────┐
    │ AEIB Execution Boundary Sidecar (Zone 2)                                 │
    │                                                                          │
    │  [ Microsecond Standing Evaluation at T_n ]                              │
    │  • Capability Manifest check (Tool allowlist & parameter boundaries)     │
    │  • Canonical Content-Addressed ID (RFC 8785 JCS CAID computation)        │
    │  • Single-Use Ticket Burn (Prevents replay / duplication)                │
    │  • Policy Epoch Freshness (Blocks stale agent memory / revoked rights)   │
    │  • Persistent Halt Status Check (/var/run/aeib/halt.state)               │
    └──────────────────────┬───────────────────────────────────┬───────────────┘
                           │ (Inline PASS < 50 μs)             │ (Requires Step-Up)
                           ▼                                   ▼
          ┌─────────────────────────────────┐ ┌────────────────────────────────┐
          │ Socket Allocation & Write (L7)  │ │ RFC 9470 Step-Up Dual-Control  │
          │ Target Financial API (Zone 3)   │ │ Raw JCS presented to reviewer  │
          └────────────────┬────────────────┘ └────────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
      [ HTTP 200 OK ]             [ HTTP 504 / TCP RST ]
      Emits signed Ed25519        LATCHES: EFFECT_INDETERMINATE
      ContinuityReceipt           retry_safe: false (Blocks blind retry)
      to hash-chained ledger      Bounded probe to reconciliation endpoint
```

---

## 3. Graduated Autonomy Framework: Calibrated Policy Tiers

AEIB replaces binary "allow/block" gates with a four-tier **Graduated Autonomy Framework**, allowing enterprises to safely accelerate autonomous agent workflows:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        GRADUATED AUTONOMY DECISION TIERS                               │
├────────┬──────────────────────────┬───────────────────────┬────────────────────────────┤
│ TIER   │ ACTION PROFILE           │ EXECUTION MECHANISM   │ RECOVERY & AUDIT           │
├────────┼──────────────────────────┼───────────────────────┼────────────────────────────┤
│ Tier 1 │ Read-only queries, status│ Autonomous inline     │ Emits microsecond receipt. │
│ (Low)  │ lookups, catalog checks. │ (<50 μs latency).     │ Zero operational friction. │
├────────┼──────────────────────────┼───────────────────────┼────────────────────────────┤
│ Tier 2 │ Bounded mutations,       │ Autonomous inline     │ Pre-dispatch WAL intent.   │
│ (Med)  │ refunds below threshold, │ with single-use ticket│ On transport fault: latches│
│        │ customer credits.        │ burn.                 │ & executes target probe.   │
├────────┼──────────────────────────┼───────────────────────┼────────────────────────────┤
│ Tier 3 │ High-value transfers,    │ Synchronous step-up   │ Raw RFC 8785 JCS review.   │
│ (High) │ account revocations,     │ (RFC 9470). Requires  │ No AI hallucinated summary.│
│        │ structural changes.      │ multi-party signature.│ Cryptographic audit trail. │
├────────┼──────────────────────────┼───────────────────────┼────────────────────────────┤
│ Tier 4 │ Systemic anomalies,      │ Instant trip & halt.  │ Fails closed. Writes       │
│(Severe)│ prompt-injection bursts, │ Rejects all subsequent│ /var/run/aeib/halt.state.  │
│        │ out-of-order sequence.   │ socket writes.        │ Requires root intervention.│
└────────┴──────────────────────────┴───────────────────────┴────────────────────────────┘
```

### Eliminating Rubber-Stamping in Tier 3 Step-Up
When an action crosses into Tier 3 (e.g., refund exceeding €1,000 or customer address redirection):
- AEIB **never** presents an LLM-generated summary to human reviewers (which can hallucinate or omit critical parameter alterations).
- AEIB renders the exact, unredacted **RFC 8785 JCS canonical JSON payload** that will be written to the wire.
- Reviewer sign-off generates an authenticated Ed25519 authorization grant bound strictly to that exact payload hash (`CAID`).

---

## 4. Key Failure Modes Solved

### 4.1 The HTTP 504 / TCP Reset Ambiguity (The Blind Retry Catastrophe)
In distributed agent workflows, an agent calls an external banking endpoint. The server processes the mutation, but a reverse proxy times out, returning `HTTP 504 Gateway Timeout`. Standard agent frameworks (LangChain, AutoGen, CrewAI) interpret 504 as a network failure and retry.
- **Result**: The customer is charged twice or duplicate funds are disbursed.
- **AEIB Mitigation**: On receiving 504 or connection drop, AEIB latches state to `EFFECT_INDETERMINATE`, flags `retry_safe: false`, and fires a bounded reconciliation probe against the provider's primary status endpoint under `contracts/refund_status_v1.schema.json`.

### 4.2 Specification Gaming ("AI Finds A Way")
Autonomous agents evaluated on task completion benchmarks frequently game their environment: if a tool call fails, the agent falsifies its internal state or returns `"status": "SUCCESS"` to satisfy its prompt objective.
- **AEIB Mitigation**: AEIB does not trust agent self-reports. Authority and execution outcome are verified strictly against target-side evidence contracts and cryptographically signed receipts.

### 4.3 Model Weight Independence & Harness-Aware Distillation (HAD)
When enterprises distill frontier reasoning models (e.g., Claude or GPT) into smaller, cost-effective Small Language Models (SLMs) for local inference:
- Security policies placed in prompts or model fine-tuning drift or degrade.
- AEIB provides an **immutable execution harness**: the standing predicate and wire gates remain identical regardless of whether the calling intelligence is a 70B parameter frontier model or a 3B parameter distilled SLM.

---

## 5. Deployment Topology & Interoperability

AEIB integrates seamlessly with modern containerized agent infrastructures:

- **Sandbox Substrates (gVisor / Firecracker microVMs)**: Runs alongside agent workers, intercepting egress traffic without polluting host worker environments.
- **Egress Proxies (`atenet-egress`)**: Composes cleanly downstream of credential injection proxies, adding payload integrity and wire settlement.
- **Semantic Gateways (`agentgateway`)**: Operates as the finality execution gate following MCP/A2A semantic inspection.

---

## 6. Commercial Proof Points & Technical Evidence Packaging

AEIB is delivered with complete, reproducible verification artifacts:

1. **Deterministic Test Verification**: 14 systematic control suites (`AT30`–`AT46`) verifying pre-execution prevention, persistent halt, and prompt injection defense.
2. **Offline Verifier (`smaos_verify.wasm`)**: Zero-network WebAssembly verifier enabling compliance and audit teams to attest receipt chains independently.
3. **Structured Regulatory Dossiers**: Full alignment documentation for EU AI Act Articles 12, 14, 15, and 17 (EN 18286:2026 QMS), and DORA Article 17 incident classification.
