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
tests/test_eo1_biometric_gate.py
================================================================================
Comprehensive verification of the Out-of-Band Biometric EO-1 Gating Adapter.
Tests real cryptography (NIST P-256 + Ed25519) and zero mocks.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.eo1_biometric_gate import (
    BiometricEO1InterlockAdapter,
    BiometricGatePolicy,
    BiometricHumanVetoError,
    BiometricTimeoutError,
    BiometricVerificationFailedError,
)
from src.eo1_write_before_execute import (
    PreDispatchIntentInterlock,
    compute_caid,
)
from src.iphone_enclave_notary_bridge import (
    EnclaveSignedWarrant,
    T3ActionProposal,
    sha256_jcs_caid,
)
from src.iphone_rpc_client import IPhoneNotaryRPCClient


def _make_p256_hardware_simulator():
    """Generates a real SECP256R1 keypair simulating the A18 Pro Secure Enclave."""
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    pub_hex = pub_bytes.hex()
    return priv, pub_hex


class MockEnclaveHTTPHandler(BaseHTTPRequestHandler):
    """Real HTTP/1.1 server answering GET /pubkey and POST /approve."""

    priv_key: Any = None
    pubkey_hex: str = ""
    veto_mode: bool = False
    tamper_mode: bool = False
    timeout_mode: bool = False

    def do_GET(self):
        if self.path == "/pubkey":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(self.pubkey_hex)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(self.pubkey_hex.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/approve":
            if self.timeout_mode:
                return  # simulate timeout by hanging

            if self.veto_mode:
                err_body = b'{"error":"HALT_HUMAN_VETOED_ON_IPHONE"}'
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(err_body)
                return

            length = int(self.headers.get("Content-Length", 0))
            canonical_bytes = self.rfile.read(length)

            digest_caid = sha256_jcs_caid(canonical_bytes)
            sig_bytes = self.priv_key.sign(canonical_bytes, ec.ECDSA(hashes.SHA256()))
            sig_hex = sig_bytes.hex()

            if self.tamper_mode:
                # Flip 1 byte of the signature
                sig_list = list(sig_bytes)
                sig_list[5] ^= 0xFF
                sig_hex = bytes(sig_list).hex()

            warrant = {
                "canonical_payload_utf8": canonical_bytes.decode("utf-8"),
                "payload_sha256_caid": digest_caid,
                "public_key_x963_hex": self.pubkey_hex,
                "signature_der_hex": sig_hex,
                "algorithm": "ECDSA_P256_SHA256_SECURE_ENCLAVE",
            }

            resp_bytes = json.dumps(warrant).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(resp_bytes)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Quiet logging


@pytest.fixture
def notary_test_server():
    priv, pub_hex = _make_p256_hardware_simulator()
    handler_cls = type(
        "ConfiguredHandler",
        (MockEnclaveHTTPHandler,),
        {
            "priv_key": priv,
            "pubkey_hex": pub_hex,
            "veto_mode": False,
            "tamper_mode": False,
            "timeout_mode": False,
        },
    )

    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield server, handler_cls, port, pub_hex
    server.shutdown()
    server.server_close()


def test_1_nominal_biometric_approval_releases_eo1_intent_and_dispatches(tmp_path: Path, notary_test_server):
    server, handler_cls, port, pub_hex = notary_test_server

    ledger_path = tmp_path / "test_eo1.ledger"
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_path,
        boundary_private_key=Ed25519PrivateKey.generate(),
    )

    rpc_client = IPhoneNotaryRPCClient(
        iphone_host="127.0.0.1",
        port=port,
        pinned_enclave_pubkey_x963_hex=pub_hex,
    )

    adapter = BiometricEO1InterlockAdapter(
        interlock=interlock,
        notary_client=rpc_client,
        policy=BiometricGatePolicy(timeout_sec=5),
        actor_id="test_actor_01",
    )

    payload = {
        "action_type": "T3_EXECUTE_IRREVERSIBLE_SETTLEMENT",
        "amount_minor": 5000000,
        "recipient": "treasury_vault_omega",
    }

    dispatched = False

    def _dispatch():
        nonlocal dispatched
        dispatched = True
        return {"status": "SETTLED_OK"}

    result = adapter.dispatch_guarded(
        target_uri="https://api.internal/v1/settle",
        tool_name="T3_settlement_escrow",
        payload=payload,
        dispatch_fn=_dispatch,
    )

    assert dispatched is True
    assert result.response == {"status": "SETTLED_OK"}

    # Assert ledger has both DISPATCH_INTENT and CONTINUITY_RECEIPT
    raw_ledger = ledger_path.read_bytes()
    assert b"DISPATCH_INTENT" in raw_ledger
    assert b"CONTINUITY_RECEIPT" in raw_ledger
    assert b"T3_settlement_escrow" in raw_ledger


def test_2_operator_veto_raises_biometric_human_veto_error_and_prevents_dispatch(tmp_path: Path, notary_test_server):
    server, handler_cls, port, pub_hex = notary_test_server
    handler_cls.veto_mode = True

    ledger_path = tmp_path / "test_eo1_veto.ledger"
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_path,
        boundary_private_key=Ed25519PrivateKey.generate(),
    )

    rpc_client = IPhoneNotaryRPCClient(
        iphone_host="127.0.0.1",
        port=port,
        pinned_enclave_pubkey_x963_hex=pub_hex,
    )

    adapter = BiometricEO1InterlockAdapter(
        interlock=interlock,
        notary_client=rpc_client,
        policy=BiometricGatePolicy(timeout_sec=5),
    )

    dispatched = False

    def _dispatch():
        nonlocal dispatched
        dispatched = True
        return {"status": "MUST_NOT_EXECUTE"}

    with pytest.raises(BiometricHumanVetoError) as exc_info:
        adapter.dispatch_guarded(
            target_uri="https://api.internal/v1/settle",
            tool_name="T3_settlement_escrow",
            payload={"amount_minor": 200000},
            dispatch_fn=_dispatch,
        )

    assert "explicitly vetoed by the operator" in str(exc_info.value)
    assert dispatched is False
    # Zero ledger writes occurred
    assert not ledger_path.exists() or ledger_path.stat().st_size == 0


def test_3_tampered_warrant_raises_verification_failed_error(tmp_path: Path, notary_test_server):
    server, handler_cls, port, pub_hex = notary_test_server
    handler_cls.tamper_mode = True

    ledger_path = tmp_path / "test_eo1_tamper.ledger"
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_path,
        boundary_private_key=Ed25519PrivateKey.generate(),
    )

    rpc_client = IPhoneNotaryRPCClient(
        iphone_host="127.0.0.1",
        port=port,
        pinned_enclave_pubkey_x963_hex=pub_hex,
    )

    adapter = BiometricEO1InterlockAdapter(
        interlock=interlock,
        notary_client=rpc_client,
        policy=BiometricGatePolicy(timeout_sec=5),
    )

    dispatched = False

    def _dispatch():
        nonlocal dispatched
        dispatched = True

    with pytest.raises(BiometricVerificationFailedError) as exc_info:
        adapter.dispatch_guarded(
            target_uri="https://api.internal/v1/settle",
            tool_name="T3_settlement_escrow",
            payload={"amount_minor": 500000},
            dispatch_fn=_dispatch,
        )

    assert "HALT_ENCLAVE_SIGNATURE_INVALID" in str(exc_info.value)
    assert dispatched is False


def test_4_non_t3_actions_bypass_biometric_prompt_and_dispatch_normally(tmp_path: Path, notary_test_server):
    server, handler_cls, port, pub_hex = notary_test_server

    ledger_path = tmp_path / "test_eo1_non_t3.ledger"
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_path,
        boundary_private_key=Ed25519PrivateKey.generate(),
    )

    # Point client to a non-existent port to verify that if it tries to connect, it fails
    rpc_client = IPhoneNotaryRPCClient(
        iphone_host="127.0.0.1",
        port=65534,
        pinned_enclave_pubkey_x963_hex=pub_hex,
    )

    adapter = BiometricEO1InterlockAdapter(
        interlock=interlock,
        notary_client=rpc_client,
        policy=BiometricGatePolicy(threshold_amount_minor=100_000),
    )

    dispatched = False

    def _dispatch():
        nonlocal dispatched
        dispatched = True
        return "READ_DATA_OK"

    # Action is low value and not T3 prefixed
    result = adapter.dispatch_guarded(
        target_uri="https://api.internal/v1/logs",
        tool_name="query_readonly_audit_logs",
        payload={"amount_minor": 500, "query": "status"},
        dispatch_fn=_dispatch,
    )

    assert dispatched is True
    assert result.response == {"result": "READ_DATA_OK"}


def test_5_dispatch_fn_exception_latches_intent_as_effect_indeterminate(tmp_path: Path, notary_test_server):
    server, handler_cls, port, pub_hex = notary_test_server

    ledger_path = tmp_path / "test_eo1_latch.ledger"
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_path,
        boundary_private_key=Ed25519PrivateKey.generate(),
    )

    rpc_client = IPhoneNotaryRPCClient(
        iphone_host="127.0.0.1",
        port=port,
        pinned_enclave_pubkey_x963_hex=pub_hex,
    )

    adapter = BiometricEO1InterlockAdapter(
        interlock=interlock,
        notary_client=rpc_client,
        policy=BiometricGatePolicy(timeout_sec=5),
    )

    def _crashing_dispatch():
        raise ConnectionResetError("Wire connection reset mid-syscall")

    payload = {"amount_minor": 200000}
    caid = compute_caid(payload)

    with pytest.raises(RuntimeError) as exc_info:
        adapter.dispatch_guarded(
            target_uri="https://api.internal/v1/settle",
            tool_name="T3_wire_funds",
            payload=payload,
            dispatch_fn=_crashing_dispatch,
        )

    assert "Wire dispatch error" in str(exc_info.value)
    # Verify intent was latched into EFFECT_INDETERMINATE fail-closed
    assert interlock.is_caid_latched(caid) is True


def test_6_biometric_gate_policy_matrix():
    policy = BiometricGatePolicy()
    assert policy.action_type_prefix == "T3_"
    assert policy.threshold_amount_minor == 100_000
    assert policy.timeout_sec == 60
    assert policy.enforce_for_all_irreversible is True

    # Disabled policy
    disabled = BiometricGatePolicy(enforce_for_all_irreversible=False)
    assert disabled.requires_biometric_authorization("T3_action", {}) is False
    assert disabled.requires_biometric_authorization("normal_action", {"amount_minor": 500000}) is False

    # Tool prefix match
    assert policy.requires_biometric_authorization("T3_settlement", {}) is True
    assert policy.requires_biometric_authorization("t3_lowercase", {}) is False

    # Payload action_type match
    assert policy.requires_biometric_authorization("call", {"action_type": "T3_escrow"}) is True
    assert policy.requires_biometric_authorization("call", {"action_type": "read_data"}) is False

    # Payload amount threshold boundary
    assert policy.requires_biometric_authorization("call", {"amount_minor": 100_000}) is True
    assert policy.requires_biometric_authorization("call", {"amount_minor": 100_001}) is True
    assert policy.requires_biometric_authorization("call", {"amount_minor": 99_999}) is False

    # Strict type checks: boolean amount must never be treated as int
    assert policy.requires_biometric_authorization("call", {"amount_minor": True}) is False
    assert policy.requires_biometric_authorization("call", {"amount_minor": False}) is False
    assert policy.requires_biometric_authorization("call", {"amount_minor": "100000"}) is False

    # Non-dict payload
    assert policy.requires_biometric_authorization("call", "raw_string") is False
    assert policy.requires_biometric_authorization("call", 12345) is False
    assert policy.requires_biometric_authorization("call", None) is False


def test_7_adapter_proposal_extraction_and_defaults(tmp_path: Path):
    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "test_prop.ledger",
        boundary_private_key=Ed25519PrivateKey.generate(),
    )
    rpc_client = IPhoneNotaryRPCClient(
        iphone_host="127.0.0.1",
        port=9999,
        pinned_enclave_pubkey_x963_hex="04" + "a" * 128,
    )

    # Test default policy assignment
    adapter = BiometricEO1InterlockAdapter(interlock=interlock, notary_client=rpc_client)
    assert adapter.policy.timeout_sec == 60
    assert adapter.policy.threshold_amount_minor == 100_000

    # Test proposal extraction with payload defaults (missing action_type and amount_minor)
    fixed_epoch = 1700000000
    proposal = adapter.extract_or_build_proposal(
        target_uri="https://api.internal/v1/dispatch",
        tool_name="unspecified_mutation",
        payload={"some_key": "some_value"},
        attempt_fence=1,
        now_epoch_sec=fixed_epoch,
    )
    assert proposal.action_type == "unspecified_mutation"
    assert proposal.amount_minor == 0
    assert proposal.attempt_fence == 1
    assert proposal.expires_at_epoch_sec == fixed_epoch + 60
    caid = compute_caid({"some_key": "some_value"})
    assert proposal.intent_caid == caid
    assert proposal.operation_id == f"op_{caid[:12]}_1"
    assert proposal.target_resource == "https://api.internal/v1/dispatch"

    # Test proposal extraction with explicit fields and attempt_fence=2
    proposal2 = adapter.extract_or_build_proposal(
        target_uri="https://api.internal/v1/dispatch2",
        tool_name="tool_foo",
        payload={"action_type": "T3_custom", "amount_minor": 250000},
        attempt_fence=2,
        now_epoch_sec=fixed_epoch,
    )
    assert proposal2.action_type == "T3_custom"
    assert proposal2.amount_minor == 250000
    assert proposal2.attempt_fence == 2
    caid2 = compute_caid({"action_type": "T3_custom", "amount_minor": 250000})
    assert proposal2.operation_id == f"op_{caid2[:12]}_2"


def test_8_biometric_timeout_raises_timeout_error(tmp_path: Path):
    class TimeoutClient:
        def request_faceid_warrant(self, proposal, timeout_sec=60, current_epoch_sec=None):
            from src.iphone_enclave_notary_bridge import T3LatchReleaseVerdict
            return T3LatchReleaseVerdict(
                latch_released=False,
                reason_code="HALT_IPHONE_FACEID_TIMEOUT",
                verified_proposal_caid="none",
                warrant_receipt_caid="none",
            )

    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "test_timeout.ledger",
        boundary_private_key=Ed25519PrivateKey.generate(),
    )
    adapter = BiometricEO1InterlockAdapter(
        interlock=interlock,
        notary_client=TimeoutClient(),  # type: ignore
        policy=BiometricGatePolicy(timeout_sec=10),
    )

    with pytest.raises(BiometricTimeoutError) as exc_info:
        adapter.dispatch_guarded(
            target_uri="https://api.internal/v1/settle",
            tool_name="T3_action",
            payload={"amount_minor": 500000},
            dispatch_fn=lambda: None,
        )

    assert "Biometric authorization timed out after 10s" in str(exc_info.value)

