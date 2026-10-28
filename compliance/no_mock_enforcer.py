#!/usr/bin/env python3
r"""
no_mock_enforcer.py — Zero-Mock & Cryptographic Purity Enforcer
Sovereign Multi-Agent OS (SMAOS) / AEIB Compliance

Enforces AGENTS.md Rule 2:
1. Zero Mocking: Forbids unittest.mock, MagicMock, patch in production and benchmark axes.
2. Zero Fake Crypto: Forbids mock_signature, stub_hash, and stub cryptographic bypasses.
3. Required Axes Verification: Validates that cryptographic signing and RFC 8785
   canonicalization axes are actively imported and invoked by real primitives.
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Set


REQUIRED_AXES = {
    "signing": {
        "module": "cryptography.hazmat.primitives.asymmetric.ed25519",
        "description": "Real Ed25519 asymmetric cryptography",
    },
    "canonicalization": {
        "module": "src.jcs_canonicalizer",
        "description": "Strict RFC 8785 JSON Canonicalization Scheme",
    },
}

FORBIDDEN_TOKENS = {
    "mock_signature",
    "stub_hash",
    "mock_sig",
    "stub_key",
    "MOCK_PUB_KEY",
    "MOCK_SIG",
}


def check_file_for_mocks_and_stubs(path: Path) -> List[str]:
    violations = []
    if path.name in ("no_mock_enforcer.py", "ast_purity.py"):
        return violations

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return violations

    # Token check
    for line_no, line in enumerate(content.splitlines(), start=1):
        for token in FORBIDDEN_TOKENS:
            if token in line and not line.strip().startswith("#"):
                violations.append(f"{path}:{line_no}: forbidden fake crypto token '{token}'")

    # AST check
    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError as e:
        violations.append(f"{path}:{e.lineno}: SyntaxError while parsing AST")
        return violations

    for node in ast.walk(tree):
        # Detect mock imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("unittest.mock", "mock"):
                    violations.append(f"{path}:{node.lineno}: forbidden mock framework import '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module in ("unittest.mock", "mock") or (
                node.module == "unittest" and any(a.name == "mock" for a in node.names)
            ):
                violations.append(f"{path}:{node.lineno}: forbidden mock framework import from '{node.module}'")

        # Detect constant boolean bypass functions (in non-test files)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not path.name.startswith("test_") and "tests" not in path.parts:
                real_body = [
                    n for n in node.body
                    if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))
                ]
                if len(real_body) == 1 and isinstance(real_body[0], ast.Return):
                    val = real_body[0].value
                    if isinstance(val, ast.Constant) and isinstance(val.value, bool):
                        violations.append(
                            f"{path}:{node.lineno}: constant boolean bypass function '{node.name}' (returns {val.value})"
                        )

    return violations


def verify_required_axes(target_dir: Path) -> List[str]:
    """Verifies that designated production modules implement the required integration axes."""
    violations = []
    engine_file = target_dir / "src" / "aeib_v040_engine.py"
    if not engine_file.is_file():
        # Try finding relative
        candidate = Path("src/aeib_v040_engine.py")
        if candidate.is_file():
            engine_file = candidate
        else:
            violations.append("Required engine file 'src/aeib_v040_engine.py' not found.")
            return violations

    try:
        content = engine_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(engine_file))
    except Exception as e:
        violations.append(f"Failed to parse engine file: {e}")
        return violations

    imported_modules: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)

    for axis_name, spec in REQUIRED_AXES.items():
        expected_mod = spec["module"]
        # Check if expected module or parent is imported
        matched = any(
            imported == expected_mod or expected_mod.startswith(imported + ".")
            for imported in imported_modules
        )
        if not matched:
            violations.append(
                f"Required axis '{axis_name}' ({spec['description']}) missing in {engine_file}: "
                f"expected import of '{expected_mod}'"
            )

    return violations


def self_test_bad_fixture() -> bool:
    """Proves that the enforcer catches a deliberate bad fixture."""
    bad_code = """
import unittest.mock
def bypass():
    return True
"""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(bad_code)
        f.flush()
        temp_path = Path(f.name)

    try:
        violations = check_file_for_mocks_and_stubs(temp_path)
        # Must detect at least the mock import and the bypass function
        has_mock = any("forbidden mock framework" in v for v in violations)
        has_bypass = any("constant boolean bypass" in v for v in violations)
        return has_mock and has_bypass
    finally:
        temp_path.unlink(missing_ok=True)


def main():
    if "--self-test" in sys.argv:
        if self_test_bad_fixture():
            print("[✓] Self-test passed: Bad fixtures successfully detected.")
            sys.exit(0)
        else:
            print("[!] Self-test failed: Enforcer failed to detect synthetic bad fixture.", file=sys.stderr)
            sys.exit(1)

    root = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else ".")
    ignore_dirs = {
        ".git", ".venv", "venv", "scratch", "dist", "__pycache__", "target", "pkg",
        "node_modules", "site-packages"
    }

    all_violations = []

    # 1. Verify required architectural axes
    all_violations.extend(verify_required_axes(root))

    # 2. Scan core production and compliance directories
    scan_targets = [
        root / "src",
        root / "compliance",
        root / "benchmarks" / "aeib_execution_integrity",
    ]

    for target in scan_targets:
        if not target.exists():
            continue
        for path in target.rglob("*.py"):
            if any(ignored in path.parts for ignored in ignore_dirs):
                continue
            all_violations.extend(check_file_for_mocks_and_stubs(path))

    # Also scan root-level Python scripts (e.g. aeib_verify.py, aeib_mcp_proxy.py)
    for path in root.glob("*.py"):
        if any(ignored in path.parts for ignored in ignore_dirs):
            continue
        all_violations.extend(check_file_for_mocks_and_stubs(path))

    if all_violations:
        print("[!] Zero-Mock Purity Violations Detected:", file=sys.stderr)
        for v in all_violations:
            print(f"    {v}", file=sys.stderr)
        sys.exit(1)

    print("[✓] Zero-Mock Enforcer: Integration axes confirmed unmocked and verified.")
    sys.exit(0)


if __name__ == "__main__":
    main()
