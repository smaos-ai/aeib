# Copyright 2026 SovereignNexus Project
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
src/a2a_trajectory_interlock.py — Agent-to-Agent Delegation Taint & SEMA-Auto Trajectory Drift Interlock

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Core Capabilities:
1. Monotonic delegation taint propagation (child agents cannot launder or lower parent taint).
2. Monotonic scope confinement (child agents cannot escalate egress host scope beyond parent).
3. SEMA-Auto multi-turn trajectory drift governance using Jaccard distance in integer basis points (0..10000 bps).
4. Content-Addressed Action provenance chains using RFC 8785 single-source JCS.

Zero floats, pure integer rational basis points, deterministic cryptographic validation.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from src.jcs_canonicalizer import encode_jcs as _encode_jcs


def sha256_jcs_caid(payload: Any) -> str:
    """Computes a deterministic Content-Addressed Identifier (CAID) using RFC 8785 JCS."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = _encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


COMMON_STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "for", "in", "on", "at", "to", "from",
    "with", "by", "of", "as", "is", "it", "this", "that"
}


# ---------------------------------------------------------------------------
# Core Token and Turn Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentDelegationToken:
    """Cryptographically anchored delegation grant binding parent, child, hosts, and taint level."""
    parent_spiffe_id: str
    child_spiffe_id: str
    parent_caid: str
    allowed_egress_hosts: Tuple[str, ...]
    taint_level: int  # 0..3: 0=Clean, 1=Untrusted, 2=Elevated, 3=Compromised
    delegation_caid: str

    def __post_init__(self) -> None:
        if not self.parent_spiffe_id.startswith("spiffe://"):
            raise ValueError(f"ERR_INVALID_PARENT_SPIFFE:{self.parent_spiffe_id}")
        if not self.child_spiffe_id.startswith("spiffe://"):
            raise ValueError(f"ERR_INVALID_CHILD_SPIFFE:{self.child_spiffe_id}")
        if not self.parent_caid.startswith("sha256:"):
            raise ValueError(f"ERR_INVALID_PARENT_CAID:{self.parent_caid}")
        if self.taint_level not in (0, 1, 2, 3):
            raise ValueError(f"ERR_INVALID_TAINT_LEVEL:{self.taint_level}")
        if not self.delegation_caid.startswith("sha256:"):
            raise ValueError(f"ERR_INVALID_DELEGATION_CAID:{self.delegation_caid}")


@dataclass(frozen=True)
class TrajectoryTurnRecord:
    """Recorded step in an agent trajectory session evaluated for SEMA-Auto drift."""
    turn_index: int
    turn_intent: str
    action_caid: str
    drift_bps: int  # 0..10000 bps
    verdict: str  # "OK_TRAJECTORY_ALIGNED" | "HALT_TRAJECTORY_DRIFT_EXCEEDED"
    record_caid: str


class A2ATrajectoryInterlock:
    """
    Coordinates Agent-to-Agent delegation chains, monotonic taint containment,
    and SEMA-Auto multi-turn trajectory drift governance.
    """

    def __init__(self, max_drift_threshold_bps: int = 4000) -> None:
        if max_drift_threshold_bps < 0 or max_drift_threshold_bps > 10000:
            raise ValueError(f"ERR_INVALID_DRIFT_THRESHOLD:{max_drift_threshold_bps}")

        self.max_drift_threshold_bps = max_drift_threshold_bps

        # root_spiffe_id -> allowed_hosts
        self._root_authorities: Dict[str, Set[str]] = {}
        # child_spiffe_id -> AgentDelegationToken
        self._delegation_tokens: Dict[str, AgentDelegationToken] = {}
        # session_id -> list of turns
        self._session_turns: Dict[str, List[TrajectoryTurnRecord]] = {}

    def register_root_authority(self, spiffe_id: str, allowed_egress_hosts: List[str]) -> None:
        if not spiffe_id.startswith("spiffe://"):
            raise ValueError(f"ERR_INVALID_SPIFFE_ID:{spiffe_id}")
        self._root_authorities[spiffe_id] = set(allowed_egress_hosts)

    def register_delegation(
        self,
        parent_spiffe_id: str,
        child_spiffe_id: str,
        parent_caid: str,
        allowed_egress_hosts: List[str],
        requested_child_taint: int = 0,
    ) -> AgentDelegationToken:
        """
        Issues a delegation token to a child agent.
        Enforces monotonic scope confinement (subset of parent hosts) and
        monotonic taint elevation (child cannot lower taint below parent level).
        """
        if parent_spiffe_id in self._root_authorities:
            parent_allowed = self._root_authorities[parent_spiffe_id]
            parent_taint = 0
        elif parent_spiffe_id in self._delegation_tokens:
            parent_token = self._delegation_tokens[parent_spiffe_id]
            parent_allowed = set(parent_token.allowed_egress_hosts)
            parent_taint = parent_token.taint_level
        else:
            raise KeyError(f"ERR_UNREGISTERED_PARENT_PRINCIPAL:{parent_spiffe_id}")

        # Scope Confinement: Child cannot request egress hosts parent does not possess
        child_hosts_set = set(allowed_egress_hosts)
        if not child_hosts_set.issubset(parent_allowed):
            forbidden = child_hosts_set - parent_allowed
            raise PermissionError(
                f"ERR_DELEGATION_HOST_ESCALATION_FORBIDDEN: child requested {forbidden} outside parent scope"
            )

        # Monotonic Taint: Child cannot launder or lower taint below parent's level
        effective_taint = max(parent_taint, requested_child_taint)

        sorted_hosts = tuple(sorted(allowed_egress_hosts))
        delegation_payload = {
            "allowed_egress_hosts": list(sorted_hosts),
            "child_spiffe_id": child_spiffe_id,
            "parent_caid": parent_caid,
            "parent_spiffe_id": parent_spiffe_id,
            "taint_level": effective_taint,
        }
        del_caid = sha256_jcs_caid(delegation_payload)

        token = AgentDelegationToken(
            parent_spiffe_id=parent_spiffe_id,
            child_spiffe_id=child_spiffe_id,
            parent_caid=parent_caid,
            allowed_egress_hosts=sorted_hosts,
            taint_level=effective_taint,
            delegation_caid=del_caid,
        )
        self._delegation_tokens[child_spiffe_id] = token
        return token

    def validate_delegated_egress(
        self, child_spiffe_id: str, target_host: str, action_caid: str
    ) -> Tuple[bool, str]:
        """
        Audits child agent egress request:
        1. Verifies valid delegation exists.
        2. Blocks all egress if child taint level indicates compromise (>= 3).
        3. Enforces that target host is within delegated scope.
        """
        if child_spiffe_id not in self._delegation_tokens:
            return False, "HALT_UNREGISTERED_CHILD_AGENT"

        token = self._delegation_tokens[child_spiffe_id]

        if token.taint_level >= 3:
            return False, "HALT_COMPROMISED_TAINT_BLOCKED"

        if target_host not in token.allowed_egress_hosts:
            return False, f"HALT_EGRESS_HOST_NOT_DELEGATED:{target_host}"

        return True, "OK_DELEGATED_EGRESS_PERMITTED"

    def record_trajectory_turn(
        self, session_id: str, turn_intent: str, action_caid: str
    ) -> TrajectoryTurnRecord:
        """
        Records a trajectory turn and computes SEMA-Auto semantic drift
        against the root intent (Turn 0) using Jaccard distance in integer basis points (0..10000 bps).
        """
        turns = self._session_turns.setdefault(session_id, [])
        turn_idx = len(turns)

        if turn_idx == 0:
            drift_bps = 0
            verdict = "OK_TRAJECTORY_ALIGNED"
        else:
            root_intent = turns[0].turn_intent
            words_root = set(re.findall(r"\w+", root_intent.lower())) - COMMON_STOPWORDS
            words_curr = set(re.findall(r"\w+", turn_intent.lower())) - COMMON_STOPWORDS

            union_len = len(words_root | words_curr)
            if union_len == 0:
                sim_bps = 10000  # claim: assumption
            else:
                inter_len = len(words_root & words_curr)
                sim_bps = (inter_len * 10000) // union_len

            drift_bps = 10000 - sim_bps

            if drift_bps > self.max_drift_threshold_bps:
                verdict = "HALT_TRAJECTORY_DRIFT_EXCEEDED"
            else:
                verdict = "OK_TRAJECTORY_ALIGNED"

        payload = {
            "action_caid": action_caid,
            "drift_bps": drift_bps,
            "session_id": session_id,
            "turn_index": turn_idx,
            "turn_intent": turn_intent,
            "verdict": verdict,
        }
        rec_caid = sha256_jcs_caid(payload)

        record = TrajectoryTurnRecord(
            turn_index=turn_idx,
            turn_intent=turn_intent,
            action_caid=action_caid,
            drift_bps=drift_bps,
            verdict=verdict,
            record_caid=rec_caid,
        )
        turns.append(record)
        return record
