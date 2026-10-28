# Multi-Jurisdictional Regulatory Compliance Profiles
## Statutory Cross-Walk for Autonomous AI Agent Infrastructure

**Governing Standard:** DORA RTS 2024/1772 · FINMA Circular 2023/1 · BaFin BAIT (Circular 10/2021) · ČNB Decree No. 7/2018 Coll.  
**Classification:** Institutional Regulatory Architecture Addendum  
**Engine:** Sovereign Multi-Agent OS (`smaos-ai`) · Air-Gapped Verification  

---

### 1. Executive Context & The 2026 European Regulatory Shift

With the formal enactment of the **Digital Omnibus amendment (July 24, 2026)**, the European Union shifted the compliance enforcement timeline for **EU AI Act High-Risk AI systems (Annex III) to December 2, 2027**. 

Consequently, leading enterprise procurement with "High-Risk AI Act compliance" is a strategic mismatch for financial institutions. In contrast, financial sector regulators across Switzerland, Germany, and the Czech Republic are actively enforcing **ICT operational resilience and incident classification mandates that are binding right now**:

1. **DORA (Regulation (EU) 2022/2554) & RTS 2024/1772:** In effect since January 17, 2025. Major incident notification clocks (4 hours initial / intermediate updates) are actively audited. 19 Critical ICT Third-Party Providers (CTPPs) have been designated.
2. **FINMA Circular 2023/1:** Binding operational risk and cyber resilience rules governing critical IT infrastructure in Swiss financial entities.
3. **BaFin Circular 10/2021 (BAIT):** Supervisory requirements for IT systems and contingency management in German credit institutions.
4. **ČNB Decree No. 7/2018 Coll.:** Operational and technical rules for financial market infrastructure and ICT risk in the Czech Republic.

---

### 2. Multi-Jurisdictional Statutory Mapping Matrix

| Jurisdiction | Regulatory Authority & Instrument | Statutory Requirement | SMAOS Substrate Enforcement |
|:---|:---|:---|:---|
| **Switzerland 🇨🇭** | **FINMA Circular 2023/1** *(Operational Risks & Resilience)* & **Circular 2018/3** *(Outsourcing)* | **Strict Client Identifying Data (CID) Protection:** No unauthorized cross-border data transfer. Independent auditability of critical outsourced IT functions without reliance on cloud provider self-attestations. | • Enforces `network_mode: "none"` Ring-0 eBPF socket isolation.<br>• Mints local Ed25519/FIPS 204 SCITT receipts offline.<br>• Zero cloud telemetry egress (`0.000 Bytes`). |
| **Germany 🇩🇪** | **BaFin Circular 10/2021 (BAIT)** & **MaRisk AT 7.2 / AT 7.3** | **IT Security, Logging, and Contingency Management:** Systems must guarantee tamper-evident logging of transactions, active detection of operational anomalies, and automated recovery procedures for failed processing runs. | • Out-of-Band Wire Reflector (`reflector.py`) overrides model overclaims on 504 timeouts.<br>• Deterministic Saga Reconciler executes idempotent compensating reversals ($\sum \Delta_{\text{net}} = 0.00$).<br>• Monotonic Merkle DAG ensures tamper-evident audit trails. |
| **Czech Republic 🇨🇿** | **ČNB Decree No. 7/2018 Coll.** & **Fintech Sandbox Guidelines** | **ICT Risk Management & Transactional Non-Repudiation:** Real-time logging of financial market transactions, strict segregation of duties, human intervention capabilities, and 7-year immutable audit retention. | • Human-in-the-Loop Resumable Cognitive Execution (RCE) cockpit with cryptographic operator sign-offs.<br>• Anti-Omission Kernel Guard intercepting un-capsulated socket traffic.<br>• Pre-formatted xBRL-CSV exports for supervisory submission. |
| **European Union 🇪🇺** | **DORA RTS 2024/1772** *(Commission Delegated Regulation)* | **Article 17 Incident Classification:** Rigorous tracking of 7 statutory criteria (clients affected, data losses, transaction value, economic impact, duration, geographical spread, reputational impact). | • Automated incident classification engine with 24h initial and 4h intermediate regulatory clocks.<br>• Standalone WASM verifier (`smaos_verify.wasm`) evaluating Merkle inclusion in 10.42 µs $p_{99}$. |

---

### 3. Deep-Dive: Jurisdiction-Specific Operational Controls

#### A. Swiss FINMA Circular 2023/1 (Operational Risk & CID Protection)
* **The Mandate:** Principle 3 (Cyber Risk Management) and Principle 4 (Critical Data Protection) require institutions to maintain continuous cryptographic control over Client Identifying Data (CID). Relying on overseas cloud provider logs (CTPPs) introduces cross-border jurisdictional risk.
* **The SMAOS Enforcement:** 
  1. The entire audit and attestation pipeline operates air-gapped (`network_mode: "none"`).
  2. BBS+ pairing-based verifiable credentials enable **selective field redaction**, allowing external supervisory bodies to mathematically verify execution integrity and Merkle proofs without exposing client identities or payment IBANs.

#### B. German BaFin BAIT (Circular 10/2021) & MaRisk AT 7.2
* **The Mandate:** Section 5 (User Access Management), Section 6 (IT Operations), and Section 10 (Contingency Management) demand that credit institutions prevent unauthorized autonomous mutations and ensure deterministic rollback when third-party services fail.
* **The SMAOS Enforcement:**
  1. When an upstream core banking API drops (HTTP 504), the **Saga Reconciler** prevents uncoordinated retry storms by freezing the action at `verdict: UNKNOWN`.
  2. Bitemporal query probes against database commit logs verify whether the transaction settled. If uncommitted, an idempotent `REVERT_TRANSFER` action is automatically dispatched, enforcing the zero net drift invariant:
     $$\sum \Delta_{\text{net}} = 0.00$$

#### C. Czech ČNB Decree No. 7/2018 Coll. (ICT Systems & Sandbox Integration)
* **The Mandate:** Sections 12–18 mandate strict operational logging, separation of environments, and explicit human oversight mechanisms for automated algorithmic decision systems.
* **The SMAOS Enforcement:**
  1. The **Resumable Cognitive Execution (RCE) Cockpit** captures atomic snapshots of paused agent execution states (AST callstack, pending socket frames, memory diffs).
  2. Resuming or aborting a halted transaction requires a cryptographically signed token (`sig:ed25519:...`) from an authorized compliance officer, satisfying dual-control regulatory rules.
  3. Pre-formatted integration templates are aligned with the Czech AI Sandbox (`fintechsandbox.cz`) and ČNB Data Box (`cyrj9gf`).

---

### 4. Enterprise Procurement Implementation Guidelines

When engaging enterprise procurement and compliance committees:
1. **Never pitch high-risk AI Act compliance** (Annex III is deferred to Dec 2027; CISOs will deprioritize).
2. **Anchor to DORA RTS 2024/1772, FINMA 2023/1, and BaFin BAIT** (Active, binding, heavily audited).
3. **Offer the Staging Provenance Audit (€1,500 fixed fee)** as a pre-production safe harbor that uncovers silent omissions and 504 retry hazards without triggering mandatory regulatory incident reporting clocks.
