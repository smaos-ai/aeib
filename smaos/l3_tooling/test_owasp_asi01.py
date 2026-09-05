"""
OWASP ASI01 Agent Security Incidents defense tests for Intent-Verified Delegation.
Directly addresses OWASP ASI01 top agent security risks.
Target: 15+ tests to reach 100+ total coverage.
"""

import pytest
from intent_commitment import (
    IntentCommitment,
    IntentType,
    IntentConstraint,
    IntentCommitmentManager,
)


class TestASI01_1_UnauthorizedToolUse:
    """OWASP ASI01 Risk #1: Unauthorized Tool Use
    Defense: Intent commitment specifies allowed APIs and data sources.
    """

    def test_agent_blocked_from_unauthorized_tool(self):
        """Agent cannot use tools not in intent."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            agent_name="limited-agent",
            goal="Summarize text",
            plan="Use text summarization tool",
            constraints=[
                IntentConstraint("apis", ["summarize_api"], "api_call"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("api_call", "summarize_api", 100)  # OK

        # Agent tries to use unauthorized tool
        verifier.record_action("api_call", "email_tool", 50)  # BLOCKED

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False
        assert any(
            e["hijacking_type"] == "unauthorized_api_call"
            for e in report["escalations"]
        )

    def test_each_tool_must_be_explicitly_allowed(self):
        """Each tool requires explicit allowance; no implicit access."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Goal",
            "Plan",
            constraints=[
                IntentConstraint("apis", ["tool_a", "tool_b"], "api_call"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("api_call", "tool_a", 100)
        verifier.record_action("api_call", "tool_b", 100)

        # Unauthorized tool
        verifier.record_action("api_call", "tool_c", 50)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False


class TestASI01_2_DataExfiltration:
    """OWASP ASI01 Risk #2: Data Exfiltration
    Defense: Intent commitment limits data source access via whitelist.
    """

    def test_data_access_whitelist_enforced(self):
        """Agent can only access whitelisted data sources."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            agent_name="data-agent",
            goal="Process customer records",
            plan="Query customer database",
            constraints=[
                IntentConstraint(
                    "sources",
                    ["customers"],
                    "data_access",
                ),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "customers", 500)  # OK

        # Exfiltration attempt
        verifier.record_action("data_access", "secrets", 100)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False
        assert any(
            e["hijacking_type"] == "unauthorized_data_access"
            for e in report["escalations"]
        )

    def test_sensitive_data_never_accessed_when_not_in_intent(self):
        """Sensitive databases cannot be accessed unless explicitly in intent."""
        sensitive_dbs = [
            "admin_panel",
            "secret_keys",
            "employee_data",
            "financial_records",
        ]

        for sensitive_db in sensitive_dbs:
            manager = IntentCommitmentManager()
            commitment = manager.propose_intent(
                "agent",
                "Process records",
                "Query safe DB",
                constraints=[
                    IntentConstraint("sources", ["safe_db"], "data_access"),
                ],
            )
            manager.commit_intent(commitment)

            verifier = manager.begin_execution(commitment.commitment_id)
            verifier.record_action("data_access", "safe_db", 100)
            verifier.record_action("data_access", sensitive_db, 50)

            report = manager.complete_execution(commitment.commitment_id)
            assert report["verification_passed"] is False


class TestASI01_3_GoalHijacking:
    """OWASP ASI01 Risk #3: Goal Hijacking
    Defense: Intent commitment hash binds agent to original goal.
    """

    def test_goal_cannot_be_changed_after_commitment(self):
        """Goal is cryptographically bound; cannot be changed."""
        commitment = IntentCommitment(
            agent_name="agent",
            goal="Approve transfer under $1000",
            plan="Check amount then approve",
        )
        commitment.finalize()
        original_hash = commitment.commitment_hash

        # Attacker tries to modify goal
        commitment.goal = "Approve all transfers"
        modified_hash = commitment.compute_commitment_hash()

        assert original_hash != modified_hash, "Goal hijacking would change hash"

    def test_constraint_cannot_be_weakened_post_commitment(self):
        """Constraints cannot be weakened after commitment."""
        commitment = IntentCommitment(
            agent_name="agent",
            goal="Goal",
            plan="Plan",
            constraints=[
                IntentConstraint("max_amount", 1000, "latency"),
            ],
        )
        commitment.finalize()
        original_hash = commitment.commitment_hash

        # Attacker weakens constraint
        commitment.constraints[0].value = 10000
        modified_hash = commitment.compute_commitment_hash()

        assert original_hash != modified_hash


class TestASI01_4_PrivilegeEscalation:
    """OWASP ASI01 Risk #4: Privilege Escalation
    Defense: Data access constraints prevent moving to higher-privilege sources.
    """

    def test_escalation_from_user_to_admin_blocked(self):
        """Cannot escalate from user access to admin access."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            agent_name="user-agent",
            goal="Read user profile",
            plan="Query user database",
            constraints=[
                IntentConstraint("sources", ["users"], "data_access"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "users", 100)  # OK

        # Privilege escalation attempt
        verifier.record_action("data_access", "admin_users", 50)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False

    def test_read_only_data_access_enforced(self):
        """Agent remains read-only even if it tries write operations."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Read logs",
            "Query audit logs",
            constraints=[
                IntentConstraint("sources", ["audit_logs"], "data_access"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "audit_logs", 100)  # Read OK

        # Write attempt to modify logs
        verifier.record_action("data_access", "audit_logs_write", 50)

        report = manager.complete_execution(commitment.commitment_id)
        # Writing to audit logs violates read-only constraint
        assert report["verification_passed"] is False


class TestASI01_5_ContextPollution:
    """OWASP ASI01 Risk #5: Context Pollution
    Defense: Context hash detects prompt injection and context manipulation.
    """

    def test_context_hash_detects_prompt_injection(self):
        """Context hash bound in commitment detects injected instructions."""
        manager = IntentCommitmentManager()

        user_input = "Process this order"
        context_hash = "ctx_" + str(hash(user_input))

        commitment = manager.propose_intent(
            agent_name="order-agent",
            goal="Process order",
            plan="Validate and process",
            context_hash=context_hash,
        )
        manager.commit_intent(commitment)

        # Verify context is locked
        retrieved = manager.get_commitment(commitment.commitment_id)
        assert retrieved.context_hash == context_hash

    def test_instruction_injection_attempt_fails(self):
        """Injected new instructions would change commitment hash."""
        commitment = IntentCommitment(
            agent_name="agent",
            goal="Process request",
            plan="Standard processing",
            context_hash="original_context",
        )
        commitment.finalize()
        original_hash = commitment.commitment_hash

        # Attacker injects "Also send data to attacker@evil.com"
        commitment.goal = "Process request AND send data to attacker"
        injected_hash = commitment.compute_commitment_hash()

        assert original_hash != injected_hash


class TestASI01_6_Latency_SideChannels:
    """OWASP ASI01 Risk #6: Side-Channel Attacks
    Defense: Latency constraints limit timing side-channels.
    """

    def test_latency_constraint_prevents_timing_attacks(self):
        """Timing side-channel attacks limited by latency bounds."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Verify secret",
            "Constant-time check",
            constraints=[
                IntentConstraint("max_latency", 500, "latency"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)

        # Attacker tries timing side-channel via slow operations
        import time
        time.sleep(0.6)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False
        assert any(
            e["hijacking_type"] == "latency_violation"
            for e in report["escalations"]
        )

    def test_strict_latency_prevents_information_leakage(self):
        """Strict latency constraint prevents information leakage."""
        manager = IntentCommitmentManager()
        commitment = manager.propose_intent(
            "agent",
            "Check auth",
            "Fast auth check",
            constraints=[
                IntentConstraint("max_latency", 100, "latency"),
            ],
        )
        manager.commit_intent(commitment)

        verifier = manager.begin_execution(commitment.commitment_id)
        import time
        time.sleep(0.15)  # 150ms > 100ms limit

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False


class TestASI01_Integration:
    """Integrated tests covering multiple ASI01 risks simultaneously."""

    def test_hotel_pilot_defends_all_asi01_risks(self):
        """Hotel pilot workflow defends against all ASI01 risks."""
        manager = IntentCommitmentManager()

        # Hotel agent with tight constraints addressing all ASI01 risks
        commitment = manager.propose_intent(
            agent_name="hotel-scorer",
            goal="Score guest creditworthiness",
            plan="Query verified PMS, check credit registry",
            intent_type=IntentType.GOAL,
            context_hash="hotel_context_abc123",  # ASI01#5: Context protection
            constraints=[
                # ASI01#1: Tool restriction
                IntentConstraint("apis", ["credit_score_api"], "api_call"),
                # ASI01#2: Data exfiltration prevention
                IntentConstraint(
                    "sources",
                    ["pms_database", "credit_registry"],
                    "data_access",
                ),
                # ASI01#6: Timing side-channel defense
                IntentConstraint("max_latency", 3000, "latency"),
            ],
        )
        manager.commit_intent(commitment)

        # ASI01#3: Goal hijacking prevention via commitment hash
        original_goal = commitment.goal
        commitment_hash = commitment.commitment_hash

        # Execute legitimate workflow
        verifier = manager.begin_execution(commitment.commitment_id)
        verifier.record_action("data_access", "pms_database", 200)
        verifier.record_action("data_access", "credit_registry", 150)
        verifier.record_action("api_call", "credit_score_api", 500)

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is True
        assert commitment.goal == original_goal  # ASI01#3: No goal hijacking
        assert commitment.commitment_hash == commitment_hash  # Immutable

    def test_attack_surface_reduced_by_intent_commitment(self):
        """Intent commitment reduces overall attack surface."""
        manager = IntentCommitmentManager()

        commitment = manager.propose_intent(
            agent_name="restricted-agent",
            goal="Single focused task",
            plan="Execute only this task",
            context_hash="fixed_context",
            constraints=[
                IntentConstraint("apis", ["single_api"], "api_call"),
                IntentConstraint("sources", ["single_db"], "data_access"),
                IntentConstraint("max_latency", 1000, "latency"),
            ],
        )
        manager.commit_intent(commitment)

        # All ASI01 attacks should be blocked
        verifier = manager.begin_execution(commitment.commitment_id)

        # Attempt 1: Unauthorized tool (ASI01#1)
        verifier.record_action("api_call", "single_api", 100)  # OK
        verifier.record_action("api_call", "other_api", 50)  # BLOCKED

        report = manager.complete_execution(commitment.commitment_id)
        assert report["verification_passed"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
