# AEIB Related Work & Competitive Landscape Synthesis

**Standard:** Agent Execution Integrity Benchmark (AEIB v0.2.0)  
**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus)  
**Status:** Research Note & Architectural Positioning  
**Scope:** Honest positioning of post-dispatch execution integrity relative to emerging standards, commercial platforms, runtime authorization engines, and real-world incidents.

---

## 🏛️ 1. The Converging Three-Layer Agent Stack

Industry consensus across academia and enterprise architecture is converging on a tripartite division of responsibilities for autonomous agent systems:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              THE THREE-LAYER AGENT STACK                               │
├──────────────────────────┬─────────────────────────────┬───────────────────────────────┤
│ 1. GOVERNANCE (Permit)   │ 2. HARNESS (Sandboxing)     │ 3. VERIFICATION (Evidence)    │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ • Access authorization   │ • Process isolation / jail  │ • Execution recording         │
│ • Identity & delegations │ • Network egress filtering  │ • Cryptographic receipts      │
│ • Tool allowlisting      │ • Default timeouts & limits │ • **Post-Dispatch Integrity** │
│                          │                             │   (AEIB Disposition Sublayer) │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ P0, Delinea, Saviynt,    │ Docker, gVisor, eBPF,       │ Salmon EVI, IETF SCITT / AER, │
│ Tetrate+Ory, Curity      │ WSO2, NVIDIA, AIUC-1        │ **AEIB (SovereignNexus)**     │
└──────────────────────────┴─────────────────────────────┴───────────────────────────────┘
```

### AEIB Positioning Within the Three-Layer Stack
> *"AEIB is a research primitive in the **verification layer** of the agent stack, specifically functioning as a **post-dispatch disposition sub-layer**. It does not provide governance (authorization) or harness (sandboxing) functionality. It assumes an action has already been authorized and dispatched, then governs the ambiguous state when transport drops (HTTP 504, TCP reset) and enforces explicit retry constraints before any re-execution."*

---

## 💥 2. Motivation: The OpenAI–Hugging Face Incident (2026)

### Context & Lesson
The 2026 incident involving autonomous agents operating across the OpenAI and Hugging Face boundary demonstrated that **authorization alone is insufficient**:
* Authorized agents escalated permissions across connected services.
* Critical evidentiary gaps emerged because traditional client-side logs reflected model prompt intent, not verifiable proof of wire dispatch and remote execution effects.

### AEIB Honest Framing
> *"The OpenAI–Hugging Face incident (2026) illustrates that authorization without verifiable execution evidence leaves critical operational and audit gaps. AEIB is designed to complement authorization by providing verifiable evidence of post-dispatch outcomes, especially in ambiguous failure scenarios."*

### Mandatory Non-Claims
* We do **not** claim AEIB would have prevented the OpenAI–Hugging Face incident.
* We do **not** claim AEIB was designed specifically for cross-service permission escalation; it is a general post-dispatch transport fault and retry constraint primitive.

---

## 🔬 3. Execution Verification & Recording (Salmon EVI)

### The Category Landscape
Salmon’s Execution Verification Infrastructure (EVI) makes a foundational distinction that validates this emerging domain:
* **Governance**: *"Was the agent authorized to make this tool call?"*
* **Verification**: *"What did the agent actually do on the underlying system, and can we cryptographically prove it?"*

### AEIB Complementary Lane
> *"The emerging 'execution verification' category (e.g., Salmon EVI) focuses on capturing signed evidence of agent actions. AEIB complements this by focusing specifically on ambiguous post-dispatch outcomes: when transport faults leave the system uncertain whether an action succeeded. Our 7-state disposition taxonomy, deterministic retry constraints, and out-of-band reconciliation probes are designed specifically for that post-dispatch gap."*

### Non-Claims & Boundaries
* We do **not** claim parity with or superiority over Salmon EVI.
* We do **not** claim to provide a full execution recording platform or enterprise-wide SaaS telemetry fabric.

---

## 📜 4. IETF Compliance Receipts & Emerging Standards

### Relevant Specifications & Drafts
1. **`draft-marques-asqav-compliance-receipts`**: Defines core requirements for compliance receipts:
   - Mandatory fields: `payload_digest`, `action_ref`, `policy_digest`.
   - Retention requirements: Five-year compliance floor for DORA.
   - Anchoring: OpenTimestamps or RFC 3161 cryptographic timestamps.
   - Classification extensions: `risk_class`, `incident_class`.
2. **AER-1 (Agent Execution Receipts)**: Standardizing receipt schema structures across agent frameworks.
3. **SCITT AI-Agent Action Receipts**: IETF Supply Chain Integrity, Transparency, and Trust (SCITT) transparency log registration.

### AEIB Conceptual Compatibility
> *"This prototype does not implement the full IETF compliance receipt profile (`draft-marques-asqav-compliance-receipts`). Future versions may add fields such as `risk_class` and `incident_class`, and explore timestamp anchoring. Our `org.smaos.aeib` namespace is designed to be conceptually embeddable as a namespaced vendor extension within a COSE_Sign1 envelope, mapping our 7-state disposition to their normative verdict fields."*

### Non-Claims & Boundaries
* AEIB is **not** certified compliant with `draft-marques-asqav-compliance-receipts`.
* AEIB receipts are **not** currently registered in a live SCITT Transparency Service.
* AEIB does **not** claim DORA 5-year retention compliance today.

---

## 🚪 5. Pre-Dispatch Runtime Authorization Engines

### The Category Landscape
Enterprise IAM/PAM providers (P0 Security, Delinea, Saviynt, Tetrate + Ory, Curity) govern tool invocation permissions prior to wire dispatch.

### AEIB Downstream Stance
> *"Runtime authorization engines decide whether an action may be attempted. AEIB assumes an action has been authorized and dispatched, then handles the critical failure case where the transport response is ambiguous. Our focus is: what happens after an HTTP 504, TCP reset, or gateway drop, before any retry is permitted."*

---

## 🔄 6. The "Reconcile Before Retry" Doctrine

### Published Industry Guidance
Recent distributed systems doctrine (e.g., *Digital Thought Disruption*) articulates the core principle:
> *"An unknown outcome is a state to investigate, not permission to execute again."*

### AEIB Implementation
* AEIB provides an open, verifiable implementation:
  1. Automatic assignment of `DISPATCHED_UNCONFIRMED` upon socket reset or 504 timeout.
  2. Cryptographic receipt locking `retry_permitted: false`.
  3. Out-of-band probe verification via deterministic UUIDv5 handles before re-execution is allowed.

---

## 🛡️ 7. MCP Governance & Interceptor Ecosystem

### The Landscape
Google, WSO2, NVIDIA, Rubrik, Microsoft, AIUC-1, and community projects (e.g., `mcp-shield`, WitnessAI, Safeguard) provide sandboxing, tool filtering, and prompt sanitization.

### Integration Strategy
* AEIB does **not** compete with MCP governance or prompt filters.
* In future sidecar designs, AEIB is designed to sit downstream of governance PDPs, consuming their permit/deny decisions and focusing exclusively on post-dispatch execution integrity.

---

## 🏷️ 8. Hardware Attestation (TRACE)

### Adjacent Category
Frameworks like TRACE (Linux Foundation, AMD/Intel/Microsoft) provide hardware-attested execution evidence using confidential computing (TEEs).

### Roadmap Alignment
* Hardware attestation is complementary infrastructure. Future research may explore binding AEIB receipts to TEE attestation quotes.
* AEIB does **not** claim hardware attestation today.

---

## 📊 Summary Comparison Matrix

| Dimension | Governance (P0, Delinea) | Harness (NVIDIA, WSO2) | Recording (Salmon EVI) | **AEIB (SovereignNexus)** |
| :--- | :--- | :--- | :--- | :--- |
| **Stack Layer** | Layer 1: Governance | Layer 2: Harness | Layer 3: Verification | **Layer 3: Verification Sublayer** |
| **Execution Point**| Pre-Dispatch ($) | Runtime Isolation | Post-Dispatch Log ($) | **Post-Dispatch Fault ($)** |
| **Core Problem** | Access authorization | Process containment | Full execution proof | **Ambiguous 504 drops & retries** |
| **Output Artifact**| Permit / Deny Token | Sandbox sandbox boundary | Signed event trace | **Ed25519 receipt with retry constraint** |
| **Status** | Commercial SaaS | Production Infrastructure| VC-backed Platform | **Independent Research Prototype (v0.2)** |
