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
tests/test_independent_validation_runner.py — Unit tests for IndependentValidationRunner.

Validates that:
- All validation steps execute cleanly and report passed=True.
- Emitted JSON receipt contains all steps, accurate durations, and valid Ed25519 signature envelope.
- Signature verifies over the canonical RFC 8785 receipt body.
"""

import base64
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, List, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from src.jcs_canonicalizer import encode_jcs
from tools.independent_validation_runner import (
    DEFAULT_VALIDATION_STEPS,
    IndependentValidationRunner,
    StepResult,
    main as runner_main,
    run_external_commission_cleanroom_probe,
    verify_validation_receipt,
)


def _assert_zero_floats_in_tree(node: Any) -> None:
    assert not isinstance(node, float), f"Float forbidden in canonical receipt body: {node!r}"
    if isinstance(node, dict):
        for k, v in node.items():
            assert isinstance(k, str)
            _assert_zero_floats_in_tree(v)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _assert_zero_floats_in_tree(item)


def _fast_steps() -> List[Tuple[str, str, List[str]]]:
    return [
        ("STEP_01_ZONE_BOUNDARY", "Zone Boundary Isolation Scanner", [sys.executable, "-c", "print('ok1')"]),
        ("STEP_02_AST_PURITY", "Zero-Mock and AST Purity Enforcer", [sys.executable, "-c", "print('ok2')"]),
    ]


def test_independent_validation_runner_no_floats_and_receipt_signing(tmp_path: Path) -> None:
    assert len(DEFAULT_VALIDATION_STEPS) == 16
    assert DEFAULT_VALIDATION_STEPS[0][0] == "STEP_01_ZONE_BOUNDARY"
    assert DEFAULT_VALIDATION_STEPS[-1][0] == "STEP_15_REPO_INTELLIGENCE_PACKER"

    runner = IndependentValidationRunner(repo_root=tmp_path, steps_override=_fast_steps())
    receipt = runner.execute_all()

    # 1. Zero floats anywhere in receipt_body
    _assert_zero_floats_in_tree(receipt["receipt_body"])
    for step in receipt["receipt_body"]["steps"]:
        assert type(step["duration_ms"]) is int
        assert type(step["passed"]) is bool

    summary = receipt["receipt_body"]["validation_run"]
    assert type(summary["total_duration_ms"]) is int
    assert summary["total_duration_ms"] == sum(s["duration_ms"] for s in receipt["receipt_body"]["steps"])
    assert summary["all_passed"] is True
    assert summary["passed_steps"] == 2
    assert summary["total_steps"] == 2
    assert summary["deterministic_outcomes_caid"].startswith("sha256:")

    # Default run uses an ephemeral key and must explicitly report key_pinned=False
    sig_envelope = receipt["signature_envelope"]
    assert sig_envelope["key_pinned"] is False
    assert sig_envelope["key_provenance"] == "ephemeral_per_run_integrity_only"

    # Unpinned verification fails closed by default
    ok, reason, pinned = verify_validation_receipt(receipt)
    assert ok is False
    assert reason == "ERR_UNPINNED_PUBLIC_KEY_REJECTED"
    assert pinned is False

    # Explicit opt-in for ephemeral key succeeds with key_pinned=False
    ok_eph, reason_eph, pinned_eph = verify_validation_receipt(
        receipt, allow_ephemeral_key=True
    )
    assert ok_eph is True
    assert reason_eph == "VERIFIED_EPHEMERAL_UNPINNED"
    assert pinned_eph is False

    # Pinned verification succeeds when matching key is supplied (case-insensitive hex)
    ok_pin, reason_pin, pinned_pin = verify_validation_receipt(
        receipt, trusted_public_key_hex=sig_envelope["public_key_hex"].upper()
    )
    assert ok_pin is True
    assert reason_pin == "VERIFIED_PINNED"
    assert pinned_pin is True

    other_pub_hex = Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()
    ok_bad, reason_bad, pinned_bad = verify_validation_receipt(
        receipt, trusted_public_key_hex=other_pub_hex
    )
    assert ok_bad is False
    assert reason_bad == "ERR_PUBLIC_KEY_MISMATCH"
    assert pinned_bad is False

    # Verify cryptographic signature of receipt directly
    pub_key_bytes = bytes.fromhex(sig_envelope["public_key_hex"])
    sig_bytes = base64.b64decode(sig_envelope["signature_b64"])
    canonical_body_bytes = encode_jcs(receipt["receipt_body"])

    ed_pub = Ed25519PublicKey.from_public_bytes(pub_key_bytes)
    ed_pub.verify(sig_bytes, canonical_body_bytes)

    # Verify that file was created in output directory
    receipt_file = tmp_path / "output" / "independent_validation_receipt.json"
    assert receipt_file.is_file()
    saved = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert saved["receipt_body"]["validation_run"]["all_passed"] is True
    _assert_zero_floats_in_tree(saved["receipt_body"])


def test_caller_pinned_signing_key_and_failing_step_handling(tmp_path: Path) -> None:
    caller_key = Ed25519PrivateKey.generate()
    steps = [
        ("STEP_PASS", "Pass Step", [sys.executable, "-c", "print('A' * 600)"]),
        ("STEP_FAIL", "Fail Step", [sys.executable, "-c", "import sys; sys.stderr.write('err_msg'); sys.exit(3)"]),
        ("STEP_SILENT_FAIL", "Silent Fail", [sys.executable, "-c", "import sys; sys.exit(7)"]),
    ]
    runner = IndependentValidationRunner(
        repo_root=tmp_path,
        signing_key=caller_key,
        steps_override=steps,
    )
    receipt = runner.execute_all()
    _assert_zero_floats_in_tree(receipt["receipt_body"])

    summary = receipt["receipt_body"]["validation_run"]
    assert summary["all_passed"] is False
    assert summary["total_steps"] == 3
    assert summary["passed_steps"] == 1
    assert runner.results[0].details == "A" * 500
    assert len(runner.results[0].details) == 500
    assert runner.results[1].details == "err_msg"
    assert runner.results[2].details == "exit_code_7"

    env = receipt["signature_envelope"]
    assert env["key_pinned"] is True
    assert env["key_provenance"] == "caller_supplied_signing_key"
    assert env["public_key_hex"] == caller_key.public_key().public_bytes_raw().hex()

    ok, reason, pinned = verify_validation_receipt(
        receipt, trusted_public_key_hex=env["public_key_hex"]
    )
    assert (ok, reason, pinned) == (True, "VERIFIED_PINNED", True)


def test_deterministic_outcomes_caid_invariance_and_tamper_rejection(tmp_path: Path) -> None:
    signing_key = Ed25519PrivateKey.generate()
    pub_hex = signing_key.public_key().public_bytes_raw().hex()

    runner1 = IndependentValidationRunner(
        repo_root=tmp_path, signing_key=signing_key, steps_override=_fast_steps()
    )
    r1 = runner1.execute_all()

    runner2 = IndependentValidationRunner(
        repo_root=tmp_path, signing_key=signing_key, steps_override=_fast_steps()
    )
    r2 = runner2.execute_all()

    # Force distinct timestamps and durations between r1 and r2
    r2["receipt_body"]["validation_run"]["timestamp_utc"] = "2099-12-31T23:59:59Z"
    r2["receipt_body"]["validation_run"]["total_duration_ms"] = 999999
    r2["receipt_body"]["steps"][0]["duration_ms"] = 444444
    r2["receipt_body"]["steps"][1]["duration_ms"] = 555555

    caid1 = r1["receipt_body"]["validation_run"]["deterministic_outcomes_caid"]
    caid2 = r2["receipt_body"]["validation_run"]["deterministic_outcomes_caid"]
    assert caid1.startswith("sha256:")
    assert len(caid1) == len("sha256:") + 64
    assert caid1 == caid2

    # Re-sign r2 with modified timestamps/durations; both must verify and share caid
    c_bytes2 = encode_jcs(r2["receipt_body"])
    r2["signature_envelope"]["canonical_hash_sha256"] = f"sha256:{hashlib.sha256(c_bytes2).hexdigest()}"
    r2["signature_envelope"]["signature_b64"] = base64.b64encode(signing_key.sign(c_bytes2)).decode("ascii")
    assert verify_validation_receipt(r2, trusted_public_key_hex=pub_hex) == (True, "VERIFIED_PINNED", True)

    # Tamper 1: Corrupt deterministic_outcomes_caid directly
    bad_caid_rcpt = copy.deepcopy(r1)
    bad_caid_rcpt["receipt_body"]["validation_run"]["deterministic_outcomes_caid"] = "sha256:" + ("0" * 64)
    assert verify_validation_receipt(bad_caid_rcpt, trusted_public_key_hex=pub_hex) == (
        False,
        "ERR_OUTCOMES_CAID_MISMATCH",
        False,
    )

    # Tamper 2: Flip a step's passed flag without updating deterministic_outcomes_caid
    flipped_step_rcpt = copy.deepcopy(r1)
    flipped_step_rcpt["receipt_body"]["steps"][0]["passed"] = False
    assert verify_validation_receipt(flipped_step_rcpt, trusted_public_key_hex=pub_hex) == (
        False,
        "ERR_OUTCOMES_CAID_MISMATCH",
        False,
    )

    # Tamper 3: Missing deterministic_outcomes_caid when steps are present
    missing_caid_rcpt = copy.deepcopy(r1)
    del missing_caid_rcpt["receipt_body"]["validation_run"]["deterministic_outcomes_caid"]
    assert verify_validation_receipt(missing_caid_rcpt, trusted_public_key_hex=pub_hex) == (
        False,
        "ERR_OUTCOMES_CAID_MISMATCH",
        False,
    )

    # Tamper 4: Malformed step entry inside steps
    malformed_step_rcpt = copy.deepcopy(r1)
    malformed_step_rcpt["receipt_body"]["steps"] = [{"step_id": 123, "passed": "yes"}]
    assert verify_validation_receipt(malformed_step_rcpt, trusted_public_key_hex=pub_hex) == (
        False,
        "ERR_OUTCOMES_CAID_MISMATCH",
        False,
    )


def test_verify_validation_receipt_negative_boundaries(tmp_path: Path) -> None:
    signing_key = Ed25519PrivateKey.generate()
    pub_hex = signing_key.public_key().public_bytes_raw().hex()
    runner = IndependentValidationRunner(
        repo_root=tmp_path, signing_key=signing_key, steps_override=_fast_steps()
    )
    valid_rcpt = runner.execute_all()

    assert verify_validation_receipt("not_a_dict") == (False, "ERR_RECEIPT_NOT_OBJECT", False)  # type: ignore[arg-type]
    assert verify_validation_receipt({"receipt_body": None, "signature_envelope": {}}) == (
        False,
        "ERR_MISSING_BODY_OR_ENVELOPE",
        False,
    )
    assert verify_validation_receipt({"receipt_body": {}, "signature_envelope": None}) == (
        False,
        "ERR_MISSING_BODY_OR_ENVELOPE",
        False,
    )
    assert verify_validation_receipt(
        {"receipt_body": {}, "signature_envelope": {"public_key_hex": 123, "signature_b64": "abc"}}
    ) == (False, "ERR_INVALID_ENVELOPE_FIELDS", False)

    # Canonical hash mismatch (modify engine string in body without updating canonical_hash_sha256)
    bad_hash_rcpt = copy.deepcopy(valid_rcpt)
    bad_hash_rcpt["receipt_body"]["validation_run"]["engine"] = "TAMPERED_ENGINE"
    assert verify_validation_receipt(bad_hash_rcpt, trusted_public_key_hex=pub_hex) == (
        False,
        "ERR_CANONICAL_HASH_MISMATCH",
        False,
    )

    # Invalid signature (recompute canonical hash on tampered body, keep old signature)
    bad_sig_rcpt = copy.deepcopy(valid_rcpt)
    bad_sig_rcpt["receipt_body"]["validation_run"]["engine"] = "TAMPERED_ENGINE"
    new_bytes = encode_jcs(bad_sig_rcpt["receipt_body"])
    bad_sig_rcpt["signature_envelope"]["canonical_hash_sha256"] = (
        f"sha256:{hashlib.sha256(new_bytes).hexdigest()}"
    )
    assert verify_validation_receipt(bad_sig_rcpt, trusted_public_key_hex=pub_hex) == (
        False,
        "ERR_SIGNATURE_INVALID",
        False,
    )


def test_external_commission_cleanroom_probe() -> None:
    res = run_external_commission_cleanroom_probe()
    _assert_zero_floats_in_tree(res)
    assert res["all_probes_held"] is True
    assert res["nominal_pinned_verified"] is True
    assert res["control_unpinned_rejected"] is True
    assert res["control_tampered_payload_rejected"] is True
    assert res["control_wrong_pubkey_rejected"] is True
    assert res["bundle_reproducible_and_tamper_evident"] is True
    expected_bundle, expected_caid = (
        IndependentValidationRunner.__module__
        and __import__("src.parallel_tracks_abcde_engine", fromlist=["ReproducibleEvidenceBundleBuilder"])
        .ReproducibleEvidenceBundleBuilder.build_deterministic_bundle_bytes(
            {
                "manifest.json": {"schema_version": 1, "step_count": 2},
                "outcomes.json": {"all_passed": True, "verified_steps": 2},
            }
        )
    )
    assert res["bundle_caid"] == expected_caid
    assert len(expected_bundle) > 0


def test_main_entry_output_and_exit_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runner_main(repo_root=tmp_path, steps_override=_fast_steps())
    out = capsys.readouterr().out
    assert ("=" * 80) in out
    assert ("-" * 80) in out
    assert "ALL_PASSED (2/2 steps passed" in out

    with pytest.raises(SystemExit) as exc:
        runner_main(
            repo_root=tmp_path,
            steps_override=[("STEP_BAD", "Bad", [sys.executable, "-c", "import sys; sys.exit(1)"])],
        )
    assert exc.value.code == 1
    out_fail = capsys.readouterr().out
    assert "[FAILED]" in out_fail
    assert "FAILURES_DETECTED (0/1 steps passed" in out_fail
