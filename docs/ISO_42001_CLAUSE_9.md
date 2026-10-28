# 📜 ISO/IEC 42001:2023 Clause 9: Runtime Audit Evidence Specification

**Overcoming the "Container Fallacy" via Objective Wire-Settlement Proof**

---

## 1. The ISO/IEC 42001 Standard & Clause 9 Requirements

**ISO/IEC 42001:2023** is the international standard for Artificial Intelligence Management Systems (AIMS). 

Under **Clause 9 (Performance Evaluation)** and **Clause 9.2 (Internal Audit)**, certified organizations must evaluate the performance and effectiveness of their AI systems. Lead ISO auditors explicitly mandate:
1. **Objective Evidence:** Written governance policies and prompt-level guardrails are legally insufficient. Organizations must produce verifiable runtime records that controls actually executed at the moment of failure.
2. **Continual Monitoring:** AI decision outcomes must be continuously monitored for divergence, hallucinations, and ungrounded execution claims.

---

## 2. The DEMM-Bench "Container Fallacy" (arXiv:2606.20634)

Standard enterprise agent architectures rely on **Container Presence**:
> *"Is a JSON log file present in Datadog or OpenTelemetry? Is an Ed25519 signature attached to the receipt?"*

Research from the Decision Evidence Maturity Model (**DEMM-Bench**, arXiv:2606.20634) reveals that relying on trace-present and schema-present logs results in a **75% overclaim rate**. Agents sign receipts claiming execution success even when the downstream TCP socket was severed or the remote ledger aborted.

**SMAOS enforces Property-Level Sufficiency:**
Instead of checking whether a receipt exists, `smaos-audit` and `aeib-receipt-fuzzer` verify whether the claimed disposition is physically substantiated by wire-level acknowledgments.

---

## 3. Runtime Verification Controls

To achieve Stage 1 and Stage 2 ISO 42001 certification, institutions deploy the SMAOS polyglot verification controls:

### JVM / Spring Boot Control: `ProofOrStopFilter.java`
Acts as an ISO 42001 Annex A.9 runtime control intercepting Spring `WebClient` requests:
```java
// Hard boundary invariant: Evidence Absent => UNKNOWN
return Mono.error(new AgentDiscrepancyException(
    "ISO 42001 Control A.9: Wire dropped with no settlement receipt. State forced to UNKNOWN."
));
```

### Python Agent Control: `@proof_or_stop`
Wraps agent tools with bitemporal receipt verification before mutating persistent state.

---

## 4. Auditor Evidence Dossier Deliverables

For each audit engagement, the engine compiles:
- **`TRI_Scorecard.md`**: Quantifies the Toxic Receipt Index (% of ungrounded model overclaims).
- **`audit_trace.mermaid`**: Visual sequence diagram showing the exact millisecond discrepancy between wire transport and model assertion.
- **`dora_art17_gap_report.json`**: Machine-readable evidence bundle linking ISO 42001 Clause 9 performance metrics to European DORA regulatory reporting.
