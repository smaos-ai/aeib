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
tests/test_us_china_redteam_crosswalk.py — Verification suite for the Bilateral USA (NIST/OWASP/SEC/EO 14110)
& China (TC260 GB/T 45654-2025/CAC/PIPL/PBOC) Red-Team Quota-Bypass & Financial Gate Crosswalk.

Evaluated under the stated model. Tests:
1. Positive RFC 8785 JCS SHA-256 digest and Ed25519 signature verification.
2. Fail-closed tamper rejection on payload, digest, and signature mutations.
3. Completeness of the 6x6 Red-Team Bypass vs. AEIB Countermeasure Matrix, 5 Station 1-2 Invariants,
   4 USA frameworks, and 4 China frameworks.
4. AT56 (Smurfing Step-Up Interlock) and AT57 (16k-Token KV Block Memory Poisoning) simulation results.
5. CLI `--self-test` and `--output-json` execution via subprocess.run.
6. Epistemic lock check ensuring zero banned words across all owned files.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from compliance.us_china_redteam_crosswalk import (
    CHINA_FRAMEWORKS,
    MATRIX_COUNTERMEASURE_DIMENSIONS,
    RED_TEAM_BYPASS_6X6_MATRIX,
    STATION_1_2_ENGINEERING_INVARIANTS,
    USA_FRAMEWORKS,
    evaluate_at56_at57_simulation,
    generate_bilateral_redteam_report,
    verify_bilateral_redteam_report,
)


def test_generate_and_verify_bilateral_redteam_report_positive() -> None:
    """Verifies that a generated bilateral report passes RFC 8785 JCS and Ed25519 verification."""
    report = generate_bilateral_redteam_report(timestamp_utc="2026-10-17T03:00:00Z")
    ok, err = verify_bilateral_redteam_report(report)
    assert ok is True, f"Expected valid report, got error: {err}"
    assert err is None
    assert len(report["report_digest_sha256"]) == 64
    assert report["signer_did_key"].startswith("did:key:z")


def test_custom_ed25519_signing_key_roundtrip() -> None:
    """Verifies signing and verification with an explicit ephemeral Ed25519 keypair."""
    custom_key = ed25519.Ed25519PrivateKey.from_private_bytes(b"\x42" * 32)
    report = generate_bilateral_redteam_report(
        signing_privkey=custom_key,
        timestamp_utc="2026-10-17T03:15:00Z",
    )
    ok, err = verify_bilateral_redteam_report(report)
    assert ok is True, f"Custom key verification failed: {err}"


def test_tamper_rejection_on_matrix_digest_and_signature() -> None:
    """Verifies fail-closed rejection when payload, digest, or signature is tampered."""
    base_report = generate_bilateral_redteam_report(timestamp_utc="2026-10-17T03:00:00Z")

    # 1. Mutate a cell inside the 6x6 matrix
    tampered_cell = copy.deepcopy(base_report)
    tampered_cell["red_team_bypass_6x6_matrix"][2]["cells"][
        "station_2_zero_credential_sidecar_and_egress_isolation"
    ] = "compromised_bypass"
    ok, err = verify_bilateral_redteam_report(tampered_cell)
    assert ok is False
    assert err is not None and "digest mismatch" in err.lower()

    # 2. Mutate the signature bytes while keeping digest intact
    tampered_sig = copy.deepcopy(base_report)
    tampered_sig["signature_b64"] = "A" * 86 + "=="
    ok_sig, err_sig = verify_bilateral_redteam_report(tampered_sig)
    assert ok_sig is False
    assert err_sig is not None and "signature verification failed" in err_sig.lower()

    # 3. Remove an invariant
    missing_inv = copy.deepcopy(base_report)
    missing_inv["station_1_2_engineering_invariants"].pop()
    ok_inv, err_inv = verify_bilateral_redteam_report(missing_inv)
    assert ok_inv is False
    assert err_inv is not None and "5 station 1-2 engineering invariants" in err_inv.lower()

    # 4. Missing signature fields
    stripped = {
        k: v
        for k, v in base_report.items()
        if k not in ("report_digest_sha256", "signature_b64", "signer_public_key_pem")
    }
    ok_strip, err_strip = verify_bilateral_redteam_report(stripped)
    assert ok_strip is False
    assert err_strip is not None and "missing cryptographic signature fields" in err_strip.lower()


def test_6x6_matrix_and_5_invariants_completeness() -> None:
    """Verifies all 6 attack vectors x 6 countermeasure columns and all 5 Station 1-2 invariants."""
    assert len(RED_TEAM_BYPASS_6X6_MATRIX) == 6
    assert len(MATRIX_COUNTERMEASURE_DIMENSIONS) == 6

    expected_attack_names = {
        "Client Reset / Cache Wipe",
        "Multi-Account Sybil Rotator",
        "Fingerprint Spoofing",
        "Pool Hopping & Smurfing",
        "Direct Socket Egress",
        "AT57 Memory Poisoning + Context Window Manipulation",
    }
    observed_attack_names = {row["attack_vector"] for row in RED_TEAM_BYPASS_6X6_MATRIX}
    assert observed_attack_names == expected_attack_names

    for row in RED_TEAM_BYPASS_6X6_MATRIX:
        cells = row["cells"]
        assert set(cells.keys()) == set(MATRIX_COUNTERMEASURE_DIMENSIONS)
        for col_name, cell_text in cells.items():
            assert isinstance(cell_text, str) and len(cell_text.strip()) > 20, (
                f"Empty or trivial matrix cell at {row['vector_id']} / {col_name}"
            )

    assert len(STATION_1_2_ENGINEERING_INVARIANTS) == 5
    expected_invariant_ids = {
        "INV_1_SPONSOR_CONSERVATION_LAW",
        "INV_2_DUAL_WINDOW_SMURF_STEP_UP_GATE",
        "INV_3_ZERO_CREDENTIAL_DPOP_SIDECAR_ISOLATION",
        "INV_4_TRIPARTITE_CONTEXT_MEMORY_ADMISSIBILITY",
        "INV_5_WRITE_AHEAD_TRINARY_FINALITY_AND_PII_REDACTION",
    }
    observed_invariant_ids = {
        inv["invariant_id"] for inv in STATION_1_2_ENGINEERING_INVARIANTS
    }
    assert observed_invariant_ids == expected_invariant_ids


def test_usa_and_china_regulatory_frameworks_completeness() -> None:
    """Verifies all 4 USA frameworks and all 4 China frameworks and their required subclauses."""
    expected_usa_keys = {
        "NIST_AI_RMF_1_0_GENAI_2024",
        "OWASP_LLM_2025_AND_AGENTIC_ASI_2026",
        "SEC_8K_CYBERSECURITY_DISCLOSURE_2023",
        "US_EO_14110_SEC_4_1",
    }
    assert set(USA_FRAMEWORKS.keys()) == expected_usa_keys

    nist_subclauses = set(USA_FRAMEWORKS["NIST_AI_RMF_1_0_GENAI_2024"]["subclauses_mapped"])
    for req_clause in ("GOVERN 1.2", "MAP 3.5", "MEASURE 2.7", "MANAGE 2.4"):
        assert req_clause in nist_subclauses

    owasp_blob = json.dumps(USA_FRAMEWORKS["OWASP_LLM_2025_AND_AGENTIC_ASI_2026"])
    for code in ("LLM01", "ASI01", "LLM06", "ASI03", "LLM08", "ASI02", "ASI06", "AT57", "ASI08"):
        assert code in owasp_blob

    sec_blob = json.dumps(USA_FRAMEWORKS["SEC_8K_CYBERSECURITY_DISCLOSURE_2023"])
    assert "Station3ContinuousLedger" in sec_blob

    eo_blob = json.dumps(USA_FRAMEWORKS["US_EO_14110_SEC_4_1"])
    assert "AT30" in eo_blob and "AT57" in eo_blob

    expected_china_keys = {
        "CAC_GENAI_INTERIM_MEASURES_2023",
        "TC260_GBT_45654_2025_AND_FRAMEWORK_V3",
        "PIPL_ART_55_AND_DSL",
        "PBOC_FINANCIAL_AI_HITL",
    }
    assert set(CHINA_FRAMEWORKS.keys()) == expected_china_keys

    cac_blob = json.dumps(CHINA_FRAMEWORKS["CAC_GENAI_INTERIM_MEASURES_2023"])
    assert "RootSponsor" in cac_blob and "did:key" in cac_blob

    tc260_blob = json.dumps(CHINA_FRAMEWORKS["TC260_GBT_45654_2025_AND_FRAMEWORK_V3"])
    assert "GB/T 45654-2025" in tc260_blob and "Sybil" in tc260_blob

    pipl_blob = json.dumps(CHINA_FRAMEWORKS["PIPL_ART_55_AND_DSL"])
    assert "SHA-256" in pipl_blob and "Station 2" in pipl_blob

    pboc_blob = json.dumps(CHINA_FRAMEWORKS["PBOC_FINANCIAL_AI_HITL"])
    assert "RFC 9470" in pboc_blob


def test_at56_and_at57_simulation_determinism() -> None:
    """Verifies AT56 cumulative smurfing step-up trigger and AT57 KV-block poisoning rejection."""
    sim = evaluate_at56_at57_simulation()
    at56 = sim["at56_smurf_interlock_evaluation"]
    assert at56["third_micro_batch_halted_for_step_up"] is True
    assert at56["events"][0]["disposition"] == "PERMITTED_WITHIN_WINDOW"
    assert at56["events"][1]["disposition"] == "PERMITTED_WITHIN_WINDOW"
    assert at56["events"][2]["disposition"] == "HALTED_RFC9470_STEP_UP_REQUIRED"
    assert at56["final_committed_spend_cents"] == 240_00

    at57 = sim["at57_memory_poisoning_evaluation"]
    assert at57["kv_block_integrity_valid"] is False
    assert at57["disposition"] == "REJECTED_MEMORY_POISONING_AT57"
    assert at57["zero_bytes_transmitted_on_mismatch"] is True


def test_cli_self_test_and_output_json(tmp_path: Path) -> None:
    """Tests CLI `--self-test` and `--output-json` execution via subprocess.run."""
    out_json = tmp_path / "bilateral_report.json"
    script_path = REPO_ROOT / "compliance" / "us_china_redteam_crosswalk.py"

    proc = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--self-test",
            "--output-json",
            str(out_json),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"CLI failed: stdout={proc.stdout}\nstderr={proc.stderr}"
    assert out_json.is_file()

    loaded = json.loads(out_json.read_text(encoding="utf-8"))
    ok, err = verify_bilateral_redteam_report(loaded)
    assert ok is True, f"Exported JSON failed verification: {err}"


def test_zero_banned_words_in_owned_files() -> None:
    """Scans all 3 owned files to ensure strict compliance with AGENTS.md linguistic boundaries."""
    banned_phrases = [
        "guaran" + "teed",
        "guaran" + "tee",
        "proven " + "universally",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
    ]
    owned_files = [
        REPO_ROOT / "compliance" / "us_china_redteam_crosswalk.py",
        REPO_ROOT / "docs" / "compliance" / "RED_TEAM_QUOTA_BYPASS_FINANCIAL_GATE_DOSSIER.md",
        REPO_ROOT / "tests" / "test_us_china_redteam_crosswalk.py",
    ]

    for file_path in owned_files:
        assert file_path.is_file(), f"Missing owned file: {file_path}"
        content_lower = file_path.read_text(encoding="utf-8").lower()
        for phrase in banned_phrases:
            assert phrase not in content_lower, (
                f"Banned epistemic phrase {phrase!r} found in {file_path}"
            )
