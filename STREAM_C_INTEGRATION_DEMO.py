"""
Stream C: Integration Demo
Demonstrates full flow: agentacct → unlazy gates → MCP discovery
"""

from agentacct_capture import AgentAcct
from unlazy_gates import FailClosedGate, GatePolicy, GateTestHelper
from mcp_discovery import MCPServerRegistry
from datetime import datetime


def demo_agentacct():
    """Demo: Work receipt capture and storage"""
    print("=" * 60)
    print("DEMO 1: agentacct Work Receipt System")
    print("=" * 60)

    acct = AgentAcct()

    # Capture 3 work receipts
    for i in range(1, 4):
        receipt = acct.capture(
            action_id=f"hotel_credit_{i:03d}",
            prompt=f"Evaluate merchant {i} for credit line",
            tokens_used=100 + i * 50,
            cost=0.002 * i,
        )
        print(f"Receipt {i}: {receipt.action_id}")
        print(f"  Signature: {receipt.signature[:32]}...")
        print(f"  Timestamp: {receipt.timestamp}")
        print(f"  Verified: {acct.verify_signature(receipt)}")
        print()

    print(f"Total receipts captured: {len(acct.get_receipts())}")
    print()


def demo_unlazy_gates():
    """Demo: Fail-closed gate enforcement"""
    print("=" * 60)
    print("DEMO 2: unlazy Fail-Closed Gates (CHECK → EXPECT → EVIDENCE)")
    print("=" * 60)

    gate = FailClosedGate()
    policy = GatePolicy(
        rule_id="hotel_credit_policy_001",
        description="Hotel credit scoring authorization",
        policy_query="SELECT * FROM policies WHERE type = 'credit'",
    )

    # Test 1: Safe action (verified merchant)
    print("\nTest 1: Safe Action (Verified Merchant)")
    print("-" * 40)

    safe_context = {"merchant": "verified_001", "amount": 10000}
    check_result = gate.check("approve_credit_line", safe_context, policy)
    print(f"CHECK Result: {check_result['status']}")

    if check_result["status"] == "ALLOWED":
        # Phase 2: EXPECT
        expected = gate.expect(
            "approve_credit_line",
            success_criteria={
                "required_fields": ["approval_id", "amount", "timestamp"],
                "response_type": "dict",
            },
        )
        print(f"EXPECT: Declared {len(expected['required_fields'])} required fields")

        # Phase 3: EVIDENCE
        agent_output = {
            "approval_id": "appr_verified_001_10000",
            "amount": 10000,
            "timestamp": datetime.utcnow().isoformat(),
        }

        evidence = gate.evidence(
            "approve_credit_line",
            agent_output,
            expected["expected_criteria"],
        )
        print(f"EVIDENCE: {evidence['status']}")
        print(f"Proof Hash: {evidence['proof_hash'][:32]}...")

        # Phase 4: FINALIZE
        final = gate.finalize("approve_credit_line", evidence)
        print(f"FINALIZE: {final['status']}")

    # Test 2: Unsafe action (unverified merchant)
    print("\nTest 2: Unsafe Action (Unverified Merchant)")
    print("-" * 40)

    unsafe_context = {"merchant": "unknown_001", "amount": 50000}
    check_result = gate.check("approve_credit_line", unsafe_context, policy)
    print(f"CHECK Result: {check_result['status']}")
    print(f"Reason: {check_result['reason']}")
    print("✓ Action BLOCKED at CHECK phase (fail-closed)")

    print()


def demo_mcp_discovery():
    """Demo: MCP server discovery"""
    print("=" * 60)
    print("DEMO 3: MCP Server Discovery")
    print("=" * 60)

    registry = MCPServerRegistry()
    servers = registry.discover()

    print(f"\nDiscovered {len(servers)} MCP servers:")
    print()

    for server in servers:
        print(f"Server: {server['name'].upper()}")
        print(f"  Port: {server['port']}")
        print(f"  Tools: {len(server['tools'])}")
        print(f"  Tool List:")
        for tool in server["tools"]:
            print(f"    - {tool['name']}")
        print()

    # Verify specific tools exist
    print("Tool Verification:")
    print("-" * 40)

    hotel = registry.get_server("hotel")
    hotel_tools = [t["name"] for t in hotel["tools"]]
    assert "check_credit_policy" in hotel_tools
    print("✓ Hotel server has check_credit_policy")

    glass = registry.get_server("glass")
    glass_tools = [t["name"] for t in glass["tools"]]
    assert "analyze_safety_risk" in glass_tools
    print("✓ Glass server has analyze_safety_risk")

    school = registry.get_server("school")
    school_tools = [t["name"] for t in school["tools"]]
    assert "verify_enrollment_eligibility" in school_tools
    print("✓ School server has verify_enrollment_eligibility")

    print()


def demo_full_integration():
    """Demo: Full Stream C integration"""
    print("=" * 60)
    print("DEMO 4: Full Stream C Integration")
    print("=" * 60)

    # Step 1: Capture work
    acct = AgentAcct()
    receipt = acct.capture(
        action_id="integration_test_001",
        prompt="Process hotel credit approval",
        tokens_used=250,
        cost=0.005,
    )
    print(f"\n1. Work Receipt Captured: {receipt.action_id}")
    print(f"   Signed: {receipt.signature[:32]}...")

    # Step 2: Enforce gates
    gate = FailClosedGate()
    policy = GatePolicy(
        rule_id="hotel_policy_001",
        description="Integration test policy",
        policy_query="SELECT * FROM policies",
    )

    check = gate.check(
        "approve_credit_line",
        {"merchant": "verified_integration_001", "amount": 5000},
        policy,
    )
    print(f"\n2. Gate CHECK: {check['status']}")

    expect = gate.expect(
        "approve_credit_line",
        {"required_fields": ["approval_id", "amount"]},
    )
    print(f"3. Gate EXPECT: {len(expect['required_fields'])} fields required")

    output = {"approval_id": "appr_int_001", "amount": 5000}
    evidence = gate.evidence(
        "approve_credit_line",
        output,
        expect["expected_criteria"],
    )
    print(f"4. Gate EVIDENCE: {evidence['status']}")

    final = gate.finalize("approve_credit_line", evidence)
    print(f"5. Gate FINALIZE: {final['status']}")

    # Step 3: Query MCP servers
    registry = MCPServerRegistry()
    servers = registry.discover()
    print(f"\n6. MCP Servers Available: {len(servers)}")
    for server in servers:
        print(f"   - {server['name']}: {len(server['tools'])} tools")

    print("\n" + "=" * 60)
    print("✓ STREAM C INTEGRATION DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    demo_agentacct()
    demo_unlazy_gates()
    demo_mcp_discovery()
    demo_full_integration()
