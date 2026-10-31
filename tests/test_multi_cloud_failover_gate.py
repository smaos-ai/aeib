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
tests/test_multi_cloud_failover_gate.py
================================================================================
Verification Suite for MultiCloudFailoverGate.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. Nominal 4-phase failover verification cycle and certificate generation.
2. Default target node profiles, primary flags, and priority order.
3. Certificate dictionary mapping and zero-float validation.
4. Certificate verification and cryptographic tamper detection.
5. Missing certificate file handling.
6. CLI execution workflow (--out and --verify flags) with nested directories.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from tools.multi_cloud_failover_gate import (
    DEFAULT_TARGET_NODES,
    MultiCloudFailoverCertificate,
    MultiCloudFailoverGate,
    main,
    verify_certificate_file,
)


def _assert_zero_floats(obj: Any) -> None:
    """Recursively asserts that no float values exist in the object graph."""
    if isinstance(obj, float):
        raise AssertionError(f"Found float value: {obj}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_zero_floats(k)
            _assert_zero_floats(v)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            _assert_zero_floats(item)


def test_gate_nominal_cycle() -> None:
    """Evaluates nominal 4-phase multi-cloud failover verification cycle."""
    gate = MultiCloudFailoverGate()
    try:
        cert = gate.run_verification_cycle()
        assert isinstance(cert, MultiCloudFailoverCertificate)
        assert cert.certificate_version == "1.0.0"
        assert cert.status == "FAILOVER_EVALUATION_COMPLETE"
        assert cert.certificate_caid.startswith("sha256:")
        assert cert.participating_clouds_count == 4
        assert cert.initial_primary == "aws-us-east-1"
        assert cert.failover_primary == "gcp-europe-west3"
        assert cert.final_epoch_id == 2
        assert cert.stale_epoch_fencing_verified is True
        assert cert.quorum_maintained is True
        assert cert.created_epoch_ms > 1_700_000_000_000

        # Verify orchestrator internal trigger reason was timeout-driven
        assert gate.orchestrator.active_failover_event is not None
        assert (
            gate.orchestrator.active_failover_event.trigger_reason
            == "CONSECUTIVE_HEARTBEAT_TIMEOUTS_EXCEEDED"
        )
        assert gate.orchestrator.consecutive_timeouts["aws-us-east-1"] == 3
    finally:
        gate.close()


def test_gate_target_nodes_and_defaults() -> None:
    """Evaluates default target node configurations, primary flags, and priority ranking."""
    assert len(DEFAULT_TARGET_NODES) == 4
    providers = [n.cloud_provider for n in DEFAULT_TARGET_NODES]
    assert providers == ["AWS", "GCP", "AZURE", "ON_PREM"]

    ranks = [n.priority_rank for n in DEFAULT_TARGET_NODES]
    assert ranks == [1, 2, 3, 4]

    assert DEFAULT_TARGET_NODES[0].is_active_primary is True
    assert DEFAULT_TARGET_NODES[1].is_active_primary is False
    assert DEFAULT_TARGET_NODES[2].is_active_primary is False
    assert DEFAULT_TARGET_NODES[3].is_active_primary is False


def test_gate_serialization_and_zero_floats() -> None:
    """Evaluates certificate dictionary serialization and zero-float invariant."""
    gate = MultiCloudFailoverGate()
    try:
        cert = gate.run_verification_cycle()
        cert_dict = cert.to_dict()
        assert cert_dict["certificate_version"] == "1.0.0"
        assert cert_dict["final_epoch_id"] == 2
        assert cert_dict["initial_primary"] == "aws-us-east-1"
        assert cert_dict["failover_primary"] == "gcp-europe-west3"
        assert cert_dict["quorum_maintained"] is True
        assert cert_dict["stale_epoch_fencing_verified"] is True
        _assert_zero_floats(cert_dict)
    finally:
        gate.close()


def test_gate_file_verification_and_tampering(tmp_path: Path) -> None:
    """Evaluates certificate file verification and tamper resistance."""
    cert_file = tmp_path / "valid_cert.json"

    gate = MultiCloudFailoverGate()
    try:
        cert = gate.run_verification_cycle()
        cert_file.write_text(json.dumps(cert.to_dict(), indent=2), encoding="utf-8")
    finally:
        gate.close()

    assert verify_certificate_file(str(cert_file)) is True

    # Tampering test: alter final_epoch_id
    tampered_data = json.loads(cert_file.read_text(encoding="utf-8"))
    tampered_data["final_epoch_id"] = 99
    tampered_file = tmp_path / "tampered_cert.json"
    tampered_file.write_text(json.dumps(tampered_data, indent=2), encoding="utf-8")

    assert verify_certificate_file(str(tampered_file)) is False


def test_gate_missing_file_raises(tmp_path: Path) -> None:
    """Evaluates that non-existent certificate file path raises FileNotFoundError."""
    missing_path = tmp_path / "non_existent.json"
    with pytest.raises(FileNotFoundError):
        verify_certificate_file(str(missing_path))


def test_gate_cli_workflow(tmp_path: Path) -> None:
    """Evaluates CLI options for running the gate and verifying output across nested paths."""
    out_file = tmp_path / "nested" / "sub" / "cli_cert.json"

    # Run generation
    with patch.object(sys, "argv", ["multi_cloud_failover_gate.py", "--out", str(out_file)]):
        exit_code = main()
        assert exit_code == 0
        assert out_file.exists()

    # Run verification
    with patch.object(sys, "argv", ["multi_cloud_failover_gate.py", "--verify", str(out_file)]):
        exit_code_verify = main()
        assert exit_code_verify == 0
