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
tests/test_vaf_mutation_gate.py — Test suite for Automated Mutation Testing Gate.

Verifies:
1. All 10 synthetic architectural mutants are detected and killed (100% kill rate).
2. The gate dispositions as PASS when 0 mutants survive.
3. Negative control: A surviving mutant correctly causes the gate to fail closed with FAIL.
4. CLI self-test execution exits with code 0.
5. Epistemic boundary compliance (zero banned words).
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.vaf_mutation_gate import MutantDef, VafMutationGate


def test_mutation_gate_all_mutants_killed():
    """Evaluates the full mutation gate across all 10 synthetic mutants."""
    gate = VafMutationGate()
    report = gate.run_all()

    assert report.total_mutants == 10
    assert report.mutants_killed == 10
    assert report.mutants_survived == 0
    assert report.mutation_score_pct == 100.0
    assert report.gate_disposition == "PASS"
    assert len(report.report_sha256) == 64

    # Every mutant must have a concrete killing vector or probe
    for res in report.results:
        assert res["status"] == "KILLED"
        assert res["killed_by_test"] is not None
        assert res["evaluation_latency_ms"] >= 0.0


def test_mutation_gate_cli_self_test():
    """Verifies CLI execution of tools/vaf_mutation_gate.py --self-test."""
    cmd = [sys.executable, str(REPO_ROOT / "tools" / "vaf_mutation_gate.py"), "--self-test"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "MUTATION TESTING GATE REPORT" in proc.stdout
    assert "Mutation Score:  100.0%" in proc.stdout
    assert "Disposition:     PASS" in proc.stdout


def test_negative_control_surviving_mutant_fails_gate(tmp_path: Path):
    """
    Non-tautological test: If a mutant survives (e.g. no vectors and no probe detect it),
    the gate MUST disposition as FAIL and report mutants_survived > 0.
    """
    # Create an empty vectors directory with no test vectors
    empty_vectors_dir = tmp_path / "empty_vectors"
    empty_vectors_dir.mkdir(parents=True, exist_ok=True)

    gate = VafMutationGate(vectors_dir=empty_vectors_dir)
    # Inject a ghost mutant that does not alter any observable behavior
    ghost_mutant = MutantDef(
        mutant_id="MUTANT_GHOST_INERT_DEFECT",
        category="INERT_NOOP",
        description="A completely inert mutation that alters nothing",
        target_component="none",
    )
    gate.mutants = [ghost_mutant]

    report = gate.run_all()
    assert report.total_mutants == 1
    assert report.mutants_killed == 0
    assert report.mutants_survived == 1
    assert report.mutation_score_pct == 0.0
    assert report.gate_disposition == "FAIL"


def test_epistemic_purity():
    """Scans tools/vaf_mutation_gate.py and this test file for banned words."""
    banned = [
        "guaran" + "teed",
        "guaran" + "tee",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
    ]
    files_to_check = [
        REPO_ROOT / "tools" / "vaf_mutation_gate.py",
        REPO_ROOT / "tests" / "test_vaf_mutation_gate.py",
    ]
    for fpath in files_to_check:
        content = fpath.read_text(encoding="utf-8").lower()
        for b in banned:
            assert b not in content, f"Banned word '{b}' found in {fpath.name}"
