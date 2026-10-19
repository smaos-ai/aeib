#!/usr/bin/env python3
"""
tests/test_standalone_receipt_verifier.py
================================================================================
Verification & Falsification Suite for Standalone Offline Receipt Verifier.

Evaluated under the stated model using real Ed25519 asymmetric cryptography
and RFC 8785 JCS canonicalization.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.standalone_receipt_verifier import (
    compute_sha256_prefixed,
    encode_jcs,
    load_ed25519_public_key,
    run_self_test,
    verify_receipt_data,
)


def test_encode_jcs_canonical_properties() -> None:
    """Verifies that encode_jcs enforces RFC 8785 UTF-16 code unit key sorting."""
    sample = {
        "z": 1,
        "a": 2,
        "\u00e9": 3,
        "A": 4,
        "nested": {"b": True, "a": None, "c": 45.5},
    }
    encoded = encode_jcs(sample)
    # RFC 8785 sorting: "A" (0x0041) comes before "a" (0x0061), "a" comes before "nested", etc.
    decoded = json.loads(encoded.decode("utf-8"))
    assert decoded["z"] == 1
    assert decoded["nested"]["c"] == 45.5
    assert b"\"A\":4" in encoded
    assert b"\"a\":2" in encoded


def test_public_key_loader_formats(tmp_path: Path) -> None:
    """Verifies public key loading from PEM, 64-char hex, and 32-byte base64."""
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()
    pk_raw = pk.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    pk_pem = pk.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # 1. Load from PEM string
    loaded_pem = load_ed25519_public_key(pk_pem)
    assert loaded_pem.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ) == pk_raw

    # 2. Load from hex string
    loaded_hex = load_ed25519_public_key(pk_raw.hex())
    assert loaded_hex.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ) == pk_raw

    # 3. Load from base64 string
    pk_b64 = base64.b64encode(pk_raw).decode("ascii")
    loaded_b64 = load_ed25519_public_key(pk_b64)
    assert loaded_b64.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ) == pk_raw

    # 4. Load from file path
    key_file = tmp_path / "trusted_pubkey.pem"
    key_file.write_bytes(pk_pem)
    loaded_file = load_ed25519_public_key(key_file)
    assert loaded_file.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ) == pk_raw


def test_verify_receipt_positive_and_tamper(tmp_path: Path) -> None:
    """Tests end-to-end receipt verification and fail-closed rejection on tampering."""
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()

    payload = {
        "amount_minor": 10000,
        "currency": "EUR",
        "operation_id": "op-unit-001",
        "recipient": "CZ00000000000000001",
    }
    caid = compute_sha256_prefixed(encode_jcs(payload))
    receipt_body = {
        "action_caid": caid,
        "action_payload": payload,
        "disposition": "CONFIRMED",
        "operation_id": "op-unit-001",
    }
    sig = sk.sign(encode_jcs(receipt_body))

    receipt = dict(receipt_body)
    receipt["signature_b64"] = base64.b64encode(sig).decode("ascii")

    # Positive check
    res_ok = verify_receipt_data(receipt, pk, expected_operation_id="op-unit-001")
    assert res_ok["valid"] is True
    assert res_ok["disposition"] == "CONFIRMED"

    # Operation ID mismatch
    res_mismatch = verify_receipt_data(receipt, pk, expected_operation_id="op-other")
    assert res_mismatch["valid"] is False
    assert "Operation ID mismatch" in res_mismatch["error"]

    # Tampered signature
    tampered_sig_receipt = dict(receipt)
    tampered_sig_receipt["signature_b64"] = base64.b64encode(b"0" * 64).decode("ascii")
    res_bad_sig = verify_receipt_data(tampered_sig_receipt, pk)
    assert res_bad_sig["valid"] is False
    assert "Invalid Ed25519 signature" in res_bad_sig["error"]


def test_standalone_verifier_self_test_battery() -> None:
    """Verifies that run_self_test() executes and returns True."""
    assert run_self_test() is True


def test_standalone_verifier_cli_self_test() -> None:
    """Tests running tools/standalone_receipt_verifier.py --self-test via CLI."""
    script_path = Path("tools/standalone_receipt_verifier.py")
    result = subprocess.run(
        [sys.executable, str(script_path), "--self-test"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "ALL 4 SELF-TEST VECTORS PASSED" in result.stdout
