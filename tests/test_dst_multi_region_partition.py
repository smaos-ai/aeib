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
tests/test_dst_multi_region_partition.py — Multi-Region Partition Deterministic Simulation Testing (DST).
Evaluated under the stated model across 100 seeded pseudo-random simulation episodes.

Evaluates 4 core safety invariants:
1. Strict Majority Quorum Enforcement (>= 2 of 3 nodes) for all budget reservations.
2. Fail-Closed Minority Denial under split-brain (HALT_CONSENSUS_QUORUM_UNAVAILABLE).
3. Latch Persistence across restart (EFFECT_INDETERMINATE survives process restarts).
4. Out-of-Band State Convergence and Hash Chain Verification upon network healing.
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.eo1_write_before_execute import (
    ContinuityReceipt,
    DispatchIntentRecord,
    IntentLifecycleState,
    LatchedCaidExecutionHaltedError,
    PreDispatchIntentInterlock,
    compute_caid,
    verify_continuity_receipt,
    verify_dispatch_intent,
)
from src.jcs_canonicalizer import encode_jcs

HALT_CONSENSUS_QUORUM_UNAVAILABLE = "HALT_CONSENSUS_QUORUM_UNAVAILABLE"


class ConsensusQuorumUnavailableError(RuntimeError):
    """Raised when strict majority quorum (>= 2 of 3 nodes) cannot be established."""
    pass


class TopologySchedule(str, Enum):
    SYMMETRIC_QUORUM = "SYMMETRIC_QUORUM"
    ASYMMETRIC_ISOLATION = "ASYMMETRIC_ISOLATION"
    SPLIT_BRAIN_MAJORITY_DENIAL = "SPLIT_BRAIN_MAJORITY_DENIAL"
    HEAL_AND_RECONCILE = "HEAL_AND_RECONCILE"


@dataclass(frozen=True)
class QuorumVote:
    statement: Dict[str, Any]
    signature_b64: str
    voter_region: str
    voter_public_key_pem: str


@dataclass(frozen=True)
class DispatchReservationResult:
    committed: bool
    reservation_id: str
    caid: str
    intent_id: str
    voter_regions: List[str]
    coordinator_region: str
    quorum_certificate: Optional[Dict[str, Any]] = None
    receipt: Optional[ContinuityReceipt] = None


class RegionNode:
    """
    Regional cluster node maintaining local intent latch store and budget reservation ledger.
    Evaluated under the stated model using real PreDispatchIntentInterlock and Ed25519 keys.
    """

    def __init__(
        self,
        region_id: str,
        role: str,
        node_dir: Path,
        private_key: Ed25519PrivateKey,
    ) -> None:
        self.region_id = region_id
        self.role = role
        self.node_dir = Path(node_dir)
        self.node_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.node_dir / "ledger.jsonl"
        self.state_dir = self.node_dir / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.private_key = private_key
        self.public_key = private_key.public_key()
        self.public_key_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        self.committed_reservations: Dict[str, Dict[str, Any]] = {}
        self.interlock = PreDispatchIntentInterlock(
            ledger_path=self.ledger_path,
            output_state_dir=self.state_dir,
            boundary_private_key=self.private_key,
            authority_id=self.region_id,
        )

    def reload_interlock(self) -> None:
        """Simulates process restart: reloads state and latches from disk."""
        self.interlock = PreDispatchIntentInterlock(
            ledger_path=self.ledger_path,
            output_state_dir=self.state_dir,
            boundary_private_key=self.private_key,
            authority_id=self.region_id,
        )

    def evaluate_vote_proposal(self, proposal: Dict[str, Any]) -> QuorumVote:
        """
        Evaluates a budget reservation proposal and produces an Ed25519-signed QuorumVote.
        """
        caid = proposal["caid"]
        intent_id = proposal["intent_id"]
        reservation_id = proposal["reservation_id"]

        if self.interlock.is_caid_latched(caid):
            raise LatchedCaidExecutionHaltedError(
                f"Region {self.region_id} refused vote: CAID {caid} latched in EFFECT_INDETERMINATE"
            )

        if reservation_id in self.committed_reservations:
            existing = self.committed_reservations[reservation_id]
            if existing["caid"] != caid:
                raise ValueError(
                    f"Region {self.region_id} detected reservation conflict: "
                    f"existing CAID {existing['caid']} != proposed CAID {caid}"
                )

        vote_statement = {
            "action": "VOTE_RESERVE_BUDGET",
            "caid": caid,
            "intent_id": intent_id,
            "reservation_id": reservation_id,
            "status": "APPROVED",
            "voter_region": self.region_id,
        }
        vote_bytes = encode_jcs(vote_statement)
        sig_bytes = self.private_key.sign(vote_bytes)
        sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

        return QuorumVote(
            statement=vote_statement,
            signature_b64=sig_b64,
            voter_region=self.region_id,
            voter_public_key_pem=self.public_key_pem,
        )

    def commit_reservation_locally(
        self,
        reservation_id: str,
        caid: str,
        account_id: str,
        amount_minor: int,
        quorum_certificate: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Commits the reservation locally upon quorum approval."""
        record = {
            "account_id": account_id,
            "amount_minor": amount_minor,
            "caid": caid,
            "committed_at_utc": "2026-10-19T18:00:00Z",
            "quorum_voters": sorted(quorum_certificate["voter_regions"]),
            "reservation_id": reservation_id,
        }
        self.committed_reservations[reservation_id] = record
        return record

    def get_state_tip(self) -> str:
        """
        Computes the canonical state tip across all locally committed reservations
        using RFC 8785 JCS canonicalization.
        """
        sorted_keys = sorted(self.committed_reservations.keys())
        state_list = [self.committed_reservations[k] for k in sorted_keys]
        return hashlib.sha256(encode_jcs(state_list)).hexdigest()


class MultiRegionClusterSimulator:
    """
    3-Region Cluster Deterministic Simulator.
    Topology nodes:
      - us-east-1 (Leader)
      - eu-west-1 (Follower 1)
      - ap-northeast-1 (Follower 2)
    Evaluated under strict majority quorum (>= 2 of 3 nodes).
    """

    def __init__(
        self,
        base_dir: Path,
        keys: Optional[Dict[str, Ed25519PrivateKey]] = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.region_ids = ["us-east-1", "eu-west-1", "ap-northeast-1"]
        self.leader_region = "us-east-1"
        self.nodes: Dict[str, RegionNode] = {}

        for rid in self.region_ids:
            key = keys[rid] if keys and rid in keys else Ed25519PrivateKey.generate()
            role = "LEADER" if rid == self.leader_region else "FOLLOWER"
            node_dir = self.base_dir / rid
            self.nodes[rid] = RegionNode(
                region_id=rid,
                role=role,
                node_dir=node_dir,
                private_key=key,
            )

        self.connectivity: Dict[str, Set[str]] = {
            r: set(self.region_ids) for r in self.region_ids
        }
        self.current_schedule = TopologySchedule.SYMMETRIC_QUORUM

    def set_topology(self, schedule: TopologySchedule) -> None:
        """Configures cluster network partition topology according to schedule."""
        self.current_schedule = schedule
        if schedule in (TopologySchedule.SYMMETRIC_QUORUM, TopologySchedule.HEAL_AND_RECONCILE):
            self.connectivity = {r: set(self.region_ids) for r in self.region_ids}
        elif schedule == TopologySchedule.ASYMMETRIC_ISOLATION:
            majority = {"us-east-1", "eu-west-1"}
            self.connectivity = {
                "us-east-1": majority,
                "eu-west-1": majority,
                "ap-northeast-1": {"ap-northeast-1"},
            }
        elif schedule == TopologySchedule.SPLIT_BRAIN_MAJORITY_DENIAL:
            followers = {"eu-west-1", "ap-northeast-1"}
            self.connectivity = {
                "us-east-1": {"us-east-1"},
                "eu-west-1": followers,
                "ap-northeast-1": followers,
            }

    def can_communicate(self, sender: str, recipient: str) -> bool:
        return recipient in self.connectivity.get(sender, set())

    def restart_node(self, region_id: str) -> None:
        """Simulates node crash and restart, testing on-disk state recovery."""
        self.nodes[region_id].reload_interlock()

    def dispatch_reservation(
        self,
        reservation_id: str,
        amount_minor: int,
        account_id: str = "acct-treasury",
        idempotency_key: Optional[str] = None,
        coordinator_region: Optional[str] = None,
        bypass_quorum: bool = False,
    ) -> DispatchReservationResult:
        """
        Coordinates a budget reservation under strict majority quorum requirements (>= 2 of 3 nodes).
        If bypass_quorum is True (negative control), commits without majority quorum.
        """
        coordinator_id = coordinator_region or self.leader_region
        coordinator = self.nodes[coordinator_id]
        idempotency_key = idempotency_key or f"idem-{reservation_id}"

        payload = {
            "account_id": account_id,
            "amount_minor": amount_minor,
            "idempotency_key": idempotency_key,
            "reservation_id": reservation_id,
        }
        caid = compute_caid(payload)
        target_uri = f"https://ledger.{coordinator_id}.internal/v1/reserve"
        intent_id = f"intent-{reservation_id}"

        # Step 1: Pre-dispatch Intent Recording on coordinator (EO-1)
        intent_record = coordinator.interlock.record_intent(
            target_uri=target_uri,
            tool_name="budget_reservation",
            payload=payload,
            intent_id=intent_id,
        )

        proposal = {
            "account_id": account_id,
            "action": "RESERVE_BUDGET",
            "amount_minor": amount_minor,
            "caid": caid,
            "intent_id": intent_id,
            "payload_digest": intent_record.payload_digest,
            "policy_epoch": 1,
            "proposer_region": coordinator_id,
            "reservation_id": reservation_id,
        }

        # Step 2: Quorum Collection
        reachable_nodes = [
            node for node in self.nodes.values()
            if self.can_communicate(coordinator_id, node.region_id)
        ]

        valid_votes: List[QuorumVote] = []
        for node in reachable_nodes:
            try:
                vote = node.evaluate_vote_proposal(proposal)
                # Verify cryptographic signature of vote
                vote_bytes = encode_jcs(vote.statement)
                sig_bytes = base64.b64decode(vote.signature_b64)
                node.public_key.verify(sig_bytes, vote_bytes)
                valid_votes.append(vote)
            except (LatchedCaidExecutionHaltedError, ValueError, InvalidSignature):
                continue

        strict_majority = (len(self.nodes) // 2) + 1  # 2 of 3

        # Quorum evaluation:
        if not bypass_quorum and len(valid_votes) < strict_majority:
            # Consensus fails closed!
            coordinator.interlock.latch_intent(
                caid=caid,
                reason=HALT_CONSENSUS_QUORUM_UNAVAILABLE,
                intent_id=intent_id,
                target_uri=target_uri,
                tool_name="budget_reservation",
            )
            raise ConsensusQuorumUnavailableError(
                f"{HALT_CONSENSUS_QUORUM_UNAVAILABLE}: strict majority quorum (>= {strict_majority} of {len(self.nodes)} nodes) "
                f"unreachable by coordinator {coordinator_id}. Valid votes observed: {len(valid_votes)}."
            )

        # Step 3: Quorum Certificate & Commit
        quorum_certificate = {
            "action": "QUORUM_CERTIFICATE",
            "caid": caid,
            "intent_id": intent_id,
            "reservation_id": reservation_id,
            "vote_signatures": [v.signature_b64 for v in valid_votes],
            "voter_regions": [v.voter_region for v in valid_votes],
        }

        # Commit to all reachable nodes participating in the quorum
        commit_nodes = reachable_nodes if not bypass_quorum else [coordinator]
        for node in commit_nodes:
            node.commit_reservation_locally(
                reservation_id=reservation_id,
                caid=caid,
                account_id=account_id,
                amount_minor=amount_minor,
                quorum_certificate=quorum_certificate,
            )
            if node.region_id != coordinator_id:
                try:
                    node.interlock.record_intent(
                        target_uri=target_uri,
                        tool_name="budget_reservation",
                        payload=payload,
                        intent_id=f"{intent_id}-{node.region_id}",
                    )
                except LatchedCaidExecutionHaltedError:
                    pass
                node.interlock._emit_receipt(
                    intent_id=f"{intent_id}-{node.region_id}",
                    caid=caid,
                    status="RECONCILED",
                    lifecycle_state="RECONCILED",
                    retry_safe=False,
                    details={
                        "quorum_certificate": quorum_certificate,
                        "reservation_id": reservation_id,
                    },
                )

        receipt = coordinator.interlock._emit_receipt(
            intent_id=intent_id,
            caid=caid,
            status="RECONCILED",
            lifecycle_state="RECONCILED",
            retry_safe=False,
            details={
                "quorum_certificate": quorum_certificate,
                "reservation_id": reservation_id,
            },
        )

        return DispatchReservationResult(
            committed=True,
            reservation_id=reservation_id,
            caid=caid,
            intent_id=intent_id,
            voter_regions=[v.voter_region for v in valid_votes],
            coordinator_region=coordinator_id,
            quorum_certificate=quorum_certificate,
            receipt=receipt,
        )

    def reconcile_minority_node(
        self,
        minority_region: str,
        majority_source_region: str = "eu-west-1",
    ) -> Dict[str, Any]:
        """
        Reconciles an isolated minority node with the majority state tip:
        1. Fetches canonical committed ledger entries from majority.
        2. Re-verifies hash chain tips and signatures.
        3. Converges local budget reservation ledger.
        4. Clears latches on uncommitted failed intents via out-of-band reconciliation.
        """
        minority_node = self.nodes[minority_region]
        source_node = self.nodes[majority_source_region]

        # Sync committed reservations
        synced_count = 0
        for res_id, res_data in source_node.committed_reservations.items():
            if res_id not in minority_node.committed_reservations:
                minority_node.committed_reservations[res_id] = dict(res_data)
                synced_count += 1

        # Resolve latched intents in minority node
        latched = minority_node.interlock.get_latched_caids()
        cleared_latches = []
        for caid, latch_state in latched.items():
            committed_in_majority = any(
                r["caid"] == caid for r in source_node.committed_reservations.values()
            )
            status = "RECONCILED_COMMITTED" if committed_in_majority else "RECONCILED_ABORTED_QUORUM_UNAVAILABLE"
            minority_node.interlock.reconcile_out_of_band(
                caid=caid,
                reconciliation_evidence={
                    "converged_source": majority_source_region,
                    "status": status,
                },
                intent_id=latch_state.intent_id,
            )
            cleared_latches.append(caid)

        # Re-verify ledger records and hash chain links from source node
        source_ledger_records = []
        previous_chain_tip = hashlib.sha256(b"aeib-eo1-chain-genesis").hexdigest()
        if source_node.ledger_path.exists():
            with open(source_node.ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if rec.get("record_type") == "CONTINUITY_RECEIPT":
                        verify_continuity_receipt(rec, source_node.public_key)
                        assert rec["chain_tip"] == previous_chain_tip, (
                            f"Hash chain link mismatch: expected {previous_chain_tip}, observed {rec['chain_tip']}"
                        )
                        stmt = {
                            "caid": rec["caid"],
                            "chain_tip": rec["chain_tip"],
                            "intent_id": rec["intent_id"],
                            "lifecycle_state": rec["lifecycle_state"],
                            "policy_epoch": rec["policy_epoch"],
                            "reconciled_at": rec["reconciled_at"],
                            "reconciliation_details": rec.get("reconciliation_details", {}),
                            "record_type": rec["record_type"],
                            "retry_safe": rec["retry_safe"],
                            "schema_version": rec["schema_version"],
                            "status": rec["status"],
                        }
                        previous_chain_tip = hashlib.sha256(encode_jcs(stmt)).hexdigest()
                    elif rec.get("record_type") == "DISPATCH_INTENT":
                        verify_dispatch_intent(rec, source_node.public_key)
                    source_ledger_records.append(rec)

        return {
            "cleared_latches": cleared_latches,
            "minority_region": minority_region,
            "synced_reservations": synced_count,
            "verified_ledger_records": len(source_ledger_records),
        }

    def count_conflicting_reservations(self) -> int:
        """
        Evaluates the entire cluster for split-brain double reservations or conflicting payloads.
        Returns the number of conflicting reservation IDs observed.
        """
        all_reservations: Dict[str, List[tuple[str, str, int]]] = {}
        for rid, node in self.nodes.items():
            for res_id, data in node.committed_reservations.items():
                if res_id not in all_reservations:
                    all_reservations[res_id] = []
                all_reservations[res_id].append((rid, data["caid"], data["amount_minor"]))

        conflicts = 0
        for res_id, entries in all_reservations.items():
            first_caid = entries[0][1]
            first_amt = entries[0][2]
            for node_id, caid, amt in entries[1:]:
                if caid != first_caid or amt != first_amt:
                    conflicts += 1
                    break
        return conflicts


def run_single_dst_episode(seed: int, base_dir: Path) -> Dict[str, Any]:
    """
    Executes a single deterministic simulation episode across the 4 network topology schedules.
    """
    rng = random.Random(seed)
    ep_dir = base_dir / f"ep_{seed:04d}"
    ep_dir.mkdir(parents=True, exist_ok=True)

    sim = MultiRegionClusterSimulator(base_dir=ep_dir)

    # -------------------------------------------------------------------------
    # Schedule A: SYMMETRIC_QUORUM
    # All 3 nodes communicate normally.
    # -------------------------------------------------------------------------
    sim.set_topology(TopologySchedule.SYMMETRIC_QUORUM)
    amt_a = rng.choice([1000, 2500, 5000])
    res_id_a = f"res-symm-{seed:04d}"
    res_a = sim.dispatch_reservation(
        reservation_id=res_id_a,
        amount_minor=amt_a,
        account_id="acct-treasury",
    )
    assert res_a.committed is True
    assert len(res_a.voter_regions) == 3
    for node in sim.nodes.values():
        assert res_id_a in node.committed_reservations

    # -------------------------------------------------------------------------
    # Schedule B: ASYMMETRIC_ISOLATION
    # ap-northeast-1 is isolated. Strict majority quorum (us-east-1 + eu-west-1) commits.
    # -------------------------------------------------------------------------
    sim.set_topology(TopologySchedule.ASYMMETRIC_ISOLATION)
    amt_b = rng.choice([1500, 3000, 7500])
    res_id_b = f"res-asymm-{seed:04d}"
    res_b = sim.dispatch_reservation(
        reservation_id=res_id_b,
        amount_minor=amt_b,
        account_id="acct-treasury",
    )
    assert res_b.committed is True
    assert set(res_b.voter_regions) == {"us-east-1", "eu-west-1"}
    assert res_id_b in sim.nodes["us-east-1"].committed_reservations
    assert res_id_b in sim.nodes["eu-west-1"].committed_reservations
    assert res_id_b not in sim.nodes["ap-northeast-1"].committed_reservations

    # -------------------------------------------------------------------------
    # Schedule C: SPLIT_BRAIN_MAJORITY_DENIAL
    # Leader us-east-1 is partitioned off from followers.
    # Minority leader attempts dispatch but fails closed with HALT_CONSENSUS_QUORUM_UNAVAILABLE!
    # -------------------------------------------------------------------------
    sim.set_topology(TopologySchedule.SPLIT_BRAIN_MAJORITY_DENIAL)
    amt_c = rng.choice([2000, 4000, 8000])
    res_id_c = f"res-split-{seed:04d}"
    caid_c = compute_caid({
        "account_id": "acct-treasury",
        "amount_minor": amt_c,
        "idempotency_key": f"idem-{res_id_c}",
        "reservation_id": res_id_c,
    })

    # Minority leader attempts dispatch:
    minority_failed_closed = False
    try:
        sim.dispatch_reservation(
            reservation_id=res_id_c,
            amount_minor=amt_c,
            account_id="acct-treasury",
            coordinator_region="us-east-1",
        )
    except ConsensusQuorumUnavailableError as err:
        assert HALT_CONSENSUS_QUORUM_UNAVAILABLE in str(err)
        minority_failed_closed = True

    assert minority_failed_closed is True
    assert res_id_c not in sim.nodes["us-east-1"].committed_reservations
    assert sim.nodes["us-east-1"].interlock.is_caid_latched(caid_c)

    # Latch persistence: simulate host crash and restart on us-east-1
    sim.restart_node("us-east-1")
    assert sim.nodes["us-east-1"].interlock.is_caid_latched(caid_c)

    # Verify blind retry is blocked fail-closed on restarted node
    blind_retry_blocked = False
    try:
        sim.nodes["us-east-1"].interlock.record_intent(
            target_uri="https://ledger.us-east-1.internal/v1/reserve",
            tool_name="budget_reservation",
            payload={
                "account_id": "acct-treasury",
                "amount_minor": amt_c,
                "idempotency_key": f"idem-{res_id_c}",
                "reservation_id": res_id_c,
            },
        )
    except LatchedCaidExecutionHaltedError:
        blind_retry_blocked = True
    assert blind_retry_blocked is True

    # Majority partition (eu-west-1 + ap-northeast-1) can make progress independently:
    amt_maj = rng.choice([500, 1200, 3500])
    res_id_maj = f"res-maj-{seed:04d}"
    res_maj = sim.dispatch_reservation(
        reservation_id=res_id_maj,
        amount_minor=amt_maj,
        account_id="acct-treasury",
        coordinator_region="eu-west-1",
    )
    assert res_maj.committed is True
    assert set(res_maj.voter_regions) == {"eu-west-1", "ap-northeast-1"}
    assert res_id_maj in sim.nodes["eu-west-1"].committed_reservations
    assert res_id_maj in sim.nodes["ap-northeast-1"].committed_reservations
    assert res_id_maj not in sim.nodes["us-east-1"].committed_reservations

    # -------------------------------------------------------------------------
    # Schedule D: HEAL_AND_RECONCILE
    # Partition heals; minority node fetches canonical entries from majority,
    # re-verifies hash chain tips, and converges to identical state tip.
    # -------------------------------------------------------------------------
    sim.set_topology(TopologySchedule.HEAL_AND_RECONCILE)

    # Reconcile minority node us-east-1 from majority node eu-west-1
    sim.reconcile_minority_node("us-east-1", majority_source_region="eu-west-1")
    # Reconcile follower ap-northeast-1 from majority node eu-west-1
    sim.reconcile_minority_node("ap-northeast-1", majority_source_region="eu-west-1")

    # State tip convergence verification
    tip_us = sim.nodes["us-east-1"].get_state_tip()
    tip_eu = sim.nodes["eu-west-1"].get_state_tip()
    tip_ap = sim.nodes["ap-northeast-1"].get_state_tip()
    assert tip_us == tip_eu == tip_ap

    # Verify all latches cleared
    assert len(sim.nodes["us-east-1"].interlock.get_latched_caids()) == 0
    assert len(sim.nodes["eu-west-1"].interlock.get_latched_caids()) == 0
    assert len(sim.nodes["ap-northeast-1"].interlock.get_latched_caids()) == 0

    # Verify zero conflicting reservations across cluster
    conflicts = sim.count_conflicting_reservations()
    assert conflicts == 0

    return {
        "seed": seed,
        "conflicts": conflicts,
        "minority_failed_closed": minority_failed_closed,
        "blind_retry_blocked": blind_retry_blocked,
        "final_state_tip": tip_us,
    }


def test_dst_100_seeds_multi_region_partition_matrix(tmp_path: Path) -> None:
    """
    Evaluates 100 pseudo-random simulation seeds (seed=0 to seed=99).
    Verifies that across all 100 seeds:
      1. Zero double-reservations occur.
      2. Minority partition strictly fails closed under isolation.
      3. Latched EFFECT_INDETERMINATE states survive restart and converge upon network healing.
      4. All 3 regional nodes converge to the identical state tip.
    """
    total_episodes = 100
    observed_double_reservations = 0
    total_minority_failures_closed = 0
    total_blind_retries_blocked = 0

    for seed in range(total_episodes):
        res = run_single_dst_episode(seed, tmp_path)
        if res["conflicts"] > 0:
            observed_double_reservations += res["conflicts"]
        if res["minority_failed_closed"]:
            total_minority_failures_closed += 1
        if res["blind_retry_blocked"]:
            total_blind_retries_blocked += 1

    assert observed_double_reservations == 0, (
        f"Expected 0 double reservations across {total_episodes} seeds, observed {observed_double_reservations}"
    )
    assert total_minority_failures_closed == total_episodes, (
        f"Expected {total_episodes} minority fail-closed events, observed {total_minority_failures_closed}"
    )
    assert total_blind_retries_blocked == total_episodes, (
        f"Expected {total_episodes} blind retries blocked, observed {total_blind_retries_blocked}"
    )


def test_dst_negative_control_quorum_bypass_causes_double_reservation(tmp_path: Path) -> None:
    """
    Non-tautological negative control:
    Demonstrates that if quorum enforcement is bypassed during a split-brain partition,
    both isolated partitions commit independent conflicting reservations for the same reservation ID,
    causing double-reservation. Proves the test harness and safety boundary can fail.
    """
    sim = MultiRegionClusterSimulator(base_dir=tmp_path / "neg_control")

    # Set split-brain topology: us-east-1 partitioned from eu-west-1 and ap-northeast-1
    sim.set_topology(TopologySchedule.SPLIT_BRAIN_MAJORITY_DENIAL)

    res_id_conflict = "res-conflict-0001"
    account_id = "acct-treasury"

    # Partition 1: us-east-1 coordinates reservation with bypass_quorum=True (un-governed)
    sim.dispatch_reservation(
        reservation_id=res_id_conflict,
        amount_minor=10000,
        account_id=account_id,
        idempotency_key="idem-conflict-p1",
        coordinator_region="us-east-1",
        bypass_quorum=True,
    )
    assert res_id_conflict in sim.nodes["us-east-1"].committed_reservations

    # Partition 2: eu-west-1 coordinates conflicting reservation for same reservation_id
    sim.dispatch_reservation(
        reservation_id=res_id_conflict,
        amount_minor=20000,
        account_id=account_id,
        idempotency_key="idem-conflict-p2",
        coordinator_region="eu-west-1",
        bypass_quorum=False,  # Quorum of 2 (eu-west-1 + ap-northeast-1) succeeds
    )
    assert res_id_conflict in sim.nodes["eu-west-1"].committed_reservations

    # Evaluate conflicts: both partitions committed res_id_conflict with divergent amounts/CAIDs!
    conflicts = sim.count_conflicting_reservations()
    assert conflicts > 0, "Expected conflicting double reservation under negative control quorum bypass!"
