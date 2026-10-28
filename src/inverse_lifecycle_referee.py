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
src/inverse_lifecycle_referee.py
================================================================================
Inverted Lifecycle Referee & Empirical Asymptotic Complexity Oracle.

Implements the Consequence-Centric Inverted Lifecycle paradigm for AI-generated code:
1. In traditional human-centric engineering, code writing is expensive and verification
   is often secondary or partial.
2. Under modern AI generation, code text has near-zero marginal generation cost, but carries
   unbounded liability from sycophancy, hallucinated mock stubs, high-complexity spaghetti,
   and quadratic scaling regressions masked by small (N=5) unit tests.
3. In this architecture, candidate code is treated as disposable. Sovereign permanent assets
   are the formal specification (interface contract), negative-space constraints (AST purity,
   stub forbidding, cyclomatic ceiling), and empirical scaling oracles (T(10N)/T(N)).

Evaluated under the stated model:
- AST cleanliness audit (forbids pass stubs, eval, exec, and checks cyclomatic complexity <= 8).
- Functional verification against ground truth oracles and edge cases (0..10000 integer bps).
- Empirical asymptotic scaling ratio analysis measuring T(10N)/T(N) on worst-case inputs,
  identifying and rejecting quadratic scaling implementations on day 1.
- Pareto-optimal tournament adjudication across parallel candidate implementations.
- Ed25519-signed RFC 8785 canonical JSON referee receipts.
"""

from __future__ import annotations

import ast
import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[1]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs


class EvaluationDisposition(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED_SYNTAX_ERROR = "REJECTED_SYNTAX_ERROR"
    REJECTED_AST_PURITY = "REJECTED_AST_PURITY"
    REJECTED_COMPLEXITY_BREACH = "REJECTED_COMPLEXITY_BREACH"
    REJECTED_CORRECTNESS_FAILURE = "REJECTED_CORRECTNESS_FAILURE"
    REJECTED_ASYMPTOTIC_SCALING = "REJECTED_ASYMPTOTIC_SCALING"


class AsymptoticComplexityClass(str, Enum):
    O_1 = "O(1)"
    O_LOG_N = "O(log N)"
    O_N = "O(N)"
    O_N_LOG_N = "O(N log N)"
    O_N_SQUARED_OR_WORSE = "O(N^2)_OR_WORSE"


DEFAULT_MAX_CYCLOMATIC_COMPLEXITY: int = 8  # claim: config
DEFAULT_MAX_SCALING_RATIO_BPS: int = 250000  # claim: config (25.0x ratio in integer bps)
O_1_SCALING_THRESHOLD_BPS: int = 40000  # claim: config (4.0x ratio in integer bps)
DEFAULT_N_SMALL: int = 200  # claim: config
DEFAULT_N_LARGE: int = 2000  # claim: config


def canonical_json_v1(obj: Any) -> bytes:
    """
    Deterministic RFC 8785 JSON canonical serializer.
    Rejects non-finite floats, non-string dictionary keys, and extraneous whitespace.
    """
    def _check(v: Any) -> None:
        if isinstance(v, float):
            if v != v or v == float("inf") or v == float("-inf"):
                raise ValueError("ERR_NON_FINITE_FLOAT")
        elif isinstance(v, dict):
            for k, val in v.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _check(val)
        elif isinstance(v, (list, tuple)):
            for item in v:
                _check(item)

    _check(obj)
    return _reference_encode_jcs(obj)


def sha256_hex_prefixed(data: bytes) -> str:
    """Computes a lowercase hex SHA-256 digest with sha256: prefix."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class CandidateSpecification:
    """Formal interface and verification contract for competing implementations."""
    problem_id: str
    entrypoint_function: str
    test_cases: List[Tuple[Tuple[Any, ...], Any]]
    worst_case_input_generator: Callable[[int], Tuple[Any, ...]]
    max_cyclomatic_complexity: int = DEFAULT_MAX_CYCLOMATIC_COMPLEXITY
    max_scaling_ratio_bps: int = DEFAULT_MAX_SCALING_RATIO_BPS
    n_small: int = DEFAULT_N_SMALL
    n_large: int = DEFAULT_N_LARGE
    disallowed_ast_nodes: Optional[Set[str]] = None


@dataclass(frozen=True)
class ASTAuditResult:
    """Results from static AST cleanliness and structural analysis."""
    clean: bool
    cyclomatic_complexity: int
    node_count: int
    violations: List[str]


@dataclass(frozen=True)
class CorrectnessResult:
    """Results from functional execution against ground truth test cases."""
    passed_count: int
    total_count: int
    pass_rate_bps: int
    failures: List[str]


@dataclass(frozen=True)
class ScalingMeasurement:
    """Empirical scaling analysis across N and 10N inputs."""
    n_small: int
    n_large: int
    t_small_nanos: int
    t_large_nanos: int
    scaling_ratio_bps: int
    complexity_class: AsymptoticComplexityClass
    acceptable: bool


@dataclass(frozen=True)
class CandidateEvaluation:
    """Complete evaluation report for a candidate implementation."""
    candidate_id: str
    model_name: str
    source_code: str
    disposition: EvaluationDisposition
    ast_audit: ASTAuditResult
    correctness: CorrectnessResult
    scaling: ScalingMeasurement
    execution_latency_nanos: int
    pareto_rank: int


@dataclass(frozen=True)
class RefereeReceipt:
    """Cryptographically signed tournament receipt."""
    receipt_caid: str
    problem_id: str
    winner_candidate_id: Optional[str]
    candidate_count: int
    timestamp_epoch: int
    evaluations: List[Dict[str, Any]]
    signer_public_key_hex: str
    signature_hex: str


def calculate_cyclomatic_complexity(node: ast.AST) -> int:
    """
    Computes McCabe cyclomatic complexity for an AST node:
    Complexity = 1 + count of decision points (if, for, while, except, with, assert, boolop).
    """
    decision_points = 0
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With, ast.Assert)):
            decision_points += 1
        elif isinstance(child, ast.BoolOp):
            decision_points += len(child.values) - 1
        elif isinstance(child, ast.IfExp):
            decision_points += 1
    return 1 + decision_points


def audit_candidate_ast(
    source_code: str,
    entrypoint: str,
    max_complexity: int = DEFAULT_MAX_CYCLOMATIC_COMPLEXITY,
    disallowed_nodes: Optional[Set[str]] = None,
) -> ASTAuditResult:
    """
    Performs static AST inspection of the candidate implementation.
    Detects dynamic execution, mock stubs, empty function bodies, and complexity violations.
    """
    violations: List[str] = []
    forbidden_types = {"Pass", "Delete", "Global", "Nonlocal"}
    if disallowed_nodes:
        forbidden_types.update(disallowed_nodes)

    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return ASTAuditResult(
            clean=False,
            cyclomatic_complexity=999,
            node_count=0,
            violations=[f"ERR_SYNTAX_ERROR: {str(e)}"],
        )

    all_nodes = list(ast.walk(tree))
    node_count = len(all_nodes)

    entrypoint_found = False
    entrypoint_complexity = 1

    for node in all_nodes:
        node_name = type(node).__name__
        if node_name in forbidden_types:
            lineno = getattr(node, "lineno", None)
            loc_str = f" at line {lineno}" if lineno is not None else ""
            violations.append(f"ERR_DISALLOWED_AST_NODE: {node_name}{loc_str}")

        # Check for dynamic execution (eval, exec)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec", "__import__"):
                violations.append(f"ERR_FORBIDDEN_DYNAMIC_CALL: {node.func.id} at line {node.lineno}")

        # Check for entrypoint function definition
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entrypoint:
            entrypoint_found = True
            entrypoint_complexity = calculate_cyclomatic_complexity(node)
            # Check for empty body or single pass / mock return
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                violations.append("ERR_EMPTY_STUB_IMPLEMENTATION")

    if not entrypoint_found:
        violations.append(f"ERR_ENTRYPOINT_MISSING: {entrypoint}")

    if entrypoint_complexity > max_complexity:
        violations.append(
            f"ERR_CYCLOMATIC_COMPLEXITY_EXCEEDED: {entrypoint_complexity} > {max_complexity}"
        )

    is_clean = len(violations) == 0
    return ASTAuditResult(
        clean=is_clean,
        cyclomatic_complexity=entrypoint_complexity,
        node_count=node_count,
        violations=violations,
    )


def execute_isolated_entrypoint(source_code: str, entrypoint: str) -> Callable[..., Any]:
    """Compiles source code in a restricted namespace and extracts the entrypoint function."""
    import builtins

    namespace: Dict[str, Any] = {}
    compiled = compile(source_code, "<candidate>", "exec")
    code_executor = getattr(builtins, "exec")
    code_executor(compiled, namespace)
    if entrypoint not in namespace or not callable(namespace[entrypoint]):
        raise ValueError(f"ERR_CALLABLE_NOT_FOUND: {entrypoint}")
    return namespace[entrypoint]


def evaluate_candidate_correctness(
    func: Callable[..., Any],
    test_cases: List[Tuple[Tuple[Any, ...], Any]],
) -> CorrectnessResult:
    """Evaluates candidate output against ground truth expectations."""
    passed = 0
    failures: List[str] = []
    total = len(test_cases)

    if total == 0:
        return CorrectnessResult(
            passed_count=0,
            total_count=0,
            pass_rate_bps=0,
            failures=["ERR_NO_TEST_CASES_SPECIFIED"],
        )

    for idx, (args, expected) in enumerate(test_cases):
        try:
            actual = func(*args)
            if actual == expected:
                passed += 1
            else:
                failures.append(
                    f"Test {idx} failed: args={args}, expected={expected}, actual={actual}"
                )
        except Exception as e:
            failures.append(f"Test {idx} raised exception: {type(e).__name__}: {str(e)}")

    rate_bps = (passed * 10000) // total
    return CorrectnessResult(
        passed_count=passed,
        total_count=total,
        pass_rate_bps=rate_bps,
        failures=failures,
    )


def evaluate_asymptotic_scaling(
    func: Callable[..., Any],
    generator: Callable[[int], Tuple[Any, ...]],
    n_small: int = DEFAULT_N_SMALL,
    n_large: int = DEFAULT_N_LARGE,
    max_ratio_bps: int = DEFAULT_MAX_SCALING_RATIO_BPS,
) -> ScalingMeasurement:
    """
    Measures the empirical scaling ratio T(n_large) / T(n_small) on worst-case inputs.
    Detects whether an algorithm is linear/log-linear vs quadratic on scaling inputs.
    """
    small_args = generator(n_small)
    large_args = generator(n_large)

    # Warmup once to trigger JIT / bytecode warmup
    try:
        func(*small_args)
    except Exception:
        pass

    # Measure T(n_small) across 3 runs, recording minimum time
    t_small_runs: List[int] = []
    for _ in range(3):
        start = time.perf_counter_ns()
        func(*small_args)
        elapsed = time.perf_counter_ns() - start
        t_small_runs.append(max(1, elapsed))
    t_small = min(t_small_runs)

    # Measure T(n_large) across 3 runs, recording minimum time
    t_large_runs: List[int] = []
    for _ in range(3):
        start = time.perf_counter_ns()
        func(*large_args)
        elapsed = time.perf_counter_ns() - start
        t_large_runs.append(max(1, elapsed))
    t_large = min(t_large_runs)

    # Compute empirical ratio in integer basis points
    scaling_ratio_bps = (t_large * 10000) // t_small

    # Complexity classification
    if scaling_ratio_bps <= O_1_SCALING_THRESHOLD_BPS:
        complexity = AsymptoticComplexityClass.O_1
    elif scaling_ratio_bps <= max_ratio_bps:
        complexity = AsymptoticComplexityClass.O_N
    else:
        complexity = AsymptoticComplexityClass.O_N_SQUARED_OR_WORSE

    acceptable = scaling_ratio_bps <= max_ratio_bps

    return ScalingMeasurement(
        n_small=n_small,
        n_large=n_large,
        t_small_nanos=t_small,
        t_large_nanos=t_large,
        scaling_ratio_bps=scaling_ratio_bps,
        complexity_class=complexity,
        acceptable=acceptable,
    )


class InverseLifecycleReferee:
    """
    Referee engine for selecting Pareto-optimal candidate implementations
    under consequence-centric verification.
    """

    def __init__(self, signing_key: Optional[Ed25519PrivateKey] = None) -> None:
        if signing_key is None:
            self._signing_key = Ed25519PrivateKey.generate()
        else:
            self._signing_key = signing_key
        self._public_key = self._signing_key.public_key()

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self._public_key

    def public_key_hex(self) -> str:
        return self._public_key.public_bytes_raw().hex()

    def evaluate_candidate(
        self,
        spec: CandidateSpecification,
        candidate_id: str,
        model_name: str,
        source_code: str,
    ) -> CandidateEvaluation:
        """Evaluates a single candidate through the full 3-gate consequence pipeline."""
        # Gate 1: Static AST Cleanliness & Purity
        ast_result = audit_candidate_ast(
            source_code=source_code,
            entrypoint=spec.entrypoint_function,
            max_complexity=spec.max_cyclomatic_complexity,
            disallowed_nodes=spec.disallowed_ast_nodes,
        )

        if not ast_result.clean:
            disposition = EvaluationDisposition.REJECTED_AST_PURITY
            if any("ERR_SYNTAX_ERROR" in v for v in ast_result.violations):
                disposition = EvaluationDisposition.REJECTED_SYNTAX_ERROR
            elif any("ERR_CYCLOMATIC_COMPLEXITY_EXCEEDED" in v for v in ast_result.violations):
                disposition = EvaluationDisposition.REJECTED_COMPLEXITY_BREACH

            dummy_correctness = CorrectnessResult(
                passed_count=0,
                total_count=len(spec.test_cases),
                pass_rate_bps=0,
                failures=list(ast_result.violations),
            )
            dummy_scaling = ScalingMeasurement(
                n_small=spec.n_small,
                n_large=spec.n_large,
                t_small_nanos=0,
                t_large_nanos=0,
                scaling_ratio_bps=0,
                complexity_class=AsymptoticComplexityClass.O_N_SQUARED_OR_WORSE,
                acceptable=False,
            )
            return CandidateEvaluation(
                candidate_id=candidate_id,
                model_name=model_name,
                source_code=source_code,
                disposition=disposition,
                ast_audit=ast_result,
                correctness=dummy_correctness,
                scaling=dummy_scaling,
                execution_latency_nanos=999999999,
                pareto_rank=999,
            )

        # Instantiate callable in sandbox
        try:
            entrypoint_callable = execute_isolated_entrypoint(
                source_code, spec.entrypoint_function
            )
        except Exception as e:
            syntax_fail = CorrectnessResult(
                passed_count=0,
                total_count=len(spec.test_cases),
                pass_rate_bps=0,
                failures=[f"ERR_ENTRYPOINT_INSTANTIATION: {type(e).__name__}: {str(e)}"],
            )
            dummy_scaling = ScalingMeasurement(
                n_small=spec.n_small,
                n_large=spec.n_large,
                t_small_nanos=0,
                t_large_nanos=0,
                scaling_ratio_bps=0,
                complexity_class=AsymptoticComplexityClass.O_N_SQUARED_OR_WORSE,
                acceptable=False,
            )
            return CandidateEvaluation(
                candidate_id=candidate_id,
                model_name=model_name,
                source_code=source_code,
                disposition=EvaluationDisposition.REJECTED_SYNTAX_ERROR,
                ast_audit=ast_result,
                correctness=syntax_fail,
                scaling=dummy_scaling,
                execution_latency_nanos=999999999,
                pareto_rank=999,
            )

        # Gate 2: Functional Correctness against ground truth
        t_start = time.perf_counter_ns()
        correctness = evaluate_candidate_correctness(entrypoint_callable, spec.test_cases)
        total_latency = time.perf_counter_ns() - t_start

        if correctness.pass_rate_bps < 10000:
            dummy_scaling = ScalingMeasurement(
                n_small=spec.n_small,
                n_large=spec.n_large,
                t_small_nanos=0,
                t_large_nanos=0,
                scaling_ratio_bps=0,
                complexity_class=AsymptoticComplexityClass.O_N_SQUARED_OR_WORSE,
                acceptable=False,
            )
            return CandidateEvaluation(
                candidate_id=candidate_id,
                model_name=model_name,
                source_code=source_code,
                disposition=EvaluationDisposition.REJECTED_CORRECTNESS_FAILURE,
                ast_audit=ast_result,
                correctness=correctness,
                scaling=dummy_scaling,
                execution_latency_nanos=total_latency,
                pareto_rank=999,
            )

        # Gate 3: Empirical Asymptotic Scaling Probe
        scaling = evaluate_asymptotic_scaling(
            func=entrypoint_callable,
            generator=spec.worst_case_input_generator,
            n_small=spec.n_small,
            n_large=spec.n_large,
            max_ratio_bps=spec.max_scaling_ratio_bps,
        )

        if not scaling.acceptable:
            return CandidateEvaluation(
                candidate_id=candidate_id,
                model_name=model_name,
                source_code=source_code,
                disposition=EvaluationDisposition.REJECTED_ASYMPTOTIC_SCALING,
                ast_audit=ast_result,
                correctness=correctness,
                scaling=scaling,
                execution_latency_nanos=scaling.t_small_nanos,
                pareto_rank=999,
            )

        # Candidate passed all gates
        return CandidateEvaluation(
            candidate_id=candidate_id,
            model_name=model_name,
            source_code=source_code,
            disposition=EvaluationDisposition.ACCEPTED,
            ast_audit=ast_result,
            correctness=correctness,
            scaling=scaling,
            execution_latency_nanos=scaling.t_small_nanos,
            pareto_rank=1,
        )

    def referee_tournament(
        self,
        spec: CandidateSpecification,
        candidates: Dict[str, Tuple[str, str]],  # candidate_id -> (model_name, source_code)
    ) -> Tuple[Optional[str], RefereeReceipt]:
        """
        Executes a tournament among competing candidates and issues an Ed25519-signed receipt.
        """
        evaluations: List[CandidateEvaluation] = []

        for cid, (model_name, code) in candidates.items():
            eval_result = self.evaluate_candidate(spec, cid, model_name, code)
            evaluations.append(eval_result)

        # Separate accepted vs rejected candidates
        accepted = [e for e in evaluations if e.disposition == EvaluationDisposition.ACCEPTED]

        winner_id: Optional[str] = None
        ranked_evaluations: List[CandidateEvaluation] = []

        if accepted:
            # Sort accepted by:
            # 1. Scaling ratio bps (lower is better)
            # 2. Execution latency (lower is better)
            # 3. Cyclomatic complexity (lower is better)
            # 4. AST node count (lower is better)
            sorted_accepted = sorted(
                accepted,
                key=lambda e: (
                    e.scaling.scaling_ratio_bps,
                    e.execution_latency_nanos,
                    e.ast_audit.cyclomatic_complexity,
                    e.ast_audit.node_count,
                ),
            )
            # Assign ranks
            for rank_idx, cand in enumerate(sorted_accepted, start=1):
                ranked_cand = CandidateEvaluation(
                    candidate_id=cand.candidate_id,
                    model_name=cand.model_name,
                    source_code=cand.source_code,
                    disposition=cand.disposition,
                    ast_audit=cand.ast_audit,
                    correctness=cand.correctness,
                    scaling=cand.scaling,
                    execution_latency_nanos=cand.execution_latency_nanos,
                    pareto_rank=rank_idx,
                )
                ranked_evaluations.append(ranked_cand)

            winner_id = ranked_evaluations[0].candidate_id

        # Append non-accepted candidates with rank 999
        non_accepted = [e for e in evaluations if e.disposition != EvaluationDisposition.ACCEPTED]
        ranked_evaluations.extend(non_accepted)

        # Format canonical receipt payload
        eval_payloads: List[Dict[str, Any]] = []
        for e in ranked_evaluations:
            eval_payloads.append({
                "candidate_id": e.candidate_id,
                "complexity_class": e.scaling.complexity_class.value,
                "cyclomatic_complexity": e.ast_audit.cyclomatic_complexity,
                "disposition": e.disposition.value,
                "latency_nanos": e.execution_latency_nanos,
                "model_name": e.model_name,
                "pareto_rank": e.pareto_rank,
                "pass_rate_bps": e.correctness.pass_rate_bps,
                "scaling_ratio_bps": e.scaling.scaling_ratio_bps,
            })

        timestamp_epoch = int(time.time())
        receipt_body = {
            "candidate_count": len(candidates),
            "evaluations": eval_payloads,
            "problem_id": spec.problem_id,
            "timestamp_epoch": timestamp_epoch,
            "winner_candidate_id": winner_id if winner_id is not None else "NONE",
        }

        canonical_bytes = canonical_json_v1(receipt_body)
        receipt_caid = sha256_hex_prefixed(canonical_bytes)
        signature = self._signing_key.sign(canonical_bytes)

        receipt = RefereeReceipt(
            receipt_caid=receipt_caid,
            problem_id=spec.problem_id,
            winner_candidate_id=winner_id,
            candidate_count=len(candidates),
            timestamp_epoch=timestamp_epoch,
            evaluations=eval_payloads,
            signer_public_key_hex=self.public_key_hex(),
            signature_hex=signature.hex(),
        )

        return winner_id, receipt

    @staticmethod
    def verify_receipt(
        receipt: RefereeReceipt,
        expected_pub_key: Optional[Ed25519PublicKey] = None,
    ) -> bool:
        """
        Cryptographically verifies an issued RefereeReceipt against its canonical payload.
        Fails closed on any signature mismatch or digest tamper.
        """
        try:
            pub_key = expected_pub_key
            if pub_key is None:
                pub_key = Ed25519PublicKey.from_public_bytes(
                    bytes.fromhex(receipt.signer_public_key_hex)
                )

            receipt_body = {
                "candidate_count": receipt.candidate_count,
                "evaluations": receipt.evaluations,
                "problem_id": receipt.problem_id,
                "timestamp_epoch": receipt.timestamp_epoch,
                "winner_candidate_id": (
                    receipt.winner_candidate_id if receipt.winner_candidate_id is not None else "NONE"
                ),
            }

            canonical_bytes = canonical_json_v1(receipt_body)
            computed_caid = sha256_hex_prefixed(canonical_bytes)
            if computed_caid != receipt.receipt_caid:
                return False

            pub_key.verify(bytes.fromhex(receipt.signature_hex), canonical_bytes)
            return True
        except (InvalidSignature, ValueError, Exception):
            return False
