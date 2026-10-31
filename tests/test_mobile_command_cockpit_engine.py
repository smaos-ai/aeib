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
tests/test_mobile_command_cockpit_engine.py
================================================================================
Comprehensive verification suite for MobileCommandCockpitEngine.
"""

from __future__ import annotations

import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.mobile_command_cockpit_engine import (
    CockpitCommandType,
    CockpitTelemetrySnapshot,
    MobileCommandCockpitEngine,
    SwarmExecutionState,
)


@pytest.fixture
def operator_keypair():
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_hex = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    return priv, pub_hex


def test_telemetry_snapshot_and_subagent_tracking(operator_keypair):
    _, pub_hex = operator_keypair
    cockpit = MobileCommandCockpitEngine(operator_pubkey_hex=pub_hex)

    cockpit.register_subagent("agent-writer-1", "worktrees/feat-1")
    cockpit.register_subagent("agent-critic-2", "worktrees/feat-2")
    cockpit.set_pending_mandates_count(3)

    snap = cockpit.get_telemetry_snapshot()
    assert snap.swarm_state == SwarmExecutionState.RUNNING
    assert snap.active_subagents_count == 2
    assert snap.ansi_50_breaker_tripped is False
    assert snap.ansi_86_lockout_active is False
    assert snap.pending_ap2_mandates_count == 3
    assert snap.snapshot_caid.startswith("sha256:")
    assert snap.host_physical_memory_bytes == 17179869184
    assert snap.thermal_state_raw == 0

    d = snap.to_dict()
    assert d["host_physical_memory_bytes"] == 17179869184
    assert d["thermal_state_raw"] == 0
    assert d["commissioning_stage"] == "STAGE_6_READY_FOR_SERVICE"

    body_check = {
        "timestamp_utc": d["timestamp_utc"],
        "swarm_state": d["swarm_state"],
        "active_subagents_count": d["active_subagents_count"],
        "ansi_50_breaker_tripped": d["ansi_50_breaker_tripped"],
        "ansi_86_lockout_active": d["ansi_86_lockout_active"],
        "commissioning_stage": d["commissioning_stage"],
        "pending_ap2_mandates_count": d["pending_ap2_mandates_count"],
        "host_physical_memory_bytes": d["host_physical_memory_bytes"],
        "thermal_state_raw": d["thermal_state_raw"],
    }
    assert snap.snapshot_caid == f"sha256:{hashlib.sha256(encode_jcs(body_check)).hexdigest()}"

    with pytest.raises((AttributeError, TypeError)):
        snap.thermal_state_raw = 1  # type: ignore

    cockpit.unregister_subagent("agent-writer-1")
    snap2 = cockpit.get_telemetry_snapshot()
    assert snap2.active_subagents_count == 1


def test_pause_and_resume_swarm(operator_keypair):
    _, pub_hex = operator_keypair
    cockpit = MobileCommandCockpitEngine(operator_pubkey_hex=pub_hex)

    ok, msg = cockpit.dispatch_remote_command(CockpitCommandType.PAUSE_SWARM, {})
    assert ok is True
    assert msg == "SWARM_PAUSED"
    assert cockpit.get_telemetry_snapshot().swarm_state == SwarmExecutionState.PAUSED_BY_OPERATOR

    ok_res, msg_res = cockpit.dispatch_remote_command(CockpitCommandType.RESUME_SWARM, {})
    assert ok_res is True
    assert msg_res == "SWARM_RESUMED"
    assert cockpit.get_telemetry_snapshot().swarm_state == SwarmExecutionState.RUNNING


def test_emergency_andon_stop_trips_breakers(operator_keypair):
    _, pub_hex = operator_keypair
    cockpit = MobileCommandCockpitEngine(operator_pubkey_hex=pub_hex)

    ok, msg = cockpit.dispatch_remote_command(CockpitCommandType.TRIGGER_EMERGENCY_ANDON_STOP, {})
    assert ok is True
    assert msg == "EMERGENCY_ANDON_STOP_LATCHED"

    snap = cockpit.get_telemetry_snapshot()
    assert snap.swarm_state == SwarmExecutionState.EMERGENCY_HALTED
    assert snap.ansi_50_breaker_tripped is True
    assert snap.ansi_86_lockout_active is True

    # Cannot resume or pause while emergency halted
    ok_p, msg_p = cockpit.dispatch_remote_command(CockpitCommandType.PAUSE_SWARM, {})
    assert ok_p is False
    assert msg_p == "ERR_CANNOT_PAUSE_WHILE_EMERGENCY_HALTED"

    ok_r, msg_r = cockpit.dispatch_remote_command(CockpitCommandType.RESUME_SWARM, {})
    assert ok_r is False
    assert "ERR_CANNOT_RESUME" in msg_r


def test_clear_ansi86_lockout_nonce_replay_defense(operator_keypair):
    priv, pub_hex = operator_keypair
    cockpit = MobileCommandCockpitEngine(operator_pubkey_hex=pub_hex)

    # Trip emergency halt to latch ANSI 86 lockout
    cockpit.dispatch_remote_command(CockpitCommandType.TRIGGER_EMERGENCY_ANDON_STOP, {})
    assert cockpit.get_telemetry_snapshot().ansi_86_lockout_active is True

    # 1. Sign valid clearance payload
    nonce = "nonce-random-12345"
    task_id = "task-remediation-001"
    payload = {
        "action": "CLEAR_ANSI86_LOCKOUT",
        "clearance_nonce": nonce,
        "task_id": task_id,
    }
    canonical_bytes = encode_jcs(payload)
    sig_hex = priv.sign(canonical_bytes).hex()

    ok, msg = cockpit.dispatch_remote_command(
        command_type=CockpitCommandType.CLEAR_ANSI86_LOCKOUT,
        command_payload=payload,
        signature_hex=sig_hex,
    )
    assert ok is True
    assert msg == "ANSI86_LOCKOUT_CLEARED"

    snap = cockpit.get_telemetry_snapshot()
    assert snap.ansi_86_lockout_active is False
    assert snap.ansi_50_breaker_tripped is False
    assert snap.swarm_state == SwarmExecutionState.RUNNING

    # 2. Missing signature
    ok_no_sig, msg_no_sig = cockpit.dispatch_remote_command(
        command_type=CockpitCommandType.CLEAR_ANSI86_LOCKOUT,
        command_payload={"clearance_nonce": "n2", "task_id": task_id},
        signature_hex=None,
    )
    assert ok_no_sig is False
    assert msg_no_sig == "ERR_SIGNATURE_REQUIRED"

    # 3. Missing nonce or task_id
    ok_no_n, msg_no_n = cockpit.dispatch_remote_command(
        command_type=CockpitCommandType.CLEAR_ANSI86_LOCKOUT,
        command_payload={"task_id": task_id},
        signature_hex=sig_hex,
    )
    assert ok_no_n is False
    assert msg_no_n == "ERR_MISSING_NONCE_OR_TASK_ID"

    ok_no_t, msg_no_t = cockpit.dispatch_remote_command(
        command_type=CockpitCommandType.CLEAR_ANSI86_LOCKOUT,
        command_payload={"clearance_nonce": "n3"},
        signature_hex=sig_hex,
    )
    assert ok_no_t is False
    assert msg_no_t == "ERR_MISSING_NONCE_OR_TASK_ID"

    # 4. Attempting to replay the exact same nonce fails closed
    ok_replay, msg_replay = cockpit.dispatch_remote_command(
        command_type=CockpitCommandType.CLEAR_ANSI86_LOCKOUT,
        command_payload=payload,
        signature_hex=sig_hex,
    )
    assert ok_replay is False
    assert msg_replay == "ERR_NONCE_REPLAY_DETECTED"

    # 5. Forged signature fails
    other_priv = ed25519.Ed25519PrivateKey.generate()
    payload_bad = {
        "action": "CLEAR_ANSI86_LOCKOUT",
        "clearance_nonce": "nonce-fresh-9999",
        "task_id": task_id,
    }
    sig_bad = other_priv.sign(encode_jcs(payload_bad)).hex()
    ok_bad, msg_bad = cockpit.dispatch_remote_command(
        command_type=CockpitCommandType.CLEAR_ANSI86_LOCKOUT,
        command_payload=payload_bad,
        signature_hex=sig_bad,
    )
    assert ok_bad is False
    assert msg_bad == "ERR_OPERATOR_SIGNATURE_INVALID"

    # 6. Unknown command
    ok_unk, msg_unk = cockpit.dispatch_remote_command(
        command_type="UNKNOWN_COMMAND",  # type: ignore
        command_payload={},
    )
    assert ok_unk is False
    assert msg_unk == "ERR_UNKNOWN_COMMAND"

    # 7. Resume while ANSI_86_LOCKED_OUT
    cockpit._swarm_state = SwarmExecutionState.ANSI_86_LOCKED_OUT
    ok_res_lock, msg_res_lock = cockpit.dispatch_remote_command(
        command_type=CockpitCommandType.RESUME_SWARM,
        command_payload={},
    )
    assert ok_res_lock is False
    assert "ERR_CANNOT_RESUME_FROM_ANSI_86_LOCKED_OUT" in msg_res_lock


def test_input_validation():
    with pytest.raises(ValueError, match="operator_pubkey_hex"):
        MobileCommandCockpitEngine(operator_pubkey_hex="")
