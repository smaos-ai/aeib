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
tests/test_epistemic_intent_compiler.py
================================================================================
Pytest Falsification Suite for D5: Epistemic Intent Compiler.

Evaluated under the stated model:
Proves that the compiler safely translates structured LLM intent into FormalIntentSpec
objects, blocking sandbox escapes, undefined variables, zero-division, and
catching implementation bugs via the MAGS Gate.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from src.epistemic_intent_compiler import (
    DEFAULT_DOMAIN_ADEQUACY_POLICY,
    DomainAdequacyPolicy,
    DomainAdequacyViolation,
    EpistemicIntentCompiler,
    HaltEpistemicCompilationFailed,
    IntentDraft,
    SafeExpressionCompiler,
)
from src.formal_mags_gate import FormalMAGSGate


def test_1_valid_escrow_intent_compiles_and_proves_sound_code() -> None:
    draft = IntentDraft(
        spec_id="epistemic_escrow_v1",
        target_function_name="settle_escrow",
        state_domains={
            "sender": (-10, -1, 0, 1, 2, 100, 500),
            "receiver": (-1, 0, 1, 2, 50, 100),
            "amount": (-1, 0, 1, 2, 10, 50, 100),
        },
        mutated_vars=["sender", "receiver"],
        preconditions=["amount > 0", "sender >= amount"],
        postconditions=[
            "sender_post == sender_pre - amount_pre",
            "receiver_post == receiver_pre + amount_pre",
        ],
        conservation_laws=["sender + receiver"],
    )
    spec = EpistemicIntentCompiler.compile(draft)
    assert spec.spec_id == "epistemic_escrow_v1"
    assert spec.domain_floor_enforced is True

    gate = FormalMAGSGate()
    sound_code = """
def settle_escrow(state: dict) -> dict:
    amount = state["amount"]
    sender = state["sender"]
    receiver = state["receiver"]
    if amount <= 0 or sender < amount:
        raise ValueError("ERR_PRECONDITION")
    out = dict(state)
    out["sender"] = sender - amount
    out["receiver"] = receiver + amount
    return out
"""
    receipt = gate.prove_candidate(sound_code, spec)
    assert receipt.proved is True
    assert receipt.halt_code == "OK_FORMAL_PROOF_VERIFIED"
    assert receipt.domain_floor_enforced is True


def test_2_compiler_blocks_undefined_variable_hallucination() -> None:
    draft = IntentDraft(
        spec_id="hallucinated_admin_bypass",
        target_function_name="process",
        state_domains={
            "balance": (-1, 0, 1, 2, 100),
            "amount": (-1, 0, 1, 2, 50),
        },
        mutated_vars=["balance"],
        preconditions=["amount > 0", "is_admin == 1"],  # 'is_admin' is not in state_domains!
        postconditions=["balance_post == balance_pre - amount_pre"],
        conservation_laws=[],
    )
    with pytest.raises(HaltEpistemicCompilationFailed, match="UNDEFINED_VARIABLE: is_admin"):
        EpistemicIntentCompiler.compile(draft)


def test_3_compiler_blocks_dunder_and_call_sandbox_escapes() -> None:
    # Smuggle sandbox escape via dunder attribute
    malicious_expr = "().__class__.__base__.__subclasses__()"
    with pytest.raises(HaltEpistemicCompilationFailed, match="FORBIDDEN_AST_NODE"):
        SafeExpressionCompiler.compile_expr(malicious_expr, {"balance"})

    # Function call attempt
    call_expr = "os.system('rm -rf /')"
    with pytest.raises(HaltEpistemicCompilationFailed, match="FORBIDDEN_AST_NODE: Call"):
        SafeExpressionCompiler.compile_expr(call_expr, {"balance"})


def test_4_compiler_catches_zero_division() -> None:
    fn = SafeExpressionCompiler.compile_expr("amount // zero_val", {"amount", "zero_val"})
    with pytest.raises(HaltEpistemicCompilationFailed, match="ERR_ZERO_DIVISION_IN_EXPRESSION"):
        fn({"amount": 100, "zero_val": 0})

    # Test modulo zero division
    fn_mod = SafeExpressionCompiler.compile_expr("amount % zero_val", {"amount", "zero_val"})
    with pytest.raises(HaltEpistemicCompilationFailed, match="ERR_ZERO_DIVISION_IN_EXPRESSION"):
        fn_mod({"amount": 100, "zero_val": 0})


def test_7_compiler_ast_nodes_and_operators() -> None:
    # 0. SyntaxError handling and single-sided underscore variable names
    with pytest.raises(HaltEpistemicCompilationFailed, match="SYNTAX_ERROR"):
        SafeExpressionCompiler.compile_expr("x + * y", {"x", "y"})

    fn_partial_dunder = SafeExpressionCompiler.compile_expr(
        "__prefix + suffix__", {"__prefix", "suffix__"}
    )
    assert fn_partial_dunder({"__prefix": 2, "suffix__": 3}) == 5

    # 1. Dunder name check
    with pytest.raises(HaltEpistemicCompilationFailed, match="FORBIDDEN_DUNDER"):
        SafeExpressionCompiler.compile_expr("__secret__", {"__secret__"})

    # 2. Forbidden constant type (string constant)
    with pytest.raises(HaltEpistemicCompilationFailed, match="FORBIDDEN_CONSTANT_TYPE"):
        fn_str = SafeExpressionCompiler.compile_expr("'bad_string'", set())
        fn_str({})

    # 3. Boolean AND & OR evaluation
    fn_and = SafeExpressionCompiler.compile_expr("x > 0 and y > 0", {"x", "y"})
    assert fn_and({"x": 1, "y": 2}) is True
    assert fn_and({"x": 1, "y": -1}) is False

    fn_or = SafeExpressionCompiler.compile_expr("x > 0 or y > 0", {"x", "y"})
    assert fn_or({"x": -1, "y": 2}) is True
    assert fn_or({"x": -1, "y": -1}) is False

    # 4. Unary NOT and USub
    fn_not = SafeExpressionCompiler.compile_expr("not x", {"x"})
    assert fn_not({"x": False}) is True
    assert fn_not({"x": True}) is False

    fn_usub = SafeExpressionCompiler.compile_expr("-x", {"x"})
    assert fn_usub({"x": 5}) == -5

    # 5. Empty postconditions and empty conservation laws
    draft_empty = IntentDraft(
        spec_id="empty_draft",
        target_function_name="noop",
        state_domains={"a": (-1, 0, 1, 2)},
        mutated_vars=[],
        preconditions=[],
        postconditions=[],
        conservation_laws=[],
    )
    spec_empty = EpistemicIntentCompiler.compile(draft_empty)
    assert spec_empty.precondition_fn({"a": 1}) is True
    assert spec_empty.postcondition_fn({"a": 1}, {"a": 1}) is True
    assert spec_empty.conserved_quantity_fn is None

    # 6. Forbidden operators (bitwise shift, in, bitwise invert)
    with pytest.raises(HaltEpistemicCompilationFailed, match="FORBIDDEN_OP"):
        SafeExpressionCompiler.compile_expr("x << 1", {"x"})({"x": 1})

    with pytest.raises(HaltEpistemicCompilationFailed, match="FORBIDDEN_OP"):
        SafeExpressionCompiler.compile_expr("x in y", {"x", "y"})({"x": 1, "y": 1})

    with pytest.raises(HaltEpistemicCompilationFailed, match="FORBIDDEN_OP"):
        SafeExpressionCompiler.compile_expr("~x", {"x"})({"x": 1})

    # 7. Unsupported AST node (subscript)
    with pytest.raises(HaltEpistemicCompilationFailed, match="UNSUPPORTED_AST_NODE"):
        SafeExpressionCompiler.compile_expr("x[0]", {"x"})({"x": [1]})

    # 8. Chained comparison returning False
    fn_chain = SafeExpressionCompiler.compile_expr("1 < x < 5", {"x"})
    assert fn_chain({"x": 0}) is False
    assert fn_chain({"x": 10}) is False
    assert fn_chain({"x": 3}) is True

    # 9. Non-empty postconditions returning False
    draft_multi = IntentDraft(
        spec_id="multi_draft",
        target_function_name="act",
        state_domains={"a": (-1, 0, 1, 2)},
        mutated_vars=["a"],
        preconditions=[],
        postconditions=["a_post == a_pre + 1", "a_post > 10"],
        conservation_laws=[],
    )
    spec_multi = EpistemicIntentCompiler.compile(draft_multi)
    assert spec_multi.postcondition_fn({"a": 1}, {"a": 2}) is False


def test_compile_enforces_domain_floor_by_default() -> None:
    draft_with_narrow_domain = IntentDraft(
        spec_id="narrow_domain_draft",
        target_function_name="act",
        state_domains={"x": (0,)},
        mutated_vars=["x"],
        preconditions=[],
        postconditions=["x_post == x_pre"],
        conservation_laws=[],
    )
    # Default compilation must reject narrow domain (fail-closed)
    with pytest.raises(DomainAdequacyViolation, match="DOMAIN_TOO_NARROW") as exc_info:
        EpistemicIntentCompiler.compile(draft_with_narrow_domain)
    assert exc_info.value.code == "DOMAIN_TOO_NARROW"
    assert exc_info.value.variable == "x"

    # Passing policy=None without allow_unfloored_domain=True must fail closed
    with pytest.raises(DomainAdequacyViolation, match="DOMAIN_FLOOR_REQUIRED") as req_exc:
        EpistemicIntentCompiler.compile(draft_with_narrow_domain, policy=None)
    assert req_exc.value.code == "DOMAIN_FLOOR_REQUIRED"
    assert req_exc.value.variable == "*"

    # Non-bool allow_unfloored_domain must raise ValueError
    with pytest.raises(ValueError, match="allow_unfloored_domain must be a bool"):
        EpistemicIntentCompiler.compile(draft_with_narrow_domain, allow_unfloored_domain="yes")  # type: ignore[arg-type]

    # Explicit allow_unfloored_domain=True allows unfloored compilation with domain_floor_enforced=False
    spec_unfloored = EpistemicIntentCompiler.compile(
        draft_with_narrow_domain, allow_unfloored_domain=True
    )
    assert spec_unfloored.domain_floor_enforced is False

    # Missing boundary value (4 distinct values, but missing 1 or -1)
    draft_missing_boundary = IntentDraft(
        spec_id="missing_boundary",
        target_function_name="act",
        state_domains={"x": (0, -1, 2, 3)},
        mutated_vars=["x"],
        preconditions=[],
        postconditions=["x_post == x_pre"],
        conservation_laws=[],
    )
    with pytest.raises(DomainAdequacyViolation, match="DOMAIN_MISSING_BOUNDARY_VALUES"):
        EpistemicIntentCompiler.compile(draft_missing_boundary)

    # Non-integer value in domain (e.g. bool is rejected by type(v) is not int)
    draft_non_int = IntentDraft(
        spec_id="non_int_domain",
        target_function_name="act",
        state_domains={"x": (True, 0, -1, 2)},
        mutated_vars=["x"],
        preconditions=[],
        postconditions=["x_post == x_pre"],
        conservation_laws=[],
    )
    with pytest.raises(DomainAdequacyViolation, match="DOMAIN_NON_INTEGER_VALUE"):
        EpistemicIntentCompiler.compile(draft_non_int)

    # Undeclared mutated variable
    draft_undeclared_mut = IntentDraft(
        spec_id="undeclared_mut",
        target_function_name="act",
        state_domains={"x": (-1, 0, 1, 2)},
        mutated_vars=["x", "ghost"],
        preconditions=[],
        postconditions=["x_post == x_pre"],
        conservation_laws=[],
    )
    with pytest.raises(HaltEpistemicCompilationFailed, match="UNDECLARED_MUTATED_VARS"):
        EpistemicIntentCompiler.compile(draft_undeclared_mut)

    # signed_floor validation: undeclared variable, missing floor value, and valid signed_floor with policy=None
    valid_draft = IntentDraft(
        spec_id="valid_draft",
        target_function_name="act",
        state_domains={"x": (-1, 0, 1, 2)},
        mutated_vars=["x"],
        preconditions=[],
        postconditions=["x_post == x_pre"],
        conservation_laws=[],
    )
    with pytest.raises(DomainAdequacyViolation, match="DOMAIN_FLOOR_VARIABLE_UNDECLARED"):
        EpistemicIntentCompiler.compile(valid_draft, signed_floor={"undeclared_var": (0,)})

    with pytest.raises(DomainAdequacyViolation, match="DOMAIN_MISSING_FLOOR_VALUES"):
        EpistemicIntentCompiler.compile(valid_draft, signed_floor={"x": (-1, 0, 99)})

    spec_signed_only = EpistemicIntentCompiler.compile(
        valid_draft, policy=None, signed_floor={"x": (-1, 0, 1, 2)}
    )
    assert spec_signed_only.domain_floor_enforced is True

    # DomainAdequacyPolicy validation and immutability
    assert DEFAULT_DOMAIN_ADEQUACY_POLICY.min_cardinality == 4
    assert DEFAULT_DOMAIN_ADEQUACY_POLICY.required_values == frozenset({0, 1, -1, 2})
    with pytest.raises(dataclasses.FrozenInstanceError):
        DEFAULT_DOMAIN_ADEQUACY_POLICY.min_cardinality = 1  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        valid_draft.spec_id = "mutated"  # type: ignore[misc]

    assert DomainAdequacyPolicy(min_cardinality=1, required_values=frozenset({0})).min_cardinality == 1
    with pytest.raises(ValueError, match="min_cardinality must be a positive int"):
        DomainAdequacyPolicy(min_cardinality=0)
    with pytest.raises(ValueError, match="min_cardinality must be a positive int"):
        DomainAdequacyPolicy(min_cardinality=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="required_values must contain ints only"):
        DomainAdequacyPolicy(required_values=frozenset({0, True}))  # type: ignore[arg-type]


def test_5_compiled_spec_catches_subtle_conservation_bug() -> None:
    draft = IntentDraft(
        spec_id="epistemic_conservation_check",
        target_function_name="transfer",
        state_domains={
            "alice": (-1, 0, 1, 2, 100, 500),
            "bob": (-1, 0, 1, 2, 100, 500),
            "fee": (-1, 0, 1, 2, 5, 10),
        },
        mutated_vars=["alice", "bob", "fee"],
        preconditions=["alice >= 10"],
        postconditions=[
            "alice_post == alice_pre - 10",
            "bob_post == bob_pre + 10 - fee_pre",
        ],
        conservation_laws=["alice + bob + fee"],
    )
    spec = EpistemicIntentCompiler.compile(draft)
    gate = FormalMAGSGate()

    # Buggy code: loses 1 unit of conservation when fee == 10
    buggy_code = """
def transfer(state: dict) -> dict:
    alice = state["alice"]
    bob = state["bob"]
    fee = state["fee"]
    if alice < 10:
        raise ValueError()
    out = dict(state)
    out["alice"] = alice - 10
    out["bob"] = bob + 10 - fee
    out["fee"] = fee + (1 if fee == 10 else 0)  # Conservation leak!
    return out
"""
    receipt = gate.prove_candidate(buggy_code, spec)
    assert receipt.proved is False
    assert receipt.halt_code == "HALT_FORMAL_PROOF_FAILED"
    assert "Conservation law violated" in (receipt.violation_detail or "")


def test_6_epistemic_linguistic_compliance() -> None:
    src_file = Path("src/epistemic_intent_compiler.py")
    test_file = Path("tests/test_epistemic_intent_compiler.py")
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
