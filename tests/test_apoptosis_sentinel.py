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
tests/test_apoptosis_sentinel.py
================================================================================
Pytest Falsification Suite for D3 & D4 (`src/apoptosis_sentinel.py`).

Evaluated under the stated model:
Proves that the Digital Apoptosis Sentinel detects context drift, AST violations,
and formal specification breaches, triggering programmed self-termination and
regrowth from seed snapshot, while verifying the Verification Tax & PQC Benchmark.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.apoptosis_sentinel import (
    DigitalApoptosisSentinel,
    run_d4_verification_tax_benchmark,
)
from src.formal_mags_gate import FormalIntentSpec


def build_test_spec() -> FormalIntentSpec:
    return FormalIntentSpec(
        spec_id="test_sentinel_spec",
        target_function_name="mutate_val",
        state_domains={"val": (1, 2, 5)},
        allowed_mutated_keys=frozenset({"val"}),
        precondition_fn=lambda s: s["val"] > 0,
        postcondition_fn=lambda pre, post: post["val"] == pre["val"] + 1,
    )


def test_1_nominal_homeostasis_maintained() -> None:
    spec = build_test_spec()
    sound_code = """
def mutate_val(state: dict) -> dict:
    if state["val"] <= 0:
        raise ValueError()
    out = dict(state)
    out["val"] = state["val"] + 1
    return out
"""
    sentinel = DigitalApoptosisSentinel(
        seed_verified_source=sound_code,
        formal_spec=spec,
        required_constraints=("C1", "C2"),
        min_stability_bps=6200,
    )
    ev = sentinel.evaluate_and_enforce_homeostasis(sound_code, ("C1", "C2"))
    assert ev.triggered is False
    assert ev.halt_code == "OK_HOMEOSTASIS_MAINTAINED"
    assert ev.stability_score_bps == 10000


def test_2_context_drift_triggers_apoptosis_and_regrowth() -> None:
    spec = build_test_spec()
    sound_code = """
def mutate_val(state: dict) -> dict:
    if state["val"] <= 0:
        raise ValueError()
    out = dict(state)
    out["val"] = state["val"] + 1
    return out
"""
    sentinel = DigitalApoptosisSentinel(
        seed_verified_source=sound_code,
        formal_spec=spec,
        required_constraints=("C1", "C2", "C3"),
        min_stability_bps=6200,
    )
    # Only 1 of 3 constraints remembered = 3333 bps < 6200 bps
    ev = sentinel.evaluate_and_enforce_homeostasis(sound_code, ("C1",))
    assert ev.triggered is True
    assert ev.halt_code == "HALT_CONTEXT_DRIFT_APOPTOSIS_TRIGGERED"
    assert ev.stability_score_bps == 3333
    assert ev.regrown_from_snapshot_caid == sentinel.seed_snapshot_caid


def test_3_candidate_ast_or_formal_violation_triggers_apoptosis() -> None:
    spec = build_test_spec()
    sound_code = """
def mutate_val(state: dict) -> dict:
    if state["val"] <= 0:
        raise ValueError()
    out = dict(state)
    out["val"] = state["val"] + 1
    return out
"""
    sentinel = DigitalApoptosisSentinel(
        seed_verified_source=sound_code,
        formal_spec=spec,
        required_constraints=("C1",),
        min_stability_bps=6200,
    )

    # AST violation (pass stub)
    stub_code = """
def mutate_val(state: dict) -> dict:
    pass
"""
    ev_ast = sentinel.evaluate_and_enforce_homeostasis(stub_code, ("C1",))
    assert ev_ast.triggered is True
    assert ev_ast.halt_code == "HALT_CONTEXT_DRIFT_APOPTOSIS_TRIGGERED"
    assert "AST Reality Gate failed" in ev_ast.reason

    # Formal spec violation (returns val + 2 instead of val + 1)
    wrong_code = """
def mutate_val(state: dict) -> dict:
    if state["val"] <= 0:
        raise ValueError()
    out = dict(state)
    out["val"] = state["val"] + 2
    return out
"""
    ev_spec = sentinel.evaluate_and_enforce_homeostasis(wrong_code, ("C1",))
    assert ev_spec.triggered is True
    assert ev_spec.halt_code == "HALT_CONTEXT_DRIFT_APOPTOSIS_TRIGGERED"
    assert "Formal MAGS proof failed" in ev_spec.reason


def test_4_verification_tax_benchmark_execution() -> None:
    from src.apoptosis_sentinel import sha256_text

    # sha256_text helper check
    h = sha256_text("hello world")
    assert h.startswith("sha256:")
    assert len(h) == 71

    # Default min_stability_bps and empty constraints check
    spec = build_test_spec()
    sentinel_default = DigitalApoptosisSentinel(
        seed_verified_source="def mutate_val(s): return s",
        formal_spec=spec,
        required_constraints=(),
    )
    assert sentinel_default.min_stability_bps == 62 * 100
    ev_empty = sentinel_default.evaluate_and_enforce_homeostasis(
        "def mutate_val(s): return s", ()
    )
    assert ev_empty.stability_score_bps == 10000

    # Run Benchmark and assert exact metrics
    bench = run_d4_verification_tax_benchmark()
    assert bench.passed_benchmark_gate is True
    assert bench.baseline_escaped_regressions == 3
    assert bench.aeib_escaped_regressions == 0
    assert bench.baseline_manual_review_minutes == 240.0
    assert bench.aeib_manual_review_minutes == 20.0
    assert bench.review_time_reduction_bps == 9166
    assert bench.pqc_score_improvement_ratio == 48.0

    # Fractional review time tests round precision to 2 decimals
    bench_frac = run_d4_verification_tax_benchmark(aeib_review_min_per_card=3.5)
    assert bench_frac.pqc_score_improvement_ratio == 54.86
    assert bench_frac.review_time_reduction_bps == 9270

    from src.apoptosis_sentinel import build_benchmark_spec, ApoptosisEvent
    import dataclasses
    ev_test = ApoptosisEvent(triggered=False, halt_code="", stability_score_bps=10000, regrown_from_snapshot_caid="", reason="")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev_test.triggered = True  # type: ignore

    with pytest.raises(dataclasses.FrozenInstanceError):
        bench.baseline_escaped_regressions = 99  # type: ignore

    b_spec = build_benchmark_spec()
    assert b_spec.state_domains["sender_bal"] == (0, 50, 100, 200)
    assert b_spec.state_domains["receiver_bal"] == (0, 50)
    assert b_spec.state_domains["amount"] == (10, 50, 100)
    assert b_spec.state_domains["fee_vault"] == (0, 10)
    assert b_spec.state_domains["fee"] == (0, 5)
    assert b_spec.state_domains["audit_epoch"] == (1,)
    assert b_spec.precondition_fn({"amount": 0, "fee": 0, "sender_bal": 100, "receiver_bal": 0, "fee_vault": 0}) is False
    assert b_spec.precondition_fn({"amount": 1, "fee": 0, "sender_bal": 100, "receiver_bal": 0, "fee_vault": 0}) is True

    pre_state = {"sender_bal": 100, "receiver_bal": 0, "fee_vault": 0, "amount": 10, "fee": 0}
    post_bad_bal = {"sender_bal": 999, "receiver_bal": 10, "fee_vault": 0}
    post_ok = {"sender_bal": 90, "receiver_bal": 10, "fee_vault": 0}
    assert b_spec.postcondition_fn(pre_state, post_bad_bal) is False
    assert b_spec.postcondition_fn(pre_state, post_ok) is True


def test_5_epistemic_linguistic_compliance() -> None:
    src_file = Path("src/apoptosis_sentinel.py")
    test_file = Path("tests/test_apoptosis_sentinel.py")
    banned_patterns = [
        r"\bguaran(?:tee|teed|tees|teeing)\b",
        r"\bproven\s+universally\b",
        r"\bbullet[p]roof\b",
        r"\benterprise-[g]rade\b",
        r"\bproduction-[s]afe\b",
        r"\b100%\s+secure\b",
        r"\bunassailable\b",
        r"\bimmune\b",
        r"\bunhackable\b",
        r"\bbank-grade\b",
        r"\bproduction-ready\b",
    ]

    for fpath in (src_file, test_file):
        text = fpath.read_text(encoding="utf-8")
        for pat in banned_patterns:
            matches = re.findall(pat, text, re.IGNORECASE)
            assert len(matches) == 0, f"Banned pattern '{pat}' found in {fpath}: {matches}"
