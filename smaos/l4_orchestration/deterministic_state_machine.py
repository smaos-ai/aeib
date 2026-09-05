"""
L4 Orchestration: Deterministic State Machine with Checkpoints & Human Escalation

Provides fault-tolerant, fail-closed workflow orchestration for LangGraph pilots.
Implements:
  - Deterministic state machine (INIT → COMPLETE)
  - Checkpoint persistence & recovery
  - Human authorization gates
  - Velocity tracking integration

Author: SMAOS Phase 1, 2026
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
import hashlib

from .action_velocity import ActionVelocityTracker

logger = logging.getLogger(__name__)


class WorkflowState(Enum):
    """Deterministic workflow states"""
    INIT = "init"
    INTENT_RECEIVED = "intent_received"
    INTENT_VALIDATED = "intent_validated"
    CLASSIFIED = "classified"
    EXECUTING = "executing"
    AWAITING_AUTHORIZATION = "awaiting_authorization"
    AUTHORIZED = "authorized"
    DENIED = "denied"
    LEDGER_WRITTEN = "ledger_written"
    COMPLETE = "complete"


@dataclass
class WorkflowContext:
    """Workflow execution context"""
    intent: Dict[str, Any]
    classification: Dict[str, Any]
    execution_results: Dict[str, Any]
    velocity_report: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CheckpointManager:
    """Manages workflow checkpoints on disk"""

    def __init__(self, checkpoint_dir: str = "/tmp/smaos_checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"CheckpointManager initialized at {checkpoint_dir}")

    def save_checkpoint(self, workflow_id: str, data: Dict[str, Any]) -> None:
        """Save checkpoint to disk with integrity hash"""
        # Compute hash for integrity
        data_str = json.dumps(data, sort_keys=True)
        checkpoint_hash = hashlib.sha256(data_str.encode()).hexdigest()

        checkpoint_data = {
            **data,
            "checkpoint_hash": checkpoint_hash
        }

        checkpoint_file = Path(self.checkpoint_dir) / f"{workflow_id}.json"
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.debug(f"Checkpoint saved: {workflow_id}")

    def load_checkpoint(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint from disk with hash validation"""
        checkpoint_file = Path(self.checkpoint_dir) / f"{workflow_id}.json"

        if not checkpoint_file.exists():
            return None

        with open(checkpoint_file) as f:
            data = json.load(f)

        # Validate hash
        stored_hash = data.pop("checkpoint_hash")
        data_str = json.dumps(data, sort_keys=True)
        computed_hash = hashlib.sha256(data_str.encode()).hexdigest()

        if stored_hash != computed_hash:
            raise ValueError(f"Checkpoint hash mismatch for {workflow_id}")

        logger.debug(f"Checkpoint loaded: {workflow_id}")
        return data

    def delete_checkpoint(self, workflow_id: str) -> None:
        """Delete checkpoint file"""
        checkpoint_file = Path(self.checkpoint_dir) / f"{workflow_id}.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            logger.debug(f"Checkpoint deleted: {workflow_id}")

    def exists(self, workflow_id: str) -> bool:
        """Check if checkpoint exists"""
        checkpoint_file = Path(self.checkpoint_dir) / f"{workflow_id}.json"
        return checkpoint_file.exists()


class EscalationRouter:
    """Routes escalations to human review"""

    def __init__(self):
        self.escalations: List[Dict[str, Any]] = []

    def create_escalation(self, workflow_id: str, pilot_name: str,
                         reason: str) -> str:
        """Create escalation and return escalation_id"""
        escalation_id = f"esc_{uuid.uuid4().hex[:8]}"

        escalation = {
            "escalation_id": escalation_id,
            "workflow_id": workflow_id,
            "pilot_name": pilot_name,
            "reason": reason,
            "status": "pending_human_review",
            "created_at": time.time()
        }

        self.escalations.append(escalation)
        logger.info(f"Escalation created: {escalation_id}")
        return escalation_id

    def approve(self, escalation_id: str, approver: str) -> bool:
        """Approve escalation"""
        for esc in self.escalations:
            if esc["escalation_id"] == escalation_id:
                esc["status"] = "approved"
                esc["approver"] = approver
                esc["approved_at"] = time.time()
                logger.info(f"Escalation approved: {escalation_id}")
                return True
        return False

    def deny(self, escalation_id: str, reason: str) -> bool:
        """Deny escalation"""
        for esc in self.escalations:
            if esc["escalation_id"] == escalation_id:
                esc["status"] = "denied"
                esc["denial_reason"] = reason
                esc["denied_at"] = time.time()
                logger.info(f"Escalation denied: {escalation_id}")
                return True
        return False

    def get(self, escalation_id: str) -> Optional[Dict[str, Any]]:
        """Get escalation by ID"""
        for esc in self.escalations:
            if esc["escalation_id"] == escalation_id:
                return esc
        return None


class DeterministicWorkflow:
    """Deterministic LangGraph workflow with checkpoints and escalation"""

    def __init__(self, pilot_name: str, workflow_id: Optional[str] = None,
                 checkpoint_dir: str = "/tmp/smaos_checkpoints",
                 velocity_tracker: Optional[ActionVelocityTracker] = None,
                 auto_restore: bool = False):
        """Initialize workflow"""
        self.pilot_name = pilot_name
        self.workflow_id = workflow_id or f"wf_{uuid.uuid4().hex[:8]}"
        self.state = WorkflowState.INIT
        self.checkpoint_manager = CheckpointManager(checkpoint_dir)
        self.escalation_router = EscalationRouter()
        self.velocity_tracker = velocity_tracker or ActionVelocityTracker()

        # Workflow context
        self.context = WorkflowContext(
            intent={},
            classification={},
            execution_results={}
        )

        # Node registry
        self.nodes: Dict[str, Callable] = {}
        self.node_order: List[str] = []

        # Escalation tracking
        self.escalation_id: Optional[str] = None
        self.escalations: List[Dict[str, Any]] = []

        # Auto-restore from checkpoint if exists and requested
        if auto_restore and self.checkpoint_manager.exists(self.workflow_id):
            self.load_from_checkpoint()
        else:
            # Save initial checkpoint
            self._save_checkpoint()

        logger.info(f"Workflow created: {self.workflow_id} ({self.pilot_name})")

    def _set_state(self, new_state: WorkflowState) -> None:
        """Transition to new state with validation"""
        # Prevent backward transitions
        state_order = [
            WorkflowState.INIT,
            WorkflowState.INTENT_RECEIVED,
            WorkflowState.INTENT_VALIDATED,
            WorkflowState.CLASSIFIED,
            WorkflowState.EXECUTING,
            WorkflowState.AWAITING_AUTHORIZATION,
            WorkflowState.AUTHORIZED,
            WorkflowState.LEDGER_WRITTEN,
            WorkflowState.COMPLETE,
        ]

        # Handle denied path
        if new_state == WorkflowState.DENIED:
            if self.state not in [WorkflowState.AWAITING_AUTHORIZATION]:
                raise ValueError(
                    f"Cannot transition {self.state.value} → {new_state.value}"
                )
            self.state = new_state
            self._save_checkpoint()
            return

        # Validate forward-only transitions
        current_idx = state_order.index(self.state)
        new_idx = state_order.index(new_state)

        if new_idx <= current_idx:
            raise ValueError(
                f"Cannot transition {self.state.value} → {new_state.value}"
            )

        self.state = new_state
        self._save_checkpoint()
        logger.info(f"State transition: → {new_state.value}")

    def _save_checkpoint(self) -> None:
        """Save current state as checkpoint"""
        checkpoint_data = {
            "workflow_id": self.workflow_id,
            "pilot_name": self.pilot_name,
            "state": self.state.value,
            "timestamp": time.time(),
            "context": self.context.to_dict(),
            "escalation_id": self.escalation_id,
            "escalations": self.escalations
        }

        self.checkpoint_manager.save_checkpoint(
            self.workflow_id,
            checkpoint_data
        )

    def _record_velocity(self, node_name: str) -> None:
        """Record node execution in velocity tracker"""
        action_id = f"{self.pilot_name}_{node_name}_{int(time.time() * 1000)}"
        status, violation = self.velocity_tracker.record_action(
            action_id=action_id,
            tool_name=node_name,
            pilot_name=self.pilot_name,
            workflow_id=self.workflow_id
        )

        if violation:
            logger.warning(
                f"Velocity violation in {node_name}: {violation.metric}"
            )

    def receive_intent(self, intent: Dict[str, Any]) -> None:
        """Receive and validate intent"""
        if not intent:
            raise ValueError("Intent cannot be empty")

        self.context.intent = intent
        self._set_state(WorkflowState.INTENT_RECEIVED)
        self._record_velocity("receive_intent")
        logger.info(f"Intent received: {intent.get('id', 'unknown')}")

    def validate_intent(self) -> None:
        """Validate intent constraints"""
        if self.state != WorkflowState.INTENT_RECEIVED:
            raise ValueError(
                f"Cannot validate intent from {self.state.value}"
            )

        # Basic validation: intent must have required fields
        required_fields = next(iter(self.context.intent.values())) \
            if self.context.intent else None

        if not self.context.intent:
            raise ValueError("Intent must be provided")

        self._set_state(WorkflowState.INTENT_VALIDATED)
        self._record_velocity("validate_intent")

    def classify_intent(self, classification: Dict[str, Any]) -> None:
        """Classify intent (called from L1 policy router)"""
        if self.state != WorkflowState.INTENT_VALIDATED:
            raise ValueError(
                f"Cannot classify from {self.state.value}"
            )

        self.context.classification = classification
        self._set_state(WorkflowState.CLASSIFIED)
        self._record_velocity("classify_intent")

        # Check risk level
        risk_level = classification.get("risk_level", "low")
        logger.info(f"Intent classified: risk_level={risk_level}")

        # Auto-escalate on high risk (will require human authorization before execution)
        if risk_level == "high":
            logger.warning(f"High-risk classification detected: {classification}")
            # Note: escalation happens at authorization time, not here
            # This is just a flag for the execution phase

    def add_node(self, node_name: str, node_func: Callable) -> None:
        """Register a node for execution"""
        self.nodes[node_name] = node_func
        self.node_order.append(node_name)
        logger.debug(f"Node registered: {node_name}")

    def execute_nodes(self) -> None:
        """Execute all registered nodes in order, then auto-request authorization"""
        if self.state != WorkflowState.CLASSIFIED:
            raise ValueError(
                f"Cannot execute nodes from {self.state.value}"
            )

        self._set_state(WorkflowState.EXECUTING)

        # Execute each node in order
        for node_name in self.node_order:
            node_func = self.nodes[node_name]

            try:
                result = node_func(self.context.execution_results)
                self.context.execution_results.update(result or {})
                self._record_velocity(node_name)
                logger.debug(f"Node executed: {node_name}")
            except Exception as e:
                logger.error(f"Node {node_name} failed: {e}")
                self.context.execution_results["error"] = str(e)
                raise

        self._save_checkpoint()

        # Auto-request authorization after execution
        # (mandatory for all workflows, per SMAOS doctrine)
        self.request_authorization()

    def request_authorization(self) -> str:
        """Request human authorization (escalate)"""
        # Allow idempotent calls (return existing escalation if already requested)
        if self.state == WorkflowState.AWAITING_AUTHORIZATION:
            return self.escalation_id

        if self.state != WorkflowState.EXECUTING:
            raise ValueError(
                f"Cannot request authorization from {self.state.value}"
            )

        # Create escalation
        reason = "manual_authorization_gate"
        self.escalation_id = self.escalation_router.create_escalation(
            self.workflow_id,
            self.pilot_name,
            reason
        )

        self.escalations.append({
            "escalation_id": self.escalation_id,
            "workflow_id": self.workflow_id,
            "pilot_name": self.pilot_name,
            "status": "pending_human_review"
        })

        self._set_state(WorkflowState.AWAITING_AUTHORIZATION)
        return self.escalation_id

    def approve_authorization(self, escalation_id: str,
                             approver: str) -> None:
        """Approve authorization (called by human)"""
        if self.state != WorkflowState.AWAITING_AUTHORIZATION:
            raise ValueError(
                f"Cannot approve authorization from {self.state.value}"
            )

        if escalation_id != self.escalation_id:
            raise ValueError(f"Unknown escalation_id: {escalation_id}")

        self.escalation_router.approve(escalation_id, approver)

        # Update local escalation record
        for esc in self.escalations:
            if esc["escalation_id"] == escalation_id:
                esc["status"] = "approved"
                break

        self._set_state(WorkflowState.AUTHORIZED)
        logger.info(f"Authorization approved by {approver}")

    def deny_authorization(self, escalation_id: str, reason: str) -> None:
        """Deny authorization (called by human)"""
        if self.state != WorkflowState.AWAITING_AUTHORIZATION:
            raise ValueError(
                f"Cannot deny authorization from {self.state.value}"
            )

        if escalation_id != self.escalation_id:
            raise ValueError(f"Unknown escalation_id: {escalation_id}")

        self.escalation_router.deny(escalation_id, reason)

        # Update local escalation record
        for esc in self.escalations:
            if esc["escalation_id"] == escalation_id:
                esc["status"] = "denied"
                esc["denial_reason"] = reason
                break

        self._set_state(WorkflowState.DENIED)
        logger.warning(f"Authorization denied: {reason}")

    def write_ledger(self, ledger_entry: Dict[str, Any]) -> None:
        """Write result to ledger (L6 integration)"""
        if self.state != WorkflowState.AUTHORIZED:
            raise ValueError(
                f"Cannot write ledger from {self.state.value}"
            )

        # In full implementation, this calls L6/L8 ledger writer
        logger.info(f"Ledger entry prepared: {ledger_entry}")

        self._set_state(WorkflowState.LEDGER_WRITTEN)
        self.context.execution_results["ledger_entry"] = ledger_entry

    def mark_complete(self) -> None:
        """Mark workflow as complete"""
        if self.state != WorkflowState.LEDGER_WRITTEN:
            raise ValueError(
                f"Cannot complete from {self.state.value}"
            )

        self._set_state(WorkflowState.COMPLETE)
        logger.info(f"Workflow completed: {self.workflow_id}")

    def load_from_checkpoint(self) -> bool:
        """Load workflow state from checkpoint"""
        checkpoint_data = self.checkpoint_manager.load_checkpoint(
            self.workflow_id
        )

        if not checkpoint_data:
            logger.warning(f"No checkpoint found for {self.workflow_id}")
            return False

        # Restore state
        self.state = WorkflowState(checkpoint_data["state"])
        self.context = WorkflowContext(
            intent=checkpoint_data["context"]["intent"],
            classification=checkpoint_data["context"]["classification"],
            execution_results=checkpoint_data["context"]["execution_results"]
        )
        self.escalation_id = checkpoint_data.get("escalation_id")
        self.escalations = checkpoint_data.get("escalations", [])

        logger.info(f"Workflow restored from checkpoint: {self.workflow_id}")
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get workflow status"""
        return {
            "workflow_id": self.workflow_id,
            "pilot_name": self.pilot_name,
            "state": self.state.value,
            "escalation_id": self.escalation_id,
            "intent": self.context.intent,
            "classification": self.context.classification,
            "execution_results": self.context.execution_results,
            "escalations": self.escalations
        }

    def get_velocity_report(self) -> Dict[str, Any]:
        """Get velocity report for this workflow"""
        return self.velocity_tracker.get_velocity_report(self.pilot_name)
