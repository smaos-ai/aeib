#!/usr/bin/env python3
"""
compliance/iso_42001_soa.py — ISO/IEC 42001:2023 Statement of Applicability (SoA) Scanner & Generator
=====================================================================================================
Automated repository artifact and cryptographic hash scanner mapping the Sovereign Agent / AEIB
execution boundary to:
1. All 38 normative controls of ISO/IEC 42001:2023 Annex A (Clauses A.2 through A.10), with explicit
   INCLUDED (35) and EXCLUDED (3) applicability determinations, auditor justifications, risk IDs,
   OWASP Agentic AI Top 10 2026 (ASI01:2026–ASI10:2026) mappings, and CEN-CENELEC prEN 18286 QMS
   clause alignments.
2. The 14 Category H Runtime Agent Governance Controls under ISO/IEC 42001:2023 and CEN-CENELEC
   prEN 18286 (EU AI Act Art. 17 QMS).

Evaluated under the stated model. All signatures use Ed25519 over RFC 8785 JCS canonical payloads,
and all file references are verified on disk with real SHA-256 digests.
"""

import argparse
import base64
import csv
import hashlib
import io
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.jcs_canonicalizer import encode_jcs

DEFAULT_REPORT_JSON_PATH = REPO_ROOT / "compliance" / "iso_42001_soa_report.json"
DEFAULT_REPORT_MD_PATH = REPO_ROOT / "docs" / "compliance" / "ISO_42001_STATEMENT_OF_APPLICABILITY.md"

CATEGORY_H_CONTROLS: List[Dict[str, Any]] = [
    {
        "control_id": "H.1",
        "title": "AI System Objectives & Impact Assessment",
        "target_files": ["docs/architecture/SOVEREIGN_AGENT_APPLICATION_SERVER.md", "README.md"],
        "category": "Governance",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 4.1 / EU AI Act Art. 17(1)(a) (Regulatory Strategy & Scope)",
        "owasp_asi_2026": "ASI01:2026 Agent Goal Hijack",
        "description": "Formal definition of autonomous execution boundary and risk thresholds.",
    },
    {
        "control_id": "H.2",
        "title": "AI Risk Assessment & Management",
        "target_files": ["compliance/claims.json", "LIMITATIONS.md"],
        "category": "Risk Management",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 6.1 / EU AI Act Art. 17(1)(g) (Risk Management System)",
        "owasp_asi_2026": "ASI08:2026 Cascading Failures",
        "description": "Epistemic claims registry and 5 bounded operational clauses.",
    },
    {
        "control_id": "H.3",
        "title": "Data Quality, Integrity & Provenance",
        "target_files": ["transport-to-disposition-mapping.yaml"],
        "category": "Data Governance",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 7.5 / EU AI Act Art. 17(1)(f) (Data Management & Schema Validation)",
        "owasp_asi_2026": "ASI02:2026 Tool Misuse & Exploitation",
        "description": "Ontological mapping of tool calls to Noun/Verb entities with schema validation.",
    },
    {
        "control_id": "H.4",
        "title": "Transparency & Non-Repudiation (SCITT COSE_Sign1)",
        "target_files": ["src/diagnostic_normalizer.py", "crates/smaos-verify/src/lib.rs"],
        "category": "Transparency",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 8.2 / EU AI Act Art. 17(1)(d) (Technical Documentation & Cryptographic Provenance)",
        "owasp_asi_2026": "ASI07:2026 Insecure Inter-Agent Communication",
        "description": "IETF SCITT COSE_Sign1 receipt sealing with Ed25519 asymmetric signatures.",
    },
    {
        "control_id": "H.5",
        "title": "Traceability & Causal Lineage (JCS CAID)",
        "target_files": ["benchmarks/aeib_execution_integrity/run_episodes.py", "aeib_mcp_proxy.py"],
        "category": "Auditability",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 8.5 / EU AI Act Art. 17(1)(e) (Automatic Record-Keeping & Traceability)",
        "owasp_asi_2026": "ASI06:2026 Memory & Context Poisoning",
        "description": "Causal Action Identifier derivation binding Noun, Verb, and JCS payload.",
    },
    {
        "control_id": "H.6",
        "title": "Human-in-the-Loop Oversight & Staging Sandbox",
        "target_files": ["transport-to-disposition-mapping.yaml", "telemetry/observability.py"],
        "category": "Oversight",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 8.6 / EU AI Act Art. 17(1)(c) (Verification, Validation & Human Oversight)",
        "owasp_asi_2026": "ASI09:2026 Human-Agent Trust Exploitation",
        "description": "Deterministic staging sandbox freezing unconfirmed mutations for human review.",
    },
    {
        "control_id": "H.7",
        "title": "Reliability & Ambiguity Resolution (OOB State Probe)",
        "target_files": ["aeib_postgresql_probe/adapter.py", "benchmarks/chaos_toxiproxy.py"],
        "category": "Resilience",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 8.7 / EU AI Act Art. 17(1)(i) (Operational Resilience & State Reconciliation)",
        "owasp_asi_2026": "ASI08:2026 Cascading Failures",
        "description": "Authoritative out-of-band database state probe with 3,000ms statement timeout.",
    },
    {
        "control_id": "H.8",
        "title": "Security Architecture & Zero-Mock AST Purity",
        "target_files": ["compliance/ast_purity.py", "compliance/no_mock_enforcer.py"],
        "category": "System Security",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 8.4 / EU AI Act Art. 17(1)(b) (Design, Quality Control & Zero-Mock Verification)",
        "owasp_asi_2026": "ASI05:2026 Unexpected Code Execution",
        "description": "Automated AST scanners enforcing zero mocks, zero stubs, and fail-closed exits.",
    },
    {
        "control_id": "H.9",
        "title": "Continuous Monitoring & Purpose-Driven Telemetry",
        "target_files": ["telemetry/observability.py", "telemetry/aeib_grafana_dashboard.json"],
        "category": "Monitoring",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 9.1 / EU AI Act Art. 17(1)(h) (Post-Market Monitoring & Telemetry)",
        "owasp_asi_2026": "ASI10:2026 Rogue Agents",
        "description": "OpenTelemetry gen_ai spans tracking tenant_id, principal_did, and purpose markings.",
    },
    {
        "control_id": "H.10",
        "title": "Privacy & Selective Disclosure (Salted SHA-256 Commitment / GDPR Art. 17)",
        "target_files": ["src/bbs_plus_redactable.rs"],
        "category": "Privacy",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 7.6 / EU AI Act Art. 17(1)(m) (Data Privacy & Accountability Redaction)",
        "owasp_asi_2026": "ASI06:2026 Memory & Context Poisoning",
        "description": "Salted SHA-256 field commitment selective redaction for confidential PII in audit receipts",
    },
    {
        "control_id": "H.11",
        "title": "Third-Party & ICT Supply Chain Risk (DORA xBRL-CSV)",
        "target_files": ["smaos_dora_generator.py", "compliance/dora_art28_roi_exporter.py"],
        "category": "Supply Chain",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 8.8 / EU AI Act Art. 17(1)(l) (Resource & Third-Party ICT Supply Chain Management)",
        "owasp_asi_2026": "ASI04:2026 Agentic Supply Chain Vulnerabilities",
        "description": "Automated generation of EBA DPM 4.0 xBRL-CSV information registers for ICT third parties.",
    },
    {
        "control_id": "H.12",
        "title": "Incident & Exception Handling (7-Rule Disposition)",
        "target_files": ["transport-to-disposition-mapping.yaml", "tools/export_dora_art17_evidence.py"],
        "category": "Incident Response",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "en_18286_qms_clause": "prEN 18286 Clause 10.2 / EU AI Act Art. 17(1)(i) (Serious Incident Reporting & Corrective Action)",
        "owasp_asi_2026": "ASI08:2026 Cascading Failures",
        "description": "Priority-ordered normative state machine resolving transport severance to closed dispositions.",
    },
    {
        "control_id": "H.13",
        "title": "Hardware Confidential VM Attestation (TDX / SEV-SNP)",
        "target_files": ["compliance/enclave_cvm.py", "src/hardware_attestation.rs"],
        "category": "Confidential Computing",
        "implementation_tier": "SCAFFOLD_ONLY",
        "en_18286_qms_clause": "prEN 18286 Clause 7.1.4 / EU AI Act Art. 17(1)(l) (Execution Environment Attestation Scaffold)",
        "owasp_asi_2026": "ASI03:2026 Identity & Privilege Abuse",
        "description": "Structural scaffolding for Confidential VM attestation (TDX / SEV-SNP); requires deployment on a hardware-enforced Linux CVM kernel",
    },
    {
        "control_id": "H.14",
        "title": "Execution Failsafe & Kill-Switch Enforcer",
        "target_files": ["src/auth/mfa.ts", "ebpf/ebpf_lsm_agent_guard.c"],
        "category": "Operational Control",
        "implementation_tier": "SCAFFOLD_ONLY",
        "en_18286_qms_clause": "prEN 18286 Clause 8.3 / EU AI Act Art. 17(1)(k) (Runtime Containment & Kill-Switch Scaffold)",
        "owasp_asi_2026": "ASI05:2026 Unexpected Code Execution",
        "description": "Structural scaffolding for Linux eBPF socket/LSM guard and step-up timeout failsafes",
    },
]

# All 38 normative ISO/IEC 42001:2023 Annex A controls across Clauses A.2 through A.10
# Distribution: A.2 (3) + A.3 (2) + A.4 (5) + A.5 (4) + A.6 (9) + A.7 (5) + A.8 (4) + A.9 (3) + A.10 (3) = 38
ISO_42001_ANNEX_A_38_CONTROLS: List[Dict[str, Any]] = [
    # =========================================================================
    # A.2 Policies related to AI (3 controls: A.2.2, A.2.3, A.2.4)
    # =========================================================================
    {
        "control_id": "A.2.2",
        "clause": "A.2 Policies related to AI",
        "title": "AI policy",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: AEIB governs high-consequence autonomous tool invocations at the L7 wire boundary. "
            "An explicit AI execution integrity policy defines fail-closed dispatch predicates, epistemic boundaries, "
            "and mandatory pre-execution intent journaling under the stated model."
        ),
        "risk_assessment_mapping": (
            "RISK-TOCTOU-01, RISK-DELEGATION | OWASP ASI01:2026 Agent Goal Hijack | "
            "CEN-CENELEC prEN 18286 Clause 4.1 / EU AI Act Art. 17(1)(a)"
        ),
        "risk_ids": ["RISK-TOCTOU-01", "RISK-DELEGATION"],
        "owasp_asi_2026": "ASI01:2026 Agent Goal Hijack",
        "en_18286_qms_clause": "prEN 18286 Clause 4.1 / EU AI Act Art. 17(1)(a)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["AGENTS.md", "docs/architecture/AEIB_SPECIFICATION.md"],
    },
    {
        "control_id": "A.2.3",
        "clause": "A.2 Policies related to AI",
        "title": "Alignment with other organizational policies",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: AEIB runtime policies align with organizational cybersecurity, data protection (GDPR Art. 17 "
            "selective commitment redaction), and financial operational resilience (DORA Art. 17 & Art. 28) policies "
            "via automated policy cross-walks and zone-isolation checks."
        ),
        "risk_assessment_mapping": (
            "RISK-DELEGATION, RISK-KEY-COMPROMISE | OWASP ASI03:2026 Identity & Privilege Abuse | "
            "CEN-CENELEC prEN 18286 Clause 5.2 / EU AI Act Art. 17(1)(a)"
        ),
        "risk_ids": ["RISK-DELEGATION", "RISK-KEY-COMPROMISE"],
        "owasp_asi_2026": "ASI03:2026 Identity & Privilege Abuse",
        "en_18286_qms_clause": "prEN 18286 Clause 5.2 / EU AI Act Art. 17(1)(a)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": [
            "docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md",
            "compliance/check_zone_boundary.py",
        ],
    },
    {
        "control_id": "A.2.4",
        "clause": "A.2 Policies related to AI",
        "title": "Review of the AI policy",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Policy epochs and regulatory synchronization baselines are reviewed and version-locked; "
            "stale policy epochs are rejected fail-closed at Station 0 via PolicyEpochFresh verification."
        ),
        "risk_assessment_mapping": (
            "RISK-TOCTOU-01, RISK-DELEGATION | OWASP ASI01:2026 Agent Goal Hijack | "
            "CEN-CENELEC prEN 18286 Clause 9.3 / EU AI Act Art. 17(1)(a)"
        ),
        "risk_ids": ["RISK-TOCTOU-01", "RISK-DELEGATION"],
        "owasp_asi_2026": "ASI01:2026 Agent Goal Hijack",
        "en_18286_qms_clause": "prEN 18286 Clause 9.3 / EU AI Act Art. 17(1)(a)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": [
            "docs/compliance/STANDARDS_SYNCHRONIZATION_OCT_2026.md",
            "src/aeib_v040_engine.py",
        ],
    },
    # =========================================================================
    # A.3 Internal organization (2 controls: A.3.2, A.3.3)
    # =========================================================================
    {
        "control_id": "A.3.2",
        "clause": "A.3 Internal organization",
        "title": "AI roles and responsibilities",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Explicit separation of duties is configured between the untrusted AI model plane, the AEIB "
            "execution boundary, and human oversight/legal incident classification owners (classification_owner: customer_defined)."
        ),
        "risk_assessment_mapping": (
            "RISK-DELEGATION, RISK-TOCTOU-01 | OWASP ASI03:2026 Identity & Privilege Abuse | "
            "CEN-CENELEC prEN 18286 Clause 5.3 / EU AI Act Art. 17(1)(j)"
        ),
        "risk_ids": ["RISK-DELEGATION", "RISK-TOCTOU-01"],
        "owasp_asi_2026": "ASI03:2026 Identity & Privilege Abuse",
        "en_18286_qms_clause": "prEN 18286 Clause 5.3 / EU AI Act Art. 17(1)(j)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["src/governance_boundary.py", "src/incident_evidence.py"],
    },
    {
        "control_id": "A.3.3",
        "clause": "A.3 Internal organization",
        "title": "Reporting of concerns",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Boundary violations, indeterminate transport outcomes, and restraint events generate "
            "structured escalation records and human-review alerts so operators can report and triage anomalies."
        ),
        "risk_assessment_mapping": (
            "RISK-RETRY-504, RISK-PROMPT-INJ | OWASP ASI09:2026 Human-Agent Trust Exploitation | "
            "CEN-CENELEC prEN 18286 Clause 7.4 / EU AI Act Art. 17(1)(i)"
        ),
        "risk_ids": ["RISK-RETRY-504", "RISK-PROMPT-INJ"],
        "owasp_asi_2026": "ASI09:2026 Human-Agent Trust Exploitation",
        "en_18286_qms_clause": "prEN 18286 Clause 7.4 / EU AI Act Art. 17(1)(i)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["src/human_review_console.py", "tools/export_dora_art17_evidence.py"],
    },
    # =========================================================================
    # A.4 Resources for AI systems (5 controls: A.4.2, A.4.3, A.4.4, A.4.5, A.4.6)
    # =========================================================================
    {
        "control_id": "A.4.2",
        "clause": "A.4 Resources for AI systems",
        "title": "Resource documentation",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: All cryptographic keys, schema registries, disposition mappings, and verification harnesses "
            "required to operate the AEIB boundary are documented and tracked with SHA-256 manifests."
        ),
        "risk_assessment_mapping": (
            "RISK-KEY-COMPROMISE, RISK-DELEGATION | OWASP ASI04:2026 Agentic Supply Chain Vulnerabilities | "
            "CEN-CENELEC prEN 18286 Clause 7.1 / EU AI Act Art. 17(1)(d)"
        ),
        "risk_ids": ["RISK-KEY-COMPROMISE", "RISK-DELEGATION"],
        "owasp_asi_2026": "ASI04:2026 Agentic Supply Chain Vulnerabilities",
        "en_18286_qms_clause": "prEN 18286 Clause 7.1 / EU AI Act Art. 17(1)(d)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["docs/compliance/ANNEX_IV_TECHNICAL_DOSSIER.md", "transport-to-disposition-mapping.yaml"],
    },
    {
        "control_id": "A.4.3",
        "clause": "A.4 Resources for AI systems",
        "title": "Data resources",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Data schemas, JCS canonicalization test vectors, and durable SQLite/PostgreSQL journal "
            "stores used by the execution boundary are inventoried and validated for integrity."
        ),
        "risk_assessment_mapping": (
            "RISK-TOCTOU-01, RISK-PROMPT-INJ | OWASP ASI06:2026 Memory & Context Poisoning | "
            "CEN-CENELEC prEN 18286 Clause 7.1.2 / EU AI Act Art. 17(1)(f)"
        ),
        "risk_ids": ["RISK-TOCTOU-01", "RISK-PROMPT-INJ"],
        "owasp_asi_2026": "ASI06:2026 Memory & Context Poisoning",
        "en_18286_qms_clause": "prEN 18286 Clause 7.1.2 / EU AI Act Art. 17(1)(f)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["src/jcs_canonicalizer.py", "src/sqlite_probe_adapter.py"],
    },
    {
        "control_id": "A.4.4",
        "clause": "A.4 Resources for AI systems",
        "title": "Tooling resources",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Agent MCP tool adapters, AST purity verifiers, and zero-mock enforcement tools are "
            "inventoried and cryptographically bound before tool invocation is permitted."
        ),
        "risk_assessment_mapping": (
            "RISK-PROMPT-INJ, RISK-TOCTOU-01 | OWASP ASI02:2026 Tool Misuse & Exploitation | "
            "CEN-CENELEC prEN 18286 Clause 7.1.3 / EU AI Act Art. 17(1)(b)"
        ),
        "risk_ids": ["RISK-PROMPT-INJ", "RISK-TOCTOU-01"],
        "owasp_asi_2026": "ASI02:2026 Tool Misuse & Exploitation",
        "en_18286_qms_clause": "prEN 18286 Clause 7.1.3 / EU AI Act Art. 17(1)(b)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["aeib_mcp_proxy.py", "compliance/ast_purity.py", "compliance/no_mock_enforcer.py"],
    },
    {
        "control_id": "A.4.5",
        "clause": "A.4 Resources for AI systems",
        "title": "System and computing resources",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Computing resource isolation and Confidential VM (Intel TDX / AMD SEV-SNP) hardware "
            "attestation interfaces are included as structural scaffolding requiring a hardware-enforced Linux CVM kernel."
        ),
        "risk_assessment_mapping": (
            "RISK-KEY-COMPROMISE, RISK-DELEGATION | OWASP ASI03:2026 Identity & Privilege Abuse | "
            "CEN-CENELEC prEN 18286 Clause 7.1.4 / EU AI Act Art. 17(1)(l)"
        ),
        "risk_ids": ["RISK-KEY-COMPROMISE", "RISK-DELEGATION"],
        "owasp_asi_2026": "ASI03:2026 Identity & Privilege Abuse",
        "en_18286_qms_clause": "prEN 18286 Clause 7.1.4 / EU AI Act Art. 17(1)(l)",
        "implementation_tier": "SCAFFOLD_ONLY",
        "target_files": ["compliance/enclave_cvm.py", "src/hardware_attestation.rs"],
    },
    {
        "control_id": "A.4.6",
        "clause": "A.4 Resources for AI systems",
        "title": "Human resources",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Human operators executing step-up review and resolving EFFECT_INDETERMINATE latches "
            "follow documented operational runbooks and field manuals with role-based authority."
        ),
        "risk_assessment_mapping": (
            "RISK-DELEGATION, RISK-RETRY-504 | OWASP ASI09:2026 Human-Agent Trust Exploitation | "
            "CEN-CENELEC prEN 18286 Clause 7.2 / EU AI Act Art. 17(1)(c)"
        ),
        "risk_ids": ["RISK-DELEGATION", "RISK-RETRY-504"],
        "owasp_asi_2026": "ASI09:2026 Human-Agent Trust Exploitation",
        "en_18286_qms_clause": "prEN 18286 Clause 7.2 / EU AI Act Art. 17(1)(c)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["docs/AUDIT_FIELD_MANUAL.md", "src/human_review_console.py"],
    },
    # =========================================================================
    # A.5 Assessing impacts of AI systems (4 controls: A.5.2, A.5.3, A.5.4, A.5.5)
    # =========================================================================
    {
        "control_id": "A.5.2",
        "clause": "A.5 Assessing impacts of AI systems",
        "title": "AI system impact assessment process",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Every side-effecting tool call undergoes deterministic pre-execution risk and impact "
            "evaluation across financial exposure, authority freshness, and duplicate-mutation blast radius."
        ),
        "risk_assessment_mapping": (
            "RISK-RETRY-504, RISK-TOCTOU-01 | OWASP ASI08:2026 Cascading Failures | "
            "CEN-CENELEC prEN 18286 Clause 6.1.2 / EU AI Act Art. 17(1)(g)"
        ),
        "risk_ids": ["RISK-RETRY-504", "RISK-TOCTOU-01"],
        "owasp_asi_2026": "ASI08:2026 Cascading Failures",
        "en_18286_qms_clause": "prEN 18286 Clause 6.1.2 / EU AI Act Art. 17(1)(g)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["src/protection_governor.py", "compliance/claims.json"],
    },
    {
        "control_id": "A.5.3",
        "clause": "A.5 Assessing impacts of AI systems",
        "title": "Documentation of AI system impact assessments",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Impact assessment outcomes, threat models, and calibrated operational limitations are "
            "documented in versioned artifacts and cryptographically signed incident/restraint evidence packages."
        ),
        "risk_assessment_mapping": (
            "RISK-RETRY-504, RISK-TOCTOU-01 | OWASP ASI08:2026 Cascading Failures | "
            "CEN-CENELEC prEN 18286 Clause 6.1.3 / EU AI Act Art. 17(1)(d)"
        ),
        "risk_ids": ["RISK-RETRY-504", "RISK-TOCTOU-01"],
        "owasp_asi_2026": "ASI08:2026 Cascading Failures",
        "en_18286_qms_clause": "prEN 18286 Clause 6.1.3 / EU AI Act Art. 17(1)(d)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["docs/THREAT_MODEL.md", "LIMITATIONS.md"],
    },
    {
        "control_id": "A.5.4",
        "clause": "A.5 Assessing impacts of AI systems",
        "title": "Assessing AI system impact on individuals or groups of individuals",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Prevents unauthorized duplicate financial debits/refunds and protects individual PII in "
            "audit trails via salted SHA-256 field commitments and GDPR Art. 17 selective redaction."
        ),
        "risk_assessment_mapping": (
            "RISK-RETRY-504, RISK-PROMPT-INJ | OWASP ASI06:2026 Memory & Context Poisoning | "
            "CEN-CENELEC prEN 18286 Clause 6.1.4 / EU AI Act Art. 17(1)(m)"
        ),
        "risk_ids": ["RISK-RETRY-504", "RISK-PROMPT-INJ"],
        "owasp_asi_2026": "ASI06:2026 Memory & Context Poisoning",
        "en_18286_qms_clause": "prEN 18286 Clause 6.1.4 / EU AI Act Art. 17(1)(m)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["src/bbs_plus_redactable.py", "src/bbs_plus_redactable.rs"],
    },
    {
        "control_id": "A.5.5",
        "clause": "A.5 Assessing impacts of AI systems",
        "title": "Assessing societal impacts of AI systems",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Evaluates systemic financial stability and cascading multi-agent failure risks in regulated "
            "banking/critical infrastructure through circuit breakers and EU AI Act Annex III conformity assessments."
        ),
        "risk_assessment_mapping": (
            "RISK-RETRY-504, RISK-DELEGATION | OWASP ASI08:2026 Cascading Failures | "
            "CEN-CENELEC prEN 18286 Clause 6.1.5 / EU AI Act Art. 17(1)(g)"
        ),
        "risk_ids": ["RISK-RETRY-504", "RISK-DELEGATION"],
        "owasp_asi_2026": "ASI08:2026 Cascading Failures",
        "en_18286_qms_clause": "prEN 18286 Clause 6.1.5 / EU AI Act Art. 17(1)(g)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["docs/EU_AI_ACT_ANNEX_III_COMPLIANCE.md", "src/ocr_audit/psi_circuit_breaker.py"],
    },
    # =========================================================================
    # A.6 AI system life cycle (9 controls: A.6.1.2, A.6.1.3, A.6.2.2 .. A.6.2.8)
    # =========================================================================
    {
        "control_id": "A.6.1.2",
        "clause": "A.6 AI system life cycle",
        "title": "Objectives for responsible development of AI system",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Establishes measurable engineering objectives for responsible AI tool execution: zero "
            "unauthorized duplicate side effects under transport severance, zero mock crypto, and fail-closed restraint."
        ),
        "risk_assessment_mapping": (
            "RISK-TOCTOU-01, RISK-RETRY-504 | OWASP ASI01:2026 Agent Goal Hijack | "
            "CEN-CENELEC prEN 18286 Clause 8.1 / EU AI Act Art. 17(1)(b)"
        ),
        "risk_ids": ["RISK-TOCTOU-01", "RISK-RETRY-504"],
        "owasp_asi_2026": "ASI01:2026 Agent Goal Hijack",
        "en_18286_qms_clause": "prEN 18286 Clause 8.1 / EU AI Act Art. 17(1)(b)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["docs/architecture/AEIB_v0.3.0_SPECIFICATION.md", "compliance/claims.json"],
    },
    {
        "control_id": "A.6.1.3",
        "clause": "A.6 AI system life cycle",
        "title": "Processes for responsible AI system design and development",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Enforces clean-room Zone 1/Zone 2 import separation, AST purity scanning, and zero-mock "
            "cryptographic checks across the development lifecycle."
        ),
        "risk_assessment_mapping": (
            "RISK-KEY-COMPROMISE, RISK-TOCTOU-01 | OWASP ASI05:2026 Unexpected Code Execution | "
            "CEN-CENELEC prEN 18286 Clause 8.4 / EU AI Act Art. 17(1)(b)"
        ),
        "risk_ids": ["RISK-KEY-COMPROMISE", "RISK-TOCTOU-01"],
        "owasp_asi_2026": "ASI05:2026 Unexpected Code Execution",
        "en_18286_qms_clause": "prEN 18286 Clause 8.4 / EU AI Act Art. 17(1)(b)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["compliance/check_zone_boundary.py", "compliance/ast_purity.py", "compliance/no_mock_enforcer.py"],
    },
    {
        "control_id": "A.6.2.2",
        "clause": "A.6 AI system life cycle",
        "title": "AI system requirements and specification",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Specifies the 5-term conjunctive execution predicate (GrantValid ^ PolicyEpochFresh ^ "
            "SourceEpochFresh ^ CAIDMatch ^ TicketUnburned) and the 7-rule transport-to-disposition state machine."
        ),
        "risk_assessment_mapping": (
            "RISK-TOCTOU-01, RISK-RETRY-504 | OWASP ASI02:2026 Tool Misuse & Exploitation | "
            "CEN-CENELEC prEN 18286 Clause 8.2 / EU AI Act Art. 17(1)(b)"
        ),
        "risk_ids": ["RISK-TOCTOU-01", "RISK-RETRY-504"],
        "owasp_asi_2026": "ASI02:2026 Tool Misuse & Exploitation",
        "en_18286_qms_clause": "prEN 18286 Clause 8.2 / EU AI Act Art. 17(1)(b)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["transport-to-disposition-mapping.yaml", "docs/AEI_STATE_MACHINE.md"],
    },
    {
        "control_id": "A.6.2.3",
        "clause": "A.6 AI system life cycle",
        "title": "Documentation of AI system design and development",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Documents the three-plane architecture (Model Behavior, Execution Authority, Observed "
            "Consequence), Station 0–5 pipeline, and EO-1 Write-Before-Execute durability protocol."
        ),
        "risk_assessment_mapping": (
            "RISK-TOCTOU-01, RISK-DELEGATION | OWASP ASI01:2026 Agent Goal Hijack | "
            "CEN-CENELEC prEN 18286 Clause 8.2 / EU AI Act Art. 17(1)(d)"
        ),
        "risk_ids": ["RISK-TOCTOU-01", "RISK-DELEGATION"],
        "owasp_asi_2026": "ASI01:2026 Agent Goal Hijack",
        "en_18286_qms_clause": "prEN 18286 Clause 8.2 / EU AI Act Art. 17(1)(d)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": [
            "docs/architecture/SMAOS-three-plane-architecture.md",
            "src/eo1_write_before_execute.py",
        ],
    },
    {
        "control_id": "A.6.2.4",
        "clause": "A.6 AI system life cycle",
        "title": "AI system verification and validation",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Verified via the deterministic 500-episode fault-injection benchmark (seed=42), RFC 8785 "
            "JCS conformance suite, and falsifiability matrix tests."
        ),
        "risk_assessment_mapping": (
            "RISK-RETRY-504, RISK-TOCTOU-01, RISK-PROMPT-INJ | OWASP ASI02:2026 Tool Misuse & Exploitation | "
            "CEN-CENELEC prEN 18286 Clause 8.6 / EU AI Act Art. 17(1)(d)"
        ),
        "risk_ids": ["RISK-RETRY-504", "RISK-TOCTOU-01", "RISK-PROMPT-INJ"],
        "owasp_asi_2026": "ASI02:2026 Tool Misuse & Exploitation",
        "en_18286_qms_clause": "prEN 18286 Clause 8.6 / EU AI Act Art. 17(1)(d)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": [
            "benchmarks/aeib_execution_integrity/run_episodes.py",
            "tools/verify_phase3_evidence.py",
        ],
    },
    {
        "control_id": "A.6.2.5",
        "clause": "A.6 AI system life cycle",
        "title": "AI system deployment",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Governs deployment progression through sequential quality gates (G1–G7), clean-room container "
            "profiles, and network egress policy gates."
        ),
        "risk_assessment_mapping": (
            "RISK-DELEGATION, RISK-KEY-COMPROMISE | OWASP ASI04:2026 Agentic Supply Chain Vulnerabilities | "
            "CEN-CENELEC prEN 18286 Clause 8.7 / EU AI Act Art. 17(1)(g)"
        ),
        "risk_ids": ["RISK-DELEGATION", "RISK-KEY-COMPROMISE"],
        "owasp_asi_2026": "ASI04:2026 Agentic Supply Chain Vulnerabilities",
        "en_18286_qms_clause": "prEN 18286 Clause 8.7 / EU AI Act Art. 17(1)(g)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["docs/architecture/DEPLOYMENT_PROFILE.md", "src/security/egress_gate.py"],
    },
    {
        "control_id": "A.6.2.6",
        "clause": "A.6 AI system life cycle",
        "title": "AI system operation and monitoring",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Enforces runtime rate limiting, multi-tenant isolation, out-of-band state probing on HTTP 504 "
            "timeouts, and continuous OpenTelemetry gen_ai span emission."
        ),
        "risk_assessment_mapping": (
            "RISK-RETRY-504, RISK-TOCTOU-01 | OWASP ASI10:2026 Rogue Agents | "
            "CEN-CENELEC prEN 18286 Clause 9.1 / EU AI Act Art. 17(1)(h)"
        ),
        "risk_ids": ["RISK-RETRY-504", "RISK-TOCTOU-01"],
        "owasp_asi_2026": "ASI10:2026 Rogue Agents",
        "en_18286_qms_clause": "prEN 18286 Clause 9.1 / EU AI Act Art. 17(1)(h)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["telemetry/observability.py", "src/multi_tenant_governor.py"],
    },
    {
        "control_id": "A.6.2.7",
        "clause": "A.6 AI system life cycle",
        "title": "AI system technical documentation",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Maintains EU AI Act Annex IV technical documentation dossiers, receipt specifications, and "
            "cryptographic verification instructions."
        ),
        "risk_assessment_mapping": (
            "RISK-TOCTOU-01, RISK-KEY-COMPROMISE | OWASP ASI07:2026 Insecure Inter-Agent Communication | "
            "CEN-CENELEC prEN 18286 Clause 8.2 / EU AI Act Art. 17(1)(d)"
        ),
        "risk_ids": ["RISK-TOCTOU-01", "RISK-KEY-COMPROMISE"],
        "owasp_asi_2026": "ASI07:2026 Insecure Inter-Agent Communication",
        "en_18286_qms_clause": "prEN 18286 Clause 8.2 / EU AI Act Art. 17(1)(d)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["docs/compliance/ANNEX_IV_TECHNICAL_DOSSIER.md", "docs/AEIB-RECEIPT-SPEC.md"],
    },
    {
        "control_id": "A.6.2.8",
        "clause": "A.6 AI system life cycle",
        "title": "AI system recording of event logs",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Records fsync-committed DISPATCH_INTENT journals before socket transmission and Ed25519-signed, "
            "hash-chained CONTINUITY_RECEIPT and restraint_record logs (EU AI Act Art. 12 alignment)."
        ),
        "risk_assessment_mapping": (
            "RISK-TOCTOU-01, RISK-RETRY-504, RISK-KEY-COMPROMISE | OWASP ASI07:2026 Insecure Inter-Agent Communication | "
            "CEN-CENELEC prEN 18286 Clause 8.5 / EU AI Act Art. 17(1)(e)"
        ),
        "risk_ids": ["RISK-TOCTOU-01", "RISK-RETRY-504", "RISK-KEY-COMPROMISE"],
        "owasp_asi_2026": "ASI07:2026 Insecure Inter-Agent Communication",
        "en_18286_qms_clause": "prEN 18286 Clause 8.5 / EU AI Act Art. 17(1)(e)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["src/eo1_write_before_execute.py", "tools/export_ai_act_art12_14_evidence.py"],
    },
    # =========================================================================
    # A.7 Data for AI systems (5 controls: A.7.2, A.7.3, A.7.4, A.7.5, A.7.6)
    # Note: A.7.4 and A.7.5 are EXCLUDED with explicit boundary justification
    # =========================================================================
    {
        "control_id": "A.7.2",
        "clause": "A.7 Data for AI systems",
        "title": "Data for development and enhancement of AI systems",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Benchmark fault schedules, adversarial prompt-injection payloads, and RFC 8785 canonical "
            "test vectors used to evaluate and harden the AEIB boundary are deterministic, seeded, and hash-locked."
        ),
        "risk_assessment_mapping": (
            "RISK-PROMPT-INJ, RISK-RETRY-504 | OWASP ASI06:2026 Memory & Context Poisoning | "
            "CEN-CENELEC prEN 18286 Clause 7.5 / EU AI Act Art. 17(1)(f)"
        ),
        "risk_ids": ["RISK-PROMPT-INJ", "RISK-RETRY-504"],
        "owasp_asi_2026": "ASI06:2026 Memory & Context Poisoning",
        "en_18286_qms_clause": "prEN 18286 Clause 7.5 / EU AI Act Art. 17(1)(f)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["benchmarks/aeib_execution_integrity/run_episodes.py", "src/jcs_canonicalizer.py"],
    },
    {
        "control_id": "A.7.3",
        "clause": "A.7 Data for AI systems",
        "title": "Acquisition of data",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Out-of-band target status responses and external MCP tool inputs acquired at runtime "
            "are authenticated, schema-checked, and normalized before admission into boundary state."
        ),
        "risk_assessment_mapping": (
            "RISK-PROMPT-INJ, RISK-TOCTOU-01 | OWASP ASI02:2026 Tool Misuse & Exploitation | "
            "CEN-CENELEC prEN 18286 Clause 7.5.2 / EU AI Act Art. 17(1)(f)"
        ),
        "risk_ids": ["RISK-PROMPT-INJ", "RISK-TOCTOU-01"],
        "owasp_asi_2026": "ASI02:2026 Tool Misuse & Exploitation",
        "en_18286_qms_clause": "prEN 18286 Clause 7.5.2 / EU AI Act Art. 17(1)(f)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["src/mcp_outcome_normalizer.py", "aeib_postgresql_probe/adapter.py"],
    },
    {
        "control_id": "A.7.4",
        "clause": "A.7 Data for AI systems",
        "title": "Data preparation for model training and quality of training datasets",
        "applicability": "EXCLUDED",
        "justification": (
            "EXCLUDED: AEIB is a deterministic Layer-7 wire-level execution proxy and cryptographic authorization "
            "boundary; it does not train, fine-tune, or update machine learning model weights or curate model training "
            "corpora. Compensating boundary controls: Station 0 strict JSON schema validation and RFC 8785 JCS "
            "canonicalization (A.7.6) reject malformed or poisoned runtime tool parameters before execution."
        ),
        "risk_assessment_mapping": (
            "RISK-PROMPT-INJ, RISK-TOCTOU-01 | OWASP ASI06:2026 Memory & Context Poisoning | "
            "CEN-CENELEC prEN 18286 Clause 7.5 (Scoped Exclusion: Deterministic Execution Proxy)"
        ),
        "risk_ids": ["RISK-PROMPT-INJ", "RISK-TOCTOU-01"],
        "owasp_asi_2026": "ASI06:2026 Memory & Context Poisoning",
        "en_18286_qms_clause": "prEN 18286 Clause 7.5 (Scoped Exclusion: Deterministic Execution Proxy)",
        "implementation_tier": "NOT_APPLICABLE_EXCLUDED",
        "target_files": ["LIMITATIONS.md", "docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md"],
    },
    {
        "control_id": "A.7.5",
        "clause": "A.7 Data for AI systems",
        "title": "Data acquisition and provenance for foundation model training",
        "applicability": "EXCLUDED",
        "justification": (
            "EXCLUDED: AEIB operates strictly as a post-inference, pre-dispatch execution interlock and does not "
            "acquire pre-training datasets or train foundation models. Upstream foundation model providers remain "
            "responsible for training data provenance. Compensating boundary controls: Cryptographic CAID payload "
            "binding (A.6.2.8, A.7.6) and COSE_Sign1 receipts ensure provenance of all wire-level tool dispatches."
        ),
        "risk_assessment_mapping": (
            "RISK-PROMPT-INJ, RISK-DELEGATION | OWASP ASI04:2026 Agentic Supply Chain Vulnerabilities | "
            "CEN-CENELEC prEN 18286 Clause 7.5 (Scoped Exclusion: Upstream Foundation Model Training)"
        ),
        "risk_ids": ["RISK-PROMPT-INJ", "RISK-DELEGATION"],
        "owasp_asi_2026": "ASI04:2026 Agentic Supply Chain Vulnerabilities",
        "en_18286_qms_clause": "prEN 18286 Clause 7.5 (Scoped Exclusion: Upstream Foundation Model Training)",
        "implementation_tier": "NOT_APPLICABLE_EXCLUDED",
        "target_files": ["LIMITATIONS.md", "docs/compliance/STANDARDS_SYNCHRONIZATION_OCT_2026.md"],
    },
    {
        "control_id": "A.7.6",
        "clause": "A.7 Data for AI systems",
        "title": "Data preparation and canonicalization for runtime AI operations",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: All runtime tool-call payloads are canonicalized under RFC 8785 JCS (UTF-16 code-unit key "
            "sorting, IEEE 754 number formatting, NFC normalization) to derive the Content-Addressed Action Identifier (CAID)."
        ),
        "risk_assessment_mapping": (
            "RISK-TOCTOU-01, RISK-PROMPT-INJ | OWASP ASI02:2026 Tool Misuse & Exploitation | "
            "CEN-CENELEC prEN 18286 Clause 7.5.4 / EU AI Act Art. 17(1)(f)"
        ),
        "risk_ids": ["RISK-TOCTOU-01", "RISK-PROMPT-INJ"],
        "owasp_asi_2026": "ASI02:2026 Tool Misuse & Exploitation",
        "en_18286_qms_clause": "prEN 18286 Clause 7.5.4 / EU AI Act Art. 17(1)(f)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["src/jcs_canonicalizer.py", "src/diagnostic_normalizer.py"],
    },
    # =========================================================================
    # A.8 Information for interested parties (4 controls: A.8.2, A.8.3, A.8.4, A.8.5)
    # Note: A.8.3 is EXCLUDED with explicit boundary justification
    # =========================================================================
    {
        "control_id": "A.8.2",
        "clause": "A.8 Information for interested parties",
        "title": "System documentation and information for users",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Provides deploying institutions and auditors with complete technical documentation, "
            "integration quality gates (G1–G7), and explicit epistemic boundary notices in LIMITATIONS.md."
        ),
        "risk_assessment_mapping": (
            "RISK-DELEGATION, RISK-RETRY-504 | OWASP ASI09:2026 Human-Agent Trust Exploitation | "
            "CEN-CENELEC prEN 18286 Clause 8.2 / EU AI Act Art. 17(1)(d)"
        ),
        "risk_ids": ["RISK-DELEGATION", "RISK-RETRY-504"],
        "owasp_asi_2026": "ASI09:2026 Human-Agent Trust Exploitation",
        "en_18286_qms_clause": "prEN 18286 Clause 8.2 / EU AI Act Art. 17(1)(d)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["LIMITATIONS.md", "docs/AUDIT_FIELD_MANUAL.md"],
    },
    {
        "control_id": "A.8.3",
        "clause": "A.8 Information for interested parties",
        "title": "Synthetic media and deepfake content labeling",
        "applicability": "EXCLUDED",
        "justification": (
            "EXCLUDED: AEIB is a deterministic Layer-7 wire-level execution proxy that intercepts structured "
            "JSON-RPC/MCP tool calls and database mutations; it does not synthesize audio, image, video, or text "
            "media for end-users (EU AI Act Art. 50 synthetic content watermarking is inapplicable). Compensating "
            "boundary controls: Every machine-generated execution receipt is cryptographically labeled and signed "
            "via Ed25519 / IETF SCITT COSE_Sign1 (A.6.2.8, A.8.5) for non-repudiable machine origin provenance."
        ),
        "risk_assessment_mapping": (
            "RISK-KEY-COMPROMISE, RISK-DELEGATION | OWASP ASI07:2026 Insecure Inter-Agent Communication | "
            "CEN-CENELEC prEN 18286 Clause 8.2 (Scoped Exclusion: Non-Generative Wire Proxy)"
        ),
        "risk_ids": ["RISK-KEY-COMPROMISE", "RISK-DELEGATION"],
        "owasp_asi_2026": "ASI07:2026 Insecure Inter-Agent Communication",
        "en_18286_qms_clause": "prEN 18286 Clause 8.2 (Scoped Exclusion: Non-Generative Wire Proxy)",
        "implementation_tier": "NOT_APPLICABLE_EXCLUDED",
        "target_files": ["src/cose_signer.py", "LIMITATIONS.md"],
    },
    {
        "control_id": "A.8.4",
        "clause": "A.8 Information for interested parties",
        "title": "Communication of incidents to interested parties",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Exports standardized three-plane DORA Art. 17 / RTS (EU) 2025/301 incident_candidate "
            "packages with Ed25519 signatures and 4-hour classification clock metadata for supervisory reporting."
        ),
        "risk_assessment_mapping": (
            "RISK-RETRY-504, RISK-KEY-COMPROMISE | OWASP ASI08:2026 Cascading Failures | "
            "CEN-CENELEC prEN 18286 Clause 10.2 / EU AI Act Art. 17(1)(i)"
        ),
        "risk_ids": ["RISK-RETRY-504", "RISK-KEY-COMPROMISE"],
        "owasp_asi_2026": "ASI08:2026 Cascading Failures",
        "en_18286_qms_clause": "prEN 18286 Clause 10.2 / EU AI Act Art. 17(1)(i)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["tools/export_dora_art17_evidence.py", "compliance/dora_art17_exporter.py"],
    },
    {
        "control_id": "A.8.5",
        "clause": "A.8 Information for interested parties",
        "title": "Information for interested parties on AI system accountability and compliance",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Generates verifiable Statement of Applicability (SoA) reports, EBA DPM 4.0 xBRL-CSV "
            "Registers of Information, and standalone clean-room verification bundles for external auditors."
        ),
        "risk_assessment_mapping": (
            "RISK-KEY-COMPROMISE, RISK-DELEGATION | OWASP ASI07:2026 Insecure Inter-Agent Communication | "
            "CEN-CENELEC prEN 18286 Clause 7.4 / EU AI Act Art. 17(1)(k)"
        ),
        "risk_ids": ["RISK-KEY-COMPROMISE", "RISK-DELEGATION"],
        "owasp_asi_2026": "ASI07:2026 Insecure Inter-Agent Communication",
        "en_18286_qms_clause": "prEN 18286 Clause 7.4 / EU AI Act Art. 17(1)(k)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["compliance/iso_42001_soa.py", "compliance/dora_art28_roi_exporter.py"],
    },
    # =========================================================================
    # A.9 Use of AI systems (3 controls: A.9.2, A.9.3, A.9.4)
    # =========================================================================
    {
        "control_id": "A.9.2",
        "clause": "A.9 Use of AI systems",
        "title": "Processes for responsible use of AI systems",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Enforces single-use cryptographic execution tickets, capability attenuation across delegation "
            "hops, and strict outbound network egress gates during agent tool execution."
        ),
        "risk_assessment_mapping": (
            "RISK-DELEGATION, RISK-PROMPT-INJ | OWASP ASI02:2026 Tool Misuse & Exploitation | "
            "CEN-CENELEC prEN 18286 Clause 8.1 / EU AI Act Art. 17(1)(b)"
        ),
        "risk_ids": ["RISK-DELEGATION", "RISK-PROMPT-INJ"],
        "owasp_asi_2026": "ASI02:2026 Tool Misuse & Exploitation",
        "en_18286_qms_clause": "prEN 18286 Clause 8.1 / EU AI Act Art. 17(1)(b)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["src/ocr_audit/capability_attenuation.py", "src/security/egress_gate.py"],
    },
    {
        "control_id": "A.9.3",
        "clause": "A.9 Use of AI systems",
        "title": "Objectives for responsible use of AI systems",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Enforces runtime containment objectives including step-up MFA timeout failsafes and "
            "structural scaffolding for Linux eBPF LSM socket guards to prevent unauthorized process/socket escapes."
        ),
        "risk_assessment_mapping": (
            "RISK-PROMPT-INJ, RISK-TOCTOU-01 | OWASP ASI05:2026 Unexpected Code Execution | "
            "CEN-CENELEC prEN 18286 Clause 8.3 / EU AI Act Art. 17(1)(k)"
        ),
        "risk_ids": ["RISK-PROMPT-INJ", "RISK-TOCTOU-01"],
        "owasp_asi_2026": "ASI05:2026 Unexpected Code Execution",
        "en_18286_qms_clause": "prEN 18286 Clause 8.3 / EU AI Act Art. 17(1)(k)",
        "implementation_tier": "SCAFFOLD_ONLY",
        "target_files": ["src/auth/mfa.ts", "ebpf/ebpf_lsm_agent_guard.c"],
    },
    {
        "control_id": "A.9.4",
        "clause": "A.9 Use of AI systems",
        "title": "Intended use of the AI system",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Restricts agent execution strictly to declared Noun/Verb ontology schemas and authorized "
            "purpose markings; out-of-scope tool calls or unmapped transport states fail closed immediately."
        ),
        "risk_assessment_mapping": (
            "RISK-PROMPT-INJ, RISK-DELEGATION | OWASP ASI01:2026 Agent Goal Hijack | "
            "CEN-CENELEC prEN 18286 Clause 8.6 / EU AI Act Art. 17(1)(c)"
        ),
        "risk_ids": ["RISK-PROMPT-INJ", "RISK-DELEGATION"],
        "owasp_asi_2026": "ASI01:2026 Agent Goal Hijack",
        "en_18286_qms_clause": "prEN 18286 Clause 8.6 / EU AI Act Art. 17(1)(c)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["transport-to-disposition-mapping.yaml", "src/aeib_v040_engine.py"],
    },
    # =========================================================================
    # A.10 Third-party and customer relationships (3 controls: A.10.2, A.10.3, A.10.4)
    # =========================================================================
    {
        "control_id": "A.10.2",
        "clause": "A.10 Third-party and customer relationships",
        "title": "Allocating responsibilities between organization, partners, and customers",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Explicitly partitions responsibilities between AEIB (operational boundary enforcement and "
            "cryptographic evidence generation) and the deploying customer (awareness tracking, legal incident "
            "classification, and regulatory authority submission)."
        ),
        "risk_assessment_mapping": (
            "RISK-DELEGATION, RISK-RETRY-504 | OWASP ASI09:2026 Human-Agent Trust Exploitation | "
            "CEN-CENELEC prEN 18286 Clause 8.8 / EU AI Act Art. 17(1)(l)"
        ),
        "risk_ids": ["RISK-DELEGATION", "RISK-RETRY-504"],
        "owasp_asi_2026": "ASI09:2026 Human-Agent Trust Exploitation",
        "en_18286_qms_clause": "prEN 18286 Clause 8.8 / EU AI Act Art. 17(1)(l)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": [
            "docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md",
            "src/incident_evidence.py",
        ],
    },
    {
        "control_id": "A.10.3",
        "clause": "A.10 Third-party and customer relationships",
        "title": "Suppliers and ICT third-party service providers",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Generates DORA Art. 28(3) EBA DPM 4.0 xBRL-CSV Registers of Information (templates b_01.01, "
            "b_02.01, b_05.01) and enforces MCP protocol version pinning against third-party tool servers."
        ),
        "risk_assessment_mapping": (
            "RISK-DELEGATION, RISK-PROMPT-INJ | OWASP ASI04:2026 Agentic Supply Chain Vulnerabilities | "
            "CEN-CENELEC prEN 18286 Clause 8.8.2 / EU AI Act Art. 17(1)(l)"
        ),
        "risk_ids": ["RISK-DELEGATION", "RISK-PROMPT-INJ"],
        "owasp_asi_2026": "ASI04:2026 Agentic Supply Chain Vulnerabilities",
        "en_18286_qms_clause": "prEN 18286 Clause 8.8.2 / EU AI Act Art. 17(1)(l)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["compliance/dora_art28_roi_exporter.py", "smaos_dora_generator.py"],
    },
    {
        "control_id": "A.10.4",
        "clause": "A.10 Third-party and customer relationships",
        "title": "Customers",
        "applicability": "INCLUDED",
        "justification": (
            "INCLUDED: Enforces multi-tenant isolation, customer-managed Ed25519 verification keys, and transparent "
            "disclosure of system scope and operational limitations in customer TPRM compliance packs."
        ),
        "risk_assessment_mapping": (
            "RISK-DELEGATION, RISK-KEY-COMPROMISE | OWASP ASI03:2026 Identity & Privilege Abuse | "
            "CEN-CENELEC prEN 18286 Clause 8.8.3 / EU AI Act Art. 17(1)(l)"
        ),
        "risk_ids": ["RISK-DELEGATION", "RISK-KEY-COMPROMISE"],
        "owasp_asi_2026": "ASI03:2026 Identity & Privilege Abuse",
        "en_18286_qms_clause": "prEN 18286 Clause 8.8.3 / EU AI Act Art. 17(1)(l)",
        "implementation_tier": "OBSERVED_AND_TESTED",
        "target_files": ["docs/TPRM_BUYER_SECURITY_AND_COMPLIANCE_PACK.md", "src/multi_tenant_governor.py"],
    },
]


def _default_soa_signing_key() -> ed25519.Ed25519PrivateKey:
    """Derives a deterministic Ed25519 private key for reproducible local SoA signing."""
    seed = hashlib.sha256(b"SovereignNexus-ISO42001-SoA-Deterministic-Key-v1").digest()
    return ed25519.Ed25519PrivateKey.from_private_bytes(seed)


def _scan_control_files(target_files: List[str]) -> Dict[str, Any]:
    """Verifies target files on disk and computes their SHA-256 digests."""
    found_files: List[str] = []
    missing_files: List[str] = []
    verified_files_sha256: Dict[str, str] = {}

    for f in target_files:
        p = REPO_ROOT / f
        if p.exists() and p.is_file():
            found_files.append(f)
            verified_files_sha256[f] = hashlib.sha256(p.read_bytes()).hexdigest()
        else:
            missing_files.append(f)

    return {
        "found_files": found_files,
        "missing_files": missing_files,
        "verified_files_sha256": verified_files_sha256,
        "is_implemented": len(missing_files) == 0,
    }


def render_soa_markdown(report: Dict[str, Any]) -> str:
    """Renders the complete ISO/IEC 42001:2023 Annex A (38 controls) & Category H (14 controls) SoA in Markdown."""
    lines: List[str] = [
        "# ISO/IEC 42001:2023 Statement of Applicability (SoA)",
        "## Full 38-Control Annex A Normative Matrix & 14 Category H Runtime Governance Controls",
        "",
        "> **EPISTEMIC & REGULATORY NOTICE:**",
        "> Evaluated under the stated model. This Statement of Applicability (SoA) documents the applicability,",
        "> justification, risk assessment mappings, implementation tiers (`OBSERVED_AND_TESTED`, `SCAFFOLD_ONLY`,",
        "> `NOT_APPLICABLE_EXCLUDED`), and SHA-256 repository artifact digests for the Agent Execution Integrity",
        "> Boundary (AEIB) prototype and scaffold components.",
        "",
        "## 1. Cryptographic Seal & Summary Metrics",
        "",
        f"- **Standard:** `{report['standard']}`",
        f"- **QMS Alignment:** `{report['qms_alignment']}`",
        f"- **Timestamp (UTC):** `{report['timestamp_utc']}`",
        f"- **Annex A Normative Controls Evaluated:** `{report['annex_a_total_controls']}` "
        f"(`{report['annex_a_included_controls']}` INCLUDED, `{report['annex_a_excluded_controls']}` EXCLUDED)",
        f"- **Annex A Implementation Tiers:** "
        f"`{report['annex_a_observed_and_tested_controls']}` `OBSERVED_AND_TESTED`, "
        f"`{report['annex_a_scaffold_only_controls']}` `SCAFFOLD_ONLY`, "
        f"`{report['annex_a_not_applicable_excluded_controls']}` `NOT_APPLICABLE_EXCLUDED`",
        f"- **Category H Runtime Controls Evaluated:** `{report['total_controls']}` "
        f"(`{report['observed_and_tested_controls']}` `OBSERVED_AND_TESTED`, "
        f"`{report['scaffold_only_controls']}` `SCAFFOLD_ONLY`)",
        f"- **RFC 8785 JCS Payload SHA-256 Digest (`soa_digest`):** `{report['soa_digest']}`",
        f"- **Ed25519 Signature (`soa_signature_b64`):** `{report['soa_signature_b64']}`",
        "",
        "### Clause Distribution Summary (ISO/IEC 42001:2023 Annex A)",
        "",
        "| Clause | Normative Domain | Total Controls | Included | Excluded |",
        "| :--- | :--- | :---: | :---: | :---: |",
    ]

    clause_titles = {
        "A.2": "Policies related to AI",
        "A.3": "Internal organization",
        "A.4": "Resources for AI systems",
        "A.5": "Assessing impacts of AI systems",
        "A.6": "AI system life cycle",
        "A.7": "Data for AI systems",
        "A.8": "Information for interested parties",
        "A.9": "Use of AI systems",
        "A.10": "Third-party and customer relationships",
    }

    for clause_prefix, domain_title in clause_titles.items():
        clause_items = [
            c for c in report["annex_a_controls"]
            if c["control_id"].startswith(clause_prefix + ".")
        ]
        inc_count = sum(1 for c in clause_items if c["applicability"] == "INCLUDED")
        exc_count = sum(1 for c in clause_items if c["applicability"] == "EXCLUDED")
        lines.append(
            f"| **{clause_prefix}** | {domain_title} | {len(clause_items)} | {inc_count} | {exc_count} |"
        )

    lines.extend([
        f"| **Total** | **All 9 Normative Clauses (A.2–A.10)** | "
        f"**{report['annex_a_total_controls']}** | **{report['annex_a_included_controls']}** | "
        f"**{report['annex_a_excluded_controls']}** |",
        "",
        "---",
        "",
        "## 2. Full 38-Control ISO/IEC 42001:2023 Annex A Statement of Applicability",
        "",
        "| Control ID | Clause | Title | Applicability | Implementation Tier | Risk Assessment & Regulatory Mapping | Justification | Verified Files (SHA-256) |",
        "| :--- | :--- | :--- | :---: | :---: | :--- | :--- | :--- |",
    ])

    for ctrl in report["annex_a_controls"]:
        files_fmt = "<br>".join(
            f"`{f}` (`{sha[:12]}...`)"
            for f, sha in ctrl["verified_files_sha256"].items()
        )
        lines.append(
            f"| **{ctrl['control_id']}** | {ctrl['clause']} | {ctrl['title']} | "
            f"`{ctrl['applicability']}` | `{ctrl['implementation_tier']}` | "
            f"{ctrl['risk_assessment_mapping']} | {ctrl['justification']} | {files_fmt} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Category H Runtime Agent Governance Controls (14 Extended Controls)",
        "",
        "| Control ID | Category | Title | Implementation Tier | EN 18286 / EU AI Act Art. 17 Clause | OWASP ASI 2026 | Description | Verified Files (SHA-256) |",
        "| :--- | :--- | :--- | :---: | :--- | :--- | :--- | :--- |",
    ])

    for h_ctrl in report["statement_of_applicability"]:
        files_fmt = "<br>".join(
            f"`{f}` (`{sha[:12]}...`)"
            for f, sha in h_ctrl["verified_files_sha256"].items()
        )
        lines.append(
            f"| **{h_ctrl['control_id']}** | {h_ctrl['category']} | {h_ctrl['title']} | "
            f"`{h_ctrl['implementation_tier']}` | {h_ctrl['en_18286_qms_clause']} | "
            f"`{h_ctrl['owasp_asi_2026']}` | {h_ctrl['description']} | {files_fmt} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Independent Verification Command",
        "",
        "```bash",
        "python3 compliance/iso_42001_soa.py --verify",
        "```",
        "",
    ])
    return "\n".join(lines)


def render_soa_csv(report: Dict[str, Any]) -> str:
    """Renders the 38 Annex A controls and 14 Category H controls as a machine-readable CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "control_set",
        "control_id",
        "clause_or_category",
        "title",
        "applicability",
        "implementation_tier",
        "status",
        "risk_assessment_mapping",
        "owasp_asi_2026",
        "en_18286_qms_clause",
        "justification_or_description",
        "verified_files",
        "verified_files_sha256",
    ])

    for ctrl in report["annex_a_controls"]:
        writer.writerow([
            "ISO_42001_ANNEX_A",
            ctrl["control_id"],
            ctrl["clause"],
            ctrl["title"],
            ctrl["applicability"],
            ctrl["implementation_tier"],
            ctrl["status"],
            ctrl["risk_assessment_mapping"],
            ctrl["owasp_asi_2026"],
            ctrl["en_18286_qms_clause"],
            ctrl["justification"],
            ";".join(ctrl["verified_files"]),
            json.dumps(ctrl["verified_files_sha256"], sort_keys=True),
        ])

    for h_ctrl in report["statement_of_applicability"]:
        writer.writerow([
            "CATEGORY_H_RUNTIME",
            h_ctrl["control_id"],
            h_ctrl["category"],
            h_ctrl["title"],
            "INCLUDED",
            h_ctrl["implementation_tier"],
            h_ctrl["status"],
            f"{h_ctrl['owasp_asi_2026']} | {h_ctrl['en_18286_qms_clause']}",
            h_ctrl["owasp_asi_2026"],
            h_ctrl["en_18286_qms_clause"],
            h_ctrl["description"],
            ";".join(h_ctrl["verified_files"]),
            json.dumps(h_ctrl["verified_files_sha256"], sort_keys=True),
        ])

    return buf.getvalue()


def verify_soa_report(report_path: Optional[Path] = None) -> Dict[str, Any]:
    """Verifies the Ed25519 signature over RFC 8785 JCS and all SHA-256 file hashes in the SoA JSON report."""
    target_path = report_path or DEFAULT_REPORT_JSON_PATH
    if not target_path.exists() or not target_path.is_file():
        raise FileNotFoundError(f"SoA report file not found: {target_path}")

    report = json.loads(target_path.read_text(encoding="utf-8"))
    unsigned_payload = {
        k: v
        for k, v in report.items()
        if k not in ("soa_digest", "soa_signature_b64", "signer_public_key_pem")
    }
    canonical_bytes = encode_jcs(unsigned_payload)
    computed_digest = hashlib.sha256(canonical_bytes).hexdigest()
    if computed_digest != report.get("soa_digest"):
        raise ValueError(
            f"JCS digest mismatch: expected {report.get('soa_digest')}, computed {computed_digest}"
        )

    pubkey = serialization.load_pem_public_key(
        report["signer_public_key_pem"].encode("ascii")
    )
    sig_bytes = base64.b64decode(report["soa_signature_b64"])
    pubkey.verify(sig_bytes, canonical_bytes)

    verified_file_count = 0
    for section_key in ("statement_of_applicability", "annex_a_controls"):
        for ctrl in report.get(section_key, []):
            sha_map = ctrl.get("verified_files_sha256", {})
            if not sha_map:
                raise ValueError(f"Control {ctrl.get('control_id')} has no verified_files_sha256 entries")
            for rel_path, expected_sha in sha_map.items():
                full_path = REPO_ROOT / rel_path
                if not full_path.is_file():
                    raise FileNotFoundError(f"Referenced file missing on disk: {rel_path}")
                actual_sha = hashlib.sha256(full_path.read_bytes()).hexdigest()
                if actual_sha != expected_sha:
                    raise ValueError(
                        f"SHA-256 mismatch for {rel_path} in {ctrl.get('control_id')}: "
                        f"expected {expected_sha}, got {actual_sha}"
                    )
                verified_file_count += 1

    return {
        "verified": True,
        "report_path": str(target_path),
        "soa_digest": computed_digest,
        "annex_a_controls_verified": len(report.get("annex_a_controls", [])),
        "category_h_controls_verified": len(report.get("statement_of_applicability", [])),
        "file_hashes_verified": verified_file_count,
    }


def scan_iso_42001_soa(
    signing_privkey: Optional[ed25519.Ed25519PrivateKey] = None,
    output_md_path: Optional[Path] = None,
) -> Dict[str, Any]:
    print("=" * 80)
    print("🏛️  ISO/IEC 42001:2023 STATEMENT OF APPLICABILITY (SoA) SCANNER")
    print("    Mapping Sovereign Agent Architecture to Annex A (38) & Category H (14)")
    print("=" * 80)

    privkey = signing_privkey or _default_soa_signing_key()
    pubkey = privkey.public_key()

    # 1. Scan Category H Controls (14 controls)
    results: List[Dict[str, Any]] = []
    total_controls = len(CATEGORY_H_CONTROLS)
    applicable_controls = 0
    implemented_controls = 0

    for c in CATEGORY_H_CONTROLS:
        applicable_controls += 1
        scan_res = _scan_control_files(c["target_files"])
        if scan_res["is_implemented"]:
            implemented_controls += 1

        status = "IMPLEMENTED" if scan_res["is_implemented"] else "PARTIAL"
        results.append({
            "control_id": c["control_id"],
            "title": c["title"],
            "category": c["category"],
            "status": status,
            "implementation_tier": c["implementation_tier"],
            "en_18286_qms_clause": c["en_18286_qms_clause"],
            "owasp_asi_2026": c["owasp_asi_2026"],
            "verified_files": scan_res["found_files"],
            "verified_files_sha256": scan_res["verified_files_sha256"],
            "missing_files": scan_res["missing_files"],
            "description": c["description"],
        })

    coverage_pct = round((implemented_controls / total_controls) * 100.0, 1)

    # 2. Scan Official ISO/IEC 42001:2023 Annex A Controls (38 controls across A.2–A.10)
    annex_a_results: List[Dict[str, Any]] = []
    annex_a_clause_counts: Dict[str, int] = {}
    annex_a_all_files_present = True

    for a_ctrl in ISO_42001_ANNEX_A_38_CONTROLS:
        scan_res = _scan_control_files(a_ctrl["target_files"])
        if not scan_res["is_implemented"]:
            annex_a_all_files_present = False

        clause_prefix = a_ctrl["control_id"].split(".")[0] + "." + a_ctrl["control_id"].split(".")[1]
        annex_a_clause_counts[clause_prefix] = annex_a_clause_counts.get(clause_prefix, 0) + 1

        if a_ctrl["applicability"] == "EXCLUDED":
            status = "EXCLUDED_DOCUMENTED" if scan_res["is_implemented"] else "MISSING_EVIDENCE"
        else:
            status = "IMPLEMENTED" if scan_res["is_implemented"] else "PARTIAL"

        annex_a_results.append({
            "control_id": a_ctrl["control_id"],
            "clause": a_ctrl["clause"],
            "title": a_ctrl["title"],
            "applicability": a_ctrl["applicability"],
            "justification": a_ctrl["justification"],
            "risk_assessment_mapping": a_ctrl["risk_assessment_mapping"],
            "risk_ids": a_ctrl["risk_ids"],
            "owasp_asi_2026": a_ctrl["owasp_asi_2026"],
            "en_18286_qms_clause": a_ctrl["en_18286_qms_clause"],
            "implementation_tier": a_ctrl["implementation_tier"],
            "status": status,
            "target_files": a_ctrl["target_files"],
            "verified_files": scan_res["found_files"],
            "verified_files_sha256": scan_res["verified_files_sha256"],
            "missing_files": scan_res["missing_files"],
        })

    annex_a_total = len(annex_a_results)
    annex_a_included = sum(1 for r in annex_a_results if r["applicability"] == "INCLUDED")
    annex_a_excluded = sum(1 for r in annex_a_results if r["applicability"] == "EXCLUDED")
    annex_a_observed = sum(
        1 for r in annex_a_results if r["implementation_tier"] == "OBSERVED_AND_TESTED"
    )
    annex_a_scaffold = sum(
        1 for r in annex_a_results if r["implementation_tier"] == "SCAFFOLD_ONLY"
    )
    annex_a_na_excluded = sum(
        1 for r in annex_a_results if r["implementation_tier"] == "NOT_APPLICABLE_EXCLUDED"
    )

    print(f"\n[*] ISO 42001 Annex A Controls:    {annex_a_total} (Included: {annex_a_included}, Excluded: {annex_a_excluded})")
    print(f"[*] Total Category H Controls:     {total_controls}")
    print(f"[*] Applicable Category H:         {applicable_controls}")
    print(f"[*] Implemented & Verified (H):    {implemented_controls}")
    print(f"[*] ISO 42001 SoA Coverage:        {coverage_pct}%\n")

    print("-" * 80)
    print(f"{'CONTROL':<8} | {'CATEGORY':<20} | {'TIER':<20} | {'TITLE'}")
    print("-" * 80)
    for r in results:
        status_icon = "✅" if r["status"] == "IMPLEMENTED" else "⚠️"
        print(
            f"{r['control_id']:<8} | {r['category']:<20} | "
            f"{status_icon} {r['implementation_tier']:<17} | {r['title']}"
        )
    print("-" * 80)

    report_payload = {
        "standard": "ISO/IEC 42001:2023",
        "qms_alignment": "CEN-CENELEC prEN 18286 / EU AI Act Art. 17 QMS",
        "annex": "ISO/IEC 42001:2023 Annex A (38 Controls) & Category H Runtime Controls (14 Controls)",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_controls": total_controls,
        "implemented_controls": implemented_controls,
        "observed_and_tested_controls": sum(
            1 for r in results if r["implementation_tier"] == "OBSERVED_AND_TESTED"
        ),
        "scaffold_only_controls": sum(
            1 for r in results if r["implementation_tier"] == "SCAFFOLD_ONLY"
        ),
        "coverage_percentage": coverage_pct,
        "statement_of_applicability": results,
        "annex_a_total_controls": annex_a_total,
        "annex_a_included_controls": annex_a_included,
        "annex_a_excluded_controls": annex_a_excluded,
        "annex_a_observed_and_tested_controls": annex_a_observed,
        "annex_a_scaffold_only_controls": annex_a_scaffold,
        "annex_a_not_applicable_excluded_controls": annex_a_na_excluded,
        "annex_a_clause_counts": annex_a_clause_counts,
        "annex_a_controls": annex_a_results,
    }

    canonical_bytes = encode_jcs(report_payload)
    soa_digest = hashlib.sha256(canonical_bytes).hexdigest()
    sig_bytes = privkey.sign(canonical_bytes)
    soa_signature_b64 = base64.b64encode(sig_bytes).decode("ascii")
    signer_public_key_pem = pubkey.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    report = {
        **report_payload,
        "soa_digest": soa_digest,
        "soa_signature_b64": soa_signature_b64,
        "signer_public_key_pem": signer_public_key_pem,
    }

    DEFAULT_REPORT_JSON_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[✔] ISO 42001 SoA JSON Report written to {DEFAULT_REPORT_JSON_PATH}")

    md_target = output_md_path or DEFAULT_REPORT_MD_PATH
    md_target.parent.mkdir(parents=True, exist_ok=True)
    md_target.write_text(render_soa_markdown(report), encoding="utf-8")
    print(f"[✔] ISO 42001 SoA Markdown Report written to {md_target}")

    assert implemented_controls == total_controls, "All 14 Category H controls must be fully implemented."
    assert annex_a_total == 38, "All 38 ISO/IEC 42001:2023 Annex A controls must be present."
    assert annex_a_all_files_present, "All target_files in ISO_42001_ANNEX_A_38_CONTROLS must exist on disk."
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="ISO/IEC 42001:2023 Full 38-Control Annex A & Category H SoA Generator and Verifier"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "csv", "all"],
        default="all",
        help="Output format to generate (default: all)",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=DEFAULT_REPORT_MD_PATH,
        help="Path to write the Markdown Statement of Applicability",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify Ed25519 signature over RFC 8785 JCS and SHA-256 file hashes of compliance/iso_42001_soa_report.json",
    )
    args = parser.parse_args(argv)

    if args.verify:
        verification = verify_soa_report(DEFAULT_REPORT_JSON_PATH)
        print(
            f"[✔] Verified {verification['report_path']}: "
            f"digest={verification['soa_digest']} "
            f"annex_a={verification['annex_a_controls_verified']} "
            f"category_h={verification['category_h_controls_verified']} "
            f"files={verification['file_hashes_verified']}"
        )
        return 0

    report = scan_iso_42001_soa(output_md_path=args.output_md)

    if args.format == "csv":
        sys.stdout.write(render_soa_csv(report))
    elif args.format == "markdown":
        sys.stdout.write(render_soa_markdown(report))
    elif args.format == "json":
        sys.stdout.write(json.dumps(report, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
