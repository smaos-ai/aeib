"""
src/runtime_boundary/runtime_execution_boundary.py
================================================================================
AEIB Track A: Full-Stack Runtime Authorization & 8-State Effect Machine

Enforces deterministic runtime boundaries between agent proposals and external effects:
1. Persistent Agent Identity: Agent identity persists across sessions and runs.
2. Permission Epoch: Capability warrants bound to policy epoch, per-call and daily caps.
3. Content-Addressed Action Identifier (CAID): Binds target, action, resource, and args.
4. Write-Ahead Intent Persistence: Persists intent in SQLite WAL before dispatch.
5. 8-State Effect State Machine:
   PROPOSED -> AUTHORIZED -> INTENT_PERSISTED -> DISPATCHED ->
   CONFIRMED | REFUTED | EFFECT_INDETERMINATE -> UNRESOLVED_ESCALATED
6. Uncertainty Latch: Latches HTTP 5xx / timeouts into EFFECT_INDETERMINATE and
   blocks blind retries.
7. Bounded Reconciliation: Authoritatively settles indeterminate records.
8. Fail-Closed Circuit Breaker: Halts all consequential execution upon integrity breach.

Epistemic Calibration:
  Observed, tested, and evaluated under the stated local fault model.
  Zero mock primitives; real Ed25519 signatures, RFC 8785 canonical JSON, and SQLite WAL.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization

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
    """Deterministic canonical JSON serialization conforming to RFC 8785."""
    if isinstance(obj, float):
        raise ValueError("ERR_FLOAT_FORBIDDEN_IN_CANONICAL_ACT")
    return _reference_encode_jcs(obj)


# ============================================================================
# 1. PERSISTENT AGENT IDENTITY & PERMISSION EPOCH
# ============================================================================
@dataclass(frozen=True)
class PersistentAgentIdentity:
    agent_id: str
    principal_id: str
    public_key_pem: str
    created_at: int
    status: str = "ACTIVE"  # "ACTIVE" | "SUSPENDED" | "REVOKED"


@dataclass(frozen=True)
class PermissionEpoch:
    capability_id: str
    agent_id: str
    scope: str
    max_per_call_minor: int
    daily_ceiling_minor: int
    policy_epoch: str
    issued_at: int
    expires_at: int
    status: str = "ACTIVE"  # "ACTIVE" | "SUPERSEDED" | "REVOKED"


# ============================================================================
# 2. 8-STATE EFFECT STATE MACHINE CONSTANTS
# ============================================================================
class EffectState:
    PROPOSED = "PROPOSED"
    AUTHORIZED = "AUTHORIZED"
    INTENT_PERSISTED = "INTENT_PERSISTED"
    DISPATCHED = "DISPATCHED"
    CONFIRMED = "CONFIRMED"
    REFUTED = "REFUTED"
    EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"
    UNRESOLVED_ESCALATED = "UNRESOLVED_ESCALATED"

    VALID_STATES = frozenset(
        {
            PROPOSED,
            AUTHORIZED,
            INTENT_PERSISTED,
            DISPATCHED,
            CONFIRMED,
            REFUTED,
            EFFECT_INDETERMINATE,
            UNRESOLVED_ESCALATED,
        }
    )


# ============================================================================
# 3. RUNTIME EXECUTION BOUNDARY IMPLEMENTATION
# ============================================================================
class RuntimeExecutionBoundary:
    """
    Station 1 Pre-Dispatch & Station 2 Reconciliation Boundary.
    Enforces write-before-execute, durable uncertainty latching, and budget solvency.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self.halted_reason: Optional[str] = None

    def _init_schema(self) -> None:
        self.conn.commit()
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=FULL;")
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    public_key_pem TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    status TEXT NOT NULL
                );
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capabilities (
                    capability_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    max_per_call_minor INTEGER NOT NULL,
                    daily_ceiling_minor INTEGER NOT NULL,
                    policy_epoch TEXT NOT NULL,
                    issued_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                );
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS intent_ledger (
                    operation_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    capability_id TEXT NOT NULL,
                    act_caid TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    amount_minor INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    policy_epoch TEXT NOT NULL,
                    payload_canonical TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    reconciliation_attempts INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id),
                    FOREIGN KEY (capability_id) REFERENCES capabilities (capability_id)
                );
                """
            )

    def register_agent(self, agent: PersistentAgentIdentity) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO agents (agent_id, principal_id, public_key_pem, created_at, status)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    agent.agent_id,
                    agent.principal_id,
                    agent.public_key_pem,
                    agent.created_at,
                    agent.status,
                ),
            )

    def register_capability(self, cap: PermissionEpoch) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO capabilities (
                    capability_id, agent_id, scope, max_per_call_minor,
                    daily_ceiling_minor, policy_epoch, issued_at, expires_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    cap.capability_id,
                    cap.agent_id,
                    cap.scope,
                    cap.max_per_call_minor,
                    cap.daily_ceiling_minor,
                    cap.policy_epoch,
                    cap.issued_at,
                    cap.expires_at,
                    cap.status,
                ),
            )

    def revoke_capability(self, capability_id: str, reason: str = "REVOKED") -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE capabilities SET status = ? WHERE capability_id = ?;",
                (reason, capability_id),
            )

    def trigger_halt(self, reason: str) -> None:
        """Fails closed: stops all consequential authorizations."""
        self.halted_reason = reason

    @staticmethod
    def compute_act_caid(act_core: Dict[str, Any]) -> str:
        """
        Computes the canonical Content-Addressed Action Identifier (CAID).
        Binds target, action, resource, amount_minor, and args_digest.
        """
        required = ("action_type", "target", "operation_id", "amount_minor")
        for k in required:
            if k not in act_core:
                raise ValueError(f"ERR_MISSING_REQUIRED_CAID_FIELD_{k.upper()}")
        canonical_bytes = canonical_json_bytes(act_core)
        return f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"

    def get_budget_exposure(self, agent_id: str) -> Dict[str, int]:
        """Calculates active reserved and settled exposure for an agent."""
        rows = self.conn.execute(
            """
            SELECT state, amount_minor FROM intent_ledger
            WHERE agent_id = ?;
            """,
            (agent_id,),
        ).fetchall()
        reserved = 0
        settled = 0
        for r in rows:
            st = r["state"]
            amt = r["amount_minor"]
            if st in (EffectState.INTENT_PERSISTED, EffectState.DISPATCHED, EffectState.EFFECT_INDETERMINATE, EffectState.UNRESOLVED_ESCALATED):
                reserved += amt
            elif st == EffectState.CONFIRMED:
                settled += amt
        return {
            "reserved_minor": reserved,
            "settled_minor": settled,
            "active_exposure_minor": reserved + settled,
        }

    def authorize_and_persist_intent(
        self,
        signed_act_envelope: Dict[str, Any],
        current_time: int,
    ) -> Dict[str, Any]:
        """
        Station 1 Pre-Dispatch:
        1. Checks circuit breaker (halted_reason).
        2. Validates Agent Identity and active status.
        3. Validates Permission Epoch and active status.
        4. Verifies CAID.
        5. Verifies cryptographic Ed25519 signature over canonical Act.
        6. Enforces per-call attenuation and daily ceiling budget.
        7. Checks for existing operation_id and latched EFFECT_INDETERMINATE states.
        8. Atomically persists intent in SQLite WAL under BEGIN IMMEDIATE.
        """
        if self.halted_reason is not None:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": f"HALT_CIRCUIT_BREAKER_ACTIVE:{self.halted_reason}",
                "state": EffectState.PROPOSED,
            }

        act_core = signed_act_envelope.get("act_core")
        sig_info = signed_act_envelope.get("signature", {})
        if not isinstance(act_core, dict) or not isinstance(sig_info, dict):
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_MALFORMED_ACT_ENVELOPE",
                "state": EffectState.PROPOSED,
            }

        try:
            caid = self.compute_act_caid(act_core)
        except ValueError as exc:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": str(exc),
                "state": EffectState.PROPOSED,
            }

        agent_id = str(act_core.get("agent_id", ""))
        capability_id = str(act_core.get("capability_id", ""))
        operation_id = str(act_core.get("operation_id", ""))
        action_type = str(act_core.get("action_type", ""))
        target = str(act_core.get("target", ""))
        amt = act_core.get("amount_minor")

        if not agent_id or not capability_id or not operation_id:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_MISSING_AGENT_OR_CAPABILITY_IDENTITY",
                "state": EffectState.PROPOSED,
            }

        if isinstance(amt, bool) or not isinstance(amt, int) or amt < 0:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_INVALID_AMOUNT_MINOR",
                "state": EffectState.PROPOSED,
            }

        # 1. Verify Agent Identity
        agent_row = self.conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?;", (agent_id,)
        ).fetchone()
        if not agent_row or agent_row["status"] != "ACTIVE":
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_AGENT_NOT_ACTIVE_OR_UNREGISTERED",
                "state": EffectState.PROPOSED,
            }

        # 2. Verify Capability / Permission Epoch
        cap_row = self.conn.execute(
            "SELECT * FROM capabilities WHERE capability_id = ? AND agent_id = ?;",
            (capability_id, agent_id),
        ).fetchone()
        if not cap_row or cap_row["status"] != "ACTIVE":
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_CAPABILITY_REVOKED_OR_EXPIRED",
                "state": EffectState.PROPOSED,
            }

        if current_time > cap_row["expires_at"] or current_time < cap_row["issued_at"]:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_POLICY_EPOCH_EXPIRED",
                "state": EffectState.PROPOSED,
            }

        if action_type != cap_row["scope"]:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_ACTION_NOT_IN_CAPABILITY_SCOPE",
                "state": EffectState.PROPOSED,
            }

        if amt > cap_row["max_per_call_minor"]:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_AMOUNT_EXCEEDS_PER_CALL_CAP",
                "state": EffectState.PROPOSED,
            }

        # 3. Verify Ed25519 signature
        pub_pem = agent_row["public_key_pem"].encode("utf-8")
        try:
            pub_key = serialization.load_pem_public_key(pub_pem)
            if not isinstance(pub_key, Ed25519PublicKey):
                raise ValueError("Expected Ed25519 key")
            sig_bytes = bytes.fromhex(sig_info.get("value", ""))
            act_canonical_bytes = canonical_json_bytes(act_core)
            pub_key.verify(sig_bytes, act_canonical_bytes)
        except Exception:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_INVALID_ACT_ED25519_SIGNATURE",
                "state": EffectState.PROPOSED,
            }

        # 4. Atomic SQLite WAL transaction
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE;")
            existing = self.conn.execute(
                "SELECT state FROM intent_ledger WHERE operation_id = ?;",
                (operation_id,),
            ).fetchone()

            if existing:
                st = existing["state"]
                if st == EffectState.EFFECT_INDETERMINATE:
                    return {
                        "disposition": "NOT_DISPATCHED",
                        "code": "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY",
                        "state": st,
                    }
                return {
                    "disposition": "ALREADY_COMMITTED",
                    "code": f"IDEMPOTENT_DUPLICATE_OPERATION_IN_STATE_{st}",
                    "state": st,
                }

            # Verify daily ceiling
            exposure = self.get_budget_exposure(agent_id)
            if exposure["active_exposure_minor"] + amt > cap_row["daily_ceiling_minor"]:
                return {
                    "disposition": "NOT_DISPATCHED",
                    "code": "ERR_DAILY_CEILING_EXCEEDED",
                    "state": EffectState.PROPOSED,
                }

            # Persist Intent
            canonical_payload_str = canonical_json_bytes(act_core).decode("utf-8")
            self.conn.execute(
                """
                INSERT INTO intent_ledger (
                    operation_id, agent_id, capability_id, act_caid, action_type,
                    target, amount_minor, state, policy_epoch, payload_canonical,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    operation_id,
                    agent_id,
                    capability_id,
                    caid,
                    action_type,
                    target,
                    amt,
                    EffectState.INTENT_PERSISTED,
                    cap_row["policy_epoch"],
                    canonical_payload_str,
                    current_time,
                    current_time,
                ),
            )

        return {
            "disposition": "AUTHORIZED_AND_INTENT_PERSISTED",
            "code": "OK",
            "operation_id": operation_id,
            "caid": caid,
            "state": EffectState.INTENT_PERSISTED,
        }

    def mark_dispatched(self, operation_id: str, current_time: int) -> None:
        """Advances state from INTENT_PERSISTED to DISPATCHED right before socket write."""
        with self.conn:
            self.conn.execute(
                """
                UPDATE intent_ledger
                SET state = ?, updated_at = ?
                WHERE operation_id = ? AND state = ?;
                """,
                (EffectState.DISPATCHED, current_time, operation_id, EffectState.INTENT_PERSISTED),
            )

    def record_effect_outcome(
        self,
        operation_id: str,
        http_status: Optional[int],
        current_time: int,
        authoritative_reconciliation: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Station 2 Reconciliation:
        - 200..299 -> CONFIRMED
        - 400..499 -> REFUTED
        - 500..599 or None (timeout / connection drop) -> EFFECT_INDETERMINATE
        - authoritative_reconciliation: settles EFFECT_INDETERMINATE into CONFIRMED or REFUTED.
        """
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE;")
            row = self.conn.execute(
                "SELECT state, reconciliation_attempts FROM intent_ledger WHERE operation_id = ?;",
                (operation_id,),
            ).fetchone()
            if not row:
                return {"disposition": "UNKNOWN_OPERATION", "state": "UNKNOWN"}

            current_state = row["state"]
            reconcile_count = row["reconciliation_attempts"]

            if authoritative_reconciliation in ("CONFIRMED", "REFUTED"):
                target_state = (
                    EffectState.CONFIRMED
                    if authoritative_reconciliation == "CONFIRMED"
                    else EffectState.REFUTED
                )
                self.conn.execute(
                    """
                    UPDATE intent_ledger
                    SET state = ?, updated_at = ?
                    WHERE operation_id = ?;
                    """,
                    (target_state, current_time, operation_id),
                )
                return {"disposition": "RECONCILED", "state": target_state}

            if http_status is not None and 200 <= http_status < 300:
                self.conn.execute(
                    """
                    UPDATE intent_ledger
                    SET state = ?, updated_at = ?
                    WHERE operation_id = ?;
                    """,
                    (EffectState.CONFIRMED, current_time, operation_id),
                )
                return {"disposition": "CONFIRMED", "state": EffectState.CONFIRMED}

            if http_status is not None and 400 <= http_status < 500:
                self.conn.execute(
                    """
                    UPDATE intent_ledger
                    SET state = ?, updated_at = ?
                    WHERE operation_id = ?;
                    """,
                    (EffectState.REFUTED, current_time, operation_id),
                )
                return {"disposition": "REFUTED", "state": EffectState.REFUTED}

            # Timeout, connection drop, or HTTP 5xx -> Enter or remain in EFFECT_INDETERMINATE
            new_reconcile_count = reconcile_count + 1
            new_state = (
                EffectState.UNRESOLVED_ESCALATED
                if new_reconcile_count >= 5
                else EffectState.EFFECT_INDETERMINATE
            )
            self.conn.execute(
                """
                UPDATE intent_ledger
                SET state = ?, reconciliation_attempts = ?, updated_at = ?
                WHERE operation_id = ?;
                """,
                (new_state, new_reconcile_count, current_time, operation_id),
            )
            return {"disposition": "LATCHED_UNCERTAINTY", "state": new_state}
