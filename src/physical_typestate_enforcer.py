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
src/physical_typestate_enforcer.py
================================================================================
Scope 3: "LeHami" Physical & Financial Type-State AST Enforcer.

Enforces dimensional conservation and hardware actuator ceilings at the AST level
($0 token cost) before candidate code reaches the Python interpreter.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.eo1_unified_gate import sha256_jcs_caid
from src.jcs_canonicalizer import encode_jcs


@dataclass(frozen=True)
class PhysicalEnvelopeSpec:
    """Hardware or financial physical envelope specification."""

    unit_type: str        # e.g., "NewtonMeters", "MinorUnitUSD", "EpochSeconds", "Kelvin"
    min_value: int
    max_value: int

    def __post_init__(self) -> None:
        if not self.unit_type.strip():
            raise ValueError("unit_type must not be empty")
        if not isinstance(self.min_value, int) or not isinstance(self.max_value, int):
            raise ValueError("min_value and max_value must be integers")
        if self.min_value > self.max_value:
            raise ValueError("min_value cannot exceed max_value")


@dataclass(frozen=True)
class TypeStatePhysicsVerdict:
    """Deterministic cryptographic verdict from AST physical enforcement."""

    passed: bool
    status_code: str
    violating_symbol: str
    line_number: int
    verdict_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_number": self.line_number,
            "passed": self.passed,
            "status_code": self.status_code,
            "verdict_caid": self.verdict_caid,
            "violating_symbol": self.violating_symbol,
        }


class PhysicalTypeStateEnforcer:
    """
    Static AST pre-filter hardwiring physical and financial laws into candidate code.
    Rejects dimensional heterogeneity and hardware limit breaches at $0 token cost.
    """

    def __init__(self, envelopes: Mapping[str, PhysicalEnvelopeSpec]) -> None:
        if not envelopes:
            raise ValueError("ERR_EMPTY_PHYSICAL_ENVELOPES")
        self._envelopes: Dict[str, PhysicalEnvelopeSpec] = dict(envelopes)

    def verify_ast_physics(
        self, source_code: str, filename: str = "<candidate>"
    ) -> TypeStatePhysicsVerdict:
        """Inspects AST for physical boundary violations and dimensional clashes."""
        try:
            tree = ast.parse(source_code, filename=filename)
        except SyntaxError as exc:
            return self._mint(False, "HALT_SYNTAX_ERROR", filename, exc.lineno or 0)

        var_units: Dict[str, str] = {}

        # Pass 1: Collect variable annotations and check initial bound limits
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                var_name = node.target.id
                unit_name = self._extract_unit_name(node.annotation)
                if unit_name is not None:
                    var_units[var_name] = unit_name
                    if unit_name in self._envelopes and node.value is not None:
                        lit_val = self._extract_int_literal(node.value)
                        if lit_val is not None:
                            env = self._envelopes[unit_name]
                            if lit_val < env.min_value or lit_val > env.max_value:
                                return self._mint(
                                    False,
                                    f"HALT_PHYSICAL_LAW_VIOLATION:BOUNDS_EXCEEDED:{unit_name}={lit_val}_outside_[{env.min_value},{env.max_value}]",
                                    var_name,
                                    getattr(node, "lineno", 0),
                                )

        # Pass 2: Check re-assignments and binary expressions for dimensional consistency
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in var_units:
                        unit_name = var_units[target.id]
                        lit_val = self._extract_int_literal(node.value)
                        if lit_val is not None and unit_name in self._envelopes:
                            env = self._envelopes[unit_name]
                            if lit_val < env.min_value or lit_val > env.max_value:
                                return self._mint(
                                    False,
                                    f"HALT_PHYSICAL_LAW_VIOLATION:BOUNDS_EXCEEDED:{unit_name}={lit_val}_outside_[{env.min_value},{env.max_value}]",
                                    target.id,
                                    getattr(node, "lineno", 0),
                                )

            elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
                left_unit = self._infer_expr_unit(node.left, var_units)
                right_unit = self._infer_expr_unit(node.right, var_units)
                if left_unit is not None and right_unit is not None and left_unit != right_unit:
                    return self._mint(
                        False,
                        f"HALT_PHYSICAL_LAW_VIOLATION:DIMENSIONAL_MISMATCH:{left_unit}_vs_{right_unit}",
                        f"{left_unit}+{right_unit}",
                        getattr(node, "lineno", 0),
                    )

        return self._mint(True, "OK_PHYSICAL_TYPESTATE_VERIFIED", "ALL", 0)

    @staticmethod
    def _extract_unit_name(annotation_node: ast.AST) -> Optional[str]:
        if isinstance(annotation_node, ast.Name):
            return annotation_node.id
        return None

    @staticmethod
    def _extract_int_literal(val_node: ast.AST) -> Optional[int]:
        if isinstance(val_node, ast.Constant) and isinstance(val_node.value, int) and not isinstance(val_node.value, bool):
            return int(val_node.value)
        if (
            isinstance(val_node, ast.UnaryOp)
            and isinstance(val_node.op, ast.USub)
            and isinstance(val_node.operand, ast.Constant)
            and isinstance(val_node.operand.value, int)
        ):
            return -int(val_node.operand.value)
        return None

    @classmethod
    def _infer_expr_unit(cls, expr: ast.AST, var_units: Mapping[str, str]) -> Optional[str]:
        if isinstance(expr, ast.Name):
            return var_units.get(expr.id)
        return None

    @staticmethod
    def _mint(
        passed: bool, status_code: str, symbol: str, line_no: int
    ) -> TypeStatePhysicsVerdict:
        payload = {
            "line_number": line_no,
            "passed": passed,
            "status_code": status_code,
            "violating_symbol": symbol,
        }
        return TypeStatePhysicsVerdict(
            passed=passed,
            status_code=status_code,
            violating_symbol=symbol,
            line_number=line_no,
            verdict_caid=sha256_jcs_caid(payload),
        )
