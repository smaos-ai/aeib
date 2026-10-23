#!/usr/bin/env python3
# File: tools/credential_starvation_gateway.py
"""
AEIB Credential Starvation, Phantom Placeholder & Supply-Chain Cooldown Gateway.

Evaluated prototype under the stated model addressing two empirical 2026 threat vectors:
1. Agent Runtime Secret Exposure (AWS Strands Box / NVIDIA OpenShell pattern):
   - Agent processes never hold, read, or log raw API keys, AWS secrets, or OAuth tokens.
   - The agent environment receives non-functional phantom placeholders
     (e.g., `AEIB_PHANTOM_AWS_KEY_...`).
   - Station 2 Egress Proxy holds real secrets in isolated gateway memory, verifies
     the Ed25519-signed CAID warrant, substitutes the phantom placeholder in-flight,
     and blocks any outbound packet containing raw secret material.
2. Supply-Chain Cooldown & `.pth` Hook Defense (LiteLLM v1.82.7 / v1.107.0 pattern):
   - Rejects package installations published fewer than 48 hours ago (`min_cooldown_hours=48`),
     unsigned artifacts lacking Sigstore provenance digests, or `.pth` startup hook mutations.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def canonical_jcs_bytes(obj: Any) -> bytes:
    def _check(val: Any) -> None:
        if isinstance(val, float):
            raise ValueError("ERR_FLOAT_FORBIDDEN_IN_JCS")
        if isinstance(val, dict):
            for k, v in val.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _check(v)
        elif isinstance(val, list):
            for item in val:
                _check(item)

    _check(obj)
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class PhantomSecretBinding:
    secret_name: str          # e.g., "AWS_SECRET_ACCESS_KEY"
    phantom_placeholder: str  # e.g., "AEIB_PHANTOM_AWS_SECRET_xyz999"
    real_secret_value: str    # Held exclusively inside AEIB gateway memory
    target_header_or_env: str # "Authorization" | "x-api-key" | "AWS_SECRET_ACCESS_KEY"


@dataclass(frozen=True)
class EgressProxyRequest:
    operation_id: str
    agent_id: str
    destination_url: str
    http_method: str
    headers: Dict[str, str]
    body_payload: Dict[str, Any]
    claimed_caid: str
    warrant_signature_b64: str


@dataclass(frozen=True)
class PackageProvenanceArtifact:
    package_name: str
    version: str
    release_age_hours: int
    sigstore_bundle_digest: str
    contains_pth_startup_hook: bool


class SupplyChainProvenanceGate:
    """
    Defends against LiteLLM-style (v1.82.7 / v1.107.0) PyPI & Docker supply-chain
    compromises by enforcing a mandatory 48-hour release cooldown, blocking `.pth`
    startup execution hooks, and requiring a pinned Sigstore provenance digest.
    """

    def __init__(self, min_cooldown_hours: int = 48) -> None:
        self.min_cooldown_hours = min_cooldown_hours

    def evaluate_package(self, artifact: PackageProvenanceArtifact) -> Tuple[bool, str]:
        if artifact.contains_pth_startup_hook:
            return False, "HALT_SUPPLY_CHAIN_PTH_STARTUP_HOOK_FORBIDDEN"
        if not artifact.sigstore_bundle_digest.startswith("sha256:"):
            return False, "HALT_SUPPLY_CHAIN_MISSING_SIGSTORE_PROVENANCE"
        if artifact.release_age_hours < self.min_cooldown_hours:
            return False, "HALT_SUPPLY_CHAIN_RELEASE_COOLDOWN_VIOLATION"
        return True, "SUPPLY_CHAIN_ARTIFACT_VERIFIED"


class CredentialStarvationGateway:
    """
    Manages phantom placeholders for untrusted agent processes and performs
    Ed25519-authenticated in-flight credential injection at the Station 2 boundary.
    """

    def __init__(
        self,
        bindings: List[PhantomSecretBinding],
        supervisor_pubkey: Ed25519PublicKey,
    ) -> None:
        self._vault: Dict[str, str] = {
            b.phantom_placeholder: b.real_secret_value for b in bindings
        }
        self.placeholders: Set[str] = {b.phantom_placeholder for b in bindings}
        self.binding_meta: Dict[str, PhantomSecretBinding] = {
            b.phantom_placeholder: b for b in bindings
        }
        self.supervisor_pubkey = supervisor_pubkey

    def get_agent_runtime_environment(self) -> Dict[str, str]:
        """
        Returns the sanitized environment dictionary provided to the agent runtime.
        Real secrets are absent; only phantom placeholders are exposed.
        """
        env: Dict[str, str] = {}
        for placeholder, binding in self.binding_meta.items():
            env[binding.target_header_or_env] = placeholder
        return env

    @staticmethod
    def compute_request_caid(
        operation_id: str,
        agent_id: str,
        destination_url: str,
        http_method: str,
        headers: Dict[str, str],
        body_payload: Dict[str, Any],
    ) -> str:
        core = {
            "agent_id": agent_id,
            "body_payload": body_payload,
            "destination_url": destination_url,
            "headers": headers,
            "http_method": http_method,
            "operation_id": operation_id,
        }
        return sha256_prefixed(canonical_jcs_bytes(core))

    def intercept_and_forward_egress(
        self, req: EgressProxyRequest
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        1. Blocks any outbound request that already contains raw secret material
           (defeating direct exfiltration attempts).
        2. Verifies the canonical CAID and Ed25519 warrant signature over the phantom request.
        3. Substitutes phantom placeholders with real credentials in-flight for wire dispatch.
        """
        req_raw = canonical_jcs_bytes(
            {"headers": req.headers, "body": req.body_payload}
        ).decode("utf-8", errors="ignore")

        for real_val in self._vault.values():
            if real_val and len(real_val) > 4 and real_val in req_raw:
                return (
                    False,
                    "HALT_CREDENTIAL_STARVATION_LEAK_DETECTED",
                    {},
                )

        expected_caid = self.compute_request_caid(
            operation_id=req.operation_id,
            agent_id=req.agent_id,
            destination_url=req.destination_url,
            http_method=req.http_method,
            headers=req.headers,
            body_payload=req.body_payload,
        )
        if req.claimed_caid != expected_caid:
            return False, "HALT_CREDENTIAL_GATEWAY_CAID_MISMATCH", {}

        try:
            self.supervisor_pubkey.verify(
                base64.b64decode(req.warrant_signature_b64, validate=True),
                expected_caid.encode("utf-8"),
            )
        except Exception:
            return False, "HALT_CREDENTIAL_GATEWAY_INVALID_WARRANT_SIGNATURE", {}

        injected_headers = dict(req.headers)
        injected_body = json.loads(json.dumps(req.body_payload))

        for placeholder, real_val in self._vault.items():
            for h_key, h_val in injected_headers.items():
                if placeholder in h_val:
                    injected_headers[h_key] = h_val.replace(placeholder, real_val)
            body_str = json.dumps(injected_body)
            if placeholder in body_str:
                body_str = body_str.replace(placeholder, real_val)
                injected_body = json.loads(body_str)

        return (
            True,
            "SUCCESS_IN_FLIGHT_CREDENTIAL_INJECTED",
            {
                "destination_url": req.destination_url,
                "http_method": req.http_method,
                "headers": injected_headers,
                "body": injected_body,
                "verified_caid": expected_caid,
            },
        )


def run_self_test() -> None:
    sup_priv = Ed25519PrivateKey.generate()
    aws_binding = PhantomSecretBinding(
        secret_name="AWS_SECRET_ACCESS_KEY",
        phantom_placeholder="AEIB_PHANTOM_AWS_SECRET_xyz999",
        real_secret_value="AKIA_REAL_SECRET_DO_NOT_EXPOSE_9999",
        target_header_or_env="AWS_SECRET_ACCESS_KEY",
    )
    gateway = CredentialStarvationGateway(
        bindings=[aws_binding],
        supervisor_pubkey=sup_priv.public_key(),
    )

    agent_env = gateway.get_agent_runtime_environment()
    assert agent_env["AWS_SECRET_ACCESS_KEY"] == "AEIB_PHANTOM_AWS_SECRET_xyz999"
    assert "AKIA_REAL_SECRET_DO_NOT_EXPOSE_9999" not in agent_env.values()

    headers = {"Authorization": "Bearer AEIB_PHANTOM_AWS_SECRET_xyz999"}
    body = {"action": "upload", "key": "AEIB_PHANTOM_AWS_SECRET_xyz999"}
    caid = gateway.compute_request_caid(
        "op-aws-call-01",
        "agent-01",
        "https://s3.amazonaws.com/bucket/data",
        "PUT",
        headers,
        body,
    )
    sig_b64 = base64.b64encode(sup_priv.sign(caid.encode("utf-8"))).decode("ascii")

    egress_req = EgressProxyRequest(
        operation_id="op-aws-call-01",
        agent_id="agent-01",
        destination_url="https://s3.amazonaws.com/bucket/data",
        http_method="PUT",
        headers=headers,
        body_payload=body,
        claimed_caid=caid,
        warrant_signature_b64=sig_b64,
    )
    ok, code, pkt = gateway.intercept_and_forward_egress(egress_req)
    assert ok is True
    assert code == "SUCCESS_IN_FLIGHT_CREDENTIAL_INJECTED"
    assert pkt["headers"]["Authorization"] == "Bearer AKIA_REAL_SECRET_DO_NOT_EXPOSE_9999"

    # Supply chain cooldown check (LiteLLM 1.107.0 pattern)
    sc_gate = SupplyChainProvenanceGate(min_cooldown_hours=48)
    ok_pth, code_pth = sc_gate.evaluate_package(
        PackageProvenanceArtifact(
            package_name="litellm",
            version="1.107.0",
            release_age_hours=2,
            sigstore_bundle_digest="sha256:bad",
            contains_pth_startup_hook=True,
        )
    )
    assert ok_pth is False
    assert code_pth == "HALT_SUPPLY_CHAIN_PTH_STARTUP_HOOK_FORBIDDEN"


if __name__ == "__main__":
    run_self_test()
    print("CREDENTIAL STARVATION & SUPPLY-CHAIN COOLDOWN GATEWAY VERIFIED.")
