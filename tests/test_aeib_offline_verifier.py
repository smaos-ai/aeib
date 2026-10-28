#!/usr/bin/env python3
"""
tests/test_aeib_offline_verifier.py
================================================================================
Wave-6 hardening regressions for tools/aeib_offline_verifier.py:
  * small-order / non-canonical trust anchors (constructor + PEM loader + CLI)
  * small-order signature R component
  * strict JSON ingress at the CLI (duplicate keys, NaN/Infinity)
  * nesting cap before canonicalization (API + CLI), never a traceback
  * malformed input yields a coded result

Real Ed25519 keys via `cryptography`; CLI runs in a subprocess with a timeout.
"""

from __future__ import annotations

import base64
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, List

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

import tools.aeib_offline_verifier as A

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = str(REPO_ROOT / "tools" / "aeib_offline_verifier.py")
KID = "aeib-test-kid"
SK = Ed25519PrivateKey.from_private_bytes(b"aeib-offline-verifier-test-seed!")
L_ORDER = 2**252 + 27742317777372353535851937790883648493


def _small_order_points() -> List[bytes]:
    """Derives the 8 torsion points as L * P using the module's own point arithmetic."""
    found = set()
    y = 2
    while len(found) < 8 and y < 400:
        enc = y.to_bytes(32, "little")
        if A.ed25519_point_weakness(enc) in (None, A.ERR_SMALL_ORDER_POINT):
            pt = _decode(enc)
            if pt is not None:
                found.add(_encode(_mul(L_ORDER, pt)))
        y += 1
    return sorted(found)


def _decode(enc: bytes):
    p = A._ED_P
    y = int.from_bytes(enc[:31] + bytes([enc[31] & 0x7F]), "little")
    u = (y * y - 1) % p
    v = (A._ED_D * y * y + 1) % p
    x = (u * pow(v, 3, p) * pow(u * pow(v, 7, p), (p - 5) // 8, p)) % p
    if (v * x * x) % p == (-u) % p:
        x = (x * A._ED_SQRT_M1) % p
    elif (v * x * x) % p != u:
        return None
    return (x, y, 1, (x * y) % p)


def _mul(k: int, pt):
    acc = A._ED_IDENTITY
    while k:
        if k & 1:
            acc = A._ed_point_add(acc, pt)
        pt = A._ed_point_add(pt, pt)
        k >>= 1
    return acc


def _encode(pt) -> bytes:
    p = A._ED_P
    x, y, z, _ = pt
    zi = pow(z, p - 2, p)
    ax, ay = (x * zi) % p, (y * zi) % p
    raw = bytearray(ay.to_bytes(32, "little"))
    if ax & 1:
        raw[31] |= 0x80
    return bytes(raw)


SMALL_ORDER = _small_order_points()


def _bundle(entries):
    return A.build_manifest(entries), entries


def _verify(entries, anchors=None):
    manifest, ents = _bundle(entries)
    verifier = A.StandaloneOfflineVerifier(anchors or {KID: SK.public_key()})
    return verifier.verify_bundle(manifest, ents, [e["operation_id"] for e in ents if isinstance(e, dict)])


def _resign_with_sig(entry, sig: bytes):
    entry["signature_b64"] = base64.b64encode(sig).decode("ascii")
    return entry


def test_small_order_corpus_has_eight_points() -> None:
    assert len(SMALL_ORDER) == 8
    assert (1).to_bytes(32, "little") in SMALL_ORDER


def test_genuine_bundle_still_verifies() -> None:
    e1 = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    e2 = A.build_signed_entry(2, "op-2", e1["entry_hash"], KID, SK)
    res = _verify([e1, e2])
    assert res.valid is True and res.error_code is None


@pytest.mark.parametrize("weak", SMALL_ORDER, ids=[w.hex()[:8] for w in SMALL_ORDER])
def test_small_order_trust_anchor_forgery_rejected(weak: bytes) -> None:
    entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    _resign_with_sig(entry, (1).to_bytes(32, "little") + bytes(32))
    anchors = {KID: Ed25519PublicKey.from_public_bytes(weak)}
    verifier = A.StandaloneOfflineVerifier(anchors)
    assert KID in verifier.weak_anchor_codes
    res = _verify([entry], anchors)
    assert res.valid is False
    assert res.error_code == "ERR_WEAK_TRUST_ANCHOR_KEY"


def test_non_canonical_and_non_ed25519_anchor_codes() -> None:
    p = A._ED_P
    assert A.ed25519_point_weakness((p + 1).to_bytes(32, "little")) == A.ERR_NON_CANONICAL_POINT
    neg_zero = bytearray((1).to_bytes(32, "little"))
    neg_zero[31] |= 0x80
    assert A.ed25519_point_weakness(bytes(neg_zero)) == A.ERR_NON_CANONICAL_POINT
    assert A.ed25519_point_weakness(b"\x01" * 31) == A.ERR_POINT_ENCODING_LENGTH
    assert A.trust_anchor_weakness("not-a-key") == A.ERR_POINT_ENCODING_LENGTH
    assert A.trust_anchor_weakness(SK.public_key()) is None
    off_curve = next(
        y.to_bytes(32, "little") for y in range(2, 200)
        if A.ed25519_point_weakness(y.to_bytes(32, "little")) == A.ERR_POINT_NOT_ON_CURVE
    )
    assert A.ed25519_point_weakness(off_curve) == A.ERR_POINT_NOT_ON_CURVE


def test_signature_screen_rejects_small_order_r_and_non_canonical_s() -> None:
    assert A.ed25519_signature_weakness(b"\x00" * 63) == A.ERR_SIGNATURE_LENGTH
    assert A.ed25519_signature_weakness((1).to_bytes(32, "little") + bytes(32)) == A.ERR_SMALL_ORDER_POINT
    genuine = SK.sign(b"m")
    assert A.ed25519_signature_weakness(genuine) is None
    s_val = int.from_bytes(genuine[32:], "little") + L_ORDER
    assert A.ed25519_signature_weakness(genuine[:32] + s_val.to_bytes(32, "little")) == A.ERR_NON_CANONICAL_SCALAR


def test_small_order_r_under_genuine_anchor_rejected() -> None:
    for r_enc in SMALL_ORDER:
        entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
        _resign_with_sig(entry, r_enc + bytes(32))
        res = _verify([entry])
        assert res.valid is False and res.error_code == "ERR_INVALID_SIGNATURE"


def test_deep_nested_field_rejected_with_code_not_exception() -> None:
    entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    deep: Any = []
    for _ in range(10_000):
        deep = [deep]
    entry["n"] = deep
    res = _verify([entry])
    assert res.valid is False and res.error_code == "ERR_INPUT_NESTING_TOO_DEEP"
    assert res.failed_seq == 1


def test_deep_manifest_rejected_and_cap_boundary() -> None:
    entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    manifest = A.build_manifest([entry])
    nested: Any = 0
    for _ in range(A.MAX_JSON_DEPTH):
        nested = [nested]
    assert A.exceeds_max_depth(nested) is False
    assert A.exceeds_max_depth([nested]) is True
    assert A.exceeds_max_depth({"a": nested}) is True
    deep_manifest = dict(manifest, extra=[nested])
    res = A.StandaloneOfflineVerifier({KID: SK.public_key()}).verify_bundle(deep_manifest, [entry], ["op-1"])
    assert res.error_code == "ERR_INPUT_NESTING_TOO_DEEP"


def test_malformed_input_yields_code() -> None:
    entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    manifest = A.build_manifest([entry])
    res = A.StandaloneOfflineVerifier({KID: SK.public_key()}).verify_bundle(manifest, [entry], [["unhashable"]])
    assert res.valid is False and res.error_code == "ERR_MALFORMED_INPUT"


def _write_bundle(tmp_path: Path, ledger_text: str, pub=None) -> List[str]:
    entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    (tmp_path / "m.json").write_text(json.dumps(A.build_manifest([entry])), encoding="utf-8")
    (tmp_path / "l.jsonl").write_text(ledger_text, encoding="utf-8")
    key = pub or SK.public_key()
    (tmp_path / "k.pem").write_bytes(
        key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    return [sys.executable, SCRIPT, "--manifest", str(tmp_path / "m.json"), "--ledger", str(tmp_path / "l.jsonl"),
            "--anchor", f"{KID}={tmp_path / 'k.pem'}"]


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(REPO_ROOT), check=False)


def test_cli_genuine_ledger_valid(tmp_path: Path) -> None:
    entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    proc = _run(_write_bundle(tmp_path, json.dumps(entry) + "\n"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["valid"] is True


def test_cli_duplicate_key_rejected(tmp_path: Path) -> None:
    entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    dup = '{"operation_id":"op-EVIL",' + json.dumps(entry)[1:]
    proc = _run(_write_bundle(tmp_path, dup + "\n"))
    assert proc.returncode == 2
    out = json.loads(proc.stdout)
    assert out == {"valid": False, "error_code": "ERR_DUPLICATE_KEY", "failed_seq": 1}


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "1e400"])
def test_cli_non_finite_rejected(tmp_path: Path, literal: str) -> None:
    entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    line = json.dumps(entry)[:-1] + f',"x":{literal}}}'
    proc = _run(_write_bundle(tmp_path, line + "\n"))
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["error_code"] == "ERR_NON_FINITE_NUMBER"


def test_cli_deep_nesting_rejected_without_traceback(tmp_path: Path) -> None:
    entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    line = json.dumps(entry)[:-1] + ',"n":' + "[" * 10_000 + "]" * 10_000 + "}"
    proc = _run(_write_bundle(tmp_path, line + "\n"))
    assert "Traceback" not in proc.stderr
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["error_code"] == "ERR_INPUT_NESTING_TOO_DEEP"


def test_cli_manifest_duplicate_key_rejected(tmp_path: Path) -> None:
    entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    cmd = _write_bundle(tmp_path, json.dumps(entry) + "\n")
    manifest_text = (tmp_path / "m.json").read_text(encoding="utf-8")
    (tmp_path / "m.json").write_text('{"entry_count":99,' + manifest_text[1:], encoding="utf-8")
    proc = _run(cmd)
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["error_code"] == "ERR_MANIFEST_DUPLICATE_KEY"


def test_cli_and_loader_reject_small_order_pem(tmp_path: Path) -> None:
    ident = Ed25519PublicKey.from_public_bytes((1).to_bytes(32, "little"))
    entry = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    cmd = _write_bundle(tmp_path, json.dumps(entry) + "\n", pub=ident)
    with pytest.raises(A.WeakTrustAnchorError) as info:
        A._load_pem_public_key(tmp_path / "k.pem")
    assert info.value.code == A.ERR_SMALL_ORDER_POINT
    proc = _run(cmd)
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["error_code"] == "ERR_WEAK_TRUST_ANCHOR_KEY"


# ------------------------------------------------------------------------------
# Schema / input-validation branches (mutation-adequacy follow-ups)
# ------------------------------------------------------------------------------

def test_canonical_helpers_and_constant_time_compare() -> None:
    sample = {"b": [1, 2.5], "a": "x"}
    assert A.canonical_jcs_bytes(sample) == A.encode_jcs(sample) == b'{"a":"x","b":[1,2.5]}'
    assert A.ct_str_eq("abc", "abc") is True
    assert A.ct_str_eq("abc", "abd") is False
    assert A.ct_str_eq(1, 1) is False
    assert A.ct_str_eq("1", 1) is False


@pytest.mark.parametrize("drift", [-1, True, "5", 1.5])
def test_constructor_rejects_invalid_drift(drift: Any) -> None:
    with pytest.raises(ValueError):
        A.StandaloneOfflineVerifier({KID: SK.public_key()}, max_clock_drift_ms=drift)
    assert A.StandaloneOfflineVerifier({KID: SK.public_key()}, max_clock_drift_ms=0).max_clock_drift_ms == 0


def test_schema_branch_codes() -> None:
    verifier = A.StandaloneOfflineVerifier({KID: SK.public_key()})
    e1 = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    manifest = A.build_manifest([e1])
    assert verifier.verify_bundle(manifest, [], ["op-1"]).error_code == "ERR_EMPTY_LEDGER"
    assert verifier.verify_bundle("not-a-dict", [e1], ["op-1"]).error_code == "ERR_MANIFEST_MALFORMED"

    one_manifest = dict(manifest)
    res = verifier.verify_bundle(one_manifest, ["not-an-entry"], ["op-1"])
    assert res.valid is False
    assert (res.error_code, res.failed_seq) == ("ERR_ENTRY_MALFORMED", 1)

    bad_seq = A.build_signed_entry(5, "op-1", A.GENESIS_PREV_HASH, KID, SK)
    res = verifier.verify_bundle(A.build_manifest([bad_seq]), [bad_seq], ["op-1"])
    assert res.valid is False
    assert (res.error_code, res.failed_seq) == ("ERR_NON_MONOTONIC_SEQ", 1)

    bad_schema = copy.deepcopy(e1)
    bad_schema["schema_version"] = "aeib.receipt.v0"
    res = verifier.verify_bundle(manifest, [bad_schema], ["op-1"])
    assert res.valid is False
    assert (res.error_code, res.failed_seq) == ("ERR_UNSUPPORTED_SCHEMA_VERSION", 1)

    negative_amount = A.build_signed_entry(1, "op-1", A.GENESIS_PREV_HASH, KID, SK, amount_minor=-5)
    res = verifier.verify_bundle(A.build_manifest([negative_amount]), [negative_amount], ["op-1"])
    assert res.valid is False
    assert (res.error_code, res.failed_seq) == ("ERR_INCOMPLETE_ACTION_BINDING", 1)

    no_binding = copy.deepcopy(e1)
    del no_binding["action_binding"]["target"]
    body = {k: v for k, v in no_binding.items() if k not in A.UNSIGNED_EXCLUDED_KEYS}
    canonical = A.canonical_json_v1(body)
    no_binding["entry_hash"] = A.sha256_prefixed(canonical)
    no_binding["signature_b64"] = base64.b64encode(SK.sign(canonical)).decode("ascii")
    res = verifier.verify_bundle(A.build_manifest([no_binding]), [no_binding], ["op-1"])
    assert res.valid is False
    assert res.error_code == "ERR_INCOMPLETE_ACTION_BINDING"


def test_negative_vector_suite_matches_expected_codes() -> None:
    results = A.run_negative_vector_suite()
    assert set(results) == set(A.EXPECTED_VECTOR_CODES)
    for name, expected in A.EXPECTED_VECTOR_CODES.items():
        assert results[name].error_code == expected, name
        assert results[name].valid is (expected is None), name
    assert results["NEG_6_BROKEN_CHAIN"].failed_seq == 2
