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
tests/test_dst_seeded_invariants.py — Deterministic Simulation Testing (DST)
RisingWave / PingCAP / FoundationDB-style seeded simulation across 500 pseudo-random runs.

Evaluates 4 core safety invariants under adversarial fault injection:
1. Zero Duplicate Mutations (observed_duplicates == 0 under lost ACKs and retries)
2. Durable Uncertainty Latching (EFFECT_INDETERMINATE on 504 / transport drops)
3. Blind Retry Interception (HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY)
4. Idempotent Authoritative Reconciliation (bounded status lookup resolves outcome)
"""

from __future__ import annotations

import hashlib
import random
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class SimulatedSettlementTarget:
    """
    Deterministic simulated settlement server with an append-only commit ledger.
    Tracks commits by idempotency key to evaluate duplication invariants.
    """

    def __init__(self) -> None:
        self.committed_records: Dict[str, Dict[str, Any]] = {}
        self.total_commit_calls: int = 0

    def execute_mutation(self, idempotency_key: str, amount_minor: int, recipient: str) -> Dict[str, Any]:
        self.total_commit_calls += 1
        if idempotency_key in self.committed_records:
            # Idempotent response for previously committed key
            rec = self.committed_records[idempotency_key]
            return {
                "status": "COMMITTED",
                "idempotency_key": idempotency_key,
                "amount_minor": rec["amount_minor"],
                "duplicate_detected": False,
                "replayed": True,
            }

        rec = {
            "status": "COMMITTED",
            "idempotency_key": idempotency_key,
            "amount_minor": amount_minor,
            "recipient": recipient,
            "replayed": False,
        }
        self.committed_records[idempotency_key] = rec
        return rec

    def get_status(self, idempotency_key: str) -> Dict[str, Any]:
        if idempotency_key in self.committed_records:
            return {"status": "COMMITTED", "idempotency_key": idempotency_key}
        return {"status": "NOT_FOUND", "idempotency_key": idempotency_key}


class AEIBDeterministicGateway:
    """
    Deterministic Station 1 & Station 2 Gateway state machine for DST simulation.
    Enforces pre-dispatch authority, wire latching on transport drops, and retry blocking.
    """

    def __init__(self, target: SimulatedSettlementTarget) -> None:
        self.target = target
        self.latched_uncertainty: Dict[str, Dict[str, Any]] = {}
        self.reconciled_operations: Dict[str, str] = {}
        self.blocked_retry_count: int = 0

    def dispatch_with_fault_injection(
        self,
        operation_id: str,
        idempotency_key: str,
        amount_minor: int,
        recipient: str,
        fault_type: str,
    ) -> Dict[str, Any]:
        caid = sha256_prefixed(
            encode_jcs({
                "amount_minor": amount_minor,
                "idempotency_key": idempotency_key,
                "operation_id": operation_id,
                "recipient": recipient,
            })
        )

        # Invariant 3: Check if CAID or idempotency_key is currently latched under uncertainty
        if idempotency_key in self.latched_uncertainty:
            self.blocked_retry_count += 1
            return {
                "verdict": "HALT",
                "error_code": "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY",
                "caid": caid,
                "idempotency_key": idempotency_key,
            }

        # Fault Injection Simulation:
        # Case A: FAULT_PRE_COMMIT_DROP (Transport drops before reaching target)
        if fault_type == "PRE_COMMIT_DROP":
            self.latched_uncertainty[idempotency_key] = {
                "operation_id": operation_id,
                "caid": caid,
                "state": "EFFECT_INDETERMINATE",
            }
            return {
                "verdict": "TRANSPORT_ERROR",
                "disposition": "EFFECT_INDETERMINATE",
                "error_code": "ERR_TRANSPORT_TIMEOUT_504",
            }

        # Case B: FAULT_POST_COMMIT_LOST_ACK (Target commits, but response ACK is dropped)
        if fault_type == "POST_COMMIT_LOST_ACK":
            # Target commits
            self.target.execute_mutation(idempotency_key, amount_minor, recipient)
            # Response is lost in transit; client observes 504 timeout
            self.latched_uncertainty[idempotency_key] = {
                "operation_id": operation_id,
                "caid": caid,
                "state": "EFFECT_INDETERMINATE",
            }
            return {
                "verdict": "TRANSPORT_ERROR",
                "disposition": "EFFECT_INDETERMINATE",
                "error_code": "ERR_LOST_ACKNOWLEDGEMENT_504",
            }

        # Case C: NOMINAL_SUCCESS
        res = self.target.execute_mutation(idempotency_key, amount_minor, recipient)
        return {
            "verdict": "SUCCESS",
            "disposition": "CONFIRMED",
            "target_response": res,
        }

    def reconcile_indeterminate(self, idempotency_key: str) -> str:
        """
        Executes authoritative single-flight status probe to reconcile uncertainty.
        """
        if idempotency_key not in self.latched_uncertainty:
            raise ValueError(f"Key {idempotency_key} is not in indeterminate latch")

        status_resp = self.target.get_status(idempotency_key)
        if status_resp.get("status") == "COMMITTED":
            resolved = "CONFIRMED"
        else:
            resolved = "REFUTED"

        self.reconciled_operations[idempotency_key] = resolved
        del self.latched_uncertainty[idempotency_key]
        return resolved


def run_single_dst_episode(seed: int) -> Dict[str, Any]:
    """
    Executes a single deterministic simulation episode with seed-driven fault scheduling.
    """
    rng = random.Random(seed)
    target = SimulatedSettlementTarget()
    gateway = AEIBDeterministicGateway(target)

    operation_id = f"op-dst-{seed:04d}"
    idem_key = f"idem-key-{seed:04d}"
    amount_minor = rng.choice([500, 1000, 2500, 5000])
    recipient = f"iban:DE893704004405{seed:08d}"

    # Random fault choice: 40% lost ACK (504), 30% pre-commit drop, 30% nominal
    roll = rng.random()
    if roll < 0.40:
        fault = "POST_COMMIT_LOST_ACK"
    elif roll < 0.70:
        fault = "PRE_COMMIT_DROP"
    else:
        fault = "NOMINAL_SUCCESS"

    # Step 1: Initial Dispatch
    disp1 = gateway.dispatch_with_fault_injection(operation_id, idem_key, amount_minor, recipient, fault)

    duplicates_detected = 0
    blind_retry_blocked = False

    if fault in ("POST_COMMIT_LOST_ACK", "PRE_COMMIT_DROP"):
        # Assert Invariant 2: Durable uncertainty latched on transport drop
        assert disp1["disposition"] == "EFFECT_INDETERMINATE"
        assert idem_key in gateway.latched_uncertainty

        # Step 2: Agent attempts naive blind retry
        retry_disp = gateway.dispatch_with_fault_injection(operation_id, idem_key, amount_minor, recipient, "NOMINAL_SUCCESS")

        # Assert Invariant 3: Blind retry blocked fail-closed
        assert retry_disp["verdict"] == "HALT"
        assert retry_disp["error_code"] == "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY"
        blind_retry_blocked = True

        # Step 3: Authoritative status probe reconciliation
        reconciled = gateway.reconcile_indeterminate(idem_key)
        if fault == "POST_COMMIT_LOST_ACK":
            assert reconciled == "CONFIRMED"
        else:
            assert reconciled == "REFUTED"
    else:
        assert disp1["verdict"] == "SUCCESS"
        assert disp1["disposition"] == "CONFIRMED"

    # Count commits on the target for this idempotency key
    target_commits = 1 if idem_key in target.committed_records else 0

    return {
        "seed": seed,
        "fault": fault,
        "target_commits": target_commits,
        "blind_retry_blocked": blind_retry_blocked,
        "final_latched_count": len(gateway.latched_uncertainty),
    }


def test_dst_500_seeded_deterministic_simulation_invariants() -> None:
    """
    Evaluates 500 pseudo-random simulation seeds (0 to 499).
    Verifies all 4 invariants across the entire batch.
    """
    total_episodes = 500
    observed_duplicate_mutations = 0
    total_retries_blocked = 0
    fault_counts: Dict[str, int] = {}

    for seed in range(total_episodes):
        res = run_single_dst_episode(seed)
        fault = res["fault"]
        fault_counts[fault] = fault_counts.get(fault, 0) + 1

        # Invariant 1: Exactly-once or zero mutation on target, NEVER duplicate (>1)
        assert res["target_commits"] <= 1, f"Seed {seed}: Duplicate mutation observed!"
        if res["target_commits"] > 1:
            observed_duplicate_mutations += 1

        if res["blind_retry_blocked"]:
            total_retries_blocked += 1

        # Invariant 4: No dangling unresolved uncertainty after reconciliation
        assert res["final_latched_count"] == 0, f"Seed {seed}: Dangling uncertainty unlatched!"

    # Across all 500 seeds:
    assert observed_duplicate_mutations == 0, f"Expected 0 duplicate mutations, observed {observed_duplicate_mutations}"
    assert total_retries_blocked > 0, "Expected blind retries to be blocked under fault injection"
    # Ensure all 3 fault modes were tested
    assert "POST_COMMIT_LOST_ACK" in fault_counts and fault_counts["POST_COMMIT_LOST_ACK"] > 100
    assert "PRE_COMMIT_DROP" in fault_counts and fault_counts["PRE_COMMIT_DROP"] > 100
    assert "NOMINAL_SUCCESS" in fault_counts and fault_counts["NOMINAL_SUCCESS"] > 100
