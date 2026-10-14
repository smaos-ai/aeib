"""
v1.1-roadmap/real_mcp_wire_adapter.py — Real MCP JSON-RPC Wire Interception Adapter Prototype.
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Boundary (AEIB).

Tier 2 Core Delivery Contract:
Operates as a wire-level Model Context Protocol (MCP) proxy between autonomous agent clients
and downstream tool servers:
  1. JSON-RPC 2.0 protocol handling over streaming or in-memory transport.
  2. Protocol handshake negotiation (initialize, notifications/initialized).
  3. Pinned tool schema validation (tools/list) against pinned manifest digest.
  4. Stateful 'tools/call' governance:
     - Dead Salmons filter stripping ephemeral reasoning tokens.
     - RFC 8785 JCS CAID computation.
     - Decision-to-dispatch authority ticket evaluation and persistent burn.
     - Pre-dispatch durable intent commitment (EO-1) with fsync acknowledgement.
     - Transport fault latching (HTTP 504 / timeout / socket drops -> EFFECT_INDETERMINATE, retry_safe: false).
     - Cancellation handling (notifications/cancelled) with clean session state tracking.
     - Station 3 Ed25519 ContinuityReceipt minting.
  5. Per-session isolation prohibiting cross-session ticket theft or cancellation crosstalk.

Operates under the stated model: Prohibits unverified tool execution and transport ambiguity leaks.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs
import importlib.util
import sys

_t1_path = Path(__file__).resolve().parent / "tier1_durable_executor.py"
_spec_t1 = importlib.util.spec_from_file_location("tier1_durable_executor", _t1_path)
if _spec_t1 is None or _spec_t1.loader is None:
    raise ImportError(f"Cannot load tier1_durable_executor from {_t1_path}")
_t1_mod = importlib.util.module_from_spec(_spec_t1)
sys.modules["tier1_durable_executor"] = _t1_mod
_spec_t1.loader.exec_module(_t1_mod)

DispatchAuthorityTicket = _t1_mod.DispatchAuthorityTicket
DurableDispatchJournal = _t1_mod.DurableDispatchJournal
GovernanceHaltError = _t1_mod.GovernanceHaltError
PersistentAuthorityTicketStore = _t1_mod.PersistentAuthorityTicketStore
Tier1DurableDispatchExecutor = _t1_mod.Tier1DurableDispatchExecutor



class McpProtocolError(Exception):
    """Raised on invalid JSON-RPC or MCP protocol messages."""


@dataclass(frozen=True)
class PinnedToolDefinition:
    """Tool definition registered in the pinned manifest."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    is_mutating: bool
    schema_digest: str  # "sha256:<hex>"


class RealMcpWireAdapter:
    """
    AEIB Tier 2 Model Context Protocol Wire Adapter.
    Intercepts and governs JSON-RPC 2.0 streams between agent clients and tool backends.
    """

    def __init__(
        self,
        *,
        authority_public_key: Ed25519PublicKey,
        ledger_signing_key: Ed25519PrivateKey,
        ticket_store: PersistentAuthorityTicketStore,
        journal: DurableDispatchJournal,
        active_policy_epoch: int,
        pinned_manifest_digest: str,
        pinned_tools: Dict[str, PinnedToolDefinition],
        downstream_tool_dispatcher: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        probe_reconciler: Optional[Callable[[str, str], str]] = None,
    ) -> None:
        self.authority_public_key = authority_public_key
        self.ledger_signing_key = ledger_signing_key
        self.ticket_store = ticket_store
        self.journal = journal
        self.active_policy_epoch = active_policy_epoch
        self.pinned_manifest_digest = pinned_manifest_digest
        self.pinned_tools = pinned_tools
        self.downstream_tool_dispatcher = downstream_tool_dispatcher

        self.executor = Tier1DurableDispatchExecutor(
            authority_public_key=authority_public_key,
            ledger_signing_key=ledger_signing_key,
            ticket_store=ticket_store,
            journal=journal,
            active_policy_epoch=active_policy_epoch,
            pinned_manifest_digest=pinned_manifest_digest,
            probe_reconciler=probe_reconciler,
        )

        self._lock = threading.Lock()
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        self._in_flight_requests: Dict[Tuple[str, Any], threading.Event] = {}

    def _strip_reasoning_tokens(self, data: Any) -> Any:
        """Dead Salmons filter: removes ephemeral model thought keys recursively."""
        banned_keys = {
            "_reasoning",
            "reasoning",
            "chain_of_thought",
            "thought",
            "thoughts",
            "rationale",
            "explanation",
            "_governance",
            "_meta",
        }
        if isinstance(data, dict):
            return {
                k: self._strip_reasoning_tokens(v)
                for k, v in data.items()
                if k not in banned_keys
            }
        elif isinstance(data, list):
            return [self._strip_reasoning_tokens(item) for item in data]
        return data

    def handle_json_rpc_message(
        self,
        raw_message_json: str,
        session_id: str = "default_session",
    ) -> Optional[str]:
        """
        Processes an incoming JSON-RPC 2.0 message string.
        Returns a JSON-RPC response string, or None for notifications.
        """
        try:
            msg = json.loads(raw_message_json)
        except json.JSONDecodeError as err:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {err}"},
            })

        if not isinstance(msg, dict):
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: must be a JSON object"},
            })

        msg_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {})

        # Handle notifications (no id)
        if msg_id is None:
            self._handle_notification(method, params, session_id)
            return None

        # Handle request methods
        if method == "initialize":
            return self._handle_initialize(msg_id, params, session_id)
        elif method == "tools/list":
            return self._handle_tools_list(msg_id, params, session_id)
        elif method == "tools/call":
            return self._handle_tools_call(msg_id, params, session_id)
        else:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: '{method}'"},
            })

    def _handle_notification(self, method: Optional[str], params: Dict[str, Any], session_id: str) -> None:
        if method == "notifications/initialized":
            with self._lock:
                self._active_sessions[session_id] = {
                    "initialized_at": time.time(),
                    "status": "ACTIVE",
                }
        elif method == "notifications/cancelled":
            target_req_id = params.get("requestId")
            if target_req_id is not None:
                key = (session_id, target_req_id)
                with self._lock:
                    cancel_event = self._in_flight_requests.get(key)
                    if cancel_event is not None:
                        cancel_event.set()

    def _handle_initialize(self, msg_id: Any, params: Dict[str, Any], session_id: str) -> str:
        protocol_version = params.get("protocolVersion", "2024-11-05")
        with self._lock:
            self._active_sessions[session_id] = {
                "protocol_version": protocol_version,
                "client_info": params.get("clientInfo", {}),
                "status": "HANDSHAKE_INITIATED",
            }
        result = {
            "protocolVersion": protocol_version,
            "capabilities": {
                "tools": {"listChanged": True},
            },
            "serverInfo": {
                "name": "aeib-governed-mcp-adapter",
                "version": "1.1.0",
            },
        }
        return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result})

    def _handle_tools_list(self, msg_id: Any, params: Dict[str, Any], session_id: str) -> str:
        """Returns tools pinned to the active manifest digest."""
        tools_array = []
        for name, defn in sorted(self.pinned_tools.items()):
            tools_array.append({
                "name": defn.name,
                "description": defn.description,
                "inputSchema": defn.input_schema,
                "_aeib_metadata": {
                    "isMutating": defn.is_mutating,
                    "schemaDigest": defn.schema_digest,
                    "manifestDigest": self.pinned_manifest_digest,
                },
            })
        return json.dumps({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": tools_array},
        })

    def _handle_tools_call(self, msg_id: Any, params: Dict[str, Any], session_id: str) -> str:
        tool_name = params.get("name")
        raw_args = params.get("arguments", {})

        if not tool_name or tool_name not in self.pinned_tools:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32602,
                    "message": f"TOOL_NOT_PERMITTED: tool '{tool_name}' not in pinned manifest",
                },
            })

        tool_defn = self.pinned_tools[tool_name]
        target_identity = f"mcp://{tool_name}"

        # Setup cancellation tracking for this in-flight request
        cancel_event = threading.Event()
        req_key = (session_id, msg_id)
        with self._lock:
            self._in_flight_requests[req_key] = cancel_event

        try:
            # Check for immediate cancellation before execution
            if cancel_event.is_set():
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32000,
                        "message": "REQUEST_CANCELLED: call cancelled by client notification before dispatch",
                    },
                })

            # Non-mutating tools: pass through with clean inputs
            if not tool_defn.is_mutating:
                cleaned_args = self._strip_reasoning_tokens(raw_args)
                tool_output = self.downstream_tool_dispatcher(tool_name, cleaned_args)
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(tool_output)}],
                        "isError": False,
                        "governance": {
                            "disposition": "CONFIRMED",
                            "mutating": False,
                            "targetIdentity": target_identity,
                        },
                    },
                })

            # Mutating tool: extract governance authority ticket
            gov_meta = raw_args.get("_governance") or params.get("_meta", {}).get("ticket") or raw_args.get("ticket")
            if not gov_meta or not isinstance(gov_meta, dict):
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32001,
                        "message": "AUTHORITY_TICKET_MISSING: mutating tool call requires DispatchAuthorizationTicket in '_governance' or '_meta'",
                    },
                })

            try:
                ticket = DispatchAuthorityTicket(
                    decision_id=gov_meta["decision_id"],
                    operation_id=gov_meta["operation_id"],
                    principal_id=gov_meta["principal_id"],
                    target_identity=gov_meta["target_identity"],
                    action_digest=gov_meta["action_digest"],
                    policy_epoch=gov_meta["policy_epoch"],
                    manifest_digest=gov_meta["manifest_digest"],
                    expires_at=gov_meta["expires_at"],
                    single_use=gov_meta.get("single_use", True),
                    signature_hex=gov_meta["signature_hex"],
                )
            except (KeyError, TypeError) as err:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32002,
                        "message": f"AUTHORITY_TICKET_MALFORMED: missing field: {err}",
                    },
                })

            # Dead Salmons: Clean input args to establish stable CAID
            cleaned_mutation_args = self._strip_reasoning_tokens(raw_args)

            # Define wire dispatcher function that respects cancellation
            def mcp_wire_dispatcher(candidate_payload: Dict[str, Any]) -> Dict[str, Any]:
                if cancel_event.is_set():
                    raise InterruptedError("Cancelled by client notification before wire invocation")
                res = self.downstream_tool_dispatcher(tool_name, candidate_payload)
                if cancel_event.is_set():
                    raise InterruptedError("Cancelled by client notification during tool execution")
                return res

            # Execute through Tier 1 Durable Executor (EO-1 intent -> ticket burn -> dispatch -> receipt)
            try:
                governed_res = self.executor.execute_governed_action(
                    ticket=ticket,
                    candidate_action_payload=cleaned_mutation_args,
                    target_identity=target_identity,
                    current_timestamp=int(time.time()),
                    wire_dispatcher=mcp_wire_dispatcher,
                )
            except GovernanceHaltError as halt_err:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32003,
                        "message": f"GOVERNANCE_HALT: {halt_err}",
                    },
                })

            # Return governed result with attached Ed25519 continuity receipt
            disposition = governed_res["disposition"]
            is_error = disposition != "CONFIRMED"

            return json.dumps({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({"disposition": disposition, "status": governed_res["status"]}),
                    }],
                    "isError": is_error,
                    "governance": {
                        "disposition": disposition,
                        "retrySafe": governed_res["retrySafe"],
                        "receipt": governed_res["receipt"],
                        "receiptSignatureHex": governed_res["receiptSignatureHex"],
                    },
                },
            })

        finally:
            with self._lock:
                self._in_flight_requests.pop(req_key, None)
