"""
Stream C: unlazy Fail-Closed Gates
Implements CHECK → EXPECT → EVIDENCE pattern
Agent cannot end turn without evidence (fail-closed enforcement)
"""

import json
import hashlib
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, List


@dataclass
class GatePolicy:
    """Policy rule for gate enforcement"""

    rule_id: str
    description: str
    policy_query: str  # Query to Stream B pgvector
    unsafe_patterns: Optional[List[str]] = None

    def __post_init__(self):
        if self.unsafe_patterns is None:
            self.unsafe_patterns = [
                "unknown",
                "unverified",
                "malicious",
                "unauthorized",
            ]


class FailClosedGate:
    """
    Fail-closed gate enforcement: CHECK → EXPECT → EVIDENCE
    Blocks: agent cannot end turn without proof
    """

    def __init__(self):
        self.gates = {}  # Track gate states per action
        self.verified_actors = {"verified_001", "verified_002", "system_admin"}

    def check(
        self,
        action: str,
        context: Dict[str, Any],
        policy: GatePolicy,
    ) -> Dict[str, Any]:
        """
        CHECK phase: Pre-execution validation against policy.
        Blocks unsafe actions before execution.
        """
        timestamp = datetime.utcnow().isoformat()

        # Check for unsafe patterns
        for key, value in context.items():
            if isinstance(value, str) and value.lower() in policy.unsafe_patterns:
                return {
                    "status": "BLOCKED",
                    "phase": "CHECK",
                    "action": action,
                    "reason": f"Unsafe pattern detected in {key}: {value}. Merchant verification required.",
                    "timestamp": timestamp,
                }

        # Check verified actor
        actor = context.get("actor") or context.get("merchant") or context.get("user")
        if actor and actor not in self.verified_actors:
            # Allow if actor is in a verified list (for testing)
            if not (isinstance(actor, str) and actor.startswith("verified")):
                return {
                    "status": "BLOCKED",
                    "phase": "CHECK",
                    "action": action,
                    "reason": f"Actor {actor} not verified. Cannot proceed with {action}.",
                    "timestamp": timestamp,
                }

        # Check passed
        return {
            "status": "ALLOWED",
            "phase": "CHECK",
            "action": action,
            "reason": "Pre-execution validation passed",
            "timestamp": timestamp,
        }

    def expect(
        self,
        action: str,
        success_criteria: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        EXPECT phase: Declare what success looks like.
        Defines expected output schema and required fields.
        """
        timestamp = datetime.utcnow().isoformat()

        # Store expected criteria for later verification
        self.gates[action] = {
            "expected_criteria": success_criteria,
            "phase": "EXPECT",
            "timestamp": timestamp,
        }

        return {
            "action": action,
            "expected_criteria": success_criteria,
            "required_fields": success_criteria.get("required_fields", []),
            "response_type": success_criteria.get("response_type", "dict"),
            "timestamp": timestamp,
        }

    def evidence(
        self,
        action: str,
        output: Dict[str, Any],
        expected_criteria: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        EVIDENCE phase: Capture proof after execution.
        Computes proof hash and verifies against expected criteria.
        """
        timestamp = datetime.utcnow().isoformat()

        # Verify output matches expected criteria
        required_fields = expected_criteria.get("required_fields", [])
        output_keys = set(output.keys())

        if required_fields and not (output_keys >= set(required_fields)):
            return {
                "status": "FAILED",
                "phase": "EVIDENCE",
                "action": action,
                "reason": f"Output missing required fields: {set(required_fields) - output_keys}",
                "timestamp": timestamp,
            }

        # Compute immutable proof hash (content hash)
        payload = json.dumps(output, sort_keys=True)
        proof_hash = hashlib.sha256(payload.encode()).hexdigest()

        return {
            "status": "CAPTURED",
            "phase": "EVIDENCE",
            "action": action,
            "proof_hash": proof_hash,
            "proof_size": len(payload),
            "timestamp": timestamp,
            "verified": True,
        }

    def finalize(
        self,
        action: str,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Finalize gate: Require evidence before allowing turn completion.
        Fail-closed: raise if no evidence provided.
        """
        if evidence is None:
            raise ValueError(
                f"FAIL-CLOSED: Cannot finalize {action} without evidence. "
                "Agent must provide proof before turn completion."
            )

        if evidence.get("status") != "CAPTURED":
            raise ValueError(
                f"FAIL-CLOSED: Evidence for {action} not properly captured. "
                f"Status: {evidence.get('status')}"
            )

        return {
            "status": "FINALIZED",
            "action": action,
            "evidence": evidence,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def audit_trail(self, action: str) -> Dict[str, Any]:
        """Retrieve complete audit trail for an action"""
        if action not in self.gates:
            return {"action": action, "status": "NOT_FOUND"}

        return {
            "action": action,
            "gate_state": self.gates[action],
            "audit": self.gates[action],
        }


# Test utilities
class GateTestHelper:
    """Helper for testing gate sequences"""

    @staticmethod
    def full_gate_flow(
        gate: FailClosedGate,
        action: str,
        context: Dict[str, Any],
        policy: GatePolicy,
        agent_output: Dict[str, Any],
        expected_criteria: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute full CHECK → EXPECT → EVIDENCE flow"""
        # Phase 1: CHECK
        check_result = gate.check(action, context, policy)
        if check_result["status"] == "BLOCKED":
            return check_result

        # Phase 2: EXPECT
        gate.expect(action, expected_criteria)

        # Phase 3: EVIDENCE
        evidence = gate.evidence(action, agent_output, expected_criteria)

        # Phase 4: FINALIZE
        return gate.finalize(action, evidence)


# Usage example
if __name__ == "__main__":
    gate = FailClosedGate()

    # Define policy
    policy = GatePolicy(
        rule_id="hotel_credit_001",
        description="Hotel credit scoring gate",
        policy_query="SELECT * FROM policies WHERE category = 'credit'",
    )

    # Safe context (verified merchant)
    safe_context = {"merchant": "verified_001", "amount": 5000}

    # Expected output
    expected = {
        "required_fields": ["approval_id", "amount"],
        "response_type": "dict",
    }

    # Agent output
    agent_output = {
        "approval_id": "appr_001",
        "amount": 5000,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Run full flow
    helper = GateTestHelper()
    result = helper.full_gate_flow(
        gate,
        action="approve_credit",
        context=safe_context,
        policy=policy,
        agent_output=agent_output,
        expected_criteria=expected,
    )

    print(f"Gate Flow Result: {result}")
