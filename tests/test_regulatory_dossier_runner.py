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
tests/test_regulatory_dossier_runner.py
================================================================================
Comprehensive verification suite for RegulatoryDossierRunner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from tools.regulatory_dossier_runner import (
    RegulatoryCommissioningDossier,
    RegulatoryDossierRunner,
    RegulatoryStatus,
    main,
    verify_regulatory_dossier,
)


@pytest.fixture
def runner() -> RegulatoryDossierRunner:
    return RegulatoryDossierRunner()


def test_nominal_full_dossier_audit(runner: RegulatoryDossierRunner):
    dossier = runner.run_full_dossier_audit(mode="OFFLINE", dossier_id="test-dossier-001")

    assert dossier.dossier_id == "test-dossier-001"
    assert dossier.regulatory_status == RegulatoryStatus.CERTIFIED_REGULATORY_COMPLIANT
    assert dossier.total_stages_commissioned == 6
    assert dossier.dora_materiality_score_bps == 10000
    assert dossier.rfs_certificate_caid.startswith("sha256:")
    assert dossier.consensus_mesh_caid.startswith("sha256:")
    assert dossier.incident_replay_caid.startswith("sha256:")
    assert dossier.dossier_caid.startswith("sha256:")
    assert dossier.biometric_hardware_gate_verified is True
    assert dossier.ast_zero_mock_pure is True
    assert dossier.claim_integrity_verified is True
    assert dossier.dora_art17_status == "COMPLIANT_CONTAINED"
    assert dossier.eu_ai_act_art14_status == "COMPLIANT_HUMAN_OVERSIGHT_PINNED"

    valid, err = verify_regulatory_dossier(dossier.to_dict())
    assert valid is True
    assert err == "OK"


def test_dossier_verification_tamper_defenses(runner: RegulatoryDossierRunner):
    dossier = runner.run_full_dossier_audit(mode="OFFLINE")
    raw = dossier.to_dict()

    # 1. Nominal with pinned key
    ok, err = verify_regulatory_dossier(raw, pinned_pubkey_hex=dossier.public_key_hex)
    assert ok is True
    assert err == "OK"

    # 2. Unpinned key
    other_key = ed25519.Ed25519PrivateKey.generate().public_key()
    other_pub_hex = other_key.public_bytes_raw().hex()
    ok, err = verify_regulatory_dossier(raw, pinned_pubkey_hex=other_pub_hex)
    assert ok is False
    assert err == "ERR_UNPINNED_DOSSIER_PUBLIC_KEY"

    # 3. Missing fields
    corrupt_missing = dict(raw)
    del corrupt_missing["dossier_id"]
    ok, err = verify_regulatory_dossier(corrupt_missing)
    assert ok is False
    assert err == "ERR_MISSING_DOSSIER_FIELDS"

    # 4. Tampered payload
    corrupt_tampered = dict(raw)
    corrupt_tampered["total_stages_commissioned"] = 7
    ok, err = verify_regulatory_dossier(corrupt_tampered)
    assert ok is False
    assert err == "ERR_DOSSIER_CAID_MISMATCH"

    # 5. Invalid signature
    corrupt_sig = dict(raw)
    corrupt_sig["signature_hex"] = "00" * 64
    ok, err = verify_regulatory_dossier(corrupt_sig)
    assert ok is False
    assert err == "ERR_DOSSIER_SIGNATURE_INVALID"
    assert err == "ERR_DOSSIER_SIGNATURE_INVALID"

    # 6. Bad hex public key
    corrupt_hex = dict(raw)
    corrupt_hex["public_key_hex"] = "bad_hex"
    ok, err = verify_regulatory_dossier(corrupt_hex)
    assert ok is False
    assert err == "ERR_INVALID_CRYPTO_ENVELOPE"

    # 7. Float forbidden
    corrupt_float = dict(raw)
    corrupt_float["total_stages_commissioned"] = 6.0
    ok, err = verify_regulatory_dossier(corrupt_float)
    assert ok is False
    assert err == "ERR_FLOAT_FORBIDDEN_IN_DOSSIER"

    # 8. Unserializable surrogate triggers JCS canonicalization failure
    corrupt_jcs = dict(raw)
    corrupt_jcs["timestamp_utc"] = "\ud800"
    ok, err = verify_regulatory_dossier(corrupt_jcs)
    assert ok is False
    assert err == "ERR_JCS_CANONICALIZATION_FAILED"


def test_failed_audit_when_subsystem_diverges(runner: RegulatoryDossierRunner):
    from src.heterogeneous_consensus_mesh import EvaluatorRole, ModelEvaluationProposal, ProposalVerdict

    # 1 approve, 2 rejects -> consensus agreement is 3333 bps < 6666 bps -> REJECTED_EXCESSIVE_SEMANTIC_JITTER
    divergent_proposals = [
        ModelEvaluationProposal(
            evaluator_id="eval-1",
            role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
            verdict=ProposalVerdict.APPROVE,
            justification="Looks ok.",
            rules_addressed=("R1_SPEC_FLOOR",),
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-2",
            role=EvaluatorRole.SECURITY_AND_MOCK_AUDITOR,
            verdict=ProposalVerdict.REJECT,
            justification="Mock usage found.",
            rules_addressed=("R1_SPEC_FLOOR",),
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-3",
            role=EvaluatorRole.BOUNDARY_AND_INVARIANT_FALSIFIER,
            verdict=ProposalVerdict.REJECT,
            justification="Boundary fail.",
            rules_addressed=("R1_SPEC_FLOOR",),
        ),
    ]

    dossier = runner.run_full_dossier_audit(mode="OFFLINE", proposals_override=divergent_proposals)
    assert dossier.regulatory_status == RegulatoryStatus.FAILED_REGULATORY_AUDIT
    assert dossier.consensus_mesh_caid.startswith("sha256:")

    valid, err = verify_regulatory_dossier(dossier.to_dict())
    assert valid is True
    assert err == "OK"


def test_cli_runner_and_file_export(tmp_path: Path):
    out_file = tmp_path / "REGULATORY_DOSSIER.json"

    # Run CLI with --out and --json
    rc = main(["--mode", "OFFLINE", "--out", str(out_file), "--json"])
    assert rc == 0
    assert out_file.exists()
    raw_text = out_file.read_text(encoding="utf-8")
    assert raw_text.startswith("{\n  \"dossier_id\":")

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["regulatory_status"] == RegulatoryStatus.CERTIFIED_REGULATORY_COMPLIANT

    # Run CLI without --json (human-readable print path)
    rc_text = main(["--mode", "OFFLINE"])
    assert rc_text == 0

    # Verify the exported dossier via CLI --verify
    rc_verify = main(["--verify", str(out_file)])
    assert rc_verify == 0

    # Verify non-existent file
    rc_fail = main(["--verify", str(tmp_path / "non_existent.json")])
    assert rc_fail == 1

    # Verify corrupt dossier fails CLI --verify
    corrupt_file = tmp_path / "corrupt_dossier.json"
    corrupt_data = dict(data)
    corrupt_data["total_stages_commissioned"] = 99
    corrupt_file.write_text(json.dumps(corrupt_data), encoding="utf-8")
    rc_corrupt = main(["--verify", str(corrupt_file)])
    assert rc_corrupt == 1
