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
tests/test_ready_for_service_e2e.py
================================================================================
End-to-End Acceptance Suite for Ready-for-Service Commissioning Orchestrator.
Tests automated stages 1 through 5, offline operator Ed25519 signing,
biometric Secure Enclave P-256 signing, certificate export, and CLI interface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from src.commissioning_pipeline import (
    CommissioningStage,
    SignOffType,
    StageHoldPointReceipt,
)
from tools.ready_for_service import ReadyForServiceRunner, main


@pytest.fixture
def rfs_env(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Create directories and files matching DEFAULT_STAGE_EVIDENCE
    (repo_root / "docs").mkdir()
    (repo_root / "compliance").mkdir()
    (repo_root / "tests").mkdir()
    (repo_root / "benchmarks" / "aeib_execution_integrity").mkdir(parents=True)
    (repo_root / "src").mkdir()

    (repo_root / "docs" / "INHERITANCE_BLUEPRINT.md").write_text("# Blueprint\nInvariants.\n")
    (repo_root / "docs" / "IDEMPOTENCY_CONTRACT.md").write_text("# Idempotency\nContract.\n")
    (repo_root / "docs" / "THREAT_MODEL.md").write_text("# Threat Model\nVectors.\n")
    (repo_root / "docs" / "LIMITATIONS.md").write_text("# Limitations\nBounds.\n")
    (repo_root / "compliance" / "check_zone_boundary.py").write_text("# Zone Boundary\n")
    (repo_root / "compliance" / "ast_purity.py").write_text("# AST Purity\n")
    (repo_root / "compliance" / "no_mock_enforcer.py").write_text("# No Mock\n")
    (repo_root / "tests" / "test_ansi_50bf_breaker_failure.py").write_text("# 50BF\n")
    (repo_root / "tests" / "test_saga_compensation.py").write_text("# Saga\n")
    (repo_root / "benchmarks" / "aeib_execution_integrity" / "run_episodes.py").write_text("# 500 Ep\n")
    (repo_root / "tests" / "test_falsifiability_matrix.py").write_text("# Falsify\n")
    (repo_root / "src" / "industrial_dev_flow_engine.py").write_text("# Governor\n")
    (repo_root / "src" / "commissioning_pipeline.py").write_text("# Pipeline\n")

    v_priv = ed25519.Ed25519PrivateKey.generate()
    v_priv_hex = v_priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()

    op_priv = ed25519.Ed25519PrivateKey.generate()
    op_priv_hex = op_priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()
    op_pub_hex = op_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()

    enclave_priv = ec.generate_private_key(ec.SECP256R1())
    enclave_pub_hex = enclave_priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    ).hex()

    return {
        "repo_root": repo_root,
        "v_priv_hex": v_priv_hex,
        "op_priv_hex": op_priv_hex,
        "op_pub_hex": op_pub_hex,
        "enclave_priv": enclave_priv,
        "enclave_pub_hex": enclave_pub_hex,
    }


def test_rfs_offline_e2e(rfs_env):
    """Full end-to-end commissioning run in OFFLINE mode."""
    out_cert = rfs_env["repo_root"] / "docs" / "RFS_CERTIFICATE.json"
    runner = ReadyForServiceRunner(
        repo_root=rfs_env["repo_root"],
        pipeline_id="pipe-e2e-offline-001",
        verifier_privkey_hex=rfs_env["v_priv_hex"],
        operator_pubkey_hex=rfs_env["op_pub_hex"],
        operator_privkey_hex=rfs_env["op_priv_hex"],
    )

    # First test direct stage execution
    receipts_1_5 = runner.run_automated_stages_1_to_5()
    assert len(receipts_1_5) == 5
    st6_offline = runner.run_stage_6_offline()
    assert isinstance(st6_offline, StageHoldPointReceipt)
    assert len(st6_offline.nonce) == 24
    assert st6_offline.metadata["operator_sign_off_mode"] == "OFFLINE_ED25519"
    assert runner.pipeline.is_ready_for_service()

    # Now test complete execution via execute_and_export_certificate with fresh runner
    runner2 = ReadyForServiceRunner(
        repo_root=rfs_env["repo_root"],
        pipeline_id="pipe-e2e-offline-002",
        verifier_privkey_hex=rfs_env["v_priv_hex"],
        operator_pubkey_hex=rfs_env["op_pub_hex"],
        operator_privkey_hex=rfs_env["op_priv_hex"],
    )
    cert = runner2.execute_and_export_certificate(mode="OFFLINE", out_path=out_cert)
    assert cert["status"] == "COMMISSIONED_READY_FOR_SERVICE"
    assert cert["commissioned_stages_count"] == 6
    assert out_cert.is_file()

    loaded = json.loads(out_cert.read_text())
    assert loaded["pipeline_id"] == "pipe-e2e-offline-002"
    assert loaded["status"] == "COMMISSIONED_READY_FOR_SERVICE"


def test_rfs_biometric_e2e(rfs_env):
    """Full end-to-end commissioning run in BIOMETRIC FaceID mode."""
    runner = ReadyForServiceRunner(
        repo_root=rfs_env["repo_root"],
        pipeline_id="pipe-e2e-biometric-002",
        verifier_privkey_hex=rfs_env["v_priv_hex"],
        operator_pubkey_hex=rfs_env["op_pub_hex"],
        enclave_x963_pubkey_hex=rfs_env["enclave_pub_hex"],
    )

    receipts = runner.run_automated_stages_1_to_5()
    assert len(receipts) == 5
    for r in receipts:
        assert isinstance(r, StageHoldPointReceipt)
        assert r.metadata["automated_verification_passed"] is True
        assert len(r.nonce) == 24

    assert runner.pipeline.current_stage == CommissioningStage.STAGE_6_READY_FOR_SERVICE

    files = runner.stage_evidence_map[CommissioningStage.STAGE_6_READY_FOR_SERVICE]
    ev_hashes, caid = runner.pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_6_READY_FOR_SERVICE, files
    )
    nonce = "nonce-bio-test-e2e-123456"
    timestamp_utc = "2026-10-29T21:10:00Z"

    dummy_st6 = StageHoldPointReceipt(
        stage=CommissioningStage.STAGE_6_READY_FOR_SERVICE,
        pipeline_id="pipe-e2e-biometric-002",
        stage_index=6,
        evidence_files=ev_hashes,
        evidence_manifest_caid=caid,
        sign_off_type=SignOffType.OPERATOR_BIOMETRIC_FACEID,
        signer_public_key_hex=rfs_env["enclave_pub_hex"],
        signature_der_or_hex="",
        timestamp_utc=timestamp_utc,
        nonce=nonce,
        status="PASSED",
        metadata={"operator_sign_off_mode": "SECURE_ENCLAVE_FACEID"},
    )
    sig_der_hex = rfs_env["enclave_priv"].sign(
        dummy_st6.canonical_bytes(), ec.ECDSA(hashes.SHA256())
    ).hex()

    st6_receipt = runner.run_stage_6_biometric(
        enclave_p256_der_signature_hex=sig_der_hex,
        timestamp_utc=timestamp_utc,
        nonce=nonce,
    )
    assert isinstance(st6_receipt, StageHoldPointReceipt)
    assert st6_receipt.status == "PASSED"
    assert st6_receipt.metadata["operator_sign_off_mode"] == "SECURE_ENCLAVE_FACEID"
    assert runner.pipeline.is_ready_for_service()

    cert = runner.pipeline.generate_rfs_certificate()
    assert cert["status"] == "COMMISSIONED_READY_FOR_SERVICE"
    assert cert["commissioned_stages_count"] == 6

    # Also test execute_and_export_certificate with mode="BIOMETRIC" on fresh runner
    out_bio_cert = rfs_env["repo_root"] / "docs" / "RFS_BIO_CERT.json"
    runner_bio = ReadyForServiceRunner(
        repo_root=rfs_env["repo_root"],
        pipeline_id="pipe-e2e-bio-export",
        verifier_privkey_hex=rfs_env["v_priv_hex"],
        operator_pubkey_hex=rfs_env["op_pub_hex"],
        enclave_x963_pubkey_hex=rfs_env["enclave_pub_hex"],
    )
    # Pre-sign dummy stage 6
    nonce_bio2 = "nonce-bio-export-999"
    ev_hashes_bio, caid_bio = runner_bio.pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_6_READY_FOR_SERVICE, files
    )
    dummy_bio2 = StageHoldPointReceipt(
        stage=CommissioningStage.STAGE_6_READY_FOR_SERVICE,
        pipeline_id="pipe-e2e-bio-export",
        stage_index=6,
        evidence_files=ev_hashes_bio,
        evidence_manifest_caid=caid_bio,
        sign_off_type=SignOffType.OPERATOR_BIOMETRIC_FACEID,
        signer_public_key_hex=rfs_env["enclave_pub_hex"],
        signature_der_or_hex="",
        timestamp_utc="2026-10-29T21:12:00Z",
        nonce=nonce_bio2,
        status="PASSED",
        metadata={"operator_sign_off_mode": "SECURE_ENCLAVE_FACEID"},
    )
    sig_der_hex2 = rfs_env["enclave_priv"].sign(
        dummy_bio2.canonical_bytes(), ec.ECDSA(hashes.SHA256())
    ).hex()
    cert_bio = runner_bio.execute_and_export_certificate(
        mode="BIOMETRIC",
        out_path=out_bio_cert,
        biometric_signature_hex=sig_der_hex2,
        biometric_nonce=nonce_bio2,
        biometric_timestamp_utc="2026-10-29T21:12:00Z",
    )
    assert cert_bio["status"] == "COMMISSIONED_READY_FOR_SERVICE"
    assert out_bio_cert.is_file()


def test_rfs_offline_without_operator_privkey_raises(rfs_env):
    """Calling run_stage_6_offline without operator_privkey raises ValueError."""
    runner = ReadyForServiceRunner(
        repo_root=rfs_env["repo_root"],
        pipeline_id="pipe-e2e-no-op-priv",
        verifier_privkey_hex=rfs_env["v_priv_hex"],
        operator_pubkey_hex=rfs_env["op_pub_hex"],
        operator_privkey_hex=None,
    )
    runner.run_automated_stages_1_to_5()
    with pytest.raises(ValueError, match="ERR_OPERATOR_PRIVATE_KEY_REQUIRED_FOR_OFFLINE_RFS"):
        runner.run_stage_6_offline()


def test_rfs_biometric_without_enclave_pubkey_raises(rfs_env):
    """Calling run_stage_6_biometric without enclave key raises ValueError."""
    runner = ReadyForServiceRunner(
        repo_root=rfs_env["repo_root"],
        pipeline_id="pipe-e2e-no-enclave",
        verifier_privkey_hex=rfs_env["v_priv_hex"],
        operator_pubkey_hex=rfs_env["op_pub_hex"],
        enclave_x963_pubkey_hex=None,
    )
    runner.run_automated_stages_1_to_5()
    with pytest.raises(ValueError, match="ERR_ENCLAVE_PUBLIC_KEY_REQUIRED_FOR_BIOMETRIC_RFS"):
        runner.run_stage_6_biometric("dummy_sig", "2026-10-29T21:00:00Z", "nonce-1")


def test_execute_and_export_certificate_biometric_missing_args(rfs_env):
    """BIOMETRIC mode in execute_and_export_certificate requires signature and nonce."""
    runner = ReadyForServiceRunner(
        repo_root=rfs_env["repo_root"],
        pipeline_id="pipe-e2e-missing-sig",
        verifier_privkey_hex=rfs_env["v_priv_hex"],
        operator_pubkey_hex=rfs_env["op_pub_hex"],
        enclave_x963_pubkey_hex=rfs_env["enclave_pub_hex"],
    )
    with pytest.raises(ValueError, match="ERR_BIOMETRIC_SIGNATURE_AND_NONCE_REQUIRED"):
        runner.execute_and_export_certificate(mode="BIOMETRIC", biometric_signature_hex=None)
    with pytest.raises(ValueError, match="ERR_BIOMETRIC_SIGNATURE_AND_NONCE_REQUIRED"):
        runner.execute_and_export_certificate(
            mode="BIOMETRIC", biometric_signature_hex="sig", biometric_nonce=None
        )


def test_execute_and_export_certificate_unsupported_mode(rfs_env):
    """Unsupported mode trips ValueError."""
    runner = ReadyForServiceRunner(
        repo_root=rfs_env["repo_root"],
        pipeline_id="pipe-e2e-unsupported",
        verifier_privkey_hex=rfs_env["v_priv_hex"],
        operator_pubkey_hex=rfs_env["op_pub_hex"],
    )
    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_RFS_MODE:INVALID_MODE"):
        runner.execute_and_export_certificate(mode="INVALID_MODE")


def test_rfs_cli_main_with_env_keys(rfs_env, monkeypatch):
    """Tests the CLI main() function execution with environment variables."""
    out_cert = rfs_env["repo_root"] / "docs" / "CLI_RFS_CERT.json"

    monkeypatch.setenv("AEIB_VERIFIER_PRIVKEY_HEX", rfs_env["v_priv_hex"])
    monkeypatch.setenv("AEIB_OPERATOR_PRIVKEY_HEX", rfs_env["op_priv_hex"])

    exit_code = main(
        [
            "--repo-root",
            str(rfs_env["repo_root"]),
            "--pipeline-id",
            "pipe-cli-test-001",
            "--mode",
            "OFFLINE",
            "--out",
            str(out_cert),
            "--json",
        ]
    )
    assert exit_code == 0
    assert out_cert.is_file()
    data = json.loads(out_cert.read_text())
    assert data["pipeline_id"] == "pipe-cli-test-001"
    assert data["status"] == "COMMISSIONED_READY_FOR_SERVICE"


def test_rfs_cli_main_without_env_ephemeral_keys(rfs_env, monkeypatch):
    """Tests CLI execution when no env vars are set (generates ephemeral keys)."""
    monkeypatch.delenv("AEIB_VERIFIER_PRIVKEY_HEX", raising=False)
    monkeypatch.delenv("AEIB_OPERATOR_PRIVKEY_HEX", raising=False)

    out_cert = rfs_env["repo_root"] / "docs" / "CLI_EPHEMERAL_CERT.json"
    exit_code = main(
        [
            "--repo-root",
            str(rfs_env["repo_root"]),
            "--pipeline-id",
            "pipe-cli-ephemeral-002",
            "--mode",
            "OFFLINE",
            "--out",
            str(out_cert),
        ]
    )
    assert exit_code == 0
    assert out_cert.is_file()
