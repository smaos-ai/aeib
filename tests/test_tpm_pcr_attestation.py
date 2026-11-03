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

import base64
import hashlib
import os
import subprocess
import sys
import pytest

from src.capability_status import SIMULATED_OPT_IN
from src.tpm_pcr_attestation import (
    TpmPcrAttestationEngine,
    TpmQuoteRecord,
    run_self_test,
    sha256_prefixed,
)


def test_sha256_prefixed():
    data = b"test_payload_123"
    expected = f"sha256:{hashlib.sha256(data).hexdigest()}"
    actual = sha256_prefixed(data)
    assert actual == expected
    assert actual.startswith("sha256:")


def test_tpm_quote_record_defaults_and_canonical_dict():
    record = TpmQuoteRecord(
        pcr_indices=[11],
        pcr_values={11: "0" * 64},
        composite_hash="c" * 64,
        qualifying_data_nonce="n" * 64,
        clock_info={"clock_ms": 1000, "reset_count": 1, "restart_count": 0, "safe": True},
        signature_b64="c2ln",
        ak_pubkey_b64="cHVi",
    )
    assert record.is_hardware_tpm is False
    cd = record.to_canonical_dict()
    assert cd["is_hardware_tpm"] is False
    assert cd["pcr_indices"] == [11]
    assert cd["pcr_values"] == {"11": "0" * 64}
    assert cd["composite_hash"] == "c" * 64
    assert cd["qualifying_data_nonce"] == "n" * 64
    assert cd["ak_pubkey_b64"] == "cHVi"


def test_tpm_pcr_initialization_and_extend():
    engine = TpmPcrAttestationEngine()
    assert engine.is_hardware_tpm is False
    assert engine.operational_status == SIMULATED_OPT_IN
    assert len(engine._pcrs) == 24

    for i in range(24):
        assert engine.get_pcr_hex(i) == "0" * 64

    with pytest.raises(IndexError):
        engine.get_pcr_hex(24)
    with pytest.raises(IndexError):
        engine.get_pcr_hex(-1)
    with pytest.raises(IndexError):
        engine.extend_pcr(24, b"overflow")
    with pytest.raises(IndexError):
        engine.extend_pcr(-1, b"underflow")

    # Extend with 32 bytes (exact digest)
    data32 = hashlib.sha256(b"sample_event_digest").digest()
    new_pcr = engine.extend_pcr(11, data32, event_label="SAMPLE_EVENT_32")
    assert new_pcr != "0" * 64

    expected_hasher = hashlib.sha256()
    expected_hasher.update(b"\x00" * 32)
    expected_hasher.update(data32)
    assert new_pcr == expected_hasher.hexdigest()

    # Extend with non-32 bytes
    data_short = b"short_data"
    old_pcr_bytes = bytes.fromhex(new_pcr)
    new_pcr_2 = engine.extend_pcr(11, data_short, event_label="SAMPLE_EVENT_SHORT")
    assert new_pcr_2 != new_pcr

    expected_hasher2 = hashlib.sha256()
    expected_hasher2.update(old_pcr_bytes)
    expected_hasher2.update(hashlib.sha256(data_short).digest())
    assert new_pcr_2 == expected_hasher2.hexdigest()

    assert len(engine._extend_log) == 2
    entry0 = engine._extend_log[0]
    assert entry0["pcr_index"] == 11
    assert entry0["old_pcr"] == "0" * 64
    assert entry0["new_pcr"] == new_pcr
    assert entry0["event_label"] == "SAMPLE_EVENT_32"
    t_now_extend = int(sys.modules["time"].time() * 1000)
    assert abs(entry0["timestamp_ms"] - t_now_extend) < 5000


def test_tpm_quote_generation_defaults_and_clock():
    engine = TpmPcrAttestationEngine()
    quote = engine.generate_quote()  # defaults: indices=None, nonce=None
    assert quote.pcr_indices == [11]
    assert len(quote.qualifying_data_nonce) == 64
    assert quote.clock_info["safe"] is True
    assert quote.clock_info["reset_count"] == 1
    assert quote.clock_info["restart_count"] == 0
    t_now_clock = int(sys.modules["time"].time() * 1000)
    assert abs(quote.clock_info["clock_ms"] - t_now_clock) < 5000
    assert quote.is_hardware_tpm is False


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

    # Verification with explicit key
    assert TpmPcrAttestationEngine.verify_quote(
        quote=quote,
        expected_pcrs={11: pcr11},
        expected_nonce_hex=nonce.hex(),
        ak_pubkey=engine.ak_pubkey,
    ) is True

    # Verification with implicit key (extracted from quote)
    assert TpmPcrAttestationEngine.verify_quote(
        quote=quote,
        expected_pcrs={11: pcr11},
        expected_nonce_hex=nonce.hex(),
        ak_pubkey=None,
    ) is True


def test_tpm_quote_falsification_tampered_nonce_and_pcr():
    engine = TpmPcrAttestationEngine()
    engine.extend_pcr(11, b"policy_payload")
    pcr11 = engine.get_pcr_hex(11)

    nonce = os.urandom(32)
    quote = engine.generate_quote(pcr_indices=[11], nonce=nonce)

    # 1. Tampered nonce rejected
    bad_nonce = os.urandom(32).hex()
    assert TpmPcrAttestationEngine.verify_quote(
        quote,
        expected_pcrs={11: pcr11},
        expected_nonce_hex=bad_nonce,
        ak_pubkey=engine.ak_pubkey,
    ) is False

    # 2. Tampered PCR register value rejected
    assert TpmPcrAttestationEngine.verify_quote(
        quote,
        expected_pcrs={11: "0" * 64},
        expected_nonce_hex=nonce.hex(),
        ak_pubkey=engine.ak_pubkey,
    ) is False

    # 3. Missing PCR index rejected
    assert TpmPcrAttestationEngine.verify_quote(
        quote,
        expected_pcrs={12: "0" * 64},
        expected_nonce_hex=nonce.hex(),
        ak_pubkey=engine.ak_pubkey,
    ) is False

    # 4. Tampered composite hash rejected
    corrupted_quote = TpmQuoteRecord(
        pcr_indices=quote.pcr_indices,
        pcr_values=quote.pcr_values,
        composite_hash="0" * 64,
        qualifying_data_nonce=quote.qualifying_data_nonce,
        clock_info=quote.clock_info,
        signature_b64=quote.signature_b64,
        ak_pubkey_b64=quote.ak_pubkey_b64,
        is_hardware_tpm=quote.is_hardware_tpm,
    )
    assert TpmPcrAttestationEngine.verify_quote(
        corrupted_quote,
        expected_pcrs={11: pcr11},
        expected_nonce_hex=nonce.hex(),
        ak_pubkey=engine.ak_pubkey,
    ) is False

    # 5. Invalid signature rejected
    bad_sig_quote = TpmQuoteRecord(
        pcr_indices=quote.pcr_indices,
        pcr_values=quote.pcr_values,
        composite_hash=quote.composite_hash,
        qualifying_data_nonce=quote.qualifying_data_nonce,
        clock_info=quote.clock_info,
        signature_b64=base64.b64encode(b"invalid_signature_32_bytes_pad!").decode("ascii"),
        ak_pubkey_b64=quote.ak_pubkey_b64,
        is_hardware_tpm=quote.is_hardware_tpm,
    )
    assert TpmPcrAttestationEngine.verify_quote(
        bad_sig_quote,
        expected_pcrs={11: pcr11},
        expected_nonce_hex=nonce.hex(),
        ak_pubkey=engine.ak_pubkey,
    ) is False


def test_tpm_pcr_attestation_self_test_in_process_and_cli():
    # Direct in-process execution to test under AST mutation
    run_self_test()

    # CLI test
    proc = subprocess.run(
        [sys.executable, "src/tpm_pcr_attestation.py", "--self-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Self-test passed" in proc.stdout
