#!/usr/bin/env python3
"""
tests/test_standalone_receipt_verifier.py
================================================================================
Verification & Falsification Suite for Standalone Offline Receipt Verifier.

Specification Reference:
  OFFLINE_VERIFIER_SPEC.md (Version 1.0.0-rc.3)

Evaluated under the stated model using real Ed25519 asymmetric cryptography
and RFC 8785 JCS canonicalization. Covers POS_01 and all 7 normative negative
vectors (NEG_01 through NEG_07).
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
    CODE_NEG_01,
    CODE_NEG_02,
    CODE_NEG_03,
    CODE_NEG_04,
    CODE_NEG_05,
    CODE_NEG_06,
    CODE_NEG_07,
    compute_sha256_prefixed,
    encode_jcs,
    load_ed25519_public_key,
    run_self_test,
    verify_ledger_stream,
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
        "alg": "Ed25519",
    }
    sig = sk.sign(encode_jcs(receipt_body))

    receipt = dict(receipt_body)
    receipt["signature_b64"] = base64.b64encode(sig).decode("ascii")

    # Positive check
    res_ok = verify_receipt_data(receipt, pk, expected_operation_id="op-unit-001")
    assert res_ok["valid"] is True
    assert res_ok["status"] == "PASS"
    assert res_ok["disposition"] == "CONFIRMED"
    assert res_ok["failure_code"] is None

    # Operation ID mismatch
    res_mismatch = verify_receipt_data(receipt, pk, expected_operation_id="op-other")
    assert res_mismatch["valid"] is False
    assert res_mismatch["status"] == "FAIL"
    assert res_mismatch["failure_code"] == CODE_NEG_03
    assert "Operation ID mismatch" in res_mismatch["error"]

    # Tampered signature
    tampered_sig_receipt = dict(receipt)
    tampered_sig_receipt["signature_b64"] = base64.b64encode(b"0" * 64).decode("ascii")
    res_bad_sig = verify_receipt_data(tampered_sig_receipt, pk)
    assert res_bad_sig["valid"] is False
    assert res_bad_sig["failure_code"] == CODE_NEG_02


def test_normative_negative_vectors_neg01_to_neg07() -> None:
    """Evaluates all seven normative negative falsification vectors per OFFLINE_VERIFIER_SPEC.md."""
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()
    rogue_sk = Ed25519PrivateKey.generate()

    action_payload = {
        "amount_minor": 25000,
        "currency": "EUR",
        "operation_id": "op-neg-matrix-01",
        "recipient": "CZ1234567890",
    }
    caid = compute_sha256_prefixed(encode_jcs(action_payload))
    body = {
        "action_caid": caid,
        "action_payload": action_payload,
        "disposition": "CONFIRMED",
        "operation_id": "op-neg-matrix-01",
        "policy_epoch": 2,
        "timestamp_epoch": 1760000000,
        "alg": "Ed25519",
    }
    sig = sk.sign(encode_jcs(body))
    valid_receipt = dict(body)
    valid_receipt["signature_b64"] = base64.b64encode(sig).decode("ascii")

    # NEG_01: Tampered Payload
    t_rec = dict(valid_receipt)
    t_rec["action_payload"] = dict(action_payload)
    t_rec["action_payload"]["amount_minor"] = 25001
    res1 = verify_receipt_data(t_rec, trusted_public_key=pk)
    assert res1["valid"] is False
    assert res1["failure_code"] == CODE_NEG_01

    # NEG_02: Wrong Key
    rogue_sig = rogue_sk.sign(encode_jcs(body))
    rogue_rec = dict(valid_receipt)
    rogue_rec["signature_b64"] = base64.b64encode(rogue_sig).decode("ascii")
    res2 = verify_receipt_data(rogue_rec, trusted_public_key=pk)
    assert res2["valid"] is False
    assert res2["failure_code"] == CODE_NEG_02

    # NEG_03: Malformed Schema / Missing operation_id
    malformed = dict(valid_receipt)
    del malformed["operation_id"]
    res3 = verify_receipt_data(malformed, trusted_public_key=pk)
    assert res3["valid"] is False
    assert res3["failure_code"] == CODE_NEG_03

    # NEG_04: Stale Authority / Expired Timestamp
    exp_body = dict(body)
    exp_body["expires_at"] = 1760000000
    exp_sig = sk.sign(encode_jcs(exp_body))
    exp_rec = dict(exp_body)
    exp_rec["signature_b64"] = base64.b64encode(exp_sig).decode("ascii")
    res4 = verify_receipt_data(exp_rec, trusted_public_key=pk, current_time_epoch=1760000500)
    assert res4["valid"] is False
    assert res4["failure_code"] == CODE_NEG_04

    # NEG_05 & NEG_06: Ledger Replay and Broken Chain
    init_tip = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    e1 = dict(valid_receipt)
    e1["operation_id"] = "op-stream-01"
    e1["prev_chain_tip"] = init_tip
    del e1["signature_b64"]
    e1["signature_b64"] = base64.b64encode(sk.sign(encode_jcs(e1))).decode("ascii")
    tip1 = compute_sha256_prefixed(encode_jcs(dict((k, v) for k, v in e1.items() if k != "signature_b64")))

    # Replay
    e2_rep = dict(valid_receipt)
    e2_rep["operation_id"] = "op-stream-01"
    e2_rep["prev_chain_tip"] = tip1
    del e2_rep["signature_b64"]
    e2_rep["signature_b64"] = base64.b64encode(sk.sign(encode_jcs(e2_rep))).decode("ascii")
    res5 = verify_ledger_stream([json.dumps(e1), json.dumps(e2_rep)], trusted_public_key=pk, expected_initial_tip=init_tip)
    assert res5["valid"] is False
    assert res5["failure_code"] == CODE_NEG_05

    # Broken Chain
    e2_bad_tip = dict(valid_receipt)
    e2_bad_tip["operation_id"] = "op-stream-02"
    e2_bad_tip["prev_chain_tip"] = "sha256:broken_tip_hash_1234567890"
    del e2_bad_tip["signature_b64"]
    e2_bad_tip["signature_b64"] = base64.b64encode(sk.sign(encode_jcs(e2_bad_tip))).decode("ascii")
    res6 = verify_ledger_stream([json.dumps(e1), json.dumps(e2_bad_tip)], trusted_public_key=pk, expected_initial_tip=init_tip)
    assert res6["valid"] is False
    assert res6["failure_code"] == CODE_NEG_06

    # NEG_07: Algorithm Downgrade
    down_rec = dict(valid_receipt)
    down_rec["alg"] = "none"
    del down_rec["signature_b64"]
    down_rec["signature_b64"] = base64.b64encode(sk.sign(encode_jcs(down_rec))).decode("ascii")
    res7 = verify_receipt_data(down_rec, trusted_public_key=pk)
    assert res7["valid"] is False
    assert res7["failure_code"] == CODE_NEG_07


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
    assert "ALL 8 NORMATIVE VECTORS PASSED" in result.stdout


def test_standalone_verifier_cli_receipt_json_output(tmp_path: Path) -> None:
    """Tests CLI execution of receipt verification with --json output formatting."""
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()
    pk_pem = pk.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pk_file = tmp_path / "trusted_pubkey.pem"
    pk_file.write_bytes(pk_pem)

    payload = {"amount_minor": 1500, "currency": "EUR", "operation_id": "op-cli-001"}
    caid = compute_sha256_prefixed(encode_jcs(payload))
    body = {
        "action_caid": caid,
        "action_payload": payload,
        "disposition": "CONFIRMED",
        "operation_id": "op-cli-001",
        "alg": "Ed25519",
    }
    sig = sk.sign(encode_jcs(body))
    receipt = dict(body)
    receipt["signature_b64"] = base64.b64encode(sig).decode("ascii")

    receipt_file = tmp_path / "receipt.json"
    receipt_file.write_text(json.dumps(receipt), encoding="utf-8")

    script_path = Path("tools/standalone_receipt_verifier.py")
    res = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--receipt",
            str(receipt_file),
            "--public-key",
            str(pk_file),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    out_json = json.loads(res.stdout)
    assert out_json["status"] == "PASS"
    assert out_json["operation_id"] == "op-cli-001"
    assert out_json["failure_code"] is None
    assert out_json["verifier_version"] == "1.0.0-rc.3"
