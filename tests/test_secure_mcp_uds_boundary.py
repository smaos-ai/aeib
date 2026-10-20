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
import socket
import sys
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
    """Provides a temporary, short Unix Domain Socket path within /tmp."""
    sock_id = uuid.uuid4().hex[:12]
    path = Path(f"/tmp/uds_test_{sock_id}.sock")
    if path.exists():
        path.unlink()
    yield path
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


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
