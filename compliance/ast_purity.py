#!/usr/bin/env python3
import ast
import re
import sys
from pathlib import Path

FORBIDDEN_CALLS = {
    "unittest.mock.patch", "unittest.mock.MagicMock", "unittest.mock.Mock",
    "os.system", "eval", "exec",
}

FORBIDDEN_STRINGS = {
    "UNSUPPORTED_SOFTWARE_STUB",
    "always-pass",
    "TODO: implement",
    "emulation_fallback",
    "dangerouslySkipPermissions",
}

HARDCODED_VERDICT_RE = re.compile(
    r"\[(PASS|PASSED|OK|SUCCESS)\]|\b(100(\.0+)?%|0(\.0+)?%)\s*(PASS|TRAP RATE|DMR|LINKAGE|FAIL-CLOSED)",
    re.IGNORECASE
)

JS_MOCK_RE = re.compile(r"\b(mock[A-Z_]\w*|MOCK_\w+|stub_hash|mock_signature)\b|\"00\"\.repeat\(")


class PurityVisitor(ast.NodeVisitor):
    def __init__(self, path: Path):
        self.path = path
        self.violations = []
        self.in_test_func = False

    def visit_FunctionDef(self, node):
        prev = self.in_test_func
        if node.name.startswith("test_") or node.name.endswith("_test"):
            self.in_test_func = True

        # Detect empty stub functions
        if node.name != "log_message":
            real_body = [
                n for n in node.body
                if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))
            ]
            if len(real_body) == 1:
                if isinstance(real_body[0], ast.Pass):
                    self.violations.append(f"{self.path}:{node.lineno}: empty pass stub '{node.name}'")
                elif isinstance(real_body[0], ast.Return) and (
                    real_body[0].value is None
                    or (isinstance(real_body[0].value, ast.Constant) and real_body[0].value.value is None)
                ):
                    self.violations.append(f"{self.path}:{node.lineno}: null-return stub '{node.name}'")

        self.generic_visit(node)
        self.in_test_func = prev

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Import(self, node):
        is_test = "tests" in self.path.parts or self.path.name.startswith("test_")
        if not is_test:
            for alias in node.names:
                if alias.name in ("unittest.mock", "mock"):
                    self.violations.append(f"{self.path}:{node.lineno}: forbidden mock framework import '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        is_test = "tests" in self.path.parts or self.path.name.startswith("test_")
        if not is_test:
            if node.module in ("unittest.mock", "mock") or (
                node.module == "unittest" and any(a.name == "mock" for a in node.names)
            ):
                self.violations.append(f"{self.path}:{node.lineno}: forbidden mock framework import from '{node.module}'")
        self.generic_visit(node)

    def visit_Call(self, node):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = ast.unparse(node.func)

        if func_name in FORBIDDEN_CALLS:
            self.violations.append(f"{self.path}:{node.lineno}: forbidden call '{func_name}'")

        # Detect hardcoded result output in non-test functions and non-test files
        if not self.in_test_func and "tests" not in self.path.parts and not self.path.name.startswith("test_"):
            if func_name == "print" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                text = node.args[0].value
                if HARDCODED_VERDICT_RE.search(text):
                    self.violations.append(f"{self.path}:{node.lineno}: hardcoded result literal in print(): {text[:60]!r}")

        self.generic_visit(node)


def scan_file(path: Path) -> list[str]:
    violations = []
    if path.name in ("ast_purity.py", "no_mock_enforcer.py"):
        return violations
    if path.is_symlink() and not path.exists():
        return violations

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return violations

    # Check raw token forbidden strings
    for line_no, line in enumerate(content.splitlines(), start=1):
        for pattern in FORBIDDEN_STRINGS:
            if pattern in line:
                violations.append(f"{path}:{line_no}: forbidden literal '{pattern}'")

    # AST checks
    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError as e:
        violations.append(f"{path}:{e.lineno}: SyntaxError while parsing AST")
        return violations

    visitor = PurityVisitor(path)
    visitor.visit(tree)
    violations.extend(visitor.violations)
    return violations


def scan_js(path: Path) -> list[str]:
    # Exempt unit test files from mock checks
    if path.name.endswith(".test.js") or path.name.endswith(".spec.js") or "tests" in path.parts:
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    return [
        f"{path}:{i}: mock token in shipped JS"
        for i, line in enumerate(content.splitlines(), start=1)
        if JS_MOCK_RE.search(line)
    ]


def self_test_bad_fixture() -> bool:
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write('print("[PASS] fake vector passed")\n')
        f.flush()
        temp_path = Path(f.name)
    try:
        v = scan_file(temp_path)
        return any("hardcoded result literal" in item for item in v)
    finally:
        temp_path.unlink(missing_ok=True)


def main():
    if "--self-test" in sys.argv:
        if self_test_bad_fixture():
            print("[✓] AST Purity Self-Test: Deliberate bad fixture successfully caught.")
            sys.exit(0)
        else:
            print("[!] AST Purity Self-Test FAILED: Bad fixture was not caught.", file=sys.stderr)
            sys.exit(1)

    root = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else ".")
    ignore_dirs = {
        ".git", ".venv", "venv", "venv_l2", "node_modules", "scratch", "dist",
        ".pre-commit-cache", "__pycache__", "site-packages", ".claude", ".worktrees",
        "duplicate-side-effect-desk", "agent-runtime-integrity-bench", "tau2-bench",
        "scripts"
    }
    all_violations = []

    for path in root.rglob("*.py"):
        if any(ignored in path.parts for ignored in ignore_dirs):
            continue
        all_violations.extend(scan_file(path))
    for path in list(root.rglob("*.js")):
        if any(ignored in path.parts for ignored in ignore_dirs | {"pkg", "target"}):
            continue
        all_violations.extend(scan_js(path))

    if all_violations:
        print("[!] AST Purity Violations Found:", file=sys.stderr)
        for v in all_violations:
            print(f"    {v}", file=sys.stderr)
        sys.exit(1)

    print("[✓] AST Purity: Zero stubs, zero forbidden strings, zero mock calls.")
    sys.exit(0)


if __name__ == "__main__":
    main()
