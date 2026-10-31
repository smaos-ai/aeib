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
tests/test_byzantine_consensus_timewarp.py
================================================================================
Comprehensive verification suite for Deterministic Time-Warp Byzantine Fault Injection Harness.
Evaluated under the stated model as an agent execution integrity boundary scaffold.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.byzantine_consensus_timewarp import (
    ByzantineConsensusError,
    ByzantineConsensusTimewarpHarness,
    ByzantineVote,
    ConsensusConvergenceReceipt,
    HALT_BYZANTINE_CLOCK_SKEW_EXCEEDED,
    HALT_BYZANTINE_EMPTY_NODE_POOL,
    HALT_BYZANTINE_EQUIVOCATION_DETECTED,
    HALT_BYZANTINE_QUORUM_UNREACHABLE,
    HALT_BYZANTINE_SIGNATURE_INVALID,
    MAX_CLOCK_SKEW_MS,
    STATUS_CONVERGED,
    STATUS_QUORUM_FAILED,
    calculate_quorum_threshold,
    compute_sha256_caid,
)


def _generate_node_vote(
    node_id: str,
    proposal_hash: str,
    round_num: int = 1,
    proposal_id: str = "prop-42",
    vote_time_ms: int = 1700000000000,
) -> tuple[ByzantineVote, ed25519.Ed25519PrivateKey]:
    priv = ed25519.Ed25519PrivateKey.generate()
    vote = ByzantineConsensusTimewarpHarness.create_vote(
        node_id=node_id,
        proposal_id=proposal_id,
        round_number=round_num,
        proposal_hash=proposal_hash,
        vote_timestamp_ms=vote_time_ms,
        priv_key=priv,
    )
    return vote, priv


def test_01_quorum_threshold_calculations() -> None:
    # 2/3 + 1 integer threshold: floor(2N/3) + 1
    assert calculate_quorum_threshold(1) == 1
    assert calculate_quorum_threshold(4) == 3   # 8 // 3 + 1 = 3
    assert calculate_quorum_threshold(7) == 5   # 14 // 3 + 1 = 5
    assert calculate_quorum_threshold(10) == 7  # 20 // 3 + 1 = 7

    with pytest.raises(ByzantineConsensusError) as exc_empty:
        calculate_quorum_threshold(0)
    assert exc_empty.value.code == HALT_BYZANTINE_EMPTY_NODE_POOL

    with pytest.raises(ByzantineConsensusError) as exc_neg:
        calculate_quorum_threshold(-5)
    assert exc_neg.value.code == HALT_BYZANTINE_EMPTY_NODE_POOL


def test_02_dataclass_and_caid_computation() -> None:
    vote, _ = _generate_node_vote("node-1", "sha256:" + "aa" * 32)
    b = vote.canonical_bytes()
    assert isinstance(b, bytes)
    assert b'"node_id":"node-1"' in b

    # Frozen checks
    with pytest.raises(Exception):
        vote.round_number = 99  # type: ignore

    receipt = ConsensusConvergenceReceipt(
        convergence_id="conv-1",
        round_number=1,
        total_nodes=7,
        quorum_threshold=5,
        valid_votes_count=5,
        byzantine_faults_detected=0,
        quorum_achieved=True,
        committed_proposal_hash="sha256:" + "aa" * 32,
        receipt_caid="sha256:" + "11" * 32,
        status="OK",
        evaluated_at_ms=1000,
    )
    with pytest.raises(Exception):
        receipt.round_number = 99  # type: ignore

    r_bytes = receipt.canonical_bytes()
    assert isinstance(r_bytes, bytes)
    assert b'"total_nodes":7' in r_bytes


def test_03_nominal_consensus_convergence() -> None:
    harness = ByzantineConsensusTimewarpHarness(db_path=":memory:")
    prop_hash = "sha256:" + "cc" * 32
    coordinator_t = 1700000000000

    votes = []
    for i in range(7):
        v, _ = _generate_node_vote(f"node-{i}", prop_hash, round_num=1, vote_time_ms=coordinator_t + (i * 10))
        votes.append(v)

    receipt = harness.evaluate_round(
        round_number=1,
        total_cluster_nodes=7,
        votes=votes,
        coordinator_now_ms=coordinator_t,
    )

    assert receipt.status == STATUS_CONVERGED
    assert receipt.quorum_achieved is True
    assert receipt.quorum_threshold == 5
    assert receipt.valid_votes_count == 7
    assert receipt.byzantine_faults_detected == 0
    assert receipt.committed_proposal_hash == prop_hash
    assert len(receipt.convergence_id) == 8 + 16


def test_04_resilience_under_byzantine_fault_tolerance_limit() -> None:
    # In N=7, f=2 Byzantine faults allowed (5 valid votes still reach quorum threshold of 5)
    harness = ByzantineConsensusTimewarpHarness(db_path=":memory:")
    prop_hash = "sha256:" + "ee" * 32
    coordinator_t = 1700000000000

    votes = []
    for i in range(5):
        v, _ = _generate_node_vote(f"honest-node-{i}", prop_hash, round_num=1, vote_time_ms=coordinator_t)
        votes.append(v)

    # 2 nodes abstain/dropped
    receipt = harness.evaluate_round(
        round_number=1,
        total_cluster_nodes=7,
        votes=votes,
        coordinator_now_ms=coordinator_t,
    )

    assert receipt.quorum_achieved is True
    assert receipt.valid_votes_count == 5
    assert receipt.committed_proposal_hash == prop_hash


def test_05_quorum_unreachable_when_faults_exceed_limit() -> None:
    # In N=7, if 3 nodes fail, only 4 honest votes remain < threshold 5
    harness = ByzantineConsensusTimewarpHarness(db_path=":memory:")
    prop_hash = "sha256:" + "ee" * 32
    coordinator_t = 1700000000000

    votes = []
    for i in range(4):
        v, _ = _generate_node_vote(f"honest-node-{i}", prop_hash, round_num=1, vote_time_ms=coordinator_t)
        votes.append(v)

    with pytest.raises(ByzantineConsensusError) as exc_quorum:
        harness.evaluate_round(
            round_number=1,
            total_cluster_nodes=7,
            votes=votes,
            coordinator_now_ms=coordinator_t,
        )
    assert exc_quorum.value.code == HALT_BYZANTINE_QUORUM_UNREACHABLE
    assert "max votes 4 < threshold 5" in str(exc_quorum.value)

    # Empty vote list strictly tests default=0 boundary on line 355
    with pytest.raises(ByzantineConsensusError) as exc_zero:
        harness.evaluate_round(
            round_number=1,
            total_cluster_nodes=7,
            votes=[],
            coordinator_now_ms=coordinator_t,
        )
    assert exc_zero.value.code == HALT_BYZANTINE_QUORUM_UNREACHABLE
    assert "max votes 0 < threshold 5" in str(exc_zero.value)


def test_06_fail_closed_equivocation_detected() -> None:
    harness = ByzantineConsensusTimewarpHarness(db_path=":memory:")
    prop_hash_a = "sha256:" + "11" * 32
    prop_hash_b = "sha256:" + "22" * 32
    coordinator_t = 1700000000000

    # Node 0 double-votes (equivocates)
    priv0 = ed25519.Ed25519PrivateKey.generate()
    v0_a = ByzantineConsensusTimewarpHarness.create_vote(
        "byz-node-0", "p-1", 1, prop_hash_a, coordinator_t, priv0
    )
    v0_b = ByzantineConsensusTimewarpHarness.create_vote(
        "byz-node-0", "p-2", 1, prop_hash_b, coordinator_t + 5, priv0
    )

    votes = [v0_a, v0_b]
    for i in range(1, 6):
        v, _ = _generate_node_vote(f"node-{i}", prop_hash_a, round_num=1, vote_time_ms=coordinator_t)
        votes.append(v)

    # 1. With fail_closed_on_equivocation=True (default)
    with pytest.raises(ByzantineConsensusError) as exc_eq:
        harness.evaluate_round(
            round_number=1,
            total_cluster_nodes=7,
            votes=votes,
            coordinator_now_ms=coordinator_t,
        )
    assert exc_eq.value.code == HALT_BYZANTINE_EQUIVOCATION_DETECTED

    # 2. With fail_closed_on_equivocation=False (records fault but continues evaluation, testing line 391)
    receipt = harness.evaluate_round(
        round_number=1,
        total_cluster_nodes=7,
        votes=votes,
        coordinator_now_ms=coordinator_t,
        fail_closed_on_equivocation=False,
    )
    assert receipt.byzantine_faults_detected == 1
    assert receipt.quorum_achieved is True
    assert receipt.committed_proposal_hash == prop_hash_a

    # Verify equivocation recorded in database
    equivocations = harness.list_equivocations()
    assert len(equivocations) >= 1
    assert equivocations[0]["node_id"] == "byz-node-0"
    assert equivocations[0]["first_hash"] == prop_hash_a
    assert equivocations[0]["conflicting_hash"] == prop_hash_b
    assert equivocations[0]["round_number"] == 1


def test_07_fail_closed_clock_skew_exceeded() -> None:
    harness = ByzantineConsensusTimewarpHarness(db_path=":memory:")
    coordinator_t = 1700000000000

    # Vote timestamp 15 seconds in future (exceeds 10s ceiling)
    skewed_vote, _ = _generate_node_vote(
        "node-skewed", "sha256:" + "aa" * 32, round_num=1, vote_time_ms=coordinator_t + 15000
    )

    with pytest.raises(ByzantineConsensusError) as exc_skew:
        harness.evaluate_round(
            round_number=1,
            total_cluster_nodes=7,
            votes=[skewed_vote],
            coordinator_now_ms=coordinator_t,
        )
    assert exc_skew.value.code == HALT_BYZANTINE_CLOCK_SKEW_EXCEEDED

    # Vote timestamp 12 seconds in past
    skewed_past, _ = _generate_node_vote(
        "node-past", "sha256:" + "aa" * 32, round_num=1, vote_time_ms=coordinator_t - 12000
    )
    with pytest.raises(ByzantineConsensusError) as exc_past:
        harness.evaluate_round(
            round_number=1,
            total_cluster_nodes=7,
            votes=[skewed_past],
            coordinator_now_ms=coordinator_t,
        )
    assert exc_past.value.code == HALT_BYZANTINE_CLOCK_SKEW_EXCEEDED


def test_08_fail_closed_signature_invalid() -> None:
    harness = ByzantineConsensusTimewarpHarness(db_path=":memory:")
    vote, _ = _generate_node_vote("node-1", "sha256:" + "aa" * 32)

    corrupted_vote = ByzantineVote(
        node_id=vote.node_id,
        proposal_id=vote.proposal_id,
        round_number=vote.round_number,
        proposal_hash=vote.proposal_hash,
        vote_timestamp_ms=vote.vote_timestamp_ms,
        public_key_hex=vote.public_key_hex,
        signature="00" * 64,
    )

    with pytest.raises(ByzantineConsensusError) as exc_sig:
        harness.evaluate_round(
            round_number=1,
            total_cluster_nodes=7,
            votes=[corrupted_vote],
            coordinator_now_ms=vote.vote_timestamp_ms,
        )
    assert exc_sig.value.code == HALT_BYZANTINE_SIGNATURE_INVALID


def test_09_sqlite_persistence_and_queries() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        harness = ByzantineConsensusTimewarpHarness(db_path=db_path)
        # Check WAL mode
        mode = harness._conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal"

        prop_hash = "sha256:" + "99" * 32
        coordinator_t = 1700000000000

        votes = []
        for i in range(5):
            v, _ = _generate_node_vote(f"node-{i}", prop_hash, round_num=1, vote_time_ms=coordinator_t)
            votes.append(v)

        receipt = harness.evaluate_round(
            round_number=1,
            total_cluster_nodes=7,
            votes=votes,
            coordinator_now_ms=coordinator_t,
        )

        retrieved = harness.get_receipt(receipt.convergence_id)
        assert retrieved is not None
        assert retrieved.convergence_id == receipt.convergence_id
        assert retrieved.round_number == 1
        assert retrieved.quorum_achieved is True

        # Check raw database integer representation for quorum_achieved (line 406 true case)
        with harness._conn:
            row_true = harness._conn.execute(
                "SELECT quorum_achieved FROM byzantine_timewarp_ledger WHERE convergence_id = ?",
                (receipt.convergence_id,),
            ).fetchone()
            assert row_true is not None
            assert row_true[0] == 1

        # Check raw database integer representation for quorum_achieved (line 406 false case)
        with pytest.raises(ByzantineConsensusError):
            harness.evaluate_round(
                round_number=2,
                total_cluster_nodes=7,
                votes=votes[:2],
                coordinator_now_ms=coordinator_t,
            )
        with harness._conn:
            row_false = harness._conn.execute(
                "SELECT quorum_achieved FROM byzantine_timewarp_ledger WHERE round_number = 2"
            ).fetchone()
            assert row_false is not None
            assert row_false[0] == 0

        assert harness.get_receipt("byzconv-nonexistent") is None

        harness.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_10_exact_mutation_boundaries() -> None:
    # Test default coordinator_now_ms evaluation
    harness = ByzantineConsensusTimewarpHarness(db_path=":memory:")
    prop_hash = "sha256:" + "88" * 32
    t_now = int(time.time() * 1000)

    votes = []
    for i in range(5):
        v, _ = _generate_node_vote(f"node-{i}", prop_hash, round_num=1, vote_time_ms=t_now)
        votes.append(v)

    receipt = harness.evaluate_round(
        round_number=1,
        total_cluster_nodes=7,
        votes=votes,
    )
    assert abs(receipt.evaluated_at_ms - t_now) < 5000

    # Total nodes boundary check
    with pytest.raises(ByzantineConsensusError) as exc_nodes:
        harness.evaluate_round(1, 0, votes)
    assert exc_nodes.value.code == HALT_BYZANTINE_EMPTY_NODE_POOL

    # Verify FrozenInstanceError on receipt (kills line 103 frozen=True mutant)
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        receipt.round_number = 999

    # Verify SQLite ledger stores exact integer 1 and sorted json (kills line 391 sort_keys and line 408 constant 1)
    cursor = harness._conn.cursor()
    cursor.execute(
        "SELECT quorum_achieved, raw_receipt_json FROM byzantine_timewarp_ledger WHERE convergence_id = ?",
        (receipt.convergence_id,),
    )
    row_achieved = cursor.fetchone()
    assert row_achieved is not None
    assert row_achieved[0] == 1
    assert row_achieved[1].startswith('{"byzantine_faults_detected":')

    # Verify SQLite ledger stores exact integer 0 when quorum fails (kills line 408 constant 0)
    v_fail, _ = _generate_node_vote("node-fail", prop_hash, round_num=2, vote_time_ms=t_now)
    with pytest.raises(ByzantineConsensusError):
        harness.evaluate_round(
            round_number=2,
            total_cluster_nodes=7,
            votes=[v_fail],
            coordinator_now_ms=t_now,
        )
    cursor.execute(
        "SELECT quorum_achieved FROM byzantine_timewarp_ledger WHERE round_number = 2",
    )
    row_fail = cursor.fetchone()
    assert row_fail is not None
    assert row_fail[0] == 0

    # Verify default=0 when votes list is empty (kills line 355 constant 0 perturbation)
    with pytest.raises(ByzantineConsensusError) as exc_empty:
        harness.evaluate_round(round_number=3, total_cluster_nodes=7, votes=[])
    assert "max votes 0 < threshold" in str(exc_empty.value)


def test_11_wilson_ci_bounds_and_epistemic_lexicon() -> None:
    import src.byzantine_consensus_timewarp as mod

    doc = mod.__doc__ or ""
    assert "INTERNAL PREVIEW COMMISSIONED" in doc
    assert "prototype" in doc

    def wilson_score_interval(k: int, n: int, z: float = 1.95996) -> tuple[int, int]:
        p = k / n
        denom = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denom
        spread = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
        low = max(0.0, center - spread)
        high = min(1.0, center + spread)
        return int(round(low * 10000)), int(round(high * 10000))

    low_bps, high_bps = wilson_score_interval(30, 30)
    assert low_bps >= 8800
    assert high_bps == 10000
