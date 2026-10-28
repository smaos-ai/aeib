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
tests/test_iso_42001_full_38_controls_soa.py — Full 38-Control ISO/IEC 42001:2023 Annex A SoA Suite

Evaluates and tests:
1. Complete 38 normative controls across all 9 clauses of ISO/IEC 42001:2023 Annex A (A.2 through A.10:
   3 + 2 + 5 + 4 + 9 + 5 + 4 + 3 + 3 == 38).
2. Explicit INCLUDED (35) and EXCLUDED (3: A.7.4, A.7.5, A.8.3) applicability determinations, non-empty
   auditor justifications, risk IDs, OWASP ASI01:2026–ASI10:2026 mappings, and CEN-CENELEC prEN 18286
   QMS clauses.
3. Real SHA-256 file digests on disk and Ed25519 signature verification over RFC 8785 JCS canonical bytes.
4. Markdown and CSV SoA rendering and CLI `--format`, `--output-md`, and `--verify` execution.
"""

import base64
import csv
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from compliance.iso_42001_soa import (
    CATEGORY_H_CONTROLS,
    DEFAULT_REPORT_JSON_PATH,
    DEFAULT_REPORT_MD_PATH,
    ISO_42001_ANNEX_A_38_CONTROLS,
    main as soa_cli_main,
    render_soa_csv,
    render_soa_markdown,
    scan_iso_42001_soa,
    verify_soa_report,
)
from src.jcs_canonicalizer import encode_jcs

EXPECTED_CLAUSE_CONTROL_IDS = {
    "A.2": ["A.2.2", "A.2.3", "A.2.4"],
    "A.3": ["A.3.2", "A.3.3"],
    "A.4": ["A.4.2", "A.4.3", "A.4.4", "A.4.5", "A.4.6"],
    "A.5": ["A.5.2", "A.5.3", "A.5.4", "A.5.5"],
    "A.6": [
        "A.6.1.2",
        "A.6.1.3",
        "A.6.2.2",
        "A.6.2.3",
        "A.6.2.4",
        "A.6.2.5",
        "A.6.2.6",
        "A.6.2.7",
        "A.6.2.8",
    ],
    "A.7": ["A.7.2", "A.7.3", "A.7.4", "A.7.5", "A.7.6"],
    "A.8": ["A.8.2", "A.8.3", "A.8.4", "A.8.5"],
    "A.9": ["A.9.2", "A.9.3", "A.9.4"],
    "A.10": ["A.10.2", "A.10.3", "A.10.4"],
}

EXPECTED_EXCLUDED_IDS = {"A.7.4", "A.7.5", "A.8.3"}

BANNED_WORDS = (
    "guaran" + "teed",
    "guaran" + "tee",
    "proven " + "universally",
    "bullet" + "proof",
    "enterprise-" + "grade",
    "production-" + "safe",
    "100% " + "secure",
)


class TestIso42001Full38ControlsSoa:
    def test_annex_a_38_controls_clause_distribution_and_ids(self):
        assert len(ISO_42001_ANNEX_A_38_CONTROLS) == 38
        clause_counts = [len(ids) for ids in EXPECTED_CLAUSE_CONTROL_IDS.values()]
        assert clause_counts == [3, 2, 5, 4, 9, 5, 4, 3, 3]
        assert sum(clause_counts) == 38

        actual_ids = [c["control_id"] for c in ISO_42001_ANNEX_A_38_CONTROLS]
        expected_ids = [
            cid for ids in EXPECTED_CLAUSE_CONTROL_IDS.values() for cid in ids
        ]
        assert actual_ids == expected_ids

        for clause_prefix, expected_clause_ids in EXPECTED_CLAUSE_CONTROL_IDS.items():
            matched = [
                c["control_id"]
                for c in ISO_42001_ANNEX_A_38_CONTROLS
                if c["control_id"].startswith(clause_prefix + ".")
            ]
            assert matched == expected_clause_ids

    def test_included_35_and_excluded_3_justifications_and_risk_mappings(self):
        included = [
            c for c in ISO_42001_ANNEX_A_38_CONTROLS if c["applicability"] == "INCLUDED"
        ]
        excluded = [
            c for c in ISO_42001_ANNEX_A_38_CONTROLS if c["applicability"] == "EXCLUDED"
        ]

        assert len(included) == 35
        assert len(excluded) == 3
        assert {c["control_id"] for c in excluded} == EXPECTED_EXCLUDED_IDS

        for ctrl in ISO_42001_ANNEX_A_38_CONTROLS:
            cid = ctrl["control_id"]
            assert isinstance(ctrl["clause"], str) and ctrl["clause"].startswith("A.")
            assert isinstance(ctrl["title"], str) and len(ctrl["title"].strip()) > 3
            assert isinstance(ctrl["justification"], str) and len(ctrl["justification"].strip()) > 30
            assert (
                isinstance(ctrl["risk_assessment_mapping"], str)
                and len(ctrl["risk_assessment_mapping"].strip()) > 20
            )
            assert "RISK-" in ctrl["risk_assessment_mapping"]
            assert "ASI" in ctrl["risk_assessment_mapping"]
            assert "prEN 18286" in ctrl["risk_assessment_mapping"]
            assert len(ctrl["target_files"]) >= 1

            if cid in EXPECTED_EXCLUDED_IDS:
                assert ctrl["applicability"] == "EXCLUDED"
                assert ctrl["implementation_tier"] == "NOT_APPLICABLE_EXCLUDED"
                assert "EXCLUDED:" in ctrl["justification"]
                assert "Compensating boundary controls:" in ctrl["justification"]
            else:
                assert ctrl["applicability"] == "INCLUDED"
                assert ctrl["implementation_tier"] in (
                    "OBSERVED_AND_TESTED",
                    "SCAFFOLD_ONLY",
                )
                assert "INCLUDED:" in ctrl["justification"]

    def test_scan_iso_42001_soa_sha256_digests_and_ed25519_jcs_signature(self):
        report = scan_iso_42001_soa()

        # Backward compatibility checks for Category H (14 controls)
        assert report["total_controls"] == 14
        assert report["implemented_controls"] == 14
        assert int(report["observed_and_tested_controls"]) == 12
        assert report["scaffold_only_controls"] == 2
        assert len(report["statement_of_applicability"]) == 14

        # Full 38 Annex A control checks
        assert int(report["annex_a_total_controls"]) == 38
        assert report["annex_a_included_controls"] == 35
        assert report["annex_a_excluded_controls"] == 3
        assert report["annex_a_not_applicable_excluded_controls"] == 3
        assert (
            report["annex_a_observed_and_tested_controls"]
            + report["annex_a_scaffold_only_controls"]
            == 35
        )
        assert report["annex_a_clause_counts"] == {
            "A.2": 3,
            "A.3": 2,
            "A.4": 5,
            "A.5": 4,
            "A.6": 9,
            "A.7": 5,
            "A.8": 4,
            "A.9": 3,
            "A.10": 3,
        }

        annex_a_list = report["annex_a_controls"]
        assert len(annex_a_list) == 38
        for item in annex_a_list:
            assert len(item["missing_files"]) == 0
            assert len(item["verified_files"]) >= 1
            for rel_path, sha_hex in item["verified_files_sha256"].items():
                disk_path = REPO_ROOT / rel_path
                assert disk_path.is_file()
                assert hashlib.sha256(disk_path.read_bytes()).hexdigest() == sha_hex

        # Verify JCS canonicalization and Ed25519 signature
        unsigned_payload = {
            k: v
            for k, v in report.items()
            if k not in ("soa_digest", "soa_signature_b64", "signer_public_key_pem")
        }
        canonical_bytes = encode_jcs(unsigned_payload)
        assert hashlib.sha256(canonical_bytes).hexdigest() == report["soa_digest"]

        pubkey = serialization.load_pem_public_key(
            report["signer_public_key_pem"].encode("ascii")
        )
        sig_bytes = base64.b64decode(report["soa_signature_b64"])
        pubkey.verify(sig_bytes, canonical_bytes)

    def test_render_soa_markdown_and_csv_and_cli_verify(self, tmp_path):
        custom_md = tmp_path / "custom_soa.md"
        exit_code = soa_cli_main(["--format", "all", "--output-md", str(custom_md)])
        assert exit_code == 0
        assert custom_md.is_file()

        # Re-generate default files so repository state stays synchronized
        report = scan_iso_42001_soa()
        assert DEFAULT_REPORT_JSON_PATH.is_file()
        assert DEFAULT_REPORT_MD_PATH.is_file()

        md_text = render_soa_markdown(report)
        assert "# ISO/IEC 42001:2023 Statement of Applicability (SoA)" in md_text
        assert report["soa_digest"] in md_text
        for ctrl in ISO_42001_ANNEX_A_38_CONTROLS:
            assert f"| **{ctrl['control_id']}** |" in md_text
        for h_ctrl in CATEGORY_H_CONTROLS:
            assert f"| **{h_ctrl['control_id']}** |" in md_text

        csv_text = render_soa_csv(report)
        rows = list(csv.reader(io.StringIO(csv_text)))
        # 1 header row + 38 Annex A controls + 14 Category H controls = 53 rows
        assert len(rows) == 1 + 38 + 14
        annex_rows = [r for r in rows[1:] if r[0] == "ISO_42001_ANNEX_A"]
        cat_h_rows = [r for r in rows[1:] if r[0] == "CATEGORY_H_RUNTIME"]
        assert len(annex_rows) == 38
        assert len(cat_h_rows) == 14

        # Verify CLI --verify succeeds on authentic report
        verify_res = verify_soa_report(DEFAULT_REPORT_JSON_PATH)
        assert verify_res["verified"] is True
        assert int(verify_res["annex_a_controls_verified"]) == 38
        assert verify_res["category_h_controls_verified"] == 14

        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "compliance" / "iso_42001_soa.py"), "--verify"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        assert proc.returncode == 0
        assert report["soa_digest"] in proc.stdout

        # Negative test: tampering with a control justification invalidates JCS digest / signature
        tampered_path = tmp_path / "tampered_soa.json"
        tampered_report = json.loads(DEFAULT_REPORT_JSON_PATH.read_text(encoding="utf-8"))
        tampered_report["annex_a_controls"][0]["justification"] = "Tampered justification"
        tampered_path.write_text(json.dumps(tampered_report, indent=2), encoding="utf-8")
        with pytest.raises(ValueError, match="JCS digest mismatch"):
            verify_soa_report(tampered_path)

    def test_epistemic_boundary_zero_banned_words(self):
        target_paths = [
            REPO_ROOT / "compliance" / "iso_42001_soa.py",
            DEFAULT_REPORT_JSON_PATH,
            DEFAULT_REPORT_MD_PATH,
        ]
        for path in target_paths:
            text_lower = path.read_text(encoding="utf-8").lower()
            for banned in BANNED_WORDS:
                assert banned not in text_lower, f"Banned term '{banned}' found in {path}"
