#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Clean-Room Verification Protocol (CRVP) - AST Purity Scanner
"""
AST Purity Scanner (scripts/ast_purity_scanner.py):
Parses the Python Abstract Syntax Tree across codebase directories to enforce
a 100% native execution surface with zero test doubles, mock frameworks, or bypass gates.
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

FORBIDDEN_SYMBOLS = {
    "MagicMock",
    "Mock",
    "create_autospec",
    "patch",
    "MockTransport",
}


class ASTPurityVisitor(ast.NodeVisitor):
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
            if alias.name in FORBIDDEN_SYMBOLS:
                self.violations.append(
                    f"{self.filename}:{node.lineno} -> forbidden mock symbol imported: '{alias.name}'"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Direct calls
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_SYMBOLS:
            self.violations.append(
                f"{self.filename}:{node.lineno} -> forbidden mock call: '{node.func.id}()'"
            )
        # Attribute calls (e.g., m.MagicMock(), mock.patch())
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_SYMBOLS:
                self.violations.append(
                    f"{self.filename}:{node.lineno} -> forbidden mock attribute call: '.{node.func.attr}()'"
                )
            if node.func.attr == "import_module" and node.args:
                if isinstance(node.args[0], ast.Constant) and node.args[0].value in FORBIDDEN_MODULES:
                    self.violations.append(
                        f"{self.filename}:{node.lineno} -> dynamic mock import: import_module('{node.args[0].value}')"
                    )
        # Dynamic built-in __import__
        elif isinstance(node.func, ast.Name) and node.func.id == "__import__" and node.args:
            if isinstance(node.args[0], ast.Constant) and node.args[0].value in FORBIDDEN_MODULES:
                self.violations.append(
                    f"{self.filename}:{node.lineno} -> dynamic mock import: __import__('{node.args[0].value}')"
                )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Detection of unconditional bypass gates: def verify_*(...): return True
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
        visitor = ASTPurityVisitor(str(filepath))
        visitor.visit(tree)
        return visitor.violations
    except Exception as e:
        return [f"{filepath}:0 -> parse error: {e}"]


def scan_codebase(directories: list[str], repo_root: Path = None) -> list[str]:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent

    all_violations = []
    for d in directories:
        dir_path = repo_root / d
        if not dir_path.exists():
            continue
        for root, dirnames, files in os.walk(dir_path):
            # Skip hidden folders and virtualenvs
            dirnames[:] = [x for x in dirnames if not x.startswith(".") and x != "__pycache__" and x != "venv"]
            for file in sorted(files):
                if file.endswith(".py"):
                    filepath = Path(root) / file
                    # Skip scanner scripts themselves
                    if filepath.name in {"ast_purity_scanner.py", "scan_for_mocks.py", "no_mock_enforcer.py", "ast_purity.py"}:
                        continue
                    # In test directories, skip unit test fixtures that legitimately test negative mocks
                    if "tests" in str(filepath).split(os.sep) and ("negative" in file or "mock" in file):
                        continue
                    violations = scan_file(filepath)
                    all_violations.extend(violations)
    return all_violations


def main():
    repo_root = Path(__file__).resolve().parent.parent
    target_dirs = ["src", "compliance", "schemas"]
    
    print("[*] Parsing AST across codebase for mock purity enforcement...")
    violations = scan_codebase(target_dirs, repo_root)

    if violations:
        print(f"[!] CRITICAL: Found {len(violations)} mock purity violations:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print("[+] AST PURITY SUCCESS: 100% native execution surface. Zero mock modules or symbols found.")
    sys.exit(0)


if __name__ == "__main__":
    main()
