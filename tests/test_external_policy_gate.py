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
tests/test_external_policy_gate.py
================================================================================
Test & Falsification Suite for External Policy Boundary Gate (NVIDIA OpenShell).

Evaluated under the stated model:
- Dual-tier NIST SP 800-100 risk boundary evaluation (Appetite & Tolerance).
- Credential exfiltration prevention in guest payload.
- Pinned egress whitelist enforcement and banned protocol defense.
- Ed25519 supervisor step-up warrant validation.
- Cryptographic SCITT execution receipt generation and tamper detection.
- Epistemic linguistic compliance check.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.external_policy_gate import (
    DEFAULT_MAX_DAILY_SPEND_MINOR,
    DEFAULT_MAX_SINGLE_ACTION_MINOR,
    DEFAULT_STEP_UP_THRESHOLD_MINOR,
    EgressExecutionReceipt,
    EgressRequest,
    EnterpriseRiskAppetite,
    ExternalPolicyBoundaryGate,
    OperationRiskTolerance,
    canonical_json_v1,
)


def _sign_step_up(
    supervisor_key: Ed25519PrivateKey,
    request_id: str,
    tenant_id: str,
    action_type: str,
    destination_domain: str,
    amount_minor: int,
) -> Tuple[str, str]:
    payload = {
        "action_type": action_type,
        "amount_minor": amount_minor,
        "destination_domain": destination_domain,
        "request_id": request_id,
        "tenant_id": tenant_id,
    }
    canonical = canonical_json_v1(payload)
    sig = supervisor_key.sign(canonical)
    pub_hex = supervisor_key.public_key().public_bytes_raw().hex()
    return sig.hex(), pub_hex


# -----------------------------------------------------------------------------
# Test 0: Configuration Constants & Immutability
# -----------------------------------------------------------------------------
def test_0_config_constants_and_immutability() -> None:
    assert DEFAULT_MAX_DAILY_SPEND_MINOR == int("10000000")
    assert DEFAULT_MAX_SINGLE_ACTION_MINOR == int("500000")
    assert DEFAULT_STEP_UP_THRESHOLD_MINOR == int("100000")

    appetite = EnterpriseRiskAppetite(tenant_id="ten_0")
    assert appetite.max_daily_spend_minor == DEFAULT_MAX_DAILY_SPEND_MINOR
    assert "api.bank.com" in appetite.allowed_egress_domains

    receipt = EgressExecutionReceipt(
        receipt_caid="caid",
        request_id="req1",
        tenant_id="t1",
        agent_id="a1",
        destination_domain="d1",
        action_type="act",
        amount_minor=100,
        daily_spend_after_minor=100,
        authorized_epoch=1234,
        signer_pubkey_hex="00" * 32,
        signature_hex="00" * 64,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.amount_minor = 200  # type: ignore

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
# Test 1: Positive Control (Valid Egress & Receipt Verification)
# -----------------------------------------------------------------------------
def test_1_positive_control_egress_and_receipt() -> None:
    appetite = EnterpriseRiskAppetite(
        tenant_id="ten_alpha",
        max_daily_spend_minor=1000000,
        allowed_egress_domains=frozenset({"api.bank.com", "ledger.internal"}),
    )
    tolerance = OperationRiskTolerance(
        max_single_action_minor=200000,
        step_up_threshold_minor=50000,
    )
    gate = ExternalPolicyBoundaryGate(appetite, tolerance)
    assert isinstance(gate.public_key, Ed25519PublicKey)
    assert gate.current_daily_spend_minor == 0

    req = EgressRequest(
        request_id="req_001",
        tenant_id="ten_alpha",
        agent_id="agent_guest_1",
        destination_domain="api.bank.com",
        action_type="CHECK_BALANCE",
        payload={"account_number": "NL91ABNA0417164300"},
        risk_tier="T0_INFORMATIONAL",
        amount_minor=0,
    )

    receipt = gate.evaluate_and_dispatch(req)
    assert receipt.receipt_caid.startswith("sha256:")
    assert receipt.request_id == "req_001"
    assert receipt.amount_minor == 0
    assert receipt.daily_spend_after_minor == 0
    assert gate.current_daily_spend_minor == 0

    assert ExternalPolicyBoundaryGate.verify_receipt(receipt) is True
    assert ExternalPolicyBoundaryGate.verify_receipt(receipt, expected_pubkey=gate.public_key) is True


# -----------------------------------------------------------------------------
# Test 2: Banned Protocol Rejection
# -----------------------------------------------------------------------------
def test_2_banned_protocol_rejection() -> None:
    appetite = EnterpriseRiskAppetite(tenant_id="ten_alpha")
    tolerance = OperationRiskTolerance()
    gate = ExternalPolicyBoundaryGate(appetite, tolerance)

    req = EgressRequest(
        request_id="req_bad_proto",
        tenant_id="ten_alpha",
        agent_id="agent_guest_1",
        destination_domain="file:///etc/passwd",
        action_type="EXFILTRATE",
        payload={},
        risk_tier="T0_INFORMATIONAL",
    )
    with pytest.raises(ValueError, match="HALT_BANNED_PROTOCOL_ATTEMPT:file://"):
        gate.evaluate_and_dispatch(req)


# -----------------------------------------------------------------------------
# Test 3: Domain Whitelist Breach
# -----------------------------------------------------------------------------
def test_3_domain_whitelist_breach() -> None:
    appetite = EnterpriseRiskAppetite(
        tenant_id="ten_alpha",
        allowed_egress_domains=frozenset({"api.bank.com"}),
    )
    tolerance = OperationRiskTolerance()
    gate = ExternalPolicyBoundaryGate(appetite, tolerance)

    req = EgressRequest(
        request_id="req_unlisted_domain",
        tenant_id="ten_alpha",
        agent_id="agent_guest_1",
        destination_domain="unauthorized-external-api.com",
        action_type="POST_DATA",
        payload={},
        risk_tier="T1_LOW_RISK",
    )
    with pytest.raises(ValueError, match="HALT_EGRESS_POLICY_VIOLATION"):
        gate.evaluate_and_dispatch(req)


# -----------------------------------------------------------------------------
# Test 4: Credential Exfiltration Defense
# -----------------------------------------------------------------------------
def test_4_credential_exfiltration_defense() -> None:
    appetite = EnterpriseRiskAppetite(
        tenant_id="ten_alpha",
        allowed_egress_domains=frozenset({"api.bank.com"}),
    )
    tolerance = OperationRiskTolerance()
    gate = ExternalPolicyBoundaryGate(appetite, tolerance)

    # 1. Sensitive key attempt
    req_key = EgressRequest(
        request_id="req_leak_key",
        tenant_id="ten_alpha",
        agent_id="agent_guest_1",
        destination_domain="api.bank.com",
        action_type="SEND_DATA",
        payload={"user": "admin", "api_key": "sk-12345678"},
        risk_tier="T1_LOW_RISK",
    )
    with pytest.raises(ValueError, match="HALT_CREDENTIAL_EXFILTRATION: detected key 'api_key'"):
        gate.evaluate_and_dispatch(req_key)

    # 2. Raw .env pattern attempt in value
    req_env = EgressRequest(
        request_id="req_leak_env",
        tenant_id="ten_alpha",
        agent_id="agent_guest_1",
        destination_domain="api.bank.com",
        action_type="SEND_DATA",
        payload={"query": "cat /app/.env"},
        risk_tier="T1_LOW_RISK",
    )
    with pytest.raises(ValueError, match="HALT_CREDENTIAL_EXFILTRATION: detected raw credential pattern"):
        gate.evaluate_and_dispatch(req_env)


# -----------------------------------------------------------------------------
# Test 5: Risk Appetite & Tolerance Boundaries
# -----------------------------------------------------------------------------
def test_5_risk_appetite_and_tolerance_boundaries() -> None:
    appetite = EnterpriseRiskAppetite(
        tenant_id="ten_alpha",
        max_daily_spend_minor=100000,  # €1,000.00
        allowed_egress_domains=frozenset({"api.bank.com"}),
        allowed_risk_tiers=frozenset({"T0_INFORMATIONAL", "T1_LOW_RISK"}),
    )
    tolerance = OperationRiskTolerance(
        max_single_action_minor=20000,  # €200.00
        step_up_threshold_minor=10000,  # €100.00
    )
    gate = ExternalPolicyBoundaryGate(appetite, tolerance)

    # Disallowed risk tier
    req_tier = EgressRequest(
        request_id="req_bad_tier",
        tenant_id="ten_alpha",
        agent_id="agent_1",
        destination_domain="api.bank.com",
        action_type="MUTATE",
        payload={},
        risk_tier="T3_IRREVERSIBLE",
        amount_minor=100,
    )
    with pytest.raises(ValueError, match="HALT_RISK_APPETITE_EXCEEDED"):
        gate.evaluate_and_dispatch(req_tier)

    # Negative amount
    req_neg = EgressRequest(
        request_id="req_neg",
        tenant_id="ten_alpha",
        agent_id="agent_1",
        destination_domain="api.bank.com",
        action_type="MUTATE",
        payload={},
        risk_tier="T1_LOW_RISK",
        amount_minor=-50,
    )
    with pytest.raises(ValueError, match="HALT_NEGATIVE_AMOUNT_REJECTED"):
        gate.evaluate_and_dispatch(req_neg)

    # Single action ceiling breach
    req_single_ceil = EgressRequest(
        request_id="req_ceil",
        tenant_id="ten_alpha",
        agent_id="agent_1",
        destination_domain="api.bank.com",
        action_type="PAY",
        payload={},
        risk_tier="T1_LOW_RISK",
        amount_minor=25000,  # > 20000 ceiling
    )
    with pytest.raises(ValueError, match="HALT_RISK_TOLERANCE_EXCEEDED"):
        gate.evaluate_and_dispatch(req_single_ceil)


# -----------------------------------------------------------------------------
# Test 6: Step-Up Warrant & Daily Accumulation Ceiling
# -----------------------------------------------------------------------------
def test_6_step_up_warrant_and_daily_accumulation() -> None:
    supervisor_key = Ed25519PrivateKey.generate()
    appetite = EnterpriseRiskAppetite(
        tenant_id="ten_alpha",
        max_daily_spend_minor=50000,  # €500.00
        allowed_egress_domains=frozenset({"api.bank.com"}),
    )
    tolerance = OperationRiskTolerance(
        max_single_action_minor=30000,  # €300.00
        step_up_threshold_minor=15000,  # €150.00
    )
    gate = ExternalPolicyBoundaryGate(appetite, tolerance)

    # 1. Missing step-up authorization above threshold (€200.00 >= €150.00)
    req_missing_stepup = EgressRequest(
        request_id="req_step_1",
        tenant_id="ten_alpha",
        agent_id="agent_1",
        destination_domain="api.bank.com",
        action_type="PAY_SUPPLIER",
        payload={},
        risk_tier="T2_MEDIUM_RISK",
        amount_minor=20000,
    )
    with pytest.raises(ValueError, match="HALT_STEP_UP_WARRANT_REQUIRED"):
        gate.evaluate_and_dispatch(req_missing_stepup)

    # Missing pubkey only / missing sig only (kills Or->And on line 291)
    with pytest.raises(ValueError, match="HALT_STEP_UP_WARRANT_REQUIRED"):
        gate.evaluate_and_dispatch(
            dataclasses.replace(req_missing_stepup, step_up_warrant_signature_hex="aa", step_up_supervisor_pubkey_hex="")
        )
    with pytest.raises(ValueError, match="HALT_STEP_UP_WARRANT_REQUIRED"):
        gate.evaluate_and_dispatch(
            dataclasses.replace(req_missing_stepup, step_up_warrant_signature_hex="", step_up_supervisor_pubkey_hex="bb")
        )

    # 2. Signed valid step-up authorization succeeds
    sig_hex, pub_hex = _sign_step_up(
        supervisor_key=supervisor_key,
        request_id="req_step_1",
        tenant_id="ten_alpha",
        action_type="PAY_SUPPLIER",
        destination_domain="api.bank.com",
        amount_minor=20000,
    )
    req_valid_stepup = EgressRequest(
        request_id="req_step_1",
        tenant_id="ten_alpha",
        agent_id="agent_1",
        destination_domain="api.bank.com",
        action_type="PAY_SUPPLIER",
        payload={},
        risk_tier="T2_MEDIUM_RISK",
        amount_minor=20000,
        step_up_warrant_signature_hex=sig_hex,
        step_up_supervisor_pubkey_hex=pub_hex,
    )
    receipt1 = gate.evaluate_and_dispatch(req_valid_stepup)
    assert receipt1.amount_minor == 20000
    assert receipt1.daily_spend_after_minor == 20000
    assert gate.current_daily_spend_minor == 20000

    # 3. Invalid signature on step-up warrant rejected
    req_bad_sig = EgressRequest(
        request_id="req_step_2",
        tenant_id="ten_alpha",
        agent_id="agent_1",
        destination_domain="api.bank.com",
        action_type="PAY_SUPPLIER",
        payload={},
        risk_tier="T2_MEDIUM_RISK",
        amount_minor=20000,
        step_up_warrant_signature_hex="00" * 64,
        step_up_supervisor_pubkey_hex=pub_hex,
    )
    with pytest.raises(ValueError, match="HALT_UNAUTHORIZED_STEP_UP"):
        gate.evaluate_and_dispatch(req_bad_sig)

    # 4. Daily accumulation ceiling reached (current: 20000, adding 35000 > 50000)
    sig_hex2, pub_hex2 = _sign_step_up(
        supervisor_key=supervisor_key,
        request_id="req_step_3",
        tenant_id="ten_alpha",
        action_type="PAY_SUPPLIER",
        destination_domain="api.bank.com",
        amount_minor=35000,
    )
    # But 35000 exceeds max_single_action_minor (30000), so test 30000
    sig_hex3, pub_hex3 = _sign_step_up(
        supervisor_key=supervisor_key,
        request_id="req_step_4",
        tenant_id="ten_alpha",
        action_type="PAY_SUPPLIER",
        destination_domain="api.bank.com",
        amount_minor=30000,
    )
    # First dispatch 25000 (total will be 45000 <= 50000)
    sig_hex4, pub_hex4 = _sign_step_up(
        supervisor_key=supervisor_key,
        request_id="req_step_5",
        tenant_id="ten_alpha",
        action_type="PAY_SUPPLIER",
        destination_domain="api.bank.com",
        amount_minor=25000,
    )
    req_step4 = EgressRequest(
        request_id="req_step_5",
        tenant_id="ten_alpha",
        agent_id="agent_1",
        destination_domain="api.bank.com",
        action_type="PAY_SUPPLIER",
        payload={},
        risk_tier="T2_MEDIUM_RISK",
        amount_minor=25000,
        step_up_warrant_signature_hex=sig_hex4,
        step_up_supervisor_pubkey_hex=pub_hex4,
    )
    gate.evaluate_and_dispatch(req_step4)
    assert gate.current_daily_spend_minor == 45000

    # Next dispatch of 10000 would exceed daily limit (55000 > 50000)
    req_exceed_daily = EgressRequest(
        request_id="req_step_6",
        tenant_id="ten_alpha",
        agent_id="agent_1",
        destination_domain="api.bank.com",
        action_type="PAY_SMALL",
        payload={},
        risk_tier="T2_MEDIUM_RISK",
        amount_minor=10000,
    )
    with pytest.raises(ValueError, match="HALT_DAILY_APPETITE_EXCEEDED"):
        gate.evaluate_and_dispatch(req_exceed_daily)


# -----------------------------------------------------------------------------
# Test 7: Receipt Tamper Detection & Canonical JSON
# -----------------------------------------------------------------------------
def test_7_receipt_tamper_and_canonical_json() -> None:
    appetite = EnterpriseRiskAppetite(tenant_id="ten_alpha")
    tolerance = OperationRiskTolerance()
    gate = ExternalPolicyBoundaryGate(appetite, tolerance)

    req = EgressRequest(
        request_id="req_tamper",
        tenant_id="ten_alpha",
        agent_id="agent_1",
        destination_domain="api.bank.com",
        action_type="PROBE",
        payload={},
        risk_tier="T0_INFORMATIONAL",
        amount_minor=0,
    )
    receipt = gate.evaluate_and_dispatch(req)
    assert ExternalPolicyBoundaryGate.verify_receipt(receipt) is True

    # Tampered recipient payload
    tampered_receipt = EgressExecutionReceipt(
        receipt_caid=receipt.receipt_caid,
        request_id=receipt.request_id,
        tenant_id=receipt.tenant_id,
        agent_id="hacked_agent",
        destination_domain=receipt.destination_domain,
        action_type=receipt.action_type,
        amount_minor=receipt.amount_minor,
        daily_spend_after_minor=receipt.daily_spend_after_minor,
        authorized_epoch=receipt.authorized_epoch,
        signer_pubkey_hex=receipt.signer_pubkey_hex,
        signature_hex=receipt.signature_hex,
    )
    assert ExternalPolicyBoundaryGate.verify_receipt(tampered_receipt) is False

    # Corrupted signature
    tampered_sig = EgressExecutionReceipt(
        receipt_caid=receipt.receipt_caid,
        request_id=receipt.request_id,
        tenant_id=receipt.tenant_id,
        agent_id=receipt.agent_id,
        destination_domain=receipt.destination_domain,
        action_type=receipt.action_type,
        amount_minor=receipt.amount_minor,
        daily_spend_after_minor=receipt.daily_spend_after_minor,
        authorized_epoch=receipt.authorized_epoch,
        signer_pubkey_hex=receipt.signer_pubkey_hex,
        signature_hex="00" * 64,
    )
    assert ExternalPolicyBoundaryGate.verify_receipt(tampered_sig) is False

    # Wrong expected pubkey
    foreign_key = Ed25519PrivateKey.generate().public_key()
    assert ExternalPolicyBoundaryGate.verify_receipt(receipt, expected_pubkey=foreign_key) is False

    # Canonical JSON checks
    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"f": float("nan")})

    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
        canonical_json_v1({123: "val"})


# -----------------------------------------------------------------------------
# Test 8: Epistemic Linguistic Compliance (Zero Banned Words)
# -----------------------------------------------------------------------------
def test_8_epistemic_linguistic_compliance() -> None:
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
        Path("src/external_policy_gate.py"),
        Path("tests/test_external_policy_gate.py"),
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
