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
tests/test_artemis_device_and_plugin_boundary.py
================================================================================
Comprehensive verification suite for Artemis Mobile Device Actuator &
Hermes Edge Plugin Boundary Gating Architecture.
Evaluated under the stated model. Prototype scaffold for AEIB Station 1.
"""

import base64
import hashlib
import time
from pathlib import Path
from typing import Dict, List

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.artemis_device_and_plugin_boundary import (
    ADB_SHELL,
    AUTHORIZE_BIOMETRIC,
    INPUT_TEXT,
    LAUNCH_INTENT,
    MODIFY_SYSTEM_SETTING,
    OPEN_PAYMENT_APP,
    READ_SCREEN,
    SUBMIT_CREDENTIAL,
    TAP_COORDINATE,
    HALT_AGENT_BUDGET_EXCEEDED,
    HALT_AGENT_LIFECYCLE_INVALID,
    HALT_DEVICE_ACTION_CAID_MISMATCH,
    HALT_DEVICE_ACTION_DELEGATION_MISMATCH,
    HALT_DEVICE_ACTION_REQUIRES_STEP_UP,
    HALT_DEVICE_ACTION_SPONSOR_SIGNATURE_INVALID,
    HALT_DEVICE_ACTION_TYPE_NOT_PERMITTED,
    HALT_DEVICE_ACTION_WARRANT_EXPIRED,
    HALT_PLUGIN_CAPABILITY_ATTENUATION_VIOLATION,
    HALT_PLUGIN_CODE_INTEGRITY_MISMATCH,
    HALT_PLUGIN_DYNAMIC_CODE_REJECTED,
    HALT_PLUGIN_SIGNATURE_INVALID,
    AdecsAgentLifecycleAutomaton,
    AdecsAgentState,
    AgentBudgetExceededHaltError,
    AgentLifecycleInvalidHaltError,
    ArtemisDeviceActuatorGate,
    DeviceAction,
    HermesASTSecurityScanner,
    HermesEdgePluginGate,
    HermesPluginManifest,
    PluginCapabilityAttenuationError,
    PluginCodeIntegrityError,
    PluginDynamicCodeRejectedError,
    PluginSignatureInvalidError,
    Rfc9470StepUpToken,
    SponsorDeviceActionWarrant,
    StepUpRequiredHaltError,
    WarrantVerificationHaltError,
)
from src.jcs_canonicalizer import encode_jcs


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def crypto_actors():
    """Generates real Ed25519 keypairs for sponsor, supervisor, and publisher."""
    sponsor_priv = Ed25519PrivateKey.generate()
    supervisor_priv = Ed25519PrivateKey.generate()
    publisher_priv = Ed25519PrivateKey.generate()
    attacker_priv = Ed25519PrivateKey.generate()

    pub_bytes = publisher_priv.public_key().public_bytes_raw()
    publisher_pub_b64 = base64.b64encode(pub_bytes).decode("ascii")

    return {
        "sponsor_priv": sponsor_priv,
        "sponsor_pub": sponsor_priv.public_key(),
        "sponsor_did": "did:aeib:sponsor-test-01",
        "supervisor_priv": supervisor_priv,
        "supervisor_pub": supervisor_priv.public_key(),
        "supervisor_did": "did:aeib:supervisor-hitl-01",
        "publisher_priv": publisher_priv,
        "publisher_pub": publisher_priv.public_key(),
        "publisher_pub_b64": publisher_pub_b64,
        "attacker_priv": attacker_priv,
        "attacker_pub": attacker_priv.public_key(),
    }


# ==============================================================================
# 1. Artemis Device Actuator Gate Tests
# ==============================================================================

def test_artemis_valid_standard_action_succeeds(crypto_actors):
    """Evaluates that a standard action with a valid CAID warrant dispatches successfully."""
    gate = ArtemisDeviceActuatorGate()
    gate.register_sponsor_key(crypto_actors["sponsor_did"], crypto_actors["sponsor_pub"])

    now = int(time.time())
    action = DeviceAction(
        action_type=TAP_COORDINATE,
        target_device_id="android_pixel_01",
        agent_id="agent-007",
        parameters={"x": 300, "y": 600},
        nonce="nonce-tap-1",
        timestamp=now,
    )
    caid = action.compute_caid()

    warrant = SponsorDeviceActionWarrant(
        warrant_id="warrant-tap-1",
        sponsor_did=crypto_actors["sponsor_did"],
        agent_id="agent-007",
        target_device_id="android_pixel_01",
        action_caid=caid,
        allowed_action_types=[TAP_COORDINATE, READ_SCREEN],
        issued_at=now,
        expires_at=now + 600,
    )
    warrant.sign(crypto_actors["sponsor_priv"])

    receipt = gate.verify_and_dispatch(action, warrant, now_ts=now)
    assert receipt["status"] == "AUTHORIZED"
    assert receipt["decision"] == "DISPATCHED"
    assert receipt["action_caid"] == caid
    assert receipt["step_up_applied"] is False


def test_artemis_caid_mismatch_fails_closed(crypto_actors):
    """Evaluates that tampering with action parameters causes CAID mismatch rejection."""
    gate = ArtemisDeviceActuatorGate()
    gate.register_sponsor_key(crypto_actors["sponsor_did"], crypto_actors["sponsor_pub"])

    now = int(time.time())
    action = DeviceAction(
        action_type=TAP_COORDINATE,
        target_device_id="android_pixel_01",
        agent_id="agent-007",
        parameters={"x": 300, "y": 600},
        nonce="nonce-tap-1",
        timestamp=now,
    )
    warrant = SponsorDeviceActionWarrant(
        warrant_id="warrant-tap-1",
        sponsor_did=crypto_actors["sponsor_did"],
        agent_id="agent-007",
        target_device_id="android_pixel_01",
        action_caid="00" * 32,  # Tampered or mismatched CAID
        allowed_action_types=[TAP_COORDINATE],
        issued_at=now,
        expires_at=now + 600,
    )
    warrant.sign(crypto_actors["sponsor_priv"])

    with pytest.raises(WarrantVerificationHaltError) as exc_info:
        gate.verify_and_dispatch(action, warrant, now_ts=now)
    assert exc_info.value.error_code == HALT_DEVICE_ACTION_CAID_MISMATCH


def test_artemis_expired_warrant_rejected(crypto_actors):
    """Evaluates that expired sponsor warrants fail closed with HALT_DEVICE_ACTION_WARRANT_EXPIRED."""
    gate = ArtemisDeviceActuatorGate()
    gate.register_sponsor_key(crypto_actors["sponsor_did"], crypto_actors["sponsor_pub"])

    now = int(time.time())
    action = DeviceAction(
        action_type=TAP_COORDINATE,
        target_device_id="android_pixel_01",
        agent_id="agent-007",
        parameters={"x": 100, "y": 200},
        nonce="nonce-exp-1",
        timestamp=now - 200,
    )
    warrant = SponsorDeviceActionWarrant(
        warrant_id="warrant-exp-1",
        sponsor_did=crypto_actors["sponsor_did"],
        agent_id="agent-007",
        target_device_id="android_pixel_01",
        action_caid=action.compute_caid(),
        allowed_action_types=[TAP_COORDINATE],
        issued_at=now - 500,
        expires_at=now - 100,  # Expired in past
    )
    warrant.sign(crypto_actors["sponsor_priv"])

    with pytest.raises(WarrantVerificationHaltError) as exc_info:
        gate.verify_and_dispatch(action, warrant, now_ts=now)
    assert exc_info.value.error_code == HALT_DEVICE_ACTION_WARRANT_EXPIRED


def test_artemis_forged_sponsor_signature_rejected(crypto_actors):
    """Evaluates that invalid sponsor signature triggers HALT_DEVICE_ACTION_SPONSOR_SIGNATURE_INVALID."""
    gate = ArtemisDeviceActuatorGate()
    gate.register_sponsor_key(crypto_actors["sponsor_did"], crypto_actors["sponsor_pub"])

    now = int(time.time())
    action = DeviceAction(
        action_type=TAP_COORDINATE,
        target_device_id="android_pixel_01",
        agent_id="agent-007",
        parameters={"x": 100, "y": 200},
        nonce="nonce-forge-1",
        timestamp=now,
    )
    warrant = SponsorDeviceActionWarrant(
        warrant_id="warrant-forge-1",
        sponsor_did=crypto_actors["sponsor_did"],
        agent_id="agent-007",
        target_device_id="android_pixel_01",
        action_caid=action.compute_caid(),
        allowed_action_types=[TAP_COORDINATE],
        issued_at=now,
        expires_at=now + 600,
    )
    # Sign with attacker key rather than authorized sponsor key
    warrant.sign(crypto_actors["attacker_priv"])

    with pytest.raises(WarrantVerificationHaltError) as exc_info:
        gate.verify_and_dispatch(action, warrant, now_ts=now)
    assert exc_info.value.error_code == HALT_DEVICE_ACTION_SPONSOR_SIGNATURE_INVALID


def test_artemis_delegation_device_or_agent_mismatch(crypto_actors):
    """Evaluates that mismatched target device or agent ID fails closed."""
    gate = ArtemisDeviceActuatorGate()
    gate.register_sponsor_key(crypto_actors["sponsor_did"], crypto_actors["sponsor_pub"])

    now = int(time.time())
    action = DeviceAction(
        action_type=TAP_COORDINATE,
        target_device_id="android_pixel_01",
        agent_id="agent-007",
        parameters={"x": 10, "y": 20},
        nonce="nonce-del-1",
        timestamp=now,
    )
    # Warrant specifies different target device
    warrant = SponsorDeviceActionWarrant(
        warrant_id="warrant-del-1",
        sponsor_did=crypto_actors["sponsor_did"],
        agent_id="agent-007",
        target_device_id="android_pixel_OTHER",
        action_caid=action.compute_caid(),
        allowed_action_types=[TAP_COORDINATE],
        issued_at=now,
        expires_at=now + 600,
    )
    warrant.sign(crypto_actors["sponsor_priv"])

    with pytest.raises(WarrantVerificationHaltError) as exc_info:
        gate.verify_and_dispatch(action, warrant, now_ts=now)
    assert exc_info.value.error_code == HALT_DEVICE_ACTION_DELEGATION_MISMATCH


def test_artemis_unpermitted_action_type_rejected(crypto_actors):
    """Evaluates that attempting an action type not listed in warrant fails closed."""
    gate = ArtemisDeviceActuatorGate()
    gate.register_sponsor_key(crypto_actors["sponsor_did"], crypto_actors["sponsor_pub"])

    now = int(time.time())
    action = DeviceAction(
        action_type=ADB_SHELL,
        target_device_id="android_pixel_01",
        agent_id="agent-007",
        parameters={"command": "pm list packages"},
        nonce="nonce-adb-1",
        timestamp=now,
    )
    # Warrant only allows READ_SCREEN
    warrant = SponsorDeviceActionWarrant(
        warrant_id="warrant-type-1",
        sponsor_did=crypto_actors["sponsor_did"],
        agent_id="agent-007",
        target_device_id="android_pixel_01",
        action_caid=action.compute_caid(),
        allowed_action_types=[READ_SCREEN],
        issued_at=now,
        expires_at=now + 600,
    )
    warrant.sign(crypto_actors["sponsor_priv"])

    with pytest.raises(WarrantVerificationHaltError) as exc_info:
        gate.verify_and_dispatch(action, warrant, now_ts=now)
    assert exc_info.value.error_code == HALT_DEVICE_ACTION_TYPE_NOT_PERMITTED


@pytest.mark.parametrize(
    "action_type,params",
    [
        (OPEN_PAYMENT_APP, {"package": "com.bank.secure", "payee": "target_acc"}),
        (SUBMIT_CREDENTIAL, {"credential_id": "cred_99", "target_service": "bank_portal"}),
        (AUTHORIZE_BIOMETRIC, {"prompt_title": "Authorize Wire", "auth_level": "strong"}),
        (MODIFY_SYSTEM_SETTING, {"setting_name": "install_non_market_apps", "value": "1"}),
        (ADB_SHELL, {"command": "reboot"}),
        (LAUNCH_INTENT, {"package": "com.android.settings", "action": "android.settings.SETTINGS"}),
        (INPUT_TEXT, {"text": "secret123", "is_sensitive": True}),
        (INPUT_TEXT, {"text": "4567", "field_type": "pin"}),
    ],
)
def test_artemis_high_consequence_actions_reject_without_step_up(crypto_actors, action_type, params):
    """Evaluates that all high-consequence device actions fail closed without an RFC 9470 step-up token."""
    gate = ArtemisDeviceActuatorGate()
    gate.register_sponsor_key(crypto_actors["sponsor_did"], crypto_actors["sponsor_pub"])

    now = int(time.time())
    action = DeviceAction(
        action_type=action_type,
        target_device_id="android_pixel_01",
        agent_id="agent-007",
        parameters=params,
        nonce="nonce-high-test",
        timestamp=now,
    )
    caid = action.compute_caid()

    warrant = SponsorDeviceActionWarrant(
        warrant_id="warrant-high-1",
        sponsor_did=crypto_actors["sponsor_did"],
        agent_id="agent-007",
        target_device_id="android_pixel_01",
        action_caid=caid,
        allowed_action_types=[action_type],
        issued_at=now,
        expires_at=now + 600,
    )
    warrant.sign(crypto_actors["sponsor_priv"])

    with pytest.raises(StepUpRequiredHaltError) as exc_info:
        gate.verify_and_dispatch(action, warrant, step_up_token=None, now_ts=now)
    assert exc_info.value.error_code == HALT_DEVICE_ACTION_REQUIRES_STEP_UP


def test_artemis_high_consequence_action_authorized_with_valid_step_up(crypto_actors):
    """Evaluates that providing an Ed25519-signed RFC 9470 step-up token authorizes high-consequence action."""
    gate = ArtemisDeviceActuatorGate()
    gate.register_sponsor_key(crypto_actors["sponsor_did"], crypto_actors["sponsor_pub"])
    gate.register_supervisor_key(crypto_actors["supervisor_did"], crypto_actors["supervisor_pub"])

    now = int(time.time())
    action = DeviceAction(
        action_type=OPEN_PAYMENT_APP,
        target_device_id="android_pixel_01",
        agent_id="agent-007",
        parameters={"package": "com.payment.wallet", "payee": "merchant_1"},
        nonce="nonce-pay-stepup",
        timestamp=now,
    )
    caid = action.compute_caid()

    warrant = SponsorDeviceActionWarrant(
        warrant_id="warrant-pay-1",
        sponsor_did=crypto_actors["sponsor_did"],
        agent_id="agent-007",
        target_device_id="android_pixel_01",
        action_caid=caid,
        allowed_action_types=[OPEN_PAYMENT_APP],
        issued_at=now,
        expires_at=now + 600,
    )
    warrant.sign(crypto_actors["sponsor_priv"])

    step_up_token = Rfc9470StepUpToken(
        token_id="stepup-valid-1",
        acr="urn:ietf:params:oauth:acr:rfc9470-webauthn-hw",
        action_caid=caid,
        target_device_id="android_pixel_01",
        supervisor_did=crypto_actors["supervisor_did"],
        challenge_nonce="challenge-nonce-001",
        issued_at=now,
        expires_at=now + 300,
    )
    step_up_token.sign(crypto_actors["supervisor_priv"])

    receipt = gate.verify_and_dispatch(action, warrant, step_up_token=step_up_token, now_ts=now)
    assert receipt["status"] == "AUTHORIZED"
    assert receipt["decision"] == "DISPATCHED"
    assert receipt["step_up_applied"] is True


def test_artemis_step_up_token_expired_fails_closed(crypto_actors):
    """Evaluates that an expired RFC 9470 step-up token is rejected with HALT_DEVICE_ACTION_REQUIRES_STEP_UP."""
    gate = ArtemisDeviceActuatorGate()
    gate.register_sponsor_key(crypto_actors["sponsor_did"], crypto_actors["sponsor_pub"])
    gate.register_supervisor_key(crypto_actors["supervisor_did"], crypto_actors["supervisor_pub"])

    now = int(time.time())
    action = DeviceAction(
        action_type=OPEN_PAYMENT_APP,
        target_device_id="android_pixel_01",
        agent_id="agent-007",
        parameters={"package": "com.payment.wallet"},
        nonce="nonce-pay-exp",
        timestamp=now,
    )
    caid = action.compute_caid()

    warrant = SponsorDeviceActionWarrant(
        warrant_id="warrant-pay-exp",
        sponsor_did=crypto_actors["sponsor_did"],
        agent_id="agent-007",
        target_device_id="android_pixel_01",
        action_caid=caid,
        allowed_action_types=[OPEN_PAYMENT_APP],
        issued_at=now,
        expires_at=now + 600,
    )
    warrant.sign(crypto_actors["sponsor_priv"])

    step_up_token = Rfc9470StepUpToken(
        token_id="stepup-exp-1",
        acr="urn:ietf:params:oauth:acr:rfc9470-webauthn-hw",
        action_caid=caid,
        target_device_id="android_pixel_01",
        supervisor_did=crypto_actors["supervisor_did"],
        challenge_nonce="nonce-exp",
        issued_at=now - 500,
        expires_at=now - 10,  # Expired
    )
    step_up_token.sign(crypto_actors["supervisor_priv"])

    with pytest.raises(StepUpRequiredHaltError) as exc_info:
        gate.verify_and_dispatch(action, warrant, step_up_token=step_up_token, now_ts=now)
    assert exc_info.value.error_code == HALT_DEVICE_ACTION_REQUIRES_STEP_UP


def test_artemis_step_up_token_caid_mismatch_fails_closed(crypto_actors):
    """Evaluates that step-up token bound to a different action CAID fails closed."""
    gate = ArtemisDeviceActuatorGate()
    gate.register_sponsor_key(crypto_actors["sponsor_did"], crypto_actors["sponsor_pub"])
    gate.register_supervisor_key(crypto_actors["supervisor_did"], crypto_actors["supervisor_pub"])

    now = int(time.time())
    action = DeviceAction(
        action_type=OPEN_PAYMENT_APP,
        target_device_id="android_pixel_01",
        agent_id="agent-007",
        parameters={"package": "com.payment.wallet"},
        nonce="nonce-pay-caid",
        timestamp=now,
    )
    caid = action.compute_caid()

    warrant = SponsorDeviceActionWarrant(
        warrant_id="warrant-pay-caid",
        sponsor_did=crypto_actors["sponsor_did"],
        agent_id="agent-007",
        target_device_id="android_pixel_01",
        action_caid=caid,
        allowed_action_types=[OPEN_PAYMENT_APP],
        issued_at=now,
        expires_at=now + 600,
    )
    warrant.sign(crypto_actors["sponsor_priv"])

    step_up_token = Rfc9470StepUpToken(
        token_id="stepup-caid-mismatch",
        acr="urn:ietf:params:oauth:acr:rfc9470-webauthn-hw",
        action_caid="11" * 32,  # Different CAID
        target_device_id="android_pixel_01",
        supervisor_did=crypto_actors["supervisor_did"],
        challenge_nonce="nonce-diff",
        issued_at=now,
        expires_at=now + 300,
    )
    step_up_token.sign(crypto_actors["supervisor_priv"])

    with pytest.raises(StepUpRequiredHaltError) as exc_info:
        gate.verify_and_dispatch(action, warrant, step_up_token=step_up_token, now_ts=now)
    assert exc_info.value.error_code == HALT_DEVICE_ACTION_REQUIRES_STEP_UP


# ==============================================================================
# 2. Hermes Edge Plugin Gate Tests
# ==============================================================================

def test_hermes_valid_plugin_admitted(crypto_actors):
    """Evaluates that a compliant edge plugin with valid signed manifest is admitted."""
    gate = HermesEdgePluginGate()
    code = (
        "import socket\n"
        "def inspect_screen():\n"
        "    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
        "    return {'status': 'screen_captured'}\n"
    )
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    now = int(time.time())

    manifest = HermesPluginManifest(
        plugin_name="hermes_screen_tool",
        version="1.0.0",
        publisher_pubkey=crypto_actors["publisher_pub_b64"],
        allowed_device_scopes=[READ_SCREEN],
        code_sha256=code_hash,
        issued_at=now,
    )
    manifest.sign(crypto_actors["publisher_priv"])

    receipt = gate.verify_and_admit_plugin(manifest, code, now_ts=now)
    assert receipt["status"] == "ADMITTED"
    assert manifest.plugin_name in gate.catalog


def test_hermes_code_tampering_rejected(crypto_actors):
    """Evaluates that modified code string triggers HALT_PLUGIN_CODE_INTEGRITY_MISMATCH."""
    gate = HermesEdgePluginGate()
    code = "def valid(): return {'ok': True}\n"
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    now = int(time.time())

    manifest = HermesPluginManifest(
        plugin_name="hermes_tampered_tool",
        version="1.0.0",
        publisher_pubkey=crypto_actors["publisher_pub_b64"],
        allowed_device_scopes=[READ_SCREEN],
        code_sha256=code_hash,
        issued_at=now,
    )
    manifest.sign(crypto_actors["publisher_priv"])

    tampered_code = "def valid(): return {'ok': False, 'injected': True}\n"
    with pytest.raises(PluginCodeIntegrityError) as exc_info:
        gate.verify_and_admit_plugin(manifest, tampered_code, now_ts=now)
    assert exc_info.value.error_code == HALT_PLUGIN_CODE_INTEGRITY_MISMATCH


def test_hermes_forged_publisher_signature_rejected(crypto_actors):
    """Evaluates that invalid publisher signature triggers HALT_PLUGIN_SIGNATURE_INVALID."""
    gate = HermesEdgePluginGate()
    code = "def f(): return 1\n"
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    now = int(time.time())

    manifest = HermesPluginManifest(
        plugin_name="hermes_forged_tool",
        version="1.0.0",
        publisher_pubkey=crypto_actors["publisher_pub_b64"],
        allowed_device_scopes=[READ_SCREEN],
        code_sha256=code_hash,
        issued_at=now,
    )
    # Sign with attacker key rather than publisher private key
    manifest.sign(crypto_actors["attacker_priv"])

    with pytest.raises(PluginSignatureInvalidError) as exc_info:
        gate.verify_and_admit_plugin(manifest, code, now_ts=now)
    assert exc_info.value.error_code == HALT_PLUGIN_SIGNATURE_INVALID


@pytest.mark.parametrize(
    "malicious_snippet,expected_rule",
    [
        ("def p(): return eval('1+1')", "FORBIDDEN_DYNAMIC_CALL"),
        ("def p(): exec('x=1')", "FORBIDDEN_DYNAMIC_CALL"),
        ("def p(): return compile('x=1', '', 'exec')", "FORBIDDEN_DYNAMIC_CALL"),
        ("def p(): return __import__('os')", "FORBIDDEN_DYNAMIC_CALL"),
        ("import ctypes\ndef p(): return 1", "FORBIDDEN_MODULE_IMPORT"),
        ("import urllib.request\ndef p(): return 1", "FORBIDDEN_MODULE_IMPORT"),
        ("import requests\ndef p(): return 1", "FORBIDDEN_MODULE_IMPORT"),
        ("def p(obj): return obj.__globals__", "FORBIDDEN_REFLECTION_INTROSPECTION"),
        ("def p(cls): return cls.__subclasses__()", "FORBIDDEN_REFLECTION_INTROSPECTION"),
        ("import subprocess\ndef p(): subprocess.Popen(['ls'])", "FORBIDDEN_UNSANDBOXED_SUBPROCESS"),
        ("import socket\ndef p(): s = socket.socket()", "FORBIDDEN_NON_UDS_SOCKET"),
        ("import socket\ndef p(): s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)", "FORBIDDEN_NON_UDS_SOCKET"),
        ("import socket\ndef p(): socket.create_connection(('1.1.1.1', 80))", "FORBIDDEN_NETWORK_CONNECTION"),
    ],
)
def test_hermes_ast_scanner_catches_forbidden_constructs(crypto_actors, malicious_snippet, expected_rule):
    """Evaluates that the AST scanner detects all forbidden dynamic, network, and reflection calls."""
    violations = HermesASTSecurityScanner.scan(malicious_snippet)
    assert len(violations) > 0
    assert any(v["rule"] == expected_rule for v in violations)

    gate = HermesEdgePluginGate()
    code_hash = hashlib.sha256(malicious_snippet.encode("utf-8")).hexdigest()
    now = int(time.time())

    manifest = HermesPluginManifest(
        plugin_name="hermes_malicious_plugin",
        version="1.0.0",
        publisher_pubkey=crypto_actors["publisher_pub_b64"],
        allowed_device_scopes=[READ_SCREEN],
        code_sha256=code_hash,
        issued_at=now,
    )
    manifest.sign(crypto_actors["publisher_priv"])

    with pytest.raises(PluginDynamicCodeRejectedError) as exc_info:
        gate.verify_and_admit_plugin(manifest, malicious_snippet, now_ts=now)
    assert exc_info.value.error_code == HALT_PLUGIN_DYNAMIC_CODE_REJECTED


def test_hermes_capability_attenuation_enforcement(crypto_actors):
    """Evaluates that plugins claiming scopes beyond their manifest fail closed."""
    gate = HermesEdgePluginGate()
    now = int(time.time())
    manifest = HermesPluginManifest(
        plugin_name="hermes_attenuation_test",
        version="1.0.0",
        publisher_pubkey=crypto_actors["publisher_pub_b64"],
        allowed_device_scopes=[READ_SCREEN, TAP_COORDINATE],
        code_sha256="00" * 32,
        issued_at=now,
    )

    # Allowed scope check passes
    assert gate.enforce_capability_attenuation(manifest, [READ_SCREEN]) is True
    assert gate.enforce_capability_attenuation(manifest, [TAP_COORDINATE, READ_SCREEN]) is True

    # Claiming unauthorized scope fails closed
    with pytest.raises(PluginCapabilityAttenuationError) as exc_info:
        gate.enforce_capability_attenuation(manifest, [OPEN_PAYMENT_APP])
    assert exc_info.value.error_code == HALT_PLUGIN_CAPABILITY_ATTENUATION_VIOLATION


# ==============================================================================
# 3. ADECS 4.0 Agent Lifecycle State Automaton Tests
# ==============================================================================

def test_adecs_lifecycle_transitions_and_rejections(crypto_actors):
    """Evaluates formal ADECS 4.0 state progression: RECRUITED -> DEPLOYED -> GROWING -> RETIRED."""
    automaton = AdecsAgentLifecycleAutomaton()
    agent_id = "agent-adecs-001"
    pubkey_b64 = crypto_actors["publisher_pub_b64"]

    # 1. Recruit
    record = automaton.recruit_agent(agent_id, pubkey_b64)
    assert record.state == AdecsAgentState.RECRUITED
    assert record.spend_budget == 0

    # Mutations on RECRUITED agent fail closed
    with pytest.raises(AgentLifecycleInvalidHaltError) as exc_info:
        automaton.authorize_mutation(agent_id, cost_minor=10)
    assert exc_info.value.error_code == HALT_AGENT_LIFECYCLE_INVALID

    # 2. Deploy
    automaton.deploy_agent(agent_id, budget_ceiling=5000)
    assert automaton.agents[agent_id].state == AdecsAgentState.DEPLOYED
    assert int(automaton.agents[agent_id].spend_budget) == 5000

    # Mutations on DEPLOYED agent decrement budget
    automaton.authorize_mutation(agent_id, cost_minor=1500)
    assert automaton.agents[agent_id].spend_budget == 3500

    # Exceeding budget ceiling fails closed
    with pytest.raises(AgentBudgetExceededHaltError) as exc_info:
        automaton.authorize_mutation(agent_id, cost_minor=4000)
    assert exc_info.value.error_code == HALT_AGENT_BUDGET_EXCEEDED

    # 3. Grow
    automaton.begin_growing(agent_id)
    assert automaton.agents[agent_id].state == AdecsAgentState.GROWING

    # Mutations paused during GROWING state
    with pytest.raises(AgentLifecycleInvalidHaltError) as exc_info:
        automaton.authorize_mutation(agent_id, cost_minor=100)
    assert exc_info.value.error_code == HALT_AGENT_LIFECYCLE_INVALID

    # Incorporate skill via Hermes AST gate
    clean_skill_code = "def read_ui(): return {'nodes': []}\n"
    code_hash = hashlib.sha256(clean_skill_code.encode("utf-8")).hexdigest()
    now = int(time.time())
    skill_manifest = HermesPluginManifest(
        plugin_name="ui_reader_v1",
        version="1.0.0",
        publisher_pubkey=pubkey_b64,
        allowed_device_scopes=[READ_SCREEN],
        code_sha256=code_hash,
        issued_at=now,
    )
    skill_manifest.sign(crypto_actors["publisher_priv"])

    automaton.admit_skill_to_agent(agent_id, skill_manifest, clean_skill_code, now_ts=now)
    assert automaton.agents[agent_id].state == AdecsAgentState.DEPLOYED
    assert "ui_reader_v1" in automaton.agents[agent_id].admitted_plugins

    # 4. Retire
    automaton.retire_agent(agent_id, reason="decommission_test")
    assert automaton.agents[agent_id].state == AdecsAgentState.RETIRED
    assert automaton.agents[agent_id].spend_budget == 0

    # Mutations on RETIRED agent fail closed
    with pytest.raises(AgentLifecycleInvalidHaltError) as exc_info:
        automaton.authorize_mutation(agent_id, cost_minor=1)
    assert exc_info.value.error_code == HALT_AGENT_LIFECYCLE_INVALID

    # Redeployment of RETIRED agent fails closed
    with pytest.raises(AgentLifecycleInvalidHaltError) as exc_info:
        automaton.deploy_agent(agent_id, budget_ceiling=1000)
    assert exc_info.value.error_code == HALT_AGENT_LIFECYCLE_INVALID


def test_adecs_end_to_end_coordinated_dispatch(crypto_actors):
    """Evaluates coordinated dispatch linking lifecycle, plugin attenuation, and device actuator gate."""
    device_gate = ArtemisDeviceActuatorGate()
    device_gate.register_sponsor_key(crypto_actors["sponsor_did"], crypto_actors["sponsor_pub"])

    plugin_gate = HermesEdgePluginGate()
    automaton = AdecsAgentLifecycleAutomaton(device_gate=device_gate, plugin_gate=plugin_gate)

    agent_id = "agent-coordinated-01"
    automaton.recruit_agent(agent_id, crypto_actors["publisher_pub_b64"])
    automaton.deploy_agent(agent_id, budget_ceiling=1000)

    # Register edge plugin
    code = "def tap_helper(): return {'action': 'tap'}\n"
    now = int(time.time())
    manifest = HermesPluginManifest(
        plugin_name="hermes_tap_plugin",
        version="1.0.0",
        publisher_pubkey=crypto_actors["publisher_pub_b64"],
        allowed_device_scopes=[TAP_COORDINATE],
        code_sha256=hashlib.sha256(code.encode("utf-8")).hexdigest(),
        issued_at=now,
    )
    manifest.sign(crypto_actors["publisher_priv"])
    plugin_gate.verify_and_admit_plugin(manifest, code, now_ts=now)

    # Setup action & warrant
    action = DeviceAction(
        action_type=TAP_COORDINATE,
        target_device_id="android_pixel_01",
        agent_id=agent_id,
        parameters={"x": 500, "y": 800},
        nonce="nonce-coord-01",
        timestamp=now,
    )
    warrant = SponsorDeviceActionWarrant(
        warrant_id="warrant-coord-01",
        sponsor_did=crypto_actors["sponsor_did"],
        agent_id=agent_id,
        target_device_id="android_pixel_01",
        action_caid=action.compute_caid(),
        allowed_action_types=[TAP_COORDINATE],
        issued_at=now,
        expires_at=now + 600,
    )
    warrant.sign(crypto_actors["sponsor_priv"])

    # Dispatches through automaton
    receipt = automaton.dispatch_agent_device_action(
        agent_id=agent_id,
        action=action,
        warrant=warrant,
        plugin_name="hermes_tap_plugin",
        cost_minor=50,
        now_ts=now,
    )
    assert receipt["status"] == "AUTHORIZED"
    assert receipt["decision"] == "DISPATCHED"
    assert receipt["agent_spend_budget_remaining"] == 950


# ==============================================================================
# 4. Strict Epistemic & Banned Promotional Words Scan
# ==============================================================================

def test_zero_banned_promotional_words_in_owned_files():
    """
    Verifies that all files owned by Subagent 3 contain zero banned promotional words.
    Uses string concatenation to avoid creating forbidden literals in test source.
    """
    banned_tokens = [
        "guaran" + "tee",
        "guaran" + "teed",
        "guaran" + "tees",
        "guaran" + "teeing",
        "proven" + " universally",
        "bullet" + "proof",
        "enterprise" + "-grade",
        "production" + "-safe",
        "100%" + " secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
        "bank" + "-grade",
        "production" + "-ready",
    ]

    target_files = [
        Path("src/artemis_device_and_plugin_boundary.py"),
        Path("docs/architecture/ARTEMIS_MOBILE_AND_HERMES_EDGE_PLUGINS.md"),
        Path("tests/test_artemis_device_and_plugin_boundary.py"),
    ]

    violations = []
    for fpath in target_files:
        assert fpath.is_file(), f"Expected file '{fpath}' to exist"
        content = fpath.read_text(encoding="utf-8").lower()
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            # Skip the test's own definition list
            if "banned_tokens = [" in line or '"guaran" +' in line:
                continue
            for token in banned_tokens:
                if token in line:
                    violations.append(f"{fpath}:{idx}: contains forbidden word '{token}'")

    assert not violations, f"Banned promotional words detected:\n" + "\n".join(violations)
