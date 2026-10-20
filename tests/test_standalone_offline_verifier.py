#!/usr/bin/env python3
"""
tests/test_standalone_offline_verifier.py
================================================================================
Verification & Falsification Suite for AEIB Standalone Zero-Dependency Verifier.

Evaluated under the stated model using pure Python RFC 8032 Ed25519 arithmetic,
RFC 8785 JCS canonicalization, and RFC 9162 Merkle inclusion proofs.
Covers positive verification vectors and rigorous falsification vectors.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from tools.standalone_offline_verifier import (
    compute_field_commitment,
    compute_jcs_sha256,
    compute_receipt_root,
    ed25519_sign,
    ed25519_verify,
    encode_jcs,
    parse_ed25519_public_key,
    rfc9162_hash_children,
    rfc9162_hash_leaf,
    run_self_test,
    verify_aeib_execution_receipt,
    verify_any_receipt,
    verify_merkle_receipt,
    verify_rfc9162_inclusion,
    verify_selective_disclosure_receipt,
)


def test_pure_python_ed25519_cross_verification_with_hazmat() -> None:
    """Verifies that pure Python RFC 8032 arithmetic matches cryptography.hazmat bit-for-bit."""
    seed_bytes = b"seed_32_bytes_cross_validation__"
    msg = b"AEIB Audit Action Payload Cross Verification"

    # 1. Sign with pure Python engine
    pure_pub, pure_sig = ed25519_sign(seed_bytes, msg)

    # 2. Sign with cryptography.hazmat
    hazmat_priv = Ed25519PrivateKey.from_private_bytes(seed_bytes)
    hazmat_pub = hazmat_priv.public_key().public_bytes_raw()
    hazmat_sig = hazmat_priv.sign(msg)

    # 3. Assert exact bit-for-bit equivalence
    assert pure_pub == hazmat_pub
    assert pure_sig == hazmat_sig

    # 4. Cross verify signatures
    assert ed25519_verify(hazmat_pub, msg, hazmat_sig) is True
    # Verify hazmat accepts pure signature
    Ed25519PublicKey.from_public_bytes(pure_pub).verify(pure_sig, msg)


def test_positive_aeib_execution_receipt_verification() -> None:
    """Verifies valid signed AEIB execution receipt with Ed25519 and JCS canonical digest."""
    seed_bytes = b"sample_seed_for_aeib_receipt_32_"
    payload = {
        "actor": "aeib-station-worker",
        "action": "execute_tool",
        "parameters": {"query": "SELECT balance FROM accounts WHERE id = 1"},
        "result_code": 200,
    }
    caid = compute_jcs_sha256(payload)

    unsigned_payload = {
        "receipt_version": "v0.2.0",
        "operation_id": "op-cross-789",
        "action_payload": payload,
        "action_caid": caid,
        "policy_epoch": 12,
        "disposition": "CONFIRMED",
    }
    payload_hash = compute_jcs_sha256(unsigned_payload)
    signable_view = {
        "unsigned_payload": unsigned_payload,
        "unsigned_payload_hash": payload_hash,
    }
    pub_bytes, receipt_sig = ed25519_sign(seed_bytes, encode_jcs(signable_view))

    receipt = {
        "format": "AEIB_JSON_ED25519_PROTOTYPE",
        "operation_id": "op-cross-789",
        "unsigned_payload": unsigned_payload,
        "unsigned_payload_hash": payload_hash,
        "signature_metadata": {
            "signature": receipt_sig.hex(),
            "algorithm": "Ed25519",
        },
    }

    result = verify_aeib_execution_receipt(receipt, pub_bytes, current_epoch=20)
    assert result["valid"] is True
    assert result["operation_id"] == "op-cross-789"
    assert result["disposition"] == "CONFIRMED"


def test_falsification_tampered_receipt_signature() -> None:
    """Falsification: Receipts with modified or corrupted signature bytes fail verification."""
    seed_bytes = b"sample_seed_for_aeib_receipt_32_"
    payload = {"account": "4401", "transfer": 500}
    caid = compute_jcs_sha256(payload)

    unsigned_payload = {
        "operation_id": "op-tamper-sig",
        "action_payload": payload,
        "action_caid": caid,
        "disposition": "CONFIRMED",
    }
    signable = {"unsigned_payload": unsigned_payload, "unsigned_payload_hash": compute_jcs_sha256(unsigned_payload)}
    pub_bytes, receipt_sig = ed25519_sign(seed_bytes, encode_jcs(signable))

    # Invert bits in signature
    corrupted_sig = bytearray(receipt_sig)
    corrupted_sig[15] ^= 0xAA

    receipt = {
        "format": "AEIB_JSON_ED25519_PROTOTYPE",
        "operation_id": "op-tamper-sig",
        "unsigned_payload": unsigned_payload,
        "unsigned_payload_hash": compute_jcs_sha256(unsigned_payload),
        "signature_metadata": {
            "signature": bytes(corrupted_sig).hex(),
            "algorithm": "Ed25519",
        },
    }

    result = verify_aeib_execution_receipt(receipt, pub_bytes)
    assert result["valid"] is False
    assert "Ed25519 signature verification failed" in result["error"]


def test_falsification_tampered_payload_content() -> None:
    """Falsification: Tampered payload content produces CAID mismatch and fails closed."""
    seed_bytes = b"sample_seed_for_aeib_receipt_32_"
    original_payload = {"amount": 100, "beneficiary": "DE100"}
    caid = compute_jcs_sha256(original_payload)

    unsigned_payload = {
        "operation_id": "op-tamper-payload",
        "action_payload": original_payload,
        "action_caid": caid,
        "disposition": "CONFIRMED",
    }
    signable = {"unsigned_payload": unsigned_payload, "unsigned_payload_hash": compute_jcs_sha256(unsigned_payload)}
    pub_bytes, receipt_sig = ed25519_sign(seed_bytes, encode_jcs(signable))

    # Attacker alters payload amount
    tampered_unsigned = dict(unsigned_payload)
    tampered_unsigned["action_payload"] = {"amount": 999999, "beneficiary": "DE100"}

    receipt = {
        "format": "AEIB_JSON_ED25519_PROTOTYPE",
        "operation_id": "op-tamper-payload",
        "unsigned_payload": tampered_unsigned,
        "unsigned_payload_hash": compute_jcs_sha256(unsigned_payload),
        "signature_metadata": {
            "signature": receipt_sig.hex(),
            "algorithm": "Ed25519",
        },
    }

    result = verify_aeib_execution_receipt(receipt, pub_bytes)
    assert result["valid"] is False
    assert "CAID mismatch" in result["error"]


def test_positive_selective_disclosure_receipt() -> None:
    """Verifies selective disclosure receipt with salted blind commitments and unredacted claims."""
    seed_bytes = b"seed_for_selective_disclosure32_"
    claims = {
        "customer_id": "cust-890",
        "customer_iban": "DE89370400440532013000",
        "transaction_ref": "tx-2026-999",
        "amount_cents": 45000,
    }
    salts = {
        "customer_id": "11" * 16,
        "customer_iban": "22" * 16,
        "transaction_ref": "33" * 16,
        "amount_cents": "44" * 16,
    }
    field_commits = {k: compute_field_commitment(k, claims[k], salts[k]) for k in claims}
    root_hash = compute_receipt_root(field_commits)
    pub_bytes, sig_bytes = ed25519_sign(seed_bytes, root_hash.encode("utf-8"))

    # Redact sensitive PII: customer_iban
    disclosed_claims = {
        "customer_id": claims["customer_id"],
        "transaction_ref": claims["transaction_ref"],
        "amount_cents": claims["amount_cents"],
    }
    disclosed_salts = {
        "customer_id": salts["customer_id"],
        "transaction_ref": salts["transaction_ref"],
        "amount_cents": salts["amount_cents"],
    }
    redacted_commits = {
        "customer_iban": field_commits["customer_iban"],
    }

    sd_receipt = {
        "receipt_id": "sd-rcpt-pii-redacted-01",
        "disclosed_claims": disclosed_claims,
        "disclosed_salts": disclosed_salts,
        "redacted_field_commitments": redacted_commits,
        "root_hash": root_hash,
        "signature_envelope": {
            "algorithm": "Ed25519",
            "public_key_hex": pub_bytes.hex(),
            "signature_b64": base64.b64encode(sig_bytes).decode("ascii"),
        },
    }

    result = verify_selective_disclosure_receipt(sd_receipt, pub_bytes)
    assert result["valid"] is True
    assert result["disclosed_fields_count"] == 3
    assert result["redacted_fields_count"] == 1


def test_positive_rfc9162_merkle_tree_inclusion() -> None:
    """Verifies RFC 9162 domain-separated inclusion proof against pinned root."""
    leaf0 = rfc9162_hash_leaf(b"leaf_data_0")
    leaf1 = rfc9162_hash_leaf(b"leaf_data_1")
    root = rfc9162_hash_children(leaf0, leaf1)

    receipt = {
        "leaf_index": 0,
        "tree_size": 2,
        "leaf_hash": leaf0.hex(),
        "root_hash": root.hex(),
        "inclusion_proof": [leaf1.hex()],
    }

    result = verify_merkle_receipt(receipt, pinned_root_bytes=root)
    assert result["valid"] is True
    assert result["leaf_index"] == 0
    assert result["tree_size"] == 2


def test_positive_validation_receipt_envelope_format() -> None:
    """Verifies that Format 5 (receipt_body + signature_envelope) is verified correctly."""
    seed_bytes = b"sample_seed_for_aeib_receipt_32_"

    receipt_body = {
        "validation_run": {
            "engine": "AEIB Standalone Offline Verifier Test",
            "all_passed": True,
        },
        "steps": [{"name": "step1", "passed": True}],
    }
    canonical_body = encode_jcs(receipt_body)
    pub_bytes, sig_bytes = ed25519_sign(seed_bytes, canonical_body)

    receipt = {
        "receipt_body": receipt_body,
        "signature_envelope": {
            "algorithm": "Ed25519",
            "public_key_hex": pub_bytes.hex(),
            "signature_b64": base64.b64encode(sig_bytes).decode("ascii"),
        },
    }

    result = verify_aeib_execution_receipt(receipt)
    assert result["valid"] is True
    assert result["operation_id"] == "AEIB Standalone Offline Verifier Test"


def test_cli_self_test_execution() -> None:
    """Verifies that standalone_offline_verifier.py --self-test executes cleanly."""
    cmd = [sys.executable, "tools/standalone_offline_verifier.py", "--self-test"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "[VALID] Standalone Offline Verifier Self-Test" in proc.stdout
