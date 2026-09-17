# SovereignNexus / SMAOS — Agent-Effect Integrity (AEI)

**Open Source Core & Staging Verification Harness for Autonomous AI Agents**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Standard](https://img.shields.io/badge/standard-RFC%208785%20JCS-green.svg)](docs/SPEC.md)
[![DORA](https://img.shields.io/badge/compliance-DORA%20Art.%2017(3)-orange.svg)](docs/THREAT_MODEL.md)

---

## 🏛️ The Core Thesis: Property-Level Sufficiency

Existing developer tooling focuses almost exclusively on **Container Presence**:
> *"Is a JSON trace file present? Is an Ed25519 signature attached?"*  
> Merely proving a log string was written and signed is a commodity that provides zero guarantee of real-world state settlement.

**SMAOS focuses on Property-Level Sufficiency**:
> *"Does the receipt prove downstream settlement or merely dispatch?"*  
> *"Did the harness preserve UNKNOWN when the payment gateway timed out?"*  
> We evaluate whether the claimed disposition is strictly justified by wire-level evidence.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CONTAINER PRESENCE VS. PROPERTY SUFFICIENCY           │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTAINER PRESENCE (Commoditized / Existing 50+ Tools)                      │
│   "Is a JSON trace file present? Is an Ed25519 signature attached?"          │
│   → Merely proves a log string was written and signed.                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ PROPERTY-LEVEL SUFFICIENCY (The AEI Architectural Focus)                    │
│   "Does the receipt prove downstream settlement or merely dispatch?"        │
│   "Did the harness preserve UNKNOWN on a 504 timeout?"                       │
│   → Evaluates whether the claimed disposition is justified by wire evidence. │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔬 The Six-Disposition Order of Precedence

Under ambiguous network conditions (HTTP 504 timeouts, connection drops, network partitions), standard harnesses emit cryptographically valid signatures asserting `CONFIRMED` or `EXECUTED`. This creates **Evidence Contamination** under DORA Art. 17(3).

SMAOS enforces a strict, fail-closed precedence cascade:

```text
INVALID_INPUT → MISSING_EVIDENCE → CONFLICT → REFUSED → CONFIRMED → UNKNOWN
     ①               ②               ③          ④          ⑤          ⑥
```

`UNKNOWN` is the **fail-safe terminus**: if no affirmative evidence from the system of record confirms external settlement, the action state MUST remain `UNKNOWN` with `retry_held: true` ($\Delta = 0$ conservation invariant).

---

## 🕷️ AEIB Receipt Fuzzer & Toxic Receipt Detector

We provide a zero-dependency local CLI harness (`scratch/aeib-receipt-fuzzer/`) to test whether your harness preserves uncertainty or emits Toxic Receipts:

```bash
cd scratch/aeib-receipt-fuzzer
python3 demo_killshot.py
```

### 5 Verified Scenarios:
1. **Clean Pass-Through**: Valid RFC 8785 JCS + ES256 envelope $\rightarrow$ `CLEAN_PASS`
2. **Dropped Signature**: Stripped cryptographic envelope $\rightarrow$ `TOXIC_RECEIPT_DETECTED`
3. **JCS Canonicalization Tampering**: Injected payload mutation $\rightarrow$ `TOXIC_RECEIPT_DETECTED`
4. **SCITT Timestamp Rollback**: Replayed stale sequence timestamp $\rightarrow$ `TOXIC_RECEIPT_DETECTED`
5. **Adversarial Loan Interception**: Silent in-transit edit (€1.85M $\rightarrow$ €1.90M) halted ex-ante via canonical digest mismatch $\rightarrow$ `HALT: digest_mismatch`

---

## 🔄 Non-Intrusive Reconciliation Adapters

In production, `CONFIRMED` cannot be claimed from API responses alone. SMAOS specifies read-only probes that verify state directly against systems of record:

* **PostgreSQL**: Transaction ID (`xid`) commit status verification via `txid_status`.
* **AWS S3**: Object `ETag` and version ID verification at target bucket paths.
* **Apache Kafka**: Committed partition offsets matching target `action_id`.
* **Stripe (Test Mode)**: `Idempotency-Key` headers cross-checked against settlement status.

---

## 🏛️ Sovereign Governance Substrate & Regulatory Roadmap

### ✅ Milestone 1 Achieved: Local-First Execution & Pre-Execution Safety
* **Pre-Execution Fail-Closed Gates**: Intercepts tool dispatches at the wire and kernel boundary before any side effect occurs.
* **Wire-Fault Simulation**: Tests harness state preservation under simulated HTTP 504 timeouts and dropped sockets, enforcing `verdict: UNKNOWN` rather than writing false `CONFIRMED` success logs.
* **Cryptographic Provenance**: Generates RFC 8785 JCS-canonicalized Merkle DAG receipts signed with Ed25519 keys for every execution.
* **Zero Egress**: Runs 100% air-gapped on local hardware under `network_mode: "none"`.

---

### 🎯 Next Target Milestone: December 2, 2027 (EU AI Act Annex III Deadline)
Under the **EU AI Act (Regulation 2024/1689)** as amended by Digital Omnibus Regulation (EU 2026/1744), the statutory enforcement date for **standalone High-Risk AI systems (Annex III)** is **December 2, 2027**. This applies to all autonomous agent workflows operating in high-risk categories:
1. **Biometrics & Biometric Categorization**
2. **Critical Infrastructure Management** (Water, gas, electricity, cloud systems)
3. **Educational & Vocational Assessment**
4. **Employment, Worker Management & Access to Self-Employment**
5. **Access to Essential Private & Public Services** (e.g., Credit Scoring, Loan Approvals, Healthcare)
6. **Law Enforcement**
7. **Migration, Asylum & Border Control**
8. **Administration of Justice & Democratic Processes**

---

### 🧪 Automated Rule & Testing Substrate for Annex III (Articles 9–15)
This repository serves as an automated test harness and evidence generation engine for Articles 9–15 compliance:

| Statutory Requirement | Governance Substrate Mapping | Technical Evidence Produced |
| :--- | :--- | :--- |
| **Article 9: Risk Management** | Bitemporal ledger tracking post-market evaluation and risk registers throughout the lifecycle. | `agentacct.db` audit traces & risk classification logs. |
| **Article 12: Record-Keeping** | Automatic, tamper-evident event recording over the system's operational lifetime. | SHA-256 Merkle DAG receipts signed with Ed25519 (IETF SCITT profile). |
| **Article 13: Transparency** | Machine-readable system boundaries, capability disclosures, and limitations. | Auto-generated Model Cards & System Boundary manifests. |
| **Article 14: Human Oversight** | Pre-execution fail-closed gates holding retries and enforcing human veto authority. | Resumable Cognitive Execution (RCE) interrupts & stop-button logs. |
| **Article 15: Cybersecurity & Robustness** | Local-first, air-gapped container isolation preventing prompt injection and exfiltration. | Substrate measurement receipts & 0-byte egress network traces. |

---

### ⚖️ Conformity Assessment Pathway: Annex VI Self-Assessment
Under **Article 43(2)** of the EU AI Act, standalone software falling under Annex III categories undergoes an **Internal Conformity Assessment (Annex VI)**. **No third-party Notified Body is required** for standalone software self-assessment.

Running this test harness automatically compiles the mandatory **Annex IV Technical Dossier** directly from real execution traces, allowing enterprise engineering teams to self-certify compliance for December 2, 2027 deployment.

---

## 💼 Commercial Offer: 5-Day Staging Forensic Audit (€2,500 Fixed Fee)

We offer a high-impact, fixed-fee diagnostic engagement to stress-test your AI agent harnesses before production deployment.

### 📋 Engagement Scope (5 Business Days)
* **Day 1: Wire-Level Baseline Capture**: Ingest up to 250 local staging traces or replay logs into the AEI verification pipeline.
* **Day 2: Fault Injection & Fuzzing**: Run our non-blocking proxy against your tool dispatcher across all 6 fault modes (504 Timeout, TCP RST, 409 Conflict, Signature Drop, JCS Poison, Replay).
* **Day 3: Evidence Contamination Scan**: Detect instances where your agents sign `CONFIRMED` without verified settlement.
* **Day 4: Remediation Plan**: Deliver concrete code patches for fail-closed state machines and idempotency retry holders.
* **Day 5: Executive Audit Dossier**: 1-page CISO/Risk Committee briefing mapping your harness against DORA Art. 17 and EU AI Act Art. 12 auditability requirements.

### 🏰 The Audit-to-Corpus Flywheel
```
Paid Staging Audit (€2,500) ──► Real Failure Mode ──► Anonymized JSON Vector ──► Open Conformance Suite
```
Every forensic audit enriches our open **AEI Conformance Corpus**, converting real-world edge cases into reproducible public benchmarks while keeping client data strictly confidential.

**Inquiries & Booking:** [andrejlo123@gmail.com](mailto:andrejlo123@gmail.com) · Fixed Fee: **€2,500 EUR** (Discretionary Procurement Bypass).

---

## 📚 Technical Documentation

* [Threat Model & Attack Surface](docs/THREAT_MODEL.md)
* [AEI State Machine & Precedence Cascade](docs/AEI_STATE_MACHINE.md)
* [AEIB Technical Specification](scratch/aeib-receipt-fuzzer/SPEC.md)
* [Bounded Compliance & Scope Limitations](LIMITATIONS.md)

---

## ⚖️ License

Apache License 2.0. See [LICENSE](LICENSE) for details.
