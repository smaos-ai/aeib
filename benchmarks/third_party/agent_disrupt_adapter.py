#!/usr/bin/env python3
"""
agent_disrupt_adapter.py
================================================================================
Multi-Framework Disruption Adapter for AgentDisruptBench 20 profiles.
Intercepts LangGraph / AutoGen / CrewAI tool invocations at Layer 1 and enforces 
deterministic dispositions under fault injection via RFC 8785 JCS CAID derivation.
Zero mocks. Deterministic hash identity.
"""

import hashlib
import json
from typing import Dict, Any, Callable

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[2]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs

def canonical_json_bytes(obj: Any) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) deterministic subset."""
    return _reference_encode_jcs(obj)

def derive_disrupt_caid(noun: str, verb: str, payload: Dict[str, Any]) -> str:
    prefix = f"{noun}::{verb}::".encode("utf-8")
    preimage = prefix + canonical_json_bytes(payload)
    return hashlib.sha256(preimage).hexdigest()

class AEIBDisruptionAdapter:
    def __init__(self, tool_executor: Callable[[Dict[str, Any]], Any]):
        self.tool_executor = tool_executor
        self.executed_caids = set()

    def invoke_with_fault_tolerance(self, noun: str, verb: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        caid_key = derive_disrupt_caid(noun, verb, payload)
        
        if caid_key in self.executed_caids:
            return {"status": "DISPOSITION_SUPPRESSED", "disposition": "IDEMPOTENT_REPLAY", "caid": caid_key}

        try:
            result = self.tool_executor(payload)
            self.executed_caids.add(caid_key)
            return {"status": "OUTCOME_VERIFIED", "result": result, "caid": caid_key}
        except (TimeoutError, ConnectionError, OSError):
            # Fault injection trapped: DISPATCHED_UNCONFIRMED
            # Check state or quarantine
            return {"status": "DISPATCHED_UNCONFIRMED", "disposition": "QUARANTINED_FOR_OOB_PROBE", "caid": caid_key}

