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
tests/test_integrated_qms_and_product_safety.py
================================================================================
Verification Suite for Integrated AI QMS, Product Safety & DHF Technical File

Evaluates:
  1. Completeness of 4-Layer Standards Architecture (ISO 42001 + EN 18286 + ISO 13485 + CBOM).
  2. Statutory transition deadlines (Dec 2, 2027 Annex III & Aug 2, 2028 Annex I DHF).
  3. ISO 14971 Hazard Log mitigation mapping (HZD-01 through HZD-04).
  4. Cryptographic integrity of generated Annex IV Technical File (RFC 8785 JCS + Ed25519).
  5. Fail-closed tamper detection on illicit package mutations.
  6. Zero banned marketing superlatives across all generated files.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from compliance.unified_technical_file_generator import (
    HAZARD_LOG_ISO14971,
    STANDARDS_ARCHITECTURE_LAYERS,
    STATUTORY_DEADLINES_MAPPING,
    UnifiedTechnicalFileGenerator,
)


def test_four_layer_standards_architecture_completeness():
    """Verifies all 4 layers of the integrated standards architecture are present."""
    assert len(STANDARDS_ARCHITECTURE_LAYERS) == 4
    layer_ids = [l["layer_id"] for l in STANDARDS_ARCHITECTURE_LAYERS]
    assert "LAYER_1_ORGANIZATIONAL_AIMS" in layer_ids
    assert "LAYER_2_EU_AI_ACT_HARMONIZED_QMS" in layer_ids
    assert "LAYER_3_PRODUCT_SAFETY_AND_MEDICAL_DHF" in layer_ids
    assert "LAYER_4_SUPPLY_CHAIN_AND_CBOM" in layer_ids

    for layer in STANDARDS_ARCHITECTURE_LAYERS:
        assert layer["governing_clauses"]
        assert layer["runtime_enforcement_mechanism"]
        assert layer["evidence_reference"]
        assert layer["implementation_tier"] in ("OBSERVED_AND_TESTED", "SCAFFOLD_ONLY")


def test_statutory_deadlines_mapping():
    """Verifies Annex III (Dec 2, 2027) and Annex I (Aug 2, 2028) deadlines."""
    assert "ANNEX_III_STANDALONE_HIGH_RISK" in STATUTORY_DEADLINES_MAPPING
    assert "ANNEX_I_EMBEDDED_HIGH_RISK" in STATUTORY_DEADLINES_MAPPING

    annex_3 = STATUTORY_DEADLINES_MAPPING["ANNEX_III_STANDALONE_HIGH_RISK"]
    assert annex_3["enforcement_deadline"] == "2027-12-02"
    assert "Credit scoring" in annex_3["applicable_sectors"][0]

    annex_1 = STATUTORY_DEADLINES_MAPPING["ANNEX_I_EMBEDDED_HIGH_RISK"]
    assert annex_1["enforcement_deadline"] == "2028-08-02"
    assert "EU MDR" in annex_1["applicable_sectors"][0]
    assert "Design History File (DHF) Addendum" in annex_1["compliance_deliverable"]


def test_iso14971_hazard_log_coverage():
    """Verifies all 4 clinical/financial hazards are cataloged with mitigations."""
    assert len(HAZARD_LOG_ISO14971) >= 4
    hazard_ids = [h["hazard_id"] for h in HAZARD_LOG_ISO14971]
    assert "HZD-01-TRANSPORT-AMBIGUITY" in hazard_ids
    assert "HZD-02-PARALLEL-RESOURCE-DEPLETION" in hazard_ids
    assert "HZD-03-CONTEXT-POISONING" in hazard_ids
    assert "HZD-04-EVIDENTIARY-TAMPERING" in hazard_ids

    for hzd in HAZARD_LOG_ISO14971:
        assert hzd["clinical_or_financial_risk"]
        assert hzd["aeib_mitigation_control"]
        assert hzd["verification_test"]
        assert hzd["residual_risk_level"] == "ACCEPTABLE_UNDER_STATED_MODEL"


def test_generate_and_verify_unified_technical_file(tmp_path: Path):
    """Tests positive end-to-end technical file generation and cryptographic verification."""
    generator = UnifiedTechnicalFileGenerator(repo_root=REPO_ROOT)
    bundle = generator.generate_unified_technical_file()

    # Verify signature
    assert generator.verify_unified_technical_file(bundle) is True
    assert bundle["package_digest"]
    assert bundle["signature_hex"]
    assert bundle["signer_public_key_pem"]

    tf = bundle["technical_file"]
    assert tf["schema_version"] == "aeib.unified.technical.file.annex_iv.v1"
    sections = tf["annex_iv_six_mandatory_sections"]
    assert "section_1_general_description" in sections
    assert "section_2_component_integration_and_hardware" in sections
    assert "section_3_development_methods_and_computational_logic" in sections
    assert "section_4_monitoring_logging_and_auditing" in sections
    assert "section_5_risk_management_and_hazard_analysis" in sections
    assert "section_6_human_oversight_and_fail_closed_gates" in sections

    # Test markdown export
    md_content = generator.render_markdown_dossier(bundle)
    assert "# EU AI Act Annex IV Unified Technical File" in md_content
    assert bundle["package_digest"] in md_content


def test_tamper_detection_fails_closed():
    """Tests that any modification to the technical file causes verification failure."""
    generator = UnifiedTechnicalFileGenerator(repo_root=REPO_ROOT)
    bundle = generator.generate_unified_technical_file()

    # Tamper with document title
    tampered_bundle = json.loads(json.dumps(bundle))
    tampered_bundle["technical_file"]["document_title"] = "Tampered Document Title"

    assert generator.verify_unified_technical_file(tampered_bundle) is False

    # Tamper with hazard log
    tampered_bundle2 = json.loads(json.dumps(bundle))
    hlog = tampered_bundle2["technical_file"]["annex_iv_six_mandatory_sections"]["section_5_risk_management_and_hazard_analysis"]["hazard_log"]
    hlog[0]["residual_risk_level"] = "ZERO_RISK_FAKE"

    assert generator.verify_unified_technical_file(tampered_bundle2) is False


def test_cli_execution_self_test_and_verify(tmp_path: Path):
    """Tests CLI commands --self-test, --output-json, and --verify."""
    out_json = tmp_path / "test_technical_file.json"

    # Run generator with --output-json
    cmd_gen = [
        sys.executable,
        str(REPO_ROOT / "compliance" / "unified_technical_file_generator.py"),
        "--self-test",
        "--output-json",
        str(out_json),
    ]
    res_gen = subprocess.run(cmd_gen, capture_output=True, text=True, check=True)
    assert "[✓] Technical File Generated" in res_gen.stdout
    assert out_json.is_file()

    # Run verifier on generated JSON
    cmd_ver = [
        sys.executable,
        str(REPO_ROOT / "compliance" / "unified_technical_file_generator.py"),
        "--verify",
        str(out_json),
    ]
    res_ver = subprocess.run(cmd_ver, capture_output=True, text=True, check=True)
    assert "[✓] Verification SUCCESS" in res_ver.stdout


def test_epistemic_boundary_zero_banned_words():
    """Verifies zero banned marketing superlatives exist in the new compliance files."""
    banned_tokens = [
        "guaran" + "tee",
        "guaran" + "teed",
        "guaran" + "tees",
        "proven " + "universally",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
    ]
    pattern = re.compile(r"\b(" + "|".join(banned_tokens) + r")\b", re.IGNORECASE)

    files_to_check = [
        REPO_ROOT / "compliance" / "unified_technical_file_generator.py",
        REPO_ROOT / "docs" / "compliance" / "INTEGRATED_AI_QMS_AND_PRODUCT_SAFETY_DOSSIER.md",
        REPO_ROOT / "docs" / "compliance" / "UNIFIED_DHF_ANNEX_IV_TECHNICAL_FILE.md",
    ]

    for fpath in files_to_check:
        assert fpath.is_file(), f"Expected file not found: {fpath}"
        text = fpath.read_text(encoding="utf-8")
        matches = pattern.findall(text)
        assert not matches, f"Banned tokens {matches} found in {fpath}"
