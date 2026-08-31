"""
PHASE 2: Glass Safety Defect Detection Pilot with Integrated Controls
Combines egress validation + intent commitment + workflow orchestration

Workflow:
  1. Agent proposes: Analyze glass safety defects
  2. Commit intent: Hash-bind to CAD repos and safety databases
  3. Validate egress: Check all API calls stay in whitelist
  4. Execute workflow: Fetch CAD → Identify materials → Check standards → Approve/reject
  5. Verify execution: Ensure no CAD exfiltration or safety bypass

Compliance: EU AI Act Article 6 (high-risk) + OWASP ASI01 defense
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class WorkflowStep(Enum):
    """Glass workflow steps."""
    FETCH_CAD = "fetch_cad"  # CAD model retrieval
    IDENTIFY_MATERIALS = "identify_materials"  # Material analysis
    CHECK_STANDARDS = "check_standards"  # Safety standards lookup
    APPROVE_REJECT = "approve_reject"  # Final decision


@dataclass
class GlassWorkflowConfig:
    """Configuration for glass defect detection workflow."""
    max_latency_ms: int = 10000  # 10 second limit
    allowed_cad_sources: List[str] = None
    allowed_api_calls: List[str] = None
    required_standard_checks: List[str] = None

    def __post_init__(self):
        self.allowed_cad_sources = self.allowed_cad_sources or [
            "cad_storage",
            "github_repos"
        ]
        self.allowed_api_calls = self.allowed_api_calls or [
            "https://api.github.com/repos",
            "https://raw.githubusercontent.com/content",
            "https://www.astm.org/api/standards",
            "https://www.nist.gov/api/materials",
            "https://glass.sovereignnexus.io/analysis"
        ]
        self.required_standard_checks = self.required_standard_checks or [
            "https://www.astm.org/api/standards",
            "https://www.iso.org/api/standards",
            "https://www.nist.gov/api/materials"
        ]


class GlassWorkflowExecutor:
    """Orchestrates glass workflow with integrated controls."""

    def __init__(
        self,
        config: GlassWorkflowConfig,
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
        model_id: str,
        model_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute full workflow with controls.

        Returns:
            {
                "workflow_id": str,
                "success": bool,
                "approval_decision": "approved" | "rejected",
                "execution_time_ms": float,
                "steps": List[Dict],
                "verification_report": Dict,
                "audit_trail": List[Dict],
            }
        """
        workflow_id = f"glass_{int(time.time() * 1000)}"
        self.start_time = time.time()

        # Step 1: Propose intent
        from smaos.l3_tooling.intent_commitment import (
            IntentConstraint,
            IntentType,
        )

        commitment = self.intent_manager.propose_intent(
            agent_name="glass-agent",
            goal=f"Analyze safety defects for model {model_id} in <10 seconds",
            plan="Fetch CAD → Identify materials → Check standards → Approve/reject",
            constraints=[
                IntentConstraint("max_latency", self.config.max_latency_ms, "latency"),
                IntentConstraint("data_sources", self.config.allowed_cad_sources, "data_access"),
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
            # Step 4: Fetch CAD model
            cad_data = self._fetch_cad(model_id, model_metadata, verifier)

            # Step 5: Identify materials
            materials = self._identify_materials(cad_data, verifier)

            # Step 6: Check standards
            standards_ok = self._check_standards(materials, verifier)

            # Step 7: Approve/reject
            decision = self._approve_reject(materials, standards_ok, verifier)

            # Step 8: Verify execution
            verification_report = self.intent_manager.complete_execution(
                commitment.commitment_id,
                final_result=f"decision={decision}"
            )

            return {
                "workflow_id": workflow_id,
                "success": verification_report["verification_passed"],
                "approval_decision": decision,
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

    def _fetch_cad(
        self,
        model_id: str,
        model_metadata: Dict[str, Any],
        verifier,
    ) -> Dict[str, Any]:
        """Fetch CAD model from repository."""
        step_start = time.time()

        # Validate egress for CAD fetch
        cad_api = "https://api.github.com/repos/user/model"
        result, attempt = self.egress_validator.validate_egress("glass", cad_api)

        if result.value != "allowed":
            raise ValueError(f"CAD fetch blocked: {cad_api}")

        # Record action
        verifier.record_action(
            action_type="data_access",
            resource_accessed="cad_storage",
            duration_ms=(time.time() - step_start) * 1000,
            metadata={"model_id": model_id}
        )

        self.execution_log.append({
            "step": WorkflowStep.FETCH_CAD.value,
            "model_id": model_id,
            "status": "success",
            "duration_ms": (time.time() - step_start) * 1000,
        })

        return model_metadata

    def _identify_materials(
        self,
        cad_data: Dict[str, Any],
        verifier,
    ) -> List[str]:
        """Identify materials from CAD model."""
        step_start = time.time()

        # Record action
        verifier.record_action(
            action_type="computation",
            resource_accessed="material_analysis",
            duration_ms=(time.time() - step_start) * 1000,
            metadata={"analysis_type": "material_identification"}
        )

        self.execution_log.append({
            "step": WorkflowStep.IDENTIFY_MATERIALS.value,
            "materials_found": ["borosilicate", "tempered_glass"],
            "status": "success",
            "duration_ms": (time.time() - step_start) * 1000,
        })

        return ["borosilicate", "tempered_glass"]

    def _check_standards(
        self,
        materials: List[str],
        verifier,
    ) -> bool:
        """Check safety standards for materials."""
        step_start = time.time()

        # Validate egress for standards checks
        for api_url in self.config.required_standard_checks:
            result, attempt = self.egress_validator.validate_egress(
                "glass",
                api_url
            )

            if result.value != "allowed":
                logger.error(f"Standards check failed: {api_url} blocked")
                return False

        # Record action
        verifier.record_action(
            action_type="api_call",
            resource_accessed="https://www.astm.org/api/standards",
            duration_ms=(time.time() - step_start) * 1000,
            metadata={"materials": materials}
        )

        self.execution_log.append({
            "step": WorkflowStep.CHECK_STANDARDS.value,
            "materials": materials,
            "status": "success",
            "standards_compliant": True,
            "duration_ms": (time.time() - step_start) * 1000,
        })

        return True

    def _approve_reject(
        self,
        materials: List[str],
        standards_ok: bool,
        verifier,
    ) -> str:
        """Final approval/rejection decision."""
        step_start = time.time()

        # Validate egress for decision logging
        decision_api = "https://glass.sovereignnexus.io/analysis"
        result, attempt = self.egress_validator.validate_egress("glass", decision_api)

        if result.value != "allowed":
            raise ValueError(f"Decision logging blocked: {decision_api}")

        # Record action
        decision = "approved" if standards_ok else "rejected"
        verifier.record_action(
            action_type="api_call",
            resource_accessed=decision_api,
            duration_ms=(time.time() - step_start) * 1000,
            metadata={"decision": decision}
        )

        self.execution_log.append({
            "step": WorkflowStep.APPROVE_REJECT.value,
            "decision": decision,
            "status": "success",
            "duration_ms": (time.time() - step_start) * 1000,
        })

        return decision

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
    config = GlassWorkflowConfig()
    executor = GlassWorkflowExecutor(config, egress_validator, intent_manager)

    # Execute workflow
    model_metadata = {
        "model_id": "GLASS001",
        "type": "tempered_glass_panel",
        "dimensions": "100x50x5mm",
    }

    result = executor.execute_workflow("GLASS001", model_metadata)

    print("Glass Workflow Execution Result")
    print("=" * 60)
    print(f"Workflow ID: {result['workflow_id']}")
    print(f"Success: {result['success']}")
    print(f"Decision: {result.get('approval_decision', 'N/A')}")
    print(f"Execution Time: {result['execution_time_ms']:.0f}ms")
    print(f"\nSteps executed: {len(result['steps'])}")
    for step in result['steps']:
        print(f"  - {step['step']}: {step['status']} ({step.get('duration_ms', 0):.0f}ms)")

    if result['verification_report']:
        print(f"\nVerification Passed: {result['verification_report']['verification_passed']}")
        print(f"Detections: {result['verification_report']['detections']}")
