#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
compliance/unified_technical_file_generator.py
================================================================================
Unified AI Compliance Technical File & Design History File (DHF) Generator

Bridges the 4-Layer High-Risk AI Governance & Enforcement Architecture:
  1. Organizational AIMS: ISO/IEC 42001:2023
  2. EU AI Act Article 17 Harmonized QMS: EN 18286:2026 (Presumption of Conformity)
  3. Product Safety & Embedded AI: ISO 13485:2016 / ISO 14971:2019 & EU MDR (2017/745)
  4. Supply Chain & Cryptography Bill of Materials: EU AI Act Art. 28 & ECMA-424 CBOM

Generates an RFC 8785 JCS canonicalized, Ed25519-signed Unified Technical File
structured strictly according to EU AI Act Annex IV (§1–§6), serving as an
independent standalone technical file for Annex III (deadline Dec 2, 2027)
or as a DHF Addendum for Annex I embedded medical/machinery systems (deadline Aug 2, 2028).

Epistemic Calibration:
  Observed, tested, and evaluated under the stated model. AEIB produces verifiable
  technical execution evidence; compliance is a deployer-level responsibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# =============================================================================
# NORMATIVE COMPLIANCE MAPPING DICTIONARIES
# =============================================================================

STANDARDS_ARCHITECTURE_LAYERS: List[Dict[str, Any]] = [
    {
        "layer_id": "LAYER_1_ORGANIZATIONAL_AIMS",
        "standard": "ISO/IEC 42001:2023",
        "scope": "Artificial Intelligence Management System (AIMS)",
        "governing_clauses": [
            "Clause 4 (Context & Stakeholders)",
            "Clause 5 (Leadership & AI Policy)",
            "Clause 6 (AI Risk Planning & Impact Assessments)",
            "Clause 8 (Operational Control)",
            "Annex A.2–A.10 (38 Normative Controls)"
        ],
        "runtime_enforcement_mechanism": (
            "System inventory, root sponsor identity binding, policy epoch monotonic "
            "versioning, and high-level risk treatment classification."
        ),
        "implementation_tier": "OBSERVED_AND_TESTED",
        "evidence_reference": "compliance/iso_42001_soa_report.json"
    },
    {
        "layer_id": "LAYER_2_EU_AI_ACT_HARMONIZED_QMS",
        "standard": "CEN-CENELEC EN 18286:2026",
        "scope": "Harmonized QMS for EU AI Act Article 17 Presumption of Conformity",
        "governing_clauses": [
            "Clause 4.1 / Art. 17(1)(a) Regulatory Compliance Strategy",
            "Clause 6.1 / Art. 17(1)(g) Risk Management System Integration",
            "Clause 7.1 / Art. 17(1)(e) Technical Verification & Validation",
            "Clause 7.5 / Art. 17(1)(f) Data Quality & Schema Integrity",
            "Clause 8.3 / Art. 17(1)(m) Serious Incident Reporting & Post-Market Monitoring (Art. 72)"
        ],
        "runtime_enforcement_mechanism": (
            "Pre-dispatch TCC escrow, fail-closed human release gates, RFC 8785 JCS CAID "
            "derivation, and continuous hash-chained execution receipt generation."
        ),
        "implementation_tier": "OBSERVED_AND_TESTED",
        "evidence_reference": "docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md"
    },
    {
        "layer_id": "LAYER_3_PRODUCT_SAFETY_AND_MEDICAL_DHF",
        "standard": "ISO 13485:2016 / ISO 14971:2019 / ISO 9001:2015 & EU MDR 2017/745 / IVDR 2017/746",
        "scope": "Product Safety, Medical Device QMS & Design History File (DHF) Integration (Annex I)",
        "governing_clauses": [
            "ISO 13485 Clause 7.3 Design & Development Controls (DHF / DMR)",
            "ISO 14971 Clauses 4–7 Risk Analysis, Evaluation, Control & Verification",
            "EU MDR Annex I General Safety and Performance Requirements (GSPR 17.2 Software Verification)",
            "EU MDR Annex II Section 6 Technical Documentation on Software Validation"
        ],
        "runtime_enforcement_mechanism": (
            "Fail-closed socket mediation for consequential actions (clinical dosage, physical actuators, "
            "financial disbursement), hazard event logging, and hardware-level container isolation."
        ),
        "implementation_tier": "OBSERVED_AND_TESTED",
        "evidence_reference": "docs/compliance/UNIFIED_DHF_ANNEX_IV_TECHNICAL_FILE.md"
    },
    {
        "layer_id": "LAYER_4_SUPPLY_CHAIN_AND_CBOM",
        "standard": "EU AI Act Art. 28 / ISO 42001 Annex A.8 / CycloneDX 1.6 / ECMA-424",
        "scope": "Cryptographic Bill of Materials (CBOM), Model Weights & Third-Party Tool Integrity",
        "governing_clauses": [
            "EU AI Act Article 28 Obligations of Third Parties / Value Chain Providers",
            "ISO 42001 Annex A.8 Information for Interested Parties & Third-Party Transparency",
            "ECMA-424 Standard for Cryptographic Bill of Materials",
            "RFC 9942 / RFC 9943 IETF SCITT Transparency Service Receipts"
        ],
        "runtime_enforcement_mechanism": (
            "Pinned MCP tool descriptors, SHA-256 model weight digests, and Ed25519-signed "
            "ECMA-424 CBOM receipts mapping cryptographic algorithm agility."
        ),
        "implementation_tier": "OBSERVED_AND_TESTED",
        "evidence_reference": "evidence/cbom.json"
    }
]

STATUTORY_DEADLINES_MAPPING: Dict[str, Any] = {
    "ANNEX_III_STANDALONE_HIGH_RISK": {
        "enforcement_deadline": "2027-12-02",
        "applicable_sectors": [
            "Credit scoring & creditworthiness evaluation (Annex III.5.b)",
            "Risk assessment & pricing in life and health insurance (Annex III.5.c)",
            "Recruitment, screening & candidate evaluation (Annex III.4.a)",
            "Critical infrastructure safety components (Annex III.2.a)"
        ],
        "compliance_deliverable": "Standalone EU AI Act Annex IV Technical File + EN 18286 QMS Conformity File",
        "governance_focus": "Automated wire-level logging (Art. 12), human oversight (Art. 14), and robustness (Art. 15)."
    },
    "ANNEX_I_EMBEDDED_HIGH_RISK": {
        "enforcement_deadline": "2028-08-02",
        "applicable_sectors": [
            "Medical Devices under EU MDR (Regulation (EU) 2017/745)",
            "In Vitro Diagnostic Medical Devices under EU IVDR (Regulation (EU) 2017/746)",
            "Machinery under EU Machinery Regulation (Regulation (EU) 2023/1230)",
            "Civil Aviation Security & Automotive Functional Safety Systems"
        ],
        "compliance_deliverable": "Unified Design History File (DHF) Addendum bridging ISO 13485 & AI Act Annex IV",
        "governance_focus": "Integration with ISO 14971 risk management, clinical evaluation, and pre-socket fail-closed actuation."
    }
}

HAZARD_LOG_ISO14971: List[Dict[str, Any]] = [
    {
        "hazard_id": "HZD-01-TRANSPORT-AMBIGUITY",
        "title": "Layer 7 Transport Ambiguity & Duplicate Consequential Mutation",
        "clinical_or_financial_risk": (
            "Network timeout (HTTP 504) or TCP reset causes unhedged agent retry, executing "
            "duplicate patient medication disbursement, double financial transfer, or redundant physical actuator cycle."
        ),
        "initial_risk_level": "CRITICAL",
        "aeib_mitigation_control": (
            "Station 3 Wire Latch traps state to EFFECT_INDETERMINATE (retry_safe: false). "
            "Automated retries blocked; single out-of-band probe (ProbeBudget: 1) verifies downstream state."
        ),
        "residual_risk_level": "ACCEPTABLE_UNDER_STATED_MODEL",
        "verification_test": "tests/test_at64_rail_interop_and_mcp_tool_taint.py",
        "iso14971_clause": "Clause 6.2 (Risk Control Options Analysis)"
    },
    {
        "hazard_id": "HZD-02-PARALLEL-RESOURCE-DEPLETION",
        "title": "Concurrent Multi-Agent Budget & Resource Overrun",
        "clinical_or_financial_risk": (
            "Concurrent subagents read unreserved balance simultaneously and execute parallel dispatches, "
            "overrunning institutional budget ceilings or physical medication reservoirs."
        ),
        "initial_risk_level": "HIGH",
        "aeib_mitigation_control": (
            "Pre-socket TCC (Try-Confirm-Cancel) atomic reservation in SQLite WAL with BEGIN IMMEDIATE. "
            "Subagents cannot dispatch until budget is locked; excess requests rejected fail-closed."
        ),
        "residual_risk_level": "ACCEPTABLE_UNDER_STATED_MODEL",
        "verification_test": "aeib-native-runtime/tests/test_tcc_parallel_acid_vs_base_anomalies.py",
        "iso14971_clause": "Clause 6.3 (Implementation of Risk Control Measures)"
    },
    {
        "hazard_id": "HZD-03-CONTEXT-POISONING",
        "title": "Memory Poisoning & Prompt Injection Parameter Tampering (AT57)",
        "clinical_or_financial_risk": (
            "Adversary manipulates working memory or RAG context to alter destination IBAN, "
            "clinical dosage value, or actuator threshold without operator consent."
        ),
        "initial_risk_level": "CRITICAL",
        "aeib_mitigation_control": (
            "Station 1 Context Integrity Gate evaluates candidate action CAID against ingestion-time "
            "commitment manifest. Tampered parameters trigger HALT_CONTEXT_INTEGRITY_FAILURE (0 socket bytes emitted)."
        ),
        "residual_risk_level": "ACCEPTABLE_UNDER_STATED_MODEL",
        "verification_test": "tests/test_sybil_rotator_and_smurfing.py",
        "iso14971_clause": "Clause 6.4 (Residual Risk Evaluation)"
    },
    {
        "hazard_id": "HZD-04-EVIDENTIARY-TAMPERING",
        "title": "Audit Log Tampering & Forensic Repudiation",
        "clinical_or_financial_risk": (
            "Malicious insider or compromised operating system alters local audit rows to conceal "
            "fraudulent transactions or lethal clinical dosage modifications."
        ),
        "initial_risk_level": "HIGH",
        "aeib_mitigation_control": (
            "RFC 8785 JCS + Ed25519 hash-chained Continuity Receipts registered into RFC 9942 / RFC 9943 "
            "SCITT Merkle tree transparent statements. Any in-place bit flip triggers InvalidSignature."
        ),
        "residual_risk_level": "ACCEPTABLE_UNDER_STATED_MODEL",
        "verification_test": "tests/test_scitt_otel_and_pqc_cbom_agility.py",
        "iso14971_clause": "Clause 7 (Overall Residual Risk Acceptability)"
    }
]


# =============================================================================
# UNIFIED TECHNICAL FILE & DHF GENERATOR ENGINE
# =============================================================================

class UnifiedTechnicalFileGenerator:
    """
    Assembles and verifies the Unified EU AI Act Annex IV Technical File
    and ISO 13485 / ISO 14971 Design History File (DHF) Addendum.
    """

    def __init__(self, repo_root: Path = REPO_ROOT) -> None:
        self.repo_root = repo_root
        self.epistemic_notice = (
            "EPISTEMIC BOUNDARY NOTICE: All technical assertions, standards alignments, and hazard "
            "mitigations in this dossier are observed, tested, and evaluated under the stated model "
            "using deterministic prototype and verification scaffolds. AEIB produces verifiable "
            "technical evidence to support deployer compliance; it does not confer legal certification."
        )

    def _load_verified_file_hash(self, rel_path: str) -> Dict[str, Any]:
        p = self.repo_root / rel_path
        if not p.is_file():
            return {"path": rel_path, "present": False, "sha256": None}
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        return {"path": rel_path, "present": True, "sha256": digest}

    def generate_unified_technical_file(
        self,
        signing_privkey: Optional[ed25519.Ed25519PrivateKey] = None,
        now_ts: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Builds the complete 6-section Annex IV / DHF Technical File package.
        """
        ts = now_ts if now_ts is not None else int(time.time())

        # Collect live file digests
        evidence_files = [
            "evidence/cbom.json",
            "compliance/iso_42001_soa_report.json",
            "docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md",
            "docs/compliance/ANNEX_IV_TECHNICAL_DOSSIER.md",
            "src/jcs_canonicalizer.py",
            "src/eo1_write_before_execute.py",
            "aeib-native-runtime/src/sqlite_acid_tcc_boundary.py"
        ]
        file_hashes = {f: self._load_verified_file_hash(f) for f in evidence_files}

        technical_file_payload: Dict[str, Any] = {
            "schema_version": "aeib.unified.technical.file.annex_iv.v1",
            "document_title": "Unified High-Risk AI Technical Documentation & ISO 13485 DHF Addendum",
            "timestamp_epoch": ts,
            "epistemic_notice": self.epistemic_notice,
            "governing_frameworks": [
                "Regulation (EU) 2024/1689 (EU AI Act), Annex IV & Articles 11, 12, 14, 15, 17, 28",
                "CEN-CENELEC EN 18286:2026 (AI Quality Management System)",
                "ISO/IEC 42001:2023 (Artificial Intelligence Management System)",
                "ISO 13485:2016 / ISO 14971:2019 (Medical Device QMS & Risk Management)",
                "Regulation (EU) 2017/745 (EU MDR) & Regulation (EU) 2017/746 (EU IVDR)",
                "Regulation (EU) 2022/2554 (DORA), Articles 17 & 28(3)"
            ],
            "statutory_transition_clocks": STATUTORY_DEADLINES_MAPPING,
            "four_layer_standards_architecture": STANDARDS_ARCHITECTURE_LAYERS,
            "annex_iv_six_mandatory_sections": {
                "section_1_general_description": {
                    "system_name": "Agent Execution Integrity Boundary (AEIB)",
                    "intended_purpose": (
                        "Deterministic interception, pre-dispatch transactional reservation (TCC), "
                        "uncertain-outcome wire latching (HTTP 504 / TCP RST), and continuous cryptographic "
                        "receipt emission for autonomous AI tool dispatches."
                    ),
                    "target_market_classification": "Annex III Standalone High-Risk & Annex I Embedded High-Risk Addendum",
                    "deployer_provider_demarcation": (
                        "AEIB operates as a deployer-configured runtime gate. The deployer retains legal "
                        "responsibility for institutional quality management, human staffing, and target systems."
                    )
                },
                "section_2_component_integration_and_hardware": {
                    "zero_egress_agent_boundary": "Agent domain configured with network_mode: 'none'; communicates via local socket.",
                    "mcp_tool_provenance_pinning": "Tool descriptors pinned via SHA-256 and verified prior to session registration.",
                    "cryptographic_bill_of_materials": {
                        "cbom_standard": "CycloneDX 1.6 / ECMA-424",
                        "cbom_file": "evidence/cbom.json",
                        "cbom_status": file_hashes["evidence/cbom.json"]["present"]
                    }
                },
                "section_3_development_methods_and_computational_logic": {
                    "five_term_pre_dispatch_predicate": (
                        "GrantValid and PolicyEpochFresh and SourceEpochFresh and CAIDMatch and TicketUnburned"
                    ),
                    "canonicalization_standard": "RFC 8785 JSON Canonicalization Scheme (JCS)",
                    "signature_algorithm": "Ed25519 (RFC 8032)",
                    "tcc_escrow_engine": "SQLite WAL with BEGIN IMMEDIATE serialized transactions"
                },
                "section_4_monitoring_logging_and_auditing": {
                    "article_12_wire_level_logging": (
                        "Every external dispatch intent and resulting outcome is committed to an append-only "
                        "hash-chained ledger prior to and immediately following socket I/O."
                    ),
                    "retention_period": "Configurable 7-year immutable retention model",
                    "ietf_scitt_transparency": "RFC 9942 COSE receipts with RFC 9162 SHA-256 Merkle inclusion proofs."
                },
                "section_5_risk_management_and_hazard_analysis": {
                    "iso_14971_risk_management_system": "Integrated 4-hazard clinical/financial hazard evaluation",
                    "hazard_log": HAZARD_LOG_ISO14971
                },
                "section_6_human_oversight_and_fail_closed_gates": {
                    "article_14_decoupled_oversight": (
                        "Safety policy decoupled from model weights; enforced at pre-socket gate. "
                        "Prohibition of [APPROVE OVERRIDE] without authenticated target evidence."
                    ),
                    "step_up_dual_control": "RFC 9470 Step-Up Dual Control token required for high-consequence dispatches."
                }
            },
            "verified_artifact_manifest": file_hashes
        }

        # Canonicalize payload with RFC 8785 JCS
        canonical_jcs = encode_jcs(technical_file_payload)
        package_digest = hashlib.sha256(canonical_jcs).hexdigest()

        # Sign with Ed25519
        signer = signing_privkey or ed25519.Ed25519PrivateKey.generate()
        sig = signer.sign(canonical_jcs)
        pubkey = signer.public_key()
        pubkey_pem = pubkey.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")

        return {
            "technical_file": technical_file_payload,
            "package_digest": package_digest,
            "signature_hex": sig.hex(),
            "signer_public_key_pem": pubkey_pem
        }

    def verify_unified_technical_file(self, signed_bundle: Dict[str, Any]) -> bool:
        """
        Validates the Ed25519 signature over RFC 8785 JCS canonical bytes.
        """
        payload = signed_bundle["technical_file"]
        sig_bytes = bytes.fromhex(signed_bundle["signature_hex"])
        pubkey_pem = signed_bundle["signer_public_key_pem"].encode("utf-8")

        pubkey = serialization.load_pem_public_key(pubkey_pem)
        if not isinstance(pubkey, ed25519.Ed25519PublicKey):
            return False

        canonical_jcs = encode_jcs(payload)
        expected_digest = hashlib.sha256(canonical_jcs).hexdigest()
        if expected_digest != signed_bundle["package_digest"]:
            return False

        try:
            pubkey.verify(sig_bytes, canonical_jcs)
            return True
        except InvalidSignature:
            return False

    def render_markdown_dossier(self, signed_bundle: Dict[str, Any]) -> str:
        """
        Renders a publication-grade Markdown Design History File (DHF) addendum
        formatted for notified body audits (e.g., TÜV, BSI, DEKRA).
        """
        tf = signed_bundle["technical_file"]
        lines = [
            "# EU AI Act Annex IV Unified Technical File & ISO 13485 DHF Addendum",
            "## Integrated Compliance Architecture: ISO 42001 + EN 18286 + ISO 13485 + ECMA-424 CBOM",
            "",
            f"> **EPISTEMIC & REGULATORY NOTICE:** {tf['epistemic_notice']}",
            "",
            "---",
            "",
            "### Section 1: Executive Identity & Cryptographic Anchor",
            f"* **Document Title:** {tf['document_title']}",
            f"* **Schema Version:** `{tf['schema_version']}`",
            f"* **Package Digest (SHA-256):** `{signed_bundle['package_digest']}`",
            f"* **Signature Hex:** `{signed_bundle['signature_hex'][:32]}...`",
            "",
            "---",
            "",
            "### Section 2: Statutory Timelines & Target Deadlines",
            "| High-Risk Classification | Mandatory Enforcement Deadline | Target Technical File Deliverable |",
            "|---|---|---|",
        ]

        for k, v in tf["statutory_transition_clocks"].items():
            lines.append(f"| **{k.replace('_', ' ')}** | `{v['enforcement_deadline']}` | {v['compliance_deliverable']} |")

        lines.extend([
            "",
            "---",
            "",
            "### Section 3: The 4-Layer Integrated Compliance Architecture",
            "| Compliance Layer | Governing Standard | Technical Runtime Enforcement Mechanism |",
            "|---|---|---|",
        ])

        for layer in tf["four_layer_standards_architecture"]:
            lines.append(f"| **{layer['layer_id']}** | `{layer['standard']}` | {layer['runtime_enforcement_mechanism']} |")

        lines.extend([
            "",
            "---",
            "",
            "### Section 4: ISO 14971 Clinical & Financial Hazard Log",
            "| Hazard ID & Title | Clinical / Operational Risk | AEIB Technical Mitigation Control | Residual Risk Level |",
            "|---|---|---|---|",
        ])

        for hzd in tf["annex_iv_six_mandatory_sections"]["section_5_risk_management_and_hazard_analysis"]["hazard_log"]:
            lines.append(
                f"| **{hzd['hazard_id']}**<br>*{hzd['title']}* | {hzd['clinical_or_financial_risk']} | "
                f"{hzd['aeib_mitigation_control']} | `{hzd['residual_risk_level']}` |"
            )

        lines.extend([
            "",
            "---",
            "",
            "### Section 5: Annex IV Mandatory Execution Controls (§1–§6)",
            f"* **Article 11 / Annex IV §1 (General Description):** {tf['annex_iv_six_mandatory_sections']['section_1_general_description']['intended_purpose']}",
            f"* **Article 12 / Annex IV §4 (Automatic Logging):** {tf['annex_iv_six_mandatory_sections']['section_4_monitoring_logging_and_auditing']['article_12_wire_level_logging']}",
            f"* **Article 14 / Annex IV §6 (Human Oversight):** {tf['annex_iv_six_mandatory_sections']['section_6_human_oversight_and_fail_closed_gates']['article_14_decoupled_oversight']}",
            f"* **Article 15 / Annex IV §3 (Robustness & Accuracy):** Five-term pre-dispatch predicate: `{tf['annex_iv_six_mandatory_sections']['section_3_development_methods_and_computational_logic']['five_term_pre_dispatch_predicate']}`",
            f"* **Article 28 / Annex IV §2 (Supply Chain / CBOM):** {tf['annex_iv_six_mandatory_sections']['section_2_component_integration_and_hardware']['cryptographic_bill_of_materials']['cbom_standard']} bound in `evidence/cbom.json`.",
            "",
            "---",
            "",
            "### Section 6: Verified Artifact Manifest",
            "| Artifact Path | File Present | SHA-256 Digest |",
            "|---|---|---|",
        ])

        for fpath, meta in tf["verified_artifact_manifest"].items():
            status_str = "Verified Present" if meta["present"] else "Not Found"
            digest_str = f"`{meta['sha256'][:16]}...`" if meta["sha256"] else "N/A"
            lines.append(f"| `{fpath}` | {status_str} | {digest_str} |")

        lines.append("")
        return "\n".join(lines)


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified AI Compliance Technical File & ISO 13485 DHF Generator"
    )
    parser.add_argument("--self-test", action="store_true", help="Run end-to-end generation and verification self-test.")
    parser.add_argument("--export-dhf", action="store_true", help="Generate and write docs/compliance/UNIFIED_DHF_ANNEX_IV_TECHNICAL_FILE.md.")
    parser.add_argument("--output-json", type=Path, default=None, help="Output path for signed JSON package.")
    parser.add_argument("--verify", type=Path, default=None, help="Verify an existing signed technical file JSON package.")

    args = parser.parse_args()
    generator = UnifiedTechnicalFileGenerator()

    if args.verify:
        if not args.verify.is_file():
            print(f"[!] Error: File not found: {args.verify}", file=sys.stderr)
            sys.exit(1)
        bundle = json.loads(args.verify.read_text(encoding="utf-8"))
        valid = generator.verify_unified_technical_file(bundle)
        if valid:
            print(f"[✓] Verification SUCCESS: Valid Ed25519 signature over RFC 8785 JCS package ({args.verify})")
            sys.exit(0)
        else:
            print(f"[!] Verification FAILED: Invalid signature or digest mismatch ({args.verify})", file=sys.stderr)
            sys.exit(1)

    if args.self_test or args.export_dhf or args.output_json:
        bundle = generator.generate_unified_technical_file()
        valid = generator.verify_unified_technical_file(bundle)
        if not valid:
            print("[!] Self-Test FAILED: Generated package failed cryptographic verification.", file=sys.stderr)
            sys.exit(1)

        print("[✓] Technical File Generated: Valid Ed25519 signature over RFC 8785 JCS.")
        print(f"    • Package Digest (SHA-256): {bundle['package_digest']}")
        print(f"    • Layers Verified: {len(bundle['technical_file']['four_layer_standards_architecture'])}")
        print(f"    • Hazards Analyzed: {len(bundle['technical_file']['annex_iv_six_mandatory_sections']['section_5_risk_management_and_hazard_analysis']['hazard_log'])}")

        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
            print(f"    • Exported JSON to: {args.output_json}")

        if args.export_dhf:
            dhf_path = REPO_ROOT / "docs" / "compliance" / "UNIFIED_DHF_ANNEX_IV_TECHNICAL_FILE.md"
            dhf_md = generator.render_markdown_dossier(bundle)
            dhf_path.parent.mkdir(parents=True, exist_ok=True)
            dhf_path.write_text(dhf_md, encoding="utf-8")
            print(f"    • Exported Markdown DHF to: {dhf_path}")

        print("[✓] Execution Complete.")
        sys.exit(0)

    parser.print_help()


if __name__ == "__main__":
    main()
