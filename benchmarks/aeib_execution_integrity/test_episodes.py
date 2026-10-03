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
    
    assert results["naive_retry_baseline"]["duplicate_mutations"] == 500
    assert results["naive_retry_baseline"]["failure_rate_pct"] == 100.0
    
    assert results["payload_derived_key"]["duplicate_mutations"] == 314
    assert results["payload_derived_key"]["failure_rate_pct"] == 62.8
    
    assert results["server_side_stable_key"]["duplicate_mutations"] == 0
    assert results["server_side_stable_key"]["unresolved_episodes"] > 0
    
    assert results["aeib"]["duplicate_mutations"] == 0
    assert results["aeib"]["failure_rate_pct"] == 0.0
    assert results["aeib"]["rule_of_three_95_upper_bound_pct"] == 0.60
