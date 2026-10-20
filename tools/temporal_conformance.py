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
tools/temporal_conformance.py — Explicit Operation-Bound Temporal Conformance Monitor.
Evaluated under the stated model as an agent execution boundary scaffold.

Tracks explicit state machine transitions per operation:
1. durable_intent_before_dispatch: INTENT_PERSISTED must precede DISPATCH_SENT.
2. no_blind_retry_after_uncertainty: When EFFECT_INDETERMINATE, further dispatches are blocked.
3. bounded_reconciliation: Indeterminate effects must be resolved within max_horizon.
4. halt_blocks_future_dispatch: Boundary HALT blocks all subsequent dispatches.
5. authoritative_evidence_for_settlement: CONFIRMED requires non-empty evidence digest.
"""

from __future__ import annotations

import argparse
import enum
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class OperationTemporalState(enum.Enum):
    UNSEEN = "UNSEEN"
    INTENT_PERSISTED = "INTENT_PERSISTED"
    DISPATCH_SENT = "DISPATCH_SENT"
    EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"
    CONFIRMED = "CONFIRMED"
    REFUTED = "REFUTED"
    UNRESOLVED_ESCALATED = "UNRESOLVED_ESCALATED"


class TemporalViolationError(Exception):
    """Raised when an operation breaches declared temporal execution rules."""

    def __init__(
        self,
        rule_id: str,
        operation_id: str,
        step_index: int,
        details: str,
    ) -> None:
        super().__init__(
            f"TEMPORAL INVARIANT BREACH [{rule_id}] (op: {operation_id}, step: {step_index}): {details}"
        )
        self.rule_id = rule_id
        self.operation_id = operation_id
        self.step_index = step_index
        self.details = details


@dataclass
class OperationTimeline:
    operation_id: str
    current_state: OperationTemporalState = OperationTemporalState.UNSEEN
    action_caid: Optional[str] = None
    amount_minor: Optional[int] = None
    intent_step: Optional[int] = None
    dispatch_step: Optional[int] = None
    indeterminate_step: Optional[int] = None
    settlement_step: Optional[int] = None
    indeterminate_reason: Optional[str] = None
    evidence_digest: Optional[str] = None
    authority_signature: Optional[str] = None
    transitions: List[Tuple[int, OperationTemporalState, str]] = field(
        default_factory=list
    )


class TemporalConformanceMonitor:
    """
    Explicit operation-bound state machine monitor for AEIB temporal conformance.
    Operates both online during execution and offline during replay verification.
    """

    def __init__(self, max_reconciliation_horizon_steps: int = 100) -> None:
        self.max_reconciliation_horizon = max_reconciliation_horizon_steps
        self.timelines: Dict[str, OperationTimeline] = {}
        self.is_halted: bool = False
        self.halt_reason: Optional[str] = None
        self.halt_step: Optional[int] = None
        self.current_step: int = 0
        self.active_indeterminate_ops: Set[str] = set()

    def record_halt(self, reason: str, step_index: Optional[int] = None) -> None:
        step = self.current_step if step_index is None else step_index
        self.is_halted = True
        self.halt_reason = reason
        self.halt_step = step

    def record_intent(
        self,
        operation_id: str,
        action_caid: str,
        amount_minor: int,
        step_index: Optional[int] = None,
    ) -> None:
        step = self.current_step if step_index is None else step_index
        if operation_id not in self.timelines:
            self.timelines[operation_id] = OperationTimeline(operation_id=operation_id)

        tl = self.timelines[operation_id]
        tl.action_caid = action_caid
        tl.amount_minor = amount_minor
        tl.intent_step = step
        tl.current_state = OperationTemporalState.INTENT_PERSISTED
        tl.transitions.append((step, OperationTemporalState.INTENT_PERSISTED, "INTENT_RECORDED"))

    def record_dispatch(
        self,
        operation_id: str,
        endpoint: str = "",
        step_index: Optional[int] = None,
    ) -> None:
        step = self.current_step if step_index is None else step_index

        # Rule 4: halt_blocks_future_dispatch
        if self.is_halted:
            raise TemporalViolationError(
                rule_id="halt_blocks_future_dispatch",
                operation_id=operation_id,
                step_index=step,
                details=f"Dispatch attempted while boundary was halted: {self.halt_reason} (halted at step {self.halt_step})",
            )

        tl = self.timelines.get(operation_id)

        # Rule 1: durable_intent_before_dispatch
        if tl is None or tl.current_state == OperationTemporalState.UNSEEN:
            raise TemporalViolationError(
                rule_id="durable_intent_before_dispatch",
                operation_id=operation_id,
                step_index=step,
                details="Dispatch executed without prior durable intent persistence",
            )

        # Rule 2: no_blind_retry_after_uncertainty
        if tl.current_state == OperationTemporalState.EFFECT_INDETERMINATE:
            raise TemporalViolationError(
                rule_id="no_blind_retry_after_uncertainty",
                operation_id=operation_id,
                step_index=step,
                details="Blind retry attempted while operation effect is indeterminate",
            )

        tl.dispatch_step = step
        tl.current_state = OperationTemporalState.DISPATCH_SENT
        tl.transitions.append((step, OperationTemporalState.DISPATCH_SENT, f"DISPATCH_TO_{endpoint}"))

    def record_uncertainty(
        self,
        operation_id: str,
        reason: str = "HTTP_504_TIMEOUT",
        step_index: Optional[int] = None,
    ) -> None:
        step = self.current_step if step_index is None else step_index
        tl = self.timelines.get(operation_id)
        if tl is None or tl.current_state != OperationTemporalState.DISPATCH_SENT:
            raise TemporalViolationError(
                rule_id="uncertainty_requires_prior_dispatch",
                operation_id=operation_id,
                step_index=step,
                details="Cannot transition to EFFECT_INDETERMINATE without prior dispatch",
            )

        tl.current_state = OperationTemporalState.EFFECT_INDETERMINATE
        tl.indeterminate_step = step
        tl.indeterminate_reason = reason
        tl.transitions.append((step, OperationTemporalState.EFFECT_INDETERMINATE, reason))
        self.active_indeterminate_ops.add(operation_id)

    def record_settlement(
        self,
        operation_id: str,
        outcome: str,
        evidence_digest: Optional[str] = None,
        authority_signature: Optional[str] = None,
        step_index: Optional[int] = None,
    ) -> None:
        step = self.current_step if step_index is None else step_index
        tl = self.timelines.get(operation_id)
        if tl is None or tl.current_state not in (
            OperationTemporalState.DISPATCH_SENT,
            OperationTemporalState.EFFECT_INDETERMINATE,
        ):
            raise TemporalViolationError(
                rule_id="settlement_requires_active_operation",
                operation_id=operation_id,
                step_index=step,
                details=f"Cannot settle operation in state {tl.current_state if tl else 'UNSEEN'}",
            )

        outcome_norm = outcome.upper()
        if outcome_norm in ("CONFIRMED", "SETTLED_CONFIRMED"):
            # Rule 5: authoritative_evidence_for_settlement
            if not evidence_digest:
                raise TemporalViolationError(
                    rule_id="no_settlement_without_authoritative_evidence",
                    operation_id=operation_id,
                    step_index=step,
                    details="CONFIRMED settlement requires authoritative evidence digest",
                )
            tl.current_state = OperationTemporalState.CONFIRMED
        elif outcome_norm in ("REFUTED", "SETTLED_REFUTED"):
            tl.current_state = OperationTemporalState.REFUTED
        elif outcome_norm in ("UNRESOLVED_ESCALATED", "ESCALATED"):
            tl.current_state = OperationTemporalState.UNRESOLVED_ESCALATED
        else:
            raise ValueError(f"Unknown settlement outcome: {outcome}")

        tl.settlement_step = step
        tl.evidence_digest = evidence_digest
        tl.authority_signature = authority_signature
        tl.transitions.append((step, tl.current_state, f"SETTLED_{outcome_norm}"))
        self.active_indeterminate_ops.discard(operation_id)

    def check_bounded_reconciliation(self, current_step: int) -> None:
        """
        Rule 3: bounded_reconciliation.
        Verifies no indeterminate operation lingers beyond the configured horizon.
        """
        for op_id in list(self.active_indeterminate_ops):
            tl = self.timelines[op_id]
            if tl.indeterminate_step is not None:
                elapsed = current_step - tl.indeterminate_step
                if elapsed > self.max_reconciliation_horizon:
                    raise TemporalViolationError(
                        rule_id="bounded_reconciliation",
                        operation_id=op_id,
                        step_index=current_step,
                        details=(
                            f"Operation {op_id} lingered in EFFECT_INDETERMINATE for {elapsed} steps "
                            f"(limit: {self.max_reconciliation_horizon})"
                        ),
                    )

    def verify_trace(self, trace_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Replays a sequence of trace events and asserts all 5 temporal invariants.
        Raises TemporalViolationError on any breach.
        """
        for step_idx, event in enumerate(trace_events):
            self.current_step = step_idx
            op_id = event.get("operation_id", "")
            action = event.get("action", "")

            # Check bounded reconciliation at each step
            self.check_bounded_reconciliation(step_idx)

            # Check if this event engages a halt
            if event.get("is_halt_trigger", False) or action.startswith("HALT"):
                self.record_halt(reason=action, step_index=step_idx)
                continue

            if action in ("INTENT_STAGED", "INTENT_PERSISTED", "RECEIPT_CREATED"):
                caid = event.get("caid", hashlib.sha256(op_id.encode()).hexdigest())
                amount = event.get("amount_minor", 100_00)
                self.record_intent(op_id, caid, amount, step_index=step_idx)

            elif action in ("DISPATCH", "DISPATCH_SENT", "DISPATCH_RESERVED"):
                endpoint = event.get("endpoint", "POST /v1/mutations")
                self.record_dispatch(op_id, endpoint, step_index=step_idx)

            elif action in (
                "TRANSPORT_TIMEOUT_504",
                "HTTP_504_TIMEOUT",
                "EFFECT_INDETERMINATE",
                "LOST_ACK_POST_COMMIT",
            ):
                reason = event.get("reason", action)
                self.record_uncertainty(op_id, reason, step_index=step_idx)

            elif action in (
                "CONFIRMED",
                "SETTLED_CONFIRMED",
                "REFUTED",
                "SETTLED_REFUTED",
                "UNRESOLVED_ESCALATED",
            ):
                evidence = event.get("evidence_digest") or event.get("evidence")
                sig = event.get("authority_signature")
                self.record_settlement(
                    op_id, action, evidence_digest=evidence, authority_signature=sig, step_index=step_idx
                )

        # Final check at the end of the trace
        self.check_bounded_reconciliation(len(trace_events))

        return {
            "status": "PASS",
            "total_steps_verified": len(trace_events),
            "total_operations": len(self.timelines),
            "halt_engaged": self.is_halted,
            "halt_reason": self.halt_reason,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AEIB Temporal Conformance Monitor & Replay Checker"
    )
    parser.add_argument("--trace", type=str, help="Path to JSON/JSONL trace file")
    parser.add_argument(
        "--max-horizon",
        type=int,
        default=100,
        help="Max reconciliation steps for indeterminate effects",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run self-test against nominal and falsification traces",
    )

    args = parser.parse_args()

    if args.self_test:
        print("[*] Running TemporalConformanceMonitor self-test...")
        monitor = TemporalConformanceMonitor(max_reconciliation_horizon_steps=5)

        # Test Rule 1: Dispatch without intent
        try:
            m1 = TemporalConformanceMonitor()
            m1.record_dispatch("op-bad", step_index=0)
            assert False, "Failed to catch Rule 1"
        except TemporalViolationError as e:
            assert e.rule_id == "durable_intent_before_dispatch"

        # Test Rule 2: Blind retry after uncertainty
        try:
            m2 = TemporalConformanceMonitor()
            m2.record_intent("op-retry", "caid1", 100, step_index=0)
            m2.record_dispatch("op-retry", step_index=1)
            m2.record_uncertainty("op-retry", step_index=2)
            m2.record_dispatch("op-retry", step_index=3)  # Blind retry
            assert False, "Failed to catch Rule 2"
        except TemporalViolationError as e:
            assert e.rule_id == "no_blind_retry_after_uncertainty"

        # Test Rule 3: Bounded reconciliation horizon
        try:
            m3 = TemporalConformanceMonitor(max_reconciliation_horizon_steps=3)
            m3.record_intent("op-linger", "caid1", 100, step_index=0)
            m3.record_dispatch("op-linger", step_index=1)
            m3.record_uncertainty("op-linger", step_index=2)
            m3.check_bounded_reconciliation(current_step=6)  # 6 - 2 = 4 > 3
            assert False, "Failed to catch Rule 3"
        except TemporalViolationError as e:
            assert e.rule_id == "bounded_reconciliation"

        # Test Rule 4: Halt blocks subsequent dispatches
        try:
            m4 = TemporalConformanceMonitor()
            m4.record_halt("CORRUPTED_LEDGER", step_index=0)
            m4.record_intent("op-sub", "caid1", 100, step_index=1)
            m4.record_dispatch("op-sub", step_index=2)
            assert False, "Failed to catch Rule 4"
        except TemporalViolationError as e:
            assert e.rule_id == "halt_blocks_future_dispatch"

        # Test Rule 5: Confirmation requires evidence
        try:
            m5 = TemporalConformanceMonitor()
            m5.record_intent("op-ev", "caid1", 100, step_index=0)
            m5.record_dispatch("op-ev", step_index=1)
            m5.record_settlement("op-ev", "CONFIRMED", evidence_digest=None, step_index=2)
            assert False, "Failed to catch Rule 5"
        except TemporalViolationError as e:
            assert e.rule_id == "no_settlement_without_authoritative_evidence"

        print("[✓] TemporalConformanceMonitor self-test PASSED (All 5 rules verified).")
        return 0

    if args.trace:
        trace_path = Path(args.trace)
        if not trace_path.exists():
            print(f"Error: Trace file not found: {trace_path}", file=sys.stderr)
            return 1

        events: List[Dict[str, Any]] = []
        if trace_path.suffix == ".jsonl":
            with open(trace_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        else:
            with open(trace_path, "r", encoding="utf-8") as f:
                events = json.load(f)

        monitor = TemporalConformanceMonitor(
            max_reconciliation_horizon_steps=args.max_horizon
        )
        try:
            res = monitor.verify_trace(events)
            print(json.dumps(res, indent=2))
            return 0
        except TemporalViolationError as e:
            print(f"FAILED: {e}", file=sys.stderr)
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
