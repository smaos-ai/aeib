#!/usr/bin/env python3
"""Zero-Mock Loopback Falsification Suite for `IPhoneNotaryRPCClient`.

Tests wire-level HTTP protocol against an in-process loopback server simulating
the iPhone 16 Pro Max `NotaryRPCServer`.
"""

import http.server
import json
import threading
from typing import Tuple

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.iphone_enclave_notary_bridge import T3ActionProposal, sha256_jcs_caid
from src.iphone_rpc_client import DEFAULT_NOTARY_PORT, IPhoneNotaryRPCClient


def _start_local_enclave_server(
    priv_key,
    pub_hex: str,
    simulate_veto: bool = False,
    malformed_json: bool = False,
    generic_403: bool = False,
    status_500: bool = False,
    simulate_timeout: bool = False,
) -> Tuple[http.server.HTTPServer, int]:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Silence output during pytest

        def do_GET(self):
            if self.path == "/pubkey":
                body = pub_hex.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path != "/approve":
                self.send_response(404)
                self.end_headers()
                return

            length = int(self.headers.get("Content-Length", "0"))
            canonical_bytes = self.rfile.read(length)

            if simulate_timeout:
                import time
                time.sleep(0.3)

            if status_500:
                err = b"Internal Server Error"
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return

            if generic_403:
                err = b'{"error":"Forbidden Access"}'
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return

            if simulate_veto:
                err = b'{"error":"HALT_HUMAN_VETOED_ON_IPHONE"}'
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return

            if malformed_json:
                bad = b"NOT_VALID_JSON"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(bad)))
                self.end_headers()
                self.wfile.write(bad)
                return

            sig_der_hex = priv_key.sign(canonical_bytes, ec.ECDSA(hashes.SHA256())).hex()
            warrant = {
                "canonical_payload_utf8": canonical_bytes.decode("utf-8"),
                "payload_sha256_caid": sha256_jcs_caid(canonical_bytes),
                "public_key_x963_hex": pub_hex,
                "signature_der_hex": sig_der_hex,
                "algorithm": "ECDSA_P256_SHA256_SECURE_ENCLAVE",
            }
            resp_bytes = json.dumps(warrant).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def test_1_end_to_end_rpc_pubkey_and_faceid_approval() -> None:
    priv_key = ec.generate_private_key(ec.SECP256R1())
    pub_hex = (
        priv_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        .hex()
    )
    server, port = _start_local_enclave_server(priv_key, pub_hex, simulate_veto=False)
    try:
        client = IPhoneNotaryRPCClient("127.0.0.1", port=port, pinned_enclave_pubkey_x963_hex=pub_hex)
        fetched_key = client.fetch_enclave_pubkey_hex()
        assert fetched_key == pub_hex

        proposal = T3ActionProposal(
            operation_id="op_wire_001",
            intent_caid="sha256:abcd",
            action_type="PRODUCTION_MIGRATION",
            target_resource="db://main",
            amount_minor=0,
            attempt_fence=1,
            expires_at_epoch_sec=1_800_000_060,
        )
        verdict = client.request_faceid_warrant(proposal, current_epoch_sec=1_800_000_010)
        assert verdict.latch_released is True
        assert verdict.reason_code == "OK_FACEID_ENCLAVE_WARRANT_VERIFIED"
    finally:
        server.shutdown()


def test_2_explicit_human_veto_on_iphone_halts_immediately() -> None:
    priv_key = ec.generate_private_key(ec.SECP256R1())
    pub_hex = (
        priv_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        .hex()
    )
    server, port = _start_local_enclave_server(priv_key, pub_hex, simulate_veto=True)
    try:
        client = IPhoneNotaryRPCClient("127.0.0.1", port=port, pinned_enclave_pubkey_x963_hex=pub_hex)
        proposal = T3ActionProposal(
            operation_id="op_rogue_drop",
            intent_caid="sha256:bad",
            action_type="DATABASE_DROP_PRODUCTION",
            target_resource="db://prod",
            amount_minor=0,
            attempt_fence=1,
            expires_at_epoch_sec=1_800_000_060,
        )
        verdict = client.request_faceid_warrant(proposal, current_epoch_sec=1_800_000_010)
        assert verdict.latch_released is False
        assert verdict.reason_code == "HALT_HUMAN_VETOED_ON_IPHONE"
        expected_halt_receipt = sha256_jcs_caid(
            {
                "expected_caid": sha256_jcs_caid(proposal.to_canonical_jcs_bytes()),
                "latch_released": False,
                "reason_code": "HALT_HUMAN_VETOED_ON_IPHONE",
            }
        )
        assert verdict.warrant_receipt_caid == expected_halt_receipt
    finally:
        server.shutdown()


def test_3_unreachable_transport_fails_closed() -> None:
    # Use port 59999 where nothing is listening
    client = IPhoneNotaryRPCClient("127.0.0.1", port=59999, pinned_enclave_pubkey_x963_hex="04" + "00" * 64)
    proposal = T3ActionProposal(
        operation_id="op_unreachable",
        intent_caid="sha256:dead",
        action_type="RESTART",
        target_resource="srv://1",
        amount_minor=0,
        attempt_fence=1,
        expires_at_epoch_sec=1_800_000_060,
    )
    verdict = client.request_faceid_warrant(proposal, current_epoch_sec=1_800_000_010, timeout_sec=2)
    assert verdict.latch_released is False
    assert "HALT_IPHONE_TRANSPORT_UNREACHABLE" in verdict.reason_code


def test_4_malformed_json_response_fails_closed() -> None:
    priv_key = ec.generate_private_key(ec.SECP256R1())
    pub_hex = (
        priv_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        .hex()
    )
    server, port = _start_local_enclave_server(priv_key, pub_hex, malformed_json=True)
    try:
        client = IPhoneNotaryRPCClient("127.0.0.1", port=port, pinned_enclave_pubkey_x963_hex=pub_hex)
        proposal = T3ActionProposal(
            operation_id="op_malformed",
            intent_caid="sha256:feed",
            action_type="REBOOT",
            target_resource="srv://2",
            amount_minor=0,
            attempt_fence=1,
            expires_at_epoch_sec=1_800_000_060,
        )
        verdict = client.request_faceid_warrant(proposal, current_epoch_sec=1_800_000_010)
        assert verdict.latch_released is False
        assert verdict.reason_code == "HALT_MALFORMED_WARRANT_JSON"
    finally:
        server.shutdown()


def test_5_client_constructor_validation() -> None:
    with pytest.raises(ValueError, match="ERR_EMPTY_IPHONE_HOST"):
        IPhoneNotaryRPCClient("   ")

    with pytest.raises(ValueError, match="ERR_INVALID_PORT"):
        IPhoneNotaryRPCClient("127.0.0.1", port=0)

    with pytest.raises(ValueError, match="ERR_INVALID_PORT"):
        IPhoneNotaryRPCClient("127.0.0.1", port=-5)

    with pytest.raises(ValueError, match="ERR_INVALID_PORT"):
        IPhoneNotaryRPCClient("127.0.0.1", port=65536)

    # Valid boundaries
    c1 = IPhoneNotaryRPCClient("127.0.0.1")
    assert c1.port == DEFAULT_NOTARY_PORT
    c2 = IPhoneNotaryRPCClient("127.0.0.1", port=1)
    assert c2.port == 1
    c3 = IPhoneNotaryRPCClient("127.0.0.1", port=65535)
    assert c3.port == 65535


def test_6_http_error_branches_fail_closed() -> None:
    priv_key = ec.generate_private_key(ec.SECP256R1())
    pub_hex = (
        priv_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        .hex()
    )
    # Test 500
    server_500, port_500 = _start_local_enclave_server(priv_key, pub_hex, status_500=True)
    try:
        client_500 = IPhoneNotaryRPCClient("127.0.0.1", port=port_500, pinned_enclave_pubkey_x963_hex=pub_hex)
        proposal = T3ActionProposal(
            operation_id="op_500",
            intent_caid="sha256:500",
            action_type="FAIL",
            target_resource="srv://500",
            amount_minor=0,
            attempt_fence=1,
            expires_at_epoch_sec=1_800_000_060,
        )
        verdict = client_500.request_faceid_warrant(proposal)  # current_epoch_sec=None default
        assert verdict.latch_released is False
        assert verdict.reason_code == "HALT_IPHONE_HTTP_ERROR:500"
    finally:
        server_500.shutdown()

    # Test generic 403 (without HALT_HUMAN_VETOED_ON_IPHONE)
    server_403, port_403 = _start_local_enclave_server(priv_key, pub_hex, generic_403=True)
    try:
        client_403 = IPhoneNotaryRPCClient("127.0.0.1", port=port_403, pinned_enclave_pubkey_x963_hex=pub_hex)
        verdict = client_403.request_faceid_warrant(proposal)
        assert verdict.latch_released is False
        assert verdict.reason_code == "HALT_IPHONE_HTTP_ERROR:403"
    finally:
        server_403.shutdown()


def test_7_timeout_branch_fails_closed() -> None:
    priv_key = ec.generate_private_key(ec.SECP256R1())
    pub_hex = (
        priv_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        .hex()
    )
    server_timeout, port_timeout = _start_local_enclave_server(priv_key, pub_hex, simulate_timeout=True)
    try:
        client = IPhoneNotaryRPCClient("127.0.0.1", port=port_timeout, pinned_enclave_pubkey_x963_hex=pub_hex)
        proposal = T3ActionProposal(
            operation_id="op_timeout",
            intent_caid="sha256:timeout",
            action_type="LONG_RUN",
            target_resource="srv://slow",
            amount_minor=0,
            attempt_fence=1,
            expires_at_epoch_sec=1_800_000_060,
        )
        verdict = client.request_faceid_warrant(proposal, timeout_sec=0.05)
        assert verdict.latch_released is False
        assert verdict.reason_code == "HALT_IPHONE_FACEID_TIMEOUT"
    finally:
        server_timeout.shutdown()


def test_8_explicit_epoch_sec_expiration_check() -> None:
    priv_key = ec.generate_private_key(ec.SECP256R1())
    pub_hex = (
        priv_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        .hex()
    )
    server, port = _start_local_enclave_server(priv_key, pub_hex)
    try:
        client = IPhoneNotaryRPCClient("127.0.0.1", port=port, pinned_enclave_pubkey_x963_hex=pub_hex)
        proposal = T3ActionProposal(
            operation_id="op_exp",
            intent_caid="sha256:exp",
            action_type="EXP",
            target_resource="srv://exp",
            amount_minor=0,
            attempt_fence=1,
            expires_at_epoch_sec=1_000,
        )
        # Passing current_epoch_sec=2000 explicitly must cause expiration failure
        v_expired = client.request_faceid_warrant(proposal, current_epoch_sec=2000)
        assert v_expired.latch_released is False
        assert v_expired.reason_code == "HALT_FACEID_WARRANT_EXPIRED"

        # Passing current_epoch_sec=500 explicitly must succeed
        v_ok = client.request_faceid_warrant(proposal, current_epoch_sec=500)
        assert v_ok.latch_released is True
        assert v_ok.reason_code == "OK_FACEID_ENCLAVE_WARRANT_VERIFIED"
    finally:
        server.shutdown()

def test_9_url_error_string_timed_out_is_caught(monkeypatch) -> None:
    client = IPhoneNotaryRPCClient("127.0.0.1", port=8080, pinned_enclave_pubkey_x963_hex="04" + "aa" * 64)
    proposal = T3ActionProposal(
        operation_id="op_str_timeout",
        intent_caid="sha256:str_timeout",
        action_type="STR_TIMEOUT",
        target_resource="srv://slow",
        amount_minor=0,
        attempt_fence=1,
        expires_at_epoch_sec=1_800_000_060,
    )

    import urllib.request
    def _fake_urlopen(*args, **kwargs):
        raise urllib.error.URLError("connection timed out")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    verdict = client.request_faceid_warrant(proposal, current_epoch_sec=1_800_000_010)
    assert verdict.latch_released is False
    assert verdict.reason_code == "HALT_IPHONE_FACEID_TIMEOUT"
