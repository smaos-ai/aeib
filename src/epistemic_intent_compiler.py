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
src/epistemic_intent_compiler.py
================================================================================
D5 Delivery: Epistemic Intent Compiler.

Evaluated under the stated model:
Translates structured neurosymbolic LLM extractions (`IntentDraft`) into `FormalIntentSpec`
objects for the FormalMAGSGate bounded model checker, without dynamic `eval()` or `exec()`.
What the gate then checks is an exhaustive evaluation over a bounded, finite state domain
that is checked against `DEFAULT_DOMAIN_ADEQUACY_POLICY` (or a caller-supplied
`DomainAdequacyPolicy` / `signed_floor`, recorded as `domain_floor_enforced=True`) by default;
unfloored compilation requires explicit `allow_unfloored_domain=True` (recorded as
`domain_floor_enforced=False`). Correctness is relative to that spec and that domain only;
nothing outside the domain is evaluated.
Enforces:
1. Zero-Dunder & Zero-Call AST Lockdown (allow-list):
   Rejects function calls, attribute access, dynamic imports, dunder references and every
   AST node / operator outside the integer-arithmetic allow-list at compile time.
2. Integer-only spec layer:
   Constants must be `int` (bool and float rejected); true division is not offered
   (only `//` and `%`).
3. Strict Variable Scoping:
   Only declared state variables can be referenced; mutated variables must be declared.
4. Safe Recursive AST Expression Evaluation:
   Zero-division in `//` / `%` raises a coded error instead of a Python exception.
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Mapping, Optional, Set, Tuple

from src.formal_mags_gate import FormalIntentSpec


class HaltEpistemicCompilationFailed(Exception):
    """Raised when the intent extraction contains unsafe, undefined, or forbidden logic."""


class DomainAdequacyViolation(HaltEpistemicCompilationFailed):
    """
    Raised (fail closed) when a draft's state domain is narrower than the caller's
    DomainAdequacyPolicy or omits a value from the operator-supplied floor.
    """

    def __init__(self, code: str, variable: str, message: str) -> None:
        super().__init__(f"{code}: {variable}: {message}")
        self.code = code
        self.variable = variable


@dataclass(frozen=True)
class DomainAdequacyPolicy:
    """
    Caller-owned (never LLM-owned) lower bound on the bounded proof domain.
    Every declared variable must have at least `min_cardinality` distinct integer values
    and contain every value in `required_values`.
    """

    min_cardinality: int = 4
    required_values: FrozenSet[int] = frozenset({0, 1, -1, 2})

    def __post_init__(self) -> None:
        if type(self.min_cardinality) is not int or self.min_cardinality < 1:
            raise ValueError("min_cardinality must be a positive int")
        if any(type(v) is not int for v in self.required_values):
            raise ValueError("required_values must contain ints only")


DEFAULT_DOMAIN_ADEQUACY_POLICY = DomainAdequacyPolicy()


class SafeExpressionCompiler:
    """Compiles string integer-arithmetic/logic expressions into lambdas via strict AST walking."""

    ALLOWED_OPS: Dict[Any, Callable[..., Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.Not: operator.not_,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    FORBIDDEN_NODES = (
        ast.Call,
        ast.Attribute,
        ast.Import,
        ast.ImportFrom,
        ast.Lambda,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Yield,
        ast.YieldFrom,
        ast.Await,
        ast.JoinedStr,
        ast.FormattedValue,
        ast.Dict,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )

    # Structural allow-list; operator nodes are checked separately against ALLOWED_OPS.
    ALLOWED_NODES = (
        ast.Expression,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.BinOp,
        ast.UnaryOp,
        ast.Compare,
        ast.BoolOp,
        ast.And,
        ast.Or,
    )

    @classmethod
    def compile_expr(cls, expr_str: str, allowed_vars: Set[str]) -> Callable[[Dict[str, Any]], Any]:
        try:
            tree = ast.parse(expr_str, mode="eval")
        except SyntaxError as e:
            raise HaltEpistemicCompilationFailed(f"SYNTAX_ERROR: {e}")

        for node in ast.walk(tree):
            if isinstance(node, cls.FORBIDDEN_NODES):
                raise HaltEpistemicCompilationFailed(f"FORBIDDEN_AST_NODE: {type(node).__name__}")
            if isinstance(node, ast.Name):
                if node.id.startswith("__") and node.id.endswith("__"):
                    raise HaltEpistemicCompilationFailed(f"FORBIDDEN_DUNDER: {node.id}")
                if node.id not in allowed_vars:
                    raise HaltEpistemicCompilationFailed(f"UNDEFINED_VARIABLE: {node.id}")
            elif isinstance(node, ast.Constant):
                if type(node.value) is not int:
                    raise HaltEpistemicCompilationFailed(
                        f"FORBIDDEN_CONSTANT_TYPE: {type(node.value).__name__}:integer_arithmetic_only"
                    )
            elif isinstance(node, (ast.operator, ast.unaryop, ast.cmpop)):
                if type(node) not in cls.ALLOWED_OPS:
                    raise HaltEpistemicCompilationFailed(f"FORBIDDEN_OP: {type(node).__name__}")
            elif not isinstance(node, cls.ALLOWED_NODES):
                raise HaltEpistemicCompilationFailed(f"UNSUPPORTED_AST_NODE: {type(node).__name__}")

        ops = cls.ALLOWED_OPS

        # Every node reaching _eval passed the compile-time allow-list above.
        def _eval(node: Any, state_dict: Dict[str, Any]) -> Any:
            if isinstance(node, ast.Expression):
                return _eval(node.body, state_dict)
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.Name):
                return state_dict[node.id]
            if isinstance(node, ast.BinOp):
                left = _eval(node.left, state_dict)
                right = _eval(node.right, state_dict)
                if isinstance(node.op, (ast.FloorDiv, ast.Mod)) and right == 0:
                    raise HaltEpistemicCompilationFailed("ERR_ZERO_DIVISION_IN_EXPRESSION")
                return ops[type(node.op)](left, right)
            if isinstance(node, ast.Compare):
                left = _eval(node.left, state_dict)
                for op, right_node in zip(node.ops, node.comparators):
                    right = _eval(right_node, state_dict)
                    if not ops[type(op)](left, right):
                        return False
                    left = right
                return True
            if isinstance(node, ast.BoolOp):
                if isinstance(node.op, ast.And):
                    return all(_eval(v, state_dict) for v in node.values)
                return any(_eval(v, state_dict) for v in node.values)
            return ops[type(node.op)](_eval(node.operand, state_dict))

        return lambda state: _eval(tree, state)


@dataclass(frozen=True)
class IntentDraft:
    """The structured output expected from neurosymbolic intent extraction."""

    spec_id: str
    target_function_name: str
    state_domains: Dict[str, Tuple[int, ...]]
    mutated_vars: List[str]
    preconditions: List[str]
    postconditions: List[str]
    conservation_laws: List[str]


def _check_domain_adequacy(
    domains: Mapping[str, Tuple[Any, ...]],
    policy: Optional[DomainAdequacyPolicy],
    signed_floor: Optional[Mapping[str, Iterable[int]]],
) -> None:
    if policy is not None:
        for var in sorted(domains):
            values = domains[var]
            bad = [v for v in values if type(v) is not int]
            if bad:
                raise DomainAdequacyViolation("DOMAIN_NON_INTEGER_VALUE", var, f"non-int values {bad!r}")
            distinct = set(values)
            if len(distinct) < policy.min_cardinality:
                raise DomainAdequacyViolation(
                    "DOMAIN_TOO_NARROW", var,
                    f"{len(distinct)} distinct values < min_cardinality {policy.min_cardinality}",
                )
            missing = sorted(policy.required_values - distinct)
            if missing:
                raise DomainAdequacyViolation("DOMAIN_MISSING_BOUNDARY_VALUES", var, f"missing {missing}")
    if signed_floor is not None:
        for var in sorted(signed_floor):
            if var not in domains:
                raise DomainAdequacyViolation("DOMAIN_FLOOR_VARIABLE_UNDECLARED", var, "floor names an undeclared variable")
            missing_floor = sorted(set(signed_floor[var]) - set(domains[var]))
            if missing_floor:
                raise DomainAdequacyViolation("DOMAIN_MISSING_FLOOR_VALUES", var, f"missing {missing_floor}")


class EpistemicIntentCompiler:
    """
    Compiles IntentDraft into a FormalIntentSpec for exhaustive checking over a bounded,
    floor-checked (by default via DEFAULT_DOMAIN_ADEQUACY_POLICY) finite domain;
    correctness is relative to that spec and domain.
    """

    @staticmethod
    def compile(
        draft: IntentDraft,
        policy: Optional[DomainAdequacyPolicy] = DEFAULT_DOMAIN_ADEQUACY_POLICY,
        signed_floor: Optional[Mapping[str, Iterable[int]]] = None,
        *,
        allow_unfloored_domain: bool = False,
    ) -> FormalIntentSpec:
        """
        policy / signed_floor are caller-owned inputs (never taken from the LLM draft).
        `signed_floor` maps a variable to integer values its domain must contain; verifying
        any signature over that floor is the caller's responsibility before passing it in.
        By default, `DEFAULT_DOMAIN_ADEQUACY_POLICY` is enforced (`domain_floor_enforced=True`).
        Unfloored compilation requires explicit `allow_unfloored_domain=True`
        (`domain_floor_enforced=False`).
        """
        if type(allow_unfloored_domain) is not bool:
            raise ValueError("allow_unfloored_domain must be a bool")

        effective_policy = (
            None
            if (allow_unfloored_domain and policy is DEFAULT_DOMAIN_ADEQUACY_POLICY)
            else policy
        )
        if not allow_unfloored_domain and effective_policy is None and signed_floor is None:
            raise DomainAdequacyViolation(
                "DOMAIN_FLOOR_REQUIRED",
                "*",
                "policy or signed_floor required unless allow_unfloored_domain=True",
            )

        domains: Dict[str, Tuple[Any, ...]] = {k: tuple(v) for k, v in draft.state_domains.items()}
        allowed_vars = set(domains.keys())

        undeclared = sorted(set(draft.mutated_vars) - allowed_vars)
        if undeclared:
            raise HaltEpistemicCompilationFailed(f"UNDECLARED_MUTATED_VARS: {undeclared}")

        floor_enforced = effective_policy is not None or signed_floor is not None
        _check_domain_adequacy(domains, effective_policy, signed_floor)

        # 1. Compile Preconditions
        pre_fns = [SafeExpressionCompiler.compile_expr(p, allowed_vars) for p in draft.preconditions]

        def precondition_fn(s: Dict[str, Any]) -> bool:
            return all(f(s) for f in pre_fns)

        # 2. Compile Postconditions (requires pre and post state mapping)
        post_allowed_vars = {f"{v}_pre" for v in allowed_vars} | {f"{v}_post" for v in allowed_vars}
        post_fns = [SafeExpressionCompiler.compile_expr(p, post_allowed_vars) for p in draft.postconditions]

        def postcondition_fn(s_pre: Dict[str, Any], s_post: Dict[str, Any]) -> bool:
            merged = {f"{k}_pre": v for k, v in s_pre.items()}
            merged.update({f"{k}_post": v for k, v in s_post.items()})
            return all(f(merged) for f in post_fns)

        # 3. Compile Conservation Laws: one value per law, compared element-wise by the gate
        # (summing laws into one scalar would let independent laws cancel each other).
        cons_fns = [SafeExpressionCompiler.compile_expr(c, allowed_vars) for c in draft.conservation_laws]

        def conserved_quantity_fn(s: Dict[str, Any]) -> Tuple[int, ...]:
            return tuple(int(f(s)) for f in cons_fns)

        return FormalIntentSpec(
            spec_id=draft.spec_id,
            target_function_name=draft.target_function_name,
            state_domains=domains,
            allowed_mutated_keys=frozenset(draft.mutated_vars),
            precondition_fn=precondition_fn,
            postcondition_fn=postcondition_fn,
            conserved_quantity_fn=conserved_quantity_fn if cons_fns else None,
            domain_floor_enforced=floor_enforced,
        )
