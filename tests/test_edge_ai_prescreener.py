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
tests/test_edge_ai_prescreener.py
================================================================================
Comprehensive verification suite for EdgeAIPrescreener.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.edge_ai_prescreener import (
    EdgeAIPrescreener,
    EdgePrescreenReport,
    PrescreenRecommendation,
    verify_edge_prescreen_report,
)


@pytest.fixture
def critic() -> EdgeAIPrescreener:
    return EdgeAIPrescreener()


def test_nominal_low_risk_proposal(critic: EdgeAIPrescreener):
    report = critic.prescreen_proposal(
        action_type="WRITE_NON_CRITICAL_LOG",
        target_resource="artifacts/logs/run.log",
        amount_minor=100,  # $1.00
        expires_at_epoch_sec=1700003600,
        current_epoch_sec=1700000000,
        operation_id="op-nominal-001",
        report_id="rep-nominal-001",
    )

    assert report.report_id == "rep-nominal-001"
    assert report.recommendation == PrescreenRecommendation.PROCEED_TO_FACEID
    assert report.is_anomalous is False
    assert report.risk_score_bps == 1000
    assert len(report.flagged_anomalies) == 0
    assert "Proposed WRITE_NON_CRITICAL_LOG" in report.sentence_1_summary
    assert "zero structural anomalies detected" in report.sentence_2_critique

    valid, err = verify_edge_prescreen_report(report.to_dict())
    assert valid is True
    assert err == "OK"

    # EdgePrescreenReport post_init bounds
    with pytest.raises(ValueError, match="risk_score_bps"):
        EdgePrescreenReport(
            report_id="r-bad",
            target_operation_id="op",
            risk_score_bps=-1,
            is_anomalous=False,
            sentence_1_summary="s1",
            sentence_2_critique="s2",
            recommendation=PrescreenRecommendation.PROCEED_TO_FACEID,
            flagged_anomalies=[],
            report_caid="sha256:0000",
            signature_hex="00",
            public_key_hex="00",
        )
    with pytest.raises(ValueError, match="risk_score_bps"):
        EdgePrescreenReport(
            report_id="r-bad2",
            target_operation_id="op",
            risk_score_bps=10001,
            is_anomalous=False,
            sentence_1_summary="s1",
            sentence_2_critique="s2",
            recommendation=PrescreenRecommendation.PROCEED_TO_FACEID,
            flagged_anomalies=[],
            report_caid="sha256:0000",
            signature_hex="00",
            public_key_hex="00",
        )
    with pytest.raises(ValueError, match="report_caid"):
        EdgePrescreenReport(
            report_id="r-bad3",
            target_operation_id="op",
            risk_score_bps=500,
            is_anomalous=False,
            sentence_1_summary="s1",
            sentence_2_critique="s2",
            recommendation=PrescreenRecommendation.PROCEED_TO_FACEID,
            flagged_anomalies=[],
            report_caid="not_sha256",
            signature_hex="00",
            public_key_hex="00",
        )


def test_elevated_spending_scrutiny(critic: EdgeAIPrescreener):
    report = critic.prescreen_proposal(
        action_type="API_RECHARGE_ESCROW",
        target_resource="fintech/escrow/account",
        amount_minor=15000,  # $150.00 > $50.00
        expires_at_epoch_sec=1700003600,
        current_epoch_sec=1700000000,
        operation_id="op-elevated-002",
    )

    assert report.recommendation == PrescreenRecommendation.OPERATOR_SCRUTINY_REQUIRED
    assert report.is_anomalous is True
    assert 3999 < report.risk_score_bps < 4001
    assert any("ELEVATED_SPENDING_AMOUNT" in a for a in report.flagged_anomalies)
    assert "Elevated caution advised" in report.sentence_2_critique

    valid, err = verify_edge_prescreen_report(report.to_dict())
    assert valid is True
    assert err == "OK"

    # High spending without other anomalies: $600 = 60000 minor
    rep_high = critic.prescreen_proposal(
        action_type="NOMINAL_TRANSFER",
        target_resource="fintech/escrow/account",
        amount_minor=60000,
        expires_at_epoch_sec=1700003600,
        current_epoch_sec=1700000000,
        operation_id="op-high-spend",
    )
    assert 4999 < rep_high.risk_score_bps < 5001
    assert any("HIGH_SPENDING_AMOUNT" in a for a in rep_high.flagged_anomalies)


def test_critical_risk_recommend_veto(critic: EdgeAIPrescreener):
    # Destructive action targeting /etc/ with large spending
    report = critic.prescreen_proposal(
        action_type="DESTRUCTIVE_PURGE_SYSTEM",
        target_resource="/etc/config.json",
        amount_minor=100000,  # $1000.00
        expires_at_epoch_sec=1700003600,
        current_epoch_sec=1700000000,
        operation_id="op-critical-003",
    )

    assert report.recommendation == PrescreenRecommendation.RECOMMEND_VETO
    assert report.is_anomalous is True
    assert report.risk_score_bps == 10000
    assert any("HIGH_SPENDING_AMOUNT" in a for a in report.flagged_anomalies)
    assert any("SENSITIVE_RESOURCE_PATTERN" in a for a in report.flagged_anomalies)
    assert any("DESTRUCTIVE_ACTION_TYPE" in a for a in report.flagged_anomalies)
    assert "Critical risk detected" in report.sentence_2_critique
    assert "human veto recommended" in report.sentence_2_critique

    valid, err = verify_edge_prescreen_report(report.to_dict())
    assert valid is True
    assert err == "OK"

    # Sensitive resource alone
    rep_env = critic.prescreen_proposal(
        action_type="READ_FILE",
        target_resource=".env.secret",
        amount_minor=100,
        expires_at_epoch_sec=1700003600,
        current_epoch_sec=1700000000,
        operation_id="op-env",
    )
    assert rep_env.risk_score_bps == 6000  # 1000 + 5000


def test_ttl_anomaly_detection(critic: EdgeAIPrescreener):
    # TTL boundary: exactly 15s is nominal
    report_boundary_15 = critic.prescreen_proposal(
        action_type="MUTATE_CACHE",
        target_resource="cache/item",
        amount_minor=10,
        expires_at_epoch_sec=1700000015,
        current_epoch_sec=1700000000,
        operation_id="op-ttl-15",
    )
    assert "EXPIRATION_TTL_TOO_SHORT" not in report_boundary_15.flagged_anomalies
    assert report_boundary_15.risk_score_bps == 1000

    # TTL too short (14 seconds < 15s)
    report_short = critic.prescreen_proposal(
        action_type="MUTATE_CACHE",
        target_resource="cache/item",
        amount_minor=10,
        expires_at_epoch_sec=1700000014,
        current_epoch_sec=1700000000,
        operation_id="op-ttl-short",
    )
    assert "EXPIRATION_TTL_TOO_SHORT" in report_short.flagged_anomalies
    assert report_short.risk_score_bps == 3500  # 1000 + 2500

    # TTL boundary: exactly 86400 * 7 is nominal
    report_boundary_7d = critic.prescreen_proposal(
        action_type="MUTATE_CACHE",
        target_resource="cache/item",
        amount_minor=10,
        expires_at_epoch_sec=1700000000 + 86400 * 7,
        current_epoch_sec=1700000000,
        operation_id="op-ttl-7d",
    )
    assert "EXPIRATION_TTL_EXCESSIVE" not in report_boundary_7d.flagged_anomalies
    assert report_boundary_7d.risk_score_bps == 1000

    # TTL excessive (> 7 days, 86400 * 7 + 1)
    report_long = critic.prescreen_proposal(
        action_type="MUTATE_CACHE",
        target_resource="cache/item",
        amount_minor=10,
        expires_at_epoch_sec=1700000000 + 86400 * 7 + 1,
        current_epoch_sec=1700000000,
        operation_id="op-ttl-long",
    )
    assert "EXPIRATION_TTL_EXCESSIVE" in report_long.flagged_anomalies
    assert 2499 < report_long.risk_score_bps < 2501  # 1000 + 1500


def test_report_verification_tamper_defenses(critic: EdgeAIPrescreener):
    report = critic.prescreen_proposal(
        action_type="NOMINAL_CHECK",
        target_resource="local/path",
        amount_minor=50,
        expires_at_epoch_sec=1700003600,
        current_epoch_sec=1700000000,
        operation_id="op-tamper-check",
    )
    raw = report.to_dict()

    # 1. Pinned key nominal
    ok, err = verify_edge_prescreen_report(raw, pinned_pubkey_hex=report.public_key_hex)
    assert ok is True
    assert err == "OK"

    # 2. Unpinned key
    other_key = ed25519.Ed25519PrivateKey.generate().public_key()
    other_hex = other_key.public_bytes_raw().hex()
    ok, err = verify_edge_prescreen_report(raw, pinned_pubkey_hex=other_hex)
    assert ok is False
    assert err == "ERR_UNPINNED_CRITIC_PUBLIC_KEY"

    # 3. Missing fields
    corrupt_missing = dict(raw)
    del corrupt_missing["sentence_1_summary"]
    ok, err = verify_edge_prescreen_report(corrupt_missing)
    assert ok is False
    assert err == "ERR_MISSING_REPORT_FIELDS"

    # 4. Tampered risk score
    corrupt_tampered = dict(raw)
    corrupt_tampered["risk_score_bps"] = 9999
    ok, err = verify_edge_prescreen_report(corrupt_tampered)
    assert ok is False
    assert err == "ERR_REPORT_CAID_MISMATCH"

    # 5. Invalid signature
    corrupt_sig = dict(raw)
    corrupt_sig["signature_hex"] = "aa" * 64
    ok, err = verify_edge_prescreen_report(corrupt_sig)
    assert ok is False
    assert err == "ERR_CRITIC_SIGNATURE_INVALID"

    # 6. Float forbidden
    corrupt_float = dict(raw)
    corrupt_float["risk_score_bps"] = 1200.0
    ok, err = verify_edge_prescreen_report(corrupt_float)
    assert ok is False
    assert err == "ERR_FLOAT_FORBIDDEN_IN_REPORT"

    # 7. Invalid crypto envelope (non-hex)
    corrupt_hex = dict(raw)
    corrupt_hex["public_key_hex"] = "not_valid_hex"
    ok, err = verify_edge_prescreen_report(corrupt_hex)
    assert ok is False
    assert err == "ERR_INVALID_CRYPTO_ENVELOPE"


def test_edge_ai_prescreener_exact_boundaries(critic: EdgeAIPrescreener):
    """Verifies boundary constants and post_init validations."""
    assert 49999 < EdgeAIPrescreener.HIGH_RISK_SPENDING_MINOR < 50001

    # Auto-generated report_id length (14 chars prefix + 16 hex = 30)
    rep_auto = critic.prescreen_proposal(
        action_type="LOG",
        target_resource="out.log",
        amount_minor=0,
        expires_at_epoch_sec=1700003600,
        current_epoch_sec=1700000000,
        operation_id="op-auto-id-check",
    )
    assert len(rep_auto.report_id) == 30  # claim: config
    assert rep_auto.report_id.startswith("report-critic-")

    # Boundary risk_score_bps = 0
    raw_dict = rep_auto.to_dict()
    r0 = EdgePrescreenReport(
        report_id=raw_dict["report_id"],
        target_operation_id=raw_dict["target_operation_id"],
        risk_score_bps=0,  # boundary: exactly zero
        is_anomalous=False,
        sentence_1_summary=raw_dict["sentence_1_summary"],
        sentence_2_critique=raw_dict["sentence_2_critique"],
        recommendation=rep_auto.recommendation,
        flagged_anomalies=[],
        report_caid="sha256:abcd",
        signature_hex=raw_dict["signature_hex"],
        public_key_hex=raw_dict["public_key_hex"],
    )
    assert r0.risk_score_bps == 0  # claim: config

    with pytest.raises(ValueError, match="0..10000 bps"):
        EdgePrescreenReport(
            report_id=raw_dict["report_id"],
            target_operation_id=raw_dict["target_operation_id"],
            risk_score_bps=-1,
            is_anomalous=False,
            sentence_1_summary=raw_dict["sentence_1_summary"],
            sentence_2_critique=raw_dict["sentence_2_critique"],
            recommendation=rep_auto.recommendation,
            flagged_anomalies=[],
            report_caid="sha256:abcd",
            signature_hex=raw_dict["signature_hex"],
            public_key_hex=raw_dict["public_key_hex"],
        )
