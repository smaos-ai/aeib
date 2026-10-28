# 🏛️ EU DORA RTS 2024/1772 Article 17 Compliance Specification

**Automated Major ICT Incident Classification & Settlement Verification for Autonomous AI Agents**

---

## 1. Executive Summary & Legal Context

Under the **Digital Operational Resilience Act (DORA)** and the European Banking Authority / EIOPA / ESMA Joint Regulatory Technical Standards (**RTS 2024/1772 Article 17**), financial entities operating in the European Union are legally mandated to identify, classify, and notify competent supervisory authorities of **major ICT-related incidents**.

When an autonomous AI agent (LangChain, Spring AI, AutoGen, CrewAI) dispatches a mutating payment or ledger transaction and the transport layer encounters an unhandled failure (e.g. `HTTP 504 Gateway Timeout` or `TCP RST`):
- **The Core Failure:** Naive agent SDKs frequently swallow socket timeouts in retry loops or interpret partial HTTP responses as successful commitments, recording a local `CONFIRMED` disposition.
- **The Regulatory Violation:** An unconfirmed transaction that mutates or leaves ledger state uncertain constitutes an **unclassified integrity breach under DORA RTS 2024/1772 Art. 17(1)(c)**.
- **Statutory Penalties:** Failure to classify and report a major ICT incident within the mandatory **4-hour notification window** exposes institutions and Critical ICT Third-Party Providers (CTPPs) to periodic penalty payments of **up to 1% of average daily worldwide turnover**, applied daily for up to 6 months.

---

## 2. DORA Article 17 Incident Severity Classification Lattice

`aeib-receipt-fuzzer` maps wire-level transport faults to DORA RTS criteria:

| Wire Condition | Agent Assertion | SMAOS Enforced State | DORA RTS 2024/1772 Classification | Statutory Reporting Clock |
| :--- | :--- | :--- | :--- | :--- |
| **HTTP 504 Timeout** | `CONFIRMED` | **`UNKNOWN`** | **Major Incident (Integrity & Availability)** | **Initial Notification within 4 Hours** |
| **TCP Reset (RST)** | `FAILED` (Retry) | **`CONFLICT`** | **Major Incident (Double-Spend Hazard)** | **Initial Notification within 4 Hours** |
| **MCP Schema Drift** | `DISPATCH` | **`INVALID_INPUT`** | **Critical Security Event (OWASP MCP03)** | Immediate Audit Halt / Quarantine |
| **HTTP 200 OK** | `CONFIRMED` | **`CONFIRMED`** | Nominal Settlement | Clear / Archived |

---

## 3. Machine-Readable Incident Dossier: `dora_art17_gap_report.json`

During execution, `aeib-receipt-fuzzer` evaluates transport telemetry against the 6-disposition precedence lattice and outputs an EBA-ready incident dossier:

```json
{
  "dora_rts_classification": "4h_major_incident",
  "incidents": [
    {
      "id": "001",
      "payload": "EUR 50,000 to [REDACTED_IBAN]",
      "wire_status": 504,
      "sdk_claim": "CONFIRMED",
      "disposition": "UNKNOWN",
      "flag": "VERIFIED_TOXIC_RECEIPT"
    }
  ],
  "telemetry_source": "wire_level_fuzzer_v0.1",
  "pci_dss_sanitization": "ACTIVE_ZERO_EGRESS",
  "sample_payload_scrubbed": "EUR 50,000 to [REDACTED_IBAN]"
}
```

---

## 4. European Supervisory Authorities (ESA) Register Entry: `RT.01.03`

To satisfy DORA Article 28(3) and the ESA Register of Information requirements for ICT third-party service providers, the engine automatically emits `RT.01.03_vendor_entry.csv`:

```csv
ContractRef,ProviderName,ICTServiceType,Criticality,ExitStrategy
CTR-SMAOS-001,SovereignNexus,S17,Critical,Documented
```

This entry certifies that agent-mediated execution endpoints have an active, documented fail-closed exit strategy that halts state corruption upon transport failure.
