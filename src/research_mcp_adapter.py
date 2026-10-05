"""
AEIB Research MCP Adapter (Zone 1 Open Core Prototype)
Implements Model Context Protocol (MCP) tool interception, canonical action binding (RFC 8785 JCS),
retry-suppression latching, and out-of-band authoritative probing for scientific research workflows
(Figshare dataset staging and Dimensions/OpenAlex literature query executions).
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple


def jcs_canonicalize(data: Any) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS)."""
    return json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def derive_caid(noun: str, verb: str, payload: Dict[str, Any]) -> str:
    """Derive deterministic Canonical Action Identifier: H(Noun || Verb || JCS(Payload))."""
    hasher = hashlib.sha256()
    hasher.update(noun.strip().upper().encode("utf-8"))
    hasher.update(verb.strip().upper().encode("utf-8"))
    hasher.update(jcs_canonicalize(payload))
    return hasher.hexdigest()


class ResearchMCPInterceptor:
    """
    Interprets MCP tool requests for scientific research APIs, binds invariant CAIDs,
    and manages execution state transitions across ambiguous transport events.
    """

    def __init__(self, key_pair: Optional[Any] = None):
        self.key_pair = key_pair
        self.dispatched_store: Dict[str, Dict[str, Any]] = {}
        self.lockout_latches: Dict[str, bool] = {}

    def prepare_mcp_action(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses an MCP tool call (e.g., 'figshare_stage_deposit', 'dimensions_query_literature'),
        derives CAID, and returns a bounded dispatch bundle.
        """
        parts = tool_name.split("_", 1)
        noun = parts[0].upper()
        verb = parts[1].upper() if len(parts) > 1 else "EXECUTE"
        caid = derive_caid(noun, verb, arguments)

        return {
            "caid": caid,
            "noun": noun,
            "verb": verb,
            "tool_name": tool_name,
            "arguments": arguments,
            "status": "PREPARED",
            "timestamp": time.time(),
        }

    def record_transport_drop(self, caid: str, error_code: str, error_message: str) -> Dict[str, Any]:
        """
        Trips the software lockout latch upon HTTP 504 / socket severance,
        quarantining the CAID into DISPATCHED_UNCONFIRMED to prevent speculative retry.
        """
        self.lockout_latches[caid] = True
        record = {
            "caid": caid,
            "state": "DISPATCHED_UNCONFIRMED",
            "error_code": error_code,
            "error_message": error_message,
            "lockout_tripped": True,
            "recorded_at": time.time(),
        }
        self.dispatched_store[caid] = record
        return record

    def should_suppress_retry(self, caid: str) -> bool:
        """Returns True if the software lockout latch is engaged for the CAID."""
        return self.lockout_latches.get(caid, False)

    def reconcile_authoritative_probe(
        self, caid: str, probe_result: Optional[Dict[str, Any]]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Reconciles authoritative out-of-band state:
        - If remote record exists with matching CAID -> OUTCOME_VERIFIED (Completed)
        - If remote record explicitly not found -> RECONCILIATION_NOT_FOUND (Safe to reset/retry)
        - If probe times out / returns ambiguous response -> EFFECT_UNKNOWN (Escalate to Human)
        """
        if not self.should_suppress_retry(caid):
            return "NO_QUARANTINE", {"error": "CAID is not under lockout"}

        if probe_result is None:
            disposition = "EFFECT_UNKNOWN"
            human_action_required = "Escalate to supervisor"
        elif probe_result.get("exists") is True and probe_result.get("caid") == caid:
            disposition = "OUTCOME_VERIFIED"
            human_action_required = "Clear quarantine - mutation verified"
            self.lockout_latches[caid] = False  # Cleared
        elif probe_result.get("exists") is False:
            disposition = "RECONCILIATION_NOT_FOUND"
            human_action_required = "Authorize clean recovery"
        else:
            disposition = "EFFECT_UNKNOWN"
            human_action_required = "Escalate for manual inspection"

        evidence = {
            "caid": caid,
            "disposition": disposition,
            "probe_observation": probe_result,
            "human_action_required": human_action_required,
            "reconciled_at": time.time(),
        }
        return disposition, evidence
