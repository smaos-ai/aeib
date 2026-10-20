#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# tests/test_verify_tpm_quote.py
#
# Epistemic notice: Evaluated and tested under the stated local verification model.

import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tpm_pcr_attestation import TpmPcrAttestationEngine
from tools.verify_tpm_quote import StandaloneTpmQuoteVerifier, TpmQuoteVerificationError


@pytest.fixture
def quote_engine_and_sample():
    engine = TpmPcrAttestationEngine()
    ebpf_map = hashlib.sha256(b"ebpf_policy_map_test").hexdigest()
    scitt_root = hashlib.sha256(b"scitt_root_test_100").hexdigest()
    pcr11 = engine.bind_ebpf_policy_and_scitt_root(ebpf_map, scitt_root)
    nonce = os.urandom(32)
    record = engine.generate_quote(pcr_indices=[11], nonce=nonce)
    quote_dict = record.to_canonical_dict()
    quote_dict["signature_b64"] = record.signature_b64
    return engine, quote_dict, pcr11, nonce.hex()


def test_tpm_quote_positive_verification(quote_engine_and_sample):
    engine, quote_dict, pcr11, nonce_hex = quote_engine_and_sample
    verifier = StandaloneTpmQuoteVerifier()

    receipt = verifier.verify_quote_dict(
        quote_dict,
        expected_nonce_hex=nonce_hex,
        expected_pcrs={11: pcr11},
    )

    assert receipt["verdict"] == "VERIFIED"
    assert receipt["signature_verified"] is True
    assert receipt["pcr_11_value"] == pcr11
    assert receipt["is_hardware_tpm"] is False
    assert receipt["operational_mode"] == "SOFTWARE_MODEL_SCAFFOLD"


def test_tpm_quote_with_trusted_ak_pubkey(quote_engine_and_sample):
    engine, quote_dict, pcr11, nonce_hex = quote_engine_and_sample
    trusted_ak = engine.ak_pubkey_b64
    verifier = StandaloneTpmQuoteVerifier(trusted_ak_pubkey_b64=trusted_ak)

    receipt = verifier.verify_quote_dict(
        quote_dict,
        expected_nonce_hex=nonce_hex,
        expected_pcrs={11: pcr11},
    )
    assert receipt["verdict"] == "VERIFIED"


def test_tpm_quote_rejects_untrusted_ak(quote_engine_and_sample):
    engine, quote_dict, pcr11, nonce_hex = quote_engine_and_sample
    other_engine = TpmPcrAttestationEngine()
    untrusted_ak = other_engine.ak_pubkey_b64
    verifier = StandaloneTpmQuoteVerifier(trusted_ak_pubkey_b64=untrusted_ak)

    with pytest.raises(TpmQuoteVerificationError, match="HALT_TPM_AK_PUBKEY_UNTRUSTED"):
        verifier.verify_quote_dict(quote_dict, expected_nonce_hex=nonce_hex)


def test_tpm_quote_rejects_nonce_mismatch(quote_engine_and_sample):
    engine, quote_dict, pcr11, nonce_hex = quote_engine_and_sample
    verifier = StandaloneTpmQuoteVerifier()
    wrong_nonce = os.urandom(32).hex()

    with pytest.raises(TpmQuoteVerificationError, match="HALT_TPM_NONCE_MISMATCH"):
        verifier.verify_quote_dict(quote_dict, expected_nonce_hex=wrong_nonce)


def test_tpm_quote_rejects_pcr_mismatch(quote_engine_and_sample):
    engine, quote_dict, pcr11, nonce_hex = quote_engine_and_sample
    verifier = StandaloneTpmQuoteVerifier()
    wrong_pcr = ("e" * 64)

    with pytest.raises(TpmQuoteVerificationError, match="HALT_TPM_PCR_MISMATCH"):
        verifier.verify_quote_dict(quote_dict, expected_nonce_hex=nonce_hex, expected_pcrs={11: wrong_pcr})


def test_tpm_quote_rejects_tampered_composite_hash(quote_engine_and_sample):
    engine, quote_dict, pcr11, nonce_hex = quote_engine_and_sample
    verifier = StandaloneTpmQuoteVerifier()
    tampered_quote = dict(quote_dict)
    tampered_quote["composite_hash"] = ("0" * 64)

    with pytest.raises(TpmQuoteVerificationError, match="HALT_TPM_COMPOSITE_HASH_MISMATCH"):
        verifier.verify_quote_dict(tampered_quote, expected_nonce_hex=nonce_hex)


def test_tpm_quote_rejects_corrupted_signature(quote_engine_and_sample):
    engine, quote_dict, pcr11, nonce_hex = quote_engine_and_sample
    verifier = StandaloneTpmQuoteVerifier()
    corrupted_quote = dict(quote_dict)
    raw_sig = bytearray(base64.b64decode(corrupted_quote["signature_b64"]))
    raw_sig[0] ^= 0xAA
    corrupted_quote["signature_b64"] = base64.b64encode(raw_sig).decode("ascii")

    with pytest.raises(TpmQuoteVerificationError, match="HALT_TPM_SIGNATURE_INVALID"):
        verifier.verify_quote_dict(corrupted_quote, expected_nonce_hex=nonce_hex)


def test_tpm_quote_rejects_hardware_enforcement_on_software(quote_engine_and_sample):
    engine, quote_dict, pcr11, nonce_hex = quote_engine_and_sample
    verifier = StandaloneTpmQuoteVerifier()

    with pytest.raises(TpmQuoteVerificationError, match="HALT_TPM_HARDWARE_REQUIRED"):
        verifier.verify_quote_dict(quote_dict, expected_nonce_hex=nonce_hex, enforce_hardware=True)


def test_tpm_quote_cli_execution(tmp_path, quote_engine_and_sample):
    engine, quote_dict, pcr11, nonce_hex = quote_engine_and_sample
    quote_file = tmp_path / "quote.json"
    quote_file.write_text(json.dumps(quote_dict), encoding="utf-8")
    receipt_file = tmp_path / "receipt.json"

    cmd = [
        sys.executable,
        "tools/verify_tpm_quote.py",
        "--quote",
        str(quote_file),
        "--expected-nonce",
        nonce_hex,
        "--expected-pcr11",
        pcr11,
        "--output-receipt",
        str(receipt_file),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"CLI error: {res.stderr}"
    assert receipt_file.exists()
    saved_receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert saved_receipt["verdict"] == "VERIFIED"
    assert saved_receipt["signature_verified"] is True
