# Integrated AI Governance, QMS & Product Safety Dossier
## Operationalizing ISO/IEC 42001, EN 18286, ISO 13485 & EU AI Act Annex IV at the Wire

```text
Document Identifier : AEIB-INTEGRATED-QMS-SAFETY-v1.1
Regulatory Framework: EU AI Act (Regulation (EU) 2024/1689), Articles 11, 12, 14, 15, 17, 28 & Annex IV
Governing Standards : ISO/IEC 42001:2023, CEN-CENELEC EN 18286:2026, ISO 13485:2016, ISO 14971:2019, ECMA-424 CBOM
Target Architecture : AEIB Station 0–3 Governed Execution Boundary & Single Technical File DHF Generator
Classification      : High-Risk AI System Regulatory Alignment & Technical Verification Specification
Release Baseline    : v1.0.0-rc.17 / Track B v1.1
Epistemic Notice    : Evaluated under the stated model. AEIB produces verifiable technical execution
                      evidence; statutory legal compliance is a deployer-level responsibility.
```

---

## Executive Summary & Epistemic Notice

> **Mandatory Deployer & Regulatory Notice (AGENTS.md §1 & §5)**:
> This specification codifies technical evidence, state-machine architectures, and automated verification mechanisms bridging organizational management (**ISO/IEC 42001:2023**), harmonized AI Quality Management Systems (**EN 18286:2026**), and product safety frameworks (**ISO 13485:2016 / ISO 14971:2019**).
> 
> Under the stated model, the Agent Execution Integrity Boundary (AEIB) produces operation-bound cryptographic receipts, deterministic wire latches, and automated technical documentation. It does not by itself confer legal compliance with the EU AI Act (Regulation (EU) 2024/1689), EU MDR (Regulation (EU) 2017/745), or DORA (Regulation (EU) 2022/2554). Compliance is an institutional obligation requiring accredited deployer infrastructure, human clinical/risk governance, and authenticated target status receivers.

---

## 1. The Multi-Standard Challenge: Preventing Compliance Theater

When deploying high-risk artificial intelligence in regulated industries (healthcare, finance, aerospace, automated critical infrastructure), organizations face overlapping standards requirements:
* **The Organizational Tier**: Corporate AI policy, ethics boards, and risk inventories (**ISO/IEC 42001:2023**).
* **The AI Quality Management Tier**: AI Act Article 17 statutory QMS requirements (**EN 18286:2026**).
* **The Product Safety Tier**: Physical hazard containment, software validation, and design controls (**ISO 13485:2016 / ISO 14971:2019**).
* **The Supply Chain Tier**: Foundation models, external APIs, and open-source MCP tools (**EU AI Act Art. 28 / ECMA-424 CBOM**).

Traditional approaches attempt to satisfy these through parallel documentation silos and manual compliance checklists. In practice, this creates **compliance theater**: static PDF policies that have zero interaction with runtime software physics, leaving the organization exposed when an autonomous agent mutates external state without authorization or fails ambiguously across an unhedged network socket.

AEIB eliminates parallel bureaucracies by **mapping organizational policies down to deterministic, automated technical execution at the runtime layer**.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              INTEGRATED AI GOVERNANCE & ENFORCEMENT ARCHITECTURE                                        │
├──────────────────────────┬──────────────────────────┬──────────────────────────────────────────────────────────────────┤
│ COMPLIANCE LAYER         │ GOVERNING STANDARD       │ RUNTIME & TECHNICAL IMPLEMENTATION MECHANISM                     │
├──────────────────────────┼──────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 1. Organizational AIMS   │ ISO/IEC 42001:2023       │ System inventory, role assignment, policy frameworks, and        │
│                          │ (Management System)      │ high-level risk assessment procedures.                           │
├──────────────────────────┼──────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 2. EU AI Act Article 17  │ EN 18286:2026            │ Pre-execution TCC escrows, fail-closed human release gates, and  │
│    QMS Presumption       │ (Harmonized AI QMS)      │ automated Article 12/14 compliance receipt generation.           │
├──────────────────────────┼──────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 3. Product Safety        │ ISO 13485 / ISO 9001     │ Biocompatibility, clinical/functional hazard logs (ISO 14971),   │
│    (Annex I / Medical)   │ & EU MDR/IVDR            │ and hardware-level isolation for embedded devices.               │
├──────────────────────────┼──────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 4. Supply Chain & CBOM   │ EU AI Act Art. 28 /      │ Pinned MCP tool manifests, cryptographic model weights hashing,   │
│    Vendor Integrity      │ ISO 42001 Annex A.8      │ and ECMA-424 Cryptography Bill of Materials (`cbom.json`).       │
└──────────────────────────┴──────────────────────────┴──────────────────────────────────────────────────────────────────┘
```

---

## 2. Technical Wire-Level Enforcement Mappings

To satisfy notified body evaluations (e.g., TÜV SÜD, DEKRA, BSI), technical evidence must be generated at the physical network boundary rather than in post-hoc application logs.

### 2.1 Article 12: Automated Wire-Level Logging (The 7-Year Immutable Trail)
* **The Mandate**: Article 12 of the EU AI Act requires high-risk AI systems to automatically record events ("logs") over their operational lifecycle, ensuring a level of traceability appropriate to the system's purpose.
* **The AEIB Wire Implementation**:
  1. Before any TCP socket allocation, Station 1 writes and flushes (`os.fsync`) a signed `DISPATCH_INTENT` record containing the RFC 8785 canonical action identifier (`CAID`).
  2. Following socket execution or transport drop, Station 3 commits a `CONTINUITY_RECEIPT` into an append-only hash-chained ledger.
  3. Receipts are enveloped as **RFC 9052 `COSE_Sign1`** statements and registered in an **RFC 9943 SCITT** Transparency Service Merkle tree with **RFC 9942** inclusion proofs.
* **Audit Value**: Provides a mathematically bound, tamper-evident audit trail suitable for 7-year regulatory retention without burdening agent developers.

### 2.2 Article 14: Decoupling Policy from Model Reasoning (Human Oversight)
* **The Mandate**: Article 14 requires technical mechanisms enabling human individuals to oversee high-risk AI, understand its outputs, and intervene or stop execution ("stop button").
* **The Vulnerability in Traditional Runtimes**: Standard agent architectures implement human oversight as system prompt instructions (e.g., "Ask the user before transferring funds") or dashboard buttons that overwrite backend database state (`[APPROVE OVERRIDE]`). Both fail under adversarial conditions: prompts can be bypassed via indirect injection, while ungrounded dashboard overrides introduce unrecorded side effects.
* **The AEIB Wire Implementation**:
  1. Safety policy is entirely decoupled from model weights; it is enforced at an out-of-process, fail-closed pre-socket gate.
  2. For high-consequence mutations exceeding configured automated thresholds (e.g. loans > €1,000, clinical dosage changes, actuator actuation), Station 1 refuses to mint an execution ticket.
  3. The system halts fail-closed until an authenticated operator supplies an **RFC 9470 Step-Up Dual Control Token** signed with an authorized Ed25519 supervisor key.
  4. The prohibition of `[APPROVE OVERRIDE]` ensures that no operator toggle can declare an ambiguous wire drop "successful" without attaching target-side authenticated reconciliation evidence.

### 2.3 Article 15: Accuracy, Robustness, and Cybersecurity
* **The Mandate**: High-risk AI systems must be resilient against errors, faults, and adversarial attempts to manipulate inputs, context, or execution environments.
* **The AEIB Wire Implementation**:
  * **Transport Ambiguity Containment**: Latches post-commit drops (`HTTP 504`, `TCP RST`) into `EFFECT_INDETERMINATE`, disallowing blind retries (`retry_safe: false`) and isolating true state via bounded status probes (`ProbeBudget: 1`).
  * **Parallel Concurrency Solvency**: Atomic pre-socket TCC (Try-Confirm-Cancel) budget reservation using SQLite WAL with `BEGIN IMMEDIATE` prevents multi-agent spend overruns.
  * **Context Integrity Protection (`AT57`)**: Station 1 verifies the runtime candidate action CAID against ingestion-time commitments, blocking poisoned RAG mutations before physical packets leave the host.

### 2.4 Article 28 / ISO 42001 Annex A.8: Supply Chain & CBOM
* **The Mandate**: Upstream foundation model providers, tool creators, and third-party API hosts must supply transparency evidence to enable deployer conformity assessments.
* **The AEIB Wire Implementation**:
  1. Pinned MCP Tool Manifests: Every registered tool descriptor (`name`, `description`, `inputSchema`) is hashed via SHA-256 and signed by an approved publisher.
  2. CycloneDX 1.6 / ECMA-424 Cryptography Bill of Materials: [`evidence/cbom.json`](file:///Users/andriileukhin/Documents/SovereignNexus/evidence/cbom.json) indexes all active cryptographic assets, key lengths, curves (`curve25519`), OIDs (`1.3.101.112`), and post-quantum migration plans (ML-DSA-65 / FIPS 204).

---

## 3. Statutory Timelines: Navigating Annex I vs. Annex III

The European AI Act establishes a phased implementation schedule based on high-risk classification:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               EU AI ACT ENFORCEMENT HORIZONS                           │
├────────────────────────┬─────────────────────────┬─────────────────────────────────────┤
│ DEADLINE               │ SCOPE & CLASSIFICATION  │ COMPLIANCE STRATEGY & DELIVERABLE   │
├────────────────────────┼─────────────────────────┼─────────────────────────────────────┤
│ August 2, 2026         │ General Governance &    │ Transparency notices, AI literacy,  │
│                        │ Transparency (Art. 50)  │ deployer governance kickoff.        │
├────────────────────────┼─────────────────────────┼─────────────────────────────────────┤
│ December 2, 2027       │ Annex III Standalone    │ Standalone Annex IV Technical File; │
│                        │ High-Risk AI Systems    │ EN 18286 QMS Presumption of         │
│                        │ (Credit, HR, Infra)     │ Conformity mapping.                 │
├────────────────────────┼─────────────────────────┼─────────────────────────────────────┤
│ August 2, 2028         │ Annex I Embedded        │ Unified Design History File (DHF)   │
│                        │ High-Risk AI Systems    │ Addendum integrating ISO 13485,     │
│                        │ (MDR Medical, Machinery)│ ISO 14971, and AI Act Annex IV.     │
└────────────────────────┴─────────────────────────┴─────────────────────────────────────┘
```

### 3.1 Target 1: December 2, 2027 (Annex III Standalone High-Risk)
* **Applicable Systems**: Creditworthiness assessment, employment recruitment, essential public service access, critical infrastructure components.
* **Delivery Mechanism**: Deployers assemble a standalone **EU AI Act Annex IV Technical Documentation File** supported by an **EN 18286 Quality Management System**.
* **Key Artifact**: Generated automatically via `compliance/unified_technical_file_generator.py`.

### 3.2 Target 2: August 2, 2028 (Annex I Embedded High-Risk)
* **Applicable Systems**: Medical devices (under EU MDR 2017/745 and EU IVDR 2017/746), machinery (Regulation (EU) 2023/1230), aviation, automotive.
* **The Unified Approach**: For medical device manufacturers with an existing ISO 13485 QMS and ISO 14971 risk management file, creating an entirely separate AI Act compliance dossier creates massive administrative overhead and audit conflict.
* **The Single Technical File Strategy**: The AI Act technical documentation is integrated directly into the medical device **Design History File (DHF)** as an authorized technical addendum, satisfying notified bodies under both MDR GSPR 17.2 and AI Act Annex IV simultaneously.

---

## 4. Verification Evidence & Artifact Manifest

All components of this integrated architecture are backed by runnable code, automated tests, and cryptographic verification receipts in the repository:

| Regulatory Plane | Implementation Code | Verification Suite | Output Artifact |
|---|---|---|---|
| **Unified Technical File** | [`compliance/unified_technical_file_generator.py`](file:///Users/andriileukhin/Documents/SovereignNexus/compliance/unified_technical_file_generator.py) | `tests/test_integrated_qms_and_product_safety.py` | [`evidence/unified_annex_iv_dhf_package.json`](file:///Users/andriileukhin/Documents/SovereignNexus/evidence/unified_annex_iv_dhf_package.json) |
| **Markdown DHF Dossier** | `render_markdown_dossier()` | Standalone CLI `--export-dhf` | [`docs/compliance/UNIFIED_DHF_ANNEX_IV_TECHNICAL_FILE.md`](file:///Users/andriileukhin/Documents/SovereignNexus/docs/compliance/UNIFIED_DHF_ANNEX_IV_TECHNICAL_FILE.md) |
| **ISO 42001 SoA (38 Controls)**| [`compliance/iso_42001_soa.py`](file:///Users/andriileukhin/Documents/SovereignNexus/compliance/iso_42001_soa.py) | `tests/test_iso_42001_full_38_controls_soa.py` | [`compliance/iso_42001_soa_report.json`](file:///Users/andriileukhin/Documents/SovereignNexus/compliance/iso_42001_soa_report.json) |
| **Harmonized QMS (EN 18286)** | [`docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md`](file:///Users/andriileukhin/Documents/SovereignNexus/docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md) | `scripts/run_integration_gates_g1_g7.py` | `artifacts/integration_gates_g1_g7_report.json` |
| **Supply Chain & CBOM** | [`src/cbom_and_scitt_otel_exporter.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/cbom_and_scitt_otel_exporter.py) | `tests/test_scitt_otel_and_pqc_cbom_agility.py` | [`evidence/cbom.json`](file:///Users/andriileukhin/Documents/SovereignNexus/evidence/cbom.json) |
| **SCITT Merkle Transparency** | [`tools/verify_cose_scitt_receipts.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tools/verify_cose_scitt_receipts.py) | `tests/test_phase4_scitt_cose_cli.py` | RFC 9942 Header 394 Transparent Receipts |
| **TCC Concurrency Escrow** | [`aeib-native-runtime/src/sqlite_acid_tcc_boundary.py`](file:///Users/andriileukhin/Documents/SovereignNexus/aeib-native-runtime/src/sqlite_acid_tcc_boundary.py) | `aeib-native-runtime/tests/test_tcc_parallel_acid_vs_base_anomalies.py` | Zero budget overruns observed |
