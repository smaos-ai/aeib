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
tests/test_aeib_dst_harness.py
================================================================================
Test Suite for AEIB Protocol-Aware Deterministic Simulation Testing (DST) Harness.

Verifies:
1. Clean 10,000-schedule simulation under seed 20261020:
   - 0 duplicate mutations
   - 0 invariant violations across all 7 invariants (I1–I7)
2. Negative control falsification:
   - Injecting unlatched retry causes harness to detect I2 / I3 violation
   - Injecting budget leakage causes harness to detect I1 violation
3. Deterministic reproducibility: identical seeds produce identical reports
4. Full CLI execution with structured JSON export

Evaluated under the stated model. Zero-mock AST purity enforced.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.aeib_dst_harness import AeibDstEngine, FaultSchedule


def test_dst_10000_schedules_zero_invariant_violations() -> None:
    """Verifies 10,000 pseudo-random schedules with zero invariant violations."""
    engine = AeibDstEngine(seed=20261020)
    report = engine.run_simulation(schedules=10000, fail_fast=True)

    assert report.is_clean, (
        f"DST reported invariant violations: {report.invariant_violations}"
    )
    assert report.schedules_evaluated == 10000
    assert report.observed_duplicates == 0
    assert report.total_timeouts > 0
    assert report.total_retries_blocked == report.total_timeouts
    assert report.total_reconciled > 0

    # Explicit check for all 7 invariants
    for inv, count in report.invariant_violations.items():
        assert count == 0, f"Invariant {inv} had {count} violations!"


def test_dst_negative_control_catches_unlatched_retry_duplicate() -> None:
    """Falsification test: buggy gate allowing retry must be caught by DST harness."""
    engine = AeibDstEngine(seed=42, bug_mode="BYPASS_LATCH_ON_RETRY")
    report = engine.run_simulation(schedules=500, fail_fast=True)

    assert not report.is_clean, "Harness failed to detect injected duplicate retry bug"
    assert report.invariant_violations["I2_zero_duplicate_mutations"] > 0
    assert report.observed_duplicates > 0
    assert report.first_failure_detail is not None
    assert report.first_failure_detail["invariant"] == "I2_zero_duplicate_mutations"


def test_dst_negative_control_catches_budget_leak() -> None:
    """Falsification test: budget leakage must be caught by DST harness."""
    engine = AeibDstEngine(seed=42, bug_mode="LEAK_BUDGET")
    report = engine.run_simulation(schedules=500, fail_fast=True)

    assert not report.is_clean, "Harness failed to detect injected budget leak"
    assert report.invariant_violations["I1_budget_conservation"] > 0
    assert report.first_failure_detail is not None
    assert report.first_failure_detail["invariant"] == "I1_budget_conservation"


def test_dst_deterministic_reproducibility() -> None:
    """Verifies that identical seeds produce bit-identical simulation trajectories."""
    engine1 = AeibDstEngine(seed=99991)
    report1 = engine1.run_simulation(schedules=1000, fail_fast=True)

    engine2 = AeibDstEngine(seed=99991)
    report2 = engine2.run_simulation(schedules=1000, fail_fast=True)

    assert report1.schedules_evaluated == report2.schedules_evaluated
    assert report1.total_dispatches == report2.total_dispatches
    assert report1.total_timeouts == report2.total_timeouts
    assert report1.total_retries_blocked == report2.total_retries_blocked
    assert report1.total_reconciled == report2.total_reconciled
    assert report1.observed_duplicates == report2.observed_duplicates
    assert report1.invariant_violations == report2.invariant_violations


def test_dst_cli_execution_with_json_output(tmp_path: Path) -> None:
    """Verifies the CLI interface and JSON output format."""
    out_json = tmp_path / "dst_report.json"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "aeib_dst_harness.py"),
        "--schedules",
        "1000",
        "--seed",
        "20261020",
        "--output-json",
        str(out_json),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"CLI exited with error: {result.stderr}"

    assert out_json.exists()
    with open(out_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["status"] == "PASS"
    assert data["schedules_evaluated"] == 1000
    assert data["observed_duplicates"] == 0
    assert data["invariant_violations"]["I1_budget_conservation"] == 0
    assert data["invariant_violations"]["I2_zero_duplicate_mutations"] == 0


def test_dst_simulator_gate_and_cli_exhaustive_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercises ProtocolAwareDstSimulator, run_dst_campaign, VirtualSettlementTarget, DstStation1Gate, and main()."""
    import base64
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from tools.aeib_dst_harness import (
        DeterministicSteppedClock,
        DstStation1Gate,
        ProtocolAwareDstSimulator,
        VirtualSettlementTarget,
        main as dst_main,
        run_dst_campaign,
        test_dst_harness_1000_schedules_in_pytest,
    )

    # 1. ProtocolAwareDstSimulator unit branches
    sim = ProtocolAwareDstSimulator(ceiling_minor=5_000)
    assert sim.step_dispatch("op-skew", 100, 1000, sim.PINNED_IBAN, sim.PINNED_IBAN, 0, sim.clock_sec + 6) == "REJECTED_CLOCK_SKEW"
    assert sim.step_dispatch("op-payee", 100, 1000, sim.PINNED_IBAN, "iban:OTHER", 0, sim.clock_sec) == "ERR_SIGNATURE_OR_PAYEE_MISMATCH"
    assert sim.step_dispatch("op-zero", 0, 1000, sim.PINNED_IBAN, sim.PINNED_IBAN, 0, sim.clock_sec) == "ERR_DELEGATION_ATTENUATION_BREACH"
    assert sim.step_dispatch("op-overcall", 1001, 1000, sim.PINNED_IBAN, sim.PINNED_IBAN, 0, sim.clock_sec) == "ERR_DELEGATION_ATTENUATION_BREACH"
    assert sim.step_dispatch("op-taint", 100, 1000, "iban:OTHER", "iban:OTHER", 2, sim.clock_sec) == "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP"

    # Valid dispatch
    assert sim.step_dispatch("op-1", 1000, 2000, sim.PINNED_IBAN, sim.PINNED_IBAN, 0, sim.clock_sec) == "DISPATCHED"
    assert sim.local_seq == 1
    assert sim.scitt_anchored_seq == 1
    assert sim.escrowed_minor == 1000
    assert sim.step_dispatch("op-1", 1000, 2000, sim.PINNED_IBAN, sim.PINNED_IBAN, 0, sim.clock_sec) == "REJECTED_DUPLICATE_OPERATION_ID"
    assert sim.step_dispatch("op-sprint", 4001, 5000, sim.PINNED_IBAN, sim.PINNED_IBAN, 0, sim.clock_sec) == "HALT_SPRINT_LIMIT_EXCEEDED"

    # Unknown op ignored
    assert sim.step_transport_outcome("op-unknown", "CONFIRMED") == "IGNORED"

    # Indeterminate outcome and blind retry halt
    assert sim.step_transport_outcome("op-1", "EFFECT_INDETERMINATE") == "EFFECT_INDETERMINATE"
    assert sim.ops["op-1"].disposition == "EFFECT_INDETERMINATE"
    assert sim.local_seq == 2
    assert sim.step_dispatch("op-1", 1000, 2000, sim.PINNED_IBAN, sim.PINNED_IBAN, 0, sim.clock_sec) == "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY"

    # Confirm op-1, idempotent re-confirm, and contradiction halt
    assert sim.step_transport_outcome("op-1", "CONFIRMED") == "CONFIRMED"
    assert sim.escrowed_minor == 0
    assert sim.settled_minor == 1000
    assert sim.step_transport_outcome("op-1", "CONFIRMED") == "CONFIRMED"

    # Refuted outcome on op-2
    assert sim.step_dispatch("op-2", 500, 1000, sim.PINNED_IBAN, sim.PINNED_IBAN, 2, sim.clock_sec) == "DISPATCHED"
    assert sim.step_transport_outcome("op-2", "REFUTED") == "REFUTED"
    assert sim.escrowed_minor == 0
    assert sim.settled_minor == 1000
    sim.assert_invariants_i1_to_i7(1)

    # Contradiction on terminal op-1
    assert sim.step_transport_outcome("op-1", "REFUTED") == "TERMINAL"
    assert sim.halted_reason == "HALT_TARGET_CONTRADICTION"
    assert sim.step_transport_outcome("op-2", "CONFIRMED") == "IGNORED"
    assert sim.step_dispatch("op-3", 100, 1000, sim.PINNED_IBAN, sim.PINNED_IBAN, 0, sim.clock_sec) == "HALT_TARGET_CONTRADICTION"

    # Two-file wipe detection and I3 invariant assertion
    sim_wipe = ProtocolAwareDstSimulator(ceiling_minor=5_000)
    sim_wipe.step_dispatch("op-w", 100, 1000, sim_wipe.PINNED_IBAN, sim_wipe.PINNED_IBAN, 0, sim_wipe.clock_sec)
    sim_wipe.step_inject_two_file_wipe_and_reboot()
    assert sim_wipe.local_seq == 0
    assert sim_wipe.scitt_anchored_seq == 1
    assert sim_wipe.halted_reason == "HALT_TWO_FILE_WIPE_DETECTED_AGAINST_SCITT_ANCHOR"
    sim_wipe.assert_invariants_i1_to_i7(2)

    sim_wipe.halted_reason = None
    with pytest.raises(AssertionError, match="I3 continuity wipe not halted"):
        sim_wipe.assert_invariants_i1_to_i7(2)

    # 2. run_dst_campaign and test_dst_harness_1000_schedules_in_pytest
    test_dst_harness_1000_schedules_in_pytest()
    camp = run_dst_campaign(schedules=50, master_seed=20261020)
    assert camp["schedules_executed"] == 50
    assert camp["invariant_violations"] == 0
    assert camp["total_settled_minor"] == 54458
    assert camp["total_escrowed_minor"] > 0

    # 3. VirtualSettlementTarget & DstStation1Gate direct branches
    target = VirtualSettlementTarget()
    assert target.total_received_requests == 0
    assert target.query_status("c-none") == "UNKNOWN"
    assert target.get_commit_count("c-none") == 0
    assert target.execute_mutation("c-1", {"x": 1}) is True
    assert target.total_received_requests == 1
    assert target.query_status("c-1") == "CONFIRMED"
    assert target.execute_mutation("c-1", {"x": 1}) is True
    assert target.get_commit_count("c-1") == 2
    target.mark_refuted("c-ref")
    assert target.query_status("c-ref") == "REFUTED"

    clock = DeterministicSteppedClock(1000)
    assert clock.advance_ms(500) == 1500
    g_priv = ed25519.Ed25519PrivateKey.generate()
    t_priv = ed25519.Ed25519PrivateKey.generate()
    gate = DstStation1Gate(
        sponsor_ceiling_minor=10000,
        sprint_limit_minor=2500,
        trust_anchors={"iban:DE89370400440532013000": b"k"},
        gate_privkey=g_priv,
        clock=clock,
    )
    assert gate.reconcile_outcome("nonexistent", "CONFIRMED") is False

    op_id = "op-g1"
    caid = gate.compute_caid(op_id, 500, "iban:DE89370400440532013000", "POST /v1", "sha256:00")
    ok, mask, _ = gate.evaluate_and_reserve(
        op_id=op_id,
        amount_minor=500,
        payee_id="iban:DE89370400440532013000",
        endpoint="POST /v1",
        payload_digest="sha256:00",
        caid=caid,
        harness_digest=b"h",
        tool_digest=b"t",
        expected_harness=b"h",
        expected_tool=b"t",
    )
    assert ok is True and mask == 0
    assert gate.reconcile_outcome(op_id, "UNKNOWN_STATUS") is False
    assert gate.reconcile_outcome(op_id, "REFUTED") is True
    assert gate.remaining_budget_minor == 10000
    assert gate.verify_journal_integrity() is True

    # Tampered journal entry fails verify_journal_integrity
    saved_hash = gate.journal[0]["entry_hash"]
    gate.journal[0]["entry_hash"] = "sha256:0000"
    assert gate.verify_journal_integrity() is False
    gate.journal[0]["entry_hash"] = saved_hash

    saved_prev = gate.journal[0]["payload"]["prev_hash"]
    gate.journal[0]["payload"]["prev_hash"] = "sha256:badprev"
    assert gate.verify_journal_integrity() is False
    gate.journal[0]["payload"]["prev_hash"] = saved_prev

    saved_sig = gate.journal[0]["signature_b64"]
    gate.journal[0]["signature_b64"] = base64.b64encode(b"0" * 64).decode("ascii")
    assert gate.verify_journal_integrity() is False
    gate.journal[0]["signature_b64"] = saved_sig

    # Forged refutation signature halts gate
    op_id2 = "op-g2"
    caid2 = gate.compute_caid(op_id2, 500, "iban:DE89370400440532013000", "POST /v1", "sha256:01")
    gate.evaluate_and_reserve(
        op_id=op_id2,
        amount_minor=500,
        payee_id="iban:DE89370400440532013000",
        endpoint="POST /v1",
        payload_digest="sha256:01",
        caid=caid2,
        harness_digest=b"h",
        tool_digest=b"t",
        expected_harness=b"h",
        expected_tool=b"t",
    )
    assert (
        gate.reconcile_outcome(
            op_id2,
            "REFUTED",
            target_attestation_sig_b64=base64.b64encode(b"0" * 64).decode("ascii"),
            target_pubkey=t_priv.public_key(),
        )
        is False
    )
    assert gate.is_halted is True
    assert gate.halt_reason == "HALT_FORGED_TARGET_REFUTATION"

    # 4. AeibDstEngine with traces_dir & exact trace assertions
    traces_dir = tmp_path / "traces_out"
    eng = AeibDstEngine(seed=42)
    rep = eng.run_simulation(schedules=40, fail_fast=True, traces_dir=traces_dir)
    assert rep.is_clean is True
    trace_lines = [
        json.loads(line)
        for line in (traces_dir / "traces.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(trace_lines) == 40
    assert trace_lines[0]["timestamp_ms"] == 1771400000000
    assert trace_lines[1]["timestamp_ms"] == 1771400001000
    assert trace_lines[2]["timestamp_ms"] == 1771400002000
    assert all(t["amount_minor"] == 15000 for t in trace_lines)
    faults_seen = {t["fault"] for t in trace_lines}
    assert "REPLAY_ATTACK" in faults_seen
    assert "DISK_FULL_SIMULATED" in faults_seen

    # 5. In-process main() invocations
    monkeypatch.setattr(sys, "argv", ["aeib_dst_harness.py", "--schedules", "5", "--seed", "42"])
    assert dst_main() == 0

    monkeypatch.setattr(sys, "argv", ["aeib_dst_harness.py", "--self-test"])
    assert dst_main() == 0

    out_fail = tmp_path / "fail_report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "aeib_dst_harness.py",
            "--schedules",
            "50",
            "--seed",
            "42",
            "--negative-control",
            "BYPASS_LATCH_ON_RETRY",
            "--output-json",
            str(out_fail),
        ],
    )
    assert dst_main() == 1

