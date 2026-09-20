# 📄 Statement of Work (SOW) — Staging Provenance & Evidence Integrity Diagnostic

**Engagement Ref:** SMAOS-SOW-2026-STG-01  
**Provider:** SMAOS Trust Infrastructure / SovereignNexus · Lead Auditor: Andrii Leukhin (`andrejlo123@gmail.com`)  
**Client:** [Client Legal Entity Name]  
**Effective Date:** [Date] · **Delivery Window:** 5 Business Days from Ingestion  
**Fixed Fee:** **€1,500 EUR (Net)** · **Air-Gap Invariant:** 100% Zero-Egress (`network_mode: "none"`)  

---

## 1. 🎯 Purpose & Executive Summary

The **Staging Provenance & Evidence Integrity Diagnostic** is a rapid, non-invasive forensic evaluation designed to uncover hidden transactional drop hazards, uncoordinated retry double-spends, and silent audit omissions in autonomous AI agent harnesses (LangGraph, Temporal, AutoGen, CrewAI, or bespoke microservices) *before* production deployment.

Under **DORA RTS 2024/1772 (Art. 17)** and **BaFin Circular 10/2021 (MaRisk/BAIT)**, discovering unmitigated transaction faults in live production triggers a mandatory 4-hour regulatory notification clock. This diagnostic establishes a **Pre-Production Safe Harbor** by verifying agent execution traces against physical wire reality in an isolated staging environment.

---

## 2. 🔬 Scope of Work & Diagnostic Battery

SMAOS will execute the following diagnostic stages using the zero-dependency `ocr-audit-engine` and `smaos_verify.wasm`:

1. **Multi-Format Telemetry Ingestion:**
   - Ingestion of up to 500,000 lines of client staging execution logs (Splunk, Elastic/ELK, Datadog, OpenTelemetry, or CSV) using `splunk_to_smaos.py`.
   - 0-byte external network transmission; all computation executes locally on client hardware or sanitized air-gapped test runners.

2. **The 8 Compliance Moats Verification:**
   - **Moat 1 (Proof-or-Stop Gate):** Detects false-positive `CONFIRMED` claims where upstream transport returned HTTP 504 timeouts or TCP drops.
   - **Moat 2 (Bitemporal Anti-Collision):** Identifies race hazards, duplicate idempotency keys, and clock drifts ($|T_s - T_v| > 50\text{ms}$).
   - **Moat 3 (Deterministic Saga Compensation):** Simulates idempotent `REVERT_TRANSFER` actions preserving the net ledger invariant ($\sum \Delta_{\text{net}} = 0.00$).
   - **Moat 4 (Ring-0 Anti-Omission Interceptor):** Identifies un-capsulated outbound socket connections bypassing audit trails.
   - **Moat 5 (Monotonic Capability Attenuation):** Detects unconstrained sub-delegation, spending cap bypasses, and unhedged tool sprawl.
   - **Moat 6 (Hardware-Rooted KMS Integrity):** Validates TPM 2.0 PCR-11/17 quotes and offline DID Revocation Lists (DRL).
   - **Moat 7 (Pure Rust WASM Verification):** Benchmarks attestation verification latency ($10.42\,\mu\text{s}\;p_{99}$).
   - **Moat 8 (Pre-Access Compliance Gating):** Enforces CNCF SPIFFE SVID and IETF SCITT `draft-mih-scitt-agent-action-capsule-04` admission criteria.

---

## 3. 📦 Day-5 Concrete Deliverables Package

Upon completion of the 5-day evaluation, Client will receive:

| # | Deliverable | Description | Format |
|:---|:---|:---|:---|
| **D1** | **Executive Forensic Audit Dossier** | Complete Provenance Coverage Report detailing causal integrity percentage, unmitigated failure vectors, and total monetary exposure halted. | PDF + Markdown |
| **D2** | **DORA Art. 17 Incident Gap Report** | Statutory incident mapping against all 7 EU DORA criteria, documenting major incident avoidance for supervisory authorities (BaFin, FINMA, ČNB). | `dora_art17_gap_report.json` |
| **D3** | **Saga Reconciliation Log** | Proof of net ledger conservation ($\sum \Delta_{\text{net}} = 0.00$) under simulated downstream timeouts and network partitions. | Machine-Readable JSONL |
| **D4** | **Remediation Patch (`fix.patch`)** | Drop-in 5-line remediation patch (`@proof_or_stop` decorator + bitemporal guard) verified against client's test suite with 0.00% line drift. | Unified Diff (`.patch`) |
| **D5** | **1-on-1 Technical Debrief** | 45-minute terminal walkthrough with Lead Platform Architects and CISO explaining findings, risk mitigation, and continuous guardrails. | Live Screen Session |

---

## 4. 🚀 Commercial Bridge: Continuous Governance Expansion

Following the delivery of the diagnostic, Client may seamlessly transition to continuous automated protection:

```
┌───────────────────────────────┐     ┌───────────────────────────────┐     ┌───────────────────────────────┐
│     PHASE 1: DIAGNOSTIC       │     │    PHASE 2: CI/CD SENTINEL    │     │   PHASE 3: PRODUCTION GUARD   │
│  5-Day Staging Forensic Audit │ ──> │   Automated Pre-Merge Engine  │ ──> │  eBPF + Enclave Live Shield   │
│       €1,500 (One-Time)       │     │      €3,500 / month Net       │     │      €7,500 / month Net       │
└───────────────────────────────┘     └───────────────────────────────┘     └───────────────────────────────┘
```

### Phase 2: Pre-Commit CI/CD Sentinel (€3,500 / month)
* **Scope:** Continuous integration gate blocking PRs that introduce non-deterministic tool calls or unhedged mutations.
* **Features:** Offline AST heuristic verification, automated mock injection tests, PR-level Provenance Coverage checks.
* **Coverage:** Up to 10 agent repositories / execution harnesses.

### Phase 3: Production eBPF & Hardware-Rooted Kernel Guard (€7,500 / month)
* **Scope:** Continuous real-time protection across production Kubernetes clusters and container runners.
* **Features:** Ring-0 eBPF socket interceptor (<10ms dangling socket kill-switch), TPM 2.0 / AMD SEV-SNP enclave signing, sub-microsecond WASM ledger verification, and quarterly statutory audit packs.
* **SLA:** 99.99% availability, 1-hour critical incident containment response.

---

## 5. 🔒 Non-Disclosure & Security Commitments

1. **Zero Data Retention / Zero Egress:** The diagnostic executes entirely within Client's isolated infrastructure or on offline ephemeral memory runners. No client code, prompts, customer PII, or credentials are ever transmitted externally.
2. **Deterministic Reproducibility:** All findings are backed by line-indexed JSONL offsets and reproducible offline shell commands.
3. **Governing Law:** This Statement of Work is governed by the laws of [Germany / Switzerland / Czech Republic].

---

## 6. ✍️ Acceptance & Authorization

**For Client:**  
Signature: ___________________________  
Name: _______________________________  
Title: ________________________________  
Date: ________________________________  

**For SMAOS Trust Infrastructure (SovereignNexus):**  
Signature: *Andrii Leukhin*  
Name: Andrii Leukhin  
Title: Founder & Principal Forensic Auditor  
Date: [Date]  
