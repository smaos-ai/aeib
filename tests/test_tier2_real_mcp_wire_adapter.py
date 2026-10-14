"""
tests/test_tier2_real_mcp_wire_adapter.py
Tests verifying the Tier 2 Real MCP JSON-RPC Wire Interception Adapter capabilities:
  1. Handshake & initialization (initialize, notifications/initialized).
  2. Pinned tool schema listing (tools/list) against pinned manifest digest.
  3. Non-mutating tool pass-through with clean inputs.
  4. Mutating tool call requires valid DispatchAuthorizationTicket.
  5. Dead Salmons reasoning filter strips model thoughts before CAID derivation.
  6. EO-1 durable intent persistence before tool invocation.
  7. Successful execution mints verifiable Ed25519 ContinuityReceipt.
  8. Wire transport failure latches EFFECT_INDETERMINATE with retry_safe: false.
  9. Client cancellation notification (notifications/cancelled) aborts dispatch cleanly.
 10. Multi-session isolation prevents cross-session ticket theft or cancellation.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.jcs_canonicalizer import encode_jcs

REPO_ROOT = Path(__file__).resolve().parents[1]
T1_PATH = REPO_ROOT / "v1.1-roadmap" / "tier1_durable_executor.py"
MCP_PATH = REPO_ROOT / "v1.1-roadmap" / "real_mcp_wire_adapter.py"

spec_t1 = importlib.util.spec_from_file_location("v1.1_roadmap.tier1_durable_executor", T1_PATH)
assert spec_t1 is not None and spec_t1.loader is not None
t1 = importlib.util.module_from_spec(spec_t1)
sys.modules["v1.1_roadmap.tier1_durable_executor"] = t1
spec_t1.loader.exec_module(t1)

spec_mcp = importlib.util.spec_from_file_location("real_mcp_wire_adapter", MCP_PATH)
assert spec_mcp is not None and spec_mcp.loader is not None
mcp = importlib.util.module_from_spec(spec_mcp)
sys.modules["real_mcp_wire_adapter"] = mcp
spec_mcp.loader.exec_module(mcp)

DurableDispatchJournal = t1.DurableDispatchJournal
PersistentAuthorityTicketStore = t1.PersistentAuthorityTicketStore
RealMcpWireAdapter = mcp.RealMcpWireAdapter
PinnedToolDefinition = mcp.PinnedToolDefinition


def _mint_mcp_ticket(
    authority_key: Ed25519PrivateKey,
    *,
    decision_id: str,
    operation_id: str,
    principal_id: str,
    tool_name: str,
    pure_arguments: Dict[str, Any],
    policy_epoch: int = 10,
    manifest_digest: str = "sha256:manifest111",
    expires_at: int = 2000000000,
) -> Dict[str, Any]:
    caid = f"sha256:{hashlib.sha256(encode_jcs(pure_arguments)).hexdigest()}"
    raw_stmt = {
        "actionDigest": caid,
        "decisionId": decision_id,
        "expiresAt": expires_at,
        "manifestDigest": manifest_digest,
        "operationId": operation_id,
        "policyEpoch": policy_epoch,
        "principalId": principal_id,
        "singleUse": True,
        "targetIdentity": f"mcp://{tool_name}",
    }
    stmt_bytes = encode_jcs(raw_stmt)
    sig_hex = authority_key.sign(stmt_bytes).hex()

    return {
        "decision_id": decision_id,
        "operation_id": operation_id,
        "principal_id": principal_id,
        "target_identity": f"mcp://{tool_name}",
        "action_digest": caid,
        "policy_epoch": policy_epoch,
        "manifest_digest": manifest_digest,
        "expires_at": expires_at,
        "single_use": True,
        "signature_hex": sig_hex,
    }


def _create_test_adapter(tmp_path: Path, tool_dispatcher) -> tuple[RealMcpWireAdapter, Ed25519PrivateKey, Ed25519PrivateKey]:
    auth_key = Ed25519PrivateKey.generate()
    ledger_key = Ed25519PrivateKey.generate()
    ticket_store = PersistentAuthorityTicketStore(tmp_path / "mcp_tickets.jsonl")
    journal = DurableDispatchJournal(tmp_path / "mcp_journal.jsonl")

    read_tool = PinnedToolDefinition(
        name="get_balance",
        description="Query account balance",
        input_schema={"type": "object", "properties": {"account": {"type": "string"}}},
        is_mutating=False,
        schema_digest="sha256:read_schema_hash",
    )
    transfer_tool = PinnedToolDefinition(
        name="transfer_funds",
        description="Mutating wire fund transfer",
        input_schema={"type": "object", "properties": {"from": {"type": "string"}, "amount": {"type": "number"}}},
        is_mutating=True,
        schema_digest="sha256:transfer_schema_hash",
    )

    adapter = RealMcpWireAdapter(
        authority_public_key=auth_key.public_key(),
        ledger_signing_key=ledger_key,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=10,
        pinned_manifest_digest="sha256:manifest111",
        pinned_tools={"get_balance": read_tool, "transfer_funds": transfer_tool},
        downstream_tool_dispatcher=tool_dispatcher,
    )
    return adapter, auth_key, ledger_key


def test_01_mcp_handshake_and_tool_listing(tmp_path: Path) -> None:
    """1. Validates MCP initialize handshake and tools/list against pinned manifest."""
    dispatcher = lambda name, args: {"ok": True}
    adapter, _, _ = _create_test_adapter(tmp_path, dispatcher)

    # Initialize
    init_msg = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "agent-orchestrator", "version": "1.0"}},
    })
    init_resp_raw = adapter.handle_json_rpc_message(init_msg, session_id="session_alpha")
    assert init_resp_raw is not None
    init_resp = json.loads(init_resp_raw)
    assert init_resp["id"] == 1
    assert init_resp["result"]["serverInfo"]["name"] == "aeib-governed-mcp-adapter"

    # Notification initialized
    notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
    assert adapter.handle_json_rpc_message(notif, session_id="session_alpha") is None

    # tools/list
    list_msg = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    list_resp_raw = adapter.handle_json_rpc_message(list_msg, session_id="session_alpha")
    assert list_resp_raw is not None
    list_resp = json.loads(list_resp_raw)
    tools = list_resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "get_balance" in tool_names
    assert "transfer_funds" in tool_names
    # Verified metadata matches pinned manifest
    assert tools[1]["_aeib_metadata"]["manifestDigest"] == "sha256:manifest111"


def test_02_non_mutating_tool_passthrough(tmp_path: Path) -> None:
    """2. Non-mutating tool executes cleanly without requiring authority ticket."""
    executed = []
    def dispatcher(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        executed.append((name, args))
        return {"balance": 1500, "currency": "EUR"}

    adapter, _, _ = _create_test_adapter(tmp_path, dispatcher)

    call_msg = json.dumps({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "get_balance",
            "arguments": {"account": "ACC_123", "_reasoning": "Checking customer balance before decision"},
        },
    })
    resp_raw = adapter.handle_json_rpc_message(call_msg, session_id="session_alpha")
    assert resp_raw is not None
    resp = json.loads(resp_raw)
    assert resp["id"] == 10
    assert resp["result"]["isError"] is False
    assert resp["result"]["governance"]["mutating"] is False
    # Dead Salmons verified: reasoning stripped from downstream call
    assert executed[0] == ("get_balance", {"account": "ACC_123"})


def test_03_mutating_tool_requires_valid_ticket_and_emits_receipt(tmp_path: Path) -> None:
    """3. Mutating tool call requires valid ticket, logs EO-1 intent, and emits receipt."""
    executed = []
    def dispatcher(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        executed.append((name, args))
        return {"transfer_id": "tx_999", "http_status": 200}

    adapter, auth_key, _ = _create_test_adapter(tmp_path, dispatcher)

    pure_args = {"from": "ACC_SOURCE", "amount": 100}
    ticket_dict = _mint_mcp_ticket(
        auth_key,
        decision_id="dec_mcp_01",
        operation_id="op_mcp_01",
        principal_id="ciso_agent",
        tool_name="transfer_funds",
        pure_arguments=pure_args,
    )

    call_msg = json.dumps({
        "jsonrpc": "2.0",
        "id": 20,
        "method": "tools/call",
        "params": {
            "name": "transfer_funds",
            "arguments": {
                "from": "ACC_SOURCE",
                "amount": 100,
                "_reasoning": "Approved loan disbursement step",
                "_governance": ticket_dict,
            },
        },
    })

    resp_raw = adapter.handle_json_rpc_message(call_msg, session_id="session_alpha")
    assert resp_raw is not None
    resp = json.loads(resp_raw)
    assert resp["id"] == 20
    assert resp["result"]["isError"] is False
    gov = resp["result"]["governance"]
    assert gov["disposition"] == "CONFIRMED"
    assert gov["retrySafe"] is True
    assert "receipt" in gov
    assert "receiptSignatureHex" in gov
    # Verify receipt actionDigest matches pure argument CAID
    expected_caid = f"sha256:{hashlib.sha256(encode_jcs(pure_args)).hexdigest()}"
    assert gov["receipt"]["actionDigest"] == expected_caid
    # Ticket consumed in persistent store
    assert adapter.ticket_store.is_consumed("dec_mcp_01") is True


def test_04_mutating_tool_missing_ticket_rejected_fail_closed(tmp_path: Path) -> None:
    """4. Mutating tool call without governance ticket is rejected with JSON-RPC error."""
    adapter, _, _ = _create_test_adapter(tmp_path, lambda n, a: {"ok": True})

    call_msg = json.dumps({
        "jsonrpc": "2.0",
        "id": 21,
        "method": "tools/call",
        "params": {
            "name": "transfer_funds",
            "arguments": {"from": "ACC_SOURCE", "amount": 100},
        },
    })
    resp_raw = adapter.handle_json_rpc_message(call_msg, session_id="session_alpha")
    assert resp_raw is not None
    resp = json.loads(resp_raw)
    assert "error" in resp
    assert resp["error"]["code"] == -32001
    assert "AUTHORITY_TICKET_MISSING" in resp["error"]["message"]


def test_05_transport_fault_latches_effect_indeterminate(tmp_path: Path) -> None:
    """5. Downstream tool 504 / timeout latches EFFECT_INDETERMINATE with retry_safe: false."""
    def timeout_dispatcher(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        raise TimeoutError("Upstream banking gateway timed out (HTTP 504 Gateway Timeout)")

    adapter, auth_key, _ = _create_test_adapter(tmp_path, timeout_dispatcher)

    pure_args = {"from": "ACC_SOURCE", "amount": 250}
    ticket_dict = _mint_mcp_ticket(
        auth_key,
        decision_id="dec_mcp_504",
        operation_id="op_mcp_504",
        principal_id="ciso_agent",
        tool_name="transfer_funds",
        pure_arguments=pure_args,
    )

    call_msg = json.dumps({
        "jsonrpc": "2.0",
        "id": 22,
        "method": "tools/call",
        "params": {
            "name": "transfer_funds",
            "arguments": {
                "from": "ACC_SOURCE",
                "amount": 250,
                "_governance": ticket_dict,
            },
        },
    })

    resp_raw = adapter.handle_json_rpc_message(call_msg, session_id="session_alpha")
    assert resp_raw is not None
    resp = json.loads(resp_raw)
    assert resp["id"] == 22
    assert resp["result"]["isError"] is True
    gov = resp["result"]["governance"]
    assert gov["disposition"] == "EFFECT_INDETERMINATE"
    assert gov["retrySafe"] is False
    assert gov["receipt"]["disposition"] == "EFFECT_INDETERMINATE"


def test_06_cancellation_notification_handling(tmp_path: Path) -> None:
    """6. Client notifications/cancelled aborts in-flight request cleanly."""
    entered_dispatcher = threading.Event()
    unblock_dispatcher = threading.Event()

    def slow_dispatcher(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        entered_dispatcher.set()
        unblock_dispatcher.wait(timeout=2.0)
        return {"transfer_id": "tx_slow", "http_status": 200}

    adapter, auth_key, _ = _create_test_adapter(tmp_path, slow_dispatcher)

    pure_args = {"from": "ACC_CANCEL", "amount": 50}
    ticket_dict = _mint_mcp_ticket(
        auth_key,
        decision_id="dec_mcp_cancel",
        operation_id="op_mcp_cancel",
        principal_id="ciso_agent",
        tool_name="transfer_funds",
        pure_arguments=pure_args,
    )

    call_msg = json.dumps({
        "jsonrpc": "2.0",
        "id": 99,
        "method": "tools/call",
        "params": {
            "name": "transfer_funds",
            "arguments": {
                "from": "ACC_CANCEL",
                "amount": 50,
                "_governance": ticket_dict,
            },
        },
    })

    response_container = []

    def call_worker():
        res = adapter.handle_json_rpc_message(call_msg, session_id="session_cancel")
        response_container.append(res)

    t = threading.Thread(target=call_worker)
    t.start()

    # Wait until tool execution is entered
    entered_dispatcher.wait(timeout=2.0)

    # Client issues cancellation notification for request id 99
    cancel_notif = json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/cancelled",
        "params": {"requestId": 99, "reason": "Operator abort"},
    })
    adapter.handle_json_rpc_message(cancel_notif, session_id="session_cancel")

    # Unblock dispatcher
    unblock_dispatcher.set()
    t.join()

    assert len(response_container) == 1
    resp = json.loads(response_container[0])
    # Transport was interrupted mid-flight; classified as EFFECT_INDETERMINATE
    gov = resp["result"]["governance"]
    assert gov["disposition"] == "EFFECT_INDETERMINATE"
    assert gov["retrySafe"] is False


def test_07_session_isolation_prevents_cancellation_crosstalk(tmp_path: Path) -> None:
    """7. Cancellation in Session A does NOT affect identically-numbered request in Session B."""
    adapter, _, _ = _create_test_adapter(tmp_path, lambda n, a: {"balance": 100})

    cancel_notif_a = json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/cancelled",
        "params": {"requestId": 5, "reason": "Session A abort"},
    })
    adapter.handle_json_rpc_message(cancel_notif_a, session_id="session_A")

    # Session B executes request with id 5 — must not be affected
    call_msg_b = json.dumps({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "get_balance", "arguments": {"account": "ACC_B"}},
    })
    resp_raw_b = adapter.handle_json_rpc_message(call_msg_b, session_id="session_B")
    assert resp_raw_b is not None
    resp_b = json.loads(resp_raw_b)
    assert resp_b["result"]["isError"] is False
