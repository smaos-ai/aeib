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
tests/test_cross_enterprise_federation_bridge.py
================================================================================
Verification Suite for CrossEnterpriseFederationBridge.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. FederationTrustPassport dataclass validations, boundaries, and frozen immutability.
2. FederationAdmissionVerdict dataclass validations, boundaries, and frozen immutability.
3. CAID generation across str, bytes, and dictionary payloads.
4. Bridge initialization with custom/default Ed25519 keys and enterprise ID validation.
5. Trust passport issuance with cryptographic signature and default timestamps.
6. Nominal cross-enterprise admission of valid signed trust passport.
7. Rejection on target enterprise mismatch.
8. Rejection on untrusted issuer or pinned public key mismatch.
9. Rejection on tampered payload, invalid signature, or non-Ed25519 public key.
10. Temporal validity: Rejection of future-dated and expired passports.
11. Epoch fencing: Rejection of stale or mismatched epoch IDs.
12. Anti-replay nonce defense across repeated submissions.
13. SQLite-WAL append-only persistence and ledger entry retrieval.
"""

from __future__ import annotations

import base64
import dataclasses
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from src.cross_enterprise_federation_bridge import (
    DEFAULT_MAX_CLOCK_SKEW_MS,
    DEFAULT_PASSPORT_TTL_MS,
    STATUS_ADMITTED,
    STATUS_REJECTED_EPOCH_STALE,
    STATUS_REJECTED_EXPIRED,
    STATUS_REJECTED_FUTURE_DATED,
    STATUS_REJECTED_REPLAY,
    STATUS_REJECTED_SIGNATURE,
    STATUS_REJECTED_UNTRUSTED_ISSUER,
    STATUS_REJECTED_WRONG_TARGET,
    CrossEnterpriseFederationBridge,
    FederationAdmissionVerdict,
    FederationTrustPassport,
    compute_sha256_caid,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    return str(tmp_path / "test_federation_bridge.db")


@pytest.fixture
def ec_pem() -> str:
    ec_key = ec.generate_private_key(ec.SECP256R1()).public_key()
    return ec_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def test_01_passport_validations() -> None:
    valid_args: Dict[str, Any] = {
        "passport_id": "pass-001",
        "origin_enterprise_id": "ent-alpha",
        "target_enterprise_id": "ent-beta",
        "epoch_id": "epoch-1",
        "scitt_super_root": "sha256:" + "a" * 64,
        "nonce": "nonce-001",
        "issued_at_ms": 1700000000000,
        "expires_at_ms": 1700003600000,
        "public_key_pem": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA\n-----END PUBLIC KEY-----",
        "signature_b64": "c2lnbmF0dXJl",
        "passport_caid": "sha256:" + "0" * 64,
    }

    passp = FederationTrustPassport(**valid_args)
    assert passp.passport_id == "pass-001"

    # Exact boundary checks
    passp_ts1 = FederationTrustPassport(**dict(valid_args, issued_at_ms=1, expires_at_ms=2))
    assert passp_ts1.issued_at_ms == 1
    assert passp_ts1.expires_at_ms == 2

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        passp.target_enterprise_id = "MUTATED"  # type: ignore

    # Invalid fields
    with pytest.raises(ValueError, match="passport_id must be a non-empty string"):
        FederationTrustPassport(**dict(valid_args, passport_id=""))
    with pytest.raises(ValueError, match="passport_id must be a non-empty string"):
        FederationTrustPassport(**dict(valid_args, passport_id=None))  # type: ignore
    with pytest.raises(ValueError, match="origin_enterprise_id must be a non-empty string"):
        FederationTrustPassport(**dict(valid_args, origin_enterprise_id=""))
    with pytest.raises(ValueError, match="target_enterprise_id must be a non-empty string"):
        FederationTrustPassport(**dict(valid_args, target_enterprise_id=""))
    with pytest.raises(ValueError, match="epoch_id must be a non-empty string"):
        FederationTrustPassport(**dict(valid_args, epoch_id=""))
    with pytest.raises(ValueError, match="scitt_super_root must be a valid sha256 prefix string"):
        FederationTrustPassport(**dict(valid_args, scitt_super_root="bad_root"))
    with pytest.raises(ValueError, match="nonce must be a non-empty string"):
        FederationTrustPassport(**dict(valid_args, nonce=""))
    with pytest.raises(ValueError, match="issued_at_ms must be a positive integer"):
        FederationTrustPassport(**dict(valid_args, issued_at_ms=0))
    with pytest.raises(ValueError, match="issued_at_ms must be a positive integer"):
        FederationTrustPassport(**dict(valid_args, issued_at_ms=-1))
    with pytest.raises(ValueError, match="issued_at_ms must be a positive integer"):
        FederationTrustPassport(**dict(valid_args, issued_at_ms=10.5))  # type: ignore
    with pytest.raises(ValueError, match="expires_at_ms must be greater than issued_at_ms"):
        FederationTrustPassport(**dict(valid_args, issued_at_ms=100, expires_at_ms=100))
    with pytest.raises(ValueError, match="expires_at_ms must be greater than issued_at_ms"):
        FederationTrustPassport(**dict(valid_args, issued_at_ms=100, expires_at_ms=90))
    with pytest.raises(ValueError, match="expires_at_ms must be greater than issued_at_ms"):
        FederationTrustPassport(**dict(valid_args, issued_at_ms=100, expires_at_ms=105.5))  # type: ignore
    with pytest.raises(ValueError, match="public_key_pem must be a non-empty string"):
        FederationTrustPassport(**dict(valid_args, public_key_pem=""))
    with pytest.raises(ValueError, match="signature_b64 must be a non-empty string"):
        FederationTrustPassport(**dict(valid_args, signature_b64=""))
    with pytest.raises(ValueError, match="passport_caid must be a valid sha256 prefix string"):
        FederationTrustPassport(**dict(valid_args, passport_caid="bad_caid"))


def test_02_verdict_validations() -> None:
    valid_args: Dict[str, Any] = {
        "admitted": True,
        "status": STATUS_ADMITTED,
        "reason": "OK",
        "verdict_caid": "sha256:" + "0" * 64,
        "verified_at_ms": 1700000000000,
    }

    verdict = FederationAdmissionVerdict(**valid_args)
    assert verdict.admitted is True

    # Exact boundary check
    verdict_ts1 = FederationAdmissionVerdict(**dict(valid_args, verified_at_ms=1))
    assert verdict_ts1.verified_at_ms == 1

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.admitted = False  # type: ignore

    # Invalid fields
    with pytest.raises(ValueError, match="admitted must be a boolean"):
        FederationAdmissionVerdict(**dict(valid_args, admitted="not_bool"))  # type: ignore
    with pytest.raises(ValueError, match="status must be a non-empty string"):
        FederationAdmissionVerdict(**dict(valid_args, status=""))
    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        FederationAdmissionVerdict(**dict(valid_args, reason=""))
    with pytest.raises(ValueError, match="verdict_caid must be a valid sha256 prefix string"):
        FederationAdmissionVerdict(**dict(valid_args, verdict_caid="bad_caid"))
    with pytest.raises(ValueError, match="verified_at_ms must be a positive integer"):
        FederationAdmissionVerdict(**dict(valid_args, verified_at_ms=0))
    with pytest.raises(ValueError, match="verified_at_ms must be a positive integer"):
        FederationAdmissionVerdict(**dict(valid_args, verified_at_ms=10.5))  # type: ignore


def test_03_caid_computation() -> None:
    c_bytes = compute_sha256_caid(b"sample_passport")
    c_str = compute_sha256_caid("sample_passport")
    c_dict = compute_sha256_caid({"status": "FEDERATION_OK"})

    assert c_bytes.startswith("sha256:")
    assert c_str.startswith("sha256:")
    assert c_dict.startswith("sha256:")
    assert c_bytes == c_str


def test_04_bridge_initialization() -> None:
    # Default initialization
    bridge = CrossEnterpriseFederationBridge("enterprise-alpha")
    assert bridge.enterprise_id == "enterprise-alpha"
    assert "BEGIN PUBLIC KEY" in bridge.public_key_pem
    bridge.close()

    # Custom key
    key = ed25519.Ed25519PrivateKey.generate()
    bridge_custom = CrossEnterpriseFederationBridge("enterprise-beta", private_key=key)
    assert bridge_custom.enterprise_id == "enterprise-beta"
    bridge_custom.close()

    # Invalid enterprise_id
    with pytest.raises(ValueError, match="enterprise_id must be a non-empty string"):
        CrossEnterpriseFederationBridge("")
    with pytest.raises(ValueError, match="enterprise_id must be a non-empty string"):
        CrossEnterpriseFederationBridge(None)  # type: ignore


def test_05_passport_issuance() -> None:
    bridge = CrossEnterpriseFederationBridge("enterprise-alpha")
    t_now = int(time.time() * 1000)

    # Valid issuance with explicit parameters
    passp = bridge.issue_trust_passport(
        target_enterprise_id="enterprise-beta",
        epoch_id="epoch-101",
        scitt_super_root="sha256:" + "f" * 64,
        ttl_ms=60000,
        now_ms=1700000001000,
    )
    assert passp.origin_enterprise_id == "enterprise-alpha"
    assert passp.target_enterprise_id == "enterprise-beta"
    assert passp.epoch_id == "epoch-101"
    assert passp.issued_at_ms == 1700000001000
    assert passp.expires_at_ms == 1700000061000
    assert passp.passport_caid.startswith("sha256:")

    # Boundary ttl_ms=1
    passp_ttl1 = bridge.issue_trust_passport(
        target_enterprise_id="enterprise-beta",
        epoch_id="epoch-101",
        scitt_super_root="sha256:" + "f" * 64,
        ttl_ms=1,
    )
    assert passp_ttl1.expires_at_ms == passp_ttl1.issued_at_ms + 1

    # Default parameters (no ttl_ms, no now_ms)
    assert DEFAULT_PASSPORT_TTL_MS == 3600000
    passp_default = bridge.issue_trust_passport(
        target_enterprise_id="enterprise-beta",
        epoch_id="epoch-101",
        scitt_super_root="sha256:" + "f" * 64,
    )
    assert passp_default.issued_at_ms >= t_now
    assert passp_default.issued_at_ms <= int(time.time() * 1000) + 5000
    assert passp_default.issued_at_ms > 1_000_000_000_000
    assert passp_default.expires_at_ms - passp_default.issued_at_ms == 3600000
    assert passp_default.expires_at_ms == passp_default.issued_at_ms + DEFAULT_PASSPORT_TTL_MS

    # Invalid arguments
    with pytest.raises(ValueError, match="target_enterprise_id must be a non-empty string"):
        bridge.issue_trust_passport("", "epoch-1", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="epoch_id must be a non-empty string"):
        bridge.issue_trust_passport("ent-beta", "", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="ERR_ISSUE_INVALID_SCITT_SUPER_ROOT"):
        bridge.issue_trust_passport("ent-beta", "epoch-1", "bad_root")
    with pytest.raises(ValueError, match="ttl_ms must be a positive integer"):
        bridge.issue_trust_passport("ent-beta", "epoch-1", "sha256:" + "0" * 64, ttl_ms=0)
    with pytest.raises(ValueError, match="ttl_ms must be a positive integer"):
        bridge.issue_trust_passport("ent-beta", "epoch-1", "sha256:" + "0" * 64, ttl_ms=-1)
    with pytest.raises(ValueError, match="ttl_ms must be a positive integer"):
        bridge.issue_trust_passport("ent-beta", "epoch-1", "sha256:" + "0" * 64, ttl_ms=10.5)  # type: ignore

    bridge.close()


def test_06_nominal_passport_verification_and_admission() -> None:
    bridge_a = CrossEnterpriseFederationBridge("enterprise-alpha")
    bridge_b = CrossEnterpriseFederationBridge("enterprise-beta")

    trusted_keys = {
        "enterprise-alpha": bridge_a.public_key_pem,
    }

    t_eval = 1700000010000
    passp = bridge_a.issue_trust_passport(
        target_enterprise_id="enterprise-beta",
        epoch_id="epoch-2026-q4",
        scitt_super_root="sha256:" + "e" * 64,
        ttl_ms=3600000,
        now_ms=t_eval,
    )

    verdict = bridge_b.verify_and_admit_passport(
        passport=passp,
        trusted_public_keys=trusted_keys,
        current_epoch_id="epoch-2026-q4",
        now_ms=t_eval + 500,
    )

    assert verdict.admitted is True
    assert verdict.status == STATUS_ADMITTED
    assert "admitted" in verdict.reason.lower()
    assert verdict.verdict_caid.startswith("sha256:")

    bridge_a.close()
    bridge_b.close()


def test_07_target_enterprise_mismatch() -> None:
    bridge_a = CrossEnterpriseFederationBridge("enterprise-alpha")
    bridge_b = CrossEnterpriseFederationBridge("enterprise-beta")

    trusted_keys = {"enterprise-alpha": bridge_a.public_key_pem}

    # Issued for enterprise-gamma, but presented to enterprise-beta!
    passp = bridge_a.issue_trust_passport("enterprise-gamma", "epoch-1", "sha256:" + "0" * 64)

    verdict = bridge_b.verify_and_admit_passport(passp, trusted_keys, "epoch-1")
    assert verdict.admitted is False
    assert verdict.status == STATUS_REJECTED_WRONG_TARGET

    bridge_a.close()
    bridge_b.close()


def test_08_untrusted_issuer_and_pinned_key_mismatch() -> None:
    bridge_a = CrossEnterpriseFederationBridge("enterprise-alpha")
    bridge_b = CrossEnterpriseFederationBridge("enterprise-beta")

    passp = bridge_a.issue_trust_passport("enterprise-beta", "epoch-1", "sha256:" + "0" * 64)

    # 1. Origin not in registry
    v1 = bridge_b.verify_and_admit_passport(passp, {}, "epoch-1")
    assert v1.admitted is False
    assert v1.status == STATUS_REJECTED_UNTRUSTED_ISSUER

    # 2. Pinned key does not match passport public key
    other_key = ed25519.Ed25519PrivateKey.generate().public_key()
    other_pem = other_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    v2 = bridge_b.verify_and_admit_passport(passp, {"enterprise-alpha": other_pem}, "epoch-1")
    assert v2.admitted is False
    assert v2.status == STATUS_REJECTED_SIGNATURE

    bridge_a.close()
    bridge_b.close()


def test_09_signature_tamper_and_non_ed25519_key(ec_pem: str) -> None:
    bridge_a = CrossEnterpriseFederationBridge("enterprise-alpha")
    bridge_b = CrossEnterpriseFederationBridge("enterprise-beta")
    trusted_keys = {"enterprise-alpha": bridge_a.public_key_pem}

    passp = bridge_a.issue_trust_passport("enterprise-beta", "epoch-1", "sha256:" + "0" * 64)

    # 1. Tampered scitt_super_root
    tampered_passp = dataclasses.replace(passp, scitt_super_root="sha256:" + "1" * 64)
    v1 = bridge_b.verify_and_admit_passport(tampered_passp, trusted_keys, "epoch-1")
    assert v1.admitted is False
    assert v1.status == STATUS_REJECTED_SIGNATURE

    # 2. Tampered signature bytes
    bad_sig_passp = dataclasses.replace(passp, signature_b64=base64.b64encode(b"bad_sig").decode("ascii"))
    v2 = bridge_b.verify_and_admit_passport(bad_sig_passp, trusted_keys, "epoch-1")
    assert v2.admitted is False
    assert v2.status == STATUS_REJECTED_SIGNATURE

    # 3. Non-Ed25519 public key (e.g. EC SECP256R1)
    ec_passp = dataclasses.replace(passp, public_key_pem=ec_pem)
    v3 = bridge_b.verify_and_admit_passport(ec_passp, {"enterprise-alpha": ec_pem}, "epoch-1")
    assert v3.admitted is False
    assert v3.status == STATUS_REJECTED_SIGNATURE

    bridge_a.close()
    bridge_b.close()


def test_10_temporal_validity() -> None:
    bridge_a = CrossEnterpriseFederationBridge("enterprise-alpha")
    bridge_b = CrossEnterpriseFederationBridge("enterprise-beta")
    trusted_keys = {"enterprise-alpha": bridge_a.public_key_pem}

    now_base = 1700000000000
    passp = bridge_a.issue_trust_passport(
        "enterprise-beta",
        "epoch-1",
        "sha256:" + "0" * 64,
        ttl_ms=10000,
        now_ms=now_base,
    )

    # 1. Future-dated (evaluated far before issued_at_ms)
    v_future = bridge_b.verify_and_admit_passport(
        passp,
        trusted_keys,
        "epoch-1",
        max_clock_skew_ms=1000,
        now_ms=now_base - 5000,
    )
    assert v_future.admitted is False
    assert v_future.status == STATUS_REJECTED_FUTURE_DATED

    # 2. Expired (evaluated far after expires_at_ms)
    v_expired = bridge_b.verify_and_admit_passport(
        passp,
        trusted_keys,
        "epoch-1",
        max_clock_skew_ms=1000,
        now_ms=now_base + 15000,
    )
    assert v_expired.admitted is False
    assert v_expired.status == STATUS_REJECTED_EXPIRED

    bridge_a.close()
    bridge_b.close()


def test_11_epoch_fencing() -> None:
    bridge_a = CrossEnterpriseFederationBridge("enterprise-alpha")
    bridge_b = CrossEnterpriseFederationBridge("enterprise-beta")
    trusted_keys = {"enterprise-alpha": bridge_a.public_key_pem}

    passp = bridge_a.issue_trust_passport("enterprise-beta", "epoch-100", "sha256:" + "0" * 64)

    # Evaluated under epoch-101 (mismatched)
    verdict = bridge_b.verify_and_admit_passport(passp, trusted_keys, "epoch-101")
    assert verdict.admitted is False
    assert verdict.status == STATUS_REJECTED_EPOCH_STALE

    bridge_a.close()
    bridge_b.close()


def test_12_anti_replay_defense() -> None:
    bridge_a = CrossEnterpriseFederationBridge("enterprise-alpha")
    bridge_b = CrossEnterpriseFederationBridge("enterprise-beta")
    trusted_keys = {"enterprise-alpha": bridge_a.public_key_pem}

    passp = bridge_a.issue_trust_passport("enterprise-beta", "epoch-1", "sha256:" + "0" * 64)

    # 1. First submission: Admitted
    v1 = bridge_b.verify_and_admit_passport(passp, trusted_keys, "epoch-1")
    assert v1.admitted is True

    # 2. Replay with same nonce: REJECTED!
    v2 = bridge_b.verify_and_admit_passport(passp, trusted_keys, "epoch-1")
    assert v2.admitted is False
    assert v2.status == STATUS_REJECTED_REPLAY

    bridge_a.close()
    bridge_b.close()


def test_13_sqlite_persistence_and_ledger_retrieval(temp_db: str) -> None:
    bridge_a = CrossEnterpriseFederationBridge("enterprise-alpha")
    bridge_b = CrossEnterpriseFederationBridge("enterprise-beta", db_path=temp_db)
    trusted_keys = {"enterprise-alpha": bridge_a.public_key_pem}

    t_eval = 1700000050000
    passp = bridge_a.issue_trust_passport("enterprise-beta", "epoch-1", "sha256:" + "0" * 64, now_ms=t_eval)
    verdict = bridge_b.verify_and_admit_passport(passp, trusted_keys, "epoch-1", now_ms=t_eval + 10)

    # Retrieve ledger entries with all fields verified
    entries = bridge_b.get_federation_ledger_entries(limit=10)
    assert len(entries) == 1
    assert entries[0]["passport_id"] == passp.passport_id
    assert entries[0]["direction"] == "INBOUND_ADMISSION"
    assert entries[0]["origin_enterprise_id"] == "enterprise-alpha"
    assert entries[0]["target_enterprise_id"] == "enterprise-beta"
    assert entries[0]["epoch_id"] == "epoch-1"
    assert entries[0]["status"] == STATUS_ADMITTED
    assert entries[0]["passport_caid"] == passp.passport_caid
    assert entries[0]["verdict_caid"] == verdict.verdict_caid
    assert entries[0]["timestamp_ms"] == t_eval + 10

    # Test default limit=100 bound
    for i in range(104):
        p_extra = bridge_a.issue_trust_passport("enterprise-beta", "epoch-1", "sha256:" + "0" * 64, now_ms=t_eval + i + 20)
        bridge_b.verify_and_admit_passport(p_extra, trusted_keys, "epoch-1", now_ms=t_eval + i + 25)

    default_entries = bridge_b.get_federation_ledger_entries()
    assert len(default_entries) == 100

    bridge_a.close()
    bridge_b.close()

    # Direct SQLite schema check
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT status, direction FROM cross_enterprise_federation_ledger WHERE passport_id = ?", (passp.passport_id,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == STATUS_ADMITTED
    assert row[1] == "INBOUND_ADMISSION"
    conn.close()
