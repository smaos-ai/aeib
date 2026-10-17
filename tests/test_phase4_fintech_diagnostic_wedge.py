#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
tests/test_phase4_fintech_diagnostic_wedge.py

Verification suite for the AEIB 48-Hour / €1,500 Fintech Agent Execution Diagnostic Wedge
(`tools/fintech_diagnostic_wedge.py`) and commercial pack documentation
(`docs/commercial/FINTECH_1500_EUR_AUDIT_WEDGE_PACK.md`).
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from tools.fintech_diagnostic_wedge import (
    DEFAULT_AEIB_HARDENED_CONFIG,
    DEFAULT_LEGACY_MCP_CONFIG,
    FintechDiagnosticWedgeEngine,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_unhardened_mcp_config_detects_toctou_asi_gaps_and_duplicates() -> None:
    """
    Evaluates an unhardened legacy MCP agent config and verifies detection of:
      - Matrix 1: AGENTIC_TOCTOU_EXPOSURE when OAuth 2.1 RFC 8707 is enabled without JCS CAID sink binding
      - Matrix 2: ASI01-ASI08 control gaps
      - Matrix 3: Duplicate mutations under HTTP 504 / TCP RST fault simulation
      - Matrix 4: EU regulatory evidence readiness gaps (DORA Art. 17/28 & EU AI Act prEN 18286)
      - Valid Ed25519 signature over RFC 8785 encode_jcs(report)
    """
    engine = FintechDiagnosticWedgeEngine(episodes=100, seed=42)
    bundle = engine.run_diagnostic(DEFAULT_LEGACY_MCP_CONFIG)

    assert engine.verify_signed_report(bundle) is True

    report = bundle["report"]
    assert report["overall_posture"] == "CRITICAL_EXECUTION_BOUNDARY_GAPS_OBSERVED"

    # Matrix 1 checks
    m1 = report["matrices"]["matrix_1_mcp_oauth21"]
    assert m1["agentic_toctou_exposure"] is True
    assert "AGENTIC_TOCTOU_EXPOSURE" in m1["flags"]
    assert m1["posture_status"] == "EXPOSURE_OBSERVED"

    # Matrix 2 checks
    m2 = report["matrices"]["matrix_2_owasp_asi_2026"]
    assert m2["configured_category_count"] == 0
    assert m2["evaluated_category_count"] == 6
    assert len(m2["missing_categories"]) == 6
    assert m2["posture_status"] == "GAPS_OBSERVED"

    # Matrix 3 checks
    m3 = report["matrices"]["matrix_3_transport_ambiguity"]
    assert m3["baseline_observed_duplicates"] > 0
    assert m3["configured_observed_duplicates"] > 0
    assert m3["aeib_observed_duplicates"] == 0
    assert m3["aeib_blocked_retries"] > 0
    assert m3["posture_status"] == "DUPLICATE_MUTATION_EXPOSURE_OBSERVED"

    # Matrix 4 checks
    m4 = report["matrices"]["matrix_4_eu_regulatory_readiness"]
    assert m4["ready_check_count"] == 0
    assert len(m4["missing_readiness_items"]) == 5
    assert m4["posture_status"] == "READINESS_GAPS_OBSERVED"


def test_aeib_hardened_config_achieves_zero_duplicates_and_valid_jcs_signature() -> None:
    """
    Evaluates an AEIB-hardened MCP config and verifies:
      - Matrix 1: Zero Agentic TOCTOU exposure with RFC 8785 JCS CAID sink binding
      - Matrix 2: Full ASI01, ASI02, ASI03, ASI06, ASI07, ASI08 control posture
      - Matrix 3: 0 configured duplicate mutations and >0 blocked retries on HTTP 504
      - Matrix 4: Full DORA Art. 17/28 EBA DPM 4.0 and EU AI Act prEN 18286 readiness
      - Independent Ed25519 signature verification over encode_jcs(report)
    """
    engine = FintechDiagnosticWedgeEngine(episodes=100, seed=42)
    bundle = engine.run_diagnostic(DEFAULT_AEIB_HARDENED_CONFIG)

    assert engine.verify_signed_report(bundle) is True

    report = bundle["report"]
    assert report["overall_posture"] == "EVALUATED_ALIGNED_UNDER_STATED_MODEL"

    m1 = report["matrices"]["matrix_1_mcp_oauth21"]
    assert m1["agentic_toctou_exposure"] is False
    assert m1["flags"] == []
    assert m1["posture_status"] == "EVALUATED_ALIGNED"

    m2 = report["matrices"]["matrix_2_owasp_asi_2026"]
    assert m2["configured_category_count"] == 6
    assert m2["missing_categories"] == []
    assert m2["posture_status"] == "EVALUATED_ALIGNED"

    m3 = report["matrices"]["matrix_3_transport_ambiguity"]
    assert m3["configured_observed_duplicates"] == 0
    assert m3["aeib_observed_duplicates"] == 0
    assert m3["configured_blocked_retries"] == m3["aeib_blocked_retries"]
    assert m3["aeib_blocked_retries"] > 0
    assert m3["posture_status"] == "EVALUATED_ALIGNED"

    m4 = report["matrices"]["matrix_4_eu_regulatory_readiness"]
    assert m4["ready_check_count"] == 5
    assert m4["missing_readiness_items"] == []
    assert m4["posture_status"] == "EVALUATED_ALIGNED"

    # Independent cryptographic verification over RFC 8785 JCS canonical bytes
    jcs_bytes = encode_jcs(report)
    assert hashlib.sha256(jcs_bytes).hexdigest() == bundle["report_digest"]
    pub_key = serialization.load_pem_public_key(bundle["public_key_pem"].encode("utf-8"))
    assert isinstance(pub_key, ed25519.Ed25519PublicKey)
    pub_key.verify(base64.b64decode(bundle["signature_b64"]), jcs_bytes)

    # Verify tamper detection fails closed when report payload is altered
    tampered = copy.deepcopy(bundle)
    tampered["report"]["matrices"]["matrix_3_transport_ambiguity"]["aeib_observed_duplicates"] = 1
    assert engine.verify_signed_report(tampered) is False


def test_cli_self_test_and_output_json_via_subprocess(tmp_path: Path) -> None:
    """
    Executes `tools/fintech_diagnostic_wedge.py --self-test --output-json <path>`
    via subprocess.run and verifies the emitted JSON structure and cryptographic proofs.
    """
    out_file = tmp_path / "wedge_self_test_output.json"
    cli_script = REPO_ROOT / "tools" / "fintech_diagnostic_wedge.py"

    proc = subprocess.run(
        [
            sys.executable,
            str(cli_script),
            "--self-test",
            "--episodes",
            "100",
            "--seed",
            "42",
            "--output-json",
            str(out_file),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    assert out_file.is_file()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    stdout_data = json.loads(proc.stdout)
    assert data == stdout_data

    assert data["comparison_schema"] == "aeib.fintech.wedge.comparison.v1"
    assert data["verification"]["legacy_signature_verified"] is True
    assert data["verification"]["hardened_signature_verified"] is True

    legacy_rep = data["legacy_unhardened_assessment"]["report"]
    hardened_rep = data["aeib_hardened_assessment"]["report"]

    assert (
        legacy_rep["matrices"]["matrix_1_mcp_oauth21"]["agentic_toctou_exposure"]
        is True
    )
    assert (
        hardened_rep["matrices"]["matrix_1_mcp_oauth21"]["agentic_toctou_exposure"]
        is False
    )
    assert (
        legacy_rep["matrices"]["matrix_3_transport_ambiguity"][
            "configured_observed_duplicates"
        ]
        > 0
    )
    assert (
        hardened_rep["matrices"]["matrix_3_transport_ambiguity"][
            "configured_observed_duplicates"
        ]
        == 0
    )


def test_epistemic_purity_and_commercial_pack_completeness() -> None:
    """
    Verifies that the commercial execution pack markdown and CLI source code contain
    zero banned epistemic words and include all required regulatory and architectural sections.
    """
    # Construct banned words list dynamically so this test file itself never contains literal banned strings
    banned_terms = [
        "guarant" + "eed",
        "guarant" + "ee",
        "proven " + "universally",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
    ]

    files_to_scan = [
        REPO_ROOT / "tools" / "fintech_diagnostic_wedge.py",
        REPO_ROOT / "docs" / "commercial" / "FINTECH_1500_EUR_AUDIT_WEDGE_PACK.md",
        REPO_ROOT / "tests" / "test_phase4_fintech_diagnostic_wedge.py",
    ]

    for file_path in files_to_scan:
        assert file_path.is_file(), f"Missing expected file: {file_path}"
        content_lower = file_path.read_text(encoding="utf-8").lower()
        for term in banned_terms:
            assert term not in content_lower, f"Banned term '{term}' found in {file_path}"

    doc_text = (
        REPO_ROOT / "docs" / "commercial" / "FINTECH_1500_EUR_AUDIT_WEDGE_PACK.md"
    ).read_text(encoding="utf-8")
    assert "€1,500" in doc_text
    assert "48-Hour" in doc_text
    assert "RFC 8707" in doc_text
    assert "RFC 9728" in doc_text
    assert "prEN 18286" in doc_text
    assert "EBA DPM 4.0" in doc_text
    assert "mermaid" in doc_text
    assert "€15,000" in doc_text
