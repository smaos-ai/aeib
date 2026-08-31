#!/usr/bin/env python3
"""
actcheck_wrapper.py

Activity Checking wrapper for SMAOS governance layer.
Validates all decision actions against:
- Policy rules (L1 Reasoning)
- Permit gates (L3 gates)
- Escalation policies (L4 Orchestration)
- Audit trail integrity (L8 Proof Layer)

Used by: L7 RAGAS monitoring, incident detection, compliance audits.

Example:
    checker = ActivityChecker(config_file="policies.yaml")
    result = checker.check_decision({
        "pilot": "hotel_credit_scoring",
        "decision": "ESCALATE",
        "risk_score": 0.78,
        "human_reviewer": "alice@hotel.com",
    })
    if result.is_valid:
        print(f"Decision valid. Policy trace: {result.policy_trace}")
    else:
        print(f"Policy violation: {result.violations}")
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from enum import Enum


class DecisionAction(Enum):
    """Valid decision actions in SMAOS."""
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"
    DEFERRED = "DEFERRED"


class PilotDomain(Enum):
    """SMAOS pilot domains."""
    HOTEL_CREDIT = "hotel_credit_scoring"
    GLASS_SAFETY = "glass_manufacturing_safety"
    SCHOOL_ACCESS = "school_access_control"


@dataclass
class PolicyTrace:
    """Record of policy evaluation for single decision."""
    decision_id: str
    timestamp: str
    pilot: str
    action: str
    policy_rules_evaluated: List[str]
    permit_gates_passed: List[str]
    policy_violations: List[str]
    escalation_justified: bool
    human_review_required: bool
    approval_confidence: float


@dataclass
class ActivityCheckResult:
    """Result of activity check."""
    is_valid: bool
    decision_id: str
    pilot: str
    policy_trace: PolicyTrace
    violations: List[str]
    warnings: List[str]
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW


class ActivityChecker:
    """Validates decisions against SMAOS policy rules."""

    # Hotel Credit Scoring Rules
    HOTEL_RULES = {
        "auto_approve": {
            "conditions": [
                "credit_score >= 700",
                "risk_score < 0.2",
                "previous_cancellations <= 2",
                "no_fraud_flags",
            ],
            "action": "APPROVED",
            "escalation_required": False,
        },
        "escalation": {
            "conditions": [
                "credit_score >= 650 AND credit_score < 700",
                "risk_score >= 0.2 AND risk_score < 0.8",
                "fraud_flags_present",
                "previous_disputes > 0",
            ],
            "action": "ESCALATED",
            "escalation_required": True,
            "sla_hours": 2,
        },
        "denial": {
            "conditions": [
                "credit_score < 650",
                "risk_score >= 0.8",
                "active_fraud_case",
            ],
            "action": "DENIED",
            "escalation_required": True,  # Appealable
            "sla_hours": 24,
        },
    }

    # Glass Manufacturing Rules
    GLASS_RULES = {
        "auto_pass": {
            "conditions": [
                "defect_confidence < 0.01",
                "process_within_tolerance",
                "no_anomalies_detected",
            ],
            "action": "APPROVED",
            "escalation_required": False,
        },
        "escalation": {
            "conditions": [
                "defect_confidence >= 0.01 AND defect_confidence < 0.05",
                "anomalous_region_detected",
                "three_consecutive_borderline",
            ],
            "action": "ESCALATED",
            "escalation_required": True,
            "sla_minutes": 5,
        },
        "rejection": {
            "conditions": [
                "defect_confidence >= 0.05",
                "critical_defect",
                "safety_concern",
            ],
            "action": "DENIED",
            "escalation_required": True,
            "sla_minutes": 2,
        },
    }

    # School Access Rules (100% human review)
    SCHOOL_RULES = {
        "human_review_required": {
            "conditions": ["all_decisions"],
            "action": "ESCALATED",
            "escalation_required": True,
            "sla_minutes": 15,
        }
    }

    def __init__(self):
        self.rules = {
            PilotDomain.HOTEL_CREDIT.value: self.HOTEL_RULES,
            PilotDomain.GLASS_SAFETY.value: self.GLASS_RULES,
            PilotDomain.SCHOOL_ACCESS.value: self.SCHOOL_RULES,
        }
        self.violations = []
        self.warnings = []

    def check_decision(self, decision_data: Dict[str, Any]) -> ActivityCheckResult:
        """
        Validate a single decision against policy rules.

        Args:
            decision_data: {
                "decision_id": "uuid",
                "pilot": "hotel_credit_scoring|glass_manufacturing_safety|school_access_control",
                "action": "APPROVED|DENIED|ESCALATED|DEFERRED",
                "credit_score" (hotel): 0-900,
                "risk_score": 0.0-1.0,
                "human_reviewer": "name@domain" (if escalated),
                "override_reason": "..." (if diverges from policy)
            }

        Returns:
            ActivityCheckResult with policy_trace, violations, severity
        """
        self.violations = []
        self.warnings = []

        decision_id = decision_data.get("decision_id", "unknown")
        pilot = decision_data.get("pilot", "unknown")
        action = decision_data.get("action", "UNKNOWN")

        # Validate input
        if pilot not in self.rules:
            return ActivityCheckResult(
                is_valid=False,
                decision_id=decision_id,
                pilot=pilot,
                policy_trace=PolicyTrace(
                    decision_id=decision_id,
                    timestamp=datetime.now().isoformat(),
                    pilot=pilot,
                    action=action,
                    policy_rules_evaluated=[],
                    permit_gates_passed=[],
                    policy_violations=["Unknown pilot domain"],
                    escalation_justified=False,
                    human_review_required=False,
                    approval_confidence=0.0,
                ),
                violations=["Unknown pilot domain"],
                warnings=[],
                severity="CRITICAL",
            )

        # Evaluate pilot-specific rules
        if pilot == PilotDomain.HOTEL_CREDIT.value:
            return self._check_hotel_credit(decision_data)
        elif pilot == PilotDomain.GLASS_SAFETY.value:
            return self._check_glass_safety(decision_data)
        elif pilot == PilotDomain.SCHOOL_ACCESS.value:
            return self._check_school_access(decision_data)

    def _check_hotel_credit(self, decision: Dict[str, Any]) -> ActivityCheckResult:
        """Validate hotel credit decision."""
        decision_id = decision.get("decision_id", "unknown")
        action = decision.get("action", "UNKNOWN")
        violations = []
        warnings = []
        rules_evaluated = []
        gates_passed = []

        credit_score = decision.get("credit_score", 0)
        risk_score = decision.get("risk_score", 1.0)
        fraud_flags = decision.get("fraud_flags_present", False)
        disputes = decision.get("previous_disputes", 0)
        human_reviewer = decision.get("human_reviewer")

        # Rule 1: Auto-Approve
        if (credit_score >= 700 and risk_score < 0.2 and not fraud_flags and disputes == 0):
            rules_evaluated.append("auto_approve")
            gates_passed.append("credit_score_threshold")
            gates_passed.append("risk_score_threshold")
            gates_passed.append("no_fraud_flags")

            if action != "APPROVED":
                violations.append(
                    f"Policy rule 'auto_approve' met but action was {action} (expected APPROVED)"
                )

        # Rule 2: Escalation
        elif (650 <= credit_score < 700) or (0.2 <= risk_score < 0.8) or fraud_flags or disputes > 0:
            rules_evaluated.append("escalation")

            if not human_reviewer:
                violations.append("Escalation rule triggered but no human_reviewer assigned")
            else:
                gates_passed.append("human_reviewer_assigned")

            if action != "ESCALATED":
                violations.append(
                    f"Escalation rule met but action was {action} (expected ESCALATED)"
                )

        # Rule 3: Denial
        elif credit_score < 650 or risk_score >= 0.8:
            rules_evaluated.append("denial")

            if not human_reviewer:
                warnings.append("Denial without human review opportunity (appeal required)")
            else:
                gates_passed.append("human_reviewer_notified")

            if action != "DENIED":
                violations.append(f"Denial rule met but action was {action} (expected DENIED)")

        # Determine escalation justification
        escalation_justified = bool(human_reviewer) and action == "ESCALATED"

        # Build policy trace
        trace = PolicyTrace(
            decision_id=decision_id,
            timestamp=datetime.now().isoformat(),
            pilot="hotel_credit_scoring",
            action=action,
            policy_rules_evaluated=rules_evaluated,
            permit_gates_passed=gates_passed,
            policy_violations=violations,
            escalation_justified=escalation_justified,
            human_review_required=action == "ESCALATED" or action == "DENIED",
            approval_confidence=1.0 - risk_score,
        )

        severity = "CRITICAL" if violations else ("MEDIUM" if warnings else "LOW")

        return ActivityCheckResult(
            is_valid=len(violations) == 0,
            decision_id=decision_id,
            pilot="hotel_credit_scoring",
            policy_trace=trace,
            violations=violations,
            warnings=warnings,
            severity=severity,
        )

    def _check_glass_safety(self, decision: Dict[str, Any]) -> ActivityCheckResult:
        """Validate glass safety decision."""
        decision_id = decision.get("decision_id", "unknown")
        action = decision.get("action", "UNKNOWN")
        violations = []
        warnings = []
        rules_evaluated = []
        gates_passed = []

        defect_confidence = decision.get("defect_confidence", 0.5)
        process_within_tolerance = decision.get("process_within_tolerance", True)
        anomalies_detected = decision.get("anomalies_detected", False)
        human_reviewer = decision.get("human_reviewer")

        # Rule 1: Auto-Pass
        if defect_confidence < 0.01 and process_within_tolerance and not anomalies_detected:
            rules_evaluated.append("auto_pass")
            gates_passed.append("defect_confidence_low")
            gates_passed.append("process_within_tolerance")

            if action != "APPROVED":
                violations.append(f"Auto-pass rule met but action was {action} (expected APPROVED)")

        # Rule 2: Escalation
        elif (0.01 <= defect_confidence < 0.05) or anomalies_detected:
            rules_evaluated.append("escalation")

            if not human_reviewer:
                violations.append("Escalation rule triggered but no human_reviewer assigned")
            else:
                gates_passed.append("human_reviewer_assigned")

            if action != "ESCALATED":
                violations.append(f"Escalation rule met but action was {action} (expected ESCALATED)")

            if defect_confidence >= 0.05:
                warnings.append("High defect confidence (>5%); consider immediate halt")

        # Rule 3: Rejection
        elif defect_confidence >= 0.05:
            rules_evaluated.append("rejection")

            if not human_reviewer:
                violations.append("Rejection without human approval (SLA 2 min)")
            else:
                gates_passed.append("human_reviewer_approved")

            if action != "DENIED":
                violations.append(f"Rejection rule met but action was {action} (expected DENIED)")

        trace = PolicyTrace(
            decision_id=decision_id,
            timestamp=datetime.now().isoformat(),
            pilot="glass_manufacturing_safety",
            action=action,
            policy_rules_evaluated=rules_evaluated,
            permit_gates_passed=gates_passed,
            policy_violations=violations,
            escalation_justified=bool(human_reviewer) and action in ["ESCALATED", "DENIED"],
            human_review_required=action in ["ESCALATED", "DENIED"],
            approval_confidence=1.0 - defect_confidence,
        )

        severity = "CRITICAL" if violations else ("MEDIUM" if warnings else "LOW")

        return ActivityCheckResult(
            is_valid=len(violations) == 0,
            decision_id=decision_id,
            pilot="glass_manufacturing_safety",
            policy_trace=trace,
            violations=violations,
            warnings=warnings,
            severity=severity,
        )

    def _check_school_access(self, decision: Dict[str, Any]) -> ActivityCheckResult:
        """Validate school access decision (100% human review)."""
        decision_id = decision.get("decision_id", "unknown")
        action = decision.get("action", "UNKNOWN")
        violations = []
        warnings = []
        rules_evaluated = ["human_review_required"]
        gates_passed = []

        human_reviewer = decision.get("human_reviewer")
        parental_consent = decision.get("parental_consent", False)

        # School: All decisions require human review
        if not human_reviewer:
            violations.append("School access decision requires human_reviewer (Article 22 compliance)")
        else:
            gates_passed.append("human_reviewer_assigned")

        if action != "ESCALATED":
            violations.append(f"School access rule requires ESCALATED but action was {action}")
        else:
            gates_passed.append("escalation_action_correct")

        if not parental_consent:
            violations.append("School access requires parental consent (GDPR Article 8)")
        else:
            gates_passed.append("parental_consent_verified")

        trace = PolicyTrace(
            decision_id=decision_id,
            timestamp=datetime.now().isoformat(),
            pilot="school_access_control",
            action=action,
            policy_rules_evaluated=rules_evaluated,
            permit_gates_passed=gates_passed,
            policy_violations=violations,
            escalation_justified=bool(human_reviewer) and action == "ESCALATED",
            human_review_required=True,  # Always required
            approval_confidence=1.0 if action == "ESCALATED" else 0.0,
        )

        severity = "CRITICAL" if violations else ("LOW")

        return ActivityCheckResult(
            is_valid=len(violations) == 0,
            decision_id=decision_id,
            pilot="school_access_control",
            policy_trace=trace,
            violations=violations,
            warnings=warnings,
            severity=severity,
        )

    def batch_check_decisions(self, decisions: List[Dict[str, Any]]) -> List[ActivityCheckResult]:
        """Check multiple decisions in batch."""
        results = []
        for decision in decisions:
            result = self.check_decision(decision)
            results.append(result)
        return results

    def generate_compliance_report(self, results: List[ActivityCheckResult]) -> Dict[str, Any]:
        """Generate summary report from batch check results."""
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid = total - valid
        critical = sum(1 for r in results if r.severity == "CRITICAL")

        by_pilot = {}
        for pilot in PilotDomain:
            pilot_results = [r for r in results if r.pilot == pilot.value]
            if pilot_results:
                by_pilot[pilot.value] = {
                    "total": len(pilot_results),
                    "valid": sum(1 for r in pilot_results if r.is_valid),
                    "invalid": sum(1 for r in pilot_results if not r.is_valid),
                }

        return {
            "timestamp": datetime.now().isoformat(),
            "total_decisions_checked": total,
            "valid": valid,
            "invalid": invalid,
            "critical_violations": critical,
            "compliance_rate": valid / total if total > 0 else 0.0,
            "by_pilot": by_pilot,
            "status": "PASS" if invalid == 0 else "FAIL",
        }


def main():
    """CLI for activity checking."""
    if len(sys.argv) < 2:
        print("Usage: python actcheck_wrapper.py <decision_json_file>")
        print("   or: python actcheck_wrapper.py --batch <results_json_file>")
        sys.exit(1)

    checker = ActivityChecker()

    if sys.argv[1] == "--batch" and len(sys.argv) > 2:
        # Batch check
        with open(sys.argv[2]) as f:
            decisions = json.load(f)

        results = checker.batch_check_decisions(decisions)
        report = checker.generate_compliance_report(results)

        print(json.dumps(report, indent=2))
        print(f"\n✅ Checked {report['total_decisions_checked']} decisions")
        print(f"Compliance Rate: {report['compliance_rate']:.1%}")
        sys.exit(0 if report["status"] == "PASS" else 1)

    else:
        # Single decision
        with open(sys.argv[1]) as f:
            decision = json.load(f)

        result = checker.check_decision(decision)

        print(json.dumps(asdict(result), indent=2, default=str))
        sys.exit(0 if result.is_valid else 1)


if __name__ == "__main__":
    main()
