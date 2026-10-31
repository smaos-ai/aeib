#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
tests/test_semantic_two_phase_commit.py
================================================================================
Verification suite for `src/semantic_two_phase_commit.py`.
Tests:
  1. SemanticTransactionReceipt creation, dataclass fields, and to_dict().
  2. SemanticACIDCoordinator initialization with None and initial state.
  3. read_committed isolation and deepcopy immutability.
  4. begin_transaction validation guards (empty tx_id, agent_id, target_keys).
  5. Lock contention detection and deterministic failure receipt.
  6. stage_write guards (unknown transaction, undeclared key write).
  7. finalize_handoff guard on unknown transaction.
  8. finalize_handoff abort paths: transport drop vs monitor rejected.
  9. finalize_handoff nominal commit path and lock cleanup.
"""

from __future__ import annotations

import dataclasses

import pytest

from src.semantic_two_phase_commit import (
    SemanticACIDCoordinator,
    SemanticTransactionReceipt,
)


def test_1_receipt_dataclass_and_to_dict() -> None:
    receipt = SemanticTransactionReceipt(
        tx_id="tx-100",
        agent_id="agent-alpha",
        status="COMMITTED",
        pre_state_caid="sha256:1111",
        post_state_caid="sha256:2222",
        receipt_caid="sha256:3333",
    )
    d = receipt.to_dict()
    assert d["tx_id"] == "tx-100"
    assert d["agent_id"] == "agent-alpha"
    assert d["status"] == "COMMITTED"
    assert d["pre_state_caid"] == "sha256:1111"
    assert d["post_state_caid"] == "sha256:2222"
    assert d["receipt_caid"] == "sha256:3333"

    # Enforce immutability (frozen=True)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        receipt.status = "MUTATED"


def test_2_coordinator_init_and_caid() -> None:
    # Init with None
    coord_empty = SemanticACIDCoordinator()
    assert coord_empty.current_state_caid().startswith("sha256:")
    assert coord_empty.read_committed("missing_key") is None

    # Init with state
    init_data = {"account_1": {"balance": 5000}}
    coord = SemanticACIDCoordinator(initial_state=init_data)
    assert coord.read_committed("account_1") == {"balance": 5000}

    # Verify deepcopy on read
    val = coord.read_committed("account_1")
    val["balance"] = 999999
    assert coord.read_committed("account_1") == {"balance": 5000}


def test_3_begin_transaction_guards() -> None:
    coord = SemanticACIDCoordinator()

    with pytest.raises(ValueError, match="ERR_EMPTY_TX_ID"):
        coord.begin_transaction("   ", "agent-1", frozenset(["k1"]))

    with pytest.raises(ValueError, match="ERR_EMPTY_AGENT_ID"):
        coord.begin_transaction("tx-1", "   ", frozenset(["k1"]))

    with pytest.raises(ValueError, match="ERR_EMPTY_TARGET_KEYS"):
        coord.begin_transaction("tx-1", "agent-1", frozenset())


def test_4_lock_contention() -> None:
    coord = SemanticACIDCoordinator({"balance": 1000})

    # Agent 1 begins transaction holding "balance"
    res1 = coord.begin_transaction("tx-1", "agent-1", frozenset(["balance"]))
    assert res1 is None
    assert coord.is_key_locked("balance") is True
    assert coord.is_key_locked("other") is False

    # Agent 2 attempts to acquire "balance" -> HALT_LOCK_CONTENTION
    res2 = coord.begin_transaction("tx-2", "agent-2", frozenset(["balance", "other"]))
    assert res2 is not None
    assert "HALT_LOCK_CONTENTION" in res2.status
    assert "balance_held_by_tx-1" in res2.status
    assert res2.agent_id == "agent-2"
    assert res2.tx_id == "tx-2"
    assert res2.pre_state_caid == res2.post_state_caid
    assert res2.receipt_caid.startswith("sha256:")

    # Verify "other" was not locked by failed transaction
    assert coord.is_key_locked("other") is False


def test_5_stage_write_guards() -> None:
    coord = SemanticACIDCoordinator()
    coord.begin_transaction("tx-1", "agent-1", frozenset(["declared_key"]))

    # Unknown transaction ID
    with pytest.raises(ValueError, match="ERR_UNKNOWN_TRANSACTION:unknown_tx"):
        coord.stage_write("unknown_tx", "declared_key", 123)

    # Undeclared key write
    with pytest.raises(ValueError, match="ERR_UNDECLARED_KEY_WRITE:unlocked_key"):
        coord.stage_write("tx-1", "unlocked_key", 123)

    # Valid staged write
    coord.stage_write("tx-1", "declared_key", {"nested": [1, 2, 3]})


def test_6_finalize_unknown_tx_guard() -> None:
    coord = SemanticACIDCoordinator()
    with pytest.raises(ValueError, match="ERR_UNKNOWN_TRANSACTION:tx-none"):
        coord.finalize_handoff("tx-none", transport_ok=True, monitor_verified=True)


def test_7_finalize_abort_transport_drop() -> None:
    coord = SemanticACIDCoordinator({"counter": 10})
    pre_caid = coord.current_state_caid()

    coord.begin_transaction("tx-1", "agent-1", frozenset(["counter"]))
    coord.stage_write("tx-1", "counter", 999)

    receipt = coord.finalize_handoff("tx-1", transport_ok=False, monitor_verified=True)
    assert receipt.status == "EFFECT_INDETERMINATE_ROLLED_BACK:TRANSPORT_DROP"
    assert receipt.pre_state_caid == pre_caid
    assert receipt.post_state_caid == pre_caid
    assert coord.read_committed("counter") == 10
    assert coord.is_key_locked("counter") is False


def test_8_finalize_abort_monitor_rejected() -> None:
    coord = SemanticACIDCoordinator({"counter": 10})
    pre_caid = coord.current_state_caid()

    coord.begin_transaction("tx-1", "agent-1", frozenset(["counter"]))
    coord.stage_write("tx-1", "counter", 999)

    receipt = coord.finalize_handoff("tx-1", transport_ok=True, monitor_verified=False)
    assert receipt.status == "EFFECT_INDETERMINATE_ROLLED_BACK:MONITOR_REJECTED"
    assert receipt.pre_state_caid == pre_caid
    assert receipt.post_state_caid == pre_caid
    assert coord.read_committed("counter") == 10
    assert coord.is_key_locked("counter") is False


def test_9_finalize_nominal_commit() -> None:
    coord = SemanticACIDCoordinator({"counter": 10, "untouched": "keep"})
    pre_caid = coord.current_state_caid()

    coord.begin_transaction("tx-1", "agent-1", frozenset(["counter"]))
    coord.stage_write("tx-1", "counter", 20)

    receipt = coord.finalize_handoff("tx-1", transport_ok=True, monitor_verified=True)
    assert receipt.status == "COMMITTED"
    assert receipt.pre_state_caid == pre_caid
    assert receipt.post_state_caid != pre_caid
    assert coord.read_committed("counter") == 20
    assert coord.read_committed("untouched") == "keep"
    assert coord.is_key_locked("counter") is False
    assert coord.current_state_caid() == receipt.post_state_caid
