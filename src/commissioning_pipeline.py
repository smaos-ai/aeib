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
src/commissioning_pipeline.py
================================================================================
Industrial 7-Stage Commissioning Lifecycle and Hold-Point Engine.

Evaluated under the stated model (Nuclear 10 CFR 50 App B, IEEE 730 / IEEE 603,
DO-178C DAL A, and OpenTelemetry GenAI Semantic Conventions).

The 7-Stage Commissioning Lifecycle:
  Stage 1: STAGE_1_DESIGN_BASIS
           Invariants, specifications, and risk register digests.
  Stage 2: STAGE_2_HAZOP
           Hazard and Operability study with falsification vectors.
  Stage 3: STAGE_3_COLD_COMMISSIONING
           Hermetic offline bootstrap pass, AST purity, and zero-mock verification.
  Stage 4: STAGE_4_HOT_COMMISSIONING
           Staging runtime execution, out-of-process isolation, UndoBench verification.
  Stage 5: STAGE_5_LOAD_TESTING
           Deterministic simulation and mutation adequacy kill ratio (>= 9000 bps).
  Stage 6: STAGE_6_READY_FOR_SERVICE
           Formal RFS promotion warrant requiring operator biometric / offline signature.
  Stage 7: STAGE_7_OPERATION
           Continuous runtime operation and daily truth compass evaluation.

Architectural Invariants:
  1. Strict Sequential Ordering:
     Stages must be commissioned in exact 1..7 order. Any attempt to advance
     out-of-order or skip hold points fails closed immediately.
  2. Disk-Anchored Evidence Verification:
     All evidence files are read from disk and content-hashed with SHA-256.
     Caller-reported hashes are never trusted without disk verification.
  3. Operator Biometric Sign-Off at Stage 6:
     Promotion to Ready-for-Service strictly requires an operator signature
     (pinned Apple Secure Enclave P-256 FaceID or pinned operator Ed25519 key).
  4. OpenTelemetry (OTEL) GenAI Compliance:
     Emits structured GenAI telemetry spans bound to RFC 8785 canonical bytes.
  5. Cryptographic Purity:
     Uses real Ed25519 and NIST P-256 primitives; zero floats in JCS envelopes.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from src.jcs_canonicalizer import encode_jcs


class CommissioningStage(str, Enum):
    """The 7 formal stages of the industrial commissioning lifecycle."""

    STAGE_1_DESIGN_BASIS = "STAGE_1_DESIGN_BASIS"
    STAGE_2_HAZOP = "STAGE_2_HAZOP"
    STAGE_3_COLD_COMMISSIONING = "STAGE_3_COLD_COMMISSIONING"
    STAGE_4_HOT_COMMISSIONING = "STAGE_4_HOT_COMMISSIONING"
    STAGE_5_LOAD_TESTING = "STAGE_5_LOAD_TESTING"
    STAGE_6_READY_FOR_SERVICE = "STAGE_6_READY_FOR_SERVICE"
    STAGE_7_OPERATION = "STAGE_7_OPERATION"


STAGE_ORDER: Tuple[CommissioningStage, ...] = (
    CommissioningStage.STAGE_1_DESIGN_BASIS,
    CommissioningStage.STAGE_2_HAZOP,
    CommissioningStage.STAGE_3_COLD_COMMISSIONING,
    CommissioningStage.STAGE_4_HOT_COMMISSIONING,
    CommissioningStage.STAGE_5_LOAD_TESTING,
    CommissioningStage.STAGE_6_READY_FOR_SERVICE,
    CommissioningStage.STAGE_7_OPERATION,
)

STAGE_INDICES: Mapping[CommissioningStage, int] = {
    stage: idx + 1 for idx, stage in enumerate(STAGE_ORDER)
}


class SignOffType(str, Enum):
    """Authorized sign-off authority types for hold points."""

    AUTOMATED_VERIFIER = "AUTOMATED_VERIFIER"
    OPERATOR_OFFLINE_ED25519 = "OPERATOR_OFFLINE_ED25519"
    OPERATOR_BIOMETRIC_FACEID = "OPERATOR_BIOMETRIC_FACEID"


class CommissioningHoldPointError(Exception):
    """Base exception for commissioning hold-point verification failures."""


class InvalidStageTransitionError(CommissioningHoldPointError):
    """Raised when an out-of-order stage transition is attempted."""


class EvidenceTamperError(CommissioningHoldPointError):
    """Raised when evidence files on disk do not match the signed manifest."""


class UnauthorizedSignerError(CommissioningHoldPointError):
    """Raised when a hold point is signed by an unrecognized key."""


class ReplayNonceError(CommissioningHoldPointError):
    """Raised when a receipt nonce has already been consumed."""


@dataclass(frozen=True)
class StageHoldPointReceipt:
    """Cryptographically signed hold-point sign-off receipt for a stage."""

    stage: CommissioningStage
    pipeline_id: str
    stage_index: int
    evidence_files: Dict[str, str]
    evidence_manifest_caid: str
    sign_off_type: SignOffType
    signer_public_key_hex: str
    signature_der_or_hex: str
    timestamp_utc: str
    nonce: str
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_canonical_signable_payload(self) -> Dict[str, Any]:
        """Constructs canonical dictionary for signing according to RFC 8785."""
        return {
            "evidence_files": self.evidence_files,
            "evidence_manifest_caid": self.evidence_manifest_caid,
            "metadata": self.metadata,
            "nonce": self.nonce,
            "pipeline_id": self.pipeline_id,
            "sign_off_type": (
                self.sign_off_type.value
                if hasattr(self.sign_off_type, "value")
                else str(self.sign_off_type)
            ),
            "signer_public_key_hex": self.signer_public_key_hex.lower(),
            "stage": self.stage.value,
            "stage_index": self.stage_index,
            "status": self.status,
            "timestamp_utc": self.timestamp_utc,
        }

    def canonical_bytes(self) -> bytes:
        """Emits byte-exact RFC 8785 canonical bytes."""
        return encode_jcs(self.to_canonical_signable_payload())

    def compute_caid(self) -> str:
        """Emits deterministic SHA-256 CAID of the receipt."""
        return "sha256:" + hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class CommissioningOTELSpan:
    """OpenTelemetry-compliant GenAI and commissioning trace span."""

    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    start_time_unix_nano: int
    end_time_unix_nano: int
    status_code: str
    status_description: str
    attributes: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Serializes span to a dictionary without floating point values."""
        return {
            "attributes": self.attributes,
            "end_time_unix_nano": self.end_time_unix_nano,
            "name": self.name,
            "parent_span_id": self.parent_span_id or "",
            "span_id": self.span_id,
            "start_time_unix_nano": self.start_time_unix_nano,
            "status": {
                "code": self.status_code,
                "description": self.status_description,
            },
            "trace_id": self.trace_id,
        }


class CommissioningPipeline:
    """
    Seven-Stage Industrial Commissioning Lifecycle Engine.
    Enforces sequential progression, disk-anchored evidence hashing,
    cryptographic verification, and OpenTelemetry trace collection.
    """

    def __init__(
        self,
        pipeline_id: str,
        repo_root: Path,
        pinned_verifier_pubkeys_hex: Sequence[str],
        pinned_operator_pubkeys_hex: Sequence[str],
        pinned_enclave_x963_pubkeys_hex: Sequence[str],
    ) -> None:
        if not pipeline_id or not isinstance(pipeline_id, str):
            raise ValueError("ERR_INVALID_PIPELINE_ID")
        self.pipeline_id = pipeline_id
        self.repo_root = repo_root.resolve()
        if not self.repo_root.is_dir():
            raise ValueError(f"ERR_REPO_ROOT_NOT_DIR:{repo_root}")

        self.pinned_verifier_pubkeys_hex: Tuple[str, ...] = tuple(
            k.lower() for k in pinned_verifier_pubkeys_hex
        )
        self.pinned_operator_pubkeys_hex: Tuple[str, ...] = tuple(
            k.lower() for k in pinned_operator_pubkeys_hex
        )
        self.pinned_enclave_x963_pubkeys_hex: Tuple[str, ...] = tuple(
            k.lower() for k in pinned_enclave_x963_pubkeys_hex
        )

        self._current_stage_index: int = 0  # 0 indicates not yet started STAGE_1
        self._stage_receipts: Dict[CommissioningStage, StageHoldPointReceipt] = {}
        self._used_nonces: Set[str] = set()
        self._otel_spans: List[CommissioningOTELSpan] = []
        self._trace_id: str = hashlib.sha256(
            pipeline_id.encode("utf-8") + str(time.time_ns()).encode("utf-8")
        ).hexdigest()[:32]

    @property
    def current_stage(self) -> CommissioningStage:
        """Returns the stage currently awaiting hold-point clearance."""
        if self._current_stage_index >= len(STAGE_ORDER):
            return CommissioningStage.STAGE_7_OPERATION
        return STAGE_ORDER[self._current_stage_index]

    @property
    def completed_stages(self) -> Tuple[CommissioningStage, ...]:
        """Returns the tuple of commissioned stages."""
        return tuple(self._stage_receipts.keys())

    @property
    def otel_spans(self) -> Tuple[CommissioningOTELSpan, ...]:
        """Returns recorded OpenTelemetry spans."""
        return tuple(self._otel_spans)

    def evaluate_stage_evidence(
        self, stage: CommissioningStage, relative_file_paths: Sequence[str]
    ) -> Tuple[Dict[str, str], str]:
        """
        Reads evidence files directly from disk, verifies presence,
        and computes deterministic SHA-256 hashes and canonical manifest CAID.
        """
        if not relative_file_paths:
            raise ValueError("ERR_EMPTY_EVIDENCE_LIST")

        evidence_hashes: Dict[str, str] = {}
        for rel in sorted(relative_file_paths):
            fpath = self.repo_root / rel
            if not fpath.is_file():
                raise FileNotFoundError(f"ERR_EVIDENCE_FILE_NOT_FOUND:{rel}")
            file_bytes = fpath.read_bytes()
            if len(file_bytes) == 0:
                raise ValueError(f"ERR_EVIDENCE_FILE_EMPTY:{rel}")
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            evidence_hashes[rel] = file_hash

        manifest_caid = (
            "sha256:" + hashlib.sha256(encode_jcs(evidence_hashes)).hexdigest()
        )
        return evidence_hashes, manifest_caid

    def verify_and_advance_stage(
        self, receipt: StageHoldPointReceipt
    ) -> StageHoldPointReceipt:
        """
        Verifies a stage hold-point receipt against disk evidence,
        sequential ordering, replay protection, and cryptographic signatures.
        Advances the pipeline to the next stage upon success.
        """
        start_nano = time.time_ns()
        span_id = hashlib.sha256(
            f"{receipt.stage.value}:{receipt.nonce}".encode("utf-8")
        ).hexdigest()[:16]

        def _record_span(status_code: str, desc: str) -> None:
            span = CommissioningOTELSpan(
                name="aeib.commissioning.hold_point_evaluation",
                trace_id=self._trace_id,
                span_id=span_id,
                parent_span_id=None,
                start_time_unix_nano=start_nano,
                end_time_unix_nano=time.time_ns(),
                status_code=status_code,
                status_description=desc,
                attributes={
                    "gen_ai.system": "sovereign_nexus_aeib",
                    "gen_ai.operation.name": "commissioning_stage_evaluation",
                    "aeib.commissioning.pipeline_id": self.pipeline_id,
                    "aeib.commissioning.stage": receipt.stage.value,
                    "aeib.commissioning.stage_index": receipt.stage_index,
                    "aeib.hold_point.sign_off_type": (
                        receipt.sign_off_type.value
                        if hasattr(receipt.sign_off_type, "value")
                        else str(receipt.sign_off_type)
                    ),
                    "aeib.hold_point.status": receipt.status,
                    "aeib.hold_point.signer_public_key": receipt.signer_public_key_hex.lower(),
                },
            )
            self._otel_spans.append(span)

        # 1. Pipeline ID check
        if receipt.pipeline_id != self.pipeline_id:
            _record_span("ERROR", "PIPELINE_ID_MISMATCH")
            raise CommissioningHoldPointError("ERR_PIPELINE_ID_MISMATCH")

        # 2. Sequential order check
        expected_stage = self.current_stage
        expected_index = STAGE_INDICES[expected_stage]
        if receipt.stage != expected_stage or receipt.stage_index != expected_index:
            _record_span("ERROR", "INVALID_STAGE_TRANSITION")
            raise InvalidStageTransitionError(
                f"ERR_INVALID_STAGE_TRANSITION: expected {expected_stage.value} "
                f"(index {expected_index}), got {receipt.stage.value} (index {receipt.stage_index})"
            )

        # 3. Status must be PASSED
        if receipt.status != "PASSED":
            _record_span("ERROR", "HOLD_POINT_NOT_PASSED")
            raise CommissioningHoldPointError(f"ERR_HOLD_POINT_FAILED:{receipt.status}")

        # 4. Replay nonce check
        if receipt.nonce in self._used_nonces:
            _record_span("ERROR", "REPLAY_NONCE_DETECTED")
            raise ReplayNonceError("ERR_REPLAY_NONCE_DETECTED")

        # 5. Disk evidence verification
        if not receipt.evidence_files:
            _record_span("ERROR", "EMPTY_EVIDENCE_FILES")
            raise EvidenceTamperError("ERR_EMPTY_EVIDENCE_FILES")

        # Verify all evidence files on disk match receipt hashes
        actual_hashes, expected_manifest_caid = self.evaluate_stage_evidence(
            receipt.stage, list(receipt.evidence_files.keys())
        )
        if actual_hashes != receipt.evidence_files:
            _record_span("ERROR", "EVIDENCE_HASH_MISMATCH")
            raise EvidenceTamperError("ERR_EVIDENCE_HASH_MISMATCH_ON_DISK")
        if receipt.evidence_manifest_caid != expected_manifest_caid:
            _record_span("ERROR", "MANIFEST_CAID_MISMATCH")
            raise EvidenceTamperError("ERR_MANIFEST_CAID_MISMATCH")

        # 6. Authority and cryptographic signature check
        signer_key = receipt.signer_public_key_hex.lower()
        signable_bytes = receipt.canonical_bytes()

        if receipt.sign_off_type == SignOffType.AUTOMATED_VERIFIER:
            if receipt.stage == CommissioningStage.STAGE_6_READY_FOR_SERVICE:
                _record_span("ERROR", "RFS_REQUIRES_OPERATOR_SIGN_OFF")
                raise UnauthorizedSignerError(
                    "ERR_STAGE_6_RFS_REQUIRES_OPERATOR_SIGN_OFF"
                )
            if signer_key not in self.pinned_verifier_pubkeys_hex:
                _record_span("ERROR", "UNPINNED_VERIFIER_KEY")
                raise UnauthorizedSignerError("ERR_UNPINNED_VERIFIER_KEY")
            self._verify_ed25519_signature(
                signer_key, signable_bytes, receipt.signature_der_or_hex
            )

        elif receipt.sign_off_type == SignOffType.OPERATOR_OFFLINE_ED25519:
            if signer_key not in self.pinned_operator_pubkeys_hex:
                _record_span("ERROR", "UNPINNED_OPERATOR_ED25519_KEY")
                raise UnauthorizedSignerError("ERR_UNPINNED_OPERATOR_KEY")
            self._verify_ed25519_signature(
                signer_key, signable_bytes, receipt.signature_der_or_hex
            )

        elif receipt.sign_off_type == SignOffType.OPERATOR_BIOMETRIC_FACEID:
            if signer_key not in self.pinned_enclave_x963_pubkeys_hex:
                _record_span("ERROR", "UNPINNED_ENCLAVE_FACEID_KEY")
                raise UnauthorizedSignerError("ERR_UNPINNED_ENCLAVE_PUBLIC_KEY")
            self._verify_p256_der_signature(
                signer_key, signable_bytes, receipt.signature_der_or_hex
            )
        else:
            _record_span("ERROR", "UNKNOWN_SIGN_OFF_TYPE")
            raise UnauthorizedSignerError(
                f"ERR_UNKNOWN_SIGN_OFF_TYPE:{receipt.sign_off_type}"
            )

        # Stage passed: advance
        self._used_nonces.add(receipt.nonce)
        self._stage_receipts[receipt.stage] = receipt
        self._current_stage_index += 1
        _record_span("OK", "STAGE_HOLD_POINT_VERIFIED")

        return receipt

    def is_ready_for_service(self) -> bool:
        """Returns True if Stages 1 through 6 have verified hold points."""
        required = STAGE_ORDER[:6]
        return all(stage in self._stage_receipts for stage in required)

    def generate_rfs_certificate(self) -> Dict[str, Any]:
        """
        Compiles the Ready-for-Service Certificate into an RFC 8785 envelope.
        Fails closed if the pipeline has not cleared Stage 6.
        """
        if not self.is_ready_for_service():
            raise CommissioningHoldPointError("ERR_PIPELINE_NOT_READY_FOR_SERVICE")

        receipt_caids = {
            stage.value: receipt.compute_caid()
            for stage, receipt in self._stage_receipts.items()
        }
        all_stage_caids_jcs = encode_jcs(receipt_caids)
        rfs_run_caid = (
            "sha256:" + hashlib.sha256(all_stage_caids_jcs).hexdigest()
        )

        cert = {
            "certificate_type": "READY_FOR_SERVICE_CERTIFICATE",
            "commissioned_stages_count": len(self._stage_receipts),
            "pipeline_id": self.pipeline_id,
            "rfs_run_caid": rfs_run_caid,
            "stage_receipt_caids": receipt_caids,
            "status": "COMMISSIONED_READY_FOR_SERVICE",
            "telemetry_spans_count": len(self._otel_spans),
            "timestamp_utc": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
        }
        return cert

    @staticmethod
    def _verify_ed25519_signature(
        pubkey_hex: str, message: bytes, sig_hex: str
    ) -> None:
        """Verifies Ed25519 raw signature bytes."""
        try:
            pub_bytes = bytes.fromhex(pubkey_hex)
            sig_bytes = bytes.fromhex(sig_hex)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            public_key.verify(sig_bytes, message)
        except (ValueError, InvalidSignature) as exc:
            raise UnauthorizedSignerError(
                "ERR_INVALID_ED25519_SIGNATURE"
            ) from exc

    @staticmethod
    def _verify_p256_der_signature(
        x963_pubkey_hex: str, message: bytes, der_sig_hex: str
    ) -> None:
        """Verifies NIST P-256 (secp256r1) DER signature from Secure Enclave."""
        try:
            pub_bytes = bytes.fromhex(x963_pubkey_hex)
            sig_bytes = bytes.fromhex(der_sig_hex)
            pub_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(), pub_bytes
            )
            pub_key.verify(sig_bytes, message, ec.ECDSA(hashes.SHA256()))
        except (ValueError, InvalidSignature) as exc:
            raise UnauthorizedSignerError(
                "ERR_INVALID_P256_DER_SIGNATURE"
            ) from exc
