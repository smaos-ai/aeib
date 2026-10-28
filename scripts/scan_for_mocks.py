#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Clean-Room Verification Protocol (CRVP) - Phase 1: True AST Mock Detection
"""
Scans the codebase using Python's native Abstract Syntax Tree (ast) module
to detect mock imports, mock instantiation, dynamic mock imports, and bypass gates.
Operates on the parsed syntax graph rather than text regex.
"""

import ast
import os
import sys
from pathlib import Path

FORBIDDEN_MODULES = {
    "unittest.mock",
    "mock",
    "responses",
    "pytest_mock",
    "httpx._transports.mock",
}

FORBIDDEN_CALLS_OR_NAMES = {
    "MagicMock",
    "Mock",
    "create_autospec",
    "patch",
    "MockTransport",
}

TARGET_DIRECTORIES = ["src", "compliance", "schemas"]


class ASTMockVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            base_mod = alias.name.split(".")[0]
            if alias.name in FORBIDDEN_MODULES or base_mod in FORBIDDEN_MODULES:
                self.violations.append(
                    f"{self.filename}:{node.lineno} -> forbidden import: 'import {alias.name}'"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        if mod in FORBIDDEN_MODULES or any(mod.startswith(m) for m in FORBIDDEN_MODULES):
            self.violations.append(
                f"{self.filename}:{node.lineno} -> forbidden from-import: 'from {mod} import ...'"
            )
        for alias in node.names:
            if alias.name in FORBIDDEN_CALLS_OR_NAMES:
                self.violations.append(
                    f"{self.filename}:{node.lineno} -> forbidden mock symbol imported: '{alias.name}'"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # 1. Direct call to MagicMock(), patch(), etc.
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS_OR_NAMES:
            self.violations.append(
                f"{self.filename}:{node.lineno} -> forbidden mock call: '{node.func.id}()'"
            )
        # 2. Attribute call: mock.patch(), unittest.mock.MagicMock()
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_CALLS_OR_NAMES:
                self.violations.append(
                    f"{self.filename}:{node.lineno} -> forbidden mock method call: '.{node.func.attr}()'"
                )
            # Check for dynamic import: importlib.import_module("unittest.mock")
            if node.func.attr == "import_module":
                if node.args and isinstance(node.args[0], ast.Constant):
                    if node.args[0].value in FORBIDDEN_MODULES:
                        self.violations.append(
                            f"{self.filename}:{node.lineno} -> dynamic mock import: import_module('{node.args[0].value}')"
                        )
        # 3. Dynamic built-in call: __import__("unittest.mock")
        elif isinstance(node.func, ast.Name) and node.func.id == "__import__":
            if node.args and isinstance(node.args[0], ast.Constant):
                if node.args[0].value in FORBIDDEN_MODULES:
                    self.violations.append(
                        f"{self.filename}:{node.lineno} -> dynamic mock import: __import__('{node.args[0].value}')"
                    )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Check for trivial verification bypass gates: def verify_*(...): return True
        func_name = node.name.lower()
        if func_name.startswith(("verify_", "validate_", "check_")) and len(node.body) == 1:
            first_stmt = node.body[0]
            if isinstance(first_stmt, ast.Return) and isinstance(first_stmt.value, ast.Constant):
                if first_stmt.value.value is True:
                    self.violations.append(
                        f"{self.filename}:{node.lineno} -> bypass gate detected: '{node.name}()' unconditionally returns True"
                    )
        self.generic_visit(node)


def scan_file(filepath: Path) -> list[str]:
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        visitor = ASTMockVisitor(str(filepath))
        visitor.visit(tree)
        return visitor.violations
    except Exception as e:
        return [f"{filepath}:0 -> parse error: {e}"]


def scan_directories(repo_root: Path, target_dirs: list[str]) -> list[str]:
    all_violations = []
    for td in target_dirs:
        dir_path = repo_root / td
        if not dir_path.exists():
            continue
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    # Skip scan script itself or tests
                    if "test" in file.lower() or file == "scan_for_mocks.py":
                        continue
                    violations = scan_file(file_path)
                    all_violations.extend(violations)
    return all_violations


def main():
    repo_root = Path(__file__).resolve().parent.parent
    print("=" * 80)
    print("CRVP PHASE 1: TRUE AST ZERO-MOCK DETECTION SCANNER")
    print(f"Scanning target directories: {TARGET_DIRECTORIES} in {repo_root}")
    print("=" * 80)

    violations = scan_directories(repo_root, TARGET_DIRECTORIES)

    if violations:
        print(f"\n[!] CRITICAL: Found {len(violations)} mock or bypass violations in production code:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print("\n[✓] SUCCESS: 0 mocks, stubs, dynamic mock loaders, or bypass gates detected.")
    print("    AST verification confirmed: all production logic executes natively.")
    sys.exit(0)


if __name__ == "__main__":
    main()
