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

"""Test wrapper for AEIB 500-episode execution integrity benchmark."""
import pytest
from benchmarks.aeib_execution_integrity.run_episodes import run_all_episodes, generate_500_episodes


def test_aeib_500_episodes_invariants():
    report = run_all_episodes(seed=42)
    results = report["results"]

    # Invariants under the stated fault model
    assert results["naive_retry_baseline"]["duplicate_mutations"] > 0
    assert results["naive_retry_baseline"]["failure_rate_pct"] > 0.0

    assert results["payload_derived_key"]["duplicate_mutations"] > 0
    assert results["payload_derived_key"]["failure_rate_pct"] > 0.0

    assert results["server_side_stable_key"]["duplicate_mutations"] == 0
    assert results["server_side_stable_key"]["unresolved_episodes"] > 0

    assert results["aeib"]["duplicate_mutations"] == 0
    assert results["aeib"]["failure_rate_pct"] == 0.0
    assert results["aeib"]["rule_of_three_95_upper_bound_pct"] <= 1.0


def test_aeib_5_arm_benchmark_invariants():
    from benchmarks.aeib_execution_integrity.run_5arm_benchmark import run_5arm_benchmark

    report = run_5arm_benchmark(seed=42, count=500)
    results = report["results"]

    assert results["arm_1_naive_retry"]["duplicate_mutations"] > 0
    assert results["arm_2_semantic_drift"]["duplicate_mutations"] > 0
    assert results["arm_3_server_stable_key"]["duplicate_mutations"] == 0
    assert results["arm_3_server_stable_key"]["unresolved_episodes"] > 0
    assert results["arm_4_stable_key_reconciled"]["duplicate_mutations"] == 0
    assert results["arm_4_stable_key_reconciled"]["signed_cryptographic_receipts"] is False
    assert results["arm_5_aeib_full_protocol"]["duplicate_mutations"] == 0
    assert results["arm_5_aeib_full_protocol"]["signed_cryptographic_receipts"] > 0
    assert results["arm_5_aeib_full_protocol"]["offline_verifiability"] is True

