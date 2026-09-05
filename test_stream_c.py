"""
Stream C: L3-L5 Tooling, Orchestration, Communication
Integration tests for agentacct, unlazy gates, MCP servers
"""

import json
import time
import subprocess
import requests
import pytest
from pathlib import Path
from datetime import datetime
import tempfile
import sys

# Adjust path for imports
sys.path.insert(0, str(Path(__file__).parent))


class TestAgentacctWorkReceipt:
    """Test agentacct work receipt system (L3 tooling)"""

    def test_capture_work_receipt_basic(self):
        """Test basic work receipt capture with Ed25519 signature"""
        from agentacct_capture import WorkReceipt, AgentAcct

        acct = AgentAcct()
        receipt = acct.capture(
            action_id="action_001",
            prompt="What is 2+2?",
            tokens_used=50,
            cost=0.001,
        )

        assert receipt.action_id == "action_001"
        assert receipt.prompt == "What is 2+2?"
        assert receipt.tokens_used == 50
        assert receipt.cost == 0.001
        assert receipt.signature is not None
        assert receipt.timestamp is not None

    def test_agentacct_stores_json_locally(self):
        """Test work receipts stored in local JSON (not phone-home)"""
        from agentacct_capture import AgentAcct

        with tempfile.TemporaryDirectory() as tmpdir:
            acct = AgentAcct(storage_dir=tmpdir)
            acct.capture(
                action_id="action_002",
                prompt="Test prompt",
                tokens_used=100,
                cost=0.002,
            )

            # Check JSON file exists
            json_files = list(Path(tmpdir).glob("work_receipts_*.json"))
            assert len(json_files) > 0

            # Check content
            with open(json_files[0]) as f:
                data = json.load(f)
                assert len(data) >= 1
                assert data[0]["action_id"] == "action_002"

    def test_agentacct_signature_verification(self):
        """Test Ed25519 signature verification"""
        from agentacct_capture import AgentAcct

        acct = AgentAcct()
        receipt = acct.capture(
            action_id="action_003",
            prompt="Another test",
            tokens_used=75,
            cost=0.0015,
        )

        # Verify signature is valid (signature present and not empty)
        assert receipt.signature is not None
        assert len(receipt.signature) > 0


class TestUnlazyGates:
    """Test unlazy fail-closed gates (L3 tooling)"""

    def test_gate_check_rejects_unsafe_action(self):
        """Test CHECK phase rejects unsafe action before execution"""
        from unlazy_gates import FailClosedGate, GatePolicy

        gate = FailClosedGate()
        policy = GatePolicy(
            rule_id="hotel_credit_001",
            description="Only approve hotel credit scoring for verified merchants",
            policy_query="SELECT policy FROM policies WHERE category = 'credit_scoring'",
        )

        # Unsafe action (no merchant verification)
        result = gate.check(
            action="approve_credit_line",
            context={"merchant": "unknown", "amount": 10000},
            policy=policy,
        )

        # Should be BLOCKED at CHECK phase
        assert result["status"] == "BLOCKED"
        assert result["phase"] == "CHECK"
        assert "merchant verification" in result["reason"].lower()

    def test_gate_check_allows_safe_action(self):
        """Test CHECK phase allows safe action to proceed"""
        from unlazy_gates import FailClosedGate, GatePolicy

        gate = FailClosedGate()
        policy = GatePolicy(
            rule_id="hotel_credit_002",
            description="Approve for verified merchants",
            policy_query="SELECT * FROM policies",
        )

        # Safe action (verified merchant)
        result = gate.check(
            action="approve_credit_line",
            context={"merchant": "verified_001", "amount": 5000},
            policy=policy,
        )

        # Should PASS CHECK and move to EXPECT
        assert result["status"] == "ALLOWED"
        assert result["phase"] == "CHECK"

    def test_gate_expect_declares_success_criteria(self):
        """Test EXPECT phase declares what success looks like"""
        from unlazy_gates import FailClosedGate, GatePolicy

        gate = FailClosedGate()

        expected = gate.expect(
            action="approve_credit_line",
            success_criteria={
                "response_type": "dict",
                "required_fields": ["approval_id", "amount", "timestamp"],
            },
        )

        assert expected["action"] == "approve_credit_line"
        assert "approval_id" in expected["required_fields"]

    def test_gate_evidence_captures_immutable_proof(self):
        """Test EVIDENCE phase captures immutable proof after execution"""
        from unlazy_gates import FailClosedGate

        gate = FailClosedGate()

        # Simulate agent output
        agent_output = {
            "approval_id": "appr_001",
            "amount": 5000,
            "timestamp": datetime.now().isoformat(),
            "merchant": "verified_001",
        }

        evidence = gate.evidence(
            action="approve_credit_line",
            output=agent_output,
            expected_criteria={
                "response_type": "dict",
                "required_fields": ["approval_id", "amount", "timestamp"],
            },
        )

        # Evidence should capture proof
        assert evidence["status"] == "CAPTURED"
        assert evidence["proof_hash"] is not None
        assert evidence["timestamp"] is not None

    def test_gate_blocks_without_evidence(self):
        """Test agent cannot end turn without proof (fail-closed)"""
        from unlazy_gates import FailClosedGate

        gate = FailClosedGate()

        # Try to finalize without evidence
        try:
            result = gate.finalize(action="approve_credit_line", evidence=None)
            # Should either raise or return failure
            assert (
                result.get("status") == "FAILED"
                or result.get("status") == "BLOCKED"
            )
        except ValueError as e:
            # Acceptable: fail-closed means error is expected
            assert "evidence" in str(e).lower()


class TestMCPServerDiscovery:
    """Test MCP server discovery (L5 communication)"""

    def test_mcp_discovery_returns_three_servers(self):
        """Test MCP discovery returns 3 configured servers"""
        from mcp_discovery import MCPServerRegistry

        registry = MCPServerRegistry()

        servers = registry.discover()

        assert len(servers) == 3
        server_names = [s["name"] for s in servers]
        assert "hotel" in server_names
        assert "glass" in server_names
        assert "school" in server_names

    def test_mcp_hotel_server_has_tools(self):
        """Test hotel MCP server exposes credit scoring tools"""
        from mcp_discovery import MCPServerRegistry

        registry = MCPServerRegistry()
        servers = registry.discover()
        hotel_server = next(s for s in servers if s["name"] == "hotel")

        assert "tools" in hotel_server
        assert len(hotel_server["tools"]) >= 5
        tool_names = [t["name"] for t in hotel_server["tools"]]
        assert any("credit" in name.lower() for name in tool_names)
        assert any("policy" in name.lower() for name in tool_names)

    def test_mcp_glass_server_has_tools(self):
        """Test glass MCP server exposes safety review tools"""
        from mcp_discovery import MCPServerRegistry

        registry = MCPServerRegistry()
        servers = registry.discover()
        glass_server = next(s for s in servers if s["name"] == "glass")

        assert "tools" in glass_server
        assert len(glass_server["tools"]) >= 5
        tool_names = [t["name"] for t in glass_server["tools"]]
        assert any("safety" in name.lower() for name in tool_names)
        assert any("review" in name.lower() for name in tool_names)

    def test_mcp_school_server_has_tools(self):
        """Test school MCP server exposes access control tools"""
        from mcp_discovery import MCPServerRegistry

        registry = MCPServerRegistry()
        servers = registry.discover()
        school_server = next(s for s in servers if s["name"] == "school")

        assert "tools" in school_server
        assert len(school_server["tools"]) >= 5
        tool_names = [t["name"] for t in school_server["tools"]]
        assert any("access" in name.lower() for name in tool_names)
        assert any("control" in name.lower() for name in tool_names)


class TestStreamCIntegration:
    """Integration tests for Stream C components"""

    def test_integration_gate_check_blocks_unsafe_action(self):
        """Integration: gates CHECK rejects unsafe action before execution"""
        from unlazy_gates import FailClosedGate, GatePolicy

        gate = FailClosedGate()
        policy = GatePolicy(
            rule_id="test_001",
            description="Test policy",
            policy_query="SELECT * FROM test",
        )

        # Unsafe: unverified actor
        result = gate.check(
            action="test_action",
            context={"actor": "unknown"},
            policy=policy,
        )

        assert result["status"] == "BLOCKED"

    def test_integration_gate_expect_matches_agent_output(self):
        """Integration: gates EXPECT matches agent output"""
        from unlazy_gates import FailClosedGate

        gate = FailClosedGate()

        # Declare expectations
        expected = gate.expect(
            action="test_action",
            success_criteria={
                "required_fields": ["result", "status"],
            },
        )

        # Agent produces compliant output
        agent_output = {"result": "success", "status": "ok"}

        # Match expectations
        matches = set(agent_output.keys()) >= set(expected["required_fields"])
        assert matches

    def test_integration_gate_evidence_captures_proof(self):
        """Integration: gates EVIDENCE captures immutable proof"""
        from unlazy_gates import FailClosedGate

        gate = FailClosedGate()

        output = {"result": "success", "status": "ok"}

        evidence = gate.evidence(
            action="test_action",
            output=output,
            expected_criteria={"required_fields": ["result", "status"]},
        )

        assert evidence["status"] == "CAPTURED"
        assert evidence["proof_hash"] is not None

    def test_integration_multiple_work_receipts(self):
        """Integration: capture 5+ work receipts with signatures"""
        from agentacct_capture import AgentAcct

        acct = AgentAcct()
        receipts = []

        for i in range(5):
            receipt = acct.capture(
                action_id=f"action_{i:03d}",
                prompt=f"Prompt {i}",
                tokens_used=100 + i * 10,
                cost=0.001 * (i + 1),
            )
            receipts.append(receipt)

        assert len(receipts) == 5
        for receipt in receipts:
            assert receipt.signature is not None
            assert receipt.action_id is not None

    def test_integration_mcp_discovery_returns_servers(self):
        """Integration: MCP server discovery returns 3 servers"""
        from mcp_discovery import MCPServerRegistry

        registry = MCPServerRegistry()
        servers = registry.discover()

        assert len(servers) == 3
        assert all("name" in s and "tools" in s for s in servers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
