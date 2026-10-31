#!/usr/bin/env python3
"""
src/mcp_outcome_normalizer.py
================================================================================
Action vs. Outcome Execution Integrity Normalizer for Model Context Protocol (MCP).

Normalizes MCP JSON-RPC 2.0 tool calls, derives deterministic action IDs, binds
authority contexts and payload hashes via RFC 8785 canonical JSON, and evaluates
physical downstream consequences via authoritative state probes.

Core Physical Invariant:
    authorized write != persisted write != correct physical outcome

Evaluation Status: INTERNAL PREVIEW COMMISSIONED.
Epistemic Boundary: Observed, tested, and configured under the stated model.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

HMAC_KEY_ENV: str = "SMAOS_HMAC_KEY"  # claim: config - environment variable for HMAC secret


def get_signing_key() -> bytes:
    """Reads HMAC signing key from environment; fails closed if missing."""
    key = os.environ.get(HMAC_KEY_ENV)
    if not key:
        raise RuntimeError(f"Security error: Environment variable '{HMAC_KEY_ENV}' is required.")
    return key.encode("utf-8")


def deterministic_json_bytes(data: Any) -> bytes:
    """Returns deterministic JSON bytes via the RFC 8785 single-source canonicalizer."""
    try:
        from src.jcs_canonicalizer import encode_jcs
    except ImportError:
        from jcs_canonicalizer import encode_jcs  # type: ignore
    return encode_jcs(data)


def deterministic_digest(data: Any) -> str:
    """Computes SHA-256 digest of deterministic JSON bytes."""
    return f"sha256:{hashlib.sha256(deterministic_json_bytes(data)).hexdigest()}"


def is_mcp_jsonrpc_payload(log: Dict[str, Any]) -> bool:
    """Verifies that payload strictly matches Model Context Protocol JSON-RPC namespace."""
    if not isinstance(log, dict):
        return False
    if log.get("jsonrpc") != "2.0":
        return False
    method = str(log.get("method", ""))
    mcp_namespaces = ("tools/", "resources/", "prompts/", "notifications/", "initialize")
    return any(method.startswith(ns) for ns in mcp_namespaces) or "mcp_source" in log


@dataclass(frozen=True)
class MCPOutcomeReceipt:
    action_id: str
    actor: str
    authority_hash: str
    authority_ttl: str
    dispatched_at: str
    request_payload_hash: str
    downstream_state_hash: Optional[str]
    observed_outcome: Dict[str, Any]
    outcome_verified: bool
    verification_method: str
    wall_clock_delta_ms: Optional[int]
    freshness_status: str
    serialization_format: str
    disposition: str
    hmac_sha256_integrity_tag: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MCPOutcomeNormalizer:
    """
    Diagnostic adapter normalizing MCP JSON-RPC 2.0 tool calls
    and evaluating physical downstream consequence integrity.
    """

    def __init__(self, key: Optional[bytes] = None):
        if key is not None:
            if not isinstance(key, bytes) or len(key) == 0:
                raise ValueError("Key must be non-empty bytes")
            self.signing_key = key
        else:
            self.signing_key = get_signing_key()

    def parse_mcp_call(self, raw_rpc: Dict[str, Any]) -> Tuple[str, Dict[str, Any], str]:
        """Extracts (tool_name, arguments, rpc_id) from MCP JSON-RPC payload."""
        if not isinstance(raw_rpc, dict):
            raise ValueError("raw_rpc must be a dictionary")

        rpc_id = str(raw_rpc.get("id", "mcp-anon-call"))
        method = raw_rpc.get("method", "tools/call")
        params = raw_rpc.get("params", {})
        if not isinstance(params, dict):
            params = {}

        if method == "tools/call":
            tool_name = str(params.get("name", "unknown_tool"))
            arguments = params.get("arguments", params.get("args", {}))
        else:
            tool_name = str(method)
            arguments = params

        if not isinstance(arguments, dict):
            arguments = {"raw_value": arguments}

        return tool_name, arguments, rpc_id

    def process_execution(
        self,
        actor: str,
        raw_mcp_request: Dict[str, Any],
        wire_status: Optional[int] = None,
        post_state_probe: Optional[Dict[str, Any]] = None,
        authority_ttl: Optional[str] = None,
        session_id: str = "sess-default",
        step_sequence: int = 1,
        valid_time_t0: Optional[float] = None,
        transaction_time_tn: Optional[float] = None,
    ) -> MCPOutcomeReceipt:
        """Processes execution parameters and returns an immutable, verified MCPOutcomeReceipt."""
        if not actor or not isinstance(actor, str):
            raise ValueError("actor must be a non-empty string")
        if step_sequence < 0:
            raise ValueError("step_sequence must be non-negative")

        tool_name, arguments, rpc_id = self.parse_mcp_call(raw_mcp_request)

        # 1. Composite action_id disambiguation: mcp://{session_id}/{step_sequence}/{rpc_id}/{tool_name}
        action_id = f"mcp://{session_id}/{step_sequence}/{rpc_id}/{tool_name}"

        # Authority Digest & Dispatch Timestamp
        auth_context: Dict[str, Any] = {"actor": actor, "tool": tool_name}
        if valid_time_t0 is not None:
            auth_context["valid_from"] = valid_time_t0
        authority_hash = deterministic_digest(auth_context)

        ttl_str = authority_ttl if authority_ttl is not None else "2026-09-28T16:00:00Z"
        time_epoch = transaction_time_tn if transaction_time_tn is not None else time.time()
        dispatched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time_epoch))

        # 2. Canonical Payload Digest
        req_payload_hash = deterministic_digest(arguments)

        # 3. Unmanufactured Authority Freshness (ΔAuth in integer milliseconds)
        if valid_time_t0 is None or transaction_time_tn is None:
            wall_clock_delta_ms = None
            freshness_status = "UNMEASURED"
        else:
            delta_val = float(transaction_time_tn) - float(valid_time_t0)
            wall_clock_delta_ms = int(round(delta_val * 1000.0))
            if wall_clock_delta_ms < 0:
                freshness_status = "CLOCK_ORDER_INVALID"
            else:
                freshness_status = "MEASURED"

        # 4. Post-Condition State Probe & Outcome Attestation
        # Invariant: Wire status 200 != Outcome Verification
        if post_state_probe is not None:
            if not isinstance(post_state_probe, dict):
                raise ValueError("post_state_probe must be a dict")
            downstream_state_hash = deterministic_digest(post_state_probe)
            observed_outcome = post_state_probe
            outcome_verified = bool(post_state_probe.get("outcome_confirmed", True))
            verification_method = "authoritative_state_probe"
            disposition = "CONFIRMED" if outcome_verified else "REFUSED"
        elif wire_status in (502, 503, 504):
            outcome_verified = False
            downstream_state_hash = None
            observed_outcome = {
                "wire_status": wire_status,
                "error": "POST_WRITE_TIMEOUT",
                "state_probe_confirmed": False,
            }
            verification_method = "quarantined_unconfirmed_probe"
            disposition = "DISPATCHED_UNCONFIRMED"
        else:
            # Wire 200 without authoritative post-condition probe -> ACK_UNVERIFIED
            outcome_verified = False
            downstream_state_hash = None
            observed_outcome = {
                "wire_status": wire_status,
                "note": "HTTP ack received; physical outcome unverified without downstream state probe",
            }
            verification_method = "no_authoritative_probe"
            disposition = "ACK_UNVERIFIED"

        # 5. Symmetric HMAC-SHA-256 Integrity Tag
        delta_str = str(wall_clock_delta_ms) if wall_clock_delta_ms is not None else "None"
        sig_data = f"{action_id}:{actor}:{req_payload_hash}:{disposition}:{outcome_verified}:{delta_str}"
        mac_tag = hmac.new(self.signing_key, sig_data.encode("utf-8"), hashlib.sha256).hexdigest()

        return MCPOutcomeReceipt(
            action_id=action_id,
            actor=actor,
            authority_hash=authority_hash,
            authority_ttl=ttl_str,
            dispatched_at=dispatched_at,
            request_payload_hash=req_payload_hash,
            downstream_state_hash=downstream_state_hash,
            observed_outcome=observed_outcome,
            outcome_verified=outcome_verified,
            verification_method=verification_method,
            wall_clock_delta_ms=wall_clock_delta_ms,
            freshness_status=freshness_status,
            serialization_format="RFC 8785 Canonical JSON (JCS)",
            disposition=disposition,
            hmac_sha256_integrity_tag=mac_tag,
        )

    def verify_receipt(self, receipt: MCPOutcomeReceipt, key: Optional[bytes] = None) -> bool:
        """Verifies the HMAC-SHA-256 integrity tag of an MCPOutcomeReceipt."""
        if not isinstance(receipt, MCPOutcomeReceipt):
            return False
        verify_key = key if key is not None else self.signing_key
        delta_str = str(receipt.wall_clock_delta_ms) if receipt.wall_clock_delta_ms is not None else "None"
        sig_data = (
            f"{receipt.action_id}:{receipt.actor}:{receipt.request_payload_hash}:"
            f"{receipt.disposition}:{receipt.outcome_verified}:{delta_str}"
        )
        expected_mac = hmac.new(verify_key, sig_data.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(receipt.hmac_sha256_integrity_tag, expected_mac)
