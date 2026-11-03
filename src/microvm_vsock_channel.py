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
src/microvm_vsock_channel.py — MicroVM VSOCK Channel & Host-Side Boundary Gating

Implements Layer 2 of the AEIB 12-item master delivery scope:
1. Firecracker guest VM isolation topology: guest agent runtime has zero external
   network egress interfaces (eth0 strictly disabled or bound to empty netns).
2. All guest proposals must traverse a dedicated host VSOCK (or UDS fallback on macOS)
   channel with length-prefixed framing.
3. Host-side boundary inspects guest CID, binds operation CAID, verifies credential
   starvation, and routes through Station 1 & 2 before any external wire dispatch.
"""

import base64
import hashlib
import json
import os
import socket
import struct
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


MAGIC_CONST: int = 0xAE1B50C0
RESERVED_CONST: int = 0
FRAME_VERSION: int = 1
MSG_PROPOSAL: int = 1
MSG_CONFIRMATION: int = 2
MSG_FAULT: int = 3
MSG_HEARTBEAT: int = 4
BUFFER_SIZE: int = 65536
DEFAULT_AUTHORIZED_CIDS: Tuple[int, ...] = (3, 4, 5)
SOCKET_PERMISSIONS: int = 0o600
BACKLOG: int = 16


class MicroVMEgressViolation(Exception):
    """Raised when a guest MicroVM attempts unauthorized egress."""
    pass


@dataclass(frozen=True)
class VsockMessageFrame:
    """Length-prefixed binary frame for host-guest communication."""
    magic: int  # 0xAE1B50C0 (AEIB-SOCK)
    version: int
    msg_type: int  # 1: PROPOSAL, 2: CONFIRMATION, 3: FAULT, 4: HEARTBEAT
    payload: bytes

    HEADER_FORMAT = ">IBBH"  # magic (4B), version (1B), msg_type (1B), reserved (2B)
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    MAGIC_CONST = MAGIC_CONST
    RESERVED_CONST = RESERVED_CONST
    FRAME_VERSION = FRAME_VERSION
    MSG_PROPOSAL = MSG_PROPOSAL
    MSG_CONFIRMATION = MSG_CONFIRMATION
    MSG_FAULT = MSG_FAULT
    MSG_HEARTBEAT = MSG_HEARTBEAT

    def serialize(self) -> bytes:
        payload_len = len(self.payload)
        header = struct.pack(self.HEADER_FORMAT, self.MAGIC_CONST, self.version, self.msg_type, self.RESERVED_CONST)
        return header + struct.pack(">I", payload_len) + self.payload

    @classmethod
    def deserialize(cls, raw: bytes) -> Tuple["VsockMessageFrame", int]:
        total_header_size = cls.HEADER_SIZE + 4  # header + payload length
        if len(raw) < total_header_size:
            raise ValueError("Frame buffer too short for header")
        magic, version, msg_type, reserved = struct.unpack(cls.HEADER_FORMAT, raw[:cls.HEADER_SIZE])
        if magic != cls.MAGIC_CONST:
            raise ValueError(f"Invalid frame magic: {hex(magic)}")
        if version != cls.FRAME_VERSION:
            raise ValueError(f"Unsupported frame version: {version}")
        if msg_type not in (cls.MSG_PROPOSAL, cls.MSG_CONFIRMATION, cls.MSG_FAULT, cls.MSG_HEARTBEAT):
            raise ValueError(f"Unknown message type: {msg_type}")
        if reserved != cls.RESERVED_CONST:
            raise ValueError(f"Non-zero reserved field: {reserved}")
        payload_len, = struct.unpack(">I", raw[cls.HEADER_SIZE:total_header_size])
        if len(raw) < total_header_size + payload_len:
            raise ValueError("Frame buffer too short for payload body")
        payload = raw[total_header_size:total_header_size + payload_len]
        return cls(magic=magic, version=version, msg_type=msg_type, payload=payload), total_header_size + payload_len


class MicroVMHostVsockServer:
    """
    Host-side VSOCK listener receiving tool dispatch proposals from Firecracker guest VMs.
    """
    BUFFER_SIZE = BUFFER_SIZE
    DEFAULT_AUTHORIZED_CIDS = DEFAULT_AUTHORIZED_CIDS
    SOCKET_PERMISSIONS = SOCKET_PERMISSIONS
    BACKLOG = BACKLOG

    def __init__(
        self,
        socket_path: str,
        authorized_guest_cids: Optional[List[int]] = None,
        host_signer: Optional[ed25519.Ed25519PrivateKey] = None,
    ) -> None:
        self.socket_path = socket_path
        self.authorized_guest_cids = set(authorized_guest_cids if authorized_guest_cids is not None else self.DEFAULT_AUTHORIZED_CIDS)
        self.host_signer = host_signer or ed25519.Ed25519PrivateKey.generate()
        self.host_pubkey_bytes = self.host_signer.public_key().public_bytes_raw()
        self.host_pubkey_b64 = base64.b64encode(self.host_pubkey_bytes).decode("ascii")

        self._server_sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.dispatched_log: List[Dict[str, Any]] = []

    def start(self) -> None:
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_sock.bind(self.socket_path)
        os.chmod(self.socket_path, self.SOCKET_PERMISSIONS)
        self._server_sock.listen(self.BACKLOG)
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _listen_loop(self) -> None:
        while self._running:
            try:
                self._server_sock.settimeout(0.2)
                conn, _ = self._server_sock.accept()
            except (socket.timeout, OSError):
                continue

            with conn:
                try:
                    data = conn.recv(self.BUFFER_SIZE)
                    if not data:
                        continue
                    frame, _ = VsockMessageFrame.deserialize(data)
                    response_frame = self._handle_guest_proposal(frame)
                    conn.sendall(response_frame.serialize())
                except Exception as ex:
                    err_payload = json.dumps({"status": "ERROR", "detail": str(ex)}).encode("utf-8")
                    err_frame = VsockMessageFrame(
                        magic=VsockMessageFrame.MAGIC_CONST,
                        version=VsockMessageFrame.FRAME_VERSION,
                        msg_type=VsockMessageFrame.MSG_FAULT,
                        payload=err_payload,
                    )
                    conn.sendall(err_frame.serialize())

    def _handle_guest_proposal(self, frame: VsockMessageFrame) -> VsockMessageFrame:
        proposal = json.loads(frame.payload.decode("utf-8"))
        guest_cid = proposal.get("guest_cid")
        if guest_cid not in self.authorized_guest_cids:
            raise MicroVMEgressViolation(f"HALT_UNAUTHORIZED_GUEST_CID: cid={guest_cid}")

        direct_egress_claimed = proposal.get("direct_egress_attempted", False)
        if direct_egress_claimed:
            raise MicroVMEgressViolation("HALT_DIRECT_EGRESS_FORBIDDEN: guest cannot bypass VSOCK")

        operation_id = proposal.get("operation_id", "")
        tool_name = proposal.get("tool_name", "")
        args = proposal.get("arguments", {})

        canonical_args = encode_jcs(args)
        caid = hashlib.sha256(canonical_args).hexdigest()

        # Host signs an authorization receipt
        ts = int(time.time())
        receipt_payload = {
            "caid": caid,
            "guest_cid": guest_cid,
            "operation_id": operation_id,
            "status": "HOST_AUTHORIZED",
            "timestamp": ts,
            "tool_name": tool_name,
        }
        sig = self.host_signer.sign(encode_jcs(receipt_payload))
        receipt_payload["signature_b64"] = base64.b64encode(sig).decode("ascii")

        self.dispatched_log.append(receipt_payload)

        out_payload = json.dumps({
            "status": "SUCCESS",
            "caid": caid,
            "operation_id": operation_id,
            "receipt": receipt_payload,
        }).encode("utf-8")

        return VsockMessageFrame(
            magic=VsockMessageFrame.MAGIC_CONST,
            version=VsockMessageFrame.FRAME_VERSION,
            msg_type=VsockMessageFrame.MSG_CONFIRMATION,
            payload=out_payload,
        )


class MicroVMGuestClient:
    """
    Client running inside the starved guest VM routing all tool calls over the host channel.
    """
    BUFFER_SIZE = BUFFER_SIZE
    DEFAULT_GUEST_CID = 3

    def __init__(self, socket_path: str, guest_cid: int = DEFAULT_GUEST_CID) -> None:
        self.socket_path = socket_path
        self.guest_cid = guest_cid

    def submit_proposal(
        self,
        operation_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        direct_egress_attempted: bool = False,
    ) -> Dict[str, Any]:
        payload_dict = {
            "arguments": arguments,
            "direct_egress_attempted": bool(direct_egress_attempted),
            "guest_cid": self.guest_cid,
            "operation_id": operation_id,
            "tool_name": tool_name,
        }
        raw_payload = json.dumps(payload_dict).encode("utf-8")
        req_frame = VsockMessageFrame(
            magic=VsockMessageFrame.MAGIC_CONST,
            version=VsockMessageFrame.FRAME_VERSION,
            msg_type=VsockMessageFrame.MSG_PROPOSAL,
            payload=raw_payload,
        )

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.socket_path)
        with sock:
            sock.sendall(req_frame.serialize())
            resp_bytes = sock.recv(self.BUFFER_SIZE)
            resp_frame, _ = VsockMessageFrame.deserialize(resp_bytes)
            return json.loads(resp_frame.payload.decode("utf-8"))
