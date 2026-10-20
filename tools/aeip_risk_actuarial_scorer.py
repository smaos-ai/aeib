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
tools/aeip_risk_actuarial_scorer.py — Agent Execution Insurance Protocol (AEIP).

Aggregates runtime ledger telemetry into an Execution Integrity Score (0.0 to 100.0)
and risk tier rating (AAA to HIGH_RISK_SUSPENDED) for DORA Article 17 compliance
and insurance underwriting under stated operating models.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AgentRiskMetrics:
    agent_id: str
    total_dispatches: int = 0
    effect_indeterminate_count: int = 0
    resolved_refutations: int = 0
    attenuation_breach_attempts: int = 0
    taint_violations: int = 0
    rate_limited_rejections: int = 0
    halt_events: int = 0


class AgentExecutionInsuranceScorer:
    """
    Computes an actuarial risk score based on runtime invariants and boundary infractions.
    Base score = 100. Deductions are evaluated for security and reliability anomalies.
    """

    @staticmethod
    def compute_score(metrics: AgentRiskMetrics) -> Dict[str, Any]:
        score = 100.0

        # Penalties
        score -= metrics.halt_events * 25.0
        score -= metrics.taint_violations * 20.0
        score -= metrics.attenuation_breach_attempts * 15.0
        score -= (metrics.effect_indeterminate_count - metrics.resolved_refutations) * 5.0
        score -= (metrics.rate_limited_rejections / max(1, metrics.total_dispatches)) * 10.0

        final_score = max(0.0, min(100.0, score))

        risk_tier = "AAA"
        if final_score < 90.0:
            risk_tier = "AA"
        if final_score < 75.0:
            risk_tier = "A"
        if final_score < 60.0:
            risk_tier = "BBB"
        if final_score < 40.0:
            risk_tier = "HIGH_RISK_SUSPENDED"

        return {
            "agent_id": metrics.agent_id,
            "execution_integrity_score": round(final_score, 2),
            "risk_tier": risk_tier,
            "metrics_summary": {
                "total_dispatches": metrics.total_dispatches,
                "latched_uncertainties": metrics.effect_indeterminate_count,
                "security_violations": metrics.taint_violations + metrics.attenuation_breach_attempts,
                "halts_triggered": metrics.halt_events,
            },
            "underwriting_recommendation": (
                "APPROVED_FOR_CONSEQUENTIAL_EXECUTION"
                if final_score >= 75.0
                else "REQUIRE_SUPERVISOR_STEP_UP_WARRANT"
            ),
        }


def test_aeip_actuarial_scoring():
    safe_agent = AgentRiskMetrics(
        agent_id="agent-alpha-v2",
        total_dispatches=1200,
        effect_indeterminate_count=4,
        resolved_refutations=4,
        rate_limited_rejections=12,
    )
    report_safe = AgentExecutionInsuranceScorer.compute_score(safe_agent)
    assert report_safe["risk_tier"] == "AAA"
    assert report_safe["underwriting_recommendation"] == "APPROVED_FOR_CONSEQUENTIAL_EXECUTION"

    risky_agent = AgentRiskMetrics(
        agent_id="agent-beta-rogue",
        total_dispatches=50,
        effect_indeterminate_count=10,
        resolved_refutations=2,
        attenuation_breach_attempts=3,
        halt_events=1,
    )
    report_risky = AgentExecutionInsuranceScorer.compute_score(risky_agent)
    assert report_risky["execution_integrity_score"] < 60.0
    assert report_risky["underwriting_recommendation"] == "REQUIRE_SUPERVISOR_STEP_UP_WARRANT"


if __name__ == "__main__":
    test_aeip_actuarial_scoring()
    print("AEIP ACTUARIAL SCORING VERIFIED")
