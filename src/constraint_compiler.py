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
src/constraint_compiler.py
================================================================================
Constraint-as-Code Compiler (RVP - Regeneration & Verification Protocol).

Status: INTERNAL PREVIEW COMMISSIONED.
Evaluated under the stated model:
  - Compiles design system tokens, AST rules, and quality constraints into a deterministic
    verification harness for AI-generated UI components.
  - Operationalizes shared specifications and constraint enforcement rather than shared packages.
  - Zero floats RFC 8785 single-source JSON Canonicalization Scheme (JCS).
"""

from __future__ import annotations

import ast
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from src.jcs_canonicalizer import encode_jcs


def sha256_jcs_caid(payload: Any) -> str:
    """Compute RFC 8785 SHA-256 CAID for bytes, string, or JSON-serializable structure."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclass(frozen=True)
class ComponentConstraintSpec:
    """Specification of design system constraints for a UI component."""

    constraint_id: str
    component_name: str
    required_design_tokens: Tuple[str, ...]
    forbidden_css_literals: Tuple[str, ...]  # e.g., hardcoded hex colors like "#ff0000" or raw px units
    required_accessibility_props: Tuple[str, ...]  # e.g., "aria-label", "role"
    max_cyclomatic_complexity: int = 10

    def __post_init__(self) -> None:
        if not self.constraint_id or not self.component_name:
            raise ValueError("ERR_INVALID_SPEC_IDENTIFIERS")
        if self.max_cyclomatic_complexity <= 0:
            raise ValueError("ERR_INVALID_MAX_CYCLOMATIC_COMPLEXITY")


@dataclass(frozen=True)
class ConstraintVerificationReceipt:
    """Deterministic cryptographic verification receipt emitted by ConstraintCompiler."""

    passed: bool
    status_code: str
    component_name: str
    violations: Tuple[str, ...]
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_name": self.component_name,
            "passed": self.passed,
            "receipt_caid": self.receipt_caid,
            "status_code": self.status_code,
            "violations": list(self.violations),
        }


class ConstraintCompiler:
    """
    Compiles and enforces constraints for regeneratable UI components.
    Prevents AI-generated UI drift from configured design system tokens and AST invariants.
    """

    def __init__(self, spec: ComponentConstraintSpec) -> None:
        self.spec = spec

    def verify_component_code(self, source_code: str) -> ConstraintVerificationReceipt:
        violations: List[str] = []

        if not isinstance(source_code, str) or not source_code.strip():
            violations.append("VIOLATION_EMPTY_SOURCE_CODE")
            return self._mint(False, "HALT_EMPTY_SOURCE_CODE", violations)

        # 1. Check for forbidden CSS/Style literals (e.g., hardcoded hex colors or pixel values)
        for lit in self.spec.forbidden_css_literals:
            if re.search(re.escape(lit), source_code, re.IGNORECASE):
                violations.append(f"VIOLATION_FORBIDDEN_LITERAL:{lit}")

        # 2. Check for required design tokens
        for token in self.spec.required_design_tokens:
            if token not in source_code:
                violations.append(f"VIOLATION_MISSING_DESIGN_TOKEN:{token}")

        # 3. Parse AST for structural, accessibility, and complexity checks
        try:
            tree = ast.parse(source_code)
        except SyntaxError as exc:
            violations.append(f"VIOLATION_SYNTAX_ERROR:{exc.msg}")
            return self._mint(False, "HALT_SYNTAX_ERROR", violations)

        # 4. Check for required accessibility attributes (props in keyword args or dict literals)
        found_props: Set[str] = set()
        complexity = 1

        for node in ast.walk(tree):
            # Check keyword arguments (e.g. role='button', aria_label=...)
            if isinstance(node, ast.keyword) and node.arg:
                found_props.add(node.arg)
                found_props.add(node.arg.replace("_", "-"))

            # Check dict keys in JSX/hyperscript call descriptors (e.g. {'role': 'button', 'aria-label': ...})
            if isinstance(node, ast.Dict):
                for k in node.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        found_props.add(k.value)
                        found_props.add(k.value.replace("_", "-"))

            # Calculate cyclomatic complexity decision points
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith, ast.Assert)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += max(0, len(node.values) - 1)

            # Detect stealth string concatenation evading raw literal regex
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                    if isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
                        folded = node.left.value + node.right.value
                        for lit in self.spec.forbidden_css_literals:
                            if lit.lower() in folded.lower():
                                violations.append(f"VIOLATION_FORBIDDEN_LITERAL:{lit}")

        for prop in self.spec.required_accessibility_props:
            if prop not in found_props:
                violations.append(f"VIOLATION_MISSING_ACCESSIBILITY_PROP:{prop}")

        if complexity > self.spec.max_cyclomatic_complexity:
            violations.append(
                f"VIOLATION_CYCLOMATIC_COMPLEXITY:{complexity}_exceeds_{self.spec.max_cyclomatic_complexity}"
            )

        passed = len(violations) == 0
        status_code = "OK_CONSTRAINTS_SATISFIED" if passed else "HALT_COMPONENT_CONSTRAINT_VIOLATION"
        return self._mint(passed, status_code, sorted(violations))

    def _mint(
        self, passed: bool, status_code: str, violations: Sequence[str]
    ) -> ConstraintVerificationReceipt:
        sorted_violations = tuple(sorted(violations))
        payload = {
            "component_name": self.spec.component_name,
            "constraint_id": self.spec.constraint_id,
            "passed": passed,
            "status_code": status_code,
            "violations": list(sorted_violations),
        }
        return ConstraintVerificationReceipt(
            passed=passed,
            status_code=status_code,
            component_name=self.spec.component_name,
            violations=sorted_violations,
            receipt_caid=sha256_jcs_caid(payload),
        )
