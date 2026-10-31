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
tests/test_jidoka_orchestrator.py
================================================================================
Verification and Falsification Suite for `src/jidoka_orchestrator.py`.
Evaluates:
1. Nominal station dispatch, isolated sandbox execution, and atomic disk commit.
2. Invariant core write interception and automatic Andon Cord trip.
3. Bounded iterative repair (B <= 3) and failure escalation.
4. Anti-reward-hacking blocker escalation (`handle_blocker_escalation`).
5. OpenTelemetry cognitive flight recorder hash chaining and JSONL export.
6. Factory line freeze on security violation and unfreeze workflow.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import List

import pytest

from src.eo1_unified_gate import EO1UnifiedGate
from src.jidoka_orchestrator import (
    EscalationNotice,
    JidokaFactoryOrchestrator,
    JidokaSpan,
    StationExecutionResult,
    sha256_jcs_caid,
)


@pytest.fixture
def jidoka_workspace(tmp_path: Path) -> Path:
    repo = tmp_path / "factory_repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".git").mkdir()
    (repo / "tests").mkdir()
    (repo / "src").mkdir()
    return repo


def test_1_nominal_station_execution_and_atomic_commit(jidoka_workspace: Path) -> None:
    orchestrator = JidokaFactoryOrchestrator(workspace_root=str(jidoka_workspace))
    assert orchestrator.default_timeout_s == 5

    def safe_builder(prompt: str, attempt: int) -> str:
        return "def compute_tax(amount: int) -> int:\n    return amount * 2\n"

    def strict_verifier(code: str) -> bool:
        return "def compute_tax" in code

    res = orchestrator.run_station(
        task_id="task_nominal_tax",
        builder_fn=safe_builder,
        target_file="src/tax_calculator.py",
        prompt="Write a tax calculator function",
        test_verifier_fn=strict_verifier,
    )

    assert res.status == "COMMITTED_SUCCESS"
    assert res.attempt_count == 1
    assert res.andon_tripped is False
    assert res.written_bytes > 0
    assert res.receipt_caid is not None
    assert res.receipt_caid.startswith("sha256:")

    # Verify physical file exists on workspace disk
    written_file = jidoka_workspace / "src" / "tax_calculator.py"
    assert written_file.exists()
    assert "def compute_tax" in written_file.read_text(encoding="utf-8")

    # Verify flight recorder recorded dispatch, builder, latch, sandbox, and commit spans
    spans = orchestrator.export_flight_recorder_spans()
    assert len(spans) >= 5
    assert spans[0]["latency_us"] == 0
    ops = [s["operation_name"] for s in spans]
    assert "start_station_cycle" in ops
    assert "generate_candidate_code" in ops
    assert "validate_code_write" in ops
    assert "execute_candidate_isolated" in ops
    assert "atomic_disk_commit" in ops


def test_2_interception_of_test_modification_trips_andon_cord(jidoka_workspace: Path) -> None:
    orchestrator = JidokaFactoryOrchestrator(workspace_root=str(jidoka_workspace))

    # Cheater agent attempts to overwrite a test
    def cheating_builder(prompt: str, attempt: int) -> str:
        return (
            "def test_cheat():\n"
            "    with open('tests/test_escrow.py', 'w') as f:\n"
            "        f.write('assert True')\n"
        )

    res = orchestrator.run_station(
        task_id="task_cheater",
        builder_fn=cheating_builder,
        target_file="src/payment_worker.py",
        prompt="Fix escrow failure",
    )

    assert res.status == "HALTED_ANDON_CORD"
    assert res.andon_tripped is True
    assert res.attempt_count == 1
    assert res.written_bytes == 0
    assert "EO1 Gate Rejected" in res.detail
    assert orchestrator.is_line_frozen is True

    # Subsequent tasks are blocked while line is frozen
    res_blocked = orchestrator.run_station(
        task_id="task_innocent",
        builder_fn=lambda p, a: "x = 1\n",
        target_file="src/innocent.py",
        prompt="Do work",
    )
    assert res_blocked.status == "HALTED_LINE_FROZEN"
    assert res_blocked.attempt_count == 0

    # Unfreeze line
    orchestrator.unfreeze_line()
    assert orchestrator.is_line_frozen is False


def test_3_bounded_repair_loop_exhaustion(jidoka_workspace: Path) -> None:
    orchestrator = JidokaFactoryOrchestrator(workspace_root=str(jidoka_workspace))

    attempts_seen: List[int] = []

    def failing_builder(prompt: str, attempt: int) -> str:
        attempts_seen.append(attempt)
        return f"# Attempt {attempt}\nraise RuntimeError('Bug remains')\n"

    res = orchestrator.run_station(
        task_id="task_flaky_repair",
        builder_fn=failing_builder,
        target_file="src/broken_module.py",
        prompt="Fix the bug",
    )

    # Obey arXiv:2608.29460v3: bounded to exactly 3 attempts
    assert attempts_seen == [1, 2, 3]
    assert res.attempt_count == 3
    assert res.status == "HALTED_ANDON_CORD"
    assert res.andon_tripped is True
    assert "Exhausted 3 repair attempts" in res.detail
    assert orchestrator.is_line_frozen is True


def test_4_anti_reward_hacking_blocker_escalation(jidoka_workspace: Path) -> None:
    orchestrator = JidokaFactoryOrchestrator(workspace_root=str(jidoka_workspace))

    # Builder AI honestly reports an impossible specification
    ticket = orchestrator.handle_blocker_escalation(
        task_id="task_impossible_spec",
        blocker_category="CONTRADICTORY_SPEC",
        reason="Spec requires constant O(1) latency on unindexed linear search",
        reproducing_evidence="Benchmark on 1M rows requires >= 180ms without index",
    )

    assert ticket.task_id == "task_impossible_spec"
    assert ticket.blocker_category == "CONTRADICTORY_SPEC"
    assert ticket.write_permissions_revoked is True
    assert ticket.ticket_caid.startswith("sha256:")
    assert orchestrator.is_line_frozen is True

    # Subsequent write attempt by task_impossible_spec is rejected
    res = orchestrator.run_station(
        task_id="task_impossible_spec",
        builder_fn=lambda p, a: "x = 1\n",
        target_file="src/retry.py",
        prompt="Try again",
    )
    assert res.status == "HALTED_LINE_FROZEN"


def test_5_flight_recorder_hash_chain_and_jsonl_export(jidoka_workspace: Path) -> None:
    orchestrator = JidokaFactoryOrchestrator(workspace_root=str(jidoka_workspace))

    # Run 1 task to generate spans
    orchestrator.run_station(
        task_id="task_span_check",
        builder_fn=lambda p, a: "y = 42\n",
        target_file="src/value.py",
        prompt="Set value",
    )

    spans = orchestrator.export_flight_recorder_spans()
    assert len(spans) >= 5

    # Verify cryptographic hash chaining
    prev_digest = "sha256:" + ("0" * 64)
    for span_dict in spans:
        assert span_dict["prev_span_digest"] == prev_digest
        span_obj = JidokaSpan(
            span_id=span_dict["span_id"],
            parent_span_id=span_dict["parent_span_id"],
            task_id=span_dict["task_id"],
            station_name=span_dict["station_name"],
            operation_name=span_dict["operation_name"],
            status=span_dict["status"],
            latency_us=span_dict["latency_us"],
            attributes=span_dict["attributes"],
            prev_span_digest=span_dict["prev_span_digest"],
            span_digest=span_dict["span_digest"],
        )
        assert span_obj.to_dict() == span_dict
        prev_digest = span_dict["span_digest"]

    # Export to JSONL file and verify content
    out_file = jidoka_workspace / "flight_recorder.jsonl"
    file_caid = orchestrator.save_flight_recorder_jsonl(str(out_file))
    assert file_caid.startswith("sha256:")
    assert out_file.exists()

    lines = [json.loads(line) for line in out_file.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == len(spans)
    assert lines[0]["operation_name"] == spans[0]["operation_name"]


def test_6_sandbox_timeout_and_error_handling(jidoka_workspace: Path) -> None:
    orchestrator = JidokaFactoryOrchestrator(workspace_root=str(jidoka_workspace))

    # 1. Syntax Error
    ok_syn, out_syn, _ = orchestrator.execute_candidate_isolated("def broken(: pass\n")
    assert ok_syn is False
    assert "ERR_CANDIDATE_EXCEPTION:SyntaxError" in out_syn

    # 2. Timeout
    infinite_loop_code = "while True: pass\n"
    ok_to, out_to, _ = orchestrator.execute_candidate_isolated(infinite_loop_code, timeout_s=1)
    assert ok_to is False
    assert out_to == "ERR_CANDIDATE_TIMEOUT_EXCEEDED"


def test_7_dataclass_methods_and_validation(jidoka_workspace: Path) -> None:
    # 1. Workspace missing .git anchor must fail closed even when a valid gate is supplied
    dummy_gate = EO1UnifiedGate(workspace_root=str(jidoka_workspace))
    with tempfile.TemporaryDirectory() as empty_dir:
        with pytest.raises(ValueError, match="HALT_WORKSPACE_MISSING_GIT_ANCHOR"):
            JidokaFactoryOrchestrator(workspace_root=empty_dir, gate=dummy_gate)

    # 2. Test StationExecutionResult.to_dict and immutability (frozen=True)
    ser = StationExecutionResult(
        task_id="t1",
        target_file="src/x.py",
        status="COMMITTED_SUCCESS",
        attempt_count=1,
        receipt_caid="sha256:123",
        written_bytes=10,
        detail="OK",
        andon_tripped=False,
    )
    ser_d = ser.to_dict()
    assert ser_d["task_id"] == "t1"
    assert ser_d["written_bytes"] == 10
    assert ser_d["andon_tripped"] is False
    assert ser_d["attempt_count"] == 1
    assert ser_d["detail"] == "OK"
    assert ser_d["receipt_caid"] == "sha256:123"
    assert ser_d["status"] == "COMMITTED_SUCCESS"
    assert ser_d["target_file"] == "src/x.py"

    with pytest.raises(Exception):
        ser.status = "MUTATED"  # type: ignore

    # 3. Test EscalationNotice.to_dict and immutability (frozen=True)
    en = EscalationNotice(
        task_id="t2",
        severity="CRITICAL",
        reason="Test failure",
        evidence_caid="sha256:456",
        timestamp_epoch_s=1700000000,
    )
    en_d = en.to_dict()
    assert en_d["task_id"] == "t2"
    assert en_d["evidence_caid"] == "sha256:456"
    assert en_d["reason"] == "Test failure"
    assert en_d["severity"] == "CRITICAL"
    assert en_d["timestamp_epoch_s"] == 1700000000

    with pytest.raises(Exception):
        en.reason = "MUTATED"  # type: ignore

    # 4. Test JidokaSpan.to_dict and immutability (frozen=True)
    span = JidokaSpan(
        span_id="span_1_100",
        parent_span_id=None,
        task_id="t3",
        station_name="TEST_STATION",
        operation_name="op",
        status="OK",
        latency_us=500,
        attributes={"k": "v"},
        prev_span_digest="sha256:0",
        span_digest="sha256:1",
    )
    span_d = span.to_dict()
    assert span_d["span_id"] == "span_1_100"
    assert span_d["latency_us"] == 500

    with pytest.raises(Exception):
        span.status = "MUTATED"  # type: ignore


def test_8_sandbox_exit_code_and_long_detail_truncation(jidoka_workspace: Path) -> None:
    orchestrator = JidokaFactoryOrchestrator(workspace_root=str(jidoka_workspace))

    # 1. Clean nonzero exit with empty stderr -> should format EXIT_<code>
    ok, out, dur_us = orchestrator.execute_candidate_isolated("import sys; sys.exit(42)\n")
    assert ok is False
    assert out == "EXIT_42"
    assert dur_us >= 0

    # 2. Long error output (>128 chars) truncated in attributes
    long_error_code = "raise RuntimeError('A' * 200)\n"
    res = orchestrator.run_station(
        task_id="task_long_err",
        builder_fn=lambda p, a: long_error_code,
        target_file="src/err.py",
        prompt="Write error",
    )
    assert res.status == "HALTED_ANDON_CORD"
    assert res.written_bytes == 0

    spans = orchestrator.export_flight_recorder_spans()
    sandbox_spans = [s for s in spans if s["operation_name"] == "execute_candidate_isolated"]
    assert len(sandbox_spans) >= 1
    detail_attr = sandbox_spans[0]["attributes"]["detail"]
    assert len(detail_attr) <= 128
    assert "ERR_CANDIDATE_EXCEPTION" in detail_attr

    # 3. Check span IDs format `span_<index>_<ts>`
    assert spans[0]["span_id"].startswith("span_1_")
    assert spans[1]["span_id"].startswith("span_2_")
    assert spans[0]["latency_us"] >= 0
    assert spans[1]["latency_us"] >= 0


def test_9_exception_path_in_execute_candidate(jidoka_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = JidokaFactoryOrchestrator(workspace_root=str(jidoka_workspace))

    # Trigger generic Exception branch in execute_candidate_isolated (e.g. OSError)
    def fail_run(*args, **kwargs):
        raise OSError("Simulated kernel descriptor exhaustion")

    monkeypatch.setattr("subprocess.run", fail_run)
    ok, out, dur_us = orchestrator.execute_candidate_isolated("x = 1\n")
    assert ok is False
    assert "ERR_SANDBOX_FAILURE:OSError:Simulated kernel descriptor exhaustion" in out
    assert 0 <= dur_us < 10_000_000


def test_10_us_from_ns_and_now_epoch_ms() -> None:
    # Exact calculation check: delta_ns // 1000
    assert JidokaFactoryOrchestrator._us_from_ns(2000) == 2
    assert JidokaFactoryOrchestrator._us_from_ns(1000) == 1
    assert JidokaFactoryOrchestrator._us_from_ns(0) == 0
    assert JidokaFactoryOrchestrator._us_from_ns(500) == 0

    # Epoch ms check: int(time.time() * 1000)
    now_ms = JidokaFactoryOrchestrator._now_epoch_ms()
    expected = int(time.time() * 1000)
    assert abs(now_ms - expected) < 2000
    assert now_ms > 1_700_000_000_000


