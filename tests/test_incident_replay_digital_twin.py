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
tests/test_incident_replay_digital_twin.py
================================================================================
Comprehensive verification suite for DigitalTwinSandboxReplayer.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.incident_replay_digital_twin import (
    DigitalTwinSandboxReplayer,
    IncidentFaultClassification,
    IncidentReplayCertificate,
    IncidentReplayOutcome,
    IncidentSnapshot,
    verify_incident_replay_certificate,
)


@pytest.fixture
def replayer() -> DigitalTwinSandboxReplayer:
    return DigitalTwinSandboxReplayer()


def test_nominal_ansi50_incident_replay(replayer: DigitalTwinSandboxReplayer):
    snapshot = IncidentSnapshot(
        incident_id="inc-ansi50-001",
        timestamp_utc="2026-10-29T21:00:00Z",
        fault_classification=IncidentFaultClassification.ANSI_50_OVERCURRENT_TRIP,
        pre_incident_state_caid="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        tripped_breaker_id="ANSI_50_INSTANTANEOUS_BREAKER",
        target_module="src/example_service.py",
        candidate_code="def execute(): pass  # scaffold",
        dora_materiality_score_bps=8500,
        eu_ai_act_article_14_stop_activated=True,
    )

    cert = replayer.replay_incident(snapshot, certificate_id="cert-ansi50-001")

    assert cert.certificate_id == "cert-ansi50-001"
    assert cert.incident_id == "inc-ansi50-001"
    assert cert.fault_classification == IncidentFaultClassification.ANSI_50_OVERCURRENT_TRIP
    assert cert.replay_outcome == IncidentReplayOutcome.REPLAY_DETERMINISTICALLY_CONTAINED
    assert cert.tripped_breaker_id == "ANSI_50_INSTANTANEOUS_BREAKER"
    assert cert.breaker_trip_confirmed is True
    assert cert.zero_side_effects_verified is True
    assert cert.dora_art17_investigation_payload["dora_article_17_compliance"] is True
    assert cert.dora_art17_investigation_payload["materiality_score_bps"] == 8500
    assert cert.eu_ai_act_art14_reversal_payload["eu_ai_act_article_14_compliance"] is True
    assert cert.eu_ai_act_art14_reversal_payload["human_oversight_reversal_applied"] is True
    assert cert.eu_ai_act_art14_reversal_payload["andon_cord_stop_activated"] is True
    assert cert.eu_ai_act_art14_reversal_payload["tripped_breaker_id"] == "ANSI_50_INSTANTANEOUS_BREAKER"
    assert cert.eu_ai_act_art14_reversal_payload["unauthorized_mutations_count"] == 0

    valid, err = verify_incident_replay_certificate(cert.to_dict())
    assert valid is True
    assert err == "OK"


@pytest.mark.parametrize(
    "fault,expected_breaker",
    [
        (IncidentFaultClassification.AST_MOCK_BYPASS_ATTEMPT, "AST_PURITY_ZERO_MOCK_BREAKER"),
        (IncidentFaultClassification.BIOMETRIC_HUMAN_VETO, "EO1_BIOMETRIC_HUMAN_VETO_BREAKER"),
        (IncidentFaultClassification.FORK_BOMB_RESOURCE_EXHAUSTION, "PROCESS_ISOLATION_RESOURCE_BREAKER"),
        (IncidentFaultClassification.TRANSACTIONAL_TIMEOUT_INDETERMINATE, "ANSI_86_INDETERMINATE_LOCKOUT_RELAY"),
        (IncidentFaultClassification.RULETREK_DEPENDENCY_VIOLATION, "RULETREK_DEPENDENCY_BREAKER"),
    ],
)
def test_all_fault_classifications_replay(
    replayer: DigitalTwinSandboxReplayer,
    fault: IncidentFaultClassification,
    expected_breaker: str,
):
    snapshot = IncidentSnapshot(
        incident_id=f"inc-{fault.value.lower()}",
        timestamp_utc="2026-10-29T21:10:00Z",
        fault_classification=fault,
        pre_incident_state_caid="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        tripped_breaker_id=expected_breaker,
        target_module="src/service.py",
        candidate_code="# faulty code",
    )

    cert = replayer.replay_incident(snapshot)
    assert cert.certificate_id.startswith("cert-replay-")
    assert len(cert.certificate_id) == len("cert-replay-") + 16
    assert cert.replay_outcome == IncidentReplayOutcome.REPLAY_DETERMINISTICALLY_CONTAINED
    assert cert.breaker_trip_confirmed is True
    assert cert.tripped_breaker_id == expected_breaker

    valid, err = verify_incident_replay_certificate(cert.to_dict())
    assert valid is True
    assert err == "OK"


def test_divergence_detected_on_mismatched_breaker(replayer: DigitalTwinSandboxReplayer):
    snapshot = IncidentSnapshot(
        incident_id="inc-divergent-001",
        timestamp_utc="2026-10-29T21:20:00Z",
        fault_classification=IncidentFaultClassification.ANSI_50_OVERCURRENT_TRIP,
        pre_incident_state_caid="sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        tripped_breaker_id="ANSI_86_INDETERMINATE_LOCKOUT_RELAY",
        target_module="src/anomaly.py",
        candidate_code="pass",
    )

    cert = replayer.replay_incident(snapshot)
    assert cert.replay_outcome == IncidentReplayOutcome.REPLAY_DIVERGENCE_DETECTED
    assert cert.breaker_trip_confirmed is False

    valid, err = verify_incident_replay_certificate(cert.to_dict())
    assert valid is True


def test_unknown_fault_classification_divergence(replayer: DigitalTwinSandboxReplayer, tmp_path: Path):
    snapshot = IncidentSnapshot(
        incident_id="inc-unknown-001",
        timestamp_utc="2026-10-29T21:25:00Z",
        fault_classification="UNKNOWN_FAULT",  # type: ignore
        pre_incident_state_caid="sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        tripped_breaker_id="ANY_BREAKER",
        target_module="src/unknown.py",
        candidate_code="pass",
        eu_ai_act_article_14_stop_activated=False,
    )

    cert = replayer.replay_incident(snapshot)
    assert cert.replay_outcome == IncidentReplayOutcome.REPLAY_DIVERGENCE_DETECTED
    assert cert.breaker_trip_confirmed is False
    assert cert.tripped_breaker_id == "ANY_BREAKER"
    assert cert.eu_ai_act_art14_reversal_payload["human_oversight_reversal_applied"] is False

    # Also test direct simulation output
    b_id, ok = replayer._simulate_incident_containment(snapshot, tmp_path)
    assert b_id == "UNKNOWN_BREAKER"
    assert ok is False


def test_certificate_tamper_verification(replayer: DigitalTwinSandboxReplayer):
    snapshot = IncidentSnapshot(
        incident_id="inc-tamper-001",
        timestamp_utc="2026-10-29T21:30:00Z",
        fault_classification=IncidentFaultClassification.BIOMETRIC_HUMAN_VETO,
        pre_incident_state_caid="sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        tripped_breaker_id="EO1_BIOMETRIC_HUMAN_VETO_BREAKER",
        target_module="src/trade.py",
        candidate_code="commit_trade()",
    )

    cert = replayer.replay_incident(snapshot)
    raw = cert.to_dict()

    # 1. Nominal with pinned key
    ok, err = verify_incident_replay_certificate(raw, pinned_pubkey_hex=cert.public_key_hex)
    assert ok is True
    assert err == "OK"

    # 2. Unpinned key rejection
    other_key = ed25519.Ed25519PrivateKey.generate().public_key()
    other_pub_hex = other_key.public_bytes_raw().hex()
    ok, err = verify_incident_replay_certificate(raw, pinned_pubkey_hex=other_pub_hex)
    assert ok is False
    assert err == "ERR_UNPINNED_REPLAY_PUBLIC_KEY"

    # 3. Missing fields
    corrupt_missing = dict(raw)
    del corrupt_missing["certificate_id"]
    ok, err = verify_incident_replay_certificate(corrupt_missing)
    assert ok is False
    assert err == "ERR_MISSING_CERTIFICATE_FIELDS"

    # 4. Tampered payload
    corrupt_tampered = dict(raw)
    corrupt_tampered["breaker_trip_confirmed"] = False
    ok, err = verify_incident_replay_certificate(corrupt_tampered)
    assert ok is False
    assert err == "ERR_REPLAY_CAID_MISMATCH"

    # 5. Invalid signature
    corrupt_sig = dict(raw)
    corrupt_sig["signature_hex"] = "ff" * 64
    ok, err = verify_incident_replay_certificate(corrupt_sig)
    assert ok is False
    assert err == "ERR_REPLAY_SIGNATURE_INVALID"
    assert err == "ERR_REPLAY_SIGNATURE_INVALID"

    # 6. Bad hex public key
    corrupt_hex = dict(raw)
    corrupt_hex["public_key_hex"] = "not_hex"
    ok, err = verify_incident_replay_certificate(corrupt_hex)
    assert ok is False
    assert err == "ERR_INVALID_CRYPTO_ENVELOPE"


def test_snapshot_defaults():
    s = IncidentSnapshot(
        incident_id="inc-def",
        timestamp_utc="2026-10-29T21:00:00Z",
        fault_classification=IncidentFaultClassification.ANSI_50_OVERCURRENT_TRIP,
        pre_incident_state_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        tripped_breaker_id="ANSI_50_INSTANTANEOUS_BREAKER",
        target_module="src/mod.py",
        candidate_code="pass",
    )
    assert s.dora_materiality_score_bps == 10000
    assert s.eu_ai_act_article_14_stop_activated is True
    # Valid boundaries for dora_materiality_score_bps
    s0 = IncidentSnapshot(
        incident_id="inc-0",
        timestamp_utc="2026-10-29T21:00:00Z",
        fault_classification=IncidentFaultClassification.ANSI_50_OVERCURRENT_TRIP,
        pre_incident_state_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        tripped_breaker_id="ANSI_50_INSTANTANEOUS_BREAKER",
        target_module="src/mod.py",
        candidate_code="pass",
        dora_materiality_score_bps=0,
    )
    assert s0.dora_materiality_score_bps == 0

    s_max = IncidentSnapshot(
        incident_id="inc-max",
        timestamp_utc="2026-10-29T21:00:00Z",
        fault_classification=IncidentFaultClassification.ANSI_50_OVERCURRENT_TRIP,
        pre_incident_state_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        tripped_breaker_id="ANSI_50_INSTANTANEOUS_BREAKER",
        target_module="src/mod.py",
        candidate_code="pass",
        dora_materiality_score_bps=10000,
    )
    assert s_max.dora_materiality_score_bps == 10000

    # Invalid dora_materiality_score_bps
    with pytest.raises(ValueError, match="dora_materiality_score_bps"):
        IncidentSnapshot(
            incident_id="inc-bad",
            timestamp_utc="2026-10-29T21:00:00Z",
            fault_classification=IncidentFaultClassification.ANSI_50_OVERCURRENT_TRIP,
            pre_incident_state_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            tripped_breaker_id="ANSI_50_INSTANTANEOUS_BREAKER",
            target_module="src/mod.py",
            candidate_code="pass",
            dora_materiality_score_bps=-1,
        )

    with pytest.raises(ValueError, match="dora_materiality_score_bps"):
        IncidentSnapshot(
            incident_id="inc-bad-2",
            timestamp_utc="2026-10-29T21:00:00Z",
            fault_classification=IncidentFaultClassification.ANSI_50_OVERCURRENT_TRIP,
            pre_incident_state_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            tripped_breaker_id="ANSI_50_INSTANTANEOUS_BREAKER",
            target_module="src/mod.py",
            candidate_code="pass",
            dora_materiality_score_bps=10001,
        )

    with pytest.raises(ValueError, match="dora_materiality_score_bps"):
        IncidentSnapshot(
            incident_id="inc-bad-3",
            timestamp_utc="2026-10-29T21:00:00Z",
            fault_classification=IncidentFaultClassification.ANSI_50_OVERCURRENT_TRIP,
            pre_incident_state_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            tripped_breaker_id="ANSI_50_INSTANTANEOUS_BREAKER",
            target_module="src/mod.py",
            candidate_code="pass",
            dora_materiality_score_bps="10000",  # type: ignore
        )


def test_frozen_dataclass_immutability(replayer: DigitalTwinSandboxReplayer):
    """Verifies that IncidentSnapshot and IncidentReplayCertificate are frozen."""
    from dataclasses import FrozenInstanceError
    snapshot = IncidentSnapshot(
        incident_id="inc-frozen",
        timestamp_utc="2026-10-29T21:00:00Z",
        fault_classification=IncidentFaultClassification.ANSI_50_OVERCURRENT_TRIP,
        pre_incident_state_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        tripped_breaker_id="ANSI_50_INSTANTANEOUS_BREAKER",
        target_module="src/mod.py",
        candidate_code="pass",
    )
    with pytest.raises(FrozenInstanceError):
        snapshot.incident_id = "inc-tampered"  # type: ignore

    cert = replayer.replay_incident(snapshot)
    with pytest.raises(FrozenInstanceError):
        cert.certificate_id = "cert-tampered"  # type: ignore
