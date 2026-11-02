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
tests/test_pre_tool_use_chain.py
================================================================================
Test suite for Pre-Tool Use Interception Hook Chain (Osprey ALS Pattern).
Evaluated under the stated model (scaffold verifier).
Zero-mock, deterministic test assertions and mutation adequacy verification.
"""

from __future__ import annotations

import dataclasses
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.biometric_hitl_gate import (
    AdjudicationVerdict,
    BiometricTelemetry,
    CircadianPhase,
)
from src.pre_tool_use_chain import (
    HookExecutionVerdict,
    PreToolUseHookChain,
    ToolCallIntent,
)


def test_pre_tool_use_dataclass_frozenness() -> None:
    intent = ToolCallIntent(
        tool_name="test_tool",
        arguments={"x": 1},
        tenant_id="tenant-1",
        risk_tier="T1",
        is_write=False,
        agent_id="agent-1",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        intent.tool_name = "modified"  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        intent.is_write = True  # type: ignore[misc]

    verdict = HookExecutionVerdict(
        passed=True,
        reason_code="OK",
        stage="STAGE_X",
        adjudication_receipt=None,
        execution_review=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.passed = False  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.stage = "STAGE_Y"  # type: ignore[misc]


def test_kill_switch_stage() -> None:
    chain = PreToolUseHookChain(
        global_writes_enabled=True,
        tenant_writes_disabled=["tenant-halted"],
    )

    # Read-only operations bypass write kill switches
    intent_ro = ToolCallIntent(
        tool_name="query_data",
        arguments={"id": 100},
        tenant_id="tenant-halted",
        risk_tier="T1",
        is_write=False,
        agent_id="agent-01",
    )
    ok_ro, reason_ro = chain.check_kill_switch(intent_ro)
    assert ok_ro is True
    assert reason_ro == "OK_READ_ONLY_CALL"

    # Write operation on halted tenant fails
    intent_tenant_fail = ToolCallIntent(
        tool_name="update_data",
        arguments={"id": 100, "val": 2},
        tenant_id="tenant-halted",
        risk_tier="T2",
        is_write=True,
        agent_id="agent-01",
    )
    ok_tf, reason_tf = chain.check_kill_switch(intent_tenant_fail)
    assert ok_tf is False
    assert reason_tf == "HALT_TENANT_WRITE_DISABLED"

    # Write operation on global halt fails
    chain_global_off = PreToolUseHookChain(global_writes_enabled=False)
    intent_global_fail = ToolCallIntent(
        tool_name="update_data",
        arguments={"id": 100},
        tenant_id="tenant-active",
        risk_tier="T2",
        is_write=True,
        agent_id="agent-01",
    )
    ok_gf, reason_gf = chain_global_off.check_kill_switch(intent_global_fail)
    assert ok_gf is False
    assert reason_gf == "HALT_GLOBAL_WRITE_DISABLED"

    # Write operation with all switches open passes
    ok_pass, reason_pass = chain.check_kill_switch(intent_global_fail)
    assert ok_pass is True
    assert reason_pass == "OK_KILL_SWITCH_OPEN"

    chain_all_open = PreToolUseHookChain(global_writes_enabled=True, tenant_writes_disabled=[])
    ok_open, reason_open = chain_all_open.check_kill_switch(intent_global_fail)
    assert ok_open is True
    assert reason_open == "OK_KILL_SWITCH_OPEN"

    # Default initialization has global_writes_enabled=True and empty disabled tenants
    chain_default = PreToolUseHookChain()
    assert chain_default.global_writes_enabled is True
    assert len(chain_default.tenant_writes_disabled) == 0
    ok_def, reason_def = chain_default.check_kill_switch(intent_global_fail)
    assert ok_def is True
    assert reason_def == "OK_KILL_SWITCH_OPEN"


def test_parameter_limits_stage() -> None:
    limits = {
        "adjust_beam": {
            "energy_gev": (1.0, 3.5),
            "attenuation_db": (0.0, 60.0),
        }
    }
    chain = PreToolUseHookChain(argument_limits=limits)

    # Tool with no limits configured
    intent_nolim = ToolCallIntent(
        tool_name="unconstrained_tool",
        arguments={"energy": 999.0},
        tenant_id="t1",
        risk_tier="T1",
        is_write=False,
        agent_id="a1",
    )
    ok_nl, reason_nl = chain.check_limits(intent_nolim)
    assert ok_nl is True
    assert reason_nl == "OK_NO_LIMITS_CONFIGURED"

    # Tool within limits
    intent_in_bounds = ToolCallIntent(
        tool_name="adjust_beam",
        arguments={"energy_gev": 2.5, "attenuation_db": 10.0},
        tenant_id="t1",
        risk_tier="T2",
        is_write=True,
        agent_id="a1",
    )
    ok_ib, reason_ib = chain.check_limits(intent_in_bounds)
    assert ok_ib is True
    assert reason_ib == "OK_LIMITS_SATISFIED"

    # Tool with out of bounds parameter
    intent_oob = ToolCallIntent(
        tool_name="adjust_beam",
        arguments={"energy_gev": 5.0},
        tenant_id="t1",
        risk_tier="T2",
        is_write=True,
        agent_id="a1",
    )
    ok_oob, reason_oob = chain.check_limits(intent_oob)
    assert ok_oob is False
    assert reason_oob == "HALT_ARGUMENT_OUT_OF_BOUNDS"

    # Tool with invalid argument type (e.g., bool or string)
    intent_bool = ToolCallIntent(
        tool_name="adjust_beam",
        arguments={"energy_gev": True},
        tenant_id="t1",
        risk_tier="T2",
        is_write=True,
        agent_id="a1",
    )
    ok_b, reason_b = chain.check_limits(intent_bool)
    assert ok_b is False
    assert reason_b == "ERR_LIMIT_TYPE_INVALID"

    intent_str = ToolCallIntent(
        tool_name="adjust_beam",
        arguments={"energy_gev": "3.0"},
        tenant_id="t1",
        risk_tier="T2",
        is_write=True,
        agent_id="a1",
    )
    ok_s, reason_s = chain.check_limits(intent_str)
    assert ok_s is False
    assert reason_s == "ERR_LIMIT_TYPE_INVALID"


def test_biometric_hitl_stage() -> None:
    priv = Ed25519PrivateKey.generate()
    chain = PreToolUseHookChain(signing_key=priv, historical_urgency_rate=0.20)

    # T1 / T2 intent exempt from biometric gate
    intent_t2 = ToolCallIntent(
        tool_name="read_spectrum",
        arguments={"channel": 1},
        tenant_id="t1",
        risk_tier="T2",
        is_write=False,
        agent_id="a1",
    )
    ok_t2, reason_t2, rc_t2 = chain.check_approval(intent_t2)
    assert ok_t2 is True
    assert reason_t2 == "OK_TIER_EXEMPT_FROM_BIOMETRIC_GATE"
    assert rc_t2 is None

    # T3 intent with missing telemetry
    intent_t3 = ToolCallIntent(
        tool_name="fire_photon_shutter",
        arguments={"shutter_id": 4},
        tenant_id="t1",
        risk_tier="T3",
        is_write=True,
        agent_id="a1",
    )
    ok_t3_missing, reason_t3_missing, rc_missing = chain.check_approval(
        intent=intent_t3,
        telemetry=None,
    )
    assert ok_t3_missing is False
    assert reason_t3_missing == AdjudicationVerdict.HALT_MISSING_TELEMETRY.value
    assert rc_missing is not None
    assert rc_missing.verdict == AdjudicationVerdict.HALT_MISSING_TELEMETRY
    assert rc_missing.verify_signature() is True

    # T3 intent with healthy biometric telemetry
    tel_healthy = BiometricTelemetry(
        hrv_ms=65.0,
        cognitive_load_bps=3200,
        circadian_phase=CircadianPhase.PEAK_ALERTNESS,
        keystroke_entropy=3.1,
        timestamp_ns=1700000000000,
    )
    ok_t3_pass, reason_t3_pass, rc_pass = chain.check_approval(
        intent=intent_t3,
        telemetry=tel_healthy,
        agent_claimed_urgency=False,
        human_intent_hash="sha256:0123456789abcdef",
        timestamp_ns=1700000000000,
    )
    assert ok_t3_pass is True
    assert reason_t3_pass == "OK_BIOMETRIC_APPROVAL_GRANTED"
    assert rc_pass is not None
    assert rc_pass.verdict == AdjudicationVerdict.ALLOW_T3_APPROVAL
    assert rc_pass.verify_signature() is True

    # Test dynamic timestamp assignment when timestamp_ns=None
    import time
    t_start = time.time_ns()
    ok_dyn, _, rc_dyn = chain.check_approval(
        intent=intent_t3,
        telemetry=tel_healthy,
        agent_claimed_urgency=False,
        human_intent_hash="sha256:0123456789abcdef",
        timestamp_ns=None,
    )
    t_end = time.time_ns()
    assert ok_dyn is True
    assert rc_dyn is not None
    assert t_start <= rc_dyn.timestamp_ns <= t_end

    # T3 intent with urgency spoofing detection
    chain_low_base = PreToolUseHookChain(signing_key=priv, historical_urgency_rate=0.01)
    ok_spoof, reason_spoof, rc_spoof = chain_low_base.check_approval(
        intent=intent_t3,
        telemetry=tel_healthy,
        agent_claimed_urgency=True,
    )
    assert ok_spoof is False
    assert reason_spoof == AdjudicationVerdict.HALT_URGENCY_SPOOFING.value
    assert rc_spoof is not None
    assert rc_spoof.verdict == AdjudicationVerdict.HALT_URGENCY_SPOOFING


def test_generate_pre_execution_review() -> None:
    chain = PreToolUseHookChain()
    intent = ToolCallIntent(
        tool_name="set_undulator_gap",
        arguments={"gap_mm": 12.5, "speed": 1},
        tenant_id="beamline-07",
        risk_tier="T2",
        is_write=True,
        agent_id="synchrotron-ai-01",
    )
    review = chain.generate_pre_execution_review(intent)
    assert "# === OSPREY ALS PRE-EXECUTION REVIEW SCRIPT ===" in review
    assert "# Tool:      set_undulator_gap" in review
    assert "# Tenant:    beamline-07" in review
    assert "# Agent:     synchrotron-ai-01" in review
    assert "# Risk Tier: T2" in review
    assert "# Write Op:  True" in review
    assert '"gap_mm":12.5' in review or '"gap_mm": 12.5' in review
    assert "# Status:    READY FOR OPERATOR ATTESTATION" in review


def test_evaluate_chain_end_to_end() -> None:
    priv = Ed25519PrivateKey.generate()
    limits = {
        "dispatch_transfer": {
            "amount": (1.0, 1000.0),
        }
    }
    chain = PreToolUseHookChain(
        global_writes_enabled=True,
        tenant_writes_disabled=["quarantine-corp"],
        argument_limits=limits,
        signing_key=priv,
        historical_urgency_rate=0.20,
    )

    # 1. Blocked at Kill Switch
    intent_ks = ToolCallIntent(
        tool_name="dispatch_transfer",
        arguments={"amount": 50.0},
        tenant_id="quarantine-corp",
        risk_tier="T3",
        is_write=True,
        agent_id="bot-1",
    )
    v_ks = chain.evaluate_chain(intent_ks)
    assert v_ks.passed is False
    assert v_ks.stage == "KILL_SWITCH"
    assert v_ks.reason_code == "HALT_TENANT_WRITE_DISABLED"
    assert v_ks.adjudication_receipt is None
    assert v_ks.execution_review is None

    # 2. Blocked at Limits
    intent_lim = ToolCallIntent(
        tool_name="dispatch_transfer",
        arguments={"amount": 5000.0},
        tenant_id="valid-corp",
        risk_tier="T3",
        is_write=True,
        agent_id="bot-1",
    )
    v_lim = chain.evaluate_chain(intent_lim)
    assert v_lim.passed is False
    assert v_lim.stage == "LIMITS"
    assert v_lim.reason_code == "HALT_ARGUMENT_OUT_OF_BOUNDS"
    assert v_lim.adjudication_receipt is None
    assert v_lim.execution_review is None

    # 3. Blocked at Approval (missing biometric telemetry for T3)
    intent_app = ToolCallIntent(
        tool_name="dispatch_transfer",
        arguments={"amount": 500.0},
        tenant_id="valid-corp",
        risk_tier="T3",
        is_write=True,
        agent_id="bot-1",
    )
    v_app = chain.evaluate_chain(intent_app, telemetry=None)
    assert v_app.passed is False
    assert v_app.stage == "APPROVAL"
    assert v_app.reason_code == AdjudicationVerdict.HALT_MISSING_TELEMETRY.value
    assert v_app.adjudication_receipt is not None
    assert v_app.execution_review is None

    # 4. Fully Approved Dispatch
    tel = BiometricTelemetry(
        hrv_ms=58.0,
        cognitive_load_bps=4000,
        circadian_phase=CircadianPhase.NORMAL,
        keystroke_entropy=3.2,
        timestamp_ns=1700000000000,
    )
    v_ok = chain.evaluate_chain(
        intent=intent_app,
        telemetry=tel,
        timestamp_ns=1700000000000,
    )
    assert v_ok.passed is True
    assert v_ok.stage == "DISPATCH_READY"
    assert v_ok.reason_code == "OK_PRE_TOOL_USE_PASSED"
    assert v_ok.adjudication_receipt is not None
    assert v_ok.adjudication_receipt.verdict == AdjudicationVerdict.ALLOW_T3_APPROVAL
    assert v_ok.adjudication_receipt.verify_signature() is True
    assert v_ok.execution_review is not None
    assert "dispatch_transfer" in v_ok.execution_review


def test_verify_dispatch_binding_and_post_approval_substitution_detection() -> None:
    priv = Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes_raw().hex()

    chain = PreToolUseHookChain(signing_key=priv)
    intent = ToolCallIntent(
        tool_name="dispatch_transfer",
        arguments={"amount": 500.0},
        tenant_id="valid-corp",
        risk_tier="T3",
        is_write=True,
        agent_id="bot-1",
    )
    digest = intent.canonical_act_digest()
    assert digest.startswith("sha256:")
    assert len(digest) == 71

    # Modified arguments produce different digest
    intent_modified = ToolCallIntent(
        tool_name="dispatch_transfer",
        arguments={"amount": 5000.0},
        tenant_id="valid-corp",
        risk_tier="T3",
        is_write=True,
        agent_id="bot-1",
    )
    assert intent_modified.canonical_act_digest() != digest

    tel = BiometricTelemetry(
        hrv_ms=58.0,
        cognitive_load_bps=4000,
        circadian_phase=CircadianPhase.NORMAL,
        keystroke_entropy=3.2,
        timestamp_ns=1700000000000,
    )
    verdict = chain.evaluate_chain(intent=intent, telemetry=tel, timestamp_ns=1700000000000)
    receipt = verdict.adjudication_receipt
    assert receipt is not None

    # 1. Missing receipt fails closed
    ok_none, reason_none = chain.verify_dispatch_binding(intent, None, pub_hex)
    assert ok_none is False
    assert reason_none == "HALT_MISSING_APPROVAL_RECEIPT"

    # 2. Non-ALLOW receipt verdict fails closed
    disallowed_receipt = dataclasses.replace(
        receipt, verdict=AdjudicationVerdict.HALT_MISSING_TELEMETRY
    )
    ok_dis, reason_dis = chain.verify_dispatch_binding(intent, disallowed_receipt, pub_hex)
    assert ok_dis is False
    assert reason_dis == "HALT_RECEIPT_NOT_ALLOW"

    # 3. Unpinned issuer public key fails closed
    ok_unpin, reason_unpin = chain.verify_dispatch_binding(intent, receipt, "00" * 32)
    assert ok_unpin is False
    assert reason_unpin == "HALT_UNPINNED_RECEIPT_ISSUER"

    # 4. Tampered signature fails closed
    import base64
    tampered_sig_receipt = dataclasses.replace(
        receipt, signature_b64=base64.b64encode(b"\xff" * 64).decode("ascii")
    )
    ok_sig, reason_sig = chain.verify_dispatch_binding(intent, tampered_sig_receipt, pub_hex)
    assert ok_sig is False
    assert reason_sig == "HALT_RECEIPT_SIGNATURE_INVALID"

    # 5. Post-approval substitution (different intent with approved receipt) fails closed
    ok_sub, reason_sub = chain.verify_dispatch_binding(intent_modified, receipt, pub_hex)
    assert ok_sub is False
    assert reason_sub == "HALT_POST_APPROVAL_SUBSTITUTION"

    # 6. Valid binding succeeds
    ok_valid, reason_valid = chain.verify_dispatch_binding(intent, receipt, pub_hex)
    assert ok_valid is True
    assert reason_valid == "OK_DISPATCH_BOUND_TO_APPROVED_ACT"

