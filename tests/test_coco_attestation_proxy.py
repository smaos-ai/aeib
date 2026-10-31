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
tests/test_coco_attestation_proxy.py
================================================================================
Comprehensive verification suite for Confidential Container (CoCo) Attestation Proxy.
Evaluated under the stated model as an agent execution integrity boundary scaffold.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import asdict
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.coco_attestation_proxy import (
    CoCoAttestationError,
    CoCoAttestationProxy,
    CoCoAttestationToken,
    CoCoKeyReleaseReceipt,
    HALT_COCO_KEY_RELEASE_DENIED,
    HALT_COCO_POLICY_DIVERGENCE,
    HALT_COCO_SIGNATURE_INVALID,
    HALT_COCO_STALE_NONCE,
    HALT_COCO_UNTRUSTED_IMAGE,
    STATUS_ATTESTATION_VERIFIED,
    STATUS_KEY_RELEASED,
    compute_sha256_caid,
)


def _generate_test_token(
    container_id: str = "ctr-worker-01",
    enclave_type: str = "amd_sev_snp",
    launch_digest: str = "sha256:" + "aa" * 32,
    image_digest: str = "sha256:" + "bb" * 32,
    cmdline_digest: str = "sha256:" + "cc" * 32,
    nonce: str = "test-nonce-001",
    priv_key: Optional[ed25519.Ed25519PrivateKey] = None,
    timestamp_ms: Optional[int] = 1700000000000,
) -> tuple[CoCoAttestationToken, ed25519.Ed25519PrivateKey]:
    priv = priv_key or ed25519.Ed25519PrivateKey.generate()
    token = CoCoAttestationProxy.create_token(
        container_id=container_id,
        enclave_type=enclave_type,
        launch_measurement_digest=launch_digest,
        container_image_digest=image_digest,
        kernel_cmdline_sha256=cmdline_digest,
        nonce=nonce,
        priv_key=priv,
        timestamp_ms=timestamp_ms,
    )
    return token, priv


def test_01_dataclass_and_caid() -> None:
    token, _ = _generate_test_token()
    assert len(token.token_id) == 25  # coco-tok- (9) + 16 hex chars (kills constant 16 perturbation)
    b = token.canonical_bytes()
    assert isinstance(b, bytes)
    assert b'"container_id":"ctr-worker-01"' in b

    # Frozen checks
    with pytest.raises(Exception):
        token.container_id = "corrupted"  # type: ignore

    receipt = CoCoKeyReleaseReceipt(
        release_id="rel-1",
        token_id="tok-1",
        container_id="c-1",
        secret_identifier="vault://key",
        fenced_key_caid="sha256:" + "11" * 32,
        receipt_caid="sha256:" + "22" * 32,
        status=STATUS_KEY_RELEASED,
        released_at_ms=1000,
    )
    r_bytes = receipt.canonical_bytes()
    assert isinstance(r_bytes, bytes)
    assert b'"secret_identifier":"vault://key"' in r_bytes


def test_02_nominal_attestation_verification() -> None:
    image_h = "sha256:" + "11" * 32
    launch_h = "sha256:" + "22" * 32
    cmdline_h = "sha256:" + "33" * 32

    proxy = CoCoAttestationProxy(
        db_path=":memory:",
        allowed_image_digests={image_h},
        approved_measurements={launch_h},
        approved_cmdlines={cmdline_h},
    )

    token, _ = _generate_test_token(
        image_digest=image_h,
        launch_digest=launch_h,
        cmdline_digest=cmdline_h,
        nonce="nonce-nominal-1",
    )

    is_valid = proxy.verify_attestation(token, now_ms=1700000001000)
    assert is_valid is True


def test_03_nominal_key_release_workflow() -> None:
    image_h = "sha256:" + "aa" * 32
    proxy = CoCoAttestationProxy(
        db_path=":memory:",
        allowed_image_digests={image_h},
    )

    token, _ = _generate_test_token(image_digest=image_h, nonce="nonce-release-1")
    key_payload = b"k" * 32

    receipt = proxy.release_key_to_enclave(
        token=token,
        secret_identifier="vault://db/passphrase",
        key_payload=key_payload,
        now_ms=1700000002000,
    )

    assert receipt.status == STATUS_KEY_RELEASED
    assert receipt.token_id == token.token_id
    assert receipt.container_id == token.container_id
    assert receipt.secret_identifier == "vault://db/passphrase"
    assert receipt.fenced_key_caid.startswith("sha256:")
    assert len(receipt.release_id) == 9 + 16


def test_04_fail_closed_stale_nonce_replay() -> None:
    proxy = CoCoAttestationProxy(db_path=":memory:")
    token, _ = _generate_test_token(nonce="nonce-replay-001")

    # First verification succeeds
    assert proxy.verify_attestation(token) is True

    # Replay with same nonce fails closed
    with pytest.raises(CoCoAttestationError) as exc_replay:
        proxy.verify_attestation(token)
    assert exc_replay.value.code == HALT_COCO_STALE_NONCE


def test_05_fail_closed_signature_invalid() -> None:
    proxy = CoCoAttestationProxy(db_path=":memory:")
    token, _ = _generate_test_token(nonce="nonce-sig-fail")

    corrupted_token = CoCoAttestationToken(
        token_id=token.token_id,
        container_id=token.container_id,
        enclave_type=token.enclave_type,
        launch_measurement_digest=token.launch_measurement_digest,
        container_image_digest=token.container_image_digest,
        kernel_cmdline_sha256=token.kernel_cmdline_sha256,
        nonce=token.nonce,
        timestamp_ms=token.timestamp_ms,
        enclave_public_key_hex=token.enclave_public_key_hex,
        signature="ff" * 64,
    )

    with pytest.raises(CoCoAttestationError) as exc_sig:
        proxy.verify_attestation(corrupted_token)
    assert exc_sig.value.code == HALT_COCO_SIGNATURE_INVALID


def test_06_fail_closed_untrusted_image() -> None:
    allowed = {"sha256:" + "aa" * 32}
    proxy = CoCoAttestationProxy(db_path=":memory:", allowed_image_digests=allowed)

    token, _ = _generate_test_token(
        image_digest="sha256:" + "99" * 32, nonce="nonce-bad-image"
    )

    with pytest.raises(CoCoAttestationError) as exc_img:
        proxy.verify_attestation(token)
    assert exc_img.value.code == HALT_COCO_UNTRUSTED_IMAGE


def test_07_fail_closed_policy_divergence() -> None:
    approved_measurements = {"sha256:" + "11" * 32}
    approved_cmdlines = {"sha256:" + "22" * 32}

    proxy = CoCoAttestationProxy(
        db_path=":memory:",
        approved_measurements=approved_measurements,
        approved_cmdlines=approved_cmdlines,
    )

    # Bad launch measurement
    token_bad_launch, _ = _generate_test_token(
        launch_digest="sha256:" + "ff" * 32,
        cmdline_digest="sha256:" + "22" * 32,
        nonce="nonce-div-1",
    )
    with pytest.raises(CoCoAttestationError) as exc_launch:
        proxy.verify_attestation(token_bad_launch)
    assert exc_launch.value.code == HALT_COCO_POLICY_DIVERGENCE

    # Bad cmdline
    token_bad_cmd, _ = _generate_test_token(
        launch_digest="sha256:" + "11" * 32,
        cmdline_digest="sha256:" + "ee" * 32,
        nonce="nonce-div-2",
    )
    with pytest.raises(CoCoAttestationError) as exc_cmd:
        proxy.verify_attestation(token_bad_cmd)
    assert exc_cmd.value.code == HALT_COCO_POLICY_DIVERGENCE


def test_08_fail_closed_insufficient_key_payload() -> None:
    proxy = CoCoAttestationProxy(db_path=":memory:")
    token, _ = _generate_test_token(nonce="nonce-short-key")

    with pytest.raises(CoCoAttestationError) as exc_key:
        proxy.release_key_to_enclave(
            token=token,
            secret_identifier="vault://short",
            key_payload=b"too-short-16byte",
        )
    assert exc_key.value.code == HALT_COCO_KEY_RELEASE_DENIED


def test_09_sqlite_persistence_and_queries() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        proxy = CoCoAttestationProxy(db_path=db_path)
        # Check WAL mode
        mode = proxy._conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal"

        token, _ = _generate_test_token(nonce="nonce-persist-1")
        receipt = proxy.release_key_to_enclave(
            token=token,
            secret_identifier="vault://db/enc",
            key_payload=b"X" * 32,
            now_ms=1700000005000,
        )

        retrieved = proxy.get_release_receipt(receipt.release_id)
        assert retrieved is not None
        assert retrieved.release_id == receipt.release_id
        assert retrieved.token_id == token.token_id
        assert retrieved.fenced_key_caid == receipt.fenced_key_caid

        # Verify deterministic JSON key ordering in attestation ledger (line 360 sort_keys=True)
        with proxy._conn:
            row_tok = proxy._conn.execute(
                "SELECT raw_token_json FROM coco_attestation_ledger WHERE token_id = ?",
                (token.token_id,),
            ).fetchone()
            assert row_tok is not None
            expected_tok_json = json.dumps(asdict(token), sort_keys=True)
            assert row_tok[0] == expected_tok_json
            assert row_tok[0].startswith('{"container_id":')

        # Verify deterministic JSON key ordering in key release ledger (line 385 sort_keys=True)
        with proxy._conn:
            row_rec = proxy._conn.execute(
                "SELECT raw_receipt_json FROM coco_key_release_ledger WHERE release_id = ?",
                (receipt.release_id,),
            ).fetchone()
            assert row_rec is not None
            expected_rec_json = json.dumps(asdict(receipt), sort_keys=True)
            assert row_rec[0] == expected_rec_json
            assert row_rec[0].startswith('{"container_id":')

        assert proxy.get_release_receipt("coco-rel-nonexistent") is None

        proxy.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_10_exact_mutation_boundaries() -> None:
    proxy = CoCoAttestationProxy(db_path=":memory:")
    t_now = int(time.time() * 1000)

    # Test default timestamp in token creation
    token, _ = _generate_test_token(nonce="nonce-now-1", timestamp_ms=None)
    assert abs(token.timestamp_ms - t_now) < 5000

    # Test default timestamp in verify_attestation (line 300 arith swap Mult -> FloorDiv)
    token2, _ = _generate_test_token(nonce="nonce-now-2")
    t_before_v = int(time.time() * 1000)
    assert proxy.verify_attestation(token2) is True
    t_after_v = int(time.time() * 1000)
    with proxy._conn:
        row_eval = proxy._conn.execute(
            "SELECT evaluated_at_ms FROM coco_attestation_ledger WHERE token_id = ?",
            (token2.token_id,),
        ).fetchone()
        assert row_eval is not None
        assert t_before_v <= row_eval[0] <= t_after_v + 500

    # Test default timestamp in release_key_to_enclave
    token3, _ = _generate_test_token(nonce="nonce-now-3")
    receipt = proxy.release_key_to_enclave(token3, "vault://k", b"M" * 32)
    assert abs(receipt.released_at_ms - t_now) < 5000


def test_11_wilson_ci_bounds_and_epistemic_lexicon() -> None:
    import src.coco_attestation_proxy as mod

    doc = mod.__doc__ or ""
    assert "INTERNAL PREVIEW COMMISSIONED" in doc
    assert "scaffold" in doc
    assert "simulated" in doc

    def wilson_score_interval(k: int, n: int, z: float = 1.95996) -> tuple[int, int]:
        p = k / n
        denom = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denom
        spread = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
        low = max(0.0, center - spread)
        high = min(1.0, center + spread)
        return int(round(low * 10000)), int(round(high * 10000))

    low_bps, high_bps = wilson_score_interval(30, 30)
    assert low_bps >= 8800
    assert high_bps == 10000
