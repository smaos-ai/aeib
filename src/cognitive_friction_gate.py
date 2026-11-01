#!/usr/bin/env python3
"""
Cognitive Friction Gate (src/cognitive_friction_gate.py).

Status: INTERNAL PREVIEW COMMISSIONED
Evaluated under the stated model to mitigate human metacognitive offloading,
one-sided AI advocacy, and Turan inverted-U reviewer fatigue.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Dict, Mapping, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


@dataclass(frozen=True)
class CriticalActionProposal:
    """Proposal requiring active human comprehension and risk acknowledgment."""

    proposal_id: str
    target_resource: str
    proposed_code_diff: str
    blast_radius_records: int
    exact_boundary_condition: str
    counter_arguments_and_risks: Tuple[str, ...]
    distractor_options: Tuple[str, ...]
    minimum_reading_time_ms: int = 3000  # claim: config

    def __post_init__(self) -> None:
        if self.blast_radius_records < 0:
            raise ValueError("blast_radius_records must be >= 0")
        if self.minimum_reading_time_ms < 500:
            raise ValueError("minimum_reading_time_ms must be >= 500")
        if not self.proposal_id.strip():
            raise ValueError("proposal_id must be non-empty")
        if not self.exact_boundary_condition.strip():
            raise ValueError("exact_boundary_condition must be non-empty")

    def proposal_caid(self) -> str:
        """Compute deterministic RFC 8785 SHA-256 digest of the proposal."""
        payload = {
            "blast_radius_records": self.blast_radius_records,
            "counter_arguments_and_risks": list(self.counter_arguments_and_risks),
            "distractor_options": list(self.distractor_options),
            "exact_boundary_condition": self.exact_boundary_condition,
            "minimum_reading_time_ms": self.minimum_reading_time_ms,
            "proposal_id": self.proposal_id,
            "proposed_code_diff": self.proposed_code_diff,
            "target_resource": self.target_resource,
        }
        return hashlib.sha256(encode_jcs(payload)).hexdigest()


@dataclass(frozen=True)
class HumanComprehensionResponse:
    """Out-of-band operator response to the Socratic comprehension challenge."""

    proposal_caid: str
    operator_id: str
    selected_boundary_condition: str
    selected_blast_radius_records: int
    acknowledged_risk: str
    reading_elapsed_ms: int
    hardware_biometric_signature_hex: str
    operator_public_key_hex: str

    def canonical_signing_payload(self) -> bytes:
        """Serialize canonical RFC 8785 bytes signed by the operator key."""
        payload = {
            "acknowledged_risk": self.acknowledged_risk,
            "operator_id": self.operator_id,
            "operator_public_key_hex": self.operator_public_key_hex.lower(),
            "proposal_caid": self.proposal_caid,
            "reading_elapsed_ms": self.reading_elapsed_ms,
            "selected_blast_radius_records": self.selected_blast_radius_records,
            "selected_boundary_condition": self.selected_boundary_condition,
        }
        return encode_jcs(payload)


@dataclass(frozen=True)
class CognitiveFrictionVerdict:
    """Deterministic receipt from CognitiveFrictionGate evaluation."""

    allowed: bool
    status_code: str
    violation_reason: str
    proposal_caid: str
    operator_id: str
    reading_elapsed_ms: int
    window_reviews_used: int
    max_reviews_per_window: int
    verdict_caid: str


class CognitiveFrictionGate:
    """Enforces counter-argument presence, fatigue caps, reading floors, and Socratic verification."""

    def __init__(
        self,
        pinned_operator_pubkeys: Mapping[str, str],
        max_reviews_per_window: int = 5,
    ) -> None:
        if max_reviews_per_window < 1:
            raise ValueError("max_reviews_per_window must be >= 1")
        self._pinned_keys: Dict[str, str] = {
            op_id: pub_hex.lower() for op_id, pub_hex in pinned_operator_pubkeys.items()
        }
        self._max_reviews_per_window: int = max_reviews_per_window
        self._operator_review_counts: Dict[str, int] = {}

    def reset_fatigue_window(self, operator_id: Optional[str] = None) -> None:
        """Reset reviewer fatigue counter for one operator or all operators."""
        if operator_id is None:
            self._operator_review_counts.clear()
        else:
            self._operator_review_counts.pop(operator_id, None)

    def _build_verdict(
        self,
        allowed: bool,
        status_code: str,
        violation_reason: str,
        proposal_caid: str,
        operator_id: str,
        reading_elapsed_ms: int,
        window_reviews_used: int,
    ) -> CognitiveFrictionVerdict:
        payload = {
            "allowed": allowed,
            "max_reviews_per_window": self._max_reviews_per_window,
            "operator_id": operator_id,
            "proposal_caid": proposal_caid,
            "reading_elapsed_ms": reading_elapsed_ms,
            "status_code": status_code,
            "violation_reason": violation_reason,
            "window_reviews_used": window_reviews_used,
        }
        verdict_caid = hashlib.sha256(encode_jcs(payload)).hexdigest()
        return CognitiveFrictionVerdict(
            allowed=allowed,
            status_code=status_code,
            violation_reason=violation_reason,
            proposal_caid=proposal_caid,
            operator_id=operator_id,
            reading_elapsed_ms=reading_elapsed_ms,
            window_reviews_used=window_reviews_used,
            max_reviews_per_window=self._max_reviews_per_window,
            verdict_caid=verdict_caid,
        )

    def verify_human_comprehension(
        self,
        proposal: CriticalActionProposal,
        response: HumanComprehensionResponse,
    ) -> CognitiveFrictionVerdict:
        """Evaluate proposal counter-arguments, fatigue quota, reading velocity, comprehension, and signature."""
        expected_caid = proposal.proposal_caid()
        current_used = self._operator_review_counts.get(response.operator_id, 0)

        # 1. One-Sided Advocacy Check
        if len(proposal.counter_arguments_and_risks) == 0 or any(
            len(r.strip()) < 5 for r in proposal.counter_arguments_and_risks
        ):
            return self._build_verdict(
                allowed=False,
                status_code="HALT_ONESIDED_ADVOCACY",
                violation_reason="REASON_MISSING_COUNTER_ARGUMENTS_OR_RISKS",
                proposal_caid=expected_caid,
                operator_id=response.operator_id,
                reading_elapsed_ms=response.reading_elapsed_ms,
                window_reviews_used=current_used,
            )

        # 2. Proposal Binding Check
        if response.proposal_caid != expected_caid:
            return self._build_verdict(
                allowed=False,
                status_code="HALT_PROPOSAL_CAID_MISMATCH",
                violation_reason="REASON_PROPOSAL_CAID_DOES_NOT_MATCH",
                proposal_caid=expected_caid,
                operator_id=response.operator_id,
                reading_elapsed_ms=response.reading_elapsed_ms,
                window_reviews_used=current_used,
            )

        # 3. Operator Key Pinning
        if (
            response.operator_id not in self._pinned_keys
            or self._pinned_keys[response.operator_id] != response.operator_public_key_hex.lower()
        ):
            return self._build_verdict(
                allowed=False,
                status_code="HALT_UNTRUSTED_OPERATOR_KEY",
                violation_reason="REASON_OPERATOR_KEY_NOT_PINNED",
                proposal_caid=expected_caid,
                operator_id=response.operator_id,
                reading_elapsed_ms=response.reading_elapsed_ms,
                window_reviews_used=current_used,
            )

        # 4. Turan Reviewer Fatigue Budget Check
        updated_used = current_used + 1
        self._operator_review_counts[response.operator_id] = updated_used
        if updated_used > self._max_reviews_per_window:
            return self._build_verdict(
                allowed=False,
                status_code="HALT_REVIEWER_FATIGUE_QUOTA_EXCEEDED",
                violation_reason="REASON_TURAN_OVERSIGHT_FATIGUE_CAP_REACHED",
                proposal_caid=expected_caid,
                operator_id=response.operator_id,
                reading_elapsed_ms=response.reading_elapsed_ms,
                window_reviews_used=updated_used,
            )

        # 5. Rubber-Stamp Velocity Check
        if response.reading_elapsed_ms < proposal.minimum_reading_time_ms:
            return self._build_verdict(
                allowed=False,
                status_code="HALT_METACOGNITIVE_RUBBER_STAMP",
                violation_reason=(
                    f"Elapsed {response.reading_elapsed_ms}ms < minimum floor {proposal.minimum_reading_time_ms}ms"
                ),
                proposal_caid=expected_caid,
                operator_id=response.operator_id,
                reading_elapsed_ms=response.reading_elapsed_ms,
                window_reviews_used=updated_used,
            )

        # 6. Socratic Comprehension Challenge Check
        valid_risks = [r.strip() for r in proposal.counter_arguments_and_risks]
        if (
            response.selected_boundary_condition.strip() != proposal.exact_boundary_condition.strip()
            or response.selected_blast_radius_records != proposal.blast_radius_records
            or response.acknowledged_risk.strip() not in valid_risks
        ):
            return self._build_verdict(
                allowed=False,
                status_code="HALT_COMPREHENSION_CHALLENGE_FAILED",
                violation_reason="REASON_INCORRECT_BOUNDARY_BLAST_RADIUS_OR_RISK",
                proposal_caid=expected_caid,
                operator_id=response.operator_id,
                reading_elapsed_ms=response.reading_elapsed_ms,
                window_reviews_used=updated_used,
            )

        # 7. Hardware Biometric Signature Verification
        try:
            pub_bytes = bytes.fromhex(response.operator_public_key_hex)
            sig_bytes = bytes.fromhex(response.hardware_biometric_signature_hex)
            pubkey = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            pubkey.verify(sig_bytes, response.canonical_signing_payload())
        except (ValueError, InvalidSignature):
            return self._build_verdict(
                allowed=False,
                status_code="HALT_INVALID_HARDWARE_SIGNATURE",
                violation_reason="REASON_ED25519_BIOMETRIC_SIGNATURE_INVALID",
                proposal_caid=expected_caid,
                operator_id=response.operator_id,
                reading_elapsed_ms=response.reading_elapsed_ms,
                window_reviews_used=updated_used,
            )

        # 8. Allow verified comprehension
        return self._build_verdict(
            allowed=True,
            status_code="ALLOW_VERIFIED_COGNITIVE_COMPREHENSION",
            violation_reason="NONE",
            proposal_caid=expected_caid,
            operator_id=response.operator_id,
            reading_elapsed_ms=response.reading_elapsed_ms,
            window_reviews_used=updated_used,
        )
