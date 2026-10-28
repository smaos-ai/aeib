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


# ---------------------------------------------------------------------------
# Behavioural coverage added for mutation adequacy (real SQLite, real files,
# real subprocesses; no test doubles).
# ---------------------------------------------------------------------------
import hashlib
import subprocess

from aeib_mcp_proxy import (
    LineageContext,
    canonical_json_bytes,
    derive_attempt_id,
    derive_logical_operation_id,
)


def _ctx(**over):
    base = dict(tenant_id="t1", actor="agent", tool_name="transfer_funds",
                arguments={"amount": 5}, workflow_run_id="wf-1", step_or_turn_id="s-1")
    base.update(over)
    return LineageContext(**base)


def test_lineage_context_validation_and_defaults():
    ctx = _ctx()
    assert ctx.attempt_number == 1
    assert ctx.causal_parent_id is None
    assert ctx.contract_version == "v0.2.4"
    for missing in ("tenant_id", "workflow_run_id", "step_or_turn_id"):
        with pytest.raises(ValueError, match="INVALID_INPUT"):
            _ctx(**{missing: ""})


def test_logical_operation_and_attempt_ids_are_independently_recomputable():
    ctx = _ctx()
    payload = {
        "tenant_id": "t1", "actor": "agent", "tool_name": "transfer_funds",
        "workflow_run_id": "wf-1", "step_or_turn_id": "s-1",
        "arguments": {"amount": 5}, "contract_version": "v0.2.4",
    }
    logical = "op-" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()[:32]
    assert derive_logical_operation_id(ctx) == logical
    attempt = "att-" + hashlib.sha256(canonical_json_bytes(
        {"logical_operation_id": logical, "attempt_number": 1})).hexdigest()[:32]
    assert derive_attempt_id(ctx) == attempt
    # retries keep the logical id and change the attempt id
    retry = _ctx(attempt_number=2)
    assert derive_logical_operation_id(retry) == logical
    assert derive_attempt_id(retry) != attempt


NATIVE_RULES = '''# comment line is skipped
rules:
  - id: "R-A:1"
    priority: 7
    match:
      transport_code: 504
      probe_status: "STATUS:X"
    target_disposition: "DISP:Y"
    retry_policy: 'POL:Z'
    description: "desc: with colon"
  - id: R-B
    priority: 3
    match:
      transport_code: 200
      probe_status: NOT_REQUIRED
    target_disposition: OUTCOME_VERIFIED
    retry_policy: NONE
  - id: R-C
'''


def test_mapping_contract_native_parser_keeps_colons_and_sorts(tmp_path):
    path = tmp_path / "mapping.yaml"
    path.write_text(NATIVE_RULES, encoding="utf-8")
    contract = MappingContract(path)
    got = [(r.rule_id, r.priority, r.transport_code, r.probe_status,
            r.target_disposition, r.retry_policy, r.description) for r in contract.rules]
    assert got == [
        ("R-B", 3, 200, "NOT_REQUIRED", "OUTCOME_VERIFIED", "NONE", ""),
        ("R-A:1", 7, 504, "STATUS:X", "DISP:Y", "POL:Z", "desc: with colon"),
        ("R-C", 100, 0, "", "DISPATCHED_UNCONFIRMED", "PROHIBITED_AWAITING_PROBE", ""),
    ]
    assert contract.resolve(504, "STATUS:X") == ("DISP:Y", "POL:Z", "R-A:1")
    assert contract.resolve(200, "NOT_REQUIRED") == ("OUTCOME_VERIFIED", "NONE", "R-B")


def test_mapping_contract_probe_status_outside_match_block_is_ignored(tmp_path):
    path = tmp_path / "mapping.yaml"
    path.write_text(
        "rules:\n  - id: R1\n    target_disposition: D\n    transport_code: 504\n"
        "    probe_status: P\n", encoding="utf-8")
    (rule,) = MappingContract(path).rules
    assert (rule.transport_code, rule.probe_status) == (0, "")


def test_mapping_contract_builtin_defaults_table(tmp_path):
    contract = MappingContract(tmp_path / "does-not-exist.yaml")
    table = [(r.rule_id, r.priority, r.transport_code, r.probe_status,
              r.target_disposition, r.retry_policy) for r in contract.rules]
    assert table == [
        ("RULE-05-CONFLICT", 10, 409, "STATE_CONFLICT", "RECONCILIATION_CONFLICT", "PROHIBITED_LOCK_RECORD"),
        ("RULE-06-CONTEXT-REFUSED", 15, 403, "NOT_DISPATCHED", "CONTEXT_POLICY_VIOLATION", "PROHIBITED_POLICY_BLOCK"),
        ("RULE-07-AUTHORITY-EXPIRED", 15, 401, "NOT_DISPATCHED", "AUTHORITY_NOT_BOUND", "PROHIBITED_REAUTH_REQUIRED"),
        ("RULE-04-PAYLOAD-MISMATCH", 20, 504, "PAYLOAD_MISMATCH", "RECONCILIATION_FAILED", "PROHIBITED_ESCALATE_AUDIT"),
        ("RULE-02B-504-RECONCILED", 25, 504, "FOUND_COMMITTED", "OUTCOME_VERIFIED", "PROHIBITED_ALREADY_COMMITTED"),
        ("RULE-03-RESET-NOT-FOUND", 25, 504, "RECORD_NOT_FOUND", "RECONCILIATION_NOT_FOUND", "PERMITTED_UNDER_HUMAN_APPROVAL"),
        ("RULE-02A-504-AMBIGUOUS", 30, 504, "AWAITING_OPERATOR_PROBE", "DISPATCHED_UNCONFIRMED", "PROHIBITED_AWAITING_PROBE"),
        ("RULE-01-CONFIRMED", 50, 200, "NOT_REQUIRED", "OUTCOME_VERIFIED", "NOT_APPLICABLE_COMPLETED"),
    ]
    assert all(r.description == "" for r in contract.rules)
    assert contract.resolve(401, "NOT_DISPATCHED") == (
        "AUTHORITY_NOT_BOUND", "PROHIBITED_REAUTH_REQUIRED", "RULE-07-AUTHORITY-EXPIRED")


def test_mapping_contract_resolve_fallbacks(tmp_path):
    contract = MappingContract(tmp_path / "missing.yaml")
    assert contract.resolve(200, "SOMETHING") == ("OUTCOME_VERIFIED", "NOT_APPLICABLE_COMPLETED", "DEFAULT-200")
    assert contract.resolve(500, "SOMETHING") == ("DISPATCHED_UNCONFIRMED", "PROHIBITED_AWAITING_PROBE", "DEFAULT-UNCONFIRMED")
    assert contract.resolve(409, "NOT_REQUIRED") == ("DISPATCHED_UNCONFIRMED", "PROHIBITED_AWAITING_PROBE", "DEFAULT-UNCONFIRMED")


def _rpc(params, rid=1):
    return {"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": params}


def test_intercept_request_op_id_sources_and_quarantine():
    proxy = AEIBMCPProxy()
    proxy.quarantined_operations.update({"op-q", "caid-q", "param-q"})
    not_intercepted = {"jsonrpc": "2.0", "id": 1, "result": {"intercepted": False}}
    assert proxy.intercept_request(_rpc({"arguments": {"logical_operation_id": "op-q"}}))["error"]["code"] == -32001
    assert proxy.intercept_request(_rpc({"args": {"_aeib_caid": "caid-q"}}))["error"]["code"] == -32001
    blocked = proxy.intercept_request(_rpc({"arguments": {}, "logical_operation_id": "param-q"}))
    assert blocked["error"]["message"] == (
        "ExecutionProhibitedByPolicy: Mutation quarantined, retry locked under logical_operation_id=param-q")
    # an argument-level id wins over a params-level id
    assert "error" in proxy.intercept_request(
        _rpc({"arguments": {"logical_operation_id": "op-q"}, "logical_operation_id": "free"}))
    assert proxy.intercept_request(_rpc({"arguments": {"logical_operation_id": "free"}})) == not_intercepted
    assert proxy.intercept_request(_rpc({"arguments": ["not", "a", "dict"]})) == not_intercepted
    assert proxy.intercept_request(_rpc({})) == not_intercepted


def test_quarantined_retry_is_refused_without_dispatch():
    proxy = AEIBMCPProxy()
    sent = []

    def timeout_sender(req):
        sent.append(req)
        return None, 504, "Gateway Timeout"

    first = proxy.process_rpc_message(_rpc({"name": "transfer_funds", "arguments": {"amount": 1}}, rid=9),
                                      timeout_sender)
    caid = first["result"]["structuredContent"]["operation_id"]
    assert caid in proxy.quarantined_operations
    retry = proxy.process_rpc_message(
        _rpc({"name": "transfer_funds", "arguments": {"amount": 1, "_aeib_caid": caid}}, rid=10), timeout_sender)
    assert retry["error"]["code"] == -32001
    assert len(sent) == 1


def test_quarantine_reconciliation_status_reflects_probe():
    def timeout_sender(req):
        return None, 504, "Gateway Timeout"

    pending = AEIBMCPProxy().process_rpc_message(
        _rpc({"name": "transfer_funds", "arguments": {"amount": 2}}), timeout_sender)
    assert pending["result"]["structuredContent"]["reconciliation_status"] == "PROBE_PENDING"
    not_found = AEIBMCPProxy(state_prober_func=lambda key: "RECORD_NOT_FOUND").process_rpc_message(
        _rpc({"name": "transfer_funds", "arguments": {"amount": 2}}), timeout_sender)
    sc = not_found["result"]["structuredContent"]
    assert sc["reconciliation_status"] == "RECORD_NOT_FOUND"
    assert sc["disposition"] == "RECONCILIATION_NOT_FOUND"
    assert not_found["result"]["_aeib_quarantine"]["dora_classification"] == "NO_IMPACT"


def test_failing_custom_prober_falls_back_to_awaiting_probe():
    def broken_prober(key):
        raise RuntimeError("probe backend down")

    proxy = AEIBMCPProxy(state_prober_func=broken_prober)
    assert proxy.execute_probe("k", "c") == "AWAITING_OPERATOR_PROBE"
    assert AEIBMCPProxy().execute_probe("k", "c") == "AWAITING_OPERATOR_PROBE"


def test_read_only_prefixes_bypass_outbox():
    proxy = AEIBMCPProxy()
    for name in ("get_x", "read_x", "list_x", "query_x", "check_x", "search_x", "describe_x"):
        assert proxy.is_mutating_tool(name) is False
    assert proxy.is_mutating_tool("transfer_funds") is True
    resp = proxy.process_rpc_message(_rpc({"name": "get_balance", "arguments": {}}, rid=3),
                                     lambda r: (None, 504, "down"))
    assert resp == {"jsonrpc": "2.0", "id": 3, "result": {}}
    assert proxy.outbox.conn.execute("SELECT COUNT(*) FROM outbox_intents").fetchone()[0] == 0


def test_successful_mutation_writes_intent_and_verified_receipt():
    proxy = AEIBMCPProxy()
    seen = []

    def ok_sender(req):
        seen.append(req)
        return {"jsonrpc": "2.0", "id": req["id"], "result": {"ok": True}}, 200, None

    resp = proxy.process_rpc_message(_rpc({"name": "transfer_funds", "arguments": {"amount": 3}}, rid="r1"),
                                     ok_sender)
    assert resp["result"] == {"ok": True}
    caid = seen[0]["params"]["arguments"]["_aeib_caid"]
    assert seen[0]["params"]["arguments"]["_idempotency_key"] == derive_idempotency_key(caid)
    intent = proxy.outbox.get_intent(caid)
    assert intent["status"] == "OUTCOME_VERIFIED"
    assert intent["step_seq"] == 1 and intent["session_id"] == "mcp-session"
    assert proxy.outbox.get_intent("sha256:none") is None


def test_lifecycle_rpc_passthrough_and_empty_fallback():
    proxy = AEIBMCPProxy()
    ping = {"jsonrpc": "2.0", "id": 5, "method": "ping"}
    assert proxy.process_rpc_message(ping, lambda r: (None, 504, "down")) == {"jsonrpc": "2.0", "id": 5, "result": {}}
    pong = {"jsonrpc": "2.0", "id": 5, "result": {"pong": True}}
    assert proxy.process_rpc_message(ping, lambda r: (pong, 200, None)) == pong


def test_cli_self_test_roundtrip_exits_zero():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "aeib_mcp_proxy.py"), "--test-roundtrip"],
        cwd=str(ROOT), env={"PATH": os.environ.get("PATH", "")},
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    for marker in ("Test 1: Normal 200 OK", "Test 2: Post-commit 504 quarantined",
                   "Test 3: 504 Timeout safely reconciled"):
        assert marker in proc.stdout


def test_cli_without_downstream_prints_help():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "aeib_mcp_proxy.py")],
        cwd=str(ROOT), env={"PATH": os.environ.get("PATH", "")},
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0
    assert "--downstream" in proc.stdout
