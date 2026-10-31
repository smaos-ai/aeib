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
tests/test_itsef_mock_lab_audit_simulator.py
================================================================================
Verification Suite for ItsefMockLabAuditSimulator and ItsefLabVerdict.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. Nominal full simulation execution: validates submission pack, runs ATE_IND.2,
   evaluates 11 CEM units, and performs 3-of-5 HSM quorum sign-off.
2. Output file generation, RFC 8785 canonical sealing, and CAID persistence.
3. Offline dossier verification: validates valid dossier and rejects tampered files.
4. Independent evaluator test harness execution verification.
5. Submission pack integrity verification and missing file handling.
6. Dataclass immutability and exhaustive parameter validation.
7. CLI interface execution (--verify and nominal run).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict

import pytest

from tools.itsef_mock_lab_audit_simulator import (
    DEFAULT_PACK_DIR,
    STATUS_INTERNAL_PREVIEW,
    TARGET_EAL,
    TARGET_TOE,
    VERDICT_CONFORMANCE_VERIFIED,
    ItsefLabVerdict,
    ItsefMockLabAuditSimulator,
    sha256_jcs_caid,
)


@pytest.fixture
def temp_output(tmp_path: Path) -> Path:
    return tmp_path / "itsef_verdict_test.json"


@pytest.fixture
def simulator(temp_output: Path) -> ItsefMockLabAuditSimulator:
    return ItsefMockLabAuditSimulator(
        pack_dir=DEFAULT_PACK_DIR,
        output_file=temp_output,
        lab_identifier="TEST-ITSEF-LAB-01",
    )


def test_01_nominal_simulation_execution(simulator: ItsefMockLabAuditSimulator, temp_output: Path) -> None:
    """Verifies complete end-to-end ITSEF lab evaluation simulation."""
    verdict, dossier = simulator.run_simulation(cluster_epoch_id=1, current_time_ms=1793414000000)

    assert isinstance(verdict, ItsefLabVerdict)
    assert verdict.lab_identifier == "TEST-ITSEF-LAB-01"
    assert verdict.evaluation_target == TARGET_TOE
    assert verdict.assurance_level == TARGET_EAL
    assert verdict.status == STATUS_INTERNAL_PREVIEW
    assert verdict.ate_ind_test_verdict == "PASS_VERIFIED"
    assert verdict.cem_work_units_passed == 11
    assert verdict.cem_work_units_total == 11
    assert verdict.cem_compliance_score_bps == 10000
    assert verdict.hsm_quorum_status == "QUORUM_ESTABLISHED"
    assert verdict.overall_evaluation_verdict == VERDICT_CONFORMANCE_VERIFIED
    assert verdict.created_epoch_ms == 1793414000000
    assert verdict.verdict_caid.startswith("sha256:")

    # Output file checks
    assert temp_output.exists()
    assert dossier["dossier_caid"] == verdict.verdict_caid
    assert dossier["verdict"]["verdict_id"] == verdict.verdict_id


def test_02_dossier_verification_and_tampering_detection(simulator: ItsefMockLabAuditSimulator, temp_output: Path) -> None:
    """Verifies that valid verdicts verify cleanly, and tampered files fail closed."""
    simulator.run_simulation(cluster_epoch_id=1, current_time_ms=1793414000000)
    assert simulator.verify_verdict_file(temp_output) is True

    # 1. Non-existent file
    assert simulator.verify_verdict_file(temp_output.parent / "nonexistent.json") is False

    # 2. Tampered score
    raw_data = json.loads(temp_output.read_text("utf-8"))
    tampered_data = dict(raw_data)
    tampered_verdict = dict(tampered_data["verdict"])
    tampered_verdict["cem_compliance_score_bps"] = 9999
    tampered_data["verdict"] = tampered_verdict

    tampered_file = temp_output.parent / "tampered_verdict.json"
    tampered_file.write_text(json.dumps(tampered_data), "utf-8")
    assert simulator.verify_verdict_file(tampered_file) is False

    # 3. Tampered status
    tampered_verdict2 = dict(raw_data["verdict"])
    tampered_verdict2["status"] = "PRODUCTION_CERTIFIED"
    tampered_data2 = dict(raw_data, verdict=tampered_verdict2)
    tampered_file2 = temp_output.parent / "tampered_verdict2.json"
    tampered_file2.write_text(json.dumps(tampered_data2), "utf-8")
    assert simulator.verify_verdict_file(tampered_file2) is False

    # 4. Tampered CAID
    tampered_data3 = dict(raw_data)
    tampered_data3["dossier_caid"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    tampered_file3 = temp_output.parent / "tampered_verdict3.json"
    tampered_file3.write_text(json.dumps(tampered_data3), "utf-8")
    assert simulator.verify_verdict_file(tampered_file3) is False


def test_03_independent_evaluator_harness_execution(simulator: ItsefMockLabAuditSimulator) -> None:
    """Verifies that the standalone evaluator harness runs and produces expected output."""
    res = simulator.execute_independent_evaluator_harness()
    assert res["verdict"] == "PASS_VERIFIED"
    assert res["returncode"] == 0
    assert "CONFORMANCE_EVALUATION_COMPLETE" in res["stdout_summary"]

    # Test missing runner
    bad_sim = ItsefMockLabAuditSimulator(pack_dir=Path("/tmp/nonexistent_pack_dir"))
    with pytest.raises(FileNotFoundError, match="ERR_ATE_IND_RUNNER_MISSING"):
        bad_sim.execute_independent_evaluator_harness()


def test_04_submission_pack_integrity_verification(simulator: ItsefMockLabAuditSimulator) -> None:
    """Verifies submission pack Merkle tree and file SHA-256 checks."""
    integrity = simulator.verify_submission_pack_integrity()
    assert integrity["valid"] is True
    assert integrity["documents_count"] >= 6
    assert integrity["submission_merkle_root"].startswith("sha256:")
    assert integrity["manifest_caid"].startswith("sha256:")

    # Missing manifest
    bad_sim = ItsefMockLabAuditSimulator(pack_dir=Path("/tmp/nonexistent_pack_dir"))
    with pytest.raises(FileNotFoundError, match="ERR_MANIFEST_NOT_FOUND"):
        bad_sim.verify_submission_pack_integrity()


def test_05_itsef_lab_verdict_validations() -> None:
    """Verifies dataclass immutability and parameter bounds on ItsefLabVerdict."""
    valid_args: Dict[str, Any] = {
        "verdict_id": "v1",
        "lab_identifier": "LAB-01",
        "evaluation_target": TARGET_TOE,
        "assurance_level": TARGET_EAL,
        "status": STATUS_INTERNAL_PREVIEW,
        "submission_manifest_caid": "sha256:" + "0" * 64,
        "submission_merkle_root": "sha256:" + "0" * 64,
        "ate_ind_test_verdict": "PASS_VERIFIED",
        "cem_work_units_passed": 11,
        "cem_work_units_total": 11,
        "cem_compliance_score_bps": 10000,
        "hsm_quorum_status": "QUORUM_ESTABLISHED",
        "hsm_quorum_receipt_caid": "sha256:" + "0" * 64,
        "overall_evaluation_verdict": VERDICT_CONFORMANCE_VERIFIED,
        "created_epoch_ms": 1793414000000,
        "verdict_caid": "sha256:" + "0" * 64,
    }

    verdict = ItsefLabVerdict(**valid_args)
    assert verdict.verdict_id == "v1"

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.status = "MUTATED"  # type: ignore

    # Validation errors
    with pytest.raises(ValueError, match="ERR_INVALID_VERDICT_ID"):
        ItsefLabVerdict(**dict(valid_args, verdict_id=""))
    with pytest.raises(ValueError, match="ERR_INVALID_LAB_IDENTIFIER"):
        ItsefLabVerdict(**dict(valid_args, lab_identifier=""))
    with pytest.raises(ValueError, match="ERR_INVALID_TOE"):
        ItsefLabVerdict(**dict(valid_args, evaluation_target="OTHER_TARGET"))
    with pytest.raises(ValueError, match="ERR_INVALID_ASSURANCE_LEVEL"):
        ItsefLabVerdict(**dict(valid_args, assurance_level="EAL7"))
    with pytest.raises(ValueError, match="ERR_INVALID_STATUS"):
        ItsefLabVerdict(**dict(valid_args, status="CERTIFIED"))
    with pytest.raises(ValueError, match="ERR_INVALID_MANIFEST_CAID"):
        ItsefLabVerdict(**dict(valid_args, submission_manifest_caid="not_sha256"))
    with pytest.raises(ValueError, match="ERR_INVALID_MERKLE_ROOT"):
        ItsefLabVerdict(**dict(valid_args, submission_merkle_root="not_sha256"))
    with pytest.raises(ValueError, match="ERR_INVALID_ATE_IND_VERDICT"):
        ItsefLabVerdict(**dict(valid_args, ate_ind_test_verdict="FAIL"))
    with pytest.raises(ValueError, match="ERR_INVALID_WORK_UNITS_PASSED"):
        ItsefLabVerdict(**dict(valid_args, cem_work_units_passed=-1))
    with pytest.raises(ValueError, match="ERR_INVALID_WORK_UNITS_TOTAL"):
        ItsefLabVerdict(**dict(valid_args, cem_work_units_total=0))
    with pytest.raises(ValueError, match="ERR_INVALID_COMPLIANCE_SCORE_BPS"):
        ItsefLabVerdict(**dict(valid_args, cem_compliance_score_bps=-1))
    with pytest.raises(ValueError, match="ERR_INVALID_QUORUM_STATUS"):
        ItsefLabVerdict(**dict(valid_args, hsm_quorum_status="QUORUM_FAILED"))
    with pytest.raises(ValueError, match="ERR_INVALID_QUORUM_RECEIPT_CAID"):
        ItsefLabVerdict(**dict(valid_args, hsm_quorum_receipt_caid="bad_caid"))
    with pytest.raises(ValueError, match="ERR_INVALID_OVERALL_VERDICT"):
        ItsefLabVerdict(**dict(valid_args, overall_evaluation_verdict="REJECTED"))
    with pytest.raises(ValueError, match="ERR_INVALID_CREATED_EPOCH_MS"):
        ItsefLabVerdict(**dict(valid_args, created_epoch_ms=0))
    with pytest.raises(ValueError, match="ERR_INVALID_VERDICT_CAID"):
        ItsefLabVerdict(**dict(valid_args, verdict_caid="bad_caid"))


def test_06_cli_execution_nominal_and_verify(tmp_path: Path) -> None:
    """Verifies running the CLI tool directly via subprocess in nominal and verify modes."""
    output_json = tmp_path / "cli_verdict.json"
    tool_path = Path(__file__).resolve().parent.parent / "tools" / "itsef_mock_lab_audit_simulator.py"

    # Nominal run
    res = subprocess.run(
        [sys.executable, str(tool_path), "--output", str(output_json)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "ACCREDITED_CONFORMANCE_VERIFIED" in res.stdout
    assert output_json.exists()

    # Verify run
    res_verify = subprocess.run(
        [sys.executable, str(tool_path), "--output", str(output_json), "--verify"],
        capture_output=True,
        text=True,
    )
    assert res_verify.returncode == 0
    assert "ITSEF Evaluation Lab Verdict Integrity Verified" in res_verify.stdout


def test_07_main_function_direct_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies direct python execution of main() testing all exit codes."""
    from tools.itsef_mock_lab_audit_simulator import main

    output_json = tmp_path / "main_verdict.json"
    nonexistent_json = tmp_path / "nonexistent_verdict.json"

    # Nominal main() returns 0
    monkeypatch.setattr(sys, "argv", ["prog", "--output", str(output_json)])
    ret_nominal = main()
    assert ret_nominal == 0
    assert output_json.exists()

    # Verify existing file returns 0
    monkeypatch.setattr(sys, "argv", ["prog", "--output", str(output_json), "--verify"])
    ret_verify_ok = main()
    assert ret_verify_ok == 0

    # Verify non-existent file returns 1
    monkeypatch.setattr(sys, "argv", ["prog", "--output", str(nonexistent_json), "--verify"])
    ret_verify_fail = main()
    assert ret_verify_fail == 1


def test_08_verify_verdict_file_edge_cases(tmp_path: Path, simulator: ItsefMockLabAuditSimulator) -> None:
    """Verifies all failure branches in verify_verdict_file."""
    bad_syntax_file = tmp_path / "bad_syntax.json"
    bad_syntax_file.write_text("{not valid json", "utf-8")
    assert simulator.verify_verdict_file(bad_syntax_file) is False

    not_dict_verdict_file = tmp_path / "not_dict.json"
    not_dict_verdict_file.write_text(json.dumps({"verdict": "string_not_dict"}), "utf-8")
    assert simulator.verify_verdict_file(not_dict_verdict_file) is False

    # CAID mismatch in dossier
    valid_verdict, dossier = simulator.run_simulation(cluster_epoch_id=1, current_time_ms=1793414000000)
    dossier_mismatch = dict(dossier, dossier_caid="sha256:1111111111111111111111111111111111111111111111111111111111111111")
    dossier_mismatch_file = tmp_path / "caid_mismatch.json"
    dossier_mismatch_file.write_text(json.dumps(dossier_mismatch), "utf-8")
    assert simulator.verify_verdict_file(dossier_mismatch_file) is False

    # Overall evaluation verdict mismatch
    dossier_verdict_mismatch = json.loads(json.dumps(dossier))
    dossier_verdict_mismatch["verdict"]["overall_evaluation_verdict"] = "REJECTED"
    # recalculate verdict_caid to test value check
    unsealed = dict(dossier_verdict_mismatch["verdict"])
    unsealed.pop("verdict_caid", None)
    new_caid = sha256_jcs_caid(unsealed)
    dossier_verdict_mismatch["verdict"]["verdict_caid"] = new_caid
    dossier_verdict_mismatch["dossier_caid"] = new_caid
    file_bad_verdict = tmp_path / "bad_verdict_value.json"
    file_bad_verdict.write_text(json.dumps(dossier_verdict_mismatch), "utf-8")
    assert simulator.verify_verdict_file(file_bad_verdict) is False

    # HSM Quorum status not established
    dossier_hsm_mismatch = json.loads(json.dumps(dossier))
    dossier_hsm_mismatch["verdict"]["hsm_quorum_status"] = "QUORUM_FAILED"
    unsealed2 = dict(dossier_hsm_mismatch["verdict"])
    unsealed2.pop("verdict_caid", None)
    new_caid2 = sha256_jcs_caid(unsealed2)
    dossier_hsm_mismatch["verdict"]["verdict_caid"] = new_caid2
    dossier_hsm_mismatch["dossier_caid"] = new_caid2
    file_bad_hsm = tmp_path / "bad_hsm_value.json"
    file_bad_hsm.write_text(json.dumps(dossier_hsm_mismatch), "utf-8")
    assert simulator.verify_verdict_file(file_bad_hsm) is False


def test_09_submission_pack_verification_failures(tmp_path: Path) -> None:
    """Verifies error handling when submission pack files or hashes are corrupted."""
    pack_dir = tmp_path / "corrupt_pack"
    pack_dir.mkdir(parents=True)

    # 1. Fewer than 6 documents
    bad_manifest = {
        "documents": {
            "00_SECURITY_TARGET_EAL4_PLUS.md": {"sha256": "sha256:1234", "words": 100}
        },
        "submission_merkle_root": "sha256:0000",
        "manifest_caid": "sha256:0000",
    }
    (pack_dir / "SUBMISSION_MANIFEST.json").write_text(json.dumps(bad_manifest), "utf-8")
    sim = ItsefMockLabAuditSimulator(pack_dir=pack_dir)
    with pytest.raises(ValueError, match="ERR_INSUFFICIENT_DOCUMENTS"):
        sim.verify_submission_pack_integrity()

    # 2. Document file missing
    manifest_6 = {
        "documents": {f"doc_{i}.md": {"sha256": "sha256:0000"} for i in range(6)},
        "submission_merkle_root": "sha256:0000",
        "manifest_caid": "sha256:0000",
    }
    (pack_dir / "SUBMISSION_MANIFEST.json").write_text(json.dumps(manifest_6), "utf-8")
    with pytest.raises(FileNotFoundError, match="ERR_DOCUMENT_FILE_MISSING"):
        sim.verify_submission_pack_integrity()

    # 3. Document digest mismatch
    for i in range(6):
        (pack_dir / f"doc_{i}.md").write_text(f"content {i}", "utf-8")
    with pytest.raises(ValueError, match="ERR_FILE_DIGEST_MISMATCH"):
        sim.verify_submission_pack_integrity()


def test_10_simulation_nested_output_directory(tmp_path: Path) -> None:
    """Verifies run_simulation automatically creates deeply nested output directories."""
    nested_output = tmp_path / "deep" / "nested" / "dir" / "itsef_verdict.json"
    sim = ItsefMockLabAuditSimulator(pack_dir=DEFAULT_PACK_DIR, output_file=nested_output)
    verdict, dossier = sim.run_simulation()
    assert nested_output.exists()
    assert verdict.created_epoch_ms > 0

