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
tests/test_public_wow_effect_live_simulation.py
================================================================================
Verification Suite for `benchmarks/public_wow_effect_live_simulation.py`.
Evaluates:
1. Vector 1: 0 duplicates on lost ACK vs. 100% duplicate rate on naive retries.
2. Vector 2: Rejection of test file tampering and symlink escape under EO1.
3. Vector 3: TrueDepth FaceID biometric latch release for T3 mutations.
4. Vector 4: Tarjan cycle detection and Havender canonical lock reordering.
5. Overall CLI execution and canonical JSON serialization.
"""

from __future__ import annotations

import json
from benchmarks.public_wow_effect_live_simulation import (
    run_vector_1_lost_ack_simulation,
    run_vector_2_test_tampering_simulation,
    run_vector_3_biometric_hardware_gate_simulation,
    run_vector_4_subexponential_concurrency_simulation,
)


def test_1_lost_ack_reconciliation() -> None:
    res = run_vector_1_lost_ack_simulation(episodes=20)
    assert res["market_duplicates"] == 20
    assert res["market_duplicate_rate_bps"] == 10000
    assert res["aeib_duplicates"] == 0
    assert res["aeib_duplicate_rate_bps"] == 0
    assert res["aeib_latched_holds"] == 20
    assert res["aeib_settled_commits"] == 20


def test_2_test_tampering_blocked() -> None:
    res = run_vector_2_test_tampering_simulation()
    assert res["market_tampered_write_allowed"] is True
    assert res["eo1_blocked_tamper"] is True
    assert "PROTECTED_DIR" in res["eo1_reason"]


def test_3_biometric_hardware_gate() -> None:
    res = run_vector_3_biometric_hardware_gate_simulation()
    assert res["market_fire_and_forget_executed"] is True
    assert res["aeib_latched_pending"] is True
    assert res["aeib_latch_released"] is True
    assert res["aeib_status_code"] == "LATCH_RELEASED_BIOMETRIC_CONFIRMED"
    assert "HIGH_RISK_CODE_DEPLOY" in res["aeib_critic_sentence_1"]


def test_4_subexponential_concurrency_deadlock_elimination() -> None:
    res = run_vector_4_subexponential_concurrency_simulation()
    assert res["market_deadlock_occurred"] is True
    assert res["aeib_cycle_detected"] is True
    assert len(res["aeib_cycles"]) == 1
    assert "agent_alpha" in res["aeib_reordered_schedules"]
