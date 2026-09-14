#!/usr/bin/env python3
"""
AEIB v0.1 Scorer
Compares evaluated results against expected scorecards.
"""
import os
import sys
import json
from pathlib import Path

# Ensure project root is in sys.path for robust container execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runner.runner import evaluate_file

def main():
    fixtures_dir = Path("fixtures")
    expected_dir = Path("expected")

    fixture_files = sorted(fixtures_dir.glob("*.jsonl"))
    if not fixture_files:
        print("Error: No fixture files found.", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print("AEIB v0.1 REFERENCE BENCHMARK EXECUTION")
    print("Precedence: INVALID_INPUT -> MISSING_EVIDENCE -> CONFLICT -> REFUSED -> CONFIRMED -> UNKNOWN")
    print("=" * 80)
    print(f"{'Scenario':<35} | {'Disposition':<18} | {'Status'}")
    print("-" * 80)

    passed = 0
    total = len(fixture_files)

    for ff in fixture_files:
        sname = ff.stem
        res = evaluate_file(ff)
        disp = res["disposition"]

        exp_json = expected_dir / f"{sname}.json"
        exp_jsonl = expected_dir / f"{sname}.jsonl"

        expected_disp = None
        if exp_json.exists():
            d = json.loads(exp_json.read_text(encoding="utf-8"))
            expected_disp = d.get("disposition") or d.get("expected_verdict")
        elif exp_jsonl.exists():
            for line in exp_jsonl.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    expected_disp = d.get("disposition") or d.get("expected_verdict")
                    break

        status = "PASSED" if disp == expected_disp else "FAILED"
        if status == "PASSED":
            passed += 1
        print(f"{sname:<35} | {disp:<18} | {status}")

    print("=" * 80)
    print(f"Summary: Total: {total}, Passed: {passed}, Failed: {total - passed}")
    print("=" * 80)

    if passed == total and total > 0:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
