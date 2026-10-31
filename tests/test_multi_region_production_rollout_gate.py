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
tests/test_multi_region_production_rollout_gate.py
================================================================================
Verification suite for MultiRegionRolloutGate and rollout certificate integrity.
Evaluated under the stated model across 5 target cloud regions with unmocked crypto.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.multi_region_production_rollout_gate import (
    MultiRegionRolloutCertificate,
    MultiRegionRolloutGate,
    RegionDeploymentProfile,
    main,
    sha256_jcs_caid,
)
import subprocess
import sys


@pytest.fixture
def rollout_gate() -> MultiRegionRolloutGate:
    return MultiRegionRolloutGate()


def test_rollout_gate_nominal_execution(rollout_gate: MultiRegionRolloutGate, tmp_path: Path):
    """Evaluates nominal multi-region pre-flight orchestration across 5 regions."""
    cert, telemetry = rollout_gate.run_preflight_evaluation(working_dir=tmp_path)

    assert isinstance(cert, MultiRegionRolloutCertificate)
    assert cert.status == "INTERNAL PREVIEW COMMISSIONED"
    assert cert.certificate_version == "1.0.0"
    assert cert.created_epoch_ms > 1_700_000_000_000
    assert cert.target_regions_count == 5
    assert cert.manifests_validated_count == 5
    assert cert.idempotency_fencing_verified is True
    assert cert.edge_latch_mean_latency_ms <= 5
    assert cert.global_merkle_batch_root.startswith("sha256:")
    assert cert.certificate_caid.startswith("sha256:")

    assert "regions_evaluated" in telemetry
    assert len(telemetry["regions_evaluated"]) == 5
    assert "us-east-1" in telemetry["regions_evaluated"]
    assert "eu-central-1" in telemetry["regions_evaluated"]
    assert telemetry["edge_latched_intents_count"] == 10
    assert telemetry["wan_simulated_rtt_ms"] == 160
    assert telemetry["manifest_max_blast_radius_bps"] == 3000


def test_rollout_gate_deployment_profiles(rollout_gate: MultiRegionRolloutGate):
    """Verifies strict constants in deployment profiles."""
    assert rollout_gate.MAX_BLAST_RADIUS_BPS == 3000
    assert rollout_gate.SIMULATED_WAN_RTT_MS == 160
    assert rollout_gate.DISPATCH_ITERATIONS_COUNT == 10

    profiles = rollout_gate.DEPLOYMENT_PROFILES
    assert len(profiles) == 5

    assert profiles[0].region_id == "us-east-1"
    assert profiles[0].observed_rtt_ms == 20
    assert profiles[0].jitter_threshold_bps == 1500

    assert profiles[1].region_id == "us-west-2"
    assert profiles[1].observed_rtt_ms == 25
    assert profiles[1].jitter_threshold_bps == 2500

    assert profiles[2].region_id == "eu-west-1"
    assert profiles[2].observed_rtt_ms == 110
    assert profiles[2].jitter_threshold_bps == 3000

    assert profiles[3].region_id == "eu-central-1"
    assert profiles[3].observed_rtt_ms == 125
    assert profiles[3].jitter_threshold_bps == 3500

    assert profiles[4].region_id == "ap-northeast-1"
    assert profiles[4].observed_rtt_ms == 180
    assert profiles[4].jitter_threshold_bps == 4000


def test_rollout_gate_idempotency_fencing_failure(tmp_path: Path):
    """Evaluates fail-closed exception when idempotency fencing requirements fail."""
    gate = MultiRegionRolloutGate()
    # Configure eu-central-1 with artificially low RTT (10ms) so transatlantic jitter stays low
    # causing receipt3 to be COMMITTED instead of FENCED_PARTITION
    gate.DEPLOYMENT_PROFILES = (
        RegionDeploymentProfile("us-east-1", 20, 1500, "spiffe://sovereign.nexus/ns/system/sa/gw-us-east"),
        RegionDeploymentProfile("us-west-2", 25, 2500, "spiffe://sovereign.nexus/ns/system/sa/gw-us-west"),
        RegionDeploymentProfile("eu-west-1", 110, 3000, "spiffe://sovereign.nexus/ns/system/sa/gw-eu-west"),
        RegionDeploymentProfile("eu-central-1", 10, 3500, "spiffe://sovereign.nexus/ns/system/sa/gw-eu-central"),
        RegionDeploymentProfile("ap-northeast-1", 180, 4000, "spiffe://sovereign.nexus/ns/system/sa/gw-ap-northeast"),
    )
    with pytest.raises(RuntimeError, match="ERR_IDEMPOTENCY_FENCING_FAILED"):
        gate.run_preflight_evaluation(working_dir=tmp_path)


def test_rollout_gate_serialization_and_zero_floats(rollout_gate: MultiRegionRolloutGate, tmp_path: Path):
    """Verifies RFC 8785 JCS zero-float invariant and deterministic CAID generation."""
    cert, _ = rollout_gate.run_preflight_evaluation(working_dir=tmp_path)
    cert_dict = cert.to_dict()

    for k, v in cert_dict.items():
        assert not isinstance(v, float), f"Forbidden float in field: {k}"

    body = {k: v for k, v in cert_dict.items() if k != "certificate_caid"}
    expected_caid = sha256_jcs_caid(body)
    assert cert.certificate_caid == expected_caid


def test_rollout_gate_file_verification_and_tampering(
    rollout_gate: MultiRegionRolloutGate,
    tmp_path: Path,
):
    """Evaluates certificate persistence, verification, and tamper rejection."""
    cert, _ = rollout_gate.run_preflight_evaluation(working_dir=tmp_path)
    cert_file = tmp_path / "test_rollout_cert.json"
    cert_file.write_text(json.dumps(cert.to_dict(), indent=2), encoding="utf-8")

    # 1. Nominal verification
    assert MultiRegionRolloutGate.verify_certificate_file(cert_file) is True

    # 2. Tampered latency rejection
    data = json.loads(cert_file.read_text(encoding="utf-8"))
    data["edge_latch_mean_latency_ms"] = 999
    tampered_file = tmp_path / "tampered_rollout_cert.json"
    tampered_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert MultiRegionRolloutGate.verify_certificate_file(tampered_file) is False

    # 3. Tampered status rejection
    data_status = json.loads(cert_file.read_text(encoding="utf-8"))
    data_status["status"] = "PRODUCTION_CERTIFIED"
    status_tampered = tmp_path / "status_tampered_rollout_cert.json"
    status_tampered.write_text(json.dumps(data_status, indent=2), encoding="utf-8")
    assert MultiRegionRolloutGate.verify_certificate_file(status_tampered) is False


def test_rollout_gate_missing_and_corrupt_files(tmp_path: Path):
    """Evaluates fail-closed handling of missing and corrupt certificate files."""
    missing_path = tmp_path / "nonexistent.json"
    assert MultiRegionRolloutGate.verify_certificate_file(missing_path) is False

    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text("{invalid json...", encoding="utf-8")
    assert MultiRegionRolloutGate.verify_certificate_file(corrupt_path) is False

    # Edge cases for verify_certificate_file:
    empty_caid = tmp_path / "empty_caid.json"
    empty_caid.write_text(json.dumps({"certificate_caid": ""}), encoding="utf-8")
    assert MultiRegionRolloutGate.verify_certificate_file(empty_caid) is False

    non_str_caid = tmp_path / "non_str_caid.json"
    non_str_caid.write_text(json.dumps({"certificate_caid": 12345}), encoding="utf-8")
    assert MultiRegionRolloutGate.verify_certificate_file(non_str_caid) is False

    non_sha_caid = tmp_path / "non_sha_caid.json"
    non_sha_caid.write_text(json.dumps({"certificate_caid": "md5:abcd"}), encoding="utf-8")
    assert MultiRegionRolloutGate.verify_certificate_file(non_sha_caid) is False

    no_caid = tmp_path / "no_caid.json"
    no_caid.write_text(json.dumps({"status": "INTERNAL PREVIEW COMMISSIONED"}), encoding="utf-8")
    assert MultiRegionRolloutGate.verify_certificate_file(no_caid) is False


def test_rollout_gate_cli_workflow(tmp_path: Path):
    """Evaluates CLI execution and verification round-trip."""
    cert_path = tmp_path / "cli_cert.json"
    res1 = subprocess.run(
        [sys.executable, "tools/multi_region_production_rollout_gate.py", "--out", str(cert_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "MULTI-REGION PRODUCTION ROLLOUT PRE-FLIGHT VERIFICATION" in res1.stdout
    assert cert_path.exists()
    cert_data = json.loads(cert_path.read_text(encoding="utf-8"))
    assert f"Global Merkle Batch Root:       {cert_data['global_merkle_batch_root'][:32]}..." in res1.stdout

    res2 = subprocess.run(
        [sys.executable, "tools/multi_region_production_rollout_gate.py", "--verify", str(cert_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "[✓] Multi-Region Rollout Certificate Verified" in res2.stdout

    tampered_path = tmp_path / "tampered_cli.json"
    tampered_path.write_text(json.dumps({"certificate_caid": "sha256:0000000000000000000000000000000000000000000000000000000000000000", "tampered": True}), encoding="utf-8")
    res3 = subprocess.run(
        [sys.executable, "tools/multi_region_production_rollout_gate.py", "--verify", str(tampered_path)],
        capture_output=True,
        text=True,
    )
    assert res3.returncode == 1
    assert "[✗] Certificate Verification Failed" in res3.stderr
