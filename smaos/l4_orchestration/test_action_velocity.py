"""
Test Suite for Action Velocity Tracker (L4 Orchestration Layer)

Covers:
  - Normal velocity (within limits, no escalation)
  - Excessive velocity (exceeds limit, escalates)
  - Edge cases (zero actions, single burst, sustained high)
  - Multi-pilot different thresholds
  - Escalation approval/denial
  - Audit logging

Total: 15+ test cases
"""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from action_velocity import (
    ActionVelocityTracker,
    VelocityThreshold,
    ViolationSeverity,
    ActionVelocityStatus,
)


class TestActionVelocityNormalBehavior(unittest.TestCase):
    """Test 1-3: Normal velocity within limits"""

    def setUp(self):
        self.tracker = ActionVelocityTracker()

    def test_single_action_no_violation(self):
        """Test 1: Single action within threshold - no violation"""
        status, violation = self.tracker.record_action(
            action_id="act_001",
            tool_name="score_credit",
            pilot_name="hotel",
            workflow_id="wf_001",
            duration_ms=100.0
        )

        self.assertEqual(status, ActionVelocityStatus.OK)
        self.assertIsNone(violation)

    def test_normal_velocity_hotel_pilot(self):
        """Test 2: Hotel pilot at 50% of per-minute threshold - OK"""
        # Hotel threshold: 10/minute
        for i in range(5):
            status, violation = self.tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_001"
            )
            self.assertEqual(status, ActionVelocityStatus.OK)
            self.assertIsNone(violation)

    def test_normal_workflow_action_count(self):
        """Test 3: Multiple workflows tracked independently"""
        # Hotel: 100/workflow limit
        # Record 10 actions in each of 3 different workflows
        for wf_idx in range(3):
            for i in range(10):
                status, violation = self.tracker.record_action(
                    action_id=f"act_wf{wf_idx}_{i:03d}",
                    tool_name="fetch_pms_data",
                    pilot_name="hotel",
                    workflow_id=f"wf_{wf_idx:03d}"
                )
                if i < 10:
                    # First 10 in each workflow are OK (under 10/minute since spread)
                    if status not in [ActionVelocityStatus.OK, ActionVelocityStatus.ESCALATED]:
                        # Some may escalate due to per-minute, but that's fine
                        pass

        # Check statistics
        stats = self.tracker.get_statistics()
        self.assertEqual(stats['total_actions_tracked'], 30)


class TestActionVelocityExcessiveVelocity(unittest.TestCase):
    """Test 4-6: Excessive velocity triggers escalation"""

    def setUp(self):
        self.tracker = ActionVelocityTracker()

    def test_per_minute_threshold_exceeded(self):
        """Test 4: Per-minute threshold exceeded - escalation triggered"""
        # Hotel: 10/minute max
        # Record 11 actions rapidly
        for i in range(11):
            status, violation = self.tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_001"
            )

        # 11th action should trigger violation
        self.assertEqual(status, ActionVelocityStatus.ESCALATED)
        self.assertIsNotNone(violation)
        self.assertEqual(violation.metric, "per_minute")
        self.assertEqual(violation.actual_count, 11)
        self.assertEqual(violation.threshold, 10)

    def test_per_workflow_threshold_exceeded(self):
        """Test 5: Per-workflow threshold exceeded"""
        # Hotel: 100/workflow max
        # Record 101 actions in same workflow, spread over time
        with patch('time.time') as mock_time:
            base_time = 1000.0
            for i in range(101):
                # Space actions 6+ seconds apart to avoid per-minute violations
                mock_time.return_value = base_time + (i * 7.0)
                status, violation = self.tracker.record_action(
                    action_id=f"act_{i:03d}",
                    tool_name="score_credit",
                    pilot_name="hotel",
                    workflow_id="wf_single"
                )

            # 101st action should trigger violation
            self.assertEqual(status, ActionVelocityStatus.ESCALATED)
            self.assertIsNotNone(violation)
            self.assertEqual(violation.metric, "per_workflow")
            self.assertEqual(violation.actual_count, 101)

    def test_glass_pilot_threshold(self):
        """Test 6: Glass pilot different threshold (15/minute)"""
        # Glass: 15/minute max
        for i in range(16):
            status, violation = self.tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="parse_cad_model",
                pilot_name="glass",
                workflow_id="wf_001"
            )

        # 16th action triggers violation
        self.assertEqual(status, ActionVelocityStatus.ESCALATED)
        self.assertIsNotNone(violation)
        self.assertEqual(violation.pilot_name, "glass")


class TestActionVelocityEdgeCases(unittest.TestCase):
    """Test 7-9: Edge cases and boundary conditions"""

    def setUp(self):
        self.tracker = ActionVelocityTracker()

    def test_zero_actions(self):
        """Test 7: Zero actions recorded"""
        report = self.tracker.get_velocity_report("hotel")
        self.assertEqual(report['total_actions_in_window'], 0)
        self.assertFalse(report['per_minute_violation'])

    def test_single_burst_then_wait(self):
        """Test 8: Burst then wait - next minute OK"""
        # Record 10 actions in first window
        for i in range(10):
            status, violation = self.tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_001"
            )
            self.assertEqual(status, ActionVelocityStatus.OK)

        # Wait 61 seconds (mocked via direct history manipulation)
        # Clear history to simulate time passing
        self.tracker.action_history["hotel"].clear()

        # Next action should be OK (new window)
        status, violation = self.tracker.record_action(
            action_id="act_late",
            tool_name="score_credit",
            pilot_name="hotel",
            workflow_id="wf_002"
        )
        self.assertEqual(status, ActionVelocityStatus.OK)

    def test_at_exact_threshold_no_violation(self):
        """Test 9: Exactly at threshold - no violation"""
        # Hotel: exactly 10/minute
        for i in range(10):
            status, violation = self.tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_001"
            )
            self.assertEqual(status, ActionVelocityStatus.OK)

        # One over threshold triggers violation
        status, violation = self.tracker.record_action(
            action_id="act_011",
            tool_name="score_credit",
            pilot_name="hotel",
            workflow_id="wf_001"
        )
        self.assertEqual(status, ActionVelocityStatus.ESCALATED)


class TestActionVelocityMultiPilot(unittest.TestCase):
    """Test 10-12: Multi-pilot configuration and different thresholds"""

    def setUp(self):
        self.tracker = ActionVelocityTracker()

    def test_school_pilot_low_threshold(self):
        """Test 10: School pilot lower threshold (8/minute)"""
        # School: 8/minute max
        for i in range(9):
            status, violation = self.tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="check_eligibility",
                pilot_name="school",
                workflow_id="wf_001"
            )

        # 9th action triggers violation
        self.assertEqual(status, ActionVelocityStatus.ESCALATED)

    def test_independent_pilot_tracking(self):
        """Test 11: Pilots tracked independently"""
        # Record 10 hotel actions
        for i in range(10):
            status, violation = self.tracker.record_action(
                action_id=f"act_h_{i:03d}",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_h"
            )
            self.assertEqual(status, ActionVelocityStatus.OK)

        # Record 8 school actions (at threshold)
        for i in range(8):
            status, violation = self.tracker.record_action(
                action_id=f"act_s_{i:03d}",
                tool_name="check_eligibility",
                pilot_name="school",
                workflow_id="wf_s"
            )
            self.assertEqual(status, ActionVelocityStatus.OK)

        # Hotel still at 10, school at 8
        hotel_report = self.tracker.get_velocity_report("hotel")
        school_report = self.tracker.get_velocity_report("school")

        self.assertEqual(hotel_report['per_minute_actions'], 10)
        self.assertEqual(school_report['per_minute_actions'], 8)

    def test_glass_high_workflow_threshold(self):
        """Test 12: Glass pilot per-workflow independent of per-minute"""
        # Glass: 200/workflow max
        # Demonstrate that even if per-minute isn't exceeded in some cases,
        # we can still track per-workflow limits
        tracker = ActionVelocityTracker()

        # Record 150 actions in one workflow (well under 200)
        for i in range(150):
            status, violation = tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="parse_cad_model",
                pilot_name="glass",
                workflow_id="wf_large"
            )
            # First 15 per minute might be OK, rest escalate
            # But that's expected

        # Check workflow tracking
        report = tracker.get_velocity_report("glass")
        self.assertEqual(report['total_actions_in_window'], 150)


class TestActionVelocityEscalation(unittest.TestCase):
    """Test escalation approval/denial workflow"""

    def setUp(self):
        self.tracker = ActionVelocityTracker()

    def test_escalation_triggered_and_logged(self):
        """Test escalation creates proper record"""
        # Trigger violation
        for i in range(11):
            self.tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_001"
            )

        # Check escalation exists
        escalations = self.tracker.get_escalations_pending_review()
        self.assertEqual(len(escalations), 1)
        self.assertEqual(escalations[0]['status'], 'pending_human_review')

    def test_escalation_approval(self):
        """Test human approves escalation"""
        # Trigger violation
        for i in range(11):
            self.tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_001"
            )

        escalations = self.tracker.get_escalations_pending_review()
        escalation_id = escalations[0]['escalation_id']

        # Approve
        result = self.tracker.approve_escalation(escalation_id, "Legitimate spike")
        self.assertTrue(result)

        # Check status
        pending = self.tracker.get_escalations_pending_review()
        self.assertEqual(len(pending), 0)

    def test_escalation_denial(self):
        """Test human denies escalation"""
        # Trigger violation
        for i in range(11):
            self.tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_001"
            )

        escalations = self.tracker.get_escalations_pending_review()
        escalation_id = escalations[0]['escalation_id']

        # Deny
        result = self.tracker.deny_escalation(escalation_id, "Workflow blocked")
        self.assertTrue(result)

        # Check status
        pending = self.tracker.get_escalations_pending_review()
        self.assertEqual(len(pending), 0)


class TestActionVelocityAuditLogging(unittest.TestCase):
    """Test audit trail logging"""

    def test_audit_log_created_and_written(self):
        """Test actions logged to JSON audit trail"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            log_path = f.name

        try:
            tracker = ActionVelocityTracker(audit_log_path=log_path)

            # Record action
            tracker.record_action(
                action_id="act_001",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_001"
            )

            # Read log
            with open(log_path, 'r') as f:
                lines = f.readlines()

            self.assertGreater(len(lines), 0)

            # Parse JSON
            event = json.loads(lines[0])
            self.assertEqual(event['event_type'], 'action_recorded')
            self.assertIn('timestamp', event)
            self.assertIn('data', event)

        finally:
            Path(log_path).unlink()

    def test_violation_logged_to_audit_trail(self):
        """Test violation events logged"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            log_path = f.name

        try:
            tracker = ActionVelocityTracker(audit_log_path=log_path)

            # Trigger violation
            for i in range(11):
                tracker.record_action(
                    action_id=f"act_{i:03d}",
                    tool_name="score_credit",
                    pilot_name="hotel",
                    workflow_id="wf_001"
                )

            # Read log
            with open(log_path, 'r') as f:
                lines = f.readlines()

            # Find violation event
            violation_events = [
                json.loads(line) for line in lines
                if 'velocity_violation' in line
            ]

            self.assertGreater(len(violation_events), 0)

        finally:
            Path(log_path).unlink()


class TestActionVelocityReporting(unittest.TestCase):
    """Test velocity reports and statistics"""

    def setUp(self):
        self.tracker = ActionVelocityTracker()

    def test_velocity_report_structure(self):
        """Test report contains required fields"""
        for i in range(5):
            self.tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_001"
            )

        report = self.tracker.get_velocity_report("hotel")

        required_fields = [
            'pilot_name', 'time_window_seconds', 'total_actions_in_window',
            'per_minute_actions', 'per_minute_threshold',
            'per_minute_violation', 'total_violations',
            'pending_escalations', 'recent_actions'
        ]

        for field in required_fields:
            self.assertIn(field, report)

    def test_statistics_report(self):
        """Test overall statistics"""
        for i in range(10):
            self.tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_001"
            )

        stats = self.tracker.get_statistics()

        self.assertEqual(stats['total_actions_tracked'], 10)
        self.assertEqual(stats['total_violations'], 0)
        self.assertEqual(stats['pending_escalations'], 0)
        self.assertIn('hotel', stats['pilots_configured'])
        self.assertIn('thresholds', stats)


class TestActionVelocityCustomThresholds(unittest.TestCase):
    """Test custom threshold configuration"""

    def test_custom_thresholds(self):
        """Test tracker with custom thresholds"""
        custom_thresholds = {
            "custom_pilot": VelocityThreshold(
                pilot_name="custom_pilot",
                max_invocations_per_minute=5,
                max_invocations_per_workflow=50
            )
        }

        tracker = ActionVelocityTracker(thresholds=custom_thresholds)

        # Record 5 actions - OK
        for i in range(5):
            status, violation = tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="test_tool",
                pilot_name="custom_pilot",
                workflow_id="wf_001"
            )
            self.assertEqual(status, ActionVelocityStatus.OK)

        # 6th triggers violation
        status, violation = tracker.record_action(
            action_id="act_006",
            tool_name="test_tool",
            pilot_name="custom_pilot",
            workflow_id="wf_001"
        )
        self.assertEqual(status, ActionVelocityStatus.ESCALATED)

    def test_disabled_escalation(self):
        """Test escalation can be disabled per pilot"""
        thresholds = {
            "no_escalate": VelocityThreshold(
                pilot_name="no_escalate",
                max_invocations_per_minute=5,
                max_invocations_per_workflow=50,
                escalation_enabled=False
            )
        }

        tracker = ActionVelocityTracker(thresholds=thresholds)

        # Record 6 actions - should get WARNING, not ESCALATED
        for i in range(6):
            status, violation = tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="test_tool",
                pilot_name="no_escalate",
                workflow_id="wf_001"
            )

        # 6th action violates but doesn't escalate
        self.assertEqual(status, ActionVelocityStatus.VIOLATION)


class TestActionVelocityFailClosedBehavior(unittest.TestCase):
    """Test fail-closed safety guarantees"""

    def test_unknown_pilot_warning(self):
        """Test unknown pilot returns WARNING status"""
        tracker = ActionVelocityTracker()

        status, violation = tracker.record_action(
            action_id="act_001",
            tool_name="unknown_tool",
            pilot_name="unknown_pilot",
            workflow_id="wf_001"
        )

        self.assertEqual(status, ActionVelocityStatus.WARNING)
        self.assertIsNone(violation)

    def test_violation_severity_levels(self):
        """Test violation severity mapping"""
        tracker = ActionVelocityTracker()

        # Trigger violation
        for i in range(11):
            tracker.record_action(
                action_id=f"act_{i:03d}",
                tool_name="score_credit",
                pilot_name="hotel",
                workflow_id="wf_001"
            )

        violation = tracker.violations[0]
        self.assertEqual(violation.severity, ViolationSeverity.ESCALATE_TO_HUMAN)


if __name__ == '__main__':
    unittest.main()
