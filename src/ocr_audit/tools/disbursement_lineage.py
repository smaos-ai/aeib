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
