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
6. Resource bounds (tested under the stated model): newline-delimited request frames are capped at
   `max_frame_bytes` (HALT_FRAME_TOO_LARGE) and read within a per-connection deadline
   (HALT_FRAME_READ_TIMEOUT); connections are served by a bounded thread pool so one idle peer
   does not block other peers.
7. Socket directory hygiene: the socket is bound inside a dedicated 0o700 directory owned by the
   effective UID (symlinks refused, HALT_SOCKET_DIR_INSECURE) under umask 0o177.
8. Durable nonce replay cache: consumed nonces are appended (fsync) to a JSONL store with expiry
   and reloaded on construction; expired entries are pruned.
9. Strict JSON ingress: request frames (server) and response frames (client) are parsed with
   src/strict_json_ingress.loads_strict, so duplicate member names, NaN/Infinity and lone
   surrogates fail closed (HALT_STRICT_JSON_REJECTED) instead of being silently resolved.
10. Tool-definition pinning (opt-in per server via `tool_pins`): before a registered tool becomes
   dispatchable, the server's advertised definitions are checked against a
   src/mcp_schema_pinning.ToolDefinitionPinSet; definition change, added/removed tools and
   cross-server name shadowing halt with HALT_TOOL_DEFINITION_DRIFT, and calls to tools outside
   the pinned set halt with HALT_TOOL_NOT_PINNED. First-use pinning ("learn mode") is OFF by
   default. `McpToolPinGuard` and the signed pin-manifest helpers are shared with
   aeib_mcp_proxy.py and adapters/mcp/idempotent_mcp_proxy.py.
"""

import base64
import concurrent.futures
import ctypes
import hashlib
import json
import math
import os
import socket
import stat
import struct
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.mcp_schema_pinning import (
    ToolDefinitionFinding,
    ToolDefinitionPinSet,
    ToolDriftKind,
    ToolSetCheckResult,
)
from src.strict_json_ingress import StrictJSONError, loads_strict


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
HALT_FRAME_TOO_LARGE = "HALT_FRAME_TOO_LARGE"
HALT_FRAME_READ_TIMEOUT = "HALT_FRAME_READ_TIMEOUT"
HALT_SOCKET_DIR_INSECURE = "HALT_SOCKET_DIR_INSECURE"
HALT_NONCE_STORE_UNAVAILABLE = "HALT_NONCE_STORE_UNAVAILABLE"
HALT_NONCE_STORE_CORRUPT = "HALT_NONCE_STORE_CORRUPT"
HALT_STRICT_JSON_REJECTED = "HALT_STRICT_JSON_REJECTED"
HALT_INVALID_SERVER_RESPONSE = "HALT_INVALID_SERVER_RESPONSE"
HALT_TOOL_DEFINITION_DRIFT = "HALT_TOOL_DEFINITION_DRIFT"
HALT_TOOL_NOT_PINNED = "HALT_TOOL_NOT_PINNED"
HALT_TOOL_PIN_MANIFEST_INVALID = "HALT_TOOL_PIN_MANIFEST_INVALID"

# JSON-RPC error code used by the MCP proxies for tool-pin violations.
JSONRPC_TOOL_PIN_VIOLATION = -32040
TOOL_PIN_MANIFEST_VERSION = 1

DEFAULT_MAX_FRAME_BYTES = 1024 * 1024
DEFAULT_CONNECTION_TIMEOUT_S = 2.0
DEFAULT_MAX_WORKERS = 8
_RECV_CHUNK_BYTES = 65536


class McpSecurityHaltError(Exception):
    """Raised when an MCP connection or invocation violates boundary policy."""

    def __init__(self, halt_code: str, detail: str = ""):
        self.halt_code = halt_code
        self.detail = detail
        self.response: Optional[Dict[str, Any]] = None
        message = f"{halt_code}: {detail}" if detail else halt_code
        super().__init__(message)


# ---------------------------------------------------------------------------
# Tool-definition pinning shared by the three MCP boundaries
# ---------------------------------------------------------------------------


def finding_to_dict(finding: ToolDefinitionFinding) -> Dict[str, Any]:
    """JSON-safe view of a typed pinning finding (for error payloads and audit)."""
    return {
        "expected": finding.expected,
        "kind": finding.kind.value,
        "observed": finding.observed,
        "other_server_id": finding.other_server_id,
        "server_id": finding.server_id,
        "tool_name": finding.tool_name,
    }


class ToolPinViolation(McpSecurityHaltError):
    """Raised when a tool advertisement or call violates the approved pin set."""

    def __init__(self, halt_code: str, server_id: str,
                 findings: Iterable[ToolDefinitionFinding], detail: str):
        self.server_id = server_id
        self.findings: Tuple[ToolDefinitionFinding, ...] = tuple(findings)
        kinds = ",".join(f.kind.value for f in self.findings)
        super().__init__(halt_code, f"{detail} [server={server_id} findings={kinds}]")

    def to_error_data(self) -> Dict[str, Any]:
        return {
            "findings": [finding_to_dict(f) for f in self.findings],
            "halt_code": self.halt_code,
            "server_id": self.server_id,
        }

    def to_jsonrpc_error(self) -> Dict[str, Any]:
        return {
            "code": JSONRPC_TOOL_PIN_VIOLATION,
            "message": self.halt_code,
            "data": self.to_error_data(),
        }


class McpToolPinGuard:
    """
    Gates one upstream server's tool advertisements and tool calls against a
    ToolDefinitionPinSet (which may be shared by several guards so that name
    shadowing across servers is detected).

    * check_advertisement(tools): a server that has no approved pins is refused
      (UNPINNED_SERVER) unless learn_mode is True, in which case the first
      advertisement is pinned (and still refused if it shadows another server).
      For a pinned server any finding from check_server blocks the advertisement.
    * Any drift finding is latched: every later advertisement and call through
      this guard is refused until an operator builds a new guard from a
      reviewed pin set. UNPINNED_SERVER alone is not latched.
    * check_call(tool_name): refused while drift is latched; for a pinned server
      the tool must be present in the approved set. For an unpinned server the
      caller decides via `require_pins`.
    """

    def __init__(self, server_id: str, pin_set: Optional[ToolDefinitionPinSet] = None,
                 learn_mode: bool = False) -> None:
        if not isinstance(server_id, str) or not server_id:
            raise ValueError("server_id must be a non-empty string")
        self.server_id = server_id
        self.pin_set = pin_set if pin_set is not None else ToolDefinitionPinSet()
        self.learn_mode = learn_mode is True
        self._lock = threading.Lock()
        self._latched: Tuple[ToolDefinitionFinding, ...] = ()

    @property
    def latched_findings(self) -> Tuple[ToolDefinitionFinding, ...]:
        return self._latched

    def is_pinned(self) -> bool:
        probe = self.pin_set.check_server(self.server_id, [])
        return all(f.kind is not ToolDriftKind.UNPINNED_SERVER for f in probe.findings)

    def _raise_latched(self, what: str) -> None:
        if self._latched:
            raise ToolPinViolation(
                HALT_TOOL_DEFINITION_DRIFT, self.server_id, self._latched,
                f"{what} refused: tool-definition drift latched for this server",
            )

    def check_advertisement(self, tools: Any) -> ToolSetCheckResult:
        """Verify a tools/list result; raises ToolPinViolation on any finding."""
        with self._lock:
            self._raise_latched("tools/list")
            if not isinstance(tools, list):
                finding = ToolDefinitionFinding(ToolDriftKind.INVALID_DEFINITION, self.server_id, "")
                self._latched = (finding,)
                raise ToolPinViolation(
                    HALT_TOOL_DEFINITION_DRIFT, self.server_id, self._latched,
                    "tools/list result.tools is not a JSON array",
                )
            if self.is_pinned():
                result = self.pin_set.check_server(self.server_id, tools)
            elif self.learn_mode:
                result = self.pin_set.pin_server(self.server_id, tools)
            else:
                raise ToolPinViolation(
                    HALT_TOOL_NOT_PINNED, self.server_id,
                    (ToolDefinitionFinding(ToolDriftKind.UNPINNED_SERVER, self.server_id, ""),),
                    "no approved tool pins for server and learn mode is off",
                )
            if result.findings:
                self._latched = tuple(result.findings)
                raise ToolPinViolation(
                    HALT_TOOL_DEFINITION_DRIFT, self.server_id, self._latched,
                    "tools/list advertisement does not match approved pins",
                )
            return result

    def check_call(self, tool_name: Any, require_pins: bool = True) -> None:
        """Refuse a tools/call that is not covered by the approved pin set."""
        with self._lock:
            self._raise_latched("tools/call")
            if not self.is_pinned():
                if require_pins:
                    raise ToolPinViolation(
                        HALT_TOOL_NOT_PINNED, self.server_id,
                        (ToolDefinitionFinding(ToolDriftKind.UNPINNED_SERVER, self.server_id, ""),),
                        "tools/call refused: no approved tool pins for server",
                    )
                return
            name = tool_name if isinstance(tool_name, str) else ""
            if name not in self.pin_set.pinned_digests(self.server_id):
                raise ToolPinViolation(
                    HALT_TOOL_NOT_PINNED, self.server_id,
                    (ToolDefinitionFinding(ToolDriftKind.TOOL_ADDED, self.server_id, name),),
                    f"tools/call refused: tool {name!r} is not in the approved pin set",
                )


def _manifest_signing_payload(servers: Mapping[str, Any]) -> Dict[str, Any]:
    return {"servers": servers, "version": TOOL_PIN_MANIFEST_VERSION}


def sign_tool_pin_manifest(servers: Mapping[str, List[Dict[str, Any]]],
                           private_key: ed25519.Ed25519PrivateKey) -> Dict[str, Any]:
    """Return a manifest {servers, version, signature_b64}; Ed25519 over JCS(servers, version)."""
    payload = _manifest_signing_payload(dict(servers))
    signature = private_key.sign(encode_jcs(payload))
    doc = dict(payload)
    doc["signature_b64"] = base64.b64encode(signature).decode("ascii")
    return doc


def load_tool_pin_manifest(source: str | Path | bytes,
                           trusted_public_key: ed25519.Ed25519PublicKey) -> ToolDefinitionPinSet:
    """
    Load a reviewed, Ed25519-signed tool pin manifest into a ToolDefinitionPinSet.
    `source` is a path or the raw manifest bytes. Parsing uses loads_strict; any
    signature, shape, definition or cross-server shadowing problem halts with
    HALT_TOOL_PIN_MANIFEST_INVALID (fail closed, nothing is partially pinned).
    """
    raw = source if isinstance(source, bytes) else Path(source).read_bytes()
    try:
        doc = loads_strict(raw)
    except StrictJSONError as exc:
        raise McpSecurityHaltError(HALT_TOOL_PIN_MANIFEST_INVALID, f"manifest JSON rejected: {exc}")
    if not isinstance(doc, dict) or set(doc) != {"servers", "signature_b64", "version"}:
        raise McpSecurityHaltError(
            HALT_TOOL_PIN_MANIFEST_INVALID,
            "manifest must contain exactly servers, version, signature_b64",
        )
    servers = doc["servers"]
    if doc["version"] != TOOL_PIN_MANIFEST_VERSION or not isinstance(servers, dict):
        raise McpSecurityHaltError(HALT_TOOL_PIN_MANIFEST_INVALID, "unsupported manifest version or servers shape")
    try:
        signature = base64.b64decode(str(doc["signature_b64"]), validate=True)
        trusted_public_key.verify(signature, encode_jcs(_manifest_signing_payload(servers)))
    except Exception:
        raise McpSecurityHaltError(HALT_TOOL_PIN_MANIFEST_INVALID, "manifest signature verification failed")
    staged = ToolDefinitionPinSet()
    for server_id in sorted(servers):
        tools = servers[server_id]
        if not server_id or not isinstance(tools, list):
            raise McpSecurityHaltError(
                HALT_TOOL_PIN_MANIFEST_INVALID, f"server {server_id!r} must map to a tool list"
            )
        result = staged.pin_server(server_id, tools)
        if result.findings:
            raise ToolPinViolation(
                HALT_TOOL_PIN_MANIFEST_INVALID, server_id, result.findings,
                "manifest tool definitions rejected",
            )
    return staged


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
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def extract_peer_credentials(conn: socket.socket, platform: Optional[str] = None) -> PeerCredentials:
    """
    Extracts kernel peer credentials (pid, uid, gid) from an active Unix Domain Socket.
    Denies TCP sockets with HALT_TCP_LOCALHOST_DENIED. `platform` defaults to sys.platform.
    """
    platform = sys.platform if platform is None else platform
    if conn.family != socket.AF_UNIX:
        raise McpSecurityHaltError(
            HALT_TCP_LOCALHOST_DENIED,
            f"Socket family {conn.family} is not AF_UNIX; TCP loopback is forbidden",
        )

    if platform.startswith("linux"):
        so_peercred = getattr(socket, "SO_PEERCRED", 17)
        cred_len = struct.calcsize("3i")
        cred_bytes = conn.getsockopt(socket.SOL_SOCKET, so_peercred, cred_len)
        pid, uid, gid = struct.unpack("3i", cred_bytes)
        return PeerCredentials(pid=pid, uid=uid, gid=gid)
    elif platform == "darwin":
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
            f"Peer credential extraction not implemented for platform {platform}",
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
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
        connection_timeout: float = DEFAULT_CONNECTION_TIMEOUT_S,
        max_workers: int = DEFAULT_MAX_WORKERS,
        nonce_store_path: Optional[str | Path] = None,
        tool_pins: Optional[ToolDefinitionPinSet] = None,
        tool_pin_learn_mode: bool = False,
    ):
        if max_frame_bytes < 1:
            raise ValueError("max_frame_bytes must be >= 1")
        if connection_timeout <= 0:
            raise ValueError("connection_timeout must be > 0")
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
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
        self.max_frame_bytes = int(max_frame_bytes)
        self.connection_timeout = float(connection_timeout)
        self.max_workers = int(max_workers)
        # Default nonce store lives beside the socket inside its dedicated 0o700 directory.
        if nonce_store_path is not None:
            self.nonce_store_path: Optional[Path] = Path(nonce_store_path)
        elif self.socket_path is not None:
            self.nonce_store_path = self.socket_path.parent / f"{self.socket_path.name}.nonces.jsonl"
        else:
            self.nonce_store_path = None

        self._tools: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._tool_definitions: Dict[str, Dict[str, Any]] = {}
        # Tool-definition pinning is enforced only when a pin set is supplied or learn mode
        # is explicitly enabled; learn mode is OFF by default.
        self.tool_pin_learn_mode = tool_pin_learn_mode is True
        self._tool_pin_guard: Optional[McpToolPinGuard] = (
            McpToolPinGuard(mcp_server_id, tool_pins, learn_mode=self.tool_pin_learn_mode)
            if tool_pins is not None or self.tool_pin_learn_mode
            else None
        )
        # Guards nonce cache, nonce store, and audit hash chain across worker threads.
        self._state_lock = threading.RLock()
        # nonce -> expiry in integer milliseconds since the epoch
        self._seen_nonces: Dict[str, int] = {}
        self._server_sock: Optional[socket.socket] = None
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._slots: Optional[threading.BoundedSemaphore] = None
        self._last_audit_hash = "0" * 64
        self.audit_records: List[Dict[str, Any]] = []
        self._load_nonce_store()

    # ------------------------------------------------------------------
    # Durable nonce replay cache
    # ------------------------------------------------------------------

    def _load_nonce_store(self) -> None:
        """Reloads consumed nonces from the append-only store, pruning expired entries."""
        path = self.nonce_store_path
        if path is None or not os.path.lexists(path):
            return
        if stat.S_ISLNK(os.lstat(path).st_mode):
            raise McpSecurityHaltError(HALT_NONCE_STORE_CORRUPT, f"Nonce store {path} is a symlink")
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # A trailing torn line (crash mid-append) is tolerated; that nonce never reached dispatch.
        complete, _sep, _torn = text.rpartition("\n")
        lines = complete.split("\n")
        now_ms = int(time.time() * 1000)
        loaded: Dict[str, int] = {}
        total = 0
        for line in lines:
            if not line:
                continue
            total += 1
            try:
                rec = json.loads(line)
                nonce = rec["nonce"]
                expiry_ms = rec["expires_at_ms"]
            except Exception as exc:
                raise McpSecurityHaltError(
                    HALT_NONCE_STORE_CORRUPT, f"Malformed nonce store entry: {exc}"
                )
            if not isinstance(nonce, str) or not isinstance(expiry_ms, int):
                raise McpSecurityHaltError(HALT_NONCE_STORE_CORRUPT, "Nonce store entry has wrong types")
            if expiry_ms >= now_ms:
                loaded[nonce] = max(expiry_ms, loaded.get(nonce, expiry_ms))
        self._seen_nonces = loaded
        if len(loaded) != total:
            self._rewrite_nonce_store()

    def _rewrite_nonce_store(self) -> None:
        """Atomically compacts the nonce store to the live (unexpired) entries."""
        path = self.nonce_store_path
        if path is None:
            return
        tmp = path.with_name(path.name + ".tmp")
        data = "".join(
            encode_jcs({"expires_at_ms": exp, "nonce": n}).decode("utf-8") + "\n"
            for n, exp in sorted(self._seen_nonces.items())
        )
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, data.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(str(tmp), str(path))

    def _persist_nonce(self, nonce: str, expiry_ms: int) -> None:
        path = self.nonce_store_path
        if path is None:
            return
        line = encode_jcs({"expires_at_ms": expiry_ms, "nonce": nonce}) + b"\n"
        try:
            fd = os.open(
                str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600
            )
            try:
                os.write(fd, line)
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError as exc:
            raise McpSecurityHaltError(
                HALT_NONCE_STORE_UNAVAILABLE, f"Failed to persist consumed nonce: {exc}"
            )

    def _consume_nonce(self, token: CapabilityToken) -> None:
        """Atomically checks, records, and durably persists a token nonce (fail-closed)."""
        expiry_ms = int(math.ceil(token.expires_at * 1000))
        with self._state_lock:
            now_ms = int(time.time() * 1000)
            expired = [n for n, exp in self._seen_nonces.items() if exp < now_ms]
            for n in expired:
                del self._seen_nonces[n]
            if token.nonce in self._seen_nonces:
                raise McpSecurityHaltError(
                    HALT_TOKEN_NONCE_REPLAY,
                    f"Capability token nonce '{token.nonce}' has already been evaluated",
                )
            self._persist_nonce(token.nonce, expiry_ms)
            self._seen_nonces[token.nonce] = expiry_ms

    def register_tool(
        self,
        name: str,
        handler: Callable[[Dict[str, Any]], Any],
        definition: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Registers a callable tool on this boundary server. `definition` is the MCP tool
        definition (name, description, inputSchema) checked against `tool_pins`; a tool
        registered without one cannot pass a configured pin check.
        """
        if definition is not None and (not isinstance(definition, dict) or definition.get("name") != name):
            raise ValueError("tool definition must be an object whose name equals the registered name")
        self._tools[name] = handler
        if definition is None:
            self._tool_definitions.pop(name, None)
        else:
            self._tool_definitions[name] = dict(definition)

    def advertised_tool_definitions(self) -> List[Dict[str, Any]]:
        """Current tool advertisement (registration without a definition yields {'name': ...})."""
        return [dict(self._tool_definitions.get(n, {"name": n})) for n in sorted(self._tools)]

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

        self._consume_nonce(token)

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
        with self._state_lock:
            return self._record_audit_event_locked(
                event_type, disposition, halt_code, peer_creds, token,
                requested_tool, detail, payload_hash,
            )

    def _record_audit_event_locked(
        self,
        event_type: str,
        disposition: str,
        halt_code: Optional[str],
        peer_creds: Optional[PeerCredentials],
        token: Optional[CapabilityToken],
        requested_tool: Optional[str],
        detail: Optional[str],
        payload_hash: Optional[str],
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

    def _read_frame(self, conn: socket.socket) -> bytes:
        """
        Reads one newline-terminated frame into an incremental bytearray.
        Halts with HALT_FRAME_TOO_LARGE once more than max_frame_bytes arrive without a
        newline (no further buffering), and with HALT_FRAME_READ_TIMEOUT when the
        per-connection deadline elapses (covers idle and drip-feeding peers).
        """
        buf = bytearray()
        deadline = time.monotonic() + self.connection_timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise McpSecurityHaltError(
                    HALT_FRAME_READ_TIMEOUT,
                    f"No complete frame within {self.connection_timeout}s",
                )
            conn.settimeout(remaining)
            try:
                chunk = conn.recv(min(_RECV_CHUNK_BYTES, self.max_frame_bytes + 1 - len(buf)))
            except (socket.timeout, TimeoutError):
                raise McpSecurityHaltError(
                    HALT_FRAME_READ_TIMEOUT,
                    f"No complete frame within {self.connection_timeout}s",
                )
            if not chunk:
                return bytes(buf)
            start = len(buf)
            buf += chunk
            nl = buf.find(b"\n", start)
            if nl >= 0:
                if nl + 1 > self.max_frame_bytes:
                    break
                return bytes(buf[: nl + 1])
            if len(buf) > self.max_frame_bytes:
                break
        raise McpSecurityHaltError(
            HALT_FRAME_TOO_LARGE,
            f"Request frame exceeds max_frame_bytes={self.max_frame_bytes}",
        )

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

            # 3. Read message frame (bounded size, bounded wall-clock deadline)
            raw = self._read_frame(conn)

            if not raw:
                return None

            payload_hash = hashlib.sha256(raw).hexdigest()
            try:
                req_data = loads_strict(raw)
            except RecursionError:
                raise McpSecurityHaltError(
                    HALT_STRICT_JSON_REJECTED,
                    "Failed to parse request JSON: ERR_NESTING_TOO_DEEP",
                )
            except StrictJSONError as e:
                raise McpSecurityHaltError(
                    HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE
                    if e.code == "ERR_INVALID_JSON"
                    else HALT_STRICT_JSON_REJECTED,
                    f"Failed to parse request JSON: {e}",
                )
            if not isinstance(req_data, dict):
                raise McpSecurityHaltError(
                    HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE,
                    "Failed to parse request JSON: request frame is not a JSON object",
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

            # 6b. Tool-definition pinning: the advertisement must match the approved pins
            # and the requested tool must be in the pinned set before it is dispatchable.
            if self._tool_pin_guard is not None:
                self._tool_pin_guard.check_advertisement(self.advertised_tool_definitions())
                self._tool_pin_guard.check_call(requested_tool)

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

    def _ensure_private_socket_dir(self, directory: Path) -> None:
        """
        Ensures `directory` is a real (non-symlink) directory owned by the effective UID
        with mode exactly 0o700, creating it with that mode when missing.
        """
        created = False
        if not os.path.lexists(directory):
            directory.parent.mkdir(parents=True, exist_ok=True)
            old_umask = os.umask(0o077)
            try:
                os.mkdir(str(directory), 0o700)
                created = True
            except FileExistsError:
                pass
            finally:
                os.umask(old_umask)
        st = os.lstat(directory)
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            raise McpSecurityHaltError(
                HALT_SOCKET_DIR_INSECURE, f"Socket directory {directory} is not a real directory"
            )
        if st.st_uid != os.geteuid():
            raise McpSecurityHaltError(
                HALT_SOCKET_DIR_INSECURE,
                f"Socket directory {directory} owned by UID {st.st_uid}, expected {os.geteuid()}",
            )
        if created and stat.S_IMODE(st.st_mode) != 0o700:
            os.chmod(str(directory), 0o700)
            st = os.lstat(directory)
        if stat.S_IMODE(st.st_mode) != 0o700:
            raise McpSecurityHaltError(
                HALT_SOCKET_DIR_INSECURE,
                f"Socket directory {directory} has mode {oct(stat.S_IMODE(st.st_mode))}, expected 0o700",
            )

    def bind_and_listen(self, backlog: int = 128) -> None:
        """
        Binds the Unix Domain Socket inside a dedicated 0o700 directory. The bind runs
        under umask 0o177 so the socket node is created 0o600 (no post-bind chmod window).
        """
        if not self.socket_path:
            raise ValueError("socket_path must be configured to bind")

        self._ensure_private_socket_dir(self.socket_path.parent)

        if os.path.lexists(self.socket_path):
            if not stat.S_ISSOCK(os.lstat(self.socket_path).st_mode):
                raise McpSecurityHaltError(
                    HALT_SOCKET_DIR_INSECURE,
                    f"Refusing to replace non-socket file at {self.socket_path}",
                )
            os.unlink(self.socket_path)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old_umask = os.umask(0o177)
        try:
            sock.bind(str(self.socket_path))
        except Exception:
            sock.close()
            raise
        finally:
            os.umask(old_umask)
        # Verify (rather than chmod) so the node is never observable with wider permissions.
        st = os.lstat(self.socket_path)
        if (
            not stat.S_ISSOCK(st.st_mode)
            or stat.S_IMODE(st.st_mode) != 0o600
            or st.st_uid != os.geteuid()
        ):
            sock.close()
            os.unlink(self.socket_path)
            raise McpSecurityHaltError(
                HALT_SOCKET_DIR_INSECURE,
                f"Socket node {self.socket_path} has mode {oct(stat.S_IMODE(st.st_mode))}, expected 0o600",
            )
        sock.listen(backlog)
        sock.settimeout(0.2)
        self._server_sock = sock

    def start(self, backlog: int = 128) -> None:
        """Starts background accept thread feeding a bounded worker pool."""
        self.bind_and_listen(backlog=backlog)
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="mcp-uds-worker"
        )
        # Accept only when a worker slot is free; excess peers wait in the kernel backlog.
        self._slots = threading.BoundedSemaphore(self.max_workers)
        self._running = True
        self._worker_thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._worker_thread.start()

    def _handle_and_release(self, conn: socket.socket) -> None:
        try:
            self.handle_connection(conn, raise_on_halt=False)
        except Exception:
            pass
        finally:
            if self._slots is not None:
                self._slots.release()

    def _serve_loop(self) -> None:
        slots = self._slots
        executor = self._executor
        if slots is None or executor is None:
            return
        while self._running and self._server_sock:
            if not slots.acquire(timeout=0.2):
                continue
            try:
                conn, _ = self._server_sock.accept()
            except socket.timeout:
                slots.release()
                continue
            except Exception:
                slots.release()
                break

            conn.settimeout(self.connection_timeout)
            try:
                executor.submit(self._handle_and_release, conn)
            except RuntimeError:
                slots.release()
                conn.close()
                break

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

        if self._executor is not None:
            # In-flight connections end within connection_timeout.
            self._executor.shutdown(wait=True)
            self._executor = None

        if self.socket_path and os.path.lexists(self.socket_path):
            try:
                if stat.S_ISSOCK(os.lstat(self.socket_path).st_mode):
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

            try:
                resp_data = loads_strict(raw)
            except StrictJSONError as exc:
                raise McpSecurityHaltError(
                    HALT_INVALID_SERVER_RESPONSE, f"Server response JSON rejected: {exc}"
                )
            if not isinstance(resp_data, dict):
                raise McpSecurityHaltError(
                    HALT_INVALID_SERVER_RESPONSE, "Server response is not a JSON object"
                )

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
