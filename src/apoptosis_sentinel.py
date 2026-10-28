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
src/apoptosis_sentinel.py
================================================================================
D3 & D4 Delivery: Digital Apoptosis Sentinel & Verification Tax / PQC Benchmark.

Evaluated under the stated model:
1. `DigitalApoptosisSentinel` (D3):
   Monitors multi-turn agent context stability (constraint recall, contract signature
   parity, and MAGS invariant health). If stability drops below the configured
   threshold (`min_stability_bps = 6200`), or if static AST or formal proofs fail,
   it triggers `HALT_CONTEXT_DRIFT_APOPTOSIS_TRIGGERED`, wipes the drifted candidate
   memory, and regrows the service cleanly from the immutable `FormalIntentSpec` and
   `seed_snapshot_caid`.
2. `VerificationTaxBenchmark` (D4):
   Measures Production-Qualified Change (PQC), downstream manual review minutes,
   and behavioral regression escape rates comparing an Ungoverned SWE Baseline
   against the Neurosymbolic Homeostatic Harness.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set

from src.formal_mags_gate import (
    FormalIntentSpec,
    FormalMAGSGate,
    MAGSVerificationReceipt,
)


def sha256_text(text: str) -> str:
    """Computes prefixed SHA-256 digest of utf-8 text."""
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


# ============================================================================
# D3: Digital Apoptosis Sentinel
# ============================================================================
@dataclass(frozen=True)
class ApoptosisEvent:
    triggered: bool
    halt_code: str
    stability_score_bps: int
    regrown_from_snapshot_caid: str
    reason: str


class DigitalApoptosisSentinel:
    """
    Monitors agent context and candidate code health; executes programmed
    self-termination (Apoptosis) and clean regrowth from the frozen spec on drift.
    """

    def __init__(
        self,
        seed_verified_source: str,
        formal_spec: FormalIntentSpec,
        required_constraints: Sequence[str],
        min_stability_bps: int = 6200,
    ) -> None:
        self.seed_verified_source = seed_verified_source
        self.seed_snapshot_caid = sha256_text(seed_verified_source)
        self.active_source = seed_verified_source
        self.active_snapshot_caid = self.seed_snapshot_caid
        self.formal_spec = formal_spec
        self.required_constraints: Set[str] = set(required_constraints)
        self.min_stability_bps = min_stability_bps
        self.mags_gate = FormalMAGSGate()

    def evaluate_and_enforce_homeostasis(
        self,
        candidate_source: str,
        active_memory_constraints: Sequence[str],
    ) -> ApoptosisEvent:
        # 1. Compute Context Constraint Stability Score (0..10000 bps)
        if not self.required_constraints:
            recall_bps = 10000  # claim: config
        else:
            retained = len(self.required_constraints & set(active_memory_constraints))
            recall_bps = (retained * 10000) // len(self.required_constraints)

        # 2. Pre-Execution AST Reality Gate Check ($0 token cost)
        ast_ok, ast_violations = FormalMAGSGate.audit_ast_totality_and_safety(
            candidate_source, self.formal_spec.target_function_name
        )
        if not ast_ok:
            self.active_source = self.seed_verified_source
            self.active_snapshot_caid = self.seed_snapshot_caid
            return ApoptosisEvent(
                triggered=True,
                halt_code="HALT_CONTEXT_DRIFT_APOPTOSIS_TRIGGERED",
                stability_score_bps=0,
                regrown_from_snapshot_caid=self.seed_snapshot_caid,
                reason=f"AST Reality Gate failed: {'; '.join(ast_violations)}",
            )

        # 3. Check Context Drift Threshold (< min_stability_bps -> Apoptosis!)
        if recall_bps < self.min_stability_bps:
            self.active_source = self.seed_verified_source
            self.active_snapshot_caid = self.seed_snapshot_caid
            return ApoptosisEvent(
                triggered=True,
                halt_code="HALT_CONTEXT_DRIFT_APOPTOSIS_TRIGGERED",
                stability_score_bps=recall_bps,
                regrown_from_snapshot_caid=self.seed_snapshot_caid,
                reason=f"Context stability {recall_bps} bps dropped below threshold {self.min_stability_bps} bps.",
            )

        # 4. Run FormalMAGSGate Bounded Model Check against the Epistemic Core
        receipt: MAGSVerificationReceipt = self.mags_gate.prove_candidate(
            candidate_source, self.formal_spec
        )
        if not receipt.proved:
            # Candidate violated formal spec -> Trigger Digital Apoptosis & regrow!
            self.active_source = self.seed_verified_source
            self.active_snapshot_caid = self.seed_snapshot_caid
            return ApoptosisEvent(
                triggered=True,
                halt_code="HALT_CONTEXT_DRIFT_APOPTOSIS_TRIGGERED",
                stability_score_bps=recall_bps,
                regrown_from_snapshot_caid=self.seed_snapshot_caid,
                reason=f"Formal MAGS proof failed ({receipt.halt_code}): {receipt.violation_detail}",
            )

        # Candidate is verified and context is stable -> Update active state
        self.active_source = candidate_source
        self.active_snapshot_caid = receipt.code_ast_digest
        return ApoptosisEvent(
            triggered=False,
            halt_code="OK_HOMEOSTASIS_MAINTAINED",
            stability_score_bps=recall_bps,
            regrown_from_snapshot_caid=self.active_snapshot_caid,
            reason="All AST, Context Stability, and Formal MAGS invariants satisfied.",
        )


# ============================================================================
# D4: Verification Tax & Production-Qualified Change (PQC) Benchmark
# ============================================================================
@dataclass(frozen=True)
class VerificationTaxComparison:
    baseline_escaped_regressions: int
    aeib_escaped_regressions: int
    baseline_manual_review_minutes: float
    aeib_manual_review_minutes: float
    review_time_reduction_bps: int
    pqc_score_improvement_ratio: float
    passed_benchmark_gate: bool


def build_benchmark_spec() -> FormalIntentSpec:
    return FormalIntentSpec(
        spec_id="mags_escrow_benchmark_v1",
        target_function_name="settle_escrow_transfer",
        state_domains={
            "sender_bal": (0, 50, 100, 200),
            "receiver_bal": (0, 50),
            "fee_vault": (0, 10),
            "amount": (10, 50, 100),
            "fee": (0, 5),
            "audit_epoch": (1,),
        },
        allowed_mutated_keys=frozenset({"sender_bal", "receiver_bal", "fee_vault"}),
        precondition_fn=lambda s: (
            s["amount"] > 0
            and s["fee"] >= 0
            and s["sender_bal"] >= (s["amount"] + s["fee"])
            and s["receiver_bal"] >= 0
            and s["fee_vault"] >= 0
        ),
        postcondition_fn=lambda pre, post: (
            post["sender_bal"] == pre["sender_bal"] - pre["amount"] - pre["fee"]
            and post["receiver_bal"] == pre["receiver_bal"] + pre["amount"]
            and post["fee_vault"] == pre["fee_vault"] + pre["fee"]
            and post["sender_bal"] >= 0
        ),
        conserved_quantity_fn=lambda s: (
            s["sender_bal"] + s["receiver_bal"] + s["fee_vault"]
        ),
    )


def run_d4_verification_tax_benchmark(
    base_review_min_per_diff: float = 24.0,
    aeib_review_min_per_card: float = 4.0,
) -> VerificationTaxComparison:
    """
    Evaluates 10 candidate commits (5 sound, 3 subtly buggy that pass unit tests, 2 hollow stubs) under:
    - Ungoverned Baseline: requires manual review for all diffs; misses subtle conservation bugs due to fatigue.
    - AEIB Neurosymbolic Homeostatic Harness: automated FormalMAGSGate + AST Gate catches 100% of bugs/stubs;
      humans only review verified cards.
    """
    sound_code = """
def settle_escrow_transfer(state: dict) -> dict:
    amount = state["amount"]
    fee = state["fee"]
    sender_bal = state["sender_bal"]
    receiver_bal = state["receiver_bal"]
    fee_vault = state["fee_vault"]
    if amount <= 0 or fee < 0 or sender_bal < (amount + fee) or receiver_bal < 0 or fee_vault < 0:
        raise ValueError("ERR_PRECONDITION_VIOLATED")
    out = dict(state)
    out["sender_bal"] = sender_bal - amount - fee
    out["receiver_bal"] = receiver_bal + amount
    out["fee_vault"] = fee_vault + fee
    return out
"""
    subtle_bug_code = sound_code.replace(
        'out["fee_vault"] = fee_vault + fee',
        'out["fee_vault"] = fee_vault + (fee - 1 if amount == 100 else fee)',
    )
    stub_code = """
def settle_escrow_transfer(state: dict) -> dict:
    pass
"""

    spec = build_benchmark_spec()

    sentinel = DigitalApoptosisSentinel(
        seed_verified_source=sound_code,
        formal_spec=spec,
        required_constraints=("C1_CONSERVATION", "C2_NO_OVERDRAFT", "C3_FRAME_IMMUTABLE"),
    )

    workload = [sound_code] * 5 + [subtle_bug_code] * 3 + [stub_code] * 2
    aeib_escaped = 0
    aeib_human_review_mins = 0.0
    # claim: assumption -- the baseline is NOT measured; it assumes a human reviewer misses
    # all 3 planted subtle bugs. The resulting PQC ratio is a property of this constructed
    # 10-diff scenario, not an empirical result.
    baseline_escaped = 3
    baseline_human_review_mins = len(workload) * base_review_min_per_diff

    for cand in workload:
        ev = sentinel.evaluate_and_enforce_homeostasis(
            cand,
            active_memory_constraints=("C1_CONSERVATION", "C2_NO_OVERDRAFT", "C3_FRAME_IMMUTABLE"),
        )
        if not ev.triggered:
            aeib_human_review_mins += aeib_review_min_per_card
            if "fee - 1" in cand or "pass" in cand:
                aeib_escaped += 1

    reduction_bps = int(
        ((baseline_human_review_mins - aeib_human_review_mins) * 10000) / baseline_human_review_mins
    )

    baseline_hours = baseline_human_review_mins / 60.0
    aeib_hours = aeib_human_review_mins / 60.0

    baseline_pqc = 5.0 / (baseline_hours * (1 + baseline_escaped))
    aeib_pqc = 5.0 / (aeib_hours * (1 + aeib_escaped))
    pqc_ratio = round(aeib_pqc / baseline_pqc, 2)

    passed = (aeib_escaped == 0) and (reduction_bps >= 4000)
    if not passed:
        raise RuntimeError("HALT_BENCHMARK_BASELINE_NOT_BEATEN")

    return VerificationTaxComparison(
        baseline_escaped_regressions=baseline_escaped,
        aeib_escaped_regressions=aeib_escaped,
        baseline_manual_review_minutes=baseline_human_review_mins,
        aeib_manual_review_minutes=aeib_human_review_mins,
        review_time_reduction_bps=reduction_bps,
        pqc_score_improvement_ratio=pqc_ratio,
        passed_benchmark_gate=passed,
    )
