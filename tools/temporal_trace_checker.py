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
tools/temporal_trace_checker.py — Temporal Invariant Runtime & Replay Checker
Sovereign Multi-Agent OS (SMAOS) / AEIB Track A: Temporal Conformance.

Enforces the 5 normative temporal invariants defined in conformance/temporal_invariants_v1.yaml:
1. durable_intent_before_dispatch: G (dispatch_sent -> F intent_persisted)
2. no_blind_retry_after_uncertainty: G (effect_indeterminate -> X !dispatch_same_operation)
3. bounded_reconciliation: G (effect_indeterminate -> F (confirmed | refuted | unresolved_escalated))
4. halt_blocks_future_dispatch: G (halt_engaged -> X !dispatch)
5. no_settlement_without_authoritative_evidence: G (confirmed -> authoritative_evidence_observed)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Set


class TemporalConformanceError(Exception):
    def __init__(self, rule_id: str, step_index: int, operation_id: str, details: str):
        super().__init__(f"TEMPORAL INVARIANT BREACH [{rule_id}] at step {step_index} (op: {operation_id}): {details}")
        self.rule_id = rule_id
        self.step_index = step_index
        self.operation_id = operation_id
        self.details = details


class TemporalTraceChecker:
    """
    Evaluates step-by-step replay traces against declared temporal rules.
    """

    def __init__(self, max_reconciliation_horizon_steps: int = 100):
        self.max_reconciliation_horizon_steps = max_reconciliation_horizon_steps

    def verify_trace(self, trace_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validates an event sequence against all 5 temporal rules.
        Raises TemporalConformanceError on the first violation.
        """
        # Internal automaton tracking state
        op_states: Dict[str, str] = {}
        indeterminate_entry_steps: Dict[str, int] = {}
        persisted_intents: Set[str] = set()
        halt_latched = False
        halt_step = -1

        evaluated_steps = len(trace_events)

        for step_idx, event in enumerate(trace_events):
            op_id = event.get("operation_id", "")
            action = event.get("action", "")

            # --- Rule 4: halt_blocks_future_dispatch ---
            if halt_latched:
                if action in ("DISPATCH", "INTENT_STAGED", "BLIND_RETRY"):
                    raise TemporalConformanceError(
                        "halt_blocks_future_dispatch",
                        step_idx,
                        op_id,
                        f"Action '{action}' attempted at step {step_idx} while gate was halted since step {halt_step}",
                    )

            if event.get("is_halt_trigger", False) or action.startswith("HALT"):
                halt_latched = True
                halt_step = step_idx

            # Track intent persistence
            if action in ("INTENT_STAGED", "RECEIPT_CREATED") or event.get("intent_persisted", False):
                persisted_intents.add(op_id)

            # --- Rule 1: durable_intent_before_dispatch ---
            if action == "DISPATCH":
                if op_id not in persisted_intents and not event.get("has_prior_intent", False):
                    raise TemporalConformanceError(
                        "durable_intent_before_dispatch",
                        step_idx,
                        op_id,
                        "Dispatch executed without a prior durable intent record",
                    )

                # --- Rule 2: no_blind_retry_after_uncertainty ---
                current_state = op_states.get(op_id, "INIT")
                if current_state == "EFFECT_INDETERMINATE":
                    raise TemporalConformanceError(
                        "no_blind_retry_after_uncertainty",
                        step_idx,
                        op_id,
                        "Re-dispatch attempted while operation was in EFFECT_INDETERMINATE before reconciliation completed",
                    )

                op_states[op_id] = "DISPATCHED"

            elif action in ("TRANSPORT_TIMEOUT_504", "TCP_RST_FAULT", "EFFECT_INDETERMINATE"):
                op_states[op_id] = "EFFECT_INDETERMINATE"
                indeterminate_entry_steps[op_id] = step_idx

            # --- Rule 5: no_settlement_without_authoritative_evidence ---
            elif action in ("RECONCILE_CONFIRMED", "SETTLEMENT_CONFIRMED"):
                has_auth_evidence = (
                    event.get("authoritative_evidence_observed", False)
                    or event.get("authoritative_probe_signature_verified", False)
                    or event.get("target_signed_attestation", False)
                )
                if not has_auth_evidence:
                    raise TemporalConformanceError(
                        "no_settlement_without_authoritative_evidence",
                        step_idx,
                        op_id,
                        "Operation transitioned to CONFIRMED without verified authoritative target evidence",
                    )
                op_states[op_id] = "CONFIRMED"
                indeterminate_entry_steps.pop(op_id, None)

            elif action in ("RECONCILE_REFUTED", "SETTLEMENT_REFUTED"):
                op_states[op_id] = "REFUTED"
                indeterminate_entry_steps.pop(op_id, None)

            elif action == "ESCALATE_UNRESOLVED":
                op_states[op_id] = "UNRESOLVED_ESCALATED"
                indeterminate_entry_steps.pop(op_id, None)

        # --- Rule 3: bounded_reconciliation ---
        unresolved = []
        for op_id, entry_step in indeterminate_entry_steps.items():
            duration = evaluated_steps - entry_step
            if duration > self.max_reconciliation_horizon_steps:
                raise TemporalConformanceError(
                    "bounded_reconciliation",
                    evaluated_steps,
                    op_id,
                    f"Operation remained indeterminate for {duration} steps (horizon={self.max_reconciliation_horizon_steps})",
                )
            unresolved.append(op_id)

        return {
            "valid": True,
            "evaluated_steps": evaluated_steps,
            "active_operations_count": len(op_states),
            "unresolved_within_horizon": unresolved,
            "halt_engaged": halt_latched,
            "rules_checked": [
                "durable_intent_before_dispatch",
                "no_blind_retry_after_uncertainty",
                "bounded_reconciliation",
                "halt_blocks_future_dispatch",
                "no_settlement_without_authoritative_evidence",
            ],
        }


def run_self_test() -> None:
    """Executes a self-test with nominal and falsification vectors."""
    checker = TemporalTraceChecker(max_reconciliation_horizon_steps=20)

    # Nominal trace
    nominal = [
        {"operation_id": "op-t1", "action": "INTENT_STAGED"},
        {"operation_id": "op-t1", "action": "DISPATCH"},
        {"operation_id": "op-t1", "action": "TRANSPORT_TIMEOUT_504"},
        {
            "operation_id": "op-t1",
            "action": "RECONCILE_CONFIRMED",
            "authoritative_evidence_observed": True,
        },
    ]
    res = checker.verify_trace(nominal)
    assert res["valid"] is True, "Nominal trace must pass"

    # Falsification: settlement without evidence
    unattested_settlement = [
        {"operation_id": "op-t2", "action": "INTENT_STAGED"},
        {"operation_id": "op-t2", "action": "DISPATCH"},
        {"operation_id": "op-t2", "action": "RECONCILE_CONFIRMED"},  # missing evidence!
    ]
    try:
        checker.verify_trace(unattested_settlement)
        raise AssertionError("Unattested settlement must fail!")
    except TemporalConformanceError as e:
        assert e.rule_id == "no_settlement_without_authoritative_evidence"

    print("TEMPORAL TRACE CHECKER: Self-test passed (nominal verified, falsification caught).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEIB Temporal Trace Conformance Checker")
    parser.add_argument("--trace", type=str, help="Path to JSON/JSONL trace file")
    parser.add_argument("--self-test", action="store_true", help="Execute built-in self test")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        sys.exit(0)

    if not args.trace:
        parser.print_help()
        sys.exit(1)

    trace_path = Path(args.trace)
    if not trace_path.exists():
        print(f"Error: Trace file not found at {trace_path}")
        sys.exit(1)

    content = trace_path.read_text(encoding="utf-8").strip()
    if content.startswith("["):
        events = json.loads(content)
    else:
        events = [json.loads(line) for line in content.splitlines() if line.strip()]

    checker = TemporalTraceChecker()
    try:
        report = checker.verify_trace(events)
        print("TEMPORAL CONFORMANCE VERIFIED: Trace adheres to all 5 temporal invariants.")
        print(json.dumps(report, indent=2))
        sys.exit(0)
    except TemporalConformanceError as exc:
        print(f"TEMPORAL CONFORMANCE VIOLATION: {exc}")
        sys.exit(1)
