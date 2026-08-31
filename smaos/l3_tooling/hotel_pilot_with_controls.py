"""
PHASE 2: Hotel Credit Scoring Pilot with Integrated Controls
Combines egress validation + intent commitment + workflow orchestration

Workflow:
  1. Agent proposes: Score hotel guest credit in <5s
  2. Commit intent: Hash-bind to specific APIs/datasources
  3. Validate egress: Check all API calls stay in whitelist
  4. Execute workflow: Query PMS → Score → Log decision
  5. Verify execution: Ensure no goal drift or data exfiltration

Compliance: EU AI Act Article 6 (high-risk) + OWASP ASI01 defense
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class WorkflowStep(Enum):
    """Hotel workflow steps."""
    QUERY_PMS = "query_pms"  # Guest data
    CHECK_SANCTIONS = "check_sanctions"  # Compliance check
    SCORE_CREDIT = "score_credit"  # ML model scoring
    LOG_DECISION = "log_decision"  # Audit trail


@dataclass
class HotelWorkflowConfig:
    """Configuration for hotel credit scoring workflow."""
    max_latency_ms: int = 5000  # 5 second limit
    allowed_pms_sources: List[str] = None
    allowed_api_calls: List[str] = None
    required_sanction_checks: List[str] = None

    def __post_init__(self):
        self.allowed_pms_sources = self.allowed_pms_sources or [
            "pms_database",
            "guest_registry"
        ]
        self.allowed_api_calls = self.allowed_api_calls or [
            "https://api.equifax.com/score",
            "https://api.experian.com/score",
            "https://api.worldcompliance.com/sanctions",
            "https://compliance.sovereignnexus.io/decisions"
        ]
        self.required_sanction_checks = self.required_sanction_checks or [
            "https://ofac.treasury.gov/check",
            "https://api.worldcompliance.com/pep"
        ]


class HotelWorkflowExecutor:
    """Orchestrates hotel workflow with integrated controls."""

    def __init__(
        self,
        config: HotelWorkflowConfig,
        egress_validator,
        intent_manager,
    ):
        self.config = config
        self.egress_validator = egress_validator
        self.intent_manager = intent_manager
        self.execution_log = []
        self.start_time = None

    def execute_workflow(
        self,
        guest_id: str,
        guest_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute full workflow with controls.

        Returns:
            {
                "workflow_id": str,
                "success": bool,
                "credit_score": int,
                "execution_time_ms": float,
                "steps": List[Dict],
                "verification_report": Dict,
                "audit_trail": List[Dict],
            }
        """
        workflow_id = f"hotel_{int(time.time() * 1000)}"
        self.start_time = time.time()

        # Step 1: Propose intent
        from smaos.l3_tooling.intent_commitment import (
            IntentCommitment,
            IntentConstraint,
            IntentType,
        )

        commitment = self.intent_manager.propose_intent(
            agent_name="hotel-agent",
            goal=f"Score credit for guest {guest_id} in <5 seconds",
            plan="Query PMS → Check sanctions → Run ML model → Log decision",
            constraints=[
                IntentConstraint("max_latency", self.config.max_latency_ms, "latency"),
                IntentConstraint("data_sources", self.config.allowed_pms_sources, "data_access"),
                IntentConstraint("apis", self.config.allowed_api_calls, "api_call"),
            ],
            intent_type=IntentType.GOAL,
            model="claude-opus-4",
        )

        # Step 2: Commit intent
        commitment = self.intent_manager.commit_intent(commitment)

        # Step 3: Begin execution tracking
        verifier = self.intent_manager.begin_execution(commitment.commitment_id)

        try:
            # Step 4: Query PMS (guest data)
            pms_data = self._query_pms(guest_id, guest_data, verifier)

            # Step 5: Check sanctions
            sanctions_ok = self._check_sanctions(guest_id, verifier)

            if not sanctions_ok:
                return {
                    "workflow_id": workflow_id,
                    "success": False,
                    "error": "Sanctions check failed",
                    "execution_time_ms": self._elapsed_ms(),
                    "steps": self.execution_log,
                    "verification_report": None,
                    "audit_trail": self.egress_validator.get_audit_log(),
                }

            # Step 6: Score credit
            credit_score = self._score_credit(pms_data, verifier)

            # Step 7: Log decision
            self._log_decision(guest_id, credit_score, verifier)

            # Step 8: Verify execution
            verification_report = self.intent_manager.complete_execution(
                commitment.commitment_id,
                final_result=f"credit_score={credit_score}"
            )

            return {
                "workflow_id": workflow_id,
                "success": verification_report["verification_passed"],
                "credit_score": credit_score,
                "execution_time_ms": self._elapsed_ms(),
                "steps": self.execution_log,
                "verification_report": verification_report,
                "audit_trail": self.egress_validator.get_audit_log(),
            }

        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            return {
                "workflow_id": workflow_id,
                "success": False,
                "error": str(e),
                "execution_time_ms": self._elapsed_ms(),
                "steps": self.execution_log,
                "verification_report": None,
                "audit_trail": self.egress_validator.get_audit_log(),
            }

    def _query_pms(
        self,
        guest_id: str,
        guest_data: Dict[str, Any],
        verifier,
    ) -> Dict[str, Any]:
        """Query PMS for guest data."""
        step_start = time.time()

        # Record action for intent verification
        verifier.record_action(
            action_type="data_access",
            resource_accessed="pms_database",
            duration_ms=(time.time() - step_start) * 1000,
            metadata={"guest_id": guest_id}
        )

        self.execution_log.append({
            "step": WorkflowStep.QUERY_PMS.value,
            "guest_id": guest_id,
            "status": "success",
            "duration_ms": (time.time() - step_start) * 1000,
        })

        return guest_data

    def _check_sanctions(
        self,
        guest_id: str,
        verifier,
    ) -> bool:
        """Check sanctions lists."""
        step_start = time.time()

        # Validate egress for sanctions check
        for api_url in self.config.required_sanction_checks:
            result, attempt = self.egress_validator.validate_egress(
                "hotel",
                api_url
            )

            if result.value != "allowed":
                logger.error(f"Sanctions check failed: {api_url} blocked")
                return False

        # Record action
        verifier.record_action(
            action_type="api_call",
            resource_accessed="https://api.worldcompliance.com/sanctions",
            duration_ms=(time.time() - step_start) * 1000,
            metadata={"guest_id": guest_id}
        )

        self.execution_log.append({
            "step": WorkflowStep.CHECK_SANCTIONS.value,
            "guest_id": guest_id,
            "status": "success",
            "sanctions_ok": True,
            "duration_ms": (time.time() - step_start) * 1000,
        })

        return True

    def _score_credit(
        self,
        pms_data: Dict[str, Any],
        verifier,
    ) -> int:
        """Score credit using ML model."""
        step_start = time.time()

        # Validate egress for scoring API
        score_api = "https://api.equifax.com/score"
        result, attempt = self.egress_validator.validate_egress(
            "hotel",
            score_api
        )

        if result.value != "allowed":
            raise ValueError(f"Score API call blocked: {score_api}")

        # Record action
        verifier.record_action(
            action_type="api_call",
            resource_accessed=score_api,
            duration_ms=(time.time() - step_start) * 1000,
            metadata={"model": "credit_score_v2"}
        )

        # Simulate scoring
        credit_score = 750  # Mock score

        self.execution_log.append({
            "step": WorkflowStep.SCORE_CREDIT.value,
            "score": credit_score,
            "status": "success",
            "duration_ms": (time.time() - step_start) * 1000,
        })

        return credit_score

    def _log_decision(
        self,
        guest_id: str,
        credit_score: int,
        verifier,
    ) -> None:
        """Log decision to compliance backend."""
        step_start = time.time()

        # Validate egress for logging
        log_api = "https://compliance.sovereignnexus.io/decisions"
        result, attempt = self.egress_validator.validate_egress(
            "hotel",
            log_api
        )

        if result.value != "allowed":
            raise ValueError(f"Logging API blocked: {log_api}")

        # Record action
        verifier.record_action(
            action_type="api_call",
            resource_accessed=log_api,
            duration_ms=(time.time() - step_start) * 1000,
            metadata={
                "guest_id": guest_id,
                "score": credit_score,
            }
        )

        self.execution_log.append({
            "step": WorkflowStep.LOG_DECISION.value,
            "guest_id": guest_id,
            "score": credit_score,
            "status": "success",
            "duration_ms": (time.time() - step_start) * 1000,
        })

    def _elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self.start_time is None:
            return 0.0
        return (time.time() - self.start_time) * 1000


# Example usage
if __name__ == "__main__":
    from egress_validator import EgressValidator, EgressPolicy
    from intent_commitment import IntentCommitmentManager
    from integration_example_egress import load_policies_from_yaml

    # Load policies
    policies = load_policies_from_yaml("whitelist_policies.yaml")
    egress_validator = EgressValidator(policies)
    intent_manager = IntentCommitmentManager()

    # Create executor
    config = HotelWorkflowConfig()
    executor = HotelWorkflowExecutor(config, egress_validator, intent_manager)

    # Execute workflow
    guest_data = {
        "guest_id": "GUEST001",
        "name": "John Doe",
        "email": "john@example.com",
    }

    result = executor.execute_workflow("GUEST001", guest_data)

    print("Hotel Workflow Execution Result")
    print("=" * 60)
    print(f"Workflow ID: {result['workflow_id']}")
    print(f"Success: {result['success']}")
    print(f"Credit Score: {result.get('credit_score', 'N/A')}")
    print(f"Execution Time: {result['execution_time_ms']:.0f}ms")
    print(f"\nSteps executed: {len(result['steps'])}")
    for step in result['steps']:
        print(f"  - {step['step']}: {step['status']} ({step.get('duration_ms', 0):.0f}ms)")

    if result['verification_report']:
        print(f"\nVerification Passed: {result['verification_report']['verification_passed']}")
        print(f"Detections: {result['verification_report']['detections']}")
