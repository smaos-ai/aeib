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
tests/test_inverse_lifecycle_referee.py
================================================================================
Test suite for InverseLifecycleReferee & Empirical Asymptotic Scaling Oracle.

Evaluated under the stated model:
- Static AST purity checks (mock stubs, dynamic execution, cyclomatic complexity limit).
- Functional verification against ground truth oracles and edge cases.
- Asymptotic scaling probe: flags O(N^2) regressions on N vs 10N worst-case inputs.
- Pareto tournament selection and Ed25519 canonical receipt verification.
- Tamper detection and negative controls.
- Epistemic linguistic compliance check.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from pathlib import Path
from typing import List, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.inverse_lifecycle_referee import (
    DEFAULT_MAX_CYCLOMATIC_COMPLEXITY,
    DEFAULT_MAX_SCALING_RATIO_BPS,
    DEFAULT_N_LARGE,
    DEFAULT_N_SMALL,
    O_1_SCALING_THRESHOLD_BPS,
    ASTAuditResult,
    AsymptoticComplexityClass,
    CandidateEvaluation,
    CandidateSpecification,
    EvaluationDisposition,
    InverseLifecycleReferee,
    RefereeReceipt,
    ScalingMeasurement,
    audit_candidate_ast,
    calculate_cyclomatic_complexity,
    canonical_json_v1,
    evaluate_asymptotic_scaling,
    evaluate_candidate_correctness,
    execute_isolated_entrypoint,
)


# -----------------------------------------------------------------------------
# Test Cases & Problem Setup: Contains Duplicate II
# -----------------------------------------------------------------------------
def _generate_worst_case_input(n: int) -> Tuple[List[int], int]:
    """Generates an array with all unique elements where distance k = n."""
    return (list(range(n)), n)


SAMPLE_TEST_CASES = [
    (([1, 2, 3, 1], 3), True),
    (([1, 0, 1, 1], 1), True),
    (([1, 2, 3, 1, 2, 3], 2), False),
    (([1, 2, 3, 4, 5], 3), False),
]

CODE_CANDIDATE_STUB = """
def has_nearby_duplicate(nums, k):
    return False
"""

CODE_CANDIDATE_QUADRATIC = """
def has_nearby_duplicate(nums, k):
    n = len(nums)
    for i in range(n):
        limit = min(n, i + k + 1)
        for j in range(i + 1, limit):
            if nums[i] == nums[j]:
                return True
    return False
"""

CODE_CANDIDATE_OPTIMAL = """
def has_nearby_duplicate(nums, k):
    seen = set()
    for i, x in enumerate(nums):
        if x in seen:
            return True
        seen.add(x)
        if len(seen) > k:
            seen.remove(nums[i - k])
    return False
"""

CODE_HIGH_COMPLEXITY = """
def has_nearby_duplicate(nums, k):
    if len(nums) == 0:
        return False
    if k <= 0:
        return False
    for i in range(len(nums)):
        if nums[i] == 1:
            pass
        elif nums[i] == 2:
            pass
        elif nums[i] == 3:
            pass
        elif nums[i] == 4:
            pass
        elif nums[i] == 5:
            pass
        elif nums[i] == 6:
            pass
        elif nums[i] == 7:
            pass
        elif nums[i] == 8:
            pass
        elif nums[i] == 9:
            pass
    return False
"""

CODE_DYNAMIC_EXEC = """
def has_nearby_duplicate(nums, k):
    return eval("False")
"""

CODE_EMPTY_PASS = """
def has_nearby_duplicate(nums, k):
    pass
"""


@pytest.fixture
def sample_spec() -> CandidateSpecification:
    return CandidateSpecification(
        problem_id="prob_contains_dup_2",
        entrypoint_function="has_nearby_duplicate",
        test_cases=SAMPLE_TEST_CASES,
        worst_case_input_generator=_generate_worst_case_input,
        max_cyclomatic_complexity=8,  # claim: config
        max_scaling_ratio_bps=250000,  # claim: config (25.0x ratio in integer bps)
        n_small=150,  # claim: config
        n_large=1500,  # claim: config
    )


# -----------------------------------------------------------------------------
# Test 0: Configuration Constants & Dataclass Immutability
# -----------------------------------------------------------------------------
def test_0_config_constants_and_immutability() -> None:
    assert DEFAULT_MAX_CYCLOMATIC_COMPLEXITY == int("8")
    assert DEFAULT_N_SMALL == int("200")
    assert DEFAULT_N_LARGE == int("2000")
    assert DEFAULT_MAX_SCALING_RATIO_BPS == int("250000")
    assert O_1_SCALING_THRESHOLD_BPS == int("40000")

    spec_default = CandidateSpecification(
        problem_id="prob_default",
        entrypoint_function="fn",
        test_cases=[],
        worst_case_input_generator=lambda n: (n,),
    )
    assert spec_default.n_small == DEFAULT_N_SMALL
    assert spec_default.n_large == DEFAULT_N_LARGE
    assert spec_default.max_cyclomatic_complexity == DEFAULT_MAX_CYCLOMATIC_COMPLEXITY

    # Assert immutability of frozen dataclasses
    dummy_scaling = ScalingMeasurement(
        n_small=100,
        n_large=1000,
        t_small_nanos=10,
        t_large_nanos=100,
        scaling_ratio_bps=100000,
        complexity_class=AsymptoticComplexityClass.O_N,
        acceptable=True,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        dummy_scaling.acceptable = False  # type: ignore


# -----------------------------------------------------------------------------
# Test 1: Static AST Cleanliness & Purity
# -----------------------------------------------------------------------------
def test_1_ast_cleanliness_and_purity(sample_spec: CandidateSpecification) -> None:
    # 1. Clean optimal candidate passes AST audit
    clean_audit = audit_candidate_ast(CODE_CANDIDATE_OPTIMAL, "has_nearby_duplicate")
    assert clean_audit.clean is True
    assert clean_audit.cyclomatic_complexity <= DEFAULT_MAX_CYCLOMATIC_COMPLEXITY
    assert clean_audit.node_count > 0
    assert len(clean_audit.violations) == 0

    # 2. Syntax error detection
    syntax_err_audit = audit_candidate_ast("def broken(: return", "broken")
    assert syntax_err_audit.clean is False
    assert syntax_err_audit.cyclomatic_complexity > 100
    assert any("ERR_SYNTAX_ERROR" in v for v in syntax_err_audit.violations)

    # 3. Dynamic call detection (eval)
    eval_audit = audit_candidate_ast(CODE_DYNAMIC_EXEC, "has_nearby_duplicate")
    assert eval_audit.clean is False
    assert any("ERR_FORBIDDEN_DYNAMIC_CALL: eval" in v for v in eval_audit.violations)

    # 4. Empty pass stub detection
    pass_audit = audit_candidate_ast(CODE_EMPTY_PASS, "has_nearby_duplicate")
    assert pass_audit.clean is False
    assert any("ERR_EMPTY_STUB_IMPLEMENTATION" in v for v in pass_audit.violations)

    # 5. Missing entrypoint detection
    missing_entry_audit = audit_candidate_ast(CODE_CANDIDATE_OPTIMAL, "non_existent_func")
    assert missing_entry_audit.clean is False
    assert any("ERR_ENTRYPOINT_MISSING" in v for v in missing_entry_audit.violations)

    # 6. Cyclomatic complexity limit breach
    high_comp_audit = audit_candidate_ast(CODE_HIGH_COMPLEXITY, "has_nearby_duplicate", max_complexity=8)
    assert high_comp_audit.clean is False
    assert high_comp_audit.cyclomatic_complexity > 8
    assert any("ERR_CYCLOMATIC_COMPLEXITY_EXCEEDED" in v for v in high_comp_audit.violations)

    # 7. Disallowed AST node on specific line
    code_global = "def has_nearby_duplicate(nums, k):\n    global x\n    return False\n"
    global_audit = audit_candidate_ast(code_global, "has_nearby_duplicate")
    assert global_audit.clean is False
    assert any("ERR_DISALLOWED_AST_NODE: Global at line 2" in v for v in global_audit.violations)

    # 8. Custom disallowed node
    code_custom = "def has_nearby_duplicate(nums, k):\n    return [x for x in nums]\n"
    custom_audit = audit_candidate_ast(
        code_custom,
        "has_nearby_duplicate",
        disallowed_nodes={"ListComp"},
    )
    assert custom_audit.clean is False
    assert any("ERR_DISALLOWED_AST_NODE: ListComp" in v for v in custom_audit.violations)


def test_1b_calculate_cyclomatic_complexity_constructs() -> None:
    code = """
def complex_fn(a, b, c):
    if a > 0:
        pass
    for i in range(10):
        pass
    while b > 0:
        pass
    try:
        pass
    except ValueError:
        pass
    with open("x") as f:
        pass
    assert c > 0
    res = 1 if a else 2
    cond = a and b and c
    return res
"""
    tree = ast.parse(code)
    fn_node = tree.body[0]
    complexity = calculate_cyclomatic_complexity(fn_node)
    # 1 (base) + 1 (if) + 1 (for) + 1 (while) + 1 (except) + 1 (with) + 1 (assert) + 1 (ifexp) + 2 (boolop: 3 values - 1) = 10
    assert complexity == 10


# -----------------------------------------------------------------------------
# Test 2: Functional Correctness Oracle
# -----------------------------------------------------------------------------
def test_2_functional_correctness_oracle() -> None:
    # 1. Optimal code achieves 10000 bps
    func_optimal = execute_isolated_entrypoint(CODE_CANDIDATE_OPTIMAL, "has_nearby_duplicate")
    res_opt = evaluate_candidate_correctness(func_optimal, SAMPLE_TEST_CASES)
    assert res_opt.passed_count == 4
    assert res_opt.total_count == 4
    assert res_opt.pass_rate_bps == 10000
    assert len(res_opt.failures) == 0

    # 2. Stub code fails 2 of 4 test cases (only returns False)
    func_stub = execute_isolated_entrypoint(CODE_CANDIDATE_STUB, "has_nearby_duplicate")
    res_stub = evaluate_candidate_correctness(func_stub, SAMPLE_TEST_CASES)
    assert res_stub.passed_count == 2
    assert res_stub.total_count == 4
    assert res_stub.pass_rate_bps == 5000
    assert len(res_stub.failures) == 2

    # 3. Code raising runtime exception
    code_raising = "def faulty(a, k): raise RuntimeError('boom')"
    func_raising = execute_isolated_entrypoint(code_raising, "faulty")
    res_raising = evaluate_candidate_correctness(func_raising, [(([1], 1), True)])
    assert res_raising.passed_count == 0
    assert res_raising.pass_rate_bps == 0
    assert any("raised exception: RuntimeError" in f for f in res_raising.failures)

    # 4. Empty test cases guard
    res_empty = evaluate_candidate_correctness(func_optimal, [])
    assert res_empty.pass_rate_bps == 0
    assert res_empty.failures == ["ERR_NO_TEST_CASES_SPECIFIED"]


# -----------------------------------------------------------------------------
# Test 3: Asymptotic Scaling Probe & Quadratic Rejection
# -----------------------------------------------------------------------------
def test_3_asymptotic_scaling_probe_and_quadratic_rejection(
    sample_spec: CandidateSpecification,
) -> None:
    referee = InverseLifecycleReferee()
    assert isinstance(referee.public_key, Ed25519PublicKey)
    assert referee.public_key.public_bytes_raw().hex() == referee.public_key_hex()

    # Candidate A: Constant Stub -> Rejected by correctness
    eval_stub = referee.evaluate_candidate(
        spec=sample_spec,
        candidate_id="cand_stub",
        model_name="model_stub",
        source_code=CODE_CANDIDATE_STUB,
    )
    assert eval_stub.disposition == EvaluationDisposition.REJECTED_CORRECTNESS_FAILURE
    assert eval_stub.correctness.pass_rate_bps < 10000
    assert eval_stub.pareto_rank > 100

    # Candidate B: Naive O(N^2) Nested Loop -> Rejected by scaling ratio
    eval_quad = referee.evaluate_candidate(
        spec=sample_spec,
        candidate_id="cand_quadratic",
        model_name="model_quadratic",
        source_code=CODE_CANDIDATE_QUADRATIC,
    )
    assert eval_quad.correctness.pass_rate_bps == 10000  # Passed functional tests
    assert eval_quad.disposition == EvaluationDisposition.REJECTED_ASYMPTOTIC_SCALING
    assert eval_quad.scaling.acceptable is False
    assert eval_quad.scaling.complexity_class == AsymptoticComplexityClass.O_N_SQUARED_OR_WORSE
    # Ratio should be far above 25.0x (250,000 bps)
    assert eval_quad.scaling.scaling_ratio_bps > 250000
    assert eval_quad.pareto_rank > 100

    # Candidate C: Optimal O(N) Hash Set -> Accepted
    eval_opt = referee.evaluate_candidate(
        spec=sample_spec,
        candidate_id="cand_optimal",
        model_name="model_optimal",
        source_code=CODE_CANDIDATE_OPTIMAL,
    )
    assert eval_opt.correctness.pass_rate_bps == 10000
    assert eval_opt.disposition == EvaluationDisposition.ACCEPTED
    assert eval_opt.scaling.acceptable is True
    assert eval_opt.pareto_rank == 1
    assert eval_opt.scaling.complexity_class in (
        AsymptoticComplexityClass.O_N,
        AsymptoticComplexityClass.O_1,
    )
    assert eval_opt.scaling.scaling_ratio_bps <= sample_spec.max_scaling_ratio_bps
    # Assert exact arithmetic relationship
    expected_ratio = (eval_opt.scaling.t_large_nanos * 10000) // eval_opt.scaling.t_small_nanos
    assert eval_opt.scaling.scaling_ratio_bps == expected_ratio


def test_3b_evaluate_asymptotic_scaling_direct() -> None:
    # Direct test on an O(1) function
    def constant_fn(*args):
        return 42

    def gen(n: int) -> Tuple[int]:
        return (n,)

    scaling_c = evaluate_asymptotic_scaling(constant_fn, gen, n_small=100, n_large=1000)
    assert scaling_c.acceptable is True
    assert scaling_c.n_small == 100
    assert scaling_c.n_large == 1000
    assert scaling_c.t_small_nanos >= 1
    assert scaling_c.t_large_nanos >= 1
    assert scaling_c.scaling_ratio_bps == (scaling_c.t_large_nanos * 10000) // scaling_c.t_small_nanos

    import time as _time

    orig_ns = _time.perf_counter_ns
    _time.perf_counter_ns = lambda: 5000  # type: ignore[assignment]
    try:
        scaling_zero = evaluate_asymptotic_scaling(constant_fn, gen, n_small=10, n_large=100)
    finally:
        _time.perf_counter_ns = orig_ns  # type: ignore[assignment]
    assert scaling_zero.t_small_nanos == 1
    assert scaling_zero.t_large_nanos == 1


# -----------------------------------------------------------------------------
# Test 4: Pareto Tournament & Ed25519 Receipt Issuance
# -----------------------------------------------------------------------------
def test_4_pareto_tournament_and_receipt_issuance(
    sample_spec: CandidateSpecification,
) -> None:
    custom_key = Ed25519PrivateKey.generate()
    referee = InverseLifecycleReferee(signing_key=custom_key)

    candidates = {
        "cand_stub": ("model_alpha", CODE_CANDIDATE_STUB),
        "cand_quadratic": ("model_beta", CODE_CANDIDATE_QUADRATIC),
        "cand_optimal": ("model_gamma", CODE_CANDIDATE_OPTIMAL),
    }

    winner_id, receipt = referee.referee_tournament(sample_spec, candidates)

    assert winner_id == "cand_optimal"
    assert receipt.winner_candidate_id == "cand_optimal"
    assert receipt.candidate_count == 3
    assert receipt.problem_id == sample_spec.problem_id
    assert receipt.timestamp_epoch > 0
    assert receipt.signer_public_key_hex == referee.public_key_hex()
    assert len(receipt.receipt_caid) == 71  # "sha256:" + 64 hex characters

    # Verify receipt signature cryptographically
    verified = InverseLifecycleReferee.verify_receipt(receipt)
    assert verified is True

    # Verify with explicit public key
    verified_explicit = InverseLifecycleReferee.verify_receipt(receipt, referee.public_key)
    assert verified_explicit is True


# -----------------------------------------------------------------------------
# Test 5: Falsification & Receipt Tamper Detection
# -----------------------------------------------------------------------------
def test_5_falsification_and_receipt_tamper_detection(
    sample_spec: CandidateSpecification,
) -> None:
    referee = InverseLifecycleReferee()

    candidates = {
        "cand_optimal": ("model_gamma", CODE_CANDIDATE_OPTIMAL),
    }

    winner_id, receipt = referee.referee_tournament(sample_spec, candidates)
    assert winner_id == "cand_optimal"
    assert InverseLifecycleReferee.verify_receipt(receipt) is True

    # Tamper 1: Modify winner_candidate_id
    tampered_winner = RefereeReceipt(
        receipt_caid=receipt.receipt_caid,
        problem_id=receipt.problem_id,
        winner_candidate_id="cand_hacked",
        candidate_count=receipt.candidate_count,
        timestamp_epoch=receipt.timestamp_epoch,
        evaluations=receipt.evaluations,
        signer_public_key_hex=receipt.signer_public_key_hex,
        signature_hex=receipt.signature_hex,
    )
    assert InverseLifecycleReferee.verify_receipt(tampered_winner) is False

    # Tamper 2: Corrupted signature
    bad_sig = "00" * 64
    tampered_sig = RefereeReceipt(
        receipt_caid=receipt.receipt_caid,
        problem_id=receipt.problem_id,
        winner_candidate_id=receipt.winner_candidate_id,
        candidate_count=receipt.candidate_count,
        timestamp_epoch=receipt.timestamp_epoch,
        evaluations=receipt.evaluations,
        signer_public_key_hex=receipt.signer_public_key_hex,
        signature_hex=bad_sig,
    )
    assert InverseLifecycleReferee.verify_receipt(tampered_sig) is False

    # Tamper 3: Wrong public key
    foreign_key = Ed25519PrivateKey.generate().public_key()
    assert InverseLifecycleReferee.verify_receipt(receipt, expected_pub_key=foreign_key) is False

    # Tournament with zero accepted candidates
    bad_candidates = {
        "cand_stub": ("model_alpha", CODE_CANDIDATE_STUB),
    }
    no_winner, no_winner_receipt = referee.referee_tournament(sample_spec, bad_candidates)
    assert no_winner is None
    assert no_winner_receipt.winner_candidate_id is None
    assert InverseLifecycleReferee.verify_receipt(no_winner_receipt) is True


# -----------------------------------------------------------------------------
# Test 6: Canonical JSON Serialization & Error Handling
# -----------------------------------------------------------------------------
def test_6_canonical_json_and_error_handling(sample_spec: CandidateSpecification) -> None:
    # 1. Non-finite float rejection
    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"val": float("nan")})

    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"val": float("inf")})

    # 2. Non-string dict key rejection
    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
        canonical_json_v1({123: "value"})

    # 3. Callable not found during execution
    with pytest.raises(ValueError, match="ERR_CALLABLE_NOT_FOUND"):
        execute_isolated_entrypoint("def other(): pass", "expected_fn")

    # 4. Evaluation of syntax failure in referee
    referee = InverseLifecycleReferee()
    eval_syntax_fail = referee.evaluate_candidate(
        spec=sample_spec,
        candidate_id="cand_broken",
        model_name="model_broken",
        source_code="def faulty(:",
    )
    assert eval_syntax_fail.disposition == EvaluationDisposition.REJECTED_SYNTAX_ERROR

    # 5. Evaluation of AST purity failure in referee
    eval_purity_fail = referee.evaluate_candidate(
        spec=sample_spec,
        candidate_id="cand_eval",
        model_name="model_eval",
        source_code=CODE_DYNAMIC_EXEC,
    )
    assert eval_purity_fail.disposition == EvaluationDisposition.REJECTED_AST_PURITY

    # 6. Evaluation of complexity breach in referee
    eval_comp_fail = referee.evaluate_candidate(
        spec=sample_spec,
        candidate_id="cand_comp",
        model_name="model_comp",
        source_code=CODE_HIGH_COMPLEXITY,
    )
    assert eval_comp_fail.disposition == EvaluationDisposition.REJECTED_COMPLEXITY_BREACH

    # 7. Evaluation of instantiation failure (valid syntax, top-level execution error)
    code_top_level_raise = "def has_nearby_duplicate(nums, k):\n    return False\nraise RuntimeError('init failure')\n"
    eval_inst_fail = referee.evaluate_candidate(
        spec=sample_spec,
        candidate_id="cand_init_error",
        model_name="model_init_error",
        source_code=code_top_level_raise,
    )
    assert eval_inst_fail.disposition == EvaluationDisposition.REJECTED_SYNTAX_ERROR
    assert eval_inst_fail.scaling.t_small_nanos == 0
    assert eval_inst_fail.scaling.t_large_nanos == 0
    assert eval_inst_fail.scaling.scaling_ratio_bps == 0
    assert eval_inst_fail.pareto_rank == 9 * 111


# -----------------------------------------------------------------------------
# Test 7: Epistemic Linguistic Compliance (Zero Banned Words)
# -----------------------------------------------------------------------------
def test_7_epistemic_linguistic_compliance() -> None:
    banned_prefixes = [
        "guaran" + "tee",
        "proven univer" + "sally",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
    ]

    files_to_check = [
        Path("src/inverse_lifecycle_referee.py"),
        Path("tests/test_inverse_lifecycle_referee.py"),
    ]

    for file_path in files_to_check:
        assert file_path.exists(), f"File {file_path} must exist"
        content = file_path.read_text(encoding="utf-8")
        for banned in banned_prefixes:
            match = re.search(r"\b" + re.escape(banned), content, re.IGNORECASE)
            assert match is None, (
                f"Epistemic boundary violation: found banned term '{banned}' "
                f"in {file_path}"
            )
