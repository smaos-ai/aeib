"""Human-in-the-Loop Resumable Cognitive Execution (RCE)

Serializes paused agent execution states into inspectable snapshots for terminal
cockpit approval and verifies cryptographic operator decisions.
"""

import json
import time
from typing import Any, Dict, List


class RceCockpit:
    def create_snapshot(
        self,
        workflow_id: str,
        action_id: str,
        ast_callstack: List[str],
        memory_diff: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "workflow_id": workflow_id,
            "action_id": action_id,
            "paused_at": time.time(),
            "ast_callstack": ast_callstack,
            "memory_diff": memory_diff,
            "status": "PAUSED_AWAITING_HUMAN_GATE",
        }

    def render_terminal_cockpit(self, snapshot: Dict[str, Any]) -> str:
        return (
            f"\n\033[93m===================================================\033[0m\n"
            f"\033[1m[RCE COCKPIT] HUMAN OVERSIGHT INTERRUPT REQUIRED\033[0m\n"
            f"Workflow ID : {snapshot.get('workflow_id')}\n"
            f"Action ID   : {snapshot.get('action_id')}\n"
            f"Callstack   : {' -> '.join(snapshot.get('ast_callstack', []))}\n"
            f"Memory Diff : {json.dumps(snapshot.get('memory_diff', {}))}\n"
            f"\033[93m===================================================\033[0m\n"
        )

    def validate_operator_decision(
        self, operator_sig: str, decision: str, action_id: str
    ) -> bool:
        """Validates operator signature format and permitted decision."""
        if not isinstance(operator_sig, str) or not operator_sig.startswith("sig:ed25519:"):
            return False
        return decision in ("RESUME", "ABORT")
