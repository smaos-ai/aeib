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
