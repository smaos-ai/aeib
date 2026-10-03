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
