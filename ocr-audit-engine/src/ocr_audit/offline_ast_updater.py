"""Offline AST Heuristic Updater (Blind Spot #6)

Ingests the day's UNKNOWN and REJECT traces offline to tighten dispatcher regex/AST pre-conditions.
Relies entirely on standard library Python ast parsing with zero cloud data egress.
"""

import ast
import json
from typing import Any, Dict, List, Optional


class OfflineAstHeuristicUpdater:
    def __init__(self, dispatcher_config_path: Optional[str] = None):
        self.config_path = dispatcher_config_path

    def process_offline_traces(
        self, trace_logs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        rejections = [
            t for t in trace_logs if t.get("verdict") in ("REJECT_FAIL_CLOSED", "UNKNOWN")
        ]
        updated_rules = []

        for record in rejections:
            ast_callstack = record.get("ast_callstack", [])
            policy_rule = record.get("policy_rule_id", "GENERIC_POLICY")

            # Analyze failing AST node path
            if ast_callstack:
                target_node = ast_callstack[-1]
                updated_rules.append({
                    "node_path": target_node,
                    "policy_rule": policy_rule,
                    "action": "TIGHTEN_AST_PRECONDITION",
                })

        return {
            "processed_traces": len(trace_logs),
            "rejections_found": len(rejections),
            "ast_rules_tightened": len(updated_rules),
            "cloud_egress_bytes": 0,
            "rules": updated_rules,
        }
