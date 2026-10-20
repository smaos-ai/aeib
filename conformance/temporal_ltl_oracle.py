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
conformance/temporal_ltl_oracle.py — Linear Temporal Logic (LTL) Trace Conformance Oracle
Sovereign Multi-Agent OS (SMAOS) / AEIB Track A: Temporal Safety Verification.

Evaluates replay execution traces against formal LTL business & safety invariants:
1. NO_BLIND_RETRY:
   G(effect_indeterminate -> X(!dispatch_until_reconciled))
   After an indeterminate transport outcome, no further dispatch is permitted for the
   same operation until terminal reconciliation (CONFIRMED or REFUTED) occurs.

2. RECEIPT_BEFORE_DISPATCH:
   G(dispatched -> receipt_exists)
   Every dispatched operation must possess a durable pre-dispatch intent receipt.

3. RECONCILIATION_BOUNDED:
   G(effect_indeterminate -> F(confirmed | refuted | unresolved_escalated))
   Any indeterminate latch must eventually reach terminal settlement or supervisor escalation.

4. HALT_ENFORCED:
   G(halt_engaged -> X(!dispatch))
   Once a security or continuity halt is latched, no subsequent consequential mutations may occur.
"""

from typing import Dict, Any, List, Optional, Set


class LTLViolationError(Exception):
    def __init__(self, rule_name: str, step_index: int, operation_id: str, message: str):
        super().__init__(f"LTL VIOLATION [{rule_name}] at step {step_index} (op: {operation_id}): {message}")
        self.rule_name = rule_name
        self.step_index = step_index
        self.operation_id = operation_id
        self.message = message


class TemporalLTLTraceOracle:
    """
    Automaton-based LTL runtime trace validator.
    Evaluates sequences of execution events against formal temporal safety invariants.
    """

    def __init__(self, max_reconciliation_horizon_steps: int = 100):
        self.max_reconciliation_horizon_steps = max_reconciliation_horizon_steps

    def verify_trace(self, trace_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates a complete trace against all four temporal invariants.
        Returns a verification summary dict or raises LTLViolationError on first breach.
        """
        # Tracking state
        # op_id -> current state: "INIT", "DISPATCHED", "EFFECT_INDETERMINATE", "CONFIRMED", "REFUTED"
        op_states: Dict[str, str] = {}
        # op_id -> step_index when entered EFFECT_INDETERMINATE
        indeterminate_steps: Dict[str, int] = {}
        # operations with verified receipts
        receipt_store: Set[str] = set()
        halt_latched = False
        halt_step = -1

        evaluated_steps = 0

        for step_idx, event in enumerate(trace_events):
            evaluated_steps += 1
            op_id = event.get("operation_id", "")
            action = event.get("action", "")
            receipt_id = event.get("receipt_id")

            # --- Rule 4: HALT_ENFORCED (G(halt_engaged -> X(!dispatch))) ---
            if halt_latched:
                if action == "DISPATCH":
                    raise LTLViolationError(
                        "RULE_HALT_ENFORCED",
                        step_idx,
                        op_id,
                        f"Dispatch attempted at step {step_idx} while gate was halted since step {halt_step}",
                    )

            if event.get("is_halt_trigger", False) or action == "HALT":
                halt_latched = True
                halt_step = step_idx

            # Track receipt creation
            if action in ("RECEIPT_CREATED", "INTENT_STAGED") or receipt_id:
                receipt_store.add(op_id)

            # --- Rule 2: RECEIPT_BEFORE_DISPATCH (G(dispatched -> receipt_exists)) ---
            if action == "DISPATCH":
                if op_id not in receipt_store and not event.get("has_prior_receipt", False):
                    raise LTLViolationError(
                        "RULE_RECEIPT_BEFORE_DISPATCH",
                        step_idx,
                        op_id,
                        "Dispatch executed without a verified prior intent receipt",
                    )

                # --- Rule 1: NO_BLIND_RETRY (G(effect_indeterminate -> X(!dispatch_until_reconciled))) ---
                current_op_state = op_states.get(op_id, "INIT")
                if current_op_state == "EFFECT_INDETERMINATE":
                    raise LTLViolationError(
                        "RULE_NO_BLIND_RETRY",
                        step_idx,
                        op_id,
                        "Blind retry dispatch executed while operation was in EFFECT_INDETERMINATE before reconciliation",
                    )

                op_states[op_id] = "DISPATCHED"

            elif action == "TRANSPORT_TIMEOUT_504":
                op_states[op_id] = "EFFECT_INDETERMINATE"
                indeterminate_steps[op_id] = step_idx

            elif action in ("RECONCILE_CONFIRMED", "SETTLEMENT_CONFIRMED"):
                op_states[op_id] = "CONFIRMED"
                indeterminate_steps.pop(op_id, None)

            elif action in ("RECONCILE_REFUTED", "SETTLEMENT_REFUTED"):
                op_states[op_id] = "REFUTED"
                indeterminate_steps.pop(op_id, None)

            elif action == "ESCALATE_UNRESOLVED":
                op_states[op_id] = "UNRESOLVED_ESCALATED"
                indeterminate_steps.pop(op_id, None)

        # --- Rule 3: RECONCILIATION_BOUNDED (G(effect_indeterminate -> F(confirmed | refuted | escalated))) ---
        # Any remaining indeterminate state must not exceed max horizon
        unresolved_operations = []
        for op_id, step_entered in indeterminate_steps.items():
            duration = evaluated_steps - step_entered
            if duration > self.max_reconciliation_horizon_steps:
                raise LTLViolationError(
                    "RULE_RECONCILIATION_BOUNDED",
                    evaluated_steps,
                    op_id,
                    f"Operation remained in indeterminate state for {duration} steps (horizon={self.max_reconciliation_horizon_steps})",
                )
            unresolved_operations.append(op_id)

        return {
            "valid": True,
            "evaluated_steps": evaluated_steps,
            "terminal_operations": len(op_states),
            "unresolved_within_horizon": unresolved_operations,
            "halt_engaged": halt_latched,
            "rules_checked": [
                "RULE_NO_BLIND_RETRY",
                "RULE_RECEIPT_BEFORE_DISPATCH",
                "RULE_RECONCILIATION_BOUNDED",
                "RULE_HALT_ENFORCED",
            ],
        }
