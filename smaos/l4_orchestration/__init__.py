"""L4 Orchestration Layer: LangGraph Orchestration with NIST Compliance

Provides:
  - ActionVelocityTracker: Runaway agent detection via invocation velocity tracking
  - Per-pilot thresholds (Hotel, Glass, School)
  - Fail-closed escalation to human review
  - JSON audit logging for compliance

Example:
    from smaos.l4_orchestration import ActionVelocityTracker

    tracker = ActionVelocityTracker()
    status, violation = tracker.record_action(
        action_id="a1", tool_name="score_credit", pilot_name="hotel",
        workflow_id="wf_001"
    )
    if violation:
        escalations = tracker.get_escalations_pending_review()
"""

from .action_velocity import (
    ActionVelocityTracker,
    VelocityThreshold,
    ActionRecord,
    VelocityViolation,
    ViolationSeverity,
    ActionVelocityStatus,
)

__all__ = [
    "ActionVelocityTracker",
    "VelocityThreshold",
    "ActionRecord",
    "VelocityViolation",
    "ViolationSeverity",
    "ActionVelocityStatus",
]
