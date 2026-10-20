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

"""
tests/test_execution_integrity_telemetry.py — Unit tests for AEIT.

Validates that:
- Reconciled ambiguous outcomes indicate proper safety handling and do not penalize.
- Unresolved ambiguous outcomes reduce the indicator score.
- Severe faults (halts, policy violations) reduce the indicator score.
- Output contains only descriptive metrics and an input-only indicator.
- Never outputs authorization decisions or insurance underwriting approvals.
"""

from tools.execution_integrity_telemetry import (
    AgentTelemetryInput,
    BoundaryIntegrityEvents,
    ExecutionIntegrityTelemetry,
)


def test_reconciled_uncertainty_is_neutral():
    data = AgentTelemetryInput(
        agent_id="agent-alpha-v2",
        measurement_window="2026-10-01T00:00:00Z/2026-10-31T23:59:59Z",
        total_dispatches=1200,
        ambiguous_outcomes=4,
        ambiguous_outcomes_reconciled=4,
        policy_violations=0,
        halt_events=0,
    )
    result = ExecutionIntegrityTelemetry.evaluate(data)

    assert result["unresolved_ambiguous_outcomes"] == 0
    assert result["execution_integrity_indicator"] == 100.0
    assert result["underwriting_use"] == "input_only_not_decision"
    assert "APPROVED" not in str(result)
    assert "AAA" not in str(result)


def test_unresolved_uncertainty_penalizes_indicator():
    data = AgentTelemetryInput(
        agent_id="agent-beta-uncertain",
        measurement_window="2026-10-01T00:00:00Z/2026-10-31T23:59:59Z",
        total_dispatches=100,
        ambiguous_outcomes=5,
        ambiguous_outcomes_reconciled=2,
        policy_violations=0,
        halt_events=0,
    )
    result = ExecutionIntegrityTelemetry.evaluate(data)

    assert result["unresolved_ambiguous_outcomes"] == 3
    assert result["execution_integrity_indicator"] == 70.0
    assert "Elevated risk signals detected" in result["interpretation"]


def test_severe_faults_lower_indicator_and_clamp():
    data = AgentTelemetryInput(
        agent_id="agent-gamma-failing",
        measurement_window="2026-10-01T00:00:00Z/2026-10-31T23:59:59Z",
        total_dispatches=50,
        ambiguous_outcomes=10,
        ambiguous_outcomes_reconciled=0,
        policy_violations=3,
        halt_events=2,
    )
    result = ExecutionIntegrityTelemetry.evaluate(data)

    assert result["execution_integrity_indicator"] == 0.0
    assert result["unresolved_ambiguous_outcomes"] == 10
    assert result["underwriting_use"] == "input_only_not_decision"
