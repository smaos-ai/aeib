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
import os
import tempfile
import time
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.microvm_vsock_channel import (
    MicroVMGuestClient,
    MicroVMHostVsockServer,
    VsockMessageFrame,
)


def test_frame_serialization_roundtrip():
    payload = b'{"action": "test_echo", "val": 42}'
    frame = VsockMessageFrame(
        magic=VsockMessageFrame.MAGIC_CONST,
        version=1,
        msg_type=1,
        payload=payload,
    )
    raw = frame.serialize()
    deserialized, consumed = VsockMessageFrame.deserialize(raw)
    assert consumed == len(raw)
    assert deserialized.magic == VsockMessageFrame.MAGIC_CONST
    assert deserialized.version == 1
    assert deserialized.msg_type == 1
    assert deserialized.payload == payload


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
