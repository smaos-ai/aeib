#!/usr/bin/env python3
"""
mcp_outcome_normalizer.py — AEIB vNext: Action vs. Outcome Execution Integrity Normalizer
Status: Prototype

Core Invariant:
    authorized write ≠ persisted write ≠ correct outcome

Cryptographic Trust Model Disambiguation:
    * SHA-256 Digest: Content fingerprinting (Implemented)
    * HMAC-SHA-256: Integrity/authenticity to holders of shared secret (Implemented, requires SMAOS_HMAC_KEY)
    * Ed25519: Public-key signature verification (Future production roadmap)
    * Merkle Structure: Tamper-evident ordering/inclusion evidence (Future production roadmap)
    * SCITT Integration: Transparency-log receipt and verifiable publication context (Future production roadmap)

Engineering Scope:
    * Ingests and normalizes selected Model Context Protocol (MCP) JSON-RPC 2.0 payloads.
    * Computes deterministic JSON bytes (JCS-compatible subset; not yet validated against RFC 8785 test vectors).
    * Enforces strict distinction: Wire HTTP 200 response ≠ Outcome Verification.
    * Quarantines ambiguous post-write states and requires authoritative downstream state probes.
"""

import sys
import os
import json
import time
import hashlib
import hmac
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

HMAC_KEY_ENV = "SMAOS_HMAC_KEY"

def get_signing_key() -> bytes:
    """Reads HMAC signing key from environment; fails closed if missing."""
    key = os.environ.get(HMAC_KEY_ENV)
    if not key:
        raise RuntimeError(f"Security error: Environment variable '{HMAC_KEY_ENV}' is required.")
    return key.encode("utf-8")

def deterministic_json_bytes(data: Any) -> bytes:
    """Returns deterministic JSON bytes.
    Note: JCS-compatible subset; not yet validated against RFC 8785 test vectors."""
    return json.dumps(
        data,
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True
    ).encode('utf-8')

def deterministic_digest(data: Any) -> str:
    """Computes SHA-256 digest of deterministic JSON bytes."""
    return f"sha256:{hashlib.sha256(deterministic_json_bytes(data)).hexdigest()}"

def is_mcp_jsonrpc_payload(log: Dict[str, Any]) -> bool:
    """Verifies that payload strictly matches Model Context Protocol JSON-RPC namespace."""
    if log.get("jsonrpc") != "2.0":
        return False
    method = str(log.get("method", ""))
    mcp_namespaces = ("tools/", "resources/", "prompts/", "notifications/", "initialize")
    return any(method.startswith(ns) for ns in mcp_namespaces) or "mcp_source" in log

@dataclass
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
    wall_clock_delta_ms: Optional[float]
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
        self.signing_key = key if key is not None else get_signing_key()

    def parse_mcp_call(self, raw_rpc: Dict[str, Any]) -> Tuple[str, Dict[str, Any], str]:
        """Extracts (tool_name, arguments, rpc_id) from MCP JSON-RPC payload."""
        rpc_id = str(raw_rpc.get("id", "mcp-anon-call"))
        method = raw_rpc.get("method", "tools/call")
        params = raw_rpc.get("params", {})
        if not isinstance(params, dict):
            params = {}

        if method == "tools/call":
            tool_name = params.get("name", "unknown_tool")
            arguments = params.get("arguments", params.get("args", {}))
        else:
            tool_name = method
            arguments = params

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
        transaction_time_tn: Optional[float] = None
    ) -> MCPOutcomeReceipt:
        tool_name, arguments, rpc_id = self.parse_mcp_call(raw_mcp_request)

        # 1. Composite action_id disambiguation: mcp://{session_id}/{step_sequence}/{rpc_id}/{tool_name}
        action_id = f"mcp://{session_id}/{step_sequence}/{rpc_id}/{tool_name}"

        # Authority Digest & Dispatch Timestamp
        auth_context = {"actor": actor, "tool": tool_name}
        if valid_time_t0 is not None:
            auth_context["valid_from"] = valid_time_t0
        authority_hash = deterministic_digest(auth_context)

        ttl_str = authority_ttl or "2026-09-28T16:00:00Z"
        dispatched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(transaction_time_tn or time.time()))

        # 2. Canonical Payload Digest
        req_payload_hash = deterministic_digest(arguments)

        # 3. Unmanufactured Authority Freshness (ΔAuth)
        if valid_time_t0 is None or transaction_time_tn is None:
            wall_clock_delta_ms = None
            freshness_status = "UNMEASURED"
        else:
            wall_clock_delta_ms = round((float(transaction_time_tn) - float(valid_time_t0)) * 1000.0, 2)
            freshness_status = "MEASURED"

        # 4. Post-Condition State Probe & Outcome Attestation
        # Invariant: Wire status 200 != Outcome Verification
        if post_state_probe is not None:
            downstream_state_hash = deterministic_digest(post_state_probe)
            observed_outcome = post_state_probe
            outcome_verified = bool(post_state_probe.get("outcome_confirmed", True))
            verification_method = "authoritative_state_probe"
            disposition = "CONFIRMED" if outcome_verified else "REFUSED"
        elif wire_status in (504, 502, 503):
            outcome_verified = False
            downstream_state_hash = None
            observed_outcome = {
                "wire_status": wire_status,
                "error": "POST_WRITE_TIMEOUT",
                "state_probe_confirmed": False
            }
            verification_method = "quarantined_unconfirmed_probe"
            disposition = "DISPATCHED_UNCONFIRMED"
        else:
            # Wire 200 without authoritative post-condition probe -> ACK_UNVERIFIED
            outcome_verified = False
            downstream_state_hash = None
            observed_outcome = {
                "wire_status": wire_status,
                "note": "HTTP ack received; physical outcome unverified without downstream state probe"
            }
            verification_method = "no_authoritative_probe"
            disposition = "ACK_UNVERIFIED"

        # 5. Symmetric HMAC-SHA-256 Integrity Tag
        sig_data = f"{action_id}:{actor}:{req_payload_hash}:{disposition}:{outcome_verified}:{wall_clock_delta_ms}"
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
            serialization_format="JCS-compatible subset (not RFC 8785 verified)",
            disposition=disposition,
            hmac_sha256_integrity_tag=mac_tag
        )

if __name__ == "__main__":
    os.environ[HMAC_KEY_ENV] = "demo_local_key_for_testing"
    normalizer = MCPOutcomeNormalizer()

    sample_mcp_call = {
        "jsonrpc": "2.0",
        "id": "101",
        "method": "tools/call",
        "params": {
            "name": "hotel.search",
            "arguments": {
                "destination": "Paris",
                "breakfast_included": True
            }
        }
    }

    # Test A: With authoritative state probe (Outcome Verified)
    probe = {
        "hotels_returned": 12,
        "all_in_paris": True,
        "breakfast_included": True,
        "outcome_confirmed": True
    }
    r_a = normalizer.process_execution(
        actor="agent:travel-planner",
        raw_mcp_request=sample_mcp_call,
        wire_status=200,
        post_state_probe=probe,
        session_id="sess-alpha",
        step_sequence=14
    )
    print("--- Test A: Authoritative Probe ---")
    print(json.dumps(r_a.to_dict(), indent=2))

    # Test B: Wire 200 without authoritative probe (ACK_UNVERIFIED)
    r_b = normalizer.process_execution(
        actor="agent:travel-planner",
        raw_mcp_request=sample_mcp_call,
        wire_status=200,
        post_state_probe=None,
        session_id="sess-alpha",
        step_sequence=15
    )
    print("\n--- Test B: Wire 200 without Probe (ACK_UNVERIFIED) ---")
    print(json.dumps(r_b.to_dict(), indent=2))
