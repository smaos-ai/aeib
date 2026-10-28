# 📄 STATEMENT OF WORK & ORDER FORM
## Staging Forensic Diagnostic Audit — Autonomous Agent Wire-Fact Verification

**Order Form Ref:** SMAOS-ORD-2026-STG-01  
**Execution Date:** [Execution Date]  
**Delivery Window:** Five (5) Business Days from Staging Trace Ingestion  
**Total Fixed Fee:** **€1,500 EUR (Net)** — Flat Fixed Price, Zero Hidden Fees  

---

### BETWEEN:
1. **SMAOS Trust Infrastructure / SovereignNexus**  
   Principal Forensic Auditor: **Andrii Leukhin** (`andrejlo123@gmail.com`)  
   Jurisdiction: Prague, Czech Republic  
   *(Hereinafter referred to as the **"Provider"**)*

2. **[Client Legal Entity Name]**  
   Registered Address: [Client Address]  
   Company ID / Tax ID: [Client ICO / VAT]  
   Authorized Representative: [Representative Name, Title]  
   *(Hereinafter referred to as the **"Client"**)*

---

## 1. 🎯 Purpose & Scope of Diagnostic

The Provider shall perform an air-gapped forensic audit of Client's pre-production / staging autonomous agent harnesses (e.g., LangGraph, AutoGen, CrewAI, Temporal, or custom microservice workers) to identify unanchored state assertions, silent transport drops, and statutory non-compliance under **EU DORA (Regulation 2022/2554, Art. 17 & 28)** and **ČNB / EBA Guidelines**.

### 🔬 Technical Diagnostic Specifications:
- **Trace Ingestion Volume:** Ingestion of up to **250 historical or synthetic staging execution traces** (Splunk, Elastic/ELK, Datadog, OpenTelemetry, or JSONL).
- **Fault-Injection Stress Battery (6 Modes):**
  1. *HTTP 504 Gateway Timeout:* Evaluates worker assertion when reverse-proxy drops outbound wire.
  2. *TCP Reset (RST):* Tests handling of abrupt socket termination during payment/ledger mutation.
  3. *HTTP 409 Conflict:* Tests duplicate idempotency handling and retry storms.
  4. *Malformed Wire Payload:* Tests fail-closed validation under corrupted upstream schemas.
  5. *Unanchored Assertion:* Detects false-positive `CONFIRMED` claims where no wire proof exists.
  6. *Bitemporal Clock Skew:* Identifies race conditions where $|T_{\text{stated}} - T_{\text{wire}}| > 50\text{ms}$.
- **Quantitative Overclaim Rate:** Calculation of Client's exact Wire-Fact Overclaim Rate:
  $$\text{Overclaim Rate} = \frac{N_{\text{false\_confirmed}}}{N_{\text{unverified\_mutations}}} \times 100\%$$

---

## 2. 📦 The 5-Artifact Day-5 Delivery Bundle

Within five (5) business days of trace ingestion, the Provider shall deliver the following complete bundle:

| # | Deliverable Artifact | Technical Format | Description |
| :--- | :--- | :--- | :--- |
| **D1** | **Executive Forensic Audit Dossier** | PDF & Markdown | Formal assessment containing calculated Overclaim Rate, blast radius analysis, and Board Risk Committee summary. |
| **D2** | **DORA Article 17 Incident Gap Report** | `dora_art17_gap_report.json` | Statutory evaluation mapping identified wire-fact drifts against the 7 mandatory EU DORA major ICT incident criteria. |
| **D3** | **xBRL-CSV Register Entry** | `RT.01.03_vendor_entry.csv` | Pre-formatted, EBA-compliant Register of Information entry ready for ČNB supervisory inspection. |
| **D4** | **Drop-In Remediation Patch** | `remedy.patch` (Unified Diff) | Verified 5-line `@proof_or_stop` decorator and `smaos-mcp` proxy configuration that neutralizes detected drifts with zero code refactoring. |
| **D5** | **Executive Debrief & Walkthrough** | 45-Min Live Screen Share | Detailed terminal walkthrough with VP Engineering and CISO explaining findings, risk mitigation, and continuous guardrails. |

---

## 3. 🔒 Air-Gap & Zero-Egress Invariants

The Provider guarantees the following operational invariants during the engagement:
1. **Zero External Network Egress:** All diagnostic software executes locally on Client hardware or isolated container runners (`docker run --network none`). Zero outbound bytes of telemetry are emitted.
2. **Zero PII & Data Retention:** The Provider does not ingest, copy, or retain customer PII, secret keys, or business databases. All analysis operates strictly on sanitized transaction execution metadata.
3. **Reproducibility Guarantee:** Every finding in the Executive Dossier is cross-referenced with exact line-indexed JSONL offsets and reproducible offline shell commands.

---

## 4. 💳 Commercial Terms & Expansion Options

1. **Fixed Fee:** €1,500 EUR (Net of VAT). Payable within fifteen (15) days of delivery of the 5-Artifact Bundle.
2. **Payment Method:** Corporate Bank Transfer / Invoice or Corporate Credit Card.
3. **Optional Expansion Paths (Client Discretion):**
   - **Phase 2 (Pre-Commit CI/CD Sentinel):** €3,500 / month — Automated pre-merge pull-request gate blocking non-deterministic agent tool calls.
   - **Phase 3 (Production eBPF & Enclave Shield):** €7,500 / month — Continuous Ring-0 eBPF socket monitoring and AMD SEV-SNP / Intel TDX cryptographic settlement sealing.

---

## 5. ⚖️ General Legal Provisions

- **Governing Law & Jurisdiction:** This Agreement shall be governed by and construed in accordance with the laws of the **Czech Republic** (or the country of the Client's registered office upon request). Any disputes shall be settled by the competent courts of Prague.
- **Confidentiality:** Both parties agree to maintain strict confidentiality regarding all proprietary systems, code, and audit findings disclosed during this engagement.

---

## ✍️ EXECUTION & ACCEPTANCE

IN WITNESS WHEREOF, the authorized representatives of the parties have executed this Order Form as of the date set forth below.

```
FOR THE CLIENT:                            FOR THE PROVIDER:
[Client Legal Entity Name]                 SMAOS Trust Infrastructure / SovereignNexus

Signature: ___________________________     Signature: ___________________________
                                                      Andrii Leukhin
Name:      ___________________________     Name:      Andrii Leukhin
Title:     ___________________________     Title:     Founder & Principal Auditor
Date:      ___________________________     Date:      [Execution Date]
```
