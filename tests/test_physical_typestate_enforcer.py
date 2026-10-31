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
tests/test_physical_typestate_enforcer.py
================================================================================
Verification suite for `src/physical_typestate_enforcer.py`.
Tests:
  1. PhysicalEnvelopeSpec validation (empty unit, non-int values, min > max).
  2. TypeStatePhysicsVerdict creation, dictionary conversion, and CAID format.
  3. PhysicalTypeStateEnforcer initialization (empty envelope guard).
  4. Syntax error handling in candidate code.
  5. AnnAssign bounds checking (lower and upper bounds, negative numbers).
  6. Multi-target and single-target Assign bounds checking.
  7. BinOp dimensional checking (Add, Sub, Mismatch, Same unit, non-unit).
  8. Nominal passes and unannotated variables.
"""

from __future__ import annotations

import ast

import pytest

from src.physical_typestate_enforcer import (
    PhysicalEnvelopeSpec,
    PhysicalTypeStateEnforcer,
    TypeStatePhysicsVerdict,
)


@pytest.fixture
def sample_envelopes() -> dict[str, PhysicalEnvelopeSpec]:
    return {
        "MinorUnitUSD": PhysicalEnvelopeSpec(unit_type="MinorUnitUSD", min_value=0, max_value=100000),
        "Kelvin": PhysicalEnvelopeSpec(unit_type="Kelvin", min_value=0, max_value=500),
        "NewtonMeters": PhysicalEnvelopeSpec(unit_type="NewtonMeters", min_value=-50, max_value=50),
    }


def test_1_physical_envelope_spec_validation() -> None:
    # Valid spec
    spec = PhysicalEnvelopeSpec("MinorUnitUSD", 0, 100000)
    assert spec.unit_type == "MinorUnitUSD"
    assert spec.min_value == 0
    assert 99999 < int(spec.max_value) < 100001

    # Empty unit type
    with pytest.raises(ValueError, match="unit_type must not be empty"):
        PhysicalEnvelopeSpec("   ", 0, 100)

    # Non-integer values
    with pytest.raises(ValueError, match="min_value and max_value must be integers"):
        PhysicalEnvelopeSpec("MinorUnitUSD", "0", 100)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="min_value and max_value must be integers"):
        PhysicalEnvelopeSpec("MinorUnitUSD", 0, 100.5)  # type: ignore[arg-type]

    # min_value > max_value
    with pytest.raises(ValueError, match="min_value cannot exceed max_value"):
        PhysicalEnvelopeSpec("MinorUnitUSD", 500, 100)


def test_2_verdict_dataclass_and_to_dict() -> None:
    verdict = TypeStatePhysicsVerdict(
        passed=True,
        status_code="OK_PHYSICAL_TYPESTATE_VERIFIED",
        violating_symbol="ALL",
        line_number=0,
        verdict_caid="sha256:abcd",
    )
    d = verdict.to_dict()
    assert d["passed"] is True
    assert d["status_code"] == "OK_PHYSICAL_TYPESTATE_VERIFIED"
    assert d["violating_symbol"] == "ALL"
    assert int(d["line_number"]) == 0
    assert d["verdict_caid"] == "sha256:abcd"


def test_3_enforcer_init_guards() -> None:
    with pytest.raises(ValueError, match="ERR_EMPTY_PHYSICAL_ENVELOPES"):
        PhysicalTypeStateEnforcer({})


def test_4_syntax_error_candidate(sample_envelopes: dict[str, PhysicalEnvelopeSpec], monkeypatch: pytest.MonkeyPatch) -> None:
    enforcer = PhysicalTypeStateEnforcer(sample_envelopes)
    bad_code = "def broken_code(:\n    return None"
    verdict = enforcer.verify_ast_physics(bad_code, filename="bad.py")
    assert verdict.passed is False
    assert verdict.status_code == "HALT_SYNTAX_ERROR"
    assert verdict.violating_symbol == "bad.py"
    assert int(verdict.line_number) > 0
    assert verdict.verdict_caid.startswith("sha256:")

    # When lineno is None, falls back to 0
    class DummySyntaxError(SyntaxError):
        def __init__(self) -> None:
            self.lineno = None

    def fake_parse(*args: object, **kwargs: object) -> object:
        raise DummySyntaxError()

    monkeypatch.setattr(ast, "parse", fake_parse)
    v_zero = enforcer.verify_ast_physics("dummy_code")
    assert int(v_zero.line_number) == 0


def test_5_ann_assign_bounds(sample_envelopes: dict[str, PhysicalEnvelopeSpec]) -> None:
    enforcer = PhysicalTypeStateEnforcer(sample_envelopes)

    # Nominal within envelope
    code_ok = "spend: MinorUnitUSD = 5000\ntorque: NewtonMeters = -20\n"
    v_ok = enforcer.verify_ast_physics(code_ok)
    assert v_ok.passed is True
    assert v_ok.status_code == "OK_PHYSICAL_TYPESTATE_VERIFIED"

    # Upper bound breach
    code_upper = "spend: MinorUnitUSD = 150000\n"
    v_upper = enforcer.verify_ast_physics(code_upper)
    assert v_upper.passed is False
    assert "BOUNDS_EXCEEDED" in v_upper.status_code
    assert "150000" in v_upper.status_code
    assert v_upper.violating_symbol == "spend"
    assert 0 < int(v_upper.line_number) < 2

    # Lower bound breach (positive min)
    code_lower = "spend: MinorUnitUSD = -10\n"
    v_lower = enforcer.verify_ast_physics(code_lower)
    assert v_lower.passed is False
    assert "BOUNDS_EXCEEDED" in v_lower.status_code
    assert "-10" in v_lower.status_code

    # Lower bound breach (negative min)
    code_neg = "torque: NewtonMeters = -75\n"
    v_neg = enforcer.verify_ast_physics(code_neg)
    assert v_neg.passed is False
    assert "BOUNDS_EXCEEDED" in v_neg.status_code
    assert "-75" in v_neg.status_code

    # AnnAssign without value or non-envelope annotation
    code_non_envelope = "val: OtherUnit = 99999999\nuninit: MinorUnitUSD\n"
    v_non = enforcer.verify_ast_physics(code_non_envelope)
    assert v_non.passed is True

    # AnnAssign with non-int value (e.g., string or float)
    code_non_int = "spend: MinorUnitUSD = 'invalid'\n"
    v_str = enforcer.verify_ast_physics(code_non_int)
    assert v_str.passed is True


def test_6_assign_reassignment_bounds(sample_envelopes: dict[str, PhysicalEnvelopeSpec]) -> None:
    enforcer = PhysicalTypeStateEnforcer(sample_envelopes)

    # Nominal reassignment
    code_ok = "spend: MinorUnitUSD = 100\nspend = 500\n"
    v_ok = enforcer.verify_ast_physics(code_ok)
    assert v_ok.passed is True

    # Reassignment upper breach
    code_re_upper = "spend: MinorUnitUSD = 100\nspend = 200000\n"
    v_re_upper = enforcer.verify_ast_physics(code_re_upper)
    assert v_re_upper.passed is False
    assert "BOUNDS_EXCEEDED" in v_re_upper.status_code
    assert v_re_upper.violating_symbol == "spend"

    # Multi-target reassignment
    code_multi = "spend: MinorUnitUSD = 100\nother = spend = 300000\n"
    v_multi = enforcer.verify_ast_physics(code_multi)
    assert v_multi.passed is False
    assert "BOUNDS_EXCEEDED" in v_multi.status_code

    # Reassignment of unannotated variable
    code_unann = "untracked = 9999999\n"
    v_unann = enforcer.verify_ast_physics(code_unann)
    assert v_unann.passed is True

    # Reassignment to non-literal/non-int value (lit_val is None while target in envelopes)
    code_non_int_reassign = "spend: MinorUnitUSD = 100\nspend = 'untracked_string'\n"
    v_non_int = enforcer.verify_ast_physics(code_non_int_reassign)
    assert v_non_int.passed is True


def test_7_binop_dimensional_consistency(sample_envelopes: dict[str, PhysicalEnvelopeSpec]) -> None:
    enforcer = PhysicalTypeStateEnforcer(sample_envelopes)

    # Mismatch in Add: MinorUnitUSD + Kelvin
    code_add_mismatch = (
        "p: MinorUnitUSD = 100\n"
        "t: Kelvin = 300\n"
        "result = p + t\n"
    )
    v_add = enforcer.verify_ast_physics(code_add_mismatch)
    assert v_add.passed is False
    assert "DIMENSIONAL_MISMATCH" in v_add.status_code
    assert "MinorUnitUSD_vs_Kelvin" in v_add.status_code
    assert v_add.violating_symbol == "MinorUnitUSD+Kelvin"
    assert 2 < int(v_add.line_number) < 4

    # Mismatch in Sub: MinorUnitUSD - Kelvin
    code_sub_mismatch = (
        "p: MinorUnitUSD = 100\n"
        "t: Kelvin = 300\n"
        "result = p - t\n"
    )
    v_sub = enforcer.verify_ast_physics(code_sub_mismatch)
    assert v_sub.passed is False
    assert "DIMENSIONAL_MISMATCH" in v_sub.status_code

    # Homogeneous Add: MinorUnitUSD + MinorUnitUSD
    code_same = (
        "p1: MinorUnitUSD = 100\n"
        "p2: MinorUnitUSD = 200\n"
        "total = p1 + p2\n"
    )
    v_same = enforcer.verify_ast_physics(code_same)
    assert v_same.passed is True

    # BinOp with literal or unannotated (left or right unit is None)
    code_mixed = (
        "p1: MinorUnitUSD = 100\n"
        "offset = p1 + 50\n"
    )
    v_mixed = enforcer.verify_ast_physics(code_mixed)
    assert v_mixed.passed is True

    # Multiplication (not Add/Sub) ignored by dimensional check
    code_mult = (
        "p1: MinorUnitUSD = 100\n"
        "t: Kelvin = 300\n"
        "product = p1 * t\n"
    )
    v_mult = enforcer.verify_ast_physics(code_mult)
    assert v_mult.passed is True
