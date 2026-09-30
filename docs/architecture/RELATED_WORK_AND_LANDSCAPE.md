# AEIB Related Work & Competitive Landscape Synthesis

**Standard:** Agent Execution Integrity Benchmark (AEIB v0.2.0)  
**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus)  
**Status:** Research Note & Architectural Positioning  
**Scope:** Honest positioning of post-dispatch execution integrity relative to emerging standards, commercial platforms, and runtime authorization engines.

---

## 🧭 Executive Summary: The Post-Dispatch Lane

The agentic infrastructure landscape is rapidly dividing into distinct operational layers:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               THE AGENT INTEGRITY PIPELINE                             │
├──────────────────────────┬─────────────────────────────┬───────────────────────────────┤
│ 1. PRE-DISPATCH (GATE)   │ 2. DISPATCH & AMBIGUITY     │ 3. POST-DISPATCH (AUDIT)      │
│ • Runtime Authorization  │ • Transport wire-fault trap │ • Execution Recording         │
│ • Policy Decision Points │ • 7-state taxonomy mapping  │ • SCITT Transparency Service  │
│ • Tool allowlisting      │ • Reconcile-before-retry    │ • Regulatory reporting        │
│                          │ • Out-of-band state probes  │                               │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ P0, Delinea, Saviynt,    │ **AEIB (SovereignNexus)**   │ Salmon EVI, IETF SCITT,       │
│ WitnessAI, Safeguard     │ (Post-dispatch integrity)   │ TRACE Hardware Attestation    │
└──────────────────────────┴─────────────────────────────┴───────────────────────────────┘
```

AEIB operates strictly in **Layer 2 (Post-Dispatch Transport Ambiguity & Reconciliation)**. It does not replace pre-dispatch policy enforcement nor try to be an enterprise-wide execution record platform.

---

## 🔬 1. Execution Verification & Recording (Salmon EVI)

### The Category Landscape
Salmon’s Execution Verification Infrastructure (EVI) makes a critical architectural distinction that validates this emerging domain:
* **Governance**: *"Was the agent authorized to make this tool call?"*
* **Verification**: *"What did the agent actually execute on the underlying system, and can we cryptographically prove it?"*

### AEIB Complementary Positioning
> *"The emerging 'execution verification' category (e.g., Salmon EVI) focuses on capturing signed evidence of agent actions. AEIB complements this by focusing specifically on ambiguous post-dispatch outcomes: when transport faults leave the system uncertain whether an action succeeded. Our 7-state disposition taxonomy, deterministic retry constraints, and out-of-band reconciliation probes are designed specifically for that post-dispatch gap."*

### Non-Claims & Boundaries
* We do **not** claim parity with or superiority over Salmon EVI.
* We do **not** claim to provide a commercial enterprise evidence collection platform or SaaS telemetry fabric.

---

## 📜 2. Emerging IETF Standards & Drafts

### Relevant Work in Progress
1. **AER-1 (Agent Execution Receipts)**: Emerging drafts exploring canonical envelopes for AI agent action receipts.
2. **SCITT AI-Agent Action Receipts**: Extensions to the IETF Supply Chain Integrity, Transparency, and Trust (SCITT) architecture to record autonomous actions.
3. **Authorization Evidence Chains**: Standardizing verifiable credentials across multi-agent delegation trees.

### AEIB Conceptual Alignment
> *"AEIB’s receipt format is designed to be conceptually compatible with emerging IETF work on agent action receipts (e.g., AER-1, SCITT AI-Agent Action Receipts). Our `org.smaos.aeib` namespace can be embedded as a vendor extension within a COSE_Sign1 envelope, mapping our 7-state disposition to their normative verdict fields."*

### Non-Claims & Boundaries
* AEIB is **not** currently certified as RFC 8785 (JCS) compliant (it uses a deterministic JSON subset).
* AEIB is **not** a formal implementation of AER-1.
* AEIB receipts are **not** currently registered in a live, public IETF SCITT Transparency Service.

---

## 🚪 3. Pre-Dispatch Runtime Authorization & Policy Decision Points

### The Category Landscape
Enterprise IAM and PAM vendors (P0 Security, Delinea, Saviynt, Tetrate + Ory, Curity) are rapidly building pre-dispatch policy enforcement for agent tool invocation.

### AEIB Downstream Positioning
> *"Runtime authorization engines decide whether an action may be attempted. AEIB assumes an action has been authorized and dispatched, then handles the critical failure case where the transport response is ambiguous. Our focus is: what happens after an HTTP 504, TCP reset, or gateway drop, before any retry is permitted."*

### Strategic Integration
* AEIB does **not** compete with runtime authorization or policy engines.
* AEIB consumes the policy context token (verifying non-expiry) and guarantees that if transport drops, the action is quarantined rather than blindly re-authorized.

---

## 🔄 4. The "Reconcile Before Retry" Doctrine

### Background & Validation
Industry guidance (such as the *Digital Thought Disruption* analysis and recent distributed agent reliability doctrine) has increasingly recognized a core failure pattern:
> *"An unknown outcome is a state to investigate, not permission to execute again."*

### AEIB Implementation
* AEIB does not claim to have invented the concept of idempotency or outbox reconciliation.
* AEIB provides a **concrete, verifiable, open implementation** of this doctrine through:
  1. Automatic assignment of the `DISPATCHED_UNCONFIRMED` disposition on unconfirmed transport drops.
  2. Hard policy lock: `retry_permitted: false`.
  3. Authoritative state reconciliation via deterministic UUIDv5 handles before any execution retry is allowed.

---

## 📦 5. Commit-Time Reject-and-Rerun & Outbox Patterns

### Emerging Literature
Recent academic work (e.g., arXiv models for governed agentic execution) explores commit-time dependency checks and outbox reservations to prevent race conditions during long-horizon agent tasks.

### Future Roadmap Adoption
* AEIB v0.2 currently operates as a synchronous interceptor / trace verifier.
* In future roadmap iterations (v0.3+), AEIB explores an outbox reservation pattern: reserving an idempotent state effect prior to wire dispatch, and marking it committed or aborted only after probe resolution.

---

## 🛡️ 6. MCP Governance & Interceptor Ecosystem

### The Category Landscape
Open-source and commercial MCP security tools (such as WitnessAI, Safeguard, and community interceptors like `mcp-shield`) provide schema validation, prompt-injection defense, and tool allowlisting.

### AEIB Non-Competition Doctrine
* We do **not** rebuild tool firewalls, prompt cleaners, or permission prompts.
* AEIB is designed to integrate cleanly with MCP proxy chains:
  - Let upstream tools handle schema validation and authorization.
  - Let AEIB handle dispatch evidence, transport fault trapping, out-of-band reconciliation, and signed disposition receipt emission.

---

## 🏷️ 7. Hardware Attestation & Enclaves (TRACE)

### Adjacent Category
Frameworks like TRACE focus on hardware-attested execution traces using confidential computing (TEE) and hardware roots of trust.

### Roadmap Alignment
* Hardware attestation is adjacent, high-value infrastructure.
* AEIB v0.2 operates at the software protocol and receipt layer. Future iterations may explore binding AEIB receipts to TEE attestation quotes when running inside confidential enclaves.

---

## 📊 Summary Comparison Matrix

| Dimension | Pre-Dispatch Auth (P0, Delinea) | Execution Recording (Salmon EVI) | MCP Gateways (WitnessAI) | **AEIB (SovereignNexus)** |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Phase** | Pre-Dispatch ($) | Post-Dispatch Logging ($) | Pre-Dispatch Intercept ($) | **Post-Dispatch Fault Boundary ($)** |
| **Problem Solved** | Access authorization & least privilege | Proof of what model executed | Prompt injection & tool filtering | **HTTP 504 drops, ambiguous writes & duplicate retries** |
| **Core Artifact** | Auth token / Permitted decision | Execution transcript / event log | Sanitized request payload | **Ed25519 receipt with retry constraint & probe hash** |
| **Current Status** | Commercial Enterprise SaaS | VC-backed Platform | Open-Source / Commercial Proxy | **Independent Research Synthetic Prototype (v0.2)** |
