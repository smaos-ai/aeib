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
tests/test_secure_mcp_uds_boundary.py — Verification of Secure MCP UDS Boundary & Peer Identity

Evaluates:
- Positive: Authorized client with kernel peer credentials and valid Ed25519 token executes tool.
- Falsification 1: TCP localhost connection rejected (HALT_TCP_LOCALHOST_DENIED).
- Falsification 2: Missing or invalid capability token signature rejected (HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE).
- Falsification 3: Audience mismatch rejected (HALT_AUDIENCE_MISMATCH).
- Falsification 4: Expired capability token rejected (HALT_CAPABILITY_TOKEN_EXPIRED).
- Falsification 5: Tool scope escalation / Confused Deputy attempt rejected (HALT_TOOL_SCOPE_NOT_AUTHORIZED).
- Falsification 6: Nonce replay rejected (HALT_TOKEN_NONCE_REPLAY).
- Falsification 7: Peer UID mismatch simulation rejected (HALT_PEER_UID_MISMATCH).
- PID reuse detection rejected (HALT_PID_REUSE_DETECTED).
- Binary hash binding verification (HALT_EXECUTABLE_HASH_MISMATCH).
- Audit trail JCS canonical formatting and hash chaining.
- Epistemic linguistic purity: zero banned promotional terms across boundary files.
"""

import base64
import json
import os
import re
import tracemalloc
import shutil
import socket
import stat
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Generator

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.secure_mcp_uds_boundary import (
    HALT_AUDIENCE_MISMATCH,
    HALT_CAPABILITY_TOKEN_EXPIRED,
    HALT_EXECUTABLE_HASH_MISMATCH,
    HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE,
    HALT_PEER_UID_MISMATCH,
    HALT_PID_REUSE_DETECTED,
    HALT_TCP_LOCALHOST_DENIED,
    HALT_TOKEN_NONCE_REPLAY,
    HALT_TOOL_SCOPE_NOT_AUTHORIZED,
    CapabilityToken,
    McpSecurityHaltError,
    SecureMcpUdsBoundaryServer,
    SecureMcpUdsClient,
    compute_executable_sha256,
    create_signed_capability_token,
    get_process_info,
)


@pytest.fixture
def ephemeral_sock_path() -> Generator[Path, None, None]:
    """
    Provides a short Unix Domain Socket path inside a dedicated 0o700 directory under /tmp
    (the server refuses shared directories such as /tmp itself).
    """
    sock_dir = Path(tempfile.mkdtemp(prefix="uds_test_", dir="/tmp"))
    path = sock_dir / "s.sock"
    yield path
    shutil.rmtree(sock_dir, ignore_errors=True)


@pytest.fixture
def issuer_keypair():
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return priv, pub


def test_positive_authorized_tool_execution(tmp_path: Path, ephemeral_sock_path: Path, issuer_keypair):
    """
    Positive test: Authorized client with valid peer credentials and Ed25519 capability token
    successfully executes an allowed tool (lookup_record) and receives a signed result.
    """
    issuer_priv, issuer_pub = issuer_keypair
    issuer_did = "did:aeib:station1:authority"
    server_id = "mcp-server-boundary-alpha"
    audit_log = tmp_path / "audit.jsonl"

    server = SecureMcpUdsBoundaryServer(
        mcp_server_id=server_id,
        socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={issuer_did: issuer_pub},
        audit_log_path=audit_log,
    )

    def handle_lookup(args):
        return {"record_id": args.get("id"), "value": "test_record_payload", "status": "AVAILABLE"}

    server.register_tool("lookup_record", handle_lookup)

    with server:
        # Verify socket permissions are 0o600
        sock_mode = os.stat(ephemeral_sock_path).st_mode & 0o777
        assert sock_mode == 0o600

        client = SecureMcpUdsClient(
            socket_path=ephemeral_sock_path,
            server_public_key=server.server_public_key,
        )

        token = create_signed_capability_token(
            issuer_privkey=issuer_priv,
            issuer_did=issuer_did,
            audience=server_id,
            client_pid=os.getpid(),
            allowed_tools=["lookup_record"],
            ttl_seconds=60.0,
        )

        response = client.call_tool(
            tool_name="lookup_record",
            arguments={"id": "rec-007"},
            capability_token=token,
        )

        assert response["status"] == "SUCCESS"
        assert response["disposition"] == "AUTHORIZED"
        assert response["result"]["record_id"] == "rec-007"
        assert response["result"]["value"] == "test_record_payload"
        assert "signature_b64" in response

    # Audit evidence log verification
    assert audit_log.exists()
    lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event_type"] == "AUTHORIZED_DISPATCH"
    assert record["disposition"] == "AUTHORIZED"
    assert record["peer_pid"] == os.getpid()
    assert record["peer_uid"] == os.getuid()
    assert record["requested_tool"] == "lookup_record"
    assert "entry_hash" in record


def test_falsification_1_tcp_localhost_denied(tmp_path: Path, ephemeral_sock_path: Path, issuer_keypair):
    """
    Falsification 1: TCP localhost connection rejected (HALT_TCP_LOCALHOST_DENIED).
    """
    _issuer_priv, issuer_pub = issuer_keypair
    audit_log = tmp_path / "audit.jsonl"

    server = SecureMcpUdsBoundaryServer(
        mcp_server_id="mcp-server-boundary-alpha",
        socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={"did:aeib:issuer": issuer_pub},
        audit_log_path=audit_log,
    )

    # 1. Test client-level explicit rejection
    client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)
    with pytest.raises(McpSecurityHaltError) as exc_client:
        client.connect_tcp("127.0.0.1", 9000)
    assert exc_client.value.halt_code == HALT_TCP_LOCALHOST_DENIED

    # 2. Test server-level transport control rejection on TCP connection
    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.bind(("127.0.0.1", 0))
    tcp_server.listen(1)
    port = tcp_server.getsockname()[1]

    tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_client.connect(("127.0.0.1", port))
    conn, _ = tcp_server.accept()

    try:
        with pytest.raises(McpSecurityHaltError) as exc_server:
            server.handle_connection(conn, raise_on_halt=True)
        assert exc_server.value.halt_code == HALT_TCP_LOCALHOST_DENIED

        # Verify audit record
        lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["halt_code"] == HALT_TCP_LOCALHOST_DENIED
        assert record["disposition"] == "HALTED"
    finally:
        tcp_client.close()
        tcp_server.close()


def test_falsification_2_invalid_capability_token_signature(
    tmp_path: Path, ephemeral_sock_path: Path, issuer_keypair
):
    """
    Falsification 2: Missing or invalid capability token signature rejected
    (HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE).
    """
    issuer_priv, issuer_pub = issuer_keypair
    server_id = "mcp-server-boundary-alpha"
    issuer_did = "did:aeib:station1:authority"
    audit_log = tmp_path / "audit.jsonl"

    server = SecureMcpUdsBoundaryServer(
        mcp_server_id=server_id,
        socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={issuer_did: issuer_pub},
        audit_log_path=audit_log,
    )
    server.register_tool("lookup_record", lambda args: {"status": "ok"})

    with server:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)

        # Corrupt the signature bytes
        token = create_signed_capability_token(
            issuer_privkey=issuer_priv,
            issuer_did=issuer_did,
            audience=server_id,
            client_pid=os.getpid(),
            allowed_tools=["lookup_record"],
        )
        token.signature_b64 = base64.b64encode(b"\x00" * 64).decode("ascii")

        with pytest.raises(McpSecurityHaltError) as exc:
            client.call_tool("lookup_record", {}, token)
        assert exc.value.halt_code == HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE

    lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["halt_code"] == HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE
    assert record["disposition"] == "HALTED"


def test_falsification_3_audience_mismatch(tmp_path: Path, ephemeral_sock_path: Path, issuer_keypair):
    """
    Falsification 3: Audience mismatch rejected (HALT_AUDIENCE_MISMATCH).
    """
    issuer_priv, issuer_pub = issuer_keypair
    server_id = "mcp-server-boundary-alpha"
    wrong_audience = "mcp-server-boundary-untrusted"
    issuer_did = "did:aeib:station1:authority"
    audit_log = tmp_path / "audit.jsonl"

    server = SecureMcpUdsBoundaryServer(
        mcp_server_id=server_id,
        socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={issuer_did: issuer_pub},
        audit_log_path=audit_log,
    )
    server.register_tool("lookup_record", lambda args: {"status": "ok"})

    with server:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)

        token = create_signed_capability_token(
            issuer_privkey=issuer_priv,
            issuer_did=issuer_did,
            audience=wrong_audience,
            client_pid=os.getpid(),
            allowed_tools=["lookup_record"],
        )

        with pytest.raises(McpSecurityHaltError) as exc:
            client.call_tool("lookup_record", {}, token)
        assert exc.value.halt_code == HALT_AUDIENCE_MISMATCH

    record = json.loads(audit_log.read_text(encoding="utf-8").strip().splitlines()[0])
    assert record["halt_code"] == HALT_AUDIENCE_MISMATCH
    assert record["disposition"] == "HALTED"


def test_falsification_4_expired_capability_token(tmp_path: Path, ephemeral_sock_path: Path, issuer_keypair):
    """
    Falsification 4: Expired capability token rejected (HALT_CAPABILITY_TOKEN_EXPIRED).
    """
    issuer_priv, issuer_pub = issuer_keypair
    server_id = "mcp-server-boundary-alpha"
    issuer_did = "did:aeib:station1:authority"
    audit_log = tmp_path / "audit.jsonl"

    server = SecureMcpUdsBoundaryServer(
        mcp_server_id=server_id,
        socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={issuer_did: issuer_pub},
        audit_log_path=audit_log,
    )
    server.register_tool("lookup_record", lambda args: {"status": "ok"})

    with server:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)

        # Issue token that expired 10 seconds ago
        past_time = time.time() - 30.0
        token = create_signed_capability_token(
            issuer_privkey=issuer_priv,
            issuer_did=issuer_did,
            audience=server_id,
            client_pid=os.getpid(),
            allowed_tools=["lookup_record"],
            ttl_seconds=10.0,
            issued_at=past_time,
        )

        with pytest.raises(McpSecurityHaltError) as exc:
            client.call_tool("lookup_record", {}, token)
        assert exc.value.halt_code == HALT_CAPABILITY_TOKEN_EXPIRED

    record = json.loads(audit_log.read_text(encoding="utf-8").strip().splitlines()[0])
    assert record["halt_code"] == HALT_CAPABILITY_TOKEN_EXPIRED
    assert record["disposition"] == "HALTED"


def test_falsification_5_tool_scope_escalation_confused_deputy(
    tmp_path: Path, ephemeral_sock_path: Path, issuer_keypair
):
    """
    Falsification 5: Tool scope escalation / Confused Deputy attempt
    (client asks for admin_wipe_database when token only permits lookup_record)
    rejected (HALT_TOOL_SCOPE_NOT_AUTHORIZED).
    """
    issuer_priv, issuer_pub = issuer_keypair
    server_id = "mcp-server-boundary-alpha"
    issuer_did = "did:aeib:station1:authority"
    audit_log = tmp_path / "audit.jsonl"

    server = SecureMcpUdsBoundaryServer(
        mcp_server_id=server_id,
        socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={issuer_did: issuer_pub},
        audit_log_path=audit_log,
    )

    admin_called = False

    def handle_admin_wipe(_args):
        nonlocal admin_called
        admin_called = True
        return {"status": "WIPED"}

    server.register_tool("lookup_record", lambda args: {"status": "ok"})
    server.register_tool("admin_wipe_database", handle_admin_wipe)

    with server:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)

        token = create_signed_capability_token(
            issuer_privkey=issuer_priv,
            issuer_did=issuer_did,
            audience=server_id,
            client_pid=os.getpid(),
            allowed_tools=["lookup_record"],  # DOES NOT include admin_wipe_database
        )

        with pytest.raises(McpSecurityHaltError) as exc:
            client.call_tool("admin_wipe_database", {}, token)

        assert exc.value.halt_code == HALT_TOOL_SCOPE_NOT_AUTHORIZED
        assert not admin_called  # Confused deputy defeated; tool was never invoked

    record = json.loads(audit_log.read_text(encoding="utf-8").strip().splitlines()[0])
    assert record["halt_code"] == HALT_TOOL_SCOPE_NOT_AUTHORIZED
    assert record["disposition"] == "HALTED"
    assert record["requested_tool"] == "admin_wipe_database"


def test_falsification_6_nonce_replay_rejected(tmp_path: Path, ephemeral_sock_path: Path, issuer_keypair):
    """
    Falsification 6: Nonce replay rejected (HALT_TOKEN_NONCE_REPLAY).
    """
    issuer_priv, issuer_pub = issuer_keypair
    server_id = "mcp-server-boundary-alpha"
    issuer_did = "did:aeib:station1:authority"
    audit_log = tmp_path / "audit.jsonl"

    server = SecureMcpUdsBoundaryServer(
        mcp_server_id=server_id,
        socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={issuer_did: issuer_pub},
        audit_log_path=audit_log,
    )
    server.register_tool("lookup_record", lambda args: {"status": "ok"})

    with server:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)

        token = create_signed_capability_token(
            issuer_privkey=issuer_priv,
            issuer_did=issuer_did,
            audience=server_id,
            client_pid=os.getpid(),
            allowed_tools=["lookup_record"],
            nonce="single-use-nonce-12345",
        )

        # First call succeeds
        resp1 = client.call_tool("lookup_record", {}, token)
        assert resp1["status"] == "SUCCESS"

        # Second call with identical token/nonce must be rejected
        with pytest.raises(McpSecurityHaltError) as exc:
            client.call_tool("lookup_record", {}, token)

        assert exc.value.halt_code == HALT_TOKEN_NONCE_REPLAY

    lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    rec1 = json.loads(lines[0])
    rec2 = json.loads(lines[1])
    assert rec1["disposition"] == "AUTHORIZED"
    assert rec2["disposition"] == "HALTED"
    assert rec2["halt_code"] == HALT_TOKEN_NONCE_REPLAY


def test_falsification_7_peer_uid_mismatch(tmp_path: Path, ephemeral_sock_path: Path, issuer_keypair):
    """
    Falsification 7: Peer UID mismatch simulation rejected (HALT_PEER_UID_MISMATCH).
    Evaluates kernel peer credential extraction and rejection when peer UID != expected_uid.
    """
    issuer_priv, issuer_pub = issuer_keypair
    server_id = "mcp-server-boundary-alpha"
    issuer_did = "did:aeib:station1:authority"
    audit_log = tmp_path / "audit.jsonl"

    # Configure server to expect a different service user UID
    simulated_daemon_uid = os.getuid() + 1000
    server = SecureMcpUdsBoundaryServer(
        mcp_server_id=server_id,
        socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={issuer_did: issuer_pub},
        expected_uid=simulated_daemon_uid,
        audit_log_path=audit_log,
    )
    server.register_tool("lookup_record", lambda args: {"status": "ok"})

    with server:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)

        token = create_signed_capability_token(
            issuer_privkey=issuer_priv,
            issuer_did=issuer_did,
            audience=server_id,
            client_pid=os.getpid(),
            allowed_tools=["lookup_record"],
        )

        with pytest.raises(McpSecurityHaltError) as exc:
            client.call_tool("lookup_record", {}, token)

        assert exc.value.halt_code == HALT_PEER_UID_MISMATCH

    lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["halt_code"] == HALT_PEER_UID_MISMATCH
    assert record["disposition"] == "HALTED"
    assert record["peer_uid"] == os.getuid()


def test_pid_reuse_and_pid_mismatch_protection(tmp_path: Path, ephemeral_sock_path: Path, issuer_keypair):
    """
    Evaluates PID reuse and recycling detection:
    1. Token client_pid mismatch against kernel peer PID.
    2. Process creation timestamp after token issuance timestamp.
    """
    issuer_priv, issuer_pub = issuer_keypair
    server_id = "mcp-server-boundary-alpha"
    issuer_did = "did:aeib:station1:authority"
    audit_log = tmp_path / "audit.jsonl"

    server = SecureMcpUdsBoundaryServer(
        mcp_server_id=server_id,
        socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={issuer_did: issuer_pub},
        audit_log_path=audit_log,
    )
    server.register_tool("lookup_record", lambda args: {"status": "ok"})

    with server:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)

        # 1. Spoofed client_pid in token (PID mismatch)
        token_bad_pid = create_signed_capability_token(
            issuer_privkey=issuer_priv,
            issuer_did=issuer_did,
            audience=server_id,
            client_pid=os.getpid() + 99999,  # Mismatched from actual peer PID
            allowed_tools=["lookup_record"],
        )

        with pytest.raises(McpSecurityHaltError) as exc1:
            client.call_tool("lookup_record", {}, token_bad_pid)
        assert exc1.value.halt_code == HALT_PID_REUSE_DETECTED

        # 2. Token issued before peer process start time (recycled PID scenario)
        _path, start_time = get_process_info(os.getpid())
        if start_time is not None:
            token_recycled = create_signed_capability_token(
                issuer_privkey=issuer_priv,
                issuer_did=issuer_did,
                audience=server_id,
                client_pid=os.getpid(),
                allowed_tools=["lookup_record"],
                ttl_seconds=3600.0,
                issued_at=start_time - 100.0,  # Token issued before this process was born
            )

            with pytest.raises(McpSecurityHaltError) as exc2:
                client.call_tool("lookup_record", {}, token_recycled)
            assert exc2.value.halt_code == HALT_PID_REUSE_DETECTED


def test_executable_hash_binding(tmp_path: Path, ephemeral_sock_path: Path, issuer_keypair):
    """
    Evaluates pinned executable digest allowlist binding.
    """
    issuer_priv, issuer_pub = issuer_keypair
    server_id = "mcp-server-boundary-alpha"
    issuer_did = "did:aeib:station1:authority"

    real_exe_path, _ = get_process_info(os.getpid())
    assert real_exe_path is not None
    real_digest = compute_executable_sha256(real_exe_path)

    # 1. Allowed executable digest succeeds
    server_allow = SecureMcpUdsBoundaryServer(
        mcp_server_id=server_id,
        socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={issuer_did: issuer_pub},
        allowed_executable_digests={f"sha256:{real_digest}"},
    )
    server_allow.register_tool("lookup_record", lambda args: {"status": "ok"})

    with server_allow:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)
        token = create_signed_capability_token(
            issuer_privkey=issuer_priv,
            issuer_did=issuer_did,
            audience=server_id,
            client_pid=os.getpid(),
            allowed_tools=["lookup_record"],
        )
        resp = client.call_tool("lookup_record", {}, token)
        assert resp["status"] == "SUCCESS"

    # 2. Mismatched executable digest rejects
    server_deny = SecureMcpUdsBoundaryServer(
        mcp_server_id=server_id,
        socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={issuer_did: issuer_pub},
        allowed_executable_digests={"sha256:" + "0" * 64},  # Pinned to an arbitrary different hash
    )
    server_deny.register_tool("lookup_record", lambda args: {"status": "ok"})

    with server_deny:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)
        token = create_signed_capability_token(
            issuer_privkey=issuer_priv,
            issuer_did=issuer_did,
            audience=server_id,
            client_pid=os.getpid(),
            allowed_tools=["lookup_record"],
        )
        with pytest.raises(McpSecurityHaltError) as exc:
            client.call_tool("lookup_record", {}, token)
        assert exc.value.halt_code == HALT_EXECUTABLE_HASH_MISMATCH


def test_banned_words_absence():
    """
    Epistemic boundary: Verifies zero promotional or unverified claims exist
    in src/secure_mcp_uds_boundary.py and tests/test_secure_mcp_uds_boundary.py.
    """
    banned_tokens = [
        "guaran" + "teed",
        "guaran" + "tee",
        "proven" + " universally",
        "bullet" + "proof",
        "enterprise" + "-grade",
        "production" + "-safe",
        "100%" + " secure",
        "un" + "hackable",
    ]

    files_to_scan = [
        Path("src/secure_mcp_uds_boundary.py"),
        Path("tests/test_secure_mcp_uds_boundary.py"),
    ]

    violations = []
    for f in files_to_scan:
        assert f.exists(), f"Target file {f} must exist"
        lines = f.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            # Exclude lines within test_banned_words_absence itself
            if "banned" in line and ("tokens" in line or "patterns" in line):
                continue
            for token in banned_tokens:
                if re.search(re.escape(token), line, re.IGNORECASE):
                    violations.append(f"{f}:{idx}: contains prohibited token '{token}'")

    assert len(violations) == 0, f"Prohibited tokens detected: {violations}"


# ----------------------------------------------------------------------------
# Regression tests for red-team findings (A5): frame cap, idle-client blocking,
# socket directory hygiene, durable nonce replay cache. Real UDS sockets and
# real threads; halt codes are string literals so the tests also run (and fail
# behaviorally) against the pre-fix module.
# ----------------------------------------------------------------------------


def _server_and_token(sock_path: Path, issuer_keypair, **server_kwargs):
    issuer_priv, issuer_pub = issuer_keypair
    issuer_did = "did:aeib:station1:authority"
    server_id = "mcp-server-boundary-alpha"
    server = SecureMcpUdsBoundaryServer(
        mcp_server_id=server_id,
        socket_path=sock_path,
        trusted_issuer_pubkeys={issuer_did: issuer_pub},
        **server_kwargs,
    )
    server.register_tool("lookup_record", lambda args: {"status": "ok"})

    def make_token(nonce=None):
        return create_signed_capability_token(
            issuer_privkey=issuer_priv,
            issuer_did=issuer_did,
            audience=server_id,
            client_pid=os.getpid(),
            allowed_tools=["lookup_record"],
            nonce=nonce,
        )

    return server, make_token


def _recv_line(sock: socket.socket) -> bytes:
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
    return buf


def _halt_codes(server: SecureMcpUdsBoundaryServer):
    return [r.get("halt_code") for r in server.audit_records]


def test_regression_idle_client_does_not_block_second_client(ephemeral_sock_path: Path, issuer_keypair):
    """
    Finding 2: one idle peer must not block other peers. The second client uses a 1.5 s
    timeout, shorter than the default 2 s per-connection deadline, so it is only served
    if connections are handled concurrently. The idle peer is then closed by the server
    with HALT_FRAME_READ_TIMEOUT.
    """
    server, make_token = _server_and_token(ephemeral_sock_path, issuer_keypair)
    with server:
        idle = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        idle.connect(str(ephemeral_sock_path))
        try:
            time.sleep(0.3)
            client = SecureMcpUdsClient(socket_path=ephemeral_sock_path, timeout=1.5)
            t0 = time.monotonic()
            resp = client.call_tool("lookup_record", {}, make_token())
            assert resp["status"] == "SUCCESS"
            assert time.monotonic() - t0 < 1.5

            idle.settimeout(5.0)
            t1 = time.monotonic()
            line = _recv_line(idle)
            assert time.monotonic() - t1 < 4.0
            assert json.loads(line)["halt_code"] == "HALT_FRAME_READ_TIMEOUT"
        finally:
            idle.close()
    assert "HALT_FRAME_READ_TIMEOUT" in _halt_codes(server)


def test_regression_drip_feed_client_bounded_by_deadline(ephemeral_sock_path: Path, issuer_keypair):
    """
    Finding 2 (variant): a peer sending one byte every 0.2 s never completes a frame;
    the total per-connection deadline (not only per-recv) closes it.
    """
    server, _make_token = _server_and_token(
        ephemeral_sock_path, issuer_keypair, connection_timeout=1.0
    )
    with server:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(str(ephemeral_sock_path))
        s.settimeout(0.05)
        t0 = time.monotonic()
        resp = b""
        try:
            while time.monotonic() - t0 < 5.0 and not resp.endswith(b"\n"):
                try:
                    s.sendall(b"{")
                except OSError:
                    break
                try:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    resp += chunk
                except (socket.timeout, TimeoutError):
                    pass
                time.sleep(0.15)
            elapsed = time.monotonic() - t0
        finally:
            s.close()
        assert elapsed < 2.5
    assert "HALT_FRAME_READ_TIMEOUT" in _halt_codes(server)


def test_regression_oversize_frame_rejected_quickly_with_bounded_memory(
    ephemeral_sock_path: Path, issuer_keypair
):
    """
    Finding 1: a 16 MiB frame without newline is rejected after at most
    max_frame_bytes (default 1 MiB) with HALT_FRAME_TOO_LARGE, quickly and without
    buffering the whole frame (traced allocation peak stays far below 16 MiB).
    """
    server, _make_token = _server_and_token(ephemeral_sock_path, issuer_keypair)
    big = b"A" * (16 * 1024 * 1024)
    with server:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(10.0)
        s.connect(str(ephemeral_sock_path))

        def sender():
            try:
                s.sendall(big)
            except OSError:
                pass

        tracemalloc.start()
        t0 = time.monotonic()
        th = threading.Thread(target=sender, daemon=True)
        th.start()
        try:
            line = _recv_line(s)
        except OSError:
            line = b""
        th.join(timeout=10.0)
        elapsed = time.monotonic() - t0
        _cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        s.close()

        assert elapsed < 3.0
        assert peak < 6 * 1024 * 1024, f"server buffered {peak} bytes"
        if line:
            assert json.loads(line)["halt_code"] == "HALT_FRAME_TOO_LARGE"
    assert _halt_codes(server) == ["HALT_FRAME_TOO_LARGE"]


def test_regression_frame_size_boundary(ephemeral_sock_path: Path, issuer_keypair):
    """
    Finding 1 (boundary): a frame of exactly max_frame_bytes (newline included) is
    accepted; one byte more is rejected with HALT_FRAME_TOO_LARGE.
    """
    server, make_token = _server_and_token(ephemeral_sock_path, issuer_keypair, max_frame_bytes=4096)
    with server:
        def send_padded(total_len: int):
            req = {
                "arguments": {"pad": ""},
                "capability_token": make_token().to_dict(),
                "request_id": "r",
                "tool_name": "lookup_record",
            }
            base_len = len(json.dumps(req, separators=(",", ":")).encode()) + 1
            req["arguments"]["pad"] = "x" * (total_len - base_len)
            wire = json.dumps(req, separators=(",", ":")).encode() + b"\n"
            assert len(wire) == total_len
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(5.0)
            s.connect(str(ephemeral_sock_path))
            try:
                s.sendall(wire)
                return json.loads(_recv_line(s))
            finally:
                s.close()

        assert send_padded(4096)["status"] == "SUCCESS"
        assert send_padded(4097)["halt_code"] == "HALT_FRAME_TOO_LARGE"


def test_regression_socket_dir_mode_0700_and_umask_restored(issuer_keypair):
    """
    Finding 3: the socket is created inside a dedicated 0o700 directory (created when
    missing, even under a permissive process umask), the socket node is 0o600, and the
    process umask is restored after bind.
    """
    base = Path(tempfile.mkdtemp(prefix="uds_dir_", dir="/tmp"))
    sock_path = base / "sub" / "s.sock"
    server, _make_token = _server_and_token(sock_path, issuer_keypair)
    old = os.umask(0o002)
    try:
        with server:
            assert os.umask(0o002) == 0o002
            dir_mode = stat.S_IMODE(os.lstat(sock_path.parent).st_mode)
            sock_mode = stat.S_IMODE(os.lstat(sock_path).st_mode)
            # owner-only: rwx for the directory, rw for the socket, no group/other bits
            assert dir_mode == stat.S_IRWXU
            assert sock_mode == stat.S_IRUSR | stat.S_IWUSR
            assert (dir_mode | sock_mode) & (stat.S_IRWXG | stat.S_IRWXO) == 0
            assert stat.S_ISSOCK(os.lstat(sock_path).st_mode)
    finally:
        os.umask(old)
        shutil.rmtree(base, ignore_errors=True)


def test_regression_socket_dir_insecure_refused(issuer_keypair):
    """
    Finding 3: an existing group/world-accessible directory, a symlinked directory,
    and a non-socket file at the socket path are refused with HALT_SOCKET_DIR_INSECURE.
    """
    base = Path(tempfile.mkdtemp(prefix="uds_dir_", dir="/tmp"))
    try:
        loose = base / "loose"
        loose.mkdir()
        os.chmod(loose, 0o755)
        server, _ = _server_and_token(loose / "s.sock", issuer_keypair)
        with pytest.raises(McpSecurityHaltError) as exc:
            server.start()
        assert exc.value.halt_code == "HALT_SOCKET_DIR_INSECURE"
        assert not (loose / "s.sock").exists()

        real = base / "real"
        real.mkdir(mode=0o700)
        link = base / "link"
        link.symlink_to(real)
        server, _ = _server_and_token(link / "s.sock", issuer_keypair)
        with pytest.raises(McpSecurityHaltError) as exc:
            server.start()
        assert exc.value.halt_code == "HALT_SOCKET_DIR_INSECURE"

        regular = real / "s.sock"
        regular.write_text("not a socket")
        server, _ = _server_and_token(regular, issuer_keypair)
        with pytest.raises(McpSecurityHaltError) as exc:
            server.start()
        assert exc.value.halt_code == "HALT_SOCKET_DIR_INSECURE"
        assert regular.read_text() == "not a socket"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_regression_nonce_replay_rejected_after_restart(ephemeral_sock_path: Path, issuer_keypair):
    """
    Finding 4: a consumed nonce stays consumed across a server restart (durable store
    beside the socket in its 0o700 directory).
    """
    server, make_token = _server_and_token(ephemeral_sock_path, issuer_keypair)
    token = make_token(nonce="restart-nonce-0001")
    with server:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)
        assert client.call_tool("lookup_record", {}, token)["status"] == "SUCCESS"

    server2, _ = _server_and_token(ephemeral_sock_path, issuer_keypair)
    with server2:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)
        with pytest.raises(McpSecurityHaltError) as exc:
            client.call_tool("lookup_record", {}, token)
        assert exc.value.halt_code == HALT_TOKEN_NONCE_REPLAY
        fresh = make_token()
        assert client.call_tool("lookup_record", {}, fresh)["status"] == "SUCCESS"


def test_regression_nonce_store_prunes_expired_and_rejects_corruption(issuer_keypair):
    """
    Finding 4: on load, expired entries are pruned (and compacted on disk), live entries
    are kept, a torn trailing line is tolerated, and a malformed interior line halts.
    """
    base = Path(tempfile.mkdtemp(prefix="uds_nonce_", dir="/tmp"))
    try:
        store = base / "nonces.jsonl"
        now_ms = int(time.time() * 1000)
        store.write_text(
            json.dumps({"expires_at_ms": now_ms - 60_000, "nonce": "old"}) + "\n"
            + json.dumps({"expires_at_ms": now_ms + 60_000, "nonce": "live"}) + "\n"
            + '{"expires_at_ms": 1, "non',
            encoding="utf-8",
        )
        server, make_token = _server_and_token(
            base / "s.sock", issuer_keypair, nonce_store_path=store
        )
        assert set(server._seen_nonces) == {"live"}
        lines = store.read_text(encoding="utf-8").splitlines()
        assert [json.loads(x)["nonce"] for x in lines] == ["live"]

        with pytest.raises(McpSecurityHaltError) as exc:
            server._verify_capability_token(make_token(nonce="live"), "lookup_record")
        assert exc.value.halt_code == HALT_TOKEN_NONCE_REPLAY

        server._verify_capability_token(make_token(nonce="n2"), "lookup_record")
        assert json.loads(store.read_text(encoding="utf-8").splitlines()[-1])["nonce"] == "n2"

        store.write_text("garbage\n" + json.dumps({"expires_at_ms": now_ms + 1, "nonce": "x"}) + "\n")
        with pytest.raises(McpSecurityHaltError) as exc:
            _server_and_token(base / "s.sock", issuer_keypair, nonce_store_path=store)
        assert exc.value.halt_code == "HALT_NONCE_STORE_CORRUPT"
    finally:
        shutil.rmtree(base, ignore_errors=True)



# ----------------------------------------------------------------------------
# Hardening tests (mutation adequacy): configuration defaults, real kernel peer
# credentials over a socketpair, request-shape halts, nonce store invariants,
# bounded worker pool behavior. All use real sockets, files and threads.
# ----------------------------------------------------------------------------

import math  # noqa: E402

import src.secure_mcp_uds_boundary as boundary_mod  # noqa: E402
from src.jcs_canonicalizer import encode_jcs  # noqa: E402
from src.secure_mcp_uds_boundary import PeerCredentials, extract_peer_credentials  # noqa: E402


def test_defaults_and_constructor_validation(issuer_keypair):
    assert boundary_mod.DEFAULT_MAX_FRAME_BYTES == 1048576
    assert boundary_mod.DEFAULT_CONNECTION_TIMEOUT_S == 2.0
    assert boundary_mod.DEFAULT_MAX_WORKERS == 8
    sock_path = Path("/tmp/uds_defaults_probe/s.sock")
    server, _ = _server_and_token(sock_path, issuer_keypair)
    assert server.max_frame_bytes == 1048576
    assert server.connection_timeout == 2.0
    assert server.max_workers == 8
    assert server.nonce_store_path == sock_path.parent / "s.sock.nonces.jsonl"
    assert SecureMcpUdsBoundaryServer(mcp_server_id="x").nonce_store_path is None
    explicit = SecureMcpUdsBoundaryServer(mcp_server_id="x", nonce_store_path="/tmp/uds_n.jsonl")
    assert explicit.nonce_store_path == Path("/tmp/uds_n.jsonl")
    # minimum accepted values
    ok = SecureMcpUdsBoundaryServer(
        mcp_server_id="x", max_frame_bytes=1, connection_timeout=0.001, max_workers=1
    )
    assert (ok.max_frame_bytes, ok.max_workers) == (1, 1)
    for kwargs in ({"max_frame_bytes": 0}, {"connection_timeout": 0}, {"max_workers": 0}):
        with pytest.raises(ValueError):
            SecureMcpUdsBoundaryServer(mcp_server_id="x", **kwargs)


def test_token_identifier_formats(issuer_keypair):
    issuer_priv, _ = issuer_keypair
    tok = create_signed_capability_token(
        issuer_privkey=issuer_priv,
        issuer_did="did:x",
        audience="aud",
        client_pid=1,
        allowed_tools=["t"],
        ttl_seconds=30.0,
        issued_at=1000.0,
    )
    assert re.fullmatch(r"tok-[0-9a-f]{12}", tok.token_id)
    assert re.fullmatch(r"nonce-[0-9a-f]{16}", tok.nonce)
    assert tok.issued_at == 1000.0 and tok.expires_at == 1030.0


def _tcp_loopback_pair():
    lst = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lst.bind(("127.0.0.1", 0))
    lst.listen(1)
    cli = socket.create_connection(lst.getsockname(), timeout=5.0)
    srv, _ = lst.accept()
    lst.close()
    return srv, cli


def test_real_kernel_peer_credentials_over_socketpair():
    a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        creds = extract_peer_credentials(a)
        assert creds.uid == os.getuid()
        assert creds.pid == os.getpid()
        assert creds.gid in set(os.getgroups()) | {os.getgid(), os.getegid()}
        with pytest.raises(McpSecurityHaltError) as exc:
            extract_peer_credentials(a, platform="plan9")
        assert exc.value.halt_code == "HALT_UNSUPPORTED_PLATFORM"
    finally:
        a.close()
        b.close()
    t1, t2 = _tcp_loopback_pair()
    try:
        with pytest.raises(McpSecurityHaltError) as exc:
            extract_peer_credentials(t1)
        assert exc.value.halt_code == HALT_TCP_LOCALHOST_DENIED
    finally:
        t1.close()
        t2.close()


def test_get_process_info_reports_current_process():
    exe, start = get_process_info(os.getpid())
    assert exe and os.path.exists(exe)
    now = time.time()
    assert start is not None and now - 7 * 86400 < start <= now
    assert get_process_info(0) == (None, None)


def test_issued_at_zero_skips_pid_reuse_window(issuer_keypair):
    issuer_priv, issuer_pub = issuer_keypair
    server = SecureMcpUdsBoundaryServer(
        mcp_server_id="aud", trusted_issuer_pubkeys={"did:x": issuer_pub}
    )
    tok = create_signed_capability_token(
        issuer_privkey=issuer_priv,
        issuer_did="did:x",
        audience="aud",
        client_pid=os.getpid(),
        allowed_tools=["t"],
        ttl_seconds=time.time() + 60.0,
        issued_at=0.0,
    )
    creds = PeerCredentials(pid=os.getpid(), uid=os.getuid(), gid=os.getgid())
    server._verify_process_binding(creds, tok)  # no halt: issued_at == 0 disables the window
    late = create_signed_capability_token(
        issuer_privkey=issuer_priv,
        issuer_did="did:x",
        audience="aud",
        client_pid=os.getpid(),
        allowed_tools=["t"],
        issued_at=1.0,
        ttl_seconds=time.time() + 60.0,
    )
    with pytest.raises(McpSecurityHaltError) as exc:
        server._verify_process_binding(creds, late)
    assert exc.value.halt_code == HALT_PID_REUSE_DETECTED


def _handle_raw(server: SecureMcpUdsBoundaryServer, wire: bytes) -> McpSecurityHaltError:
    a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        b.sendall(wire)
        with pytest.raises(McpSecurityHaltError) as exc:
            server.handle_connection(a, raise_on_halt=True)
        return exc.value
    finally:
        a.close()
        b.close()


def test_request_shape_halts_over_socketpair(issuer_keypair):
    issuer_priv, issuer_pub = issuer_keypair
    server = SecureMcpUdsBoundaryServer(
        mcp_server_id="aud", trusted_issuer_pubkeys={"did:x": issuer_pub}
    )
    server.register_tool("t", lambda args: {"ok": True})
    err = _handle_raw(server, b'{"tool_name":"t","capability_token":"abc"}\n')
    assert err.halt_code == HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE
    assert "missing capability token dictionary" in err.detail
    err = _handle_raw(server, b"not json\n")
    assert "Failed to parse request JSON" in err.detail

    tok = create_signed_capability_token(
        issuer_privkey=issuer_priv, issuer_did="did:x", audience="aud",
        client_pid=os.getpid(), allowed_tools=["t"],
    )
    tok.signature_b64 = ""
    req = {"tool_name": "t", "capability_token": tok.to_dict(), "arguments": {}}
    err = _handle_raw(server, json.dumps(req).encode() + b"\n")
    assert err.halt_code == HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE
    assert "missing Ed25519 signature" in err.detail

    t1, t2 = _tcp_loopback_pair()
    try:
        with pytest.raises(McpSecurityHaltError) as exc:
            server.handle_connection(t1, raise_on_halt=True)
        assert exc.value.halt_code == HALT_TCP_LOCALHOST_DENIED
        assert "TCP loopback is forbidden" in exc.value.detail
    finally:
        t1.close()
        t2.close()


def test_nonce_store_invariants(issuer_keypair):
    base = Path(tempfile.mkdtemp(prefix="uds_nonce_", dir="/tmp"))
    try:
        store = base / "nonces.jsonl"
        now_ms = int(time.time() * 1000)
        # live-only store in non-sorted order: loaded verbatim, not rewritten
        original = (
            json.dumps({"expires_at_ms": now_ms + 90_000, "nonce": "zz"}) + "\n"
            + json.dumps({"expires_at_ms": now_ms + 90_000, "nonce": "aa"}) + "\n"
        )
        store.write_text(original, encoding="utf-8")
        server, make_token = _server_and_token(base / "s.sock", issuer_keypair, nonce_store_path=store)
        assert server._seen_nonces == {"zz": now_ms + 90_000, "aa": now_ms + 90_000}
        assert store.read_text(encoding="utf-8") == original

        # persisted line is RFC 8785 JCS with ceil(ms) expiry; file mode 0o600
        tok = make_token(nonce="n-persist")
        server._verify_capability_token(tok, "lookup_record")
        last = store.read_bytes().splitlines()[-1]
        expected_ms = int(math.ceil(tok.expires_at * 1000))
        assert last == encode_jcs({"expires_at_ms": expected_ms, "nonce": "n-persist"})
        assert server._seen_nonces["n-persist"] == expected_ms

        # expired in-memory entries are pruned on consume
        server._seen_nonces["stale"] = now_ms - 1000
        server._verify_capability_token(make_token(), "lookup_record")
        assert "stale" not in server._seen_nonces

        # compaction writes 0o600, sorted, leaves no temp file
        store.write_text(
            json.dumps({"expires_at_ms": now_ms + 90_000, "nonce": "b"}) + "\n"
            + json.dumps({"expires_at_ms": now_ms - 90_000, "nonce": "gone"}) + "\n"
            + json.dumps({"expires_at_ms": now_ms + 90_000, "nonce": "a"}) + "\n",
            encoding="utf-8",
        )
        os.chmod(store, 0o600)
        _server_and_token(base / "s.sock", issuer_keypair, nonce_store_path=store)
        assert [json.loads(x)["nonce"] for x in store.read_text().splitlines()] == ["a", "b"]
        assert stat.S_IMODE(os.lstat(store).st_mode) == stat.S_IRUSR | stat.S_IWUSR
        assert not (base / "nonces.jsonl.tmp").exists()

        # wrong types and symlinked store halt
        store.write_text(json.dumps({"expires_at_ms": "1", "nonce": "x"}) + "\n")
        with pytest.raises(McpSecurityHaltError) as exc:
            _server_and_token(base / "s.sock", issuer_keypair, nonce_store_path=store)
        assert exc.value.halt_code == "HALT_NONCE_STORE_CORRUPT"
        store.unlink()
        target = base / "target.jsonl"
        target.write_text("")
        store.symlink_to(target)
        with pytest.raises(McpSecurityHaltError) as exc:
            _server_and_token(base / "s.sock", issuer_keypair, nonce_store_path=store)
        assert exc.value.halt_code == "HALT_NONCE_STORE_CORRUPT"

        # unwritable store fails closed and does not record the nonce in memory
        bad, make_bad = _server_and_token(
            base / "s.sock", issuer_keypair, nonce_store_path=base / "missing" / "n.jsonl"
        )
        with pytest.raises(McpSecurityHaltError) as exc:
            bad._verify_capability_token(make_bad(nonce="n-fail"), "lookup_record")
        assert exc.value.halt_code == "HALT_NONCE_STORE_UNAVAILABLE"
        assert "n-fail" not in bad._seen_nonces
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_context_manager_and_socket_mode_under_open_umask(ephemeral_sock_path: Path, issuer_keypair):
    server, make_token = _server_and_token(ephemeral_sock_path, issuer_keypair)
    old = os.umask(0)
    try:
        with server as entered:
            assert entered is server
            assert os.umask(0) == 0
            assert stat.S_IMODE(os.lstat(ephemeral_sock_path).st_mode) == stat.S_IRUSR | stat.S_IWUSR
            client = SecureMcpUdsClient(socket_path=ephemeral_sock_path)
            assert client.call_tool("lookup_record", {}, make_token())["status"] == "SUCCESS"
    finally:
        os.umask(old)
    assert not os.path.lexists(ephemeral_sock_path)


def test_bounded_pool_queues_beyond_max_workers(ephemeral_sock_path: Path, issuer_keypair):
    """With max_workers=1 an idle peer holds the only slot until its deadline; the next
    peer is then served (queued in the kernel backlog, not dropped)."""
    server, make_token = _server_and_token(
        ephemeral_sock_path, issuer_keypair, max_workers=1, connection_timeout=1.0
    )
    with server:
        idle = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        idle.connect(str(ephemeral_sock_path))
        try:
            time.sleep(0.2)
            client = SecureMcpUdsClient(socket_path=ephemeral_sock_path, timeout=5.0)
            t0 = time.monotonic()
            resp = client.call_tool("lookup_record", {}, make_token())
            elapsed = time.monotonic() - t0
            assert resp["status"] == "SUCCESS"
            assert 0.5 < elapsed < 3.0
        finally:
            idle.close()
    assert _halt_codes(server)[0] == "HALT_FRAME_READ_TIMEOUT"


def test_read_frame_returns_exactly_one_frame(issuer_keypair):
    server = SecureMcpUdsBoundaryServer(mcp_server_id="aud", max_frame_bytes=64)
    a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        b.sendall(b'{"k":1}\nTRAILING')
        assert server._read_frame(a) == b'{"k":1}\n'
        b.sendall(b"partial")
        b.shutdown(socket.SHUT_WR)
        # one request per connection: bytes after the first newline are not carried over;
        # EOF without newline returns the partial frame
        assert server._read_frame(a) == b"partial"
    finally:
        a.close()
        b.close()


def test_missing_peer_executable_halts_when_allowlist_configured(issuer_keypair):
    issuer_priv, issuer_pub = issuer_keypair
    server = SecureMcpUdsBoundaryServer(
        mcp_server_id="aud",
        trusted_issuer_pubkeys={"did:x": issuer_pub},
        allowed_executable_digests={"0" * 64},
    )
    dead_pid = 2_000_000_000  # far above any live PID on this host
    tok = create_signed_capability_token(
        issuer_privkey=issuer_priv, issuer_did="did:x", audience="aud",
        client_pid=dead_pid, allowed_tools=["t"],
    )
    creds = PeerCredentials(pid=dead_pid, uid=os.getuid(), gid=os.getgid())
    with pytest.raises(McpSecurityHaltError) as exc:
        server._verify_process_binding(creds, tok)
    assert exc.value.halt_code == "HALT_EXECUTABLE_NOT_FOUND"


def test_client_halts_on_empty_server_response(ephemeral_sock_path: Path, issuer_keypair):
    os.chmod(ephemeral_sock_path.parent, 0o700)
    lst = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    lst.bind(str(ephemeral_sock_path))
    lst.listen(1)

    def close_after_read():
        conn, _ = lst.accept()
        conn.settimeout(5.0)
        try:
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
        finally:
            conn.close()

    th = threading.Thread(target=close_after_read, daemon=True)
    th.start()
    try:
        _server, make_token = _server_and_token(Path("/tmp/uds_unused/s.sock"), issuer_keypair)
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path, timeout=5.0)
        with pytest.raises(McpSecurityHaltError) as exc:
            client.call_tool("lookup_record", {}, make_token())
        assert exc.value.halt_code == "HALT_EMPTY_SERVER_RESPONSE"
    finally:
        th.join(timeout=5.0)
        lst.close()


def test_handle_connection_default_returns_signed_halt_dict(issuer_keypair):
    """Default raise_on_halt=False returns the signed HALTED payload (no exception)."""
    _issuer_priv, issuer_pub = issuer_keypair
    server = SecureMcpUdsBoundaryServer(mcp_server_id="aud", trusted_issuer_pubkeys={"did:x": issuer_pub})
    a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        b.sendall(b'{"tool_name":"t"}\n')
        out = server.handle_connection(a)
        reply = b.recv(65536)
    finally:
        a.close()
        b.close()
    assert out["status"] == "HALTED"
    assert out["halt_code"] == HALT_INVALID_CAPABILITY_TOKEN_SIGNATURE
    unsigned = {k: v for k, v in out.items() if k != "signature_b64"}
    from src.jcs_canonicalizer import encode_jcs

    server.server_public_key.verify(base64.b64decode(out["signature_b64"]), encode_jcs(unsigned))
    assert json.loads(reply) == out


def test_bind_without_socket_path_raises(issuer_keypair):
    server = SecureMcpUdsBoundaryServer(mcp_server_id="aud")
    with pytest.raises(ValueError, match="socket_path must be configured"):
        server.bind_and_listen()


def test_client_rejects_forged_server_signature(ephemeral_sock_path: Path, issuer_keypair):
    """A response signed by a key other than the pinned server key is rejected."""
    issuer_priv, issuer_pub = issuer_keypair
    server = SecureMcpUdsBoundaryServer(
        mcp_server_id="aud", socket_path=ephemeral_sock_path,
        trusted_issuer_pubkeys={"did:x": issuer_pub},
    )
    server.register_tool("t", lambda args: {"ok": True})
    wrong_key = ed25519.Ed25519PrivateKey.generate().public_key()
    with server:
        client = SecureMcpUdsClient(socket_path=ephemeral_sock_path, server_public_key=wrong_key)
        tok = create_signed_capability_token(
            issuer_privkey=issuer_priv, issuer_did="did:x", audience="aud",
            client_pid=os.getpid(), allowed_tools=["t"],
        )
        with pytest.raises(McpSecurityHaltError) as exc:
            client.call_tool("t", {}, tok)
    assert exc.value.halt_code == "HALT_INVALID_SERVER_SIGNATURE"
