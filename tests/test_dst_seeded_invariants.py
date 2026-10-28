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

Evaluates 4 core safety invariants driving real PreDispatchIntentInterlock:
1. Zero Duplicate Mutations: every call that reaches the simulated target's commit
   endpoint is counted per idempotency key; the count must never exceed 1 under lost
   ACKs, crash/restart, blind retries and post-resolution re-sends.
2. Durable Uncertainty Latching (EFFECT_INDETERMINATE on 504 / transport drops)
3. Blind Retry Interception (LatchedCaidExecutionHaltedError after process restart)
4. Idempotent Authoritative Reconciliation (bounded status lookup resolves outcome)

Negative controls:
- Un-governed retry without the interlock duplicates the mutation.
- A subclass of the real interlock whose admission gate (latch / committed / unresolved
  checks) is disabled makes the same DST harness observe duplicate commit calls, so the
  invariant-1 assertion can fail if the latch regresses.
"""

from __future__ import annotations

import hashlib
import random
import sys
from pathlib import Path
from typing import Any, Dict, Type

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.eo1_write_before_execute import (
    CaidAlreadyCommittedError,
    IntentLifecycleState,
    LatchedCaidExecutionHaltedError,
    PreDispatchIntentInterlock,
    compute_caid,
)
from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class SimulatedSettlementTarget:
    """
    Deterministic simulated settlement server with an append-only commit ledger.
    Tracks commits by idempotency key to evaluate duplication invariants.
    Every call reaching the commit endpoint is counted per key in commit_calls_by_key
    (including idempotent replays): a replay means the agent re-sent a mutation.
    """

    def __init__(self) -> None:
        self.committed_records: Dict[str, Dict[str, Any]] = {}
        self.total_commit_calls: int = 0
        self.commit_calls_by_key: Dict[str, int] = {}

    def execute_mutation(self, idempotency_key: str, amount_minor: int, recipient: str) -> Dict[str, Any]:
        self.total_commit_calls += 1
        self.commit_calls_by_key[idempotency_key] = self.commit_calls_by_key.get(idempotency_key, 0) + 1
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

    def execute_mutation_non_idempotent(self, amount_minor: int, recipient: str) -> Dict[str, Any]:
        """Simulates non-idempotent settlement endpoint where duplicate calls cause duplicate financial disbursals."""
        self.total_commit_calls += 1
        txn_id = f"txn-{self.total_commit_calls:06d}"
        rec = {
            "status": "COMMITTED",
            "txn_id": txn_id,
            "amount_minor": amount_minor,
            "recipient": recipient,
        }
        self.committed_records[txn_id] = rec
        return rec

    def get_status(self, idempotency_key: str) -> Dict[str, Any]:
        if idempotency_key in self.committed_records:
            return {"status": "COMMITTED", "idempotency_key": idempotency_key}
        return {"status": "NOT_FOUND", "idempotency_key": idempotency_key}


class _MutantInterlockAdmissionGateDisabled(PreDispatchIntentInterlock):
    """
    Negative-control mutant: the real interlock with its admission gate (latch check,
    committed-CAID check and unresolved-intent check) disabled. Durable intent/receipt/latch
    writes are unchanged. The DST harness must observe duplicate commit calls with this class.
    """

    def _check_admissible(self, caid: str) -> None:
        self.skipped_admission_caids = getattr(self, "skipped_admission_caids", []) + [caid]


def run_single_dst_episode(
    seed: int,
    base_dir: Path,
    boundary_key: Ed25519PrivateKey,
    interlock_cls: Type[PreDispatchIntentInterlock] = PreDispatchIntentInterlock,
) -> Dict[str, Any]:
    """
    Executes a single deterministic simulation episode driving real PreDispatchIntentInterlock
    (or a subclass) with seed-driven fault scheduling and on-disk crash/restart recovery.
    Records observations only; invariants are asserted by the caller so that the same
    harness can evaluate the negative-control mutant.
    """
    rng = random.Random(seed)
    ep_dir = base_dir / f"ep_{seed:04d}"
    ep_dir.mkdir(parents=True, exist_ok=True)

    ledger_path = ep_dir / "ledger.jsonl"
    state_dir = ep_dir / "state"

    # Instantiate real PreDispatchIntentInterlock on disk
    interlock = interlock_cls(
        ledger_path=ledger_path,
        output_state_dir=state_dir,
        boundary_private_key=boundary_key,
    )
    target = SimulatedSettlementTarget()

    operation_id = f"op-dst-{seed:04d}"
    idem_key = f"idem-key-{seed:04d}"
    amount_minor = rng.choice([500, 1000, 2500, 5000])
    recipient = f"iban:DE893704004405{seed:08d}"

    payload = {
        "amount_minor": amount_minor,
        "idempotency_key": idem_key,
        "operation_id": operation_id,
        "recipient": recipient,
    }
    caid = compute_caid(payload)
    target_uri = "https://settlement.local.internal/v1/disburse"

    # Random fault choice: 40% lost ACK (504), 30% pre-commit drop, 30% nominal
    roll = rng.random()
    if roll < 0.40:
        fault = "POST_COMMIT_LOST_ACK"
    elif roll < 0.70:
        fault = "PRE_COMMIT_DROP"
    else:
        fault = "NOMINAL_SUCCESS"

    def dispatch_call() -> Dict[str, Any]:
        if fault == "POST_COMMIT_LOST_ACK":
            target.execute_mutation(idem_key, amount_minor, recipient)
            raise TimeoutError("504 Gateway Timeout: lost ACK on response wire")
        elif fault == "PRE_COMMIT_DROP":
            raise ConnectionResetError("TCP Connection Reset: dropped before target execution")
        else:
            return target.execute_mutation(idem_key, amount_minor, recipient)

    def naive_resend(active: PreDispatchIntentInterlock) -> str:
        try:
            active.dispatch(
                target_uri=target_uri,
                tool_name="financial_refund",
                payload=payload,
                dispatch_fn=lambda: target.execute_mutation(idem_key, amount_minor, recipient),
            )
            return "ADMITTED"
        except CaidAlreadyCommittedError:
            return "DENY_ALREADY_COMMITTED"
        except LatchedCaidExecutionHaltedError:
            return "DENY_LATCHED"

    obs: Dict[str, Any] = {
        "seed": seed,
        "fault": fault,
        "initial_dispatch_raised": False,
        "latched_after_fault": False,
        "latched_after_restart": False,
        "blind_retry_blocked": False,
        "blind_retry_target_calls": 0,
        "nominal_reconciled": False,
    }

    # Step 1: Initial Dispatch
    if fault in ("POST_COMMIT_LOST_ACK", "PRE_COMMIT_DROP"):
        try:
            interlock.dispatch(
                target_uri=target_uri,
                tool_name="financial_refund",
                payload=payload,
                dispatch_fn=dispatch_call,
            )
        except RuntimeError:
            obs["initial_dispatch_raised"] = True

        # Invariant 2: Durable uncertainty latched on transport drop
        obs["latched_after_fault"] = interlock.is_caid_latched(caid)

        # Step 2: Crash & Restart Recovery Simulation
        # Simulate host process crash: instantiate a new interlock from disk
        restarted_interlock = interlock_cls(
            ledger_path=ledger_path,
            output_state_dir=state_dir,
            boundary_private_key=boundary_key,
        )
        obs["latched_after_restart"] = restarted_interlock.is_caid_latched(caid)

        # Step 3: Agent attempts naive blind retry; count calls that reach the target
        calls_before_retry = target.commit_calls_by_key.get(idem_key, 0)
        obs["blind_retry_blocked"] = naive_resend(restarted_interlock) != "ADMITTED"
        obs["blind_retry_target_calls"] = target.commit_calls_by_key.get(idem_key, 0) - calls_before_retry

        # Step 4: Authoritative Status Probe Reconciliation
        status_resp = target.get_status(idem_key)
        obs["probe_status"] = status_resp["status"]
        if status_resp["status"] == "COMMITTED":
            reconciliation_evidence = {"status": "COMMITTED", "target_observed": True}
        else:
            reconciliation_evidence = {"status": "NOT_FOUND", "target_observed": False}

        if restarted_interlock.is_caid_latched(caid):
            receipt = restarted_interlock.reconcile_out_of_band(
                caid=caid,
                reconciliation_evidence=reconciliation_evidence,
            )
            obs["reconcile_lifecycle_state"] = receipt.lifecycle_state
        obs["latched_after_reconcile"] = restarted_interlock.is_caid_latched(caid)
        active_interlock = restarted_interlock
    else:
        disp = interlock.dispatch(
            target_uri=target_uri,
            tool_name="financial_refund",
            payload=payload,
            dispatch_fn=dispatch_call,
        )
        obs["nominal_reconciled"] = disp.lifecycle_state == IntentLifecycleState.RECONCILED
        active_interlock = interlock

    # Step 5: Post-resolution re-sends (agent re-issues the same action twice)
    obs["post_resolution_resends"] = [naive_resend(active_interlock), naive_resend(active_interlock)]

    # Invariant 1 input: REAL number of calls that reached the target commit endpoint for this key
    obs["target_commit_calls"] = target.commit_calls_by_key.get(idem_key, 0)
    obs["final_latched_count"] = len(active_interlock.get_latched_caids())
    return obs


def count_invariant_1_violations(results: list) -> int:
    """Invariant 1: number of episodes where the target commit endpoint was called more than once."""
    return sum(1 for res in results if res["target_commit_calls"] > 1)


def test_dst_500_seeded_deterministic_simulation_invariants(tmp_path: Path) -> None:
    """
    Evaluates 500 pseudo-random simulation seeds (0 to 499) driving real PreDispatchIntentInterlock.
    Verifies all 4 invariants across the entire batch with on-disk state recovery.
    """
    total_episodes = 500
    total_retries_blocked = 0
    fault_counts: Dict[str, int] = {}
    boundary_key = Ed25519PrivateKey.generate()
    results = []

    for seed in range(total_episodes):
        res = run_single_dst_episode(seed, tmp_path, boundary_key)
        results.append(res)
        fault = res["fault"]
        fault_counts[fault] = fault_counts.get(fault, 0) + 1

        # Invariant 1: exactly one real commit call per key (never zero for a resolved
        # episode, NEVER a duplicate), counted at the target.
        assert res["target_commit_calls"] == 1, (
            f"Seed {seed} ({fault}): target commit endpoint called {res['target_commit_calls']} times"
        )

        if fault == "NOMINAL_SUCCESS":
            assert res["nominal_reconciled"], f"Seed {seed}: nominal dispatch not RECONCILED"
            assert res["post_resolution_resends"] == ["DENY_ALREADY_COMMITTED", "DENY_ALREADY_COMMITTED"], (
                f"Seed {seed}: re-send after clean success not refused: {res['post_resolution_resends']}"
            )
        else:
            assert res["initial_dispatch_raised"], f"Seed {seed}: Expected dispatch to fail on wire fault"
            # Invariant 2: durable uncertainty latched on transport drop and across restart
            assert res["latched_after_fault"], f"Seed {seed}: CAID not latched on wire fault"
            assert res["latched_after_restart"], f"Seed {seed}: CAID failed to recover latch from disk on restart"
            # Invariant 3: blind retry intercepted with zero calls reaching the target
            assert res["blind_retry_blocked"], f"Seed {seed}: Expected LatchedCaidExecutionHaltedError on blind retry"
            assert res["blind_retry_target_calls"] == 0, f"Seed {seed}: Target commit called during blocked retry"
            # Invariant 4: authoritative reconciliation clears the latch
            assert res["reconcile_lifecycle_state"] == "RECONCILED"
            assert not res["latched_after_reconcile"], f"Seed {seed}: Latch not cleared after reconciliation"
            if fault == "POST_COMMIT_LOST_ACK":
                assert res["probe_status"] == "COMMITTED"
                assert res["post_resolution_resends"] == ["DENY_ALREADY_COMMITTED", "DENY_ALREADY_COMMITTED"], (
                    f"Seed {seed}: re-send after reconcile-COMMITTED not refused: {res['post_resolution_resends']}"
                )
            else:
                assert res["probe_status"] == "NOT_FOUND"
                assert res["post_resolution_resends"] == ["ADMITTED", "DENY_ALREADY_COMMITTED"], (
                    f"Seed {seed}: NOT_COMMITTED must admit exactly one fresh attempt: {res['post_resolution_resends']}"
                )

        if res["blind_retry_blocked"]:
            total_retries_blocked += 1

        # Invariant 4: No dangling unresolved uncertainty after reconciliation
        assert res["final_latched_count"] == 0, f"Seed {seed}: Dangling uncertainty unlatched!"

    # Across all 500 seeds:
    observed_duplicate_mutations = count_invariant_1_violations(results)
    assert observed_duplicate_mutations == 0, f"Expected 0 duplicate mutations, observed {observed_duplicate_mutations}"
    assert total_retries_blocked > 0, "Expected blind retries to be blocked under fault injection"
    # Ensure all 3 fault modes were tested
    assert "POST_COMMIT_LOST_ACK" in fault_counts and fault_counts["POST_COMMIT_LOST_ACK"] > 100
    assert "PRE_COMMIT_DROP" in fault_counts and fault_counts["PRE_COMMIT_DROP"] > 100
    assert "NOMINAL_SUCCESS" in fault_counts and fault_counts["NOMINAL_SUCCESS"] > 100


def test_dst_mutant_admission_gate_disabled_is_detected(tmp_path: Path) -> None:
    """
    Mutant negative control: the same DST harness driving a subclass of the real interlock with
    the latch/admission gate disabled must observe duplicate commit calls. This demonstrates
    that the invariant-1 check above can fail if the latch regresses.
    """
    boundary_key = Ed25519PrivateKey.generate()
    results = [
        run_single_dst_episode(seed, tmp_path, boundary_key, interlock_cls=_MutantInterlockAdmissionGateDisabled)
        for seed in range(60)
    ]
    violations = count_invariant_1_violations(results)
    lost_ack = [r for r in results if r["fault"] == "POST_COMMIT_LOST_ACK"]
    assert lost_ack, "mutant run must include lost-ACK episodes"
    assert violations > 0, "DST harness failed to detect duplicates with the admission gate disabled"
    # Every lost-ACK episode re-sends through the mutant after restart: the duplicate reaches the target.
    assert all(r["blind_retry_target_calls"] == 1 and r["target_commit_calls"] > 1 for r in lost_ack)
    assert not any(r["blind_retry_blocked"] for r in results)


def test_dst_negative_control_unlatched_retry_causes_duplication() -> None:
    """
    Negative Control: Demonstrates that without PreDispatchIntentInterlock,
    an un-governed agent naively retrying on lost ACK (HTTP 504) executes
    the mutation multiple times on the target, resulting in duplication.
    Proves that the test harness and safety boundary are non-tautological.
    """
    target = SimulatedSettlementTarget()
    amount_minor = 2500_00
    recipient = "iban:DE89370400440500999999"

    # Step 1: Un-governed dispatch experiences lost ACK after commit
    # Target commits first call
    target.execute_mutation_non_idempotent(amount_minor, recipient)
    # Network transport drops the response; un-governed agent observes 504 timeout

    # Step 2: Un-governed agent naively retries without AEIB interlock or latch
    # Naive retry executes a second mutation on target
    target.execute_mutation_non_idempotent(amount_minor, recipient)

    # In the absence of AEIB PreDispatchIntentInterlock, 2 mutations occurred
    assert target.total_commit_calls == 2
    assert len(target.committed_records) == 2, "Un-governed retry produced duplicate disbursement records"
