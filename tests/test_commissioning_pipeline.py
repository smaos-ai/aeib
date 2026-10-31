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
tests/test_commissioning_pipeline.py
================================================================================
Comprehensive verification suite for the 7-Stage Commissioning Lifecycle Engine.
Tests sequential stage enforcement, disk-anchored evidence validation,
biometric & cryptographic authority, replay defense, and OpenTelemetry spans.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Dict, Tuple

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from src.commissioning_pipeline import (
    STAGE_ORDER,
    CommissioningHoldPointError,
    CommissioningPipeline,
    CommissioningStage,
    EvidenceTamperError,
    InvalidStageTransitionError,
    ReplayNonceError,
    SignOffType,
    StageHoldPointReceipt,
    UnauthorizedSignerError,
)
from src.jcs_canonicalizer import encode_jcs


def _generate_ed25519_keypair() -> Tuple[ed25519.Ed25519PrivateKey, str]:
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    return priv, pub_hex


def _generate_p256_keypair() -> Tuple[ec.EllipticCurvePrivateKey, str]:
    priv = ec.generate_private_key(ec.SECP256R1())
    pub_hex = priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    ).hex()
    return priv, pub_hex


def _sign_receipt_ed25519(
    priv: ed25519.Ed25519PrivateKey,
    receipt_kwargs: Dict,
) -> StageHoldPointReceipt:
    dummy = StageHoldPointReceipt(
        signature_der_or_hex="",
        **receipt_kwargs,
    )
    sig_hex = priv.sign(dummy.canonical_bytes()).hex()
    return StageHoldPointReceipt(
        signature_der_or_hex=sig_hex,
        **receipt_kwargs,
    )


def _sign_receipt_p256(
    priv: ec.EllipticCurvePrivateKey,
    receipt_kwargs: Dict,
) -> StageHoldPointReceipt:
    dummy = StageHoldPointReceipt(
        signature_der_or_hex="",
        **receipt_kwargs,
    )
    sig_der_hex = priv.sign(dummy.canonical_bytes(), ec.ECDSA(hashes.SHA256())).hex()
    return StageHoldPointReceipt(
        signature_der_or_hex=sig_der_hex,
        **receipt_kwargs,
    )


@pytest.fixture
def test_env(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    (repo_root / "docs").mkdir()
    (repo_root / "docs" / "DESIGN_BASIS.md").write_text("# Design Basis\nInvariants confirmed.\n")
    (repo_root / "docs" / "HAZOP_REPORT.md").write_text("# HAZOP Report\nAll 8 guide words evaluated.\n")
    (repo_root / "docs" / "COLD_COMMISSIONING_CERT.md").write_text("# Cold Commissioning\nBootstrap verified.\n")
    (repo_root / "docs" / "HOT_COMMISSIONING_REPORT.md").write_text("# Hot Commissioning\nStaging clean.\n")
    (repo_root / "docs" / "LOAD_TEST_REPORT.md").write_text("# Load Test Report\nMutation kill ratio 9333 bps.\n")
    (repo_root / "docs" / "RFS_CERTIFICATE.md").write_text("# Ready for Service\nSigned by operator.\n")

    verifier_priv, verifier_pub = _generate_ed25519_keypair()
    operator_priv, operator_pub = _generate_ed25519_keypair()
    enclave_priv, enclave_pub = _generate_p256_keypair()

    pipeline = CommissioningPipeline(
        pipeline_id="pipe-nuclear-7stage-001",
        repo_root=repo_root,
        pinned_verifier_pubkeys_hex=[verifier_pub],
        pinned_operator_pubkeys_hex=[operator_pub],
        pinned_enclave_x963_pubkeys_hex=[enclave_pub],
    )

    return {
        "repo_root": repo_root,
        "pipeline": pipeline,
        "verifier_priv": verifier_priv,
        "verifier_pub": verifier_pub,
        "operator_priv": operator_priv,
        "operator_pub": operator_pub,
        "enclave_priv": enclave_priv,
        "enclave_pub": enclave_pub,
    }


def test_sequential_commissioning_happy_path(test_env):
    """Verifies complete Stages 1 through 6 progression to Ready-for-Service."""
    pipeline = test_env["pipeline"]
    repo_root = test_env["repo_root"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]
    e_priv = test_env["enclave_priv"]
    e_pub = test_env["enclave_pub"]

    stage_files = {
        CommissioningStage.STAGE_1_DESIGN_BASIS: ["docs/DESIGN_BASIS.md"],
        CommissioningStage.STAGE_2_HAZOP: ["docs/HAZOP_REPORT.md"],
        CommissioningStage.STAGE_3_COLD_COMMISSIONING: ["docs/COLD_COMMISSIONING_CERT.md"],
        CommissioningStage.STAGE_4_HOT_COMMISSIONING: ["docs/HOT_COMMISSIONING_REPORT.md"],
        CommissioningStage.STAGE_5_LOAD_TESTING: ["docs/LOAD_TEST_REPORT.md"],
        CommissioningStage.STAGE_6_READY_FOR_SERVICE: ["docs/RFS_CERTIFICATE.md"],
    }

    # Execute stages 1 through 5 with automated verifier key
    for stage in [
        CommissioningStage.STAGE_1_DESIGN_BASIS,
        CommissioningStage.STAGE_2_HAZOP,
        CommissioningStage.STAGE_3_COLD_COMMISSIONING,
        CommissioningStage.STAGE_4_HOT_COMMISSIONING,
        CommissioningStage.STAGE_5_LOAD_TESTING,
    ]:
        idx = list(stage_files.keys()).index(stage) + 1
        ev_hashes, caid = pipeline.evaluate_stage_evidence(stage, stage_files[stage])
        receipt = _sign_receipt_ed25519(
            v_priv,
            {
                "stage": stage,
                "pipeline_id": pipeline.pipeline_id,
                "stage_index": idx,
                "evidence_files": ev_hashes,
                "evidence_manifest_caid": caid,
                "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
                "signer_public_key_hex": v_pub,
                "timestamp_utc": "2026-10-29T21:00:00Z",
                "nonce": f"nonce-stage-{idx}",
                "status": "PASSED",
                "metadata": {"test_metric_bps": 10000},
            },
        )
        assert len(receipt.canonical_bytes()) > 0
        assert receipt.compute_caid().startswith("sha256:")
        pipeline.verify_and_advance_stage(receipt)

    assert not pipeline.is_ready_for_service()
    assert pipeline.current_stage == CommissioningStage.STAGE_6_READY_FOR_SERVICE
    assert len(pipeline.completed_stages) == 5

    # Stage 6: Signed by operator FaceID biometric key
    st6 = CommissioningStage.STAGE_6_READY_FOR_SERVICE
    ev_hashes, caid = pipeline.evaluate_stage_evidence(st6, stage_files[st6])
    rfs_receipt = _sign_receipt_p256(
        e_priv,
        {
            "stage": st6,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 6,
            "evidence_files": ev_hashes,
            "evidence_manifest_caid": caid,
            "sign_off_type": SignOffType.OPERATOR_BIOMETRIC_FACEID,
            "signer_public_key_hex": e_pub,
            "timestamp_utc": "2026-10-29T21:05:00Z",
            "nonce": "nonce-stage-6-faceid",
            "status": "PASSED",
            "metadata": {"biometric_confidence_bps": 10000},
        },
    )
    pipeline.verify_and_advance_stage(rfs_receipt)

    assert pipeline.is_ready_for_service()
    assert pipeline.current_stage == CommissioningStage.STAGE_7_OPERATION
    assert len(pipeline.completed_stages) == 6

    cert = pipeline.generate_rfs_certificate()
    assert cert["status"] == "COMMISSIONED_READY_FOR_SERVICE"
    assert cert["commissioned_stages_count"] == 6
    assert cert["rfs_run_caid"].startswith("sha256:")
    assert len(pipeline.otel_spans) == 6


def test_pipeline_constructor_validations(tmp_path: Path):
    """Constructor rejects invalid pipeline IDs and missing directories."""
    with pytest.raises(ValueError, match="ERR_INVALID_PIPELINE_ID"):
        CommissioningPipeline("", tmp_path, [], [], [])
    with pytest.raises(ValueError, match="ERR_INVALID_PIPELINE_ID"):
        CommissioningPipeline(None, tmp_path, [], [], [])  # type: ignore

    missing_dir = tmp_path / "nonexistent"
    with pytest.raises(ValueError, match="ERR_REPO_ROOT_NOT_DIR"):
        CommissioningPipeline("pipe-1", missing_dir, [], [], [])


def test_evaluate_stage_evidence_edge_cases(test_env):
    """Validates missing files, empty files, and empty list in evidence evaluation."""
    pipeline = test_env["pipeline"]
    repo_root = test_env["repo_root"]

    with pytest.raises(ValueError, match="ERR_EMPTY_EVIDENCE_LIST"):
        pipeline.evaluate_stage_evidence(CommissioningStage.STAGE_1_DESIGN_BASIS, [])

    with pytest.raises(FileNotFoundError, match="ERR_EVIDENCE_FILE_NOT_FOUND"):
        pipeline.evaluate_stage_evidence(
            CommissioningStage.STAGE_1_DESIGN_BASIS, ["docs/NONEXISTENT.md"]
        )

    (repo_root / "docs" / "EMPTY.md").write_text("")
    with pytest.raises(ValueError, match="ERR_EVIDENCE_FILE_EMPTY"):
        pipeline.evaluate_stage_evidence(
            CommissioningStage.STAGE_1_DESIGN_BASIS, ["docs/EMPTY.md"]
        )


def test_out_of_order_transition_rejected(test_env):
    """Skipping a stage trips InvalidStageTransitionError immediately."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    ev_hashes, caid = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_2_HAZOP, ["docs/HAZOP_REPORT.md"]
    )
    # Attempting to jump directly to Stage 2 with wrong stage
    receipt = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_2_HAZOP,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 2,
            "evidence_files": ev_hashes,
            "evidence_manifest_caid": caid,
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:00:00Z",
            "nonce": "nonce-skip-to-2",
            "status": "PASSED",
            "metadata": {},
        },
    )
    with pytest.raises(InvalidStageTransitionError, match="ERR_INVALID_STAGE_TRANSITION"):
        pipeline.verify_and_advance_stage(receipt)

    # Attempting with correct stage STAGE_1 but wrong stage_index (e.g. 2 instead of 1)
    ev_hashes1, caid1 = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_1_DESIGN_BASIS, ["docs/DESIGN_BASIS.md"]
    )
    receipt_bad_idx = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_1_DESIGN_BASIS,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 2,  # Should be 1!
            "evidence_files": ev_hashes1,
            "evidence_manifest_caid": caid1,
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:00:00Z",
            "nonce": "nonce-bad-idx",
            "status": "PASSED",
            "metadata": {},
        },
    )
    with pytest.raises(InvalidStageTransitionError, match="ERR_INVALID_STAGE_TRANSITION"):
        pipeline.verify_and_advance_stage(receipt_bad_idx)


def test_pipeline_id_mismatch_rejected(test_env):
    """Receipt with different pipeline_id trips CommissioningHoldPointError."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    ev_hashes, caid = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_1_DESIGN_BASIS, ["docs/DESIGN_BASIS.md"]
    )
    receipt = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_1_DESIGN_BASIS,
            "pipeline_id": "other-foreign-pipeline",
            "stage_index": 1,
            "evidence_files": ev_hashes,
            "evidence_manifest_caid": caid,
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:00:00Z",
            "nonce": "nonce-foreign-pipe",
            "status": "PASSED",
            "metadata": {},
        },
    )
    with pytest.raises(CommissioningHoldPointError, match="ERR_PIPELINE_ID_MISMATCH"):
        pipeline.verify_and_advance_stage(receipt)


def test_status_not_passed_rejected(test_env):
    """Receipt with status != PASSED trips CommissioningHoldPointError."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    ev_hashes, caid = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_1_DESIGN_BASIS, ["docs/DESIGN_BASIS.md"]
    )
    receipt = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_1_DESIGN_BASIS,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 1,
            "evidence_files": ev_hashes,
            "evidence_manifest_caid": caid,
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:00:00Z",
            "nonce": "nonce-failed-status",
            "status": "FAILED",
            "metadata": {},
        },
    )
    with pytest.raises(CommissioningHoldPointError, match="ERR_HOLD_POINT_FAILED:FAILED"):
        pipeline.verify_and_advance_stage(receipt)


def test_empty_evidence_files_rejected(test_env):
    """Receipt with empty evidence files trips EvidenceTamperError."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    receipt = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_1_DESIGN_BASIS,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 1,
            "evidence_files": {},
            "evidence_manifest_caid": "sha256:dummy",
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:00:00Z",
            "nonce": "nonce-empty-ev",
            "status": "PASSED",
            "metadata": {},
        },
    )
    with pytest.raises(EvidenceTamperError, match="ERR_EMPTY_EVIDENCE_FILES"):
        pipeline.verify_and_advance_stage(receipt)


def test_evidence_tamper_rejected(test_env):
    """Modifying evidence on disk trips EvidenceTamperError."""
    pipeline = test_env["pipeline"]
    repo_root = test_env["repo_root"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    ev_hashes, caid = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_1_DESIGN_BASIS, ["docs/DESIGN_BASIS.md"]
    )
    receipt = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_1_DESIGN_BASIS,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 1,
            "evidence_files": ev_hashes,
            "evidence_manifest_caid": caid,
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:00:00Z",
            "nonce": "nonce-tamper-probe",
            "status": "PASSED",
            "metadata": {},
        },
    )

    (repo_root / "docs" / "DESIGN_BASIS.md").write_text("# Malicious Modification\n")

    with pytest.raises(EvidenceTamperError, match="ERR_EVIDENCE_HASH_MISMATCH_ON_DISK"):
        pipeline.verify_and_advance_stage(receipt)


def test_manifest_caid_mismatch_rejected(test_env):
    """Spoofed manifest CAID in receipt trips EvidenceTamperError."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    ev_hashes, _ = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_1_DESIGN_BASIS, ["docs/DESIGN_BASIS.md"]
    )
    receipt = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_1_DESIGN_BASIS,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 1,
            "evidence_files": ev_hashes,
            "evidence_manifest_caid": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:00:00Z",
            "nonce": "nonce-spoofed-caid",
            "status": "PASSED",
            "metadata": {},
        },
    )
    with pytest.raises(EvidenceTamperError, match="ERR_MANIFEST_CAID_MISMATCH"):
        pipeline.verify_and_advance_stage(receipt)


def test_invalid_ed25519_signature_rejected(test_env):
    """Bit-flipped Ed25519 signature trips UnauthorizedSignerError."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    ev_hashes, caid = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_1_DESIGN_BASIS, ["docs/DESIGN_BASIS.md"]
    )
    receipt = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_1_DESIGN_BASIS,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 1,
            "evidence_files": ev_hashes,
            "evidence_manifest_caid": caid,
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:00:00Z",
            "nonce": "nonce-bad-sig-ed25519",
            "status": "PASSED",
            "metadata": {},
        },
    )
    # Corrupt signature hex
    bad_sig = "ff" * 64
    corrupted_receipt = StageHoldPointReceipt(
        stage=receipt.stage,
        pipeline_id=receipt.pipeline_id,
        stage_index=receipt.stage_index,
        evidence_files=receipt.evidence_files,
        evidence_manifest_caid=receipt.evidence_manifest_caid,
        sign_off_type=receipt.sign_off_type,
        signer_public_key_hex=receipt.signer_public_key_hex,
        signature_der_or_hex=bad_sig,
        timestamp_utc=receipt.timestamp_utc,
        nonce=receipt.nonce,
        status=receipt.status,
        metadata=receipt.metadata,
    )
    with pytest.raises(UnauthorizedSignerError, match="ERR_INVALID_ED25519_SIGNATURE"):
        pipeline.verify_and_advance_stage(corrupted_receipt)


def test_invalid_p256_der_signature_rejected(test_env):
    """Bit-flipped P-256 DER signature trips UnauthorizedSignerError."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]
    e_priv = test_env["enclave_priv"]
    e_pub = test_env["enclave_pub"]

    # Advance stages 1 to 5
    stage_files = {
        CommissioningStage.STAGE_1_DESIGN_BASIS: ["docs/DESIGN_BASIS.md"],
        CommissioningStage.STAGE_2_HAZOP: ["docs/HAZOP_REPORT.md"],
        CommissioningStage.STAGE_3_COLD_COMMISSIONING: ["docs/COLD_COMMISSIONING_CERT.md"],
        CommissioningStage.STAGE_4_HOT_COMMISSIONING: ["docs/HOT_COMMISSIONING_REPORT.md"],
        CommissioningStage.STAGE_5_LOAD_TESTING: ["docs/LOAD_TEST_REPORT.md"],
    }
    for stage, files in stage_files.items():
        idx = list(stage_files.keys()).index(stage) + 1
        ev_hashes, caid = pipeline.evaluate_stage_evidence(stage, files)
        receipt = _sign_receipt_ed25519(
            v_priv,
            {
                "stage": stage,
                "pipeline_id": pipeline.pipeline_id,
                "stage_index": idx,
                "evidence_files": ev_hashes,
                "evidence_manifest_caid": caid,
                "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
                "signer_public_key_hex": v_pub,
                "timestamp_utc": "2026-10-29T21:00:00Z",
                "nonce": f"nonce-advance-{idx}",
                "status": "PASSED",
            },
        )
        pipeline.verify_and_advance_stage(receipt)

    st6 = CommissioningStage.STAGE_6_READY_FOR_SERVICE
    ev_hashes6, caid6 = pipeline.evaluate_stage_evidence(st6, ["docs/RFS_CERTIFICATE.md"])
    rfs_receipt = _sign_receipt_p256(
        e_priv,
        {
            "stage": st6,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 6,
            "evidence_files": ev_hashes6,
            "evidence_manifest_caid": caid6,
            "sign_off_type": SignOffType.OPERATOR_BIOMETRIC_FACEID,
            "signer_public_key_hex": e_pub,
            "timestamp_utc": "2026-10-29T21:05:00Z",
            "nonce": "nonce-bad-sig-p256",
            "status": "PASSED",
        },
    )
    # Corrupt DER signature
    corrupt_der = "3006020100020100"  # Dummy invalid DER
    corrupted_p256 = StageHoldPointReceipt(
        stage=rfs_receipt.stage,
        pipeline_id=rfs_receipt.pipeline_id,
        stage_index=rfs_receipt.stage_index,
        evidence_files=rfs_receipt.evidence_files,
        evidence_manifest_caid=rfs_receipt.evidence_manifest_caid,
        sign_off_type=rfs_receipt.sign_off_type,
        signer_public_key_hex=rfs_receipt.signer_public_key_hex,
        signature_der_or_hex=corrupt_der,
        timestamp_utc=rfs_receipt.timestamp_utc,
        nonce=rfs_receipt.nonce,
        status=rfs_receipt.status,
    )
    with pytest.raises(UnauthorizedSignerError, match="ERR_INVALID_P256_DER_SIGNATURE"):
        pipeline.verify_and_advance_stage(corrupted_p256)


def test_operator_offline_ed25519_for_stage_6(test_env):
    """Stage 6 succeeds when signed by pinned operator offline Ed25519 key."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]
    op_priv = test_env["operator_priv"]
    op_pub = test_env["operator_pub"]

    stage_files = {
        CommissioningStage.STAGE_1_DESIGN_BASIS: ["docs/DESIGN_BASIS.md"],
        CommissioningStage.STAGE_2_HAZOP: ["docs/HAZOP_REPORT.md"],
        CommissioningStage.STAGE_3_COLD_COMMISSIONING: ["docs/COLD_COMMISSIONING_CERT.md"],
        CommissioningStage.STAGE_4_HOT_COMMISSIONING: ["docs/HOT_COMMISSIONING_REPORT.md"],
        CommissioningStage.STAGE_5_LOAD_TESTING: ["docs/LOAD_TEST_REPORT.md"],
    }
    for stage, files in stage_files.items():
        idx = list(stage_files.keys()).index(stage) + 1
        ev_hashes, caid = pipeline.evaluate_stage_evidence(stage, files)
        receipt = _sign_receipt_ed25519(
            v_priv,
            {
                "stage": stage,
                "pipeline_id": pipeline.pipeline_id,
                "stage_index": idx,
                "evidence_files": ev_hashes,
                "evidence_manifest_caid": caid,
                "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
                "signer_public_key_hex": v_pub,
                "timestamp_utc": "2026-10-29T21:00:00Z",
                "nonce": f"nonce-offline-op-{idx}",
                "status": "PASSED",
            },
        )
        pipeline.verify_and_advance_stage(receipt)

    st6 = CommissioningStage.STAGE_6_READY_FOR_SERVICE
    ev_hashes6, caid6 = pipeline.evaluate_stage_evidence(st6, ["docs/RFS_CERTIFICATE.md"])
    rfs_op_receipt = _sign_receipt_ed25519(
        op_priv,
        {
            "stage": st6,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 6,
            "evidence_files": ev_hashes6,
            "evidence_manifest_caid": caid6,
            "sign_off_type": SignOffType.OPERATOR_OFFLINE_ED25519,
            "signer_public_key_hex": op_pub,
            "timestamp_utc": "2026-10-29T21:05:00Z",
            "nonce": "nonce-stage-6-op-ed25519",
            "status": "PASSED",
        },
    )
    pipeline.verify_and_advance_stage(rfs_op_receipt)
    assert pipeline.is_ready_for_service()


def test_premature_rfs_certificate_generation_rejected(test_env):
    """Calling generate_rfs_certificate before clearing Stage 6 raises error."""
    pipeline = test_env["pipeline"]
    with pytest.raises(CommissioningHoldPointError, match="ERR_PIPELINE_NOT_READY_FOR_SERVICE"):
        pipeline.generate_rfs_certificate()


def test_nonce_replay_rejected(test_env):
    """Replaying the same nonce trips ReplayNonceError."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    ev_hashes, caid = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_1_DESIGN_BASIS, ["docs/DESIGN_BASIS.md"]
    )
    receipt = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_1_DESIGN_BASIS,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 1,
            "evidence_files": ev_hashes,
            "evidence_manifest_caid": caid,
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:00:00Z",
            "nonce": "nonce-duplicate-test",
            "status": "PASSED",
            "metadata": {},
        },
    )
    pipeline.verify_and_advance_stage(receipt)

    ev_hashes2, caid2 = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_2_HAZOP, ["docs/HAZOP_REPORT.md"]
    )
    receipt2 = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_2_HAZOP,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 2,
            "evidence_files": ev_hashes2,
            "evidence_manifest_caid": caid2,
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:01:00Z",
            "nonce": "nonce-duplicate-test",  # replayed!
            "status": "PASSED",
            "metadata": {},
        },
    )
    with pytest.raises(ReplayNonceError, match="ERR_REPLAY_NONCE_DETECTED"):
        pipeline.verify_and_advance_stage(receipt2)


def test_stage_6_automated_verifier_rejected(test_env):
    """Stage 6 (RFS) strictly requires operator signature, rejecting automated verifiers."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    stage_files = {
        CommissioningStage.STAGE_1_DESIGN_BASIS: ["docs/DESIGN_BASIS.md"],
        CommissioningStage.STAGE_2_HAZOP: ["docs/HAZOP_REPORT.md"],
        CommissioningStage.STAGE_3_COLD_COMMISSIONING: ["docs/COLD_COMMISSIONING_CERT.md"],
        CommissioningStage.STAGE_4_HOT_COMMISSIONING: ["docs/HOT_COMMISSIONING_REPORT.md"],
        CommissioningStage.STAGE_5_LOAD_TESTING: ["docs/LOAD_TEST_REPORT.md"],
    }

    for stage, files in stage_files.items():
        idx = list(stage_files.keys()).index(stage) + 1
        ev_hashes, caid = pipeline.evaluate_stage_evidence(stage, files)
        receipt = _sign_receipt_ed25519(
            v_priv,
            {
                "stage": stage,
                "pipeline_id": pipeline.pipeline_id,
                "stage_index": idx,
                "evidence_files": ev_hashes,
                "evidence_manifest_caid": caid,
                "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
                "signer_public_key_hex": v_pub,
                "timestamp_utc": "2026-10-29T21:00:00Z",
                "nonce": f"nonce-st-{idx}",
                "status": "PASSED",
            },
        )
        pipeline.verify_and_advance_stage(receipt)

    ev_hashes6, caid6 = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_6_READY_FOR_SERVICE, ["docs/RFS_CERTIFICATE.md"]
    )
    rfs_auto = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_6_READY_FOR_SERVICE,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 6,
            "evidence_files": ev_hashes6,
            "evidence_manifest_caid": caid6,
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:06:00Z",
            "nonce": "nonce-auto-rfs-illegal",
            "status": "PASSED",
        },
    )
    with pytest.raises(UnauthorizedSignerError, match="ERR_STAGE_6_RFS_REQUIRES_OPERATOR_SIGN_OFF"):
        pipeline.verify_and_advance_stage(rfs_auto)


def test_unpinned_operator_key_rejected(test_env):
    """An unpinned operator key signing Stage 6 trips UnauthorizedSignerError."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    stage_files = {
        CommissioningStage.STAGE_1_DESIGN_BASIS: ["docs/DESIGN_BASIS.md"],
        CommissioningStage.STAGE_2_HAZOP: ["docs/HAZOP_REPORT.md"],
        CommissioningStage.STAGE_3_COLD_COMMISSIONING: ["docs/COLD_COMMISSIONING_CERT.md"],
        CommissioningStage.STAGE_4_HOT_COMMISSIONING: ["docs/HOT_COMMISSIONING_REPORT.md"],
        CommissioningStage.STAGE_5_LOAD_TESTING: ["docs/LOAD_TEST_REPORT.md"],
    }
    for stage, files in stage_files.items():
        idx = list(stage_files.keys()).index(stage) + 1
        ev_hashes, caid = pipeline.evaluate_stage_evidence(stage, files)
        receipt = _sign_receipt_ed25519(
            v_priv,
            {
                "stage": stage,
                "pipeline_id": pipeline.pipeline_id,
                "stage_index": idx,
                "evidence_files": ev_hashes,
                "evidence_manifest_caid": caid,
                "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
                "signer_public_key_hex": v_pub,
                "timestamp_utc": "2026-10-29T21:00:00Z",
                "nonce": f"nonce-prep-{idx}",
                "status": "PASSED",
            },
        )
        pipeline.verify_and_advance_stage(receipt)

    attacker_priv, attacker_pub = _generate_ed25519_keypair()
    ev_hashes6, caid6 = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_6_READY_FOR_SERVICE, ["docs/RFS_CERTIFICATE.md"]
    )
    rfs_unpinned = _sign_receipt_ed25519(
        attacker_priv,
        {
            "stage": CommissioningStage.STAGE_6_READY_FOR_SERVICE,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 6,
            "evidence_files": ev_hashes6,
            "evidence_manifest_caid": caid6,
            "sign_off_type": SignOffType.OPERATOR_OFFLINE_ED25519,
            "signer_public_key_hex": attacker_pub,
            "timestamp_utc": "2026-10-29T21:06:00Z",
            "nonce": "nonce-attacker-rfs",
            "status": "PASSED",
        },
    )
    with pytest.raises(UnauthorizedSignerError, match="ERR_UNPINNED_OPERATOR_KEY"):
        pipeline.verify_and_advance_stage(rfs_unpinned)


def test_otel_spans_serialization(test_env):
    """Verifies OpenTelemetry spans serialize cleanly with no floats."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    ev_hashes, caid = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_1_DESIGN_BASIS, ["docs/DESIGN_BASIS.md"]
    )
    receipt = _sign_receipt_ed25519(
        v_priv,
        {
            "stage": CommissioningStage.STAGE_1_DESIGN_BASIS,
            "pipeline_id": pipeline.pipeline_id,
            "stage_index": 1,
            "evidence_files": ev_hashes,
            "evidence_manifest_caid": caid,
            "sign_off_type": SignOffType.AUTOMATED_VERIFIER,
            "signer_public_key_hex": v_pub,
            "timestamp_utc": "2026-10-29T21:00:00Z",
            "nonce": "nonce-otel-check",
            "status": "PASSED",
            "metadata": {},
        },
    )
    pipeline.verify_and_advance_stage(receipt)

    assert len(pipeline.otel_spans) == 1
    span_dict = pipeline.otel_spans[0].to_dict()
    assert span_dict["name"] == "aeib.commissioning.hold_point_evaluation"
    assert span_dict["attributes"]["gen_ai.system"] == "sovereign_nexus_aeib"
    assert span_dict["attributes"]["aeib.commissioning.stage"] == "STAGE_1_DESIGN_BASIS"

    # Test span with non-empty parent_span_id preserves parent_span_id
    from src.commissioning_pipeline import CommissioningOTELSpan
    span_with_parent = CommissioningOTELSpan(
        name="test.span",
        trace_id="0123456789abcdef0123456789abcdef",
        span_id="0123456789abcdef",
        parent_span_id="parent-span-999",
        start_time_unix_nano=1000,
        end_time_unix_nano=2000,
        status_code="OK",
        status_description="Success",
        attributes={"key": 1},
    )
    assert span_with_parent.to_dict()["parent_span_id"] == "parent-span-999"

    # Test receipt frozen immutability and payload
    payload = receipt.to_canonical_signable_payload()
    assert isinstance(payload, dict)
    assert payload["stage"] == "STAGE_1_DESIGN_BASIS"
    assert receipt.canonical_bytes() != encode_jcs(None)
    with pytest.raises(Exception):
        receipt.status = "MUTATED"  # type: ignore

    def _assert_no_float(val):
        assert not isinstance(val, float), f"Found float: {val}"
        if isinstance(val, dict):
            for v in val.values():
                _assert_no_float(v)
        elif isinstance(val, list):
            for v in val:
                _assert_no_float(v)

    _assert_no_float(span_dict)


def test_unknown_sign_off_type_rejected(test_env):
    """Receipt with unknown sign_off_type trips UnauthorizedSignerError."""
    pipeline = test_env["pipeline"]
    v_priv = test_env["verifier_priv"]
    v_pub = test_env["verifier_pub"]

    ev_hashes, caid = pipeline.evaluate_stage_evidence(
        CommissioningStage.STAGE_1_DESIGN_BASIS, ["docs/DESIGN_BASIS.md"]
    )
    dummy_receipt = StageHoldPointReceipt(
        stage=CommissioningStage.STAGE_1_DESIGN_BASIS,
        pipeline_id=pipeline.pipeline_id,
        stage_index=1,
        evidence_files=ev_hashes,
        evidence_manifest_caid=caid,
        sign_off_type="UNKNOWN_ARBITRARY_TYPE",  # type: ignore
        signer_public_key_hex=v_pub,
        signature_der_or_hex="00",
        timestamp_utc="2026-10-29T21:00:00Z",
        nonce="nonce-unknown-type",
        status="PASSED",
    )
    with pytest.raises(UnauthorizedSignerError, match="ERR_UNKNOWN_SIGN_OFF_TYPE"):
        pipeline.verify_and_advance_stage(dummy_receipt)

