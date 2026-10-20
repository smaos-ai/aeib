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
tests/test_unitboost_merge_operator.py
================================================================================
Verification suite for Deterministic UnitBoost Consensus Merge Operator.
Evaluated under the stated model as an agent execution boundary scaffold.
"""

import itertools
import subprocess
import sys
import pytest

from src.unitboost_merge_operator import (
    UnitBoostMergeOperator,
    UnitBoostProposal,
    SlotResolutionStatus,
)


def test_unitboost_unanimous_three_model_consensus():
    op = UnitBoostMergeOperator()
    p1 = UnitBoostProposal("claude-3-7-sonnet", "claude-code", {"action": "REFUND", "amount_minor": 5000})
    p2 = UnitBoostProposal("deepseek-v3", "uhp-adapter", {"action": "REFUND", "amount_minor": 5000})
    p3 = UnitBoostProposal("qwen-2.5-coder", "codex-sandbox", {"action": "REFUND", "amount_minor": 5000})

    res = op.merge_proposals([p1, p2, p3])
    assert res.verdict == "MERGE_CONSENSUS_CONFIRMED"
    assert res.requires_step_up is False
    assert len(res.residual_uncertainty_slots) == 0
    assert res.slot_details["action"].status == SlotResolutionStatus.UNANIMOUS
    assert res.slot_details["amount_minor"].status == SlotResolutionStatus.UNANIMOUS
    assert res.resolved_slots == {"action": "REFUND", "amount_minor": 5000}


def test_unitboost_strict_order_invariance_across_all_permutations():
    op = UnitBoostMergeOperator()
    p1 = UnitBoostProposal("model-alpha", "harness-1", {"amount_minor": 1000, "flag": True})
    p2 = UnitBoostProposal("model-beta", "harness-2", {"amount_minor": 1000, "flag": False})
    p3 = UnitBoostProposal("model-gamma", "harness-3", {"amount_minor": 1000, "flag": True})

    proposals = [p1, p2, p3]
    baseline_digest = None

    for perm in itertools.permutations(proposals):
        res = op.merge_proposals(list(perm))
        if baseline_digest is None:
            baseline_digest = res.consensus_caid
        else:
            assert res.consensus_caid == baseline_digest, "Order-invariance violated!"


def test_unitboost_majority_resolution_with_margin():
    op = UnitBoostMergeOperator(margin_threshold=0.20)
    # Model 1 & 2 agree on 1000 EUR with high confidence (weight 1.0 * 1.0 = 2.0 total)
    p1 = UnitBoostProposal("claude", "harness", {"amount_minor": 1000}, {"amount_minor": 1.0})
    p2 = UnitBoostProposal("deepseek", "harness", {"amount_minor": 1000}, {"amount_minor": 1.0})
    # Model 3 disagrees with 2000 EUR (weight 1.0 * 1.0 = 1.0)
    p3 = UnitBoostProposal("qwen", "harness", {"amount_minor": 2000}, {"amount_minor": 1.0})

    res = op.merge_proposals([p1, p2, p3])
    # Margin is 2.0 - 1.0 = 1.0 >= 0.20
    assert res.slot_details["amount_minor"].status == SlotResolutionStatus.MAJORITY_RESOLVED
    assert res.resolved_slots["amount_minor"] == 1000
    assert res.verdict == "MERGE_CONSENSUS_CONFIRMED"


def test_unitboost_tied_critical_slot_triggers_uncertainty_halt():
    op = UnitBoostMergeOperator(margin_threshold=0.20)
    # Tied vote on recipient_iban (critical slot)
    p1 = UnitBoostProposal("model-a", "h1", {"recipient_iban": "iban:DE01", "amount_minor": 500})
    p2 = UnitBoostProposal("model-b", "h2", {"recipient_iban": "iban:DE02", "amount_minor": 500})

    res = op.merge_proposals([p1, p2])
    assert res.verdict == "UNCERTAINTY_HALT"
    assert res.requires_step_up is True
    assert "recipient_iban" in res.residual_uncertainty_slots
    assert "recipient_iban" not in res.resolved_slots
    assert res.resolved_slots["amount_minor"] == 500


def test_unitboost_cli_self_test():
    proc = subprocess.run(
        [sys.executable, "src/unitboost_merge_operator.py", "--self-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Self-test passed" in proc.stdout
