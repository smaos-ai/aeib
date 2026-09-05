"""Unlazy Gates: Fail-Closed Gate Engine for L3 Tooling Layer"""

import json
import logging
from enum import Enum
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class GatePhase(Enum):
    CHECK = "check"
    EXPECT = "expect"
    EVIDENCE = "evidence"

class GateStatus(Enum):
    PASS = "pass"
    BLOCK = "block"
    PENDING_EVIDENCE = "pending_evidence"

class UnlazyGate:
    """Fail-closed gate: CHECK → EXPECT → EVIDENCE"""
    
    def __init__(self, gate_id: str, policy_rule: str, article: str):
        self.gate_id = gate_id
        self.policy_rule = policy_rule
        self.article = article
        self.status = GateStatus.BLOCK  # Default: fail-closed
        
    def check_policy(self, tool_name: str, governance_rules: Dict[str, Any]) -> bool:
        """Phase 1: CHECK - Verify policy rule applies"""
        logger.info(f"CHECK: {self.article} rule for {tool_name}")
        
        if tool_name not in governance_rules:
            logger.warning(f"BLOCK: {tool_name} not in governance rules")
            return False
        
        rule = governance_rules[tool_name]
        if rule.get("blocked"):
            logger.warning(f"BLOCK: {tool_name} marked as blocked in governance")
            return False
        
        logger.info(f"PASS: {tool_name} passes policy CHECK")
        return True
    
    def expect_evidence(self, evidence_type: str) -> bool:
        """Phase 2: EXPECT - Agent must provide evidence"""
        logger.info(f"EXPECT: {evidence_type} evidence required")
        self.status = GateStatus.PENDING_EVIDENCE
        return True
    
    def verify_evidence(self, evidence: Dict[str, Any]) -> bool:
        """Phase 3: EVIDENCE - Verify evidence matches expectation"""
        logger.info(f"EVIDENCE: Verifying evidence payload")
        
        required_fields = ["type", "confidence", "citation", "timestamp"]
        for field in required_fields:
            if field not in evidence:
                logger.error(f"BLOCK: Missing evidence field: {field}")
                return False
        
        confidence = evidence.get("confidence", 0)
        if confidence < 0.8:
            logger.error(f"BLOCK: Confidence {confidence} below threshold 0.8")
            return False
        
        logger.info(f"PASS: Evidence verified (confidence {confidence})")
        self.status = GateStatus.PASS
        return True
    
    def execute_tool(self, tool_name: str, governance_rules: Dict[str, Any], evidence: Optional[Dict] = None) -> Dict[str, Any]:
        """Full gate execution: CHECK → EXPECT → EVIDENCE"""
        
        # Phase 1: CHECK
        if not self.check_policy(tool_name, governance_rules):
            return {
                "status": "blocked",
                "reason": f"Policy CHECK failed for {tool_name}",
                "article": self.article,
                "phase": "CHECK"
            }
        
        # Phase 2: EXPECT (auto-trigger for high-risk operations)
        self.expect_evidence("policy_compliance")
        
        # Phase 3: EVIDENCE (if provided)
        if evidence:
            if not self.verify_evidence(evidence):
                return {
                    "status": "blocked",
                    "reason": "Evidence VERIFICATION failed",
                    "article": self.article,
                    "phase": "EVIDENCE"
                }
        else:
            return {
                "status": "pending_evidence",
                "reason": "Awaiting evidence submission",
                "article": self.article,
                "phase": "EXPECT"
            }
        
        # All phases passed
        return {
            "status": "approved",
            "tool": tool_name,
            "article": self.article,
            "phases": ["CHECK", "EXPECT", "EVIDENCE"]
        }

class PermitGate:
    """Pre-execution permit checking"""
    
    def __init__(self, governance_risks: Dict[str, Any]):
        self.governance_risks = governance_risks
    
    def permit_tool_call(self, tool_name: str) -> Dict[str, Any]:
        """Check if tool is permitted before execution"""
        
        if tool_name not in self.governance_risks:
            return {"permitted": False, "reason": f"Tool {tool_name} not in governance registry"}
        
        rule = self.governance_risks[tool_name]
        
        if rule.get("blocked"):
            return {
                "permitted": False,
                "reason": f"Tool {tool_name} is blocked",
                "policy": rule.get("policy", "unknown"),
                "article": rule.get("article", "unknown")
            }
        
        return {
            "permitted": True,
            "tool": tool_name,
            "policy": rule.get("policy"),
            "article": rule.get("article")
        }

# Example governance rules
GOVERNANCE_RULES = {
    "score_credit": {"blocked": False, "policy": "credit_scoring", "article": "Article 50"},
    "fetch_pms_data": {"blocked": False, "policy": "data_retrieval", "article": "Article 10"},
    "check_sanctions": {"blocked": False, "policy": "sanctions_check", "article": "Article 14"},
    "parse_cad_model": {"blocked": False, "policy": "cad_analysis", "article": "Article 71"},
    "analyze_safety_violations": {"blocked": False, "policy": "safety_assessment", "article": "Article 9"},
    "update_spec": {"blocked": True, "policy": "spec_modification", "article": "Annex I"},  # Blocked: requires human
    "verify_student_records": {"blocked": False, "policy": "record_verification", "article": "Article 35"},
    "check_eligibility": {"blocked": False, "policy": "eligibility_check", "article": "Article 50"},
    "grant_access": {"blocked": True, "policy": "access_grant", "article": "Article 14"},  # Blocked: requires human
}
