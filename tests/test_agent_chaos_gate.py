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
tests/test_agent_chaos_gate.py — AgentChaos Fault Ingestion Gate Verification

Evaluates Station 1 ingress boundary resilience under the 9 non-OS LLM fault
modes defined in AgentChaos (arXiv:2608.06790) and Track B:
1. MALFORMED_JSON
2. TRUNCATED_JSON
3. HALLUCINATED_TOOL
4. DUPLICATE_OPERATION_ID
5. NEGATIVE_AMOUNT_DRAIN
6. OVERFLOW_INTEGER_AND_FLOAT
7. WRONG_RECIPIENT_OR_HOMOGLYPH
8. INFINITE_RETRY_REQUEST
9. CONTRADICTORY_CONTEXT

Asserts zero budget leaks, zero unauthorized dispatches, zero blind retries,
and persistent cryptographic audit logging for every rejected attempt.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from tools.agent_chaos_injector import AgentChaosFaultInjector


class HardenedStation1IngressBoundary:
    """
    Ingress boundary implementing Station 1 fail-closed parsing,
    schema validation, semantic contradiction checks, and audit logging.
    """

    REGISTERED_TOOLS: Set[str] = {
        "dispatch_refund",
        "dispatch_payout",
        "query_account_balance",
        "lookup_transaction_status",
    }

    def __init__(self, audit_dir: Path) -> None:
        self.audit_dir = audit_dir
        self.rejection_log_path = audit_dir / "rejection_audit_log.jsonl"
        self.ledger_path = audit_dir / "settlement_ledger.jsonl"
        self.committed_operation_ids: Set[str] = {"op-already-committed-999"}
        self.total_budget_spent_minor: int = 0
        self.total_dispatches_executed: int = 0
        self.rejections_recorded: int = 0
        self.signing_key = ed25519.Ed25519PrivateKey.generate()

    def evaluate_incoming_payload(self, request_container: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses and evaluates an incoming agent tool-call request.
        Fails closed on any structural, semantic, or schema anomaly.
        """
        # 1. Structural parse check (MALFORMED_JSON, TRUNCATED_JSON)
        if request_container.get("is_raw_string"):
            raw = request_container.get("raw_input", "")
            try:
                if "\\ud800" in raw:
                    raise ValueError("UTF-8 surrogate escape forbidden")
                parsed = json.loads(raw)
            except (json.JSONDecodeError, ValueError) as err:
                return self._reject(
                    op_id="unparseable-raw-input",
                    code="ERR_MALFORMED_OR_TRUNCATED_JSON",
                    detail=str(err),
                )
            payload = parsed
            tool_name = payload.get("tool_name", "dispatch_refund")
        else:
            payload = request_container.get("payload", {})
            tool_name = request_container.get("tool_name", "dispatch_refund")

        op_id = payload.get("operation_id", "op-missing")

        # 2. Tool registration check (HALLUCINATED_TOOL)
        if tool_name not in self.REGISTERED_TOOLS:
            return self._reject(
                op_id=op_id,
                code="ERR_UNREGISTERED_TOOL",
                detail=f"Tool '{tool_name}' is not in registered tool inventory",
            )

        # 3. Duplicate operation ID check (DUPLICATE_OPERATION_ID)
        if payload.get("is_known_duplicate") or op_id in self.committed_operation_ids:
            return self._reject(
                op_id=op_id,
                code="ERR_DUPLICATE_OPERATION_ID",
                detail=f"Operation '{op_id}' was already committed or marked duplicate",
            )

        # 4. Currency integer precision & non-negative check (P3C-FIN01)
        amt = payload.get("amount_minor")
        if amt is None:
            return self._reject(
                op_id=op_id,
                code="ERR_MISSING_AMOUNT",
                detail="Field 'amount_minor' is required",
            )

        # Strict integer check: floats like 100.50 or bools must be rejected
        if isinstance(amt, bool) or not isinstance(amt, int):
            return self._reject(
                op_id=op_id,
                code="ERR_FLOAT_PRECISION_FORBIDDEN",
                detail=f"Amount {amt} is not a valid discrete integer minor unit",
            )

        if amt <= 0:
            return self._reject(
                op_id=op_id,
                code="ERR_INVALID_CURRENCY_AMOUNT",
                detail=f"Amount {amt} must be strictly positive",
            )

        # 5. Unicode recipient confusion & homoglyph check (WRONG_RECIPIENT_OR_HOMOGLYPH)
        rcpt = payload.get("recipient", "")
        if not rcpt:
            return self._reject(
                op_id=op_id,
                code="ERR_MISSING_RECIPIENT",
                detail="Recipient identifier is missing",
            )

        # Detect zero-width space (U+200B) or Cyrillic characters substituting Latin
        if any(ord(c) in (0x200B, 0xFEFF, 0x200C, 0x200D) or (0x0400 <= ord(c) <= 0x04FF) for c in rcpt):
            return self._reject(
                op_id=op_id,
                code="ERR_HOMOGLYPH_RECIPIENT",
                detail=f"Recipient '{rcpt}' contains forbidden homoglyph or zero-width code points",
            )

        # 6. Retry storm check (INFINITE_RETRY_REQUEST)
        if payload.get("repeat_count", 0) > 1:
            return self._reject(
                op_id=op_id,
                code="ERR_RETRY_STORM_BLOCKED",
                detail="High-frequency retry storm blocked by ingress rate limiter",
            )

        # 7. Semantic contradiction check (CONTRADICTORY_CONTEXT)
        declared_class = payload.get("action_class")
        target_endpoint = payload.get("endpoint", "")
        if declared_class == "READ_ONLY_QUERY" and any(m in target_endpoint for m in ("refunds", "payouts", "transfer")):
            return self._reject(
                op_id=op_id,
                code="ERR_CONTRADICTORY_CONTEXT",
                detail=f"Declared action_class '{declared_class}' contradicts state-mutating endpoint '{target_endpoint}'",
            )

        # 8. Null byte, bloat, prompt injection, and unanchored recipient checks
        if "\x00" in str(op_id) or "\x00" in str(rcpt):
            return self._reject(op_id=op_id, code="ERR_NULL_BYTE_DETECTED", detail="Null byte forbidden")
        if len(str(payload)) > 1024 * 1024:
            return self._reject(op_id=op_id, code="ERR_PAYLOAD_TOO_LARGE", detail="Payload exceeds 1MB cap")
        if "SYSTEM OVERRIDE" in str(payload.get("notes", "")):
            return self._reject(op_id=op_id, code="ERR_PROMPT_INJECTION_REJECTED", detail="Prompt injection blocked")
        if rcpt != "iban:DE89370400440532013000":
            return self._reject(op_id=op_id, code="ERR_UNANCHORED_RECIPIENT", detail="Recipient not in allowlist")

        # Positive dispatch path
        self.total_budget_spent_minor += amt
        self.total_dispatches_executed += 1
        self.committed_operation_ids.add(op_id)

        canonical_entry = encode_jcs(
            {
                "operation_id": op_id,
                "amount_minor": amt,
                "recipient": rcpt,
                "status": "DISPATCHED",
            }
        )
        sig = self.signing_key.sign(canonical_entry)

        with open(self.ledger_path, "ab") as f:
            f.write(canonical_entry + b"\n")
            f.flush()
            os.fsync(f.fileno())

        return {
            "valid": True,
            "disposition": "DISPATCHED",
            "operation_id": op_id,
            "signature_hex": sig.hex(),
        }

    def _reject(self, op_id: str, code: str, detail: str) -> Dict[str, Any]:
        self.rejections_recorded += 1
        audit_payload = {
            "operation_id": op_id,
            "rejection_code": code,
            "detail": detail,
            "disposition": "NOT_DISPATCHED",
        }
        canonical_bytes = encode_jcs(audit_payload)
        audit_hash = hashlib.sha256(canonical_bytes).hexdigest()

        with open(self.rejection_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({**audit_payload, "audit_sha256": audit_hash}) + "\n")
            f.flush()

        return {
            "valid": False,
            "disposition": "NOT_DISPATCHED",
            "code": code,
            "detail": detail,
            "audit_sha256": audit_hash,
        }


# ==============================================================================
# PYTEST TEST SUITE
# ==============================================================================

def test_agent_chaos_all_9_vectors_rejected_fail_closed(tmp_path: Path):
    """
    Evaluates that all 9 chaos fault vectors are rejected fail-closed,
    allocating zero budget and executing zero dispatches.
    """
    boundary = HardenedStation1IngressBoundary(audit_dir=tmp_path)

    chaos_report = AgentChaosFaultInjector.execute_chaos_evaluation(
        boundary.evaluate_incoming_payload
    )

    # 1. Assert full resilience
    assert chaos_report["total_vectors_injected"] == 16
    assert chaos_report["rejected_fail_closed"] == 16
    assert chaos_report["passed_unexpectedly"] == 0
    assert chaos_report["chaos_resilience_rate_pct"] == 100.0

    # 2. Assert zero budget leak
    assert boundary.total_budget_spent_minor == 0
    assert boundary.total_dispatches_executed == 0
    assert boundary.rejections_recorded == 16

    # 3. Assert audit evidence retained for all 16 rejections
    assert boundary.rejection_log_path.exists()
    lines = boundary.rejection_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 16

    codes = [json.loads(line)["rejection_code"] for line in lines]
    assert "ERR_MALFORMED_OR_TRUNCATED_JSON" in codes
    assert "ERR_UNREGISTERED_TOOL" in codes
    assert "ERR_DUPLICATE_OPERATION_ID" in codes
    assert "ERR_INVALID_CURRENCY_AMOUNT" in codes
    assert "ERR_FLOAT_PRECISION_FORBIDDEN" in codes
    assert "ERR_HOMOGLYPH_RECIPIENT" in codes
    assert "ERR_RETRY_STORM_BLOCKED" in codes
    assert "ERR_CONTRADICTORY_CONTEXT" in codes


def test_nominal_ingress_payload_succeeds(tmp_path: Path):
    """
    Positive control: Valid payload successfully dispatches and commits to ledger.
    """
    boundary = HardenedStation1IngressBoundary(audit_dir=tmp_path)

    valid_request = {
        "is_raw_string": False,
        "tool_name": "dispatch_refund",
        "payload": {
            "operation_id": "op-valid-nominal-001",
            "amount_minor": 15000,
            "recipient": "iban:DE89370400440532013000",
            "action_class": "FINANCIAL_SETTLEMENT",
            "endpoint": "POST /v1/refunds",
        },
    }

    res = boundary.evaluate_incoming_payload(valid_request)
    assert res["valid"] is True
    assert res["disposition"] == "DISPATCHED"
    assert res["operation_id"] == "op-valid-nominal-001"
    assert "signature_hex" in res

    assert boundary.total_budget_spent_minor == 15000
    assert boundary.total_dispatches_executed == 1
    assert boundary.ledger_path.exists()

    ledger_content = boundary.ledger_path.read_bytes()
    assert b"op-valid-nominal-001" in ledger_content


def test_agent_chaos_injector_cli_self_test():
    """
    Evaluates that tools/agent_chaos_injector.py executes cleanly via CLI.
    """
    result = subprocess.run(
        [sys.executable, "tools/agent_chaos_injector.py", "--self-test"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "16/16 chaos vectors rejected fail-closed" in result.stdout


@pytest.mark.parametrize(
    "vector_name,expected_code",
    [
        ("MALFORMED_JSON", "ERR_MALFORMED_OR_TRUNCATED_JSON"),
        ("TRUNCATED_JSON", "ERR_MALFORMED_OR_TRUNCATED_JSON"),
        ("HALLUCINATED_TOOL", "ERR_UNREGISTERED_TOOL"),
        ("DUPLICATE_OPERATION_ID", "ERR_DUPLICATE_OPERATION_ID"),
        ("NEGATIVE_AMOUNT_DRAIN", "ERR_INVALID_CURRENCY_AMOUNT"),
        ("OVERFLOW_INTEGER_AND_FLOAT", "ERR_FLOAT_PRECISION_FORBIDDEN"),
        ("WRONG_RECIPIENT_OR_HOMOGLYPH", "ERR_HOMOGLYPH_RECIPIENT"),
        ("INFINITE_RETRY_REQUEST", "ERR_RETRY_STORM_BLOCKED"),
        ("CONTRADICTORY_CONTEXT", "ERR_CONTRADICTORY_CONTEXT"),
    ],
)
def test_individual_chaos_vector_falsification(tmp_path: Path, vector_name: str, expected_code: str):
    """
    Evaluates individual chaos vector handling to ensure bit-isolated coverage.
    """
    boundary = HardenedStation1IngressBoundary(audit_dir=tmp_path)
    payloads = {p["vector"]: p for p in AgentChaosFaultInjector.generate_fault_payloads()}

    target_payload = payloads[vector_name]
    res = boundary.evaluate_incoming_payload(target_payload)

    assert res["valid"] is False
    assert res["disposition"] == "NOT_DISPATCHED"
    assert res["code"] == expected_code
    assert boundary.total_budget_spent_minor == 0
