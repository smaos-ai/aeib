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
src/unitboost_merge_operator.py
================================================================================
Deterministic UnitBoost Consensus Merge Operator.
Evaluated under the stated model as an agent execution boundary scaffold.

Replaces stochastic LLM supervisor managers with deterministic, order-invariant
constrained argmax consensus merging over slot-value proposals (s, v).
Flagged slots without conclusive separation are preserved as RESIDUAL_UNCERTAINTY.
"""

from __future__ import annotations

import argparse
import enum
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    """Computes prefixed SHA-256 digest."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class SlotResolutionStatus(enum.Enum):
    UNANIMOUS = "UNANIMOUS"
    MAJORITY_RESOLVED = "MAJORITY_RESOLVED"
    RESIDUAL_UNCERTAINTY = "RESIDUAL_UNCERTAINTY"


@dataclass
class UnitBoostProposal:
    model_id: str
    harness_id: str
    slot_values: Dict[str, Any]
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    model_weight: float = 1.0


@dataclass
class MergedSlotResult:
    slot_name: str
    resolved_value: Any
    status: SlotResolutionStatus
    candidate_scores: Dict[str, float]
    margin: float
    canonical_repr: str


@dataclass
class UnitBoostMergeResult:
    verdict: str  # "MERGE_CONSENSUS_CONFIRMED" | "UNCERTAINTY_HALT"
    requires_step_up: bool
    consensus_caid: str
    resolved_slots: Dict[str, Any]
    slot_details: Dict[str, MergedSlotResult]
    residual_uncertainty_slots: List[str]
    participating_models: List[str]

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "consensus_caid": self.consensus_caid,
            "participating_models": self.participating_models,
            "residual_uncertainty_slots": self.residual_uncertainty_slots,
            "resolved_slots": self.resolved_slots,
            "status": self.verdict,
        }


class UnitBoostMergeOperator:
    """
    Deterministic consensus merge operator for heterogeneous model handoffs.
    Guarantees mathematical order-invariance across proposal evaluation.
    """

    DEFAULT_CRITICAL_SLOTS = {
        "action_class",
        "amount_minor",
        "recipient_iban",
        "endpoint",
        "currency",
    }

    def __init__(
        self,
        margin_threshold: float = 0.20,
        critical_slots: Optional[Set[str]] = None,
    ) -> None:
        self.margin_threshold = margin_threshold
        self.critical_slots = critical_slots or set(self.DEFAULT_CRITICAL_SLOTS)

    def merge_proposals(
        self, proposals: List[UnitBoostProposal]
    ) -> UnitBoostMergeResult:
        if not proposals:
            raise ValueError("Cannot merge empty proposal list")

        # 1. Sort proposals by (model_id, harness_id) to enforce order-invariance
        sorted_proposals = sorted(
            proposals, key=lambda p: (p.model_id, p.harness_id)
        )
        participating_models = [p.model_id for p in sorted_proposals]

        # 2. Collect all proposed slots
        all_slots: Set[str] = set()
        for p in sorted_proposals:
            all_slots.update(p.slot_values.keys())

        resolved_slots: Dict[str, Any] = {}
        slot_details: Dict[str, MergedSlotResult] = {}
        residual_uncertainty_slots: List[str] = []

        # 3. Evaluate each slot deterministically
        for slot in sorted(all_slots):
            candidate_weights: Dict[str, float] = {}
            candidate_raw_values: Dict[str, Any] = {}

            for p in sorted_proposals:
                if slot not in p.slot_values:
                    continue
                raw_val = p.slot_values[slot]
                # Canonicalize candidate value via JCS bytes for consistent string hashing
                try:
                    c_key = encode_jcs(raw_val).decode("utf-8")
                except Exception:
                    c_key = json.dumps(raw_val, sort_keys=True)

                candidate_raw_values[c_key] = raw_val
                conf = p.confidence_scores.get(slot, 1.0)
                # Bound confidence to [0.0, 1.0]
                conf = max(0.0, min(1.0, float(conf)))
                score = p.model_weight * conf
                candidate_weights[c_key] = candidate_weights.get(c_key, 0.0) + score

            if not candidate_weights:
                continue

            sorted_candidates = sorted(
                candidate_weights.items(), key=lambda kv: (-kv[1], kv[0])
            )

            top_key, top_score = sorted_candidates[0]

            if len(sorted_candidates) == 1:
                status = SlotResolutionStatus.UNANIMOUS
                margin = top_score
                resolved_val = candidate_raw_values[top_key]
            else:
                second_score = sorted_candidates[1][1]
                margin = top_score - second_score
                if margin >= self.margin_threshold:
                    status = SlotResolutionStatus.MAJORITY_RESOLVED
                    resolved_val = candidate_raw_values[top_key]
                else:
                    status = SlotResolutionStatus.RESIDUAL_UNCERTAINTY
                    resolved_val = None
                    residual_uncertainty_slots.append(slot)

            if resolved_val is not None:
                resolved_slots[slot] = resolved_val

            slot_details[slot] = MergedSlotResult(
                slot_name=slot,
                resolved_value=resolved_val,
                status=status,
                candidate_scores=candidate_weights,
                margin=round(margin, 4),
                canonical_repr=top_key,
            )

        # 4. Check if any critical slot remains in RESIDUAL_UNCERTAINTY
        critical_uncertainty = any(
            s in self.critical_slots for s in residual_uncertainty_slots
        )

        verdict = (
            "UNCERTAINTY_HALT"
            if critical_uncertainty
            else "MERGE_CONSENSUS_CONFIRMED"
        )
        requires_step_up = critical_uncertainty

        # 5. Compute consensus CAID over JCS canonical representation
        payload_for_digest = {
            "participating_models": participating_models,
            "residual_uncertainty_slots": sorted(residual_uncertainty_slots),
            "resolved_slots": resolved_slots,
            "status": verdict,
        }
        consensus_caid = sha256_prefixed(encode_jcs(payload_for_digest))

        return UnitBoostMergeResult(
            verdict=verdict,
            requires_step_up=requires_step_up,
            consensus_caid=consensus_caid,
            resolved_slots=resolved_slots,
            slot_details=slot_details,
            residual_uncertainty_slots=sorted(residual_uncertainty_slots),
            participating_models=participating_models,
        )


def run_self_test() -> None:
    """Executes UnitBoost merge operator self-test."""
    op = UnitBoostMergeOperator(margin_threshold=0.20)

    # Test 1: Unanimous consensus
    p1 = UnitBoostProposal(
        model_id="claude-3-7-sonnet",
        harness_id="claude-code",
        slot_values={"action_class": "REFUND", "amount_minor": 100_00},
    )
    p2 = UnitBoostProposal(
        model_id="deepseek-v3",
        harness_id="codex-sandbox",
        slot_values={"action_class": "REFUND", "amount_minor": 100_00},
    )
    res_unanimous = op.merge_proposals([p1, p2])
    assert res_unanimous.verdict == "MERGE_CONSENSUS_CONFIRMED"
    assert res_unanimous.slot_details["action_class"].status == SlotResolutionStatus.UNANIMOUS

    # Test 2: Order-invariance (p1, p2) == (p2, p1)
    res_reversed = op.merge_proposals([p2, p1])
    assert res_unanimous.consensus_caid == res_reversed.consensus_caid

    # Test 3: Critical uncertainty halt on tied vote
    p3_conflict = UnitBoostProposal(
        model_id="deepseek-v3",
        harness_id="codex-sandbox",
        slot_values={"action_class": "TRANSFER", "amount_minor": 100_00},
    )
    res_conflict = op.merge_proposals([p1, p3_conflict])
    assert res_conflict.verdict == "UNCERTAINTY_HALT"
    assert res_conflict.requires_step_up is True
    assert "action_class" in res_conflict.residual_uncertainty_slots

    print("[✓] UnitBoostMergeOperator: Self-test passed (Unanimous, Order-Invariance, and Uncertainty Halt verified).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic UnitBoost Consensus Merge Operator")
    parser.add_argument("--self-test", action="store_true", help="Execute self-test")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        sys.exit(0)
    else:
        parser.print_help()
