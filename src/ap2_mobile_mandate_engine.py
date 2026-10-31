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
src/ap2_mobile_mandate_engine.py
================================================================================
Agent Payments Protocol (AP2) Mobile Mandate Engine & Async Authorization Queue.

Evaluated under the stated model:
  - Google Agent Payments Protocol (AP2 v0.2) Open -> Closed Mandate Transitions
  - Asynchronous Out-of-Band Hardware Authorization (Apple Silicon Secure Enclave)
  - RFC 8785 JSON Canonicalization Scheme (JCS) Purity
  - Zero-Float & Monotonic Attempt Fence Invariants

Core Architectural Invariants:
  1. Mandate Stage Integrity:
     A mandate cannot execute payment or irreversible side effects until transitioning
     from OPEN -> PENDING_MOBILE_AUTHORIZATION -> CLOSED_AUTHORIZED via a verified
     hardware warrant from the edge notary.
  2. Bounded Spending & Expiration:
     Every mandate enforces an integer spending cap (spending_cap_minor > 0) and
     an immutable expiration epoch (expires_at_epoch_sec). Expired mandates fail closed.
  3. Replay & Attempt Fencing:
     Each mandate binds a monotonic attempt_fence and a unique intent_caid.
     Attempting to reuse a mandate across different intents or stale fences is blocked.
  4. Out-of-Band Human Veto:
     An operator can explicitly veto a pending mandate from their mobile device,
     permanently transitioning it to VETOED and releasing all latches fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.iphone_enclave_notary_bridge import (
    EnclaveSignedWarrant,
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
    T3LatchReleaseVerdict,
    sha256_jcs_caid,
)
from src.jcs_canonicalizer import encode_jcs


class AP2MandateStage(str, Enum):
    """Lifecycle stages for an AP2 mobile intent mandate."""

    OPEN = "OPEN"
    PENDING_MOBILE_AUTHORIZATION = "PENDING_MOBILE_AUTHORIZATION"
    CLOSED_AUTHORIZED = "CLOSED_AUTHORIZED"
    EXPIRED = "EXPIRED"
    VETOED = "VETOED"


@dataclass(frozen=True)
class AP2IntentMandate:
    """Canonical RFC 8785 AP2 intent mandate bound to mobile authorization."""

    mandate_id: str
    task_id: str
    intent_caid: str
    spending_cap_minor: int  # integer minor units, e.g. cents
    allowed_rails: Tuple[str, ...]
    attempt_fence: int
    expires_at_epoch_sec: int
    stage: AP2MandateStage = AP2MandateStage.OPEN
    enclave_warrant: Optional[Dict[str, Any]] = None
    veto_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.spending_cap_minor, int) or self.spending_cap_minor <= 0:
            raise ValueError("spending_cap_minor must be a positive integer")
        if not isinstance(self.attempt_fence, int) or self.attempt_fence < 1:
            raise ValueError("attempt_fence must be a positive integer >= 1")
        if not isinstance(self.expires_at_epoch_sec, int) or self.expires_at_epoch_sec <= 0:
            raise ValueError("expires_at_epoch_sec must be a positive integer epoch")
        if not self.intent_caid.startswith("sha256:"):
            raise ValueError("intent_caid must be a sha256: prefixed string")

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Returns the canonical dictionary payload for JCS signing."""
        return {
            "mandate_id": self.mandate_id,
            "task_id": self.task_id,
            "intent_caid": self.intent_caid,
            "spending_cap_minor": self.spending_cap_minor,
            "allowed_rails": list(self.allowed_rails),
            "attempt_fence": self.attempt_fence,
            "expires_at_epoch_sec": self.expires_at_epoch_sec,
            "stage": self.stage.value,
        }

    def compute_mandate_caid(self) -> str:
        """Computes the SHA-256 CAID over canonical JCS bytes."""
        canonical_bytes = encode_jcs(self.to_canonical_dict())
        return f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"


class AP2AsyncMobileQueue:
    """
    Thread-safe asynchronous queue for AP2 mobile authorization mandates.
    Supports long-horizon agent batches, lock-screen review, and FaceID verification.
    """

    def __init__(self, pinned_enclave_pubkey_hex: str) -> None:
        if not isinstance(pinned_enclave_pubkey_hex, str) or not pinned_enclave_pubkey_hex.strip():
            raise ValueError("pinned_enclave_pubkey_hex must be a non-empty string")
        self.pinned_pubkey_hex = pinned_enclave_pubkey_hex.strip().lower()
        self._lock = threading.Lock()
        self._mandates: Dict[str, AP2IntentMandate] = {}

    def create_and_enqueue_mandate(
        self,
        task_id: str,
        intent_caid: str,
        spending_cap_minor: int,
        allowed_rails: Sequence[str],
        attempt_fence: int,
        ttl_seconds: int = 3600,
        current_epoch_sec: Optional[int] = None,
        mandate_id: Optional[str] = None,
    ) -> AP2IntentMandate:
        """
        Creates a new AP2 mandate and latches it into PENDING_MOBILE_AUTHORIZATION.
        """
        now_epoch = current_epoch_sec if current_epoch_sec is not None else int(time.time())
        expires_at = now_epoch + ttl_seconds
        mid = mandate_id or f"mandate-ap2-{hashlib.sha256(f'{task_id}:{intent_caid}:{now_epoch}'.encode('utf-8')).hexdigest()[:16]}"

        mandate = AP2IntentMandate(
            mandate_id=mid,
            task_id=task_id,
            intent_caid=intent_caid,
            spending_cap_minor=spending_cap_minor,
            allowed_rails=tuple(sorted(allowed_rails)),
            attempt_fence=attempt_fence,
            expires_at_epoch_sec=expires_at,
            stage=AP2MandateStage.PENDING_MOBILE_AUTHORIZATION,
        )

        with self._lock:
            self._mandates[mid] = mandate

        return mandate

    def get_mandate(self, mandate_id: str) -> Optional[AP2IntentMandate]:
        """Retrieves a mandate by ID."""
        with self._lock:
            return self._mandates.get(mandate_id)

    def list_pending_mandates(self) -> List[AP2IntentMandate]:
        """Lists all mandates currently awaiting mobile authorization."""
        with self._lock:
            return [
                m for m in self._mandates.values()
                if m.stage == AP2MandateStage.PENDING_MOBILE_AUTHORIZATION
            ]

    def resolve_with_hardware_warrant(
        self,
        mandate_id: str,
        warrant_data: Dict[str, Any],
        current_epoch_sec: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[AP2IntentMandate]]:
        """
        Resolves a pending mandate with an iPhone Secure Enclave P-256 warrant.
        Verifies signature, WYSIWYS payload binding, expiration, and key pinning.
        """
        now_epoch = current_epoch_sec if current_epoch_sec is not None else int(time.time())

        with self._lock:
            mandate = self._mandates.get(mandate_id)
            if not mandate:
                return False, "ERR_MANDATE_NOT_FOUND", None

            if mandate.stage != AP2MandateStage.PENDING_MOBILE_AUTHORIZATION:
                return False, f"ERR_INVALID_MANDATE_STAGE_{mandate.stage.value}", mandate

            if now_epoch > mandate.expires_at_epoch_sec:
                expired_mandate = AP2IntentMandate(
                    mandate_id=mandate.mandate_id,
                    task_id=mandate.task_id,
                    intent_caid=mandate.intent_caid,
                    spending_cap_minor=mandate.spending_cap_minor,
                    allowed_rails=mandate.allowed_rails,
                    attempt_fence=mandate.attempt_fence,
                    expires_at_epoch_sec=mandate.expires_at_epoch_sec,
                    stage=AP2MandateStage.EXPIRED,
                )
                self._mandates[mandate_id] = expired_mandate
                return False, "ERR_MANDATE_EXPIRED", expired_mandate

            # Convert mandate to T3ActionProposal for notary verifier
            proposal = T3ActionProposal(
                action_type="AP2_PAYMENT_MANDATE",
                amount_minor=mandate.spending_cap_minor,
                attempt_fence=mandate.attempt_fence,
                expires_at_epoch_sec=mandate.expires_at_epoch_sec,
                intent_caid=mandate.intent_caid,
                operation_id=mandate.mandate_id,
                target_resource=mandate.task_id,
            )

            try:
                warrant = EnclaveSignedWarrant(
                    canonical_payload_utf8=warrant_data["canonical_payload_utf8"],
                    payload_sha256_caid=warrant_data["payload_sha256_caid"],
                    public_key_x963_hex=warrant_data["public_key_x963_hex"],
                    signature_der_hex=warrant_data["signature_der_hex"],
                    algorithm=warrant_data.get("algorithm", "ECDSA_P256_SHA256_SECURE_ENCLAVE"),
                )
            except Exception:
                return False, "ERR_MALFORMED_ENCLAVE_WARRANT", mandate

            verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
                expected_proposal=proposal,
                warrant=warrant,
                pinned_enclave_pubkey_x963_hex=self.pinned_pubkey_hex,
                current_epoch_sec=now_epoch,
            )

            if not verdict.latch_released:
                return False, f"ERR_ENCLAVE_VERIFICATION_FAILED_{verdict.reason_code}", mandate

            closed_mandate = AP2IntentMandate(
                mandate_id=mandate.mandate_id,
                task_id=mandate.task_id,
                intent_caid=mandate.intent_caid,
                spending_cap_minor=mandate.spending_cap_minor,
                allowed_rails=mandate.allowed_rails,
                attempt_fence=mandate.attempt_fence,
                expires_at_epoch_sec=mandate.expires_at_epoch_sec,
                stage=AP2MandateStage.CLOSED_AUTHORIZED,
                enclave_warrant=warrant_data,
            )
            self._mandates[mandate_id] = closed_mandate
            return True, "OK", closed_mandate

    def veto_mandate_from_mobile(
        self,
        mandate_id: str,
        reason: str,
    ) -> Tuple[bool, str, Optional[AP2IntentMandate]]:
        """
        Processes an explicit operator human veto from the mobile lock screen/cockpit.
        """
        with self._lock:
            mandate = self._mandates.get(mandate_id)
            if not mandate:
                return False, "ERR_MANDATE_NOT_FOUND", None

            vetoed_mandate = AP2IntentMandate(
                mandate_id=mandate.mandate_id,
                task_id=mandate.task_id,
                intent_caid=mandate.intent_caid,
                spending_cap_minor=mandate.spending_cap_minor,
                allowed_rails=mandate.allowed_rails,
                attempt_fence=mandate.attempt_fence,
                expires_at_epoch_sec=mandate.expires_at_epoch_sec,
                stage=AP2MandateStage.VETOED,
                veto_reason=reason,
            )
            self._mandates[mandate_id] = vetoed_mandate
            return True, "OK", vetoed_mandate

    def purge_expired(self, current_epoch_sec: Optional[int] = None) -> int:
        """Purges or marks expired mandates."""
        now_epoch = current_epoch_sec if current_epoch_sec is not None else int(time.time())
        purged_count = 0

        with self._lock:
            for mid, m in list(self._mandates.items()):
                if m.stage == AP2MandateStage.PENDING_MOBILE_AUTHORIZATION and now_epoch > m.expires_at_epoch_sec:
                    self._mandates[mid] = AP2IntentMandate(
                        mandate_id=m.mandate_id,
                        task_id=m.task_id,
                        intent_caid=m.intent_caid,
                        spending_cap_minor=m.spending_cap_minor,
                        allowed_rails=m.allowed_rails,
                        attempt_fence=m.attempt_fence,
                        expires_at_epoch_sec=m.expires_at_epoch_sec,
                        stage=AP2MandateStage.EXPIRED,
                    )
                    purged_count += 1

        return purged_count
