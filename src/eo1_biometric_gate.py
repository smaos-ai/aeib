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
src/eo1_biometric_gate.py
================================================================================
Out-of-Band Physical Biometric Hardware Notary Gate for EO1 Interlock.

Evaluated under the stated model (A18 Pro Secure Enclave + Mac M3 Pro).
Binds out-of-band human biometric authorization (FaceID on physical Apple Silicon)
to the Pre-Dispatch Intent Interlock (EO-1) before irreversible wire mutations.

Architectural Invariants:
  1. Separation of Concerns (arXiv:2607.21325v3):
     - Identity Binding: Bound to the pinned A18 Pro SEP NIST P-256 public key.
     - Request Binding: Bound via strict RFC 8785 JCS canonical bytes (WYSIWYS).
     - Execution Binding: Bound to the Mac M3 Pro PreDispatchIntentInterlock latch.
  2. Fail-Closed Biometric Gating:
     - If the proposed action meets the biometric threshold, zero network bytes
       or mutations proceed without an unexpired, cryptographically verified
       EnclaveSignedWarrant from the physical device.
     - Immediate emergency kill (<10 ms): Explicit operator veto on the iPhone
       returns HALT_HUMAN_VETOED_ON_IPHONE and halts execution fail-closed.
  3. Single-Use Exact Operation Approval Grant:
     - On biometric approval, an OperationApprovalGrant is constructed and
       atomically consumed by the interlock, binding warrant_receipt_caid to
       the verified_proposal_caid and actor_id.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from src.eo1_write_before_execute import (
    OperationApprovalGrant,
    PreDispatchIntentInterlock,
    compute_caid,
)
from src.iphone_enclave_notary_bridge import (
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
    T3LatchReleaseVerdict,
)
from src.iphone_rpc_client import IPhoneNotaryRPCClient
from src.jcs_canonicalizer import encode_jcs


class BiometricGatingError(RuntimeError):
    """Base error for biometric gating refusals."""


class BiometricHumanVetoError(BiometricGatingError):
    """Raised when the operator explicitly vetoes the irreversible action on the iPhone screen."""


class BiometricTimeoutError(BiometricGatingError):
    """Raised when the biometric approval window expires before receiving operator input."""


class BiometricVerificationFailedError(BiometricGatingError):
    """Raised when biometric warrant cryptographic or WYSIWYS verification fails."""


@dataclass(frozen=True)
class BiometricGatePolicy:
    """Policy configuring when out-of-band biometric gating is enforced."""

    action_type_prefix: str = "T3_"
    threshold_amount_minor: int = 100_000  # $1,000.00 in minor units
    timeout_sec: int = 60
    enforce_for_all_irreversible: bool = True

    def requires_biometric_authorization(
        self,
        tool_name: str,
        payload: Any,
    ) -> bool:
        """Determines whether a proposed tool call requires physical FaceID approval."""
        if not self.enforce_for_all_irreversible:
            return False

        if tool_name.startswith(self.action_type_prefix):
            return True

        if isinstance(payload, dict):
            action = str(payload.get("action_type", "")).strip()
            if action.startswith(self.action_type_prefix):
                return True

            amount = payload.get("amount_minor")
            if isinstance(amount, int) and not isinstance(amount, bool):
                if amount >= self.threshold_amount_minor:
                    return True

        return False


class BiometricEO1InterlockAdapter:
    """Binds PreDispatchIntentInterlock to the physical iPhone 16 Pro Max Secure Enclave."""

    def __init__(
        self,
        interlock: PreDispatchIntentInterlock,
        notary_client: IPhoneNotaryRPCClient,
        policy: Optional[BiometricGatePolicy] = None,
        actor_id: str = "agent_orchestrator_alpha",
    ) -> None:
        self.interlock = interlock
        self.notary_client = notary_client
        self.policy = policy or BiometricGatePolicy()
        self.actor_id = actor_id

    def extract_or_build_proposal(
        self,
        target_uri: str,
        tool_name: str,
        payload: Any,
        attempt_fence: int = 1,
        now_epoch_sec: Optional[int] = None,
    ) -> T3ActionProposal:
        """Constructs a typed T3ActionProposal from the intent parameters."""
        now = now_epoch_sec if now_epoch_sec is not None else int(time.time())
        expires_at = now + self.policy.timeout_sec

        action_type = tool_name
        amount_minor = 0

        if isinstance(payload, dict):
            if "action_type" in payload:
                action_type = str(payload["action_type"])
            if "amount_minor" in payload and isinstance(payload["amount_minor"], int):
                amount_minor = payload["amount_minor"]

        intent_caid = compute_caid(payload)
        operation_id = f"op_{intent_caid[:12]}_{attempt_fence}"

        return T3ActionProposal(
            action_type=action_type,
            amount_minor=amount_minor,
            attempt_fence=attempt_fence,
            expires_at_epoch_sec=expires_at,
            intent_caid=intent_caid,
            operation_id=operation_id,
            target_resource=target_uri,
        )

    def dispatch_guarded(
        self,
        target_uri: str,
        tool_name: str,
        payload: Any,
        dispatch_fn: Callable[[], Any],
        attempt_fence: int = 1,
        now_epoch_sec: Optional[int] = None,
        reconciliation_readback_fn: Optional[Callable[[], Any]] = None,
    ) -> Any:
        """Guards execution by requiring physical biometric FaceID approval for T3 actions.

        Workflow:
          1. Checks policy: if biometric is not required, dispatches through standard EO-1.
          2. If required: builds T3ActionProposal and transmits canonical JCS bytes to iPhone.
          3. Awaits FaceID approval or operator VETO on iPhone screen.
          4. Verifies returned warrant on Mac M3 Pro against pinned SEP public key.
          5. Binds warrant receipt into single-use OperationApprovalGrant.
          6. Records DISPATCH_INTENT and executes dispatch_fn().
          7. Records CONTINUITY_RECEIPT upon execution.
        """
        now = now_epoch_sec if now_epoch_sec is not None else int(time.time())

        # Biometric Authorization Required if policy matches
        approval = None
        if self.policy.requires_biometric_authorization(tool_name, payload):
            proposal = self.extract_or_build_proposal(
                target_uri=target_uri,
                tool_name=tool_name,
                payload=payload,
                attempt_fence=attempt_fence,
                now_epoch_sec=now,
            )

            verdict: T3LatchReleaseVerdict = self.notary_client.request_faceid_warrant(
                proposal=proposal,
                timeout_sec=self.policy.timeout_sec,
                current_epoch_sec=now,
            )

            if not verdict.latch_released:
                if verdict.reason_code == "HALT_HUMAN_VETOED_ON_IPHONE":
                    raise BiometricHumanVetoError(
                        f"Action {tool_name} was explicitly vetoed by the operator on iPhone screen."
                    )
                elif verdict.reason_code == "HALT_IPHONE_FACEID_TIMEOUT":
                    raise BiometricTimeoutError(
                        f"Biometric authorization timed out after {self.policy.timeout_sec}s."
                    )
                else:
                    raise BiometricVerificationFailedError(
                        f"Biometric warrant verification failed: {verdict.reason_code}"
                    )

            # Build single-use OperationApprovalGrant bound to warrant receipt
            approval = OperationApprovalGrant(
                approval_id=verdict.warrant_receipt_caid,
                subject_actor_id=self.actor_id,
                tool_name=tool_name,
                operation_caid=compute_caid(payload),
                expires_at_epoch_s=float(proposal.expires_at_epoch_sec),
            )

        return self.interlock.dispatch(
            target_uri=target_uri,
            tool_name=tool_name,
            payload=payload,
            dispatch_fn=dispatch_fn,
            approval=approval,
            actor_id=self.actor_id,
        )
