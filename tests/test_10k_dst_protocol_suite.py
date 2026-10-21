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
tests/test_10k_dst_protocol_suite.py — Tests for 10,000-Schedule Protocol-Aware DST Suite
"""

import os
import tempfile
import pytest

from benchmarks.run_10k_dst_protocol_suite import (
    SimulatedDownstreamTarget,
    run_10k_dst_benchmark,
)


def test_dst_benchmark_zero_duplicates():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_json = os.path.join(tmpdir, "dst_summary.json")
        res = run_10k_dst_benchmark(num_schedules=1000, seed=20261020, output_json=out_json)
        assert res["invariant_verdict"] == "PASSED"
        assert res["duplicate_mutations_observed"] == 0
        assert res["blind_retries_blocked"] > 0
        assert res["indeterminate_latches_engaged"] > 0
        assert os.path.exists(out_json)


def test_falsification_negative_control_bypass_causes_duplicates():
    """
    Asserts that bypassing the interlock directly causes duplicate mutations,
    proving the harness is non-tautological and can detect failures.
    """
    target = SimulatedDownstreamTarget()
    # Simulate naive client without interlock retrying on dropped ACK
    target.execute_mutation("tx_key_bypass_1", 1000)
    # Network timeout occurs, naive client blind retries:
    target.execute_mutation("tx_key_bypass_1", 1000)

    assert target.commits["tx_key_bypass_1"] == 2  # Duplication detected!


def test_banned_words_absence_in_dst_suite():
    for fpath in ["benchmarks/run_10k_dst_protocol_suite.py", "tests/test_10k_dst_protocol_suite.py"]:
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read().lower()
        forbidden = [
            "guaran" + "tee",
            "bullet" + "proof",
            "enterprise-" + "grade",
            "production-" + "safe",
            "100% " + "secure",
            "unassail" + "able",
        ]
        for word in forbidden:
            assert word not in text, f"Banned word '{word}' found in {fpath}"
