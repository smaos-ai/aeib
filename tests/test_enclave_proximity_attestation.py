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
tests/test_enclave_proximity_attestation.py
================================================================================
Verification Suite for EnclaveProximityAttestor.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. ProximityChallengeRequest dataclass validations, boundaries, and frozen immutability.
2. ProximityAttestationToken dataclass validations, boundaries, and frozen immutability.
3. CAID generation across str, bytes, and dictionary payloads.
4. Attestor initialization with custom/default parameters and host ID validation.
5. Challenge creation with cryptographic nonces and default timestamps.
6. Nominal physical proximity attestation and Ed25519 signature sealing.
7. Anti-replay defense across duplicate challenge response attempts.
8. Epoch fencing and rejection of stale epoch challenges.
9. Remote tunnel detection via physical RTT ceiling enforcement.
10. Token signature verification and tamper detection.
11. SQLite-WAL append-only persistence and ledger entry retrieval.
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

from src.enclave_proximity_attestation import (
    MAX_PHYSICAL_RTT_MICROS,
    STATUS_PROXIMITY_CONFIRMED,
    STATUS_VIOLATION_REPLAY,
    STATUS_VIOLATION_REMOTE_TUNNEL,
    STATUS_VIOLATION_STALE_EPOCH,
    EnclaveProximityAttestor,
    ProximityAttestationToken,
    ProximityChallengeRequest,
    compute_sha256_caid,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    return str(tmp_path / "test_proximity_attestor.db")


@pytest.fixture
def enclave_key() -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.generate()


@pytest.fixture
def ec_pem() -> str:
    ec_key = ec.generate_private_key(ec.SECP256R1()).public_key()
    return ec_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def test_01_challenge_request_validations() -> None:
    valid_args: Dict[str, Any] = {
        "challenge_id": "chal-001",
        "enclave_id": "enclave-apple-se-01",
        "epoch_id": "epoch-001",
        "nonce": "nonce-001",
        "issued_at_micros": 1700000000000000,
        "max_allowed_rtt_micros": MAX_PHYSICAL_RTT_MICROS,
    }

    req = ProximityChallengeRequest(**valid_args)
    assert req.challenge_id == "chal-001"

    # Exact boundary checks
    req_ts1 = ProximityChallengeRequest(**dict(valid_args, issued_at_micros=1, max_allowed_rtt_micros=1))
    assert req_ts1.issued_at_micros == 1
    assert req_ts1.max_allowed_rtt_micros == 1

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        req.enclave_id = "MUTATED"  # type: ignore

    # Invalid fields
    with pytest.raises(ValueError, match="challenge_id must be a non-empty string"):
        ProximityChallengeRequest(**dict(valid_args, challenge_id=""))
    with pytest.raises(ValueError, match="challenge_id must be a non-empty string"):
        ProximityChallengeRequest(**dict(valid_args, challenge_id=None))  # type: ignore
    with pytest.raises(ValueError, match="enclave_id must be a non-empty string"):
        ProximityChallengeRequest(**dict(valid_args, enclave_id=""))
    with pytest.raises(ValueError, match="epoch_id must be a non-empty string"):
        ProximityChallengeRequest(**dict(valid_args, epoch_id=""))
    with pytest.raises(ValueError, match="nonce must be a non-empty string"):
        ProximityChallengeRequest(**dict(valid_args, nonce=""))
    with pytest.raises(ValueError, match="issued_at_micros must be a positive integer"):
        ProximityChallengeRequest(**dict(valid_args, issued_at_micros=0))
    with pytest.raises(ValueError, match="issued_at_micros must be a positive integer"):
        ProximityChallengeRequest(**dict(valid_args, issued_at_micros=-1))
    with pytest.raises(ValueError, match="issued_at_micros must be a positive integer"):
        ProximityChallengeRequest(**dict(valid_args, issued_at_micros=10.5))  # type: ignore
    with pytest.raises(ValueError, match="max_allowed_rtt_micros must be a positive integer"):
        ProximityChallengeRequest(**dict(valid_args, max_allowed_rtt_micros=0))
    with pytest.raises(ValueError, match="max_allowed_rtt_micros must be a positive integer"):
        ProximityChallengeRequest(**dict(valid_args, max_allowed_rtt_micros=-1))
    with pytest.raises(ValueError, match="max_allowed_rtt_micros must be a positive integer"):
        ProximityChallengeRequest(**dict(valid_args, max_allowed_rtt_micros=2500.5))  # type: ignore


def test_02_attestation_token_validations() -> None:
    valid_args: Dict[str, Any] = {
        "token_id": "tok-001",
        "challenge_id": "chal-001",
        "enclave_id": "enclave-apple-se-01",
        "epoch_id": "epoch-001",
        "status": STATUS_PROXIMITY_CONFIRMED,
        "measured_rtt_micros": 450,
        "max_allowed_rtt_micros": 2500,
        "public_key_pem": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA\n-----END PUBLIC KEY-----",
        "signature_b64": "c2lnbmF0dXJl",
        "token_caid": "sha256:" + "0" * 64,
        "timestamp_micros": 1700000000000000,
    }

    tok = ProximityAttestationToken(**valid_args)
    assert tok.token_id == "tok-001"

    # Exact boundary checks
    tok_rtt0 = ProximityAttestationToken(**dict(valid_args, measured_rtt_micros=0, max_allowed_rtt_micros=1, timestamp_micros=1))
    assert tok_rtt0.measured_rtt_micros == 0
    assert tok_rtt0.max_allowed_rtt_micros == 1
    assert tok_rtt0.timestamp_micros == 1

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        tok.status = "MUTATED"  # type: ignore

    # Invalid fields
    with pytest.raises(ValueError, match="token_id must be a non-empty string"):
        ProximityAttestationToken(**dict(valid_args, token_id=""))
    with pytest.raises(ValueError, match="token_id must be a non-empty string"):
        ProximityAttestationToken(**dict(valid_args, token_id=None))  # type: ignore
    with pytest.raises(ValueError, match="challenge_id must be a non-empty string"):
        ProximityAttestationToken(**dict(valid_args, challenge_id=""))
    with pytest.raises(ValueError, match="enclave_id must be a non-empty string"):
        ProximityAttestationToken(**dict(valid_args, enclave_id=""))
    with pytest.raises(ValueError, match="epoch_id must be a non-empty string"):
        ProximityAttestationToken(**dict(valid_args, epoch_id=""))
    with pytest.raises(ValueError, match="status must be a non-empty string"):
        ProximityAttestationToken(**dict(valid_args, status=""))
    with pytest.raises(ValueError, match="measured_rtt_micros must be a non-negative integer"):
        ProximityAttestationToken(**dict(valid_args, measured_rtt_micros=-1))
    with pytest.raises(ValueError, match="measured_rtt_micros must be a non-negative integer"):
        ProximityAttestationToken(**dict(valid_args, measured_rtt_micros=10.5))  # type: ignore
    with pytest.raises(ValueError, match="max_allowed_rtt_micros must be a positive integer"):
        ProximityAttestationToken(**dict(valid_args, max_allowed_rtt_micros=0))
    with pytest.raises(ValueError, match="max_allowed_rtt_micros must be a positive integer"):
        ProximityAttestationToken(**dict(valid_args, max_allowed_rtt_micros=10.5))  # type: ignore
    with pytest.raises(ValueError, match="public_key_pem must be a non-empty string"):
        ProximityAttestationToken(**dict(valid_args, public_key_pem=""))
    with pytest.raises(ValueError, match="signature_b64 must be a non-empty string"):
        ProximityAttestationToken(**dict(valid_args, signature_b64=""))
    with pytest.raises(ValueError, match="token_caid must be a valid sha256 prefix string"):
        ProximityAttestationToken(**dict(valid_args, token_caid="bad_caid"))
    with pytest.raises(ValueError, match="timestamp_micros must be a positive integer"):
        ProximityAttestationToken(**dict(valid_args, timestamp_micros=0))
    with pytest.raises(ValueError, match="timestamp_micros must be a positive integer"):
        ProximityAttestationToken(**dict(valid_args, timestamp_micros=-1))
    with pytest.raises(ValueError, match="timestamp_micros must be a positive integer"):
        ProximityAttestationToken(**dict(valid_args, timestamp_micros=10.5))  # type: ignore


def test_03_caid_computation() -> None:
    c_bytes = compute_sha256_caid(b"proximity_payload")
    c_str = compute_sha256_caid("proximity_payload")
    c_dict = compute_sha256_caid({"status": "PROXIMITY_CONFIRMED"})

    assert c_bytes.startswith("sha256:")
    assert c_str.startswith("sha256:")
    assert c_dict.startswith("sha256:")
    assert c_bytes == c_str


def test_04_attestor_initialization() -> None:
    # Default initialization
    att = EnclaveProclaveProximity = EnclaveProximityAttestor()
    assert att.host_id == "host-primary"
    assert att.current_epoch_id == "epoch-001"
    assert att.max_physical_rtt_micros == MAX_PHYSICAL_RTT_MICROS
    att.close()

    # Boundary check max_physical_rtt_micros=1
    att_b1 = EnclaveProximityAttestor(max_physical_rtt_micros=1)
    assert att_b1.max_physical_rtt_micros == 1
    att_b1.close()

    # Invalid arguments
    with pytest.raises(ValueError, match="host_id must be a non-empty string"):
        EnclaveProximityAttestor(host_id="")
    with pytest.raises(ValueError, match="host_id must be a non-empty string"):
        EnclaveProximityAttestor(host_id=None)  # type: ignore
    with pytest.raises(ValueError, match="current_epoch_id must be a non-empty string"):
        EnclaveProximityAttestor(current_epoch_id="")
    with pytest.raises(ValueError, match="max_physical_rtt_micros must be a positive integer"):
        EnclaveProximityAttestor(max_physical_rtt_micros=0)
    with pytest.raises(ValueError, match="max_physical_rtt_micros must be a positive integer"):
        EnclaveProximityAttestor(max_physical_rtt_micros=-1)
    with pytest.raises(ValueError, match="max_physical_rtt_micros must be a positive integer"):
        EnclaveProximityAttestor(max_physical_rtt_micros=2500.5)  # type: ignore


def test_05_challenge_creation() -> None:
    att = EnclaveProximityAttestor()
    t_now_micros = int(time.time() * 1000000)

    # Valid challenge with explicit now_micros
    chal = att.create_challenge("enclave-se-01", now_micros=1700000000000000)
    assert chal.enclave_id == "enclave-se-01"
    assert chal.epoch_id == "epoch-001"
    assert chal.issued_at_micros == 1700000000000000
    assert chal.nonce.startswith("prox-")
    assert len(chal.challenge_id) == 17

    # Default now_micros
    chal_default = att.create_challenge("enclave-se-01")
    assert chal_default.issued_at_micros >= t_now_micros
    assert chal_default.issued_at_micros <= int(time.time() * 1000000) + 5000000
    assert chal_default.issued_at_micros > 1_000_000_000_000_000

    # Invalid enclave_id
    with pytest.raises(ValueError, match="enclave_id must be a non-empty string"):
        att.create_challenge("")
    with pytest.raises(ValueError, match="enclave_id must be a non-empty string"):
        att.create_challenge(None)  # type: ignore

    att.close()


def test_06_nominal_proximity_attestation(enclave_key: ed25519.Ed25519PrivateKey) -> None:
    att = EnclaveProximityAttestor()
    t_now = 1700000001000000
    chal = att.create_challenge("enclave-se-01", now_micros=t_now)

    # Nominal fast response (450 micros <= 2500 micros)
    token = att.verify_and_seal_response(
        challenge=chal,
        enclave_private_key=enclave_key,
        observed_rtt_micros=450,
        now_micros=t_now + 450,
    )

    assert token.status == STATUS_PROXIMITY_CONFIRMED
    assert token.measured_rtt_micros == 450
    assert token.max_allowed_rtt_micros == MAX_PHYSICAL_RTT_MICROS
    assert token.token_caid.startswith("sha256:")

    # Verify cryptographic signature on confirmed token
    assert att.verify_token_signature(token, chal.nonce) is True

    # Nominal response with default now_micros (verifying exact 1,000,000 microsecond scaling)
    chal2 = att.create_challenge("enclave-se-01", now_micros=t_now)
    t_before = int(time.time() * 1000000)
    token2 = att.verify_and_seal_response(
        challenge=chal2,
        enclave_private_key=enclave_key,
        observed_rtt_micros=450,
    )
    t_after = int(time.time() * 1000000)
    assert token2.status == STATUS_PROXIMITY_CONFIRMED
    assert t_before <= token2.timestamp_micros <= t_after + 50000  # tighter than 1760s drift from 1000001 mutant

    att.close()


def test_07_anti_replay_defense(enclave_key: ed25519.Ed25519PrivateKey) -> None:
    att = EnclaveProximityAttestor()
    chal = att.create_challenge("enclave-se-01")

    # 1. First attempt: confirmed
    t1 = att.verify_and_seal_response(chal, enclave_key, 300)
    assert t1.status == STATUS_PROXIMITY_CONFIRMED

    # 2. Replay with same challenge/nonce: REJECTED!
    t2 = att.verify_and_seal_response(chal, enclave_key, 300)
    assert t2.status == STATUS_VIOLATION_REPLAY
    assert att.verify_token_signature(t2, chal.nonce) is False

    att.close()


def test_08_epoch_fencing(enclave_key: ed25519.Ed25519PrivateKey) -> None:
    att = EnclaveProximityAttestor(current_epoch_id="epoch-002")
    # Challenge created under stale epoch-001
    chal = ProximityChallengeRequest(
        challenge_id="chal-stale",
        enclave_id="enclave-se-01",
        epoch_id="epoch-001",
        nonce="prox-stale",
        issued_at_micros=1700000000000000,
        max_allowed_rtt_micros=2500,
    )

    token = att.verify_and_seal_response(chal, enclave_key, 400)
    assert token.status == STATUS_VIOLATION_STALE_EPOCH
    assert att.verify_token_signature(token, chal.nonce) is False

    att.close()


def test_09_remote_tunnel_rtt_violation(enclave_key: ed25519.Ed25519PrivateKey) -> None:
    att = EnclaveProximityAttestor(max_physical_rtt_micros=2500)
    chal = att.create_challenge("enclave-se-01")

    # RTT exceeds threshold (e.g. 3500 micros > 2500 micros indicates WAN proxy relay)
    token = att.verify_and_seal_response(chal, enclave_key, observed_rtt_micros=3500)
    assert token.status == STATUS_VIOLATION_REMOTE_TUNNEL
    assert token.measured_rtt_micros == 3500
    assert att.verify_token_signature(token, chal.nonce) is False

    att.close()


def test_10_signature_verification_and_tamper(
    enclave_key: ed25519.Ed25519PrivateKey,
    ec_pem: str,
) -> None:
    att = EnclaveProximityAttestor()
    chal = att.create_challenge("enclave-se-01")
    token = att.verify_and_seal_response(chal, enclave_key, 500)
    assert att.verify_token_signature(token, chal.nonce) is True

    # 1. Wrong nonce
    assert att.verify_token_signature(token, "wrong-nonce") is False

    # 2. Tampered measured RTT
    tampered_rtt = dataclasses.replace(token, measured_rtt_micros=100)
    assert att.verify_token_signature(tampered_rtt, chal.nonce) is False

    # 3. Tampered signature bytes
    bad_sig = dataclasses.replace(token, signature_b64=base64.b64encode(b"bad_sig").decode("ascii"))
    assert att.verify_token_signature(bad_sig, chal.nonce) is False

    # 4. Non-Ed25519 PEM
    ec_token = dataclasses.replace(token, public_key_pem=ec_pem)
    assert att.verify_token_signature(ec_token, chal.nonce) is False

    # 5. Invalid PEM syntax
    bad_pem = dataclasses.replace(token, public_key_pem="bad_pem")
    assert att.verify_token_signature(bad_pem, chal.nonce) is False

    att.close()


def test_11_sqlite_persistence_and_ledger_retrieval(
    temp_db: str,
    enclave_key: ed25519.Ed25519PrivateKey,
) -> None:
    att = EnclaveProximityAttestor(db_path=temp_db, host_id="host-db-test")
    t_now = 1700000010000000
    chal = att.create_challenge("enclave-se-01", now_micros=t_now)
    token = att.verify_and_seal_response(chal, enclave_key, 600, now_micros=t_now + 600)

    # Retrieve ledger entries with all fields verified
    entries = att.get_ledger_entries(limit=10)
    assert len(entries) == 1
    assert entries[0]["token_id"] == token.token_id
    assert entries[0]["challenge_id"] == chal.challenge_id
    assert entries[0]["enclave_id"] == "enclave-se-01"
    assert entries[0]["epoch_id"] == "epoch-001"
    assert entries[0]["status"] == STATUS_PROXIMITY_CONFIRMED
    assert entries[0]["measured_rtt_micros"] == 600
    assert entries[0]["max_allowed_rtt_micros"] == MAX_PHYSICAL_RTT_MICROS
    assert entries[0]["token_caid"] == token.token_caid
    assert entries[0]["timestamp_micros"] == t_now + 600

    # Test default limit=100 bound
    for i in range(104):
        c_extra = att.create_challenge("enclave-se-01", now_micros=t_now + (i + 1) * 1000)
        att.verify_and_seal_response(c_extra, enclave_key, 500, now_micros=t_now + (i + 1) * 1000 + 500)

    default_entries = att.get_ledger_entries()
    assert len(default_entries) == 100

    att.close()

    # Direct SQLite schema check
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT status, measured_rtt_micros FROM enclave_proximity_ledger WHERE token_id = ?", (token.token_id,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == STATUS_PROXIMITY_CONFIRMED
    assert row[1] == 600
    conn.close()


def test_12_exact_mutation_boundaries(
    enclave_key: ed25519.Ed25519PrivateKey,
) -> None:
    att = EnclaveProximityAttestor(host_id="host-boundary")

    # 1. Challenge ID length and prefix
    chal = att.create_challenge("enclave-01")
    assert chal.challenge_id.startswith("chal-")
    assert len(chal.challenge_id) == 17
    # Default now_micros uses microsecond multiplier (1,000,000)
    assert chal.issued_at_micros > 1_700_000_000_000_000

    # 2. Token sealing with default now_micros
    token = att.verify_and_seal_response(chal, enclave_key, 1000)
    assert token.timestamp_micros > 1_700_000_000_000_000

    # 3. max_allowed_rtt_micros <= 0 in token validation
    with pytest.raises(ValueError, match="max_allowed_rtt_micros must be a positive integer"):
        dataclasses.replace(token, max_allowed_rtt_micros=0)

    with pytest.raises(ValueError, match="max_allowed_rtt_micros must be a positive integer"):
        dataclasses.replace(token, max_allowed_rtt_micros=-1)

    # 4. DEFAULT_MAX_PHYSICAL_RTT_MICROS == 2500
    assert MAX_PHYSICAL_RTT_MICROS == 2500

    att.close()

