# "DORA Article 17 Insurance" — 5-Day Diagnostic Audit Package
**Sovereign Multi-Agent OS (SMAOS) / Commercial Execution Playbook**

*Target Stakeholders: Enterprise CISO, CIO, Head of Operational Risk, ICT Risk Committee*  
*Engagement Model: Observe-Only Diagnostic Audit (Zero Code Changes, Zero Cloud Egress)*  
*Standard Fee: €1,500 – €5,000 (Credited against Enterprise License upon adoption)*

---

## 1. Executive Summary & Value Proposition

Under **Regulation (EU) 2022/2554 (DORA) Article 19(4)(a)** and **Commission Delegated Regulation (EU) 2025/301 Article 4**:
- **The Dual-Clock Reporting Invariant**: The **4-hour reporting clock** initiates **strictly upon formal classification of an incident as major**, while the separate **24-hour awareness backstop** runs continuously from initial detection/awareness.
- **Statutory Reporting Window**: Initial notification must be submitted within $\min(T_{\text{class}} + 4\text{h}, T_{\text{aware}} + 24\text{h})$. Intermediate report at $T_{\text{class}} + 72\text{h}$; final report at 1 month.
- **RTS 2025/301 Article 4(2) Non-Adjustment**: Credit institutions and essential entities receive zero weekend or holiday extensions.

For financial institutions running agentic workflows (SEPA payment routing, ERP updates, ledger mutations):
- Raw agent logs are unstructured, non-reproducible, and legally non-verifiable.
- Upstream HTTP 504 timeouts and TCP drops cause unconfirmed states that trigger either dangerous speculative double-spend or undetected transaction drops.
- **The DORA Article 17 Insurance Package** installs SMAOS in **Observe-Only Mode** for 5 days. It traps socket anomalies, quantifies the institution's toxic receipt exposure, runs zero-egress local OLAP analytics, and produces a complete, pre-filled **DORA RTS 2025/301 Annex II Incident Dossier** for human audit sign-off.
- **EU AI Act Timeline Alignment**: High-risk Annex III obligations are deferred to **December 2, 2027** (via Digital Omnibus EU 2026/1744) and embedded systems to August 2, 2028. Commercial urgency focuses strictly on **Article 50 transparency & machine-readable content marking duties** (live as of August 2, 2026; synthetic content marking transition to December 2, 2026).
- **SCITT Standards Alignment**: Cryptographic receipts anchor directly to published IETF standards—**RFC 9943** (SCITT Architecture, June 2026) and **RFC 9942** (COSE Receipts, June 2026)—utilizing the **Emilia Protocol profile** over local RFC 9162 Merkle trees.

---

## 2. 5-Day Engagement Timeline

```text
DAY 1: DISCOVERY & DOCKER DEPLOYMENT
├── Zero-privilege staging deployment (Docker / Python venv)
├── Connection to staging MCP gateway or reverse proxy log stream
└── Baseline zero-egress verification (no outbound internet egress required)

DAY 2–3: PASSIVE TRAFFIC CAPTURE & FAULT INJECTION
├── Trap 100% of staging agent tool calls (tools/call)
├── Inject controlled socket drop scenarios (HTTP 504 / TCP RST)
└── Measure fail-closed quarantine and downstream idempotency enforcement

DAY 4: LOCAL OLAP AUDIT & INCIDENT AGGREGATION
├── Execute in-process ClickHouse / chDB queries directly on local silicon
├── Extract: 504 drop rates, duplicate risk exposure, authority freshness
└── Verify hash-chain ledger continuity and Ed25519 signature coverage

DAY 5: CISO EXECUTIVE BRIEFING & REGULATORY HANDOVER
├── Present Executive Risk Leave-Behind to CISO & ICT Risk Committee
├── Hand over pre-filled draft dora_annex_ii_prefill.json
└── Deliver SOW credit for Enterprise SMAOS production deployment
```

---

## 3. Scope & Operating Boundary

1. **Observe-Only Non-Invasive Interception**:
   - Deployed as a transparent reverse-proxy wrapper (`mcp_interceptor.py` or Docker sidecar) or run post-hoc over historical JSONL logs.
   - Requires **zero modification** to core banking code, LLM prompts, or agent orchestration logic.
2. **Zero Cloud Data Egress**:
   - 100% of cryptographic signing (RFC 9052 `COSE_Sign1`), verification, and analytical queries (`chDB`) run locally on customer infrastructure.
   - No telemetry, tokens, or customer data ever leaves the host machine.
3. **Strict Governance & Legal Shield**:
   - All exported regulatory artifacts are permanently watermarked:
     ```json
     {
       "impact_severity_rating": "PENDING_HUMAN_REVIEW",
       "submission_status": "NOT_SUBMITTED",
       "detection_timestamp_utc": "2026-09-29T01:15:00+00:00",
       "classification_timestamp_utc": "2026-09-29T03:30:00+00:00",
       "legal_disclaimer": "Internal technical pre-fill draft generated for review by the ICT Incident Management function. Does not constitute legal advice or automated regulatory submission."
     }
     ```
   - SMAOS is an indispensable **evidence generator**, preserving human-in-the-loop governance while eliminating 90% of manual data assembly time.
   - **Schema Verification**: Both `detection_timestamp_utc` (tracking the 24-hour awareness backstop) and `classification_timestamp_utc` (initiating the 4-hour reporting clock) are strictly validated in `dora_annex_ii_prefill.json`.

---

## 4. Key Customer Deliverables

1. **Executive Risk Leave-Behind (`EXECUTIVE_CISO_RISK_LEAVEBEHIND.pdf`)**:
   - Quantified exposure score: number of ambiguous drops, duplicate spend risk, authority drift.
2. **Pre-Filled DORA Annex II Incident Notification (`dora_annex_ii_prefill.json`)**:
   - Complete draft satisfying all 14 mandatory fields under RTS 2025/301 with dual timestamps.
3. **Cryptographically Signed Audit Log (`receipts.jsonl` + `manifest.json`)**:
   - 100% Ed25519-signed, SHA-256 hash-chained immutable audit trail ready for Big 4 auditor review.
4. **Local OLAP Metric Dashboards**:
   - Sub-35ms query results proving real-time observability across all agent execution flows.

---

## 5. Global Export Positioning & Regional Brussels Moat

1. **Regional Operational Moat**: The Brussels Effect functions as a regional moat for multinational corporations that require unified EU-compliant execution across borders, rather than relying on speculative foreign regulatory uptake.
2. **Singapore (MAS FEAT) as #1 Export Market**: Aligns directly with the Monetary Authority of Singapore's March 2026 AI Risk Management Toolkit, which moved from voluntary principles to mandatory, evidence-based risk management.
3. **US Alignment (NYDFS Part 500)**: Maps `DISPATCHED_UNCONFIRMED` state isolation to NYDFS May 2026 operational resilience expectations for frontier AI risks.
