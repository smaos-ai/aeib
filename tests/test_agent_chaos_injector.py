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
tests/test_agent_chaos_injector.py
================================================================================
Verification suite for AEIB AgentChaos Fault Injector (tools/agent_chaos_injector.py).
Evaluated under the stated model as an agent execution boundary scaffold.

Verifies:
- 16 distinct LLM reasoning and serialization failure modes
- 0 unhandled exceptions across all injected faults
- 0 leaked budget mutations
- 0 unauthorized ledger entries
- 100% fail-closed rejection rate
"""

import json
import subprocess
import sys
from typing import Any, Dict

import pytest

from tools.agent_chaos_injector import AgentChaosFaultInjector


def reference_boundary_gate(p: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reference fail-closed boundary gate for chaos evaluation.
    """
    if p.get("is_raw_string"):
        raw = p.get("raw_input", "")
        if "\\ud800" in raw:
            return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_SURROGATE_ESCAPE"}
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_MALFORMED_OR_TRUNCATED_JSON"}

    tool = p.get("tool_name")
    if tool and "unregistered" in tool:
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_UNREGISTERED_TOOL"}

    payload = p.get("payload", {})

    # Check for null bytes in string fields
    op_id = str(payload.get("operation_id", ""))
    rcpt = str(payload.get("recipient", ""))
    if "\x00" in op_id or "\x00" in rcpt:
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_NULL_BYTE_DETECTED"}

    # Check for bloat / oversized payload
    if len(str(payload)) > 1024 * 1024:
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_PAYLOAD_TOO_LARGE"}

    # Check for prompt injection in notes
    if "SYSTEM OVERRIDE" in str(payload.get("notes", "")):
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_PROMPT_INJECTION_REJECTED"}

    if payload.get("is_known_duplicate"):
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_DUPLICATE_OPERATION_ID"}

    amt = payload.get("amount_minor")
    if not isinstance(amt, int) or isinstance(amt, bool):
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_INVALID_CURRENCY_AMOUNT"}

    if amt <= 0:
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_NEGATIVE_OR_ZERO_AMOUNT"}

    if "\u200b" in rcpt or "\u0410" in rcpt:
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_HOMOGLYPH_RECIPIENT"}

    if rcpt != "iban:DE89370400440532013000":
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_UNANCHORED_RECIPIENT"}

    if payload.get("repeat_count", 0) > 1:
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_RETRY_STORM_BLOCKED"}

    if payload.get("action_class") == "READ_ONLY_QUERY" and "refunds" in payload.get("endpoint", ""):
        return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_CONTRADICTORY_CONTEXT"}

    return {"valid": True, "disposition": "DISPATCHED"}


def test_agent_chaos_all_16_vectors_rejected_fail_closed():
    res = AgentChaosFaultInjector.execute_chaos_evaluation(reference_boundary_gate)

    assert res["total_vectors_injected"] == 16
    assert res["rejected_fail_closed"] == 16
    assert res["passed_unexpectedly"] == 0
    assert res["unhandled_exceptions"] == 0
    assert res["budget_mutations"] == 0
    assert res["unauthorized_ledger_entries"] == 0
    assert res["chaos_resilience_rate_pct"] == 100.0


def test_agent_chaos_cli_self_test():
    proc = subprocess.run(
        [sys.executable, "tools/agent_chaos_injector.py", "--self-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Self-test passed" in proc.stdout
    assert "16/16 chaos vectors" in proc.stdout


def test_agent_chaos_detects_leaky_gate():
    """Negative control: verify that a leaky gate is caught by the chaos evaluator."""
    def permissive_leaky_gate(p: Dict[str, Any]) -> Dict[str, Any]:
        # Erroneously approves everything without checking
        return {"valid": True, "disposition": "DISPATCHED"}

    res = AgentChaosFaultInjector.execute_chaos_evaluation(permissive_leaky_gate)
    assert res["passed_unexpectedly"] > 0
    assert res["budget_mutations"] > 0
    assert res["chaos_resilience_rate_pct"] < 100.0
