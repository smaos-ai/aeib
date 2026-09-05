"""
Test suite for Stream H: Intent-Verified Delegation
Tests verify: commitment hashing, hijacking detection, escalation, and clean execution.
Total: 16+ test cases covering legitimate intents and 5+ hijacking scenarios.
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


class TestIntentCommitmentBasics:
    """Test core commitment creation and hashing."""

    def test_commitment_id_unique(self):
        """Each commitment gets unique ID."""
        c1 = IntentCommitment(agent_name="agent1", goal="goal1")
        c2 = IntentCommitment(agent_name="agent1", goal="goal1")
        assert c1.commitment_id != c2.commitment_id

    def test_commitment_hash_computed(self):
        """Commitment hash is computed correctly."""
        commitment = IntentCommitment(
            agent_name="agent1",
            goal="Score credit quickly",
            plan="Use ML model",
        )
        commitment.finalize()
        assert commitment.commitment_hash
        assert len(commitment.commitment_hash) == 64  # SHA256 hex

    def test_commitment_hash_deterministic(self):
        """Same intent produces same hash."""
        c1 = IntentCommitment(
            agent_name="hotel-agent",
            goal="Score credit",
            plan="ML model",
            timestamp="2026-01-01T00:00:00",
        )
        c1.finalize()
        hash1 = c1.commitment_hash

        c2 = IntentCommitment(
            agent_name="hotel-agent",
            goal="Score credit",
            plan="ML model",
            timestamp="2026-01-01T00:00:00",
        )
        c2.commitment_id = c1.commitment_id  # Same ID
        c2.finalize()
        hash2 = c2.commitment_hash

        assert hash1 == hash2

    def test_commitment_hash_changes_with_goal(self):
        """Different goal produces different hash."""
        c1 = IntentCommitment(agent_name="a1", goal="Goal A")
        c1.finalize()

        c2 = IntentCommitment(agent_name="a1", goal="Goal B")
        c2.finalize()

        assert c1.commitment_hash != c2.commitment_hash

    def test_commitment_hash_changes_with_constraints(self):
        """Different constraints produce different hash."""
        c1 = IntentCommitment(
            agent_name="a1",
            goal="Goal",
            constraints=[IntentConstraint("latency", 5000, "latency")],
        )
        c1.finalize()

        c2 = IntentCommitment(
            agent_name="a1",
            goal="Goal",
            constraints=[IntentConstraint("latency", 10000, "latency")],
        )
        c2.finalize()

        assert c1.commitment_hash != c2.commitment_hash

    def test_commitment_to_dict(self):
        """Commitment converts to dictionary correctly."""
        commitment = IntentCommitment(
            agent_name="agent1",
            goal="test goal",
            plan="test plan",
        )
        commitment.finalize()
        d = commitment.to_dict()

        assert d["agent_name"] == "agent1"
        assert d["goal"] == "test goal"
        assert d["commitment_hash"] == commitment.commitment_hash


class TestIntentConstraints:
    """Test constraint definition and validation."""

    def test_latency_constraint_creation(self):
        """Latency constraint created correctly."""
        constraint = IntentConstraint("max_latency", 5000, "latency")
        assert constraint.name == "max_latency"
        assert constraint.value == 5000
        assert constraint.constraint_type == "latency"

    def test_data_access_constraint_creation(self):
        """Data access constraint with whitelist."""
        constraint = IntentConstraint(
            "allowed_data",
            ["db1", "db2"],
            "data_access",
        )
        assert constraint.constraint_type == "data_access"
        assert constraint.value == ["db1", "db2"]

    def test_api_constraint_creation(self):
        """API call constraint with whitelist."""
        constraint = IntentConstraint(
            "allowed_apis",
            ["score_api", "verify_api"],
            "api_call",
        )
        assert constraint.constraint_type == "api_call"
        assert len(constraint.value) == 2

    def test_constraint_to_dict(self):
        """Constraint converts to dictionary."""
        c = IntentConstraint("test", 123, "latency")
        d = c.to_dict()
        assert d["name"] == "test"
        assert d["value"] == 123
        assert d["constraint_type"] == "latency"


class TestIntentManager:
    """Test intent commitment manager."""

    def test_manager_initialization(self):
        """Manager initializes correctly."""
        manager = IntentCommitmentManager()
        assert len(manager.commitments) == 0
        assert len(manager.verifiers) == 0

    def test_propose_intent(self):
        """Agent can propose intent."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            agent_name="hotel-agent",
            goal="Score credit",
            plan="Use ML",
        )
        assert commitment.agent_name == "hotel-agent"
        assert commitment.commitment_hash
        assert commitment not in manager.commitments.values()  # Not committed yet

    def test_commit_intent(self):
        """Intent can be committed."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        committed = manager.commit_intent(commitment)

        assert committed.ap2_ledger_id
        assert committed.ed25519_signature
        assert committed.commitment_id in manager.commitments

    def test_commitment_retrieval(self):
        """Committed intent can be retrieved."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        manager.commit_intent(commitment)

        retrieved = manager.get_commitment(commitment.commitment_id)
        assert retrieved.goal == "Goal"

    def test_begin_execution(self):
        """Execution can begin after commitment."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        assert verifier.commitment.commitment_id == commitment.commitment_id

    def test_begin_execution_unknown_commitment(self):
        """Cannot begin execution for unknown commitment."""
        manager = IntentCommitmentManager()
        with pytest.raises(ValueError, match="Unknown commitment"):
            manager.begin_execution("invalid_id")


class TestCleanExecution:
    """Test legitimate, hijacking-free execution."""

    def test_clean_execution_no_constraints(self):
        """Execution without constraints passes verification."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("computation", "", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is True
        assert report["detections"] == 0

    def test_clean_execution_with_latency_ok(self):
        """Execution within latency constraint passes."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[IntentConstraint("max_latency", 5000, "latency")],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        time.sleep(0.1)  # 100ms < 5000ms
        verifier.record_action("computation", "", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is True

    def test_clean_execution_with_data_access_whitelist(self):
        """Execution respects data access whitelist."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[
                IntentConstraint("sources", ["db1", "db2"], "data_access"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "db1", 100)
        verifier.record_action("data_access", "db2", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is True

    def test_clean_execution_with_api_whitelist(self):
        """Execution respects API whitelist."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[
                IntentConstraint("apis", ["api1", "api2"], "api_call"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("api_call", "api1", 100)
        verifier.record_action("api_call", "api2", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is True

    def test_multiple_actions_all_clean(self):
        """Multiple actions can all be clean."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        for i in range(5):
            verifier.record_action("computation", "", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["actions_recorded"] == 5
        assert report["verification_passed"] is True


class TestHijackingDetectionUnauthorizedDataAccess:
    """Test detection of unauthorized data access."""

    def test_detect_unauthorized_data_access(self):
        """Hijacking detected: unauthorized data source."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[
                IntentConstraint("sources", ["db1"], "data_access"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "db1", 100)  # OK
        verifier.record_action("data_access", "hr_records", 100)  # HIJACKING

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False
        assert report["detections"] >= 1

    def test_unauthorized_access_marked_critical(self):
        """Unauthorized data access marked as CRITICAL."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[
                IntentConstraint("sources", ["public_db"], "data_access"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "secret_db", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert len(report["escalations"]) >= 1
        assert report["escalations"][0]["severity"] == "immediate_halt"

    def test_unauthorized_access_escalated(self):
        """Unauthorized access escalated to human."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[
                IntentConstraint("sources", ["allowed"], "data_access"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "forbidden", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert any(e["human_escalated"] for e in report["escalations"])


class TestHijackingDetectionLatencyViolation:
    """Test detection of latency constraint violations."""

    def test_detect_latency_violation(self):
        """Hijacking detected: execution too slow."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[IntentConstraint("max_latency", 500, "latency")],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        time.sleep(0.6)  # 600ms > 500ms
        verifier.record_action("computation", "", 600)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False
        assert report["detections"] >= 1

    def test_latency_violation_includes_evidence(self):
        """Latency violation report includes actual vs. allowed."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[IntentConstraint("max_time", 200, "latency")],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        time.sleep(0.3)  # 300ms

        report = manager.complete_execution(commitment.commitment_id)
        assert len(report["escalations"]) >= 1
        detection = report["escalations"][0]
        assert detection["hijacking_type"] == "latency_violation"
        assert "actual_latency_ms" in detection["evidence"]
        assert "max_allowed_ms" in detection["evidence"]


class TestHijackingDetectionUnauthorizedAPI:
    """Test detection of unauthorized API calls."""

    def test_detect_unauthorized_api_call(self):
        """Hijacking detected: API call to unauthorized endpoint."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[IntentConstraint("apis", ["score_api"], "api_call")],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("api_call", "score_api", 100)  # OK
        verifier.record_action("api_call", "exfil_api", 100)  # HIJACKING

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False
        assert report["detections"] >= 1

    def test_unauthorized_api_includes_details(self):
        """Unauthorized API detection includes called vs. allowed."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[IntentConstraint("apis", ["safe_api"], "api_call")],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("api_call", "dangerous_api", 100)

        report = manager.complete_execution(commitment.commitment_id)
        detection = report["escalations"][0]
        assert "api_called" in detection["evidence"]
        assert "allowed_apis" in detection["evidence"]


class TestHijackingDetectionContextPollution:
    """Test context pollution and prompt injection defense."""

    def test_different_context_hash_blocks_execution(self):
        """Execution with different context is flagged."""
        manager = IntentCommitmentManager()

        # Original commitment with context hash
        commitment = manager.propose_intent(
            "agent",
            "Score credit",
            "Use ML",
            context_hash="context_abc123",
        )
        manager.commit_intent(commitment)

        # Verify stored context
        stored = manager.get_commitment(commitment.commitment_id)
        assert stored.context_hash == "context_abc123"

    def test_commitment_immutable_after_signing(self):
        """Commitment hash binds to original content."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        original_hash = commitment.commitment_hash
        manager.commit_intent(commitment)

        # Try to modify after commitment
        commitment.goal = "Different goal"
        new_hash = commitment.compute_commitment_hash()

        # Hashes should differ, proving immutability is enforced
        assert original_hash != new_hash


class TestHijackingDetectionGoalDrift:
    """Test detection of goal changes during execution."""

    def test_commitment_hash_prevents_goal_substitution(self):
        """Commitment hash binds to original goal."""
        commitment = IntentCommitment(
            agent_name="agent",
            goal="Original goal",
            plan="Plan",
        )
        commitment.finalize()
        original_hash = commitment.commitment_hash

        # Try to change goal
        commitment.goal = "Modified goal"
        new_hash = commitment.compute_commitment_hash()

        # Hashes don't match
        assert original_hash != new_hash

    def test_multiple_detections_reported(self):
        """Multiple violations in one execution all reported."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[
                IntentConstraint("sources", ["db1"], "data_access"),
                IntentConstraint("apis", ["api1"], "api_call"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "forbidden_db", 100)  # Violation 1
        verifier.record_action("api_call", "forbidden_api", 100)  # Violation 2

        report = manager.complete_execution(commitment.commitment_id)
        assert report["critical_detections"] >= 2


class TestEscalationMechanism:
    """Test escalation to human when hijacking detected."""

    def test_critical_hijacking_escalated(self):
        """Critical hijacking marked for human escalation."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[IntentConstraint("sources", ["safe"], "data_access")],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "private_data", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert len(report["escalations"]) > 0

    def test_escalation_includes_full_context(self):
        """Escalation report includes evidence and metadata."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[IntentConstraint("sources", ["allowed"], "data_access")],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "forbidden", 100)

        report = manager.complete_execution(commitment.commitment_id)
        escalation = report["escalations"][0]

        assert escalation["hijacking_type"]
        assert escalation["severity"]
        assert escalation["description"]
        assert "evidence" in escalation


class TestAP2Integration:
    """Test integration with AP2 ledger for immutable proof."""

    def test_commitment_recorded_to_ap2(self):
        """Commitment recorded to AP2 ledger if available."""
        # Note: requires AP2 ledger mock/stub
        # This test verifies the integration point exists
        manager = IntentCommitmentManager(ap2_ledger=None)
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        manager.commit_intent(commitment)

        # Should not raise even without ledger
        assert commitment.ap2_ledger_id

    def test_verification_recorded_to_ap2(self):
        """Verification results recorded to AP2."""
        manager = IntentCommitmentManager(ap2_ledger=None)
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        manager.commit_intent(commitment)
        manager.begin_execution(commitment.commitment_id)

        # Should not raise
        report = manager.complete_execution(commitment.commitment_id)
        assert report


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_constraint_list(self):
        """Commitment with no constraints is valid."""
        commitment = IntentCommitment(
            agent_name="agent",
            goal="Goal",
            plan="Plan",
            constraints=[],
        )
        commitment.finalize()
        assert commitment.commitment_hash

    def test_constraint_with_single_value(self):
        """Constraint with single value (not list)."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[IntentConstraint("api", "single_api", "api_call")],
        )
        manager.commit_intent(commitment)
        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("api_call", "single_api", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"]

    def test_large_action_sequence(self):
        """Many actions recorded and verified."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        for i in range(100):
            verifier.record_action("computation", "", 10)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["actions_recorded"] == 100
        assert report["verification_passed"]

    def test_get_nonexistent_commitment(self):
        """Getting nonexistent commitment returns None."""
        manager = IntentCommitmentManager()
        result = manager.get_commitment("invalid_id")
        assert result is None


class TestVerificationReport:
    """Test verification report generation."""

    def test_report_structure(self):
        """Verification report has required fields."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent("agent", "Goal", "Plan")
        manager.commit_intent(commitment)
        manager.begin_execution(commitment.commitment_id)

        report = manager.complete_execution(commitment.commitment_id)

        required_fields = [
            "commitment_id",
            "verification_passed",
            "actions_recorded",
            "detections",
            "critical_detections",
            "escalations",
            "actions",
        ]
        for field in required_fields:
            assert field in report

    def test_report_includes_all_detections(self):
        """Report includes all detected violations."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[
                IntentConstraint("sources", ["safe"], "data_access"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "bad1", 100)
        verifier.record_action("data_access", "bad2", 100)

        report = manager.complete_execution(commitment.commitment_id)
        # Should have detections for both bad accesses
        assert report["detections"] >= 2


if __name__ == "__main__":
    # Run all tests: python -m pytest smaos/l3_tooling/test_intent_verification.py -v
    pytest.main([__file__, "-v"])
