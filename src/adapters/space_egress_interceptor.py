#!/usr/bin/env python3
"""
src/adapters/space_egress_interceptor.py
================================================================================
Host-Level MicroVM Secret-Injection & TLS/SNI Egress Interceptor (AT70).

Inspired by Perplexity SPACE (Firecracker microVM sandbox architecture) and
Zero-Credential Agent Isolation patterns.

Evaluates under the stated model:
  1. Blocks DNS spoofing and shared-CDN IP laundering by verifying both the TLS SNI
     and the destination IP against pinned host allowlists.
  2. Blocks domain fronting by verifying that TLS SNI strictly matches the HTTP Host header.
  3. Enforces that the guest microVM holds zero raw API secrets.
  4. Injects downstream credentials (Authorization: Bearer ...) and deterministic
     idempotency keys only AFTER verifying a valid AEIB Station 1 cryptographic warrant.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    """Computes a SHA-256 digest with standard prefix."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class OutboundMicroVmRequest:
    """Outbound HTTP proposal initiated from an unprivileged guest microVM."""

    operation_id: str
    tls_sni: str
    http_host_header: str
    resolved_dest_ip: str
    http_method: str
    path: str
    canonical_body_caid: str
    station1_approval_sig_b64: Optional[str]


class HostEgressSecretInjector:
    """
    Host-side egress filter terminating TLS/SNI inspection and injecting
    credentials onto the external wire only upon verified Station 1 warrants.
    """

    def __init__(
        self,
        station1_pubkey: Ed25519PublicKey,
        allowed_domains_to_ips: Dict[str, Set[str]],
        host_secret_vault: Dict[str, str],
    ) -> None:
        self.station1_pubkey = station1_pubkey
        self.allowed_domains_to_ips = allowed_domains_to_ips
        self._vault = host_secret_vault

    def inspect_and_inject_secret(
        self, req: OutboundMicroVmRequest
    ) -> Tuple[str, Optional[str], Optional[Dict[str, str]]]:
        """
        Evaluates egress request safety and injects host-held secrets.
        Returns (disposition, rejection_code, injected_headers).
        """
        # 1. Defeat domain fronting / SNI-Host header mismatch
        if req.tls_sni.lower() != req.http_host_header.lower():
            return "BLOCKED", "HALT_EGRESS_SNI_HOST_MISMATCH", None

        domain = req.tls_sni.lower()
        if domain not in self.allowed_domains_to_ips:
            return "BLOCKED", "HALT_EGRESS_UNPINNED_DOMAIN", None

        # 2. Defeat DNS spoofing / shared-CDN IP laundering
        if req.resolved_dest_ip not in self.allowed_domains_to_ips[domain]:
            return "BLOCKED", "HALT_EGRESS_DNS_OR_SHARED_CDN_IP_SPOOF", None

        # 3. Verify AEIB Station 1 cryptographic authorization over the exact payload CAID
        if not req.station1_approval_sig_b64:
            return "BLOCKED", "HALT_MISSING_STATION1_WARRANT", None

        signed_envelope = encode_jcs(
            {
                "canonical_body_caid": req.canonical_body_caid,
                "domain": domain,
                "http_method": req.http_method,
                "operation_id": req.operation_id,
                "path": req.path,
            }
        )

        try:
            sig_bytes = base64.b64decode(req.station1_approval_sig_b64, validate=True)
            self.station1_pubkey.verify(sig_bytes, signed_envelope)
        except Exception:
            return "BLOCKED", "HALT_INVALID_STATION1_WARRANT_SIGNATURE", None

        # 4. Inject secret outside the guest VM + bind deterministic Idempotency-Key
        secret = self._vault.get(domain)
        if not secret:
            return "BLOCKED", "HALT_EGRESS_SECRET_NOT_CONFIGURED", None

        idem_hash = hashlib.sha256(
            f"{req.operation_id}:{req.canonical_body_caid}".encode("utf-8")
        ).hexdigest()[:32]

        injected_headers = {
            "Authorization": f"Bearer {secret}",
            "Idempotency-Key": f"aeib-v1-{idem_hash}",
        }
        return "DISPATCHED_WITH_HOST_SECRET", None, injected_headers
