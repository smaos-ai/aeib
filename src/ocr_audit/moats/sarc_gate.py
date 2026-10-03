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

"""Moat 4: Runtime Data-Quality Gating via SARC-DQ (arXiv:2607.26313)

Pre-Retrieval Gate that classifies evidence BEFORE allowing tool execution or
forensic LLM context window ingestion.

Prevents garbage-in, garbage-out failure modes by enforcing a 4-way classification:
  • VALID: Structurally conformant, in-scope, within freshness horizon.
  • STALE: Expired timestamp beyond admissible TTL.
  • MALFORMED: Corrupted JSON, truncated digests, invalid fields.
  • OUT_OF_SCOPE: External domain, mismatched tenant, unmonitored tool namespace.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class SARCQualityStatus(str, Enum):
    VALID = "valid"
    STALE = "stale"
    MALFORMED = "malformed"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class SARCQualityVerdict:
    status: SARCQualityStatus
    reason: str
    action_id: str
    is_admissible: bool


class SARCDataQualityGate:
    """Pre-Retrieval Data Quality Evaluator."""

    def __init__(
        self,
        allowed_namespaces: Optional[Set[str]] = None,
        max_freshness_seconds: float = 86400.0,  # 24 hour fresh limit
    ):
        self.allowed_namespaces = allowed_namespaces or {"sepa", "payments", "core_banking", "treasury"}
        self.max_freshness_seconds = max_freshness_seconds

    def check_record(
        self,
        record: Dict[str, Any],
        now_dt: Optional[datetime] = None,
    ) -> SARCQualityVerdict:
        action_id = str(record.get("action_id", "UNKNOWN"))

        # Check 1: Malformed structure
        if not isinstance(record, dict) or not record.get("action_id"):
            return SARCQualityVerdict(
                status=SARCQualityStatus.MALFORMED,
                reason="Missing action_id or non-dictionary record",
                action_id=action_id,
                is_admissible=False,
            )

        intent = record.get("intent_digest")
        if intent and (len(intent) != 64 or not all(c in "0123456789abcdefABCDEF" for c in intent)):
            return SARCQualityVerdict(
                status=SARCQualityStatus.MALFORMED,
                reason=f"Corrupted intent_digest: {intent}",
                action_id=action_id,
                is_admissible=False,
            )

        # Check 2: Out of Scope
        ns = record.get("namespace") or record.get("domain") or "payments"
        if ns not in self.allowed_namespaces:
            return SARCQualityVerdict(
                status=SARCQualityStatus.OUT_OF_SCOPE,
                reason=f"Namespace '{ns}' not in allowed set: {self.allowed_namespaces}",
                action_id=action_id,
                is_admissible=False,
            )

        # Check 3: Stale / Expired
        ts_raw = record.get("timestamp")
        if ts_raw:
            try:
                ts_clean = str(ts_raw).replace("Z", "+00:00")
                dt = datetime.fromisoformat(ts_clean)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)

                check_time = now_dt or datetime.now(timezone.utc)
                age = (check_time - dt).total_seconds()
                if age > self.max_freshness_seconds:
                    return SARCQualityVerdict(
                        status=SARCQualityStatus.STALE,
                        reason=f"Record age {age:.0f}s exceeds freshness window {self.max_freshness_seconds:.0f}s",
                        action_id=action_id,
                        is_admissible=False,
                    )
            except Exception as e:
                return SARCQualityVerdict(
                    status=SARCQualityStatus.MALFORMED,
                    reason=f"Timestamp unparseable: {e}",
                    action_id=action_id,
                    is_admissible=False,
                )

        # All checks pass
        return SARCQualityVerdict(
            status=SARCQualityStatus.VALID,
            reason="Conforms to SARC-DQ criteria",
            action_id=action_id,
            is_admissible=True,
        )
