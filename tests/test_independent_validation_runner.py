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
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from src.jcs_canonicalizer import encode_jcs
from tools.independent_validation_runner import IndependentValidationRunner


def test_independent_validation_runner_executes_cleanly():
    runner = IndependentValidationRunner()
    receipt = runner.execute_all()

    summary = receipt["receipt_body"]["validation_run"]
    assert summary["all_passed"] is True
    assert summary["passed_steps"] == summary["total_steps"]
    assert summary["total_steps"] >= 8

    # Verify cryptographic signature of receipt
    sig_envelope = receipt["signature_envelope"]
    pub_key_bytes = bytes.fromhex(sig_envelope["public_key_hex"])
    sig_bytes = base64.b64decode(sig_envelope["signature_b64"])
    canonical_body_bytes = encode_jcs(receipt["receipt_body"])

    ed_pub = Ed25519PublicKey.from_public_bytes(pub_key_bytes)
    # Must verify strictly without exception
    ed_pub.verify(sig_bytes, canonical_body_bytes)

    # Verify that file was created in output directory
    receipt_file = Path("output/independent_validation_receipt.json")
    assert receipt_file.is_file()
    saved = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert saved["receipt_body"]["validation_run"]["all_passed"] is True
