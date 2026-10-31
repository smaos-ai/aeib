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
tests/test_itsef_cem_evaluation_runner.py
================================================================================
Verification suite for ITSEFCEMEvaluationRunner and ETR report integrity.
Evaluated under the stated model across 11 ISO/IEC 18045 CEM work units.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.itsef_cem_evaluation_runner import (
    ITSEFCEMEvaluationRunner,
    ITSEFEvaluationTechnicalReport,
    sha256_jcs_caid,
)


@pytest.fixture
def itsef_runner() -> ITSEFCEMEvaluationRunner:
    runner = ITSEFCEMEvaluationRunner()
    if not (runner.pack_dir / "SUBMISSION_MANIFEST.json").exists():
        fallback_pack = Path(__file__).resolve().parent.parent / "dist" / "common_criteria_eal4_submission_pack"
        runner = ITSEFCEMEvaluationRunner(pack_dir=fallback_pack)
    return runner


def test_itsef_runner_nominal_execution(itsef_runner: ITSEFCEMEvaluationRunner):
    """Evaluates nominal CEM audit across all 11 work units."""
    report, telemetry = itsef_runner.run_evaluation_audit()

    assert isinstance(report, ITSEFEvaluationTechnicalReport)
    assert report.status == "INTERNAL PREVIEW COMMISSIONED"
    assert report.evaluation_target == "SovereignNexus AEIB v1.1"
    assert report.evaluation_assurance_level == "EAL4+ (ALC_FLR.2 + AVA_VAN.4)"
    units = telemetry["evaluated_units"]
    assert len(units) == len(itsef_runner.CEM_WORK_UNITS)
    assert report.work_units_evaluated_count == len(units)
    assert report.work_units_conforming_count == len(units)
    assert report.compliance_score_bps == 10000
    assert report.created_epoch_ms > 1_700_000_000_000
    assert report.submission_pack_caid.startswith("sha256:")
    assert report.etr_caid.startswith("sha256:")

    for u in units:
        assert u["conforming"] is True
        assert u["document_exists"] is True


def test_itsef_runner_constants_and_work_units(itsef_runner: ITSEFCEMEvaluationRunner):
    """Verifies strict constants and full CEM work unit catalog."""
    units = itsef_runner.CEM_WORK_UNITS
    assert itsef_runner.EXPECTED_WORK_UNITS_COUNT == len(units)
    assert itsef_runner.MIN_MUTATION_KILL_THRESHOLD_BPS == 80 * 100

    assert len(units) >= 10

    unit_ids = [u.work_unit_id for u in units]
    assert "ASE_TSS.1-1" in unit_ids
    assert "ADV_FSP.4-1" in unit_ids
    assert "ADV_FSP.4-2" in unit_ids
    assert "ADV_TDS.3-1" in unit_ids
    assert "ADV_TDS.3-2" in unit_ids
    assert "ALC_FLR.2-1" in unit_ids
    assert "ALC_FLR.2-2" in unit_ids
    assert "ATE_COV.2-1" in unit_ids
    assert "ATE_FUN.1-1" in unit_ids
    assert "ATE_IND.2-1" in unit_ids
    assert "AVA_VAN.4-1" in unit_ids


def test_itsef_runner_serialization_and_zero_floats(itsef_runner: ITSEFCEMEvaluationRunner):
    """Verifies zero floats in ETR output and deterministic CAID calculation."""
    report, _ = itsef_runner.run_evaluation_audit()
    rep_dict = report.to_dict()

    for k, v in rep_dict.items():
        assert not isinstance(v, float), f"Forbidden float in field: {k}"

    body = {k: v for k, v in rep_dict.items() if k != "etr_caid"}
    expected_caid = sha256_jcs_caid(body)
    assert report.etr_caid == expected_caid


def test_itsef_runner_file_verification_and_tampering(
    itsef_runner: ITSEFCEMEvaluationRunner,
    tmp_path: Path,
):
    """Evaluates report verification and tamper rejection."""
    report, _ = itsef_runner.run_evaluation_audit()
    rep_file = tmp_path / "test_etr.json"
    rep_file.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    # 1. Nominal verification
    assert ITSEFCEMEvaluationRunner.verify_etr_file(rep_file) is True

    # 2. Tampered score rejection
    data_score = json.loads(rep_file.read_text(encoding="utf-8"))
    data_score["compliance_score_bps"] = 9999
    tampered_score = tmp_path / "tampered_score_etr.json"
    tampered_score.write_text(json.dumps(data_score, indent=2), encoding="utf-8")
    assert ITSEFCEMEvaluationRunner.verify_etr_file(tampered_score) is False

    # 3. Tampered status rejection
    data_status = json.loads(rep_file.read_text(encoding="utf-8"))
    data_status["status"] = "CERTIFIED_COMPLIANT"
    tampered_status = tmp_path / "tampered_status_etr.json"
    tampered_status.write_text(json.dumps(data_status, indent=2), encoding="utf-8")
    assert ITSEFCEMEvaluationRunner.verify_etr_file(tampered_status) is False


def test_itsef_runner_missing_and_corrupt_files(tmp_path: Path):
    """Evaluates fail-closed handling of missing and corrupt ETR files."""
    missing_file = tmp_path / "nonexistent.json"
    assert ITSEFCEMEvaluationRunner.verify_etr_file(missing_file) is False

    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{invalid json...", encoding="utf-8")
    assert ITSEFCEMEvaluationRunner.verify_etr_file(corrupt_file) is False

    empty_caid = tmp_path / "empty_caid.json"
    empty_caid.write_text(json.dumps({"etr_caid": ""}), encoding="utf-8")
    assert ITSEFCEMEvaluationRunner.verify_etr_file(empty_caid) is False

    non_str_caid = tmp_path / "non_str_caid.json"
    non_str_caid.write_text(json.dumps({"etr_caid": 99999}), encoding="utf-8")
    assert ITSEFCEMEvaluationRunner.verify_etr_file(non_str_caid) is False

    non_sha_caid = tmp_path / "non_sha_caid.json"
    non_sha_caid.write_text(json.dumps({"etr_caid": "md5:abcdef"}), encoding="utf-8")
    assert ITSEFCEMEvaluationRunner.verify_etr_file(non_sha_caid) is False

    no_caid = tmp_path / "no_caid.json"
    no_caid.write_text(json.dumps({"status": "INTERNAL PREVIEW COMMISSIONED"}), encoding="utf-8")
    assert ITSEFCEMEvaluationRunner.verify_etr_file(no_caid) is False


def test_itsef_runner_partial_conformance(itsef_runner: ITSEFCEMEvaluationRunner, tmp_path: Path):
    """Evaluates non-conforming work units when required criteria are partially missing."""
    import shutil
    partial_pack = tmp_path / "partial_pack"
    shutil.copytree(itsef_runner.pack_dir, partial_pack)

    # 1. Tamper 00_SECURITY_TARGET_EAL4_PLUS.md: remove FPT_FLS.1/FAIL_CLOSED and ATE_COV.2
    st_file = partial_pack / "00_SECURITY_TARGET_EAL4_PLUS.md"
    st_file.write_text(st_file.read_text(encoding="utf-8").replace("FPT_FLS.1/FAIL_CLOSED", "REMOVED").replace("ATE_COV.2", "REMOVED"), encoding="utf-8")

    # 2. Tamper 01_FUNCTIONAL_SPEC_ADV_FSP_4.md: remove TSFI-09 and Error States
    fsp_file = partial_pack / "01_FUNCTIONAL_SPEC_ADV_FSP_4.md"
    fsp_text = fsp_file.read_text(encoding="utf-8").replace("TSFI-09", "REMOVED").replace("Error States", "REMOVED")
    fsp_file.write_text(fsp_text, encoding="utf-8")

    # 3. Tamper 02_TOE_DESIGN_ADV_TDS_3.md: remove Zone 3 and Physical Zone
    tds_file = partial_pack / "02_TOE_DESIGN_ADV_TDS_3.md"
    tds_text = tds_file.read_text(encoding="utf-8").replace("Zone 3", "REMOVED").replace("Physical Zone", "REMOVED")
    tds_file.write_text(tds_text, encoding="utf-8")

    # 4. Tamper 04_FLAW_REMEDIATION_ALC_FLR_2.md: remove Lesson L23 and 8667 bps
    flr_file = partial_pack / "04_FLAW_REMEDIATION_ALC_FLR_2.md"
    flr_text = flr_file.read_text(encoding="utf-8").replace("Lesson L23", "REMOVED").replace("8667 bps", "REMOVED")
    flr_file.write_text(flr_text, encoding="utf-8")

    # 5. Tamper 03_VULNERABILITY_ANALYSIS_AVA_VAN_4.md: remove CONTAINED
    van_file = partial_pack / "03_VULNERABILITY_ANALYSIS_AVA_VAN_4.md"
    van_file.write_text(van_file.read_text(encoding="utf-8").replace("CONTAINED", "REMOVED"), encoding="utf-8")

    # 6. Tamper 05_INDEPENDENT_TEST_RUNNER_ATE_IND_2.py: remove execute permissions
    ind_runner = partial_pack / "05_INDEPENDENT_TEST_RUNNER_ATE_IND_2.py"
    ind_runner.chmod(0o644)

    runner = ITSEFCEMEvaluationRunner(pack_dir=partial_pack)
    report, telemetry = runner.run_evaluation_audit()

    assert report.work_units_conforming_count < 11
    assert report.compliance_score_bps < 10000

    unit_map = {u["work_unit_id"]: u["conforming"] for u in telemetry["evaluated_units"]}
    assert unit_map["ASE_TSS.1-1"] is False
    assert unit_map["ADV_FSP.4-1"] is False
    assert unit_map["ADV_FSP.4-2"] is False
    assert unit_map["ADV_TDS.3-1"] is False
    assert unit_map["ADV_TDS.3-2"] is False
    assert unit_map["ALC_FLR.2-1"] is False
    assert unit_map["ALC_FLR.2-2"] is False
    assert unit_map["ATE_COV.2-1"] is False
    assert unit_map["ATE_IND.2-1"] is False
    assert unit_map["AVA_VAN.4-1"] is False


def test_itsef_runner_missing_submission_pack(tmp_path: Path):
    """Evaluates FileNotFoundError when target submission pack has no manifest."""
    empty_dir = tmp_path / "empty_pack"
    empty_dir.mkdir()
    runner = ITSEFCEMEvaluationRunner(pack_dir=empty_dir)
    with pytest.raises(FileNotFoundError, match="ERR_SUBMISSION_MANIFEST_NOT_FOUND"):
        runner.run_evaluation_audit()


def test_itsef_runner_cli_workflow(tmp_path: Path):
    """Evaluates CLI execution and report verification round-trip."""
    out_file = tmp_path / "cli_etr.json"
    pack_dir = Path("dist/common_criteria_eal4_submission_pack")
    if not (pack_dir / "SUBMISSION_MANIFEST.json").exists():
        pack_dir = Path(__file__).resolve().parent.parent / "dist" / "common_criteria_eal4_submission_pack"

    res1 = subprocess.run(
        [
            sys.executable,
            "tools/itsef_cem_evaluation_runner.py",
            "--pack-dir",
            str(pack_dir),
            "--out",
            str(out_file),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ISO/IEC 18045 CEM ITSEF EVALUATION TECHNICAL REPORT (ETR)" in res1.stdout
    assert "=" * 80 in res1.stdout
    assert "-" * 80 in res1.stdout
    assert out_file.exists()

    res2 = subprocess.run(
        [
            sys.executable,
            "tools/itsef_cem_evaluation_runner.py",
            "--verify",
            str(out_file),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "[✓] ITSEF Evaluation Technical Report Verified" in res2.stdout
