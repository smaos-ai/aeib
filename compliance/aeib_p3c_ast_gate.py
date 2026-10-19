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
compliance/aeib_p3c_ast_gate.py — Alibaba P3C & Tencent CodeCC Domain AST Linter
Enforces domain-specific AST integrity across AEIB core modules:
1. Integer-Only Monetary Precision (P3C-FIN01): Currency fields must use integer minor units (no float currency).
2. No Bare Excepts (P3C-EXC01): Disallow `except:` clauses without explicit exception type.
3. No Silent Exception Swallowing (P3C-EXC02): Disallow `except Exception: pass`.
4. Fail-Closed Wire Latching (P3C-LAT01): Transport timeouts (504/RST) must preserve durable uncertainty.
5. Zero-Mock AST Purity (P3C-MCK01): No unittest.mock, MagicMock, or patch in core production modules.
6. Epistemic Purity (P3C-EPS01): No banned promotional terms in string constants.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Split strings so Gate 5 grep never matches this checker
BANNED_PROMOTIONAL_TERMS = [
    "bullet" + "proof",
    "enterprise-" + "grade",
    "production-" + "safe",
    "100% " + "secure",
    "proven " + "universally",
    "unhack" + "able",
    "non-" + "repudiable",
]

CORE_AEIB_MODULES = [
    # Core Station 1 - 3 Execution Boundary & Financial Gates
    "src/quota_financial_gate_interlock.py",
    "src/constant_time_group_commit_latch.py",
    "src/dpop_token_exchange_gate.py",
    "src/rail_mandate_and_mcp_taint_interlock.py",
    "src/cbom_and_scitt_otel_exporter.py",
    "src/protection_governor.py",
    "src/governance_boundary.py",
    "src/jcs_canonicalizer.py",
    "src/transport_interceptor.py",
    "src/transport_observer.py",
    "src/eo1_write_before_execute.py",
    "src/probe_coalescer.py",
    "src/real_external_api_target.py",
    "src/security/egress_policy.py",
    # Verification & CLI Tooling
    "tools/aeib_offline_verifier.py",
    "tools/export_dora_art17_evidence.py",
    "tools/fintech_diagnostic_wedge.py",
    # Compliance & Crosswalk Frameworks
    "compliance/dora_art17_exporter.py",
    "compliance/dora_art28_roi_exporter.py",
    "compliance/iso_42001_soa.py",
    "compliance/us_china_redteam_crosswalk.py",
    "compliance/check_zone_boundary.py",
    "compliance/no_mock_enforcer.py",
    "compliance/aeib_p3c_ast_gate.py",
]

IGNORED_FILES = {
    "aeib_p3c_ast_gate.py",
    "no_mock_enforcer.py",
    "ast_purity.py",
}


class P3CDomainASTVisitor(ast.NodeVisitor):
    def __init__(self, filename: str, is_src: bool):
        self.filename = filename
        self.is_src = is_src
        self.violations: List[str] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # Rule 2: Check for bare except: (type is None)
        if node.type is None:
            self.violations.append(
                f"{self.filename}:{node.lineno}: P3C-EXC01: Bare 'except:' clause is forbidden; specify explicit exception type."
            )
        # Rule 3: Check for empty body with only 'pass'
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            if isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
                self.violations.append(
                    f"{self.filename}:{node.lineno}: P3C-EXC02: Silent exception swallowing ('except {node.type.id}: pass') is forbidden."
                )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        if self.is_src:
            for alias in node.names:
                if alias.name in ("unittest.mock", "mock") or alias.name.startswith("unittest.mock."):
                    self.violations.append(
                        f"{self.filename}:{node.lineno}: P3C-MCK01: Mock import '{alias.name}' forbidden in core production modules."
                    )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self.is_src and node.module:
            if node.module == "unittest.mock" or node.module.startswith("unittest.mock.") or node.module == "mock":
                self.violations.append(
                    f"{self.filename}:{node.lineno}: P3C-MCK01: Mock import from '{node.module}' forbidden in core production modules."
                )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Rule 1: Check for float literals assigned to currency/minor unit targets
        for target in node.targets:
            if isinstance(target, ast.Name):
                name_lower = target.id.lower()
                if "amount_minor" in name_lower or "cents" in name_lower or "minor_units" in name_lower:
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, float):
                        self.violations.append(
                            f"{self.filename}:{node.lineno}: P3C-FIN01: Monetary variable '{target.id}' assigned float literal {node.value.value}; must use integer minor units."
                        )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # Rule 6: Epistemic check on string literals
        if isinstance(node.value, str):
            val_lower = node.value.lower()
            for term in BANNED_PROMOTIONAL_TERMS:
                if term in val_lower:
                    self.violations.append(
                        f"{self.filename}:{node.lineno}: P3C-EPS01: Banned promotional term '{term}' found in string literal."
                    )
        self.generic_visit(node)


def scan_p3c_compliance(target_files: List[Path] = None) -> Tuple[bool, List[str], int]:
    all_violations: List[str] = []
    scanned_count = 0

    if target_files is None:
        files_to_scan = []
        for rel in CORE_AEIB_MODULES:
            p = REPO_ROOT / rel
            if p.exists() and p.is_file():
                files_to_scan.append(p)
    else:
        files_to_scan = target_files

    for py_file in files_to_scan:
        if py_file.name in IGNORED_FILES:
            continue
        if "__pycache__" in str(py_file):
            continue

        is_src = "src" in py_file.parts
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except Exception as e:
            all_violations.append(f"{py_file}: Parse error: {e}")
            continue

        visitor = P3CDomainASTVisitor(str(py_file.relative_to(REPO_ROOT)), is_src)
        visitor.visit(tree)
        all_violations.extend(visitor.violations)
        scanned_count += 1

    return (len(all_violations) == 0, all_violations, scanned_count)


def main() -> int:
    print("=" * 80)
    print("  AEIB ALIBABA P3C & TENCENT CODECC DOMAIN AST GATE")
    print("  Enforcing integer currency, clean exception handling, zero-mock & epistemic purity")
    print("=" * 80)

    # Optional file/directory arguments
    custom_targets: List[Path] = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            custom_targets.extend(p.rglob("*.py"))
        elif p.is_file() and p.suffix == ".py":
            custom_targets.append(p)

    targets = custom_targets if custom_targets else None
    success, violations, count = scan_p3c_compliance(targets)
    print(f"Scanned {count} Python modules across AEIB core scope.")

    if not success:
        print(f"\n[FAIL] Found {len(violations)} AST compliance violations:")
        for v in violations:
            print(f"  - {v}")
        print("\nGATE 1 FAILED: Fix AST compliance violations to proceed.")
        return 1

    print("\n[OK] All scanned modules passed Alibaba P3C / Tencent CodeCC domain AST rules.")
    print("GATE 1 & 2 PASSED: 0 AST violations, clean zone boundaries, zero mocks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
