#!/usr/bin/env python3
"""
src/universal_agent_adapter.py — Universal Deterministic Agent Interceptor
Sovereign Multi-Agent OS (SMAOS) / AEIB v0.2.4

Implements fail-closed wire-truth middleware and idempotency bindings across:
  1. LangChain / LangGraph (Tool Call Checkpointer & Callback)
  2. LlamaIndex (Step-wise Tool Middleware)
  3. CrewAI (Agent Task Dispatch Wrapper)
  4. Microsoft AutoGen (Agent Conversation Hook)
  5. Native Model Context Protocol (MCP JSON-RPC 2.0 Stdio/SSE Proxy)

Zero mocks. Cryptographic RFC 8785 JCS digest derivation and UUIDv5 idempotency keys.
"""

import os
import sys
import json
import time
import uuid
import hashlib
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, asdict

# UUIDv5 Namespace for Sovereign Actions
NAMESPACE_SMAOS_ACTIONS = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def rfc8785_jcs_canonicalize(data: Any) -> str:
    """Deterministic JSON serialization matching RFC 8785 JCS subset."""
    return json.dumps(data, separators=(',', ':'), sort_keys=True, ensure_ascii=False)


def compute_payload_digest(arguments: Dict[str, Any]) -> str:
    canonical = rfc8785_jcs_canonicalize(arguments)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_action_idempotency_key(tenant_id: str, action_id: str, payload_digest: str) -> str:
    """Derives deterministic UUIDv5 idempotency key bound to tenant, action, and arguments."""
    seed = f"{tenant_id}:{action_id}:{payload_digest}"
    return str(uuid.uuid5(NAMESPACE_SMAOS_ACTIONS, seed))


@dataclass
class InterceptedOutcome:
    action_id: str
    idempotency_key: str
    tenant_id: str
    framework: str
    tool_name: str
    payload_digest: str
    wire_status: int
    disposition: str
    outcome_verified: bool
    duplicate_prevented: bool
    wall_clock_ms: float
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class UniversalAgentInterceptor:
    """
    Core deterministic interceptor that wraps tool executions across heterogeneous
    AI agent frameworks, enforcing the fundamental invariant:
    authorized write != persisted write != correct outcome
    """

    def __init__(self, tenant_id: str = "default_tenant", state_prober: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None):
        self.tenant_id = tenant_id
        self.state_prober = state_prober
        self.execution_ledger: Dict[str, Dict[str, Any]] = {}

    def execute_guarded_tool(
        self,
        framework: str,
        tool_name: str,
        arguments: Dict[str, Any],
        raw_executor: Callable[[Dict[str, Any], Dict[str, str]], Any],
        action_id: Optional[str] = None
    ) -> Tuple[Any, InterceptedOutcome]:
        """
        Executes an agent tool call inside the deterministic AEIB envelope:
        1. Injects UUIDv5 idempotency key.
        2. Detects replay attempts before wire dispatch.
        3. Traps socket drops / HTTP 504 / TCP RST.
        4. Queries authoritative state prober on transport uncertainty.
        """
        t0 = time.perf_counter()
        p_digest = compute_payload_digest(arguments)
        act_id = action_id or f"{framework}:{tool_name}:{p_digest[:16]}"
        idem_key = derive_action_idempotency_key(self.tenant_id, act_id, p_digest)

        headers = {
            "X-Idempotency-Key": idem_key,
            "X-SMAOS-Tenant": self.tenant_id,
            "X-SMAOS-Action-ID": act_id,
            "X-SMAOS-Payload-Hash": p_digest
        }

        # Check local boundary ledger for replay
        if idem_key in self.execution_ledger:
            prior = self.execution_ledger[idem_key]
            elapsed = (time.perf_counter() - t0) * 1000
            outcome = InterceptedOutcome(
                action_id=act_id,
                idempotency_key=idem_key,
                tenant_id=self.tenant_id,
                framework=framework,
                tool_name=tool_name,
                payload_digest=p_digest,
                wire_status=prior["wire_status"],
                disposition=prior["disposition"],
                outcome_verified=prior["outcome_verified"],
                duplicate_prevented=True,
                wall_clock_ms=elapsed,
                error_message="Duplicate tool call intercepted and blocked by boundary kernel."
            )
            return prior.get("cached_result"), outcome

        # Dispatch through raw executor with boundary trap
        raw_result = None
        wire_status = 200
        disposition = "CONFIRMED"
        outcome_verified = True
        err_msg = None

        try:
            raw_result = raw_executor(arguments, headers)
        except Exception as exc:
            err_name = type(exc).__name__
            err_str = str(exc)
            err_msg = f"{err_name}: {err_str}"

            # Trap HTTP 504 / Timeout / Connection Reset
            if "504" in err_str or "Timeout" in err_name or "ConnectionReset" in err_name:
                wire_status = 504
                # Perform out-of-band state probe if available
                if self.state_prober is not None:
                    probe_evidence = self.state_prober(idem_key)
                    if probe_evidence and probe_evidence.get("outcome_confirmed"):
                        disposition = "OUTCOME_VERIFIED"
                        outcome_verified = True
                        raw_result = probe_evidence.get("result_data", {"status": "COMMITTED_ON_SERVER"})
                    elif probe_evidence and probe_evidence.get("not_found"):
                        disposition = "RECONCILIATION_NOT_FOUND"
                        outcome_verified = False
                    else:
                        disposition = "DISPATCHED_UNCONFIRMED"
                        outcome_verified = False
                else:
                    disposition = "DISPATCHED_UNCONFIRMED"
                    outcome_verified = False
            else:
                wire_status = 500
                disposition = "REFUSED"
                outcome_verified = False

        elapsed = (time.perf_counter() - t0) * 1000

        # Record in ledger to protect against subsequent speculative retries
        self.execution_ledger[idem_key] = {
            "action_id": act_id,
            "tool_name": tool_name,
            "wire_status": wire_status,
            "disposition": disposition,
            "outcome_verified": outcome_verified,
            "cached_result": raw_result
        }

        outcome = InterceptedOutcome(
            action_id=act_id,
            idempotency_key=idem_key,
            tenant_id=self.tenant_id,
            framework=framework,
            tool_name=tool_name,
            payload_digest=p_digest,
            wire_status=wire_status,
            disposition=disposition,
            outcome_verified=outcome_verified,
            duplicate_prevented=False,
            wall_clock_ms=elapsed,
            error_message=err_msg
        )

        return raw_result, outcome


# ==============================================================================
# SPECIFIC FRAMEWORK INTEGRATION ADAPTERS
# ==============================================================================

class LangChainAdapter:
    """Adapter for LangChain / LangGraph tool dispatch."""
    def __init__(self, interceptor: UniversalAgentInterceptor):
        self.interceptor = interceptor

    def wrap_tool_call(self, tool_func: Callable[..., Any], tool_name: str):
        def _guarded(*args, **kwargs):
            payload = kwargs if kwargs else ({"args": args} if args else {})
            def _raw_exec(params, headers):
                return tool_func(**params)
            res, outcome = self.interceptor.execute_guarded_tool("LangChain/LangGraph", tool_name, payload, _raw_exec)
            return res
        return _guarded


class LlamaIndexAdapter:
    """Adapter for LlamaIndex query and tool workflows."""
    def __init__(self, interceptor: UniversalAgentInterceptor):
        self.interceptor = interceptor

    def wrap_tool(self, tool_callable: Callable[[Dict[str, Any]], Any], tool_name: str):
        def _guarded(arguments: Dict[str, Any]):
            def _raw_exec(params, headers):
                return tool_callable(params)
            res, outcome = self.interceptor.execute_guarded_tool("LlamaIndex", tool_name, arguments, _raw_exec)
            return res
        return _guarded


class CrewAIAdapter:
    """Adapter for CrewAI agent tool execution."""
    def __init__(self, interceptor: UniversalAgentInterceptor):
        self.interceptor = interceptor

    def execute_crew_tool(self, tool_name: str, arguments: Dict[str, Any], executor: Callable[[Dict[str, Any]], Any]) -> Any:
        def _raw_exec(params, headers):
            return executor(params)
        res, outcome = self.interceptor.execute_guarded_tool("CrewAI", tool_name, arguments, _raw_exec)
        return res


class AutoGenAdapter:
    """Adapter for Microsoft AutoGen agent-to-agent tool execution."""
    def __init__(self, interceptor: UniversalAgentInterceptor):
        self.interceptor = interceptor

    def intercept_autogen_call(self, tool_name: str, arguments: Dict[str, Any], caller_fn: Callable[[Dict[str, Any]], Any]) -> Tuple[Any, InterceptedOutcome]:
        def _raw_exec(params, headers):
            return caller_fn(params)
        return self.interceptor.execute_guarded_tool("Microsoft AutoGen", tool_name, arguments, _raw_exec)


class MCPProxyInterceptor:
    """
    Model Context Protocol (MCP) JSON-RPC 2.0 Wire Proxy Interceptor.
    Sits between client (Claude, Cursor, OpenCodeReview) and backend MCP servers.
    """
    def __init__(self, interceptor: UniversalAgentInterceptor):
        self.interceptor = interceptor

    def process_jsonrpc_request(self, raw_rpc: Dict[str, Any], backend_dispatcher: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        rpc_id = raw_rpc.get("id", "mcp-anon")
        method = raw_rpc.get("method", "")
        params = raw_rpc.get("params", {})
        if not isinstance(params, dict):
            params = {}

        if method == "tools/call":
            tool_name = params.get("name", "unknown_tool")
            arguments = params.get("arguments", params.get("args", {}))
            if not isinstance(arguments, dict):
                arguments = {}

            def _raw_exec(args_dict, headers):
                call_payload = {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": args_dict, "_meta": headers}
                }
                return backend_dispatcher(call_payload)

            res, outcome = self.interceptor.execute_guarded_tool(
                "ModelContextProtocol",
                tool_name,
                arguments,
                _raw_exec,
                action_id=f"mcp-{rpc_id}"
            )

            if not outcome.outcome_verified and outcome.disposition == "DISPATCHED_UNCONFIRMED":
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {
                        "code": -32000,
                        "message": "SMAOS Execution Boundary Quarantined: Post-write timeout detected. Speculative retry prohibited.",
                        "data": outcome.to_dict()
                    }
                }
            return res

        # Non-mutating methods pass through directly
        return backend_dispatcher(raw_rpc)
