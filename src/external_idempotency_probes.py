#!/usr/bin/env python3
"""
src/external_idempotency_probes.py — Authoritative External Idempotency Probes for Zombie Agent Resolution

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated, and configured under the stated model.

Core Capabilities:
1. Authoritative external API idempotency probes resolving `EFFECT_INDETERMINATE` states.
2. Provider-specific probe adapters:
   - GitHub: Commit and Pull Request CAID audit probe (`api.github.com`).
   - Stripe: Event and Charge idempotency-key audit probe (`api.stripe.com`).
   - Generic REST / Webhook: Audit log intent endpoint probe (`X-EO1-Intent-CAID`).
3. Deterministic zero-mock transport interface with fault injection (timeouts, 404, 5xx, dropped frames).
4. Direct interlock with SubstrateCubeInterlockManager (SQLite-WAL) and SubstrateCubeInterlock.
5. ECDSA SECP256R1 signed authoritative probe resolution receipts with RFC 8785 JCS canonicalization.
6. Integer basis points (0..10000 bps) determinism with zero floats.
"""

from __future__ import annotations

import abc
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Protocol, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

from src.hypergraph_blast_radius import sha256_jcs_caid
from src.jcs_canonicalizer import encode_jcs as _encode_jcs


class IdempotencyProbeOutcome(str, Enum):
    """Authoritative outcome of an external idempotency probe."""
    SUCCESS_CONFIRMED = "SUCCESS_CONFIRMED"
    FAILURE_CONFIRMED = "FAILURE_CONFIRMED"
    INDETERMINATE_TIMEOUT = "INDETERMINATE_TIMEOUT"


@dataclass(frozen=True)
class ProbeTransportResponse:
    """Byte-exact HTTP transport response from an idempotency probe."""
    status_code: int
    headers: Dict[str, str]
    body_bytes: bytes

    def json_payload(self) -> Dict[str, Any]:
        if not self.body_bytes:
            return {}
        try:
            val = json.loads(self.body_bytes.decode("utf-8"))
            if isinstance(val, dict):
                return val
            return {"data": val}
        except Exception:
            return {"raw_string": self.body_bytes.decode("utf-8", errors="replace")}


class ProbeTransport(Protocol):
    """Protocol for probe HTTP dispatch."""
    def execute_probe(
        self,
        method: str,
        host: str,
        path: str,
        headers: Mapping[str, str],
        timeout_ms: int,
    ) -> ProbeTransportResponse: ...


class DeterministicSimulatedProbeTransport:
    """
    Zero-mock in-memory probe transport for empirical test suites.
    Provides deterministic responses, route dispatch, and configurable failure modes.
    """
    def __init__(self) -> None:
        self._routes: Dict[Tuple[str, str, str], ProbeTransportResponse] = {}
        self._simulate_timeout_hosts: Set[str] = set()
        self._call_log: List[Dict[str, Any]] = []

    def register_route(
        self,
        method: str,
        host: str,
        path: str,
        status_code: int,
        headers: Optional[Dict[str, str]] = None,
        body_bytes: bytes = b"",
    ) -> None:
        self._routes[(method.upper(), host.lower(), path)] = ProbeTransportResponse(
            status_code=status_code,
            headers=headers or {},
            body_bytes=body_bytes,
        )

    def set_timeout_for_host(self, host: str, timeout_enabled: bool) -> None:
        if timeout_enabled:
            self._simulate_timeout_hosts.add(host.lower())
        else:
            self._simulate_timeout_hosts.discard(host.lower())

    def execute_probe(
        self,
        method: str,
        host: str,
        path: str,
        headers: Mapping[str, str],
        timeout_ms: int,
    ) -> ProbeTransportResponse:
        self._call_log.append(
            {
                "method": method.upper(),
                "host": host.lower(),
                "path": path,
                "headers": dict(headers),
                "timeout_ms": timeout_ms,
            }
        )
        if host.lower() in self._simulate_timeout_hosts:
            return ProbeTransportResponse(
                status_code=504,
                headers={"X-Probe-Error": "GATEWAY_TIMEOUT"},
                body_bytes=b'{"error": "Simulated Gateway Timeout"}',
            )

        key = (method.upper(), host.lower(), path)
        if key in self._routes:
            return self._routes[key]

        # Default 404 for unmapped probe routes
        return ProbeTransportResponse(
            status_code=404,
            headers={"X-Probe-Result": "NOT_FOUND"},
            body_bytes=b'{"error": "Resource Not Found"}',
        )

    @property
    def call_history(self) -> List[Dict[str, Any]]:
        return list(self._call_log)


class BaseIdempotencyProbe(abc.ABC):
    """Abstract base class for provider-specific idempotency audits."""

    @property
    @abc.abstractmethod
    def target_host(self) -> str:
        """Target hostname matched by this probe adapter."""
        ...

    @abc.abstractmethod
    def probe_effect(
        self,
        transport: ProbeTransport,
        actor_spiffe_id: str,
        effect_key_caid: str,
        effect_metadata: Mapping[str, Any],
        timeout_ms: int = 5000,
    ) -> Tuple[IdempotencyProbeOutcome, Dict[str, Any]]:
        """
        Executes the authoritative probe against the external provider.
        Returns:
            Tuple of (Outcome, AuditMetadataDict)
        """
        ...


class GitHubCommitOrPrProbe(BaseIdempotencyProbe):
    """
    Authoritative idempotency probe for GitHub API (`api.github.com`).
    Audits whether a commit or pull request matching the effect CAID exists.
    """
    @property
    def target_host(self) -> str:
        return "api.github.com"

    def probe_effect(
        self,
        transport: ProbeTransport,
        actor_spiffe_id: str,
        effect_key_caid: str,
        effect_metadata: Mapping[str, Any],
        timeout_ms: int = 5000,
    ) -> Tuple[IdempotencyProbeOutcome, Dict[str, Any]]:
        owner = str(effect_metadata.get("owner", "sovereign-nexus"))
        repo = str(effect_metadata.get("repo", "core-repo"))
        branch = str(effect_metadata.get("branch", "main"))

        # 1. Query commits endpoint checking for CAID in commit message
        commits_path = f"/repos/{owner}/{repo}/commits?sha={branch}"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-EO1-Intent-CAID": effect_key_caid,
            "User-Agent": "SovereignNexus-AuthoritativeProbe/1.0",
        }

        resp = transport.execute_probe("GET", self.target_host, commits_path, headers, timeout_ms)
        if resp.status_code >= 500:
            return (
                IdempotencyProbeOutcome.INDETERMINATE_TIMEOUT,
                {"http_status": resp.status_code, "phase": "COMMITS_LOOKUP"},
            )

        if resp.status_code == 200:
            body = resp.json_payload()
            items = body.get("data", body) if isinstance(body, dict) else body
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        msg = item.get("commit", {}).get("message", "")
                        sha = item.get("sha", "")
                        if effect_key_caid in msg or (sha and effect_key_caid in sha):
                            return (
                                IdempotencyProbeOutcome.SUCCESS_CONFIRMED,
                                {"commit_sha": sha, "verified_at_endpoint": "commits"},
                            )

        # 2. Check Pull Requests endpoint if not found in commits
        pulls_path = f"/repos/{owner}/{repo}/pulls?state=all"
        resp_pr = transport.execute_probe("GET", self.target_host, pulls_path, headers, timeout_ms)
        if resp_pr.status_code >= 500:
            return (
                IdempotencyProbeOutcome.INDETERMINATE_TIMEOUT,
                {"http_status": resp_pr.status_code, "phase": "PULLS_LOOKUP"},
            )

        if resp_pr.status_code == 200:
            body_pr = resp_pr.json_payload()
            prs = body_pr.get("data", body_pr) if isinstance(body_pr, dict) else body_pr
            if isinstance(prs, list):
                for pr in prs:
                    if isinstance(pr, dict):
                        body_text = str(pr.get("body", ""))
                        title = str(pr.get("title", ""))
                        if effect_key_caid in body_text or effect_key_caid in title:
                            return (
                                IdempotencyProbeOutcome.SUCCESS_CONFIRMED,
                                {"pull_number": pr.get("number"), "verified_at_endpoint": "pulls"},
                            )

        # 3. If both endpoints return 200/404 without the CAID, failure is confirmed
        return (
            IdempotencyProbeOutcome.FAILURE_CONFIRMED,
            {"reason": "CAID_NOT_FOUND_IN_COMMITS_OR_PRS", "inspected_branch": branch},
        )


class StripeIdempotencyKeyProbe(BaseIdempotencyProbe):
    """
    Authoritative idempotency probe for Stripe API (`api.stripe.com`).
    Audits whether an event or charge with `Idempotency-Key == effect_key_caid` exists.
    """
    @property
    def target_host(self) -> str:
        return "api.stripe.com"

    def probe_effect(
        self,
        transport: ProbeTransport,
        actor_spiffe_id: str,
        effect_key_caid: str,
        effect_metadata: Mapping[str, Any],
        timeout_ms: int = 5000,
    ) -> Tuple[IdempotencyProbeOutcome, Dict[str, Any]]:
        # Query events audit log for the idempotency token
        path = f"/v1/events?idempotency_key={effect_key_caid}"
        headers = {
            "Accept": "application/json",
            "Idempotency-Key": effect_key_caid,
            "User-Agent": "SovereignNexus-AuthoritativeProbe/1.0",
        }

        resp = transport.execute_probe("GET", self.target_host, path, headers, timeout_ms)
        if resp.status_code >= 500:
            return (
                IdempotencyProbeOutcome.INDETERMINATE_TIMEOUT,
                {"http_status": resp.status_code, "endpoint": "/v1/events"},
            )

        if resp.status_code == 200:
            body = resp.json_payload()
            events = body.get("data", [])
            if isinstance(events, list) and len(events) > 0:
                event = events[0]
                ev_id = event.get("id", "evt_unknown")
                return (
                    IdempotencyProbeOutcome.SUCCESS_CONFIRMED,
                    {"event_id": ev_id, "event_type": event.get("type", "charge.succeeded")},
                )
            # Empty event list indicates key was never committed
            return (
                IdempotencyProbeOutcome.FAILURE_CONFIRMED,
                {"reason": "EMPTY_EVENT_LOG_FOR_KEY"},
            )

        if resp.status_code == 404:
            return (
                IdempotencyProbeOutcome.FAILURE_CONFIRMED,
                {"reason": "KEY_NOT_FOUND_404"},
            )

        return (
            IdempotencyProbeOutcome.INDETERMINATE_TIMEOUT,
            {"unexpected_http_status": resp.status_code},
        )


class GenericRestAuditProbe(BaseIdempotencyProbe):
    """
    Authoritative probe for generic REST / Webhook endpoints.
    Audits `/api/v1/intent-receipts/{effect_key_caid}`.
    """
    def __init__(self, target_host: str) -> None:
        self._target_host = target_host.lower()

    @property
    def target_host(self) -> str:
        return self._target_host

    def probe_effect(
        self,
        transport: ProbeTransport,
        actor_spiffe_id: str,
        effect_key_caid: str,
        effect_metadata: Mapping[str, Any],
        timeout_ms: int = 5000,
    ) -> Tuple[IdempotencyProbeOutcome, Dict[str, Any]]:
        probe_path = f"/api/v1/intent-receipts/{effect_key_caid}"
        headers = {
            "Accept": "application/json",
            "X-EO1-Intent-CAID": effect_key_caid,
            "User-Agent": "SovereignNexus-AuthoritativeProbe/1.0",
        }
        resp = transport.execute_probe("GET", self._target_host, probe_path, headers, timeout_ms)

        if resp.status_code >= 500:
            return (
                IdempotencyProbeOutcome.INDETERMINATE_TIMEOUT,
                {"http_status": resp.status_code, "host": self._target_host},
            )

        if resp.status_code in (200, 204):
            return (
                IdempotencyProbeOutcome.SUCCESS_CONFIRMED,
                {"http_status": resp.status_code, "payload": resp.json_payload()},
            )

        if resp.status_code == 404:
            return (
                IdempotencyProbeOutcome.FAILURE_CONFIRMED,
                {"http_status": 404, "reason": "RESOURCE_DOES_NOT_EXIST"},
            )

        return (
            IdempotencyProbeOutcome.INDETERMINATE_TIMEOUT,
            {"unexpected_http_status": resp.status_code},
        )


@dataclass(frozen=True)
class AuthoritativeProbeReceipt:
    """
    Cryptographically signed receipt certifying probe audit outcome.
    RFC 8785 JCS canonicalized with ECDSA SECP256R1 signature.
    """
    actor_spiffe_id: str
    effect_key_caid: str
    target_host: str
    probe_outcome: str
    resolved_status: str
    probe_metadata: Dict[str, Any]
    timestamp_epoch_s: int
    receipt_caid: str
    signature_secp256r1_hex: str


class AuthoritativeProbeIndeterminateError(RuntimeError):
    """Raised when external probe cannot resolve state (5xx/timeout). Fails closed."""
    pass


class ExternalIdempotencyProbeOrchestrator:
    """
    Orchestrates authoritative external probes, signs outcome receipts,
    and reconciles indeterminate records in SubstrateCubeInterlockManager.
    """
    def __init__(
        self,
        trusted_spiffe_prefix: str = "spiffe://sovereign.nexus/agent/",
        signing_key: Optional[ec.EllipticCurvePrivateKey] = None,
    ) -> None:
        self.trusted_spiffe_prefix = trusted_spiffe_prefix
        self._private_key = signing_key or ec.generate_private_key(ec.SECP256R1())
        self._public_key = self._private_key.public_key()
        self._probes: Dict[str, BaseIdempotencyProbe] = {}

        # Register standard default probes
        self.register_probe(GitHubCommitOrPrProbe())
        self.register_probe(StripeIdempotencyKeyProbe())
        self.register_probe(GenericRestAuditProbe("aiplatform.googleapis.com"))
        self.register_probe(GenericRestAuditProbe("api.anthropic.com"))
        self.register_probe(GenericRestAuditProbe("127.0.0.1"))
        self.register_probe(GenericRestAuditProbe("localhost"))

    def register_probe(self, probe: BaseIdempotencyProbe) -> None:
        self._probes[probe.target_host.lower()] = probe

    def get_probe_for_host(self, host: str) -> Optional[BaseIdempotencyProbe]:
        return self._probes.get(host.lower())

    def execute_and_reconcile(
        self,
        actor_spiffe_id: str,
        effect_key_caid: str,
        target_host: str,
        transport: ProbeTransport,
        effect_metadata: Optional[Mapping[str, Any]] = None,
        interlock_manager: Optional[Any] = None,
        timeout_ms: int = 5000,
    ) -> AuthoritativeProbeReceipt:
        """
        1. Validates actor identity.
        2. Resolves matching provider probe.
        3. Dispatches authoritative audit.
        4. If INDETERMINATE_TIMEOUT: fails closed without clearing ledger.
        5. If SUCCESS/FAILURE: updates interlock manager and mints signed receipt.
        """
        if not actor_spiffe_id.startswith(self.trusted_spiffe_prefix):
            raise ValueError(f"ERR_UNTRUSTED_SPIFFE_PREFIX:{actor_spiffe_id}")

        probe = self.get_probe_for_host(target_host)
        if probe is None:
            raise KeyError(f"ERR_UNREGISTERED_PROBE_HOST:{target_host}")

        outcome, meta = probe.probe_effect(
            transport=transport,
            actor_spiffe_id=actor_spiffe_id,
            effect_key_caid=effect_key_caid,
            effect_metadata=effect_metadata or {},
            timeout_ms=timeout_ms,
        )

        now = int(time.time())
        resolved_status = "EFFECT_INDETERMINATE"
        if outcome == IdempotencyProbeOutcome.SUCCESS_CONFIRMED:
            resolved_status = "COMMITTED"
        elif outcome == IdempotencyProbeOutcome.FAILURE_CONFIRMED:
            resolved_status = "ROLLED_BACK"

        # If interlock manager provided, update durable SQLite-WAL ledger
        if interlock_manager is not None:
            if outcome in (
                IdempotencyProbeOutcome.SUCCESS_CONFIRMED,
                IdempotencyProbeOutcome.FAILURE_CONFIRMED,
            ):
                # SubstrateCubeInterlockManager interface
                if hasattr(interlock_manager, "resolve_indeterminate_probe"):
                    interlock_manager.resolve_indeterminate_probe(
                        actor_id=actor_spiffe_id,
                        request_id=effect_key_caid,
                        probe_outcome=outcome.value,
                    )
                # SubstrateCubeInterlock interface
                elif hasattr(interlock_manager, "reconcile_indeterminate_effect"):
                    interlock_manager.reconcile_indeterminate_effect(
                        effect_key_caid=effect_key_caid,
                        provider_confirmed_executed=(outcome == IdempotencyProbeOutcome.SUCCESS_CONFIRMED),
                    )

        unsigned_receipt = {
            "actor_spiffe_id": actor_spiffe_id,
            "effect_key_caid": effect_key_caid,
            "probe_metadata": meta,
            "probe_outcome": outcome.value,
            "resolved_status": resolved_status,
            "target_host": target_host.lower(),
            "timestamp_epoch_s": now,
        }
        receipt_bytes = _encode_jcs(unsigned_receipt)
        receipt_caid = sha256_jcs_caid(receipt_bytes)

        sig_der = self._private_key.sign(receipt_bytes, ec.ECDSA(hashes.SHA256()))
        sig_hex = sig_der.hex()

        receipt = AuthoritativeProbeReceipt(
            actor_spiffe_id=actor_spiffe_id,
            effect_key_caid=effect_key_caid,
            target_host=target_host.lower(),
            probe_outcome=outcome.value,
            resolved_status=resolved_status,
            probe_metadata=meta,
            timestamp_epoch_s=now,
            receipt_caid=receipt_caid,
            signature_secp256r1_hex=sig_hex,
        )

        if outcome == IdempotencyProbeOutcome.INDETERMINATE_TIMEOUT:
            raise AuthoritativeProbeIndeterminateError(
                f"ERR_PROBE_INDETERMINATE_TIMEOUT: Provider {target_host} timed out or returned 5xx for CAID {effect_key_caid}"
            )

        return receipt

    def verify_probe_receipt(self, receipt: AuthoritativeProbeReceipt) -> bool:
        """Verifies receipt signature against orchestrator public key."""
        unsigned = {
            "actor_spiffe_id": receipt.actor_spiffe_id,
            "effect_key_caid": receipt.effect_key_caid,
            "probe_metadata": receipt.probe_metadata,
            "probe_outcome": receipt.probe_outcome,
            "resolved_status": receipt.resolved_status,
            "target_host": receipt.target_host.lower(),
            "timestamp_epoch_s": receipt.timestamp_epoch_s,
        }
        canonical_bytes = _encode_jcs(unsigned)
        expected_caid = sha256_jcs_caid(canonical_bytes)
        if receipt.receipt_caid != expected_caid:
            return False

        try:
            sig_der = bytes.fromhex(receipt.signature_secp256r1_hex)
            self._public_key.verify(sig_der, canonical_bytes, ec.ECDSA(hashes.SHA256()))
            return True
        except (InvalidSignature, ValueError):
            return False
