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
tests/test_biometric_hitl_gate.py
================================================================================
Falsification & Verification Suite for Biometric & Cognitive Load Gate.
Proves that high-consequence (T3) human adjudications are physically locked
under fatigue, urgency spoofing, circadian violations, and missing telemetry.
"""

from __future__ import annotations

import dataclasses
import time
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.biometric_hitl_gate import (
    AdjudicationVerdict,
    BiometricAdjudicationReceipt,
    BiometricHITLGate,
    BiometricTelemetry,
    CircadianPhase,
    T3ApprovalRequest,
)


def test_blocks_fatigued_human_hrv() -> None:
    """Human is awake but physiologically exhausted (HRV < 45.0 ms). Gate blocks."""
    req = T3ApprovalRequest("sha256:wire1", "T3", False, "sha256:intent1")
    telemetry = BiometricTelemetry(
        hrv_ms=32.0,  # Below 45.0 threshold
        cognitive_load_bps=5000,
        circadian_phase=CircadianPhase.FATIGUED,
        keystroke_entropy=2.1,
        timestamp_ns=time.time_ns(),
    )
    verdict = BiometricHITLGate.evaluate_adjudication_capacity(req, telemetry, 0.10)
    assert verdict == AdjudicationVerdict.HALT_HRV_DEPRESSION


def test_blocks_circadian_violation() -> None:
    """Action pushed during deep biological night. Gate blocks."""
    req = T3ApprovalRequest("sha256:db_drop", "T3", True, "sha256:intent2")
    telemetry = BiometricTelemetry(
        hrv_ms=62.0,
        cognitive_load_bps=4000,
        circadian_phase=CircadianPhase.DEEP_NIGHT,
        keystroke_entropy=3.0,
        timestamp_ns=time.time_ns(),
    )
    verdict = BiometricHITLGate.evaluate_adjudication_capacity(req, telemetry, 0.10)
    assert verdict == AdjudicationVerdict.HALT_CIRCADIAN_VIOLATION


def test_blocks_agent_urgency_spoofing() -> None:
    """Agent spams 'URGENT' flag when base rate is abnormal (< 5%). Gate blocks."""
    req = T3ApprovalRequest("sha256:refund", "T3", True, "sha256:intent3")
    telemetry = BiometricTelemetry(
        hrv_ms=70.0,
        cognitive_load_bps=3000,
        circadian_phase=CircadianPhase.PEAK_ALERTNESS,
        keystroke_entropy=3.2,
        timestamp_ns=time.time_ns(),
    )
    # Historical base rate is only 2% (0.02 < 0.05)
    verdict = BiometricHITLGate.evaluate_adjudication_capacity(req, telemetry, 0.02)
    assert verdict == AdjudicationVerdict.HALT_URGENCY_SPOOFING


def test_blocks_cognitive_overload_and_keystroke_entropy() -> None:
    """Cognitive load > 7500 bps or keystroke entropy > 4.5 yields cognitive overload halt."""
    req = T3ApprovalRequest("sha256:deploy", "T3", False, "sha256:intent4")

    # Boundary: exactly 7500 bps is allowed
    tel_at_boundary = BiometricTelemetry(
        hrv_ms=55.0,
        cognitive_load_bps=7500,
        circadian_phase=CircadianPhase.NORMAL,
        keystroke_entropy=4.5,
        timestamp_ns=time.time_ns(),
    )
    assert BiometricHITLGate.evaluate_adjudication_capacity(req, tel_at_boundary, 0.10) == AdjudicationVerdict.ALLOW_T3_APPROVAL

    # Exactly 7501 bps triggers overload
    tel_load = BiometricTelemetry(
        hrv_ms=55.0,
        cognitive_load_bps=7501,  # > 7500
        circadian_phase=CircadianPhase.NORMAL,
        keystroke_entropy=3.1,
        timestamp_ns=time.time_ns(),
    )
    assert BiometricHITLGate.evaluate_adjudication_capacity(req, tel_load, 0.10) == AdjudicationVerdict.HALT_COGNITIVE_OVERLOAD

    # High keystroke entropy (> 4.5)
    tel_entropy = BiometricTelemetry(
        hrv_ms=55.0,
        cognitive_load_bps=4000,
        circadian_phase=CircadianPhase.NORMAL,
        keystroke_entropy=4.51,  # > 4.5
        timestamp_ns=time.time_ns(),
    )
    assert BiometricHITLGate.evaluate_adjudication_capacity(req, tel_entropy, 0.10) == AdjudicationVerdict.HALT_COGNITIVE_OVERLOAD


def test_fails_closed_without_telemetry() -> None:
    """Missing biometric telemetry fails closed."""
    req = T3ApprovalRequest("sha256:release", "T3", False, "sha256:intent5")
    verdict = BiometricHITLGate.evaluate_adjudication_capacity(req, None, 0.10)
    assert verdict == AdjudicationVerdict.HALT_MISSING_TELEMETRY


def test_allows_peak_alertness() -> None:
    """Alert human with healthy telemetry approves T3 action."""
    req = T3ApprovalRequest("sha256:prod", "T3", False, "sha256:intent6")
    telemetry = BiometricTelemetry(
        hrv_ms=68.0,
        cognitive_load_bps=4200,
        circadian_phase=CircadianPhase.PEAK_ALERTNESS,
        keystroke_entropy=3.4,
        timestamp_ns=time.time_ns(),
    )
    verdict = BiometricHITLGate.evaluate_adjudication_capacity(req, telemetry, 0.10)
    assert verdict == AdjudicationVerdict.ALLOW_T3_APPROVAL


def test_rejects_non_t3_requests() -> None:
    """Non-T3 tasks must not be processed by the biometric gate."""
    req = T3ApprovalRequest("sha256:t1", "T1", False, "sha256:intent7")
    with pytest.raises(ValueError, match="ERR_BIOMETRIC_GATE_ONLY_FOR_T3"):
        BiometricHITLGate.evaluate_adjudication_capacity(req, None, 0.10)


def test_telemetry_post_init_validation() -> None:
    """Telemetry validates integer basis points range and non-negative HRV."""
    # Boundary exact values 0 and 10000 bps and 0.0 hrv are valid
    tel_min = BiometricTelemetry(
        hrv_ms=0.0,
        cognitive_load_bps=0,
        circadian_phase=CircadianPhase.NORMAL,
        keystroke_entropy=0.0,
        timestamp_ns=0,
    )
    assert tel_min.cognitive_load_bps == 0
    assert tel_min.hrv_ms == 0.0

    tel_max = BiometricTelemetry(
        hrv_ms=100.0,
        cognitive_load_bps=10000,
        circadian_phase=CircadianPhase.NORMAL,
        keystroke_entropy=2.0,
        timestamp_ns=0,
    )
    assert tel_max.cognitive_load_bps == 10000

    with pytest.raises(ValueError, match="ERR_INVALID_COGNITIVE_LOAD_BPS"):
        BiometricTelemetry(
            hrv_ms=50.0,
            cognitive_load_bps=10001,  # > 10000 bps
            circadian_phase=CircadianPhase.NORMAL,
            keystroke_entropy=2.0,
            timestamp_ns=time.time_ns(),
        )

    with pytest.raises(ValueError, match="ERR_INVALID_COGNITIVE_LOAD_BPS"):
        BiometricTelemetry(
            hrv_ms=50.0,
            cognitive_load_bps=-1,
            circadian_phase=CircadianPhase.NORMAL,
            keystroke_entropy=2.0,
            timestamp_ns=time.time_ns(),
        )

    with pytest.raises(ValueError, match="ERR_INVALID_HRV"):
        BiometricTelemetry(
            hrv_ms=-0.001,
            cognitive_load_bps=5000,
            circadian_phase=CircadianPhase.NORMAL,
            keystroke_entropy=2.0,
            timestamp_ns=time.time_ns(),
        )


def test_mint_and_verify_adjudication_receipt() -> None:
    """Mints an Ed25519-signed adjudication receipt and verifies integrity."""
    sk = Ed25519PrivateKey.generate()
    req = T3ApprovalRequest("sha256:sign_action", "T3", False, "sha256:intent8")
    telemetry = BiometricTelemetry(
        hrv_ms=65.0,
        cognitive_load_bps=4500,
        circadian_phase=CircadianPhase.PEAK_ALERTNESS,
        keystroke_entropy=3.8,
        timestamp_ns=1760000000,
    )

    now_ns = time.time_ns()
    receipt = BiometricHITLGate.mint_adjudication_receipt(
        request=req,
        telemetry=telemetry,
        verdict=AdjudicationVerdict.ALLOW_T3_APPROVAL,
        timestamp_ns=now_ns,
        signing_key=sk,
    )

    assert receipt.verdict == AdjudicationVerdict.ALLOW_T3_APPROVAL
    assert receipt.telemetry_digest is not None
    assert receipt.signature_b64 is not None
    assert receipt.verify_signature() is True

    # Tampered receipt fails signature check
    tampered = BiometricAdjudicationReceipt(
        action_digest="sha256:tampered_action",
        verdict=receipt.verdict,
        telemetry_digest=receipt.telemetry_digest,
        timestamp_ns=receipt.timestamp_ns,
        issuer_public_key_hex=receipt.issuer_public_key_hex,
        signature_b64=receipt.signature_b64,
    )
    assert tampered.verify_signature() is False

    # Unsigned receipt returns False (both None)
    unsigned = BiometricAdjudicationReceipt(
        action_digest=req.action_digest,
        verdict=receipt.verdict,
        telemetry_digest=receipt.telemetry_digest,
        timestamp_ns=now_ns,
    )
    assert unsigned.verify_signature() is False

    # Partial None returns False
    partial_key = BiometricAdjudicationReceipt(
        action_digest=req.action_digest,
        verdict=receipt.verdict,
        telemetry_digest=receipt.telemetry_digest,
        timestamp_ns=now_ns,
        issuer_public_key_hex="00" * 32,
        signature_b64=None,
    )
    assert partial_key.verify_signature() is False

    partial_sig = BiometricAdjudicationReceipt(
        action_digest=req.action_digest,
        verdict=receipt.verdict,
        telemetry_digest=receipt.telemetry_digest,
        timestamp_ns=now_ns,
        issuer_public_key_hex=None,
        signature_b64="AA==",
    )
    assert partial_sig.verify_signature() is False


def test_dataclass_immutability() -> None:
    """Telemetry, requests, and receipts are frozen."""
    req = T3ApprovalRequest("sha256:req", "T3", False, "sha256:int")
    with pytest.raises(dataclasses.FrozenInstanceError):
        req.risk_tier = "T0"  # type: ignore

    tel = BiometricTelemetry(
        hrv_ms=50.0,
        cognitive_load_bps=5000,
        circadian_phase=CircadianPhase.NORMAL,
        keystroke_entropy=2.0,
        timestamp_ns=100,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        tel.hrv_ms = 40.0  # type: ignore

    rec = BiometricAdjudicationReceipt(
        action_digest="sha256:a",
        verdict=AdjudicationVerdict.ALLOW_T3_APPROVAL,
        telemetry_digest=None,
        timestamp_ns=100,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.action_digest = "sha256:mutated"  # type: ignore
