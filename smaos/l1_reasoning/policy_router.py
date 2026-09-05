"""
Policy Router for SMAOS Phase 1

Routes AI decisions through EU AI Act compliance framework.
Each pilot maps to specific Articles/Annexes based on use case risk.

Why this approach:
- Policy-bound decisions enforce compliance upfront (not after)
- Each pilot has different risk profile → different Article citations
- Transparent audit trail (pilot_name → articles → decision)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4


class RiskLevel(Enum):
    """EU AI Act risk classification (Article 6)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PROHIBITED = "prohibited"


@dataclass
class PolicyRoute:
    """Decision record with full compliance trail."""
    route_id: str
    pilot_name: str  # hotel | glass | school
    risk_level: RiskLevel
    articles: List[str]  # Which EU AI Act Articles apply
    annex_sections: List[str]  # Which Annex sections apply
    decision: str
    reasoning: str
    timestamp: str
    compliance_score: int  # 0-100 (must be ≥80 to proceed)
    audit_trail: str = ""

    def __post_init__(self):
        if self.compliance_score < 80:
            raise ValueError(f"Compliance score {self.compliance_score} below minimum 80")


class PolicyRouter:
    """
    SMAOS Policy Router for EU AI Act compliance.

    Patterns for each pilot:
    - Hotel credit scoring: Uses GPAI (Article 51) + essential service (Annex III)
    - Glass safety review: Uses high-risk (Article 6 + Annex I)
    - School access control: Uses education (Article 6 + Annex III)
    """

    # Articles and their purposes
    ARTICLES = {
        "Article 5": "Prohibited AI practices (behavioral manipulation, children, discrimination)",
        "Article 6": "High-risk AI classification and management",
        "Article 13": "Documentation and record-keeping requirements",
        "Article 14": "Model cards and documentation for accuracy/robustness",
        "Article 50": "Transparency and disclosure obligations",
        "Article 51": "General-purpose AI (GPAI) governance",
    }

    # Annex sections
    ANNEXES = {
        "Annex I": "High-risk AI systems (8 categories: biometric, critical infrastructure, etc)",
        "Annex III": "Prohibited AI uses in employment, education, essential services",
    }

    # Pilot-specific policies
    PILOT_POLICIES = {
        "hotel": {
            "risk_level": RiskLevel.HIGH,
            "articles": ["Article 50", "Article 51", "Article 14"],
            "annexes": ["Annex III"],
            "reasoning": "Credit scoring affects essential financial service. GPAI (Article 51) applies. "
                         "Must disclose chatbot nature (Article 50), document accuracy (Article 14), "
                         "and avoid Annex III prohibited use in employment/finance decisions.",
            "min_compliance": 90,
        },
        "glass": {
            "risk_level": RiskLevel.HIGH,
            "articles": ["Article 6", "Article 13", "Article 14"],
            "annexes": ["Annex I"],
            "reasoning": "Safety-critical system (glass defect detection affects user safety). "
                         "Annex I applies (safety component in high-risk category). "
                         "Requires robust documentation (Article 13, 14) and risk management.",
            "min_compliance": 85,
        },
        "school": {
            "risk_level": RiskLevel.HIGH,
            "articles": ["Article 6", "Article 50", "Article 14"],
            "annexes": ["Annex III"],
            "reasoning": "Education access control affects minors and essential service. "
                         "Annex III applies (education). Requires transparency (Article 50), "
                         "risk mitigation (Article 6), and robustness documentation (Article 14).",
            "min_compliance": 88,
        },
    }

    def __init__(self):
        """Initialize policy router with SMAOS configurations."""
        self.router_id = str(uuid4())[:8]
        self.routes = []

    def validate_pilot(self, pilot_name: str) -> bool:
        """Check if pilot is registered in SMAOS."""
        return pilot_name in self.PILOT_POLICIES

    def route_request(
        self,
        pilot_name: str,
        request_description: str,
        compliance_assessment: Optional[int] = None,
    ) -> PolicyRoute:
        """
        Route a request through compliance framework.

        Args:
            pilot_name: "hotel", "glass", or "school"
            request_description: What the AI will do
            compliance_assessment: Pre-calculated compliance score (0-100)

        Returns:
            PolicyRoute with decision and audit trail

        Raises:
            ValueError: If pilot unknown or compliance score too low
        """
        if not self.validate_pilot(pilot_name):
            raise ValueError(f"Unknown pilot: {pilot_name}. Must be: hotel, glass, school")

        policy = self.PILOT_POLICIES[pilot_name]

        # Use provided assessment or default to minimum
        if compliance_assessment is None:
            compliance_score = policy["min_compliance"]
        else:
            compliance_score = min(100, max(0, compliance_assessment))

        # Enforce both global and pilot-specific minimums
        if compliance_score < 80:
            raise ValueError(
                f"Pilot '{pilot_name}' requires compliance ≥80, got {compliance_score}"
            )

        if compliance_score < policy["min_compliance"]:
            raise ValueError(
                f"Pilot '{pilot_name}' requires compliance ≥{policy['min_compliance']}, got {compliance_score}"
            )

        # Build audit trail
        audit_trail = self._build_audit_trail(pilot_name, request_description, policy)

        # Create route record
        route = PolicyRoute(
            route_id=str(uuid4()),
            pilot_name=pilot_name,
            risk_level=policy["risk_level"],
            articles=policy["articles"],
            annex_sections=policy["annexes"],
            decision="APPROVED" if compliance_score >= policy["min_compliance"] else "DENIED",
            reasoning=policy["reasoning"],
            timestamp=datetime.now(timezone.utc).isoformat(),
            compliance_score=compliance_score,
            audit_trail=audit_trail,
        )

        self.routes.append(route)
        return route

    def _build_audit_trail(
        self, pilot_name: str, request_description: str, policy: dict
    ) -> str:
        """Build human-readable audit trail for decision."""
        trail = f"""
POLICY ROUTING AUDIT TRAIL
══════════════════════════════════════════════════════════
Pilot: {pilot_name.upper()}
Request: {request_description[:100]}...
Decision Date: {datetime.now(timezone.utc).isoformat()}

Risk Level: {policy['risk_level'].value.upper()}

Applicable Articles:
{self._format_articles(policy['articles'])}

Applicable Annexes:
{self._format_annexes(policy['annexes'])}

Compliance Reasoning:
{policy['reasoning']}

Enforcement Action: Decision routed to L2 Knowledge layer for policy enforcement.
Monitoring: Article 14 documentation requirements active.
══════════════════════════════════════════════════════════
"""
        return trail.strip()

    def _format_articles(self, articles: List[str]) -> str:
        """Format article list for audit trail."""
        return "\n".join(
            f"  ✓ {article}: {self.ARTICLES.get(article, 'Unknown')}"
            for article in articles
        )

    def _format_annexes(self, annexes: List[str]) -> str:
        """Format annex list for audit trail."""
        return "\n".join(
            f"  ✓ {annex}: {self.ANNEXES.get(annex, 'Unknown')}"
            for annex in annexes
        )

    def get_routes(self) -> List[PolicyRoute]:
        """Return all routed decisions (audit log)."""
        return self.routes.copy()

    def cite_article(self, article: str) -> str:
        """Get citation text for an article."""
        return self.ARTICLES.get(article, f"{article}: Not found in registry")

    def cite_annex(self, annex: str) -> str:
        """Get citation text for an annex section."""
        return self.ANNEXES.get(annex, f"{annex}: Not found in registry")

    def enforce_policy(self, route: PolicyRoute) -> dict:
        """
        Enforce policy decision (pass to L2/L3 layers).

        Returns enforcement metadata for downstream processing.
        """
        return {
            "route_id": route.route_id,
            "pilot": route.pilot_name,
            "enforcement_level": "STRICT" if route.risk_level == RiskLevel.HIGH else "NORMAL",
            "articles_to_enforce": route.articles,
            "annexes_to_enforce": route.annex_sections,
            "decision": route.decision,
            "compliance_requirement": f"≥{90 if route.risk_level == RiskLevel.HIGH else 80}%",
        }
