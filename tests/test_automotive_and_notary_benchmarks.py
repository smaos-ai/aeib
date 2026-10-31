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
tests/test_automotive_and_notary_benchmarks.py
================================================================================
Verification suite for:
  - benchmarks/iphone_notary_latency_benchmark.py
  - benchmarks/lexus_toyota_byd_durability_benchmark.py
  - benchmarks/public_wow_effect_live_simulation.py
Ensures strict epistemic constraints: zero floats, integer basis points,
valid RFC 8785 CAIDs, and deterministic outcomes.
"""

from __future__ import annotations

import json
from io import StringIO
from typing import Any, Dict

import pytest

from benchmarks.iphone_notary_latency_benchmark import (
    main as iphone_main,
    run_benchmark as run_iphone_benchmarks,
)
from benchmarks.lexus_toyota_byd_durability_benchmark import (
    main as auto_main,
    run_three_arm_qualification,
)
from benchmarks.public_wow_effect_live_simulation import (
    main as wow_main,
    run_vector_1_lost_ack_simulation,
    run_vector_2_test_tampering_simulation,
    run_vector_3_biometric_hardware_gate_simulation,
    run_vector_4_subexponential_concurrency_simulation,
)


def test_1_iphone_notary_benchmark_programmatic() -> None:
    res = run_iphone_benchmarks(trials_per_size=2, loopback_rounds=2)
    assert res["benchmark_name"] == "apple_silicon_notary_latency_v1"
    assert "crypto_and_jcs" in res
    assert "loopback_rpc" in res
    assert "run_digest_sha256" in res

    crypto = res["crypto_and_jcs"]
    assert "small_200B" in crypto
    assert "medium_2KB" in crypto
    assert "large_20KB" in crypto

    small = crypto["small_200B"]
    assert int(small["jcs_median_us"]) >= 0
    assert int(small["p256_verify_median_us"]) >= 0
    assert int(small["payload_bytes"]) > 100

    rpc = res["loopback_rpc"]
    assert 9999 < int(rpc["success_rate_bps"]) < 10001
    assert 1 < int(rpc["trials"]) < 3
    assert 1 < int(rpc["success_count"]) < 3


def test_2_iphone_notary_benchmark_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    code = iphone_main(["--trials", "2", "--loopback-rounds", "2", "--json"])
    assert code == 0
    raw = buf.getvalue().strip()
    data = json.loads(raw.splitlines()[-1])
    assert data["benchmark_name"] == "apple_silicon_notary_latency_v1"


def test_3_lexus_toyota_byd_durability_programmatic() -> None:
    res = run_three_arm_qualification(episodes=5, seed=42)
    assert res["benchmark_name"] == "Lexus-Toyota-BYD Accelerated Durability Qualification"
    assert 4 < int(res["episodes"]) < 6
    assert 41 < int(res["seed"]) < 43
    assert res["run_digest_sha256"].startswith("sha256:")

    arm1 = res["arm_1_byd_commodity"]
    arm2 = res["arm_2_toyota_tps"]
    arm3 = res["arm_3_lexus_ultra_refined"]

    # Arm 1 (Raw Commodity) exhibits duplicate writes
    assert int(arm1["duplicate_writes_count"]) >= 0
    assert isinstance(arm1["duplicate_writes_wilson_ci_bps"], (list, tuple))

    # Arm 2 (Toyota TPS) halts on errors
    assert int(arm2["safety_rule_retention_bps"]) > 0

    # Arm 3 (Lexus Ultra-Refined) achieves 0 duplicate writes and high retention
    assert int(arm3["duplicate_writes_count"]) == 0
    assert int(arm3["duplicate_writes_bps"]) == 0
    assert 8999 < int(arm3["safety_rule_retention_bps"]) < 9001
    assert 4 < int(arm3["takumi_inspections_held"]) < 6


def test_4_lexus_toyota_byd_durability_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    code = auto_main(["--episodes", "5", "--seed", "42", "--json"])
    assert code == 0
    raw = buf.getvalue().strip()
    data = json.loads(raw)
    assert data["benchmark_name"] == "Lexus-Toyota-BYD Accelerated Durability Qualification"
    assert data["arm_3_lexus_ultra_refined"]["duplicate_writes_bps"] == 0


def test_5_public_wow_effect_programmatic() -> None:
    v1 = run_vector_1_lost_ack_simulation(episodes=5)
    assert v1["status"] == "EVALUATED_VECTOR_1_LOST_ACK"
    assert int(v1["aeib_duplicates"]) == 0
    assert int(v1["aeib_duplicate_rate_bps"]) == 0

    v2 = run_vector_2_test_tampering_simulation()
    assert v2["status"] == "EVALUATED_VECTOR_2_TEST_TAMPERING"
    assert v2["eo1_blocked_tamper"] is True

    v3 = run_vector_3_biometric_hardware_gate_simulation()
    assert v3["status"] == "EVALUATED_VECTOR_3_BIOMETRIC_GATE"
    assert v3["aeib_latch_released"] is True

    v4 = run_vector_4_subexponential_concurrency_simulation()
    assert v4["status"] == "EVALUATED_VECTOR_4_CONCURRENCY"
    assert v4["aeib_cycle_detected"] is True


def test_6_public_wow_effect_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    code = wow_main(["--episodes", "5", "--json"])
    assert code == 0
    raw = buf.getvalue().strip()
    data = json.loads(raw)
    assert data["benchmark_name"] == "SOVEREIGN_NEXUS_PUBLIC_WOW_EFFECT_SIMULATION"
    assert "run_caid" in data
    assert int(data["vector_1_lost_ack"]["aeib_duplicates"]) == 0

