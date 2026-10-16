# AEIB Technical Standards Synchronization Dossier (October 2026)

**Document Reference:** `AEIB-STD-SYNC-2026-10`  
**Classification:** Technical Architecture & Standards Alignment  
**Epistemic Boundary Notice:**  
*Evaluated under the stated model. Permitted words: observed, tested, evaluated, configured, prototype, scaffold. AEIB produces structured technical evidence that an entity may associate with its risk management, incident disclosure, and governance workflows. AEIB does not claim universal compliance, legal warranty, or automated conformity with any regulation or standard.*

---

## 1. Executive Summary: What We Researched & Synthesized

A comprehensive review of contemporary standards, regulatory technical specifications, and open-source infrastructure across Europe and international bodies reveals five major shifts affecting autonomous AI agents:

```text
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                 CONTEMPORARY AI GOVERNANCE & REGULATORY LANDSCAPE (OCT 2026)              │
├──────────────────────────┬─────────────────────────────┬──────────────────────────────────┤
│ BODY / JURISDICTION      │ SPECIFICATION / STANDARD    │ TECHNICAL IMPLICATION FOR AEIB   │
├──────────────────────────┼─────────────────────────────┼──────────────────────────────────┤
│ CEN-CENELEC JTC 21       │ prEN 18282 (Cybersecurity)  │ Formalizes defense against model/│
│ (EU AI Act Harmonization)│ & EN 18286:2026 (QMS)       │ data poisoning and evasion.      │
├──────────────────────────┼─────────────────────────────┼──────────────────────────────────┤
│ European Supervisory     │ Delegated Reg (EU) 2025/301 │ Strict major ICT incident clock: │
│ Authorities (EBA/ESMA)   │ & Implementing Reg 2025/302 │ 4h initial, 72h intermediate.    │
├──────────────────────────┼─────────────────────────────┼──────────────────────────────────┤
│ IETF SCITT Working Group │ draft-emirdag-scitt-ai-*    │ AgentInteractionRecord (AIR) in  │
│                          │ draft-mih-scitt-capsule-*   │ COSE_Sign1 for verifiable audit. │
├──────────────────────────┼─────────────────────────────┼──────────────────────────────────┤
│ Linux Foundation         │ Model Context Protocol (MCP)│ Standardizes tool interoperability│
│ Agentic AI Foundation    │ Gateway Security Specs      │ but introduces tool rug-pulls.   │
├──────────────────────────┼─────────────────────────────┼──────────────────────────────────┤
│ OpenTelemetry            │ GenAI Semantic Conventions  │ Canonical telemetry namespace for│
│                          │ v1.28.0+ / v1.30.0+         │ agent actions and tool calls.    │
└──────────────────────────┴─────────────────────────────┴──────────────────────────────────┘
```

---

## 2. CEN-CENELEC JTC 21: The Harmonized Standards Baseline

Under European Commission standardization requests M/593 and M/613, CEN-CENELEC Joint Technical Committee 21 (JTC 21) established the technical criteria required for presumptions of conformity under the EU AI Act:

### 2.1 prEN 18282: Cybersecurity Specifications for AI Systems (Article 15)
- **Scope:** Technical robustness and protection against AI-specific vulnerabilities.
- **Specific Threats Addressed:**
  - *Data & Tool Output Poisoning:* Attackers injecting instructions into retrieved data or tool responses to hijack the agent reasoning loop.
  - *Adversarial Input Evasion:* Subtle parameter alterations evading static keyword or classifier guardrails.
  - *Confidentiality Breaches:* Sensitive identifier leakage (e.g. PAN, IBAN, API keys) through authorized tools.
- **AEIB Alignment:**
  - Evaluated in `tests/test_mitre_adversarial_matrix_at48_at51.py` under tests AT48 (Content Injection), AT49 (Result Poisoning), and AT50 (Exfiltration via Allowed Tool).
  - Enforces exact payload binding to the RFC 8785 Content-Addressed Action Identifier (`CAID`) so poisoned model context cannot mutate wire execution parameters.

### 2.2 EN 18286:2026: Quality Management System for EU AI Act (Article 17)
- **Scope:** Provides a product-focused QMS tailored to AI system lifecycle control, distinguishing itself from general organizational frameworks (like ISO 9001/ISO 42001).
- **Epistemic Calibration:** Adherence to EN 18286 provides a presumption of conformity for *quality management processes*, but does not inherently validate runtime execution correctness.
- **AEIB Role:** AEIB produces reproducible run-time evidence packages (`artifacts/adversarial/`, `artifacts/phase3/`) that quality auditors can inspect independently.

### 2.3 prEN 18229: Logging and Transparency (Article 12)
- **Scope:** Automated recording of operational events over the AI lifecycle to ensure post-market traceability.
- **AEIB Alignment:** Implemented via cryptographic hash chains (`Station3ContinuousLedger`) and the shared incident evidence format (`schemas/incident_evidence_v1.schema.json`).

---

## 3. DORA Technical Regulations: Implementing & Delegated Acts

For financial entities subject to the Digital Operational Resilience Act (Regulation (EU) 2022/2554), the European Supervisory Authorities (EBA, EIOPA, and ESMA) adopted binding Level 2 measures:

### 3.1 Commission Delegated Regulation (EU) 2025/301 (RTS on Incident Timelines)
Establishes the mandatory submission schedule for major ICT-related incidents:
1. **Initial Notification:** Submitted within **4 hours** of incident classification (and no later than **24 hours** from detection).
2. **Intermediate Report:** Submitted within **72 hours** of the initial notification.
3. **Final Report:** Submitted within **1 month** of the intermediate report or operational stabilization.

### 3.2 Commission Implementing Regulation (EU) 2025/302 (ITS on Standard Templates)
- Establishes harmonized machine-readable fields for incident notification.
- Identifies critical attributes: governing authority handle, root-cause classification, technical impact assessment, and third-party dependency involvement.

### 3.3 How AEIB Supports DORA Compliance Workflows
- **Evidence Plane Separation:** AEIB separates untrusted model behavior from authorized execution and observed consequences. When a transport failure occurs (e.g. HTTP 504), AEIB records:
  - `authority_revocation_state`: enum
  - `boundary_verdict`: `EFFECT_INDETERMINATE`
  - `reproducibility_manifest_sha256`: verifiable hash
- **Rapid Initial Notification Support:** By providing machine-readable, Ed25519-signed incident bundles within milliseconds of boundary trips, internal incident-response teams receive the exact cryptographic traces needed to meet the strict 4-hour reporting deadline.

---

## 4. IETF SCITT: The Transparency Receipt Frontier

The IETF Supply Chain Integrity, Transparency, and Trust (SCITT) Working Group is standardizing verifiable receipts for autonomous systems:

### 4.1 Relevant Internet-Drafts
- **`draft-emirdag-scitt-ai-agent-execution`:**
  - Proposes the **AgentInteractionRecord (AIR)**, structured as an RFC 9052 `COSE_Sign1` statement.
  - Decouples the **Issuer** (the organization operating the agent boundary) from an external **Transparency Service** (which appends the statement to a verifiable Merkle tree and issues a counter-signature receipt).
- **`draft-mih-scitt-agent-action-capsule`:**
  - Encapsulates tool invocations, parameters, and return hashes into signed action capsules.

### 4.2 AEIB Integration Architecture
- AEIB’s native format utilizes RFC 8785 JCS canonical JSON with Ed25519 signatures.
- For SCITT interoperability, AEIB provides `v1.1-roadmap/rfc9052_cose_profile.py`, encoding the canonical payload into RFC 8949 CBOR wrapped in an RFC 9052 `COSE_Sign1` envelope with algorithm `-8` (EdDSA).
- This allows AEIB receipts to be registered asynchronously with external SCITT transparency ledgers without introducing out-of-process network latency into the hot execution path.

---

## 5. Model Context Protocol (MCP) Security & Gateways (2025–2026)

With MCP transitioning under the **Linux Foundation's Agentic AI Foundation**, tools are standardized across agent runtimes. However, public research identifies critical security vectors:

### 5.1 Observed Attack Vectors
1. **Tool Rug-Pull / Dynamic Schema Drift:** A compromised MCP server returns an altered tool schema or modified parameter descriptions after the initial handshake, tricking the agent into executing unintended commands.
2. **Ambient Credential Leakage:** MCP servers holding long-lived static bearer tokens in environment variables or passing raw API keys through prompt context.
3. **SSRF / Unbounded Egress:** Malicious tool responses redirecting agent tool callers to internal infrastructure endpoints (e.g., metadata services `169.254.169.254`).

### 5.2 AEIB Pre-Dispatch Defenses
- **Protocol Negotiation Enforcement (`MCP01`):** Enforces explicit MCP protocol version negotiation (pinned to `2025-06-18`) and rejects unnegotiated connections before socket allocation.
- **Canonical Action Digest Binding:** Requires tool parameters to be cryptographically bound to the single-use execution ticket. If an MCP server mutates schemas or descriptions, the `CAID` diverges and dispatch is blocked fail-closed.
- **Zero Ambient Credentials:** All target tokens are vaulted out-of-band; agents hold only opaque capability handles.

---

## 6. Synthesis: What AEIB Implements vs. What Remains External

| Capability Domain | AEIB Native Boundary Role | External Enterprise Dependency |
| :--- | :--- | :--- |
| **Incident Evidence** | Produces signed, 3-plane incident bundles (`incident_evidence_v1`). | Legal / Compliance teams classify incidents and submit DORA / AI Act reports. |
| **Adversarial Interception** | Rejects indirect injection, tool exfiltration, and defense tampering at the socket edge. | Enterprise EDR / SIEM ingests AEIB telemetry for organizational threat hunting. |
| **Audit Continuity** | Appends SHA-256 hash chains and signs receipts with Ed25519. | External SCITT ledger / long-term cold archive for multi-year regulatory retention. |
| **Tool Execution** | Enforces $O(1)$ zero-allocation admission, `EO-1` pre-dispatch intent, and transport latches. | Downstream API targets maintain idempotent write endpoints and status readback APIs. |
