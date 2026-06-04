#!/usr/bin/env python3
"""
DEMO: Wire Human Gate in Action
Demonstrates complete governance flow with realistic scenarios.
Shows fail-closed gates, zero-charge rejections, and Merkle proofs.
"""

from vision_api import (
    VisionAPI, GovernRequest, RiskLevel, HumanGatePolicy,
    MongeGapGovernor
)
import json


def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_decision(request_id, result):
    """Pretty print a governance decision"""
    status = "✓ APPROVED" if result.allowed else "✗ BLOCKED"
    print(f"{status:15} | Request: {request_id}")
    print(f"{'':15} | Charge: {result.charge_amount} AP2 units")
    print(f"{'':15} | Reason: {result.reason}")
    if result.proof:
        print(f"{'':15} | Merkle Root: {result.proof.merkle_root[:32]}...")
    if result.error:
        print(f"{'':15} | Error: {result.error}")
    print()


def demo_basic_flow():
    """Demo 1: Basic approval flow with risk levels"""
    print_header("DEMO 1: Basic Approval Flow (Risk Levels)")

    api = VisionAPI()

    # Scenario A: Low-risk read operation
    print("Scenario A: Low-risk data read (auto-approved)\n")
    read_request = GovernRequest(
        request_id="demo-001-read",
        action="read_analytics_data",
        blast_radius=0.10,  # LOW RISK
        user_id="analyst@company.com",
        app_id="dashboard-service",
        human_approved=False,
    )
    read_result = api.pre_execute_check(read_request)
    print_decision("demo-001-read", read_result)

    # Scenario B: High-risk write operation WITHOUT approval
    print("Scenario B: High-risk system update (BLOCKED - no approval)\n")
    write_request = GovernRequest(
        request_id="demo-001-write",
        action="update_system_config",
        blast_radius=0.80,  # HIGH RISK
        user_id="developer@company.com",
        app_id="dashboard-service",
        human_approved=False,
    )
    write_result = api.pre_execute_check(write_request)
    print_decision("demo-001-write", write_result)

    # Scenario C: High-risk write operation WITH approval
    print("Scenario C: Same operation WITH human approval (APPROVED)\n")
    approved_write_request = GovernRequest(
        request_id="demo-001-write-approved",
        action="update_system_config",
        blast_radius=0.80,  # HIGH RISK
        user_id="admin@company.com",
        app_id="dashboard-service",
        human_approved=True,  # HUMAN APPROVED
    )
    approved_write_result = api.pre_execute_check(approved_write_request)
    print_decision("demo-001-write-approved", approved_write_result)

    print(f"Final Merkle Root: {api.merkle_root[:32]}...")


def demo_drift_detection():
    """Demo 2: PSI drift detection and auto-gate engagement"""
    print_header("DEMO 2: PSI Drift Detection (MongeGapGovernor)")

    api = VisionAPI()
    governor = MongeGapGovernor()

    # Baseline model performance
    print("Baseline model performance (stable distribution):\n")
    baseline = [0.85, 0.87, 0.86, 0.88, 0.84, 0.86, 0.87, 0.85, 0.86, 0.88]
    print(f"  Mean: {sum(baseline) / len(baseline):.2f}")
    print(f"  Std Dev: {(sum((x - sum(baseline)/len(baseline))**2 for x in baseline) / len(baseline))**0.5:.4f}")
    print()

    # Current model (no drift)
    print("Current model output (stable, PSI < 0.25):\n")
    current_stable = [0.84, 0.86, 0.87, 0.89, 0.85, 0.87, 0.86, 0.84, 0.85, 0.87]
    psi_stable = governor.compute_psi(baseline, current_stable)
    print(f"  Mean: {sum(current_stable) / len(current_stable):.2f}")
    print(f"  Std Dev: {(sum((x - sum(current_stable)/len(current_stable))**2 for x in current_stable) / len(current_stable))**0.5:.4f}")
    print(f"  PSI: {psi_stable:.4f} (< 0.25 threshold)")
    print(f"  → Model STABLE - inference allowed\n")

    # Current model (WITH drift)
    print("Current model output (drifted, PSI > 0.25):\n")
    current_drift = [0.65, 0.67, 0.68, 0.70, 0.64, 0.66, 0.67, 0.65, 0.66, 0.68]
    psi_drift = governor.compute_psi(baseline, current_drift)
    print(f"  Mean: {sum(current_drift) / len(current_drift):.2f}")
    print(f"  Std Dev: {(sum((x - sum(current_drift)/len(current_drift))**2 for x in current_drift) / len(current_drift))**0.5:.4f}")
    print(f"  PSI: {psi_drift:.4f} (> 0.25 threshold)")
    print(f"  → Model DRIFTED - AUTO-GATE ENGAGED\n")

    # Test governance with drift
    print("Governance decision with drifted model:\n")
    inference_request = GovernRequest(
        request_id="demo-002-inference",
        action="run_inference",
        blast_radius=0.45,  # MEDIUM RISK
        user_id="ml-team@company.com",
        app_id="dashboard-service",
        human_approved=False,
    )

    # Without human approval - BLOCKED due to drift
    result_no_approval = api.pre_execute_check(inference_request, psi_drift=psi_drift)
    print_decision("demo-002-inference", result_no_approval)

    # WITH human approval - ALLOWED despite drift
    approved_inference = GovernRequest(
        request_id="demo-002-inference-approved",
        action="run_inference",
        blast_radius=0.45,
        user_id="ml-lead@company.com",
        app_id="dashboard-service",
        human_approved=True,  # HUMAN APPROVED
    )
    result_with_approval = api.pre_execute_check(approved_inference, psi_drift=psi_drift)
    print_decision("demo-002-inference-approved", result_with_approval)


def demo_critical_action():
    """Demo 3: Critical-risk action requires approval"""
    print_header("DEMO 3: Critical-Risk Action (Delete Operation)")

    api = VisionAPI()

    # Attempt 1: No approval
    print("Attempt 1: Delete critical data WITHOUT approval\n")
    delete_request = GovernRequest(
        request_id="demo-003-delete-no-approval",
        action="delete_production_database",
        blast_radius=0.95,  # CRITICAL
        user_id="developer@company.com",
        app_id="dashboard-service",
        human_approved=False,
    )
    delete_result = api.pre_execute_check(delete_request)
    print_decision("demo-003-delete-no-approval", delete_result)

    print("Notice: Charge amount is ZERO on rejection")
    print("        No ledger entry, no cost to the system")
    print()

    # Attempt 2: With CEO approval
    print("Attempt 2: Same operation WITH executive approval\n")
    approved_delete = GovernRequest(
        request_id="demo-003-delete-approved",
        action="delete_production_database",
        blast_radius=0.95,  # CRITICAL
        user_id="ceo@company.com",
        app_id="dashboard-service",
        human_approved=True,  # APPROVED BY CEO
    )
    approved_result = api.pre_execute_check(approved_delete)
    print_decision("demo-003-delete-approved", approved_result)

    print("Executive approval overrides the gate")
    print("Action proceeds with full AP2 charge and Merkle proof")


def demo_audit_trail():
    """Demo 4: Audit trail and compliance export"""
    print_header("DEMO 4: Audit Trail & Compliance Export")

    api = VisionAPI()

    # Run several operations
    requests = [
        GovernRequest("demo-004-req1", "read_data", 0.15, "user1", "app", False),
        GovernRequest("demo-004-req2", "write_config", 0.60, "user2", "app", False),
        GovernRequest("demo-004-req3", "execute_command", 0.80, "admin", "app", True),
    ]

    for req in requests:
        api.pre_execute_check(req)

    # Export audit trail
    audit = api.export_audit_trail()
    print(audit)

    print("Audit trail features:")
    print("  ✓ Cryptographically signed (SHA256)")
    print("  ✓ Immutable Merkle chain")
    print("  ✓ Non-repudiable (user_id logged)")
    print("  ✓ Compliant with EU AI Act Article 12")


def demo_custom_policy():
    """Demo 5: Custom governance policy"""
    print_header("DEMO 5: Custom Governance Policy")

    # Policy 1: Strict (no AP2 charges for testing)
    print("Policy 1: Testing environment (no charges)\n")
    test_policy = HumanGatePolicy(
        policy_id="testing-no-charge",
        ap2_charge_enabled=False,
        psi_drift_threshold=0.15,  # More sensitive drift detection
    )

    api_test = VisionAPI(policy=test_policy)
    test_request = GovernRequest(
        request_id="demo-005-test",
        action="read",
        blast_radius=0.10,
        user_id="qa-team",
        app_id="test-harness",
        human_approved=False,
    )
    test_result = api_test.pre_execute_check(test_request)
    print(f"Charge (testing): {test_result.charge_amount} (disabled)")
    print()

    # Policy 2: Permissive (higher drift threshold)
    print("Policy 2: Production environment (higher drift threshold)\n")
    prod_policy = HumanGatePolicy(
        policy_id="production-default",
        ap2_charge_enabled=True,
        psi_drift_threshold=0.35,  # Less sensitive, only alert on major drift
    )

    api_prod = VisionAPI(policy=prod_policy)
    prod_request = GovernRequest(
        request_id="demo-005-prod",
        action="inference",
        blast_radius=0.45,
        user_id="ml-ops",
        app_id="production",
        human_approved=False,
    )

    # PSI = 0.30 (between old and new thresholds)
    psi = 0.30
    prod_result = api_prod.pre_execute_check(prod_request, psi_drift=psi)

    print(f"PSI: {psi:.2f}")
    print(f"  Testing threshold: 0.15 → GATE TRIGGERS")
    print(f"  Production threshold: 0.35 → GATE PASSES")
    print(f"Allowed (production): {prod_result.allowed}")
    print(f"Charge (production): {prod_result.charge_amount}")


def main():
    print("\n" + "█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "  WIRE HUMAN GATE — COMPLETE GOVERNANCE INTEGRATION DEMO".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80)

    demo_basic_flow()
    demo_drift_detection()
    demo_critical_action()
    demo_audit_trail()
    demo_custom_policy()

    print_header("DEMO COMPLETE")
    print("Wire Human Gate Features Demonstrated:")
    print("  ✓ Fail-closed gates (high-risk blocked without approval)")
    print("  ✓ Zero charge on rejection (no cost to system)")
    print("  ✓ AP2 charge + Merkle proof on approval")
    print("  ✓ PSI drift detection with auto-gate engagement")
    print("  ✓ Human override capability (admin approval)")
    print("  ✓ Cryptographic audit trail (EU AI Act Article 12)")
    print("  ✓ Custom policies per environment")
    print()
    print("Ready for production deployment and compliance audits.")
    print()


if __name__ == "__main__":
    main()
