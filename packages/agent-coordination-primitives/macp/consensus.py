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

"""
macp.consensus
================================================================================
Gap 5: Quorum Consensus Resolver over RFC 8785 JCS canonicalized finding digests.
Prevents uncoordinated silent overrides by latching split outcomes to INDETERMINATE.
"""

from __future__ import annotations

from collections import Counter
import hashlib
from typing import Any, Dict, List

from macp.idempotency import encode_jcs


class QuorumConsensusResolver:
    """Computes strict majority quorum over verified agent outputs."""

    @staticmethod
    def resolve(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolves 2-of-3 or strict majority consensus. Latches INDETERMINATE upon split."""
        if not results:
            return {
                "status": "INDETERMINATE",
                "reason": "EMPTY_RESULT_SET",
            }

        canonical_map: Dict[str, Dict[str, Any]] = {}
        counts: Counter[str] = Counter()

        for r in results:
            key = hashlib.sha256(encode_jcs(r.get("verified_findings", []))).hexdigest()
            canonical_map[key] = r
            counts[key] += 1

        top_key, top_count = counts.most_common(1)[0]
        quorum_threshold = (len(results) // 2) + 1

        if top_count >= quorum_threshold:
            winner = dict(canonical_map[top_key])
            winner["consensus_quorum"] = f"{top_count}/{len(results)}"
            return winner

        return {
            "status": "INDETERMINATE",
            "reason": "NO_CONSENSUS_QUORUM",
            "conflicting_results": results,
        }
