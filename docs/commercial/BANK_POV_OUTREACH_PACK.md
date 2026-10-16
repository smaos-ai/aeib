# Bank PoV Outreach Pack: Autonomous Financial Execution Boundary

**Document Reference:** `AEIB-BANK-POV-v1.1`  
**Classification:** Enterprise Banking PoV & Commercial Engagement Pack  
**Audience:** Bank Chief Risk Officers (CRO), Chief Information Security Officers (CISO), Heads of AI Governance, and Enterprise Architects.  
**Epistemic Boundary Notice:**  
*Evaluated under the stated model. Permitted terms: observed, tested, evaluated, configured, prototype, scaffold. AEIB produces operation-level evidence that a financial institution can associate with its ICT third-party management, incident management, and compliance programs. AEIB does not maintain the DORA Register of Information (Article 28), perform vendor due diligence, warrant system-wide conformity, or automate regulatory filings.*

---

## 1. Executive Summary & Defensible Value Proposition

When autonomous AI agents interact with core banking APIs (payments, loan disbursements, customer refunds), traditional perimeter security faces an unaddressed operational reality: **network and transport ambiguity**.

If an agent dispatches an HTTP `POST /refunds` and the connection drops mid-flight (HTTP 504 Gateway Timeout, TCP RST, or connection reset):
* Traditional API gateways and client runtimes classify the request as a failed call and trigger an automated retry storm.
* If the bank's backend actually processed the debit before the transport drop, every retry duplicates financial loss.

**The AEIB Product Wedge:**  
AEIB is an out-of-process, wire-level execution integrity boundary that introduces four deterministic controls:
1. **Pre-Dispatch Parameter Integrity (\\(\text{CAID}\\)):** Binds candidate tool mutations to an RFC 8785 JSON Canonicalization Scheme (JCS) SHA-256 digest before wire commitment.
2. **\\(T_n\\) Temporal Standing Check:** Verifies policy epoch, authorization validity, and unrevoked credentials at the exact moment of dispatch; stale requests are dropped with **strictly 0 egress bytes**.
3. **Post-Dispatch Fault Latching (`EFFECT_INDETERMINATE`):** Latches unconfirmed mutations into an indeterminate state with `retry_safe: False` until reconciled out-of-band.
4. **Target-Attested Reconciliation (`refund_status_v1`):** Direct cryptographic verification against the downstream target API before declaring success or failure.

---

## 2. Defensible Competitive Gap Hypothesis

> **Competitive Gap Hypothesis:**  
> Based on public materials reviewed on current archive dates, we did not find documented evidence that the evaluated commercial and open-source agent governance products combine exact pre-dispatch action binding, durable dispatch intent (`EO-1`), post-dispatch transport-ambiguity handling (`EFFECT_INDETERMINATE`), and target-attested financial reconciliation (`refund_status_v1`). This is an evaluated review gap, not proof that no competitor possesses these capabilities.

---

## 3. Calibrated 3-Level Trust Hierarchy

Financial auditors and bank risk teams require clarity on cryptographic provenance:

| Trust Level | Attribution Tier | What It Proves | What It Does NOT Prove |
| :--- | :--- | :--- | :--- |
| **Level 1** | **Agent-Signed** | Proves an internal signer inside the agent runtime generated and signed a record. | Does not establish that the runtime host was uncompromised or that the action was executed. |
| **Level 2** | **Boundary-Signed (Restraint)** | Proves a controlled out-of-process boundary observed or authorized a dispatch (e.g. AEIB Restraint Records). | Does not by itself establish target-side state change or financial settlement. |
| **Level 3** | **Target-Attested (Receiver)** | Proves an authenticated downstream target reported an operation-specific status under a versioned contract (`refund_status_v1`). | Subject to the target's key custody, API schema accuracy, and host security model. |

---

## 4. Bounded Regulatory Mapping (DORA & EU AI Act)

AEIB provides structured, machine-readable evidence for bank compliance and audit teams:

### 4.1 Digital Operational Resilience Act (DORA - Regulation (EU) 2022/2554)
* **What AEIB Delivers:**
  * **Article 17 & 19 (Incident Management & Reporting):** When a transport drop occurs, AEIB emits an Ed25519-signed incident record with explicit enums (`authority_revocation_state`, `boundary_verdict: EFFECT_INDETERMINATE`, `reproducibility_manifest_sha256`). This provides the exact cryptographic trace needed to meet the **4-hour initial incident notification window** established in Commission Delegated Regulation (EU) 2025/301.
  * **Article 11 (Response and Recovery):** Deterministic rollback coordination and automated probe escalation via out-of-band reconciliation.
* **What AEIB Does NOT Do:**
  * AEIB does **not** maintain the DORA Article 28(3) Register of Information for ICT third-party contracts.
  * AEIB does **not** conduct third-party vendor audits or automate regulatory submissions to National Competent Authorities (NCAs).

### 4.2 EU AI Act (Regulation (EU) 2024/1689)
* **Article 12 (Record-Keeping & Logging):** Real-time continuous ledger hash chains (`chainTip`) linking candidate proposals to terminal receipts.
* **Article 14 (Human Oversight):** Dual-control STEP_UP gates and immediate kill-switch latches for high-value financial thresholds.
* **Article 15 (Cybersecurity & Robustness):** Enforces zero wire allocation and pre-dispatch rejection under indirect prompt injection (AT48 / MITRE T1659), result poisoning (AT49 / T1565), and tool exfiltration (AT50 / T1048).

---

## 5. The 6-Week Commercial Proof-of-Value (PoV) Pilot

We offer Tier-1 banks a structured, low-risk deployment pattern designed to observe and evaluate without disrupting production core banking infrastructure:

```mermaid
flowchart LR
    W1["Week 1:<br/>Scoping & Architecture"] --> W2["Week 2:<br/>Shadow Mode (Passive)"]
    W2 --> W3["Week 3:<br/>Active Enforcement"]
    W3 --> W4_6["Weeks 4-6:<br/>Reconciliation & Exit Dossier"]
```

### Week 1: Scoping & Architecture
- Deploy AEIB as a sidecar proxy or container tap in front of a staging banking API (e.g. refund/disbursement endpoint).
- Pin target API capability schemas and generate test Ed25519 keypairs.

### Week 2: Shadow Mode (Passive Observation)
- Intercept agent tool calls in passive mode.
- Compute \\(\text{CAID}\\) and standing verdicts without blocking wire traffic.
- Measure baseline metrics: duplicate request rate, counterfactual blocked rate, and parameter drift.

### Week 3: Active Pre-Dispatch Enforcement
- Enable active inline enforcement.
- Actions with invalid epochs, altered parameters, or unallowlisted targets are dropped fail-closed.
- Verify that rejected mutations transmit **0 network bytes** to the target banking system.

### Weeks 4–6: Target-Attested Reconciliation & Exit Dossier
- Connect the `refund_status_v1` target readback probe.
- Execute simulated fault injection: HTTP 504 timeouts and TCP RST drops.
- Verify `EFFECT_INDETERMINATE` latching, automated probe resolution, and receipt generation.
- Deliver the final **PoV Evidence Dossier** with offline verification tooling.

---

## 6. Pilot Integration Prerequisites

To conduct a 6-week PoV, the bank provides:
1. **Target Readback Endpoint:** An authenticated API endpoint returning transaction status given an operation reference (`refund_status_v1`).
2. **Staging Environment Access:** Network connectivity between the agent sandbox, AEIB proxy container, and the mock/staging core API.
3. **Custody Configuration:** Dedicated Ed25519 test keys (or PKCS#11 / HSM handles) for boundary and target receipt signing.
