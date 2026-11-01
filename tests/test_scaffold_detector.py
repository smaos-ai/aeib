#!/usr/bin/env python3
"""Tests for src/scaffold_detector.py against a hand-written labelled corpus.

The corpus (tests/data/scaffold_corpus.json) was written to the detector's stated spec, so the
AST detector's agreement with it shows the spec is implemented; it is not field accuracy. The
informative comparison is the pasted substring matcher on the same corpus (prediction made before
running: substring FP > 0 on the negatives and FN > 0 on `def f(x): ...`)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from src.scaffold_detector import (
    SCAFFOLD_CATEGORIES,
    WARN_CATEGORIES,
    DetectionResult,
    Finding,
    _is_not_implemented,
    _real_params,
    detect_scaffolds,
)

CORPUS = json.loads((Path(__file__).parent / "data" / "scaffold_corpus.json").read_text(encoding="utf-8"))
PASTED_PATTERNS = ("pass", "... ", "# TODO", "# FIXME", "raise NotImplementedError", "class Mock", "def stub_")


def pasted_substring_detector(after: str) -> bool:
    """Re-implementation of the pasted OpusBehavioralProxy string matcher (for comparison only)."""
    return any(p in after for p in PASTED_PATTERNS)


def confusion(predict) -> dict:
    m = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for c in CORPUS:
        got, want = predict(c), c["expected_scaffold"]
        m[("t" if got == want else "f") + ("p" if got else "n")] += 1
    return m


@pytest.mark.parametrize("case", CORPUS, ids=[c["id"] for c in CORPUS])
def test_corpus_case_matches_label(case) -> None:
    r = detect_scaffolds(case["before"], case["after"], case["is_test_file"], case["test_doubles_allowed"])
    assert sorted(f.category for f in r.findings) == case["expected_categories"]
    assert (r.scaffold_count > 0) is case["expected_scaffold"]
    assert r.scaffold_count == sum(1 for f in r.findings if f.category in SCAFFOLD_CATEGORIES)
    assert r.warn_count == sum(1 for f in r.findings if f.category in WARN_CATEGORIES)


def test_confusion_matrices_ast_vs_pasted_substring() -> None:
    ast_m = confusion(lambda c: detect_scaffolds(
        c["before"], c["after"], c["is_test_file"], c["test_doubles_allowed"]).scaffold_count > 0)
    sub_m = confusion(lambda c: pasted_substring_detector(c["after"]))
    assert len(CORPUS) >= 40
    assert ast_m == {"tp": 20, "fp": 0, "tn": 22, "fn": 0}
    # Measured on this corpus on 2026-10-28 (an earlier exact guess of tp18/fn2 was wrong; only the
    # qualitative prediction FP>0 and FN>0 was pre-registered). Recorded so a change is visible.
    assert sub_m["fp"] > 0 and sub_m["fn"] > 0
    assert sub_m == {"tp": 13, "fp": 12, "tn": 10, "fn": 7}


def test_result_shapes_and_frozen() -> None:
    r = detect_scaffolds(None, "def f(x):\n    pass\n")
    assert isinstance(r, DetectionResult) and r.scaffold_count == 1 and r.warn_count == 0
    assert r.findings == (Finding("SCAFFOLD_PASS_BODY", 1, "f"),)
    with pytest.raises(Exception):
        r.scaffold_count = 0  # type: ignore[misc]
    with pytest.raises(Exception):
        r.findings[0].line = 5  # type: ignore[misc]


def test_non_str_after_rejected_and_bad_before_tolerated() -> None:
    with pytest.raises(TypeError):
        detect_scaffolds(None, b"def f(): pass")  # type: ignore[arg-type]
    r = detect_scaffolds("def broken(:\n", "def f(x):\n    return x\n")
    assert r.scaffold_count == 0


def test_syntax_error_line_and_symbol() -> None:
    r = detect_scaffolds(None, "x = 1\ndef f(:\n    pass\n")
    assert r.findings == (Finding("SYNTAX_ERROR", 2, "<module>"),) and r.scaffold_count == 1
    assert r.warn_count == 0


def test_qualified_names_lines_and_ordering() -> None:
    src = "class A:\n    def m(self, x):\n        ...\n\ndef g(y):\n    pass\n"
    r = detect_scaffolds(None, src)
    assert [(f.category, f.line, f.symbol) for f in r.findings] == [
        ("SCAFFOLD_ELLIPSIS_BODY", 2, "A.m"), ("SCAFFOLD_PASS_BODY", 5, "g")]


def test_todo_counts_multiset_and_line() -> None:
    before = "def f(x):\n    # TODO a\n    return x\n"
    after = "def f(x):\n    # TODO a\n    # TODO a\n    return x + 1\n"
    r = detect_scaffolds(before, after)
    assert r.findings == (Finding("SCAFFOLD_TODO_ADDED", 2, "# TODO a"),)
    r2 = detect_scaffolds(None, "x = 1\n# FIXME later\n")
    assert r2.findings == (Finding("SCAFFOLD_TODO_ADDED", 2, "# FIXME later"),)


def test_constant_return_needs_real_params() -> None:
    assert detect_scaffolds(None, "class C:\n    def ok(self):\n        return True\n").warn_count == 0
    assert detect_scaffolds(None, "class C:\n    def ok(self, x):\n        return True\n").warn_count == 1
    assert detect_scaffolds(None, "def f(*args):\n    return 0\n").warn_count == 1
    assert detect_scaffolds(None, "def f(**kw):\n    return 0\n").warn_count == 1
    assert detect_scaffolds(None, "def f(*, k):\n    return 0\n").warn_count == 1
    assert detect_scaffolds(None, "def f(x):\n    return x\n").warn_count == 0


def test_bare_except_counted_relative_to_before() -> None:
    body = "def f(x):\n    try:\n        return int(x)\n    except:\n        pass\n    return 0\n"
    assert detect_scaffolds(body, body + "\n").warn_count == 0
    assert detect_scaffolds(None, body).warn_count == 1
    typed = "def f(x):\n    try:\n        return int(x)\n    except ValueError:\n        pass\n    return 0\n"
    assert detect_scaffolds(None, typed).warn_count == 0
    two = "def f(x):\n    try:\n        return int(x)\n    except:\n        return 1\n"
    assert detect_scaffolds(None, two).warn_count == 0


def test_abc_variants_and_metaclass() -> None:
    meta = "from abc import ABCMeta\nclass P(metaclass=ABCMeta):\n    def send(self):\n        \"\"\"Doc.\"\"\"\n"
    assert detect_scaffolds(None, meta).scaffold_count == 0
    dotted = "import abc\nclass P(abc.ABC):\n    @abc.abstractmethod\n    def send(self):\n        pass\n"
    assert detect_scaffolds(None, dotted).scaffold_count == 0
    generic = "import typing\nclass R(typing.Protocol[int]):\n    def read(self):\n        ...\n"
    assert detect_scaffolds(None, generic).scaffold_count == 0
    plain = "class P:\n    def send(self):\n        \"\"\"Doc.\"\"\"\n"
    assert detect_scaffolds(None, plain).scaffold_count == 1
    subscripted = "from typing import Generic, TypeVar\nT = TypeVar('T')\nclass G(Generic[T]):\n    def f(self):\n        pass\n"
    assert detect_scaffolds(None, subscripted).scaffold_count == 1


def test_test_double_name_rules() -> None:
    for name, flagged in (("Mock", True), ("Mock_", True), ("Fake2", True), ("StubX", True),
                          ("Mocker", False), ("Fakery", False), ("MyMock", False)):
        src = f"class {name}:\n    x = 1\n"
        assert (detect_scaffolds(None, src).scaffold_count == 1) is flagged, name


def test_unchanged_class_with_double_name_not_reflagged() -> None:
    src = "class MockGateway:\n    x = 1\n"
    assert detect_scaffolds(src, src).scaffold_count == 0


def test_metaclass_keyword_rules() -> None:
    # Only `metaclass=<Name|Attribute>` counts; a call-valued metaclass or another keyword does not.
    call_meta = "class P(metaclass=make_meta()):\n    def send(self):\n        \"\"\"Doc.\"\"\"\n"
    assert detect_scaffolds(None, call_meta).scaffold_count == 1
    other_kw = "class P(Base, kind=ABC):\n    def send(self):\n        \"\"\"Doc.\"\"\"\n"
    assert detect_scaffolds(None, other_kw).scaffold_count == 1


def test_type_error_message_for_non_str() -> None:
    with pytest.raises(TypeError, match="after_source must be str"):
        detect_scaffolds(None, b"def f():\n    return 1\n")  # type: ignore[arg-type]


def test_bare_except_finding_shape() -> None:
    src = "def f(x):\n    try:\n        return int(x)\n    except:\n        pass\n"
    r = detect_scaffolds(None, src)
    assert r.findings == (Finding("WARN_BARE_EXCEPT_PASS", 0, "<except>"),)


def test_is_not_implemented_boundaries() -> None:
    assert _is_not_implemented(ast.Pass()) is False
    assert _is_not_implemented(ast.Raise(exc=None)) is False
    assert _is_not_implemented(ast.Raise(exc=ast.Name(id="ValueError"))) is False
    assert _is_not_implemented(ast.Raise(exc=ast.Name(id="NotImplementedError"))) is True
    assert _is_not_implemented(ast.Raise(exc=ast.Call(func=ast.Name(id="NotImplementedError"), args=[], keywords=[]))) is True


def test_real_params_vararg_and_kwarg() -> None:
    tree1 = ast.parse("def f(self, *args): pass").body[0]
    assert _real_params(tree1) == 1
    tree2 = ast.parse("def f(cls, **kwargs): pass").body[0]
    assert _real_params(tree2) == 1
    tree3 = ast.parse("def f(self, x, *args, **kwargs): pass").body[0]
    assert _real_params(tree3) == 3

