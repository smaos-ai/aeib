# EN 18286:2026 & Implementing Decision (EU) 2026/2274 Compliance Crosswalk
## High-Risk AI Quality Management System (Article 17 & Article 40 Presumption of Conformity)

```text
Document Identifier : AEIB-EN18286-CROSSWALK-v1.1
Governing Decision  : Commission Implementing Decision (EU) 2026/2274 (14 October 2026)
Official Journal    : OJ L, 2026/2274, 16.10.2026 (Harmonized Standards for AI Act Art. 17)
Standard Reference  : CEN-CENELEC EN 18286:2026 (Artificial Intelligence Quality Management Systems)
Complementary Stds  : ISO/IEC 42001:2023 (Organizational AIMS), ISO 13485:2016 (Medical Device QMS)
Target Architecture : AEIB Station 0–3 Governed Execution Boundary & SCITT Merkle Receipt Engine
Epistemic Notice    : Evaluated under the stated model. AEIB produces verifiable technical evidence
                      to support deployer conformity; it does not confer legal certification.
```

---

## 1. Statutory Context & Legal Presumption of Conformity

Under **Article 40 of Regulation (EU) 2024/1689 (EU AI Act)**, high-risk AI systems that comply with harmonized standards published in the Official Journal of the European Union enjoy a **presumption of conformity** with the corresponding requirements set out in Chapter III, Section 2 of the Act.

On **14 October 2026**, the European Commission published **Commission Implementing Decision (EU) 2026/2274**, formally citing **CEN-CENELEC EN 18286:2026** as the European harmonized standard for **Article 17 Quality Management Systems (QMS)**.

### Crucial Distinction: EN 18286:2026 vs. ISO/IEC 42001:2023
* **ISO/IEC 42001:2023** is an *organizational management system standard*. It governs institutional AI strategy, ethics boards, and company-wide governance processes. It does not by itself confer presumption of conformity with EU AI Act Article 17 because it lacks prescriptive, per-system technical controls.
* **EN 18286:2026** is a *system-level technical QMS standard*. It establishes concrete, verifiable engineering requirements for testing, data provenance, post-market monitoring, and serious incident handling for each specific high-risk AI deployment.

---

## 2. Normative Crosswalk: EU AI Act Article 17 $\leftrightarrow$ EN 18286 $\leftrightarrow$ AEIB Runtime

The table below maps the statutory obligations of Article 17 to EN 18286 clauses and AEIB technical enforcement primitives:

| EU AI Act Art. 17 Obligation | EN 18286:2026 Clause | AEIB Technical Mechanism | Verifiable Repository Artifact |
|---|---|---|---|
| **Art. 17(1)(a)**<br>Regulatory compliance strategy & allocation of responsibilities | **Clause 4.1 & 5.1**<br>Context, scope determination, and leadership commitments | Station 1 Root Sponsor (`did:key`) identity tree. Ephemeral subagents roll up to cryptographic sponsor; header spoofing is rejected. | [`src/quota_financial_gate_interlock.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/quota_financial_gate_interlock.py) |
| **Art. 17(1)(b)**<br>Design control & verification procedures | **Clause 7.1**<br>System design, specification constraints, and pre-release gates | 5-term pre-dispatch conjunctive predicate ($GrantValid \land PolicyEpochFresh \land SourceEpochFresh \land CAIDMatch \land TicketUnburned$). | [`scripts/run_integration_gates_g1_g7.py`](file:///Users/andriileukhin/Documents/SovereignNexus/scripts/run_integration_gates_g1_g7.py) |
| **Art. 17(1)(c)**<br>Development, quality control & quality assurance | **Clause 7.2 & 7.3**<br>Verification, validation, and zero-mock testing | 14-scenario rehearsal matrix (`test_assessment_rehearsal_14.py`) and 500-episode fault injection harness across 15 vectors. | [`benchmarks/aeib_execution_integrity/run_episodes.py`](file:///Users/andriileukhin/Documents/SovereignNexus/benchmarks/aeib_execution_integrity/run_episodes.py) |
| **Art. 17(1)(d)**<br>Examination, test and validation procedures | **Clause 7.4**<br>Adversarial robustness & security verification | `AT30`–`AT64` test matrix covering prompt injection, memory poisoning (`AT57`), shadow MCP servers (`AT63b`), and Sybil rotators. | [`tests/test_at64_rail_interop_and_mcp_tool_taint.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tests/test_at64_rail_interop_and_mcp_tool_taint.py) |
| **Art. 17(1)(e)**<br>Technical specifications & standards conformity | **Clause 7.1.3**<br>Harmonized standard conformity & cryptographic agility | RFC 8785 JCS canonicalization, Ed25519 (RFC 8032), RFC 9052 `COSE_Sign1`, and CycloneDX 1.6 / ECMA-424 CBOM. | [`evidence/cbom.json`](file:///Users/andriileukhin/Documents/SovereignNexus/evidence/cbom.json) |
| **Art. 17(1)(f)**<br>Data management & schema validation | **Clause 7.5**<br>Context integrity & input/output sanitization | Station 0 JSON-RPC schema validation and Station 1 Context Integrity Gate binding input manifest to action CAID. | [`src/quota_financial_gate_interlock.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/quota_financial_gate_interlock.py) |
| **Art. 17(1)(g)**<br>Risk management system integration (Art. 9) | **Clause 6.1**<br>Risk analysis, mitigation controls, and residual risk evaluation | ISO 14971 4-hazard clinical/financial risk analysis (`HZD-01` through `HZD-04`) mapped to pre-socket TCC escrow. | [`compliance/unified_technical_file_generator.py`](file:///Users/andriileukhin/Documents/SovereignNexus/compliance/unified_technical_file_generator.py) |
| **Art. 17(1)(h)**<br>Post-market monitoring system (Art. 72) | **Clause 8.1 & 8.2**<br>Operational logging and continuous monitoring | Out-of-process append-only JCS ledger (`ledger.jsonl`) with boot-time per-entry signature verification (`AT59`). | [`tests/test_sybil_rotator_and_smurfing.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tests/test_sybil_rotator_and_smurfing.py) |
| **Art. 17(1)(i)**<br>Serious incident reporting (Art. 73) | **Clause 8.3**<br>Incident recording, root-cause analysis, and notification | Automated DORA Art. 17 (4 stages) and EU AI Act Art. 73 incident bundle generator separating model, gate, and target facts. | [`compliance/dora_art17_exporter.py`](file:///Users/andriileukhin/Documents/SovereignNexus/compliance/dora_art17_exporter.py) |
| **Art. 17(1)(j)**<br>Record-keeping & technical documentation (Art. 11 & 12) | **Clause 7.6**<br>Automated technical documentation & retention | Single Technical File Annex IV / ISO 13485 DHF Addendum generator; RFC 9942/9943 SCITT Merkle transparent statements. | [`docs/compliance/UNIFIED_DHF_ANNEX_IV_TECHNICAL_FILE.md`](file:///Users/andriileukhin/Documents/SovereignNexus/docs/compliance/UNIFIED_DHF_ANNEX_IV_TECHNICAL_FILE.md) |

---

## 3. Resolving the 1NTEGRAGUARD Domain 5 (Transparency & Bias) Gap

The 1NTEGRAGUARD October 2026 audit observed that enterprise deployments routinely score **<40% in Domain 5 (Transparency & Bias)** because they rely on unstructured text logs or opaque LLM summaries.

AEIB resolves this deficiency by providing **operation-level mathematical transparency**:
1. **Model Proposal vs. Authority vs. Target Facts Separation**:
   Every receipt documents exactly what the LLM proposed (`CandidateAction` CAID), what policy authorized (`boundary_verdict`), and what the target confirmed (`observed_target_consequence`).
2. **Offline External Verifiability**:
   Regulators and notified bodies do not need to trust the deployer's internal database. Using [`tools/verify_cose_scitt_receipts.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tools/verify_cose_scitt_receipts.py) or [`smaos-wasm-verifier/smaos-verify.html`](file:///Users/andriileukhin/Documents/SovereignNexus/smaos-wasm-verifier/smaos-verify.html), an auditor verifies RFC 9942 Merkle inclusion proofs offline with zero network egress.

---

## 4. Verification & Conformity Checklist

To verify your deployment's EN 18286 technical evidence baseline, execute:

```bash
# 1. Run the Unified Technical File & DHF generator:
python3 compliance/unified_technical_file_generator.py --self-test --export-dhf --output-json evidence/unified_annex_iv_dhf_package.json

# 2. Run the full integration quality gates (G1 through G7):
python3 scripts/run_integration_gates_g1_g7.py

# 3. Verify zero banned marketing words in documentation:
python3 compliance/ast_purity.py .
```
