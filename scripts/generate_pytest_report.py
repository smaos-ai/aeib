#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
scripts/generate_pytest_report.py — Generates Canonical pytest JSON Report.

Executes declared pytest suites and emits deterministic JSON report conforming
to release archive specifications.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import sys
import pytest

TEST_FILES = [
    "tests/test_dst_multi_region_partition.py",
    "tests/test_contextcart_20_tasks.py",
    "tests/test_postgres_tcc_concurrency_stress.py",
    "tests/test_secure_mcp_uds_boundary.py",
    "tests/test_dynamic_code_policy_gate.py",
    "tests/test_governed_cross_model_handoff.py",
    "tests/test_audit_disproving_verifier.py",
    "tests/test_ncm_parallel_burst_latch.py",
    "tests/test_artemis_device_and_plugin_boundary.py",
    "tests/test_predictive_trajectory_drift_latch.py",
    "tests/test_zk_budget_proof_engine.py",
    "tests/test_standalone_offline_verifier.py",
    "tests/test_bpf_lsm_profile_compiler.py",
]


class DeterministicJsonReporter:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            outcome = report.outcome
            if outcome == "passed":
                self.passed += 1
            elif outcome == "failed":
                self.failed += 1
            elif outcome == "skipped":
                self.skipped += 1

            self.results.append({
                "nodeid": report.nodeid,
                "outcome": outcome,
                "duration_seconds": round(report.duration, 4),
            })


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate pytest JSON Report")
    parser.add_argument("--output", "-o", type=str, default="output/pytest-report.json")
    args = parser.parse_args()

    reporter = DeterministicJsonReporter()
    pytest_args = ["-q"] + TEST_FILES

    print(f"[*] Running pytest on {len(TEST_FILES)} declared test files...")
    exit_code = pytest.main(pytest_args, plugins=[reporter])

    total = reporter.passed + reporter.failed + reporter.skipped
    report_data = {
        "suite": "aeib_declared_test_set",
        "timestamp_utc": "2026-10-21T00:00:00Z",
        "total_collected": total,
        "passed": reporter.passed,
        "failed": reporter.failed,
        "skipped": reporter.skipped,
        "pass_rate_pct": round((reporter.passed / total * 100.0) if total > 0 else 0.0, 2),
        "test_files": TEST_FILES,
        "tests": reporter.results,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"[+] pytest report generated: {out_path} ({reporter.passed}/{total} passed)")
    return 0 if (reporter.failed == 0 and reporter.passed == 149) else 1


if __name__ == "__main__":
    sys.exit(main())
