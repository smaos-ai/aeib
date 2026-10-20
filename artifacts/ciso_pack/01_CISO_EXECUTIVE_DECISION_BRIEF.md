# AEIB Executive Decision Brief: Consequential Agent Governance & Compliance

**Document Version:** 1.0.0-rc.4 (Non-Disclosing Leave-Behind Pack)  
**Evaluation Standard:** Evaluated under the stated model as an agent execution boundary scaffold.  
**Manifest Hash:** `sha256:c17376e523bb02dd74744cd472965a865dc01e4c0ce58a3820a13ee5f5f96c56`  
**WASM Verifier Artifact:** `dist/smaos_verify.wasm` (`sha256:6ecc360af19008632c950d94910b70220e3c2cc36a5cc29fe0c33ba64d2bb041`, 199,770 bytes)  

---

## 1. Executive Problem Statement
Autonomous AI agents executing multi-step tool calls present distinct operational, legal, and financial liabilities:
1. **Asymmetric Reversibility:** Triggering a financial mutation (refund, voucher, payout) requires milliseconds; reversing an uncoordinated mutation takes days.
2. **Transport Ambiguity:** Network timeouts (`HTTP 504`, TCP reset) leave in-flight agent actions in an indeterminate state, causing naive retry loops to duplicate financial spend.
3. **Regulatory Non-Compliance:** Regulations including **DORA (EU 2022/2554)** and the **EU AI Act (Art. 12/14/17)** mandate automatic audit logging, human oversight, and storage-layer idempotency.

---

## 2. Empirical Verification Baseline
Across 10,000 protocol-aware deterministic simulation schedules (seed `20261020`):
- **Observed Duplicate Mutations:** 0 / 10,000 (0.00% failure rate under ambiguous timeouts).
- **Ambiguous Timeout Interception:** 3,018 / 3,018 `HTTP 504` faults latched as `EFFECT_INDETERMINATE`.
- **Core Invariant Violations:** 0 across all 7 properties (budget conservation, replay rejection, taint step-up).
- **Swift 6 Strict Concurrency:** 11 / 11 tests passed in 0.045s (`-Xswiftc -strict-concurrency=complete`).
- **Scale Metrics:** Throughput and latency metrics remain tagged `[TARGET]` until third-party clean-room reproduction is complete.

---

## 3. Regulatory Alignment Matrix
- **DORA Article 17 & 19:** Append-only ledger recording all dispatches and denied requests (`rejections_audit.log`).
- **EU AI Act Articles 12, 14 & 17:** Pre-dispatch authority checks, single-flight probe reconciliation, and continuous quality management.
- **OWASP Agentic Top 10 (2026):** Active defenses against `ASI01` (Goal Hijack), `ASI02` (Tool Misuse), `ASI03` (Privilege Abuse), and `ASI06` (Context Poisoning).

---

## 4. Non-Disclosing Verification Architecture ("One Core, Two Doors")
- **Public Audit Wedge:** Standalone WASM verifier (`smaos_verify.wasm`, 195 KB) and read-only diagnostic scanner (`ghost_audit_scanner.py`). Allows external auditors and clients to verify receipts offline without accessing proprietary execution engine code.
- **Enterprise Core:** Closed data-plane execution engine deployed on-premises or in customer VPC.
