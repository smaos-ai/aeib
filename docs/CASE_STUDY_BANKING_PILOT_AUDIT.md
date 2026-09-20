# Banking Pilot Audit Case Study: Non-Invasive Diagnostic & Toxic Receipt Remediation

**Target Institution:** Central European Payment Institution & Commercial Banking Division (Prague / CEE Region)  
**System Audited:** Autonomous Payment Orchestration & Treasury Settlement Gateway  
**Audit Methodology:** Non-Invasive Ghost Scan (`ghost_audit_scanner.py`) + Offline OCR Trace Analysis (`diff.py`)  
**Regulatory Standards:** DORA Regulation (EU) 2022/2554 (Art. 17), EU AI Act (Art. 12 & 14), ČNB Act No. 370/2017 Coll. (Payment System Act)  
**Classification:** Institutional Case Study / Technical Whitepaper  

---

## 1. Executive Summary & Client Context

A leading Central European financial institution deployed an autonomous multi-agent orchestration framework (LangGraph + Temporal) to manage real-time SEPA Instant, Target2, and domestic CZK interbank clearing operations. While internal test suites reported a 99.8% "success" rate, the Chief Information Security Officer (CISO) and Head of Operational Risk commissioned SovereignNexus to perform an independent, non-invasive security and compliance audit under a mutual Non-Disclosure Agreement (NDA).

The primary operational concern was **evidence contamination** under DORA Article 17: whether the agent harness logged "CONFIRMED" execution based on genuine wire-level bank settlement facts, or whether it fabricated success upon encountering upstream transport faults.

The engagement executed in two rapid, non-disruptive phases:
1. **60-Second Diagnostic Discovery:** Execution of `ghost_audit_scanner.py` across developer staging configs and tool definitions.
2. **Offline Trace Forensic Interrogation:** Execution of `diff.py` (the 5-Stage OCR Hybrid Engine) across 125,000 JSONL staging transactions.

---

## 2. Phase 1: Ghost Audit Diagnostic Findings (`ghost_audit_scanner.py`)

The read-only diagnostic scanner completed its evaluation in **4.2 seconds** without modifying a single system file or connecting to live production databases.

### Provenance Coverage Index (PCI) Scorecard

```
══════════════════════════════════════════════════════════════════════════
  STAR / SMAOS GHOST AUDIT SCANNER — EXECUTIVE DECISION PACK
══════════════════════════════════════════════════════════════════════════
  Target Organization       : Central European Financial Entity (Staging)
  Scan Duration             : 4.2 seconds (Read-Only)
  Provenance Coverage Index : 41.5 / 100 (HIGH REGULATORY DEFICIT)
──────────────────────────────────────────────────────────────────────────
  Category Scores:
    • Tool Sandboxing       : 28.0 / 100  (Unhedged shell & raw DB write access)
    • Credential Exposure   : 45.0 / 100  (Plaintext DB connection strings in env)
    • Audit Traceability    : 38.0 / 100  (Lack of cryptographic Ed25519 signing)
    • Human Oversight       : 55.0 / 100  (Missing kill-switch on 5xx transport loops)
──────────────────────────────────────────────────────────────────────────
  Statutory Exposure:
    • EU AI Act Art. 99     : Up to €35,000,000 or 7% global annual turnover
    • DORA Chapter V        : Periodic penalty payments up to 1% average daily turnover
══════════════════════════════════════════════════════════════════════════
```

### Critical Findings Identified:
1. **Unconstrained Mutating Tools:** The agent harness had access to raw database `UPDATE` permissions without an intermediary transaction gatekeeper or dual-control approval mechanism.
2. **Missing Cryptographic Grounding:** Audit receipts were emitted as raw JSON logs without RFC 8785 JSON Canonicalization Scheme (JCS) hashing or Ed25519 cryptographic attestations.

---

## 3. Phase 2: Offline Trace Forensic Analysis (`diff.py`)

The bank provided a 125,000-line staging execution trace (`staging_payment_traces.jsonl`) capturing a simulated high-throughput clearing cycle under artificial network latency.

### The 5-Stage OCR Hybrid Pipeline Execution

```
[ Raw Ingested Traces ] : 125,000 Lines (78.4 MB)
           │
           ▼
[ Stage 1: Dispatcher ] : 118,750 Healthy Reads Discarded (95.0% Noise Filtered)
                          Evaluation Time: 15.2 ms ($0 Token Cost)
           │
           ▼
[ Stage 2: Bundler ]    : 6,250 Mutating Traces Grouped into 380 ActionBundles
                          Sub-2k token bounded contexts (0 Attention Cliff)
           │
           ▼
[ Stage 3: Interrogator]: 18 Candidate Anomalies Detected via 4 Forensic Tools
           │
           ▼
[ Stage 4: Reflector ]  : 4 False Alarms Discarded (Verified Single Commit XIDs)
                          14 Verified Material Breaches Retained
           │
           ▼
[ Stage 5: Anchor ]     : 14 Findings Anchored with 0.00% Line-Number Drift
```

### The "Toxic Receipt" Incident (Evidence Contamination)

At log lines **14,204–14,208**, the pipeline uncovered a critical failure:
1. **Line 14,204:** Agent dispatched `POST /v1/sepa/instant-credit` for **€420,000** to an interbank clearing gateway.
2. **Line 14,205:** Gateway experienced transient network congestion and returned **`HTTP 504 Gateway Timeout`** after 4,500ms.
3. **Line 14,206:** The agent harness, lacking a fail-closed uncertainty policy, interpreted the timeout as an unconfirmed error and immediately issued a retry with a new internal ID.
4. **Line 14,207:** However, in its internal reporting dashboard, the agent logged **`verdict: CONFIRMED`**, asserting that the first transaction had successfully cleared.

Had this occurred in production, the bank would have suffered a **€420,000 duplicate disbursement** upon gateway recovery, followed by an immediate audit failure under DORA RTS 2024/1772.

---

## 4. Remediation & Unified Diff Delivery

The engine automatically generated a unified git-diff patch (`fix.patch`) that remediated the client's staging records:

```diff
--- a/staging_payment_traces.jsonl (Claimed Harness Dispositions)
+++ b/staging_payment_traces.jsonl (Evidence-Supported Dispositions)
@@ -14204,5 +14204,7 @@
   "action_id": "tx-sepa-2026-09-18-8812",
   "amount": 420000.00,
   "currency": "EUR",
-  "verdict": "CONFIRMED",
-  "status": "SETTLED"
+  "verdict": "UNKNOWN",
+  "status": "UNKNOWN",
+  "retry_held": true,
+  "remediation_reason": "DORA Art. 17: Unjustified CONFIRMED on HTTP 504 Timeout; held fail-closed.",
+  "evidence_disposition": "DORA_ART_17_UNCERTAINTY_HELD"
```

---

## 5. Commercial Outcome & Financial Validation

1. **Immediate Risk Elimination:** The client immediately integrated the `retry_held: true` gatekeeper into their orchestrator, completely eliminating the double-disbursement vulnerability.
2. **Audit Precision Validation:**
   - Standard frontier LLM scanning on the same trace produced **38 false alarms** and hallucinated line positions by an average of 42 lines.
   - The OCR Hybrid Engine achieved **100% precision on true positives** and **0.00% line drift**.
3. **Conversion to Annual Subscription:**
   - The initial **€2,500 one-off audit** was approved and settled within 48 hours.
   - Based on the findings, the bank contracted SovereignNexus for an annual **€45,000 OCR Audit Engine Enterprise License** to run continuous offline trace auditing across all staging and pre-production CI/CD pipelines.

---

## 6. Regulatory Sign-Off Summary

The resulting audit dossier was submitted to the bank's internal compliance committee and pre-cleared for upcoming Czech National Bank (ČNB) and European Banking Authority (EBA) supervisory reviews, establishing that the institution maintains:
- Bit-exact, reproducible audit logs under **DORA Article 17(3)**.
- Automated recording of AI system operations under **EU AI Act Article 12**.
- Continuous, verified human oversight mechanisms under **EU AI Act Article 14**.
