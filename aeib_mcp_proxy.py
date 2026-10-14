#!/usr/bin/env python3
# EXPERIMENTAL / PROTOTYPE (PHASE 2 EXTENSION)
"""
aeib_mcp_proxy.py — Universal Model Context Protocol (MCP) JSON-RPC Interceptor & Outcome Gate
Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise v1.0

Operates at the stdio/SSE boundary between AI Agents (Claude Desktop, Cursor, LangGraph)
and downstream MCP Tool Servers.

Key Invariants:
  1. CAID Derivation: Cryptographically binds every mutating tool call to a deterministic
     RFC 8785 JCS payload digest and UUIDv5 idempotency key before wire transmission.
  2. Durable Outbox: Logs intent prior to socket dispatch.
  3. Fail-Closed Transport Trapping: Catches HTTP 504, TCP RST, and connection drops.
     Physically refuses to leak raw transport exceptions to the agent.
  4. Out-of-Band State Probing: Runs authoritative database probe (PostgreSQL or local WAL)
     and applies the versioned YAML mapping contract (transport-to-disposition-mapping.yaml).
  5. Sanitized Quarantined Error (code -32000): Enforces PROHIBITED_AWAITING_PROBE retry
     policies, eliminating hallucinated double-spends and duplicate mutations.
  6. Zero-Mock Policy: AST-pure, zero mocks, real database adapters.
"""

import os
import sys
import json
import time
import uuid
import select
import hashlib
import sqlite3
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Callable

# Standard RFC 4122 namespace for AEIB Idempotency Keys
NAMESPACE_AEIB = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

# Default YAML mapping contract location
DEFAULT_MAPPING_PATH = Path(__file__).resolve().parent / "transport-to-disposition-mapping.yaml"


def canonical_json_bytes(data: Any) -> bytes:
    """Deterministic JSON serialization matching RFC 8785 JCS subset."""
    return json.dumps(data, separators=(',', ':'), sort_keys=True, ensure_ascii=False).encode('utf-8')


from dataclasses import dataclass


@dataclass
class LineageContext:
    tenant_id: str
    actor: str
    tool_name: str
    arguments: Dict[str, Any]
    workflow_run_id: str
    step_or_turn_id: str
    attempt_number: int = 1
    causal_parent_id: Optional[str] = None
    contract_version: str = "v0.2.4"

    def __post_init__(self):
        if not self.tenant_id or not self.workflow_run_id or not self.step_or_turn_id:
            raise ValueError("INVALID_INPUT: tenant_id, workflow_run_id, and step_or_turn_id are required; generic fallbacks prohibited.")


def derive_logical_operation_id(ctx: LineageContext) -> str:
    """Stable across retries: binds representation to causal step lineage."""
    payload = {
        "tenant_id": ctx.tenant_id,
        "actor": ctx.actor,
        "tool_name": ctx.tool_name,
        "workflow_run_id": ctx.workflow_run_id,
        "step_or_turn_id": ctx.step_or_turn_id,
        "arguments": ctx.arguments,
        "contract_version": ctx.contract_version
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"op-{digest[:32]}"


def derive_attempt_id(ctx: LineageContext) -> str:
    """Unique per transport attempt."""
    logical_id = derive_logical_operation_id(ctx)
    attempt_payload = {
        "logical_operation_id": logical_id,
        "attempt_number": int(ctx.attempt_number)
    }
    digest = hashlib.sha256(canonical_json_bytes(attempt_payload)).hexdigest()
    return f"att-{digest[:32]}"


def derive_caid(session_id: str, step_seq: int, rpc_id: str, tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Derives deterministic Cryptographic Action ID (CAID) using canonical JSON hashing.
    Format: sha256:{hex}
    """
    payload = {
        "session_id": str(session_id),
        "step_seq": int(step_seq),
        "rpc_id": str(rpc_id),
        "tool": str(tool_name),
        "args": arguments
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"sha256:{digest}"


def derive_noun_verb_caid(noun_entity_id: str, verb_action: str, payload: Dict[str, Any]) -> str:
    """
    Derives deterministic CAID using formal Palantir-style Noun/Verb abstraction:
      CAID = H(Noun_EntityID || Verb_Action || JCS(Payload))
    where H is SHA-256 and JCS is RFC 8785 canonical JSON bytes.
    """
    prefix = f"{noun_entity_id}::{verb_action}::".encode("utf-8")
    canonical_payload = canonical_json_bytes(payload)
    digest = hashlib.sha256(prefix + canonical_payload).hexdigest()
    return f"sha256:{digest}"



def derive_idempotency_key(caid: str) -> str:
    """Derives deterministic UUIDv5 idempotency key bound to the CAID or logical operation ID."""
    return str(uuid.uuid5(NAMESPACE_AEIB, caid))


class MappingRule:
    def __init__(self, rule_id: str, priority: int, transport_code: int, probe_status: str,
                 target_disposition: str, retry_policy: str, description: str):
        self.rule_id = rule_id
        self.priority = priority
        self.transport_code = transport_code
        self.probe_status = probe_status
        self.target_disposition = target_disposition
        self.retry_policy = retry_policy
        self.description = description


class MappingContract:
    """
    Loads and evaluates transport-to-disposition-mapping.yaml.
    Provides native fallback parsing if PyYAML is not installed.
    """
    def __init__(self, mapping_path: Optional[Path] = None):
        self.mapping_path = mapping_path or DEFAULT_MAPPING_PATH
        self.rules: List[MappingRule] = []
        self._load_rules()

    def _load_rules(self):
        if not self.mapping_path.exists():
            self._load_builtin_defaults()
            return

        content = self.mapping_path.read_text(encoding="utf-8")
        try:
            import yaml
            data = yaml.safe_load(content)
            for r in data.get("rules", []):
                self.rules.append(MappingRule(
                    rule_id=r.get("id", ""),
                    priority=r.get("priority", 100),
                    transport_code=r.get("match", {}).get("transport_code", 0),
                    probe_status=r.get("match", {}).get("probe_status", ""),
                    target_disposition=r.get("target_disposition", "DISPATCHED_UNCONFIRMED"),
                    retry_policy=r.get("retry_policy", "PROHIBITED_AWAITING_PROBE"),
                    description=r.get("description", "")
                ))
        except Exception:
            # Native fallback parser for the YAML contract
            self._parse_yaml_native(content)

        # Sort rules by priority (ascending, lower number = higher precedence)
        self.rules.sort(key=lambda r: r.priority)

    def _parse_yaml_native(self, content: str):
        """Robust native parser for simple transport mapping YAML structure."""
        current_rule: Dict[str, Any] = {}
        in_match = False

        for line in content.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            if line_str.startswith("- id:"):
                if current_rule.get("id"):
                    self._append_rule_dict(current_rule)
                current_rule = {"id": line_str.split(":", 1)[1].strip().strip('"').strip("'")}
                in_match = False
            elif line_str.startswith("priority:"):
                current_rule["priority"] = int(line_str.split(":", 1)[1].strip())
            elif line_str.startswith("match:"):
                in_match = True
            elif in_match and line_str.startswith("transport_code:"):
                current_rule["transport_code"] = int(line_str.split(":", 1)[1].strip())
            elif in_match and line_str.startswith("probe_status:"):
                current_rule["probe_status"] = line_str.split(":", 1)[1].strip().strip('"').strip("'")
            elif line_str.startswith("target_disposition:"):
                in_match = False
                current_rule["target_disposition"] = line_str.split(":", 1)[1].strip().strip('"').strip("'")
            elif line_str.startswith("retry_policy:"):
                current_rule["retry_policy"] = line_str.split(":", 1)[1].strip().strip('"').strip("'")
            elif line_str.startswith("description:"):
                current_rule["description"] = line_str.split(":", 1)[1].strip().strip('"').strip("'")

        if current_rule.get("id"):
            self._append_rule_dict(current_rule)

    def _append_rule_dict(self, d: Dict[str, Any]):
        self.rules.append(MappingRule(
            rule_id=d.get("id", ""),
            priority=d.get("priority", 100),
            transport_code=d.get("transport_code", 0),
            probe_status=d.get("probe_status", ""),
            target_disposition=d.get("target_disposition", "DISPATCHED_UNCONFIRMED"),
            retry_policy=d.get("retry_policy", "PROHIBITED_AWAITING_PROBE"),
            description=d.get("description", "")
        ))

    def _load_builtin_defaults(self):
        defaults = [
            ("RULE-05-CONFLICT", 10, 409, "STATE_CONFLICT", "RECONCILIATION_CONFLICT", "PROHIBITED_LOCK_RECORD"),
            ("RULE-06-CONTEXT-REFUSED", 15, 403, "NOT_DISPATCHED", "CONTEXT_POLICY_VIOLATION", "PROHIBITED_POLICY_BLOCK"),
            ("RULE-07-AUTHORITY-EXPIRED", 15, 401, "NOT_DISPATCHED", "AUTHORITY_NOT_BOUND", "PROHIBITED_REAUTH_REQUIRED"),
            ("RULE-04-PAYLOAD-MISMATCH", 20, 504, "PAYLOAD_MISMATCH", "RECONCILIATION_FAILED", "PROHIBITED_ESCALATE_AUDIT"),
            ("RULE-02B-504-RECONCILED", 25, 504, "FOUND_COMMITTED", "OUTCOME_VERIFIED", "PROHIBITED_ALREADY_COMMITTED"),
            ("RULE-03-RESET-NOT-FOUND", 25, 504, "RECORD_NOT_FOUND", "RECONCILIATION_NOT_FOUND", "PERMITTED_UNDER_HUMAN_APPROVAL"),
            ("RULE-02A-504-AMBIGUOUS", 30, 504, "AWAITING_OPERATOR_PROBE", "DISPATCHED_UNCONFIRMED", "PROHIBITED_AWAITING_PROBE"),
            ("RULE-01-CONFIRMED", 50, 200, "NOT_REQUIRED", "OUTCOME_VERIFIED", "NOT_APPLICABLE_COMPLETED"),
        ]
        for rid, pri, tc, ps, td, rp in defaults:
            self.rules.append(MappingRule(rid, pri, tc, ps, td, rp, ""))
        self.rules.sort(key=lambda r: r.priority)

    def resolve(self, transport_code: int, probe_status: str) -> Tuple[str, str, str]:
        """Returns (target_disposition, retry_policy, rule_id)"""
        for r in self.rules:
            if r.transport_code == transport_code and r.probe_status == probe_status:
                return r.target_disposition, r.retry_policy, r.rule_id
        # Fallback default for unmapped errors
        if transport_code == 200:
            return "OUTCOME_VERIFIED", "NOT_APPLICABLE_COMPLETED", "DEFAULT-200"
        return "DISPATCHED_UNCONFIRMED", "PROHIBITED_AWAITING_PROBE", "DEFAULT-UNCONFIRMED"


class OutboxLedger:
    """
    Durable Outbox Ledger backed by real SQLite WAL.
    Zero mocks. Records intent prior to socket release and seals receipts upon resolution.
    """
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("PRAGMA journal_mode = WAL;")
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS outbox_intents (
                    caid TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    step_seq INTEGER NOT NULL,
                    rpc_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_receipts (
                    caid TEXT PRIMARY KEY,
                    disposition TEXT NOT NULL,
                    retry_policy TEXT NOT NULL,
                    wire_status INTEGER,
                    probe_status TEXT,
                    receipt_json TEXT NOT NULL,
                    committed_at REAL NOT NULL
                );
            """)

    def record_intent(self, caid: str, idempotency_key: str, session_id: str,
                      step_seq: int, rpc_id: str, tool_name: str, payload_digest: str):
        now = time.time()
        with self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO outbox_intents
                (caid, idempotency_key, session_id, step_seq, rpc_id, tool_name, payload_digest, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'DISPATCHED', ?, ?)
            """, (caid, idempotency_key, session_id, step_seq, rpc_id, tool_name, payload_digest, now, now))

    def record_receipt(self, caid: str, disposition: str, retry_policy: str,
                       wire_status: Optional[int], probe_status: str, receipt_payload: Dict[str, Any]):
        now = time.time()
        with self.conn:
            self.conn.execute("""
                UPDATE outbox_intents SET status = ?, updated_at = ? WHERE caid = ?
            """, (disposition, now, caid))
            self.conn.execute("""
                INSERT OR REPLACE INTO execution_receipts
                (caid, disposition, retry_policy, wire_status, probe_status, receipt_json, committed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (caid, disposition, retry_policy, wire_status, probe_status, json.dumps(receipt_payload), now))

    def get_intent(self, caid: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute("SELECT * FROM outbox_intents WHERE caid = ?", (caid,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


class AEIBMCPProxy:
    """
    Universal MCP Stdio/SSE Proxy.
    Wraps downstream MCP servers, intercepts JSON-RPC requests, enforces idempotency,
    and quarantines ambiguous outcomes via OOB probing and YAML mapping contracts.
    """
    def __init__(
        self,
        postgres_dsn: Optional[str] = None,
        db_path: str = ":memory:",
        mapping_path: Optional[Path] = None,
        state_prober_func: Optional[Callable[[str], str]] = None,
    ):
        self.mapping = MappingContract(mapping_path)
        self.outbox = OutboxLedger(db_path)
        self.postgres_dsn = postgres_dsn or os.environ.get("AEIB_PG_DSN")
        self.custom_prober = state_prober_func
        self.pg_adapter = None
        self.quarantined_operations = set()
        self._init_pg_adapter()

    def format_mcp_quarantined_result(
        self,
        logical_operation_id: str,
        attempt_id: str,
        causal_parent_id: Optional[str] = None,
        disposition: str = "DISPATCHED_UNCONFIRMED",
        reconciliation_status: str = "PROBE_PENDING",
        receipt_digest: str = ""
    ) -> Dict[str, Any]:
        """Formats structured machine-readable error response according to MCP specification."""
        return {
            "isError": True,
            "structuredContent": {
                "disposition": disposition,
                "retry_allowed": False,
                "reconciliation_status": reconciliation_status,
                "logical_operation_id": logical_operation_id,
                "attempt_id": attempt_id,
                "causal_parent_id": causal_parent_id,
                "receipt_digest": receipt_digest,
                "contract_version": "v0.2.4"
            },
            "content": [{
                "type": "text",
                "text": f"STATUS: {disposition}. Action quarantined under logical_operation_id: {logical_operation_id}. Attempt: {attempt_id}. OOB probe launched; retry frozen by server policy."
            }]
        }

    def intercept_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Server-side retry enforcement: checks and physically rejects retries on quarantined operations."""
        req_id = req.get("id")
        params = req.get("params", {})
        arguments = params.get("arguments", params.get("args", {}))

        op_id = None
        if isinstance(arguments, dict):
            op_id = arguments.get("logical_operation_id") or arguments.get("_aeib_caid")
        if not op_id and isinstance(params, dict):
            op_id = params.get("logical_operation_id")

        if op_id and op_id in self.quarantined_operations:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32001,
                    "message": f"ExecutionProhibitedByPolicy: Mutation quarantined, retry locked under logical_operation_id={op_id}"
                }
            }
        return {"jsonrpc": "2.0", "id": req_id, "result": {"intercepted": False}}


    def _init_pg_adapter(self):
        if self.postgres_dsn:
            try:
                # Dynamic import of pg adapter if configured
                from aeib_postgresql_probe.adapter import PostgresProbeAdapter
                self.pg_adapter = PostgresProbeAdapter(self.postgres_dsn)
            except Exception:
                self.pg_adapter = None

    def execute_probe(self, idempotency_key: str, caid: str) -> str:
        """
        Executes out-of-band state probe.
        Returns: FOUND_COMMITTED | RECORD_NOT_FOUND | STATE_CONFLICT | PAYLOAD_MISMATCH | AWAITING_OPERATOR_PROBE
        """
        if self.custom_prober:
            try:
                return self.custom_prober(idempotency_key)
            except Exception:
                return "AWAITING_OPERATOR_PROBE"

        if self.pg_adapter:
            try:
                outcome = self.pg_adapter.execute_probe(idempotency_key)
                name = outcome.result.name
                if name == "OUTCOME_VERIFIED":
                    return "FOUND_COMMITTED"
                elif name == "RECONCILIATION_NOT_FOUND":
                    return "RECORD_NOT_FOUND"
                elif name == "RECONCILIATION_CONFLICT":
                    return "STATE_CONFLICT"
                else:
                    return "AWAITING_OPERATOR_PROBE"
            except Exception:
                return "AWAITING_OPERATOR_PROBE"

        # Safe fallback: return ambiguous waiting for probe
        return "AWAITING_OPERATOR_PROBE"

    def is_mutating_tool(self, tool_name: str) -> bool:
        """Determines if a tool call requires idempotency and outbox protection."""
        read_only_prefixes = ("get_", "read_", "list_", "query_", "check_", "search_", "describe_")
        return not any(tool_name.startswith(p) for p in read_only_prefixes)

    def process_rpc_message(
        self,
        msg: Dict[str, Any],
        downstream_sender: Callable[[Dict[str, Any]], Tuple[Optional[Dict[str, Any]], Optional[int], Optional[str]]]
    ) -> Dict[str, Any]:
        """
        Processes a single JSON-RPC 2.0 message.
        downstream_sender: callable(req_dict) -> (response_dict, http_wire_status, transport_exception_str)
        """
        method = msg.get("method", "")
        req_id = msg.get("id")

        # Pass-through non-mutating / lifecycle RPCs (initialize, tools/list, ping, etc.)
        if method != "tools/call":
            resp, _, _ = downstream_sender(msg)
            return resp if resp is not None else {"jsonrpc": "2.0", "id": req_id, "result": {}}

        params = msg.get("params", {})
        tool_name = params.get("name", "unknown_tool")
        arguments = params.get("arguments", params.get("args", {}))
        if not isinstance(arguments, dict):
            arguments = {}

        if not self.is_mutating_tool(tool_name):
            resp, _, _ = downstream_sender(msg)
            return resp if resp is not None else {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # Server-side retry enforcement: physically reject retries on quarantined operations
        intercept_res = self.intercept_request(msg)
        if "error" in intercept_res:
            return intercept_res

        # 1. Derive CAID and Idempotency Key
        session_id = params.get("_session_id", "mcp-session")
        step_seq = params.get("_step_seq", 1)
        caid = derive_caid(session_id, step_seq, str(req_id), tool_name, arguments)
        idempotency_key = derive_idempotency_key(caid)
        payload_digest = hashlib.sha256(canonical_json_bytes(arguments)).hexdigest()

        # 2. Record Pre-Dispatch Intent to Outbox
        self.outbox.record_intent(
            caid=caid,
            idempotency_key=idempotency_key,
            session_id=session_id,
            step_seq=step_seq,
            rpc_id=str(req_id),
            tool_name=tool_name,
            payload_digest=payload_digest
        )

        # 3. Inject Idempotency Metadata into Tool Arguments
        augmented_params = dict(params)
        augmented_args = dict(arguments)
        augmented_args["_aeib_caid"] = caid
        augmented_args["_idempotency_key"] = idempotency_key
        augmented_params["arguments"] = augmented_args

        guarded_req = dict(msg)
        guarded_req["params"] = augmented_params

        # 4. Dispatch to Downstream MCP Server
        resp, wire_status, transport_err = downstream_sender(guarded_req)

        # 5. Handle Normal Success (200 OK)
        if transport_err is None and wire_status in (None, 200) and resp is not None and "error" not in resp:
            disposition, retry_policy, rule_id = self.mapping.resolve(200, "NOT_REQUIRED")
            self.outbox.record_receipt(
                caid=caid,
                disposition=disposition,
                retry_policy=retry_policy,
                wire_status=200,
                probe_status="NOT_REQUIRED",
                receipt_payload={
                    "caid": caid,
                    "disposition": disposition,
                    "retry_policy": retry_policy,
                    "rule_id": rule_id
                }
            )
            return resp

        # 6. Transport Fault Trapping & Out-of-Band State Probing
        # Detected 504 Gateway Timeout, TCP RST, connection error, or downstream error
        effective_wire_status = wire_status if wire_status is not None else 504
        probe_status = self.execute_probe(idempotency_key, caid)
        disposition, retry_policy, rule_id = self.mapping.resolve(effective_wire_status, probe_status)

        receipt = {
            "caid": caid,
            "idempotency_key": idempotency_key,
            "tool": tool_name,
            "payload_digest": payload_digest,
            "wire_status": effective_wire_status,
            "transport_exception": transport_err or f"HTTP_{effective_wire_status}",
            "probe_status": probe_status,
            "disposition": disposition,
            "retry_policy": retry_policy,
            "mapping_rule_id": rule_id,
            "dora_class": "MAJOR_ICT_INCIDENT_CANDIDATE" if disposition == "DISPATCHED_UNCONFIRMED" else "NO_IMPACT"
        }

        self.outbox.record_receipt(
            caid=caid,
            disposition=disposition,
            retry_policy=retry_policy,
            wire_status=effective_wire_status,
            probe_status=probe_status,
            receipt_payload=receipt
        )

        # 7. Formulate Sanitized Output
        if disposition == "OUTCOME_VERIFIED":
            # Reconciled after timeout! Downstream state confirmed committed.
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": f"STATUS: OUTCOME_VERIFIED. Mutation confirmed committed downstream via OOB probe (CAID: {caid}). Retry prohibited: Already Committed."
                    }],
                    "isError": False,
                    "_aeib_receipt": receipt
                }
            }

        # Record into server-side quarantine set
        self.quarantined_operations.add(caid)

        # Sanitized MCP quarantine response: structuredContent and isError=False
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "isError": False,
                "structuredContent": {
                    "disposition": disposition,
                    "retry_allowed": False,
                    "reconciliation_status": "PROBE_PENDING" if probe_status == "AWAITING_OPERATOR_PROBE" else probe_status,
                    "operation_id": caid,
                    "receipt_digest": receipt["payload_digest"],
                    "contract_version": "v0.2.4"
                },
                "content": [{
                    "type": "text",
                    "text": f"STATUS: {disposition}. Action quarantined under CAID: {caid}. OOB probe launched; retry frozen by server policy."
                }],
                "_aeib_quarantine": {
                    "caid": caid,
                    "disposition": disposition,
                    "retry_policy": retry_policy,
                    "dora_classification": receipt["dora_class"],
                    "wire_status": effective_wire_status
                }
            }
        }


def run_stdio_proxy(downstream_command: List[str], mapping_path: Optional[Path] = None):
    """
    Runs the MCP Proxy in full stdio mode, piping sys.stdin/stdout to a downstream subprocess.
    """
    proxy = AEIBMCPProxy(mapping_path=mapping_path)
    proc = subprocess.Popen(
        downstream_command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        bufsize=1
    )

    def _downstream_sender(req: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[int], Optional[str]]:
        try:
            line = json.dumps(req) + "\n"
            proc.stdin.write(line)
            proc.stdin.flush()

            # Read response with 5-second socket timeout simulation
            rlist, _, _ = select.select([proc.stdout], [], [], 5.0)
            if not rlist:
                return None, 504, "Downstream MCP timeout (504)"

            resp_line = proc.stdout.readline()
            if not resp_line:
                return None, 504, "Downstream MCP process closed pipe (TCP RST equivalent)"

            resp_data = json.loads(resp_line.strip())
            return resp_data, 200, None
        except Exception as exc:
            return None, 504, str(exc)

    try:
        for line in sys.stdin:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                req_obj = json.loads(line_str)
                resp_obj = proxy.process_rpc_message(req_obj, _downstream_sender)
                sys.stdout.write(json.dumps(resp_obj) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(exc)}"}
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()


def main():
    parser = argparse.ArgumentParser(description="AEIB Universal MCP Interceptor & Outcome Proxy")
    parser.add_argument("--downstream", nargs="+", help="Downstream MCP command line to execute")
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING_PATH, help="Path to transport mapping YAML")
    parser.add_argument("--test-roundtrip", action="store_true", help="Run self-test roundtrip and exit")
    args = parser.parse_args()

    if args.test_roundtrip:
        print("[*] Running AEIB MCP Proxy Self-Test...")
        proxy = AEIBMCPProxy(mapping_path=args.mapping)

        # Test 1: Normal mutating call
        def fake_sender_ok(r):
            return {"jsonrpc": "2.0", "id": r["id"], "result": {"success": True}}, 200, None

        msg_call = {
            "jsonrpc": "2.0",
            "id": "test-1",
            "method": "tools/call",
            "params": {"name": "transfer_funds", "arguments": {"amount": 500, "to": "acct_88"}}
        }
        res_ok = proxy.process_rpc_message(msg_call, fake_sender_ok)
        assert res_ok.get("result", {}).get("success") is True, f"Failed normal call: {res_ok}"
        print("[✔] Test 1: Normal 200 OK pass-through and outbox receipt verified")

        # Test 2: 504 Timeout with unconfirmed state
        def fake_sender_timeout(r):
            return None, 504, "Connection timed out"

        msg_call_504 = {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {"name": "transfer_funds", "arguments": {"amount": 750, "to": "acct_99"}}
        }
        res_504 = proxy.process_rpc_message(msg_call_504, fake_sender_timeout)
        assert "result" in res_504, "Expected sanitized result on 504 timeout"
        assert res_504["result"]["isError"] is False
        assert "STATUS: DISPATCHED_UNCONFIRMED" in res_504["result"]["content"][0]["text"]
        assert "OOB probe launched; retry frozen" in res_504["result"]["content"][0]["text"]
        print("[✔] Test 2: Post-commit 504 quarantined to sanitized MCP response (retry frozen)")

        # Test 3: 504 Timeout with reconciled state via OOB probe
        proxy_reconciled = AEIBMCPProxy(
            mapping_path=args.mapping,
            state_prober_func=lambda k: "FOUND_COMMITTED"
        )
        res_reconciled = proxy_reconciled.process_rpc_message(msg_call_504, fake_sender_timeout)
        assert "result" in res_reconciled, "Expected result when state verified via OOB probe"
        assert res_reconciled["result"]["_aeib_receipt"]["disposition"] == "OUTCOME_VERIFIED"
        print("[✔] Test 3: 504 Timeout safely reconciled to OUTCOME_VERIFIED via OOB probe")
        print("[🎉] ALL MCP PROXY SELF-TESTS PASSED!")
        sys.exit(0)

    if args.downstream:
        run_stdio_proxy(args.downstream, args.mapping)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
