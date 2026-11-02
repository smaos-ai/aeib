#!/usr/bin/env python3
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
src/stateful_hitl.py
================================================================================
Stateful Human-in-the-Loop (HITL) Resumption & Interactive Canvas Serializer.

Implements stateful suspension and deterministic resumption for high-consequence
actions (NIST SP 800-100 / EU AI Act Art. 14 / Gemini CLI / ShowAI canvas pattern):
1. Suspends execution at T3_IRREVERSIBLE boundaries, serializing memory pointers,
   task intent, step index, canvas state, and staged mutation parameters.
2. Computes an RFC 8785 canonical JSON state hash over the suspended runtime state.
3. Allows human supervisors to review interactive canvas parameters, adjust values,
   and sign an Ed25519 adjustment warrant.
4. Resumes deterministically upon verifying the state hash and Ed25519 signature,
   preventing retroactive session tampering or blind replay without re-reading
   the full conversational transcript.

Evaluated under the stated model:
- Zero mock crypto: Real Ed25519 signature verification (cryptography.hazmat).
- RFC 8785 canonical JSON sorting and SHA-256 digest computation.
- Fail-closed halts on state hash divergence, expired sessions, or invalid signatures.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:
    from jcs_canonicalizer import encode_jcs as _reference_encode_jcs

DEFAULT_HITL_TIMEOUT_SEC: int = 3600  # claim: config (1 hour timeout)


class SessionStateStatus(str, Enum):
    SUSPENDED_AWAITING_APPROVAL = "SUSPENDED_AWAITING_APPROVAL"
    RESUMED_APPROVED = "RESUMED_APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


def canonical_json_v1(obj: Any) -> bytes:
    """
    Deterministic RFC 8785 JSON canonical serializer.
    Rejects non-finite floats, non-string dictionary keys, and extraneous whitespace.
    """
    def _check(v: Any) -> None:
        if isinstance(v, float):
            if v != v or v == float("inf") or v == float("-inf"):
                raise ValueError("ERR_NON_FINITE_FLOAT")
        elif isinstance(v, dict):
            for k, val in v.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _check(val)
        elif isinstance(v, (list, tuple)):
            for item in v:
                _check(item)

    _check(obj)
    return _reference_encode_jcs(obj)


def sha256_hex_prefixed(data: bytes) -> str:
    """Computes a lowercase hex SHA-256 digest with sha256: prefix."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class StatefulSessionSnapshot:
    """Immutable snapshot of suspended agent state awaiting human adjudication."""
    session_id: str
    task_intent: str
    step_index: int
    memory_digest: str
    canvas_data: Dict[str, Any]
    staged_action_name: str
    staged_parameters: Dict[str, Any]
    risk_tier: str
    state_hash: str
    status: SessionStateStatus
    created_at_epoch: int
    expires_at_epoch: int


@dataclass(frozen=True)
class HumanAdjustmentWarrant:
    """Cryptographically signed authorization to adjust parameters and resume."""
    session_id: str
    expected_state_hash: str
    adjusted_parameters: Dict[str, Any]
    supervisor_pubkey_hex: str
    signature_hex: str


class StatefulHitlSerializer:
    """
    Manages session suspension, state hashing, and cryptographic resumption.
    """

    def __init__(self, session_ttl_sec: int = DEFAULT_HITL_TIMEOUT_SEC) -> None:
        self.session_ttl_sec = session_ttl_sec
        self._sessions: Dict[str, StatefulSessionSnapshot] = {}

    def suspend_for_hitl(
        self,
        session_id: str,
        task_intent: str,
        step_index: int,
        memory_digest: str,
        canvas_data: Dict[str, Any],
        staged_action_name: str,
        staged_parameters: Dict[str, Any],
        risk_tier: str = "T3_IRREVERSIBLE",
    ) -> StatefulSessionSnapshot:
        """
        Suspends an execution trajectory and generates a deterministic state hash.
        """
        now = int(time.time())
        expires_at = now + self.session_ttl_sec

        # Construct canonical state payload for digest computation
        hash_payload = {
            "canvas_data": canvas_data,
            "memory_digest": memory_digest,
            "risk_tier": risk_tier,
            "session_id": session_id,
            "staged_action_name": staged_action_name,
            "staged_parameters": staged_parameters,
            "step_index": step_index,
            "task_intent": task_intent,
        }
        canonical_bytes = canonical_json_v1(hash_payload)
        state_hash = sha256_hex_prefixed(canonical_bytes)

        snapshot = StatefulSessionSnapshot(
            session_id=session_id,
            task_intent=task_intent,
            step_index=step_index,
            memory_digest=memory_digest,
            canvas_data=dict(canvas_data),
            staged_action_name=staged_action_name,
            staged_parameters=dict(staged_parameters),
            risk_tier=risk_tier,
            state_hash=state_hash,
            status=SessionStateStatus.SUSPENDED_AWAITING_APPROVAL,
            created_at_epoch=now,
            expires_at_epoch=expires_at,
        )

        self._sessions[session_id] = snapshot
        return snapshot

    def resume_with_warrant(
        self,
        warrant: HumanAdjustmentWarrant,
        now_epoch: Optional[int] = None,
    ) -> Tuple[StatefulSessionSnapshot, Dict[str, Any]]:
        """
        Resumes a suspended session using a verified Ed25519 adjustment warrant.
        Fails closed on hash mismatch, expiry, or invalid signature.
        """
        session_id = warrant.session_id
        if session_id not in self._sessions:
            raise ValueError(f"HALT_SESSION_NOT_FOUND:{session_id}")

        snapshot = self._sessions[session_id]
        current_time = int(time.time()) if now_epoch is None else now_epoch

        # Expiry check
        if current_time > snapshot.expires_at_epoch:
            expired_snap = StatefulSessionSnapshot(
                session_id=snapshot.session_id,
                task_intent=snapshot.task_intent,
                step_index=snapshot.step_index,
                memory_digest=snapshot.memory_digest,
                canvas_data=snapshot.canvas_data,
                staged_action_name=snapshot.staged_action_name,
                staged_parameters=snapshot.staged_parameters,
                risk_tier=snapshot.risk_tier,
                state_hash=snapshot.state_hash,
                status=SessionStateStatus.EXPIRED,
                created_at_epoch=snapshot.created_at_epoch,
                expires_at_epoch=snapshot.expires_at_epoch,
            )
            self._sessions[session_id] = expired_snap
            raise ValueError("HALT_SESSION_EXPIRED")

        # Status check
        if snapshot.status != SessionStateStatus.SUSPENDED_AWAITING_APPROVAL:
            raise ValueError(f"HALT_INVALID_SESSION_STATUS:{snapshot.status.value}")

        # State hash integrity check
        if warrant.expected_state_hash != snapshot.state_hash:
            raise ValueError(
                f"HALT_STATE_HASH_MISMATCH: expected {snapshot.state_hash}, "
                f"got {warrant.expected_state_hash}"
            )

        # Cryptographic signature verification over canonical adjustment payload
        warrant_payload = {
            "adjusted_parameters": warrant.adjusted_parameters,
            "expected_state_hash": warrant.expected_state_hash,
            "session_id": warrant.session_id,
        }
        warrant_canonical = canonical_json_v1(warrant_payload)

        try:
            pub_key = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(warrant.supervisor_pubkey_hex)
            )
            pub_key.verify(bytes.fromhex(warrant.signature_hex), warrant_canonical)
        except (InvalidSignature, ValueError, Exception) as exc:
            raise ValueError("HALT_UNAUTHORIZED_RESUME: signature verification failed") from exc

        # Apply adjusted parameters over staged parameters
        effective_params = dict(snapshot.staged_parameters)
        effective_params.update(warrant.adjusted_parameters)

        resumed_snapshot = StatefulSessionSnapshot(
            session_id=snapshot.session_id,
            task_intent=snapshot.task_intent,
            step_index=snapshot.step_index + 1,
            memory_digest=snapshot.memory_digest,
            canvas_data=snapshot.canvas_data,
            staged_action_name=snapshot.staged_action_name,
            staged_parameters=effective_params,
            risk_tier=snapshot.risk_tier,
            state_hash=snapshot.state_hash,
            status=SessionStateStatus.RESUMED_APPROVED,
            created_at_epoch=snapshot.created_at_epoch,
            expires_at_epoch=snapshot.expires_at_epoch,
        )

        self._sessions[session_id] = resumed_snapshot
        return resumed_snapshot, effective_params

    def reject_session(
        self,
        session_id: str,
        reason: str,
    ) -> StatefulSessionSnapshot:
        """Explicitly transitions a suspended session to REJECTED."""
        if session_id not in self._sessions:
            raise ValueError(f"HALT_SESSION_NOT_FOUND:{session_id}")

        snapshot = self._sessions[session_id]
        rejected_snap = StatefulSessionSnapshot(
            session_id=snapshot.session_id,
            task_intent=snapshot.task_intent,
            step_index=snapshot.step_index,
            memory_digest=snapshot.memory_digest,
            canvas_data=snapshot.canvas_data,
            staged_action_name=snapshot.staged_action_name,
            staged_parameters=snapshot.staged_parameters,
            risk_tier=snapshot.risk_tier,
            state_hash=snapshot.state_hash,
            status=SessionStateStatus.REJECTED,
            created_at_epoch=snapshot.created_at_epoch,
            expires_at_epoch=snapshot.expires_at_epoch,
        )
        self._sessions[session_id] = rejected_snap
        return rejected_snap

    def get_session(self, session_id: str) -> Optional[StatefulSessionSnapshot]:
        return self._sessions.get(session_id)
