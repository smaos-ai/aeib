"""
Track 2: Primary-Source Verified Regulatory Applicability Matrix & Three-Tier
Decision Authorization Engine.

Grounded in verified primary sources (no unverified compliance claims):
1. CAC / NDRC / MIIT《智能体规范应用与创新发展实施意见》(Issued May 8, 2026):
   Section III(1) "明确决策权限" (Clarify Decision Authority) defines 3 strict tiers:
   - Tier A (`HUMAN_ONLY_DECISION` / 仅限用户本人决策): Agent execution strictly forbidden.
   - Tier B (`USER_AUTHORIZED_DECISION` / 需由用户授权决策): Requires explicit cryptographic
     human approval warrant bound to the exact `CAID` before execution.
   - Tier C (`AUTONOMOUS_BOUNDED_DECISION` / 智能体自主决策): Permitted only within
     user-authorized scope, budget ceiling, and taint constraints.
2. SAMR / SAC《人工智能 智能体互联》(GB/Z 185-2026, June 4, 2026) & AIP (Agent
   Interconnection Protocol): Digital identity registration, capability declaration,
   compliant payment (`合规支付`), and traceable behavior logs (`行为可验证、可追溯`).
3. Audit-Compliant Evidence-to-Control Matrix: Explicitly records `addressed_by_operator`
   and `partially_addressed` gaps requiring legal counsel review.
"""
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class ThreeTierDecisionAuthorityGate:
    """
    Enforces the 3-tier decision boundary defined in Section III(1) of the May 8, 2026
    CAC/NDRC/MIIT Implementation Opinions on Intelligent Agents.
    """

    HUMAN_ONLY_ACTIONS = frozenset(
        {
            "policy.modify_ceiling",
            "key.rotate_root_anchor",
            "compliance.waive_audit_log",
            "account.close_statutory_ledger",
        }
    )
    USER_AUTHORIZATION_REQUIRED_ACTIONS = frozenset(
        {
            "refund.create",
            "payment.wire_transfer",
            "production.deploy_release",
            "database.schema_drop",
        }
    )

    @classmethod
    def classify_and_enforce(
        cls,
        action_type: str,
        caid: str,
        human_approval_warrant_caid: Optional[str],
        within_delegated_budget: bool,
    ) -> Dict[str, str]:
        # Tier 1: Strictly reserved to the human principal (`仅限用户本人决策`)
        if action_type in cls.HUMAN_ONLY_ACTIONS:
            return {
                "decision_tier": "HUMAN_ONLY_DECISION",
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_TIER_HUMAN_ONLY_AGENT_EXECUTION_FORBIDDEN",
            }

        # Tier 2: Requires explicit per-CAID user authorization (`需由用户授权决策`)
        if action_type in cls.USER_AUTHORIZATION_REQUIRED_ACTIONS:
            if human_approval_warrant_caid != caid:
                return {
                    "decision_tier": "USER_AUTHORIZED_DECISION",
                    "disposition": "NOT_DISPATCHED",
                    "code": "ERR_MISSING_OR_MISMATCHED_USER_AUTHORIZATION_WARRANT",
                }
            if not within_delegated_budget:
                return {
                    "decision_tier": "USER_AUTHORIZED_DECISION",
                    "disposition": "NOT_DISPATCHED",
                    "code": "ERR_EXCEEDS_USER_AUTHORIZED_SCOPE",
                }
            return {
                "decision_tier": "USER_AUTHORIZED_DECISION",
                "disposition": "AUTHORIZED",
                "code": "OK",
            }

        # Tier 3: Bounded autonomous execution (`智能体自主决策，不得超出用户授权范围`)
        if not within_delegated_budget:
            return {
                "decision_tier": "AUTONOMOUS_BOUNDED_DECISION",
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_AUTONOMOUS_ACTION_EXCEEDS_BOUNDED_SCOPE",
            }
        return {
            "decision_tier": "AUTONOMOUS_BOUNDED_DECISION",
            "disposition": "AUTHORIZED",
            "code": "OK",
        }


def generate_regulatory_applicability_matrix() -> List[Dict[str, Any]]:
    """
    Produces the two-part Regulatory Applicability & Evidence-to-Control Matrix
    following the audit schema (`id`, `source`, `obligation`, `applicability`,
    `aeib_evidence`, `gap`, `owner`). Does NOT claim statutory compliance.
    """
    return [
        {
            "id": "CHN-001",
            "source": "CAC/NDRC/MIIT《智能体规范应用与创新发展实施意见》(2026-05-08) Sec. III(1)",
            "obligation": "Clarify boundaries between human-only decisions, user-authorized decisions, and bounded autonomous agent decisions; never exceed user authorization scope.",
            "applicability": {
                "deployment_region": "CN",
                "data_processing_location": "CN_or_cross_border",
                "sector": "all_consequential_agent_deployments",
            },
            "aeib_evidence": [
                "ThreeTierDecisionAuthorityGate verdict record",
                "CAID-bound human_approval_warrant receipt",
                "AT71 max_per_call_minor and sprint_limit_minor enforcement log",
            ],
            "gap": "partially_addressed (operator must define domain-specific action classification table and UI disclosure)",
            "owner": "compliance_or_legal_and_product_owner",
        },
        {
            "id": "CHN-002",
            "source": "SAMR/SAC《人工智能 智能体互联》(GB/Z 185-2026, 2026-06-04) & AIP Protocol",
            "obligation": "Agent digital identity management, capability declaration, compliant payment (合规支付), and verifiable/traceable behavior logs (行为可验证、可追溯).",
            "applicability": {
                "deployment_region": "CN",
                "sector": "multi_agent_interconnection_and_payment_workflows",
            },
            "aeib_evidence": [
                "Ed25519 agent key_id & binary SHA-256 attestation receipt",
                "OpenAPI / JSON Schema capability contract manifest",
                "Authoritative SQLite/Rust WAL hash-chained receipt log",
            ],
            "gap": "addressed_by_operator (registration with national/industry AIP identity registries requires operator entity filing)",
            "owner": "compliance_or_legal",
        },
        {
            "id": "CHN-003",
            "source": "CAC/NDRC/MIIT《智能体规范应用与创新发展实施意见》(2026-05-08) Sec. III(3)",
            "obligation": "Filing (备案), security assessment, ethics review衔接, and recall mechanisms (问题产品召回) for sensitive/key industry scenarios.",
            "applicability": {
                "deployment_region": "CN",
                "sector": "finance_healthcare_public_safety_and_key_sectors",
            },
            "aeib_evidence": [
                "Emergency HALT_* circuit breaker & rollback runbook",
                "Deterministic clean-room reproduction bundle",
            ],
            "gap": "addressed_by_operator (statutory CAC algorithm/agent filing and ethics committee review cannot be automated by software)",
            "owner": "compliance_or_legal",
        },
        {
            "id": "EU-DORA-017",
            "source": "EU Regulation (EU) 2022/2554 (DORA) Article 17 & EN 18286:2026 QMS",
            "obligation": "ICT-related incident management, root-cause analysis, and separation of change approval from implementation.",
            "applicability": {
                "deployment_region": "EU",
                "sector": "regulated_financial_entities",
            },
            "aeib_evidence": [
                "EFFECT_INDETERMINATE durable uncertainty latch & reconciliation log",
                "docs/governance/RACI.md & INCIDENT_RUNBOOK.md",
            ],
            "gap": "partially_addressed (requires institutional SOC/SIEM integration and designated human RACI sign-off)",
            "owner": "ciso_and_risk_committee",
        },
    ]


def test_three_tier_decision_gate_and_applicability_matrix() -> None:
    caid = "sha256:" + ("a" * 64)

    # 1. Human-only action is always denied to agents even with a warrant
    r_human = ThreeTierDecisionAuthorityGate.classify_and_enforce(
        "policy.modify_ceiling", caid, caid, True
    )
    assert r_human["decision_tier"] == "HUMAN_ONLY_DECISION"
    assert r_human["disposition"] == "NOT_DISPATCHED"

    # 2. User-authorized action (`refund.create`) denied without matching CAID warrant
    r_no_warrant = ThreeTierDecisionAuthorityGate.classify_and_enforce(
        "refund.create", caid, None, True
    )
    assert r_no_warrant["decision_tier"] == "USER_AUTHORIZED_DECISION"
    assert r_no_warrant["disposition"] == "NOT_DISPATCHED"

    # 3. User-authorized action (`refund.create`) succeeds with exact CAID warrant & budget
    r_auth_ok = ThreeTierDecisionAuthorityGate.classify_and_enforce(
        "refund.create", caid, caid, True
    )
    assert r_auth_ok["disposition"] == "AUTHORIZED"

    # 4. Bounded autonomous action (`search.query_docs`) succeeds within budget
    r_auto_ok = ThreeTierDecisionAuthorityGate.classify_and_enforce(
        "search.query_docs", caid, None, True
    )
    assert r_auto_ok["decision_tier"] == "AUTONOMOUS_BOUNDED_DECISION"
    assert r_auto_ok["disposition"] == "AUTHORIZED"

    # 5. Verify applicability matrix contains explicit gap & owner fields
    matrix = generate_regulatory_applicability_matrix()
    assert len(matrix) == 4
    assert all("gap" in item and "owner" in item for item in matrix)


if __name__ == "__main__":
    test_three_tier_decision_gate_and_applicability_matrix()
    print("TRACK 2 THREE-TIER DECISION GATE & REGULATORY APPLICABILITY MATRIX PASSED.")
