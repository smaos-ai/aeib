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
tests/test_microvm_vsock_channel.py — MicroVM VSOCK Channel & Guest Isolation Tests
"""

import base64
import dataclasses
import json
import os
import socket
import struct
import tempfile
import time
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.microvm_vsock_channel import (
    BACKLOG,
    BUFFER_SIZE,
    DEFAULT_AUTHORIZED_CIDS,
    FRAME_VERSION,
    MAGIC_CONST,
    MSG_CONFIRMATION,
    MSG_FAULT,
    MSG_HEARTBEAT,
    MSG_PROPOSAL,
    RESERVED_CONST,
    SOCKET_PERMISSIONS,
    MicroVMEgressViolation,
    MicroVMGuestClient,
    MicroVMHostVsockServer,
    VsockMessageFrame,
)


def test_frame_serialization_roundtrip():
    payload = b'{"action": "test_echo", "val": 42}'
    frame = VsockMessageFrame(
        magic=MAGIC_CONST,
        version=FRAME_VERSION,
        msg_type=MSG_PROPOSAL,
        payload=payload,
    )
    raw = frame.serialize()
    deserialized, consumed = VsockMessageFrame.deserialize(raw)
    assert consumed == len(raw)
    assert deserialized.magic == MAGIC_CONST
    assert deserialized.version == FRAME_VERSION
    assert deserialized.msg_type == MSG_PROPOSAL
    assert deserialized.payload == payload


def test_protocol_constants_and_immutability():
    assert MAGIC_CONST == 0xAE1B50C0
    assert RESERVED_CONST == 0
    assert FRAME_VERSION == 1
    assert MSG_PROPOSAL == 1
    assert MSG_CONFIRMATION == 2
    assert MSG_FAULT == 3
    assert MSG_HEARTBEAT == 4
    assert BUFFER_SIZE == 65536
    assert DEFAULT_AUTHORIZED_CIDS == (3, 4, 5)
    assert SOCKET_PERMISSIONS == 0o600
    assert BACKLOG == 16

    frame = VsockMessageFrame(
        magic=MAGIC_CONST,
        version=FRAME_VERSION,
        msg_type=MSG_PROPOSAL,
        payload=b"test",
    )
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError)):
        frame.magic = 0


def test_deserialize_validation_boundaries():
    # Buffer shorter than header
    with pytest.raises(ValueError, match="Frame buffer too short for header"):
        VsockMessageFrame.deserialize(b"\x00" * 5)

    valid_payload = b"test_payload"
    payload_len = len(valid_payload)

    # Invalid magic
    bad_magic = struct.pack(">IBBHI", 0x12345678, FRAME_VERSION, MSG_PROPOSAL, RESERVED_CONST, payload_len) + valid_payload
    with pytest.raises(ValueError, match="Invalid frame magic"):
        VsockMessageFrame.deserialize(bad_magic)

    # Unsupported version
    bad_ver = struct.pack(">IBBHI", MAGIC_CONST, 99, MSG_PROPOSAL, RESERVED_CONST, payload_len) + valid_payload
    with pytest.raises(ValueError, match="Unsupported frame version: 99"):
        VsockMessageFrame.deserialize(bad_ver)

    # Unknown message type
    bad_type = struct.pack(">IBBHI", MAGIC_CONST, FRAME_VERSION, 99, RESERVED_CONST, payload_len) + valid_payload
    with pytest.raises(ValueError, match="Unknown message type: 99"):
        VsockMessageFrame.deserialize(bad_type)

    # Non-zero reserved field
    bad_reserved = struct.pack(">IBBHI", MAGIC_CONST, FRAME_VERSION, MSG_PROPOSAL, 7, payload_len) + valid_payload
    with pytest.raises(ValueError, match="Non-zero reserved field: 7"):
        VsockMessageFrame.deserialize(bad_reserved)

    # Short payload buffer
    short_payload = struct.pack(">IBBHI", MAGIC_CONST, FRAME_VERSION, MSG_PROPOSAL, RESERVED_CONST, 100) + b"too_short"
    with pytest.raises(ValueError, match="Frame buffer too short for payload body"):
        VsockMessageFrame.deserialize(short_payload)


def test_host_server_defaults_and_socket_permissions():
    with tempfile.TemporaryDirectory() as tmpdir:
        sock_path = os.path.join(tmpdir, "vsock_defaults.sock")
        custom_signer = ed25519.Ed25519PrivateKey.generate()
        server = MicroVMHostVsockServer(socket_path=sock_path, authorized_guest_cids=None, host_signer=custom_signer)
        assert server._running is False
        assert server.authorized_guest_cids == {3, 4, 5}
        assert server.host_signer == custom_signer
        # Calling stop before start should be a clean no-op
        server.stop()
        server.start()
        try:
            assert server._running is True
            assert server._thread is not None
            assert server._thread.daemon is True
            mode = os.stat(sock_path).st_mode & 0o777
            assert mode == 0o600
        finally:
            server.stop()
            assert server._running is False


def test_proposal_with_omitted_direct_egress_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        sock_path = os.path.join(tmpdir, "vsock_omitted.sock")
        server = MicroVMHostVsockServer(socket_path=sock_path, authorized_guest_cids=[3])
        server.start()
        try:
            # Send raw proposal without direct_egress_attempted key
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(sock_path)
            with sock:
                payload = json.dumps({
                    "guest_cid": 3,
                    "operation_id": "op_omitted_key",
                    "tool_name": "status_check",
                    "arguments": {"test": 1},
                }).encode("utf-8")
                frame = VsockMessageFrame(
                    magic=MAGIC_CONST,
                    version=FRAME_VERSION,
                    msg_type=MSG_PROPOSAL,
                    payload=payload,
                )
                sock.sendall(frame.serialize())
                resp_bytes = sock.recv(BUFFER_SIZE)
                resp_frame, _ = VsockMessageFrame.deserialize(resp_bytes)
                assert resp_frame.msg_type == MSG_CONFIRMATION
                resp_dict = json.loads(resp_frame.payload.decode("utf-8"))
                assert resp_dict["status"] == "SUCCESS"
        finally:
            server.stop()


def test_raw_socket_fault_frame_on_malformed_client_input():
    with tempfile.TemporaryDirectory() as tmpdir:
        sock_path = os.path.join(tmpdir, "vsock_fault.sock")
        server = MicroVMHostVsockServer(socket_path=sock_path)
        server.start()
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(sock_path)
            with sock:
                # Send frame with invalid magic to trigger error handler in _listen_loop
                bad_magic = struct.pack(">IBBHI", 0xDEADBEEF, FRAME_VERSION, MSG_PROPOSAL, RESERVED_CONST, 4) + b"test"
                sock.sendall(bad_magic)
                resp_bytes = sock.recv(BUFFER_SIZE)
                resp_frame, _ = VsockMessageFrame.deserialize(resp_bytes)
                assert resp_frame.magic == MAGIC_CONST
                assert resp_frame.version == FRAME_VERSION
                assert resp_frame.msg_type == MSG_FAULT
                err_dict = json.loads(resp_frame.payload.decode("utf-8"))
                assert err_dict["status"] == "ERROR"
                assert "Invalid frame magic" in err_dict["detail"]
        finally:
            server.stop()


def test_guest_client_default_cid():
    client = MicroVMGuestClient(socket_path="/tmp/fake.sock")
    assert client.guest_cid == 3


def test_nominal_guest_proposal_authorized():
    with tempfile.TemporaryDirectory() as tmpdir:
        sock_path = os.path.join(tmpdir, "vsock_host.sock")
        server = MicroVMHostVsockServer(socket_path=sock_path, authorized_guest_cids=[3, 4])
        server.start()
        try:
            client = MicroVMGuestClient(socket_path=sock_path, guest_cid=3)
            resp = client.submit_proposal(
                operation_id="op_guest_101",
                tool_name="transfer_escrow",
                arguments={"amount_minor": 2500, "currency": "EUR"},
            )
            assert resp.get("status") == "SUCCESS"
            assert resp.get("operation_id") == "op_guest_101"
            assert "caid" in resp
            receipt = resp.get("receipt", {})
            assert receipt.get("status") == "HOST_AUTHORIZED"
            assert receipt.get("guest_cid") == 3

            # Verify Ed25519 signature
            pubkey = ed25519.Ed25519PublicKey.from_public_bytes(
                base64.b64decode(server.host_pubkey_b64)
            )
            sig_bytes = base64.b64decode(receipt["signature_b64"])
            unsigned = dict(receipt)
            del unsigned["signature_b64"]
            pubkey.verify(sig_bytes, encode_jcs(unsigned))
        finally:
            server.stop()


def test_falsification_unauthorized_guest_cid():
    with tempfile.TemporaryDirectory() as tmpdir:
        sock_path = os.path.join(tmpdir, "vsock_host.sock")
        server = MicroVMHostVsockServer(socket_path=sock_path, authorized_guest_cids=[3])
        server.start()
        try:
            # Client with unauthorized CID=99
            client = MicroVMGuestClient(socket_path=sock_path, guest_cid=99)
            resp = client.submit_proposal(
                operation_id="op_rogue_99",
                tool_name="probe_network",
                arguments={"target": "10.0.0.1"},
            )
            assert resp.get("status") == "ERROR"
            assert "HALT_UNAUTHORIZED_GUEST_CID" in resp.get("detail", "")
        finally:
            server.stop()


def test_falsification_direct_egress_attempt_blocked():
    with tempfile.TemporaryDirectory() as tmpdir:
        sock_path = os.path.join(tmpdir, "vsock_host.sock")
        server = MicroVMHostVsockServer(socket_path=sock_path, authorized_guest_cids=[3])
        server.start()
        try:
            client = MicroVMGuestClient(socket_path=sock_path, guest_cid=3)
            resp = client.submit_proposal(
                operation_id="op_bypass_attempt",
                tool_name="external_http_fetch",
                arguments={"url": "https://attacker.com"},
                direct_egress_attempted=True,
            )
            assert resp.get("status") == "ERROR"
            assert "HALT_DIRECT_EGRESS_FORBIDDEN" in resp.get("detail", "")
        finally:
            server.stop()


def test_banned_words_absence_in_vsock_files():
    for fpath in ["src/microvm_vsock_channel.py", "tests/test_microvm_vsock_channel.py"]:
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read().lower()
        forbidden = [
            "guaran" + "tee",
            "bullet" + "proof",
            "enterprise-" + "grade",
            "production-" + "safe",
            "100% " + "secure",
            "unassail" + "able",
        ]
        for word in forbidden:
            assert word not in text, f"Banned word '{word}' found in {fpath}"
