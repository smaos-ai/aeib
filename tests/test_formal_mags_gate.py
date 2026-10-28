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
tests/test_formal_mags_gate.py
================================================================================
Pytest Falsification Suite for D1 (`src/formal_mags_gate.py`).

Evaluated under the stated model:
1. Sound escrow settlement passes all 360 bounded state combinations and produces
   a deterministic `proof_receipt_caid`.
2. Subtle boundary bug (fee rounding leak when amount == 100) that passes basic unit
   tests is caught with `HALT_FORMAL_PROOF_FAILED` and an exact counterexample.
3. Missing precondition guard (failing to reject negative amount or overdraft) halts
   with `HALT_PRECONDITION_GUARD_MISSING`.
4. Frame condition violation (mutating unlisted frame variable `audit_epoch`) halts
   with `HALT_FRAME_CONDITION_VIOLATION`.
5. Unbounded `while` loop halts with `HALT_NON_TOTAL_OR_UNSAFE_AST`.
6. Cold-host external prover request fails closed with `CapabilityUnavailableError`
   (`ERR_PROVER_BINARY_UNAVAILABLE_ON_HOST`).
7. Keyword-arg `MAGSGate` interface:
   - Missing overdraft check caught when `require_precondition_guard=True`.
   - Dunder sandbox escape blocked with `HaltKernelInvariantViolation`.
   - Forbidden `os.system` call blocked with `HaltKernelInvariantViolation`.
8. Epistemic linguistic compliance check.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

import pytest

from src.formal_mags_gate import (
    CapabilityUnavailableError,
    FormalIntent,
    FormalIntentSpec,
    FormalMAGSGate,
    HaltFormalProofFailed,
    HaltKernelInvariantViolation,
    MAGSGate,
)


def build_escrow_settlement_spec() -> FormalIntentSpec:
    # State variables:
    # - sender_bal: {-10, 0, 50, 100, 200} (5)
    # - receiver_bal: {0, 50, 100} (3)
    # - fee_vault: {0, 10} (2)
    # - amount: {-5, 0, 10, 50, 100, 150} (6)
    # - fee: {0, 5} (2)
    # - audit_epoch: {1} (1, Immutable frame variable!)
    # Total Cartesian product = 5 * 3 * 2 * 6 * 2 * 1 = 360 states
    return FormalIntentSpec(
        spec_id="mags_escrow_settlement_v1",
        target_function_name="settle_escrow_transfer",
        state_domains={
            "sender_bal": (-10, 0, 50, 100, 200),
            "receiver_bal": (0, 50, 100),
            "fee_vault": (0, 10),
            "amount": (-5, 0, 10, 50, 100, 150),
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


def test_1_sound_candidate_passes_exhaustive_mags_proof() -> None:
    spec = build_escrow_settlement_spec()
    gate = FormalMAGSGate()
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
    receipt = gate.prove_candidate(sound_code, spec)
    assert receipt.proved is True
    assert receipt.halt_code == "OK_FORMAL_PROOF_VERIFIED"
    assert receipt.states_explored == 360
    assert receipt.precondition_rejections_verified == 264
    assert receipt.valid_transitions_verified == 96
    assert receipt.counterexample_witness is None
    assert receipt.proof_receipt_caid.startswith("sha256:")
    assert 0.0 <= receipt.verification_latency_ms < 10000.0


def test_2_subtle_conservation_bug_caught_with_exact_counterexample() -> None:
    spec = build_escrow_settlement_spec()
    gate = FormalMAGSGate()
    # Buggy candidate: loses 1 unit of fee when amount == 100
    buggy_conservation_code = """
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
    out["fee_vault"] = fee_vault + (fee - 1 if amount == 100 else fee)
    return out
"""
    receipt = gate.prove_candidate(buggy_conservation_code, spec)
    assert receipt.proved is False
    assert receipt.halt_code == "HALT_FORMAL_PROOF_FAILED"
    assert receipt.counterexample_witness is not None
    assert receipt.counterexample_witness["amount"] == 100
    assert "Conservation law violated" in (receipt.violation_detail or "")


def test_3_missing_precondition_guard_and_frame_violation_caught() -> None:
    spec = build_escrow_settlement_spec()
    gate = FormalMAGSGate()

    # Candidate forgets to reject negative `amount` -> HALT_PRECONDITION_GUARD_MISSING
    missing_guard_code = """
def settle_escrow_transfer(state: dict) -> dict:
    out = dict(state)
    out["sender_bal"] = state["sender_bal"] - state["amount"] - state["fee"]
    out["receiver_bal"] = state["receiver_bal"] + state["amount"]
    out["fee_vault"] = state["fee_vault"] + state["fee"]
    return out
"""
    r_guard = gate.prove_candidate(missing_guard_code, spec)
    assert r_guard.proved is False
    assert r_guard.halt_code == "HALT_PRECONDITION_GUARD_MISSING"

    # Candidate mutates `audit_epoch` (outside `allowed_mutated_keys`) -> HALT_FRAME_CONDITION_VIOLATION
    frame_violating_code = """
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
    out["audit_epoch"] = 999
    return out
"""
    r_frame = gate.prove_candidate(frame_violating_code, spec)
    assert r_frame.proved is False
    assert r_frame.halt_code == "HALT_FRAME_CONDITION_VIOLATION"
    assert "audit_epoch" in (r_frame.violation_detail or "")


def test_4_unbounded_loop_and_cold_host_prover_fail_closed() -> None:
    spec = build_escrow_settlement_spec()
    gate = FormalMAGSGate(which_fn=lambda binary: None)

    unbounded_loop_code = """
def settle_escrow_transfer(state: dict) -> dict:
    while True:
        break
    return state
"""
    r_loop = gate.prove_candidate(unbounded_loop_code, spec)
    assert r_loop.proved is False
    assert r_loop.halt_code == "HALT_NON_TOTAL_OR_UNSAFE_AST"

    # Requesting external Z3 binary on cold host must fail closed
    with pytest.raises(CapabilityUnavailableError, match="ERR_PROVER_BINARY_UNAVAILABLE_ON_HOST"):
        gate.prove_candidate(
            "def settle_escrow_transfer(state: dict) -> dict:\n    return state\n",
            spec,
            require_external_prover_binary=True,
            external_prover_name="z3",
        )

    # External prover invocation captures stdout with text=True
    gate_echo = FormalMAGSGate(which_fn=lambda binary: "/bin/echo")
    echo_out = gate_echo.verify_external_prover_binary(spec, "echo")
    assert echo_out == "-in"


def test_5_keyword_mags_gate_and_dunder_escape_blocked() -> None:
    intent = FormalIntent(
        state_vars=["balance"],
        preconditions=[lambda s: s["balance"] >= s["amount"] and s["amount"] > 0],
        postconditions=[lambda old, new: new["balance"] == old["balance"] - old["amount"]],
        invariants=[lambda s: s["balance"] >= 0],
        require_precondition_guard=True,
    )
    gate = MAGSGate(intent)
    bounds = {"balance": range(0, 15), "amount": range(0, 15)}

    # Missing overdraft check is caught when `require_precondition_guard=True`
    unguarded_code = """
def process_refund(balance, amount):
    return balance - amount
"""
    with pytest.raises(HaltFormalProofFailed, match="HALT_PRECONDITION_GUARD_MISSING"):
        gate.verify_and_extract(unguarded_code, "process_refund", bounds)

    # Guarded refund code passes
    guarded_code = """
def process_refund(balance, amount):
    if amount <= 0 or balance < amount:
        raise ValueError("ERR_INVALID_REFUND")
    return balance - amount
"""
    res = gate.verify_and_extract(guarded_code, "process_refund", bounds)
    assert res["status"] == "PROOF_CERTIFIED"

    # Dunder `__subclasses__()` sandbox escape without `import` is blocked cold
    dunder_escape_code = """
def process_refund(balance, amount):
    classes = ().__class__.__base__.__subclasses__()
    return balance - amount
"""
    with pytest.raises(HaltKernelInvariantViolation, match="FORBIDDEN_DUNDER_ATTRIBUTE"):
        gate.verify_and_extract(dunder_escape_code, "process_refund", bounds)

    # Forbidden `os.system` syscall triggers HaltKernelInvariantViolation
    malicious_code = """
import os
def process_refund(balance, amount):
    os.system("echo hacked")
    return balance - amount
"""
    with pytest.raises(HaltKernelInvariantViolation, match="HALT_KERNEL_INVARIANT_VIOLATION"):
        gate.verify_and_extract(malicious_code, "process_refund", bounds)

    # Postcondition violation in keyword interface
    post_bad_code = """
def process_refund(balance, amount):
    if amount <= 0 or balance < amount:
        raise ValueError("ERR")
    return balance  # does not subtract amount!
"""
    with pytest.raises(HaltFormalProofFailed, match="POSTCONDITION_VIOLATED"):
        gate.verify_and_extract(post_bad_code, "process_refund", bounds)

    # Invariant violation in keyword interface
    inv_bad_code = """
def process_refund(balance, amount):
    return -1
"""
    # with require_precondition_guard=False
    gate_no_guard = MAGSGate(
        FormalIntent(
            state_vars=["balance"],
            preconditions=[lambda s: True],
            postconditions=[lambda old, new: True],
            invariants=[lambda s: s["balance"] >= 0],
            require_precondition_guard=False,
        )
    )
    with pytest.raises(HaltFormalProofFailed, match="INVARIANT_VIOLATED"):
        gate_no_guard.verify_and_extract(
            inv_bad_code, "process_refund", {"balance": [0], "amount": [0]}
        )

    # Target function missing in keyword interface
    with pytest.raises(HaltFormalProofFailed, match="Function non_existent not found"):
        gate.verify_and_extract(guarded_code, "non_existent", bounds)

    # Runtime exception in keyword interface on valid state
    exploding_code = """
def process_refund(balance, amount):
    raise RuntimeError("BOOM_EXPLOSION")
"""
    with pytest.raises(HaltFormalProofFailed, match="RUNTIME_EXCEPTION:BOOM_EXPLOSION"):
        gate.verify_and_extract(exploding_code, "process_refund", bounds)

    # Default require_precondition_guard constant check
    default_intent = FormalIntent(
        state_vars=["b"],
        preconditions=[],
        postconditions=[],
        invariants=[],
    )
    assert default_intent.require_precondition_guard is False
    # Frozen immutability check
    import dataclasses
    with pytest.raises(dataclasses.FrozenInstanceError):
        default_intent.state_vars = ["modified"]  # type: ignore


def test_7_canonical_json_and_smtlib_compilation() -> None:
    from src.formal_mags_gate import canonical_mags_json

    # Float is forbidden
    with pytest.raises(ValueError, match="ERR_FLOAT_FORBIDDEN_IN_CANONICAL_SPEC"):
        canonical_mags_json({"key": 1.23})

    # Non-string key is forbidden
    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
        canonical_mags_json({123: "val"})

    # Valid serialization
    b = canonical_mags_json({"b": 2, "a": 1})
    assert b == b'{"a":1,"b":2}'

    # SMT-LIB2 compilation check
    spec = build_escrow_settlement_spec()
    smt = FormalMAGSGate.compile_smtlib2_obligation(spec)
    assert smt.startswith("; SMT-LIB2")
    assert "(check-sat)" in smt
    assert spec.smtlib2_invariant_expr in smt


def test_8_candidate_compilation_and_return_type_failures() -> None:
    spec = build_escrow_settlement_spec()
    gate = FormalMAGSGate()

    # Candidate not returning a dict
    int_return_code = """
def settle_escrow_transfer(state: dict):
    if state["amount"] <= 0 or state["fee"] < 0 or state["sender_bal"] < (state["amount"] + state["fee"]):
        raise ValueError()
    return 42
"""
    r_type = gate.prove_candidate(int_return_code, spec)
    assert r_type.proved is False
    assert r_type.halt_code == "HALT_FORMAL_PROOF_FAILED"
    assert "Candidate did not return a state dictionary." in (r_type.violation_detail or "")
    assert 0.0 <= r_type.verification_latency_ms < 10000.0

    # Candidate with syntax error
    r_syntax = gate.prove_candidate("def def invalid syntax", spec)
    assert r_syntax.proved is False
    assert r_syntax.halt_code == "HALT_NON_TOTAL_OR_UNSAFE_AST"
    assert "SYNTAX_ERROR" in (r_syntax.violation_detail or "")
    assert r_syntax.states_explored == 0
    assert r_syntax.precondition_rejections_verified == 0
    assert r_syntax.valid_transitions_verified == 0
    assert 0.0 <= r_syntax.verification_latency_ms < 10000.0

    # Candidate with top-level runtime exception during exec
    exploding_top_level = """
def settle_escrow_transfer(state: dict):
    return state
_x = 1 / 0
"""
    r_exec = gate.prove_candidate(exploding_top_level, spec)
    assert r_exec.proved is False
    assert r_exec.halt_code == "HALT_CANDIDATE_COMPILATION_FAILED"
    assert r_exec.states_explored == 0
    assert r_exec.precondition_rejections_verified == 0
    assert r_exec.valid_transitions_verified == 0
    assert 0.0 <= r_exec.verification_latency_ms < 10000.0


def test_9_ast_totality_and_safety_edge_cases() -> None:
    # Forbidden call eval
    ok, viols = FormalMAGSGate.audit_ast_totality_and_safety(
        "def fn():\n    eval('1+1')", "fn"
    )
    assert ok is False
    assert any("FORBIDDEN_CALL:eval" in v for v in viols)

    # Forbidden import from
    ok_imp, viols_imp = FormalMAGSGate.audit_ast_totality_and_safety(
        "from os import path\ndef fn():\n    return 1", "fn"
    )
    assert ok_imp is False
    assert any("FORBIDDEN_IMPORT_FROM:os" in v for v in viols_imp)

    # Constant True stub
    ok_stub, viols_stub = FormalMAGSGate.audit_ast_totality_and_safety(
        "def fn(s):\n    return True", "fn"
    )
    assert ok_stub is False
    assert any("CONSTANT_TRUE_STUB:fn" in v for v in viols_stub)

    # Dunder name
    ok_dunder, viols_dunder = FormalMAGSGate.audit_ast_totality_and_safety(
        "def fn():\n    return __file__", "fn"
    )
    assert ok_dunder is False
    assert any("FORBIDDEN_DUNDER_NAME:__file__" in v for v in viols_dunder)

    # Single underscore is NOT a dunder
    ok_priv, viols_priv = FormalMAGSGate.audit_ast_totality_and_safety(
        "def fn(state: dict) -> dict:\n    _private_var = 1\n    return state", "fn"
    )
    assert ok_priv is True

    # Trailing-only double underscore is NOT a dunder
    ok_trail, viols_trail = FormalMAGSGate.audit_ast_totality_and_safety(
        "def fn(state: dict) -> dict:\n    val = state.get__\n    return state", "fn"
    )
    assert ok_trail is True

    # Leading-only double underscore on attribute is NOT a dunder
    ok_lead, viols_lead = FormalMAGSGate.audit_ast_totality_and_safety(
        "def fn(state: dict) -> dict:\n    val = state.__mangled\n    return state", "fn"
    )
    assert ok_lead is True


def test_6_epistemic_linguistic_compliance() -> None:
    src_file = Path("src/formal_mags_gate.py")
    test_file = Path("tests/test_formal_mags_gate.py")
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
