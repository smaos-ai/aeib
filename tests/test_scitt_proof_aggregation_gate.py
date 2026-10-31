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
tests/test_scitt_proof_aggregation_gate.py
================================================================================
Verification Suite for ScittProofAggregationGate.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. Nominal 4-phase SCITT proof aggregation cycle and certificate generation.
2. Certificate dictionary mapping and zero-float validation.
3. Certificate file verification and tamper resistance.
4. Missing certificate file handling.
5. CLI execution workflow (--out, valid --verify, and invalid --verify).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from tools.scitt_proof_aggregation_gate import (
    ScittAggregationCertificate,
    ScittProofAggregationGate,
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
    """Evaluates nominal 4-phase SCITT proof aggregation cycle."""
    gate = ScittProofAggregationGate()
    try:
        cert = gate.run_verification_cycle()
        assert isinstance(cert, ScittAggregationCertificate)
        assert cert.certificate_version == "1.0.0"
        assert cert.status == "SCITT_AGGREGATION_EVALUATION_COMPLETE"
        assert cert.certificate_caid.startswith("sha256:")
        assert cert.federated_super_root_caid.startswith("sha256:")
        assert cert.participating_regions_count == 3
        assert cert.total_leaves_witnessed == 550  # 120 + 250 + 180
        assert cert.inclusion_proofs_verified is True
        assert cert.consistency_proofs_verified is True
        assert cert.created_epoch_ms > 1_700_000_000_000
        assert len(gate.reconciler.leaves) == 5
    finally:
        gate.close()


def test_gate_serialization_and_zero_floats() -> None:
    """Evaluates certificate dictionary serialization and zero-float invariant."""
    gate = ScittProofAggregationGate()
    try:
        cert = gate.run_verification_cycle()
        cert_dict = cert.to_dict()
        assert cert_dict["certificate_version"] == "1.0.0"
        assert cert_dict["participating_regions_count"] == 3
        assert cert_dict["total_leaves_witnessed"] == 550
        _assert_zero_floats(cert_dict)
    finally:
        gate.close()


def test_gate_file_verification_and_tampering(tmp_path: Path) -> None:
    """Evaluates certificate file verification and tamper resistance."""
    cert_file = tmp_path / "valid_scitt_cert.json"

    gate = ScittProofAggregationGate()
    try:
        cert = gate.run_verification_cycle()
        cert_file.write_text(json.dumps(cert.to_dict(), indent=2), encoding="utf-8")
    finally:
        gate.close()

    assert verify_certificate_file(str(cert_file)) is True

    # Tampering test: alter total_leaves_witnessed
    tampered_data = json.loads(cert_file.read_text(encoding="utf-8"))
    tampered_data["total_leaves_witnessed"] = 999
    tampered_file = tmp_path / "tampered_scitt_cert.json"
    tampered_file.write_text(json.dumps(tampered_data, indent=2), encoding="utf-8")

    assert verify_certificate_file(str(tampered_file)) is False


def test_gate_missing_file_raises(tmp_path: Path) -> None:
    """Evaluates that non-existent certificate file path raises FileNotFoundError."""
    missing_path = tmp_path / "non_existent_scitt.json"
    with pytest.raises(FileNotFoundError):
        verify_certificate_file(str(missing_path))


def test_gate_cli_workflow(tmp_path: Path) -> None:
    """Evaluates CLI options for running the gate and verifying output across nested paths."""
    out_file = tmp_path / "nested" / "scitt" / "cli_cert.json"

    # 1. Run generation
    with patch.object(sys, "argv", ["scitt_proof_aggregation_gate.py", "--out", str(out_file)]):
        exit_code = main()
        assert exit_code == 0
        assert out_file.exists()

    # 2. Run verification on valid file (exit code 0)
    with patch.object(sys, "argv", ["scitt_proof_aggregation_gate.py", "--verify", str(out_file)]):
        exit_code_verify = main()
        assert exit_code_verify == 0

    # 3. Run verification on tampered file (exit code 1)
    tampered_p = tmp_path / "nested" / "scitt" / "cli_tampered.json"
    data = json.loads(out_file.read_text(encoding="utf-8"))
    data["total_leaves_witnessed"] = 0
    tampered_p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    with patch.object(sys, "argv", ["scitt_proof_aggregation_gate.py", "--verify", str(tampered_p)]):
        exit_code_fail = main()
        assert exit_code_fail == 1
