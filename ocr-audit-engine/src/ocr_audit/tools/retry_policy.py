"""Tool 3: CheckRetryPolicy — Verifies if agent harness respected retry pause invariants."""

from typing import Any, Dict


def check_retry_policy(bundle: Any, action_id: str) -> Dict[str, Any]:
    """Verifies whether the agent harness respected retry_held: true during transport failures."""
    wire_fault_seen = False
    unheld_retry = False
    violating_lines = []

    for t in getattr(bundle, "traces", []):
        if t.has_wire_fault():
            wire_fault_seen = True
        elif wire_fault_seen:
            retry_held = getattr(t, "record", {}).get("retry_held", False)
            if not retry_held and getattr(t, "claimed_verdict", "") in ("CONFIRMED", "EXECUTED", "RETRYING"):
                unheld_retry = True
                violating_lines.append(getattr(t, "line_no", 0))

    return {
        "action_id": action_id,
        "wire_fault_seen": wire_fault_seen,
        "unheld_retry_storm": unheld_retry,
        "violating_lines": violating_lines,
    }
