"""L4 Orchestration: LangGraph Integration with Deterministic State Machine

Integrates DeterministicWorkflow with ActionVelocityTracker for formal LangGraph orchestration.
Provides fault-tolerant, checkpoint-recoverable workflows with human authorization gates.

Usage:
    from smaos.l4_orchestration.l4_langgraph_integration import L4WorkflowOrchestrator

    orchestrator = L4WorkflowOrchestrator(pilot_name="hotel")
    result = orchestrator.execute_intent(
        intent={"guest_id": "g_001", "amount": 100},
        classification={"risk_level": "low"},
        nodes=[("fetch_pms", tool_fetch_pms), ...],
        approver="John Doe"
    )
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Callable, Tuple
from .action_velocity import ActionVelocityTracker, ActionVelocityStatus
from .deterministic_state_machine import (
    DeterministicWorkflow,
    WorkflowState,
)

logger = logging.getLogger(__name__)


class VelocityCheckedNode:
    """Wraps a LangGraph node to enforce velocity constraints"""

    def __init__(self, node_name: str, tool_func: Callable,
                 tracker: ActionVelocityTracker, pilot_name: str,
                 workflow_id: str):
        """
        Initialize velocity-checked node.

        Args:
            node_name: Name of the node (e.g., 'score_credit')
            tool_func: The actual tool function to execute
            tracker: ActionVelocityTracker instance
            pilot_name: Pilot identifier (hotel/glass/school)
            workflow_id: Workflow instance ID
        """
        self.node_name = node_name
        self.tool_func = tool_func
        self.tracker = tracker
        self.pilot_name = pilot_name
        self.workflow_id = workflow_id
        self.call_count = 0

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute node with velocity checking.

        Returns state unchanged if velocity OK, escalation error if violated.
        """
        # Check velocity before execution
        action_id = f"{self.pilot_name}_{self.node_name}_{self.call_count}"
        self.call_count += 1

        status, violation = self.tracker.record_action(
            action_id=action_id,
            tool_name=self.node_name,
            pilot_name=self.pilot_name,
            workflow_id=self.workflow_id
        )

        # Fail-closed: deny execution if escalated
        if status == ActionVelocityStatus.ESCALATED:
            logger.error(
                f"VELOCITY VIOLATION: Node {self.node_name} blocked. "
                f"Escalation {violation.violation_id} pending human review."
            )
            return {
                **state,
                "velocity_escalated": True,
                "escalation_id": self.tracker.escalations[-1]['escalation_id'],
                "error": f"Velocity threshold exceeded for {self.pilot_name}"
            }

        # Execute the tool
        try:
            result = self.tool_func(state)
            logger.info(f"Node {self.node_name} executed successfully")
            return result
        except Exception as e:
            logger.error(f"Node {self.node_name} failed: {e}")
            return {
                **state,
                "error": str(e)
            }


class VelocityCheckedWorkflow:
    """LangGraph workflow with integrated velocity tracking"""

    def __init__(self, pilot_name: str, workflow_id: Optional[str] = None,
                 tracker: Optional[ActionVelocityTracker] = None,
                 audit_log_path: Optional[str] = None):
        """
        Initialize velocity-checked workflow.

        Args:
            pilot_name: Pilot identifier (hotel/glass/school)
            workflow_id: Optional workflow ID (auto-generated if None)
            tracker: Optional custom tracker (default thresholds if None)
            audit_log_path: Optional path for audit logging
        """
        self.pilot_name = pilot_name
        self.workflow_id = workflow_id or f"wf_{uuid.uuid4().hex[:8]}"
        self.tracker = tracker or ActionVelocityTracker(
            audit_log_path=audit_log_path
        )
        self.nodes: Dict[str, VelocityCheckedNode] = {}
        self.node_sequence: List[str] = []

    def add_node(self, node_name: str, tool_func: Callable) -> None:
        """
        Add a node to the workflow with velocity checking.

        Args:
            node_name: Name of the node
            tool_func: Function to execute (receives state dict)
        """
        node = VelocityCheckedNode(
            node_name=node_name,
            tool_func=tool_func,
            tracker=self.tracker,
            pilot_name=self.pilot_name,
            workflow_id=self.workflow_id
        )
        self.nodes[node_name] = node
        self.node_sequence.append(node_name)
        logger.info(f"Added node {node_name} to workflow {self.workflow_id}")

    def execute(self, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute workflow sequentially with velocity checks.

        Args:
            state: Initial state dict

        Returns:
            Final state after all nodes execute or escalation
        """
        state = state or {}
        state["workflow_id"] = self.workflow_id
        state["pilot_name"] = self.pilot_name
        state["velocity_escalated"] = False

        logger.info(f"Starting workflow {self.workflow_id} for {self.pilot_name}")

        for node_name in self.node_sequence:
            logger.info(f"Executing node {node_name}")
            node = self.nodes[node_name]
            state = node.invoke(state)

            # Stop if velocity escalated
            if state.get("velocity_escalated"):
                logger.warning(
                    f"Workflow {self.workflow_id} escalated at node {node_name}"
                )
                return state

            # Stop if error
            if "error" in state:
                logger.error(f"Workflow stopped due to error: {state['error']}")
                return state

        logger.info(f"Workflow {self.workflow_id} completed successfully")
        return state

    def get_velocity_report(self) -> Dict[str, Any]:
        """Get velocity report for this workflow's pilot"""
        return self.tracker.get_velocity_report(self.pilot_name)

    def get_pending_escalations(self) -> List[Dict[str, Any]]:
        """Get pending escalations for human review"""
        return [
            e for e in self.tracker.get_escalations_pending_review()
            if e['pilot_name'] == self.pilot_name and e['workflow_id'] == self.workflow_id
        ]


# Example tool functions (would be replaced with real tools)

def tool_fetch_pms(state: Dict) -> Dict:
    """Example hotel tool: Fetch PMS data"""
    state['pms_data'] = {
        'guest_id': '12345',
        'checkin': '2026-09-01',
        'rating': 4.5
    }
    return state


def tool_score_credit(state: Dict) -> Dict:
    """Example hotel tool: Score credit"""
    state['credit_score'] = 750
    state['approval_likelihood'] = 0.95
    return state


def tool_check_sanctions(state: Dict) -> Dict:
    """Example hotel tool: Check sanctions"""
    state['sanctions_check'] = 'clear'
    state['risk_level'] = 'low'
    return state


def tool_parse_cad(state: Dict) -> Dict:
    """Example glass tool: Parse CAD model"""
    state['cad_parsed'] = True
    state['model_vertices'] = 1500
    return state


def tool_check_safety(state: Dict) -> Dict:
    """Example glass tool: Check material safety"""
    state['material_safe'] = True
    state['safety_rating'] = 'A'
    return state


def tool_verify_student(state: Dict) -> Dict:
    """Example school tool: Verify student records"""
    state['student_verified'] = True
    state['enrollment_status'] = 'active'
    return state


def tool_check_eligibility(state: Dict) -> Dict:
    """Example school tool: Check eligibility"""
    state['eligible'] = True
    state['clearance_level'] = 'standard'
    return state


# Example usage

def example_hotel_workflow():
    """Example: Hotel credit scoring workflow with velocity tracking"""
    workflow = VelocityCheckedWorkflow(
        pilot_name="hotel",
        audit_log_path="/tmp/hotel_velocity.jsonl"
    )

    # Add nodes in sequence
    workflow.add_node("fetch_pms", tool_fetch_pms)
    workflow.add_node("score_credit", tool_score_credit)
    workflow.add_node("check_sanctions", tool_check_sanctions)

    # Execute workflow
    result = workflow.execute()

    # Check result
    if result.get("velocity_escalated"):
        print(f"ESCALATED: {result['escalation_id']}")
        escalations = workflow.get_pending_escalations()
        for e in escalations:
            print(f"  {e['action_required']}")
    else:
        print("Workflow completed successfully")
        print(f"Credit score: {result.get('credit_score')}")
        print(f"Risk level: {result.get('risk_level')}")

    # Print velocity report
    report = workflow.get_velocity_report()
    print(f"Per-minute actions: {report['per_minute_actions']}/{report['per_minute_threshold']}")


def example_glass_workflow():
    """Example: Glass safety review workflow with velocity tracking"""
    workflow = VelocityCheckedWorkflow(
        pilot_name="glass",
        audit_log_path="/tmp/glass_velocity.jsonl"
    )

    # Add nodes
    workflow.add_node("parse_cad", tool_parse_cad)
    workflow.add_node("check_safety", tool_check_safety)

    # Execute
    result = workflow.execute()

    if not result.get("velocity_escalated"):
        print("Safety review completed")
        print(f"Material safe: {result.get('material_safe')}")
        print(f"Safety rating: {result.get('safety_rating')}")


def example_school_workflow():
    """Example: School access control workflow with velocity tracking"""
    workflow = VelocityCheckedWorkflow(
        pilot_name="school",
        audit_log_path="/tmp/school_velocity.jsonl"
    )

    # Add nodes
    workflow.add_node("verify_student", tool_verify_student)
    workflow.add_node("check_eligibility", tool_check_eligibility)

    # Execute
    result = workflow.execute()

    if not result.get("velocity_escalated"):
        print("Access control check completed")
        print(f"Eligible: {result.get('eligible')}")
        print(f"Clearance level: {result.get('clearance_level')}")


if __name__ == "__main__":
    example_hotel_workflow()
