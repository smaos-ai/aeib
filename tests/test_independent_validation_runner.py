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
import json
import pytest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from src.jcs_canonicalizer import encode_jcs
from tools.independent_validation_runner import (
    IndependentValidationRunner,
    verify_validation_receipt,
)


def test_independent_validation_runner_executes_cleanly():
    runner = IndependentValidationRunner()
    receipt = runner.execute_all()

    summary = receipt["receipt_body"]["validation_run"]
    assert summary["all_passed"] is True
    assert summary["passed_steps"] == summary["total_steps"]
    assert summary["total_steps"] >= 8

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

    # Pinned verification succeeds when matching key is supplied, fails on wrong key
    ok_pin, reason_pin, pinned_pin = verify_validation_receipt(
        receipt, trusted_public_key_hex=sig_envelope["public_key_hex"]
    )
    assert ok_pin is True
    assert reason_pin == "VERIFIED_PINNED"
    assert pinned_pin is True

    other_pub_hex = Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()
    ok_bad, reason_bad, _ = verify_validation_receipt(
        receipt, trusted_public_key_hex=other_pub_hex
    )
    assert ok_bad is False
    assert reason_bad == "ERR_PUBLIC_KEY_MISMATCH"

    # Verify cryptographic signature of receipt directly
    pub_key_bytes = bytes.fromhex(sig_envelope["public_key_hex"])
    sig_bytes = base64.b64decode(sig_envelope["signature_b64"])
    canonical_body_bytes = encode_jcs(receipt["receipt_body"])

    ed_pub = Ed25519PublicKey.from_public_bytes(pub_key_bytes)
    ed_pub.verify(sig_bytes, canonical_body_bytes)

    # Verify that file was created in output directory
    receipt_file = Path("output/independent_validation_receipt.json")
    assert receipt_file.is_file()
    saved = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert saved["receipt_body"]["validation_run"]["all_passed"] is True
