# 🛡️ SMAOS | Air-Gapped AI Agent Wire-Truth Engine (`v0.2.0`)

> **Deterministic boundary integrity and ambiguity resolution for autonomous AI agent workflows.**

[![Release](https://img.shields.io/badge/release-v0.2.0-blue.svg)](https://github.com/sovreignnexus/smaos/releases/tag/v0.2.0)
[![Prototype](https://img.shields.io/badge/format-AEIB__JSON__ED25519__PROTOTYPE-blueviolet.svg)](#operational-limits--disclaimers)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Egress](https://img.shields.io/badge/egress-0%20bytes%20(air--gapped)-success.svg)](#privacy--zero-egress-invariant)

> 📖 **Full Architectural Specification**: See [`docs/architecture/AEIB_SPECIFICATION.md`](docs/architecture/AEIB_SPECIFICATION.md) for the definitive technical formulation of the 6-stage pipeline and structural fault breakdown.

---

## 🏛️ The Problem: The "Container Fallacy"

When an autonomous payment agent dispatches a mutating tool call and the gateway drops with an **HTTP 504 Gateway Timeout**, standard agent SDKs (LangChain, Spring AI) catch the transport exception and falsely log **`CONFIRMED`**.

* **The Result:** The AI agent claims success, the database records the transfer, but the clearing ledger never moved the money.
* **The Systemic Risk:** Triggers 4:00 AM reconciliation drift and mandatory 4-hour **DORA Article 17 EBA incident reporting clocks**.

---

## ⚡ 60-Second Quickstart (100% Local / Air-Gapped)

### Option 1: Native Python (Zero Dependencies)
```bash
git clone https://github.com/sovereignnexus/aeib-receipt-fuzzer.git
cd aeib-receipt-fuzzer
python3 run.py
```

### Option 2: Air-Gapped Docker Container
```bash
docker compose up
```
*Navigates to local dashboard at `http://127.0.0.1:8765`.*

---

## 🛒 The "Container Shop" Menu (`docker-compose.yml`)

Configure your target stack and fault profiles locally via simple environment variables:

```yaml
services:
  smaos-audit:
    image: sovereignnexus/aeib-receipt-fuzzer:v0.1.0
    ports:
      - "127.0.0.1:8765:8765"
    environment:
      RUNTIME: "java21"             # java21 | python
      FRAMEWORK: "spring-boot"      # spring-boot | langchain4j | fastapi
      FAULT_MODES: "504,TCP_RST"    # 504 | TCP_RST
      PRIVACY_GUARD: "true"         # In-memory IBAN/PAN/JWT scrubbing
      COMPLIANCE_EXPORT: "DORA,ISO42001,ATH"
```

---

## 🛡️ Key Safety Invariants

1. **In-Memory Privacy Scrubber:** IBANs (`[REDACTED_IBAN]`), card PANs, and JWT bearer tokens (`[REDACTED_JWT]`) are scrubbed in-memory *before* any disk writes.
2. **Proof-or-Stop Invariant:** Hard precedence override forcing unconfirmed state transitions:
   $$\text{Evidence Absent} \implies \text{UNKNOWN}$$
3. **Polyglot Remediation:** Exports `ProofOrStopFilter.java` for Spring Boot `WebClient` and `fix.patch` for Python.

---

## 📊 Audit Deliverable Bundle (`./audit_out/`)

Every local run outputs:
* `dora_art17_gap_report.json` — EBA RTS 2024/1772 major incident JSON report.
* `audit_trace.mermaid` — Visual sequence diagram mapping wire drops vs. SDK overclaims.
* `ProofOrStopFilter.java` — Drop-in fail-closed filter for Spring Boot microservices.
* `index.html` — Interactive dark-mode dashboard for local CISO review.

---

## ⚠️ Operational Limits & Disclaimers

1. **Synthetic Prototype**: The current AEIB v0.2.0 package operates strictly on synthetic benchmark vectors and simulated transport outcomes. It is an engineering review deliverable, not a production security control.
2. **Deterministic Serialization**: Payloads use a deterministic JSON subset (sorted keys, compact separators) as an engineering precursor; it is **not RFC 8785 validated**.
3. **Adapter Dependency**: Real-world reconciliation requires target-side idempotency adapters (`ServerIdempotencyAdapter`).
4. **Non-Certification**: Provides evidence capture to support internal audit trails. Does not constitute statutory compliance certification under DORA or the EU AI Act.

---

## 📜 License & Author

Apache License 2.0. Developed by **Andrii Leukhin** (Independent Researcher & Founder, SovereignNexus project, `andrejlo123@gmail.com`).  
*Note: SovereignNexus is an independent research initiative (incorporation pending in the Czech Republic).*

## 📚 Prior Art & Interoperability Targets

AEIB aims for conceptual alignment with emerging literature and standards. The following frameworks are cited as **informational prior art and interoperability targets**, rather than formally tested standards in this benchmark:
- **AER-1 / AEB (Agent Execution Receipt / Agent Execution Boundary)**
- **AAC (Agent Action Capsule)**
- **CAID (Causal Action Identifier)**
- **EffectMatch & EMILIA**
- **GRIP (Gateway Receipt Integrity Protocol)**

## Prior-Art Matrix & Citations

| Framework / Protocol | Primary Focus | Relationship to AEIB | Status |
|---|---|---|---|
| **AER-1** (`draft-zambo-aer1-04`) | Execution receipts for tool calls | Informational prior art; adjacent receipt format | Interoperability target (untested) |
| **AEB** (`draft-schrock-action-evidence-boundary-07`) | Evidence boundary enforcement | Conceptual overlap on execution boundaries | Interoperability target (untested) |
| **AAC** (`draft-mih-scitt-agent-action-capsule-05`) | SCITT agent action capsules | Envelope encapsulation standard | Interoperability target (untested) |
| **CAID** (`draft-schrock-canonical-action-identifier-04`) | Canonical Action Identifiers | Identity scheme consumed by AEIB | Consumed identifier |
| **EffectMatch** (`arXiv:2609.31301`) | Post-execution reconciliation | Prior art on side-effect reconciliation | Informational citation |
| **Authority at Commit Time** (`arXiv:2609.31490`) | Dynamic authorization gates | Complementary pre-commit gate | Informational citation |
| **EMILIA Protocol** (`emilia-protocol`) | Multi-agent interaction audit | Broader governance and interaction audit | Informational citation |
| **GRIP** (`grip-protocol`) | Gateway receipt integrity | Gateway-level receipt binding | Informational citation |

### Citation List
- **`draft-zambo-aer1-04`**: *Agent Execution Receipts (AER-1)* (September 29, 2026).
- **`draft-schrock-action-evidence-boundary-07`**: *Action Evidence Boundary* (September 26, 2026).
- **`draft-mih-scitt-agent-action-capsule-05`**: *Agent Action Capsule* (September 27, 2026).
- **`arXiv:2609.31301`**: *EffectMatch: Deterministic Side-Effect Reconciliation for Autonomous Systems* (September 25, 2026).
- **`arXiv:2609.31490`**: *Authority at Commit Time: Dynamic Privilege Bounds for Tool Calls* (September 25, 2026).
- **`draft-schrock-canonical-action-identifier-04`**: *Canonical Action Identifier (CAID)* (September 28, 2026).
- **EMILIA Protocol**: `emilia-protocol` GitHub repository (Informational).
- **GRIP**: `grip-protocol` (Informational).
