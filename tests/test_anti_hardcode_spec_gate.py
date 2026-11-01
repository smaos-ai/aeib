#!/usr/bin/env python3
"""
Tests for `src/anti_hardcode_spec_gate.py` — Hardened 4-Pillar Anti-Hardcode,
PROCTOR Canary & Stratified Holdout Gate.
"""

from __future__ import annotations

import ast
import dataclasses
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.anti_hardcode_spec_gate import (
    AntiHardcodeSpecGate,
    AntiHardcodeVerdict,
    ASTInspectionResult,
    CanaryTestCase,
    HonestBlockerTicket,
    REQUIRED_HOLDOUT_STRATA,
    STATUS_ACCEPTED_BLOCKER,
    STATUS_ALLOW_GENUINE,
    STATUS_HALT_CANARY_VIOLATED,
    STATUS_HALT_OVERFITTED,
    STATUS_HALT_PUBLIC_FAILED,
    STATUS_HALT_STATIC_TAMPER,
    STATUS_HALT_WEAK_MUTATION,
    STATUS_REJECTED_BLOCKER,
    STATUS_REVIEW_PARTIAL,
    SUSPICION_HALT_THRESHOLD_BPS,
    SpecificationContract,
    _ast_literal_or_none,
    _extract_nontrivial_scalars,
    _is_trivial_base_constant,
    _normalize_for_jcs,
    _run_candidate_out_of_process,
    _synthesize_stratum_arg,
    _value_matches_ast_subtree,
    compute_jcs_caid,
    inspect_ast_for_hardcoding_and_tampering,
)

GENUINE_MERGE_SORTED_SOURCE = """
def merge_sorted_lists(a, b):
    i = 0
    j = 0
    merged = []
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            merged.append(a[i])
            i += 1
        else:
            merged.append(b[j])
            j += 1
    while i < len(a):
        merged.append(a[i])
        i += 1
    while j < len(b):
        merged.append(b[j])
        j += 1
    return merged
"""

REFERENCE_MERGE_ORACLE_SOURCE = """
def merge_sorted_lists(a, b):
    return sorted(list(a) + list(b))
"""


def _make_merge_contract() -> SpecificationContract:
    return SpecificationContract(
        spec_id="SPEC-MERGE-SORTED-001",
        target_function_name="merge_sorted_lists",
        public_examples=(
            (([2, 7], [3, 9]), [2, 3, 7, 9]),
            (([4, 12], [5, 15]), [4, 5, 12, 15]),
        ),
    )


def test_pillar_all_genuine_generalized_implementation_passes() -> None:
    """Scenario 1: Genuine generalized implementation passes all 4 pillars with signed verdict."""
    gate = AntiHardcodeSpecGate(generator_seed=42)
    contract = _make_merge_contract()
    verdict = gate.evaluate_candidate(
        contract=contract,
        candidate_source=GENUINE_MERGE_SORTED_SOURCE,
        reference_oracle_source=REFERENCE_MERGE_ORACLE_SOURCE,
    )
    assert verdict.accepted is True
    assert verdict.status_code == STATUS_ALLOW_GENUINE
    assert verdict.violation_reason == "NONE"
    assert verdict.public_pass_rate_bps == 10000
    assert verdict.hidden_holdout_pass_rate_bps == 10000
    assert verdict.holdout_stratification_coverage_bps == 10000
    assert verdict.fixture_mirror_suspicion_bps == 0
    assert verdict.canary_failures_expected_bps == 10000
    assert verdict.mutation_kill_rate_bps >= contract.minimum_mutation_kill_bps
    assert verdict.spec_digest.startswith("sha256:")
    assert verdict.candidate_digest.startswith("sha256:")
    assert verdict.oracle_digest.startswith("sha256:")
    assert gate.verify_verdict_signature(verdict) is True
    verdict_dict = verdict.to_dict()
    assert verdict_dict["spec_id"] == "SPEC-MERGE-SORTED-001"
    assert verdict_dict["accepted"] is True


def test_pillar1_hardcoded_lookup_and_if_elif_overfitters_caught() -> None:
    """Scenario 2: Hardcoded lookup-table and if/elif overfitters passing 100% public tests are halted."""
    gate = AntiHardcodeSpecGate(generator_seed=42)
    contract = _make_merge_contract()

    lookup_candidate = """
def merge_sorted_lists(a, b):
    table = {
        "case1": [2, 3, 7, 9],
        "case2": [4, 5, 12, 15],
    }
    if a == [2, 7]:
        return table["case1"]
    return table["case2"]
"""
    verdict_lookup = gate.evaluate_candidate(
        contract=contract,
        candidate_source=lookup_candidate,
        reference_oracle_source=REFERENCE_MERGE_ORACLE_SOURCE,
    )
    assert verdict_lookup.accepted is False
    assert verdict_lookup.status_code == STATUS_HALT_STATIC_TAMPER
    assert "LOOKUP_TABLE" in verdict_lookup.violation_reason
    assert verdict_lookup.fixture_mirror_suspicion_bps == 10000
    assert gate.verify_verdict_signature(verdict_lookup) is True

    if_elif_candidate = """
def merge_sorted_lists(a, b):
    if a == [2, 7] and b == [3, 9]:
        return [2, 3, 7, 9]
    elif a == [4, 12] and b == [5, 15]:
        return [4, 5, 12, 15]
    return []
"""
    verdict_branches = gate.evaluate_candidate(
        contract=contract,
        candidate_source=if_elif_candidate,
        reference_oracle_source=REFERENCE_MERGE_ORACLE_SOURCE,
    )
    assert verdict_branches.accepted is False
    assert verdict_branches.status_code == STATUS_HALT_STATIC_TAMPER
    assert "FIXTURE_MIRROR_SUSPICION_EXCEEDED" in verdict_branches.violation_reason
    assert verdict_branches.fixture_mirror_suspicion_bps == 10000


def test_pillar2_subtle_overfitter_caught_by_stratified_hidden_holdouts() -> None:
    """Scenario 3: Subtle overfitter passes AST check and public examples but fails hidden holdouts."""
    gate = AntiHardcodeSpecGate(generator_seed=42)
    contract = _make_merge_contract()

    # Evades AST literal detection and works on 2-element positive lists where a[0]<b[0]<a[1]<b[1],
    # but fails on empty lists, singletons, negatives, large lists, and adversarial order.
    subtle_overfitter = """
def merge_sorted_lists(a, b):
    if len(a) == 2 and len(b) == 2:
        return [a[0], b[0], a[1], b[1]]
    return list(a)
"""
    verdict = gate.evaluate_candidate(
        contract=contract,
        candidate_source=subtle_overfitter,
        reference_oracle_source=REFERENCE_MERGE_ORACLE_SOURCE,
    )
    assert verdict.accepted is False
    assert verdict.status_code == STATUS_HALT_OVERFITTED
    assert verdict.public_pass_rate_bps == 10000
    assert verdict.fixture_mirror_suspicion_bps == 0
    assert verdict.holdout_stratification_coverage_bps == 10000
    assert verdict.hidden_holdout_pass_rate_bps < contract.review_holdout_floor_bps


def test_pillar2_proctor_canary_catches_always_equal_and_impossible_output() -> None:
    """Scenario 4: PROCTOR Canary trap catches universal-equality `__eq__` tamper and leaked canary output."""
    gate = AntiHardcodeSpecGate(generator_seed=42)
    contract = _make_merge_contract()

    always_equal_candidate = """
class EverythingEqual:
    def __eq__(self, other):
        return True

def merge_sorted_lists(a, b):
    return EverythingEqual()
"""
    verdict_eq = gate.evaluate_candidate(
        contract=contract,
        candidate_source=always_equal_candidate,
        reference_oracle_source=REFERENCE_MERGE_ORACLE_SOURCE,
    )
    assert verdict_eq.accepted is False
    assert verdict_eq.status_code == STATUS_HALT_CANARY_VIOLATED
    assert verdict_eq.violation_reason == "REASON_UNIVERSAL_EQ_TAMPER_DETECTED"

    # Candidate that passes public examples normally, then triggers AlwaysEqual only on a specific canary input
    canary_contract = SpecificationContract(
        spec_id="SPEC-CANARY-LEAK-001",
        target_function_name="merge_sorted_lists",
        public_examples=((([2, 7], [3, 9]), [2, 3, 7, 9]),),
        canary_cases=(
            CanaryTestCase(
                canary_id="CANARY-TRAP-99",
                input_args=([99], [99]),
                impossible_expected_output=[-999, -999],
                trap_category="HOLDOUT_LEAKAGE_TRAP",
            ),
        ),
    )
    leaked_canary_candidate = """
def merge_sorted_lists(a, b):
    if len(a) == 1 and a[0] > 90:
        return [-999, -999]
    return sorted(list(a) + list(b))
"""
    verdict_leak = gate.evaluate_candidate(
        contract=canary_contract,
        candidate_source=leaked_canary_candidate,
        reference_oracle_source=REFERENCE_MERGE_ORACLE_SOURCE,
    )
    assert verdict_leak.accepted is False
    assert verdict_leak.status_code == STATUS_HALT_CANARY_VIOLATED
    assert verdict_leak.violation_reason == "REASON_CANARY_IMPOSSIBLE_OUTPUT_MATCHED"
    assert verdict_leak.canary_failures_expected_bps == 0


def test_pillar1_legitimate_base_cases_not_false_flagged() -> None:
    """Scenario 5: Legitimate base cases (`if n <= 1: return n`, `if not items: return 0`) have 0 suspicion."""
    gate = AntiHardcodeSpecGate(generator_seed=42)
    range_contract = SpecificationContract(
        spec_id="SPEC-RANGE-COUNT-001",
        target_function_name="count_in_closed_range",
        public_examples=(
            (([], 0, 1), 0),
            (([0, 1], 1, 0), -1),
            (([5], 5, 5), 1),
            (([4, 8, 12], 4, 8), 2),
            (([3, 20], 2, 15), 1),
        ),
    )
    range_source = """
def count_in_closed_range(items, low, high):
    if not items:
        return 0
    if high < low:
        return -1
    count = 0
    for val in items:
        if val >= low and val <= high:
            count += 1
    return count
"""
    ast_res = gate.inspect_ast(range_source, range_contract)
    assert ast_res.halted is False
    assert ast_res.fixture_mirror_suspicion_bps == 0
    assert ast_res.lookup_table_detected is False
    assert ast_res.matched_public_io_pairs == 0
    assert ast_res.total_non_trivial_public_pairs == 3

    dict_innocent_source = """
def count_in_closed_range(items, low, high):
    config = {"threshold": 99999, "version": 88888}
    if not items:
        return 0
    return len([x for x in items if low <= x <= high])
"""
    dict_ast_res = gate.inspect_ast(dict_innocent_source, range_contract)
    assert dict_ast_res.halted is False
    assert dict_ast_res.fixture_mirror_suspicion_bps == 0
    assert dict_ast_res.lookup_table_detected is False

    verdict = gate.evaluate_candidate(
        contract=range_contract,
        candidate_source=range_source,
        reference_oracle_source=range_source,
    )
    assert verdict.accepted is True
    assert verdict.status_code == STATUS_ALLOW_GENUINE
    assert verdict.fixture_mirror_suspicion_bps == 0
    assert verdict.mutation_kill_rate_bps == 10000


def test_pillar4_honest_blocker_ticket_accepts_contradiction_and_rejects_bogus_excuse() -> None:
    """Scenario 6: Honest Blocker Ticket accepts genuine contradiction and rejects satisfiable excuse."""
    gate = AntiHardcodeSpecGate(generator_seed=42)

    valid_ticket = gate.submit_honest_blocker_ticket(
        spec_id="SPEC-CONTRADICT-001",
        contradicting_constraint_a="Output must strictly exceed 100",
        contradicting_constraint_b="Output must be strictly negative (< 0)",
        minimal_counterexample_input=(5,),
        predicate_a_expr="res > 100",
        predicate_b_expr="res < 0",
    )
    assert valid_ticket.verified_contradiction is True
    assert valid_ticket.status_code == STATUS_ACCEPTED_BLOCKER
    assert valid_ticket.verification_reason == "REASON_MUTUALLY_EXCLUSIVE_POSTCONDITIONS_CONFIRMED"
    assert valid_ticket.ticket_caid.startswith("sha256:")
    assert gate.verify_blocker_ticket_signature(valid_ticket) is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        valid_ticket.ticket_id = "mut"  # type: ignore[misc]
    assert valid_ticket.to_dict()["verified_contradiction"] is True

    # Boundary test: exactly 1 probe matches predicate a (res == 100000) and exactly 1 probe matches predicate b (res == -1)
    boundary_ticket = gate.submit_honest_blocker_ticket(
        spec_id="SPEC-CONTRADICT-BOUNDARY",
        contradicting_constraint_a="Output must equal 100000",
        contradicting_constraint_b="Output must equal -1",
        minimal_counterexample_input=(5,),
        predicate_a_expr="res == 100000",
        predicate_b_expr="res == -1",
    )
    assert boundary_ticket.verified_contradiction is True
    assert boundary_ticket.status_code == STATUS_ACCEPTED_BLOCKER

    bogus_ticket = gate.submit_honest_blocker_ticket(
        spec_id="SPEC-CONTRADICT-001",
        contradicting_constraint_a="Output must be positive (> 0)",
        contradicting_constraint_b="Output must be less than 100",
        minimal_counterexample_input=(5,),
        predicate_a_expr="res > 0",
        predicate_b_expr="res < 100",
    )
    assert bogus_ticket.verified_contradiction is False
    assert bogus_ticket.status_code == STATUS_REJECTED_BLOCKER
    assert gate.verify_blocker_ticket_signature(bogus_ticket) is True

    single_b_ticket = gate.submit_honest_blocker_ticket(
        spec_id="SPEC-CONTRADICT-001",
        contradicting_constraint_a="Output must strictly exceed 100",
        contradicting_constraint_b="Output must equal minus one",
        minimal_counterexample_input=(5,),
        predicate_a_expr="res > 100",
        predicate_b_expr="res == -1",
    )
    assert single_b_ticket.verified_contradiction is True
    assert single_b_ticket.status_code == STATUS_ACCEPTED_BLOCKER

    vacuous_b_ticket = gate.submit_honest_blocker_ticket(
        spec_id="SPEC-CONTRADICT-001",
        contradicting_constraint_a="Output must strictly exceed 100",
        contradicting_constraint_b="Output must be less than minus 999999",
        minimal_counterexample_input=(5,),
        predicate_a_expr="res > 100",
        predicate_b_expr="res < -999999",
    )
    assert vacuous_b_ticket.verified_contradiction is False
    assert vacuous_b_ticket.status_code == STATUS_REJECTED_BLOCKER


def test_out_of_process_isolation_blocks_os_fork() -> None:
    """Scenario 7: Out-of-process runner sets RLIMIT_NPROC=(0,0) and blocks os.fork()."""
    gate = AntiHardcodeSpecGate(generator_seed=42)
    contract = _make_merge_contract()
    fork_bomb_candidate = """
import os

def merge_sorted_lists(a, b):
    os.fork()
    return sorted(list(a) + list(b))
"""
    verdict = gate.evaluate_candidate(
        contract=contract,
        candidate_source=fork_bomb_candidate,
        reference_oracle_source=REFERENCE_MERGE_ORACLE_SOURCE,
    )
    assert verdict.accepted is False
    assert verdict.status_code == STATUS_HALT_PUBLIC_FAILED
    assert "BlockingIOError" in verdict.violation_reason or "OSError" in verdict.violation_reason


def test_pillar1_forbidden_imports_and_syntax_errors_halted() -> None:
    """Verify AST tamper checks catch forbidden imports, attributes, names, and syntax errors."""
    contract = _make_merge_contract()

    syntax_bad = inspect_ast_for_hardcoding_and_tampering("def broken(:", contract)
    assert syntax_bad.halted is True
    assert syntax_bad.violation_reason == "REASON_CANDIDATE_SYNTAX_ERROR"
    assert syntax_bad.fixture_mirror_suspicion_bps == 10000

    for snippet in (
        "import unittest.mock\ndef merge_sorted_lists(a, b): return []",
        "from unittest.mock import MagicMock\ndef merge_sorted_lists(a, b): return []",
        "from unittest.mock import NonCallableMock\ndef merge_sorted_lists(a, b): return []",
        "import sys\ndef merge_sorted_lists(a, b):\n    sys.modules['x'] = None\n    return []",
        "def merge_sorted_lists(a, b):\n    x = __builtins__\n    return []",
    ):
        res = inspect_ast_for_hardcoding_and_tampering(snippet, contract)
        assert res.halted is True
        assert "REASON_FORBIDDEN_AST_TAMPER" in res.violation_reason
        assert len(res.forbidden_tokens_found) >= 1


def test_pillar3_weak_mutation_oracle_and_partial_generalization_review_band() -> None:
    """Verify Pillar 3 halts when dead mutatable constants survive and Review band triggers at 9000..9899 bps."""
    gate = AntiHardcodeSpecGate(generator_seed=42)

    # Candidate with dead mutatable integer constants that survive test assertions
    dead_mutant_candidate = """
def merge_sorted_lists(a, b):
    unused_a = 10
    unused_b = 20
    unused_c = 30
    return sorted(list(a) + list(b))
"""
    contract = _make_merge_contract()
    verdict_mut = gate.evaluate_candidate(
        contract=contract,
        candidate_source=dead_mutant_candidate,
        reference_oracle_source=REFERENCE_MERGE_ORACLE_SOURCE,
    )
    assert verdict_mut.accepted is False
    assert verdict_mut.status_code == STATUS_HALT_WEAK_MUTATION
    assert verdict_mut.mutation_kill_rate_bps < contract.minimum_mutation_kill_bps

    normalized_strata = {
        "empty_or_singleton": (([], [1]), ([2], [])),
        "duplicates": (([3, 3], [3, 3]), ([4, 4], [5, 5])),
        "negatives": (([-5, -2], [-4, -1]), ([-9, -8], [-7, -6])),
        "boundary_extremes": (([-100, 0], [0, 100]), ([-50, 50], [-25, 25])),
        "large_inputs": (([1, 2, 3], [4, 5, 6]), ([7, 8, 9], [10, 11, 12])),
        "adversarial_order": (([20, 30], [1, 2]), ([77, 88], [1, 2])),
    }
    review_contract = SpecificationContract(
        spec_id="SPEC-REVIEW-BAND-001",
        target_function_name="merge_sorted_lists",
        public_examples=((([2, 7], [3, 9]), [2, 3, 7, 9]),),
        domain_bounds_or_strata=normalized_strata,
        minimum_mutation_kill_bps=5000,
    )
    partial_candidate = """
def merge_sorted_lists(a, b):
    if a and a[0] == 77:
        return []
    i = 0
    j = 0
    out = []
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            out.append(a[i])
            i += 1
        else:
            out.append(b[j])
            j += 1
    out.extend(a[i:])
    out.extend(b[j:])
    return out
"""
    verdict_review = gate.evaluate_candidate(
        contract=review_contract,
        candidate_source=partial_candidate,
        reference_oracle_source=REFERENCE_MERGE_ORACLE_SOURCE,
    )
    assert verdict_review.accepted is False
    assert verdict_review.status_code == STATUS_REVIEW_PARTIAL
    assert verdict_review.hidden_holdout_pass_rate_bps >= review_contract.review_holdout_floor_bps
    assert verdict_review.hidden_holdout_pass_rate_bps < review_contract.minimum_holdout_pass_bps


def test_contract_and_canary_validation_and_signature_tamper_detection() -> None:
    """Test dataclass validation boundaries and cryptographic signature tamper rejection."""
    with pytest.raises(ValueError, match="ERR_EMPTY_CANARY_ID"):
        CanaryTestCase(canary_id=" ", input_args=(1,), impossible_expected_output=2)

    with pytest.raises(ValueError, match="ERR_CANARY_INPUT_ARGS_MUST_BE_TUPLE"):
        CanaryTestCase(canary_id="C1", input_args=[1], impossible_expected_output=2)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="ERR_INVALID_TRAP_CATEGORY"):
        CanaryTestCase(canary_id="C1", input_args=(1,), impossible_expected_output=2, trap_category="BAD")

    with pytest.raises(ValueError, match="ERR_EMPTY_SPEC_ID"):
        SpecificationContract(spec_id="", target_function_name="fn", public_examples=(((1,), 1),))

    with pytest.raises(ValueError, match="ERR_EMPTY_TARGET_FUNCTION_NAME"):
        SpecificationContract(spec_id="S1", target_function_name="", public_examples=(((1,), 1),))

    with pytest.raises(ValueError, match="ERR_EMPTY_PUBLIC_EXAMPLES"):
        SpecificationContract(spec_id="S1", target_function_name="fn", public_examples=())

    for bad_bps in (0, 10001):
        with pytest.raises(ValueError, match="ERR_INVALID_MINIMUM_MUTATION_KILL_BPS"):
            SpecificationContract(
                spec_id="S1",
                target_function_name="fn",
                public_examples=(((1,), 1),),
                minimum_mutation_kill_bps=bad_bps,
            )
        with pytest.raises(ValueError, match="ERR_INVALID_MINIMUM_HOLDOUT_PASS_BPS"):
            SpecificationContract(
                spec_id="S1",
                target_function_name="fn",
                public_examples=(((1,), 1),),
                minimum_holdout_pass_bps=bad_bps,
            )

    with pytest.raises(ValueError, match="ERR_INVALID_REVIEW_HOLDOUT_FLOOR_BPS"):
        SpecificationContract(
            spec_id="S1",
            target_function_name="fn",
            public_examples=(((1,), 1),),
            minimum_holdout_pass_bps=9000,
            review_holdout_floor_bps=9500,
        )

    with pytest.raises(ValueError, match="ERR_INVALID_REVIEW_HOLDOUT_FLOOR_BPS"):
        SpecificationContract(
            spec_id="S1",
            target_function_name="fn",
            public_examples=(((1,), 1),),
            review_holdout_floor_bps=0,
        )

    with pytest.raises(ValueError, match="ERR_EMPTY_POLICY_VERSION"):
        SpecificationContract(
            spec_id="S1",
            target_function_name="fn",
            public_examples=(((1,), 1),),
            policy_version=" ",
        )

    with pytest.raises(ValueError, match="ERR_EMPTY_KEY_ID"):
        AntiHardcodeSpecGate(key_id=" ")

    gate = AntiHardcodeSpecGate(private_key=Ed25519PrivateKey.generate(), generator_seed=7)
    with pytest.raises(ValueError, match="ERR_EMPTY_SPEC_ID"):
        gate.submit_honest_blocker_ticket("", "a", "b", (1,), "res > 1", "res < 0")
    with pytest.raises(ValueError, match="ERR_EMPTY_PREDICATE_EXPR"):
        gate.submit_honest_blocker_ticket("S1", "a", "b", (1,), " ", "res < 0")

    ticket = gate.submit_honest_blocker_ticket("S1", "a", "b", (1,), "res > 10", "res < 0")
    assert gate.verify_blocker_ticket_signature(ticket) is True

    other_gate = AntiHardcodeSpecGate(generator_seed=7)
    assert other_gate.verify_blocker_ticket_signature(ticket) is False

    tampered_ticket = type(ticket)(
        **{**ticket.__dict__, "ticket_caid": "sha256:0000"}
    )
    assert gate.verify_blocker_ticket_signature(tampered_ticket) is False


def test_helper_functions_and_edge_cases() -> None:
    """Exercise helper functions, scalar synthesis, and error paths for full mutation adequacy."""
    with pytest.raises(TypeError, match="ERR_FLOAT_FORBIDDEN_IN_JCS_PAYLOAD"):
        _normalize_for_jcs(1.5)

    assert _normalize_for_jcs({"k": (1, True, None, "s")}) == {"k": [1, True, None, "s"]}
    assert isinstance(_normalize_for_jcs(object()), str)
    assert compute_jcs_caid("abc").startswith("sha256:")
    assert compute_jcs_caid({"a": 1}).startswith("sha256:")

    assert _is_trivial_base_constant(None) is True
    assert _is_trivial_base_constant(True) is True
    assert _is_trivial_base_constant(0) is True
    assert _is_trivial_base_constant(-1) is True
    assert _is_trivial_base_constant(1) is True
    assert _is_trivial_base_constant([]) is True
    assert _is_trivial_base_constant(2) is False

    assert _extract_nontrivial_scalars({"a": [1, 5, "hello"]}) == {"a", 5, "hello"}
    ok, val = _ast_literal_or_none(ast.parse("[1, 2]", mode="eval").body)
    assert ok is True and val == [1, 2]
    ok_bad, _ = _ast_literal_or_none(ast.parse("x + y", mode="eval").body)
    assert ok_bad is False

    assert _value_matches_ast_subtree(0, ast.parse("0", mode="eval").body) is False
    assert _value_matches_ast_subtree((7,), ast.parse("7", mode="eval").body) is True
    assert _value_matches_ast_subtree((7, 8), ast.parse("[7, 8, 9]", mode="eval").body) is True

    rng = __import__("random").Random(42)
    for stratum in REQUIRED_HOLDOUT_STRATA:
        scalar_val0 = _synthesize_stratum_arg(10, stratum, 0, 0, rng)
        scalar_val1 = _synthesize_stratum_arg(10, stratum, 1, 0, rng)
        assert isinstance(scalar_val0, int) and isinstance(scalar_val1, int)

    adv_0 = _synthesize_stratum_arg(10, "adversarial_order", 0, 0, rng)
    adv_1 = _synthesize_stratum_arg(10, "adversarial_order", 1, 0, rng)
    assert adv_0 == 100
    assert adv_1 == -100

    rng_large = __import__("random").Random(42)
    large_0 = _synthesize_stratum_arg(10, "large_inputs", 0, 0, rng_large)
    large_1 = _synthesize_stratum_arg(10, "large_inputs", 1, 0, rng_large)
    assert large_0 == -3619
    assert large_1 == 1456

    gate = AntiHardcodeSpecGate(generator_seed=42)
    contract = _make_merge_contract()
    list_strata = gate.generate_stratified_holdouts(contract)
    assert list_strata["empty_or_singleton"] == (([], [3]), ([2], []))
    assert list_strata["duplicates"] == (([14, 14, 14], [7, 7, 7]), ([6, 6, 6], [6, 6, 6]))
    assert list_strata["negatives"] == (([-28, -26, -9], [-25, -15, -8]), ([-22, -21, -10], [-33, -29, -14]))
    assert list_strata["boundary_extremes"] == (
        ([-100000, 0, 100000], [-99999, 1, 99999]),
        ([-100000, 0, 100000], [-99999, 1, 99999]),
    )
    assert len(list_strata["large_inputs"][0][0]) == 16
    assert list_strata["adversarial_order"] == (
        ([50, 60, 70], [-70, -60, -50]),
        ([60, 70, 80], [-80, -70, -60]),
    )

    scalar_contract = SpecificationContract(
        spec_id="S-INT",
        target_function_name="f",
        public_examples=(((2, 3), 5),),
    )
    scalar_strata = gate.generate_stratified_holdouts(scalar_contract)
    assert scalar_strata == {
        "empty_or_singleton": ((0, 0), (1, 1)),
        "duplicates": ((7, 7), (7, 7)),
        "negatives": ((-50, -10), (-50, -10)),
        "boundary_extremes": ((-100000, 100000), (-100000, 100000)),
        "large_inputs": ((-3619, 1456), (-1102, 4037)),
        "adversarial_order": ((100, -100), (100, -100)),
    }

    # Verify frozen dataclass immutability on all dataclasses
    canary_obj = CanaryTestCase(canary_id="C1", input_args=(1,), impossible_expected_output=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        canary_obj.canary_id = "mut"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        contract.spec_id = "mut"  # type: ignore[misc]
    ast_obj = gate.inspect_ast("def merge_sorted_lists(a, b): return []", contract)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ast_obj.halted = True  # type: ignore[misc]

    # Candidate that passes public examples, then triggers tamper_eq on canary case
    canary_eq_contract = SpecificationContract(
        spec_id="SPEC-CANARY-EQ-ONLY",
        target_function_name="merge_sorted_lists",
        public_examples=((([2, 7], [3, 9]), [2, 3, 7, 9]),),
        canary_cases=(
            CanaryTestCase(
                canary_id="CANARY-EQ-99",
                input_args=([99], [99]),
                impossible_expected_output=[-1],
            ),
        ),
    )
    canary_eq_src = """
class EverythingEqual:
    def __eq__(self, other):
        return True

def merge_sorted_lists(a, b):
    if len(a) == 1 and a[0] > 90:
        return EverythingEqual()
    return sorted(list(a) + list(b))
"""
    v_canary_eq = gate.evaluate_candidate(canary_eq_contract, canary_eq_src, REFERENCE_MERGE_ORACLE_SOURCE)
    assert v_canary_eq.accepted is False
    assert v_canary_eq.status_code == STATUS_HALT_CANARY_VIOLATED
    assert v_canary_eq.public_pass_rate_bps == 10000

    # Candidate that passes public examples and canary, then crashes on holdout
    holdout_crash_src = """
def merge_sorted_lists(a, b):
    if not a or not b:
        raise RuntimeError("holdout crash")
    return sorted(list(a) + list(b))
"""
    v_holdout_crash = gate.evaluate_candidate(contract, holdout_crash_src, REFERENCE_MERGE_ORACLE_SOURCE)
    assert v_holdout_crash.accepted is False
    assert v_holdout_crash.status_code == STATUS_HALT_OVERFITTED
    assert v_holdout_crash.violation_reason == "REASON_HOLDOUT_RUNTIME_FAILURE"

    # Single-case (N=1) per stratum boundary check for holdout_stratification_coverage_bps (kills > 0 -> > 1)
    n1_strata = {s: ((([1], [2]),),) for s in REQUIRED_HOLDOUT_STRATA}
    n1_contract = SpecificationContract(
        spec_id="SPEC-N1-STRATA",
        target_function_name="merge_sorted_lists",
        public_examples=((([2, 7], [3, 9]), [2, 3, 7, 9]),),
        domain_bounds_or_strata={s: (([1], [2]),) for s in REQUIRED_HOLDOUT_STRATA},
    )
    v_n1 = gate.evaluate_candidate(n1_contract, wrong_candidate := "def merge_sorted_lists(a, b):\n    return [2, 3, 7, 9]\n", REFERENCE_MERGE_ORACLE_SOURCE)
    assert v_n1.holdout_stratification_coverage_bps == 10000

    # Test out-of-process timeout and missing function
    missing_fn_res = _run_candidate_out_of_process("x = 1", "missing_fn", [(1,)])
    assert missing_fn_res["status"] == "error"
    assert missing_fn_res["detail"] == "TARGET_FUNCTION_NOT_FOUND"

    timeout_res = _run_candidate_out_of_process(
        "def loop_forever(x):\n    while True:\n        pass\n",
        "loop_forever",
        [(1,)],
        timeout_seconds=0.1,
    )
    assert timeout_res["status"] == "error"
    assert timeout_res["detail"] == "REASON_CANDIDATE_TIMEOUT"

    # Public example mismatch test
    wrong_candidate = "def merge_sorted_lists(a, b):\n    return [0]\n"
    verdict_wrong = gate.evaluate_candidate(contract, wrong_candidate, REFERENCE_MERGE_ORACLE_SOURCE)
    assert verdict_wrong.accepted is False
    assert verdict_wrong.status_code == STATUS_HALT_PUBLIC_FAILED
    assert verdict_wrong.public_pass_rate_bps == 0
    assert gate.verify_verdict_signature(verdict_wrong) is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict_wrong.accepted = True  # type: ignore[misc]

    assert other_gate_verify_fails(gate, verdict_wrong) is True


def other_gate_verify_fails(gate: AntiHardcodeSpecGate, verdict) -> bool:
    other = AntiHardcodeSpecGate(generator_seed=99)
    tampered = type(verdict)(**{**verdict.__dict__, "verdict_caid": "sha256:bad"})
    return (other.verify_verdict_signature(verdict) is False) and (gate.verify_verdict_signature(tampered) is False)
