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
tests/test_phase4_dora_and_iso42001_exporters.py — Phase 4 Compliance Exporters Verification Suite

Evaluates and tests:
1. DORA Art. 17 incident evidence exporters (`tools/export_dora_art17_evidence.py` and `compliance/dora_art17_exporter.py`).
2. DORA Art. 28(3) EBA DPM 4.0 xBRL-CSV Open Information Model (OIM) report package exporter (`compliance/dora_art28_roi_exporter.py`).
3. ISO/IEC 42001:2023 + CEN-CENELEC prEN 18286 Statement of Applicability scanner (`compliance/iso_42001_soa.py`).
"""

import base64
import csv
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from compliance.dora_art17_exporter import (
    export_dora_art17_to_file,
    generate_dora_art17_report,
)
from compliance.dora_art28_roi_exporter import (
    RT_02_01_HEADERS,
    export_dora_register_to_file,
    export_dora_roi_package,
    export_eba_dpm40_xbrl_csv_package,
    generate_dora_rt0101_rows,
    generate_dora_rt0201_rows,
)
from compliance.iso_42001_soa import CATEGORY_H_CONTROLS, scan_iso_42001_soa
from src.incident_evidence import AuthorityRevocationState, BoundaryVerdict
from src.jcs_canonicalizer import encode_jcs
from tools.export_dora_art17_evidence import DoraArt17Exporter


class TestPhase4DoraArt17Exporters:
    def test_dora_art17_exporter_three_plane_evidence_and_ed25519_jcs_signature(self):
        privkey = ed25519.Ed25519PrivateKey.generate()
        exporter = DoraArt17Exporter(signing_privkey=privkey)

        caid_hex = hashlib.sha256(
            encode_jcs({"noun": "Treasury", "verb": "Disburse", "amount": 250000})
        ).hexdigest()
        manifest_hex = hashlib.sha256(
            encode_jcs({"manifest_version": "1.1.0", "suite": "dora-art17"})
        ).hexdigest()

        bundle = exporter.generate_incident_package(
            incident_id="INC-2026-DORA-1701",
            operation_id="op:sepa:8821",
            caid=caid_hex,
            fault_type="http_504_gateway_timeout",
            detection_timestamp_utc="2026-10-17T01:00:00Z",
            classification_timestamp_utc="2026-10-17T01:15:00Z",
            resolved_timestamp_utc=None,
            financial_impact_minor_units=250000,
            currency="EUR",
            governing_authority_id="auth-grant-sepa-01",
            authority_revocation_state=AuthorityRevocationState.VALID,
            boundary_verdict=BoundaryVerdict.EFFECT_INDETERMINATE,
            reproducibility_manifest_sha256=manifest_hex,
        )

        pkg = bundle["package"]
        assert pkg["dora_schema_version"] == "1.1.0-dora-art17"
        assert pkg["incident_id"] == "INC-2026-DORA-1701"
        assert pkg["incident_candidate"]["reconciliation_state"] == "EFFECT_INDETERMINATE"
        assert pkg["incident_candidate"]["reporting_decision"] == "not_determined_by_aeib"
        assert "4-hour clock runs from major-incident classification" in pkg["timeline"]["initial_notification_clock_note"]

        evidence = pkg["incident_evidence"]
        assert "model_behavior" in evidence
        assert "execution_authority" in evidence
        assert "observed_consequence" in evidence
        assert evidence["observed_consequence"]["final_disposition"] == "EFFECT_INDETERMINATE"

        canonical_bytes = encode_jcs(pkg)
        expected_digest = hashlib.sha256(canonical_bytes).hexdigest()
        assert bundle["package_digest"] == expected_digest

        pubkey = serialization.load_pem_public_key(
            bundle["boundary_public_key_pem"].encode("ascii")
        )
        sig = base64.b64decode(bundle["boundary_signature_b64"])
        pubkey.verify(sig, canonical_bytes)

    def test_compliance_dora_art17_exporter_4h_deadline_and_file_output(self, tmp_path):
        report = generate_dora_art17_report(
            incident_id="INC-2026-RTS-09",
            detection_timestamp_utc="2026-10-17T08:30:00Z",
            impacted_service="SEPA Instant Settlement Gateway",
            transport_fault="tcp_rst_mid_flight",
            caid="caid:sha256:99887766554433221100",
            operation_id="op:sepa:09",
            disposition="EFFECT_INDETERMINATE",
        )
        assert report["regulation"] == "EU 2022/2554 (DORA)"
        assert report["timeline"]["detection_timestamp_utc"] == "2026-10-17T08:30:00Z"
        assert report["timeline"]["regulatory_notification_deadline_utc"] == "2026-10-17T12:30:00Z"
        assert report["timeline"]["window_hours"] == 4
        assert report["telemetry_evidence"]["fail_closed_latch_engaged"] is True
        assert report["telemetry_evidence"]["retry_suppressed"] is True

        out_path = tmp_path / "art17_report.json"
        export_dora_art17_to_file(report, out_path)
        assert out_path.is_file()
        loaded = json.loads(out_path.read_text(encoding="utf-8"))
        assert loaded["incident_id"] == "INC-2026-RTS-09"


class TestPhase4EbaDpm40XbrlCsvExporter:
    def test_export_eba_dpm40_xbrl_csv_package_structure_and_signature(self, tmp_path):
        entity_lei = "5493006MHB84DD0ZWV18"
        ref_period = "2026-12-31"
        arrangements = [
            {
                "entity_lei": entity_lei,
                "entity_name": "Sovereign Bank Europe",
                "contract_reference": "CTR-DORA-2026-01",
                "tpsp_lei": "529900HNOAA1KXQJUQ27",
                "tpsp_name": "SovereignNexus AEIB Runtime",
                "criticality_assessment": "CRITICAL",
                "service_type": "AI_EXECUTION_GATEWAY",
                "country_of_provision": "CZ",
                "effective_date": "2026-01-01",
            }
        ]
        services = [
            {
                "entity_lei": entity_lei,
                "contract_reference": "CTR-DORA-2026-01",
                "service_identifier": "SVC-AEIB-GATEWAY-01",
                "service_type": "AI_EXECUTION_GATEWAY",
                "criticality_flag": "CRITICAL",
                "recovery_time_objective_hours": 1,
                "recovery_point_objective_hours": 0,
            }
        ]

        privkey = ed25519.Ed25519PrivateKey.generate()
        result = export_eba_dpm40_xbrl_csv_package(
            entity_lei=entity_lei,
            ref_period=ref_period,
            arrangements=arrangements,
            services=services,
            output_dir=tmp_path,
            signing_privkey=privkey,
        )

        pkg_name = result["package_name"]
        pkg_dir = result["package_dir"]
        zip_path = result["zip_path"]

        assert pkg_dir.is_dir()
        assert zip_path.is_file()
        assert zip_path.name == f"{pkg_name}.zip"

        # 1. Verify META-INF/reportPackage.json
        report_pkg_file = pkg_dir / "META-INF" / "reportPackage.json"
        assert report_pkg_file.is_file()
        report_pkg_json = json.loads(report_pkg_file.read_text(encoding="utf-8"))
        assert report_pkg_json == {
            "documentInfo": {
                "documentType": "https://xbrl.org/report-package/2023"
            }
        }

        # 2. Verify reports/report.json
        report_json_file = pkg_dir / "reports" / "report.json"
        assert report_json_file.is_file()
        report_json = json.loads(report_json_file.read_text(encoding="utf-8"))
        assert report_json == {
            "documentInfo": {
                "documentType": "https://xbrl.org/2021/xbrl-csv",
                "extends": [
                    "http://www.eba.europa.eu/eu/fr/xbrl/crr/fws/dora/4.0/mod/dora.json"
                ],
            }
        }

        # 3. Verify reports/parameters.csv
        params_file = pkg_dir / "reports" / "parameters.csv"
        assert params_file.is_file()
        params_rows = list(csv.reader(io.StringIO(params_file.read_text(encoding="utf-8"))))
        assert params_rows[0] == ["name", "value"]
        params_dict = {row[0]: row[1] for row in params_rows[1:]}
        assert params_dict["entityID"] == f"rs:{entity_lei}"
        assert params_dict["refPeriod"] == ref_period
        assert params_dict["baseCurrency"] == "iso4217:EUR"
        assert params_dict["decimalsInteger"] == "0"
        assert params_dict["decimalsMonetary"] == "-2"

        # 4. Verify reports/FilingIndicators.csv
        fi_file = pkg_dir / "reports" / "FilingIndicators.csv"
        assert fi_file.is_file()
        fi_rows = list(csv.reader(io.StringIO(fi_file.read_text(encoding="utf-8"))))
        assert fi_rows[0] == ["templateID", "reported"]
        fi_dict = {row[0]: row[1] for row in fi_rows[1:]}
        assert fi_dict == {
            "B_01.01": "true",
            "B_02.01": "true",
            "B_05.01": "true",
        }

        # 5. Verify strictly lowercase b_01.01.csv and b_02.01.csv filenames
        b01_file = pkg_dir / "reports" / "b_01.01.csv"
        b02_file = pkg_dir / "reports" / "b_02.01.csv"
        assert b01_file.is_file()
        assert b02_file.is_file()
        reports_filenames = [p.name for p in (pkg_dir / "reports").iterdir()]
        assert "b_01.01.csv" in reports_filenames
        assert "b_02.01.csv" in reports_filenames

        # 6. Verify ZIP archive has single matching top-level directory {package_name}/
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            assert len(namelist) >= 7
            top_dirs = {name.split("/")[0] for name in namelist}
            assert top_dirs == {pkg_name}
            assert f"{pkg_name}/META-INF/reportPackage.json" in namelist
            assert f"{pkg_name}/reports/report.json" in namelist
            assert f"{pkg_name}/reports/parameters.csv" in namelist
            assert f"{pkg_name}/reports/FilingIndicators.csv" in namelist
            assert f"{pkg_name}/reports/b_01.01.csv" in namelist
            assert f"{pkg_name}/reports/b_02.01.csv" in namelist
            assert f"{pkg_name}/package_manifest_receipt.json" in namelist

        # 7. Verify SHA-256 digests and Ed25519 signature over JCS-canonicalized manifest
        receipt = result["manifest_receipt"]
        manifest_payload = receipt["manifest"]
        for rel_path, recorded_sha256 in manifest_payload["files_sha256"].items():
            actual_bytes = (pkg_dir / rel_path).read_bytes()
            assert hashlib.sha256(actual_bytes).hexdigest() == recorded_sha256

        canonical_manifest = encode_jcs(manifest_payload)
        assert hashlib.sha256(canonical_manifest).hexdigest() == receipt["manifest_digest_sha256"]

        pubkey = serialization.load_pem_public_key(
            receipt["signer_public_key_pem"].encode("ascii")
        )
        sig_bytes = base64.b64decode(receipt["signature_b64"])
        pubkey.verify(sig_bytes, canonical_manifest)


class TestPhase4Iso42001AndEn18286SoaScanner:
    def test_scan_iso_42001_soa_controls_tiers_mappings_and_signature(self):
        # Run with default deterministic signing key so compliance/iso_42001_soa_report.json stays reproducible
        report = scan_iso_42001_soa()

        assert report["standard"] == "ISO/IEC 42001:2023"
        assert report["total_controls"] == 14
        assert report["implemented_controls"] == 14
        assert report["observed_and_tested_controls"] == 12
        assert report["scaffold_only_controls"] == 2
        assert report["coverage_percentage"] == 100.0

        controls_by_id = {
            item["control_id"]: item for item in report["statement_of_applicability"]
        }
        assert len(controls_by_id) == 14

        # Check H.10 accurate description without unsubstantiated BBS+ pairing claims
        h10 = controls_by_id["H.10"]
        assert (
            h10["description"]
            == "Salted SHA-256 field commitment selective redaction for confidential PII in audit receipts"
        )
        assert h10["implementation_tier"] == "OBSERVED_AND_TESTED"

        # Check H.13 and H.14 SCAFFOLD_ONLY markings and accurate descriptions per AGENTS.md §5
        h13 = controls_by_id["H.13"]
        assert h13["implementation_tier"] == "SCAFFOLD_ONLY"
        assert (
            h13["description"]
            == "Structural scaffolding for Confidential VM attestation (TDX / SEV-SNP); requires deployment on a hardware-enforced Linux CVM kernel"
        )

        h14 = controls_by_id["H.14"]
        assert h14["implementation_tier"] == "SCAFFOLD_ONLY"
        assert (
            h14["description"]
            == "Structural scaffolding for Linux eBPF socket/LSM guard and step-up timeout failsafes"
        )

        # Check all other controls are OBSERVED_AND_TESTED and all have EN 18286 + OWASP ASI 2026 mappings
        for cid, ctrl in controls_by_id.items():
            if cid in ("H.13", "H.14"):
                assert ctrl["implementation_tier"] == "SCAFFOLD_ONLY"
            else:
                assert ctrl["implementation_tier"] == "OBSERVED_AND_TESTED"

            assert ctrl["en_18286_qms_clause"].startswith("prEN 18286")
            assert ctrl["owasp_asi_2026"].startswith("ASI")
            assert len(ctrl["verified_files"]) >= 1
            assert len(ctrl["missing_files"]) == 0

            # Verify real SHA-256 file hashes
            for f_rel, digest in ctrl["verified_files_sha256"].items():
                actual_digest = hashlib.sha256((REPO_ROOT / f_rel).read_bytes()).hexdigest()
                assert digest == actual_digest

        # Verify JCS canonicalization and Ed25519 signature over report payload
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
        sig = base64.b64decode(report["soa_signature_b64"])
        pubkey.verify(sig, canonical_bytes)

        # Verify persisted compliance/iso_42001_soa_report.json matches
        report_file = REPO_ROOT / "compliance" / "iso_42001_soa_report.json"
        assert report_file.is_file()
        persisted = json.loads(report_file.read_text(encoding="utf-8"))
        assert persisted["soa_digest"] == report["soa_digest"]
        assert persisted["soa_signature_b64"] == report["soa_signature_b64"]

