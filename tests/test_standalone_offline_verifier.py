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

    # Pinned key: verified. (Previously this test called the verifier with no
    # trusted key and expected valid=True from the receipt's self-embedded key;
    # that encoded the key-substitution weakness and was changed.)
    result = verify_aeib_execution_receipt(receipt, pub_bytes)
    assert result["valid"] is True
    assert result["key_pinned"] is True
    assert result["operation_id"] == "AEIB Standalone Offline Verifier Test"

    # No trusted key: rejected by default, accepted only with explicit opt-in.
    unpinned = verify_aeib_execution_receipt(receipt)
    assert unpinned["valid"] is False
    assert unpinned["key_pinned"] is False
    opted_in = verify_aeib_execution_receipt(receipt, allow_embedded_key=True)
    assert opted_in["valid"] is True
    assert opted_in["key_pinned"] is False


def test_cli_self_test_execution() -> None:
    """Verifies that standalone_offline_verifier.py --self-test executes cleanly."""
    cmd = [sys.executable, "tools/standalone_offline_verifier.py", "--self-test"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "[VALID] Standalone Offline Verifier Self-Test" in proc.stdout


# ------------------------------------------------------------------------------
# Red-team regression tests (A4 offline verifier / A1 JCS differential)
# ------------------------------------------------------------------------------

import hashlib
import math
import os
import random

from cryptography.exceptions import InvalidSignature

import tools.standalone_offline_verifier as sov
from src.jcs_canonicalizer import encode_jcs as reference_encode_jcs

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _small_order_encodings() -> list:
    """Derives the distinct torsion-subgroup point encodings as L * P for curve points P."""
    found = set()
    y = 2
    while len(found) < 8 and y < 400:
        for sign in (0, 1):
            pt = sov._decompress_point(y.to_bytes(32, "little") if sign == 0 else
                                       (y | (1 << 255)).to_bytes(32, "little"))
            if pt is not None:
                found.add(sov._compress_point(sov._point_mul(sov.ORDER_L, pt)))
        y += 1
    return sorted(found)


def test_small_order_encodings_cover_full_torsion_subgroup() -> None:
    encs = _small_order_encodings()
    assert len(encs) == 8
    assert (1).to_bytes(32, "little") in encs  # neutral element


def test_small_order_public_key_forgery_rejected() -> None:
    """A = R = small-order point with s = 0 used to verify for any message; must be rejected."""
    for enc in _small_order_encodings():
        weak_sig = enc + (0).to_bytes(32, "little")
        for _ in range(3):
            assert ed25519_verify(enc, os.urandom(16), weak_sig) is False


def test_small_order_r_with_honest_key_rejected() -> None:
    seed = b"small_order_R_rejection_seed_32_"
    pub, sig = ed25519_sign(seed, b"m")
    assert ed25519_verify(pub, b"m", sig) is True
    for enc in _small_order_encodings():
        assert ed25519_verify(pub, b"m", enc + sig[32:]) is False


def test_non_canonical_point_encodings_rejected() -> None:
    p = sov.FIELD_P
    seed = b"non_canonical_encoding_seed_32__"
    pub, sig = ed25519_sign(seed, b"m")
    # y >= p (y = p + 1 aliases y = 1) and y = p (aliases 0)
    for y_val in (p, p + 1, p + 2, 2**255 - 1):
        enc = y_val.to_bytes(32, "little")
        assert sov._decompress_point(enc) is None
        assert ed25519_verify(enc, b"m", sig) is False
        assert ed25519_verify(pub, b"m", enc + sig[32:]) is False
    # x == 0 with sign bit set (non-canonical identity encoding)
    neg_zero = bytearray((1).to_bytes(32, "little"))
    neg_zero[31] |= 0x80
    assert sov._decompress_point(bytes(neg_zero)) is None
    # s >= L malleability still rejected
    s_int = int.from_bytes(sig[32:], "little") + sov.ORDER_L
    assert ed25519_verify(pub, b"m", sig[:32] + s_int.to_bytes(32, "little")) is False


def _hazmat_accepts(pub: bytes, msg: bytes, sig: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, msg)
        return True
    except (InvalidSignature, ValueError):
        return False


def test_ed25519_parity_with_hazmat_on_random_and_tampered_signatures() -> None:
    rng = random.Random(42)
    mismatches = []
    for i in range(200):
        seed = bytes(rng.getrandbits(8) for _ in range(32))
        msg = bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 64)))
        priv = Ed25519PrivateKey.from_private_bytes(seed)
        pub = priv.public_key().public_bytes_raw()
        sig = priv.sign(msg)
        bad_sig = bytearray(sig)
        bad_sig[rng.randrange(64)] ^= 1 << rng.randrange(8)
        bad_pub = bytearray(pub)
        bad_pub[rng.randrange(32)] ^= 1 << rng.randrange(8)
        cases = [
            (pub, msg, sig, True),
            (pub, msg + b"x", sig, False),
            (pub, msg, bytes(bad_sig), False),
            (bytes(bad_pub), msg, sig, False),
        ]
        for c_pub, c_msg, c_sig, expected in cases:
            ours = ed25519_verify(c_pub, c_msg, c_sig)
            theirs = _hazmat_accepts(c_pub, c_msg, c_sig)
            if ours != theirs or ours != expected:
                mismatches.append((i, ours, theirs, expected))
    assert mismatches == []


def _signed_flat_receipt(seed: bytes) -> tuple:
    pub, _ = ed25519_sign(seed, b"")
    unsigned = {"caid": "a" * 64, "disposition": "CONFIRMED", "policy_epoch": 1, "public_key_hex": pub.hex()}
    _, sig = ed25519_sign(seed, encode_jcs(unsigned))
    return pub, dict(unsigned, signature_hex=sig.hex())


def test_unpinned_embedded_key_rejected_by_default() -> None:
    pub, rcpt = _signed_flat_receipt(b"attacker_self_signed_seed_32b___")
    res = verify_any_receipt(rcpt, None)
    assert res["valid"] is False
    assert res["key_pinned"] is False
    assert "No trusted public key supplied" in res["error"]

    opted = verify_any_receipt(rcpt, None, allow_embedded_key=True)
    assert opted["valid"] is True
    assert opted["key_pinned"] is False

    pinned = verify_any_receipt(rcpt, pub)
    assert pinned["valid"] is True
    assert pinned["key_pinned"] is True

    other_pub, _ = ed25519_sign(b"legitimate_issuer_seed_32_bytes_", b"")
    assert verify_any_receipt(rcpt, other_pub)["valid"] is False


def test_unpinned_selective_disclosure_rejected_by_default() -> None:
    seed = b"sd_unpinned_seed_32_bytes_long__"
    claims = {"a": 1, "b": "x"}
    salts = {"a": "11" * 16, "b": "22" * 16}
    commits = {k: compute_field_commitment(k, claims[k], salts[k]) for k in claims}
    root = compute_receipt_root(commits)
    pub, sig = ed25519_sign(seed, root.encode("utf-8"))
    rcpt = {
        "receipt_id": "sd-unpinned",
        "disclosed_claims": {"a": 1},
        "disclosed_salts": {"a": salts["a"]},
        "redacted_field_commitments": {"b": commits["b"]},
        "root_hash": root,
        "signature_envelope": {"public_key_hex": pub.hex(), "signature_b64": base64.b64encode(sig).decode()},
    }
    res = verify_any_receipt(rcpt)
    assert res["valid"] is False and res["key_pinned"] is False
    opted = verify_any_receipt(rcpt, allow_embedded_key=True)
    assert opted["valid"] is True and opted["key_pinned"] is False
    pinned = verify_any_receipt(rcpt, pub)
    assert pinned["valid"] is True and pinned["key_pinned"] is True


def test_cli_requires_pinned_key_unless_allow_embedded_key(tmp_path: Path) -> None:
    _, rcpt = _signed_flat_receipt(b"cli_unpinned_seed_32_bytes_long_")
    path = tmp_path / "r.json"
    path.write_text(json.dumps(rcpt), encoding="utf-8")
    script = str(_REPO_ROOT / "tools" / "standalone_offline_verifier.py")
    base = [sys.executable, script, "--verify-receipt", str(path), "--json"]
    proc = subprocess.run(base, capture_output=True, text=True, check=False)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["valid"] is False
    proc2 = subprocess.run(base + ["--allow-embedded-key"], capture_output=True, text=True, check=False)
    assert proc2.returncode == 0
    out = json.loads(proc2.stdout)
    assert out["valid"] is True and out["key_pinned"] is False
    helptext = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True, check=False).stdout
    assert "--allow-embedded-key" in helptext


def _mth(leaves: list) -> bytes:
    n = len(leaves)
    if n == 1:
        return leaves[0]
    k = 1
    while k * 2 < n:
        k *= 2
    return rfc9162_hash_children(_mth(leaves[:k]), _mth(leaves[k:]))


def _path(m: int, leaves: list) -> list:
    n = len(leaves)
    if n == 1:
        return []
    k = 1
    while k * 2 < n:
        k *= 2
    if m < k:
        return _path(m, leaves[:k]) + [_mth(leaves[k:])]
    return _path(m - k, leaves[k:]) + [_mth(leaves[:k])]


def test_rfc9162_inclusion_exhaustive_small_trees() -> None:
    """Every honest proof for sizes 1..33 verifies; truncated/extended/wrong-index proofs fail."""
    for n in range(1, 34):
        leaves = [rfc9162_hash_leaf(f"leaf-{n}-{i}".encode()) for i in range(n)]
        root = _mth(leaves)
        for m in range(n):
            path = _path(m, leaves)
            assert verify_rfc9162_inclusion(leaves[m], m, n, path, root) is True, (n, m)
            if path:
                assert verify_rfc9162_inclusion(leaves[m], m, n, path[:-1], root) is False
            assert verify_rfc9162_inclusion(leaves[m], m, n, path + [root], root) is False
            if n > 1 and (m ^ 1) < n:
                assert verify_rfc9162_inclusion(leaves[m], m ^ 1, n, path, root) is False


def test_truncated_proof_interior_node_as_leaf_rejected() -> None:
    leaves = [rfc9162_hash_leaf(bytes([i])) for i in range(4)]
    n01 = rfc9162_hash_children(leaves[0], leaves[1])
    n23 = rfc9162_hash_children(leaves[2], leaves[3])
    root = rfc9162_hash_children(n01, n23)
    assert verify_rfc9162_inclusion(n01, 0, 4, [n23], root) is False
    assert verify_rfc9162_inclusion(n23, 1, 4, [n01], root) is False
    rcpt = {"leaf_index": 0, "tree_size": 4, "root_hash": root.hex(), "leaf_hash": n01.hex(), "inclusion_proof": [n23.hex()]}
    assert verify_merkle_receipt(rcpt, pinned_root_bytes=root)["valid"] is False
    honest = dict(rcpt, leaf_hash=leaves[0].hex(), inclusion_proof=[leaves[1].hex(), n23.hex()])
    assert verify_merkle_receipt(honest, pinned_root_bytes=root)["valid"] is True


def test_self_rooted_merkle_receipt_without_pinned_root_rejected() -> None:
    leaf = rfc9162_hash_leaf(b"attacker claim")
    other = os.urandom(32)
    root = rfc9162_hash_children(leaf, other)
    rcpt = {"leaf_index": 0, "tree_size": 2, "root_hash": root.hex(), "leaf_hash": leaf.hex(), "inclusion_proof": [other.hex()]}
    res = verify_any_receipt(rcpt, None, None)
    assert res["valid"] is False
    assert res["root_pinned"] is False
    pinned = verify_any_receipt(rcpt, None, root)
    assert pinned["valid"] is True and pinned["root_pinned"] is True


def test_jcs_number_formatting_matches_ecmascript() -> None:
    vectors = {
        1e21: "1e+21",
        1e-7: "1e-7",
        0.000001: "0.000001",
        -0.0: "0",
        1e20: "100000000000000000000",
        5e-324: "5e-324",
        1.7976931348623157e308: "1.7976931348623157e+308",
        0.1 + 0.2: "0.30000000000000004",
        123e-20: "1.23e-18",
        -1.5e300: "-1.5e+300",
        333333333.33333329: "333333333.3333333",
        1.0: "1",
    }
    for num, expected in vectors.items():
        assert encode_jcs(num).decode() == expected, (num, expected)
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            encode_jcs(bad)


def test_jcs_utf16_code_unit_key_ordering() -> None:
    smile = chr(0x1F600)
    out = encode_jcs({smile: 1, chr(0xFFFF): 2, chr(0x20AC): 3, "\r": 4, "1": 5, chr(0xF6): 6})
    # UTF-16: U+1F600 -> D83D DE00 sorts before U+FFFF; code point order would differ.
    assert out.decode() == '{"\\r":4,"1":5,"\u00f6":6,"\u20ac":3,"' + smile + '":1,"\uffff":2}'


_JCS_VECTOR_DIR = _REPO_ROOT / "tests" / "data" / "jcs"


@pytest.mark.skipif(
    not (_JCS_VECTOR_DIR / "input").is_dir(),
    reason="cyberphone vectors (tests/data/jcs) not present in this checkout/shadow copy",
)
def test_jcs_cyberphone_vectors_byte_exact_and_reference_parity() -> None:
    """Byte-exact output on the cyberphone vectors used by test_jcs_cyberphone_conformance.py."""
    vector_files = sorted((_JCS_VECTOR_DIR / "input").glob("*.json"))
    assert len(vector_files) >= 6
    for in_path in vector_files:
        data = json.loads(in_path.read_text(encoding="utf-8"))
        expected = (_JCS_VECTOR_DIR / "output" / in_path.name).read_bytes()
        assert encode_jcs(data) == expected, in_path.name
        assert reference_encode_jcs(data) == expected, in_path.name


def test_jcs_differential_parity_with_reference_encoder() -> None:
    """0 divergences vs src.jcs_canonicalizer.encode_jcs on A1-style random + edge payloads."""
    payloads = [{"z": 1, "a": [1.5, "x", None]}]

    rng = random.Random(42)
    smile = chr(0x1F600)
    pool = ["a", "B", "z", "\u00e9", "e\u0301", chr(0x20AC), chr(0xFFFF), smile, chr(0x10000), "\x01", '"', "\\", "\u2028"]

    def rnd_str() -> str:
        return "".join(rng.choice(pool) for _ in range(rng.randint(0, 5)))

    def rnd_val(d: int = 0):
        t = rng.randint(0, 7 if d < 3 else 3)
        if t == 0:
            return rng.randint(-2**60, 2**60)
        if t == 1:
            return rng.choice([True, False, None])
        if t == 2:
            return rnd_str()
        if t == 3:
            return rng.choice([rng.uniform(-1e30, 1e30), rng.uniform(-1, 1) * 1e-8, float(rng.randint(0, 10**22)), rng.random()])
        if t in (4, 5):
            return [rnd_val(d + 1) for _ in range(rng.randint(0, 3))]
        return {rnd_str(): rnd_val(d + 1) for _ in range(rng.randint(0, 4))}

    payloads += [{"k": rnd_val()} for _ in range(300)]
    payloads += [{"f": 10.0 ** e} for e in range(-30, 31)] + [{"f": -(2.0 ** e)} for e in range(-80, 80, 7)]
    payloads += [{"a": 1e21}, {"a": 1e-7}, {"a": 5e-324}, {"a": -0.0}, {"a": 9007199254740993}]

    divergences = [p for p in payloads if encode_jcs(p) != reference_encode_jcs(p)]
    assert divergences == []
    assert compute_jcs_sha256(payloads[0]) == hashlib.sha256(reference_encode_jcs(payloads[0])).hexdigest()


# ------------------------------------------------------------------------------
# Mutation-adequacy follow-ups (targets surviving mutants in adjacent branches)
# ------------------------------------------------------------------------------

def test_merkle_receipt_pinned_root_mismatch_and_malformed_root_rejected() -> None:
    leaf0, leaf1 = rfc9162_hash_leaf(b"l0"), rfc9162_hash_leaf(b"l1")
    root = rfc9162_hash_children(leaf0, leaf1)
    rcpt = {"leaf_index": 0, "tree_size": 2, "root_hash": root.hex(), "leaf_hash": leaf0.hex(), "inclusion_proof": [leaf1.hex()]}
    mismatch = verify_merkle_receipt(rcpt, pinned_root_bytes=b"\x11" * 32)
    assert mismatch["valid"] is False
    assert "pinned root" in mismatch["error"]
    short_root = verify_merkle_receipt(dict(rcpt, root_hash=root.hex()[:62]), pinned_root_bytes=root)
    assert short_root["valid"] is False
    assert "root_hash" in short_root["error"]


def test_selective_disclosure_flat_signature_and_malformed_embedded_key() -> None:
    seed = b"sd_flat_signature_seed_32_bytes_"
    commits = {"a": compute_field_commitment("a", 1, "11" * 16)}
    root = compute_receipt_root(commits)
    pub, sig = ed25519_sign(seed, root.encode("utf-8"))
    rcpt = {
        "receipt_id": "sd-flat",
        "disclosed_claims": {"a": 1},
        "disclosed_salts": {"a": "11" * 16},
        "redacted_field_commitments": {},
        "root_hash": root,
        "signature": sig.hex(),
        "public_key_hex": pub.hex(),
    }
    assert verify_selective_disclosure_receipt(rcpt, pub)["valid"] is True
    bad_key = dict(rcpt, public_key_hex="zz" * 32)
    res = verify_selective_disclosure_receipt(bad_key, None, allow_embedded_key=True)
    assert res["valid"] is False
    assert "Malformed public_key_hex" in res["error"]


def test_attestation_signature_block_base64_signature_pinned() -> None:
    seed = b"attestation_block_seed_32_bytes_"
    pub, _ = ed25519_sign(seed, b"")
    body = {"operation_id": "op-att-1", "disposition": "CONFIRMED", "policy_epoch": 3}
    _, sig = ed25519_sign(seed, encode_jcs(body))
    rcpt = dict(body, attestation_signature={"signature_b64": base64.b64encode(sig).decode("ascii")})
    res = verify_aeib_execution_receipt(rcpt, pub)
    assert res["valid"] is True and res["key_pinned"] is True
    hex_rcpt = dict(body, attestation_signature={"signature_hex": sig.hex()})
    assert verify_aeib_execution_receipt(hex_rcpt, pub)["valid"] is True


def test_parse_public_key_pem_raw_and_malformed() -> None:
    raw = bytes(range(32))
    pem_raw = "-----BEGIN PUBLIC KEY-----\n" + base64.b64encode(raw).decode() + "\n-----END PUBLIC KEY-----\n"
    assert parse_ed25519_public_key(pem_raw) == raw
    pem_bad = "-----BEGIN PUBLIC KEY-----\n" + base64.b64encode(b"\x01" * 20).decode() + "\n-----END PUBLIC KEY-----\n"
    with pytest.raises(ValueError):
        parse_ed25519_public_key(pem_bad)


def test_bundle_directory_counts_and_pinning(tmp_path: Path) -> None:
    pub, rcpt = _signed_flat_receipt(b"bundle_pinning_seed_32_bytes____")
    (tmp_path / "a.json").write_text(json.dumps(rcpt), encoding="utf-8")
    (tmp_path / "b.jsonl").write_text(json.dumps(rcpt) + "\n" + json.dumps(rcpt) + "\n", encoding="utf-8")
    pinned = sov.verify_bundle_directory(tmp_path, trusted_pubkey_bytes=pub)
    assert pinned["valid"] is True
    assert pinned["total_receipts"] == 3 and pinned["valid_receipts"] == 3
    unpinned = sov.verify_bundle_directory(tmp_path)
    assert unpinned["valid"] is False
    assert unpinned["failed_receipts"] == 3
    opted = sov.verify_bundle_directory(tmp_path, allow_embedded_key=True)
    assert opted["valid"] is True and opted["total_receipts"] == 3


# ------------------------------------------------------------------------------
# Wave-6 hardening regressions (weak key loader, strict ingress, nesting cap,
# strict signature decoding, declared-algorithm check, coded errors)
# ------------------------------------------------------------------------------

def _w6_flat(seed: bytes = b"offline_w6_flat_receipt_seed_32b", **extra) -> tuple:
    pub, _ = ed25519_sign(seed, b"")
    body = {"operation_id": "op-w6", "disposition": "CONFIRMED", "policy_epoch": 1}
    body.update(extra)
    _, sig = ed25519_sign(seed, encode_jcs(body))
    return pub, sig, body


def test_w6_parse_public_key_rejects_weak_keys() -> None:
    for enc in _small_order_encodings():
        with pytest.raises(sov.WeakPublicKeyError) as info:
            parse_ed25519_public_key(enc.hex())
        assert info.value.code == "ERR_SMALL_ORDER_POINT"
    with pytest.raises(sov.WeakPublicKeyError) as info2:
        parse_ed25519_public_key((sov.FIELD_P + 1).to_bytes(32, "little"))
    assert info2.value.code == "ERR_NON_CANONICAL_POINT_ENCODING"
    off_curve = next(
        y.to_bytes(32, "little") for y in range(2, 200)
        if sov._recover_x(y, 0) is None
    )
    assert sov.ed25519_public_key_weakness(off_curve) == "ERR_POINT_NOT_ON_CURVE"
    neg_zero = bytearray((1).to_bytes(32, "little"))
    neg_zero[31] |= 0x80
    assert sov.ed25519_public_key_weakness(bytes(neg_zero)) == "ERR_NON_CANONICAL_POINT_ENCODING"
    assert sov.ed25519_public_key_weakness(b"\x00" * 31) == "ERR_POINT_ENCODING_LENGTH"
    pub, _, _ = _w6_flat()
    assert parse_ed25519_public_key(pub.hex()) == pub


def test_w6_pinned_weak_key_coded_rejection() -> None:
    _, _, body = _w6_flat()
    rcpt = dict(body, signature_hex=((1).to_bytes(32, "little") + bytes(32)).hex())
    res = verify_any_receipt(rcpt, (1).to_bytes(32, "little"))
    assert res["valid"] is False and res["error_code"] == sov.ERR_WEAK_PUBLIC_KEY
    commits = {"a": compute_field_commitment("a", 1, "11" * 16)}
    root = compute_receipt_root(commits)
    sd = {
        "receipt_id": "sd-weak", "disclosed_claims": {"a": 1}, "disclosed_salts": {"a": "11" * 16},
        "redacted_field_commitments": {}, "root_hash": root,
        "signature_b64": base64.b64encode((1).to_bytes(32, "little") + bytes(32)).decode(),
    }
    res_sd = verify_any_receipt(sd, (1).to_bytes(32, "little"))
    assert res_sd["valid"] is False and res_sd["error_code"] == sov.ERR_WEAK_PUBLIC_KEY


def test_w6_lenient_base64_signature_rejected() -> None:
    pub, sig, body = _w6_flat()
    good = dict(body, signature_b64=base64.b64encode(sig).decode())
    assert verify_any_receipt(good, pub)["valid"] is True
    bad = dict(body, signature_b64="!!" + base64.b64encode(sig).decode())
    res = verify_any_receipt(bad, pub)
    assert res["valid"] is False and res["error_code"] == "ERR_MALFORMED_RECEIPT"


@pytest.mark.parametrize("alg", ["none", "HS256", "ES256", "ed25519"])
def test_w6_declared_algorithm_confusion_rejected(alg: str) -> None:
    pub, sig, body = _w6_flat(alg=alg)
    res = verify_any_receipt(dict(body, signature_hex=sig.hex()), pub)
    assert res["valid"] is False and res["error_code"] == "ERR_UNSUPPORTED_ALGORITHM"
    pub2, sig2, body2 = _w6_flat(alg="Ed25519")
    assert verify_any_receipt(dict(body2, signature_hex=sig2.hex()), pub2)["valid"] is True
    nested = {"format": "x", "signature_metadata": {"algorithm": alg}}
    assert sov.declared_algorithm_violation(nested) == alg
    assert sov.declared_algorithm_violation({"signature_envelope": {"alg": "EdDSA"}}) is None


def test_w6_deep_nesting_rejected_with_code() -> None:
    pub, sig, body = _w6_flat()
    deep: list = []
    for _ in range(10_000):
        deep = [deep]
    res = verify_any_receipt(dict(body, signature_hex=sig.hex(), n=deep), pub)
    assert res["valid"] is False and res["error_code"] == sov.ERR_NESTING_TOO_DEEP
    within: list = [0]
    for _ in range(sov.MAX_JSON_DEPTH - 1):
        within = [within]
    assert sov.exceeds_max_depth(within) is False
    assert sov.exceeds_max_depth([within]) is True


def test_w6_malformed_receipt_coded_not_exception() -> None:
    pub, _, body = _w6_flat()
    res = verify_any_receipt(dict(body, signature_hex="zz" * 64), pub)
    assert res["valid"] is False and res["error_code"] == "ERR_MALFORMED_RECEIPT"
    res2 = verify_any_receipt([1, 2], pub)
    assert res2["valid"] is False and res2["error_code"] == "ERR_SCHEMA_INVALID"


def test_w6_strict_json_loader_codes() -> None:
    with pytest.raises(sov.StrictIngressError) as e1:
        sov.loads_strict_json('{"a":1,"a":2}')
    assert e1.value.code == sov.ERR_DUPLICATE_KEY
    for lit in ("NaN", "-Infinity", "1e999"):
        with pytest.raises(sov.StrictIngressError) as e2:
            sov.loads_strict_json("[%s]" % lit)
        assert e2.value.code == sov.ERR_NON_FINITE_NUMBER
    with pytest.raises(sov.StrictIngressError) as e3:
        sov.loads_strict_json("[" * 10_000 + "]" * 10_000)
    assert e3.value.code == sov.ERR_NESTING_TOO_DEEP
    with pytest.raises(sov.StrictIngressError) as e4:
        sov.loads_strict_json("{bad")
    assert e4.value.code == sov.ERR_INVALID_JSON
    assert sov.loads_strict_json(b'{"a":0.5}') == {"a": 0.5}


def test_w6_cli_duplicate_key_and_deep_receipt_rejected(tmp_path: Path) -> None:
    pub, sig, body = _w6_flat()
    text = json.dumps(dict(body, signature_hex=sig.hex()))
    path = tmp_path / "r.json"
    script = str(_REPO_ROOT / "tools" / "standalone_offline_verifier.py")
    base = [sys.executable, script, "--verify-receipt", str(path), "--public-key", pub.hex(), "--json"]
    path.write_text(text)
    ok = subprocess.run(base, capture_output=True, text=True, timeout=120, check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    path.write_text('{"operation_id":"op-EVIL",' + text[1:])
    dup = subprocess.run(base, capture_output=True, text=True, timeout=120, check=False)
    assert dup.returncode == 2
    assert json.loads(dup.stdout)["error_code"] == sov.ERR_DUPLICATE_KEY
    path.write_text(text[:-1] + ',"n":' + "[" * 10_000 + "]" * 10_000 + "}")
    deep = subprocess.run(base, capture_output=True, text=True, timeout=120, check=False)
    assert deep.returncode == 2 and "Traceback" not in deep.stderr
    assert json.loads(deep.stdout)["error_code"] == sov.ERR_NESTING_TOO_DEEP


def test_w6_bundle_strict_ingress_failures_are_coded(tmp_path: Path) -> None:
    pub, sig, body = _w6_flat()
    text = json.dumps(dict(body, signature_hex=sig.hex()))
    (tmp_path / "good.json").write_text(text)
    (tmp_path / "dup.json").write_text('{"operation_id":"x",' + text[1:])
    res = sov.verify_bundle_directory(tmp_path, trusted_pubkey_bytes=pub)
    assert res["valid"] is False and res["total_receipts"] == 2 and res["valid_receipts"] == 1
    assert [f["error_code"] for f in res["failures"]] == [sov.ERR_DUPLICATE_KEY]


def test_w6_selective_disclosure_wrong_signature_coded() -> None:
    seed = b"sd_wrong_signature_seed_32_bytes"
    commits = {"a": compute_field_commitment("a", 1, "11" * 16)}
    root = compute_receipt_root(commits)
    pub, sig = ed25519_sign(seed, b"different message")
    sd = {
        "receipt_id": "sd-wrong", "disclosed_claims": {"a": 1}, "disclosed_salts": {"a": "11" * 16},
        "redacted_field_commitments": {}, "root_hash": root, "signature": sig.hex(),
    }
    res = verify_selective_disclosure_receipt(sd, pub)
    assert res["valid"] is False and res["error_code"] == "ERR_INVALID_SIGNATURE"


def test_w6_merkle_sibling_validation_and_derived_leaf() -> None:
    action_id, intent, verdict = "act-1", bytes(range(32)), "ALLOW"
    leaf = rfc9162_hash_leaf(action_id.encode() + intent + verdict.encode())
    other = rfc9162_hash_leaf(b"other")
    root = rfc9162_hash_children(leaf, other)
    rcpt = {"leaf_index": 0, "tree_size": 2, "root_hash": root.hex(), "inclusion_proof": [other.hex()],
            "action_id": action_id, "intent_digest": intent.hex(), "verdict": verdict}
    assert verify_merkle_receipt(rcpt, pinned_root_bytes=root)["valid"] is True
    assert verify_merkle_receipt(dict(rcpt, verdict="DENY"), pinned_root_bytes=root)["valid"] is False
    short = verify_merkle_receipt(dict(rcpt, inclusion_proof=["ab" * 31]), pinned_root_bytes=root)
    assert short["valid"] is False and "32 bytes" in short["error"]
    bad_hex = verify_merkle_receipt(dict(rcpt, inclusion_proof=["zz"]), pinned_root_bytes=root)
    assert bad_hex["valid"] is False and "Malformed sibling" in bad_hex["error"]


def test_w6_parse_public_key_base64_spki() -> None:
    pub, _ = ed25519_sign(b"spki_base64_parse_seed_32_bytes_", b"")
    spki = bytes.fromhex("302a300506032b6570032100") + pub
    assert parse_ed25519_public_key(base64.b64encode(spki).decode()) == pub
    assert parse_ed25519_public_key(base64.b64encode(pub).decode()) == pub


def test_w6_cli_bundle_exit_codes(tmp_path: Path) -> None:
    script = str(_REPO_ROOT / "tools" / "standalone_offline_verifier.py")
    pub, sig, body = _w6_flat()
    good_dir = tmp_path / "good"
    good_dir.mkdir()
    (good_dir / "r.json").write_text(json.dumps(dict(body, signature_hex=sig.hex())))
    base = [sys.executable, script, "--public-key", pub.hex()]
    ok = subprocess.run(base + ["--verify-bundle", str(good_dir)], capture_output=True, text=True, timeout=120, check=False)
    assert ok.returncode == 0, ok.stderr
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "r.json").write_text(json.dumps(dict(body, signature_hex=("00" * 64))))
    bad = subprocess.run(base + ["--verify-bundle", str(bad_dir)], capture_output=True, text=True, timeout=120, check=False)
    assert bad.returncode == 1
    missing = subprocess.run(base + ["--verify-bundle", str(tmp_path / "nope")], capture_output=True, text=True, timeout=120, check=False)
    assert missing.returncode == 2
    bad_root = subprocess.run(base + ["--verify-bundle", str(good_dir), "--pinned-root", "abcd"],
                              capture_output=True, text=True, timeout=120, check=False)
    assert bad_root.returncode == 2
