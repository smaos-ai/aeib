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
src/live_biometric_latch_bridge.py
================================================================================
Live Biometric Latch Bridge & End-to-End Hardware Notary Orchestration Engine.

Evaluated under the stated model:
  - Jidoka Factory Station 2 (EO1 Pre-Execution Latch) Integration
  - Zero-Egress On-Device Edge AI Pre-Screening & Anomaly Critic
  - AP2 Asynchronous Mobile Intent Mandate Lifecycle
  - Apple Silicon Secure Enclave NIST P-256 (secp256r1) Hardware Verification
  - Zero-Float RFC 8785 JSON Canonicalization Scheme (JCS) and SHA-256 CAIDs

Core Architectural Invariants:
  1. Fail-Closed Latch Integrity:
     Any high-risk mutation or indeterminate effect cannot release the execution
     latch without valid out-of-band biometric approval or pre-screen pass.
  2. Edge Critic Pre-Screening Gate:
     Evaluates proposal before operator prompt. If critical risk (>= 8000 bps)
     is detected, the gate fails closed with RECOMMEND_VETO.
  3. WYSIWYS Hardware Binding:
     The Secure Enclave signs byte-exact RFC 8785 canonical bytes displayed to
     the human operator, binding operation_id, intent_caid, and attempt_fence.
  4. Monotonic Attempt Fencing:
     Each biometric release warrant binds an integer attempt fence to prevent
     replay across long-horizon agent batches.
"""

from __future__ import annotations

import hashlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.ap2_mobile_mandate_engine import (
    AP2AsyncMobileQueue,
    AP2IntentMandate,
    AP2MandateStage,
)
from src.edge_ai_prescreener import (
    EdgeAIPrescreener,
    EdgePrescreenReport,
    PrescreenRecommendation,
)
from src.iphone_enclave_notary_bridge import (
    EnclaveSignedWarrant,
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
    T3LatchReleaseVerdict,
    sha256_jcs_caid,
)
from src.jcs_canonicalizer import encode_jcs

MAX_FAIL_CLOSED_RISK_BPS = 10000  # claim: config


@dataclass(frozen=True)
class BiometricGateSubmission:
    """Result of submitting a high-risk proposal to the biometric bridge."""

    mandate_id: str
    operation_id: str
    latch_status: str
    is_pending: bool
    risk_score_bps: int
    recommendation: str
    summary_sentence_1: str
    critique_sentence_2: str
    prescreen_report_caid: str
    submission_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "critique_sentence_2": self.critique_sentence_2,
            "is_pending": self.is_pending,
            "latch_status": self.latch_status,
            "mandate_id": self.mandate_id,
            "operation_id": self.operation_id,
            "prescreen_report_caid": self.prescreen_report_caid,
            "recommendation": self.recommendation,
            "risk_score_bps": self.risk_score_bps,
            "submission_caid": self.submission_caid,
            "summary_sentence_1": self.summary_sentence_1,
        }


@dataclass(frozen=True)
class BiometricAdjudicationReceipt:
    """Cryptographic receipt for biometric latch adjudication."""

    adjudication_caid: str
    latch_released: bool
    status_code: str
    mandate_id: str
    operation_id: str
    attempt_fence: int
    risk_score_bps: int
    adjudication_epoch_sec: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adjudication_caid": self.adjudication_caid,
            "adjudication_epoch_sec": self.adjudication_epoch_sec,
            "attempt_fence": self.attempt_fence,
            "latch_released": self.latch_released,
            "mandate_id": self.mandate_id,
            "operation_id": self.operation_id,
            "risk_score_bps": self.risk_score_bps,
            "status_code": self.status_code,
        }


class LiveBiometricLatchBridge:
    """
    Coordinates edge AI pre-screening, AP2 mandate queuing, and Mac Enclave
    hardware signature verification to govern high-risk execution latches.
    """

    def __init__(
        self,
        queue: AP2AsyncMobileQueue,
        prescreener: EdgeAIPrescreener,
        pinned_enclave_pubkey_x963_hex: str,
    ) -> None:
        if not isinstance(pinned_enclave_pubkey_x963_hex, str):
            raise ValueError("ERR_INVALID_PINNED_PUBKEY")
        if not pinned_enclave_pubkey_x963_hex.strip():
            raise ValueError("ERR_INVALID_PINNED_PUBKEY")
        self.queue = queue
        self.prescreener = prescreener
        self.pinned_pubkey_hex = pinned_enclave_pubkey_x963_hex.strip().lower()
        self._proposals: Dict[str, Tuple[T3ActionProposal, EdgePrescreenReport]] = {}

    def _get_current_epoch_sec(self, override_epoch: Optional[int]) -> int:
        return override_epoch if override_epoch is not None else int(time.time())

    @staticmethod
    def _compute_ttl(expires_at_epoch_sec: int, now_epoch: int) -> int:
        remaining = expires_at_epoch_sec - now_epoch
        if remaining < 60:
            return 60
        return remaining

    @staticmethod
    def _resolve_spending_cap(amount_minor: int) -> int:
        return max(1, amount_minor)

    def propose_high_risk_action(
        self,
        proposal: T3ActionProposal,
        allowed_rails: Sequence[str] = ("sepa_instant", "local_posix_exec"),
        current_epoch_sec: Optional[int] = None,
    ) -> BiometricGateSubmission:
        """
        Processes a high-risk action proposal:
        1. Executes on-device edge AI pre-screening to detect anomalies.
        2. Evaluates recommendation: if RECOMMEND_VETO, immediately locks latch.
        3. Otherwise, enqueues an AP2 mandate for mobile lock-screen review.
        """
        now_epoch = self._get_current_epoch_sec(current_epoch_sec)

        # 1. Edge AI Pre-Screening
        report = self.prescreener.prescreen_proposal(
            action_type=proposal.action_type,
            target_resource=proposal.target_resource,
            amount_minor=proposal.amount_minor,
            expires_at_epoch_sec=proposal.expires_at_epoch_sec,
            current_epoch_sec=now_epoch,
            operation_id=proposal.operation_id,
        )

        mandate_id = f"mandate-{proposal.operation_id}"
        self._proposals[mandate_id] = (proposal, report)

        # 2. Check for Critic Veto
        if report.recommendation == PrescreenRecommendation.RECOMMEND_VETO:
            payload = {
                "latch_status": "LATCH_LOCKED_CRITIC_VETO",
                "mandate_id": mandate_id,
                "operation_id": proposal.operation_id,
                "risk_score_bps": report.risk_score_bps,
            }
            sub_caid = sha256_jcs_caid(payload)
            return BiometricGateSubmission(
                mandate_id=mandate_id,
                operation_id=proposal.operation_id,
                latch_status="LATCH_LOCKED_CRITIC_VETO",
                is_pending=False,
                risk_score_bps=report.risk_score_bps,
                recommendation=report.recommendation.value,
                summary_sentence_1=report.sentence_1_summary,
                critique_sentence_2=report.sentence_2_critique,
                prescreen_report_caid=report.report_caid,
                submission_caid=sub_caid,
            )

        # 3. Enqueue into AP2 Mobile Authorization Queue
        ttl_sec = self._compute_ttl(proposal.expires_at_epoch_sec, now_epoch)
        cap = self._resolve_spending_cap(proposal.amount_minor)
        self.queue.create_and_enqueue_mandate(
            task_id=proposal.operation_id,
            intent_caid=proposal.intent_caid,
            spending_cap_minor=cap,
            allowed_rails=allowed_rails,
            attempt_fence=proposal.attempt_fence,
            ttl_seconds=ttl_sec,
            current_epoch_sec=now_epoch,
            mandate_id=mandate_id,
        )

        sub_payload = {
            "latch_status": "LATCH_PENDING_MOBILE_AUTHORIZATION",
            "mandate_id": mandate_id,
            "operation_id": proposal.operation_id,
            "risk_score_bps": report.risk_score_bps,
        }
        sub_caid = sha256_jcs_caid(sub_payload)

        return BiometricGateSubmission(
            mandate_id=mandate_id,
            operation_id=proposal.operation_id,
            latch_status="LATCH_PENDING_MOBILE_AUTHORIZATION",
            is_pending=True,
            risk_score_bps=report.risk_score_bps,
            recommendation=report.recommendation.value,
            summary_sentence_1=report.sentence_1_summary,
            critique_sentence_2=report.sentence_2_critique,
            prescreen_report_caid=report.report_caid,
            submission_caid=sub_caid,
        )

    def adjudicate_biometric_warrant(
        self,
        mandate_id: str,
        warrant: EnclaveSignedWarrant,
        current_epoch_sec: Optional[int] = None,
    ) -> BiometricAdjudicationReceipt:
        """
        Adjudicates an incoming Secure Enclave biometric warrant against the pending mandate.
        Releases latch only if the cryptographic signature, attempt fence, and TTL hold.
        """
        now_epoch = self._get_current_epoch_sec(current_epoch_sec)

        entry = self._proposals.get(mandate_id)
        if not entry:
            rec_payload = {
                "latch_released": False,
                "mandate_id": mandate_id,
                "status_code": "ERR_UNKNOWN_MANDATE",
            }
            return BiometricAdjudicationReceipt(
                adjudication_caid=sha256_jcs_caid(rec_payload),
                latch_released=False,
                status_code="ERR_UNKNOWN_MANDATE",
                mandate_id=mandate_id,
                operation_id="",
                attempt_fence=0,
                risk_score_bps=MAX_FAIL_CLOSED_RISK_BPS,  # claim: config
                adjudication_epoch_sec=now_epoch,
            )

        proposal, report = entry

        # Verify via Mac Enclave Notary Verifier
        verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
            expected_proposal=proposal,
            warrant=warrant,
            pinned_enclave_pubkey_x963_hex=self.pinned_pubkey_hex,
            current_epoch_sec=now_epoch,
        )

        latch_released = verdict.latch_released
        status_code = "LATCH_RELEASED_BIOMETRIC_CONFIRMED" if latch_released else f"LATCH_LOCKED_{verdict.reason_code}"

        # If released, transition mandate in queue to CLOSED_AUTHORIZED
        if latch_released:
            warrant_dict = {
                "canonical_payload_utf8": warrant.canonical_payload_utf8,
                "payload_sha256_caid": warrant.payload_sha256_caid,
                "public_key_x963_hex": warrant.public_key_x963_hex,
                "signature_der_hex": warrant.signature_der_hex,
                "algorithm": warrant.algorithm,
            }
            mandate = self.queue.get_mandate(mandate_id)
            if mandate is not None:
                if mandate.stage == AP2MandateStage.PENDING_MOBILE_AUTHORIZATION:
                    with self.queue._lock:
                        self.queue._mandates[mandate_id] = AP2IntentMandate(
                            mandate_id=mandate.mandate_id,
                            task_id=mandate.task_id,
                            intent_caid=mandate.intent_caid,
                            spending_cap_minor=mandate.spending_cap_minor,
                            allowed_rails=mandate.allowed_rails,
                            attempt_fence=mandate.attempt_fence,
                            expires_at_epoch_sec=mandate.expires_at_epoch_sec,
                            stage=AP2MandateStage.CLOSED_AUTHORIZED,
                            enclave_warrant=warrant_dict,
                        )

        payload = {
            "adjudication_epoch_sec": now_epoch,
            "attempt_fence": proposal.attempt_fence,
            "latch_released": latch_released,
            "mandate_id": mandate_id,
            "operation_id": proposal.operation_id,
            "risk_score_bps": report.risk_score_bps,
            "status_code": status_code,
        }
        adj_caid = sha256_jcs_caid(payload)

        return BiometricAdjudicationReceipt(
            adjudication_caid=adj_caid,
            latch_released=latch_released,
            status_code=status_code,
            mandate_id=mandate_id,
            operation_id=proposal.operation_id,
            attempt_fence=proposal.attempt_fence,
            risk_score_bps=report.risk_score_bps,
            adjudication_epoch_sec=now_epoch,
        )

    def adjudicate_operator_veto(
        self,
        mandate_id: str,
        veto_reason: str,
        current_epoch_sec: Optional[int] = None,
    ) -> BiometricAdjudicationReceipt:
        """
        Registers an explicit operator veto, locking the execution latch fail-closed.
        """
        now_epoch = self._get_current_epoch_sec(current_epoch_sec)

        entry = self._proposals.get(mandate_id)
        op_id = entry[0].operation_id if entry else ""
        fence = entry[0].attempt_fence if entry else 0
        risk_bps = entry[1].risk_score_bps if entry else MAX_FAIL_CLOSED_RISK_BPS  # claim: config

        self.queue.veto_mandate_from_mobile(mandate_id, reason=veto_reason)

        payload = {
            "adjudication_epoch_sec": now_epoch,
            "attempt_fence": fence,
            "latch_released": False,
            "mandate_id": mandate_id,
            "operation_id": op_id,
            "risk_score_bps": risk_bps,
            "status_code": "LATCH_LOCKED_OPERATOR_VETO",
            "veto_reason": veto_reason,
        }
        adj_caid = sha256_jcs_caid(payload)

        return BiometricAdjudicationReceipt(
            adjudication_caid=adj_caid,
            latch_released=False,
            status_code="LATCH_LOCKED_OPERATOR_VETO",
            mandate_id=mandate_id,
            operation_id=op_id,
            attempt_fence=fence,
            risk_score_bps=risk_bps,
            adjudication_epoch_sec=now_epoch,
        )
