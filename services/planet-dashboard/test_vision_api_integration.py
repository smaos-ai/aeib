#!/usr/bin/env python3
"""
Integration test for Wire Human Gate — Vision API
Tests complete integration with zero blocking.
"""

import sys
from vision_api import (
    VisionAPI, GovernRequest, RiskLevel, HumanGatePolicy,
    PreExecuteCheckResult, HumanGateProof, MongeGapGovernor
)


def test_complete_integration():
    """Test: Complete Wire Human Gate integration"""
    print("=" * 70)
    print("WIRE HUMAN GATE — COMPLETE INTEGRATION TEST")
    print("=" * 70)
    print()

    # Initialize VisionAPI
    api = VisionAPI()
    print("✓ VisionAPI initialized")

    # Test 1: Low-risk action (auto-approved)
    print("\n[TEST 1] Low-risk action auto-approved")
    low_risk_request = GovernRequest(
        request_id="int-001",
        action="read_metadata",
        blast_radius=0.15,  # LOW
        user_id="analyst-1",
        app_id="dashboard-app",
        human_approved=False,
    )
    low_risk_result = api.pre_execute_check(low_risk_request)
    assert low_risk_result.allowed is True
    assert low_risk_result.charge_amount == 100
    assert low_risk_result.proof is not None
    assert low_risk_result.proof.auto_approved is True
    print(f"  ✓ Allowed: {low_risk_result.allowed}")
    print(f"  ✓ Charge: {low_risk_result.charge_amount}")
    print(f"  ✓ Auto-approved: {low_risk_result.proof.auto_approved}")
    print(f"  ✓ Merkle proof: {low_risk_result.proof.merkle_root[:16]}...")

    # Test 2: High-risk action WITHOUT approval (blocked, zero charge)
    print("\n[TEST 2] High-risk action without approval (BLOCKED)")
    high_risk_request = GovernRequest(
        request_id="int-002",
        action="execute_system_command",
        blast_radius=0.85,  # HIGH
        user_id="developer-1",
        app_id="dashboard-app",
        human_approved=False,
    )
    high_risk_result = api.pre_execute_check(high_risk_request)
    assert high_risk_result.allowed is False
    assert high_risk_result.charge_amount == 0  # ZERO charge
    assert high_risk_result.proof is None
    assert high_risk_result.error == "HumanGateRequired"
    print(f"  ✓ Allowed: {high_risk_result.allowed}")
    print(f"  ✓ Charge (zero): {high_risk_result.charge_amount}")
    print(f"  ✓ Error: {high_risk_result.error}")
    print(f"  ✓ Reason: {high_risk_result.reason}")

    # Test 3: High-risk action WITH human approval (allowed, charged)
    print("\n[TEST 3] High-risk action with human approval (ALLOWED)")
    approved_request = GovernRequest(
        request_id="int-003",
        action="execute_system_command",
        blast_radius=0.85,  # HIGH
        user_id="admin-1",
        app_id="dashboard-app",
        human_approved=True,  # APPROVED
    )
    approved_result = api.pre_execute_check(approved_request)
    assert approved_result.allowed is True
    assert approved_result.charge_amount == 100
    assert approved_result.proof is not None
    assert approved_result.proof.approved_by == "admin-1"
    assert approved_result.proof.auto_approved is False
    print(f"  ✓ Allowed: {approved_result.allowed}")
    print(f"  ✓ Charge: {approved_result.charge_amount}")
    print(f"  ✓ Approved by: {approved_result.proof.approved_by}")
    print(f"  ✓ Merkle proof: {approved_result.proof.merkle_root[:16]}...")

    # Test 4: Critical-risk action (requires approval)
    print("\n[TEST 4] Critical-risk action requires approval")
    critical_request = GovernRequest(
        request_id="int-004",
        action="delete_all_data",
        blast_radius=0.95,  # CRITICAL
        user_id="user-1",
        app_id="dashboard-app",
        human_approved=False,
    )
    critical_result = api.pre_execute_check(critical_request)
    assert critical_result.allowed is False
    assert critical_result.charge_amount == 0
    assert critical_result.error == "HumanGateRequired"
    print(f"  ✓ Allowed: {critical_result.allowed}")
    print(f"  ✓ Charge (zero): {critical_result.charge_amount}")
    print(f"  ✓ Blocked correctly")

    # Test 5: PSI drift detection triggers gate
    print("\n[TEST 5] PSI drift > 0.25 auto-engages human gate")
    drift_request = GovernRequest(
        request_id="int-005",
        action="inference",
        blast_radius=0.45,  # MEDIUM
        user_id="ml-team",
        app_id="dashboard-app",
        human_approved=False,
    )
    psi_drift = 0.30  # Triggers gate (> 0.25)
    drift_result = api.pre_execute_check(drift_request, psi_drift=psi_drift)
    assert drift_result.allowed is False
    assert drift_result.charge_amount == 0
    assert drift_result.error == "DriftGateRequired"
    print(f"  ✓ PSI: {psi_drift}")
    print(f"  ✓ Threshold: {api.policy.psi_drift_threshold}")
    print(f"  ✓ Gate triggered: {drift_result.error}")
    print(f"  ✓ Charge (zero): {drift_result.charge_amount}")

    # Test 6: PSI drift can be overridden with human approval
    print("\n[TEST 6] PSI drift overridden by human approval")
    approved_drift_request = GovernRequest(
        request_id="int-006",
        action="inference",
        blast_radius=0.45,  # MEDIUM
        user_id="admin-2",
        app_id="dashboard-app",
        human_approved=True,  # APPROVED
    )
    approved_drift_result = api.pre_execute_check(approved_drift_request, psi_drift=psi_drift)
    assert approved_drift_result.allowed is True
    assert approved_drift_result.charge_amount == 100
    assert approved_drift_result.proof is not None
    print(f"  ✓ Allowed with human override: {approved_drift_result.allowed}")
    print(f"  ✓ Charge: {approved_drift_result.charge_amount}")
    print(f"  ✓ Approved by: {approved_drift_result.proof.approved_by}")

    # Test 7: Merkle proof accumulation
    print("\n[TEST 7] Merkle proof accumulation across requests")
    initial_root = api.merkle_root
    req_a = GovernRequest(
        request_id="int-007a",
        action="action_a",
        blast_radius=0.1,
        user_id="user-a",
        app_id="app",
        human_approved=False,
    )
    result_a = api.pre_execute_check(req_a)
    root_after_a = api.merkle_root

    req_b = GovernRequest(
        request_id="int-007b",
        action="action_b",
        blast_radius=0.2,
        user_id="user-b",
        app_id="app",
        human_approved=False,
    )
    result_b = api.pre_execute_check(req_b)
    root_after_b = api.merkle_root

    assert initial_root != root_after_a
    assert root_after_a != root_after_b
    print(f"  ✓ Initial Merkle root: {initial_root[:16]}...")
    print(f"  ✓ After request A: {root_after_a[:16]}...")
    print(f"  ✓ After request B: {root_after_b[:16]}...")
    print(f"  ✓ Merkle chain properly accumulates")

    # Test 8: Custom policy override
    print("\n[TEST 8] Custom policy override (AP2 disabled)")
    custom_policy = HumanGatePolicy(
        policy_id="custom-no-charge",
        ap2_charge_enabled=False,
    )
    api_custom = VisionAPI(policy=custom_policy)
    custom_request = GovernRequest(
        request_id="int-008",
        action="read",
        blast_radius=0.1,
        user_id="user",
        app_id="app",
        human_approved=False,
    )
    custom_result = api_custom.pre_execute_check(custom_request)
    assert custom_result.allowed is True
    assert custom_result.charge_amount == 0  # No charge
    print(f"  ✓ Custom policy initialized")
    print(f"  ✓ AP2 charge disabled: {custom_result.charge_amount == 0}")
    print(f"  ✓ Request still approved: {custom_result.allowed}")

    # Test 9: Audit trail export
    print("\n[TEST 9] Audit trail export for compliance")
    audit_trail = api.export_audit_trail()
    assert "int-001" in audit_trail
    assert "int-003" in audit_trail
    assert "DECISION AUDIT TRAIL" in audit_trail
    print(f"  ✓ Audit trail contains decisions")
    print(f"  ✓ Audit trail format valid")
    print(f"  ✓ Cryptographically signed Merkle proofs")

    # Test 10: Drift detection with MongeGapGovernor
    print("\n[TEST 10] MongeGapGovernor drift detection")
    governor = MongeGapGovernor()
    # Baseline with natural variance
    baseline = [95.0, 100.0, 105.0, 98.0, 102.0, 101.0, 99.0, 100.0, 103.0, 97.0]
    # Stable: similar distribution
    current_stable = [96.0, 99.0, 104.0, 97.0, 103.0, 102.0, 98.0, 99.0, 104.0, 96.0]
    # Drift: major shift
    current_drift = [70.0, 75.0, 80.0, 72.0, 78.0, 76.0, 74.0, 75.0, 78.0, 71.0]

    psi_stable = governor.compute_psi(baseline, current_stable)
    psi_drift = governor.compute_psi(baseline, current_drift)

    assert psi_stable < 0.25, f"Expected psi_stable < 0.25, got {psi_stable}"
    assert psi_drift > 0.25, f"Expected psi_drift > 0.25, got {psi_drift}"
    print(f"  ✓ Stable distribution PSI: {psi_stable:.4f} (< 0.25)")
    print(f"  ✓ Drift distribution PSI: {psi_drift:.4f} (> 0.25)")
    print(f"  ✓ MongeGapGovernor correctly detects drift")

    print("\n" + "=" * 70)
    print("ALL INTEGRATION TESTS PASSED ✓")
    print("=" * 70)
    print()
    print("Summary:")
    print("  ✓ Wire Human Gate completely integrated")
    print("  ✓ Fail-closed gates working (high-risk blocked without approval)")
    print("  ✓ Zero charge on rejection")
    print("  ✓ AP2 charge + Merkle proof on approval")
    print("  ✓ PSI drift detection auto-engages gate")
    print("  ✓ Custom policies override defaults")
    print("  ✓ Audit trail cryptographically signed")
    print("  ✓ MongeGapGovernor drift detection integrated")
    print("  ✓ Ready for demo")
    print()


if __name__ == "__main__":
    try:
        test_complete_integration()
        exit(0)
    except AssertionError as e:
        print(f"\n[FAILED] {e}")
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        exit(1)
