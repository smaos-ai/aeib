# Regulatory Mapping: DORA RTS Art. 17 & EU AI Act Art. 12

## 1. EU Digital Operational Resilience Act (DORA)

Under **Regulation (EU) 2022/2554** and **Commission Delegated Regulation (EU) 2024/1772 (RTS on Incident Classification)**:

### Article 17: ICT-Related Incident Management
- **Art. 17(1) Incident Detection:** The engine automatically detects anomalies in automated execution pipelines (transport drops, timeouts, signature failures).
- **Art. 17(3) Chain of Custody & Traceability:** All audit findings are anchored to exact byte offsets with cryptographic SHA-256 evidence digests. No non-deterministic model guesses are admitted.
- **Fail-Closed Remediation:** When transport timeouts (`504 Gateway Timeout`, `TCP_RST`) occur, the engine validates that the agent harness marked the disposition as `UNKNOWN` with `retry_held: true`. Fabricated `CONFIRMED` statuses are flagged as material compliance breaches.

---

## 2. EU AI Act (Regulation (EU) 2024/1689)

### Article 12: Record-Keeping
- **Art. 12(1) Automatic Logging:** High-risk AI systems must continuously log operations throughout their lifecycle.
- **Art. 12(2) Traceability of Decisions:** The 5-stage pipeline links high-level agent intentions (`intent_digest`) to wire-level socket effects (`xid`, HTTP status).
- **Art. 14 Human Oversight:** Toxic receipts generate explicit remediation patches (`fix.patch`) requiring authorized officer sign-off before state reconciliation.
