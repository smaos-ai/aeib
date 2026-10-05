"""
AEIB Human-Review Interface & ASD-STE100 Console (Zone 1 Prototype)
Formats ambiguous execution states and Ed25519 receipts into simplified plain text
and records human operator disposition decisions.
"""

import time
import json
import hashlib
from typing import Dict, Any, List

class HumanReviewConsole:
    """Provides plain-language ASD-STE100 readbacks and records supervisor intervention trails."""

    def __init__(self):
        self.decision_audit_log: List[Dict[str, Any]] = []

    def format_ste100_summary(self, evidence: Dict[str, Any]) -> str:
        """Translates technical execution state into Simplified Technical English (ASD-STE100)."""
        caid = evidence.get("caid", "UNKNOWN")
        disposition = evidence.get("disposition", "UNKNOWN")
        obs = evidence.get("probe_observation") or {}
        
        lines = [
            "===========================================================",
            "             AEIB HUMAN AUDIT REVIEW SUMMARY               ",
            "===========================================================",
            f"ACTION IDENTIFIER : {caid}",
            f"CURRENT STATUS    : {disposition}",
        ]
        
        if disposition == "OUTCOME_VERIFIED":
            lines.append("EXPLANATION       : The external system finished the task.")
            lines.append("RECOMMENDED ACTION: Clear the quarantine. Do not retry.")
        elif disposition == "RECONCILIATION_NOT_FOUND":
            lines.append("EXPLANATION       : The external system did not execute the task.")
            lines.append("RECOMMENDED ACTION: You may start a clean recovery or retry.")
        elif disposition == "EFFECT_UNKNOWN":
            lines.append("EXPLANATION       : The remote state cannot be confirmed.")
            lines.append("RECOMMENDED ACTION: Inspect the target server manually.")
        else:
            lines.append("EXPLANATION       : System state is non-standard.")
            lines.append("RECOMMENDED ACTION: Hold execution.")

        lines.append("===========================================================")
        return "\n".join(lines)

    def record_human_decision(
        self, caid: str, operator_id: str, decision: str, notes: str = ""
    ) -> Dict[str, Any]:
        """
        Records human intervention. Valid decisions:
        - CONFIRM
        - ESCALATE
        - AUTHORIZE_RECOVERY
        - KEEP_SUSPENDED
        - RESET_LOCKOUT
        """
        valid_decisions = {
            "CONFIRM",
            "ESCALATE",
            "AUTHORIZE_RECOVERY",
            "KEEP_SUSPENDED",
            "RESET_LOCKOUT",
        }
        if decision not in valid_decisions:
            raise ValueError(f"Invalid decision '{decision}'. Must be one of {valid_decisions}")

        record = {
            "caid": caid,
            "operator_id": operator_id,
            "decision": decision,
            "notes": notes,
            "timestamp": time.time(),
        }
        # Compute signature hash of the audit entry
        record_bytes = json.dumps(record, sort_keys=True).encode("utf-8")
        record["audit_digest"] = hashlib.sha256(record_bytes).hexdigest()
        self.decision_audit_log.append(record)
        return record
