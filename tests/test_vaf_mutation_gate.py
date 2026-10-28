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

import tools.vaf_mutation_gate as vmg_mod
from tools.vaf_mutation_gate import AEIBStation1Gate, MutantDef, VafMutationGate


def test_mutated_gates_and_probes_exact_boundaries(tmp_path: Path):
    """Verifies exact boundary constants inside _create_mutated_gate and _probe_mutated_gate."""
    vg = VafMutationGate()

    # 1. MUTANT_02 probe escrows exact base_valid amount_minor == 1000
    g2 = vg._create_mutated_gate("MUTANT_02_DISABLE_ADDITIONAL_PROPERTIES_CHECK")
    killed2, name2, _ = vg._probe_mutated_gate("MUTANT_02_DISABLE_ADDITIONAL_PROPERTIES_CHECK", g2)
    assert killed2 is True
    assert name2 == "probe:additional_properties_injection"
    assert g2.escrowed_spend_minor == 10 * 100

    # 2. MUTANT_03 ceiling is exactly 10**15 (10**15 + 1 exceeds it)
    g3 = vg._create_mutated_gate("MUTANT_03_BYPASS_SPRINT_BUDGET_CEILING")
    valid_vec = json.loads((REPO_ROOT / "conformance" / "vectors" / "act-valid-nominal-001.json").read_text())["input_payload"]
    over_10_15 = json.loads(json.dumps(valid_vec))
    over_10_15["constraints"]["amount_minor"] = 10 ** (3 * 5) + 1
    over_10_15["constraints"]["max_per_call_minor"] = 10 ** (3 * 5) + 1
    res3 = g3.evaluate_raw_payload(json.dumps(over_10_15).encode("utf-8"))
    assert res3["error_code"] == "ERR_SPRINT_BUDGET_EXCEEDED"

    # 3. Inspect transformed payloads for MUTANT_04, MUTANT_08, MUTANT_10
    recorded_decoded = []
    orig_eval = AEIBStation1Gate.evaluate_raw_payload

    def spy_eval(self_obj, raw_bytes: bytes):
        try:
            recorded_decoded.append(json.loads(raw_bytes.decode("utf-8")))
        except Exception:
            recorded_decoded.append(raw_bytes)
        return orig_eval(self_obj, raw_bytes)

    try:
        AEIBStation1Gate.evaluate_raw_payload = spy_eval
        g4 = vg._create_mutated_gate("MUTANT_04_BYPASS_MAX_PER_CALL_LIMIT")
        g4.evaluate_raw_payload(b'{"constraints":{}}')
        assert recorded_decoded[-1]["constraints"]["max_per_call_minor"] == 1

        g8 = vg._create_mutated_gate("MUTANT_08_ALLOW_NEGATIVE_OR_ZERO_AMOUNTS")
        g8.evaluate_raw_payload(b'{"constraints":{"amount_minor":0}}')
        assert recorded_decoded[-1]["constraints"]["amount_minor"] == 10 * 10

        g10 = vg._create_mutated_gate("MUTANT_10_ALLOW_PAST_EXPIRES_AT")
        boundary_ts = 17 * 10**8
        g10.evaluate_raw_payload(json.dumps({"constraints": {"expires_at": boundary_ts}}).encode("utf-8"))
        assert recorded_decoded[-1]["constraints"]["expires_at"] == boundary_ts

        class _NonDictConstraints:
            def __init__(self) -> None:
                self.expires_at = 100

            def get(self, _k: str, _default: int = 0) -> int:
                return self.expires_at

            def __setitem__(self, _k: str, v: int) -> None:
                self.expires_at = v

        non_dict = _NonDictConstraints()
        orig_loads = vmg_mod.json.loads
        try:
            vmg_mod.json.loads = lambda _s: {"constraints": non_dict}
            g10.evaluate_raw_payload(b"{}")
        finally:
            vmg_mod.json.loads = orig_loads
        assert non_dict.expires_at == 10 * 10
    finally:
        AEIBStation1Gate.evaluate_raw_payload = orig_eval

    killed10, name10, _ = vg._probe_mutated_gate("MUTANT_10_ALLOW_PAST_EXPIRES_AT", g10)
    assert killed10 is True
    assert name10 == "probe:past_timestamp"
    assert vg._probe_mutated_gate("MUTANT_UNKNOWN", g10) == (False, None, None)

    # 4. Inspect MUTANT_08 probe negative amount (-500)
    probe_inputs = []

    class _ProbeRecorderGate:
        def evaluate_raw_payload(self, raw_bytes: bytes):
            probe_inputs.append(json.loads(raw_bytes.decode("utf-8")))
            return {"error_code": "BYPASSED"}

    killed8, name8, _ = vg._probe_mutated_gate("MUTANT_08_ALLOW_NEGATIVE_OR_ZERO_AMOUNTS", _ProbeRecorderGate())  # type: ignore[arg-type]
    assert killed8 is True
    assert name8 == "probe:negative_amount_minor"
    assert probe_inputs[0]["constraints"]["amount_minor"] == -(5 * 100)

    # 5. Empty mutants list (total == 0) and SURVIVED 3-decimal latency rounding
    empty_dir = tmp_path / "empty_vecs"
    empty_dir.mkdir(exist_ok=True)
    vg_empty = VafMutationGate(vectors_dir=empty_dir)
    vg_empty.mutants = []
    rep_zero = vg_empty.run_all()
    assert rep_zero.total_mutants == 0
    assert rep_zero.mutation_score_pct == 0.0

    ticks = iter([10.0, 10.00123456])
    orig_pc = vmg_mod.time.perf_counter
    try:
        vmg_mod.time.perf_counter = lambda: next(ticks)
        ghost = MutantDef("GHOST", "CAT", "DESC", "NONE")
        res_surv = vg_empty.evaluate_mutant(ghost)
    finally:
        vmg_mod.time.perf_counter = orig_pc
    assert res_surv.status == "SURVIVED"
    assert res_surv.evaluation_latency_ms == 1.235


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
