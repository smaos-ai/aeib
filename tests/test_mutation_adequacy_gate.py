#!/usr/bin/env python3
"""
Tests for tools/mutation_adequacy_gate.py.

Uses a tiny real fixture package (written to a temp repo root) with:
  - a STRONG test file that checks exact behaviour (should kill mutants), and
  - a WEAK test file that only checks the function runs (mutants should survive).
No mocks: every mutant is executed through a real pytest subprocess.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.mutation_adequacy_gate import (  # noqa: E402
    STATUS_KILLED,
    STATUS_SURVIVED,
    apply_mutation,
    enumerate_mutation_sites,
    run_mutation_adequacy,
)

FIXTURE_SRC = textwrap.dedent(
    '''
    """Fixture module under mutation."""


    def clamp_budget(spent, ceiling):
        if spent < 0:
            raise ValueError("negative spend")
        if spent > ceiling:
            return ceiling
        return spent


    def is_retry_allowed(latched, committed):
        return not latched and not committed
    '''
).lstrip()

STRONG_TESTS = textwrap.dedent(
    '''
    import pytest
    from src.fixture_budget import clamp_budget, is_retry_allowed


    def test_clamp_exact():
        assert clamp_budget(5, 10) == 5
        assert clamp_budget(10, 10) == 10
        assert clamp_budget(11, 10) == 10
        assert clamp_budget(0, 10) == 0


    def test_negative_rejected():
        with pytest.raises(ValueError):
            clamp_budget(-1, 10)


    def test_retry_matrix():
        assert is_retry_allowed(False, False) is True
        assert is_retry_allowed(True, False) is False
        assert is_retry_allowed(False, True) is False
        assert is_retry_allowed(True, True) is False
    '''
).lstrip()

WEAK_TESTS = textwrap.dedent(
    '''
    from src.fixture_budget import clamp_budget, is_retry_allowed


    def test_runs():
        clamp_budget(5, 10)
        is_retry_allowed(False, False)
    '''
).lstrip()


def _make_fixture_repo(root: Path) -> None:
    (root / "src").mkdir()
    (root / "src" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "fixture_budget.py").write_text(FIXTURE_SRC, encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_strong.py").write_text(STRONG_TESTS, encoding="utf-8")
    (root / "tests" / "test_weak.py").write_text(WEAK_TESTS, encoding="utf-8")


def test_enumerates_expected_operator_classes() -> None:
    sites = enumerate_mutation_sites(FIXTURE_SRC)
    operators = {s.operator for s in sites}
    assert {"CMP_FLIP", "RETURN_NONE", "RAISE_DROP", "NOT_DROP", "BOOL_SWAP"} <= operators
    # Docstring constant must not be a mutation site
    assert all(s.lineno != 1 for s in sites if s.operator == "CONST_PERTURB")


def test_apply_mutation_changes_behaviour_text() -> None:
    sites = enumerate_mutation_sites(FIXTURE_SRC)
    cmp_site = next(s for s in sites if s.operator == "CMP_FLIP")
    mutated = apply_mutation(FIXTURE_SRC, cmp_site)
    assert mutated != FIXTURE_SRC
    compile(mutated, "fixture", "exec")
    raise_site = next(s for s in sites if s.operator == "RAISE_DROP")
    assert "raise ValueError" not in apply_mutation(FIXTURE_SRC, raise_site)


def test_strong_suite_kills_all_and_weak_suite_leaves_survivors(tmp_path: Path) -> None:
    _make_fixture_repo(tmp_path)
    strong = run_mutation_adequacy(
        target_rel="src/fixture_budget.py",
        test_files=["tests/test_strong.py"],
        max_mutants=50,
        seed=7,
        per_mutant_timeout_s=60.0,
        repo_root=tmp_path,
    )
    weak = run_mutation_adequacy(
        target_rel="src/fixture_budget.py",
        test_files=["tests/test_weak.py"],
        max_mutants=50,
        seed=7,
        per_mutant_timeout_s=60.0,
        repo_root=tmp_path,
    )
    assert strong.baseline_suite_passed and weak.baseline_suite_passed
    assert strong.mutants_sampled == weak.mutants_sampled == strong.sites_enumerated
    assert strong.survived == 0, [o.site for o in strong.outcomes if o.status == STATUS_SURVIVED]
    assert strong.killed > 0
    assert weak.survived > 0
    assert weak.kill_ratio() < strong.kill_ratio()
    # Survivors carry concrete line numbers for a targeted follow-up test
    assert all(site.lineno > 0 for site in weak.survivors())
    # The real fixture file on disk is never modified by the experiment
    assert (tmp_path / "src" / "fixture_budget.py").read_text(encoding="utf-8") == FIXTURE_SRC
    assert any(o.status == STATUS_KILLED for o in strong.outcomes)


def test_failing_baseline_is_reported_not_scored(tmp_path: Path) -> None:
    _make_fixture_repo(tmp_path)
    (tmp_path / "tests" / "test_broken.py").write_text(
        "def test_broken():\n    assert 1 == 2\n", encoding="utf-8"
    )
    report = run_mutation_adequacy(
        target_rel="src/fixture_budget.py",
        test_files=["tests/test_broken.py"],
        max_mutants=5,
        seed=1,
        per_mutant_timeout_s=60.0,
        repo_root=tmp_path,
    )
    assert report.baseline_suite_passed is False
    assert report.kill_ratio() is None
    assert report.outcomes == []


def test_epistemic_language_purity() -> None:
    banned = [
        "guarant" + "eed", "bullet" + "proof", "enterprise-" + "grade",
        "production-" + "safe", "100% " + "secure", "proven universal" + "ly",
        "production-" + "ready",
    ]
    for rel in ("tools/mutation_adequacy_gate.py", "tests/test_mutation_adequacy_gate.py"):
        text = (_REPO_ROOT / rel).read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in text, f"{word} in {rel}"


def test_explicit_return_none_is_not_a_mutation_site() -> None:
    """`return None` -> `return None` is equivalent by construction. The tool must not
    sample it; otherwise authors are pushed to restyle code (bare `return`) to dodge it."""
    src = "def f(x):\n    if x:\n        return None\n    return x\n"
    sites = [s for s in enumerate_mutation_sites(src) if s.operator == "RETURN_NONE"]
    assert [s.lineno for s in sites] == [4]
    bare = "def f(x):\n    if x:\n        return\n    return x\n"
    assert [s.lineno for s in enumerate_mutation_sites(bare) if s.operator == "RETURN_NONE"] == [4]
