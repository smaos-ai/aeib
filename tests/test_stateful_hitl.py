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
tests/test_stateful_hitl.py
================================================================================
Test & Falsification Suite for Stateful HITL Resumption & Canvas Serializer.

Evaluated under the stated model:
- Deterministic RFC 8785 state hash generation over suspended canvas and runtime state.
- Real Ed25519 cryptographic warrant verification and parameter adjustment.
- Negative controls: state hash mismatch rejection, unauthorized signature rejection,
  expired session rejection, and double-resumption prevention.
- Epistemic linguistic compliance check.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.stateful_hitl import (
    DEFAULT_HITL_TIMEOUT_SEC,
    HumanAdjustmentWarrant,
    SessionStateStatus,
    StatefulHitlSerializer,
    StatefulSessionSnapshot,
    canonical_json_v1,
)


def _sign_warrant(
    signing_key: Ed25519PrivateKey,
    session_id: str,
    expected_state_hash: str,
    adjusted_parameters: Dict[str, Any],
) -> HumanAdjustmentWarrant:
    payload = {
        "adjusted_parameters": adjusted_parameters,
        "expected_state_hash": expected_state_hash,
        "session_id": session_id,
    }
    canonical = canonical_json_v1(payload)
    sig = signing_key.sign(canonical)
    pub_hex = signing_key.public_key().public_bytes_raw().hex()
    return HumanAdjustmentWarrant(
        session_id=session_id,
        expected_state_hash=expected_state_hash,
        adjusted_parameters=adjusted_parameters,
        supervisor_pubkey_hex=pub_hex,
        signature_hex=sig.hex(),
    )


# -----------------------------------------------------------------------------
# Test 0: Configuration Constants & Immutability
# -----------------------------------------------------------------------------
def test_0_config_constants_and_immutability() -> None:
    assert DEFAULT_HITL_TIMEOUT_SEC == int("3600")
    serializer = StatefulHitlSerializer()
    assert serializer.session_ttl_sec == DEFAULT_HITL_TIMEOUT_SEC

    snap = StatefulSessionSnapshot(
        session_id="s1",
        task_intent="intent",
        step_index=1,
        memory_digest="d1",
        canvas_data={},
        staged_action_name="act",
        staged_parameters={},
        risk_tier="T3_IRREVERSIBLE",
        state_hash="h1",
        status=SessionStateStatus.SUSPENDED_AWAITING_APPROVAL,
        created_at_epoch=100,
        expires_at_epoch=200,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.status = SessionStateStatus.RESUMED_APPROVED  # type: ignore

    warrant = HumanAdjustmentWarrant(
        session_id="s1",
        expected_state_hash="h1",
        adjusted_parameters={},
        supervisor_pubkey_hex="00" * 32,
        signature_hex="00" * 64,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        warrant.session_id = "s2"  # type: ignore

    # canonical_json_v1 delegates to the RFC 8785 reference encoder; the former
    # json.dumps flag spy pinned the old local implementation. Assert behaviour:
    # UTF-8 without ASCII escaping, UTF-16 key order, ECMAScript numbers, NaN rejected.
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs

    assert canonical_json_v1({"u": "α"}) == '{"u":"α"}'.encode("utf-8")
    probe = {"\U0001F600": 1, "\uffff": [1e21, 1e-7, -0.0]}
    assert canonical_json_v1(probe) == _reference_encode_jcs(probe)
    assert canonical_json_v1(probe) == '{"\U0001F600":1,"\uffff":[1e+21,1e-7,0]}'.encode("utf-8")
    with pytest.raises(ValueError):
        canonical_json_v1({"x": float("nan")})


# -----------------------------------------------------------------------------
# Test 1: Positive Control (Suspension, Adjustment & Resumption)
# -----------------------------------------------------------------------------
def test_1_positive_control_suspend_adjust_resume() -> None:
    serializer = StatefulHitlSerializer(session_ttl_sec=3600)
    supervisor_key = Ed25519PrivateKey.generate()

    canvas = {"chart_type": "disbursement_slider", "slider_value": 500}
    staged_params = {"recipient_id": "ACC_123", "amount_minor": 50000, "currency": "EUR"}

    snapshot = serializer.suspend_for_hitl(
        session_id="sess_001",
        task_intent="Disburse vendor payment",
        step_index=4,
        memory_digest="sha256:abc1234",
        canvas_data=canvas,
        staged_action_name="wire_transfer",
        staged_parameters=staged_params,
        risk_tier="T3_IRREVERSIBLE",
    )

    assert snapshot.session_id == "sess_001"
    assert snapshot.status == SessionStateStatus.SUSPENDED_AWAITING_APPROVAL
    assert snapshot.state_hash.startswith("sha256:")
    assert snapshot.expires_at_epoch > snapshot.created_at_epoch

    # Human supervisor adjusts amount down to 45000 in canvas and signs warrant
    adjusted_params = {"amount_minor": 45000}
    warrant = _sign_warrant(
        signing_key=supervisor_key,
        session_id="sess_001",
        expected_state_hash=snapshot.state_hash,
        adjusted_parameters=adjusted_params,
    )

    resumed_snap, effective_params = serializer.resume_with_warrant(warrant)

    assert resumed_snap.status == SessionStateStatus.RESUMED_APPROVED
    assert resumed_snap.step_index == 5  # Incremented
    assert effective_params["amount_minor"] == 45000
    assert effective_params["recipient_id"] == "ACC_123"
    assert effective_params["currency"] == "EUR"
    assert serializer.get_session("sess_001") == resumed_snap


# -----------------------------------------------------------------------------
# Test 2: State Hash Mismatch Rejection
# -----------------------------------------------------------------------------
def test_2_state_hash_mismatch_rejection() -> None:
    serializer = StatefulHitlSerializer(session_ttl_sec=3600)
    supervisor_key = Ed25519PrivateKey.generate()

    snapshot = serializer.suspend_for_hitl(
        session_id="sess_002",
        task_intent="Database migration",
        step_index=1,
        memory_digest="sha256:mem1",
        canvas_data={"table": "users"},
        staged_action_name="drop_partition",
        staged_parameters={"partition": "p2025"},
    )

    # Forged state hash
    tampered_hash = "sha256:" + "0" * 64
    warrant = _sign_warrant(
        signing_key=supervisor_key,
        session_id="sess_002",
        expected_state_hash=tampered_hash,
        adjusted_parameters={},
    )

    with pytest.raises(ValueError, match="HALT_STATE_HASH_MISMATCH"):
        serializer.resume_with_warrant(warrant)


# -----------------------------------------------------------------------------
# Test 3: Unauthorized Signature Rejection
# -----------------------------------------------------------------------------
def test_3_unauthorized_signature_rejection() -> None:
    serializer = StatefulHitlSerializer(session_ttl_sec=3600)
    key_a = Ed25519PrivateKey.generate()
    key_b = Ed25519PrivateKey.generate()

    snapshot = serializer.suspend_for_hitl(
        session_id="sess_003",
        task_intent="API key rotation",
        step_index=2,
        memory_digest="sha256:mem2",
        canvas_data={},
        staged_action_name="rotate_keys",
        staged_parameters={"target": "aws_kms"},
    )

    # Signed with key_a, but presenting key_b public key hex
    warrant_valid = _sign_warrant(
        signing_key=key_a,
        session_id="sess_003",
        expected_state_hash=snapshot.state_hash,
        adjusted_parameters={},
    )
    tampered_warrant = HumanAdjustmentWarrant(
        session_id=warrant_valid.session_id,
        expected_state_hash=warrant_valid.expected_state_hash,
        adjusted_parameters=warrant_valid.adjusted_parameters,
        supervisor_pubkey_hex=key_b.public_key().public_bytes_raw().hex(),
        signature_hex=warrant_valid.signature_hex,
    )

    with pytest.raises(ValueError, match="HALT_UNAUTHORIZED_RESUME"):
        serializer.resume_with_warrant(tampered_warrant)


# -----------------------------------------------------------------------------
# Test 4: Session Expiry
# -----------------------------------------------------------------------------
def test_4_session_expiry() -> None:
    serializer = StatefulHitlSerializer(session_ttl_sec=10)
    supervisor_key = Ed25519PrivateKey.generate()

    snapshot = serializer.suspend_for_hitl(
        session_id="sess_004",
        task_intent="Firmware upgrade",
        step_index=3,
        memory_digest="sha256:mem3",
        canvas_data={},
        staged_action_name="flash_rom",
        staged_parameters={"version": "2.0"},
    )

    warrant = _sign_warrant(
        signing_key=supervisor_key,
        session_id="sess_004",
        expected_state_hash=snapshot.state_hash,
        adjusted_parameters={},
    )

    # Simulate arrival 50 seconds later (> 10s TTL)
    future_time = snapshot.created_at_epoch + 50
    with pytest.raises(ValueError, match="HALT_SESSION_EXPIRED"):
        serializer.resume_with_warrant(warrant, now_epoch=future_time)

    expired_snap = serializer.get_session("sess_004")
    assert expired_snap is not None
    assert expired_snap.status == SessionStateStatus.EXPIRED


# -----------------------------------------------------------------------------
# Test 5: Double Resumption & Rejection Flow
# -----------------------------------------------------------------------------
def test_5_double_resumption_and_rejection() -> None:
    serializer = StatefulHitlSerializer(session_ttl_sec=3600)
    supervisor_key = Ed25519PrivateKey.generate()

    snapshot = serializer.suspend_for_hitl(
        session_id="sess_005",
        task_intent="Disburse grant",
        step_index=1,
        memory_digest="sha256:mem5",
        canvas_data={},
        staged_action_name="disburse",
        staged_parameters={"grant_id": "G-99"},
    )

    # Session not found check
    bad_warrant = HumanAdjustmentWarrant(
        session_id="non_existent",
        expected_state_hash="sha256:none",
        adjusted_parameters={},
        supervisor_pubkey_hex="00" * 32,
        signature_hex="00" * 64,
    )
    with pytest.raises(ValueError, match="HALT_SESSION_NOT_FOUND"):
        serializer.resume_with_warrant(bad_warrant)

    with pytest.raises(ValueError, match="HALT_SESSION_NOT_FOUND"):
        serializer.reject_session("non_existent", reason="bad id")

    # Rejection flow
    rejected_snap = serializer.reject_session("sess_005", reason="budget exceeded")
    assert rejected_snap.status == SessionStateStatus.REJECTED

    # Attempting to resume a rejected session fails closed
    warrant = _sign_warrant(
        signing_key=supervisor_key,
        session_id="sess_005",
        expected_state_hash=snapshot.state_hash,
        adjusted_parameters={},
    )
    with pytest.raises(ValueError, match="HALT_INVALID_SESSION_STATUS:REJECTED"):
        serializer.resume_with_warrant(warrant)


# -----------------------------------------------------------------------------
# Test 6: Canonical JSON Error Handling
# -----------------------------------------------------------------------------
def test_6_canonical_json_error_handling() -> None:
    # 1. Non-finite float rejections
    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"val": float("nan")})

    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"val": float("inf")})

    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"val": float("-inf")})

    # 2. Non-string key rejection
    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
        canonical_json_v1({42: "val"})

    # 3. Key sorting verification
    sorted_bytes = canonical_json_v1({"z": 1, "a": 2})
    assert sorted_bytes == b'{"a":2,"z":1}'

    # 4. UTF-8 raw byte preservation (ensure_ascii=False)
    unicode_bytes = canonical_json_v1({"symbol": "€"})
    assert unicode_bytes == '{"symbol":"€"}'.encode("utf-8")


# -----------------------------------------------------------------------------
# Test 7: Epistemic Linguistic Compliance (Zero Banned Words)
# -----------------------------------------------------------------------------
def test_7_epistemic_linguistic_compliance() -> None:
    banned_prefixes = [
        "guaran" + "tee",
        "proven univer" + "sally",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
    ]

    files_to_check = [
        Path("src/stateful_hitl.py"),
        Path("tests/test_stateful_hitl.py"),
    ]

    for file_path in files_to_check:
        assert file_path.exists(), f"File {file_path} must exist"
        content = file_path.read_text(encoding="utf-8")
        for banned in banned_prefixes:
            match = re.search(r"\b" + re.escape(banned), content, re.IGNORECASE)
            assert match is None, (
                f"Epistemic boundary violation: found banned term '{banned}' "
                f"in {file_path}"
            )
