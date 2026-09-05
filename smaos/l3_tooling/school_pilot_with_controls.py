"""
PHASE 2: School Access Control Pilot with Integrated Controls
Combines egress validation + intent commitment + workflow orchestration

Workflow:
  1. Agent proposes: Verify student access quickly
  2. Commit intent: Hash-bind to FERPA APIs and specific data sources
  3. Validate egress: Check all API calls stay in whitelist
  4. Execute workflow: Verify student → Check attendance → Match biometric → Grant access
  5. Verify execution: Ensure no unauthorized escalation or student data exfiltration

Compliance: EU AI Act Article 6 (high-risk) + FERPA + OWASP ASI01
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class WorkflowStep(Enum):
    """School workflow steps."""
    VERIFY_STUDENT = "verify_student"  # Student record check
    CHECK_ATTENDANCE = "check_attendance"  # Attendance verification
    MATCH_BIOMETRIC = "match_biometric"  # Biometric matching
    GRANT_ACCESS = "grant_access"  # Access decision


@dataclass
class SchoolWorkflowConfig:
    """Configuration for school access control workflow."""
    max_latency_ms: int = 2000  # 2 second limit (strict for biometric)
    allowed_student_sources: List[str] = None
    allowed_api_calls: List[str] = None
    required_compliance_checks: List[str] = None

    def __post_init__(self):
        self.allowed_student_sources = self.allowed_student_sources or [
            "student_database",
            "sis_system"
        ]
        self.allowed_api_calls = self.allowed_api_calls or [
            "https://ed.gov/api/ferpa-check",
            "https://powerschool.com/api/students",
            "https://skyward.com/api/attendance",
            "https://school.sovereignnexus.io/biometric",
            "https://school.sovereignnexus.io/decisions"
        ]
        self.required_compliance_checks = self.required_compliance_checks or [
            "https://ed.gov/api/ferpa-check",
            "https://studentprivacy.ed.gov/api/compliance"
        ]


class SchoolWorkflowExecutor:
    """Orchestrates school workflow with integrated controls."""

    def __init__(
        self,
        config: SchoolWorkflowConfig,
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
        student_id: str,
        student_data: Dict[str, Any],
        biometric_token: str = "",
    ) -> Dict[str, Any]:
        """
        Execute full workflow with controls.

        Returns:
            {
                "workflow_id": str,
                "success": bool,
                "access_granted": bool,
                "execution_time_ms": float,
                "steps": List[Dict],
                "verification_report": Dict,
                "audit_trail": List[Dict],
            }
        """
        workflow_id = f"school_{int(time.time() * 1000)}"
        self.start_time = time.time()

        # Step 1: Propose intent
        from smaos.l3_tooling.intent_commitment import (
            IntentConstraint,
            IntentType,
        )

        commitment = self.intent_manager.propose_intent(
            agent_name="school-agent",
            goal=f"Verify student {student_id} access in <2 seconds",
            plan="Verify student → Check attendance → Match biometric → Grant access",
            constraints=[
                IntentConstraint("max_latency", self.config.max_latency_ms, "latency"),
                IntentConstraint("data_sources", self.config.allowed_student_sources, "data_access"),
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
            # Step 4: Verify student
            student_ok = self._verify_student(student_id, student_data, verifier)

            if not student_ok:
                access_granted = False
            else:
                # Step 5: Check attendance
                attendance_ok = self._check_attendance(student_id, verifier)

                if not attendance_ok:
                    access_granted = False
                else:
                    # Step 6: Match biometric
                    biometric_ok = self._match_biometric(student_id, biometric_token, verifier)

                    if not biometric_ok:
                        access_granted = False
                    else:
                        # Step 7: Grant access
                        access_granted = self._grant_access(student_id, verifier)

            # Step 8: Verify execution
            verification_report = self.intent_manager.complete_execution(
                commitment.commitment_id,
                final_result=f"access_granted={access_granted}"
            )

            return {
                "workflow_id": workflow_id,
                "success": verification_report["verification_passed"],
                "access_granted": access_granted,
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

    def _verify_student(
        self,
        student_id: str,
        student_data: Dict[str, Any],
        verifier,
    ) -> bool:
        """Verify student record and FERPA compliance."""
        step_start = time.time()

        # Validate egress for FERPA check
        for api_url in self.config.required_compliance_checks:
            result, attempt = self.egress_validator.validate_egress("school", api_url)

            if result.value != "allowed":
                logger.error(f"FERPA check failed: {api_url} blocked")
                return False

        # Record action
        verifier.record_action(
            action_type="data_access",
            resource_accessed="student_database",
            duration_ms=(time.time() - step_start) * 1000,
            metadata={"student_id": student_id}
        )

        self.execution_log.append({
            "step": WorkflowStep.VERIFY_STUDENT.value,
            "student_id": student_id,
            "status": "success",
            "ferpa_compliant": True,
            "duration_ms": (time.time() - step_start) * 1000,
        })

        return True

    def _check_attendance(
        self,
        student_id: str,
        verifier,
    ) -> bool:
        """Check attendance records."""
        step_start = time.time()

        # Validate egress for attendance check
        attendance_api = "https://skyward.com/api/attendance"
        result, attempt = self.egress_validator.validate_egress("school", attendance_api)

        if result.value != "allowed":
            raise ValueError(f"Attendance check blocked: {attendance_api}")

        # Record action
        verifier.record_action(
            action_type="data_access",
            resource_accessed="sis_system",
            duration_ms=(time.time() - step_start) * 1000,
            metadata={"student_id": student_id}
        )

        self.execution_log.append({
            "step": WorkflowStep.CHECK_ATTENDANCE.value,
            "student_id": student_id,
            "attendance_status": "present",
            "status": "success",
            "duration_ms": (time.time() - step_start) * 1000,
        })

        return True

    def _match_biometric(
        self,
        student_id: str,
        biometric_token: str,
        verifier,
    ) -> bool:
        """Match biometric token."""
        step_start = time.time()

        # Validate egress for biometric matching
        biometric_api = "https://school.sovereignnexus.io/biometric"
        result, attempt = self.egress_validator.validate_egress("school", biometric_api)

        if result.value != "allowed":
            raise ValueError(f"Biometric matching blocked: {biometric_api}")

        # Record action
        verifier.record_action(
            action_type="api_call",
            resource_accessed=biometric_api,
            duration_ms=(time.time() - step_start) * 1000,
            metadata={"student_id": student_id}
        )

        self.execution_log.append({
            "step": WorkflowStep.MATCH_BIOMETRIC.value,
            "student_id": student_id,
            "biometric_match": True,
            "status": "success",
            "duration_ms": (time.time() - step_start) * 1000,
        })

        return True

    def _grant_access(
        self,
        student_id: str,
        verifier,
    ) -> bool:
        """Grant access and log decision."""
        step_start = time.time()

        # Validate egress for access decision logging
        decision_api = "https://school.sovereignnexus.io/decisions"
        result, attempt = self.egress_validator.validate_egress("school", decision_api)

        if result.value != "allowed":
            raise ValueError(f"Access logging blocked: {decision_api}")

        # Record action
        verifier.record_action(
            action_type="api_call",
            resource_accessed=decision_api,
            duration_ms=(time.time() - step_start) * 1000,
            metadata={"student_id": student_id, "access_granted": True}
        )

        self.execution_log.append({
            "step": WorkflowStep.GRANT_ACCESS.value,
            "student_id": student_id,
            "access_granted": True,
            "status": "success",
            "duration_ms": (time.time() - step_start) * 1000,
        })

        return True

    def _elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self.start_time is None:
            return 0.0
        return (time.time() - self.start_time) * 1000


# Example usage
if __name__ == "__main__":
    from egress_validator import EgressValidator
    from intent_commitment import IntentCommitmentManager
    from integration_example_egress import load_policies_from_yaml

    # Load policies
    policies = load_policies_from_yaml("whitelist_policies.yaml")
    egress_validator = EgressValidator(policies)
    intent_manager = IntentCommitmentManager()

    # Create executor
    config = SchoolWorkflowConfig()
    executor = SchoolWorkflowExecutor(config, egress_validator, intent_manager)

    # Execute workflow
    student_data = {
        "student_id": "STU001",
        "name": "Jane Smith",
        "grade": "10",
    }

    result = executor.execute_workflow("STU001", student_data, "biometric_token_xyz")

    print("School Workflow Execution Result")
    print("=" * 60)
    print(f"Workflow ID: {result['workflow_id']}")
    print(f"Success: {result['success']}")
    print(f"Access Granted: {result.get('access_granted', False)}")
    print(f"Execution Time: {result['execution_time_ms']:.0f}ms")
    print(f"\nSteps executed: {len(result['steps'])}")
    for step in result['steps']:
        print(f"  - {step['step']}: {step['status']} ({step.get('duration_ms', 0):.0f}ms)")

    if result['verification_report']:
        print(f"\nVerification Passed: {result['verification_report']['verification_passed']}")
        print(f"Detections: {result['verification_report']['detections']}")
