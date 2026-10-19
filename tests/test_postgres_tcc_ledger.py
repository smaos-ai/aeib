#!/usr/bin/env python3
"""
tests/test_postgres_tcc_ledger.py
================================================================================
Test suite for PostgreSQL Bitemporal Outbox and Atomic TCC Ledger.
Evaluates Try-Confirm-Cancel reservations, concurrency serialization across
subagent branches, budget ceiling enforcement, and Ed25519 JCS receipts.
"""

import concurrent.futures
from pathlib import Path
from typing import List, Dict, Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.storage.postgres_tcc_ledger import (
    PostgresTccLedger,
    verify_tcc_ledger_receipt,
)


def test_tcc_ledger_try_confirm_lifecycle(tmp_path: Path):
    db_file = tmp_path / "test_tcc_lifecycle.db"
    privkey = ed25519.Ed25519PrivateKey.generate()

    # Initial budget €1,000.00 (100,000 minor units)
    ledger = PostgresTccLedger(
        workflow_id="wf_life_01",
        budget_minor=100000,
        signing_key=privkey,
        db_path=db_file,
    )

    state0 = ledger.get_budget_state()
    assert state0["budget_minor"] == 100000
    assert state0["reserved_minor"] == 0
    assert state0["confirmed_minor"] == 0
    assert state0["available_minor"] == 100000

    # 1. Try-reserve €300.00
    res1 = ledger.try_reserve(
        operation_id="op_tcc_01",
        subagent_id="subagent_alpha",
        amount_minor=30000,
        action_payload={"tool": "transfer", "amount": 30000},
    )
    assert res1["success"] is True
    assert res1["status"] == "TCC_TRY_RESERVED"
    assert verify_tcc_ledger_receipt(ledger.public_key, res1["receipt"]) is True

    state1 = ledger.get_budget_state()
    assert state1["reserved_minor"] == 30000
    assert state1["available_minor"] == 70000

    # 2. Confirm reservation
    conf_res = ledger.confirm(operation_id="op_tcc_01")
    assert conf_res["success"] is True
    assert conf_res["status"] == "TCC_CONFIRMED"
    assert verify_tcc_ledger_receipt(ledger.public_key, conf_res["receipt"]) is True

    state2 = ledger.get_budget_state()
    assert state2["reserved_minor"] == 0
    assert state2["confirmed_minor"] == 30000
    assert state2["available_minor"] == 70000


def test_tcc_ledger_budget_ceiling_rejection(tmp_path: Path):
    db_file = tmp_path / "test_tcc_ceiling.db"
    privkey = ed25519.Ed25519PrivateKey.generate()

    # Budget €500.00
    ledger = PostgresTccLedger(
        workflow_id="wf_ceiling_01",
        budget_minor=50000,
        signing_key=privkey,
        db_path=db_file,
    )

    # Reserve €400.00
    res1 = ledger.try_reserve(
        operation_id="op_tcc_10",
        subagent_id="subagent_1",
        amount_minor=40000,
        action_payload={"amount": 40000},
    )
    assert res1["success"] is True

    # Attempt to reserve €200.00 (exceeds available €100.00)
    res2 = ledger.try_reserve(
        operation_id="op_tcc_11",
        subagent_id="subagent_2",
        amount_minor=20000,
        action_payload={"amount": 20000},
    )
    assert res2["success"] is False
    assert res2["status"] == "HALT_BUDGET_EXCEEDED"
    assert res2["available_minor"] == 10000
    assert res2["requested_minor"] == 20000

    # Budget state should remain unchanged
    state = ledger.get_budget_state()
    assert state["reserved_minor"] == 40000
    assert state["available_minor"] == 10000


def test_tcc_ledger_parallel_subagent_contention(tmp_path: Path):
    db_file = tmp_path / "test_tcc_parallel.db"
    privkey = ed25519.Ed25519PrivateKey.generate()

    # Budget €1,000.00 (100,000 minor units)
    ledger = PostgresTccLedger(
        workflow_id="wf_parallel_01",
        budget_minor=100000,
        signing_key=privkey,
        db_path=db_file,
    )

    # 10 concurrent threads each attempting to reserve €200.00 (20,000 minor units)
    # Exactly 5 must succeed (100,000 / 20,000 = 5), and 5 must fail with HALT_BUDGET_EXCEEDED
    def attempt_reservation(idx: int) -> Dict[str, Any]:
        return ledger.try_reserve(
            operation_id=f"op_parallel_{idx}",
            subagent_id=f"subagent_{idx}",
            amount_minor=20000,
            action_payload={"thread_idx": idx, "amount": 20000},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_reservation, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    succeeded = [r for r in results if r["success"] is True]
    failed = [r for r in results if r["success"] is False]

    assert len(succeeded) == 5
    assert len(failed) == 5
    for f in failed:
        assert f["status"] == "HALT_BUDGET_EXCEEDED"

    final_state = ledger.get_budget_state()
    assert final_state["reserved_minor"] == 100000
    assert final_state["available_minor"] == 0


def test_tcc_ledger_cancellation_and_indeterminate_latch(tmp_path: Path):
    db_file = tmp_path / "test_tcc_cancel.db"
    privkey = ed25519.Ed25519PrivateKey.generate()

    ledger = PostgresTccLedger(
        workflow_id="wf_cancel_01",
        budget_minor=100000,
        signing_key=privkey,
        db_path=db_file,
    )

    # 1. Reserve €500.00 and cancel
    ledger.try_reserve(
        operation_id="op_cancel_1",
        subagent_id="subagent_x",
        amount_minor=50000,
        action_payload={"tool": "flight_booking"},
    )
    cancel_res = ledger.cancel(operation_id="op_cancel_1", reason="USER_ABORT")
    assert cancel_res["success"] is True
    assert cancel_res["status"] == "TCC_CANCELLED"

    state1 = ledger.get_budget_state()
    assert state1["reserved_minor"] == 0
    assert state1["available_minor"] == 100000

    # 2. Reserve €500.00 and latch indeterminate upon transport fault
    ledger.try_reserve(
        operation_id="op_cancel_2",
        subagent_id="subagent_y",
        amount_minor=50000,
        action_payload={"tool": "hotel_booking"},
    )
    latch_res = ledger.latch_indeterminate(
        operation_id="op_cancel_2",
        reason="HTTP_504_GATEWAY_TIMEOUT",
    )
    assert latch_res["success"] is True
    assert latch_res["status"] == "TCC_EFFECT_INDETERMINATE"

    # Funds must remain reserved while indeterminate
    state2 = ledger.get_budget_state()
    assert state2["reserved_minor"] == 50000
    assert state2["available_minor"] == 50000
