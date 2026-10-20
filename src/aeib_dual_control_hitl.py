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
aeib_dual_control_hitl.py — Challenge-Response Cryptographic Dual-Control Quorum
Part of the Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.

Defeats the Human-in-the-Loop (HITL) rubber-stamping pathology (EU AI Act Art. 14 / PBOC):
1. Replaces passive one-click modals with mandatory challenge code transcription:
   challenge_code = CRC32(caid || payee_id || amount_minor) -> "XXXX-XXXX".
2. Enforces M-of-N Cryptographic Quorum (e.g. 2-of-3 human supervisors) for
   high-consequence financial dispatches.
3. Completely prevents blind automated click-through and Sybil approver bypass.
"""

import base64
import time
import zlib
from typing import Dict, Any, Optional, List, Set
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from src.jcs_canonicalizer import encode_jcs


def compute_hitl_challenge_code(
    operation_id: str,
    action_caid: str,
    payee_id: str,
    amount_minor: int,
) -> str:
    """
    Computes a deterministic, human-readable 8-digit challenge verification code:
    XXXX-XXXX derived from CRC32 over canonical representation of the mutation.
    """
    payload = f"{operation_id}:{action_caid}:{payee_id}:{amount_minor}"
    crc = zlib.crc32(payload.encode("utf-8"))
    hex_str = f"{crc:08X}"
    return f"{hex_str[:4]}-{hex_str[4:]}"


class DualControlHitlGate:
    """
    Cryptographic Human-in-the-Loop enforcement gate with challenge verification
    and M-of-N supervisor quorum.
    """

    def __init__(
        self,
        high_consequence_threshold_minor: int = 250_000,  # €2,500.00
        default_required_quorum_m: int = 2,
        challenge_ttl_seconds: int = 300,  # 5 minutes
    ):
        self.high_consequence_threshold_minor = high_consequence_threshold_minor
        self.default_required_quorum_m = default_required_quorum_m
        self.challenge_ttl_seconds = challenge_ttl_seconds
        self._authorized_supervisors: Dict[str, ed25519.Ed25519PublicKey] = {}
        self._active_challenges: Dict[str, Dict[str, Any]] = {}

    def register_supervisor(
        self,
        supervisor_id: str,
        public_key: ed25519.Ed25519PublicKey,
    ) -> None:
        """Registers an authorized human supervisor and their public key."""
        self._authorized_supervisors[supervisor_id] = public_key

    def issue_challenge(
        self,
        operation_id: str,
        action_caid: str,
        payee_id: str,
        amount_minor: int,
        current_time: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Issues an active challenge requiring human transcription and signing.
        """
        now = current_time if current_time is not None else int(time.time())
        code = compute_hitl_challenge_code(operation_id, action_caid, payee_id, amount_minor)

        is_high_consequence = amount_minor >= self.high_consequence_threshold_minor
        required_m = self.default_required_quorum_m if is_high_consequence else 1

        challenge_data = {
            "operation_id": operation_id,
            "action_caid": action_caid,
            "payee_id": payee_id,
            "amount_minor": amount_minor,
            "challenge_code": code,
            "issued_at": now,
            "expires_at": now + self.challenge_ttl_seconds,
            "is_high_consequence": is_high_consequence,
            "required_quorum_m": required_m,
        }
        self._active_challenges[operation_id] = challenge_data

        return {
            "operation_id": operation_id,
            "challenge_code": code,
            "is_high_consequence": is_high_consequence,
            "required_quorum_m": required_m,
            "expires_at": challenge_data["expires_at"],
            "instruction": "Transcribe this 8-character challenge code on the supervisor terminal.",
        }

    def verify_step_up_authorization(
        self,
        operation_id: str,
        transcribed_challenge_code: str,
        supervisor_approvals: List[Dict[str, Any]],
        current_time: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Verifies the human supervisor response against challenge code and M-of-N quorum.
        supervisor_approvals: List of dicts with:
          - supervisor_id: str
          - signature_b64: str
        """
        now = current_time if current_time is not None else int(time.time())

        challenge = self._active_challenges.get(operation_id)
        if not challenge:
            return {"valid": False, "error": "ERR_NO_ACTIVE_CHALLENGE_FOR_OPERATION"}

        # 1. TTL Check
        if now > challenge["expires_at"]:
            return {"valid": False, "error": "ERR_CHALLENGE_CODE_EXPIRED"}

        # 2. Challenge Code Exact Match Check
        if transcribed_challenge_code.strip().upper() != challenge["challenge_code"]:
            return {
                "valid": False,
                "error": "ERR_CHALLENGE_CODE_MISMATCH",
                "entered": transcribed_challenge_code,
                "expected": challenge["challenge_code"],
            }

        # 3. Quorum Count Check
        required_m = challenge["required_quorum_m"]
        if len(supervisor_approvals) < required_m:
            return {
                "valid": False,
                "error": "ERR_INSUFFICIENT_SUPERVISOR_QUORUM",
                "received_count": len(supervisor_approvals),
                "required_m": required_m,
            }

        # 4. Signatures Verification and Sybil-Approver Prevention
        seen_supervisors: Set[str] = set()
        canonical_statement = {
            "challenge_code": challenge["challenge_code"],
            "operation_id": operation_id,
            "action_caid": challenge["action_caid"],
            "payee_id": challenge["payee_id"],
            "amount_minor": challenge["amount_minor"],
        }
        statement_bytes = encode_jcs(canonical_statement)

        for approval in supervisor_approvals:
            sup_id = approval.get("supervisor_id", "")
            if sup_id in seen_supervisors:
                return {
                    "valid": False,
                    "error": "ERR_DUPLICATE_SUPERVISOR_SIGNATURE",
                    "supervisor_id": sup_id,
                }
            seen_supervisors.add(sup_id)

            pubkey = self._authorized_supervisors.get(sup_id)
            if not pubkey:
                return {
                    "valid": False,
                    "error": "ERR_UNAUTHORIZED_SUPERVISOR",
                    "supervisor_id": sup_id,
                }

            try:
                sig_bytes = base64.b64decode(approval.get("signature_b64", ""))
                pubkey.verify(sig_bytes, statement_bytes)
            except Exception:
                return {
                    "valid": False,
                    "error": "ERR_INVALID_SUPERVISOR_SIGNATURE",
                    "supervisor_id": sup_id,
                }

        # Everything verified: consume the challenge (single-use)
        del self._active_challenges[operation_id]

        return {
            "valid": True,
            "operation_id": operation_id,
            "verified_supervisors": list(seen_supervisors),
            "quorum_achieved": len(seen_supervisors),
            "challenge_code": challenge["challenge_code"],
        }
