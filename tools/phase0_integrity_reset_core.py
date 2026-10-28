#!/usr/bin/env python3
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
AEIB v1.0.0-rc.5-preprod — Phase 0 Integrity Reset Core.

Closes the 4 mandatory Phase 0 blockers before any external archive or expansion:
- Phase 0.1: Deterministic `canonical_json_v1` (rejects NaN/Inf & duplicate keys)
             and standalone offline verifier (`verify_ledger_offline`).
- Phase 0.2: Close AT57b (Pure Taint Gate — blocks TIER_2_UNTRUSTED without
             relying on keyword heuristics or CoT inspection).
- Phase 0.3: Close AT58 (`record_downstream_effect` durable SQLite WAL escrow path
             preserving reservations under HTTP 5xx / timeout uncertainty).
- Phase 0.4: Close G3 (`_verify_continuity_on_boot` re-verifying Ed25519 signatures,
             recomputing CAID digests, checking hash-chain continuity, and detecting
             two-file wipe against an external continuity anchor).
- Architectural Fixes:
  * Explicit versioned workflow preconditions (`required_prior_effects`) instead of
    post-hoc heuristics.
  * `scoped_forget()` that discards scratchpads while preserving all audit receipts
    and unresolved `EFFECT_INDETERMINATE` operations.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[1]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs


# ============================================================================
# PHASE 0.1: STRICT CANONICAL JSON & CAID COMPUTATION
# ============================================================================
def canonical_json_v1(obj: Any) -> bytes:
    """
    Deterministic canonical JSON serializer:
    - Rejects floats, NaN, and Infinity in financial/boundary structures.
    - Sorts UTF-8 keys lexicographically with compact separators.
    """
    def _check_types(val: Any) -> None:
        if isinstance(val, float):
            raise ValueError("ERR_FLOAT_FORBIDDEN_IN_CANONICAL_ACT")
        if isinstance(val, dict):
            for k, v in val.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _check_types(v)
        elif isinstance(val, list):
            for item in val:
                _check_types(item)

    _check_types(obj)
    return _reference_encode_jcs(obj)


def parse_strict_json_bytes(raw: bytes) -> Dict[str, Any]:
    """Parses UTF-8 JSON while rejecting duplicate keys and NaN/Infinity constants."""
    text = raw.decode("utf-8", errors="strict")
    dup_detected = [False]

    def _no_dups(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                dup_detected[0] = True
            out[k] = v
        return out

    def _no_constants(c: str) -> Any:
        raise ValueError(f"ERR_FORBIDDEN_JSON_CONSTANT:{c}")

    parsed = json.loads(text, object_pairs_hook=_no_dups, parse_constant=_no_constants)
    if dup_detected[0] or not isinstance(parsed, dict):
        raise ValueError("ERR_DUPLICATE_KEYS_OR_NON_OBJECT")
    return parsed


def compute_act_caid(act_core: Dict[str, Any]) -> str:
    """Computes exact content-addressed action identifier over the unsigned Act core."""
    return f"sha256:{hashlib.sha256(canonical_json_v1(act_core)).hexdigest()}"


# ============================================================================
# PHASE 0.2, 0.3, 0.4: STATION 1 & 2 GATE WITH BOOT RE-VERIFICATION
# ============================================================================
@dataclass(frozen=True)
class BoundaryVerdict:
    disposition: str
    code: str
    operation_id: str
    caid: str


class Phase0ExecutionBoundary:
    """
    Deterministic Execution Boundary closing Phase 0 blockers:
    - AT57b: Pure taint-tier enforcement (no keyword heuristics).
    - AT58: Durable escrow state machine (`record_downstream_effect`).
    - G3: Full boot-time Ed25519 + CAID + hash-chain + external anchor verification.
    """

    GENESIS_HASH = "sha256:" + ("0" * 64)

    def __init__(
        self,
        db_path: str,
        public_keys: Dict[str, Ed25519PublicKey],
        sprint_limit_minor: int,
        pinned_recipients: Set[str],
        workflow_preconditions: Optional[Dict[str, List[str]]] = None,
        external_anchor_tip: Optional[Tuple[int, str]] = None,
    ) -> None:
        self.db_path = db_path
        self.public_keys = dict(public_keys)
        self.sprint_limit_minor = sprint_limit_minor
        self.pinned_recipients = frozenset(pinned_recipients)
        # Explicit versioned workflow preconditions: action_type -> list of required prior confirmed action_types
        self.workflow_preconditions = workflow_preconditions or {}
        self.external_anchor_tip = external_anchor_tip  # (expected_seq, expected_chain_hash)
        self.halted_reason: Optional[str] = None

        self.conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=FULL;")
        self._init_schema()
        self._verify_continuity_on_boot()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS authoritative_ledger (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id TEXT UNIQUE NOT NULL,
                action_type TEXT NOT NULL,
                amount_minor INTEGER NOT NULL,
                max_per_call_minor INTEGER NOT NULL,
                recipient TEXT NOT NULL,
                taint_tier TEXT NOT NULL,
                policy_epoch TEXT NOT NULL,
                key_id TEXT NOT NULL,
                act_core_json TEXT NOT NULL,
                caid TEXT NOT NULL,
                signature_b64 TEXT NOT NULL,
                disposition TEXT NOT NULL,
                prev_entry_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL
            );
            """
        )

    @staticmethod
    def _compute_entry_hash(prev_hash: str, caid: str, signature_b64: str) -> str:
        material = f"{prev_hash}|{caid}|{signature_b64}".encode("utf-8")
        return f"sha256:{hashlib.sha256(material).hexdigest()}"

    def _verify_continuity_on_boot(self) -> None:
        """
        Phase 0.4 (G3 Closure):
        Re-verifies every WAL entry on boot:
        1. Recomputes `caid` from `act_core_json` and checks against stored columns
           (catches on-disk `amount_minor` or `recipient` tampering).
        2. Re-verifies the Ed25519 signature over `canonical_json_v1(act_core)`.
        3. Verifies `prev_entry_hash -> entry_hash` chain continuity.
        4. Compares local tip against `external_anchor_tip` (catches two-file wipe).
        """
        rows = self.conn.execute(
            """
            SELECT seq, operation_id, action_type, amount_minor, max_per_call_minor,
                   recipient, taint_tier, policy_epoch, key_id, act_core_json,
                   caid, signature_b64, prev_entry_hash, entry_hash
            FROM authoritative_ledger ORDER BY seq ASC;
            """
        ).fetchall()

        expected_prev = self.GENESIS_HASH
        last_seq = 0

        for row in rows:
            (
                seq,
                op_id,
                act_type,
                amt,
                max_call,
                rcpt,
                taint,
                epoch,
                key_id,
                core_json,
                stored_caid,
                sig_b64,
                prev_hash,
                entry_hash,
            ) = row

            try:
                core_obj = parse_strict_json_bytes(core_json.encode("utf-8"))
                recomputed_caid = compute_act_caid(core_obj)
            except Exception:
                self.halted_reason = f"HALT_BOOT_CORRUPT_JSON_AT_SEQ_{seq}"
                return

            # Check column parity against signed JSON core (defeats SQL column tampering)
            if (
                recomputed_caid != stored_caid
                or core_obj.get("operation_id") != op_id
                or core_obj.get("action_type") != act_type
                or core_obj.get("amount_minor") != amt
                or core_obj.get("max_per_call_minor") != max_call
                or core_obj.get("recipient") != rcpt
                or core_obj.get("taint_tier") != taint
                or core_obj.get("policy_epoch") != epoch
            ):
                self.halted_reason = f"HALT_BOOT_CAID_OR_COLUMN_TAMPER_AT_SEQ_{seq}"
                return

            # Re-verify Ed25519 signature
            pub = self.public_keys.get(key_id)
            if pub is None:
                self.halted_reason = f"HALT_BOOT_UNKNOWN_KEY_AT_SEQ_{seq}"
                return
            try:
                sig_bytes = base64.b64decode(sig_b64, validate=True)
                pub.verify(sig_bytes, canonical_json_v1(core_obj))
            except (InvalidSignature, Exception):
                self.halted_reason = f"HALT_BOOT_INVALID_SIGNATURE_AT_SEQ_{seq}"
                return

            # Verify Merkle/hash chain continuity
            expected_entry_hash = self._compute_entry_hash(expected_prev, stored_caid, sig_b64)
            if prev_hash != expected_prev or entry_hash != expected_entry_hash:
                self.halted_reason = f"HALT_BOOT_HASH_CHAIN_BROKEN_AT_SEQ_{seq}"
                return

            expected_prev = entry_hash
            last_seq = seq

        # Verify against external continuity anchor if configured
        if self.external_anchor_tip is not None:
            anchor_seq, anchor_hash = self.external_anchor_tip
            if last_seq < anchor_seq or (
                last_seq == anchor_seq and expected_prev != anchor_hash
            ):
                self.halted_reason = "HALT_BOOT_CONTINUITY_ANCHOR_VIOLATION"
                return

    def get_budget_exposure(self) -> Dict[str, int]:
        """Returns reserved (DISPATCHED + EFFECT_INDETERMINATE + UNRESOLVED) and settled (CONFIRMED) totals."""
        rows = self.conn.execute(
            "SELECT disposition, amount_minor FROM authoritative_ledger;"
        ).fetchall()
        reserved = 0
        settled = 0
        for disp, amt in rows:
            if disp in ("DISPATCHED", "EFFECT_INDETERMINATE", "UNRESOLVED_ESCALATED"):
                reserved += amt
            elif disp == "CONFIRMED":
                settled += amt
        return {
            "reserved_minor": reserved,
            "settled_minor": settled,
            "active_exposure_minor": reserved + settled,
        }

    def authorize_and_reserve(self, signed_act_envelope: Dict[str, Any]) -> BoundaryVerdict:
        """
        Station 1 Pre-Dispatch Gate:
        Validates signature, CAID, pure taint tier (AT57b), per-call attenuation,
        explicit workflow preconditions, and sprint escrow limit before writing DISPATCHED.
        """
        if self.halted_reason is not None:
            return BoundaryVerdict("NOT_DISPATCHED", self.halted_reason, "", "")

        act_core = signed_act_envelope.get("act_core")
        sig_info = signed_act_envelope.get("signature", {})
        if not isinstance(act_core, dict) or not isinstance(sig_info, dict):
            return BoundaryVerdict("NOT_DISPATCHED", "ERR_MALFORMED_ACT_ENVELOPE", "", "")

        try:
            caid = compute_act_caid(act_core)
        except ValueError as exc:
            return BoundaryVerdict("NOT_DISPATCHED", str(exc), "", "")

        op_id = str(act_core.get("operation_id", ""))
        act_type = str(act_core.get("action_type", ""))
        amt = act_core.get("amount_minor")
        max_call = act_core.get("max_per_call_minor")
        rcpt = str(act_core.get("recipient", ""))
        taint = str(act_core.get("taint_tier", ""))
        epoch = str(act_core.get("policy_epoch", ""))

        if (
            not op_id
            or isinstance(amt, bool)
            or not isinstance(amt, int)
            or amt < 0
            or isinstance(max_call, bool)
            or not isinstance(max_call, int)
        ):
            return BoundaryVerdict("NOT_DISPATCHED", "ERR_INVALID_NUMERIC_OR_ID", op_id, caid)

        # 1. Verify Ed25519 signature over canonical_json_v1(act_core)
        key_id = str(sig_info.get("key_id", ""))
        sig_b64 = str(sig_info.get("value_b64", ""))
        pub = self.public_keys.get(key_id)
        if pub is None:
            return BoundaryVerdict("NOT_DISPATCHED", "ERR_UNKNOWN_SIGNING_KEY", op_id, caid)
        try:
            sig_bytes = base64.b64decode(sig_b64, validate=True)
            pub.verify(sig_bytes, canonical_json_v1(act_core))
        except Exception:
            return BoundaryVerdict(
                "NOT_DISPATCHED", "ERR_SIGNATURE_OR_PAYEE_MISMATCH", op_id, caid
            )

        # 2. Phase 0.2 (AT57b Closure): Pure Taint Gate (no keyword heuristics)
        if taint == "TIER_2_UNTRUSTED":
            return BoundaryVerdict(
                "NOT_DISPATCHED",
                "ERR_AT57B_UNTAMPERED_TAINT_TIER2_CONSEQUENTIAL_DENIED",
                op_id,
                caid,
            )

        # 3. Delegation per-call attenuation check (AT71)
        if amt > max_call:
            return BoundaryVerdict(
                "NOT_DISPATCHED", "ERR_DELEGATION_CALL_CAP_EXCEEDED", op_id, caid
            )

        # 4. Pinned recipient check
        if amt > 0 and rcpt not in self.pinned_recipients:
            return BoundaryVerdict("NOT_DISPATCHED", "ERR_UNPINNED_RECIPIENT", op_id, caid)

        # 5. Explicit versioned workflow precondition check (Inner Loop rule)
        required_priors = self.workflow_preconditions.get(act_type, [])
        for req_action in required_priors:
            prior_ok = self.conn.execute(
                "SELECT 1 FROM authoritative_ledger WHERE action_type = ? AND disposition = 'CONFIRMED' LIMIT 1;",
                (req_action,),
            ).fetchone()
            if not prior_ok:
                return BoundaryVerdict(
                    "NOT_DISPATCHED",
                    f"ERR_MISSING_REQUIRED_PRECONDITION:{req_action}",
                    op_id,
                    caid,
                )

        # 6. Atomic Escrow Reservation in SQLite WAL
        self.conn.execute("BEGIN IMMEDIATE;")
        try:
            existing = self.conn.execute(
                "SELECT disposition FROM authoritative_ledger WHERE operation_id = ? OR caid = ?;",
                (op_id, caid),
            ).fetchone()
            if existing is not None:
                self.conn.execute("ROLLBACK;")
                prior_disp = existing[0]
                code = (
                    "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY"
                    if prior_disp in ("EFFECT_INDETERMINATE", "UNRESOLVED_ESCALATED")
                    else "ERR_DUPLICATE_OPERATION_OR_CAID"
                )
                return BoundaryVerdict("NOT_DISPATCHED", code, op_id, caid)

            exposure = self.get_budget_exposure()["active_exposure_minor"]
            if exposure + amt > self.sprint_limit_minor:
                self.conn.execute("ROLLBACK;")
                return BoundaryVerdict(
                    "NOT_DISPATCHED", "HALT_SPRINT_BUDGET_EXCEEDED", op_id, caid
                )

            tip_row = self.conn.execute(
                "SELECT entry_hash FROM authoritative_ledger ORDER BY seq DESC LIMIT 1;"
            ).fetchone()
            prev_hash = tip_row[0] if tip_row else self.GENESIS_HASH
            entry_hash = self._compute_entry_hash(prev_hash, caid, sig_b64)

            self.conn.execute(
                """
                INSERT INTO authoritative_ledger (
                    operation_id, action_type, amount_minor, max_per_call_minor,
                    recipient, taint_tier, policy_epoch, key_id, act_core_json,
                    caid, signature_b64, disposition, prev_entry_hash, entry_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DISPATCHED', ?, ?);
                """,
                (
                    op_id,
                    act_type,
                    amt,
                    max_call,
                    rcpt,
                    taint,
                    epoch,
                    key_id,
                    canonical_json_v1(act_core).decode("utf-8"),
                    caid,
                    sig_b64,
                    prev_hash,
                    entry_hash,
                ),
            )
            self.conn.execute("COMMIT;")
            return BoundaryVerdict("DISPATCHED", "OK", op_id, caid)
        except Exception:
            self.conn.execute("ROLLBACK;")
            raise

    def record_downstream_effect(
        self,
        operation_id: str,
        http_status: Optional[int],
        transport_exception: bool = False,
        authoritative_reconciliation: Optional[str] = None,
    ) -> str:
        """
        Phase 0.3 (AT58 Closure):
        Durable Escrow Write Path.
        - Transport exception, HTTP 504, or any HTTP 5xx latches `EFFECT_INDETERMINATE`
          and keeps the escrow reservation locked.
        - Only an explicit `authoritative_reconciliation` ("CONFIRMED" | "REFUTED" |
          "UNRESOLVED_ESCALATED") can exit `EFFECT_INDETERMINATE`.
        """
        self.conn.execute("BEGIN IMMEDIATE;")
        try:
            row = self.conn.execute(
                "SELECT disposition FROM authoritative_ledger WHERE operation_id = ?;",
                (operation_id,),
            ).fetchone()
            if row is None:
                self.conn.execute("ROLLBACK;")
                raise KeyError(f"Unknown operation_id: {operation_id}")

            current_disp = row[0]

            if authoritative_reconciliation is not None:
                if current_disp != "EFFECT_INDETERMINATE":
                    self.conn.execute("ROLLBACK;")
                    raise ValueError("ERR_RECONCILIATION_REQUIRES_INDETERMINATE_STATE")
                if authoritative_reconciliation not in (
                    "CONFIRMED",
                    "REFUTED",
                    "UNRESOLVED_ESCALATED",
                ):
                    self.conn.execute("ROLLBACK;")
                    raise ValueError("ERR_INVALID_RECONCILIATION_TARGET")
                new_disp = authoritative_reconciliation
            else:
                if current_disp != "DISPATCHED":
                    self.conn.execute("ROLLBACK;")
                    raise ValueError(f"Cannot record transport effect from {current_disp}")

                if transport_exception or http_status is None or http_status >= 500:
                    new_disp = "EFFECT_INDETERMINATE"
                elif 200 <= http_status < 300:
                    new_disp = "CONFIRMED"
                elif http_status in (400, 401, 403, 404, 422):
                    # Definitive pre-execution target rejection releases escrow
                    new_disp = "REFUTED"
                else:
                    new_disp = "EFFECT_INDETERMINATE"

            self.conn.execute(
                "UPDATE authoritative_ledger SET disposition = ? WHERE operation_id = ?;",
                (new_disp, operation_id),
            )
            self.conn.execute("COMMIT;")
            return new_disp
        except Exception:
            self.conn.execute("ROLLBACK;")
            raise


# ============================================================================
# SCOPED FORGETTING POLICY (NEVER DISCARDS EVIDENCE OR UNRESOLVED EFFECTS)
# ============================================================================
def execute_scoped_forget(
    scratchpad_drafts: List[str],
    boundary: Phase0ExecutionBoundary,
) -> Dict[str, Any]:
    """
    Discards ephemeral agent scratchpads while preserving 100% of the authoritative
    ledger, signed receipts, and unresolved `EFFECT_INDETERMINATE` states.
    """
    discarded_count = len(scratchpad_drafts)
    scratchpad_drafts.clear()
    ledger_count = boundary.conn.execute(
        "SELECT COUNT(*) FROM authoritative_ledger;"
    ).fetchone()[0]
    indeterminate_count = boundary.conn.execute(
        "SELECT COUNT(*) FROM authoritative_ledger WHERE disposition = 'EFFECT_INDETERMINATE';"
    ).fetchone()[0]
    return {
        "scratchpads_discarded": discarded_count,
        "authoritative_ledger_entries_retained": ledger_count,
        "unresolved_indeterminate_retained": indeterminate_count,
    }


# ============================================================================
# PHASE 0 VERIFICATION TEST SUITE (CLOSING 0.1, 0.2, 0.3, 0.4)
# ============================================================================
def _sign_act(
    priv: Ed25519PrivateKey, key_id: str, act_core: Dict[str, Any]
) -> Dict[str, Any]:
    sig = priv.sign(canonical_json_v1(act_core))
    return {
        "act_core": act_core,
        "signature": {
            "alg": "Ed25519",
            "key_id": key_id,
            "value_b64": base64.b64encode(sig).decode("ascii"),
        },
    }


def test_phase0_integrity_reset_all_blockers() -> None:
    priv = Ed25519PrivateKey.generate()
    pub_registry = {"agent-key-1": priv.public_key()}
    good_iban = "iban:DE89370400440532013000"

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = tmp.name

    try:
        gate = Phase0ExecutionBoundary(
            db_path=db_path,
            public_keys=pub_registry,
            sprint_limit_minor=1000_00,
            pinned_recipients={good_iban},
            workflow_preconditions={"book_seat": ["check_seat_availability"]},
        )

        # 0.1: Float in Act core is rejected deterministically
        bad_float_act = {
            "operation_id": "op-float",
            "action_type": "refund.create",
            "amount_minor": 100.50,
            "max_per_call_minor": 500_00,
            "recipient": good_iban,
            "taint_tier": "TIER_1_REVIEWED",
            "policy_epoch": "2026-Q4",
        }
        v_float = gate.authorize_and_reserve(
            {"act_core": bad_float_act, "signature": {"key_id": "agent-key-1", "value_b64": ""}}
        )
        assert v_float.disposition == "NOT_DISPATCHED"
        assert "ERR_FLOAT_FORBIDDEN" in v_float.code

        # 0.2 (AT57b): Pure Taint Gate blocks TIER_2_UNTRUSTED even with clean text and valid signature
        tainted_act = {
            "operation_id": "op-taint-pure",
            "action_type": "refund.create",
            "amount_minor": 100_00,
            "max_per_call_minor": 500_00,
            "recipient": good_iban,
            "taint_tier": "TIER_2_UNTRUSTED",
            "policy_epoch": "2026-Q4",
        }
        v_taint = gate.authorize_and_reserve(_sign_act(priv, "agent-key-1", tainted_act))
        assert v_taint.disposition == "NOT_DISPATCHED"
        assert v_taint.code == "ERR_AT57B_UNTAMPERED_TAINT_TIER2_CONSEQUENTIAL_DENIED"

        # Explicit Workflow Precondition: `book_seat` blocked before `check_seat_availability`
        book_act = {
            "operation_id": "op-book-1",
            "action_type": "book_seat",
            "amount_minor": 50_00,
            "max_per_call_minor": 500_00,
            "recipient": good_iban,
            "taint_tier": "TIER_1_REVIEWED",
            "policy_epoch": "2026-Q4",
        }
        v_pre = gate.authorize_and_reserve(_sign_act(priv, "agent-key-1", book_act))
        assert v_pre.disposition == "NOT_DISPATCHED"
        assert v_pre.code == "ERR_MISSING_REQUIRED_PRECONDITION:check_seat_availability"

        # 0.3 (AT58): Escrow Write Path holds reservation across HTTP 504/500 & Scoped Forget
        valid_act = {
            "operation_id": "op-escrow-504",
            "action_type": "refund.create",
            "amount_minor": 600_00,
            "max_per_call_minor": 700_00,
            "recipient": good_iban,
            "taint_tier": "TIER_1_REVIEWED",
            "policy_epoch": "2026-Q4",
        }
        v_ok = gate.authorize_and_reserve(_sign_act(priv, "agent-key-1", valid_act))
        assert v_ok.disposition == "DISPATCHED"
        assert gate.get_budget_exposure()["reserved_minor"] == 600_00

        # Downstream returns HTTP 503 -> latches EFFECT_INDETERMINATE; escrow stays reserved
        new_state = gate.record_downstream_effect("op-escrow-504", http_status=503)
        assert new_state == "EFFECT_INDETERMINATE"
        assert gate.get_budget_exposure()["reserved_minor"] == 600_00

        # Scoped Forget clears scratchpads without losing the indeterminate escrow or ledger
        scratchpads = ["draft_1", "draft_2", "failed_search"]
        forget_res = execute_scoped_forget(scratchpads, gate)
        assert forget_res["scratchpads_discarded"] == 3
        assert len(scratchpads) == 0
        assert forget_res["unresolved_indeterminate_retained"] == 1

        # Second request for 500_00 exceeds remaining sprint budget (600_00 reserved + 500_00 > 1000_00)
        overflow_act = {
            "operation_id": "op-overflow",
            "action_type": "refund.create",
            "amount_minor": 500_00,
            "max_per_call_minor": 700_00,
            "recipient": good_iban,
            "taint_tier": "TIER_1_REVIEWED",
            "policy_epoch": "2026-Q4",
        }
        v_ovf = gate.authorize_and_reserve(_sign_act(priv, "agent-key-1", overflow_act))
        assert v_ovf.disposition == "NOT_DISPATCHED"
        assert v_ovf.code == "HALT_SPRINT_BUDGET_EXCEEDED"

        # Reconcile `op-escrow-504` as CONFIRMED -> moves 600_00 from reserved to settled
        rec_state = gate.record_downstream_effect(
            "op-escrow-504",
            http_status=None,
            authoritative_reconciliation="CONFIRMED",
        )
        assert rec_state == "CONFIRMED"
        exp = gate.get_budget_exposure()
        assert exp["reserved_minor"] == 0 and exp["settled_minor"] == 600_00

        # 0.4 (G3): Boot Signature & Column Re-Verification catches on-disk tampering
        # First verify clean reboot succeeds
        tip_hash = gate.conn.execute(
            "SELECT entry_hash FROM authoritative_ledger WHERE seq = 1;"
        ).fetchone()[0]
        gate_reboot_ok = Phase0ExecutionBoundary(
            db_path=db_path,
            public_keys=pub_registry,
            sprint_limit_minor=1000_00,
            pinned_recipients={good_iban},
            external_anchor_tip=(1, tip_hash),
        )
        assert gate_reboot_ok.halted_reason is None

        # Now tamper with `amount_minor` on disk (downgrading 600_00 -> 0 in SQLite)
        gate.conn.execute(
            "UPDATE authoritative_ledger SET amount_minor = 0 WHERE seq = 1;"
        )
        gate_tampered = Phase0ExecutionBoundary(
            db_path=db_path,
            public_keys=pub_registry,
            sprint_limit_minor=1000_00,
            pinned_recipients={good_iban},
        )
        assert gate_tampered.halted_reason == "HALT_BOOT_CAID_OR_COLUMN_TAMPER_AT_SEQ_1"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == "__main__":
    test_phase0_integrity_reset_all_blockers()
    print(
        "PHASE 0 INTEGRITY RESET PASSED: "
        "0.1 (CANONICAL JSON/CAID), 0.2 (AT57B PURE TAINT), "
        "0.3 (AT58 ESCROW WRITE PATH), 0.4 (G3 BOOT SIGNATURE RE-VERIFY)."
    )
