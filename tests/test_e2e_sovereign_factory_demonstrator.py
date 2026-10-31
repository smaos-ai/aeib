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
tests/test_e2e_sovereign_factory_demonstrator.py
================================================================================
Verification Suite for the Seven-Layer Sovereign Factory Demonstrator.

Status: INTERNAL PREVIEW COMMISSIONED.
Zero mocks, zero floats, deterministic cryptographic validation.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tools.e2e_sovereign_factory_demonstrator import (
    SovereignFactoryDemonstrator,
    SovereignFactoryExecutionPassport,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_1_e2e_demonstrator_full_execution_flow() -> None:
    demonstrator = SovereignFactoryDemonstrator(db_path=":memory:")
    intent = "Deploy hardened banking microservice with deterministic idempotency gates."
    passport, telemetry = demonstrator.run_demonstration(intent)

    assert isinstance(passport, SovereignFactoryExecutionPassport)
    assert passport.all_layers_verified is True
    assert passport.status == "INTERNAL PREVIEW COMMISSIONED"
    assert passport.root_intent_caid.startswith("sha256:")
    assert passport.layer2_spiffe_id.startswith("spiffe://sovereign.nexus/agent/")
    assert passport.layer2_bpf_lsm_digest.startswith("sha256:")
    assert passport.layer3_egress_receipt_caid.startswith("sha256:")
    assert passport.layer4_wal_reconciled_caid == passport.layer3_egress_receipt_caid

    # Layer 4 Telemetry Check
    assert telemetry["layer4"]["duplicate_retry_blocked"] is True
    assert telemetry["layer4"]["reconciled_disposition"] == "COMMITTED"

    # Layer 5 Kiro stress test metrics
    assert passport.layer5_auto_merged == 755
    assert passport.layer5_human_escalated == 100
    assert passport.layer5_single_scope_halted == 100
    assert passport.layer5_smurfing_halted == 45
    assert passport.layer5_uncontained_merges == 0

    # Layer 6 A2A Trajectory Drift & Monotonic Taint
    assert passport.layer6_child_warrant_caid.startswith("sha256:")
    assert passport.layer6_trajectory_drift_bps <= 4000
    assert telemetry["layer6"]["assigned_taint_level"] == 1
    assert telemetry["layer6"]["drift_verdict"] == "OK_TRAJECTORY_ALIGNED"

    # Layer 7 Jidoka AST & Visual Regression
    assert passport.layer7_ui_constraint_caid.startswith("sha256:")
    assert passport.layer7_visual_divergence_bps <= 100
    assert telemetry["layer7"]["ui_constraint_passed"] is True
    assert telemetry["layer7"]["visual_status_code"] == "OK_VISUAL_REGRESSION_SATISFIED"

    # Performance boundary
    assert passport.execution_duration_ms >= 0
    assert passport.execution_duration_ms < 5000


def test_2_demonstrator_cli_invocation_and_disk_passport() -> None:
    with tempfile.TemporaryDirectory(prefix="sovereign_test_passport_") as tmp_dir:
        out_path = Path(tmp_dir) / "test_passport.json"
        cmd = [
            sys.executable,
            str(REPO_ROOT / "tools" / "e2e_sovereign_factory_demonstrator.py"),
            "--intent",
            "CLI test intent verifying disk serialization and zero float purity.",
            "--out",
            str(out_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert "SOVEREIGNNEXUS SEVEN-LAYER FACTORY DEMONSTRATOR" in res.stdout
        assert "SEALED PASSPORT WRITTEN TO" in res.stdout
        assert out_path.exists()

        raw_data = json.loads(out_path.read_text(encoding="utf-8"))
        assert raw_data["all_layers_verified"] is True
        assert raw_data["layer5_uncontained_merges"] == 0
        assert raw_data["layer5_smurfing_halted"] == 45
        assert raw_data["status"] == "INTERNAL PREVIEW COMMISSIONED"

        # Verify zero float contamination
        def _check_no_floats(obj: object) -> None:
            if isinstance(obj, float):
                raise AssertionError(f"Forbidden float detected in serialized passport: {obj}")
            elif isinstance(obj, dict):
                for v in obj.values():
                    _check_no_floats(v)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _check_no_floats(item)

        _check_no_floats(raw_data)


def test_3_epistemic_purity_and_zero_mocks() -> None:
    source_file = REPO_ROOT / "tools" / "e2e_sovereign_factory_demonstrator.py"
    text = source_file.read_text(encoding="utf-8").lower()

    banned_promotional_tokens = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unhack" + "able",
    ]
    for token in banned_promotional_tokens:
        assert token not in text, f"Forbidden promotional token '{token}' in demonstrator source"

    mock_tokens = ["mock.", "unittest.mock", "magicmock", "monkeypatch"]
    for token in mock_tokens:
        assert token not in text, f"Forbidden mock token '{token}' in demonstrator source"


def test_4_custom_drift_threshold_and_cli_output() -> None:
    demonstrator = SovereignFactoryDemonstrator(db_path=":memory:", max_drift_threshold_bps=5000)
    assert demonstrator.max_drift_threshold_bps == 5000
    passport, telemetry = demonstrator.run_demonstration("Testing custom drift configuration.")
    assert passport.all_layers_verified is True
    assert "layer1" in telemetry
    assert "layer2" in telemetry
    assert "layer3" in telemetry
    assert "layer4" in telemetry
    assert "layer5" in telemetry
    assert "layer6" in telemetry
    assert "layer7" in telemetry

    # Verify that strict threshold (< 2223 bps) halts trajectory drift
    strict_demonstrator = SovereignFactoryDemonstrator(db_path=":memory:", max_drift_threshold_bps=1000)
    with pytest.raises(AssertionError):
        strict_demonstrator.run_demonstration("Testing strict drift cutoff.")

