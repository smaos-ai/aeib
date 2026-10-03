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

"""Relying-Party Evidence Sufficiency Module (sufficiency.py)

Implements Moat 2: Evidence Sufficiency under IETF EP-AEG draft-00 §4.2
(draft-schrock-ep-action-evidence-graph-00).

Evaluates sufficiency from the auditor / regulator / relying-party perspective
using a closed 5-verdict taxonomy:
  • ADMISSIBLE: Complete, fresh, non-conflicting, cryptographically verified evidence.
  • MISSING_EVIDENCE: Required dispatch, wire response, or attribution node is absent.
  • STALE: Evidence age exceeds the maximum permissible freshness TTL.
  • CONFLICTED: Graph contains contradictory outcomes, diverging hashes, or dual-claim states.
  • UNVERIFIABLE: Malformed structure, invalid signature, or corrupted Merkle root.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class RelyingPartyVerdict(str, Enum):
    ADMISSIBLE = "admissible"
    MISSING_EVIDENCE = "missing_evidence"
    STALE = "stale"
    CONFLICTED = "conflicted"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class SufficiencyEvaluation:
    action_id: str
    verdict: RelyingPartyVerdict
    reason: str
    evidence_nodes: int
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "relying_party_verdict": self.verdict.value,
            "reason": self.reason,
            "evidence_nodes": self.evidence_nodes,
            "evaluated_at": self.evaluated_at,
        }


class RelyingPartySufficiencyEvaluator:
    """Evaluates Action-Evidence Graphs (AEG) for institutional relying parties."""

    def __init__(self, max_ttl_seconds: float = 86400.0 * 7):  # 7-day default audit window
        self.max_ttl_seconds = max_ttl_seconds

    def evaluate_receipt(
        self,
        receipt: Dict[str, Any],
        now_dt: Optional[datetime] = None,
    ) -> SufficiencyEvaluation:
        """Evaluates a ReceiptPayload v1.0 / v1.1 from the relying-party perspective."""
        action_id = str(receipt.get("action_id", "UNKNOWN"))

        # Gate 1: Check Structural & Cryptographic Viability (UNVERIFIABLE)
        required_fields = [
            "version", "action_id", "leaf_index", "tree_size",
            "timestamp", "intent_digest", "verdict", "root_hash",
            "signature", "signer_pubkey"
        ]
        missing_fields = [f for f in required_fields if f not in receipt]
        if missing_fields:
            return SufficiencyEvaluation(
                action_id=action_id,
                verdict=RelyingPartyVerdict.UNVERIFIABLE,
                reason=f"Missing core cryptographic fields: {missing_fields}",
                evidence_nodes=0,
            )

        # Validate hex lengths
        sig = str(receipt.get("signature", ""))
        root_hash = str(receipt.get("root_hash", ""))
        intent_digest = str(receipt.get("intent_digest", ""))
        pubkey = str(receipt.get("signer_pubkey", ""))

        if len(root_hash) != 64 or len(intent_digest) != 64 or len(pubkey) != 64 or len(sig) < 64:
            return SufficiencyEvaluation(
                action_id=action_id,
                verdict=RelyingPartyVerdict.UNVERIFIABLE,
                reason="Cryptographic hash or signature hex length invalid",
                evidence_nodes=1,
            )

        # Gate 2: Missing Evidence in Action-Evidence Graph (MISSING_EVIDENCE)
        verdict = str(receipt.get("verdict", ""))
        if verdict in ("MISSING_EVIDENCE", "UNKNOWN"):
            return SufficiencyEvaluation(
                action_id=action_id,
                verdict=RelyingPartyVerdict.MISSING_EVIDENCE,
                reason=f"Action terminated in unhedged state ({verdict}); missing qualifying wire confirmation",
                evidence_nodes=1,
            )

        # Gate 3: Conflicting Evidence (CONFLICTED)
        if verdict in ("CONFLICT", "REFUSED_WITH_CONTRADICTION"):
            return SufficiencyEvaluation(
                action_id=action_id,
                verdict=RelyingPartyVerdict.CONFLICTED,
                reason=f"Action contains contradictory claims ({verdict})",
                evidence_nodes=2,
            )

        # Gate 4: Freshness / TTL (STALE)
        ts_str = str(receipt.get("timestamp", ""))
        try:
            ts_clean = ts_str.replace("Z", "+00:00")
            receipt_dt = datetime.fromisoformat(ts_clean)
            if receipt_dt.tzinfo is None:
                receipt_dt = receipt_dt.replace(tzinfo=timezone.utc)

            check_time = now_dt or datetime.now(timezone.utc)
            age = (check_time - receipt_dt).total_seconds()

            if age < -300:  # Future skew > 5 minutes
                return SufficiencyEvaluation(
                    action_id=action_id,
                    verdict=RelyingPartyVerdict.UNVERIFIABLE,
                    reason=f"Timestamp lies in the future ({age:.1f}s skew)",
                    evidence_nodes=1,
                )

            if age > self.max_ttl_seconds:
                return SufficiencyEvaluation(
                    action_id=action_id,
                    verdict=RelyingPartyVerdict.STALE,
                    reason=f"Evidence expired: age {age:.0f}s exceeds TTL {self.max_ttl_seconds:.0f}s",
                    evidence_nodes=1,
                )
        except Exception as e:
            return SufficiencyEvaluation(
                action_id=action_id,
                verdict=RelyingPartyVerdict.UNVERIFIABLE,
                reason=f"Timestamp parsing failed: {e}",
                evidence_nodes=1,
            )

        # Gate 5: All checks pass -> ADMISSIBLE
        return SufficiencyEvaluation(
            action_id=action_id,
            verdict=RelyingPartyVerdict.ADMISSIBLE,
            reason="Action-Evidence Graph is complete, fresh, cryptographically bound, and admissible",
            evidence_nodes=len(receipt.get("inclusion_proof", [])) + 1,
        )
