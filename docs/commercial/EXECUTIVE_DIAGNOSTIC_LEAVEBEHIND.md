# SMAOS Execution Integrity Diagnostic & Reconstructable Evidence Audit
## Executive Leave-Behind & Risk Committee Checklist (ISO/IEC 42006 & DORA Alignment)

**Prepared by:** SovereignNexus (Prague, Czech Republic)  
**Target Audience:** Chief Information Security Officers (CISOs), Chief Risk Officers (CROs), Heads of AI Governance & Internal Audit  
**Document Classification:** Commercial Briefing / Executive Leave-Behind  
**Release Baseline:** AEIB v0.2.0 • RFC 8785 JCS • RFC 9052 COSE_Sign1 (`alg: -8`, Ed25519)  
**Date:** September 2026  

---

### 1. Executive Summary: The Ambiguity Cliff in Autonomous AI

When an autonomous AI agent initiates a consequential action—such as a funds transfer, production database mutation, ERP entitlement update, or privileged data export—the primary operational hazard is neither "hallucination" nor conversational prompt injection.

The primary operational hazard is **the Ambiguity Cliff at the network socket layer**:

> **The action may have been transmitted across the wire, but its external effect cannot yet be confirmed.**

```text
PROPOSAL OPTIMIZATION (Microsoft SkillOpt / Competitors)       TEMPORAL STANDING & EXECUTION SAFETY (SMAOS AEIB)
┌────────────────────────────────────────────────────────┐     ┌─────────────────────────────────────────────────────────┐
│ • Focus: T_0 Prompt & Skill Hyperparameter Tuning     │     │ • T_0: JCS Payload Canonicalization & Authority Binding │
│ • Goal: Make the model 20% smarter at proposing actions│  vs │ • ΔN: Socket Trap catches 504 Timeouts & Wire-Faults   │
│ ❌ Fails at ΔN: Blind retries on dropped TCP connection │     │ • T_n: Out-of-Band State Probe before Consequence Binds │
│                                                        │     │ ✅ Outcome: Mints Ed25519 Evidence That Survives Audit  │
└────────────────────────────────────────────────────────┘     └─────────────────────────────────────────────────────────┘
```

* **Models propose ($T_0$)**: SkillOpt, guardrail libraries, and prompt tuners optimize what the agent *asks* to do.
* **Governance decides ($T_n$)**: SMAOS intercepts the Model Context Protocol (MCP) call, evaluates present standing out-of-band when a network drop ($\Delta N$) occurs, and prevents catastrophic "phantom retries."
* **Evidence survives**: Mints RFC 9052 `COSE_Sign1` Ed25519-signed receipts, preserving the **Accountability Chain** so CISOs and CFOs can sign DORA and EU AI Act disclosures without personal legal liability.

For example, an **HTTP 504 Gateway Timeout** or socket reset merely indicates that an intermediate reverse proxy or gateway did not receive a timely upstream response. It does not establish whether the downstream ledger, core banking engine, or database committed the operation before the socket severed.

If an autonomous workflow treats this transport ambiguity as a failure and triggers an automated retry without strict idempotency and out-of-band reconciliation, it introduces **duplicate execution, double-spend, and unmonitored compliance violations**.

---

### 2. The 7-State Disposition Taxonomy: Beyond Binary Success/Failure

Standard agent frameworks collapse execution into a crude binary: `success` or `failure`. Under regulatory audit (DORA Art. 17, ISO/IEC 42006), binary status is legally inadmissible. SMAOS enforces a **7-state disposition engine**:

| State | Statutory Meaning | Runtime Enforcement |
| :--- | :--- | :--- |
| **`OUTCOME_VERIFIED`** | Physical execution confirmed downstream with cryptographic receipt. | Consequence committed; thread unlocked. |
| **`ACK_UNVERIFIED`** | Wire ACK received, but downstream register state unconfirmed. | Awaiting background reconciliation. |
| **`DISPATCHED_UNCONFIRMED`** | Socket timeout (`HTTP 504`) or TCP RST post-dispatch. | **FAIL-CLOSED QUARANTINE**: All agent retries blocked. |
| **`RECONCILIATION_NOT_FOUND`** | Out-of-band probe proves downstream register never committed. | Safe to retry under explicit human approval. |
| **`RECONCILIATION_FAILED`** | Downstream state inconsistent or corrupted during fault. | Incident escalated to ICT Risk Committee. |
| **`PROBE_EXCEPTION`** | Reconciliation probe itself unreachable or timed out. | Preserves quarantine; locks agent credentials. |
| **`REFUSED`** | Authority token expired, JIT check failed, or policy violated. | Execution rejected ex-ante prior to wire egress. |

---

### 3. The ISO/IEC 42006 "Reconstructable Evidence" Audit Checklist

Under **ISO/IEC 42006** and **EU AI Act Article 12**, post-incident investigations cannot rely on conversational LLM chat logs, prompt-evaluation scores, or unverified application metrics. Regulatory auditors require **reconstructable, tamper-evident telemetry** proving what occurred at the physical network boundary.

Use this 6-point checklist to evaluate whether your autonomous agent architecture satisfies the reconstructable evidence threshold:

| # | Audit Criterion | Forensic Question for Risk & Engineering Leads | Risk Level |
|---|---|---|:---:|
| **1** | **Canonical Payload Integrity (RFC 8785 JCS)** | *Does your audit trail contain a cryptographically normalized SHA-256 hash of the exact JSON payload transmitted to the API before dispatch?* | **HIGH** |
| **2** | **Cryptographic Idempotency Binding** | *Is a deterministic UUIDv5 key derived from the canonical payload and verified by the target backend before execution?* | **CRITICAL** |
| **3** | **Fail-Closed Ambiguity Quarantine** | *When an HTTP 504 or socket reset occurs, does the runtime immediately halt autonomous retries and enter a `DISPATCHED_UNCONFIRMED` quarantine state?* | **CRITICAL** |
| **4** | **Authority Freshness (<100ms JIT)** | *Is the policy authorization evaluated immediately prior to socket dispatch (sub-100ms), or does the workflow rely on stale pre-session tokens?* | **HIGH** |
| **5** | **Immutable COSE_Sign1 Work Receipts** | *Are dispatch outcomes recorded as Ed25519-signed Merkle-tree receipts (RFC 9052 / RFC 9162) capable of offline, zero-egress third-party verification?* | **HIGH** |
| **6** | **Out-of-Band Target Reconciliation** | *Does the system enforce an automated query to a dedicated reconciliation endpoint (`/reconcile`) before any human or automated retry is released?* | **CRITICAL** |

---

### 4. The Execution Integrity Diagnostic (Observe-Only)

SovereignNexus offers a **fixed-scope observe-only Diagnostic Audit** designed to quantify your institution's exposure to post-transmission ambiguity and double-execution risk without disrupting production operations:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              DIAGNOSTIC ENGAGEMENT SCOPE                               │
├────────────────────┬────────────────────┬────────────────────┬─────────────────────────┤
│ Zero Code Changes  │ Zero Credentials   │ Air-Gapped Silicon │ Fixed Turnaround        │
│ No production      │ No secret keys,    │ 100% processed     │ 48-Hour Rapid Forensic  │
│ proxy or runtime   │ API credentials,   │ locally with zero  │ or 5-Day Full Spectrum  │
│ modification       │ or database logins │ cloud data egress  │ Diagnostic Review       │
└────────────────────┴────────────────────┴────────────────────┴─────────────────────────┘
```

#### Four Core Forensic Measurements:
1. **Approval Linkage**: Does supplied evidence show a verifiable cryptographic link between the policy authorization and the resolved action released at runtime?
2. **Retry Exposure**: When an outcome is ambiguous after dispatch, do available records show a deterministic idempotency key, a status-query path, or reconciliation evidence?
3. **Authority Freshness**: Is there empirical evidence that authority was evaluated immediately prior to action release (JIT delta $<100\,\text{ms}$), or are stale pre-session grants reused?
4. **Evidence Continuity**: Can supplied records cleanly distinguish not-dispatched, unconfirmed, accepted, refused, and target-confirmed outcomes following an unexpected transport failure?

---

### 5. DORA RTS 2025/301 Annex II Dual-Clock Reporting Engine

For financial entities subject to **Regulation (EU) 2022/2554 (DORA)** and **Commission Delegated Regulation (EU) 2025/301**, SMAOS automates initial major incident reporting without manual human log stitching:

$$\text{Statutory Deadline} = \min\left(T_{\text{classification}} + 4\,\text{hours},\; T_{\text{awareness}} + 24\,\text{hours}\right)$$

#### In-Process DuckDB/chDB Analytics & Governance Locks:
- **Zero Cloud Egress**: Evaluates local JSONL receipts on host silicon in **13.5 ms**.
- **Automated Artifact**: Generates pre-filled `dora_annex_ii_prefill.json`.
- **Absolute Governance Review Locks**:
  - `severity_status`: Locked to **`PENDING_HUMAN_REVIEW`** (agents never self-classify).
  - `submission_status`: Locked to **`NOT_SUBMITTED`** (agents never transmit regulatory filings autonomously).

---

### 6. Diagnostic Deliverables & Commercial Structure

#### Commercial Tiers:
- **€1,500 Rapid Diagnostic**: 48-hour observe-only assessment of one high-consequence agent workflow against synthetic/redacted trace exports.
- **5-Day Comprehensive Enterprise Diagnostic**: Multi-workflow cluster review, live wire-fault injection simulation in staging, and formal CISO / Risk Committee readout.

#### Executive Deliverables:
1. **Event-Level Forensic Findings**: Quantitative audit of wire-fact overclaim rates (instances where agent logs claimed success without network confirmation).
2. **Reconstructable Evidence Gap Analysis**: Defensible scoring against ISO/IEC 42006, EU AI Act Art. 12/14, and DORA Art. 17.
3. **Double-Spend & Retry Vulnerability Map**: Identification of unquarantined retry loops across dead sockets.
4. **Prioritized Remediation Blueprint**: Concrete, 5-point engineering roadmap to integrate RFC 8785 canonicalization and fail-closed state machines.

---

### 7. Important Limits & Regulatory Disclaimer

SMAOS supports evidence collection and runtime-control objectives relevant to incident reconstruction, human oversight, and operational resilience.

**Explicit Boundaries:**
- SMAOS does not guarantee exactly-once execution on non-idempotent third-party backends.
- SMAOS does not prove a remote state change from a network timeout alone.
- SMAOS does not replace target-side idempotency validation.
- SMAOS does not certify formal regulatory compliance (compliance certification remains the exclusive prerogative of national competent authorities and accredited audit bodies).

---

### 8. Institutional Contact & Diagnostic Scheduling

**SovereignNexus**  
Corporate Status: Independent Research Initiative (Czech Republic incorporation pending)  
Founder & Independent Researcher: Andrii Leukhin (`andrejlo123@gmail.com`)  
Academic Partner: Lviv Polytechnic National University (IKNI / Prof. Natalia Shakhovska)  
Open-Source AEIB Benchmark: [https://github.com/andriileukhin/SovereignNexus](https://github.com/andriileukhin/SovereignNexus)  
Verification Runner: `.venv/bin/python3 scripts/verify.py provenance/receipts` (16/16 receipts verified)

---

*Legal Status: This 5-Day Diagnostic is an independent research activity. A formal Czech limited-liability entity (s.r.o.) will be established prior to commercial production deployment. No warranties are provided for this synthetic prototype.*
