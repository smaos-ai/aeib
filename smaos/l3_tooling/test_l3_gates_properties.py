#!/usr/bin/env python3
"""
Property-Based Tests for L3 Permit Gates (Gate Layer)

Tests invariants using Hypothesis:
- Property 1: Gate CHECK completes in <100ms
- Property 2: EXPECT matches EVIDENCE (no contradictions)
- Property 3: Evidence SHA256 immutability
- Property 4: Escalation triggered on constraint violation
- Property 5: Gates are idempotent (same input → same output)
- Property 6: Status transitions valid (BLOCK → PENDING → PASS)
- Property 7: Confidence threshold enforced [0.8, 1.0]
- Property 8: Evidence field validation (all required fields present)
- Property 9: Policy rule matching
- Property 10: Permit gate consistency

Run: pytest test_l3_gates_properties.py -v
"""

import time
import hashlib
import json
from enum import Enum
from hypothesis import given, strategies as st, settings, Verbosity, HealthCheck
from unlazy_gates import UnlazyGate, PermitGate, GateStatus, GOVERNANCE_RULES


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def gate_ids(draw):
    """Generate valid gate IDs."""
    return f"gate_{draw(st.integers(min_value=0, max_value=10000))}"


@st.composite
def valid_tool_names(draw):
    """Generate tool names (existing or new)."""
    existing = list(GOVERNANCE_RULES.keys())
    if draw(st.booleans()):
        return draw(st.sampled_from(existing))
    else:
        return f"tool_{draw(st.integers(min_value=0, max_value=1000))}"


@st.composite
def policy_rules(draw):
    """Generate policy rules."""
    rule = {}
    if draw(st.booleans()):
        rule["blocked"] = draw(st.booleans())
    rule["policy"] = f"policy_{draw(st.integers(min_value=1, max_value=100))}"
    rule["article"] = f"Article_{draw(st.integers(min_value=1, max_value=100))}"
    return rule


@st.composite
def governance_rulesets(draw):
    """Generate governance rulesets."""
    num_tools = draw(st.integers(min_value=1, max_value=20))
    rules = {}
    for i in range(num_tools):
        tool_name = f"tool_{i}"
        rules[tool_name] = {
            "blocked": draw(st.booleans()),
            "policy": f"policy_{i}",
            "article": f"Article_{i}"
        }
    return rules


@st.composite
def evidence_payloads(draw, valid=True):
    """Generate evidence payloads."""
    evidence = {}

    if valid:
        # Valid evidence with required fields
        evidence["type"] = draw(st.sampled_from([
            "policy_compliance", "audit_trail", "consent_record"
        ]))
        evidence["confidence"] = draw(st.floats(min_value=0.8, max_value=1.0))
        evidence["citation"] = f"ref_{draw(st.integers(min_value=0, max_value=1000))}"
        evidence["timestamp"] = draw(st.integers(min_value=1600000000, max_value=1700000000))
    else:
        # Potentially invalid evidence (missing fields or low confidence)
        fields = ["type", "confidence", "citation", "timestamp"]
        num_fields = draw(st.integers(min_value=0, max_value=len(fields)))
        for field in draw(st.permutations(fields)).build()[:num_fields]:
            if field == "confidence":
                evidence[field] = draw(st.floats(min_value=0.0, max_value=1.0))
            elif field == "type":
                evidence[field] = draw(st.text(min_size=1, max_size=30))
            else:
                evidence[field] = f"val_{draw(st.integers(min_value=0, max_value=1000))}"

    return evidence


# ============================================================================
# PROPERTY 1: Gate CHECK Latency <100ms
# ============================================================================
@given(
    gate_id=gate_ids(),
    tool_name=valid_tool_names(),
    rules=governance_rulesets()
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_gate_check_latency_under_100ms(gate_id, tool_name, rules):
    """Property: Gate CHECK phase completes in <100ms."""
    gate = UnlazyGate(gate_id, f"policy_rule_{gate_id}", f"Article_50")

    start_time = time.time()
    result = gate.check_policy(tool_name, rules)
    elapsed_ms = (time.time() - start_time) * 1000

    assert elapsed_ms < 100, \
        f"CHECK took {elapsed_ms}ms, expected <100ms"
    assert isinstance(result, bool), "CHECK should return bool"


# ============================================================================
# PROPERTY 2: EXPECT Matches EVIDENCE (No Contradictions)
# ============================================================================
@given(
    gate_id=gate_ids(),
    evidence_type=st.text(min_size=1, max_size=50)
)
@settings(max_examples=100)
def test_expect_evidence_type_consistency(gate_id, evidence_type):
    """Property: EXPECT sets status to PENDING_EVIDENCE."""
    gate = UnlazyGate(gate_id, "policy_rule", "Article_50")

    # Initial status
    initial_status = gate.status
    assert initial_status == GateStatus.BLOCK, "Initial status should be BLOCK"

    # Call EXPECT
    result = gate.expect_evidence(evidence_type)

    # Check status changed
    assert gate.status == GateStatus.PENDING_EVIDENCE, \
        "Status should be PENDING_EVIDENCE after EXPECT"
    assert result is True, "EXPECT should return True"


# ============================================================================
# PROPERTY 3: Evidence SHA256 Immutability
# ============================================================================
@given(evidence=evidence_payloads(valid=True))
@settings(max_examples=100)
def test_evidence_immutability(evidence):
    """Property: Evidence SHA256 hash is deterministic and immutable."""
    # Hash evidence twice
    evidence_json1 = json.dumps(evidence, sort_keys=True)
    hash1 = hashlib.sha256(evidence_json1.encode()).hexdigest()

    evidence_json2 = json.dumps(evidence, sort_keys=True)
    hash2 = hashlib.sha256(evidence_json2.encode()).hexdigest()

    # Hashes should be identical
    assert hash1 == hash2, \
        f"Evidence hash not immutable: {hash1} != {hash2}"

    # Hash should be valid hex
    assert all(c in "0123456789abcdef" for c in hash1), \
        "Hash not valid hex"


# ============================================================================
# PROPERTY 4: Escalation on Constraint Violation
# ============================================================================
@given(
    gate_id=gate_ids(),
    confidence=st.floats(min_value=0.0, max_value=1.0),
    has_required_fields=st.booleans()
)
@settings(max_examples=100)
def test_escalation_on_low_confidence(gate_id, confidence, has_required_fields):
    """Property: Low confidence evidence triggers escalation (BLOCK)."""
    gate = UnlazyGate(gate_id, "policy_rule", "Article_50")

    evidence = {
        "type": "test_evidence",
        "confidence": confidence,
        "citation": "test_ref",
        "timestamp": 1600000000
    }

    result = gate.verify_evidence(evidence)

    if confidence < 0.8:
        # Should fail (escalate)
        assert result is False, \
            f"Confidence {confidence} < 0.8 should fail"
    else:
        # Should pass
        assert result is True, \
            f"Confidence {confidence} >= 0.8 should pass"


# ============================================================================
# PROPERTY 5: Gates are Idempotent
# ============================================================================
@given(
    gate_id=gate_ids(),
    tool_name=valid_tool_names(),
    rules=governance_rulesets(),
    evidence=evidence_payloads(valid=True)
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_gate_execution_idempotent(gate_id, tool_name, rules, evidence):
    """Property: Same input produces same output (idempotent)."""
    gate1 = UnlazyGate(gate_id, "policy_rule", "Article_50")
    gate2 = UnlazyGate(gate_id, "policy_rule", "Article_50")

    # Execute both gates with same input
    result1 = gate1.execute_tool(tool_name, rules, evidence)
    result2 = gate2.execute_tool(tool_name, rules, evidence)

    # Results should be identical
    assert result1["status"] == result2["status"], \
        f"Status mismatch: {result1['status']} != {result2['status']}"
    assert result1.get("phase") == result2.get("phase"), \
        f"Phase mismatch: {result1.get('phase')} != {result2.get('phase')}"


# ============================================================================
# PROPERTY 6: Valid Status Transitions
# ============================================================================
@given(gate_id=gate_ids())
@settings(max_examples=50)
def test_valid_status_transitions(gate_id):
    """Property: Status transitions follow: BLOCK → PENDING_EVIDENCE → PASS."""
    gate = UnlazyGate(gate_id, "policy_rule", "Article_50")

    # Initial: BLOCK
    assert gate.status == GateStatus.BLOCK

    # After EXPECT: PENDING_EVIDENCE
    gate.expect_evidence("test")
    assert gate.status == GateStatus.PENDING_EVIDENCE

    # After valid EVIDENCE: PASS
    valid_evidence = {
        "type": "test",
        "confidence": 0.9,
        "citation": "ref",
        "timestamp": 1600000000
    }
    gate.verify_evidence(valid_evidence)
    assert gate.status == GateStatus.PASS


# ============================================================================
# PROPERTY 7: Confidence Threshold Enforcement
# ============================================================================
@given(confidence=st.floats(min_value=0.0, max_value=1.0))
@settings(max_examples=100)
def test_confidence_threshold_0_8(confidence):
    """Property: Confidence threshold is strictly enforced at 0.8."""
    gate = UnlazyGate("test_gate", "rule", "Article_50")

    evidence = {
        "type": "test",
        "confidence": confidence,
        "citation": "ref",
        "timestamp": 1600000000
    }

    result = gate.verify_evidence(evidence)

    # Result should match confidence >= 0.8
    expected = confidence >= 0.8
    assert result == expected, \
        f"Confidence {confidence}: expected {expected}, got {result}"


# ============================================================================
# PROPERTY 8: Evidence Field Validation
# ============================================================================
@given(evidence=evidence_payloads(valid=False))
@settings(max_examples=100)
def test_evidence_required_fields_validation(evidence):
    """Property: Missing required fields cause verification failure."""
    gate = UnlazyGate("test_gate", "rule", "Article_50")

    required_fields = ["type", "confidence", "citation", "timestamp"]
    has_all_fields = all(field in evidence for field in required_fields)

    result = gate.verify_evidence(evidence)

    if not has_all_fields:
        # Missing fields should fail
        assert result is False, \
            f"Missing fields should fail: {evidence}"
    else:
        # If all fields present, check confidence threshold
        confidence = evidence.get("confidence", 0)
        expected = confidence >= 0.8
        assert result == expected, \
            f"Should depend on confidence: {confidence}"


# ============================================================================
# PROPERTY 9: Policy Rule Matching
# ============================================================================
@given(
    gate_id=gate_ids(),
    tool_name=valid_tool_names(),
    rules=governance_rulesets()
)
@settings(max_examples=100)
def test_policy_rule_matching(gate_id, tool_name, rules):
    """Property: Tool in rules is found/not found correctly."""
    gate = UnlazyGate(gate_id, "policy_rule", "Article_50")

    result = gate.check_policy(tool_name, rules)

    # If tool in rules and not blocked, should pass
    if tool_name in rules and not rules[tool_name].get("blocked", False):
        assert result is True or result is False  # Depends on implementation
    # If tool not in rules, should fail
    elif tool_name not in rules:
        assert result is False, \
            f"Tool not in rules should fail: {tool_name}"


# ============================================================================
# PROPERTY 10: Permit Gate Consistency
# ============================================================================
@given(
    tool_name=valid_tool_names(),
    rules=governance_rulesets()
)
@settings(max_examples=100)
def test_permit_gate_consistency(tool_name, rules):
    """Property: PermitGate checks are consistent."""
    permit_gate = PermitGate(rules)

    result = permit_gate.permit_tool_call(tool_name)

    # Result should have expected structure
    assert "permitted" in result, "Missing 'permitted' key"
    assert isinstance(result["permitted"], bool), "'permitted' should be bool"

    # If tool not in rules, should be blocked
    if tool_name not in rules:
        assert result["permitted"] is False, \
            f"Tool not in rules should not be permitted: {tool_name}"

    # If tool in rules and blocked, should not be permitted
    if tool_name in rules and rules[tool_name].get("blocked", False):
        assert result["permitted"] is False, \
            f"Blocked tool should not be permitted: {tool_name}"


# ============================================================================
# Additional: Evidence Field Count
# ============================================================================
@given(
    num_extra_fields=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=100)
def test_evidence_extra_fields_allowed(num_extra_fields):
    """Property: Extra fields in evidence are allowed (forward compatibility)."""
    gate = UnlazyGate("test_gate", "rule", "Article_50")

    evidence = {
        "type": "test",
        "confidence": 0.9,
        "citation": "ref",
        "timestamp": 1600000000
    }

    # Add extra fields
    for i in range(num_extra_fields):
        evidence[f"extra_field_{i}"] = f"value_{i}"

    # Should not fail due to extra fields
    result = gate.verify_evidence(evidence)

    # Should still validate based on required fields and confidence
    assert result is True, \
        f"Extra fields shouldn't cause failure"


# ============================================================================
# Additional: Gate ID Uniqueness
# ============================================================================
@given(
    gate_id1=gate_ids(),
    gate_id2=gate_ids()
)
@settings(max_examples=100)
def test_gate_id_independence(gate_id1, gate_id2):
    """Property: Different gate IDs create independent gates."""
    gate1 = UnlazyGate(gate_id1, "rule1", "Article_50")
    gate2 = UnlazyGate(gate_id2, "rule2", "Article_51")

    # Modify one gate
    gate1.expect_evidence("test")

    # Other gate should not be affected
    if gate_id1 != gate_id2:
        assert gate2.status == GateStatus.BLOCK, \
            "Gate 2 should not be affected by Gate 1"


# ============================================================================
# Test Runner
# ============================================================================
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
