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

"""Delegated Capability Attenuation

Enforces Macaroon-style capability subtrees, ensuring downstream agents
strictly narrow authority across tool boundaries.
"""

import hashlib
import json
from typing import Any, Dict, List


class CapabilityAttenuator:
    def mint_root_capability(
        self,
        parent_agent: str,
        tool_allowlist: List[str],
        spending_cap_eur: float,
        ttl_sec: int,
    ) -> Dict[str, Any]:
        token_str = f"{parent_agent}:{sorted(tool_allowlist)}:{spending_cap_eur}:{ttl_sec}"
        sig = hashlib.sha256(token_str.encode()).hexdigest()
        return {
            "depth": 0,
            "issuer": parent_agent,
            "tool_allowlist": sorted(tool_allowlist),
            "spending_cap_eur": spending_cap_eur,
            "ttl_sec": ttl_sec,
            "signature": sig,
        }

    def attenuate_sub_capability(
        self,
        parent_cap: Dict[str, Any],
        child_agent: str,
        requested_tools: List[str],
        requested_cap_eur: float,
    ) -> Dict[str, Any]:
        # Enforce Monotonic Attenuation Rules
        parent_tools = set(parent_cap.get("tool_allowlist", []))
        allowed_tools = sorted([t for t in requested_tools if t in parent_tools])
        allowed_cap = min(requested_cap_eur, float(parent_cap.get("spending_cap_eur", 0.0)))
        allowed_ttl = int(parent_cap.get("ttl_sec", 0)) // 2

        token_str = (
            f"{parent_cap['signature']}:{child_agent}:{allowed_tools}:{allowed_cap}:{allowed_ttl}"
        )
        child_sig = hashlib.sha256(token_str.encode()).hexdigest()

        return {
            "depth": parent_cap["depth"] + 1,
            "issuer": child_agent,
            "parent_sig": parent_cap["signature"],
            "tool_allowlist": allowed_tools,
            "spending_cap_eur": allowed_cap,
            "ttl_sec": allowed_ttl,
            "signature": child_sig,
        }

    def verify_capability(
        self, capability: Dict[str, Any], requested_tool: str, requested_amount: float
    ) -> bool:
        if requested_tool not in capability.get("tool_allowlist", []):
            return False
        if requested_amount > capability.get("spending_cap_eur", 0.0):
            return False
        return True
