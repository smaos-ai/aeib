#!/usr/bin/env python3
"""
tests/test_postgres_tcc_concurrency_stress.py
================================================================================
PostgreSQL / SQLite Bitemporal Outbox & TCC Concurrency Stress Suite.
Evaluated under the stated model for high-contention Try-Confirm-Cancel reservations,
bitemporal interval monotonicity, CDC transactional outbox immutability,
and RFC 8785 JCS Ed25519 cryptographic continuity.
"""

from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.storage.postgres_tcc_ledger import (
    PostgresTccLedger,
    verify_tcc_ledger_receipt,
)


def sha256_prefixed(data: bytes) -> str:
    """Computes standard sha256: hex string."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass
class BitemporalCdcOutboxEntry:
    """
    Represents an outbox entry conforming to src/storage/postgres_bitemporal_outbox.sql.
    """
    event_id: int
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload_json: Dict[str, Any]
    caid: str
    signature_b64: str
    valid_time_start: int
    valid_time_end: int
    system_time_start: int


def load_bitemporal_cdc_outbox_entries(db_path: Path) -> List[BitemporalCdcOutboxEntry]:
    """
    Loads all CDC outbox records joined with outbox journal intervals from storage.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            """
            SELECT e.event_id, e.aggregate_type, e.aggregate_id, e.event_type,
                   e.payload_jcs, e.caid, e.signature_b64, e.created_at,
                   j.valid_from, j.valid_to
            FROM tcc_cdc_outbox_events e
            JOIN tcc_outbox_journal j ON e.aggregate_id = j.operation_id
            ORDER BY e.event_id ASC
            """
        )
        entries: List[BitemporalCdcOutboxEntry] = []
        for row in cursor.fetchall():
            (
                event_id,
                aggregate_type,
                aggregate_id,
                event_type,
                payload_jcs,
                caid,
                signature_b64,
                created_at,
                valid_from,
                valid_to,
            ) = row
            payload_dict = json.loads(payload_jcs)
            entries.append(
                BitemporalCdcOutboxEntry(
                    event_id=event_id,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    event_type=event_type,
                    payload_json=payload_dict,
                    caid=caid,
                    signature_b64=signature_b64,
                    valid_time_start=valid_from,
                    valid_time_end=valid_to,
                    system_time_start=created_at,
                )
            )
        return entries
    finally:
        conn.close()


def subagent_reserve_with_retry_backoff(
    ledger: PostgresTccLedger,
    operation_id: str,
    subagent_id: str,
    amount_minor: int,
    action_payload: Dict[str, Any],
    max_retries: int = 2,
    base_backoff_sec: float = 0.001,
) -> Dict[str, Any]:
    """
    Executes a subagent reservation attempt with exponential backoff on budget contention.
    When budget is genuinely exhausted, halts fail-closed with TCC_ERROR_BUDGET_EXCEEDED.
    """
    for attempt in range(max_retries + 1):
        res = ledger.try_reserve(
            operation_id=operation_id,
            subagent_id=subagent_id,
            amount_minor=amount_minor,
            action_payload=action_payload,
        )
        if res.get("success") is True:
            return res

        if res.get("status") == "HALT_BUDGET_EXCEEDED":
            if attempt < max_retries:
                time.sleep(base_backoff_sec * (2**attempt))
                continue
            return {
                "success": False,
                "status": "TCC_ERROR_BUDGET_EXCEEDED",
                "original_status": res.get("status"),
                "available_minor": res.get("available_minor", 0),
                "requested_minor": amount_minor,
                "subagent_id": subagent_id,
            }

        return res

    return {
        "success": False,
        "status": "TCC_ERROR_BUDGET_EXCEEDED",
        "requested_minor": amount_minor,
        "subagent_id": subagent_id,
    }


class HighContentionTccStressTest:
    """
    High-Contention TCC Concurrency & Bitemporal Stress Suite.
    Evaluates 100 concurrent subagents across a shared workflow budget ceiling.
    """

    __test__ = True

    def test_concurrent_100_subagents_high_contention_budget_exhaustion(
        self, tmp_path: Path
    ) -> None:
        """
        Spawns 100 concurrent subagents across a shared workflow_id with €5,000.00
        (5000_00 minor units) budget ceiling. Evaluates thread contention, serialization,
        and fail-closed budget exhaustion.
        """
        db_file = tmp_path / "tcc_stress_100_agents.db"
        privkey = ed25519.Ed25519PrivateKey.generate()
        shared_workflow_id = "wf_stress_high_contention_100"
        budget_ceiling_minor = 5000_00  # €5,000.00 (500,000 cents)

        ledger = PostgresTccLedger(
            workflow_id=shared_workflow_id,
            budget_minor=budget_ceiling_minor,
            signing_key=privkey,
            db_path=db_file,
        )

        initial_state = ledger.get_budget_state()
        assert initial_state["found"] is True
        assert initial_state["budget_minor"] == 5000_00
        assert initial_state["reserved_minor"] == 0
        assert initial_state["confirmed_minor"] == 0
        assert initial_state["available_minor"] == 5000_00

        num_subagents = 100
        # Reservation amounts ranging between €50.00 (50_00) and €300.00 (300_00) minor units
        # Total requested budget across 100 subagents ~ €17,219.00, far exceeding €5,000.00
        reservation_amounts = [
            50_00 + ((i * 37) % 251) * 100 for i in range(num_subagents)
        ]
        assert min(reservation_amounts) >= 50_00
        assert max(reservation_amounts) <= 300_00
        assert sum(reservation_amounts) > budget_ceiling_minor

        barrier = threading.Barrier(num_subagents)
        observed_solvency_violations: List[str] = []
        lock = threading.Lock()

        def subagent_worker(agent_index: int) -> Dict[str, Any]:
            op_id = f"op_agent_{agent_index:03d}"
            subagent_id = f"subagent_{agent_index:03d}"
            amount = reservation_amounts[agent_index]
            payload = {
                "action": "reserve_compute_cluster",
                "agent_index": agent_index,
                "amount_minor": amount,
                "currency": "EUR",
            }

            # Align all 100 threads to release simultaneously for maximum row contention
            barrier.wait()

            result = subagent_reserve_with_retry_backoff(
                ledger=ledger,
                operation_id=op_id,
                subagent_id=subagent_id,
                amount_minor=amount,
                action_payload=payload,
                max_retries=2,
            )

            # Observe instantaneous solvency check
            snapshot = ledger.get_budget_state()
            if snapshot["reserved_minor"] + snapshot["confirmed_minor"] > budget_ceiling_minor:
                with lock:
                    observed_solvency_violations.append(
                        f"Solvency violation: reserved={snapshot['reserved_minor']} + "
                        f"confirmed={snapshot['confirmed_minor']} > {budget_ceiling_minor}"
                    )

            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_subagents) as executor:
            futures = [executor.submit(subagent_worker, i) for i in range(num_subagents)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Zero solvency violations observed during execution
        assert not observed_solvency_violations

        # 1. Zero lost updates across all 100 concurrent threads
        assert len(results) == num_subagents
        succeeded = [r for r in results if r.get("success") is True]
        failed = [r for r in results if r.get("success") is False]
        assert len(succeeded) + len(failed) == num_subagents
        assert len(succeeded) > 0
        assert len(failed) > 0

        # 2. Mathematical Solvency Invariant
        final_state = ledger.get_budget_state()
        assert final_state["reserved_minor"] + final_state["confirmed_minor"] <= budget_ceiling_minor
        assert final_state["available_minor"] >= 0
        assert final_state["available_minor"] == (
            budget_ceiling_minor - (final_state["reserved_minor"] + final_state["confirmed_minor"])
        )

        # Exact accounting: sum of amounts of all successful reservations equals reserved_minor
        total_succeeded_amount = sum(r["amount_minor"] for r in succeeded)
        assert total_succeeded_amount == final_state["reserved_minor"]

        # 3. Zero double-allocation and fail-closed budget rejection verification
        for f in failed:
            assert f["status"] in ("HALT_BUDGET_EXCEEDED", "TCC_ERROR_BUDGET_EXCEEDED")
            assert f["requested_minor"] > final_state["available_minor"]

        # 4. Storage ledger cross-verification via direct SQLite inspection
        conn = sqlite3.connect(str(db_file))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT operation_id, amount_minor, tcc_state FROM tcc_outbox_journal WHERE workflow_id = ?",
                (shared_workflow_id,),
            )
            journal_rows = cur.fetchall()

            # Every successful reservation must exist in the journal as TRY_RESERVED
            assert len(journal_rows) == len(succeeded)
            journal_total = sum(row[1] for row in journal_rows)
            assert journal_total == final_state["reserved_minor"]
            for row in journal_rows:
                assert row[2] == "TRY_RESERVED"

            # Verify that none of the failed subagents created reservations in the journal
            failed_subagents = {f["subagent_id"] for f in failed}
            cur.execute(
                "SELECT subagent_id FROM tcc_outbox_journal WHERE workflow_id = ?",
                (shared_workflow_id,),
            )
            recorded_subagents = {r[0] for r in cur.fetchall()}
            assert failed_subagents.isdisjoint(recorded_subagents)
        finally:
            conn.close()

        # 5. Cryptographic verification of every issued receipt
        for s in succeeded:
            receipt = s["receipt"]
            assert verify_tcc_ledger_receipt(ledger.public_key, receipt) is True

    def test_concurrent_confirm_and_cancel_lifecycle_with_reallocation(
        self, tmp_path: Path
    ) -> None:
        """
        Evaluates concurrent TCC confirmation and cancellation across active holds,
        verifying release of escrowed budget and re-allocation to subsequent subagents.
        """
        db_file = tmp_path / "tcc_lifecycle_reallocation.db"
        privkey = ed25519.Ed25519PrivateKey.generate()
        workflow_id = "wf_tcc_realloc_01"
        budget_minor = 5000_00  # €5,000.00

        ledger = PostgresTccLedger(
            workflow_id=workflow_id,
            budget_minor=budget_minor,
            signing_key=privkey,
            db_path=db_file,
        )

        # Initial reservation wave: 10 holds of €400.00 each = €4,000.00 total
        for i in range(10):
            res = ledger.try_reserve(
                operation_id=f"op_wave1_{i:02d}",
                subagent_id=f"subagent_wave1_{i:02d}",
                amount_minor=400_00,
                action_payload={"wave": 1, "index": i},
                now_ts=1000 + i,
            )
            assert res["success"] is True

        state_before = ledger.get_budget_state()
        assert state_before["reserved_minor"] == 4000_00
        assert state_before["confirmed_minor"] == 0
        assert state_before["available_minor"] == 1000_00

        # Concurrent transition: confirm first 5 (indices 0..4), cancel remaining 5 (indices 5..9)
        def transition_worker(idx: int) -> Dict[str, Any]:
            op_id = f"op_wave1_{idx:02d}"
            if idx < 5:
                return ledger.confirm(operation_id=op_id, now_ts=2000 + idx)
            else:
                return ledger.cancel(
                    operation_id=op_id,
                    reason="TASK_ABORTED_OR_SUPERSEDED",
                    now_ts=2000 + idx,
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futs = [executor.submit(transition_worker, i) for i in range(10)]
            transition_results = [f.result() for f in concurrent.futures.as_completed(futs)]

        for tr in transition_results:
            assert tr["success"] is True
            assert tr["status"] in ("TCC_CONFIRMED", "TCC_CANCELLED")
            assert verify_tcc_ledger_receipt(ledger.public_key, tr["receipt"]) is True

        state_mid = ledger.get_budget_state()
        # 5 confirmed @ €400.00 = €2,000.00; 5 cancelled released €2,000.00 back to available
        assert state_mid["reserved_minor"] == 0
        assert state_mid["confirmed_minor"] == 2000_00
        assert state_mid["available_minor"] == 3000_00
        assert state_mid["confirmed_minor"] + state_mid["reserved_minor"] <= budget_minor

        # Wave 2: 10 concurrent subagents attempt to reserve newly released budget (€300.00 each)
        # Total requested = €3,000.00. Exactly all 10 should succeed!
        def wave2_worker(idx: int) -> Dict[str, Any]:
            return ledger.try_reserve(
                operation_id=f"op_wave2_{idx:02d}",
                subagent_id=f"subagent_wave2_{idx:02d}",
                amount_minor=300_00,
                action_payload={"wave": 2, "index": idx},
                now_ts=3000 + idx,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futs2 = [executor.submit(wave2_worker, i) for i in range(10)]
            wave2_results = [f.result() for f in concurrent.futures.as_completed(futs2)]

        wave2_succeeded = [r for r in wave2_results if r["success"] is True]
        assert len(wave2_succeeded) == 10

        state_final = ledger.get_budget_state()
        assert state_final["confirmed_minor"] == 2000_00
        assert state_final["reserved_minor"] == 3000_00
        assert state_final["available_minor"] == 0
        assert state_final["confirmed_minor"] + state_final["reserved_minor"] <= budget_minor

    def test_bitemporal_interval_and_cdc_outbox_verification(
        self, tmp_path: Path
    ) -> None:
        """
        Validates that every confirmed or cancelled transaction creates a valid outbox entry
        conforming to src/storage/postgres_bitemporal_outbox.sql.
        Verifies that valid_time and system_time intervals are strictly monotonic and immutable.
        Verifies Ed25519 signature over strict RFC 8785 JCS payload representation.
        """
        db_file = tmp_path / "tcc_bitemporal_outbox.db"
        privkey = ed25519.Ed25519PrivateKey.generate()
        workflow_id = "wf_bitemporal_cdc_test"
        budget_minor = 5000_00

        ledger = PostgresTccLedger(
            workflow_id=workflow_id,
            budget_minor=budget_minor,
            signing_key=privkey,
            db_path=db_file,
        )

        # Step 1: Create 4 distinct operations with explicit timestamps
        op_specs = [
            ("op_cdc_01", "subagent_a", 150_00, 1000),
            ("op_cdc_02", "subagent_b", 200_00, 1010),
            ("op_cdc_03", "subagent_c", 250_00, 1020),
            ("op_cdc_04", "subagent_d", 300_00, 1030),
        ]

        for op_id, sub_id, amount, ts in op_specs:
            res = ledger.try_reserve(
                operation_id=op_id,
                subagent_id=sub_id,
                amount_minor=amount,
                action_payload={"op": op_id, "amount": amount},
                now_ts=ts,
            )
            assert res["success"] is True

        # Step 2: Confirm op_cdc_01 and op_cdc_02; Cancel op_cdc_03; Latch op_cdc_04 indeterminate
        conf1 = ledger.confirm(operation_id="op_cdc_01", now_ts=1050)
        assert conf1["success"] is True

        conf2 = ledger.confirm(operation_id="op_cdc_02", now_ts=1060)
        assert conf2["success"] is True

        canc3 = ledger.cancel(operation_id="op_cdc_03", reason="TIMEOUT_ABORT", now_ts=1070)
        assert canc3["success"] is True

        latch4 = ledger.latch_indeterminate(
            operation_id="op_cdc_04",
            reason="TRANSPORT_504_TIMEOUT",
            now_ts=1080,
        )
        assert latch4["success"] is True

        # Reconcile op_cdc_04 from indeterminate state to confirmed after upstream check
        conf4 = ledger.confirm(operation_id="op_cdc_04", now_ts=1090)
        assert conf4["success"] is True

        # Step 3: Load all CDC outbox records and evaluate conformance
        outbox_entries = load_bitemporal_cdc_outbox_entries(db_file)
        # 4 reserves + 2 direct confirms + 1 cancel + 1 reconciled confirm = 8 CDC events
        assert len(outbox_entries) == 8

        # Verify conformance to postgres_bitemporal_outbox.sql fields
        for entry in outbox_entries:
            assert entry.event_id > 0
            assert entry.aggregate_type == "AEIB_TCC_OUTBOX"
            assert entry.aggregate_id.startswith("op_cdc_")
            assert entry.event_type in (
                "TCC_TRY_RESERVED",
                "TCC_CONFIRMED",
                "TCC_CANCELLED",
                "TCC_EFFECT_INDETERMINATE",
            )
            # Mandatory payload keys
            payload = entry.payload_json
            assert payload["workflow_id"] == workflow_id
            assert payload["operation_id"] == entry.aggregate_id
            assert "subagent_id" in payload
            assert "amount_minor" in payload
            assert "action_caid" in payload
            assert payload["event_type"] == entry.event_type
            assert "timestamp" in payload

            assert entry.valid_time_start > 0
            assert entry.system_time_start > 0

        # Step 4: Strict Monotonicity & Bitemporal Interval Checks
        for idx in range(len(outbox_entries) - 1):
            curr_entry = outbox_entries[idx]
            next_entry = outbox_entries[idx + 1]

            # Monotonic event_id sequence (append-only)
            assert next_entry.event_id == curr_entry.event_id + 1

            # System time interval monotonic non-decreasing
            assert next_entry.system_time_start >= curr_entry.system_time_start

        # Bitemporal interval validation for confirmed/cancelled operations
        confirmed_or_cancelled = [
            e for e in outbox_entries if e.event_type in ("TCC_CONFIRMED", "TCC_CANCELLED")
        ]
        assert len(confirmed_or_cancelled) == 4
        for entry in confirmed_or_cancelled:
            # valid_time_start must precede or equal valid_time_end (closing the interval)
            assert entry.valid_time_start <= entry.valid_time_end
            assert entry.valid_time_end < 2147483647  # Interval is closed upon confirmation/cancel

        # Step 5: Cryptographic Purity - Real Ed25519 & RFC 8785 JCS verification
        for entry in outbox_entries:
            canonical_jcs_bytes = encode_jcs(entry.payload_json)
            expected_caid = sha256_prefixed(canonical_jcs_bytes)
            assert entry.caid == expected_caid

            # Verify signature using public key
            sig_bytes = base64.b64decode(entry.signature_b64, validate=True)
            ledger.public_key.verify(sig_bytes, canonical_jcs_bytes)

        # Step 6: Negative Cryptographic Tamper Test
        tampered_payload = dict(outbox_entries[0].payload_json)
        tampered_payload["amount_minor"] = 99999_99  # Tampered amount
        tampered_canonical = encode_jcs(tampered_payload)
        sig0 = base64.b64decode(outbox_entries[0].signature_b64)
        with pytest.raises(Exception):
            ledger.public_key.verify(sig0, tampered_canonical)

    def test_idempotent_duplicate_confirm_and_cancel_under_concurrency(
        self, tmp_path: Path
    ) -> None:
        """
        Evaluates concurrent duplicate confirmation and cancellation invocations,
        verifying that exactly one transition applies and duplicate calls yield
        idempotent responses without double-mutating budget balance.
        """
        db_file = tmp_path / "tcc_idempotency.db"
        privkey = ed25519.Ed25519PrivateKey.generate()
        workflow_id = "wf_idempotency_01"
        budget_minor = 5000_00

        ledger = PostgresTccLedger(
            workflow_id=workflow_id,
            budget_minor=budget_minor,
            signing_key=privkey,
            db_path=db_file,
        )

        res = ledger.try_reserve(
            operation_id="op_idempotent_conf",
            subagent_id="subagent_idem_1",
            amount_minor=1000_00,
            action_payload={"item": "flight"},
            now_ts=1000,
        )
        assert res["success"] is True

        # 20 concurrent threads attempting to confirm the exact same operation
        def concurrent_confirm(thread_id: int) -> Dict[str, Any]:
            return ledger.confirm(operation_id="op_idempotent_conf", now_ts=1010 + thread_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futs = [executor.submit(concurrent_confirm, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futs)]

        for r in results:
            assert r["success"] is True
            assert r["status"] in ("TCC_CONFIRMED", "ALREADY_CONFIRMED")

        first_confirms = [r for r in results if r["status"] == "TCC_CONFIRMED"]
        already_confirms = [r for r in results if r["status"] == "ALREADY_CONFIRMED"]
        assert len(first_confirms) == 1
        assert len(already_confirms) == 19

        state = ledger.get_budget_state()
        assert state["reserved_minor"] == 0
        assert state["confirmed_minor"] == 1000_00
        assert state["available_minor"] == 4000_00

    def test_postgres_bitemporal_sql_schema_contract(self) -> None:
        """
        Validates the SQL schema definition in src/storage/postgres_bitemporal_outbox.sql.
        Evaluates presence of pessimistic row-level locking (FOR UPDATE NOWAIT),
        bitemporal range definitions, and budget ceiling constraints.
        """
        sql_path = Path("src/storage/postgres_bitemporal_outbox.sql")
        assert sql_path.is_file()
        sql_text = sql_path.read_text(encoding="utf-8")

        # Invariant 1: Budget table ceiling constraint
        assert "chk_budget_ceiling" in sql_text
        assert "reserved_minor + confirmed_minor <= budget_minor" in sql_text

        # Invariant 2: Bitemporal range columns
        assert "valid_time_range TSTZRANGE" in sql_text
        assert "system_time_range TSTZRANGE" in sql_text

        # Invariant 3: Transactional CDC Outbox table
        assert "CREATE TABLE IF NOT EXISTS tcc_cdc_outbox_events" in sql_text
        assert "aggregate_type VARCHAR" in sql_text
        assert "aggregate_id VARCHAR" in sql_text
        assert "event_type VARCHAR" in sql_text
        assert "payload_jcs JSONB" in sql_text
        assert "caid VARCHAR" in sql_text
        assert "signature_b64 TEXT" in sql_text

        # Invariant 4: Pessimistic FOR UPDATE NOWAIT serialization in stored functions
        assert "FOR UPDATE NOWAIT;" in sql_text
        assert "lock_not_available" in sql_text
        assert "HALT_LOCK_CONTENTION_NOWAIT" in sql_text
