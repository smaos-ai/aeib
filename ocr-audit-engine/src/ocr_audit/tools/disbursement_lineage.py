"""Tool 4: InspectDisbursementLineage — Cross-references commit transaction IDs (xid)."""

from typing import Any, Dict


def inspect_disbursement_lineage(bundle: Any, action_id: str) -> Dict[str, Any]:
    """Cross-references database commit transaction IDs (xid) or charge hashes."""
    facts = getattr(bundle, "wire_facts", {})
    xids = facts.get("commit_xids", [])
    confirmed_count = facts.get("confirmed_count", 0)
    double_execution = confirmed_count > 1 and len(xids) > 1

    return {
        "action_id": action_id,
        "unique_xid_count": len(xids),
        "commit_xids": xids,
        "confirmed_count": confirmed_count,
        "double_execution_risk": double_execution,
    }
