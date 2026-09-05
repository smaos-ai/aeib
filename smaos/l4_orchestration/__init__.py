"""L4 Orchestration Layer: Deterministic State Machine + Velocity Tracking + NIST Compliance

Provides:
  - DeterministicWorkflow: Formal state machine (INIT → COMPLETE)
  - CheckpointManager: Fault tolerance with integrity hashing
  - EscalationRouter: Human authorization gates (fail-closed)
  - ActionVelocityTracker: Runaway agent detection via invocation velocity tracking
  - L4WorkflowOrchestrator: High-level orchestration API for pilots

Example:
    from smaos.l4_orchestration import L4WorkflowOrchestrator

    orchestrator = L4WorkflowOrchestrator(pilot_name="hotel")
    result = orchestrator.execute_intent(
        intent={"guest_id": "g_001"},
        classification={"risk_level": "low"},
        nodes=[("fetch_pms", tool_func)],
        approver="John Doe"
    )
"""

from .action_velocity import (
    ActionVelocityTracker,
    VelocityThreshold,
    ActionRecord,
    VelocityViolation,
    ViolationSeverity,
    ActionVelocityStatus,
)

from .deterministic_state_machine import (
    DeterministicWorkflow,
    WorkflowState,
    WorkflowContext,
    CheckpointManager,
    EscalationRouter,
)

from .l4_langgraph_integration import L4WorkflowOrchestrator

__all__ = [
    # Velocity tracking
    "ActionVelocityTracker",
    "VelocityThreshold",
    "ActionRecord",
    "VelocityViolation",
    "ViolationSeverity",
    "ActionVelocityStatus",
    # Deterministic state machine
    "DeterministicWorkflow",
    "WorkflowState",
    "WorkflowContext",
    "CheckpointManager",
    "EscalationRouter",
    # High-level orchestration
    "L4WorkflowOrchestrator",
]
