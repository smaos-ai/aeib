# Copyright 2026 SovereignNexus Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
