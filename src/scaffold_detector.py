#!/usr/bin/env python3
"""
Scaffold detector (AST-based, prototype).

Answers one narrow question about a candidate module: which functions or classes that were
ADDED or CHANGED relative to a "before" source are placeholders rather than implementations?

SCAFFOLD (counted):
  SCAFFOLD_PASS_BODY            function body is only `pass` (after an optional docstring)
  SCAFFOLD_ELLIPSIS_BODY        function body is only `...`
  SCAFFOLD_NOT_IMPLEMENTED      function body is only `raise NotImplementedError[...]`
  SCAFFOLD_DOCSTRING_ONLY       function body is only a docstring (outside an ABC)
  SCAFFOLD_TODO_ADDED           a TODO/FIXME comment that was not present before
  SCAFFOLD_TEST_DOUBLE_IN_PRODUCTION  a Mock*/Fake*/Stub* class in a non-test file when test
                                doubles were not requested
WARN (reported, not counted):
  WARN_CONSTANT_RETURN          a function with parameters whose body is a single `return <constant>`
  WARN_BARE_EXCEPT_PASS         a new `except: pass`
ALLOWLIST (never flagged): @abstractmethod, @overload, members of typing.Protocol classes,
  docstring-only methods of ABCs, names that merely contain "Mock" (MockingbirdDecoder),
  exception subclasses whose body is `pass`, TODOs unchanged from before.

Limitations (stated, not hidden): this is a structural check. It does not decide whether an
implementation is correct, and a model can write a non-empty but wrong body that passes it; the
hidden tests in the benchmark are what measure correctness.
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

SCAFFOLD_CATEGORIES = frozenset({
    "SCAFFOLD_PASS_BODY",
    "SCAFFOLD_ELLIPSIS_BODY",
    "SCAFFOLD_NOT_IMPLEMENTED",
    "SCAFFOLD_DOCSTRING_ONLY",
    "SCAFFOLD_TODO_ADDED",
    "SCAFFOLD_TEST_DOUBLE_IN_PRODUCTION",
    "SYNTAX_ERROR",
})
WARN_CATEGORIES = frozenset({"WARN_CONSTANT_RETURN", "WARN_BARE_EXCEPT_PASS"})

_TEST_DOUBLE_RE = re.compile(r"^(Mock|Fake|Stub)([A-Z_0-9]|$)")
_TODO_RE = re.compile(r"\b(TODO|FIXME)\b")


@dataclass(frozen=True)
class Finding:
    category: str
    line: int
    symbol: str


@dataclass(frozen=True)
class DetectionResult:
    findings: Tuple[Finding, ...]
    scaffold_count: int
    warn_count: int


def _decorator_names(node: ast.AST) -> List[str]:
    names = []
    for dec in getattr(node, "decorator_list", []):
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute):
            names.append(target.attr)
        elif isinstance(target, ast.Name):
            names.append(target.id)
    return names


def _base_names(cls: ast.ClassDef) -> List[str]:
    names = []
    for base in cls.bases:
        if isinstance(base, ast.Attribute):
            names.append(base.attr)
        elif isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Subscript):
            inner = base.value
            if isinstance(inner, ast.Attribute):
                names.append(inner.attr)
            elif isinstance(inner, ast.Name):
                names.append(inner.id)
    for kw in cls.keywords:
        if kw.arg == "metaclass" and isinstance(kw.value, (ast.Name, ast.Attribute)):
            names.append(kw.value.id if isinstance(kw.value, ast.Name) else kw.value.attr)
    return names


def _is_abc(cls: Optional[ast.ClassDef]) -> bool:
    return cls is not None and any(b in ("ABC", "ABCMeta") for b in _base_names(cls))


def _is_protocol(cls: Optional[ast.ClassDef]) -> bool:
    return cls is not None and "Protocol" in _base_names(cls)


def _strip_docstring(body: List[ast.stmt]) -> List[ast.stmt]:
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _is_not_implemented(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Raise) or stmt.exc is None:
        return False
    exc = stmt.exc.func if isinstance(stmt.exc, ast.Call) else stmt.exc
    return isinstance(exc, ast.Name) and exc.id == "NotImplementedError"


def _real_params(fn: ast.AST) -> int:
    args = fn.args
    names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
    names = [n for n in names if n not in ("self", "cls")]
    return len(names) + (1 if args.vararg else 0) + (1 if args.kwarg else 0)


def _collect_defs(tree: ast.Module) -> Dict[str, Tuple[ast.AST, Optional[ast.ClassDef]]]:
    """Qualified name -> (node, enclosing class or None)."""
    out: Dict[str, Tuple[ast.AST, Optional[ast.ClassDef]]] = {}

    def walk(nodes: List[ast.stmt], prefix: str, cls: Optional[ast.ClassDef]) -> None:
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = prefix + node.name
                out[qual] = (node, cls)
                walk(node.body, qual + ".", None)
            elif isinstance(node, ast.ClassDef):
                qual = prefix + node.name
                out[qual] = (node, cls)
                walk(node.body, qual + ".", node)

    walk(tree.body, "", None)
    return out


def _todo_comments(source: str) -> Counter:
    found: Counter = Counter()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT and _TODO_RE.search(tok.string):
                found[tok.string.strip()] += 1
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return found
    return found


def _bare_except_pass_count(tree: Optional[ast.Module]) -> int:
    if tree is None:
        return 0
    return sum(
        1 for n in ast.walk(tree)
        if isinstance(n, ast.ExceptHandler) and n.type is None
        and len(n.body) == 1 and isinstance(n.body[0], ast.Pass)
    )


def _todo_lines(source: str) -> Dict[str, int]:
    lines: Dict[str, int] = {}
    for idx, text in enumerate(source.splitlines(), start=1):
        if "#" in text and _TODO_RE.search(text):
            lines.setdefault(text[text.index("#"):].strip(), idx)
    return lines


def detect_scaffolds(
    before_source: Optional[str],
    after_source: str,
    is_test_file: bool = False,
    test_doubles_allowed: bool = False,
) -> DetectionResult:
    if not isinstance(after_source, str):
        raise TypeError("after_source must be str")
    try:
        after_tree = ast.parse(after_source)
    except SyntaxError as exc:
        finding = Finding("SYNTAX_ERROR", int(exc.lineno or 0), "<module>")
        return DetectionResult((finding,), 1, 0)
    before_tree: Optional[ast.Module] = None
    if before_source is not None:
        try:
            before_tree = ast.parse(before_source)
        except SyntaxError:
            before_tree = None

    before_defs = _collect_defs(before_tree) if before_tree is not None else {}
    after_defs = _collect_defs(after_tree)
    findings: List[Finding] = []

    for qual, (node, cls) in after_defs.items():
        prior = before_defs.get(qual)
        if prior is not None and ast.dump(prior[0]) == ast.dump(node):
            continue  # unchanged
        line = node.lineno
        if isinstance(node, ast.ClassDef):
            if _TEST_DOUBLE_RE.match(node.name) and not is_test_file and not test_doubles_allowed:
                findings.append(Finding("SCAFFOLD_TEST_DOUBLE_IN_PRODUCTION", line, qual))
            continue
        decorators = _decorator_names(node)
        if "abstractmethod" in decorators or "overload" in decorators or _is_protocol(cls):
            continue
        body = _strip_docstring(node.body)
        if not body:
            if not _is_abc(cls):
                findings.append(Finding("SCAFFOLD_DOCSTRING_ONLY", line, qual))
            continue
        if len(body) != 1:
            continue
        stmt = body[0]
        if isinstance(stmt, ast.Pass):
            findings.append(Finding("SCAFFOLD_PASS_BODY", line, qual))
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) \
                and stmt.value.value is Ellipsis:
            findings.append(Finding("SCAFFOLD_ELLIPSIS_BODY", line, qual))
        elif _is_not_implemented(stmt):
            findings.append(Finding("SCAFFOLD_NOT_IMPLEMENTED", line, qual))
        elif isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant) \
                and _real_params(node) > 0:
            findings.append(Finding("WARN_CONSTANT_RETURN", line, qual))

    added_todos = _todo_comments(after_source) - _todo_comments(before_source or "")
    todo_lines = _todo_lines(after_source)
    for text, count in sorted(added_todos.items()):
        for _ in range(count):
            findings.append(Finding("SCAFFOLD_TODO_ADDED", todo_lines.get(text, 0), text))

    extra_bare = _bare_except_pass_count(after_tree) - _bare_except_pass_count(before_tree)
    for _ in range(max(0, extra_bare)):
        findings.append(Finding("WARN_BARE_EXCEPT_PASS", 0, "<except>"))

    findings.sort(key=lambda f: (f.line, f.category, f.symbol))
    scaffold = sum(1 for f in findings if f.category in SCAFFOLD_CATEGORIES)
    warn = sum(1 for f in findings if f.category in WARN_CATEGORIES)
    return DetectionResult(tuple(findings), scaffold, warn)
