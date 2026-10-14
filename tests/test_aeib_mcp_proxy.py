#!/usr/bin/env python3
"""
tests/test_aeib_mcp_proxy.py
Comprehensive unit tests for aeib_mcp_proxy.py
Adheres strictly to the Zero-Mock Architectural Invariant (AEIB v0.2.4).
"""

import os
import ast
import json
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aeib_mcp_proxy import (
    derive_caid,
    derive_idempotency_key,
    MappingContract,
    OutboxLedger,
    AEIBMCPProxy
)


def test_zero_mock_ast_purity():
    """Verify that aeib_mcp_proxy.py does not import unittest.mock or MagicMock."""
    proxy_path = ROOT / "aeib_mcp_proxy.py"
    tree = ast.parse(proxy_path.read_text(encoding="utf-8"))
    banned = {"mock", "unittest.mock", "MagicMock"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in banned, f"Banned import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in banned, f"Banned module: {node.module}"


def test_caid_derivation_deterministic():
    args1 = {"amount": 100, "currency": "EUR", "recipient": "IBAN123"}
    args2 = {"recipient": "IBAN123", "amount": 100, "currency": "EUR"}
    caid1 = derive_caid("sess_1", 1, "rpc_99", "transfer", args1)
    caid2 = derive_caid("sess_1", 1, "rpc_99", "transfer", args2)
    assert caid1 == caid2, "Canonicalization must yield identical CAID regardless of key order"

    key1 = derive_idempotency_key(caid1)
    key2 = derive_idempotency_key(caid2)
    assert key1 == key2
    assert key1.startswith(key1[:8])


def test_mapping_contract_resolution():
    contract = MappingContract(ROOT / "transport-to-disposition-mapping.yaml")

    # 504 + FOUND_COMMITTED -> OUTCOME_VERIFIED
    disp, pol, rid = contract.resolve(504, "FOUND_COMMITTED")
    assert disp == "OUTCOME_VERIFIED"
    assert pol == "PROHIBITED_ALREADY_COMMITTED"

    # 504 + RECORD_NOT_FOUND -> RECONCILIATION_NOT_FOUND
    disp, pol, rid = contract.resolve(504, "RECORD_NOT_FOUND")
    assert disp == "RECONCILIATION_NOT_FOUND"
    assert pol == "PERMITTED_UNDER_HUMAN_APPROVAL"

    # 504 + AWAITING_OPERATOR_PROBE -> DISPATCHED_UNCONFIRMED
    disp, pol, rid = contract.resolve(504, "AWAITING_OPERATOR_PROBE")
    assert disp == "DISPATCHED_UNCONFIRMED"
    assert pol == "PROHIBITED_AWAITING_PROBE"

    # 409 + STATE_CONFLICT -> RECONCILIATION_CONFLICT
    disp, pol, rid = contract.resolve(409, "STATE_CONFLICT")
    assert disp == "RECONCILIATION_CONFLICT"
    assert pol == "PROHIBITED_LOCK_RECORD"


def test_outbox_ledger_real_sqlite():
    ledger = OutboxLedger(":memory:")
    caid = "sha256:abcd1234ef5678"
    ledger.record_intent(
        caid=caid,
        idempotency_key="uuid-test-1",
        session_id="session-x",
        step_seq=1,
        rpc_id="rpc-1",
        tool_name="debit_account",
        payload_digest="digest-123"
    )
    intent = ledger.get_intent(caid)
    assert intent is not None
    assert intent["status"] == "DISPATCHED"
    assert intent["tool_name"] == "debit_account"

    ledger.record_receipt(
        caid=caid,
        disposition="OUTCOME_VERIFIED",
        retry_policy="NOT_APPLICABLE_COMPLETED",
        wire_status=200,
        probe_status="NOT_REQUIRED",
        receipt_payload={"verified": True}
    )
    updated = ledger.get_intent(caid)
    assert updated["status"] == "OUTCOME_VERIFIED"


def test_mcp_proxy_normal_dispatch():
    proxy = AEIBMCPProxy(mapping_path=ROOT / "transport-to-disposition-mapping.yaml")

    def mockless_sender(req):
        return {"jsonrpc": "2.0", "id": req["id"], "result": {"balance": 1500}}, 200, None

    req = {
        "jsonrpc": "2.0",
        "id": "rpc-101",
        "method": "tools/call",
        "params": {"name": "transfer_funds", "arguments": {"amount": 200}}
    }
    resp = proxy.process_rpc_message(req, mockless_sender)
    assert "result" in resp
    assert resp["result"]["balance"] == 1500


def test_mcp_proxy_504_quarantine():
    proxy = AEIBMCPProxy(mapping_path=ROOT / "transport-to-disposition-mapping.yaml")

    def failing_sender(req):
        return None, 504, "Gateway Timeout"

    req = {
        "jsonrpc": "2.0",
        "id": 42,
        "method": "tools/call",
        "params": {"name": "transfer_funds", "arguments": {"amount": 999}}
    }
    resp = proxy.process_rpc_message(req, failing_sender)
    assert "result" in resp
    res = resp["result"]
    assert res["isError"] is False
    assert "STATUS: DISPATCHED_UNCONFIRMED" in res["content"][0]["text"]
    assert "retry frozen" in res["content"][0]["text"]
    quar = res["_aeib_quarantine"]
    assert quar["disposition"] == "DISPATCHED_UNCONFIRMED"
    assert quar["retry_policy"] == "PROHIBITED_AWAITING_PROBE"
    assert quar["dora_classification"] == "MAJOR_ICT_INCIDENT_CANDIDATE"


def test_noun_verb_caid_derivation():
    from aeib_mcp_proxy import derive_noun_verb_caid
    noun_id = "acc_debit_primary"
    verb_action = "DEBIT"
    payload1 = {"amount": 500, "currency": "EUR", "beneficiary": "DE89370400440532013000"}
    payload2 = {"currency": "EUR", "beneficiary": "DE89370400440532013000", "amount": 500}

    caid1 = derive_noun_verb_caid(noun_id, verb_action, payload1)
    caid2 = derive_noun_verb_caid(noun_id, verb_action, payload2)

    # Invariant: canonicalization ensures key order independence
    assert caid1 == caid2
    assert caid1.startswith("sha256:")

    # Invariant: different verb produces different CAID
    caid_credit = derive_noun_verb_caid(noun_id, "CREDIT", payload1)
    assert caid_credit != caid1
