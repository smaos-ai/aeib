"""Action Velocity Tracker: NIST Agentic Profile Runaway Detection (L4 Orchestration)

Tracks tool invocation velocity per time window to detect and prevent runaway agents.
Implements fail-closed escalation to human review when thresholds exceeded.

Per-pilot thresholds:
  - Hotel: 10/minute, 100/workflow
  - Glass: 15/minute, 200/workflow
  - School: 8/minute, 80/workflow

Complies with NIST agentic profile AI RMF Section 3.2 (Runaway Detection).
"""

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class ViolationSeverity(Enum):
    """Escalation severity levels"""
    WARNING = "warning"
    CRITICAL = "critical"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class ActionVelocityStatus(Enum):
    """Velocity check status"""
    OK = "ok"
    WARNING = "warning"
    VIOLATION = "violation"
    ESCALATED = "escalated"


@dataclass
class VelocityThreshold:
    """Per-pilot velocity thresholds"""
    pilot_name: str
    max_invocations_per_minute: int
    max_invocations_per_workflow: int
    escalation_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActionRecord:
    """Single action invocation record"""
    action_id: str
    tool_name: str
    pilot_name: str
    workflow_id: str
    timestamp: float
    duration_ms: Optional[float] = None
    status: str = "pending"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VelocityViolation:
    """Velocity violation record"""
    violation_id: str
    pilot_name: str
    workflow_id: str
    metric: str  # "per_minute" or "per_workflow"
    threshold: int
    actual_count: int
    timestamp: float
    severity: ViolationSeverity
    escalated: bool = False
    human_action: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['severity'] = self.severity.value
        return data


class ActionVelocityTracker:
    """Fail-closed velocity tracker for NIST agentic profile compliance"""

    def __init__(self, thresholds: Optional[Dict[str, VelocityThreshold]] = None,
                 audit_log_path: Optional[str] = None):
        """
        Initialize velocity tracker.

        Args:
            thresholds: Dict of pilot_name -> VelocityThreshold
            audit_log_path: Optional path for JSON audit log
        """
        self.thresholds = thresholds or self._default_thresholds()
        self.audit_log_path = audit_log_path

        # Track actions per pilot
        self.action_history: Dict[str, deque] = {
            pilot: deque(maxlen=1000) for pilot in self.thresholds.keys()
        }

        # Track violations
        self.violations: List[VelocityViolation] = []

        # Track escalations requiring human intervention
        self.escalations: List[Dict[str, Any]] = []

        # Lock to track escalations in current window
        self._escalation_lock: Dict[str, bool] = {}

        logger.info(f"Initialized ActionVelocityTracker with {len(self.thresholds)} pilots")

    @staticmethod
    def _default_thresholds() -> Dict[str, VelocityThreshold]:
        """Default NIST agentic profile thresholds"""
        return {
            "hotel": VelocityThreshold(
                pilot_name="hotel",
                max_invocations_per_minute=10,
                max_invocations_per_workflow=100
            ),
            "glass": VelocityThreshold(
                pilot_name="glass",
                max_invocations_per_minute=15,
                max_invocations_per_workflow=200
            ),
            "school": VelocityThreshold(
                pilot_name="school",
                max_invocations_per_minute=8,
                max_invocations_per_workflow=80
            ),
        }

    def record_action(self, action_id: str, tool_name: str, pilot_name: str,
                     workflow_id: str, duration_ms: Optional[float] = None,
                     status: str = "pending") -> Tuple[ActionVelocityStatus, Optional[VelocityViolation]]:
        """
        Record a tool invocation and check velocity.

        Returns:
            (status, violation) - status is OK/WARNING/VIOLATION/ESCALATED
        """
        if pilot_name not in self.thresholds:
            logger.warning(f"Unknown pilot: {pilot_name}")
            return ActionVelocityStatus.WARNING, None

        now = time.time()
        record = ActionRecord(
            action_id=action_id,
            tool_name=tool_name,
            pilot_name=pilot_name,
            workflow_id=workflow_id,
            timestamp=now,
            duration_ms=duration_ms,
            status=status
        )

        # Add to history
        self.action_history[pilot_name].append(record)

        # Check thresholds
        violation = self._check_velocity_thresholds(pilot_name, workflow_id, now)

        if violation:
            self.violations.append(violation)
            self._log_audit_event("velocity_violation", record.to_dict(), violation.to_dict())

            if violation.severity == ViolationSeverity.ESCALATE_TO_HUMAN:
                self._escalate_to_human(violation)
                return ActionVelocityStatus.ESCALATED, violation
            elif violation.severity == ViolationSeverity.CRITICAL:
                return ActionVelocityStatus.VIOLATION, violation
            else:
                return ActionVelocityStatus.WARNING, violation

        self._log_audit_event("action_recorded", record.to_dict())
        return ActionVelocityStatus.OK, None

    def _check_velocity_thresholds(self, pilot_name: str, workflow_id: str,
                                   now: float) -> Optional[VelocityViolation]:
        """
        Check per-minute and per-workflow thresholds.
        Returns violation if exceeded, None otherwise.
        """
        threshold = self.thresholds[pilot_name]
        history = self.action_history[pilot_name]

        # Check per-minute threshold
        one_minute_ago = now - 60.0
        recent_actions = [
            a for a in history if a.timestamp >= one_minute_ago
        ]

        if len(recent_actions) > threshold.max_invocations_per_minute:
            severity = ViolationSeverity.ESCALATE_TO_HUMAN if threshold.escalation_enabled else ViolationSeverity.CRITICAL
            violation = VelocityViolation(
                violation_id=f"v_{pilot_name}_{int(now * 1000)}_minute",
                pilot_name=pilot_name,
                workflow_id=workflow_id,
                metric="per_minute",
                threshold=threshold.max_invocations_per_minute,
                actual_count=len(recent_actions),
                timestamp=now,
                severity=severity
            )
            logger.error(
                f"VELOCITY VIOLATION: {pilot_name} exceeded per-minute threshold "
                f"({len(recent_actions)} > {threshold.max_invocations_per_minute})"
            )
            return violation

        # Check per-workflow threshold
        workflow_actions = [
            a for a in history if a.workflow_id == workflow_id
        ]

        if len(workflow_actions) > threshold.max_invocations_per_workflow:
            severity = ViolationSeverity.ESCALATE_TO_HUMAN if threshold.escalation_enabled else ViolationSeverity.CRITICAL
            violation = VelocityViolation(
                violation_id=f"v_{pilot_name}_{workflow_id}_{int(now * 1000)}_workflow",
                pilot_name=pilot_name,
                workflow_id=workflow_id,
                metric="per_workflow",
                threshold=threshold.max_invocations_per_workflow,
                actual_count=len(workflow_actions),
                timestamp=now,
                severity=severity
            )
            logger.error(
                f"VELOCITY VIOLATION: {pilot_name} workflow {workflow_id} exceeded "
                f"per-workflow threshold ({len(workflow_actions)} > {threshold.max_invocations_per_workflow})"
            )
            return violation

        return None

    def _escalate_to_human(self, violation: VelocityViolation) -> None:
        """Escalate violation to human review (fail-closed)"""
        escalation = {
            "escalation_id": f"esc_{violation.violation_id}",
            "violation_id": violation.violation_id,
            "pilot_name": violation.pilot_name,
            "workflow_id": violation.workflow_id,
            "metric": violation.metric,
            "threshold": violation.threshold,
            "actual_count": violation.actual_count,
            "timestamp": violation.timestamp,
            "status": "pending_human_review",
            "action_required": f"Review velocity spike in {violation.pilot_name} - {violation.metric} threshold exceeded"
        }

        self.escalations.append(escalation)
        violation.escalated = True

        self._log_audit_event("escalation_triggered", escalation)
        logger.critical(f"ESCALATED TO HUMAN: {escalation['escalation_id']}")

    def approve_escalation(self, escalation_id: str, reason: str) -> bool:
        """Human approval of escalated violation"""
        for escalation in self.escalations:
            if escalation['escalation_id'] == escalation_id:
                escalation['status'] = 'approved'
                escalation['human_action'] = reason
                escalation['approved_at'] = time.time()
                self._log_audit_event("escalation_approved", escalation)
                logger.info(f"Escalation approved: {escalation_id} - {reason}")
                return True
        return False

    def deny_escalation(self, escalation_id: str, reason: str) -> bool:
        """Human denial of escalated violation - blocks workflow"""
        for escalation in self.escalations:
            if escalation['escalation_id'] == escalation_id:
                escalation['status'] = 'denied'
                escalation['human_action'] = reason
                escalation['denied_at'] = time.time()
                self._log_audit_event("escalation_denied", escalation)
                logger.warning(f"Escalation denied: {escalation_id} - {reason}")
                return True
        return False

    def get_velocity_report(self, pilot_name: str,
                           time_window_seconds: int = 300) -> Dict[str, Any]:
        """Generate velocity report for a pilot"""
        if pilot_name not in self.thresholds:
            return {"error": f"Unknown pilot: {pilot_name}"}

        now = time.time()
        window_start = now - time_window_seconds

        history = self.action_history[pilot_name]
        recent_actions = [a for a in history if a.timestamp >= window_start]

        threshold = self.thresholds[pilot_name]

        # Calculate per-minute rate
        one_minute_ago = now - 60.0
        per_minute_actions = [a for a in history if a.timestamp >= one_minute_ago]

        return {
            "pilot_name": pilot_name,
            "time_window_seconds": time_window_seconds,
            "total_actions_in_window": len(recent_actions),
            "per_minute_actions": len(per_minute_actions),
            "per_minute_threshold": threshold.max_invocations_per_minute,
            "per_minute_violation": len(per_minute_actions) > threshold.max_invocations_per_minute,
            "total_violations": len([v for v in self.violations if v.pilot_name == pilot_name]),
            "pending_escalations": len([e for e in self.escalations if e['pilot_name'] == pilot_name and e['status'] == 'pending_human_review']),
            "recent_actions": [a.to_dict() for a in recent_actions[-10:]]
        }

    def _log_audit_event(self, event_type: str, *args) -> None:
        """Log event to audit trail"""
        if not self.audit_log_path:
            return

        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": args if len(args) > 1 else (args[0] if args else {})
        }

        try:
            with open(self.audit_log_path, 'a') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def get_escalations_pending_review(self) -> List[Dict[str, Any]]:
        """Get all pending escalations"""
        return [e for e in self.escalations if e['status'] == 'pending_human_review']

    def clear_history(self, pilot_name: Optional[str] = None) -> None:
        """Clear action history (for testing)"""
        if pilot_name:
            self.action_history[pilot_name].clear()
        else:
            for pilot in self.action_history:
                self.action_history[pilot].clear()

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall velocity statistics"""
        total_actions = sum(len(h) for h in self.action_history.values())
        total_violations = len(self.violations)
        pending_escalations = len(self.get_escalations_pending_review())

        return {
            "total_actions_tracked": total_actions,
            "total_violations": total_violations,
            "pending_escalations": pending_escalations,
            "pilots_configured": list(self.thresholds.keys()),
            "thresholds": {
                name: threshold.to_dict()
                for name, threshold in self.thresholds.items()
            }
        }
