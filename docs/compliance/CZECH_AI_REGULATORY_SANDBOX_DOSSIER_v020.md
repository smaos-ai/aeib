# Czech AI & FinTech Regulatory Sandbox Submission Addendum (v0.2.0)
**Candidate: SovereignNexus / SMAOS (Agent Execution Integrity Benchmark)**  
**Supervisory Authority: Czech National Bank (ČNB) / Ministry of Industry & Trade (MPO / ČAS)**  
**Target Program: Czech National AI & FinTech Regulatory Sandbox**  
*Date: 2026-09-29 | Technology Tier: v0.2.0 Cryptographic Evidence Tier*

---

## 1. Regulatory Context & Advisory Engagement Scope

Under **Regulation (EU) 2022/2554 (DORA)** Article 17, Article 19, and the **EU AI Act (Regulation (EU) 2024/1689)**:
- **EU AI Act Enforceability Timelines**: High-risk Annex III requirements are deferred to **December 2, 2027** (via Digital Omnibus EU 2026/1744). Current regulatory urgency centers strictly on **Article 50 transparency & machine-readable marking duties** (enforceable as of August 2, 2026).
- **The ČAS Program Context**: The Czech Agency for Standardization (ČAS) is preparing the national Regulatory AI Sandbox with an allocated budget of **232 million CZK (€9.3 million) for 2026–2028**.
- **Role Realignment (Technical Advisor)**: The ČAS sandbox is designed for AI system deployers testing their own applications—not for compliance tooling certification. SMAOS engages ČAS and the Czech National Bank (ČNB) as a **Technical Advisor on Audit Evidence Requirements**.
- **Audit Intake Standard**: SMAOS submits its open-core 5-state disposition taxonomy and RFC 8785 JCS + Ed25519 receipt schema as the **recommended audit intake format** for sandbox participants and financial supervisory reviews.

### The Specific Supervisory Paradox
When an autonomous agent dispatches a financial mutation (e.g. SEPA payment, account freeze, credit evaluation) through a network gateway, physical socket faults (`HTTP 504 Gateway Timeout` or `TCP RST`) destroy transport telemetry. Standard runtime frameworks log either speculative retries (causing double-debits) or silent failures.

### The Advisory Proposal
SMAOS provides the ČAS sandbox and ČNB with a mathematically verifiable, zero-egress evidence schema that converts ambiguous agent network failures into deterministic, human-gated DORA Annex II pre-fill artifacts.

---

## 2. Technical Evidence Package Submitted for Sandbox Review

| Component | Specification | Supervisory Proof |
| :--- | :--- | :--- |
| **Disposition State Machine** | 5 Core Dispositions (`OUTCOME_VERIFIED`, `ACK_UNVERIFIED`, `DISPATCHED_UNCONFIRMED`, `RECONCILIATION_FAILED`, `REFUSED`) | Proves zero speculative retries under transport drops; strictly quarantines ambiguous post-dispatch states. |
| **Cryptographic Envelope** | RFC 9052 `COSE_Sign1` (`alg: -8`, EdDSA / Ed25519) | Complete 15+ field receipt coverage establishing non-repudiation and third-party auditability. |
| **Append-Only Ledger** | SHA-256 Hash Chaining (`chain_hash = SHA-256(prev \|\| canon \|\| ts)`) | Guarantees tamper-evident, cryptographically ordered audit trail across multi-agent sessions. |
| **DORA RTS 2025/301 Pre-Fill** | Annex II Major ICT Incident Schema (`dora_annex_ii_prefill.json`) | Auto-prefills all 14 mandatory fields while permanently locking `severity_status = PENDING_HUMAN_REVIEW` with dual detection/classification clocks. |
| **SCITT Receipt Architecture** | RFC 9943 (SCITT Architecture) & RFC 9942 (COSE Receipts) | Implements the **Emilia Protocol profile** over local RFC 9162 Merkle trees for offline transparency logs. |
| **BBS+ EUDI Interoperability** | BBS+ Selective Disclosure Cryptosuite (W3C CR) | Constant-size (~140-byte) zero-knowledge proofs verifying execution authority without leaking customer PII, meeting mandatory 2026 EUDI Wallet baselines. |
| **Zero Cloud Egress** | Local In-Process ClickHouse (`chDB`) / SQLite Engine | Zero external network calls; 100% of data processing, cryptographic signing, and OLAP analytics remain on local host silicon. |
| **Empirical Verification** | 73 Automated Test Vectors across `tests/` | 100% test pass rate confirming rejection of tampered payloads, expired tokens, and race conditions. |

---

## 3. Pilot Implementation Plan with Czech Credit Institutions

1. **Phase A (Synthetic Sandbox Simulation — Weeks 1–4)**:
   - Run synthetic high-volume transactional fault injection (`scripts/demo_15min_killshot.py`, `tests/test_aeib_negative_cases.py`) on sandbox infrastructure.
   - Verify that 100% of ambiguous 504 socket drops transition to `DISPATCHED_UNCONFIRMED` and trigger out-of-band reconciliation rather than duplicate execution.
2. **Phase B (Passive Staging Pilot with Design Partner — Weeks 5–12)**:
   - Deploy non-invasive observe-only interceptor (`mcp_interceptor.py`) in staging environment of a participating Czech bank.
   - Generate weekly audit ledgers and pre-filled DORA Annex II dossiers for the bank's ICT Risk Committee.
3. **Phase C (Supervisory Conformance & No-Objection Assessment — Weeks 13–16)**:
   - Present empirical findings and ledger continuity verification to ČNB supervisory examiners.
   - Seek formal sandbox conclusion evaluating whether SMAOS receipts meet the requirements of DORA Article 17(3) and Czech Act No. 370/2017 Coll. (Payment System Act).

---

## 4. Verification Checkpoint

```bash
# Verify entire test suite locally (zero external egress)
.venv/bin/python3 -m unittest discover -s tests
# 73 tests passing in 0.028s

# Run the 15-minute terminal demonstration
.venv/bin/python3 scripts/demo_15min_killshot.py
```
