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
tests/test_tpm_pcr_attestation.py
================================================================================
Verification suite for TPM 2.0 PCR Attestation Engine.
Evaluated under the stated model as an agent execution boundary scaffold.
"""

import hashlib
import os
import subprocess
import sys
import pytest

from src.tpm_pcr_attestation import TpmPcrAttestationEngine, TpmQuoteRecord


def test_tpm_pcr_initialization_and_extend():
    engine = TpmPcrAttestationEngine()
    assert engine.get_pcr_hex(11) == "0" * 64

    # Extend with 32 bytes
    data = hashlib.sha256(b"sample_event_digest").digest()
    new_pcr = engine.extend_pcr(11, data, event_label="SAMPLE_EVENT")
    assert new_pcr != "0" * 64

    # Verify deterministic SHA-256 calculation
    expected_hasher = hashlib.sha256()
    expected_hasher.update(b"\x00" * 32)
    expected_hasher.update(data)
    assert new_pcr == expected_hasher.hexdigest()


def test_tpm_quote_generation_and_positive_verification():
    engine = TpmPcrAttestationEngine()
    engine.bind_ebpf_policy_and_scitt_root(
        ebpf_map_digest_hex="0123456789abcdef" * 4,
        scitt_merkle_root_hex="fedcba9876543210" * 4,
    )
    pcr11 = engine.get_pcr_hex(11)

    nonce = os.urandom(32)
    quote = engine.generate_quote(pcr_indices=[11], nonce=nonce)

    assert quote.pcr_values[11] == pcr11
    assert quote.qualifying_data_nonce == nonce.hex()

    is_valid = TpmPcrAttestationEngine.verify_quote(
        quote=quote,
        expected_pcrs={11: pcr11},
        expected_nonce_hex=nonce.hex(),
        ak_pubkey=engine.ak_pubkey,
    )
    assert is_valid is True


def test_tpm_quote_falsification_tampered_nonce_and_pcr():
    engine = TpmPcrAttestationEngine()
    engine.extend_pcr(11, b"policy_payload")
    pcr11 = engine.get_pcr_hex(11)

    nonce = os.urandom(32)
    quote = engine.generate_quote(pcr_indices=[11], nonce=nonce)

    # 1. Tampered nonce rejected
    bad_nonce = os.urandom(32).hex()
    assert not TpmPcrAttestationEngine.verify_quote(
        quote,
        expected_pcrs={11: pcr11},
        expected_nonce_hex=bad_nonce,
        ak_pubkey=engine.ak_pubkey,
    )

    # 2. Tampered PCR register value rejected
    assert not TpmPcrAttestationEngine.verify_quote(
        quote,
        expected_pcrs={11: "0" * 64},
        expected_nonce_hex=nonce.hex(),
        ak_pubkey=engine.ak_pubkey,
    )


def test_tpm_pcr_attestation_cli_self_test():
    proc = subprocess.run(
        [sys.executable, "src/tpm_pcr_attestation.py", "--self-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Self-test passed" in proc.stdout
