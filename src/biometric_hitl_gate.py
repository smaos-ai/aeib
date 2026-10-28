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
src/biometric_hitl_gate.py
================================================================================
Biometric & Cognitive Load Gate for T3 (Irreversible) Action Adjudication.

Evaluated under the stated model:
Closes the "Human-in-the-Loop Fatigue" and "Urgency Spoofing" vulnerabilities.
When high-consequence agents flag actions as critical or urgent, fatigued human
operators frequently rubber-stamp requests without semantic scrutiny.

Enforces:
1. Urgency Spoofing Detection:
   Statistical base-rate evaluation that blocks agents attempting to claim urgency
   when historical base rates demonstrate abnormal alerting rates.
2. Circadian Phase Gating:
   Blocks T3 approvals during biological deep night phases regardless of agent claims.
3. Physiological Zero-Trust:
   Evaluates real-time Heart Rate Variability (HRV), cognitive load in integer basis
   points (0..10000 bps), and typing entropy before authorization.
4. Cryptographic Adjudication Receipt:
   Mints an Ed25519-signed receipt binding action, telemetry, and verdict over RFC 8785 JCS.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

try:
    from src.jcs_canonicalizer import encode_jcs
except ImportError:
    from jcs_canonicalizer import encode_jcs


class CircadianPhase(str, Enum):
    PEAK_ALERTNESS = "PEAK_ALERTNESS"
    NORMAL = "NORMAL"
    FATIGUED = "FATIGUED"
    DEEP_NIGHT = "DEEP_NIGHT"


class AdjudicationVerdict(str, Enum):
    ALLOW_T3_APPROVAL = "ALLOW_T3_APPROVAL"
    HALT_COGNITIVE_OVERLOAD = "HALT_COGNITIVE_OVERLOAD"
    HALT_HRV_DEPRESSION = "HALT_HRV_DEPRESSION"
    HALT_CIRCADIAN_VIOLATION = "HALT_CIRCADIAN_VIOLATION"
    HALT_URGENCY_SPOOFING = "HALT_URGENCY_SPOOFING"
    HALT_MISSING_TELEMETRY = "HALT_MISSING_TELEMETRY"


@dataclass(frozen=True)
class BiometricTelemetry:
    hrv_ms: float
    cognitive_load_bps: int  # 0..10000 basis points
    circadian_phase: CircadianPhase
    keystroke_entropy: float
    timestamp_ns: int

    def __post_init__(self) -> None:
        if not (0 <= self.cognitive_load_bps <= 10000):
            raise ValueError("ERR_INVALID_COGNITIVE_LOAD_BPS: must be 0..10000 bps")
        if self.hrv_ms < 0:
            raise ValueError("ERR_INVALID_HRV: must be non-negative")


@dataclass(frozen=True)
class T3ApprovalRequest:
    action_digest: str
    risk_tier: str  # Must be "T3"
    agent_claimed_urgency: bool
    human_intent_hash: str


@dataclass(frozen=True)
class BiometricAdjudicationReceipt:
    action_digest: str
    verdict: AdjudicationVerdict
    telemetry_digest: Optional[str]
    timestamp_ns: int
    issuer_public_key_hex: Optional[str] = None
    signature_b64: Optional[str] = None

    def verify_signature(self) -> bool:
        if self.issuer_public_key_hex is None or self.signature_b64 is None:
            return False
        payload = {
            "action_digest": self.action_digest,
            "verdict": self.verdict.value,
            "telemetry_digest": self.telemetry_digest,
            "timestamp_ns": self.timestamp_ns,
            "issuer_public_key_hex": self.issuer_public_key_hex,
        }
        canonical_bytes = encode_jcs(payload)
        try:
            pubkey = Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.issuer_public_key_hex))
            sig_bytes = base64.b64decode(self.signature_b64)
            pubkey.verify(sig_bytes, canonical_bytes)
            return True
        except (InvalidSignature, ValueError):
            return False


class BiometricHITLGate:
    """
    Physiological gatekeeper for high-consequence (T3) human authorizations.
    """

    MIN_HRV_MS: float = 45.0  # claim: config
    MAX_COGNITIVE_LOAD_BPS: int = 7500  # claim: config
    MAX_KEYSTROKE_ENTROPY: float = 4.5  # claim: config
    MIN_HISTORICAL_URGENCY_RATE: float = 0.05  # claim: config

    @classmethod
    def evaluate_adjudication_capacity(
        cls,
        request: T3ApprovalRequest,
        telemetry: Optional[BiometricTelemetry],
        historical_urgency_rate: float,
    ) -> AdjudicationVerdict:
        if request.risk_tier != "T3":
            raise ValueError("ERR_BIOMETRIC_GATE_ONLY_FOR_T3")

        # 0. Fail-closed on missing biometric telemetry
        if telemetry is None:
            return AdjudicationVerdict.HALT_MISSING_TELEMETRY

        # 1. Detect Agent Urgency Spoofing (historical base-rate check)
        if request.agent_claimed_urgency and historical_urgency_rate < cls.MIN_HISTORICAL_URGENCY_RATE:
            return AdjudicationVerdict.HALT_URGENCY_SPOOFING

        # 2. Circadian Phase Gating
        if telemetry.circadian_phase == CircadianPhase.DEEP_NIGHT:
            return AdjudicationVerdict.HALT_CIRCADIAN_VIOLATION

        # 3. Autonomic Regulation (Heart Rate Variability)
        if telemetry.hrv_ms < cls.MIN_HRV_MS:
            return AdjudicationVerdict.HALT_HRV_DEPRESSION

        # 4. Cognitive Overload & Erroneous Keystroke Entropy
        if (
            telemetry.cognitive_load_bps > cls.MAX_COGNITIVE_LOAD_BPS
            or telemetry.keystroke_entropy > cls.MAX_KEYSTROKE_ENTROPY
        ):
            return AdjudicationVerdict.HALT_COGNITIVE_OVERLOAD

        return AdjudicationVerdict.ALLOW_T3_APPROVAL

    @classmethod
    def mint_adjudication_receipt(
        cls,
        request: T3ApprovalRequest,
        telemetry: Optional[BiometricTelemetry],
        verdict: AdjudicationVerdict,
        timestamp_ns: int,
        signing_key: Optional[Ed25519PrivateKey] = None,
    ) -> BiometricAdjudicationReceipt:
        telemetry_digest: Optional[str] = None
        if telemetry is not None:
            tel_payload = {
                "hrv_ms": telemetry.hrv_ms,
                "cognitive_load_bps": telemetry.cognitive_load_bps,
                "circadian_phase": telemetry.circadian_phase.value,
                "keystroke_entropy": telemetry.keystroke_entropy,
                "timestamp_ns": telemetry.timestamp_ns,
            }
            telemetry_digest = f"sha256:{hashlib.sha256(encode_jcs(tel_payload)).hexdigest()}"

        pub_hex: Optional[str] = None
        sig_b64: Optional[str] = None

        if signing_key is not None:
            pub_hex = signing_key.public_key().public_bytes_raw().hex()
            payload = {
                "action_digest": request.action_digest,
                "verdict": verdict.value,
                "telemetry_digest": telemetry_digest,
                "timestamp_ns": timestamp_ns,
                "issuer_public_key_hex": pub_hex,
            }
            canonical_bytes = encode_jcs(payload)
            sig_bytes = signing_key.sign(canonical_bytes)
            sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

        return BiometricAdjudicationReceipt(
            action_digest=request.action_digest,
            verdict=verdict,
            telemetry_digest=telemetry_digest,
            timestamp_ns=timestamp_ns,
            issuer_public_key_hex=pub_hex,
            signature_b64=sig_b64,
        )
