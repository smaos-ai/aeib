#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# tests/test_contextcart_paired_benchmark.py
#
# Epistemic notice: Evaluated and tested under the stated local verification model.

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.contextcart_paired_benchmark import (
    run_paired_workload_benchmark,
    test_paired_workload_benchmark_honest_reporting,
)


def test_contextcart_paired_benchmark_execution():
    test_paired_workload_benchmark_honest_reporting()
    report = run_paired_workload_benchmark()
    assert report["total_workloads"] == 3
    assert report["exact_answer_checks_passed"] == "3/3"
    assert report["overall_input_token_reduction_pct"] > 70.0
