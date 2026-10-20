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
src/secure_mcp_uds_boundary.py — Secure MCP Unix Domain Socket (UDS) Boundary & Peer Identity

Implements local IPC boundaries for Model Context Protocol (MCP) servers:
1. Transport Control: Unix Domain Socket (UDS) with strict 0o600 permissions,
   explicitly denying TCP 127.0.0.1 connection attempts (HALT_TCP_LOCALHOST_DENIED).
2. Kernel Peer Credential Inspection: Linux SO_PEERCRED / Darwin LOCAL_PEERCRED + LOCAL_PEEREPID,
   rejecting peer UID mismatches (HALT_PEER_UID_MISMATCH).
3. Process Lineage & Binary Hash Binding: executable SHA-256 verification and PID reuse detection
   (HALT_PID_REUSE_DETECTED, HALT_EXECUTABLE_HASH_MISMATCH).
4. Ed25519 Capability Token Gating: RFC 8785 JCS signed tokens with audience, TTL, nonce replay,
   and tool scope enforcement (defeating Confused Deputy).
5. Audit Evidence Logging: append-only JSONL log with RFC 8785 JCS canonical formatting and SHA-256 digests.
"""

import base64
import ctypes
import hashlib
import json
import os
import socket
import struct
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


HALT_TCP_LOCALHOST_DENIED = "HALT_TCP_LOCALHOST_DENIED"
HALT_PEER_UID_MISMATCH = "HALT_PEER_UID_MISMATCH"
HALT_PID_REUSE_DETECTED = "HALT_PID_REUSE_DETECTED"
HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE = "HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE"
HALT_AUDIENCE_MISMATCH = "HALT_AUDIENCE_MISMATCH"
HALT_CAPABILITY_TOKEN_EXPIRED = "HALT_CAPABILITY_TOKEN_EXPIRED"
HALT_TOOL_SCOPE_NOT_AUTHORIZED = "HALT_TOOL_SCOPE_NOT_AUTHORIZED"
HALT_TOKEN_NONCE_REPLAY = "HALT_TOKEN_NONCE_REPLAY"
HALT_EXECUTABLE_HASH_MISMATCH = "HALT_EXECUTABLE_HASH_MISMATCH"
HALT_EXECUTABLE_NOT_FOUND = "HALT_EXECUTABLE_NOT_FOUND"


class McpSecurityHaltError(Exception):
    """Raised when an MCP connection or invocation violates boundary policy."""

    def __init__(self, halt_code: str, detail: str = ""):
        self.halt_code = halt_code
        self.detail = detail
        self.response: Optional[Dict[str, Any]] = None
        message = f"{halt_code}: {detail}" if detail else halt_code
        super().__init__(message)


@dataclass(frozen=True)
class PeerCredentials:
    """Kernel peer credentials extracted from an active Unix Domain Socket."""

    pid: int
    uid: int
    gid: int


@dataclass
class CapabilityToken:
    """Ed25519-signed capability token authorizing specific tool execution."""

    token_id: str
    issuer_did: str
    audience: str
    client_pid: int
    allowed_tools: List[str]
    issued_at: float
    expires_at: float
    nonce: str
    signature_b64: str = ""

    def to_claims_dict(self) -> Dict[str, Any]:
        return {
            "allowed_tools": list(self.allowed_tools),
            "audience": self.audience,
            "client_pid": self.client_pid,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "issuer_did": self.issuer_did,
            "nonce": self.nonce,
            "token_id": self.token_id,
        }

    def canonical_bytes(self) -> bytes:
        return encode_jcs(self.to_claims_dict())

    def sign(self, private_key: ed25519.Ed25519PrivateKey) -> str:
        sig = private_key.sign(self.canonical_bytes())
        self.signature_b64 = base64.b64encode(sig).decode("ascii")
        return self.signature_b64

    def verify(self, public_key: ed25519.Ed25519PublicKey) -> bool:
        if not self.signature_b64:
            return False
        try:
            sig_bytes = base64.b64decode(self.signature_b64)
            public_key.verify(sig_bytes, self.canonical_bytes())
            return True
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        d = self.to_claims_dict()
        d["signature_b64"] = self.signature_b64
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapabilityToken":
        return cls(
            token_id=str(data.get("token_id", "")),
            issuer_did=str(data.get("issuer_did", "")),
            audience=str(data.get("audience", "")),
            client_pid=int(data.get("client_pid", 0)),
            allowed_tools=list(data.get("allowed_tools", [])),
            issued_at=float(data.get("issued_at", 0.0)),
            expires_at=float(data.get("expires_at", 0.0)),
            nonce=str(data.get("nonce", "")),
            signature_b64=str(data.get("signature_b64", "")),
        )


def create_signed_capability_token(
    issuer_privkey: ed25519.Ed25519PrivateKey,
    issuer_did: str,
    audience: str,
    client_pid: int,
    allowed_tools: List[str],
    ttl_seconds: float = 60.0,
    nonce: Optional[str] = None,
    issued_at: Optional[float] = None,
    token_id: Optional[str] = None,
) -> CapabilityToken:
    """Helper to instantiate and sign an Ed25519 capability token."""
    now = time.time() if issued_at is None else issued_at
    tok = CapabilityToken(
        token_id=token_id or f"tok-{uuid.uuid4().hex[:12]}",
        issuer_did=issuer_did,
        audience=audience,
        client_pid=client_pid,
        allowed_tools=allowed_tools,
        issued_at=now,
        expires_at=now + ttl_seconds,
        nonce=nonce or f"nonce-{uuid.uuid4().hex[:16]}",
    )
    tok.sign(issuer_privkey)
    return tok


def get_process_info(pid: int) -> Tuple[Optional[str], Optional[float]]:
    """
    Evaluates peer process executable path and process creation/start timestamp.
    Under Darwin: uses libproc proc_pidpath and proc_pidinfo.
    Under Linux: uses /proc/<pid>/exe and /proc/<pid> stat.
    """
    if pid <= 0:
        return None, None

    exe_path: Optional[str] = None
    start_time: Optional[float] = None

    if sys.platform == "darwin":
        try:
            libproc = ctypes.CDLL("libproc.dylib")
            path_buf = ctypes.create_string_buffer(4096)
            path_len = libproc.proc_pidpath(pid, path_buf, 4096)
            if path_len > 0:
                exe_path = path_buf.value.decode("utf-8")
        except Exception:
            pass

        try:
            libproc = ctypes.CDLL("libproc.dylib")
            # PROC_PIDTBSDINFO = 3
            info_buf = ctypes.create_string_buffer(512)
            info_len = libproc.proc_pidinfo(pid, 3, ctypes.c_uint64(0), info_buf, 512)
            if info_len >= 136:
                start_sec, start_usec = struct.unpack_from("QQ", info_buf, 120)
                start_time = float(start_sec) + float(start_usec) / 1_000_000.0
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            exe_path = os.readlink(f"/proc/{pid}/exe")
        except Exception:
            pass

        try:
            st = os.stat(f"/proc/{pid}")
            start_time = float(st.st_ctime)
        except Exception:
            pass

    if not exe_path and pid == os.getpid():
        exe_path = sys.executable

    return exe_path, start_time


def compute_executable_sha256(path: str) -> str:
    """Computes SHA-256 digest of executable binary on disk."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def extract_peer_credentials(conn: socket.socket) -> PeerCredentials:
    """
    Extracts kernel peer credentials (pid, uid, gid) from an active Unix Domain Socket.
    Denies TCP sockets with HALT_TCP_LOCALHOST_DENIED.
    """
    if conn.family != socket.AF_UNIX:
        raise McpSecurityHaltError(
            HALT_TCP_LOCALHOST_DENIED,
            f"Socket family {conn.family} is not AF_UNIX; TCP loopback is forbidden",
        )

    if sys.platform.startswith("linux"):
        so_peercred = getattr(socket, "SO_PEERCRED", 17)
        cred_len = struct.calcsize("3i")
        cred_bytes = conn.getsockopt(socket.SOL_SOCKET, so_peercred, cred_len)
        pid, uid, gid = struct.unpack("3i", cred_bytes)
        return PeerCredentials(pid=pid, uid=uid, gid=gid)
    elif sys.platform == "darwin":
        local_peercred = getattr(socket, "LOCAL_PEERCRED", 1)
        cred_bytes = conn.getsockopt(0, local_peercred, 1024)
        _version, uid = struct.unpack_from("II", cred_bytes, 0)

        # LOCAL_PEEREPID = 3, SOL_LOCAL = 0
        try:
            pid_bytes = conn.getsockopt(0, 3, 4)
            pid = struct.unpack("i", pid_bytes)[0]
        except Exception:
            pid = -1

        gid = os.getgid()
        if len(cred_bytes) >= 12:
            try:
                gid = struct.unpack_from("I", cred_bytes, 12)[0]
            except Exception:
                pass

        return PeerCredentials(pid=pid, uid=uid, gid=gid)
    else:
        raise McpSecurityHaltError(
            "HALT_UNSUPPORTED_PLATFORM",
            f"Peer credential extraction not implemented for platform {sys.platform}",
        )


class SecureMcpUdsBoundaryServer:
    """
    Unix Domain Socket Boundary Server for Model Context Protocol (MCP).
    Enforces kernel peer credentials, process binding, Ed25519 capability gating,
    and append-only JCS audit logging.
    """

    def __init__(
        self,
        mcp_server_id: str,
        socket_path: Optional[str | Path] = None,
        trusted_issuer_pubkeys: Optional[Dict[str, ed25519.Ed25519PublicKey]] = None,
        server_private_key: Optional[ed25519.Ed25519PrivateKey] = None,
        allowed_executable_digests: Optional[Set[str]] = None,
        expected_uid: Optional[int] = None,
        audit_log_path: Optional[str | Path] = None,
        clock_skew_tolerance: float = 0.5,
    ):
        self.mcp_server_id = mcp_server_id
        self.socket_path = Path(socket_path) if socket_path else None
        self.trusted_issuer_pubkeys = trusted_issuer_pubkeys or {}
        self.server_private_key = server_private_key or ed25519.Ed25519PrivateKey.generate()
        self.server_public_key = self.server_private_key.public_key()
        self.allowed_executable_digests = (
            {d.lower().removeprefix("sha256:") for d in allowed_executable_digests}
            if allowed_executable_digests is not None
            else None
        )
        self.expected_uid = expected_uid if expected_uid is not None else os.getuid()
        self.audit_log_path = Path(audit_log_path) if audit_log_path else None
        self.clock_skew_tolerance = clock_skew_tolerance

        self._tools: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._seen_nonces: Set[str] = set()
        self._server_sock: Optional[socket.socket] = None
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._last_audit_hash = "0" * 64
        self.audit_records: List[Dict[str, Any]] = []

    def register_tool(self, name: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """Registers a callable tool on this boundary server."""
        self._tools[name] = handler

    def _extract_peer_credentials(self, conn: socket.socket) -> PeerCredentials:
        return extract_peer_credentials(conn)

    def _verify_peer_credentials(self, creds: PeerCredentials) -> None:
        if creds.uid != self.expected_uid:
            raise McpSecurityHaltError(
                HALT_PEER_UID_MISMATCH,
                f"Peer UID {creds.uid} does not match expected UID {self.expected_uid}",
            )

    def _verify_process_binding(
        self, peer_credentials: PeerCredentials, token: CapabilityToken
    ) -> None:
        if peer_credentials.pid != token.client_pid:
            raise McpSecurityHaltError(
                HALT_PID_REUSE_DETECTED,
                f"Peer kernel PID {peer_credentials.pid} does not match token client_pid {token.client_pid}",
            )

        exe_path, start_time = get_process_info(peer_credentials.pid)

        # PID reuse protection:
        # If the process was created after the capability token's issuance time,
        # the PID was recycled after token issuance.
        if start_time is not None and token.issued_at > 0:
            if start_time > (token.issued_at + self.clock_skew_tolerance):
                raise McpSecurityHaltError(
                    HALT_PID_REUSE_DETECTED,
                    f"Peer process start time {start_time} is after token issued_at {token.issued_at} (PID recycled)",
                )

        # Executable digest allowlist check
        if self.allowed_executable_digests is not None:
            if not exe_path or not os.path.exists(exe_path):
                raise McpSecurityHaltError(
                    HALT_EXECUTABLE_NOT_FOUND,
                    f"Peer executable for PID {peer_credentials.pid} not found on disk",
                )
            digest = compute_executable_sha256(exe_path).lower()
            if digest not in self.allowed_executable_digests:
                raise McpSecurityHaltError(
                    HALT_EXECUTABLE_HASH_MISMATCH,
                    f"Peer executable SHA-256 digest {digest} is not in allowed executable digests",
                )

    def _verify_capability_token(self, token: CapabilityToken, requested_tool: str) -> None:
        if not token.signature_b64:
            raise McpSecurityHaltError(
                HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE,
                "Capability token missing Ed25519 signature",
            )

        issuer_pubkey = self.trusted_issuer_pubkeys.get(token.issuer_did)
        if not issuer_pubkey:
            raise McpSecurityHaltError(
                HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE,
                f"Untrusted or unknown token issuer: {token.issuer_did}",
            )

        if not token.verify(issuer_pubkey):
            raise McpSecurityHaltError(
                HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE,
                "Cryptographic signature verification failed on capability token",
            )

        if token.audience != self.mcp_server_id:
            raise McpSecurityHaltError(
                HALT_AUDIENCE_MISMATCH,
                f"Capability token audience '{token.audience}' does not match server '{self.mcp_server_id}'",
            )

        now = time.time()
        if now > token.expires_at:
            raise McpSecurityHaltError(
                HALT_CAPABILITY_TOKEN_EXPIRED,
                f"Capability token expired at {token.expires_at} (current time {now})",
            )

        if token.nonce in self._seen_nonces:
            raise McpSecurityHaltError(
                HALT_TOKEN_NONCE_REPLAY,
                f"Capability token nonce '{token.nonce}' has already been evaluated",
            )
        self._seen_nonces.add(token.nonce)

        if requested_tool not in token.allowed_tools:
            raise McpSecurityHaltError(
                HALT_TOOL_SCOPE_NOT_AUTHORIZED,
                f"Requested tool '{requested_tool}' is not in authorized tool scope {token.allowed_tools}",
            )

    def _record_audit_event(
        self,
        event_type: str,
        disposition: str,
        halt_code: Optional[str] = None,
        peer_creds: Optional[PeerCredentials] = None,
        token: Optional[CapabilityToken] = None,
        requested_tool: Optional[str] = None,
        detail: Optional[str] = None,
        payload_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        entry_payload = {
            "disposition": disposition,
            "event_type": event_type,
            "halt_code": halt_code,
            "mcp_server_id": self.mcp_server_id,
            "peer_pid": peer_creds.pid if peer_creds else None,
            "peer_uid": peer_creds.uid if peer_creds else None,
            "prev_hash": self._last_audit_hash,
            "requested_tool": requested_tool,
            "timestamp": time.time(),
            "token_id": token.token_id if token else None,
        }
        if detail:
            entry_payload["detail"] = detail
        if payload_hash:
            entry_payload["payload_hash"] = payload_hash

        canonical_bytes = encode_jcs(entry_payload)
        entry_hash = hashlib.sha256(canonical_bytes).hexdigest()

        full_entry = dict(entry_payload)
        full_entry["entry_hash"] = entry_hash
        self._last_audit_hash = entry_hash
        self.audit_records.append(full_entry)

        if self.audit_log_path:
            line = encode_jcs(full_entry).decode("utf-8") + "\n"
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()

        return full_entry

    def handle_connection(
        self, conn: socket.socket, raise_on_halt: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Processes an incoming connection, enforcing transport, peer credentials,
        process binding, and capability token gating.
        """
        peer_creds: Optional[PeerCredentials] = None
        token: Optional[CapabilityToken] = None
        requested_tool: Optional[str] = None
        request_id: str = ""

        try:
            # 1. Transport Control: Deny non-AF_UNIX sockets
            if conn.family != socket.AF_UNIX:
                raise McpSecurityHaltError(
                    HALT_TCP_LOCALHOST_DENIED,
                    f"Socket family {conn.family} is not AF_UNIX; TCP loopback is forbidden",
                )

            # 2. Kernel Peer Credential Inspection
            peer_creds = self._extract_peer_credentials(conn)
            self._verify_peer_credentials(peer_creds)

            # 3. Read message frame
            raw = b""
            while not raw.endswith(b"\n"):
                chunk = conn.recv(4096)
                if not chunk:
                    break
                raw += chunk

            if not raw:
                return None

            payload_hash = hashlib.sha256(raw).hexdigest()
            try:
                req_data = json.loads(raw.decode("utf-8"))
            except Exception as e:
                raise McpSecurityHaltError(
                    HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE,
                    f"Failed to parse request JSON: {e}",
                )

            request_id = str(req_data.get("request_id", ""))
            requested_tool = str(req_data.get("tool_name", ""))
            arguments = req_data.get("arguments", {})
            raw_token = req_data.get("capability_token")

            if not raw_token or not isinstance(raw_token, dict):
                raise McpSecurityHaltError(
                    HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE,
                    "Request missing capability token dictionary",
                )

            token = CapabilityToken.from_dict(raw_token)

            # 4. Ed25519 Capability Token Gating
            self._verify_capability_token(token, requested_tool)

            # 5. Process Lineage & Binary Hash Binding
            self._verify_process_binding(peer_creds, token)

            # 6. Tool Execution
            tool_fn = self._tools.get(requested_tool)
            if not tool_fn:
                raise McpSecurityHaltError(
                    HALT_TOOL_SCOPE_NOT_AUTHORIZED,
                    f"Tool '{requested_tool}' not registered on server",
                )

            result = tool_fn(arguments)

            # 7. Formulate and sign response
            resp_payload = {
                "disposition": "AUTHORIZED",
                "mcp_server_id": self.mcp_server_id,
                "request_id": request_id,
                "result": result,
                "status": "SUCCESS",
                "timestamp": time.time(),
                "tool_name": requested_tool,
            }
            canonical_resp = encode_jcs(resp_payload)
            sig = self.server_private_key.sign(canonical_resp)
            resp_dict = dict(resp_payload)
            resp_dict["signature_b64"] = base64.b64encode(sig).decode("ascii")

            # 8. Audit Logging
            self._record_audit_event(
                event_type="AUTHORIZED_DISPATCH",
                disposition="AUTHORIZED",
                peer_creds=peer_creds,
                token=token,
                requested_tool=requested_tool,
                payload_hash=payload_hash,
            )

            wire_bytes = encode_jcs(resp_dict) + b"\n"
            conn.sendall(wire_bytes)
            return resp_dict

        except McpSecurityHaltError as halt_err:
            self._record_audit_event(
                event_type="REQUEST_REJECTED",
                disposition="HALTED",
                halt_code=halt_err.halt_code,
                peer_creds=peer_creds,
                token=token,
                requested_tool=requested_tool,
                detail=halt_err.detail,
            )

            err_payload = {
                "disposition": "HALTED",
                "error": halt_err.detail,
                "halt_code": halt_err.halt_code,
                "mcp_server_id": self.mcp_server_id,
                "request_id": request_id,
                "status": "HALTED",
                "timestamp": time.time(),
            }
            canonical_err = encode_jcs(err_payload)
            sig = self.server_private_key.sign(canonical_err)
            err_dict = dict(err_payload)
            err_dict["signature_b64"] = base64.b64encode(sig).decode("ascii")

            try:
                conn.sendall(encode_jcs(err_dict) + b"\n")
            except Exception:
                pass

            if raise_on_halt:
                raise halt_err

            return err_dict

        except Exception as exc:
            self._record_audit_event(
                event_type="INTERNAL_ERROR",
                disposition="HALTED",
                halt_code="HALT_INTERNAL_ERROR",
                peer_creds=peer_creds,
                token=token,
                requested_tool=requested_tool,
                detail=str(exc),
            )
            if raise_on_halt:
                raise exc
            return None

        finally:
            try:
                conn.close()
            except Exception:
                pass

    def bind_and_listen(self, backlog: int = 128) -> None:
        """Binds to the local Unix Domain Socket with permissions 0o600."""
        if not self.socket_path:
            raise ValueError("socket_path must be configured to bind")

        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        self.socket_path.parent.mkdir(parents=True, exist_ok=True)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(self.socket_path))
        os.chmod(str(self.socket_path), 0o600)
        sock.listen(backlog)
        sock.settimeout(0.2)
        self._server_sock = sock

    def start(self, backlog: int = 128) -> None:
        """Starts background listener worker thread."""
        self.bind_and_listen(backlog=backlog)
        self._running = True
        self._worker_thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._worker_thread.start()

    def _serve_loop(self) -> None:
        while self._running and self._server_sock:
            try:
                conn, _ = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception:
                break

            try:
                self.handle_connection(conn, raise_on_halt=False)
            except Exception:
                pass

    def stop(self) -> None:
        """Stops background listener and cleans up ephemeral socket file."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
            self._worker_thread = None

        if self.socket_path and os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except Exception:
                pass

    def __enter__(self) -> "SecureMcpUdsBoundaryServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


class SecureMcpUdsClient:
    """
    Client for interacting with Secure MCP UDS Boundary Server.
    Enforces local Unix Domain Socket transport and verifies server responses.
    """

    def __init__(
        self,
        socket_path: Optional[str | Path] = None,
        server_public_key: Optional[ed25519.Ed25519PublicKey] = None,
        timeout: float = 5.0,
    ):
        self.socket_path = Path(socket_path) if socket_path else None
        self.server_public_key = server_public_key
        self.timeout = timeout

    def connect_tcp(self, host: str, port: int) -> None:
        """
        Explicitly denies TCP connection attempts, enforcing local UDS transport.
        """
        raise McpSecurityHaltError(
            HALT_TCP_LOCALHOST_DENIED,
            f"TCP connection to {host}:{port} is explicitly denied; local UDS required",
        )

    def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        capability_token: CapabilityToken,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sends an RFC 8785 JCS canonical request with capability token over UDS,
        verifying the server's signed response.
        """
        if not self.socket_path:
            raise ValueError("socket_path must be configured on client")

        req_id = request_id or str(uuid.uuid4())
        req_msg = {
            "arguments": arguments,
            "capability_token": capability_token.to_dict(),
            "request_id": req_id,
            "tool_name": tool_name,
        }
        wire_req = encode_jcs(req_msg) + b"\n"

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect(str(self.socket_path))
            sock.sendall(wire_req)

            raw = b""
            while not raw.endswith(b"\n"):
                chunk = sock.recv(4096)
                if not chunk:
                    break
                raw += chunk

            if not raw:
                raise McpSecurityHaltError(
                    "HALT_EMPTY_SERVER_RESPONSE",
                    "Connection closed without server response",
                )

            resp_data = json.loads(raw.decode("utf-8"))

            # Verify server signature if server public key configured
            if self.server_public_key and "signature_b64" in resp_data:
                sig_b64 = resp_data["signature_b64"]
                unsigned_payload = {k: v for k, v in resp_data.items() if k != "signature_b64"}
                canonical_bytes = encode_jcs(unsigned_payload)
                try:
                    sig_bytes = base64.b64decode(sig_b64)
                    self.server_public_key.verify(sig_bytes, canonical_bytes)
                except Exception:
                    raise McpSecurityHaltError(
                        "HALT_INVALID_SERVER_SIGNATURE",
                        "Server response signature failed cryptographic verification",
                    )

            if resp_data.get("status") == "HALTED":
                halt_code = resp_data.get("halt_code", "UNKNOWN_HALT")
                err_detail = resp_data.get("error", "")
                exc = McpSecurityHaltError(halt_code, err_detail)
                exc.response = resp_data
                raise exc

            return resp_data

        finally:
            try:
                sock.close()
            except Exception:
                pass
