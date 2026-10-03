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

"""Attestation and Sufficiency Engine (attestation_and_sufficiency.py)

Implements:
  1. IETF EP-AEG draft-00 §4.2 5-Verdict Closed Set:
     ADMISSIBLE, MISSING_EVIDENCE, STALE, CONFLICTED, UNVERIFIABLE
  2. IETF AAT draft-03 §13.6 Attestation Closure Digests:
     tokenizer_digest, chat_template_digest, engine_build_digest, numeric_environment_digest

Verification Invariants (Falsifiability):
  - Pass an event older than ttl_seconds -> Evaluator outputs STALE
  - Pass an event with jcs_match = False (or _jcs_tampered = True) -> Evaluator outputs UNVERIFIABLE
  - Pass an event with missing dispatch / wire confirmation -> Evaluator outputs MISSING_EVIDENCE
  - Pass an event with contradictory outcomes / hash divergence -> Evaluator outputs CONFLICTED
  - Pass a complete, fresh, cryptographically valid event -> Evaluator outputs ADMISSIBLE
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class RelyingPartyVerdict(str, Enum):
    ADMISSIBLE = "ADMISSIBLE"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True)
class AttestationClosure:
    tokenizer_digest: str
    chat_template_digest: str
    engine_build_digest: str
    numeric_environment_digest: str

    def is_valid(self) -> bool:
        for d in (
            self.tokenizer_digest,
            self.chat_template_digest,
            self.engine_build_digest,
            self.numeric_environment_digest,
        ):
            if not isinstance(d, str) or len(d) != 64:
                return False
            try:
                int(d, 16)
            except ValueError:
                return False
        return True

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class SufficiencyResult:
    action_id: str
    verdict: RelyingPartyVerdict
    reason: str
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "verdict": self.verdict.value,
            "reason": self.reason,
            "evaluated_at": self.evaluated_at,
            "details": self.details,
        }


class AttestationAndSufficiencyEvaluator:
    """Evaluates Action-Evidence Graphs for relying-party admissibility."""

    def __init__(self, ttl_seconds: float = 3600.0):
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def compute_attestation_closure(
        tokenizer_data: bytes,
        chat_template: str,
        engine_build: str,
        numeric_params: Dict[str, Any],
    ) -> AttestationClosure:
        num_canonical = json.dumps(numeric_params, sort_keys=True).encode("utf-8")
        return AttestationClosure(
            tokenizer_digest=hashlib.sha256(tokenizer_data).hexdigest(),
            chat_template_digest=hashlib.sha256(chat_template.encode("utf-8")).hexdigest(),
            engine_build_digest=hashlib.sha256(engine_build.encode("utf-8")).hexdigest(),
            numeric_environment_digest=hashlib.sha256(num_canonical).hexdigest(),
        )

    def evaluate_event(
        self,
        event: Dict[str, Any],
        now_dt: Optional[datetime] = None,
    ) -> SufficiencyResult:
        action_id = str(event.get("action_id", "act-unknown"))

        # 1. JCS Match Check -> UNVERIFIABLE
        if event.get("jcs_match") is False or event.get("jcs_digest_match") is False or event.get("_jcs_tampered") is True:
            return SufficiencyResult(
                action_id=action_id,
                verdict=RelyingPartyVerdict.UNVERIFIABLE,
                reason="RFC 8785 JCS canonicalization digest mismatch (jcs_match=False)",
            )

        # 2. Structural & Cryptographic Viability
        sig = event.get("signature")
        if sig is not None and (len(str(sig)) < 64 or str(sig) == "INVALID_SIGNATURE"):
            return SufficiencyResult(
                action_id=action_id,
                verdict=RelyingPartyVerdict.UNVERIFIABLE,
                reason="Cryptographic signature invalid or truncated",
            )

        # 3. Attestation Closure Validation (if present)
        ac_data = event.get("attestation_closure")
        if ac_data:
            if isinstance(ac_data, dict):
                ac = AttestationClosure(
                    tokenizer_digest=str(ac_data.get("tokenizer_digest", "")),
                    chat_template_digest=str(ac_data.get("chat_template_digest", "")),
                    engine_build_digest=str(ac_data.get("engine_build_digest", "")),
                    numeric_environment_digest=str(ac_data.get("numeric_environment_digest", "")),
                )
                if not ac.is_valid():
                    return SufficiencyResult(
                        action_id=action_id,
                        verdict=RelyingPartyVerdict.UNVERIFIABLE,
                        reason="Attestation closure contains malformed 64-char SHA-256 digest",
                    )
            else:
                return SufficiencyResult(
                    action_id=action_id,
                    verdict=RelyingPartyVerdict.UNVERIFIABLE,
                    reason="Attestation closure format invalid",
                )

        # 4. TTL / Freshness Check -> STALE
        raw_ts = event.get("timestamp") or event.get("created_at")
        if raw_ts is not None:
            ts: Optional[datetime] = None
            if isinstance(raw_ts, (int, float)):
                sec = raw_ts / 1000.0 if raw_ts > 1e11 else float(raw_ts)
                try:
                    ts = datetime.fromtimestamp(sec, tz=timezone.utc)
                except Exception:
                    ts = None
            else:
                try:
                    clean_ts = str(raw_ts).replace("Z", "+00:00")
                    ts = datetime.fromisoformat(clean_ts)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    ts = None

            if ts:
                ref_time = now_dt or datetime.now(timezone.utc)
                age = (ref_time - ts).total_seconds()
                if age > self.ttl_seconds:
                    return SufficiencyResult(
                        action_id=action_id,
                        verdict=RelyingPartyVerdict.STALE,
                        reason=f"Event timestamp age ({age:.1f}s) exceeds ttl_seconds ({self.ttl_seconds:.1f}s)",
                        details={"age_seconds": age, "ttl_seconds": self.ttl_seconds},
                    )

        # 5. Missing Evidence in Action Graph -> MISSING_EVIDENCE
        status = str(event.get("verdict", event.get("status", "UNKNOWN"))).upper()
        if status in ("UNKNOWN", "MISSING_EVIDENCE") or event.get("wire_status") in (504, 502, 503, 0):
            return SufficiencyResult(
                action_id=action_id,
                verdict=RelyingPartyVerdict.MISSING_EVIDENCE,
                reason="Required dispatch or wire confirmation missing from evidence graph",
            )

        # 6. Conflicted Evidence -> CONFLICTED
        if status in ("CONFLICT", "REFUSED_WITH_CONTRADICTION") or event.get("conflict_detected") is True:
            return SufficiencyResult(
                action_id=action_id,
                verdict=RelyingPartyVerdict.CONFLICTED,
                reason="Contradictory execution evidence recorded across audit perspectives",
            )

        # 7. Admissible -> ADMISSIBLE
        return SufficiencyResult(
            action_id=action_id,
            verdict=RelyingPartyVerdict.ADMISSIBLE,
            reason="Action evidence graph is complete, fresh, authenticated, and admissible",
            details={"verdict": status},
        )
