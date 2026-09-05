#!/usr/bin/env python3
"""
Integration Example: L1 Policy Router with Vision API

This example shows how to use the PolicyRouter in the SMAOS pipeline:
1. Client sends request to Vision API (port 8000)
2. Vision API creates PolicyRoute using PolicyRouter
3. PolicyRoute passed to L2 (Knowledge) layer for policy lookup
4. L2 enforces policies using L3 (PermitGates)
5. Decision returned with compliance trail

Run this to see policy routing in action.
"""

import json
from policy_router import PolicyRouter


def demonstrate_hotel_credit_scoring():
    """Example: Hotel credit scoring pilot."""
    print("\n" + "=" * 70)
    print("SMAOS L1 POLICY ROUTING: HOTEL CREDIT SCORING")
    print("=" * 70)

    router = PolicyRouter()

    # Scenario: Guest requests financing for stay
    request = {
        "pilot": "hotel",
        "guest_id": "g123456",
        "amount_requested": 2500,  # USD
        "description": "Financing check for 7-night stay",
    }

    print(f"\nRequest: {json.dumps(request, indent=2)}")

    # Run policy routing (simulated compliance assessment: 92%)
    route = router.route_request(
        pilot_name="hotel",
        request_description=request["description"],
        compliance_assessment=92,
    )

    print(f"\nPolicy Route Decision:")
    print(f"  Route ID: {route.route_id}")
    print(f"  Decision: {route.decision}")
    print(f"  Compliance Score: {route.compliance_score}%")
    print(f"  Risk Level: {route.risk_level.value}")
    print(f"  Articles: {', '.join(route.articles)}")
    print(f"  Annexes: {', '.join(route.annex_sections)}")

    print(f"\nAudit Trail:")
    print(route.audit_trail)

    # Enforcement metadata for downstream layers
    enforcement = router.enforce_policy(route)
    print(f"\nEnforcement Configuration (for L2/L3):")
    print(json.dumps(enforcement, indent=2))


def demonstrate_glass_safety_review():
    """Example: Glass safety detection pilot."""
    print("\n" + "=" * 70)
    print("SMAOS L1 POLICY ROUTING: GLASS SAFETY REVIEW")
    print("=" * 70)

    router = PolicyRouter()

    request = {
        "pilot": "glass",
        "batch_id": "b789",
        "num_samples": 150,
        "description": "Safety-critical glass defect detection",
    }

    print(f"\nRequest: {json.dumps(request, indent=2)}")

    # Compliance assessment: 87%
    route = router.route_request(
        pilot_name="glass",
        request_description=request["description"],
        compliance_assessment=87,
    )

    print(f"\nPolicy Route Decision:")
    print(f"  Route ID: {route.route_id}")
    print(f"  Decision: {route.decision}")
    print(f"  Compliance Score: {route.compliance_score}%")
    print(f"  Risk Level: {route.risk_level.value}")
    print(f"  Articles: {', '.join(route.articles)}")
    print(f"  Annexes: {', '.join(route.annex_sections)}")

    print(f"\nAudit Trail:")
    print(route.audit_trail)

    enforcement = router.enforce_policy(route)
    print(f"\nEnforcement Configuration (for L2/L3):")
    print(json.dumps(enforcement, indent=2))


def demonstrate_school_access_control():
    """Example: School access control pilot."""
    print("\n" + "=" * 70)
    print("SMAOS L1 POLICY ROUTING: SCHOOL ACCESS CONTROL")
    print("=" * 70)

    router = PolicyRouter()

    request = {
        "pilot": "school",
        "student_id": "s456789",
        "access_type": "classroom_entry",
        "description": "Student access control system",
    }

    print(f"\nRequest: {json.dumps(request, indent=2)}")

    # Compliance assessment: 91%
    route = router.route_request(
        pilot_name="school",
        request_description=request["description"],
        compliance_assessment=91,
    )

    print(f"\nPolicy Route Decision:")
    print(f"  Route ID: {route.route_id}")
    print(f"  Decision: {route.decision}")
    print(f"  Compliance Score: {route.compliance_score}%")
    print(f"  Risk Level: {route.risk_level.value}")
    print(f"  Articles: {', '.join(route.articles)}")
    print(f"  Annexes: {', '.join(route.annex_sections)}")

    print(f"\nAudit Trail:")
    print(route.audit_trail)

    enforcement = router.enforce_policy(route)
    print(f"\nEnforcement Configuration (for L2/L3):")
    print(json.dumps(enforcement, indent=2))


def demonstrate_rejection_scenario():
    """Example: Request rejected due to low compliance."""
    print("\n" + "=" * 70)
    print("SMAOS L1 POLICY ROUTING: REJECTION SCENARIO")
    print("=" * 70)

    router = PolicyRouter()

    request = {
        "pilot": "hotel",
        "description": "High-risk credit decision without sufficient guardrails",
    }

    print(f"\nRequest: {json.dumps(request, indent=2)}")
    print("\nAttempting to route with compliance score of 75%...")

    try:
        route = router.route_request(
            pilot_name="hotel",
            request_description=request["description"],
            compliance_assessment=75,
        )
    except ValueError as e:
        print(f"\nPOLICY ENFORCEMENT REJECTED:")
        print(f"  Error: {e}")
        print(f"  Reason: Hotel pilot requires minimum 90% compliance")
        print(f"  Current score: 75%")
        print(f"  Gap: {90 - 75}% below threshold")


def demonstrate_audit_log():
    """Example: Audit log of all routed decisions."""
    print("\n" + "=" * 70)
    print("SMAOS L1 POLICY ROUTING: AUDIT LOG")
    print("=" * 70)

    router = PolicyRouter()

    # Route multiple decisions
    routes_list = [
        ("hotel", "Credit check 1", 92),
        ("glass", "Safety review", 87),
        ("school", "Access control", 91),
        ("hotel", "Credit check 2", 88),
    ]

    for pilot, desc, score in routes_list:
        try:
            router.route_request(pilot, desc, score)
        except ValueError:
            pass

    all_routes = router.get_routes()

    print(f"\nTotal decisions routed: {len(all_routes)}\n")
    for i, route in enumerate(all_routes, 1):
        print(f"Decision {i}:")
        print(f"  Route ID: {route.route_id}")
        print(f"  Pilot: {route.pilot_name}")
        print(f"  Decision: {route.decision}")
        print(f"  Compliance: {route.compliance_score}%")
        print(f"  Timestamp: {route.timestamp}")
        print()


def main():
    """Run all demonstrations."""
    print("\nSMEOS L1 POLICY ROUTER — INTEGRATION EXAMPLES")
    print("Demonstrates EU AI Act compliance routing for 3 pilots")

    demonstrate_hotel_credit_scoring()
    demonstrate_glass_safety_review()
    demonstrate_school_access_control()
    demonstrate_rejection_scenario()
    demonstrate_audit_log()

    print("\n" + "=" * 70)
    print("L1 POLICY ROUTING COMPLETE")
    print("=" * 70)
    print("\nNext Steps:")
    print("  1. L2 (Knowledge Layer): Load policy knowledge for cited Articles")
    print("  2. L3 (Permit Gates): Apply enforcement rules")
    print("  3. L4 (Orchestration): Execute decision with policy constraints")
    print("  4. L8 (Proof Layer): Create immutable audit record")
    print()


if __name__ == "__main__":
    main()
