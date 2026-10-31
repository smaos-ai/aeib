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
tests/test_common_criteria_eal4_runner.py
================================================================================
Verification suite for CommonCriteriaEAL4Runner and evidence dossier integrity.
Evaluated under the stated model with unmocked cryptographic verification.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

from tools.common_criteria_eal4_runner import (
    CommonCriteriaEAL4Dossier,
    CommonCriteriaEAL4Runner,
    CommonCriteriaSFRMapping,
    main,
    sha256_jcs_caid,
)


@pytest.fixture
def runner() -> CommonCriteriaEAL4Runner:
    return CommonCriteriaEAL4Runner()


def test_common_criteria_runner_nominal(runner: CommonCriteriaEAL4Runner):
    """Evaluates nominal Common Criteria EAL4+ audit execution."""
    dossier, telemetry = runner.run_evaluation()

    assert isinstance(dossier, CommonCriteriaEAL4Dossier)
    assert dossier.status == "INTERNAL PREVIEW COMMISSIONED"
    assert dossier.assurance_level == "EAL4+ (ALC_FLR.2 + AVA_VAN.4)"
    assert dossier.evaluation_target == "SovereignNexus AEIB v1.1"
    assert dossier.sfrs_mapped_count == 8
    assert dossier.test_suites_verified_count >= 200
    assert dossier.vulnerability_vectors_contained == 5
    assert dossier.formal_states_checked > 0
    assert dossier.dossier_caid.startswith("sha256:")
    assert dossier.created_epoch_ms > 0

    assert "sfr_evaluations" in telemetry
    assert len(telemetry["sfr_evaluations"]) == 8
    for sfr in telemetry["sfr_evaluations"]:
        assert sfr["exists"] is True
        assert sfr["verified"] is True


def test_common_criteria_dossier_serialization_and_caid(runner: CommonCriteriaEAL4Runner):
    """Verifies RFC 8785 JCS serialization and zero-float invariant."""
    dossier, _ = runner.run_evaluation()
    dossier_dict = dossier.to_dict()

    for k, v in dossier_dict.items():
        assert not isinstance(v, float), f"Float forbidden in field: {k}"

    payload = {k: v for k, v in dossier_dict.items() if k != "dossier_caid"}
    expected_caid = sha256_jcs_caid(payload)
    assert dossier.dossier_caid == expected_caid


def test_common_criteria_file_verification_and_tamper_detection(
    runner: CommonCriteriaEAL4Runner,
    tmp_path: Path,
):
    """Evaluates dossier persistence, verification, and tamper rejection."""
    dossier, _ = runner.run_evaluation()
    dossier_file = tmp_path / "test_cc_dossier.json"
    dossier_file.write_text(json.dumps(dossier.to_dict(), indent=2), encoding="utf-8")

    # 1. Nominal verification
    assert CommonCriteriaEAL4Runner.verify_dossier_file(dossier_file) is True

    # 2. Tampered field rejection
    data = json.loads(dossier_file.read_text(encoding="utf-8"))
    data["formal_states_checked"] = 99999
    tampered_file = tmp_path / "tampered_cc_dossier.json"
    tampered_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert CommonCriteriaEAL4Runner.verify_dossier_file(tampered_file) is False

    # 3. Tampered status rejection
    data_status = json.loads(dossier_file.read_text(encoding="utf-8"))
    data_status["status"] = "PRODUCTION_CERTIFIED"
    status_tampered = tmp_path / "status_tampered_cc_dossier.json"
    status_tampered.write_text(json.dumps(data_status, indent=2), encoding="utf-8")
    assert CommonCriteriaEAL4Runner.verify_dossier_file(status_tampered) is False


def test_common_criteria_missing_or_corrupt_file(tmp_path: Path):
    """Evaluates robust handling of missing or corrupted dossier files."""
    missing_path = tmp_path / "nonexistent.json"
    assert CommonCriteriaEAL4Runner.verify_dossier_file(missing_path) is False

    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text("{not valid json...", encoding="utf-8")
    assert CommonCriteriaEAL4Runner.verify_dossier_file(corrupt_path) is False


def test_common_criteria_missing_sfr_module_raises(tmp_path: Path):
    """Evaluates fail-closed behavior when an SFR implementation module is missing."""
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    (empty_repo / "tests").mkdir()

    runner = CommonCriteriaEAL4Runner(repo_root=empty_repo)
    with pytest.raises(FileNotFoundError, match="ERR_SFR_MODULE_MISSING"):
        runner.run_evaluation()


def test_common_criteria_dataclasses_frozen():
    """Verifies that SFR mappings and Dossier dataclasses are immutable."""
    mapping = CommonCriteriaSFRMapping("FCS_TEST", "Test Comp", "src/test.py", True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        mapping.verified = False  # type: ignore

    dossier = CommonCriteriaEAL4Dossier(
        dossier_version="1.0.0",
        dossier_caid="sha256:abcd",
        evaluation_target="target",
        assurance_level="EAL4+",
        sfrs_mapped_count=1,
        test_suites_verified_count=1,
        vulnerability_vectors_contained=1,
        formal_states_checked=1,
        status="TEST",
        created_epoch_ms=1000,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        dossier.status = "MUTATED"  # type: ignore


def test_sha256_jcs_caid_bytes_and_dict():
    """Verifies sha256_jcs_caid handles both bytes and dict objects deterministically."""
    b_caid = sha256_jcs_caid(b"canonical_bytes")
    assert b_caid.startswith("sha256:")

    d_caid = sha256_jcs_caid({"key": "val"})
    assert d_caid.startswith("sha256:")
    assert d_caid != b_caid


def test_verify_dossier_file_edge_cases(tmp_path: Path):
    """Verifies edge cases for verify_dossier_file."""
    p_no_caid = tmp_path / "no_caid.json"
    p_no_caid.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    assert CommonCriteriaEAL4Runner.verify_dossier_file(p_no_caid) is False

    p_empty_caid = tmp_path / "empty_caid.json"
    p_empty_caid.write_text(json.dumps({"dossier_caid": ""}), encoding="utf-8")
    assert CommonCriteriaEAL4Runner.verify_dossier_file(p_empty_caid) is False

    p_none_caid = tmp_path / "none_caid.json"
    p_none_caid.write_text(json.dumps({"dossier_caid": None}), encoding="utf-8")
    assert CommonCriteriaEAL4Runner.verify_dossier_file(p_none_caid) is False

    p_int_caid = tmp_path / "int_caid.json"
    p_int_caid.write_text(json.dumps({"dossier_caid": 12345}), encoding="utf-8")
    assert CommonCriteriaEAL4Runner.verify_dossier_file(p_int_caid) is False

    p_wrong_prefix = tmp_path / "wrong_prefix.json"
    p_wrong_prefix.write_text(json.dumps({"dossier_caid": "md5:12345"}), encoding="utf-8")
    assert CommonCriteriaEAL4Runner.verify_dossier_file(p_wrong_prefix) is False

    p_list_data = tmp_path / "list_data.json"
    p_list_data.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert CommonCriteriaEAL4Runner.verify_dossier_file(p_list_data) is False


def test_common_criteria_unverified_sfr_mapping(monkeypatch):
    """Verifies that an unverified SFR mapping results in verified=False."""
    fake_sfrs = (
        CommonCriteriaSFRMapping("FCS_TEST", "Test Comp", "src/jcs_canonicalizer.py", False),
    )
    monkeypatch.setattr(CommonCriteriaEAL4Runner, "MAPPED_SFRS", fake_sfrs)
    runner = CommonCriteriaEAL4Runner()
    dossier, telemetry = runner.run_evaluation()
    assert telemetry["sfr_evaluations"][0]["exists"] is True
    assert telemetry["sfr_evaluations"][0]["verified"] is False


def test_common_criteria_epoch_ms_exact(monkeypatch):
    """Verifies exact millisecond conversion of epoch time."""
    import time
    fake_epoch = 1700000000.123
    monkeypatch.setattr(time, "time", lambda: fake_epoch)
    runner = CommonCriteriaEAL4Runner()
    dossier, _ = runner.run_evaluation()
    assert dossier.created_epoch_ms == 1700000000123  # claim: config


def test_common_criteria_cli_main_out(tmp_path: Path, monkeypatch, capsys):
    """Verifies CLI execution with --out writes dossier and displays summary table."""
    out_dir = tmp_path / "level1" / "level2"
    out_file = out_dir / "output_dossier.json"
    monkeypatch.setattr(sys, "argv", ["common_criteria_eal4_runner.py", "--out", str(out_file)])
    
    # Run once to create
    main()
    captured = capsys.readouterr()
    assert "COMMON CRITERIA (ISO/IEC 15408) EAL4+ AUDIT DOSSIER" in captured.out
    assert "Dossier Exported To:" in captured.out
    lines = captured.out.strip().splitlines()
    assert lines[0] == "=" * 80  # claim: config
    assert lines[3] == "=" * 80  # claim: config
    assert lines[-4] == "-" * 80  # claim: config
    assert lines[-1] == "=" * 80  # claim: config
    assert out_file.exists()
    assert '\n  "assurance_level":' in out_file.read_text(encoding="utf-8")
    assert CommonCriteriaEAL4Runner.verify_dossier_file(out_file) is True

    # Run second time to verify mkdir exist_ok=True
    main()
    captured_second = capsys.readouterr()
    lines_second = captured_second.out.strip().splitlines()
    assert lines_second[0] == "=" * 80  # claim: config
    assert lines_second[3] == "=" * 80  # claim: config
    assert lines_second[-4] == "-" * 80  # claim: config
    assert lines_second[-1] == "=" * 80  # claim: config


def test_common_criteria_cli_main_verify_success(tmp_path: Path, monkeypatch, capsys):
    """Verifies CLI execution with --verify succeeds on authentic dossier."""
    out_file = tmp_path / "output_dossier.json"
    runner = CommonCriteriaEAL4Runner()
    dossier, _ = runner.run_evaluation()
    out_file.write_text(json.dumps(dossier.to_dict(), indent=2), encoding="utf-8")

    exit_codes = []
    monkeypatch.setattr(sys, "exit", lambda code: exit_codes.append(code))
    monkeypatch.setattr(sys, "argv", ["common_criteria_eal4_runner.py", "--verify", str(out_file)])

    main()

    captured = capsys.readouterr()
    assert "[✓] Common Criteria EAL4+ Dossier Verified" in captured.out
    assert exit_codes == [0]


def test_common_criteria_cli_main_verify_failure(tmp_path: Path, monkeypatch, capsys):
    """Verifies CLI execution with --verify fails closed on corrupt/missing dossier."""
    tampered_file = tmp_path / "bad_dossier.json"
    tampered_file.write_text(json.dumps({"dossier_caid": "sha256:deadbeef"}), encoding="utf-8")

    exit_codes = []
    monkeypatch.setattr(sys, "exit", lambda code: exit_codes.append(code))
    monkeypatch.setattr(sys, "argv", ["common_criteria_eal4_runner.py", "--verify", str(tampered_file)])

    main()

    captured = capsys.readouterr()
    assert "[✗] Dossier Verification Failed" in captured.err
    assert exit_codes == [1]

