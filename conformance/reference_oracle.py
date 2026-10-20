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
conformance/reference_oracle.py — Pure Mathematical Reference Oracle
Independent, author-agnostic reference implementation used for differential testing.

Evaluates client requests against a minimal, formal state-machine model:
1. Sprint budget accounting (escrowed + settled <= limit)
2. Monotonic clock skew threshold (abs(drift) <= 5s)
3. Bell-LaPadula taint downgrade (TIER_2 requires pinned recipient or step-up)
4. Monotonic per-call delegation ceiling (amount <= max_per_call)
5. Wire recipient vs signed recipient binding
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Callable


@dataclass
class ReferenceOracleState:
    sprint_limit_minor: int
    pinned_recipients: Tuple[str, ...]
    clock_sec: int = 1_760_000_000
    escrowed_minor: int = 0
    settled_minor: int = 0
    ops: Dict[str, Tuple[int, str]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.ops is None:
            self.ops = {}

    def apply_client_request(
        self,
        op_id: str,
        amount_minor: int,
        max_per_call_minor: int,
        signed_recipient: str,
        wire_recipient: str,
        taint_tier: str,
        claimed_ts: int,
    ) -> Tuple[str, str]:
        # 1. Monotonic clock-skew verification
        if abs(claimed_ts - self.clock_sec) > 5:
            return ("NOT_DISPATCHED", "REJECTED_CLOCK_SKEW_OR_MANIPULATION")

        # 2. Replay & Indeterminate latch check
        if op_id in self.ops:
            _, state = self.ops[op_id]
            if state == "EFFECT_INDETERMINATE":
                return ("NOT_DISPATCHED", "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY")
            return ("NOT_DISPATCHED", "REJECTED_DUPLICATE_OPERATION_ID")

        # 3. Delegation ceiling check
        if amount_minor <= 0 or amount_minor > max_per_call_minor:
            return ("NOT_DISPATCHED", "ERR_DELEGATION_ATTENUATION_BREACH")

        # 4. Payee binding check
        if signed_recipient != wire_recipient:
            return ("NOT_DISPATCHED", "ERR_SIGNATURE_OR_PAYEE_MISMATCH")

        # 5. Bell-LaPadula Taint check
        if taint_tier == "TIER_2_UNTRUSTED_EXTERNAL" and wire_recipient not in self.pinned_recipients:
            return ("NOT_DISPATCHED", "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP")

        # 6. Solvency / Sprint limit check
        if self.escrowed_minor + self.settled_minor + amount_minor > self.sprint_limit_minor:
            return ("NOT_DISPATCHED", "HALT_SPRINT_LIMIT_EXCEEDED")

        self.escrowed_minor += amount_minor
        self.ops[op_id] = (amount_minor, "DISPATCHED")
        return ("DISPATCHED", "OK")

    def apply_outcome(self, op_id: str, outcome: str) -> None:
        if op_id not in self.ops:
            return
        amt, prior = self.ops[op_id]
        if prior in ("DISPATCHED", "EFFECT_INDETERMINATE"):
            if outcome == "CONFIRMED":
                self.escrowed_minor -= amt
                self.settled_minor += amt
            elif outcome == "REFUTED":
                self.escrowed_minor -= amt
            self.ops[op_id] = (amt, outcome)


def run_conformance_battery_against_predicate(
    pred_fn: Callable[..., bool]
) -> None:
    """
    Normative Black-Box Conformance Suite.
    Must pass on the genuine predicate and FAIL on every AST mutant.
    """
    good = b"X" * 32
    bad = b"Y" * 32

    # 1. Exact boundary pass: requested_minor == max_per_call_minor == remaining_budget_minor, drift == 5
    assert pred_fn(good, good, "iban:1", "iban:1", 0, False, 500, 500, 500, 5) is True

    # 2. Boundary + 1 fail: requested_minor == 501 > max_per_call_minor (500)
    assert pred_fn(good, good, "iban:1", "iban:1", 0, False, 501, 500, 1000, 0) is False

    # 3. Boundary + 1 fail: requested_minor == 501 > remaining_budget_minor (500)
    assert pred_fn(good, good, "iban:1", "iban:1", 0, False, 501, 1000, 500, 0) is False

    # 4. Zero amount rejected
    assert pred_fn(good, good, "iban:1", "iban:1", 0, False, 0, 500, 500, 0) is False

    # 5. Negative amount rejected
    assert pred_fn(good, good, "iban:1", "iban:1", 0, False, -100, 500, 500, 0) is False

    # 6. Clock drift == 6 rejected
    assert pred_fn(good, good, "iban:1", "iban:1", 0, False, 100, 500, 500, 6) is False

    # 7. Taint tier 2 without warrant rejected; with warrant allowed
    assert pred_fn(good, good, "iban:1", "iban:1", 2, False, 100, 500, 500, 0) is False
    assert pred_fn(good, good, "iban:1", "iban:1", 2, True, 100, 500, 500, 0) is True

    # 8. Payee mismatch rejected
    assert pred_fn(good, good, "iban:evil", "iban:1", 0, False, 100, 500, 500, 0) is False

    # 9. CAID mismatch rejected
    assert pred_fn(bad, good, "iban:1", "iban:1", 0, False, 100, 500, 500, 0) is False
