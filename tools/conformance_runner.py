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
tools/conformance_runner.py — Standalone Conformance Runner for AEIB & MCP Test Vectors.

Purpose:
  Provides an independent execution entrypoint for external evaluators and auditors
  to execute the 30-vector MCP golden suite or individual vector files and produce
  canonical JSON reports offline.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

# Ensure repository root is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.mcp.idempotent_mcp_proxy import run_conformance_suite_vectors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AEIB Standalone Conformance Runner"
    )
    parser.add_argument(
        "--vectors",
        type=str,
        required=True,
        help="Path to vector JSON file or directory containing vector files.",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Path to write the output JSON report.",
    )
    parser.add_argument(
        "--db-dir",
        type=str,
        default=None,
        help="Optional directory for ephemeral SQLite databases.",
    )

    args = parser.parse_args()
    vectors_path = Path(args.vectors)

    if not vectors_path.exists():
        print(f"Error: Vector path not found: {vectors_path}", file=sys.stderr)
        return 1

    target_files = []
    if vectors_path.is_file():
        target_files.append(vectors_path)
    elif vectors_path.is_dir():
        # Search for mcp_idempotency vector files or json files
        json_files = sorted(vectors_path.glob("*.json"))
        target_files.extend(json_files)

    if not target_files:
        print(f"Error: No vector JSON files found in {vectors_path}", file=sys.stderr)
        return 1

    total_passed = 0
    total_vectors = 0
    all_reports = []

    db_dir = Path(args.db_dir) if args.db_dir else None

    for vf in target_files:
        print(f"[*] Evaluating conformance vectors from: {vf.name}")
        report = run_conformance_suite_vectors(vf, db_dir=db_dir)
        all_reports.append(report)
        total_passed += report.get("passed", 0)
        total_vectors += report.get("total", report.get("total_vectors", 0))

        for res in report.get("results", []):
            status = "PASS" if res.get("passed") else "FAIL"
            print(f"  [{status}] {res.get('vector_id')}: {res.get('name')}")

    pass_rate = (total_passed / total_vectors * 100.0) if total_vectors > 0 else 0.0
    print(f"\n[=] Conformance Evaluation Summary: {total_passed}/{total_vectors} passed ({pass_rate:.1f}%)")

    final_report = all_reports[0] if len(all_reports) == 1 else {
        "suite": "aggregate_conformance",
        "total_vectors": total_vectors,
        "passed": total_passed,
        "failed": total_vectors - total_passed,
        "pass_rate_pct": pass_rate,
        "reports": all_reports,
    }

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2)
        print(f"[+] Canonical report saved to: {report_path}")

    return 0 if (total_passed == total_vectors and total_vectors > 0) else 1


if __name__ == "__main__":
    sys.exit(main())
