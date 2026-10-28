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
    """Verifies that encode_jcs enforces RFC 8785 UTF-16 code unit key sorting and ECMAScript numbers."""
    sample = {
        "z": 1,
        "a": 2,
        "\u00e9": 3,
        "A": 4,
        "nested": {"b": True, "a": None, "c": 45.5},
        "zero": 0.0,
        "neg_zero": -0.0,
    }
    encoded = encode_jcs(sample)
    decoded = json.loads(encoded.decode("utf-8"))
    assert decoded["z"] == 1
    assert decoded["nested"]["c"] == 45.5
    assert decoded["zero"] == 0
    assert decoded["neg_zero"] == 0
    assert b"\"A\":4" in encoded
    assert b"\"a\":2" in encoded
    assert b"\"neg_zero\":0" in encoded
    assert b"\"zero\":0" in encoded


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


# ==============================================================================
# Wave-6 hardening regressions (F1 small-order keys, F2 strict JSON, F3 nesting,
# F4 alg / base64 / gate_signature / Format D / ledger completeness)
# ==============================================================================

import tools.standalone_receipt_verifier as S
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = str(_REPO / "tools" / "standalone_receipt_verifier.py")
_W6_SK = Ed25519PrivateKey.from_private_bytes(b"receipt-verifier-wave6-seed-32b!")
_W6_PK = _W6_SK.public_key()
_NOW = 1_760_000_000
_L = 2**252 + 27742317777372353535851937790883648493


def _w6_body(**extra):
    payload = {"intent": "refund", "amount": 2500}
    body = {
        "operation_id": "op-w6-1",
        "disposition": "CONFIRMED",
        "alg": "Ed25519",
        "action_payload": payload,
        "action_caid": compute_sha256_prefixed(encode_jcs(payload)),
        "timestamp_epoch": _NOW,
    }
    body.update(extra)
    return body


def _w6_sign(body, sk=_W6_SK):
    out = dict(body)
    out["signature_b64"] = base64.b64encode(sk.sign(encode_jcs(body))).decode("ascii")
    return out


def _w6_verify(rcpt, key=_W6_PK, **kw):
    return verify_receipt_data(rcpt, trusted_public_key=key, current_time_epoch=_NOW, **kw)


def _w6_small_order_points():
    found = set()
    p = S._ED_P
    for y in range(2, 400):
        if len(found) == 8:
            break
        enc = y.to_bytes(32, "little")
        if S.ed25519_point_weakness(enc) == S.ERR_POINT_NOT_ON_CURVE:
            continue
        u = (y * y - 1) % p
        v = (S._ED_D * y * y + 1) % p
        x = (u * pow(v, 3, p) * pow(u * pow(v, 7, p), (p - 5) // 8, p)) % p
        if (v * x * x) % p != u:
            x = (x * S._ED_SQRT_M1) % p
        acc, pt, k = S._ED_IDENTITY, (x, y, 1, (x * y) % p), _L
        while k:
            if k & 1:
                acc = S._ed_point_add(acc, pt)
            pt = S._ed_point_add(pt, pt)
            k >>= 1
        zi = pow(acc[2], p - 2, p)
        ax, ay = (acc[0] * zi) % p, (acc[1] * zi) % p
        raw = bytearray(ay.to_bytes(32, "little"))
        if ax & 1:
            raw[31] |= 0x80
        found.add(bytes(raw))
    return sorted(found)


_W6_SMALL_ORDER = _w6_small_order_points()


def test_w6_small_order_corpus() -> None:
    assert len(_W6_SMALL_ORDER) == 8


@pytest.mark.parametrize("weak", _W6_SMALL_ORDER, ids=[w.hex()[:8] for w in _W6_SMALL_ORDER])
def test_w6_loader_rejects_small_order_keys_all_formats(weak: bytes, tmp_path: Path) -> None:
    for source in (weak.hex(), base64.b64encode(weak).decode(), weak):
        with pytest.raises(S.WeakPublicKeyError) as info:
            load_ed25519_public_key(source)
        assert info.value.code == S.ERR_SMALL_ORDER_POINT
    pem = Ed25519PublicKey.from_public_bytes(weak).public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    pem_file = tmp_path / "weak.pem"
    pem_file.write_bytes(pem)
    with pytest.raises(S.WeakPublicKeyError):
        load_ed25519_public_key(pem_file)


def test_w6_loader_rejects_non_canonical_encodings_and_accepts_genuine() -> None:
    p = S._ED_P
    with pytest.raises(S.WeakPublicKeyError) as info:
        load_ed25519_public_key((p + 1).to_bytes(32, "little").hex())
    assert info.value.code == S.ERR_NON_CANONICAL_POINT
    neg_zero = bytearray((1).to_bytes(32, "little"))
    neg_zero[31] |= 0x80
    assert S.ed25519_point_weakness(bytes(neg_zero)) == S.ERR_NON_CANONICAL_POINT
    raw = _W6_PK.public_bytes_raw()
    assert load_ed25519_public_key(raw.hex()).public_bytes_raw() == raw
    assert load_ed25519_public_key(base64.b64encode(raw).decode()).public_bytes_raw() == raw
    assert S.public_key_weakness("not a key") == S.ERR_POINT_ENCODING_LENGTH


@pytest.mark.parametrize("weak", _W6_SMALL_ORDER, ids=[w.hex()[:8] for w in _W6_SMALL_ORDER])
def test_w6_pinned_small_order_key_forgery_rejected(weak: bytes) -> None:
    forged = dict(_w6_body())
    forged["signature_b64"] = base64.b64encode((1).to_bytes(32, "little") + bytes(32)).decode()
    res = _w6_verify(forged, key=Ed25519PublicKey.from_public_bytes(weak))
    assert res["valid"] is False
    assert res["failure_code"] == S.CODE_NEG_09


def test_w6_small_order_r_and_s_plus_l_rejected() -> None:
    genuine = _w6_sign(_w6_body())
    assert _w6_verify(genuine)["valid"] is True
    sig = base64.b64decode(genuine["signature_b64"])
    for r_enc in _W6_SMALL_ORDER:
        bad = dict(genuine, signature_b64=base64.b64encode(r_enc + sig[32:]).decode())
        res = _w6_verify(bad)
        assert res["valid"] is False and res["failure_code"] == CODE_NEG_02
        assert "Signature rejected before verification" in res["error"]
    s_val = int.from_bytes(sig[32:], "little") + _L
    mall = dict(genuine, signature_b64=base64.b64encode(sig[:32] + s_val.to_bytes(32, "little")).decode())
    res = _w6_verify(mall)
    assert res["valid"] is False and S.ERR_NON_CANONICAL_SCALAR in res["error"]


def test_w6_lenient_base64_signature_rejected() -> None:
    genuine = _w6_sign(_w6_body())
    for junk in ("!!" + genuine["signature_b64"], genuine["signature_b64"] + "\n", " " + genuine["signature_b64"]):
        res = _w6_verify(dict(genuine, signature_b64=junk))
        assert res["valid"] is False and res["failure_code"] == CODE_NEG_03


def test_w6_missing_alg_rejected_unless_opted_in() -> None:
    body = _w6_body()
    del body["alg"]
    rcpt = _w6_sign(body)
    res = _w6_verify(rcpt)
    assert res["valid"] is False and res["failure_code"] == CODE_NEG_07
    assert "allow_missing_alg" in res["error"]
    assert _w6_verify(rcpt, allow_missing_alg=True)["valid"] is True


def test_w6_unsigned_gate_signature_cannot_ride_along() -> None:
    genuine = _w6_sign(_w6_body())
    smuggled = dict(genuine, gate_signature={"approved_by": "ciso", "amount_override": 10**9})
    res = _w6_verify(smuggled)
    assert res["valid"] is False and res["failure_code"] == CODE_NEG_02
    signed_with_gate = _w6_sign(_w6_body(gate_signature={"approved_by": "ciso"}))
    assert _w6_verify(signed_with_gate)["valid"] is True


def _w6_format_d(outer_op: str, stmt: dict, sk=_W6_SK, **outer):
    raw = json.dumps(stmt).encode()
    rcpt = {
        "operation_id": outer_op,
        "alg": "Ed25519",
        "signedStatement": base64.b64encode(raw).decode(),
        "signature": {"ed25519Signature": base64.b64encode(sk.sign(raw)).decode()},
    }
    rcpt.update(outer)
    return rcpt


def test_w6_format_d_reports_only_signed_fields() -> None:
    ok = _w6_verify(_w6_format_d("op-1", {"operation_id": "op-1", "disposition": "REFUTED"}))
    assert ok["valid"] is True and ok["operation_id"] == "op-1" and ok["disposition"] == "REFUTED"
    assert ok["receipt_sha256"].startswith("sha256:")

    attacker = _w6_verify(_w6_format_d("op-ATTACKER", {"operation_id": "op-1", "disposition": "CONFIRMED"}))
    assert attacker["valid"] is False and attacker["failure_code"] == CODE_NEG_03
    assert attacker["operation_id"] == "op-1"

    disp = _w6_verify(_w6_format_d("op-1", {"operation_id": "op-1", "disposition": "REFUTED"}, disposition="CONFIRMED"))
    assert disp["valid"] is False and disp["failure_code"] == CODE_NEG_03

    no_op = _w6_verify(_w6_format_d("op-1", {"disposition": "CONFIRMED"}))
    assert no_op["valid"] is False and no_op["failure_code"] == CODE_NEG_03

    expected = verify_receipt_data(
        _w6_format_d("op-1", {"operation_id": "op-1"}), trusted_public_key=_W6_PK, expected_operation_id="op-2"
    )
    assert expected["valid"] is False and expected["failure_code"] == CODE_NEG_03

    dup_stmt = _w6_format_d("op-1", {"operation_id": "op-1"})
    raw = b'{"operation_id":"op-1","operation_id":"op-1"}'
    dup_stmt["signedStatement"] = base64.b64encode(raw).decode()
    dup_stmt["signature"] = {"ed25519Signature": base64.b64encode(_W6_SK.sign(raw)).decode()}
    dup = _w6_verify(dup_stmt)
    assert dup["valid"] is False and dup["failure_code"] == S.CODE_NEG_10

    weak = _w6_verify(_w6_format_d("op-1", {"operation_id": "op-1"}),
                      key=Ed25519PublicKey.from_public_bytes((1).to_bytes(32, "little")))
    assert weak["valid"] is False and weak["failure_code"] == S.CODE_NEG_09


def test_w6_deep_nesting_rejected_with_code() -> None:
    deep = []
    for _ in range(10_000):
        deep = [deep]
    res = _w6_verify(dict(_w6_sign(_w6_body()), n=deep))
    assert res["valid"] is False and res["failure_code"] == S.CODE_NEG_10


def test_w6_malformed_input_yields_code_not_exception() -> None:
    res = _w6_verify(dict(_w6_sign(_w6_body()), disposition=["CONFIRMED"]))
    assert res["valid"] is False and res["failure_code"] == CODE_NEG_03


def _w6_ledger(n: int):
    tip = "sha256:" + "0" * 64
    lines = []
    for i in range(n):
        entry = _w6_sign(_w6_body(operation_id=f"op-led-{i}", prev_chain_tip=tip))
        tip = compute_sha256_prefixed(encode_jcs({k: v for k, v in entry.items() if k != "signature_b64"}))
        lines.append(json.dumps(entry))
    return lines, tip


def test_w6_ledger_requires_completeness_anchor() -> None:
    lines, tip = _w6_ledger(3)
    res = verify_ledger_stream(lines, _W6_PK)
    assert res["valid"] is False and res["failure_code"] == S.CODE_NO_COMPLETENESS_ANCHOR

    opted = verify_ledger_stream(lines, _W6_PK, allow_unanchored=True)
    assert opted["valid"] is True and opted["complete"] is False
    assert opted["warning_code"] == S.WARN_LEDGER_UNANCHORED

    by_count = verify_ledger_stream(lines, _W6_PK, expected_entry_count=3)
    assert by_count["valid"] is True and by_count["complete"] is True and "warning_code" not in by_count
    by_tip = verify_ledger_stream(lines, _W6_PK, expected_final_tip=tip)
    assert by_tip["valid"] is True and by_tip["complete"] is True


def test_w6_tail_truncated_ledger_rejected_with_anchor() -> None:
    lines, tip = _w6_ledger(3)
    truncated = lines[:2]
    res = verify_ledger_stream(truncated, _W6_PK, expected_entry_count=3)
    assert res["valid"] is False and res["failure_code"] == S.CODE_NEG_08
    res_tip = verify_ledger_stream(truncated, _W6_PK, expected_final_tip=tip)
    assert res_tip["valid"] is False and res_tip["failure_code"] == S.CODE_NEG_08
    extended = verify_ledger_stream(lines, _W6_PK, expected_entry_count=2)
    assert extended["valid"] is False and extended["failure_code"] == S.CODE_NEG_08


def test_w6_ledger_strict_lines() -> None:
    lines, _ = _w6_ledger(1)
    dup = '{"operation_id":"op-EVIL",' + lines[0][1:]
    res = verify_ledger_stream([dup], _W6_PK, expected_entry_count=1)
    assert res["valid"] is False and res["failure_code"] == S.CODE_NEG_10
    res_list = verify_ledger_stream(["[1,2]"], _W6_PK, expected_entry_count=1)
    assert res_list["valid"] is False and res_list["failure_code"] == CODE_NEG_03
    res_bad = verify_ledger_stream(["{not json"], _W6_PK, expected_entry_count=1)
    assert res_bad["valid"] is False and res_bad["failure_code"] == CODE_NEG_03
    deep = lines[0][:-1] + ',"n":' + "[" * 10_000 + "]" * 10_000 + "}"
    res_deep = verify_ledger_stream([deep], _W6_PK, expected_entry_count=1)
    assert res_deep["valid"] is False and res_deep["failure_code"] == S.CODE_NEG_10


def test_w6_strict_loader_codes() -> None:
    with pytest.raises(S.StrictIngressError) as e1:
        S.loads_strict_json('{"a":1,"a":2}')
    assert e1.value.code == S.ERR_DUPLICATE_KEY
    for lit in ("NaN", "Infinity", "-Infinity", "1e400"):
        with pytest.raises(S.StrictIngressError) as e2:
            S.loads_strict_json('{"a":%s}' % lit)
        assert e2.value.code == S.ERR_NON_FINITE_NUMBER
    with pytest.raises(S.StrictIngressError) as e3:
        S.loads_strict_json(b"\xff\xfe")
    assert e3.value.code == S.ERR_INVALID_JSON
    nested = "[" * S.MAX_JSON_DEPTH + "]" * S.MAX_JSON_DEPTH
    assert S.loads_strict_json(nested) is not None
    with pytest.raises(S.StrictIngressError) as e4:
        S.loads_strict_json("[" + nested + "]")
    assert e4.value.code == S.ERR_NESTING_TOO_DEEP
    assert S.loads_strict_json('{"a":[1.5,2]}') == {"a": [1.5, 2]}


def _w6_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    kf = tmp_path / "k.hex"
    kf.write_text(_W6_PK.public_bytes_raw().hex())
    return subprocess.run([sys.executable, _SCRIPT, "--public-key", str(kf), *args],
                          capture_output=True, text=True, timeout=120, cwd=str(_REPO), check=False)


def test_w6_cli_duplicate_key_and_deep_receipt_rejected(tmp_path: Path) -> None:
    genuine = json.dumps(_w6_sign(_w6_body()))
    rf = tmp_path / "r.json"
    rf.write_text('{"operation_id":"op-EVIL",' + genuine[1:])
    proc = _w6_cli(tmp_path, "--receipt", str(rf), "--json")
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["failure_code"] == S.CODE_NEG_10
    rf.write_text(genuine[:-1] + ',"n":' + "[" * 10_000 + "]" * 10_000 + "}")
    proc2 = _w6_cli(tmp_path, "--receipt", str(rf), "--json")
    assert proc2.returncode == 1 and "Traceback" not in proc2.stderr
    assert json.loads(proc2.stdout)["failure_code"] == S.CODE_NEG_10
    rf.write_text("{not json")
    proc3 = _w6_cli(tmp_path, "--receipt", str(rf), "--json")
    assert json.loads(proc3.stdout)["failure_code"] == CODE_NEG_03


def test_w6_cli_ledger_anchor_flags(tmp_path: Path) -> None:
    lines, tip = _w6_ledger(2)
    lf = tmp_path / "l.jsonl"
    lf.write_text("\n".join(lines) + "\n")
    no_anchor = _w6_cli(tmp_path, "--ledger", str(lf), "--json")
    assert no_anchor.returncode == 1
    assert json.loads(no_anchor.stdout)["failure_code"] == S.CODE_NO_COMPLETENESS_ANCHOR
    opted = _w6_cli(tmp_path, "--ledger", str(lf), "--allow-unanchored")
    assert opted.returncode == S.EXIT_UNANCHORED_LEDGER
    assert S.WARN_LEDGER_UNANCHORED in opted.stderr
    anchored = _w6_cli(tmp_path, "--ledger", str(lf), "--expected-count", "2", "--expected-tip", tip, "--json")
    assert anchored.returncode == 0 and json.loads(anchored.stdout)["complete"] is True
    truncated = _w6_cli(tmp_path, "--ledger", str(lf), "--expected-count", "3")
    assert truncated.returncode == 1
    helptext = _w6_cli(tmp_path, "--help").stdout
    for flag in ("--allow-unanchored", "--expected-count", "--expected-tip", "--allow-missing-alg"):
        assert flag in helptext


def test_w6_cli_rejects_small_order_key_file(tmp_path: Path) -> None:
    rf = tmp_path / "r.json"
    rf.write_text(json.dumps(_w6_sign(_w6_body())))
    kf = tmp_path / "weak.hex"
    kf.write_text("01" + "00" * 31)
    proc = subprocess.run([sys.executable, _SCRIPT, "--public-key", str(kf), "--receipt", str(rf), "--json"],
                          capture_output=True, text=True, timeout=120, cwd=str(_REPO), check=False)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["failure_code"] == S.CODE_NEG_09


def test_w6_cli_missing_alg_opt_in(tmp_path: Path) -> None:
    body = _w6_body()
    del body["alg"]
    rf = tmp_path / "r.json"
    rf.write_text(json.dumps(_w6_sign(body)))
    assert _w6_cli(tmp_path, "--receipt", str(rf), "--json").returncode == 1
    assert _w6_cli(tmp_path, "--receipt", str(rf), "--json", "--allow-missing-alg").returncode == 0


def test_w6_format_d_small_order_r_under_genuine_key_rejected() -> None:
    rcpt = _w6_format_d("op-1", {"operation_id": "op-1"})
    rcpt["signature"] = {"ed25519Signature": base64.b64encode((1).to_bytes(32, "little") + bytes(32)).decode()}
    res = _w6_verify(rcpt)
    assert res["valid"] is False and res["failure_code"] == CODE_NEG_02
    assert "Signature rejected before verification" in res["error"]
