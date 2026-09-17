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
* [Honest Limitations & Cryptographic Boundaries](scratch/aeib-receipt-fuzzer/LIMITATIONS.md)

---

## ⚖️ License

Apache License 2.0. See [LICENSE](LICENSE) for details.
