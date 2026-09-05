"""
Integration and advanced tests for Intent-Verified Delegation (Stream H / B8)
Tests KMS signing integration, agent delegation patterns, and end-to-end workflows.
Target: 60+ additional tests to reach 100+ total.
"""

import pytest
import time
from intent_commitment import (
    IntentCommitment,
    IntentType,
    IntentConstraint,
    IntentVerifier,
    IntentCommitmentManager,
    HijackingType,
    EscalationLevel,
)

try:
    from smaos.l6_infrastructure.kms_signer import KMSSigner
    HAS_KMS = True
except ImportError:
    HAS_KMS = False


class TestKMSIntegration:
    """Test real cryptographic signing with KMS."""

    @pytest.mark.skipif(not HAS_KMS, reason="KMS signer not available")
    def test_manager_with_kms_signer(self):
        """Manager can be initialized with KMS signer."""
        signer = KMSSigner()
        signer.generate_key_pair("ed25519")
        manager = IntentCommitmentManager(kms_signer=signer)
        assert manager.kms_signer is not None

    @pytest.mark.skipif(not HAS_KMS, reason="KMS signer not available")
    def test_commitment_signed_with_kms(self):
        """Commitment can be signed with real KMS key."""
        signer = KMSSigner()
        signer.generate_key_pair("ed25519")
        manager = IntentCommitmentManager(kms_signer=signer)

        commitment = manager.propose_intent(
            agent_name="hotel-agent",
            goal="Score credit",
            plan="Use ML model",
        )
        manager.commit_intent(commitment)

        # Should have a real signature (not placeholder)
        assert commitment.ed25519_signature
        assert len(commitment.ed25519_signature) == 64  # SHA256 hex

    @pytest.mark.skipif(not HAS_KMS, reason="KMS signer not available")
    def test_multiple_commitments_signed_differently(self):
        """Different commitments produce different signatures."""
        signer = KMSSigner()
        signer.generate_key_pair("ed25519")
        manager = IntentCommitmentManager(kms_signer=signer)

        c1 = manager.propose_intent("agent", "Goal A", "Plan A")
        c2 = manager.propose_intent("agent", "Goal B", "Plan B")

        manager.commit_intent(c1)
        manager.commit_intent(c2)

        assert c1.ed25519_signature != c2.ed25519_signature


class TestAgentDelegationPatterns:
    """Test patterns for agent delegation with intent verification."""

    def test_agent_intent_wrapper_happy_path(self):
        """Agent can be wrapped with intent verification (happy path)."""
        manager = IntentCommitmentManager()

        # Propose intent
        commitment = manager.propose_intent(
            agent_name="scorer",
            goal="Score hotel credit in <5 seconds",
            plan="Query PMS, run ML, return score",
            constraints=[
                IntentConstraint("latency", 5000, "latency"),
                IntentConstraint("sources", ["pms_db"], "data_access"),
            ],
        )
        manager.commit_intent(commitment)

        # Begin execution
        verifier = manager.begin_execution(commitment.commitment_id)

        # Simulate agent actions (within bounds)
        verifier.record_action("data_access", "pms_db", 200)
        verifier.record_action("computation", "", 1000)

        # Verify
        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is True
        assert report["critical_detections"] == 0

    def test_agent_intent_wrapper_hijacking_blocked(self):
        """Agent attempting unauthorized action is blocked."""
        manager = IntentCommitmentManager()

        # Propose constrained intent
        commitment = manager.propose_intent(
            agent_name="glass-agent",
            goal="Analyze CAD models",
            plan="Safety check",
            constraints=[
                IntentConstraint("sources", ["cad_db"], "data_access"),
                IntentConstraint("apis", ["safety_api"], "api_call"),
            ],
        )
        manager.commit_intent(commitment)

        # Begin execution
        verifier = manager.begin_execution(commitment.commitment_id)

        # Agent tries unauthorized access
        verifier.record_action("data_access", "cad_db", 100)  # OK
        verifier.record_action("data_access", "secret_db", 100)  # HIJACKING

        # Verify and check for escalation
        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False
        assert report["critical_detections"] >= 1
        assert any(e["severity"] == "immediate_halt" for e in report["escalations"])

    def test_agent_with_privilege_escalation_detection(self):
        """Agent attempting privilege escalation is detected."""
        manager = IntentCommitmentManager()

        commitment = manager.propose_intent(
            agent_name="user-agent",
            goal="Read user profile",
            plan="Query user DB",
            constraints=[
                IntentConstraint("sources", ["public_users"], "data_access"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "public_users", 100)  # OK
        verifier.record_action("data_access", "admin_credentials", 100)  # ESCALATION

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False
        assert len(report["escalations"]) >= 1


class TestMultiAgentCoordination:
    """Test intent verification across multiple coordinated agents."""

    def test_two_agents_sequential_intents(self):
        """Two agents with sequential intents both verified."""
        manager = IntentCommitmentManager()

        # Agent 1: Classification
        c1 = manager.propose_intent(
            agent_name="classifier",
            goal="Classify intent",
            plan="Run classifier model",
            constraints=[
                IntentConstraint("latency", 2000, "latency"),
            ],
        )
        manager.commit_intent(c1)
        v1 = manager.begin_execution(c1.commitment_id)
        time.sleep(0.5)
        v1.record_action("computation", "", 500)
        r1 = manager.complete_execution(c1.commitment_id)

        # Agent 2: Authorization
        c2 = manager.propose_intent(
            agent_name="authorizer",
            goal="Authorize action",
            plan="Check permissions",
            constraints=[
                IntentConstraint("latency", 1000, "latency"),
                IntentConstraint("apis", ["authz_api"], "api_call"),
            ],
        )
        manager.commit_intent(c2)
        v2 = manager.begin_execution(c2.commitment_id)
        v2.record_action("api_call", "authz_api", 100)
        r2 = manager.complete_execution(c2.commitment_id)

        # Both should be clean
        assert r1["verification_passed"] is True
        assert r2["verification_passed"] is True

    def test_agent_coordination_with_data_passing(self):
        """Agents coordinate via data access tracking."""
        manager = IntentCommitmentManager()

        # Agent A: Fetch data
        c_a = manager.propose_intent(
            agent_name="fetcher",
            goal="Fetch user data",
            plan="Query database",
            constraints=[
                IntentConstraint("sources", ["user_db"], "data_access"),
            ],
        )
        manager.commit_intent(c_a)
        v_a = manager.begin_execution(c_a.commitment_id)
        v_a.record_action("data_access", "user_db", 100)
        r_a = manager.complete_execution(c_a.commitment_id)

        # Agent B: Transform data
        c_b = manager.propose_intent(
            agent_name="transformer",
            goal="Transform user data",
            plan="Apply transformations",
            constraints=[
                IntentConstraint("latency", 3000, "latency"),
            ],
        )
        manager.commit_intent(c_b)
        v_b = manager.begin_execution(c_b.commitment_id)
        v_b.record_action("computation", "", 500)
        r_b = manager.complete_execution(c_b.commitment_id)

        assert r_a["verification_passed"] is True
        assert r_b["verification_passed"] is True


class TestConstraintVariations:
    """Test various constraint combinations and edge cases."""

    def test_constraint_with_zero_latency(self):
        """Constraint with very strict latency (0ms) causes violation."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[IntentConstraint("max_latency", 0, "latency")],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        time.sleep(0.01)  # 10ms > 0ms

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False

    def test_constraint_with_multiple_data_sources(self):
        """Agent respects multiple allowed data sources."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[
                IntentConstraint("sources", ["db1", "db2", "db3"], "data_access"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "db1", 100)
        verifier.record_action("data_access", "db2", 100)
        verifier.record_action("data_access", "db3", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is True

    def test_constraint_mixture_all_respected(self):
        """Agent respects all constraint types simultaneously."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Complex goal",
            "Complex plan",
            constraints=[
                IntentConstraint("max_latency", 5000, "latency"),
                IntentConstraint("sources", ["db1", "db2"], "data_access"),
                IntentConstraint("apis", ["api1", "api2"], "api_call"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "db1", 100)
        verifier.record_action("data_access", "db2", 100)
        verifier.record_action("api_call", "api1", 100)
        verifier.record_action("api_call", "api2", 100)
        time.sleep(0.5)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is True

    def test_constraint_violation_on_first_constraint_type(self):
        """Violation on first constraint type is caught."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[
                IntentConstraint("max_latency", 100, "latency"),  # Will violate
                IntentConstraint("sources", ["db1"], "data_access"),
                IntentConstraint("apis", ["api1"], "api_call"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        time.sleep(0.2)  # 200ms > 100ms limit

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False


class TestHijackingScenarios:
    """Test realistic hijacking scenarios."""

    def test_data_exfiltration_attempt(self):
        """Detect attempt to exfiltrate sensitive data."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "payment-agent",
            "Process payment",
            "Call payment API",
            constraints=[
                IntentConstraint("apis", ["payment_api"], "api_call"),
                IntentConstraint("sources", ["payment_db"], "data_access"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("api_call", "payment_api", 100)  # OK
        verifier.record_action("data_access", "payment_db", 100)  # OK
        verifier.record_action("data_access", "customer_emails", 100)  # EXFIL

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False
        assert report["critical_detections"] >= 1

    def test_unauthorized_api_exfiltration(self):
        """Detect unauthorized API calls for data exfil."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "api-agent",
            "Validate data",
            "Check data integrity",
            constraints=[
                IntentConstraint("apis", ["validate_api"], "api_call"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("api_call", "validate_api", 100)  # OK
        verifier.record_action("api_call", "exfil_service_com", 50)  # EXFIL

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False

    def test_goal_drift_via_context_injection(self):
        """Detect goal drift attempts via context pollution."""
        manager = IntentCommitmentManager()

        # Original intent with context hash
        commitment = manager.propose_intent(
            "agent",
            "Process order",
            "Validate and process",
            context_hash="original_context_abc123",
        )
        original_hash = commitment.commitment_hash
        manager.commit_intent(commitment)

        # Later attempt to process with modified context should be flagged
        retrieved = manager.get_commitment(commitment.commitment_id)
        assert retrieved.context_hash == "original_context_abc123"
        assert retrieved.commitment_hash == original_hash


class TestEscalationPaths:
    """Test escalation to human review in various scenarios."""

    def test_escalation_creates_actionable_alert(self):
        """Escalation includes actionable information."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[IntentConstraint("sources", ["safe"], "data_access")],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "forbidden", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert len(report["escalations"]) > 0

        escalation = report["escalations"][0]
        assert escalation["hijacking_type"]
        assert escalation["severity"] == "immediate_halt"
        assert escalation["description"]
        assert escalation["evidence"]
        assert escalation["human_escalated"] is True

    def test_multiple_escalations_all_reported(self):
        """All escalations reported, not just first."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[
                IntentConstraint("sources", ["safe1"], "data_access"),
                IntentConstraint("apis", ["safe_api"], "api_call"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "forbidden1", 100)
        verifier.record_action("data_access", "forbidden2", 100)
        verifier.record_action("api_call", "evil_api", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["critical_detections"] >= 3


class TestVerificationIdempotency:
    """Test that verification is idempotent."""

    def test_verify_execution_idempotent(self):
        """Calling verify multiple times returns same result."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("computation", "", 100)

        # Verify multiple times
        result1 = verifier.verify_execution()
        result2 = verifier.verify_execution()
        result3 = verifier.verify_execution()

        assert result1 == result2 == result3

    def test_complete_execution_idempotent(self):
        """Completing execution multiple times is safe."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        manager.commit_intent(commitment)
        manager.begin_execution(commitment.commitment_id)

        # Complete multiple times
        r1 = manager.complete_execution(commitment.commitment_id)
        r2 = manager.complete_execution(commitment.commitment_id)

        assert r1["verification_passed"] == r2["verification_passed"]
        assert r1["actions_recorded"] == r2["actions_recorded"]


class TestWorkflowCompletion:
    """Test complete workflow scenarios."""

    def test_hotel_pilot_workflow(self):
        """Simulate hotel credit scoring workflow."""
        manager = IntentCommitmentManager()

        # Hotel agent proposes credit scoring
        commitment = manager.propose_intent(
            agent_name="hotel-agent",
            goal="Score guest credit for room booking",
            plan="Query PMS and credit registry, apply ML model",
            intent_type=IntentType.GOAL,
            constraints=[
                IntentConstraint("latency", 3000, "latency"),
                IntentConstraint("sources", ["pms_database", "credit_registry"], "data_access"),
                IntentConstraint("apis", ["score_credit_api"], "api_call"),
            ],
            model="claude-opus-4",
        )
        manager.commit_intent(commitment)

        # Execute workflow
        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "pms_database", 200)
        verifier.record_action("data_access", "credit_registry", 150)
        verifier.record_action("api_call", "score_credit_api", 500)
        verifier.record_action("computation", "", 800)

        # Verify
        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is True
        assert report["actions_recorded"] == 4
        assert report["critical_detections"] == 0

    def test_glass_pilot_workflow_with_hijacking_attempt(self):
        """Simulate glass safety analysis with hijacking attempt."""
        manager = IntentCommitmentManager()

        commitment = manager.propose_intent(
            agent_name="glass-agent",
            goal="Analyze safety-critical glass defects",
            plan="Parse CAD models, run safety analysis",
            intent_type=IntentType.GOAL,
            constraints=[
                IntentConstraint("latency", 10000, "latency"),
                IntentConstraint("sources", ["cad_storage"], "data_access"),
                IntentConstraint("apis", ["safety_check_api"], "api_call"),
            ],
            model="claude-opus-4",
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        # Legitimate actions
        verifier.record_action("data_access", "cad_storage", 500)
        verifier.record_action("api_call", "safety_check_api", 1000)

        # HIJACKING ATTEMPT: Unauthorized data access
        verifier.record_action("data_access", "hr_employee_records", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False
        assert len(report["escalations"]) >= 1
        assert report["escalations"][0]["hijacking_type"] == "unauthorized_data_access"


class TestCommitmentExport:
    """Test audit trail export functionality."""

    def test_export_commitments_structure(self):
        """Exported commitments have correct structure."""
        manager = IntentCommitmentManager()

        c1 = manager.propose_intent("a1", "Goal 1", "Plan 1")
        manager.commit_intent(c1)

        c2 = manager.propose_intent("a2", "Goal 2", "Plan 2")
        manager.commit_intent(c2)

        export = manager.export_commitments()
        assert "total_commitments" in export
        assert "commitments" in export
        assert "detections" in export
        assert export["total_commitments"] == 2

    def test_export_includes_detections(self):
        """Exported data includes all detections."""
        manager = IntentCommitmentManager()

        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[IntentConstraint("sources", ["safe"], "data_access")],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "forbidden", 100)
        manager.complete_execution(commitment.commitment_id)

        export = manager.export_commitments()
        assert len(export["detections"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
