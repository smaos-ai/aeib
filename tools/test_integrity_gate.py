#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
tools/test_integrity_gate.py
================================================================================
CLI Gate enforcing SHA-256 test-suite immutability (ImpossibleBench defense).

Evaluated under the stated model:
Prevents agent reward-hacking by verifying that the active test files match
a frozen pre-flight baseline manifest unless authorized by a signed warrant.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.evidence_carrying_termination import TestSuiteHashLock, TestModificationWarrant


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Enforce test-suite integrity manifest.")
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=REPO_ROOT / "tests",
        help="Path to tests directory.",
    )
    parser.add_argument(
        "--dump-manifest",
        type=Path,
        help="Dump current test suite manifest JSON to file.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Path to baseline manifest JSON to verify against.",
    )
    parser.add_argument(
        "--warrant",
        type=Path,
        help="Optional path to signed TestModificationWarrant JSON.",
    )

    args = parser.parse_args(argv)

    if args.dump_manifest:
        manifest = TestSuiteHashLock.compute_manifest(args.tests_dir)
        args.dump_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.dump_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        digest = TestSuiteHashLock.compute_manifest_digest(manifest)
        print(f"[test-integrity] Dumped {len(manifest)} test files; Merkle digest: {digest}")
        return 0

    if args.baseline:
        if not args.baseline.exists():
            print(f"[test-integrity] ERROR: Baseline manifest not found: {args.baseline}", file=sys.stderr)
            return 2

        baseline_manifest = json.loads(args.baseline.read_text())
        warrant: Optional[TestModificationWarrant] = None
        if args.warrant:
            w_data = json.loads(args.warrant.read_text())
            warrant = TestModificationWarrant(
                warrant_id=w_data["warrant_id"],
                authorized_test_paths=tuple(w_data["authorized_test_paths"]),
                justification=w_data["justification"],
                issuer_public_key_hex=w_data["issuer_public_key_hex"],
                signature_hex=w_data["signature_hex"],
            )

        ok, msg = TestSuiteHashLock.verify_integrity(args.tests_dir, baseline_manifest, warrant)
        if not ok:
            print(f"[test-integrity] REJECTED: {msg}", file=sys.stderr)
            return 1

        print(f"[test-integrity] PASSED: {msg}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
