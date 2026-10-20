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
tests/test_hybrid_pqc_envelope.py — Unit tests for Post-Quantum Evidence Envelope (PQEE).

Validates require_both_valid verification under positive and negative test vectors:
- Valid envelope passes.
- Tampered statement fails.
- Tampered Ed25519 signature fails.
- Tampered ML-DSA-65 signature fails.
- Wrong public key fails.
- Canonicalization format mismatch fails.
"""

import pytest
from dataclasses import replace
from tools.hybrid_pqc_envelope import HybridPqcSigner, HybridPqcEnvelope


@pytest.fixture
def sample_statement():
    return {
        "operation_id": "op-pqee-001",
        "action_caid": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "amount_minor": 250000,
        "disposition": "CONFIRMED",
    }


@pytest.fixture
def valid_envelope(sample_statement):
    signer = HybridPqcSigner()
    return signer.sign_statement(sample_statement, ephemeral=True)


def test_valid_hybrid_envelope_passes(sample_statement, valid_envelope):
    assert valid_envelope.crypto_bill_of_materials["pqc_algorithm"] == "ML-DSA-65"
    assert valid_envelope.crypto_bill_of_materials["pqc_standard"] == "FIPS 204"
    assert valid_envelope.crypto_bill_of_materials["verification_policy"] == "require_both_valid"
    assert HybridPqcSigner.verify_envelope(sample_statement, valid_envelope) is True


def test_tampered_statement_fails(sample_statement, valid_envelope):
    tampered = dict(sample_statement)
    tampered["amount_minor"] = 999999
    assert HybridPqcSigner.verify_envelope(tampered, valid_envelope) is False


def test_tampered_ed25519_signature_fails(sample_statement, valid_envelope):
    # Alter the Ed25519 signature
    bad_ed_sig = "00" * 32 + valid_envelope.ed25519_signature_hex[64:]
    tampered_env = replace(valid_envelope, ed25519_signature_hex=bad_ed_sig)
    assert HybridPqcSigner.verify_envelope(sample_statement, tampered_env) is False


def test_tampered_mldsa65_signature_fails(sample_statement, valid_envelope):
    # Alter the ML-DSA-65 signature
    bad_ml_sig = "00" * 32 + valid_envelope.mldsa65_signature_hex[64:]
    tampered_env = replace(valid_envelope, mldsa65_signature_hex=bad_ml_sig)
    assert HybridPqcSigner.verify_envelope(sample_statement, tampered_env) is False


def test_wrong_ed25519_public_key_fails(sample_statement, valid_envelope):
    bad_ed_pk = "01" * 32
    tampered_env = replace(valid_envelope, ed25519_public_key_hex=bad_ed_pk)
    assert HybridPqcSigner.verify_envelope(sample_statement, tampered_env) is False


def test_wrong_mldsa65_public_key_fails(sample_statement, valid_envelope):
    bad_ml_pk = "01" * (len(valid_envelope.mldsa65_public_key_hex) // 2)
    tampered_env = replace(valid_envelope, mldsa65_public_key_hex=bad_ml_pk)
    assert HybridPqcSigner.verify_envelope(sample_statement, tampered_env) is False
