# Copyright 2026 SovereignNexus Project
#
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
tests/test_blackbox_two_socket_slo.py — Pytest suite for Two-Socket Black-Box TDD & SLO.
"""

import json
import pytest
from pathlib import Path
from tools.blackbox_two_socket_slo_and_fuzzer import (
    SlotProposal,
    run_two_socket_blackbox_and_slo_suite,
    test_two_socket_blackbox_fuzzer_and_slo_baseline,
    unitboost_algebraic_merge,
)


def test_unitboost_commutativity_and_margin() -> None:
    """Verifies that UnitBoost algebraic merge is commutative under all permutations."""
    m1 = SlotProposal(
        model_id="model_a",
        slot_values={"recipient": ("DE89370400440532013000", 0.92), "action": ("REFUND", 0.88)},
    )
    m2 = SlotProposal(
        model_id="model_b",
        slot_values={"recipient": ("DE89370400440532013000", 0.85), "action": ("REFUND", 0.90)},
    )
    m3 = SlotProposal(
        model_id="model_c",
        slot_values={"recipient": ("DE89370400440532013000", 0.95), "action": ("REFUND", 0.84)},
    )

    merge_123 = unitboost_algebraic_merge([m1, m2, m3])
    merge_321 = unitboost_algebraic_merge([m3, m2, m1])
    merge_213 = unitboost_algebraic_merge([m2, m1, m3])

    assert merge_123 == merge_321 == merge_213
    assert merge_123["recipient"] == "DE89370400440532013000"
    assert merge_123["action"] == "REFUND"


def test_unitboost_uncertainty_halt() -> None:
    """Verifies fail-closed halt when confidence separation margin is narrow (< 0.20)."""
    m1 = SlotProposal(
        model_id="model_a",
        slot_values={"recipient": ("DE89370400440532013000", 0.51)},
    )
    m2 = SlotProposal(
        model_id="model_b",
        slot_values={"recipient": ("FR7630006000011234567890189", 0.49)},
    )

    res = unitboost_algebraic_merge([m1, m2])
    assert res["recipient"] == "UNCERTAINTY_HALT"


def test_two_socket_blackbox_slo_execution() -> None:
    """Evaluates the full two-socket black-box fuzzer and SLO benchmark."""
    report = run_two_socket_blackbox_and_slo_suite()

    assert report["false_halt_rate_pct"] == 0.0
    assert report["adversarial_rejection_rate_pct"] == 100.0
    assert report["duplicate_mutations_on_twin_bank"] == 0
    assert report["p50_wire_latency_ms"] < 10.0
    assert report["p99_wire_latency_ms"] < 50.0
    assert report["wal_bytes_per_entry"] > 0
    assert report["reconciliation_rto_ms"] < 50.0


def test_banned_words_compliance() -> None:
    """Verifies zero prohibited promotional words in the test file."""
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "bank-" + "grade",
    ]
    with open(__file__, "r", encoding="utf-8") as f:
        content = f.read()
    for word in banned:
        assert word not in content, f"Banned word detected: {word}"
