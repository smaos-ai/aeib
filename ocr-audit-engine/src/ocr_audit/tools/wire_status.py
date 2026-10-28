"""Tool 1: GetWireStatus — Queries raw socket and transport handshake facts."""

from typing import Any, Dict


def get_wire_status(bundle: Any, trace_id: str) -> Dict[str, Any]:
    """Queries gateway socket logs for raw TCP/HTTP handshake states."""
    for t in getattr(bundle, "traces", []):
        if getattr(t, "action_id", None) == trace_id:
            return {
                "trace_id": trace_id,
                "http_status": getattr(t, "http_status", None),
                "wire_fault": getattr(t, "wire_fault", "NONE"),
                "has_wire_fault": t.has_wire_fault() if hasattr(t, "has_wire_fault") else False,
                "ebpf_action": getattr(t, "record", {}).get("ebpf_action", "ALLOW"),
            }
    return {"trace_id": trace_id, "error": "NOT_FOUND"}
