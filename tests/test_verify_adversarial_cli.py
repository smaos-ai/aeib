#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
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
tests/test_verify_adversarial_cli.py
================================================================================
Unit and Falsification Test Suite for verify_adversarial_evidence.py CLI.
Evaluated under the stated model. Preserves strict epistemic lock.

Tests:
  1. CLI --check-jcs-conformance passes 25 RFC 8785 test vectors.
  2. CLI --all passes across existing artifacts/adversarial/*.json bundles.
  3. CLI --bundle passes for individual AT48, AT49, AT50, and AT51 files.
  4. Falsification matrix:
     - Bit-flipped signature fails verification.
     - Mutated evidence_digest fails verification.
     - Tampered disclaimer fails verification.
     - Tampered verdict/transport fails invariant check (AT48, AT49, AT50, AT51).
     - Missing plane fails schema verification.
     - Free-text enum fails schema verification.
     - Mismatched public key override fails verification.
"""

import base64
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs
from tools.verify_adversarial_evidence import (
    MANDATORY_DISCLAIMER,
    VerificationStatus,
    verify_adversarial_bundle,
)

CLI_SCRIPT = REPO_ROOT / "tools" / "verify_adversarial_evidence.py"
ADVERSARIAL_DIR = REPO_ROOT / "artifacts" / "adversarial"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Helper to execute the verifier CLI in a subprocess."""
    cmd = [sys.executable, str(CLI_SCRIPT), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _re_sign_bundle(
    bundle_data: Dict[str, Any],
    signing_key: ed25519.Ed25519PrivateKey,
) -> Dict[str, Any]:
    """Canonicalizes incident_evidence, recomputes SHA-256 digest, and re-signs with Ed25519."""
    updated = copy.deepcopy(bundle_data)
    ie = updated["incident_evidence"]
    canonical_bytes = encode_jcs(ie)
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    signature_bytes = signing_key.sign(canonical_bytes)

    pub_pem = signing_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    updated["evidence_digest"] = digest
    updated["boundary_signature_b64"] = base64.b64encode(signature_bytes).decode("ascii")
    updated["boundary_public_key_pem"] = pub_pem
    return updated


# ------------------------------------------------------------------------------
# 1. JCS Conformance Check
# ------------------------------------------------------------------------------
def test_cli_check_jcs_conformance():
    """Verify that --check-jcs-conformance executes and passes RFC 8785 vectors."""
    res = _run_cli("--check-jcs-conformance")
    assert res.returncode == VerificationStatus.SUCCESS.value
    assert "25 RFC 8785 canonicalization vectors verified" in res.stdout


# ------------------------------------------------------------------------------
# 2. All Adversarial Bundles Verification
# ------------------------------------------------------------------------------
def test_cli_verify_all_adversarial_bundles():
    """Verify that --all passes on all existing bundles in artifacts/adversarial/."""
    res = _run_cli("--all")
    assert res.returncode == VerificationStatus.SUCCESS.value
    assert "All 4 adversarial evidence bundles in" in res.stdout
    assert "VERIFICATION RESULT: VALID (AT48_indirect_prompt_injection_evidence.json)" in res.stdout
    assert "VERIFICATION RESULT: VALID (AT49_ai_result_poisoning_evidence.json)" in res.stdout
    assert "VERIFICATION RESULT: VALID (AT50_ai_enabled_exfiltration_evidence.json)" in res.stdout
    assert "VERIFICATION RESULT: VALID (AT51_impair_autonomous_defenses_evidence.json)" in res.stdout


# ------------------------------------------------------------------------------
# 3. Individual Bundle Verification
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bundle_filename,expected_scenario",
    [
        ("AT48_indirect_prompt_injection_evidence.json", "T1659"),
        ("AT49_ai_result_poisoning_evidence.json", "T1565"),
        ("AT50_ai_enabled_exfiltration_evidence.json", "T1048"),
        ("AT51_impair_autonomous_defenses_evidence.json", "T1562"),
    ],
)
def test_cli_verify_individual_bundles(bundle_filename: str, expected_scenario: str):
    """Verify that --bundle passes on individual AT48, AT49, AT50, and AT51 bundles."""
    target_path = ADVERSARIAL_DIR / bundle_filename
    assert target_path.exists(), f"Missing required bundle file: {target_path}"

    res = _run_cli("--bundle", str(target_path))
    assert res.returncode == VerificationStatus.SUCCESS.value
    assert f"VERIFICATION RESULT: VALID ({bundle_filename})" in res.stdout
    assert expected_scenario in res.stdout


# ------------------------------------------------------------------------------
# 4. Falsification Matrix: Bit-Flipped Signature
# ------------------------------------------------------------------------------
def test_falsification_bit_flipped_signature(tmp_path: Path):
    """Verify that a bit-flipped signature causes verification failure."""
    orig_path = ADVERSARIAL_DIR / "AT48_indirect_prompt_injection_evidence.json"
    data = json.loads(orig_path.read_text(encoding="utf-8"))

    # Decode signature and flip bits
    raw_sig = bytearray(base64.b64decode(data["boundary_signature_b64"]))
    raw_sig[5] ^= 0xFF
    data["boundary_signature_b64"] = base64.b64encode(raw_sig).decode("ascii")

    corrupted_bundle = tmp_path / "corrupted_sig.json"
    corrupted_bundle.write_text(json.dumps(data), encoding="utf-8")

    res = _run_cli("--bundle", str(corrupted_bundle))
    assert res.returncode == VerificationStatus.INVALID_SIGNATURE.value
    assert "Signature verification failed" in res.stderr or "Signature verification failed" in res.stdout


# ------------------------------------------------------------------------------
# 5. Falsification Matrix: Mutated Digest
# ------------------------------------------------------------------------------
def test_falsification_mutated_evidence_digest(tmp_path: Path):
    """Verify that an altered evidence digest causes verification failure."""
    orig_path = ADVERSARIAL_DIR / "AT49_ai_result_poisoning_evidence.json"
    data = json.loads(orig_path.read_text(encoding="utf-8"))

    # Tamper with the evidence digest
    data["evidence_digest"] = "e" * 64

    corrupted_bundle = tmp_path / "corrupted_digest.json"
    corrupted_bundle.write_text(json.dumps(data), encoding="utf-8")

    res = _run_cli("--bundle", str(corrupted_bundle))
    assert res.returncode == VerificationStatus.DIGEST_MISMATCH.value
    assert "digest mismatch" in res.stderr.lower() or "digest mismatch" in res.stdout.lower()


# ------------------------------------------------------------------------------
# 6. Falsification Matrix: Tampered Disclaimer
# ------------------------------------------------------------------------------
def test_falsification_tampered_disclaimer(tmp_path: Path):
    """Verify that altering the legal disclaimer causes verification failure."""
    orig_path = ADVERSARIAL_DIR / "AT50_ai_enabled_exfiltration_evidence.json"
    data = json.loads(orig_path.read_text(encoding="utf-8"))

    data["incident_evidence"]["disclaimer"] = "AEIB handles all regulatory determinations."

    corrupted_bundle = tmp_path / "corrupted_disclaimer.json"
    corrupted_bundle.write_text(json.dumps(data), encoding="utf-8")

    res = _run_cli("--bundle", str(corrupted_bundle))
    assert res.returncode == VerificationStatus.SCHEMA_ERROR.value
    assert "disclaimer" in res.stderr.lower() or "disclaimer" in res.stdout.lower()


# ------------------------------------------------------------------------------
# 7. Falsification Matrix: Tampered Verdict / Transport Invariants
# ------------------------------------------------------------------------------
def test_falsification_at48_tampered_verdict(tmp_path: Path):
    """Verify that AT48 fails when boundary_verdict is tampered to ALLOWED."""
    orig_path = ADVERSARIAL_DIR / "AT48_indirect_prompt_injection_evidence.json"
    data = json.loads(orig_path.read_text(encoding="utf-8"))
    signing_key = ed25519.Ed25519PrivateKey.generate()

    data["incident_evidence"]["execution_authority"]["boundary_verdict"] = "ALLOWED"
    signed_data = _re_sign_bundle(data, signing_key)

    bundle_path = tmp_path / "at48_tampered_verdict.json"
    bundle_path.write_text(json.dumps(signed_data), encoding="utf-8")

    res = _run_cli("--bundle", str(bundle_path))
    assert res.returncode == VerificationStatus.INVARIANT_VIOLATION.value
    assert "AT48 invariant violation" in res.stderr or "AT48 invariant violation" in res.stdout


def test_falsification_at48_tampered_transport(tmp_path: Path):
    """Verify that AT48 fails when connections_accepted > 0."""
    orig_path = ADVERSARIAL_DIR / "AT48_indirect_prompt_injection_evidence.json"
    data = json.loads(orig_path.read_text(encoding="utf-8"))
    signing_key = ed25519.Ed25519PrivateKey.generate()

    data["incident_evidence"]["observed_consequence"]["transport_observation"]["connections_accepted"] = 1
    signed_data = _re_sign_bundle(data, signing_key)

    bundle_path = tmp_path / "at48_tampered_conns.json"
    bundle_path.write_text(json.dumps(signed_data), encoding="utf-8")

    res = _run_cli("--bundle", str(bundle_path))
    assert res.returncode == VerificationStatus.INVARIANT_VIOLATION.value
    assert "AT48 invariant violation" in res.stderr or "AT48 invariant violation" in res.stdout


def test_falsification_at49_tampered_disposition(tmp_path: Path):
    """Verify that AT49 fails when final_disposition is not EFFECT_INDETERMINATE."""
    orig_path = ADVERSARIAL_DIR / "AT49_ai_result_poisoning_evidence.json"
    data = json.loads(orig_path.read_text(encoding="utf-8"))
    signing_key = ed25519.Ed25519PrivateKey.generate()

    data["incident_evidence"]["observed_consequence"]["final_disposition"] = "SETTLED"
    signed_data = _re_sign_bundle(data, signing_key)

    bundle_path = tmp_path / "at49_tampered_disp.json"
    bundle_path.write_text(json.dumps(signed_data), encoding="utf-8")

    res = _run_cli("--bundle", str(bundle_path))
    assert res.returncode == VerificationStatus.INVARIANT_VIOLATION.value
    assert "AT49 invariant violation" in res.stderr or "AT49 invariant violation" in res.stdout


def test_falsification_at49_tampered_rejection_code(tmp_path: Path):
    """Verify that AT49 fails when rejection_code is not TARGET_EVIDENCE_CONTRACT_MISMATCH."""
    orig_path = ADVERSARIAL_DIR / "AT49_ai_result_poisoning_evidence.json"
    data = json.loads(orig_path.read_text(encoding="utf-8"))
    signing_key = ed25519.Ed25519PrivateKey.generate()

    data["incident_evidence"]["execution_authority"]["rejection_code"] = "DIFFERENT_CODE"
    signed_data = _re_sign_bundle(data, signing_key)

    bundle_path = tmp_path / "at49_tampered_code.json"
    bundle_path.write_text(json.dumps(signed_data), encoding="utf-8")

    res = _run_cli("--bundle", str(bundle_path))
    assert res.returncode == VerificationStatus.INVARIANT_VIOLATION.value
    assert "AT49 invariant violation" in res.stderr or "AT49 invariant violation" in res.stdout


def test_falsification_at50_tampered_rejection_code(tmp_path: Path):
    """Verify that AT50 fails when rejection_code is not EXFILTRATION_PATTERN_OR_RECIPIENT_MUTATED."""
    orig_path = ADVERSARIAL_DIR / "AT50_ai_enabled_exfiltration_evidence.json"
    data = json.loads(orig_path.read_text(encoding="utf-8"))
    signing_key = ed25519.Ed25519PrivateKey.generate()

    data["incident_evidence"]["execution_authority"]["rejection_code"] = "OTHER_CODE"
    signed_data = _re_sign_bundle(data, signing_key)

    bundle_path = tmp_path / "at50_tampered_code.json"
    bundle_path.write_text(json.dumps(signed_data), encoding="utf-8")

    res = _run_cli("--bundle", str(bundle_path))
    assert res.returncode == VerificationStatus.INVARIANT_VIOLATION.value
    assert "AT50 invariant violation" in res.stderr or "AT50 invariant violation" in res.stdout


def test_falsification_at51_tampered_control_plane_write(tmp_path: Path):
    """Verify that AT51 fails when control plane write permission is True."""
    orig_path = ADVERSARIAL_DIR / "AT51_impair_autonomous_defenses_evidence.json"
    data = json.loads(orig_path.read_text(encoding="utf-8"))
    signing_key = ed25519.Ed25519PrivateKey.generate()

    data["incident_evidence"]["observed_consequence"]["transport_observation"]["agent_write_permitted"] = True
    signed_data = _re_sign_bundle(data, signing_key)

    bundle_path = tmp_path / "at51_tampered_write.json"
    bundle_path.write_text(json.dumps(signed_data), encoding="utf-8")

    res = _run_cli("--bundle", str(bundle_path))
    assert res.returncode == VerificationStatus.INVARIANT_VIOLATION.value
    assert "AT51 invariant violation" in res.stderr or "AT51 invariant violation" in res.stdout


# ------------------------------------------------------------------------------
# 8. Schema & Separation Integrity Tests
# ------------------------------------------------------------------------------
def test_falsification_missing_plane(tmp_path: Path):
    """Verify that deleting an evidence plane fails schema validation."""
    orig_path = ADVERSARIAL_DIR / "AT48_indirect_prompt_injection_evidence.json"
    data = json.loads(orig_path.read_text(encoding="utf-8"))
    del data["incident_evidence"]["observed_consequence"]

    corrupted_bundle = tmp_path / "missing_plane.json"
    corrupted_bundle.write_text(json.dumps(data), encoding="utf-8")

    res = _run_cli("--bundle", str(corrupted_bundle))
    assert res.returncode == VerificationStatus.SCHEMA_ERROR.value
    assert "evidence plane" in res.stderr.lower() or "evidence plane" in res.stdout.lower()


def test_falsification_invalid_revocation_state_enum(tmp_path: Path):
    """Verify that an invalid authority_revocation_state fails schema validation."""
    orig_path = ADVERSARIAL_DIR / "AT48_indirect_prompt_injection_evidence.json"
    data = json.loads(orig_path.read_text(encoding="utf-8"))
    data["incident_evidence"]["execution_authority"]["authority_revocation_state"] = "PENDING_AUDIT"

    corrupted_bundle = tmp_path / "invalid_enum.json"
    corrupted_bundle.write_text(json.dumps(data), encoding="utf-8")

    res = _run_cli("--bundle", str(corrupted_bundle))
    assert res.returncode == VerificationStatus.SCHEMA_ERROR.value
    assert "authority_revocation_state" in res.stderr.lower() or "authority_revocation_state" in res.stdout.lower()


def test_falsification_public_key_override(tmp_path: Path):
    """Verify that overriding with an untrusted public key causes signature failure."""
    orig_path = ADVERSARIAL_DIR / "AT48_indirect_prompt_injection_evidence.json"
    other_key = ed25519.Ed25519PrivateKey.generate()
    other_pub_pem = other_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pem_file = tmp_path / "untrusted_pub.pem"
    pem_file.write_bytes(other_pub_pem)

    res = _run_cli("--bundle", str(orig_path), "--public-key", str(pem_file))
    assert res.returncode == VerificationStatus.INVALID_SIGNATURE.value


def test_cli_no_args_prints_help():
    """Verify that calling without arguments returns schema error and prints usage."""
    res = _run_cli()
    assert res.returncode == VerificationStatus.SCHEMA_ERROR.value
    assert "usage:" in res.stderr.lower() or "usage:" in res.stdout.lower()
