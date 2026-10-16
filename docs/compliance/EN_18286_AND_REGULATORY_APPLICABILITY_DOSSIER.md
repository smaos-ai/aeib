# EN 18286 & Regulatory Applicability Dossier (AEIB v1.1)
## Harmonized Quality Management Systems, Epistemic Calibration, and Incident Evidence Crosswalk

> **EPISTEMIC & REGULATORY NOTICE:**
> This dossier documents the calibrated technical baseline, harmonized European standardization mappings (EN 18286 vs. ISO/IEC 42001), and regulatory evidence interfaces for the Agent Execution Integrity Boundary (AEIB v1.1).
> Under the stated model, AEIB produces independently reproducible operational control evidence (`DISPATCH_INTENT`, `CONTINUITY_RECEIPT`, `restraint_record`, and `incident_candidate`). It does not confer automatic statutory compliance or replace the deploying institution's internal governance, legal classification, or regulatory reporting functions under the EU AI Act (Regulation (EU) 2024/1689) or DORA (Regulation (EU) 2022/2554).

---

### Section 1: Locked Calibrated Baseline vs. Discarded Overclaims

To maintain strict epistemic boundaries across technical and regulatory documentation, AEIB v1.1 locks the following calibrated claims and explicitly discards unsubstantiated overclaims:

| Topic | Discarded Overclaim (Do Not Use) | Locked Calibrated Baseline (Use Exactly) |
| :--- | :--- | :--- |
| **Stripe / Server-Stable-Key Comparison** | "Stripe idempotency keys fail." | Under the tested 500-episode fault schedule (`seed=42`), server-side stable idempotency keys prevented duplicate execution (`0` duplicates) when the request reached the target with a stable key, but left `198` of `500` episodes (`39.6%`) unresolved in ambiguous post-timeout state (`EFFECT_INDETERMINATE`) without bounded out-of-band target reconciliation. |
| **Naive Retry Baseline** | "Industry standard retry fails." | Naive retry is modeled as an **application-level failure mode** (where an agent or wrapper retries after HTTP `504` / timeout without idempotency anchoring or state reconciliation), resulting in `302` observed duplicate mutations across `500` episodes (`60.4%`). |
| **Novelty / Prior Art Framing** | "No existing system does this." | In our review of public literature and documentation across classical consensus (`Paxos`, `Raft`, `2PC`), workflow engines (`Temporal`, `Restate`), payment APIs (`Stripe`, `Adyen`), and agent guardrails (`AgentSpec`, ` NeMo Guardrails`, `LlamaFirewall`), we did not identify an integrated open specification combining **durable pre-dispatch intent (`DISPATCH_INTENT`) + canonical action idempotency (`CAID`) + bounded out-of-band target reconciliation (`refund_status_v1`)** at the agent tool-call boundary. |
| **Regulatory / Audit Positioning** | "Passes regulatory audits automatically." | AEIB produces **independently reproducible operational control evidence** (`DISPATCH_INTENT`, `CONTINUITY_RECEIPT`, `restraint_record`, `incident_candidate`) that supports a deploying organization's conformity assessment and incident investigation workflows under the stated model. |

---

### Section 2: EN 18286 (CEN-CENELEC QMS) vs. ISO/IEC 42001 under EU AI Act Articles 17 & 40

#### 2.1 Harmonized Standard Architecture (EN 18286) vs. General AI Management Systems (ISO/IEC 42001)

Under the EU Artificial Intelligence Act (Regulation (EU) 2024/1689), providers of high-risk AI systems must establish a Quality Management System (QMS) pursuant to **Article 17**. Under **Article 40**, conformity with harmonized European standards drafted by CEN and CENELEC (under European Commission Standardization Request M/593) and cited in the *Official Journal of the European Union (OJEU)* grants a formal **presumption of conformity** with the corresponding statutory requirements.

* **EN 18286 (CEN-CENELEC JTC 21 Quality Management System for EU AI Act Article 17):**
  * Specifically drafted and structured to mirror the exact statutory clauses of **EU AI Act Article 17(1)(a)–(m)**.
  * Focuses on product-level and system-level regulatory lifecycle controls, including pre-deployment verification and validation, technical documentation linkage (Article 11 / Annex IV), post-market monitoring plans (Article 72), and serious incident reporting protocols (Article 73).
  * Designed to support presumption of conformity under **Article 40** once formally cited in the OJEU.
* **ISO/IEC 42001:2023 (Information Technology — Artificial Intelligence — Management System):**
  * An international, organization-wide management system standard structured around the ISO Harmonized Structure (Annex SL, Plan-Do-Check-Act).
  * Not directly cited in the OJEU for automatic Article 40 presumption of conformity; deploying organizations relying solely on ISO/IEC 42001 must execute explicit regulatory gap-bridging to satisfy product-specific EU AI Act Article 17 obligations (such as deterministic execution logging, Annex IV technical dossier generation, and statutory incident reporting thresholds).

| Dimension | EN 18286 (CEN-CENELEC JTC 21) | ISO/IEC 42001:2023 | AEIB v1.1 Evidence Role |
| :--- | :--- | :--- | :--- |
| **Primary Regulatory Scope** | European Harmonized Standard tailored to EU AI Act Art. 17 QMS | General international organizational AI Management System (AIMS) | Supplies operation-level cryptographic execution and restraint records |
| **EU AI Act Art. 40 Status** | Candidate harmonized standard for OJEU citation (presumption of conformity) | Non-harmonized international baseline; requires explicit Art. 17 gap-bridging | Bridges runtime execution controls to QMS verification & audit clauses |
| **Unit of Governance** | High-risk AI system lifecycle & product conformity dossier | Organization-wide policies, leadership, and continual improvement | Per-invocation tool-call boundary (`Station 0` to `Station 5`) |
| **Post-Market & Incident Linkage** | Direct alignment with EU AI Act Art. 72 (PMM) & Art. 73 (Serious Incidents) | Generic nonconformity and corrective action (Clause 10.1) | Emits `CONTINUITY_RECEIPT`, `restraint_record`, and `incident_candidate` |

#### 2.2 Mapping AEIB v1.1 Technical Artifacts to EN 18286 / EU AI Act Article 17 QMS Clauses

| EN 18286 / EU AI Act Art. 17 QMS Clause | Statutory Requirement Summary | AEIB v1.1 Technical Artifact / Mechanism | Evaluated Verification Method |
| :--- | :--- | :--- | :--- |
| **Art. 17(1)(b) & (c): Design, Design Control & Development Techniques** | Systematic design specifications, architecture boundaries, and state-transition enforcement. | 5-term conjunctive execution predicate (`GrantValid ^ PolicyEpochFresh ^ SourceEpochFresh ^ CAIDMatch ^ TicketUnburned`) and EO-1 Write-Before-Execute interlock (`DISPATCH_INTENT`). | Evaluated via AST purity checks (`compliance/ast_purity.py`) and Zone 1/Zone 2 boundary checks (`compliance/check_zone_boundary.py`). |
| **Art. 17(1)(d): Examination, Test, Verification & Validation Procedures** | Before, during, and after development testing of accuracy, robustness, and fault handling. | **14-Scenario Assessment Rehearsal Matrix** (`tests/test_assessment_rehearsal_14.py`) and **5-Arm Comparative Benchmark** (`500` episodes, `seed=42`). | Reproducible execution via `verify_all.sh` and standalone clean-room verifiers (`tools/verify_phase3_evidence.py`). |
| **Art. 17(1)(e) & (f): Technical Specifications & Data Management** | Integrity, canonical formatting, and cryptographic provenance of system records. | RFC 8785 JCS canonicalization, `CAID` (SHA-256 over canonical mutation payload), and Ed25519-signed `CONTINUITY_RECEIPT` and `restraint_record` artifacts. | 25/25 RFC 8785 conformance vectors and 0-byte cross-language JVM/Python differential verification. |
| **Art. 17(1)(h) & Art. 72: Post-Market Monitoring (PMM) System** | Ongoing collection and analysis of operational performance and boundary restraint events. | Continuous hash-chained emission of `CONTINUITY_RECEIPT` (executed dispatches) and `restraint_record` (blocked stale/revoked/duplicate proposals). | Offline verification of sealed evidence packs (`artifacts/aeib-pilot-evidence-pack-v1.1.0.tar.gz`). |
| **Art. 17(1)(i) & Art. 73: Serious Incident Reporting & Management** | Recording and structured export of operational faults and indeterminate execution states. | Three-plane `incident_candidate` record exported via `tools/export_dora_art17_evidence.py`, preserving `EFFECT_INDETERMINATE` without blind retry. | Tested under rehearsals #07, #08, #09, and #10 (`test_assessment_rehearsal_14.py`). |
| **Art. 17(1)(g) & (m): Resource Management, Deployment & Quality Gates** | Release readiness, supply-chain pinning, and operational runbook governance. | **Integration Quality Gates (`G1`–`G7`)** and deterministic operational runbooks (`RB01`–`RB05`). | Verified through sequential gate checks prior to pilot sign-off. |

---

### Section 3: EU AI Act Articles 12, 14, 15 & DORA Article 17 Crosswalk

#### 3.1 Statutory Crosswalk Matrix

| Regulatory Provision | Statutory Focus | AEIB v1.1 Control Surface | Boundary Scope & Epistemic Limitation |
| :--- | :--- | :--- | :--- |
| **EU AI Act Article 12** *(Record-Keeping / Logging)* | Automatic recording of events over the lifetime of the system to ensure traceability of operation. | `DISPATCH_INTENT` (pre-socket fsync), `CONTINUITY_RECEIPT` (post-reconciliation hash chain), and `restraint_record` (fail-closed halts). | Logs boundary-level authorization, transport observations, and target status confirmations. Does not log internal LLM weights. |
| **EU AI Act Article 14** *(Human Oversight)* | Measures enabling human overseers to intervene, interrupt, halt ("stop button"), or resolve ambiguous states. | `EFFECT_INDETERMINATE` latch (`retry_safe: false`) on HTTP `504` / timeout, bounded probe (`ProbeBudget: 1`), and emergency Andon-cord halt (Rehearsal #11). | Routes unresolved ambiguous operations to the customer's human review queue (`RB01`). Human operators execute final disposition. |
| **EU AI Act Article 15** *(Accuracy, Robustness & Cybersecurity)* | Resilience against errors, faults, inconsistencies, and adversarial manipulation (e.g., prompt drift/injection). | Station 0 strict schema validation, RFC 8785 `CAID` parameter binding, single-use ticket burn, and epoch revocation checks. | Evaluated across 15 fault vectors (`0` observed duplicate mutations across `500` episodes under the stated model). |
| **DORA Article 17 & RTS (EU) 2025/301** *(ICT-Related Incident Management & Classification)* | Detection, recording, internal classification, and timely notification of major ICT-related incidents. | Standardized `incident_candidate` evidence export (`tools/export_dora_art17_evidence.py`) separating operational facts from legal classification. | AEIB exports operational evidence only. The financial entity owns awareness tracking, major incident classification, and authority submission. |

#### 3.2 Exact `incident_candidate` Schema Boundary

To prevent premature or unauthorized regulatory filing while supplying forensic timestamps and cryptographic evidence, AEIB v1.1 enforces the following exact `incident_candidate` schema boundary in `tools/export_dora_art17_evidence.py`:

```json
{
  "operation_id": "op-2026-000142",
  "detection_time": "2026-10-16T14:22:05Z",
  "financial_entity_awareness_time": "unknown_until_supplied",
  "major_classification_time": "unknown_until_supplied",
  "authorization_evidence": {
    "governing_authority_id": "auth-grant-01",
    "authority_revocation_state": "VALID",
    "caid": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  "dispatch_evidence": {
    "intent_committed": true,
    "tool_name": "agent_financial_dispatch"
  },
  "transport_observation": {
    "socket_connect_invoked": true,
    "connections_accepted": 1,
    "external_bytes_transmitted": 128,
    "transport_fault": "HTTP_504_GATEWAY_TIMEOUT"
  },
  "reconciliation_state": "EFFECT_INDETERMINATE",
  "observed_duplicate_mutations": 0,
  "potentially_affected_operations": "assessed_or_unknown",
  "financial_exposure": "assessed_or_unknown",
  "customer_impact": "assessed_or_unknown",
  "classification_owner": "customer_defined",
  "reporting_decision": "not_determined_by_aeib"
}
```

#### 3.3 DORA Article 17 & RTS 2025/301 Notification Clock Rule

Under **DORA Regulation (EU) 2022/2554 Article 17 / Article 19** and **Commission Delegated Regulation (EU) 2025/301 (RTS on Major Incident Reporting)**:
1. **No Automatic Trigger on Transport Timeout:** An individual HTTP `504` timeout, TCP reset, or `EFFECT_INDETERMINATE` latch at the AEIB boundary is recorded at `detection_time` as an operational observation. It does **not** automatically start the statutory 4-hour regulatory reporting clock.
2. **Awareness and Classification Window:** The **4-hour initial notification window** begins only when the financial entity formally classifies the event as a **major ICT-related incident** (`major_classification_time`), where classification must occur within the statutory window after the financial entity becomes aware of the incident (`financial_entity_awareness_time`, up to 24 hours from awareness where continuous assessment is required).
3. **Explicit Role Separation:** AEIB populates `detection_time`, `authorization_evidence`, `dispatch_evidence`, `transport_observation`, `reconciliation_state`, and `observed_duplicate_mutations: 0`. The deploying financial entity supplies `financial_entity_awareness_time`, `major_classification_time`, `financial_exposure`, and `customer_impact`, and retains sole authority over `classification_owner: customer_defined` and `reporting_decision: not_determined_by_aeib`.

---

### Section 4: Scoped Workstreams A–E & Integration Quality Gates (G1 -> G7)

#### 4.1 Scoped Implementation Workstreams (A–E)

To transition AEIB v1.1 from repository verification to customer pilot deployment without scope drift, engineering and compliance activities are partitioned into five bounded workstreams:

* **Workstream A — Core Boundary & Durable Authority Interlock:**
  * Enforces the 5-term conjunctive execution predicate (`GrantValid ^ PolicyEpochFresh ^ SourceEpochFresh ^ CAIDMatch ^ TicketUnburned`), fsync-backed single-use ticket consumption (`v1.1-roadmap/tier1_durable_executor.py`), and EO-1 pre-dispatch write-ahead journaling (`src/eo1_write_before_execute.py`).
* **Workstream B — Target Reconciliation & Bounded Probe Protocol:**
  * Implements the `refund_status_v1` authenticated target status contract, latches ambiguous transport outcomes into `EFFECT_INDETERMINATE` (`retry_safe: false`), and enforces `ProbeBudget: 1` prior to human review escalation (`RB01`).
* **Workstream C — Cross-Language Cryptographic & Differential Verification:**
  * Maintains strict RFC 8785 JCS canonicalization and Ed25519 signature verification across Python 3 (`tools/verify_phase3_evidence.py`) and Java 21 / GraalVM (`aeib-native-runtime/aeib-verifier/`), evaluated for 0-byte canonical divergence.
* **Workstream D — EN 18286 QMS & DORA / EU AI Act Evidence Packaging:**
  * Generates hash-chained `CONTINUITY_RECEIPT` and `restraint_record` logs, exports three-plane `incident_candidate` bundles (`tools/export_dora_art17_evidence.py`), and aligns technical documentation with EN 18286 / EU AI Act Article 17 QMS clauses.
* **Workstream E — Customer Pilot Integration & Operational Runbook Rehearsal:**
  * Executes staging integration against customer target status receivers, verifies Zone 1 / Zone 2 / Zone 3 network isolation, and rehearses operational runbooks (`RB01`–`RB05`) with customer incident-response teams.

#### 4.2 Sequential Integration Quality Gates (`G1` -> `G7`)

Deployment progression is governed by seven sequential, fail-closed quality gates:

| Gate ID | Gate Identifier | Entry / Acceptance Criteria | Verification Artifact / Command |
| :--- | :--- | :--- | :--- |
| **G1** | `G1_source_and_deps_locked` | Repository commit hash pinned; zero unvetted dependencies; Zone 1 / Zone 2 import purity and zero-mock AST checks passing. | `python3 compliance/check_zone_boundary.py && python3 compliance/ast_purity.py . && python3 compliance/no_mock_enforcer.py` |
| **G2** | `G2_crypto_and_jcs_conformance` | 25/25 RFC 8785 JCS vectors passing; strict Ed25519 signature validation; 0-byte divergence between Python and Java 21 verifiers. | `pytest tests/test_falsifiability_matrix.py -v` & `benchmarks/jvm_native_diff_engine.py` |
| **G3** | `G3_rehearsal_14_and_5arm_verified` | All 14 fault-injection assessment rehearsals passing; 5-arm benchmark (`500` episodes, `seed=42`) verified with `observed_duplicate_mutations: 0`, `blocked_duplicate_attempts: 302`, and `preserved_indeterminate_outcomes: 198`. | `pytest tests/test_assessment_rehearsal_14.py -v` & `python3 benchmarks/aeib_execution_integrity/run_5arm_benchmark.py` |
| **G4** | `G4_offline_evidence_pack_sealed` | Sealed evidence archive generated, SHA-256 digest locked, and verified via standalone clean-room CLI verifier without runtime dependencies. | `python3 tools/verify_phase3_evidence.py` |
| **G5** | `G5_target_status_contract_integrated` | Customer downstream service exposes authenticated `refund_status_v1` endpoint; Ed25519 target status signatures verified in staging. | Staging contract integration test suite (`urn:aeib:contract:refund_status:v1`) |
| **G6** | `G6_runbook_and_incident_export_rehearsed` | Customer operations and legal teams rehearse `RB01`–`RB05` and validate `incident_candidate` export handoff (`classification_owner: customer_defined`). | `python3 tools/export_dora_art17_evidence.py` & signed runbook rehearsal log |
| **G7** | `G7_customer_pilot_accepted` | Controlled pilot episode window completed with zero unobserved duplicate mutations, verified Zone 2 network isolation, and joint technical sign-off. | Customer Pilot Acceptance Record & EN 18286 QMS Dossier Archive |
