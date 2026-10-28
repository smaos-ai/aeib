#!/usr/bin/env python3
"""Controls for the scaffold-depth scorer (benchmarks/scaffold_depth/score_arm.py).

Positive control: arms built from the hidden reference solutions must pass every hidden test with
0 scaffolds. Negative control: arms built from the starter sources must fail every hidden test.
Integrity: a tampered hidden test halts the run. Determinism: the same inputs give the same digest.
Skipped (with a reason) when the hidden-test directory is not present on this machine."""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("score_arm", REPO / "benchmarks" / "scaffold_depth" / "score_arm.py")
score_arm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(score_arm)  # loads the repo's own scorer module (trusted code, not a candidate)

HIDDEN = score_arm.DEFAULT_HIDDEN
pytestmark = pytest.mark.skipif(not (HIDDEN / "manifest.json").exists(),
                                reason="hidden tests live outside the repo and are absent on this machine")


def _build_arms(root: Path) -> None:
    tasks = score_arm.load_tasks()
    for tid, t in tasks.items():
        ref = root / "A_reference" / tid
        stub = root / "B_starter" / tid
        ref.mkdir(parents=True)
        stub.mkdir(parents=True)
        shutil.copyfile(HIDDEN / f"{tid}_reference.py", ref / "rep1.py")
        (stub / "rep1.py").write_text(t["starter_source"], encoding="utf-8")


def test_reference_passes_and_starter_fails_every_task(tmp_path: Path) -> None:
    _build_arms(tmp_path)
    summary = score_arm.score_all(tmp_path)
    ref, stub = summary["arms"]
    n = summary["tasks"]
    assert n >= 20
    assert (ref["arm"], ref["candidates"], ref["hidden_pass"], ref["scaffold_total"]) == ("A_reference", n, n, 0)
    assert ref["hidden_pass_bps"] == 10000 and ref["timeouts"] == 0 and ref["syntax_errors"] == 0
    assert (stub["candidates"], stub["hidden_pass"]) == (n, 0)
    assert stub["scaffold_total"] > 0
    assert stub["candidates_with_scaffold"] < n  # bugfix/refactor starters are real (wrong) code
    assert all(r["outcome"] == "FAIL" for r in stub["rows"])
    # determinism
    assert score_arm.score_all(tmp_path)["run_digest_sha256"] == summary["run_digest_sha256"]


def test_tampered_hidden_test_halts(tmp_path: Path) -> None:
    hidden_copy = tmp_path / "hidden"
    shutil.copytree(HIDDEN, hidden_copy)
    victim = sorted(hidden_copy.glob("*_test.py"))[0]
    victim.write_text(victim.read_text() + "\n# weakened\n")
    arms = tmp_path / "arms"
    arms.mkdir()
    with pytest.raises(score_arm.HiddenTestPinMismatch):
        score_arm.score_all(arms, hidden_dir=hidden_copy)


def test_missing_pin_and_reference_tamper_halt(tmp_path: Path) -> None:
    hidden_copy = tmp_path / "hidden"
    shutil.copytree(HIDDEN, hidden_copy)
    ref = sorted(hidden_copy.glob("*_reference.py"))[0]
    ref.write_text(ref.read_text() + "\n")
    with pytest.raises(score_arm.HiddenTestPinMismatch):
        score_arm.verify_pins(hidden_copy, [ref.name.replace("_reference.py", "")])
    with pytest.raises(score_arm.HiddenTestPinMismatch):
        score_arm.verify_pins(HIDDEN, ["no_such_task"])


def test_wilson_bps_known_values() -> None:
    assert score_arm.wilson_bps(0, 0) == [0, 0]
    assert score_arm.wilson_bps(0, 50) == [0, 714]
    assert score_arm.wilson_bps(50, 50) == [9286, 10000]
    low, high = score_arm.wilson_bps(10, 20)
    assert low < 5000 < high
