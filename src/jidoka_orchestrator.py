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
src/jidoka_orchestrator.py
================================================================================
Jidoka Factory Orchestrator with EO1 Pre-Execution Latching, Out-of-Process
Subprocess Isolation, Cognitive Flight Recorder, and Andon Cord Escalation.

Under the stated model, this module implements an industrial agentic software
factory loop:
1. Station Loop & Pre-Execution Latch: Integrates `EO1UnifiedGate` to block
   symlink escapes, reflection, and PCI Lethal Trifecta taint before disk writes.
2. Out-of-Process Isolation: Executes untrusted code proposals in isolated
   subprocesses (`python3 -I`) with restricted environment and resource limits.
3. Bounded Iterative Repair: Restricts repair loops to B <= 3 before triggering
   the Jidoka Andon Cord line-stop (arXiv:2608.29460v3).
4. Cognitive Flight Recorder: Generates hash-chained, OpenTelemetry-compatible
   decision spans using RFC 8785 canonical JSON serialization without raw floats.
5. Anti-Reward-Hacking Escalation: Provides first-class support for
   `report_unsolvable_blocker` tickets to halt without cheating (arXiv:2605.15221).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.eo1_unified_gate import (
    BlockerTicket,
    EO1GateReceipt,
    EO1UnifiedGate,
    TaintFlag,
)
from src.jcs_canonicalizer import encode_jcs


def sha256_jcs_caid(payload: Any) -> str:
    """Computes deterministic SHA-256 CAID digest over RFC 8785 canonical bytes."""
    raw = payload if isinstance(payload, bytes) else encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclass(frozen=True)
class JidokaSpan:
    """Hash-chained OpenTelemetry-compatible execution span."""

    span_id: str
    parent_span_id: Optional[str]
    task_id: str
    station_name: str
    operation_name: str
    status: str
    latency_us: int
    attributes: Dict[str, Any]
    prev_span_digest: str
    span_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attributes": dict(sorted(self.attributes.items())),
            "latency_us": self.latency_us,
            "operation_name": self.operation_name,
            "parent_span_id": self.parent_span_id,
            "prev_span_digest": self.prev_span_digest,
            "span_digest": self.span_digest,
            "span_id": self.span_id,
            "station_name": self.station_name,
            "status": self.status,
            "task_id": self.task_id,
        }


@dataclass(frozen=True)
class StationExecutionResult:
    """Outcome of a Jidoka factory station execution cycle."""

    task_id: str
    target_file: str
    status: str
    attempt_count: int
    receipt_caid: Optional[str]
    written_bytes: int
    detail: str
    andon_tripped: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "andon_tripped": self.andon_tripped,
            "attempt_count": self.attempt_count,
            "detail": self.detail,
            "receipt_caid": self.receipt_caid,
            "status": self.status,
            "target_file": self.target_file,
            "task_id": self.task_id,
            "written_bytes": self.written_bytes,
        }


@dataclass(frozen=True)
class EscalationNotice:
    """Human orchestrator escalation notice generated upon Andon Cord pull."""

    task_id: str
    severity: str
    reason: str
    evidence_caid: str
    timestamp_epoch_s: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_caid": self.evidence_caid,
            "reason": self.reason,
            "severity": self.severity,
            "task_id": self.task_id,
            "timestamp_epoch_s": self.timestamp_epoch_s,
        }


_CHILD_ISOLATION_WRAPPER = """
import sys
import resource

# Restrict fork bombs under process isolation
try:
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
except Exception:
    pass

candidate_code = sys.stdin.read()
try:
    compiled = compile(candidate_code, "<candidate>", "exec")
    scope = {"__name__": "__main__"}
    exec(compiled, scope)
    sys.stdout.write("OK_EXECUTION_COMPLETED\\n")
    sys.exit(0)
except Exception as e:
    sys.stderr.write(f"ERR_CANDIDATE_EXCEPTION:{type(e).__name__}:{e}\\n")
    sys.exit(1)
"""


class JidokaFactoryOrchestrator:
    """
    Industrial Jidoka software factory orchestrator.
    Controls the Builder/Monitor loop with deterministic hold points,
    bounded repair (B <= 3), and immutable flight recording.
    """

    MAX_REPAIR_ATTEMPTS: int = 3  # claim: config - bounded repair B <= 3

    def __init__(
        self,
        workspace_root: str,
        gate: Optional[EO1UnifiedGate] = None,
        default_timeout_s: int = 5,
    ) -> None:
        self.workspace_root = os.path.realpath(workspace_root)
        if not os.path.exists(os.path.join(self.workspace_root, ".git")):
            raise ValueError("HALT_WORKSPACE_MISSING_GIT_ANCHOR")

        self.gate = gate or EO1UnifiedGate(workspace_root=self.workspace_root)
        self.default_timeout_s = default_timeout_s
        self._spans: List[JidokaSpan] = []
        self._last_span_digest = "sha256:" + ("0" * 64)
        self._escalations: List[EscalationNotice] = []
        self._line_frozen: bool = False

    @property
    def is_line_frozen(self) -> bool:
        return self._line_frozen

    def unfreeze_line(self) -> None:
        """Clears line-freeze state after human orchestrator review."""
        self._line_frozen = False

    @staticmethod
    def _us_from_ns(delta_ns: int) -> int:
        """Converts nanoseconds delta to integer microseconds."""
        return delta_ns // 1000

    @staticmethod
    def _now_epoch_ms() -> int:
        """Returns current epoch timestamp in milliseconds."""
        return int(time.time() * 1000)

    def record_span(
        self,
        task_id: str,
        station_name: str,
        operation_name: str,
        status: str,
        latency_us: int,
        attributes: Dict[str, Any],
        parent_span_id: Optional[str] = None,
    ) -> JidokaSpan:
        """Appends a cryptographically hash-chained execution span."""
        span_id = f"span_{len(self._spans) + 1}_{self._now_epoch_ms()}"
        clean_attrs = dict(sorted(attributes.items()))

        body = {
            "attributes": clean_attrs,
            "latency_us": latency_us,
            "operation_name": operation_name,
            "parent_span_id": parent_span_id,
            "prev_span_digest": self._last_span_digest,
            "span_id": span_id,
            "station_name": station_name,
            "status": status,
            "task_id": task_id,
        }
        span_digest = sha256_jcs_caid(body)
        span = JidokaSpan(
            span_id=span_id,
            parent_span_id=parent_span_id,
            task_id=task_id,
            station_name=station_name,
            operation_name=operation_name,
            status=status,
            latency_us=latency_us,
            attributes=clean_attrs,
            prev_span_digest=self._last_span_digest,
            span_digest=span_digest,
        )
        self._last_span_digest = span_digest
        self._spans.append(span)
        return span

    def execute_candidate_isolated(
        self,
        code: str,
        timeout_s: Optional[int] = None,
    ) -> Tuple[bool, str, int]:
        """
        Executes untrusted candidate code in an out-of-process Python sandbox.
        Process isolation with clean env and restricted process limits.
        """
        timeout = timeout_s or self.default_timeout_s
        start_ns = time.perf_counter_ns()

        clean_env = {
            "PATH": "/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }

        with tempfile.TemporaryDirectory(prefix="jidoka_sandbox_") as tmpdir:
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-c", _CHILD_ISOLATION_WRAPPER],
                    input=code,
                    text=True,
                    capture_output=True,
                    cwd=tmpdir,
                    env=clean_env,
                    timeout=timeout,
                )
                dur_us = self._us_from_ns(time.perf_counter_ns() - start_ns)
                if proc.returncode == 0:
                    return True, proc.stdout.strip(), dur_us
                return False, proc.stderr.strip() or f"EXIT_{proc.returncode}", dur_us
            except subprocess.TimeoutExpired:
                dur_us = self._us_from_ns(time.perf_counter_ns() - start_ns)
                return False, "ERR_CANDIDATE_TIMEOUT_EXCEEDED", dur_us
            except Exception as e:
                dur_us = self._us_from_ns(time.perf_counter_ns() - start_ns)
                return False, f"ERR_SANDBOX_FAILURE:{type(e).__name__}:{e}", dur_us

    def escalate_to_human(
        self, task_id: str, severity: str, reason: str, evidence: str
    ) -> EscalationNotice:
        """Pulls the Jidoka Andon Cord, freezing the factory line."""
        self._line_frozen = True
        evidence_payload = {
            "evidence": evidence,
            "reason": reason,
            "severity": severity,
            "task_id": task_id,
        }
        evidence_caid = sha256_jcs_caid(evidence_payload)
        notice = EscalationNotice(
            task_id=task_id,
            severity=severity,
            reason=reason,
            evidence_caid=evidence_caid,
            timestamp_epoch_s=int(time.time()),
        )
        self._escalations.append(notice)
        return notice

    def handle_blocker_escalation(
        self,
        task_id: str,
        blocker_category: str,
        reason: str,
        reproducing_evidence: str,
    ) -> BlockerTicket:
        """
        Records an auditable blocker report via EO1, pulling the Andon Cord
        legitimately without penalizing the agent with reward hacking.
        """
        ticket = self.gate.report_unsolvable_blocker(
            task_id=task_id,
            blocker_category=blocker_category,
            reason=reason,
            reproducing_evidence=reproducing_evidence,
        )
        self.record_span(
            task_id=task_id,
            station_name="ESCALATION_STATION",
            operation_name="report_unsolvable_blocker",
            status="ESCALATED_BLOCKER",
            latency_us=0,
            attributes={
                "blocker_category": blocker_category,
                "ticket_caid": ticket.ticket_caid,
            },
        )
        self.escalate_to_human(
            task_id=task_id,
            severity="BLOCKER_ESCALATED",
            reason=f"Agent declared unsolvable blocker: {blocker_category}",
            evidence=ticket.ticket_caid,
        )
        return ticket

    def run_station(
        self,
        task_id: str,
        builder_fn: Callable[[str, int], str],
        target_file: str,
        prompt: str,
        test_verifier_fn: Optional[Callable[[str], bool]] = None,
        timeout_s: Optional[int] = None,
    ) -> StationExecutionResult:
        """
        Executes a bounded Jidoka station cycle (B <= 3 attempts):
        1. Invokes Builder AI.
        2. Validates code write via EO1 pre-execution latch.
        3. Sandboxes execution out-of-process.
        4. Verifies tests if provided.
        5. Commits to workspace disk atomically upon verification.
        """
        if self._line_frozen:
            return StationExecutionResult(
                task_id=task_id,
                target_file=target_file,
                status="HALTED_LINE_FROZEN",
                attempt_count=0,
                receipt_caid=None,
                written_bytes=0,
                detail="Factory line is frozen awaiting human resolution",
                andon_tripped=True,
            )

        parent_span = self.record_span(
            task_id=task_id,
            station_name="DISPATCH_STATION",
            operation_name="start_station_cycle",
            status="IN_PROGRESS",
            latency_us=0,
            attributes={"target_file": target_file},
        )

        feedback = ""
        for attempt in range(1, self.MAX_REPAIR_ATTEMPTS + 1):
            builder_prompt = prompt if not feedback else f"{prompt}\n[FEEDBACK]: {feedback}"
            start_builder_ns = time.perf_counter_ns()
            proposed_code = builder_fn(builder_prompt, attempt)
            builder_dur_us = self._us_from_ns(time.perf_counter_ns() - start_builder_ns)

            self.record_span(
                task_id=task_id,
                station_name="BUILDER_STATION",
                operation_name="generate_candidate_code",
                status="OK",
                latency_us=builder_dur_us,
                attributes={"attempt": attempt, "code_bytes": len(proposed_code.encode("utf-8"))},
                parent_span_id=parent_span.span_id,
            )

            # Step 1: EO1 Pre-Execution Latch
            start_latch_ns = time.perf_counter_ns()
            receipt = self.gate.validate_code_write(
                task_id=task_id,
                file_path=target_file,
                proposed_code=proposed_code,
            )
            latch_dur_us = self._us_from_ns(time.perf_counter_ns() - start_latch_ns)

            if not receipt.allowed:
                self.record_span(
                    task_id=task_id,
                    station_name="EO1_LATCH_STATION",
                    operation_name="validate_code_write",
                    status="HALTED_EO1_LATCH",
                    latency_us=latch_dur_us,
                    attributes={
                        "attempt": attempt,
                        "receipt_caid": receipt.receipt_caid,
                        "status_code": receipt.status_code,
                    },
                    parent_span_id=parent_span.span_id,
                )
                self.escalate_to_human(
                    task_id=task_id,
                    severity="SECURITY_VIOLATION",
                    reason=f"EO1 Latch Blocked Write: {receipt.status_code}",
                    evidence=receipt.receipt_caid,
                )
                return StationExecutionResult(
                    task_id=task_id,
                    target_file=target_file,
                    status="HALTED_ANDON_CORD",
                    attempt_count=attempt,
                    receipt_caid=receipt.receipt_caid,
                    written_bytes=0,
                    detail=f"EO1 Gate Rejected: {receipt.status_code}",
                    andon_tripped=True,
                )

            self.record_span(
                task_id=task_id,
                station_name="EO1_LATCH_STATION",
                operation_name="validate_code_write",
                status="OK",
                latency_us=latch_dur_us,
                attributes={
                    "attempt": attempt,
                    "receipt_caid": receipt.receipt_caid,
                    "status_code": receipt.status_code,
                },
                parent_span_id=parent_span.span_id,
            )

            # Step 2: Out-of-process isolated execution probe
            iso_ok, iso_out, iso_us = self.execute_candidate_isolated(
                proposed_code, timeout_s=timeout_s
            )
            self.record_span(
                task_id=task_id,
                station_name="SANDBOX_STATION",
                operation_name="execute_candidate_isolated",
                status="OK" if iso_ok else "SANDBOX_FAIL",
                latency_us=iso_us,
                attributes={"attempt": attempt, "detail": iso_out[:128]},
                parent_span_id=parent_span.span_id,
            )

            if not iso_ok:
                feedback = f"Sandbox execution failed on attempt {attempt}: {iso_out}"
                continue

            # Step 3: Domain test verification if provided
            if test_verifier_fn is not None:
                tests_passed = test_verifier_fn(proposed_code)
                if not tests_passed:
                    feedback = f"Verification tests failed on attempt {attempt}"
                    continue

            # Step 4: Atomic write to workspace disk
            abs_target = os.path.realpath(os.path.join(self.workspace_root, target_file))
            os.makedirs(os.path.dirname(abs_target), exist_ok=True)
            tmp_target = f"{abs_target}.tmp.{os.getpid()}"
            encoded = proposed_code.encode("utf-8")
            with open(tmp_target, "wb") as f:
                f.write(encoded)
            os.replace(tmp_target, abs_target)

            self.record_span(
                task_id=task_id,
                station_name="COMMIT_STATION",
                operation_name="atomic_disk_commit",
                status="COMMITTED",
                latency_us=0,
                attributes={"bytes_written": len(encoded), "target_file": target_file},
                parent_span_id=parent_span.span_id,
            )

            return StationExecutionResult(
                task_id=task_id,
                target_file=target_file,
                status="COMMITTED_SUCCESS",
                attempt_count=attempt,
                receipt_caid=receipt.receipt_caid,
                written_bytes=len(encoded),
                detail="Code verified and committed to workspace disk",
                andon_tripped=False,
            )

        # Retries exhausted -> Trip Andon cord
        self.escalate_to_human(
            task_id=task_id,
            severity="REPAIR_BUDGET_EXHAUSTED",
            reason=f"Exhausted {self.MAX_REPAIR_ATTEMPTS} repair attempts without passing tests",
            evidence=feedback,
        )
        return StationExecutionResult(
            task_id=task_id,
            target_file=target_file,
            status="HALTED_ANDON_CORD",
            attempt_count=self.MAX_REPAIR_ATTEMPTS,
            receipt_caid=None,
            written_bytes=0,
            detail=f"Exhausted {self.MAX_REPAIR_ATTEMPTS} repair attempts: {feedback}",
            andon_tripped=True,
        )

    def export_flight_recorder_spans(self) -> List[Dict[str, Any]]:
        """Returns ordered list of hash-chained execution spans."""
        return [s.to_dict() for s in self._spans]

    def save_flight_recorder_jsonl(self, output_path: str) -> str:
        """Writes RFC 8785 canonical JSONL entries to disk and returns file CAID."""
        lines = [encode_jcs(s.to_dict()).decode("utf-8") + "\n" for s in self._spans]
        raw_bytes = "".join(lines).encode("utf-8")
        with open(output_path, "wb") as f:
            f.write(raw_bytes)
        return sha256_jcs_caid(raw_bytes)
