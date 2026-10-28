# Copyright 2026 SovereignNexus Project
#
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
adapters/mcp/idempotent_mcp_proxy.py — Hardened Idempotent MCP Proxy Middleware.

Lifts Station 1 (schema + Content-Addressed Action Identifier) and Station 2
(SQLite Write-Ahead Log + uncertainty latch) directly into the Model Context Protocol (MCP)
JSON-RPC transport and tool call lifecycle.

Core Functions:
1. Intercepts JSON-RPC `tools/call` and `tools/status` requests.
2. Computes Content-Addressed Action Identifiers (CAID) via RFC 8785 JCS canonicalization.
3. Disambiguates request-intent digest (CAID) from operation identity (composite key).
4. Enforces write-before-execute intent logging into a durable SQLite WAL with `BEGIN IMMEDIATE`.
5. Serializes concurrent requests on identical keys/CAID to defeat thundering herd races.
6. Latches ambiguous network transport drops, 5xx, and ambiguous 408/429 errors into `EFFECT_INDETERMINATE`.
7. Inspects MCP tool-level `isError: true` in 200 responses and routes to uncertainty latch.
8. Enforces separate retention TTL and uncertainty resolution deadlines (never purges unresolved uncertainty).
9. Halts blind retries under uncertainty and drives authoritative `tools/status` reconciliation.
10. Preserves latched uncertainty across policy epoch rotations.
11. Strict JSON ingress via `handle_raw_frame` (src/strict_json_ingress.loads_strict): duplicate
    keys, NaN/Infinity and lone surrogates are rejected with JSON-RPC -32700.
12. Tool-definition pinning: upstream `tools/list` results are checked against an approved
    ToolDefinitionPinSet via McpToolPinGuard (unpinned server, rug pull, added/removed tool,
    cross-server shadowing -> JSON-RPC -32040 with typed findings); once pinned, `tools/call`
    for a tool outside the pinned set is refused. Learn mode is OFF by default.
13. Optional effect-key CAID (``effect_key_registry``, src/eo1_effect_key.py): the intent hash is
    the schema-declared effect CAID, so a regenerated retry (new idempotency_key / client UUID,
    changed memo; same recipient, amount, business reference) matches the earlier record
    (ACRFence, arXiv:2603.20625). The digest of the exact raw arguments is stored next to it
    (``raw_payload_digest``). A tool without a schema, or a missing / invalid identity field,
    is refused with JSON-RPC -32095 EFFECT_KEY_SCHEMA_REJECTED before any upstream call.
14. Optional settle-before-retry (``reconcile_probe_fn``): a call that matches a record in
    EFFECT_INDETERMINATE probes the target first. APPLIED -> the record is settled CONFIRMED with
    an Ed25519-signed settlement receipt and the duplicate is refused (-32012
    OPERATION_RECONCILED_CONFIRMED_DUPLICATE_BLOCKED). NOT_APPLIED -> fail closed by default:
    a read-back cannot distinguish "never applied" from "still in flight, will commit late"
    (LIMBO, arXiv:2609.29095, Prop. 1). The prior attempt is settled SUPERSEDED_NOT_APPLIED and one
    fresh attempt is dispatched only on a settlement basis recorded in the signed receipt:
    "deadline" (the prior attempt carried a target-enforced not-after, forwarded as
    `_meta.aeib_not_after_ms` when `dispatch_not_after_ms` is set, that has passed + `deadline_skew_ms`),
    "fence" (`fence_probe_fn(tool, caid, next_attempt_no)` returned True: the target will refuse
    attempts with a lower `_meta.aeib_attempt_no`), or "unsafe_opt_in"
    (`trust_not_applied_without_fence=True`; a late commit can then duplicate). Without a basis the
    latch stays (-32009, reason NOT_APPLIED_UNFENCED). Whether the target enforces the deadline or
    fence is the operator's configuration claim; the proxy cannot verify it. UNKNOWN, any
    other answer, or a probe exception -> the latch stays (-32009
    EXECUTION_HALTED_INDETERMINATE_LATCH). The probe runs while the proxy holds its lock and the
    SQLite write transaction, so settlement and the decision to dispatch are serialized. A record
    whose dispatch has not yet returned in this process is never probed (a read-back cannot tell
    "in flight" from "not applied"); this in-flight set is per process. The read-back
    is only as authoritative as the target (a target that applies a request after answering
    NOT_APPLIED can still produce a duplicate).
"""

from __future__ import annotations

import base64
import concurrent.futures
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.eo1_effect_key import EffectKeyError, EffectKeySchemaRegistry, bind_effect_key
from src.jcs_canonicalizer import encode_jcs
from src.mcp_schema_pinning import ToolDefinitionPinSet
from src.secure_mcp_uds_boundary import McpToolPinGuard, ToolPinViolation
from src.strict_json_ingress import StrictJSONError, loads_strict

PROBE_APPLIED = "APPLIED"
PROBE_NOT_APPLIED = "NOT_APPLIED"
PROBE_UNKNOWN = "UNKNOWN"
STATE_SUPERSEDED_NOT_APPLIED = "SUPERSEDED_NOT_APPLIED"
SETTLEMENT_RECEIPT_TYPE = "AEIB_MCP_SETTLEMENT_RECEIPT_V1"
_RECEIPT_STATEMENT_FIELDS = (
    "receipt_type", "idempotency_key", "effect_caid", "raw_payload_digest", "settled_state",
    "probe_outcome", "settlement_basis", "settled_attempt_no", "next_attempt_no", "settled_at_ms",
    "signer_public_key_hex",
)
SETTLEMENT_BASIS_READ_BACK_APPLIED = "read_back_applied"
SETTLEMENT_BASIS_DEADLINE = "deadline"
SETTLEMENT_BASIS_FENCE = "fence"
SETTLEMENT_BASIS_UNSAFE_OPT_IN = "unsafe_opt_in"


def _public_key_hex(public_key: Ed25519PublicKey) -> str:
    return public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def verify_settlement_receipt(receipt: Mapping[str, Any], public_key: Ed25519PublicKey) -> bool:
    """
    Verifies an Ed25519 settlement receipt against a caller-supplied trusted public key.
    The key embedded in the receipt is never trusted on its own: it must equal ``public_key``.
    """
    if not isinstance(receipt, Mapping) or not isinstance(public_key, Ed25519PublicKey):
        return False
    if receipt.get("receipt_type") != SETTLEMENT_RECEIPT_TYPE:
        return False
    if any(name not in receipt for name in _RECEIPT_STATEMENT_FIELDS):
        return False
    if receipt["signer_public_key_hex"] != _public_key_hex(public_key):
        return False
    statement = {name: receipt[name] for name in _RECEIPT_STATEMENT_FIELDS}
    try:
        signature = base64.b64decode(str(receipt.get("signature_b64", "")), validate=True)
        public_key.verify(signature, encode_jcs(statement))
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def canonical_json_v1(obj: Any) -> bytes:
    """Canonicalizes JSON objects according to RFC 8785 (UTF-8, sorted keys, strict formatting)."""
    return encode_jcs(obj)


@dataclass
class McpProxyStateRecord:
    idempotency_key: str
    caid: str
    tool_name: str
    state: str  # CONFIRMED, EFFECT_INDETERMINATE, REFUTED, UNRESOLVED_ESCALATED, NOT_FOUND
    tenant_id: str = "default_tenant"
    principal: str = "default_principal"
    operation_id: Optional[str] = None
    cached_response: Optional[Dict[str, Any]] = None
    policy_epoch: str = "epoch-2026-Q4"
    created_at: float = field(default_factory=time.time)
    uncertainty_resolution_deadline: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class HardenedIdempotentMcpProxy:
    """
    Sits between the agent client and the upstream MCP server.
    Owns the idempotency SQLite WAL and enforces uncertainty state-machine rules.
    """

    def __init__(
        self,
        upstream_transport_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        db_path: str | Path = ":memory:",
        ttl_sec: int = 86400,
        uncertainty_deadline_sec: int = 300,
        active_policy_epoch: str = "epoch-2026-Q4",
        tool_pins: Optional[ToolDefinitionPinSet] = None,
        upstream_server_id: str = "upstream",
        tool_pin_learn_mode: bool = False,
        effect_key_registry: Optional[EffectKeySchemaRegistry] = None,
        reconcile_probe_fn: Optional[Callable[[str, str, Dict[str, Any]], str]] = None,
        receipt_signing_key: Optional[Ed25519PrivateKey] = None,
        fence_probe_fn: Optional[Callable[[str, str, int], bool]] = None,
        trust_not_applied_without_fence: bool = False,
        dispatch_not_after_ms: Optional[int] = None,
        deadline_skew_ms: int = 0,
    ) -> None:
        self.upstream = upstream_transport_fn
        self.db_path = str(db_path)
        self.ttl_sec = ttl_sec
        self.retention_ttl_sec = ttl_sec
        self.uncertainty_deadline_sec = uncertainty_deadline_sec
        self.active_policy_epoch = active_policy_epoch
        self.lock = threading.Lock()
        # Optional effect-key CAID and settle-before-retry probe (both off when None).
        self.effect_key_registry = effect_key_registry
        self.reconcile_probe_fn = reconcile_probe_fn
        # Settlement receipts are signed with this key. Without an explicit key the proxy holds an
        # ephemeral one; receipts then verify only against receipt_public_key() of this instance.
        self.receipt_signing_key = receipt_signing_key if receipt_signing_key is not None else Ed25519PrivateKey.generate()
        # Keys whose upstream dispatch has not returned in this process. Their EFFECT_INDETERMINATE
        # record is never settled by probe (a read-back cannot tell "in flight" from "not applied").
        # Not visible across processes sharing one database file.
        self._in_flight_keys: set = set()
        # Late-commit fail-closed policy (LIMBO arXiv:2609.29095 Prop. 1): a NOT_APPLIED read-back
        # unlocks a fresh dispatch only on a settlement basis -- "deadline" (the prior attempt carried
        # a not-after that the target enforces and it has passed + skew), "fence" (fence_probe_fn
        # returned True: the target will refuse attempts older than the new attempt number), or
        # "unsafe_opt_in" (trust_not_applied_without_fence=True). Otherwise the latch stays.
        if dispatch_not_after_ms is not None and (isinstance(dispatch_not_after_ms, bool)
                                                  or not isinstance(dispatch_not_after_ms, int)
                                                  or dispatch_not_after_ms <= 0):
            raise ValueError("dispatch_not_after_ms must be a positive int (milliseconds) or None")
        if isinstance(deadline_skew_ms, bool) or not isinstance(deadline_skew_ms, int) or deadline_skew_ms < 0:
            raise ValueError("deadline_skew_ms must be a non-negative int (milliseconds)")
        self.fence_probe_fn = fence_probe_fn
        self.trust_not_applied_without_fence = trust_not_applied_without_fence is True
        self.dispatch_not_after_ms = dispatch_not_after_ms
        self.deadline_skew_ms = deadline_skew_ms
        # tools/list is always gated; learn mode (first-use pinning) is OFF by default.
        self.tool_pin_guard = McpToolPinGuard(
            upstream_server_id, tool_pins, learn_mode=tool_pin_learn_mode
        )

        # If disk path provided, ensure parent directory exists
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite database with WAL mode and immediate locking
        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode, manual BEGIN/COMMIT
        )
        if self.db_path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA synchronous=FULL;")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS mcp_idempotency (
                idem_key TEXT PRIMARY KEY,
                tenant_id TEXT,
                principal TEXT,
                operation_id TEXT,
                tool_name TEXT,
                caid TEXT,
                state TEXT, -- CONFIRMED, EFFECT_INDETERMINATE, REFUTED, UNRESOLVED_ESCALATED
                policy_epoch TEXT,
                created_at REAL,
                uncertainty_resolution_deadline REAL,
                cached_response TEXT
            );
        """)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tenant_caid ON mcp_idempotency(tenant_id, principal, tool_name, caid);"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_caid_tool ON mcp_idempotency(caid, tool_name);")
        # Additive columns (older databases are migrated in place; existing rows get NULL).
        existing_cols = {r[1] for r in self.conn.execute("PRAGMA table_info(mcp_idempotency);").fetchall()}
        for col, col_type in (("raw_payload_digest", "TEXT"), ("settlement_receipt", "TEXT"),
                              ("attempt_no", "INTEGER"), ("not_after_ms", "INTEGER")):
            if col not in existing_cols:
                self.conn.execute(f"ALTER TABLE mcp_idempotency ADD COLUMN {col} {col_type};")

    def receipt_public_key(self) -> Ed25519PublicKey:
        """Public half of the settlement-receipt signing key."""
        return self.receipt_signing_key.public_key()

    def _sign_settlement(self, idem_key: str, caid: str, raw_digest: Optional[str], settled_state: str,
                         probe_outcome: str, now: float, settlement_basis: str, settled_attempt_no: int,
                         next_attempt_no: int) -> Dict[str, Any]:
        statement = {
            "receipt_type": SETTLEMENT_RECEIPT_TYPE,
            "idempotency_key": idem_key,
            "effect_caid": caid,
            "raw_payload_digest": raw_digest or "",
            "settled_state": settled_state,
            "probe_outcome": probe_outcome,
            "settlement_basis": settlement_basis,
            "settled_attempt_no": settled_attempt_no,
            "next_attempt_no": next_attempt_no,
            "settled_at_ms": int(now * 1000),
            "signer_public_key_hex": _public_key_hex(self.receipt_public_key()),
        }
        signature = self.receipt_signing_key.sign(encode_jcs(statement))
        return {**statement, "signature_b64": base64.b64encode(signature).decode("ascii")}

    def _probe_target(self, tool_name: str, caid: str, args: Any) -> Tuple[str, str]:
        """Calls reconcile_probe_fn; only the exact strings APPLIED / NOT_APPLIED are acted on."""
        try:
            answer = self.reconcile_probe_fn(tool_name, caid, dict(args) if isinstance(args, dict) else {})
        except Exception as exc:  # any probe failure keeps the latch (fail closed)
            return PROBE_UNKNOWN, f"probe_raised:{type(exc).__name__}"
        if answer in (PROBE_APPLIED, PROBE_NOT_APPLIED) and isinstance(answer, str):
            return answer, "probe_answer"
        return PROBE_UNKNOWN, "probe_answer" if answer == PROBE_UNKNOWN else "probe_answer_unrecognised"

    def _settle_indeterminate(
        self, prior_key: str, prior_raw: Optional[str], caid: str, tool_name: str, args: Any,
        retry_raw: Optional[str], now: float,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Settle-before-retry for a record in EFFECT_INDETERMINATE (caller holds lock + transaction).
        Returns (response, None) when the call must not be dispatched (transaction committed), or
        (None, receipt) when the prior attempt was settled NOT_APPLIED and the fresh attempt may proceed.
        """
        if prior_key in self._in_flight_keys:
            outcome, detail = PROBE_UNKNOWN, "not_probed_attempt_in_flight"
        else:
            outcome, detail = self._probe_target(tool_name, caid, args)
        prior = self.conn.execute(
            "SELECT tenant_id, principal, tool_name, attempt_no, not_after_ms FROM mcp_idempotency WHERE idem_key = ?;",
            (prior_key,),
        ).fetchone()
        p_tenant, p_principal, p_tool, p_attempt, p_not_after = prior
        settled_attempt = int(p_attempt or 0)
        if outcome == PROBE_APPLIED:
            receipt = self._sign_settlement(prior_key, caid, prior_raw, "CONFIRMED", outcome, now,
                                            SETTLEMENT_BASIS_READ_BACK_APPLIED, settled_attempt, 0)
            cached = {"reconciled_state": "CONFIRMED", "effect_caid": caid, "settlement_receipt": receipt}
            self.conn.execute(
                "UPDATE mcp_idempotency SET state = 'CONFIRMED', settlement_receipt = ?, cached_response = ? "
                "WHERE idem_key = ? AND state = 'EFFECT_INDETERMINATE';",
                (json.dumps(receipt), json.dumps(cached), prior_key),
            )
            self.conn.execute("COMMIT;")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32012,
                    "message": "OPERATION_RECONCILED_CONFIRMED_DUPLICATE_BLOCKED",
                    "data": {
                        "effect_caid": caid,
                        "raw_payload_digest": prior_raw,
                        "retry_raw_payload_digest": retry_raw,
                        "reconciled_state": "CONFIRMED",
                        "existing_idempotency_key": prior_key,
                        "settlement_receipt": receipt,
                    },
                },
            }, None
        if outcome == PROBE_NOT_APPLIED:
            next_attempt = self._next_attempt_no(p_tenant, p_principal, p_tool, caid)
            basis, fence_detail = self._not_applied_basis(tool_name, caid, next_attempt, p_not_after, now)
            if basis is None:
                self.conn.execute("COMMIT;")
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32009,
                        "message": "EXECUTION_HALTED_INDETERMINATE_LATCH",
                        "data": {
                            "state": "EFFECT_INDETERMINATE",
                            "idempotency_key": prior_key,
                            "caid": caid,
                            "probe_outcome": outcome,
                            "probe_detail": detail,
                            "reason": "NOT_APPLIED_UNFENCED",
                            "fence_detail": fence_detail,
                            "settled_attempt_no": settled_attempt,
                        },
                    },
                }, None
            receipt = self._sign_settlement(prior_key, caid, prior_raw, STATE_SUPERSEDED_NOT_APPLIED, outcome, now,
                                            basis, settled_attempt, next_attempt)
            self.conn.execute(
                "UPDATE mcp_idempotency SET state = ?, settlement_receipt = ? "
                "WHERE idem_key = ? AND state = 'EFFECT_INDETERMINATE';",
                (STATE_SUPERSEDED_NOT_APPLIED, json.dumps(receipt), prior_key),
            )
            return None, receipt
        self.conn.execute("COMMIT;")
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32009,
                "message": "EXECUTION_HALTED_INDETERMINATE_LATCH",
                "data": {
                    "state": "EFFECT_INDETERMINATE",
                    "idempotency_key": prior_key,
                    "caid": caid,
                    "probe_outcome": outcome,
                    "probe_detail": detail,
                },
            },
        }, None

    def _next_attempt_no(self, tenant_id: str, principal: str, tool_name: str, caid: str) -> int:
        """1 + the highest attempt number recorded for this intent (rows without a number count as 1)."""
        row = self.conn.execute(
            "SELECT MAX(COALESCE(attempt_no, 1)) FROM mcp_idempotency "
            "WHERE tenant_id = ? AND principal = ? AND tool_name = ? AND caid = ?;",
            (tenant_id, principal, tool_name, caid),
        ).fetchone()
        return int(row[0] or 0) + 1

    def _not_applied_basis(self, tool_name: str, caid: str, next_attempt: int, prior_not_after_ms: Optional[int],
                           now: float) -> Tuple[Optional[str], str]:
        """Returns (settlement basis or None, fence detail) for a NOT_APPLIED read-back."""
        now_ms = int(now * 1000)
        if prior_not_after_ms is not None and now_ms > int(prior_not_after_ms) + self.deadline_skew_ms:
            return SETTLEMENT_BASIS_DEADLINE, "not_attempted_deadline_elapsed"
        fence_detail = "no_fence_probe_configured"
        if self.fence_probe_fn is not None:
            try:
                acked = self.fence_probe_fn(tool_name, caid, next_attempt)
            except Exception as exc:  # a failed fence never unlocks a dispatch
                acked, fence_detail = False, f"fence_raised:{type(exc).__name__}"
            else:
                fence_detail = "fence_acked" if acked is True else "fence_not_acked"
            if acked is True:
                return SETTLEMENT_BASIS_FENCE, fence_detail
        if self.trust_not_applied_without_fence:
            return SETTLEMENT_BASIS_UNSAFE_OPT_IN, fence_detail
        return None, fence_detail

    def compute_caid(self, arguments: Dict[str, Any], tool_name: str = "") -> str:
        """Computes deterministic Content-Addressed Action Identifier over canonical arguments."""
        canonical = canonical_json_v1({"tool": tool_name, "arguments": arguments})
        return f"sha256:{hashlib.sha256(canonical).hexdigest()}"

    def _compute_identity_key(
        self,
        tenant_id: str,
        principal_id: str,
        operation_id: str,
        tool_name: str,
        canonical_args: bytes,
    ) -> str:
        """
        Primary identity is the explicit operation_id bound to tenant and principal.
        CAID (args_digest) is retained for intent-collision detection but does not override operation identity.
        """
        args_digest = hashlib.sha256(canonical_args).hexdigest()
        if not operation_id:
            # Weak identity fallback; requires strict operator policy to allow
            operation_id = f"caid_fallback_{args_digest[:16]}"
        return f"{tenant_id}:{principal_id}:{operation_id}:{tool_name}:{args_digest}"

    def _classify_upstream_response(self, http_status: int, mcp_payload: dict) -> tuple[str, str]:
        """
        Classifies upstream response:
        - HTTP >= 500, 408/425/429, or JSON-RPC server error (< 0 except 326xx client errors): EFFECT_INDETERMINATE (ambiguous)
        - HTTP >= 400 or definitive JSON-RPC client errors (-32600..-32602, -32700): REFUTED (definitive client rejection)
        - HTTP 200 with isError: true: EFFECT_INDETERMINATE (tool-level error requires reconciliation)
        - HTTP 200 normal: CONFIRMED (success)
        """
        if http_status >= 500 or http_status in (408, 425, 429) or (http_status < 0 and http_status not in (-32600, -32601, -32602, -32700)):
            return "EFFECT_INDETERMINATE", "ambiguous_upstream_or_transport"
        if http_status in (-32600, -32601, -32602, -32700, 400, 401, 403, 404, 422):
            return "REFUTED", "definitive_client_rejection"
        if http_status >= 400:
            return "REFUTED", "definitive_client_rejection"

        # HTTP 200 but MCP tool-level failure
        if isinstance(mcp_payload, dict) and mcp_payload.get("isError") is True:
            return "EFFECT_INDETERMINATE", "tool_level_error_requires_upstream_reconciliation"

        return "CONFIRMED", "success"

    def _evict_stale_records(self, current_ts: float) -> None:
        """
        SAFETY INVARIANT: Never evict unresolved uncertainty based on retention TTL.
        Unresolved indeterminate records whose deadline has passed are escalated to UNRESOLVED_ESCALATED.
        Only settled records (CONFIRMED, REFUTED) are purged after retention TTL.
        """
        self.conn.execute(
            """
            UPDATE mcp_idempotency 
            SET state = 'UNRESOLVED_ESCALATED' 
            WHERE state = 'EFFECT_INDETERMINATE' 
              AND (? - created_at > ? OR ? > uncertainty_resolution_deadline);
            """,
            (current_ts, self.ttl_sec, current_ts),
        )
        self.conn.execute(
            """
            DELETE FROM mcp_idempotency 
            WHERE state IN ('CONFIRMED', 'REFUTED', 'SUPERSEDED_NOT_APPLIED') 
              AND ? - created_at > ?;
            """,
            (current_ts, self.ttl_sec),
        )

    def handle_raw_frame(self, raw: str | bytes) -> Dict[str, Any]:
        """Strictly parses one inbound JSON-RPC frame (I-JSON profile) and routes it."""
        try:
            frame = loads_strict(raw)
        except RecursionError:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error",
                    "data": {"strict_json_code": "ERR_NESTING_TOO_DEEP", "detail": ""},
                },
            }
        except StrictJSONError as exc:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error",
                    "data": {"strict_json_code": exc.code, "detail": exc.detail},
                },
            }
        if not isinstance(frame, dict):
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request: expected object"},
            }
        return self.handle_json_rpc(frame)

    def handle_json_rpc(self, request_frame: Dict[str, Any]) -> Dict[str, Any]:
        """Routes inbound JSON-RPC frame based on method."""
        method = request_frame.get("method")
        params = request_frame.get("params")

        if method == "tools/call":
            if not isinstance(params, dict):
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32602,
                        "message": "Invalid params: expected object",
                    },
                }
            try:
                self.tool_pin_guard.check_call(params.get("name"), require_pins=False)
            except ToolPinViolation as exc:
                return {"jsonrpc": "2.0", "error": exc.to_jsonrpc_error()}
            return self._handle_tools_call(params)
        elif method == "tools/status":
            if not isinstance(params, dict):
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32602,
                        "message": "Missing required idempotency_key",
                    },
                }
            return self._handle_tools_status(params)
        elif method == "tools/list":
            # Tool advertisements are never passed through unchecked.
            resp = self.upstream(request_frame)
            if "error" in resp:
                return resp
            result = resp.get("result")
            try:
                self.tool_pin_guard.check_advertisement(
                    result.get("tools") if isinstance(result, dict) else None
                )
            except ToolPinViolation as exc:
                return {"jsonrpc": "2.0", "error": exc.to_jsonrpc_error()}
            return resp
        else:
            # Pass-through for non-consequential inspection methods (e.g., resources/list)
            return self.upstream(request_frame)

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()

        # Capability expiration check
        expires_at = params.get("expires_at")
        if expires_at is not None and expires_at < now:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32029,
                    "message": "HALT_CAPABILITY_EXPIRED",
                    "data": {"expires_at": expires_at, "now": now},
                },
            }

        key = params.get("idempotency_key")
        op_id = params.get("operation_id") or key
        tenant_id = params.get("tenant_id", "default_tenant")
        principal = params.get("principal", "default_principal")
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        caid = params.get("caid") or self.compute_caid(args, tool_name=tool_name)
        epoch = params.get("policy_epoch", self.active_policy_epoch)

        binding = None
        if self.effect_key_registry is not None:
            # Effect-key mode: the schema-declared effect CAID is the intent hash; a caller-supplied
            # "caid" is ignored so it cannot steer matching. No schema / bad identity -> refuse.
            try:
                binding = bind_effect_key(tool_name, args, self.effect_key_registry)
            except EffectKeyError as exc:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32095,
                        "message": "EFFECT_KEY_SCHEMA_REJECTED",
                        "data": {"tool": tool_name, "reason": type(exc).__name__, "detail": str(exc)},
                    },
                }
            caid = binding.effect_caid
            if not key:
                key = f"effect:{caid}"
                op_id = params.get("operation_id") or key
        raw_digest = binding.raw_payload_digest if binding is not None else None
        prior_receipt: Optional[Dict[str, Any]] = None

        if not key:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "message": "Missing required idempotency_key",
                },
            }

        # Concurrency Lock + Atomic Transaction (Defeats Thundering Herd)
        with self.lock:
            try:
                self.conn.execute("BEGIN IMMEDIATE;")

                # SAFETY INVARIANT: Evict stale records without ever clearing unresolved uncertainty
                self._evict_stale_records(now)

                # Query matching record by idempotency_key
                row = self.conn.execute(
                    """
                    SELECT idem_key, tenant_id, principal, operation_id, tool_name, caid, state, cached_response, policy_epoch, created_at, uncertainty_resolution_deadline, raw_payload_digest
                    FROM mcp_idempotency 
                    WHERE idem_key = ?;
                    """,
                    (key,),
                ).fetchone()

                if row and row[6] == STATE_SUPERSEDED_NOT_APPLIED:
                    # This key's attempt was settled NOT_APPLIED and superseded; resolve by intent below.
                    row = None

                if row:
                    r_key, r_tenant, r_principal, r_op_id, r_tool, r_caid, state, cached_resp, old_epoch, created_at, deadline, r_raw = row

                    # Payload consistency check: reject reuse of same key with different arguments
                    if r_caid != caid:
                        self.conn.execute("COMMIT;")
                        return {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32602,
                                "message": "IDEMPOTENCY_KEY_REUSE_WITH_DIFFERENT_PAYLOAD",
                                "data": {"idempotency_key": key, "existing_caid": r_caid, "new_caid": caid},
                            },
                        }

                    # Epoch check: if policy epoch rotated and epoch != "unknown"
                    if old_epoch != epoch and epoch != "unknown":
                        if state in ("EFFECT_INDETERMINATE", "UNRESOLVED_ESCALATED"):
                            # Uncertainty must be preserved across epoch rotation; never silently erased!
                            pass
                        else:
                            # Settled records from old epoch may be cleared
                            self.conn.execute(
                                "DELETE FROM mcp_idempotency WHERE idem_key = ?;",
                                (key,),
                            )
                            row = None

                    if row is not None:
                        if state == "CONFIRMED":
                            self.conn.execute("COMMIT;")
                            cached_data = json.loads(cached_resp) if cached_resp else {}
                            return {
                                "jsonrpc": "2.0",
                                "result": cached_data,
                                "meta": {"replay": True, "caid": caid},
                            }
                        elif state == "EFFECT_INDETERMINATE" and self.reconcile_probe_fn is not None:
                            halt, prior_receipt = self._settle_indeterminate(
                                r_key, r_raw, caid, tool_name, args, raw_digest, now)
                            if halt is not None:
                                return halt
                            row = None
                        elif state == "EFFECT_INDETERMINATE":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32009,
                                    "message": "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY",
                                    "data": {
                                        "state": "EFFECT_INDETERMINATE",
                                        "idempotency_key": key,
                                        "caid": caid,
                                    },
                                },
                            }
                        elif state == "UNRESOLVED_ESCALATED":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32010,
                                    "message": "OPERATION_UNRESOLVED_REQUIRES_RECONCILIATION",
                                    "data": {"idempotency_key": key, "state": "UNRESOLVED_ESCALATED"},
                                },
                            }
                        elif state == "REFUTED":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32011,
                                    "message": "OPERATION_PREVIOUSLY_REFUTED",
                                    "data": {"state": "REFUTED", "idempotency_key": key},
                                },
                            }

                if row is None:
                    # Query by composite request intent (tenant_id, principal, tool_name, caid)
                    caid_row = self.conn.execute(
                        """
                        SELECT idem_key, operation_id, state, cached_response, policy_epoch, raw_payload_digest
                        FROM mcp_idempotency
                        WHERE tenant_id = ? AND principal = ? AND tool_name = ? AND caid = ?
                          AND state != 'SUPERSEDED_NOT_APPLIED';
                        """,
                        (tenant_id, principal, tool_name, caid),
                    ).fetchone()

                    if caid_row:
                        c_key, c_op_id, c_state, c_resp, c_epoch, c_raw = caid_row
                        # Disambiguate request-intent digest (CAID) from operation identity
                        has_explicit_op_id = bool(params.get("operation_id"))
                        if (has_explicit_op_id and c_op_id and c_op_id != params.get("operation_id")) or params.get("require_distinct_operation"):
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32012,
                                    "message": "HALT_CAID_OPERATION_IDENTITY_CONFLICT",
                                    "data": {
                                        "caid": caid,
                                        "existing_idem_key": c_key,
                                        "existing_operation_id": c_op_id,
                                        "new_operation_id": op_id,
                                        "action": "CONFLICT_RESOLUTION_REQUIRED",
                                    },
                                },
                            }
                        elif c_state == "CONFIRMED":
                            self.conn.execute("COMMIT;")
                            cached_data = json.loads(c_resp) if c_resp else {}
                            return {
                                "jsonrpc": "2.0",
                                "result": cached_data,
                                "meta": {"replay": True, "caid": caid},
                            }
                        elif c_state == "EFFECT_INDETERMINATE" and self.reconcile_probe_fn is not None:
                            halt, prior_receipt = self._settle_indeterminate(
                                c_key, c_raw, caid, tool_name, args, raw_digest, now)
                            if halt is not None:
                                return halt
                        elif c_state == "EFFECT_INDETERMINATE":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32009,
                                    "message": "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY",
                                    "data": {
                                        "state": "EFFECT_INDETERMINATE",
                                        "idempotency_key": c_key,
                                        "caid": caid,
                                    },
                                },
                            }
                        elif c_state == "UNRESOLVED_ESCALATED":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32010,
                                    "message": "OPERATION_UNRESOLVED_REQUIRES_RECONCILIATION",
                                    "data": {"idempotency_key": c_key},
                                },
                            }
                        elif c_state == "REFUTED":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32011,
                                    "message": "OPERATION_PREVIOUSLY_REFUTED",
                                    "data": {"state": "REFUTED", "idempotency_key": c_key},
                                },
                            }

                # Latch fresh intent as EFFECT_INDETERMINATE before network call (Write-Before-Execute)
                deadline = now + self.uncertainty_deadline_sec
                attempt_no = self._next_attempt_no(tenant_id, principal, tool_name, caid)
                not_after_ms = (int(now * 1000) + self.dispatch_not_after_ms
                                if self.dispatch_not_after_ms is not None else None)
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO mcp_idempotency 
                    (idem_key, tenant_id, principal, operation_id, tool_name, caid, state, policy_epoch, created_at, uncertainty_resolution_deadline, cached_response, raw_payload_digest, settlement_receipt, attempt_no, not_after_ms) 
                    VALUES (?, ?, ?, ?, ?, ?, 'EFFECT_INDETERMINATE', ?, ?, ?, NULL, ?, ?, ?, ?);
                    """,
                    (key, tenant_id, principal, op_id, tool_name, caid, epoch, now, deadline, raw_digest,
                     json.dumps(prior_receipt) if prior_receipt is not None else None, attempt_no, not_after_ms),
                )
                self.conn.execute("COMMIT;")
                self._in_flight_keys.add(key)
            except sqlite3.Error as io_err:
                try:
                    self.conn.execute("ROLLBACK;")
                except Exception:
                    pass
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32027,
                        "message": "HALT_STORAGE_IO_FAILURE_FAILED_CLOSED",
                        "data": {"detail": str(io_err)},
                    },
                }
            except Exception:
                try:
                    self.conn.execute("ROLLBACK;")
                except Exception:
                    pass
                raise

        # Dispatch upstream OUTSIDE the SQLite lock to prevent thread starvation
        # Effect-key mode forwards the effect CAID and the (possibly derived) key so the target can
        # index the effect for read-back.
        forward_params = params if binding is None else {**params, "caid": caid, "idempotency_key": key}
        if binding is not None or self.fence_probe_fn is not None or not_after_ms is not None:
            # Attempt metadata lets the target honour a fence (refuse attempt_no below the fenced
            # number) and a not-after deadline (refuse to execute after it).
            meta = dict(params["_meta"]) if isinstance(params.get("_meta"), dict) else {}
            meta.update({"aeib_caid": caid, "aeib_attempt_no": attempt_no})
            if not_after_ms is not None:
                meta["aeib_not_after_ms"] = not_after_ms
            forward_params = {**forward_params, "_meta": meta}
        try:
            resp = self.upstream(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": forward_params,
                }
            )

            if "result" in resp:
                result_payload = resp["result"]
                state, classification = self._classify_upstream_response(200, result_payload)

                if state == "EFFECT_INDETERMINATE":
                    self._update_state(key, "EFFECT_INDETERMINATE", result_payload)
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32021,
                            "message": "TOOL_ERROR_REQUIRES_RECONCILIATION",
                            "data": {
                                "state": "EFFECT_INDETERMINATE",
                                "idempotency_key": key,
                                "caid": caid,
                                "classification": classification,
                                "tool_result": result_payload,
                            },
                        },
                    }
                else:
                    self._update_state(key, "CONFIRMED", result_payload)
                    return resp
            elif "error" in resp:
                err_code = resp["error"].get("code", 500)
                state, classification = self._classify_upstream_response(err_code, resp["error"])
                self._update_state(key, state, resp.get("error"))
                return resp
            else:
                self._update_state(key, "EFFECT_INDETERMINATE", None)
                return resp

        except (TimeoutError, ConnectionResetError, IOError) as exc:
            self._update_state(key, "EFFECT_INDETERMINATE", None)
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32504,
                    "message": "ERR_EFFECT_INDETERMINATE_LATCHED",
                    "data": {
                        "idempotency_key": key,
                        "caid": caid,
                        "action": "PROBE_REQUIRED",
                        "detail": str(exc),
                    },
                },
            }
        finally:
            with self.lock:
                self._in_flight_keys.discard(key)

    def _update_state(self, key: str, state: str, result_obj: Optional[Dict[str, Any]]) -> None:
        """Updates the state and cached response for an idempotency key in SQLite WAL."""
        with self.lock:
            try:
                resp_str = json.dumps(result_obj) if result_obj is not None else None
                self.conn.execute(
                    "UPDATE mcp_idempotency SET state = ?, cached_response = ? WHERE idem_key = ?;",
                    (state, resp_str, key),
                )
            except Exception:
                pass

    def _handle_tools_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Probes status for an idempotency key to reconcile indeterminate state."""
        key = params.get("idempotency_key")
        if not key:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "message": "Missing required idempotency_key",
                },
            }

        with self.lock:
            row = self.conn.execute(
                "SELECT state, cached_response, caid FROM mcp_idempotency WHERE idem_key = ?;",
                (key,),
            ).fetchone()

        if not row:
            return {
                "jsonrpc": "2.0",
                "result": {"state": "NOT_FOUND", "idempotency_key": key},
            }

        current_state, cached_resp, caid = row

        # If already settled (CONFIRMED or REFUTED), return settled state directly
        if current_state in ("CONFIRMED", "REFUTED"):
            cached_data = json.loads(cached_resp) if cached_resp else None
            return {
                "jsonrpc": "2.0",
                "result": {
                    "state": current_state,
                    "idempotency_key": key,
                    "caid": caid,
                    "cached_response": cached_data,
                },
            }

        # Attempt remote verification if target supports tools/status
        try:
            status_resp = self.upstream(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/status",
                    "params": {"idempotency_key": key},
                }
            )
            if "result" in status_resp:
                remote_state = status_resp["result"].get("state")
                if remote_state in ("CONFIRMED", "REFUTED"):
                    self._update_state(key, remote_state, status_resp["result"].get("response"))
                    current_state = remote_state
                elif remote_state in ("CONTRADICTORY_CONFLICT", "CONFLICT", "UNKNOWN"):
                    # Contradictory probe response preserves uncertainty
                    current_state = "EFFECT_INDETERMINATE"
            elif "error" in status_resp:
                # Upstream error (e.g. METHOD_NOT_FOUND) -> retain EFFECT_INDETERMINATE
                pass
        except Exception:
            # If status probe fails or isn't supported, retain local indeterminate state
            pass

        return {
            "jsonrpc": "2.0",
            "result": {"state": current_state, "idempotency_key": key, "caid": caid},
        }

    def close(self) -> None:
        """Closes the underlying SQLite database connection."""
        try:
            self.conn.close()
        except Exception:
            pass


# Backwards compatibility alias
IdempotentMcpProxyMiddleware = HardenedIdempotentMcpProxy

# Tool definition advertised by the conformance suite's simulated upstream.
SIMULATED_TOOL_DEFINITION = {
    "name": "refund.create",
    "description": "Create a refund.",
    "inputSchema": {"type": "object"},
}


def run_conformance_suite_vectors(
    vectors_file: Path,
    db_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Evaluates the 30-vector conformance suite against HardenedIdempotentMcpProxy.
    Returns structured pass/fail results per vector.
    """
    with open(vectors_file, "r", encoding="utf-8") as f:
        suite_data = json.load(f)

    vectors = suite_data.get("vectors", [])
    results: List[Dict[str, Any]] = []

    base_dir = db_dir or (REPO_ROOT / "output" / "mcp_conformance_dbs")
    base_dir.mkdir(parents=True, exist_ok=True)

    for v in vectors:
        v_id = v["vector_id"]
        v_name = v.get("name", "")

        call_counter = [0]
        upstream_log: List[Dict[str, Any]] = []

        def make_simulated_upstream(vector_def: Dict[str, Any]):
            def simulated_transport(req: Dict[str, Any]) -> Dict[str, Any]:
                upstream_log.append(req)
                method = req.get("method")
                behavior = vector_def.get("simulate_upstream") or vector_def.get("server_behavior")

                if method == "tools/call":
                    call_counter[0] += 1
                    # Sequence-based behavior
                    if "sequence" in vector_def:
                        seq_idx = min(call_counter[0] - 1, len(vector_def["sequence"]) - 1)
                        step = vector_def["sequence"][seq_idx]
                        step_sim = step.get("simulate_upstream") or step.get("server_behavior", "NORMAL_200")
                        if step_sim == "TIMEOUT":
                            raise TimeoutError("Simulated upstream 504 Gateway Timeout")
                        elif step_sim == "UPSTREAM_ERROR_400":
                            return {"error": {"code": 400, "message": "Bad Request"}}
                        elif step_sim == "UPSTREAM_ERROR_408":
                            return {"error": {"code": 408, "message": "Request Timeout"}}
                        elif step_sim == "UPSTREAM_ERROR_429":
                            return {"error": {"code": 429, "message": "Too Many Requests"}}
                        elif "simulate_tool_is_error" in step:
                            return {"result": step["simulate_tool_is_error"]}
                        return {"result": {"status": "SUCCESS", "step": seq_idx}}

                    if behavior == "TIMEOUT":
                        raise TimeoutError("Simulated upstream 504 Gateway Timeout")
                    elif "simulate_tool_is_error" in vector_def:
                        return {"result": vector_def["simulate_tool_is_error"]}
                    elif "simulate_upstream_error" in vector_def:
                        return {"error": vector_def["simulate_upstream_error"]}
                    return {"result": {"status": "SUCCESS"}}

                elif method == "tools/status":
                    if "sequence" in vector_def:
                        for s in vector_def["sequence"]:
                            if s.get("method") == "tools/status" and "simulate_remote_status" in s:
                                resp = s["simulate_remote_status"]
                                if "error" in resp:
                                    return {"error": {"code": -32601, "message": resp["error"]}}
                                return {"result": resp}
                    if "simulate_remote_status" in vector_def:
                        resp = vector_def["simulate_remote_status"]
                        if "error" in resp:
                            return {"error": {"code": -32601, "message": resp["error"]}}
                        return {"result": resp}
                    return {"result": {"state": "CONFIRMED"}}

                elif method == "tools/list":
                    return {"result": {"tools": [dict(SIMULATED_TOOL_DEFINITION)]}}

                return {"error": {"code": -32601, "message": "Method not found"}}

            return simulated_transport

        db_file = base_dir / f"mcp_{v_id}.db"
        if db_file.exists():
            db_file.unlink()

        proxy = HardenedIdempotentMcpProxy(
            upstream_transport_fn=make_simulated_upstream(v),
            db_path=db_file,
        )

        passed = False
        reason = ""

        try:
            if v_id == "mcp-vec-001":
                res = proxy.handle_json_rpc(v["input"])
                passed = "result" in res and res["result"].get("status") == "SUCCESS"

            elif v_id == "mcp-vec-002":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "result" in res2
                    and res2.get("meta", {}).get("replay") is True
                    and len(upstream_log) == 1
                )

            elif v_id == "mcp-vec-003":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "result" in res2
                    and res2.get("meta", {}).get("replay") is True
                    and len(upstream_log) == 1
                )

            elif v_id == "mcp-vec-004":
                res = proxy.handle_json_rpc(v["input"])
                passed = (
                    "error" in res
                    and "ERR_EFFECT_INDETERMINATE_LATCHED" in res["error"]["message"]
                )

            elif v_id == "mcp-vec-005":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "error" in res2
                    and "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY" in res2["error"]["message"]
                )

            elif v_id == "mcp-vec-006":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = "result" in res2 and res2["result"].get("state") == "CONFIRMED"

            elif v_id == "mcp-vec-007":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = "result" in res2 and res2["result"].get("state") == "REFUTED"

            elif v_id == "mcp-vec-008":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "result" in res2
                    and res2["result"].get("state") == "EFFECT_INDETERMINATE"
                )

            elif v_id == "mcp-vec-009":
                # Pre-populate expired record from previous epoch
                old_now = time.time() - 100000
                proxy.conn.execute(
                    """
                    INSERT INTO mcp_idempotency (idem_key, caid, tool_name, state, policy_epoch, created_at, cached_response)
                    VALUES (?, ?, ?, 'CONFIRMED', ?, ?, ?);
                    """,
                    ("k-009", "sha256:old", "refund.create", v["simulate_expired_record_with_epoch"], old_now, json.dumps({"status": "OLD"})),
                )
                proxy.ttl_sec = 1000
                res = proxy.handle_json_rpc(v["input"])
                passed = "result" in res and res["result"].get("status") == "SUCCESS"

            elif v_id == "mcp-vec-010":
                # Server crash recovery simulation
                # 1. First proxy run writes in-flight record to SQLite WAL
                proxy.conn.execute(
                    """
                    INSERT INTO mcp_idempotency (idem_key, caid, tool_name, state, policy_epoch, created_at)
                    VALUES (?, ?, ?, 'EFFECT_INDETERMINATE', 'epoch-2026-Q4', ?);
                    """,
                    ("k-010", "sha256:1010", "refund.create", time.time()),
                )
                proxy.close()

                # 2. Reboot new proxy pointing to same SQLite database
                proxy_reboot = HardenedIdempotentMcpProxy(
                    upstream_transport_fn=make_simulated_upstream(v),
                    db_path=db_file,
                )
                # Attempt retry on rebooted proxy
                res = proxy_reboot.handle_json_rpc(v["input"])
                passed = (
                    "error" in res
                    and "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY" in res["error"]["message"]
                )
                proxy_reboot.close()

            elif v_id == "mcp-vec-011":
                res = proxy.handle_json_rpc(v["input"])
                passed = "error" in res and res["error"]["code"] == -32602

            elif v_id == "mcp-vec-012":
                res = proxy.handle_json_rpc(v["input"])
                row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-012';").fetchone()
                passed = row is not None and row[0] == "EFFECT_INDETERMINATE"

            elif v_id == "mcp-vec-013":
                res = proxy.handle_json_rpc(v["input"])
                row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-013';").fetchone()
                passed = row is not None and row[0] == "REFUTED"

            elif v_id == "mcp-vec-014":
                res = proxy.handle_json_rpc(v["input"])
                passed = "error" in res and res["error"]["code"] == -32602

            elif v_id == "mcp-vec-015":
                # Concurrency stress test: 10 concurrent threads
                def worker():
                    return proxy.handle_json_rpc(
                        {
                            "method": "tools/call",
                            "params": {
                                "name": "refund.create",
                                "arguments": {"amount_minor": 1000},
                                "idempotency_key": v["idempotency_key"],
                            },
                        }
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(worker) for _ in range(10)]
                    responses = [f.result() for f in futures]

                # Exactly 1 should have reached upstream
                passed = len(upstream_log) == 1

            elif v_id == "mcp-vec-016":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = len(upstream_log) == 2

            elif v_id == "mcp-vec-017":
                # tools/list is pass-through only for a pinned advertisement; the same
                # advertisement without approved pins is refused (no silent pass-through).
                res = proxy.handle_json_rpc(v["input"])
                pins = ToolDefinitionPinSet()
                pins.pin_server("upstream", [dict(SIMULATED_TOOL_DEFINITION)])
                pinned_proxy = HardenedIdempotentMcpProxy(
                    upstream_transport_fn=make_simulated_upstream(v), tool_pins=pins
                )
                try:
                    pinned_res = pinned_proxy.handle_json_rpc(v["input"])
                finally:
                    pinned_proxy.close()
                passed = (
                    "result" in pinned_res
                    and "tools" in pinned_res["result"]
                    and res.get("error", {}).get("code") == -32040
                )

            elif v_id == "mcp-vec-018":
                res = proxy.handle_json_rpc(v["input"])
                passed = "error" in res and res["error"]["code"] == -32602

            elif v_id == "mcp-vec-019":
                res = proxy.handle_json_rpc(v["input"])
                passed = "result" in res and res["result"].get("state") == "NOT_FOUND"

            elif v_id == "mcp-vec-020":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = "result" in res2 and res2["result"].get("status") == "SUCCESS"

            elif v_id == "mcp-vec-021":
                res = proxy.handle_json_rpc(v["input"])
                row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-021';").fetchone()
                passed = (
                    "error" in res
                    and res["error"].get("message") == "TOOL_ERROR_REQUIRES_RECONCILIATION"
                    and row is not None
                    and row[0] == "EFFECT_INDETERMINATE"
                )

            elif v_id == "mcp-vec-022":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "error" in res2
                    and "HALT_CAID_OPERATION_IDENTITY_CONFLICT" in res2["error"].get("message", "")
                )

            elif v_id == "mcp-vec-023":
                # Pre-populate expired indeterminate record
                old_time = time.time() - 100000
                proxy.conn.execute(
                    """
                    INSERT INTO mcp_idempotency 
                    (idem_key, tenant_id, principal, operation_id, tool_name, caid, state, policy_epoch, created_at, uncertainty_resolution_deadline)
                    VALUES (?, 'default_tenant', 'default_principal', 'op-023', 'refund.create', 'sha256:2323', 'EFFECT_INDETERMINATE', 'epoch-2026-Q4', ?, ?);
                    """,
                    ("k-023", old_time, old_time + 60),
                )
                proxy.ttl_sec = 1000
                res = proxy.handle_json_rpc(v["input"])
                row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-023';").fetchone()
                passed = (
                    "error" in res
                    and "OPERATION_UNRESOLVED_REQUIRES_RECONCILIATION" in res["error"]["message"]
                    and row is not None
                    and row[0] == "UNRESOLVED_ESCALATED"
                )

            elif v_id == "mcp-vec-024":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-024';").fetchone()
                passed = (
                    "error" in res2
                    and "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY" in res2["error"]["message"]
                    and row is not None
                    and row[0] == "EFFECT_INDETERMINATE"
                )

            elif v_id == "mcp-vec-025":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                forwarded_keys = [
                    req.get("params", {}).get("idempotency_key")
                    for req in upstream_log
                    if "params" in req
                ]
                passed = (
                    len(forwarded_keys) >= 2
                    and all(k == "k-025-stable" for k in forwarded_keys)
                    and "result" in res2
                    and res2["result"].get("state") == "CONFIRMED"
                )

            elif v_id == "mcp-vec-026":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "result" in res2
                    and res2["result"].get("state") == "EFFECT_INDETERMINATE"
                )

            elif v_id == "mcp-vec-027":
                proxy.conn.close()
                class BrokenConn:
                    def execute(self, *args, **kwargs):
                        raise sqlite3.OperationalError("disk I/O error or filesystem full")
                proxy.conn = BrokenConn()
                res = proxy.handle_json_rpc(v["input"])
                passed = (
                    "error" in res
                    and "HALT_STORAGE_IO_FAILURE_FAILED_CLOSED" in res["error"]["message"]
                    and len(upstream_log) == 0
                )

            elif v_id == "mcp-vec-028":
                future_time = time.time() + 1000
                target_caid = proxy.compute_caid(v["input"]["params"]["arguments"], tool_name="refund.create")
                proxy.conn.execute(
                    """
                    INSERT INTO mcp_idempotency 
                    (idem_key, tenant_id, principal, operation_id, tool_name, caid, state, policy_epoch, created_at, uncertainty_resolution_deadline)
                    VALUES (?, 'default_tenant', 'default_principal', 'op-028', 'refund.create', ?, 'EFFECT_INDETERMINATE', 'epoch-2026-Q4', ?, ?);
                    """,
                    ("k-028", target_caid, future_time, future_time + 300),
                )
                res = proxy.handle_json_rpc(v["input"])
                passed = (
                    "error" in res
                    and "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY" in res["error"]["message"]
                )

            elif v_id == "mcp-vec-029":
                res = proxy.handle_json_rpc(v["input"])
                passed = (
                    "error" in res
                    and "HALT_CAPABILITY_EXPIRED" in res["error"]["message"]
                    and len(upstream_log) == 0
                )

            elif v_id == "mcp-vec-030":
                def worker():
                    return proxy.handle_json_rpc(
                        {
                            "method": "tools/call",
                            "params": {
                                "name": "refund.create",
                                "arguments": {"amount_minor": 1000},
                                "idempotency_key": v["idempotency_key"],
                            },
                        }
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    futures = [executor.submit(worker) for _ in range(8)]
                    responses = [f.result() for f in futures]

                passed = len(upstream_log) == 1 and all("result" in r or "error" in r for r in responses)

        except Exception as exc:
            passed = False
            reason = str(exc)
        finally:
            proxy.close()
            if db_file.exists():
                try:
                    db_file.unlink()
                except Exception:
                    pass

        results.append(
            {
                "vector_id": v_id,
                "name": v_name,
                "passed": passed,
                "reason": reason if not passed else "OK",
            }
        )

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "suite": suite_data.get("conformance_suite", "mcp_idempotency.vectors.v1"),
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "pass_rate_pct": round((passed_count / max(1, len(results))) * 100.0, 2),
        "results": results,
    }


def main() -> int:
    vectors_path = REPO_ROOT / "conformance" / "vectors" / "mcp_idempotency.vectors.v1.json"
    if not vectors_path.exists():
        print(f"Error: Conformance vectors not found at {vectors_path}", file=sys.stderr)
        return 1

    report = run_conformance_suite_vectors(vectors_path)
    print("================================================================================")
    print("       HARDENED IDEMPOTENT MCP PROXY — CONFORMANCE SUITE REPORT               ")
    print("================================================================================")
    print(f"Suite:           {report['suite']}")
    print(f"Total Vectors:   {report['total']}")
    print(f"Passed:          {report['passed']}")
    print(f"Failed:          {report['failed']}")
    print(f"Pass Rate:       {report['pass_rate_pct']}%")
    print("--------------------------------------------------------------------------------")
    for r in report["results"]:
        status = "PASSED" if r["passed"] else "FAILED"
        print(f"[{status}] {r['vector_id']:<14} : {r['name']}")
    print("================================================================================")

    # Write output artifact
    out_dir = REPO_ROOT / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "mcp-conformance-report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
