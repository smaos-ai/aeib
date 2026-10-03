#!/usr/bin/env python3
import ast
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

def scan_file(path: Path) -> list[str]:
    violations = []
    if path.name == "ast_purity.py":
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

    for node in ast.walk(tree):
        # 1. Detect stub functions (docstring only, pass only, or return None only)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "log_message":
                continue
            real_body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
            if len(real_body) == 1:
                if isinstance(real_body[0], ast.Pass):
                    violations.append(f"{path}:{node.lineno}: empty pass stub '{node.name}'")
                elif isinstance(real_body[0], ast.Return) and (real_body[0].value is None or (isinstance(real_body[0].value, ast.Constant) and real_body[0].value.value is None)):
                    violations.append(f"{path}:{node.lineno}: null-return stub '{node.name}'")

        # 2. Detect forbidden calls
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = ast.unparse(node.func)
            if func_name in FORBIDDEN_CALLS:
                violations.append(f"{path}:{node.lineno}: forbidden call '{func_name}'")

    return violations

def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    ignore_dirs = {
        ".git", ".venv", "venv", "venv_l2", "node_modules", "scratch", "dist",
        ".pre-commit-cache", "__pycache__", "site-packages",
        "duplicate-side-effect-desk", "agent-runtime-integrity-bench", "tau2-bench"
    }
    all_violations = []

    for path in root.rglob("*.py"):
        if any(ignored in path.parts for ignored in ignore_dirs):
            continue
        all_violations.extend(scan_file(path))

    if all_violations:
        print("[!] AST Purity Violations Found:", file=sys.stderr)
        for v in all_violations:
            print(f"    {v}", file=sys.stderr)
        sys.exit(1)

    print("[✓] AST Purity: Zero stubs, zero forbidden strings, zero mock calls.")
    sys.exit(0)

if __name__ == "__main__":
    main()
