"""
Test suite for SMAOS L1 Policy Router

Tests verify:
1. Correct Article citations for each pilot
2. Risk classification and compliance scoring
3. Audit trail generation
4. Policy enforcement metadata
5. Edge cases (invalid pilots, low compliance scores)
"""

import pytest
from policy_router import PolicyRouter, PolicyRoute, RiskLevel


class TestPolicyRouterBasics:
    """Test core policy routing functionality."""

    def test_router_initialization(self):
        """Router initializes with unique ID."""
        router = PolicyRouter()
        assert router.router_id is not None
        assert len(router.router_id) == 8

    def test_hotel_pilot_routing(self):
        """Hotel pilot routes with correct articles."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="hotel",
            request_description="Credit scoring for guest financing",
            compliance_assessment=90,
        )

        assert route.pilot_name == "hotel"
        assert route.risk_level == RiskLevel.HIGH
        assert "Article 50" in route.articles  # Transparency
        assert "Article 51" in route.articles  # GPAI
        assert "Article 14" in route.articles  # Documentation
        assert "Annex III" in route.annex_sections  # Essential service prohibition

    def test_glass_pilot_routing(self):
        """Glass pilot routes with safety articles."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="glass",
            request_description="Safety-critical glass defect detection",
            compliance_assessment=92,
        )

        assert route.pilot_name == "glass"
        assert route.risk_level == RiskLevel.HIGH
        assert "Article 6" in route.articles  # Risk classification
        assert "Article 13" in route.articles  # Documentation
        assert "Article 14" in route.articles  # Robustness
        assert "Annex I" in route.annex_sections  # High-risk safety system

    def test_school_pilot_routing(self):
        """School pilot routes with education articles."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="school",
            request_description="Student access control system",
            compliance_assessment=88,
        )

        assert route.pilot_name == "school"
        assert route.risk_level == RiskLevel.HIGH
        assert "Article 6" in route.articles  # Risk classification
        assert "Article 50" in route.articles  # Transparency
        assert "Article 14" in route.articles  # Documentation
        assert "Annex III" in route.annex_sections  # Education

    def test_route_decision_approved(self):
        """High compliance score → APPROVED decision."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="hotel",
            request_description="Standard credit check",
            compliance_assessment=95,
        )
        assert route.decision == "APPROVED"

    def test_route_decision_denied_low_compliance(self):
        """Low compliance score → ValueError (won't route)."""
        router = PolicyRouter()
        with pytest.raises(ValueError, match="compliance ≥80"):
            router.route_request(
                pilot_name="glass",
                request_description="Risky operation",
                compliance_assessment=75,
            )


class TestPolicyValidation:
    """Test input validation and constraints."""

    def test_invalid_pilot_name(self):
        """Unknown pilot name raises error."""
        router = PolicyRouter()
        with pytest.raises(ValueError, match="Unknown pilot"):
            router.route_request(
                pilot_name="invalid_pilot",
                request_description="Some request",
            )

    def test_default_compliance_score(self):
        """Default compliance score set to pilot minimum."""
        router = PolicyRouter()
        # Hotel minimum is 90
        route = router.route_request(
            pilot_name="hotel",
            request_description="Request",
            compliance_assessment=None,
        )
        assert route.compliance_score == 90

    def test_compliance_score_clamped(self):
        """Compliance score clamped to 0-100 range."""
        router = PolicyRouter()
        # Try to set 150 → should clamp to 100
        route = router.route_request(
            pilot_name="school",
            request_description="Request",
            compliance_assessment=150,
        )
        assert route.compliance_score == 100

    def test_compliance_score_minimum_threshold(self):
        """Score below 80 globally rejected."""
        router = PolicyRouter()
        with pytest.raises(ValueError, match="compliance ≥80"):
            router.route_request(
                pilot_name="hotel",
                request_description="Request",
                compliance_assessment=79,
            )

    def test_pilot_validation(self):
        """validate_pilot correctly identifies registered pilots."""
        router = PolicyRouter()
        assert router.validate_pilot("hotel") is True
        assert router.validate_pilot("glass") is True
        assert router.validate_pilot("school") is True
        assert router.validate_pilot("unknown") is False


class TestAuditTrail:
    """Test audit trail generation and format."""

    def test_audit_trail_contains_pilot_name(self):
        """Audit trail includes pilot identification."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="hotel",
            request_description="Credit check",
            compliance_assessment=90,
        )
        assert "HOTEL" in route.audit_trail

    def test_audit_trail_lists_articles(self):
        """Audit trail shows all applicable articles."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="glass",
            request_description="Safety review",
            compliance_assessment=85,
        )
        assert "Article 6" in route.audit_trail
        assert "Article 13" in route.audit_trail
        assert "Article 14" in route.audit_trail

    def test_audit_trail_lists_annexes(self):
        """Audit trail shows applicable annexes."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="school",
            request_description="Access control",
            compliance_assessment=88,
        )
        assert "Annex III" in route.audit_trail
        assert "education" in route.audit_trail.lower()

    def test_audit_trail_includes_reasoning(self):
        """Audit trail includes compliance reasoning."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="hotel",
            request_description="Credit",
            compliance_assessment=90,
        )
        assert "GPAI" in route.audit_trail or "Article 51" in route.audit_trail
        assert "disclosure" in route.audit_trail.lower() or "Article 50" in route.audit_trail

    def test_audit_trail_has_timestamp(self):
        """Audit trail includes ISO timestamp."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="glass",
            request_description="Request",
            compliance_assessment=85,
        )
        assert route.timestamp  # Should be ISO format
        assert "T" in route.timestamp  # ISO format includes T


class TestArticleCitations:
    """Test article and annex citation methods."""

    def test_cite_article_50(self):
        """Article 50 citation available."""
        router = PolicyRouter()
        citation = router.cite_article("Article 50")
        assert "Transparency" in citation or "disclosure" in citation.lower()

    def test_cite_article_6(self):
        """Article 6 citation available."""
        router = PolicyRouter()
        citation = router.cite_article("Article 6")
        assert "risk" in citation.lower() or "High-risk" in citation

    def test_cite_article_51(self):
        """Article 51 citation available."""
        router = PolicyRouter()
        citation = router.cite_article("Article 51")
        assert "GPAI" in citation or "General-purpose" in citation

    def test_cite_annex_i(self):
        """Annex I citation available."""
        router = PolicyRouter()
        citation = router.cite_annex("Annex I")
        assert "High-risk" in citation or "safety" in citation.lower()

    def test_cite_annex_iii(self):
        """Annex III citation available."""
        router = PolicyRouter()
        citation = router.cite_annex("Annex III")
        assert "employment" in citation.lower() or "education" in citation.lower()

    def test_unknown_article_citation(self):
        """Unknown article returns not-found message."""
        router = PolicyRouter()
        citation = router.cite_article("Article 999")
        assert "Not found" in citation


class TestPolicyEnforcement:
    """Test enforcement metadata generation."""

    def test_enforce_policy_returns_metadata(self):
        """enforce_policy returns enforcement configuration."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="hotel",
            request_description="Credit check",
            compliance_assessment=90,
        )
        enforcement = router.enforce_policy(route)

        assert enforcement is not None
        assert isinstance(enforcement, dict)
        assert "route_id" in enforcement
        assert "pilot" in enforcement
        assert "enforcement_level" in enforcement

    def test_enforce_policy_strict_for_high_risk(self):
        """High-risk pilots get STRICT enforcement level."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="glass",
            request_description="Safety check",
            compliance_assessment=85,
        )
        enforcement = router.enforce_policy(route)
        assert enforcement["enforcement_level"] == "STRICT"

    def test_enforce_policy_includes_articles(self):
        """Enforcement metadata includes articles to enforce."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="school",
            request_description="Access",
            compliance_assessment=88,
        )
        enforcement = router.enforce_policy(route)
        assert "articles_to_enforce" in enforcement
        assert len(enforcement["articles_to_enforce"]) > 0

    def test_enforce_policy_includes_annexes(self):
        """Enforcement metadata includes annexes to enforce."""
        router = PolicyRouter()
        route = router.route_request(
            pilot_name="hotel",
            request_description="Credit",
            compliance_assessment=90,
        )
        enforcement = router.enforce_policy(route)
        assert "annexes_to_enforce" in enforcement
        assert "Annex III" in enforcement["annexes_to_enforce"]


class TestAuditLog:
    """Test audit log and route history."""

    def test_router_maintains_route_history(self):
        """Router tracks all routed decisions."""
        router = PolicyRouter()
        router.route_request("hotel", "Request 1", 90)
        router.route_request("glass", "Request 2", 85)
        router.route_request("school", "Request 3", 88)

        routes = router.get_routes()
        assert len(routes) == 3

    def test_each_route_has_unique_id(self):
        """Each route gets unique ID."""
        router = PolicyRouter()
        route1 = router.route_request("hotel", "R1", 90)
        route2 = router.route_request("hotel", "R2", 90)

        assert route1.route_id != route2.route_id

    def test_route_history_immutable(self):
        """get_routes returns copy, not reference."""
        router = PolicyRouter()
        router.route_request("hotel", "Request", 90)
        routes1 = router.get_routes()
        routes2 = router.get_routes()

        assert routes1 is not routes2  # Different objects
        assert len(routes1) == len(routes2)  # Same content


class TestCompliance:
    """Test compliance threshold enforcement."""

    def test_hotel_minimum_compliance_90(self):
        """Hotel requires minimum 90% compliance."""
        router = PolicyRouter()
        # Should pass at 90
        route = router.route_request("hotel", "Request", 90)
        assert route.decision == "APPROVED"

        # Should fail at 89
        with pytest.raises(ValueError):
            router.route_request("hotel", "Request", 89)

    def test_school_minimum_compliance_88(self):
        """School requires minimum 88% compliance."""
        router = PolicyRouter()
        route = router.route_request("school", "Request", 88)
        assert route.decision == "APPROVED"

        with pytest.raises(ValueError):
            router.route_request("school", "Request", 87)

    def test_glass_minimum_compliance_85(self):
        """Glass requires minimum 85% compliance."""
        router = PolicyRouter()
        route = router.route_request("glass", "Request", 85)
        assert route.decision == "APPROVED"

        with pytest.raises(ValueError):
            router.route_request("glass", "Request", 84)


if __name__ == "__main__":
    # Run tests with: python -m pytest smaos/l1_reasoning/test_policy_router.py -v
    pytest.main([__file__, "-v"])
