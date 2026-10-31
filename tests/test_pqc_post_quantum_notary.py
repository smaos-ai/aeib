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
tests/test_pqc_post_quantum_notary.py
================================================================================
Verification Suite for PqcPostQuantumNotary.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. HybridPqcNotaryReceipt validations, boundaries, and frozen immutability.
2. CAID generation across str, bytes, and dictionary payloads.
3. Notary initialization parameters and invalid argument rejection.
4. Nominal hybrid notarization (Ed25519 + ML-DSA dual algorithm success).
5. Statement payload mismatch detection and rejection.
6. Classical signature tampering detection and fail-closed rejection.
7. PQC signature tampering detection and fail-closed rejection.
8. PQC public key mismatch detection.
9. SQLite-WAL persistence and durable ledger queries.
10. Exact mutation boundary testing and limit queries.
11. Wilson 95% confidence interval calculations.
"""

from __future__ import annotations

import base64
import dataclasses
import math
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Tuple

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.pqc_post_quantum_notary import (
    ALGORITHM_CLASSICAL,
    ALGORITHM_PQC_DEFAULT,
    STATUS_DUAL_VERIFIED,
    STATUS_FAIL_CLASSICAL,
    STATUS_FAIL_MALFORMED,
    STATUS_FAIL_PQC,
    HybridPqcNotaryReceipt,
    PqcPostQuantumNotary,
    compute_sha256_caid,
)


def compute_wilson_ci_bps(k: int, n: int, z: float = 1.959963984540054) -> Tuple[int, int]:
    """Calculates conservative Wilson 95% confidence interval in basis points."""
    if n == 0:
        return (0, 10000)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    low = max(0.0, centre - half)
    high = min(1.0, centre + half)
    return (int(round(low * 10000)), int(round(high * 10000)))


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    return str(tmp_path / "test_pqc_notary.db")


@pytest.fixture
def notary() -> PqcPostQuantumNotary:
    return PqcPostQuantumNotary(notary_id="notary-test-01")


def test_01_receipt_dataclass_validations() -> None:
    valid_args: Dict[str, Any] = {
        "receipt_id": "rcpt-01",
        "epoch_id": "epoch-01",
        "statement_caid": "sha256:11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        "classical_algorithm": ALGORITHM_CLASSICAL,
        "classical_pubkey_pem": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA\n-----END PUBLIC KEY-----",
        "classical_signature_b64": "c2lnbmF0dXJl",
        "pqc_algorithm": ALGORITHM_PQC_DEFAULT,
        "pqc_public_key_hex": "0123456789abcdef" * 4,
        "pqc_signature_hex": "fedcba9876543210" * 4,
        "status": STATUS_DUAL_VERIFIED,
        "receipt_caid": "sha256:99887766554433221100aabbccddeeff99887766554433221100aabbccddeeff",
        "timestamp_ms": 1700000000000,
    }
    r = HybridPqcNotaryReceipt(**valid_args)
    assert r.receipt_id == "rcpt-01"

    # Frozen immutability
    with pytest.raises(Exception):
        r.status = STATUS_FAIL_CLASSICAL  # type: ignore

    # Validation errors
    for f in [
        "receipt_id",
        "epoch_id",
        "classical_algorithm",
        "classical_pubkey_pem",
        "classical_signature_b64",
        "pqc_algorithm",
        "pqc_public_key_hex",
        "pqc_signature_hex",
        "status",
    ]:
        bad = dict(valid_args)
        bad[f] = ""
        with pytest.raises(ValueError, match=f"{f} must be a non-empty string"):
            HybridPqcNotaryReceipt(**bad)

    bad_stmt = dict(valid_args)
    bad_stmt["statement_caid"] = "bad"
    with pytest.raises(ValueError, match="statement_caid must be a valid sha256 prefix string"):
        HybridPqcNotaryReceipt(**bad_stmt)

    bad_caid = dict(valid_args)
    bad_caid["receipt_caid"] = "bad"
    with pytest.raises(ValueError, match="receipt_caid must be a valid sha256 prefix string"):
        HybridPqcNotaryReceipt(**bad_caid)

    bad_ts = dict(valid_args)
    bad_ts["timestamp_ms"] = 0
    with pytest.raises(ValueError, match="timestamp_ms must be a positive integer"):
        HybridPqcNotaryReceipt(**bad_ts)

    # Exact boundary check timestamp_ms = 1
    good_ts1 = HybridPqcNotaryReceipt(**dict(valid_args, timestamp_ms=1))
    assert good_ts1.timestamp_ms == 1


def test_02_caid_generation() -> None:
    c1 = compute_sha256_caid("test_statement")
    c2 = compute_sha256_caid(b"test_statement")
    assert c1 == c2
    assert c1.startswith("sha256:")

    d1 = {"b": 2, "a": 1}
    d2 = {"a": 1, "b": 2}
    assert compute_sha256_caid(d1) == compute_sha256_caid(d2)


def test_03_notary_initialization_and_validation() -> None:
    n = PqcPostQuantumNotary(notary_id="notary-custom", pqc_algorithm="SLH-DSA-SHAKE-128f")
    assert n.notary_id == "notary-custom"
    assert n.pqc_algorithm == "SLH-DSA-SHAKE-128f"
    assert len(n.pqc_public_key_hex) == 64
    n.close()

    with pytest.raises(ValueError, match="notary_id must be a non-empty string"):
        PqcPostQuantumNotary(notary_id="")
    with pytest.raises(ValueError, match="pqc_algorithm must be a non-empty string"):
        PqcPostQuantumNotary(pqc_algorithm="")


def test_04_nominal_hybrid_notarization(notary: PqcPostQuantumNotary) -> None:
    statement = {
        "action": "SCITT_SUPER_ROOT_SEAL",
        "epoch_id": "epoch-001",
        "root_hash": "sha256:00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff",
    }
    t_start = int(time.time() * 1000)
    receipt = notary.notarize_statement(statement, epoch_id="epoch-001")
    t_end = int(time.time() * 1000)
    assert t_start <= receipt.timestamp_ms <= t_end + 100
    assert receipt.status == STATUS_DUAL_VERIFIED
    assert receipt.classical_algorithm == ALGORITHM_CLASSICAL
    assert receipt.pqc_algorithm == ALGORITHM_PQC_DEFAULT

    # Verify receipt
    is_valid, status = notary.verify_hybrid_receipt(receipt, statement)
    assert is_valid is True
    assert status == STATUS_DUAL_VERIFIED


def test_05_statement_mismatch_rejection(notary: PqcPostQuantumNotary) -> None:
    statement = {"action": "ROOT_SEAL", "val": 100}
    receipt = notary.notarize_statement(statement, epoch_id="epoch-001")

    # Present a modified statement
    tampered_statement = {"action": "ROOT_SEAL", "val": 999}
    is_valid, status = notary.verify_hybrid_receipt(receipt, tampered_statement)
    assert is_valid is False
    assert status == STATUS_FAIL_MALFORMED


def test_06_classical_signature_tampering(notary: PqcPostQuantumNotary) -> None:
    statement = {"action": "TRANSACTION_COMMIT", "amount": 5000}
    receipt = notary.notarize_statement(statement, epoch_id="epoch-001")

    # Tamper classical signature
    bad_classical_sig = base64.b64encode(b"forged_ed25519_signature_bytes_1234567890123456").decode("ascii")
    bad_receipt = dataclasses.replace(receipt, classical_signature_b64=bad_classical_sig)

    is_valid, status = notary.verify_hybrid_receipt(bad_receipt, statement)
    assert is_valid is False
    assert status == STATUS_FAIL_CLASSICAL


def test_07_pqc_signature_tampering(notary: PqcPostQuantumNotary) -> None:
    statement = {"action": "TRANSACTION_COMMIT", "amount": 5000}
    receipt = notary.notarize_statement(statement, epoch_id="epoch-001")

    # Tamper PQC signature
    bad_pqc_sig = "0" * 64
    bad_receipt = dataclasses.replace(receipt, pqc_signature_hex=bad_pqc_sig)

    is_valid, status = notary.verify_hybrid_receipt(bad_receipt, statement)
    assert is_valid is False
    assert status == STATUS_FAIL_PQC


def test_08_pqc_public_key_mismatch(notary: PqcPostQuantumNotary) -> None:
    statement = {"action": "TRANSACTION_COMMIT", "amount": 5000}
    receipt = notary.notarize_statement(statement, epoch_id="epoch-001")

    # Foreign public key
    bad_pqc_pubkey = "f" * 64
    bad_receipt = dataclasses.replace(receipt, pqc_public_key_hex=bad_pqc_pubkey)

    is_valid, status = notary.verify_hybrid_receipt(bad_receipt, statement)
    assert is_valid is False
    assert status == STATUS_FAIL_PQC


def test_09_sqlite_persistence_and_queries(temp_db: str) -> None:
    n = PqcPostQuantumNotary(notary_id="notary-sql", db_path=temp_db)
    statement = {"action": "AUDIT_CLOSE", "count": 10}
    rcpt = n.notarize_statement(statement, epoch_id="epoch-99", now_ms=1700000005000)

    records = n.get_ledger_records(limit=10)
    assert len(records) == 1
    assert records[0]["receipt_id"] == rcpt.receipt_id
    assert records[0]["status"] == STATUS_DUAL_VERIFIED
    n.close()

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT status, classical_algorithm, pqc_algorithm FROM pqc_notary_ledger")
    row = cur.fetchone()
    assert row[0] == STATUS_DUAL_VERIFIED
    assert row[1] == ALGORITHM_CLASSICAL
    assert row[2] == ALGORITHM_PQC_DEFAULT
    conn.close()


def test_10_exact_mutation_boundaries(temp_db: str) -> None:
    # Test algorithm constants
    assert ALGORITHM_CLASSICAL == "Ed25519-RFC-8032"
    assert ALGORITHM_PQC_DEFAULT == "ML-DSA-65-FIPS-204"

    n = PqcPostQuantumNotary(notary_id="notary-bound", db_path=temp_db)

    # Input validations on notarize_statement
    with pytest.raises(ValueError, match="statement_payload must be a non-empty dictionary"):
        n.notarize_statement({}, epoch_id="ep-1")  # type: ignore
    with pytest.raises(ValueError, match="statement_payload must be a non-empty dictionary"):
        n.notarize_statement("not_dict", epoch_id="ep-1")  # type: ignore
    with pytest.raises(ValueError, match="epoch_id must be a non-empty string"):
        n.notarize_statement({"a": 1}, epoch_id="")

    # Test exact dictionary fields from ledger
    n.notarize_statement({"init": 1}, epoch_id="ep-0", now_ms=1000)
    r_def = n.notarize_statement({"test_key": "val"}, epoch_id="ep-fields", now_ms=2000)
    assert r_def.timestamp_ms == 2000
    records = n.get_ledger_records(limit=5)
    assert len(records) >= 2
    r_last = records[0]
    assert r_last["receipt_id"] == r_def.receipt_id
    assert r_last["epoch_id"] == "ep-fields"
    assert r_last["statement_caid"] == r_def.statement_caid
    assert r_last["status"] == STATUS_DUAL_VERIFIED
    assert r_last["classical_algorithm"] == ALGORITHM_CLASSICAL
    assert r_last["pqc_algorithm"] == ALGORITHM_PQC_DEFAULT
    assert r_last["receipt_caid"] == r_def.receipt_caid
    assert r_last["timestamp_ms"] == r_def.timestamp_ms

    # Test timestamp_ms <= 0 boundary
    valid_args: Dict[str, Any] = {
        "receipt_id": "r1",
        "epoch_id": "e1",
        "statement_caid": "sha256:00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff",
        "classical_algorithm": ALGORITHM_CLASSICAL,
        "classical_pubkey_pem": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA\n-----END PUBLIC KEY-----",
        "classical_signature_b64": "c2lnbmF0dXJl",
        "pqc_algorithm": ALGORITHM_PQC_DEFAULT,
        "pqc_public_key_hex": "0123456789abcdef" * 4,
        "pqc_signature_hex": "fedcba9876543210" * 4,
        "status": STATUS_DUAL_VERIFIED,
        "receipt_caid": "sha256:00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff",
        "timestamp_ms": 0,
    }
    with pytest.raises(ValueError, match="timestamp_ms must be a positive integer"):
        HybridPqcNotaryReceipt(**valid_args)

    # Test non-Ed25519 classical public key (e.g. EC SECP256R1)
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    ec_priv = ec.generate_private_key(ec.SECP256R1())
    ec_pem_str = ec_priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    bad_ec_rcpt = dataclasses.replace(r_def, classical_pubkey_pem=ec_pem_str)
    ok_ec, status_ec = n.verify_hybrid_receipt(bad_ec_rcpt, {"test_key": "val"})
    assert ok_ec is False
    assert status_ec == STATUS_FAIL_CLASSICAL

    # Query with limit=1
    rows_1 = n.get_ledger_records(limit=1)
    assert len(rows_1) == 1
    n.close()


def test_11_wilson_ci_bounds() -> None:
    low, high = compute_wilson_ci_bps(30, 30)
    assert low > 8500
    assert high == 10000
