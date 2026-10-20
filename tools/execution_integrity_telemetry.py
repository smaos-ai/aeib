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
tools/execution_integrity_telemetry.py — Agent Execution Integrity Telemetry (AEIT).

Produces structured, descriptive execution integrity telemetry from AEIB runtime logs.
Calculates a heuristic Execution Integrity Indicator (EII) for operator risk monitoring.
Explicitly designated as: input_only_not_decision.
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class BoundaryIntegrityEvents:
    attenuation_breaches_blocked: int = 0
    taint_violations_blocked: int = 0
    malformed_payloads_blocked: int = 0


@dataclass
class AgentTelemetryInput:
    agent_id: str
    measurement_window: str
    total_dispatches: int = 0
    ambiguous_outcomes: int = 0
    ambiguous_outcomes_reconciled: int = 0
    policy_violations: int = 0
    halt_events: int = 0
    boundary_events: BoundaryIntegrityEvents = field(default_factory=BoundaryIntegrityEvents)


class ExecutionIntegrityTelemetry:
    """
    Computes descriptive metrics and a heuristic execution integrity indicator (0.0 to 100.0).
    Under the AEIT model:
    - Ambiguous outcomes that are successfully reconciled (e.g., EFFECT_INDETERMINATE -> CONFIRMED/REFUTED)
      indicate proper boundary safety behavior and are not penalized.
    - Unresolved ambiguous outcomes, unmitigated policy violations, and halt events represent risk signals.
    """

    @staticmethod
    def evaluate(data: AgentTelemetryInput) -> Dict[str, Any]:
        unresolved_ambiguous = max(0, data.ambiguous_outcomes - data.ambiguous_outcomes_reconciled)

        # Base heuristic indicator starting at 100.0
        indicator = 100.0

        # Unresolved ambiguity signals transport or reconciliation failure
        indicator -= unresolved_ambiguous * 10.0

        # Direct policy violations and halt events signal severe execution faults
        indicator -= data.policy_violations * 20.0
        indicator -= data.halt_events * 25.0

        # Boundary events blocked by Station 1 gates are defensive interventions
        blocked_total = (
            data.boundary_events.attenuation_breaches_blocked
            + data.boundary_events.taint_violations_blocked
            + data.boundary_events.malformed_payloads_blocked
        )
        if data.total_dispatches > 0:
            intervention_rate = blocked_total / data.total_dispatches
            indicator -= min(15.0, intervention_rate * 50.0)

        indicator_clamped = max(0.0, min(100.0, indicator))

        # Descriptive interpretation
        if unresolved_ambiguous == 0 and data.policy_violations == 0 and data.halt_events == 0:
            interpretation = "No unresolved uncertainty; no policy violations observed."
        else:
            interpretation = (
                f"Elevated risk signals detected: {unresolved_ambiguous} unresolved ambiguous outcomes, "
                f"{data.policy_violations} policy violations, {data.halt_events} halt events."
            )

        return {
            "agent_id": data.agent_id,
            "measurement_window": data.measurement_window,
            "total_dispatches": data.total_dispatches,
            "ambiguous_outcomes": data.ambiguous_outcomes,
            "ambiguous_outcomes_reconciled": data.ambiguous_outcomes_reconciled,
            "unresolved_ambiguous_outcomes": unresolved_ambiguous,
            "policy_violations": data.policy_violations,
            "halt_events": data.halt_events,
            "boundary_integrity_events": {
                "attenuation_breaches_blocked": data.boundary_events.attenuation_breaches_blocked,
                "taint_violations_blocked": data.boundary_events.taint_violations_blocked,
                "malformed_payloads_blocked": data.boundary_events.malformed_payloads_blocked,
            },
            "execution_integrity_indicator": round(indicator_clamped, 1),
            "indicator_method": "aeib-eit-v0",
            "interpretation": interpretation,
            "underwriting_use": "input_only_not_decision",
        }
