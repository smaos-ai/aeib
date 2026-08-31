"""Stream C: L3-L5 Tooling Gates + MCP Servers Tests"""

import sys
sys.path.insert(0, '/Users/andriileukhin/.smaos/l3_tooling')

from unlazy_gates import UnlazyGate, PermitGate, GOVERNANCE_RULES
import pytest

def test_unlazy_gates_check_phase_blocks_invalid_policy():
    """Test CHECK phase blocks invalid policy"""
    gate = UnlazyGate("gate_1", "credit_scoring", "Article 50")
    
    invalid_rules = {"score_credit": {"blocked": True}}
    result = gate.check_policy("score_credit", invalid_rules)
    
    assert result == False, "CHECK phase should block when tool is blocked"

def test_unlazy_gates_expect_phase_requires_evidence():
    """Test EXPECT phase requires evidence"""
    gate = UnlazyGate("gate_1", "credit_scoring", "Article 50")
    
    result = gate.expect_evidence("policy_compliance")
    assert result == True, "EXPECT phase should trigger"

def test_unlazy_gates_evidence_phase_verifies():
    """Test EVIDENCE phase verifies evidence"""
    gate = UnlazyGate("gate_1", "credit_scoring", "Article 50")
    
    valid_evidence = {
        "type": "policy_compliance",
        "confidence": 0.92,
        "citation": "Article 50",
        "timestamp": "2026-09-15T14:23:47Z"
    }
    
    result = gate.verify_evidence(valid_evidence)
    assert result == True, "EVIDENCE phase should verify valid evidence"

def test_permit_gate_blocks_unauthorized_tool():
    """Test permit gate blocks unauthorized tools"""
    permit = PermitGate(GOVERNANCE_RULES)
    
    result = permit.permit_tool_call("update_spec")
    assert result["permitted"] == False, "Permit gate should block update_spec"
    assert "blocked" in result["reason"].lower()

def test_permit_gate_allows_authorized_tool():
    """Test permit gate allows authorized tools"""
    permit = PermitGate(GOVERNANCE_RULES)
    
    result = permit.permit_tool_call("score_credit")
    assert result["permitted"] == True, "Permit gate should allow score_credit"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
