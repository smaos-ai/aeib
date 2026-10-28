#!/usr/bin/env python3
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

r"""
test_probe_circuit_breaker.py — Acceptance Test AT53 (Probe Amplification DoS Defense)
Evaluates token-bucket rate limiting on probe queries: when thundering-herd
retries occur during an outage, outbound probes are capped at 50 RPS.
Rate exhaustion trips ANSI 86 lockout (ANSI_86_LOCKOUT / COMPENSATION_FAILED).
"""

import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.probe_coalescer import (
    ProbeCoalescer,
    ProbeCircuitBreakerTripped,
    PROBE_CIRCUIT_BREAKER_LIMIT,
)


class TestProbeCircuitBreakerAT53:
    def test_single_flight_coalescing_respects_normal_rate(self):
        call_count = 0

        def dummy_probe(effect_id: str) -> str:
            nonlocal call_count
            call_count += 1
            return "OUTCOME_VERIFIED"

        coalescer = ProbeCoalescer(probe_fn=dummy_probe, rate_limit_rps=50.0, burst_capacity=50.0)

        # 10 calls for the same effect coalesce to 1 physical probe
        for _ in range(10):
            res = coalescer.resolve("effect:test:001")
            assert res == "OUTCOME_VERIFIED"

        assert call_count == 1
        assert not coalescer.is_ansi_86_locked()

    def test_probe_rate_exhaustion_trips_ansi_86_lockout(self):
        def probe_target(effect_id: str) -> str:
            return "OUTCOME_VERIFIED"

        # Configure small capacity of 5 probes to simulate rapid burst exhaustion
        coalescer = ProbeCoalescer(
            probe_fn=probe_target,
            rate_limit_rps=5.0,
            burst_capacity=5.0,
        )

        # First 5 distinct effects consume the burst capacity
        for i in range(5):
            res = coalescer.resolve(f"effect:burst:{i}")
            assert res == "OUTCOME_VERIFIED"

        # 6th distinct effect exceeds capacity and trips the circuit breaker
        with pytest.raises(ProbeCircuitBreakerTripped) as exc_info:
            coalescer.resolve("effect:burst:exhausted")

        assert "ANSI_86_LOCKOUT" in str(exc_info.value)
        assert coalescer.is_ansi_86_locked()

        # Subsequent attempts fail-closed instantly under ANSI 86 lockout
        with pytest.raises(ProbeCircuitBreakerTripped):
            coalescer.resolve("effect:burst:another_call")
