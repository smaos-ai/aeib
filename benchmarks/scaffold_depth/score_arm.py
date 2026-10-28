#!/usr/bin/env python3
"""
Scaffold-depth benchmark scorer (offline; makes no model calls).

Scores recorded candidate modules: arm_outputs/<arm>/<task_id>/rep<k>.py

For each candidate it
  1. verifies the hidden test + reference sha256 pins (a mismatch halts the whole run),
  2. copies the candidate (as <entry_module>.py) and its hidden test into a fresh temp dir and
     runs `sys.executable -I -m pytest -q` there with env={'HOME': tmp}, cwd=tmp and a timeout
     (process isolation, not a sandbox),
  3. runs src.scaffold_detector on the whole candidate (before=None).

Output: integer counts and integer basis points only; a run digest = sha256(encode_jcs(summary)).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from math import isqrt
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.jcs_canonicalizer import encode_jcs  # noqa: E402
from src.scaffold_detector import detect_scaffolds  # noqa: E402

TASK_DIR = Path(__file__).resolve().parent / "tasks"
DEFAULT_HIDDEN = Path(
    "/Users/andriileukhin/.gemini/antigravity/brain/5d79cd4e-030d-4b16-91b2-f9330b16dfda/scratch/scaffold_hidden"
)


class HiddenTestPinMismatch(RuntimeError):
    pass


def wilson_bps(successes: int, total: int) -> List[int]:
    """Wilson 95% interval (z=1.96) in integer basis points, computed with exact rationals."""
    if total <= 0:
        return [0, 0]
    z2 = Fraction(38416, 10000)
    n = Fraction(total)
    p = Fraction(successes, total)
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    rad_sq = z2 * (p * (1 - p) / n + z2 / (4 * n * n)) / (denom * denom)
    scale = 10 ** 12
    scaled = int(rad_sq * scale * scale)
    root = isqrt(scaled)
    if root * root < scaled:
        root += 1  # round the radius outward so the interval is never narrower than exact
    rad = Fraction(root, scale)
    low = max(Fraction(0), center - rad)
    high = min(Fraction(1), center + rad)
    low_bps = math.floor(low * 10000)
    high_bps = min(10000, math.ceil(high * 10000))
    return [low_bps, high_bps]


def load_tasks(task_dir: Path = TASK_DIR) -> Dict[str, Dict[str, Any]]:
    tasks = {}
    for p in sorted(task_dir.glob("*.json")):
        t = json.loads(p.read_text(encoding="utf-8"))
        tasks[t["id"]] = t
    if not tasks:
        raise FileNotFoundError(f"no tasks in {task_dir}")
    return tasks


def verify_pins(hidden_dir: Path, task_ids: List[str]) -> Dict[str, Any]:
    manifest = json.loads((hidden_dir / "manifest.json").read_text(encoding="utf-8"))
    for tid in task_ids:
        pins = manifest.get(tid)
        if pins is None:
            raise HiddenTestPinMismatch(f"no pin for {tid}")
        for kind in ("test", "reference"):
            data = (hidden_dir / f"{tid}_{kind}.py").read_bytes()
            if hashlib.sha256(data).hexdigest() != pins[f"{kind}_sha256"]:
                raise HiddenTestPinMismatch(f"{tid} {kind} sha256 mismatch")
    return manifest


def run_hidden_tests(candidate_source: str, task: Dict[str, Any], hidden_dir: Path,
                     timeout_s: float = 30.0) -> str:
    """Returns 'PASS', 'FAIL' or 'TIMEOUT'."""
    with tempfile.TemporaryDirectory(prefix="scaffold_eval_") as tmp:
        tmp_path = Path(tmp)
        (tmp_path / f"{task['entry_module']}.py").write_text(candidate_source, encoding="utf-8")
        shutil.copyfile(hidden_dir / f"{task['id']}_test.py", tmp_path / "test_hidden.py")
        try:
            res = subprocess.run(
                [sys.executable, "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_hidden.py"],
                cwd=tmp, env={"HOME": tmp}, capture_output=True, text=True, timeout=timeout_s, check=False,
            )
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
    return "PASS" if res.returncode == 0 else "FAIL"


def score_arm(arm_dir: Path, tasks: Dict[str, Dict[str, Any]], hidden_dir: Path) -> Dict[str, Any]:
    rows = []
    categories: Dict[str, int] = {}
    passed = total = scaffold_total = warn_total = syntax = timeouts = 0
    for tid in sorted(tasks):
        for cand in sorted((arm_dir / tid).glob("rep*.py")):
            src = cand.read_text(encoding="utf-8")
            outcome = run_hidden_tests(src, tasks[tid], hidden_dir)
            # before=None: every placeholder in the submitted module counts, including a starter
            # stub the candidate left in place (leaving the stub is not an implementation).
            det = detect_scaffolds(None, src)
            total += 1
            passed += outcome == "PASS"
            timeouts += outcome == "TIMEOUT"
            scaffold_total += det.scaffold_count
            warn_total += det.warn_count
            for f in det.findings:
                categories[f.category] = categories.get(f.category, 0) + 1
                syntax += f.category == "SYNTAX_ERROR"
            rows.append({"task": tid, "rep": cand.stem, "outcome": outcome,
                         "scaffold": det.scaffold_count, "warn": det.warn_count})
    return {
        "arm": arm_dir.name,
        "candidates": total,
        "hidden_pass": passed,
        "hidden_pass_bps": (passed * 10000 // total) if total else 0,
        "hidden_pass_wilson_bps": wilson_bps(passed, total),
        "scaffold_total": scaffold_total,
        "candidates_with_scaffold": sum(1 for r in rows if r["scaffold"] > 0),
        "warn_total": warn_total,
        "syntax_errors": syntax,
        "timeouts": timeouts,
        "scaffold_by_category": dict(sorted(categories.items())),
        "rows": rows,
    }


def score_all(arms_root: Path, hidden_dir: Path = DEFAULT_HIDDEN, task_dir: Path = TASK_DIR) -> Dict[str, Any]:
    tasks = load_tasks(task_dir)
    verify_pins(hidden_dir, sorted(tasks))
    arms = [score_arm(d, tasks, hidden_dir) for d in sorted(p for p in arms_root.iterdir() if p.is_dir())]
    summary = {"tasks": len(tasks), "arms": arms}
    summary["run_digest_sha256"] = hashlib.sha256(encode_jcs(summary)).hexdigest()
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arms_root", type=Path)
    ap.add_argument("--hidden-dir", type=Path, default=DEFAULT_HIDDEN)
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()
    summary = score_all(args.arms_root, args.hidden_dir)
    if args.json_out:
        args.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{'arm':36s} {'pass':>9s} {'Wilson95 (bps)':>16s} {'scaffolds':>9s} {'w/ scaffold':>11s} {'warn':>5s} {'syntax':>6s}")
    for a in summary["arms"]:
        print(f"{a['arm']:36s} {a['hidden_pass']:>4d}/{a['candidates']:<4d} {str(a['hidden_pass_wilson_bps']):>16s} "
              f"{a['scaffold_total']:>9d} {a['candidates_with_scaffold']:>11d} {a['warn_total']:>5d} {a['syntax_errors']:>6d}")
    print(f"run_digest_sha256={summary['run_digest_sha256']}")


if __name__ == "__main__":
    main()
