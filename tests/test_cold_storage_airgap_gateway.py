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
tests/test_cold_storage_airgap_gateway.py
================================================================================
Verification Suite for ColdStorageAirgapGateway.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. AirgapRequestEnvelope validation, boundaries, and frozen immutability.
2. AirgapResponseEnvelope validation, boundaries, and frozen immutability.
3. CAID generation across str, bytes, and dictionary payloads.
4. Gateway initialization with custom/default Ed25519 keys and ID checks.
5. Outbound request creation, cryptographic signing, and CAID sealing.
6. Inbound cold-storage processing and authorization.
7. Anti-replay nonce defense across consecutive transit cycles.
8. Operator manual denial and custom rejection reasons.
9. Hot station cryptographic signature verification and tamper detection.
10. Cold notary cryptographic response signature verification.
11. SQLite-WAL append-only persistence and ledger durability.
"""

from __future__ import annotations

import base64
import dataclasses
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from src.cold_storage_airgap_gateway import (
    DECISION_AUTHORIZED,
    DECISION_REJECTED,
    AirgapRequestEnvelope,
    AirgapResponseEnvelope,
    ColdStorageAirgapGateway,
    compute_sha256_caid,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    return str(tmp_path / "test_airgap_gateway.db")


@pytest.fixture
def test_gateway() -> ColdStorageAirgapGateway:
    return ColdStorageAirgapGateway(gateway_id="gw-test-01")


@pytest.fixture
def ec_pem() -> str:
    ec_key = ec.generate_private_key(ec.SECP256R1()).public_key()
    return ec_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def test_01_request_envelope_validations() -> None:
    valid_args: Dict[str, Any] = {
        "envelope_id": "env-01",
        "action_type": "T3_COLD_SETTLE",
        "target_resource": "vault://cold/reserve",
        "amount_minor": 100000,
        "nonce": "nonce-12345",
        "dispatch_epoch_ms": 1700000000000,
        "hot_station_pubkey_pem": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA\n-----END PUBLIC KEY-----",
        "signature_b64": "c2lnbmF0dXJl",
        "request_caid": "sha256:" + "0" * 64,
    }

    env = AirgapRequestEnvelope(**valid_args)
    assert env.envelope_id == "env-01"

    # Exact boundary checks
    env_amt_0 = AirgapRequestEnvelope(**dict(valid_args, amount_minor=0))
    assert env_amt_0.amount_minor == 0

    env_ms_1 = AirgapRequestEnvelope(**dict(valid_args, dispatch_epoch_ms=1))
    assert env_ms_1.dispatch_epoch_ms == 1

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        env.amount_minor = 500  # type: ignore

    # Invalid fields
    with pytest.raises(ValueError, match="ERR_INVALID_ENVELOPE_ID"):
        AirgapRequestEnvelope(**dict(valid_args, envelope_id=""))
    with pytest.raises(ValueError, match="ERR_INVALID_ACTION_TYPE"):
        AirgapRequestEnvelope(**dict(valid_args, action_type=""))
    with pytest.raises(ValueError, match="ERR_INVALID_TARGET_RESOURCE"):
        AirgapRequestEnvelope(**dict(valid_args, target_resource=""))
    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT_MINOR"):
        AirgapRequestEnvelope(**dict(valid_args, amount_minor=-1))
    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT_MINOR"):
        AirgapRequestEnvelope(**dict(valid_args, amount_minor=10.5))  # type: ignore
    with pytest.raises(ValueError, match="ERR_INVALID_NONCE"):
        AirgapRequestEnvelope(**dict(valid_args, nonce=""))
    with pytest.raises(ValueError, match="ERR_INVALID_DISPATCH_EPOCH_MS"):
        AirgapRequestEnvelope(**dict(valid_args, dispatch_epoch_ms=0))
    with pytest.raises(ValueError, match="ERR_INVALID_DISPATCH_EPOCH_MS"):
        AirgapRequestEnvelope(**dict(valid_args, dispatch_epoch_ms=10.5))  # type: ignore
    with pytest.raises(ValueError, match="ERR_INVALID_PUBKEY_PEM"):
        AirgapRequestEnvelope(**dict(valid_args, hot_station_pubkey_pem=""))
    with pytest.raises(ValueError, match="ERR_INVALID_SIGNATURE_B64"):
        AirgapRequestEnvelope(**dict(valid_args, signature_b64=""))
    with pytest.raises(ValueError, match="ERR_INVALID_REQUEST_CAID"):
        AirgapRequestEnvelope(**dict(valid_args, request_caid="bad_caid"))


def test_02_response_envelope_validations() -> None:
    valid_args: Dict[str, Any] = {
        "response_id": "resp-01",
        "request_envelope_id": "env-01",
        "decision": DECISION_AUTHORIZED,
        "rejection_reason": None,
        "notarized_at_epoch_ms": 1700000000000,
        "cold_notary_pubkey_pem": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA\n-----END PUBLIC KEY-----",
        "signature_b64": "c2lnbmF0dXJl",
        "response_caid": "sha256:" + "0" * 64,
    }

    resp = AirgapResponseEnvelope(**valid_args)
    assert resp.response_id == "resp-01"

    # Exact boundary check
    resp_ms_1 = AirgapResponseEnvelope(**dict(valid_args, notarized_at_epoch_ms=1))
    assert resp_ms_1.notarized_at_epoch_ms == 1

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        resp.decision = "MUTATED"  # type: ignore

    # Invalid fields
    with pytest.raises(ValueError, match="ERR_INVALID_RESPONSE_ID"):
        AirgapResponseEnvelope(**dict(valid_args, response_id=""))
    with pytest.raises(ValueError, match="ERR_INVALID_REQUEST_ENVELOPE_ID"):
        AirgapResponseEnvelope(**dict(valid_args, request_envelope_id=""))
    with pytest.raises(ValueError, match="ERR_INVALID_DECISION"):
        AirgapResponseEnvelope(**dict(valid_args, decision="INVALID"))
    with pytest.raises(ValueError, match="ERR_INVALID_NOTARIZED_EPOCH_MS"):
        AirgapResponseEnvelope(**dict(valid_args, notarized_at_epoch_ms=0))
    with pytest.raises(ValueError, match="ERR_INVALID_NOTARIZED_EPOCH_MS"):
        AirgapResponseEnvelope(**dict(valid_args, notarized_at_epoch_ms=10.5))  # type: ignore
    with pytest.raises(ValueError, match="ERR_INVALID_PUBKEY_PEM"):
        AirgapResponseEnvelope(**dict(valid_args, cold_notary_pubkey_pem=""))
    with pytest.raises(ValueError, match="ERR_INVALID_SIGNATURE_B64"):
        AirgapResponseEnvelope(**dict(valid_args, signature_b64=""))
    with pytest.raises(ValueError, match="ERR_INVALID_RESPONSE_CAID"):
        AirgapResponseEnvelope(**dict(valid_args, response_caid="bad_caid"))


def test_03_caid_computation() -> None:
    c_bytes = compute_sha256_caid(b"payload")
    c_str = compute_sha256_caid("payload")
    c_dict = compute_sha256_caid({"status": "AIRGAP_OK"})

    assert c_bytes.startswith("sha256:")
    assert c_str.startswith("sha256:")
    assert c_dict.startswith("sha256:")
    assert c_bytes == c_str


def test_04_gateway_initialization() -> None:
    # Default initialization
    gw = ColdStorageAirgapGateway()
    assert gw.gateway_id == "airgap-gw-01"
    assert "BEGIN PUBLIC KEY" in gw.public_key_pem

    # Custom key
    key = ed25519.Ed25519PrivateKey.generate()
    gw_custom = ColdStorageAirgapGateway(gateway_id="gw-custom", private_key=key)
    assert gw_custom.gateway_id == "gw-custom"

    # Invalid ID
    with pytest.raises(ValueError, match="ERR_INVALID_GATEWAY_ID"):
        ColdStorageAirgapGateway(gateway_id="")
    with pytest.raises(ValueError, match="ERR_INVALID_GATEWAY_ID"):
        ColdStorageAirgapGateway(gateway_id="   ")


def test_05_outbound_request_creation(test_gateway: ColdStorageAirgapGateway) -> None:
    env = test_gateway.create_outbound_request(
        action_type="T3_TRANSFER",
        target_resource="vault://cold/acct_42",
        amount_minor=50000,
        nonce="test-nonce-1",
        dispatch_time_ms=1700000001000,
    )
    assert env.action_type == "T3_TRANSFER"
    assert env.amount_minor == 50000
    assert env.nonce == "test-nonce-1"
    assert env.dispatch_epoch_ms == 1700000001000
    assert env.request_caid.startswith("sha256:")

    # Signature verifies natively
    assert test_gateway.verify_request_signature(env) is True

    # Default parameters (no nonce, no dispatch_time_ms)
    t_start = int(time.time() * 1000)
    env_default = test_gateway.create_outbound_request(
        action_type="T3_TRANSFER",
        target_resource="vault://cold/acct_42",
        amount_minor=1000,
    )
    assert env_default.nonce.startswith("nonce-")
    assert env_default.dispatch_epoch_ms >= t_start
    assert env_default.dispatch_epoch_ms <= int(time.time() * 1000) + 5000
    assert env_default.dispatch_epoch_ms > 1_000_000_000_000

    # Invalid args
    with pytest.raises(ValueError, match="ERR_INVALID_ACTION_TYPE"):
        test_gateway.create_outbound_request("", "target", 100)
    with pytest.raises(ValueError, match="ERR_INVALID_TARGET_RESOURCE"):
        test_gateway.create_outbound_request("T3_TRANSFER", "", 100)
    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT_MINOR"):
        test_gateway.create_outbound_request("T3_TRANSFER", "target", -1)
    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT_MINOR"):
        test_gateway.create_outbound_request("T3_TRANSFER", "target", 1.5)  # type: ignore


def test_06_inbound_cold_storage_authorization(test_gateway: ColdStorageAirgapGateway) -> None:
    req_env = test_gateway.create_outbound_request("T3_TRANSFER", "vault://cold/acct_42", 50000)

    resp_env = test_gateway.process_and_authorize_in_cold_storage(
        request_env=req_env,
        operator_authorized=True,
        cold_time_ms=1700000002000,
    )
    assert resp_env.decision == DECISION_AUTHORIZED
    assert resp_env.rejection_reason is None
    assert resp_env.request_envelope_id == req_env.envelope_id
    assert resp_env.notarized_at_epoch_ms == 1700000002000
    assert test_gateway.verify_response_signature(resp_env) is True

    # Default cold_time_ms (None)
    req_env2 = test_gateway.create_outbound_request("T3_TRANSFER", "vault://cold/acct_42", 20000)
    t_cold = int(time.time() * 1000)
    resp_default = test_gateway.process_and_authorize_in_cold_storage(
        request_env=req_env2,
        operator_authorized=True,
    )
    assert resp_default.notarized_at_epoch_ms >= t_cold
    assert resp_default.notarized_at_epoch_ms <= int(time.time() * 1000) + 5000
    assert resp_default.notarized_at_epoch_ms > 1_000_000_000_000



def test_07_anti_replay_nonce_defense(test_gateway: ColdStorageAirgapGateway) -> None:
    req_env = test_gateway.create_outbound_request("T3_TRANSFER", "vault://cold/acct_42", 50000)

    # First attempt: Authorized
    r1 = test_gateway.process_and_authorize_in_cold_storage(req_env, operator_authorized=True)
    assert r1.decision == DECISION_AUTHORIZED

    # Second attempt (Replay with same nonce): REJECTED!
    r2 = test_gateway.process_and_authorize_in_cold_storage(req_env, operator_authorized=True)
    assert r2.decision == DECISION_REJECTED
    assert r2.rejection_reason == "ERR_AIRGAP_REPLAY_DETECTED"
    assert test_gateway.verify_response_signature(r2) is True


def test_08_operator_denial_and_custom_reasons(test_gateway: ColdStorageAirgapGateway) -> None:
    req1 = test_gateway.create_outbound_request("T3_TRANSFER", "vault://cold/acct_42", 100000)
    # Default denial reason
    r1 = test_gateway.process_and_authorize_in_cold_storage(req1, operator_authorized=False)
    assert r1.decision == DECISION_REJECTED
    assert r1.rejection_reason == "OPERATOR_AUTHORIZATION_DENIED"

    req2 = test_gateway.create_outbound_request("T3_TRANSFER", "vault://cold/acct_42", 200000)
    # Custom denial reason
    r2 = test_gateway.process_and_authorize_in_cold_storage(
        req2,
        operator_authorized=False,
        rejection_reason="EXCEEDS_SINGLE_TRANSACTION_LIMIT",
    )
    assert r2.decision == DECISION_REJECTED
    assert r2.rejection_reason == "EXCEEDS_SINGLE_TRANSACTION_LIMIT"


def test_09_request_signature_tamper_detection(test_gateway: ColdStorageAirgapGateway, ec_pem: str) -> None:
    req = test_gateway.create_outbound_request("T3_TRANSFER", "vault://cold/acct_42", 50000)

    # Tampered amount
    tampered_req = dataclasses.replace(req, amount_minor=999999)
    assert test_gateway.verify_request_signature(tampered_req) is False

    resp = test_gateway.process_and_authorize_in_cold_storage(tampered_req, operator_authorized=True)
    assert resp.decision == DECISION_REJECTED
    assert resp.rejection_reason == "ERR_INVALID_HOT_STATION_SIGNATURE"

    # Tampered signature bytes
    bad_sig_req = dataclasses.replace(req, signature_b64=base64.b64encode(b"invalid_sig").decode("ascii"))
    assert test_gateway.verify_request_signature(bad_sig_req) is False

    # Invalid public key PEM
    bad_pem_req = dataclasses.replace(req, hot_station_pubkey_pem="bad_pem")
    assert test_gateway.verify_request_signature(bad_pem_req) is False

    # Non-Ed25519 PEM (e.g. EC P-256) returns False
    ec_req = dataclasses.replace(req, hot_station_pubkey_pem=ec_pem)
    assert test_gateway.verify_request_signature(ec_req) is False


def test_10_response_signature_tamper_detection(test_gateway: ColdStorageAirgapGateway, ec_pem: str) -> None:
    req = test_gateway.create_outbound_request("T3_TRANSFER", "vault://cold/acct_42", 50000)
    resp = test_gateway.process_and_authorize_in_cold_storage(req, operator_authorized=True)

    # Tampered decision
    tampered_resp = dataclasses.replace(resp, decision=DECISION_REJECTED)
    assert test_gateway.verify_response_signature(tampered_resp) is False

    # Tampered signature
    bad_sig_resp = dataclasses.replace(resp, signature_b64=base64.b64encode(b"bad_sig").decode("ascii"))
    assert test_gateway.verify_response_signature(bad_sig_resp) is False

    # Bad PEM
    bad_pem_resp = dataclasses.replace(resp, cold_notary_pubkey_pem="not_pem")
    assert test_gateway.verify_response_signature(bad_pem_resp) is False

    # Non-Ed25519 PEM (e.g. EC P-256) returns False
    ec_resp = dataclasses.replace(resp, cold_notary_pubkey_pem=ec_pem)
    assert test_gateway.verify_response_signature(ec_resp) is False


def test_11_sqlite_persistence_and_durability(temp_db: str) -> None:
    gw = ColdStorageAirgapGateway(gateway_id="gw-db-test", db_path=temp_db)
    now_ms = 1700000010000
    req = gw.create_outbound_request(
        action_type="T3_TRANSFER",
        target_resource="vault://cold/acct_42",
        amount_minor=50000,
        dispatch_time_ms=now_ms,
    )
    resp = gw.process_and_authorize_in_cold_storage(req, operator_authorized=True, cold_time_ms=now_ms + 100)
    gw.close()

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT envelope_id, transit_direction, action_type, status, envelope_caid FROM airgap_transit_ledger ORDER BY epoch_ms ASC")
    rows = cur.fetchall()
    assert len(rows) == 2

    # Outbound row
    assert rows[0][0] == req.envelope_id
    assert rows[0][1] == "OUTBOUND"
    assert rows[0][2] == "T3_TRANSFER"
    assert rows[0][3] == "PENDING"
    assert rows[0][4] == req.request_caid

    # Inbound response row
    assert rows[1][0] == resp.response_id
    assert rows[1][1] == "INBOUND_RESPONSE"
    assert rows[1][2] == "T3_TRANSFER"
    assert rows[1][3] == DECISION_AUTHORIZED
    assert rows[1][4] == resp.response_caid
    conn.close()
