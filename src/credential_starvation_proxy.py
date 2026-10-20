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
src/credential_starvation_proxy.py — Host-Side Credential-Injecting Egress Proxy

Implements the Perplexity SPACE-inspired Credential Starvation Architecture:
1. The untrusted agent process holds ZERO credentials (API keys, bearer tokens, certs).
2. The agent cannot open arbitrary external sockets; all egress routes to this host proxy.
3. The proxy verifies the AEIB CAID warrant (signed by Station 1) and destination allowlist.
4. The proxy injects the real upstream authorization credential at the wire level.
5. All upstream secrets are stripped from responses returned to the agent.
6. Persistent append-only audit logging for every dispatched and blocked attempt.
"""

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    """Computes a SHA-256 hex digest prefixed with 'sha256:'."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class EgressPolicyViolation(Exception):
    """Raised when an outbound dispatch violates host egress policy."""
    pass


@dataclass(frozen=True)
class CaidWarrant:
    """Station 1 cryptographic authorization warrant for an exact wire mutation."""
    operation_id: str
    action_caid: str
    target_url: str
    http_method: str
    expires_at: int
    budget_ceiling_minor: int
    signature_b64: str

    def canonical_bytes(self) -> bytes:
        payload = {
            "action_caid": self.action_caid,
            "budget_ceiling_minor": self.budget_ceiling_minor,
            "expires_at": self.expires_at,
            "http_method": self.http_method,
            "operation_id": self.operation_id,
            "target_url": self.target_url,
        }
        return encode_jcs(payload)


class HostCredentialVault:
    """
    Isolated host-side credential storage.
    Accessible only to the host proxy; never exposed to agent processes or microVM guests.
    """

    def __init__(self) -> None:
        self._secrets: Dict[str, str] = {}

    def register_credential(self, domain_or_url: str, credential_header_value: str) -> None:
        self._secrets[domain_or_url] = credential_header_value

    def get_credential(self, target_url: str) -> Optional[str]:
        # Match exact URL or base domain
        if target_url in self._secrets:
            return self._secrets[target_url]
        for key, val in self._secrets.items():
            if target_url.startswith(key):
                return val
        return None


class CredentialStarvationEgressProxy:
    """
    Host-side egress proxy enforcing credential starvation and exact CAID binding.
    """

    def __init__(
        self,
        audit_log_path: Path,
        station1_pubkey: ed25519.Ed25519PublicKey,
        destination_allowlist: Set[str],
        credential_vault: HostCredentialVault,
        upstream_dispatcher: Optional[Callable[[str, str, Dict[str, str], bytes], Dict[str, Any]]] = None,
    ) -> None:
        self.audit_log_path = audit_log_path
        self.station1_pubkey = station1_pubkey
        self.destination_allowlist = set(destination_allowlist)
        self.credential_vault = credential_vault
        self.upstream_dispatcher = upstream_dispatcher or self._default_mock_upstream_dispatch
        self.total_dispatches_forwarded: int = 0
        self.total_dispatches_blocked: int = 0
        self._used_warrant_nonces: Set[str] = set()

    def _default_mock_upstream_dispatch(
        self, method: str, url: str, headers: Dict[str, str], body: bytes
    ) -> Dict[str, Any]:
        """Default loopback simulation of upstream target."""
        return {
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "SETTLED", "timestamp": int(time.time())}).encode("utf-8"),
        }

    def dispatch_agent_request(
        self,
        target_url: str,
        http_method: str,
        raw_payload: Dict[str, Any],
        warrant: CaidWarrant,
        agent_supplied_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Receives an agent request, enforces egress policy, injects credentials,
        forwards upstream, and strips secrets before returning to the agent.
        """
        now = int(time.time())
        agent_headers = dict(agent_supplied_headers or {})

        # 1. Rule: Agent must not supply authorization credentials (starvation enforcement)
        for h in ("Authorization", "X-API-Key", "Proxy-Authorization", "Cookie"):
            if h in agent_headers or h.lower() in agent_headers:
                self._record_audit(
                    warrant.operation_id,
                    "HALT_AGENT_POSSESSES_OR_SUPPLIED_CREDENTIALS",
                    target_url,
                    http_method,
                    warrant.action_caid,
                )
                self.total_dispatches_blocked += 1
                raise EgressPolicyViolation(
                    "HALT_AGENT_POSSESSES_OR_SUPPLIED_CREDENTIALS: Agent must not carry bearer credentials"
                )

        # 2. Rule: Destination must be explicitly allowlisted
        is_allowlisted = any(target_url.startswith(allowed) for allowed in self.destination_allowlist)
        if not is_allowlisted:
            self._record_audit(
                warrant.operation_id,
                "HALT_DESTINATION_NOT_ALLOWLISTED",
                target_url,
                http_method,
                warrant.action_caid,
            )
            self.total_dispatches_blocked += 1
            raise EgressPolicyViolation(
                f"HALT_DESTINATION_NOT_ALLOWLISTED: '{target_url}' is not in host egress allowlist"
            )

        # 3. Rule: Verify Station 1 Ed25519 signature on warrant
        try:
            sig = base64.b64decode(warrant.signature_b64, validate=True)
            self.station1_pubkey.verify(sig, warrant.canonical_bytes())
        except (ValueError, InvalidSignature) as exc:
            self._record_audit(
                warrant.operation_id,
                "HALT_INVALID_CAID_WARRANT_SIGNATURE",
                target_url,
                http_method,
                warrant.action_caid,
            )
            self.total_dispatches_blocked += 1
            raise EgressPolicyViolation(
                "HALT_INVALID_CAID_WARRANT_SIGNATURE: Station 1 warrant signature invalid"
            ) from exc

        # 4. Rule: Verify warrant freshness
        if warrant.expires_at < now:
            self._record_audit(
                warrant.operation_id,
                "HALT_CAID_WARRANT_EXPIRED",
                target_url,
                http_method,
                warrant.action_caid,
            )
            self.total_dispatches_blocked += 1
            raise EgressPolicyViolation("HALT_CAID_WARRANT_EXPIRED: Warrant expired")

        # 5. Rule: Verify exact method and target URL matching
        if warrant.http_method != http_method or warrant.target_url != target_url:
            self._record_audit(
                warrant.operation_id,
                "HALT_WARRANT_TARGET_MISMATCH",
                target_url,
                http_method,
                warrant.action_caid,
            )
            self.total_dispatches_blocked += 1
            raise EgressPolicyViolation("HALT_WARRANT_TARGET_MISMATCH: Warrant parameters do not match request")

        # 6. Rule: Verify wire payload CAID commitment
        canonical_body = encode_jcs(raw_payload)
        computed_caid = sha256_prefixed(canonical_body)
        if computed_caid != warrant.action_caid:
            self._record_audit(
                warrant.operation_id,
                "HALT_WIRE_PAYLOAD_CAID_MISMATCH",
                target_url,
                http_method,
                warrant.action_caid,
            )
            self.total_dispatches_blocked += 1
            raise EgressPolicyViolation(
                f"HALT_WIRE_PAYLOAD_CAID_MISMATCH: Expected {warrant.action_caid}, got {computed_caid}"
            )

        # 7. Single-use warrant enforcement
        if warrant.operation_id in self._used_warrant_nonces:
            self._record_audit(
                warrant.operation_id,
                "HALT_WARRANT_REPLAY_ATTEMPT",
                target_url,
                http_method,
                warrant.action_caid,
            )
            self.total_dispatches_blocked += 1
            raise EgressPolicyViolation("HALT_WARRANT_REPLAY_ATTEMPT: Warrant has already been executed")
        self._used_warrant_nonces.add(warrant.operation_id)

        # 8. Host-Side Credential Injection
        injected_headers = dict(agent_headers)
        upstream_cred = self.credential_vault.get_credential(target_url)
        if upstream_cred:
            injected_headers["Authorization"] = upstream_cred
        injected_headers["X-AEIB-CAID"] = warrant.action_caid
        injected_headers["X-AEIB-Operation-ID"] = warrant.operation_id

        # 9. Outbound Wire Dispatch
        response = self.upstream_dispatcher(http_method, target_url, injected_headers, canonical_body)
        self.total_dispatches_forwarded += 1

        # 10. Audit Record Creation
        self._record_audit(
            warrant.operation_id,
            "DISPATCH_FORWARDED_AUTHORIZED",
            target_url,
            http_method,
            warrant.action_caid,
            status_code=response.get("status_code", 200),
        )

        # 11. Sanitize response (ensure no injected upstream credentials leak back to agent)
        sanitized_resp = {
            "status_code": response.get("status_code", 200),
            "body": response.get("body", b""),
            "headers": {
                k: v for k, v in response.get("headers", {}).items()
                if "auth" not in k.lower() and "cookie" not in k.lower()
            },
            "verified_caid": warrant.action_caid,
        }
        return sanitized_resp

    def _record_audit(
        self,
        operation_id: str,
        verdict: str,
        target_url: str,
        http_method: str,
        action_caid: str,
        status_code: Optional[int] = None,
    ) -> None:
        record = {
            "operation_id": operation_id,
            "verdict": verdict,
            "target_url": target_url,
            "http_method": http_method,
            "action_caid": action_caid,
            "timestamp": int(time.time()),
            "status_code": status_code,
        }
        line = json.dumps(record) + "\n"
        with open(self.audit_log_path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
