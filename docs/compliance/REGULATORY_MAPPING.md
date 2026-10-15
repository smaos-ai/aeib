# Calibrated Regulatory & Standards Crosswalk (2026–2027)
**Technical Evidence Mapping for EU AI Act, EN 18286:2026, DORA, and ISO/IEC 42001**

```text
Document Version : 1.1.0-rc.1
Release Baseline : v1.0.0-rc.3 / v1.1 Candidate
Status           : Standardized Regulatory & Standards Crosswalk
Classification   : Technical Compliance Architecture
Epistemic Notice : Evaluated under the stated model. Preserves strict epistemic lock.
                   AEIB provides technical execution evidence, not legal certification.
```

---

## 1. Regulatory Context & Legal Baseline (2026)

The European Union regulatory landscape for artificial intelligence and operational digital resilience established binding technical thresholds across 2025 and 2026:

1. **EU AI Act (Regulation (EU) 2024/1689 as amended by Regulation (EU) 2026/1744 - Digital Omnibus)**:
   - High-risk and general-purpose AI deployers must satisfy lifecycle logging (Article 12), human oversight (Article 14), cybersecurity resilience (Article 15), quality management (Article 17), and post-market monitoring with serious incident reporting (Article 72).
2. **CEN/CENELEC Harmonised Standard EN 18286:2026**:
   - Titled *Artificial intelligence — Quality management system for EU AI Act regulatory purposes*, harmonised under Commission Implementing Decision (EU) 2026/2274 on 14 October 2026.
   - Provides a structured presumption of conformity, strictly defined and delimited by its **Annex ZA**.
3. **Digital Operational Resilience Act (Regulation (EU) 2022/2554 - DORA)**:
   - Binding on EU financial entities and critical ICT third-party providers since 17 January 2025.
   - Mandates major ICT incident classification, timeline reconstruction, and root cause reporting (Article 17), alongside ICT third-party subcontracting risk registers (Article 28(3)).
4. **ISO/IEC 42001:2023**:
   - The international baseline for AI Management Systems (AIMS), serving as the process foundation harmonised into EN 18286:2026.

---

## 2. Fundamental Boundary: Technical Evidence vs. Legal Certification

> [!IMPORTANT]
> **Core Epistemic Invariant**:
> AEIB produces verifiable, machine-readable, and cryptographically signed technical execution evidence. **AEIB does not confer legal certification or regulatory compliance on its own.**
> 
> Compliance with the EU AI Act, DORA, or harmonised standards is an organizational and operational duty incumbent upon the **deployer** or **provider**. AEIB supplies the tamper-evident technical artifacts required by auditors, notified bodies, and competent authorities to substantiate conformity claims.

Under Commission Implementing Decision (EU) 2026/2274:
- Conformity with a harmonised standard confers a presumption of conformity **only for the requirements that standard, or the relevant parts of it, covers**.
- Citing a standard does not substitute for empirical, verifiable records of technical operation.
- An equation of the form `SOC 2 + ISO 42001 + EN 18286 = Automatic Enterprise Security` is epistemically invalid.

---

## 3. EN 18286:2026 Detailed Clause Analysis & Annex ZA Delimitation

### 3.1 Clause 0.1: Scope & Internal Pilot Non-Exemption
- **Standard Requirement**: EN 18286:2026 applies to any organization developing, providing, or deploying AI systems subject to the EU AI Act.
- **Critical Regulatory Implication**: Internal corporate pilots, departmental proof-of-concept projects, and operational sandboxes are **not exempt** from QMS obligations once autonomous agents initiate state-mutating actions on production or test financial records.
- **AEIB Role**: AEIB operates identically in pilot and production environments. It provides pre-execution prevention records (`docs/compliance/pre_execution_evidence.yaml`) and cryptographic audit logs regardless of organizational deployment scale.

### 3.2 Clause 3.2.7 & Clause 9.4: Substantial Modification & Algorithmic Drift
- **Standard Requirement**: Changes that alter the intended purpose, operational boundaries, or risk profile of an AI system constitute a *substantial modification*, legally resetting conformity assessment.
- **Dynamic Model Behavior**: In autonomous agentic systems, model distillation (e.g., student models under Harness-Aware Distillation), fine-tuning, system prompt revisions, or dynamic tool additions risk triggering Clause 3.2.7 and Clause 9.4 resets.
- **AEIB Execution Binding**:
  - AEIB decouples governance from mutable model weights.
  - The microsecond standing check re-evaluates:
    $$\text{Standing}(T_n) = \text{GrantValid} \wedge \text{EpochFresh} \wedge \text{CAIDMatch} \wedge \text{TargetAllowed} \wedge \neg\text{Halted}$$
  - Retraining or distilling an agent cannot bypass the boundary: if the resulting action attempts an unauthorized mutation or uses stale authority, AEIB blocks it at $T_n$.
  - Continuous telemetry (`docs/compliance/post_market_evidence.jsonl`) logs all policy epoch updates and drift indicators for QMS change control.

### 3.3 Clause 5.1: Leadership & Governance Ownership
- **Standard Requirement**: Top management must demonstrate leadership and active commitment to AI quality management. Accountability cannot be delegated to an algorithmic process or autonomous sub-agent.
- **AEIB Enforcement**:
  - AEIB rejects prompt-injected governance overrides (e.g., `[APPROVE OVERRIDE]` instructions in untrusted tool output).
  - High-consequence mutations require explicit human multi-signature step-up (`RFC 9470`), maintaining unambiguous accountability chains.

### 3.4 Clause 8.5: Operational Planning and Control
- **Standard Requirement**: Processes must be in place to ensure that AI system operations conform to documented acceptance criteria and safety envelopes.
- **AEIB Enforcement**:
  - Station 0 capability manifest validation.
  - Station 1 RFC 8785 JCS canonical content-addressed identifier (`CAID`) computation.
  - Station 2 bounded probe reconciliation on transport ambiguity (HTTP 504 / TCP RST).
  - Station 3 Ed25519 hash-chained continuity receipts.

---

## 4. 5-Step Integration Path: From ISO/IEC 42001 to EN 18286 Presumption of Conformity

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│              5-STEP QMS & TECHNICAL EVIDENCE INTEGRATION WORKFLOW                      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 1: Leadership & Policy Definition (EN 18286 Clause 5.1 / ISO 42001 §5)            │
│ • Establish organizational AI acceptable-use policies and monetary authority ceilings. │
│ • Deployer registers authorized signing keys and policy epochs in AEIB.                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 2: Consequence Classification & Threat Modeling (EN 18286 Clause 6.1 / ISO §6)   │
│ • Classify tool surfaces into Tier 1 (read), Tier 2 (bounded), Tier 3 (step-up).       │
│ • Lock contracts/refund_status_v1.schema.json for authenticated target state probes.   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 3: Inline Operational Control & L7 Guarding (EN 18286 Clause 8.5 / ISO §8)        │
│ • Intercept socket writes via Station 1 microsecond Tn revalidation engine.            │
│ • Enforce persistent halt state machine (/var/run/aeib/halt.state) on anomalies.       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 4: Tamper-Evident Lifecycle Logging (EU AI Act Art. 12 / ISO 42001 §9)            │
│ • Emit Ed25519-signed ContinuityReceipts over RFC 8785 JCS canonical payloads.         │
│ • Export hash-chained operational records to offline cleanroom verifier.              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 5: Post-Market Monitoring & Drift Governance (EU AI Act Art. 72 / Clause 9.4)     │
│ • Ingest docs/compliance/post_market_evidence.jsonl into deployer QMS monitoring.       │
│ • Audit model distillation (HAD) or prompt changes against fixed execution baselines.  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Comprehensive Regulatory & Standards Crosswalk Matrix

The table below delineates the strict boundary between technical evidence generated by AEIB and the organizational obligations fulfilled by the deployer:

| Regulatory Article / Standard Clause | Focus Area | AEIB Technical Evidence & Verification Artifacts | Deployer / Provider Organizational Responsibility |
| :--- | :--- | :--- | :--- |
| **EU AI Act Art. 12** | Lifecycle Event Logging | • Append-only Ed25519-signed `ContinuityReceipt` records.<br>• RFC 8785 JCS payload canonicalization.<br>• Hash-chained logs (`post_market_evidence.jsonl`). | • Establish enterprise log retention policies (minimum statutory duration).<br>• Provision secure offsite storage and access control. |
| **EU AI Act Art. 14** | Human Oversight & Intervention | • Bounded human step-up gate (`RFC 9470`).<br>• Persistent halt state machine (`/var/run/aeib/halt.state`).<br>• Presentation of raw unredacted JCS payload (no hallucinated AI summaries). | • Assign qualified personnel for review desks.<br>• Establish escalation runbooks and operational duty rotations. |
| **EU AI Act Art. 15** | Cybersecurity & Robustness | • L7 socket interlock blocking blind retry loops.<br>• Fail-closed latching on HTTP 504 / TCP RST (`EFFECT_INDETERMINATE`).<br>• Anti-prompt-injection boundary isolation (`PEP-01` to `PEP-06`). | • Manage host OS hardening, TLS key rotation, and perimeter network defenses. |
| **EU AI Act Art. 17** & **EN 18286:2026** | Quality Management System | • Reproducible build digests and SBOM tracking.<br>• Systematic test vectors (`AT30`–`AT46`, `REC-01`–`REC-05`, `RB-01`–`RB-05`).<br>• Empirical evidence dossiers (`pre_execution_evidence.yaml`). | • Maintain organizational QMS documentation, management reviews, and audit schedules. |
| **EU AI Act Art. 72** | Post-Market Monitoring & Incident Reporting | • Structured, hash-chained operational incident telemetry (`post_market_evidence.jsonl`).<br>• Instant detection of anomalous tool call patterns. | • Investigate root causes and file statutory incident notifications with national competent authorities. |
| **DORA Art. 17** | ICT Incident Classification & Timeline | • Microsecond-accurate timestamped receipt lineage.<br>• Pre-dispatch intent log (EO-1 WAL) matched against target response.<br>• Gap report generation (`reports/dora_art17_gap_report.json`). | • Formal incident reporting to financial supervisory authorities (EBA, ECB, national regulators). |
| **DORA Art. 28(3)** | ICT Third-Party Subcontracting Risk | • Target API evidence contracts (`refund_status_v1.schema.json`).<br>• Pinned server identity and cryptographic SPKI digests. | • Maintain enterprise register of information on ICT third-party arrangements. |
| **ISO/IEC 42001:2023** | AI Management System (AIMS) | • Continuous verifier integration (`smaos_verify.wasm`).<br>• Deterministic test suites asserting zero-mock AST purity.<br>• Automated evidence packaging. | • Complete internal and external AIMS management certification audits. |

---

## 6. Distinguishing DORA Article 17 from EU AI Act Article 72

Deployers in financial services frequently confuse DORA ICT incident reporting with EU AI Act post-market incident reporting. AEIB strictly separates these reporting pipelines:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                  ICT RESILIENCE vs. AI POST-MARKET INCIDENT PATHWAYS                   │
├──────────────────────────────┬────────────────────────────┬────────────────────────────┤
│ DIMENSION                    │ DORA ARTICLE 17            │ EU AI ACT ARTICLE 72       │
├──────────────────────────────┼────────────────────────────┼────────────────────────────┤
│ Primary Focus                │ ICT operational disruption │ Fundamental rights & safety│
│ Trigger Threshold            │ Financial impact, duration,│ Serious incident, death,   │
│                              │ clients affected, data loss│ critical infrastructure hit│
│ Statutory Reporting Window   │ Initial: 4h / Intermediate:│ Immediate (without delay), │
│                              │ 24h / Final: 1 month       │ max 15 days                │
│ Supervisory Recipient        │ ECB, EBA, National Fin Reg │ AI Office & National AI    │
│                              │ (e.g., BaFin, ČNB)         │ Market Surveillance Auth   │
│ AEIB Artifact Input          │ dora_art17_gap_report.json │ post_market_evidence.jsonl │
└──────────────────────────────┴────────────────────────────┴────────────────────────────┘
```

---

## 7. Operational Cleanroom Verification Runbook

To verify that AEIB technical evidence meets audit requirements under zero-network conditions:

1. **Cleanroom Environment Isolation**:
   - Ensure the verifier host operates without internet egress (`BypassSandbox: false`).
2. **Execute Independent Receipt Verification**:
   ```bash
   # Offline Python reference verifier
   python3 scripts/verify_track_b_reproduction.py
   
   # WebAssembly cleanroom verifier
   node tests/test_smaos_verify_wasm.js
   ```
3. **Verify Zero-Mock and AST Purity**:
   ```bash
   python3 compliance/check_zone_boundary.py
   python3 compliance/ast_purity.py .
   python3 compliance/no_mock_enforcer.py
   ```
4. **Assert Expected Verdict**:
   All 14 control vectors (`AT30`–`AT46`) must yield `PASS` with 0-byte divergence across canonical bytes and exact Ed25519 signature validation.
