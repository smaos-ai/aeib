#!/usr/bin/env python3
"""
tests/test_jcs_canonicalizer_discovery.py — closes the registry-gap defeater.

tests/test_jcs_single_source.py only compares canonicalizers listed in its
CANONICALIZERS registry. This test discovers local copies by AST instead of by
list: any function or method whose name contains canonical / jcs / rfc8785 and
that calls `json.dumps(..., sort_keys=...)` itself must be in the registry.
Functions that delegate to src.jcs_canonicalizer.encode_jcs are not flagged.

Scope (stated honestly): name-based discovery. A canonicalizer with an
unrelated name, or one built without json.dumps, is not found.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import List, Tuple

from tests.test_jcs_single_source import CANONICALIZERS

REPO = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("src", "tools", "compliance", "adapters", "benchmarks", "scripts")
SKIP_DIRS = {"__pycache__", "third_party", "node_modules", ".venv"}
NAME_RE = re.compile(
    r"canonical|jcs|rfc8785|deterministic_json|compute_.*hash|_compute_hash",
    re.I,
)
# Reviewed exceptions, each with a reason. Adding an entry here is a visible,
# reviewable decision, not a silent opt-out.
EXEMPT = {
    # the reference implementation itself
    ("src.jcs_canonicalizer", "encode_jcs"),
    # stdlib-only standalone wire twin: bytes feed an HMAC token computed and
    # checked by the same class; it does not claim RFC 8785 and cannot import
    # src/ when run as a script. Listed as OPEN in the decide report.
    ("tools.blackbox_wire_tdd_harness", "_canonical_bytes"),
}


def _python_files() -> List[Path]:
    files: List[Path] = []
    for d in SCAN_DIRS:
        for dp, dn, fn in os.walk(REPO / d):
            dn[:] = [x for x in dn if x not in SKIP_DIRS]
            files += [Path(dp) / f for f in fn if f.endswith(".py")]
    files += list(REPO.glob("*.py"))
    return files


def _sorted_dumps(fn: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "dumps"
        and any(k.arg == "sort_keys" for k in n.keywords)
        for n in ast.walk(fn)
    )


def discover_local_canonicalizers() -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        module = ".".join(path.relative_to(REPO).with_suffix("").parts)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and NAME_RE.search(node.name):
                if _sorted_dumps(node):
                    found.append((module, node.name))
    return sorted(set(found))


def test_every_local_json_dumps_canonicalizer_is_registered() -> None:
    registered = {(m, f) for m, f, _ in CANONICALIZERS}
    unregistered = [x for x in discover_local_canonicalizers() if x not in registered and x not in EXEMPT]
    assert unregistered == [], (
        "Local canonicalizers not compared against the RFC 8785 reference. Delegate to "
        f"src.jcs_canonicalizer.encode_jcs or add to CANONICALIZERS: {unregistered}"
    )


def test_discovery_finds_a_planted_copy(tmp_path: Path) -> None:
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import json\n"
        "def my_canonical_bytes(o):\n    return json.dumps(o, sort_keys=True).encode()\n"
        "class K:\n    @staticmethod\n    def _jcs(o):\n        return json.dumps(o, sort_keys=True)\n"
        "def canonical_ok(o):\n    from src.jcs_canonicalizer import encode_jcs\n    return encode_jcs(o)\n"
        "def unrelated(o):\n    return json.dumps(o, sort_keys=True)\n"
    )
    tree = ast.parse(planted.read_text())
    hits = sorted(n.name for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and NAME_RE.search(n.name) and _sorted_dumps(n))
    assert hits == ["_jcs", "my_canonical_bytes"]
