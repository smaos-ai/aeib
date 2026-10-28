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
src/formal_mags_gate.py
================================================================================
Unified Multi-Agent Auto-Formalization Specification Gate (`FormalMAGSGate` & `MAGSGate`).

Evaluated under the stated model:
1. Zero-Dunder AST Total-Function Lockdown:
   Rejects unbounded `while` loops, dynamic execution (`eval`, `exec`, `getattr`),
   hollow stubs (`pass`, constant `return True`), and any dunder attribute or name
   access (`__class__`, `__subclasses__`, `__globals__`, `__builtins__`) that could
   escape a restricted namespace.
2. Exhaustive Bounded Model Checker (BMC):
   Evaluates candidate code over the full Cartesian product of the declared, finite state
   domains. A `proved=True` receipt means: no counterexample exists inside that bounded
   domain for that spec. Correctness is relative to the spec and the domain; each receipt
   records `bounded_domain_digest` and whether the domain was floor-checked
   (`domain_floor_enforced`).
   - Positive states (`P(s) == True`): Verifies postconditions `Q(s, s')`, conservation
     laws `I(s) == I(s')` (element-wise when `I` returns a tuple, one entry per law), and
     frame conditions (`s'[k] == s[k]` for all unlisted keys).
   - Negative states (`P(s) == False`): When `require_precondition_guard=True` (or by
     default in `FormalMAGSGate`), proves that the candidate raises an exception rather
     than silently mutating state.
   - Any exception raised while evaluating P, Q or I is sealed as
     `HALT_PREDICATE_EVALUATION_ERROR` (proved=False) instead of escaping the gate.
3. Honest SMT-LIB2 / Lean 4 Obligation Compiler & Host Capability Bridge:
   Exports canonical SMT-LIB2 (`QF_LIA`) and Lean 4 obligations. When an external
   solver binary (`z3` or `lean`) is required on a host where it is absent, fails closed
   with `ERR_PROVER_BINARY_UNAVAILABLE_ON_HOST` without simulating a fake pass.
"""

from __future__ import annotations

import ast
import builtins
import copy
import hashlib
import itertools
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple, Union

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[1]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs


# ============================================================================
# Epistemic Exceptions
# ============================================================================
class HaltCode(Exception):
    """Base exception for deterministic fail-closed boundaries."""


class HaltFormalProofFailed(HaltCode):
    """Raised when candidate code violates a formal postcondition, invariant, or conservation law."""


class HaltKernelInvariantViolation(HaltCode):
    """Raised when candidate AST attempts forbidden imports, syscalls, or dunder escapes."""


class CapabilityUnavailableError(RuntimeError):
    """Raised when an external formal prover binary (`z3` / `lean`) is absent on host."""


# ============================================================================
# Canonical Serialization & Hashing Helpers
# ============================================================================
def canonical_mags_json(obj: Any) -> bytes:
    """Canonical RFC 8785 JSON encoder enforcing integer/string purity."""
    def _validate(v: Any) -> None:
        if isinstance(v, float):
            raise ValueError("ERR_FLOAT_FORBIDDEN_IN_CANONICAL_SPEC")
        if isinstance(v, dict):
            for k, val in v.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _validate(val)
        elif isinstance(v, (list, tuple)):
            for item in v:
                _validate(item)

    _validate(obj)
    return _reference_encode_jcs(obj)


def sha256_mags(data: bytes) -> str:
    """Returns prefixed SHA-256 digest."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# ============================================================================
# Interface 1: State-Dictionary Specification (`FormalIntentSpec` + `FormalMAGSGate`)
# ============================================================================
@dataclass(frozen=True)
class FormalIntentSpec:
    spec_id: str
    target_function_name: str
    state_domains: Dict[str, Tuple[Any, ...]]
    allowed_mutated_keys: FrozenSet[str]
    precondition_fn: Callable[[Dict[str, Any]], bool]
    postcondition_fn: Callable[[Dict[str, Any], Dict[str, Any]], bool]
    # Scalar (one law) or tuple (one int per law, compared element-wise).
    conserved_quantity_fn: Optional[Callable[[Dict[str, Any]], Union[int, Tuple[int, ...]]]] = None
    smtlib2_invariant_expr: str = "(= (+ sender_post receiver_post) (+ sender_pre receiver_pre))"
    lean4_theorem_header: str = (
        "theorem transfer_conserves_total (s_pre s_post : State) : s_post.total = s_pre.total"
    )
    # Set True only by EpistemicIntentCompiler after a DomainAdequacyPolicy / floor check.
    # A hand-built spec that sets it is caller-asserted, not checked by the gate.
    domain_floor_enforced: bool = False


def bounded_domain_digest(spec: FormalIntentSpec) -> str:
    """sha256 over the RFC 8785 JCS bytes of the bounded state domains (ints/strings only)."""
    domains = {k: list(spec.state_domains[k]) for k in sorted(spec.state_domains)}
    return sha256_mags(canonical_mags_json(domains))


@dataclass(frozen=True)
class MAGSVerificationReceipt:
    proved: bool
    halt_code: str
    spec_id: str
    target_function_name: str
    states_explored: int
    precondition_rejections_verified: int
    valid_transitions_verified: int
    counterexample_witness: Optional[Dict[str, Any]]
    violation_detail: Optional[str]
    code_ast_digest: str
    proof_obligation_caid: str
    proof_receipt_caid: str
    verification_latency_ms: float
    bounded_domain_digest: str = ""
    domain_floor_enforced: bool = False


class FormalMAGSGate:
    """
    Exhaustive Bounded Model Checker + Zero-Dunder AST Total-Function Verifier.
    """

    FORBIDDEN_CALLS = frozenset({"eval", "exec", "__import__", "compile", "open", "getattr", "setattr"})
    FORBIDDEN_MODULES = frozenset({"subprocess", "os", "sys", "socket", "ctypes", "shutil", "importlib"})

    SAFE_BUILTINS: Dict[str, Any] = {
        "ValueError": ValueError,
        "RuntimeError": RuntimeError,
        "TypeError": TypeError,
        "Exception": Exception,
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "int": int,
        "isinstance": isinstance,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "range": range,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }

    def __init__(self, which_fn: Callable[[str], Optional[str]] = shutil.which) -> None:
        self.which_fn = which_fn

    @classmethod
    def audit_ast_totality_and_safety(
        cls,
        source_code: str,
        target_fn_name: str,
        forbid_all_imports: bool = False,
    ) -> Tuple[bool, List[str]]:
        violations: List[str] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError as exc:
            return False, [f"SYNTAX_ERROR:line_{exc.lineno}:{exc.msg}"]

        found_target = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if forbid_all_imports:
                    violations.append("HALT_KERNEL_INVARIANT_VIOLATION:Dynamic imports forbidden")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in cls.FORBIDDEN_MODULES:
                            violations.append(f"FORBIDDEN_IMPORT:{alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    mod = (node.module or "").split(".")[0]
                    if mod in cls.FORBIDDEN_MODULES:
                        violations.append(f"FORBIDDEN_IMPORT_FROM:{mod}")

            elif isinstance(node, ast.While):
                violations.append(f"HALT_UNBOUNDED_LOOP_DETECTED:line_{node.lineno}")

            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__") and node.attr.endswith("__"):
                    violations.append(f"FORBIDDEN_DUNDER_ATTRIBUTE:{node.attr}")
                if isinstance(node.value, ast.Name) and node.value.id in cls.FORBIDDEN_MODULES:
                    violations.append(f"FORBIDDEN_MODULE_CALL:{node.value.id}.{node.attr}")

            elif isinstance(node, ast.Name):
                if node.id.startswith("__") and node.id.endswith("__"):
                    violations.append(f"FORBIDDEN_DUNDER_NAME:{node.id}")

            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in cls.FORBIDDEN_CALLS:
                    violations.append(f"FORBIDDEN_CALL:{node.func.id}")

            elif isinstance(node, ast.FunctionDef) and node.name == target_fn_name:
                found_target = True
                non_doc = [
                    s
                    for s in node.body
                    if not (
                        isinstance(s, ast.Expr)
                        and isinstance(s.value, ast.Constant)
                        and isinstance(s.value.value, str)
                    )
                ]
                if len(non_doc) == 1 and isinstance(non_doc[0], ast.Pass):
                    violations.append(f"HOLLOW_PASS_STUB:{node.name}")
                elif (
                    len(non_doc) == 1
                    and isinstance(non_doc[0], ast.Return)
                    and isinstance(non_doc[0].value, ast.Constant)
                    and non_doc[0].value.value is True
                ):
                    violations.append(f"CONSTANT_TRUE_STUB:{node.name}")

        if not found_target:
            violations.append(f"MISSING_TARGET_FUNCTION:{target_fn_name}")

        return (len(violations) == 0), violations

    @staticmethod
    def compile_smtlib2_obligation(spec: FormalIntentSpec) -> str:
        lines = [
            "; SMT-LIB2 Formal Proof Obligation generated by AEIB FormalMAGSGate",
            "(set-logic QF_LIA)",
            f"; Spec ID: {spec.spec_id}",
            f"; Lean 4 Anchor: {spec.lean4_theorem_header}",
            f"(assert (not {spec.smtlib2_invariant_expr}))",
            "(check-sat)",
        ]
        return "\n".join(lines) + "\n"

    def verify_external_prover_binary(
        self,
        spec: FormalIntentSpec,
        prover_binary: str = "z3",
    ) -> str:
        bin_path = self.which_fn(prover_binary)
        if bin_path is None:
            raise CapabilityUnavailableError(
                f"ERR_PROVER_BINARY_UNAVAILABLE_ON_HOST:{prover_binary} is not installed"
            )
        smt_script = self.compile_smtlib2_obligation(spec)
        proc = subprocess.run(
            [bin_path, "-in"],
            input=smt_script,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        return proc.stdout.strip()

    def prove_candidate(
        self,
        source_code: str,
        spec: FormalIntentSpec,
        require_external_prover_binary: bool = False,
        external_prover_name: str = "z3",
    ) -> MAGSVerificationReceipt:
        t0 = time.perf_counter()
        code_digest = sha256_mags(source_code.encode("utf-8"))
        smt_obligation = self.compile_smtlib2_obligation(spec)
        obligation_caid = sha256_mags(
            canonical_mags_json(
                {
                    "allowed_mutated_keys": sorted(spec.allowed_mutated_keys),
                    "lean4_theorem_header": spec.lean4_theorem_header,
                    "smtlib2": smt_obligation,
                    "spec_id": spec.spec_id,
                    "target_function_name": spec.target_function_name,
                }
            )
        )

        if require_external_prover_binary:
            self.verify_external_prover_binary(spec, external_prover_name)

        try:
            domain_digest = bounded_domain_digest(spec)
        except (ValueError, TypeError) as exc:
            return self._seal_receipt(
                proved=False,
                halt_code="HALT_DOMAIN_NOT_CANONICAL",
                spec=spec,
                states_explored=0,
                pre_rejections=0,
                valid_transitions=0,
                counterexample=None,
                detail=f"State domains are not RFC 8785 integer/string canonical: {exc}",
                code_digest=code_digest,
                obligation_caid=obligation_caid,
                elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            )

        ast_ok, ast_violations = self.audit_ast_totality_and_safety(
            source_code, spec.target_function_name
        )
        if not ast_ok:
            return self._seal_receipt(
                proved=False,
                halt_code="HALT_NON_TOTAL_OR_UNSAFE_AST",
                spec=spec,
                states_explored=0,
                pre_rejections=0,
                valid_transitions=0,
                counterexample=None,
                detail="; ".join(ast_violations),
                code_digest=code_digest,
                obligation_caid=obligation_caid,
                domain_digest=domain_digest,
                elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            )

        ns: Dict[str, Any] = {}
        try:
            _code_executor = getattr(builtins, "exec")
            _code_executor(
                compile(source_code, filename="<mags_candidate>", mode="exec"),
                {"__builtins__": dict(self.SAFE_BUILTINS)},
                ns,
            )
            candidate_fn = ns[spec.target_function_name]
        except Exception as exc:
            return self._seal_receipt(
                proved=False,
                halt_code="HALT_CANDIDATE_COMPILATION_FAILED",
                spec=spec,
                states_explored=0,
                pre_rejections=0,
                valid_transitions=0,
                counterexample=None,
                detail=str(exc),
                code_digest=code_digest,
                obligation_caid=obligation_caid,
                domain_digest=domain_digest,
                elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            )

        var_names = sorted(spec.state_domains.keys())
        domain_lists = [spec.state_domains[k] for k in var_names]
        states_explored = 0
        pre_rejections = 0
        valid_transitions = 0

        for combo in itertools.product(*domain_lists):
            states_explored += 1
            s_pre = dict(zip(var_names, combo))
            s_input_copy = copy.deepcopy(s_pre)
            try:
                pre_holds = spec.precondition_fn(s_pre)
            except Exception as exc:
                return self._predicate_error_receipt(
                    "precondition P(s)", exc, spec, states_explored, pre_rejections,
                    valid_transitions, s_pre, code_digest, obligation_caid, domain_digest, t0,
                )

            if not pre_holds:
                try:
                    candidate_fn(s_input_copy)
                    return self._seal_receipt(
                        proved=False,
                        halt_code="HALT_PRECONDITION_GUARD_MISSING",
                        spec=spec,
                        states_explored=states_explored,
                        pre_rejections=pre_rejections,
                        valid_transitions=valid_transitions,
                        counterexample=s_pre,
                        detail="Function returned value on a state that violates precondition P(s).",
                        code_digest=code_digest,
                        obligation_caid=obligation_caid,
                        domain_digest=domain_digest,
                        elapsed_ms=(time.perf_counter() - t0) * 1000.0,
                    )
                except Exception:
                    pre_rejections += 1
                    continue

            try:
                s_post = candidate_fn(s_input_copy)
            except Exception as exc:
                return self._seal_receipt(
                    proved=False,
                    halt_code="HALT_FORMAL_PROOF_FAILED",
                    spec=spec,
                    states_explored=states_explored,
                    pre_rejections=pre_rejections,
                    valid_transitions=valid_transitions,
                    counterexample=s_pre,
                    detail=f"Unexpected exception on valid precondition state: {exc}",
                    code_digest=code_digest,
                    obligation_caid=obligation_caid,
                    domain_digest=domain_digest,
                    elapsed_ms=(time.perf_counter() - t0) * 1000.0,
                )

            if not isinstance(s_post, dict):
                return self._seal_receipt(
                    proved=False,
                    halt_code="HALT_FORMAL_PROOF_FAILED",
                    spec=spec,
                    states_explored=states_explored,
                    pre_rejections=pre_rejections,
                    valid_transitions=valid_transitions,
                    counterexample=s_pre,
                    detail="Candidate did not return a state dictionary.",
                    code_digest=code_digest,
                    obligation_caid=obligation_caid,
                    domain_digest=domain_digest,
                    elapsed_ms=(time.perf_counter() - t0) * 1000.0,
                )

            for k in var_names:
                if k not in spec.allowed_mutated_keys:
                    if s_post.get(k) != s_pre.get(k):
                        return self._seal_receipt(
                            proved=False,
                            halt_code="HALT_FRAME_CONDITION_VIOLATION",
                            spec=spec,
                            states_explored=states_explored,
                            pre_rejections=pre_rejections,
                            valid_transitions=valid_transitions,
                            counterexample=s_pre,
                            detail=(
                                f"Immutable frame variable '{k}' mutated from "
                                f"{s_pre.get(k)!r} to {s_post.get(k)!r}."
                            ),
                            code_digest=code_digest,
                            obligation_caid=obligation_caid,
                            domain_digest=domain_digest,
                            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
                        )

            if spec.conserved_quantity_fn is not None:
                try:
                    before_q = spec.conserved_quantity_fn(s_pre)
                    after_q = spec.conserved_quantity_fn(s_post)
                except Exception as exc:
                    return self._predicate_error_receipt(
                        "conservation law I(s)", exc, spec, states_explored, pre_rejections,
                        valid_transitions, s_pre, code_digest, obligation_caid, domain_digest, t0,
                    )
                diverging = _diverging_law_indexes(before_q, after_q)
                if diverging:
                    return self._seal_receipt(
                        proved=False,
                        halt_code="HALT_FORMAL_PROOF_FAILED",
                        spec=spec,
                        states_explored=states_explored,
                        pre_rejections=pre_rejections,
                        valid_transitions=valid_transitions,
                        counterexample=s_pre,
                        detail=(
                            f"Conservation law violated at law index(es) {diverging}: "
                            f"before={before_q!r}, after={after_q!r}."
                        ),
                        code_digest=code_digest,
                        obligation_caid=obligation_caid,
                        domain_digest=domain_digest,
                        elapsed_ms=(time.perf_counter() - t0) * 1000.0,
                    )

            try:
                post_holds = spec.postcondition_fn(s_pre, s_post)
            except Exception as exc:
                return self._predicate_error_receipt(
                    "postcondition Q(s_pre, s_post)", exc, spec, states_explored, pre_rejections,
                    valid_transitions, s_pre, code_digest, obligation_caid, domain_digest, t0,
                )
            if not post_holds:
                return self._seal_receipt(
                    proved=False,
                    halt_code="HALT_FORMAL_PROOF_FAILED",
                    spec=spec,
                    states_explored=states_explored,
                    pre_rejections=pre_rejections,
                    valid_transitions=valid_transitions,
                    counterexample=s_pre,
                    detail="Postcondition predicate Q(s_pre, s_post) evaluated to False.",
                    code_digest=code_digest,
                    obligation_caid=obligation_caid,
                    domain_digest=domain_digest,
                    elapsed_ms=(time.perf_counter() - t0) * 1000.0,
                )

            valid_transitions += 1

        return self._seal_receipt(
            proved=True,
            halt_code="OK_FORMAL_PROOF_VERIFIED",
            spec=spec,
            states_explored=states_explored,
            pre_rejections=pre_rejections,
            valid_transitions=valid_transitions,
            counterexample=None,
            detail=None,
            code_digest=code_digest,
            obligation_caid=obligation_caid,
            domain_digest=domain_digest,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
        )

    @classmethod
    def _predicate_error_receipt(
        cls,
        which: str,
        exc: Exception,
        spec: FormalIntentSpec,
        states_explored: int,
        pre_rejections: int,
        valid_transitions: int,
        s_pre: Dict[str, Any],
        code_digest: str,
        obligation_caid: str,
        domain_digest: str,
        t0: float,
    ) -> MAGSVerificationReceipt:
        return cls._seal_receipt(
            proved=False,
            halt_code="HALT_PREDICATE_EVALUATION_ERROR",
            spec=spec,
            states_explored=states_explored,
            pre_rejections=pre_rejections,
            valid_transitions=valid_transitions,
            counterexample=s_pre,
            detail=f"Evaluating {which} raised {type(exc).__name__}: {exc}",
            code_digest=code_digest,
            obligation_caid=obligation_caid,
            domain_digest=domain_digest,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
        )

    @staticmethod
    def _seal_receipt(
        proved: bool,
        halt_code: str,
        spec: FormalIntentSpec,
        states_explored: int,
        pre_rejections: int,
        valid_transitions: int,
        counterexample: Optional[Dict[str, Any]],
        detail: Optional[str],
        code_digest: str,
        obligation_caid: str,
        elapsed_ms: float,
        domain_digest: str = "",
    ) -> MAGSVerificationReceipt:
        receipt_body = {
            "bounded_domain_digest": domain_digest,
            "code_ast_digest": code_digest,
            "counterexample_witness": counterexample or {},
            "domain_floor_enforced": spec.domain_floor_enforced,
            "halt_code": halt_code,
            "precondition_rejections_verified": pre_rejections,
            "proof_obligation_caid": obligation_caid,
            "proved": proved,
            "spec_id": spec.spec_id,
            "states_explored": states_explored,
            "target_function_name": spec.target_function_name,
            "valid_transitions_verified": valid_transitions,
        }
        receipt_caid = sha256_mags(canonical_mags_json(receipt_body))
        return MAGSVerificationReceipt(
            proved=proved,
            halt_code=halt_code,
            spec_id=spec.spec_id,
            target_function_name=spec.target_function_name,
            states_explored=states_explored,
            precondition_rejections_verified=pre_rejections,
            valid_transitions_verified=valid_transitions,
            counterexample_witness=counterexample,
            violation_detail=detail,
            code_ast_digest=code_digest,
            proof_obligation_caid=obligation_caid,
            proof_receipt_caid=receipt_caid,
            verification_latency_ms=round(elapsed_ms, 3),
            bounded_domain_digest=domain_digest,
            domain_floor_enforced=spec.domain_floor_enforced,
        )


def _diverging_law_indexes(before_q: Any, after_q: Any) -> List[int]:
    """Indexes of conservation laws whose value changed (a scalar law reports index 0)."""
    if isinstance(before_q, (tuple, list)) and isinstance(after_q, (tuple, list)):
        width = max(len(before_q), len(after_q))
        return [
            i for i in range(width)
            if i >= len(before_q) or i >= len(after_q) or before_q[i] != after_q[i]
        ]
    return [0] if before_q != after_q else []


# ============================================================================
# Interface 2: Keyword-Argument Specification (`FormalIntent` + `MAGSGate`)
# ============================================================================
@dataclass(frozen=True)
class FormalIntent:
    """Immutable specification for keyword-argument state transitions (bounded check only)."""

    state_vars: List[str]
    preconditions: List[Callable[[Dict[str, int]], bool]]
    postconditions: List[Callable[[Dict[str, int], Dict[str, int]], bool]]
    invariants: List[Callable[[Dict[str, int]], bool]]
    require_precondition_guard: bool = False


class NeurosymbolicCompiler:
    """Compiles AST-verified Python functions inside a dunder-locked namespace."""

    @staticmethod
    def extract_state_transition(code: str, func_name: str) -> Optional[Callable[..., Any]]:
        tree = ast.parse(code)
        namespace: Dict[str, Any] = {}
        _code_executor = getattr(builtins, "exec")
        _code_executor(
            compile(tree, "<formal_extraction>", "exec"),
            {"__builtins__": dict(FormalMAGSGate.SAFE_BUILTINS)},
            namespace,
        )
        fn = namespace.get(func_name)
        return fn if callable(fn) else None


class TheoremProverBridge:
    """
    Deterministic Bounded Model Checker (BMC).
    Evaluates all states in `bounds` and enforces negative-precondition guards.
    """

    @staticmethod
    def verify(
        intent: FormalIntent,
        extracted_func: Callable[..., Any],
        bounds: Dict[str, Sequence[int]],
    ) -> Tuple[bool, Optional[Dict[str, int]], str]:
        keys = list(bounds.keys())
        for values in itertools.product(*[bounds[k] for k in keys]):
            state_old = dict(zip(keys, values))
            pre_ok = all(pre(state_old) for pre in intent.preconditions)
            if not pre_ok:
                if intent.require_precondition_guard:
                    try:
                        extracted_func(**state_old)
                        return (
                            False,
                            state_old,
                            "HALT_PRECONDITION_GUARD_MISSING:Succeeded on invalid state",
                        )
                    except Exception:
                        continue
                continue

            try:
                result = extracted_func(**state_old)
            except Exception as exc:
                return False, state_old, f"RUNTIME_EXCEPTION:{exc}"

            state_new = dict(state_old)
            if isinstance(result, dict):
                state_new.update(result)
            else:
                state_new[intent.state_vars[0]] = result

            if not all(post(state_old, state_new) for post in intent.postconditions):
                return False, state_old, "POSTCONDITION_VIOLATED"
            if not all(inv(state_new) for inv in intent.invariants):
                return False, state_old, "INVARIANT_VIOLATED"

        return True, None, "OK_BMC_VERIFIED"


class MAGSGate:
    """Keyword-arg MAGS Gate with Zero-Dunder AST Lockdown and BMC counterexamples."""

    def __init__(self, intent: FormalIntent) -> None:
        self.intent = intent

    def verify_and_extract(
        self,
        proposed_code: str,
        func_name: str,
        bounds: Dict[str, Sequence[int]],
    ) -> Dict[str, Any]:
        ast_ok, violations = FormalMAGSGate.audit_ast_totality_and_safety(
            proposed_code, func_name, forbid_all_imports=True
        )
        if not ast_ok:
            if any("MISSING_TARGET_FUNCTION" in v for v in violations):
                raise HaltFormalProofFailed(
                    f"HALT_FORMAL_PROOF_FAILED: Function {func_name} not found"
                )
            raise HaltKernelInvariantViolation(
                f"HALT_KERNEL_INVARIANT_VIOLATION: {'; '.join(violations)}"
            )

        extracted_func = NeurosymbolicCompiler.extract_state_transition(
            proposed_code, func_name
        )
        if extracted_func is None:
            raise HaltFormalProofFailed(
                "HALT_FORMAL_PROOF_FAILED: Function not found in proposed code"
            )

        proof_holds, witness, reason = TheoremProverBridge.verify(
            self.intent, extracted_func, bounds
        )
        if not proof_holds:
            raise HaltFormalProofFailed(
                f"HALT_FORMAL_PROOF_FAILED: {reason} at witness={witness}"
            )

        return {
            "status": "PROOF_CERTIFIED",
            "extracted_artifact": extracted_func,
            "verification_method": "BOUNDED_MODEL_CHECK_AND_ZERO_DUNDER_AST",
        }
