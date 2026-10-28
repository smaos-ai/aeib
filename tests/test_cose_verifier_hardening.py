#!/usr/bin/env python3
"""
tests/test_cose_verifier_hardening.py — regression tests for the COSE/SCITT
verifier hardening (tools/verify_cose_scitt_receipts.py and
v1.1-roadmap/rfc9052_cose_profile.py).

Covers, with real Ed25519 keys from `cryptography`:
  C1  small-order / non-canonical Ed25519 public keys rejected at load and verify
  C2  no empty-AAD fallback for binary receipts
  C3  Merkle position (tree_size, leaf_index) taken only from signed data
  C4  alg accepted only from the protected header
  C5  duplicate keys / NaN / deep nesting -> coded rejection, never a traceback
  plus the n=1..33 genuine inclusion sweep (all must keep verifying).
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.verify_cose_scitt_receipts as V  # noqa: E402

CB, Tag, MT = V.RFC8949CBOR, V.CBORTag, V.SCITTMerkleTree
cose = V.cose_mod
TOOL = REPO_ROOT / "tools" / "verify_cose_scitt_receipts.py"


def _key(label: str) -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.from_private_bytes(hashlib.sha256(label.encode()).digest())


ISK, TSK = _key("hardening-issuer"), _key("hardening-ts")
IPK, TPK = ISK.public_key(), TSK.public_key()
ISSUER = V.RFC9052CoseSigner(private_key=ISK, key_id="issuer-1")


def _raw(pk: ed25519.Ed25519PublicKey) -> bytes:
    return pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _parts(blob: bytes) -> List[Any]:
    return list(CB.decode(blob).value)


def _sign1(prot: bytes, unprot: Dict[Any, Any], payload: bytes, sig: bytes) -> bytes:
    return CB.encode(Tag(tag=V.COSE_TAG_SIGN1, value=[prot, unprot, payload, sig]))


def _transparent(stmt: bytes, pre: int = 0, aad: bytes = b"") -> bytes:
    ts = V.SCITTTransparencyService("ts1", TSK)
    for i in range(pre):
        ts.issue_binary_cose_receipt(ISSUER.sign(b"filler-%d" % i))
    rc = ts.issue_binary_cose_receipt(stmt, expected_aad=aad)
    return V.append_receipt_to_signed_statement(stmt, rc)


# ---------------------------------------------------------------------------
# Independent Edwards25519 arithmetic (test-side, to enumerate torsion points)
# ---------------------------------------------------------------------------
P = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, P - 2, P)) % P
I = pow(2, (P - 1) // 4, P)
IDENT = (0, 1, 1, 0)


def _add(a: Tuple[int, ...], b: Tuple[int, ...]) -> Tuple[int, int, int, int]:
    x1, y1, z1, t1 = a
    x2, y2, z2, t2 = b
    A, B = (y1 - x1) * (y2 - x2) % P, (y1 + x1) * (y2 + x2) % P
    C, DD = 2 * t1 * t2 * D % P, 2 * z1 * z2 % P
    E, F, G, H = (B - A) % P, (DD - C) % P, (DD + C) % P, (B + A) % P
    return (E * F % P, G * H % P, F * G % P, E * H % P)


def _mul(k: int, pt: Tuple[int, ...]) -> Tuple[int, int, int, int]:
    r = IDENT
    while k:
        if k & 1:
            r = _add(r, pt)
        pt = _add(pt, pt)
        k >>= 1
    return r


def _affine(pt: Tuple[int, ...]) -> Tuple[int, int]:
    zi = pow(pt[2], P - 2, P)
    return (pt[0] * zi % P, pt[1] * zi % P)


def _decode_any(y: int, sign: int) -> Optional[Tuple[int, int, int, int]]:
    u, v = (y * y - 1) % P, (D * y * y + 1) % P
    x = u * pow(v, 3, P) * pow(u * pow(v, 7, P), (P - 5) // 8, P) % P
    if v * x * x % P == (-u) % P:
        x = x * I % P
    if v * x * x % P != u:
        return None
    if x % 2 != sign:
        x = (P - x) % P
    return (x, y, 1, x * y % P)


def _encode(x: int, y: int) -> bytes:
    raw = bytearray(y.to_bytes(32, "little"))
    raw[31] |= (x & 1) << 7
    return bytes(raw)


def _torsion_points() -> List[Tuple[int, int]]:
    for seed in range(1, 200):
        cand = _decode_any(seed, 0)
        if cand is None:
            continue
        t = _mul(L, cand)  # torsion component
        if _affine(_mul(4, t)) != (0, 1):  # order exactly 8 -> generates all 8
            pts = {_affine(_mul(k, t)) for k in range(8)}
            assert len(pts) == 8
            return sorted(pts)
    raise AssertionError("no order-8 point found")


TORSION = _torsion_points()
CANONICAL_SMALL_ORDER = [_encode(x, y) for x, y in TORSION]


def _noncanonical_small_order() -> List[bytes]:
    out: Set[bytes] = set()
    for x, y in TORSION:
        if y + P < 2**255:  # y >= p encodings of the same point
            out.add(_encode(x, y + P))
            if x == 0:
                out.add(_encode(1, y + P))
        if x == 0:  # x == 0 with the sign bit set
            out.add(_encode(1, y))
    return sorted(out)


NONCANONICAL_SMALL_ORDER = _noncanonical_small_order()


def test_enumerated_small_order_vectors() -> None:
    assert len(CANONICAL_SMALL_ORDER) == 8
    assert (0, 1) in TORSION and (0, P - 1) in TORSION
    assert len(NONCANONICAL_SMALL_ORDER) >= 4
    assert not set(CANONICAL_SMALL_ORDER) & set(NONCANONICAL_SMALL_ORDER)


@pytest.mark.parametrize("raw", CANONICAL_SMALL_ORDER, ids=lambda b: b.hex()[:8] + b.hex()[-4:])
def test_c1_canonical_small_order_keys_rejected(raw: bytes) -> None:
    assert cose.ed25519_public_key_rejection(raw) == "ERR_ED25519_KEY_SMALL_ORDER"
    with pytest.raises(ValueError, match="ERR_ED25519_KEY_SMALL_ORDER"):
        V.load_public_key(raw.hex())
    with pytest.raises(ValueError, match="ERR_ED25519_KEY_SMALL_ORDER"):
        V.load_public_key(base64.b64encode(raw).decode())


@pytest.mark.parametrize("raw", NONCANONICAL_SMALL_ORDER, ids=lambda b: b.hex()[:8] + b.hex()[-4:])
def test_c1_noncanonical_small_order_encodings_rejected(raw: bytes) -> None:
    assert cose.ed25519_public_key_rejection(raw) == "ERR_ED25519_KEY_NONCANONICAL"
    with pytest.raises(ValueError, match="ERR_ED25519_KEY_NONCANONICAL|Unable to parse"):
        V.load_public_key(raw.hex())


def test_c1_key_files_and_pem_admission(tmp_path: Path) -> None:
    weak = CANONICAL_SMALL_ORDER[0]
    for name, content in (("raw.bin", weak), ("hex.txt", weak.hex().encode()),
                          ("b64.txt", base64.b64encode(weak))):
        f = tmp_path / name
        f.write_bytes(content)
        with pytest.raises(ValueError, match="ERR_ED25519_KEY_SMALL_ORDER"):
            V.load_public_key(str(f))
    ec_pem = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    (tmp_path / "ec.pem").write_bytes(ec_pem)
    with pytest.raises(ValueError, match="ERR_ED25519_KEY_TYPE"):
        V.load_public_key(str(tmp_path / "ec.pem"))
    good_pem = IPK.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    (tmp_path / "good.pem").write_bytes(good_pem)
    assert _raw(V.load_public_key(str(tmp_path / "good.pem"))) == _raw(IPK)
    assert _raw(V.load_public_key(_raw(IPK).hex())) == _raw(IPK)
    assert cose.ed25519_public_key_rejection(b"\x00" * 31) == "ERR_ED25519_KEY_LENGTH"
    assert cose.admit_ed25519_public_key("not-a-key") == "ERR_ED25519_KEY_TYPE"
    assert cose.admit_ed25519_public_key(IPK) is None


def test_c1_off_curve_encoding_rejected() -> None:
    for y in range(2, 400):
        if _decode_any(y, 0) is None:
            assert cose.ed25519_public_key_rejection(_encode(0, y)) == "ERR_ED25519_KEY_NOT_ON_CURVE"
            return
    raise AssertionError("no off-curve y found")


def test_c1_forged_sign1_under_small_order_key_rejected_by_verifier() -> None:
    """pyca accepts these keys and the forgery; the verifier must refuse the key."""
    forged_count = 0
    for raw in CANONICAL_SMALL_ORDER:
        try:
            weak = ed25519.Ed25519PublicKey.from_public_bytes(raw)
        except ValueError:
            continue
        prot = CB.encode({1: -8})
        payload = b'{"op":"FORGED"}'
        # R = identity, s = 0: valid under a small-order A for cofactorless checks
        sig = (1).to_bytes(32, "little") + bytes(32)
        try:
            weak.verify(sig, CB.encode(["Signature1", prot, b"", payload]))
            forged_count += 1
        except Exception:
            pass
        res = V.RFC9052CoseVerifier.verify(_sign1(prot, {}, payload, sig), weak)
        assert res.valid is False
        assert (res.error or "").startswith("ERR_ED25519_KEY_SMALL_ORDER")
        good = V.append_receipt_to_signed_statement(
            _sign1(prot, {}, payload, sig),
            V.SCITTTransparencyService("ts1", TSK).issue_binary_cose_receipt(_sign1(prot, {}, payload, sig)),
        )
        bres = V.verify_binary_transparent_statement(good, weak, TPK)
        assert bres["valid"] is False and "ERR_ED25519_KEY_SMALL_ORDER" in bres["error"]
    assert forged_count >= 1  # the underlying library alone is not sufficient


# ---------------------------------------------------------------------------
# C2: external AAD must match exactly
# ---------------------------------------------------------------------------
def test_c2_receipt_without_required_aad_rejected() -> None:
    stmt = ISSUER.sign(b'{"op":"op-aad"}', external_aad=b"ctx")
    res = V.verify_binary_transparent_statement(_transparent(stmt, aad=b""), IPK, TPK, expected_aad=b"ctx")
    assert res["valid"] is False
    assert res["error"].startswith("Transparency Service COSE Receipt [0] verification failed")
    ok = V.verify_binary_transparent_statement(_transparent(stmt, aad=b"ctx"), IPK, TPK, expected_aad=b"ctx")
    assert ok["valid"] is True, ok["error"]


# ---------------------------------------------------------------------------
# C3: Merkle position only from signed data
# ---------------------------------------------------------------------------
def _receipt_parts(tr: bytes) -> Tuple[List[Any], bytes, List[Any]]:
    op = _parts(tr)
    rc = bytes(op[1][V.COSE_HEADER_RECEIPTS][0])
    return op, rc, _parts(rc)


def test_c3_genuine_receipt_reports_signed_position() -> None:
    tr = _transparent(ISSUER.sign(b'{"op":"op-3"}'), pre=2)
    _, _, rp = _receipt_parts(tr)
    prot = CB.decode(rp[0])
    assert prot[V.COSE_HEADER_AEIB_SIGNED_VDP_POSITION] == {V.VDP_TREE_SIZE: 3, V.VDP_LEAF_INDEX: 2}
    res = V.verify_binary_transparent_statement(tr, IPK, TPK)
    assert res["valid"] is True and (res["leaf_index"], res["tree_size"]) == (2, 3)


@pytest.mark.parametrize("size,index", [(2, 1), (3, 1), (4, 2), (3, 0)])
def test_c3_relabelled_unprotected_vdp_rejected(size: int, index: int) -> None:
    tr = _transparent(ISSUER.sign(b'{"op":"op-3"}'), pre=2)
    op, rc, rp = _receipt_parts(tr)
    vdp = dict(rp[1][V.COSE_HEADER_VDP])
    vdp[V.VDP_TREE_SIZE], vdp[V.VDP_LEAF_INDEX] = size, index
    rc2 = _sign1(rp[0], {**rp[1], V.COSE_HEADER_VDP: vdp}, rp[2], rp[3])
    tr2 = _sign1(op[0], {**op[1], V.COSE_HEADER_RECEIPTS: [rc2]}, op[2], op[3])
    res = V.verify_binary_transparent_statement(tr2, IPK, TPK)
    assert res["valid"] is False
    assert res["error"].startswith("ERR_VDP_POSITION_MISMATCH")
    assert "leaf_index" not in res


def _resign_receipt(rp: List[Any], prot_map: Dict[Any, Any], aad: bytes = b"") -> bytes:
    prot = CB.encode(prot_map)
    sig = TSK.sign(CB.encode(["Signature1", prot, aad, rp[2]]))
    return _sign1(prot, rp[1], rp[2], sig)


@pytest.mark.parametrize("position", [
    None,                                              # header absent (legacy receipt)
    {V.VDP_TREE_SIZE: 3},                              # incomplete
    {V.VDP_TREE_SIZE: 3, V.VDP_LEAF_INDEX: 2, -3: 0},  # extra key
    [3, 2],                                            # wrong type
])
def test_c3_missing_or_malformed_signed_position_rejected(position: Any) -> None:
    tr = _transparent(ISSUER.sign(b'{"op":"op-3"}'), pre=2)
    op, _, rp = _receipt_parts(tr)
    pm = dict(CB.decode(rp[0]))
    pm.pop(V.COSE_HEADER_AEIB_SIGNED_VDP_POSITION)
    if position is not None:
        pm[V.COSE_HEADER_AEIB_SIGNED_VDP_POSITION] = position
    tr2 = _sign1(op[0], {**op[1], V.COSE_HEADER_RECEIPTS: [_resign_receipt(rp, pm)]}, op[2], op[3])
    res = V.verify_binary_transparent_statement(tr2, IPK, TPK)
    assert res["valid"] is False
    assert res["error"].startswith("ERR_VDP_POSITION_NOT_SIGNED")


@pytest.mark.parametrize("signed", [
    {V.VDP_TREE_SIZE: True, V.VDP_LEAF_INDEX: 2},
    {V.VDP_TREE_SIZE: 3, V.VDP_LEAF_INDEX: False},
    {V.VDP_TREE_SIZE: 4, V.VDP_LEAF_INDEX: 2},
    {V.VDP_TREE_SIZE: 3, V.VDP_LEAF_INDEX: 1},
])
def test_c3_signed_position_must_equal_vdp_and_be_int(signed: Dict[int, Any]) -> None:
    tr = _transparent(ISSUER.sign(b'{"op":"op-3"}'), pre=2)
    op, _, rp = _receipt_parts(tr)
    pm = dict(CB.decode(rp[0]))
    pm[V.COSE_HEADER_AEIB_SIGNED_VDP_POSITION] = signed
    tr2 = _sign1(op[0], {**op[1], V.COSE_HEADER_RECEIPTS: [_resign_receipt(rp, pm)]}, op[2], op[3])
    res = V.verify_binary_transparent_statement(tr2, IPK, TPK)
    assert res["valid"] is False
    assert res["error"].startswith("ERR_VDP_POSITION_MISMATCH")


def test_c3_unprotected_kid_cannot_relabel_service() -> None:
    tr = _transparent(ISSUER.sign(b'{"op":"op-kid"}'))
    op, _, rp = _receipt_parts(tr)
    rc2 = _sign1(rp[0], {**rp[1], V.COSE_HEADER_KID: b"scitt-ts:evil"}, rp[2], rp[3])
    tr2 = _sign1(op[0], {**op[1], V.COSE_HEADER_RECEIPTS: [rc2]}, op[2], op[3])
    res = V.verify_binary_transparent_statement(tr2, IPK, TPK)
    assert res["valid"] is True
    assert res["ts_kid"] == "scitt-ts:ts1" and res["service_id"] == "ts1"


def test_inclusion_sweep_n1_to_33_and_binary_receipts() -> None:
    passed = total = 0
    for n in range(1, 34):
        tree = MT()
        leaves = [b"leaf-%d" % i for i in range(n)]
        for lf in leaves:
            tree.add_leaf(lf)
        root = tree.root_hash().hex()
        for i in range(n):
            total += 1
            passed += MT.verify_inclusion_proof(leaves[i], tree.inclusion_proof(i), root)
    assert (passed, total) == (561, 561)

    ts = V.SCITTTransparencyService("sweep", TSK)
    for i in range(33):
        stmt = ISSUER.sign(b'{"seq":%d}' % i)
        tr = V.append_receipt_to_signed_statement(stmt, ts.issue_binary_cose_receipt(stmt))
        res = V.verify_binary_transparent_statement(tr, IPK, TPK)
        assert res["valid"] is True, res["error"]
        assert (res["leaf_index"], res["tree_size"]) == (i, i + 1)


# ---------------------------------------------------------------------------
# C4: alg only from the protected header
# ---------------------------------------------------------------------------
def test_c4_alg_only_in_unprotected_header_rejected() -> None:
    prot = CB.encode({4: b"issuer-1"})
    blob = _sign1(prot, {1: -8}, b"x", ISK.sign(CB.encode(["Signature1", prot, b"", b"x"])))
    res = V.RFC9052CoseVerifier.verify(blob, IPK)
    assert res.valid is False
    assert (res.error or "").startswith("ERR_ALG_NOT_PROTECTED")
    missing = _sign1(prot, {}, b"x", ISK.sign(CB.encode(["Signature1", prot, b"", b"x"])))
    assert V.RFC9052CoseVerifier.verify(missing, IPK).error == "Missing required algorithm parameter (alg)"


def test_c4_protected_kid_preferred_over_unprotected() -> None:
    blob = ISSUER.sign(b"x", protected_extra={4: b"signed-kid"})
    p = _parts(blob)
    res = V.RFC9052CoseVerifier.verify(_sign1(p[0], {4: b"spoofed"}, p[2], p[3]), IPK)
    assert res.valid is True and res.kid == "signed-kid"


# ---------------------------------------------------------------------------
# C5: coded rejection for duplicate keys / NaN / deep nesting
# ---------------------------------------------------------------------------
def _bundle_with_payload(payload: bytes) -> Dict[str, Any]:
    stmt = ISSUER.sign(b'{"op":"op-1"}')
    bundle = V.SCITTTransparencyService("ts1", TSK).register_signed_statement(stmt, IPK)
    rc = V.RFC9052CoseSigner(private_key=TSK, key_id="scitt-ts:ts1").sign(payload)
    b2 = dict(bundle, cose_receipt_b64=base64.b64encode(rc).decode())
    b2.pop("merkle_root_hex", None)
    b2.pop("inclusion_proof", None)
    return b2


@pytest.mark.parametrize("payload,code", [
    (b'{"a":1,"a":2}', "ERR_DUPLICATE_KEY"),
    (b'{"a":NaN}', "ERR_NON_FINITE_NUMBER"),
    (b'{"a":1e400}', "ERR_NON_FINITE_NUMBER"),
    (b"[" * 200000 + b"]" * 200000, "ERR_JSON_NESTING_TOO_DEEP"),
    (b'"\\ud800"', "ERR_LONE_SURROGATE"),
    (b"[1,2]", "ERR_RECEIPT_NOT_OBJECT"),
    (b"{not json", "ERR_INVALID_JSON"),
])
def test_c5_json_receipt_payload_coded_rejection(payload: bytes, code: str) -> None:
    res = V.verify_transparent_statement(_bundle_with_payload(payload), IPK, TPK)
    assert res["valid"] is False
    assert res["error"].startswith("Malformed COSE Receipt JSON payload") and code in res["error"]


def test_c5_noncanonical_json_receipt_rejected() -> None:
    res = V.verify_transparent_statement(_bundle_with_payload(b'{ "a": 1 }'), IPK, TPK)
    assert res == {"valid": False, "error": "COSE Receipt payload is not RFC 8785 JCS canonical"}


def test_c5_legacy_bundle_still_verifies() -> None:
    stmt = ISSUER.sign(b'{"op":"op-1"}')
    bundle = V.SCITTTransparencyService("ts1", TSK).register_signed_statement(stmt, IPK)
    res = V.verify_transparent_statement(bundle, IPK, TPK)
    assert res["valid"] is True and (res["leaf_index"], res["tree_size"]) == (0, 1)


@pytest.mark.parametrize("blob", [
    b"\x81" * 10000 + b"\x00",
    b"\xd2\x84\x40\xa0" + b"\x81" * 10000 + b"\x00" + b"\x40",
    b"\xc1" * 10000 + b"\x00",
])
def test_c5_deep_cbor_nesting_coded(blob: bytes) -> None:
    res = V.verify_binary_transparent_statement(blob, IPK, TPK)
    assert res["valid"] is False and "ERR_CBOR_NESTING_TOO_DEEP" in res["error"]
    with pytest.raises(ValueError, match="ERR_CBOR_NESTING_TOO_DEEP"):
        V.inspect_cose_envelope(blob)


def test_c5_cbor_nesting_limit_boundary() -> None:
    limit = cose.MAX_CBOR_NESTING_DEPTH
    assert limit == 64
    at_limit = b"\x81" * limit + b"\x00"
    over = b"\x81" * (limit + 1) + b"\x00"
    decoded = CB.decode(at_limit)
    for _ in range(limit):
        decoded = decoded[0]
    assert decoded == 0
    with pytest.raises(ValueError, match="ERR_CBOR_NESTING_TOO_DEEP"):
        CB.decode(over)
    nested_map = b"\xa1\x00" * limit + b"\x00"
    CB.decode(nested_map)
    with pytest.raises(ValueError, match="ERR_CBOR_NESTING_TOO_DEEP"):
        CB.decode(b"\xa1\x00" * (limit + 1) + b"\x00")
    with pytest.raises(ValueError, match="ERR_CBOR_NESTING_TOO_DEEP"):
        CB.decode(b"\xa1" + b"\x81" * limit + b"\x00" + b"\x00")


# ---------------------------------------------------------------------------
# CLI: coded failures, no traceback (process isolation, not a sandbox)
# ---------------------------------------------------------------------------
def _cli(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True,
                          timeout=120, cwd=str(cwd))


def test_cli_rejects_small_order_keys_without_traceback(tmp_path: Path) -> None:
    stmt = ISSUER.sign(b'{"op":"cli"}')
    tr = _transparent(stmt)
    (tmp_path / "s.scitt.cose").write_bytes(tr)
    (tmp_path / "s.cose").write_bytes(stmt)
    (tmp_path / "ts.key").write_bytes(TSK.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
    weak = CANONICAL_SMALL_ORDER[0].hex()
    good_i, good_t = _raw(IPK).hex(), _raw(TPK).hex()

    ok = _cli(["verify-scitt", "--transparent-statement", "s.scitt.cose",
               "--issuer-pubkey", good_i, "--ts-pubkey", good_t], tmp_path)
    assert ok.returncode == 0, ok.stderr
    assert "VDP Leaf Index    : 0 / Tree Size 1" in ok.stdout

    for args in (
        ["verify-scitt", "--transparent-statement", "s.scitt.cose", "--issuer-pubkey", weak, "--ts-pubkey", good_t],
        ["verify-scitt", "--transparent-statement", "s.scitt.cose", "--issuer-pubkey", good_i, "--ts-pubkey", weak],
        ["append-receipt", "--envelope", "s.cose", "--issuer-pubkey", weak, "--ts-key", "ts.key", "--output", "o.cose"],
        ["--envelope", "s.cose", "--public-key", weak],
    ):
        proc = _cli(args, tmp_path)
        assert proc.returncode == 1, (args, proc.stdout, proc.stderr)
        assert "ERR_ED25519_KEY_SMALL_ORDER" in proc.stderr
        assert "Traceback" not in proc.stderr
    assert not (tmp_path / "o.cose").exists()

    bad_aad = _cli(["verify-scitt", "--transparent-statement", "s.scitt.cose", "--issuer-pubkey", good_i,
                    "--ts-pubkey", good_t, "--aad", "ctx"], tmp_path)
    assert bad_aad.returncode == 1 and "Traceback" not in bad_aad.stderr


# ---------------------------------------------------------------------------
# Fail-closed branch coverage (exact outcomes, so mutants of each branch die)
# ---------------------------------------------------------------------------
def _good_proof() -> Tuple[bytes, Dict[str, Any], str]:
    tree = MT()
    leaves = [b"a", b"b", b"c"]
    for lf in leaves:
        tree.add_leaf(lf)
    return leaves[1], tree.inclusion_proof(1), tree.root_hash().hex()


def _mutated(**kw: Any) -> Dict[str, Any]:
    _, proof, _ = _good_proof()
    return dict(proof, **kw)


@pytest.mark.parametrize("proof,root", [
    ("not-a-dict", None),
    ({}, 5),
    (_mutated(leaf_index=True), None),
    (_mutated(tree_size=True), None),
    (_mutated(leaf_index="1"), None),
    (_mutated(tree_size=3.0), None),
    (_mutated(audit_path="ab"), None),
    (_mutated(leaf_index=-1), None),
    (_mutated(tree_size=0, leaf_index=0), None),
    (_mutated(leaf_index=3), None),
    (_mutated(root_hash_hex="zz"), None),
    (_mutated(root_hash_hex="00" * 32), None),
    (_mutated(), "zz"),
    (_mutated(), "00" * 31),
    (_mutated(audit_path=[]), None),
    (_mutated(audit_path=[7, "00" * 32]), None),
    (_mutated(audit_path=["zz", "00" * 32]), None),
    (_mutated(audit_path=["00" * 31, "00" * 32]), None),
])
def test_verify_inclusion_proof_rejects_malformed(proof: Any, root: Any) -> None:
    leaf, _, good_root = _good_proof()
    assert MT.verify_inclusion_proof(leaf, proof, good_root if root is None else root) is False


def test_verify_inclusion_proof_positive_and_wrong_leaf() -> None:
    leaf, proof, root = _good_proof()
    assert MT.verify_inclusion_proof(leaf, proof, root) is True
    no_root = {k: v for k, v in proof.items() if k != "root_hash_hex"}
    assert MT.verify_inclusion_proof(leaf, no_root, root) is True
    assert MT.verify_inclusion_proof(b"x", proof, root) is False
    # A negative index walks the same split directions as leaf 0, so leaf 0's
    # genuine path would recompute the root; the bounds check must reject it.
    t2 = MT()
    t2.add_leaf(b"l0")
    t2.add_leaf(b"l1")
    p0 = t2.inclusion_proof(0)
    assert MT.verify_inclusion_proof(b"l0", p0, t2.root_hash().hex()) is True
    assert MT.verify_inclusion_proof(b"l0", dict(p0, leaf_index=-1), t2.root_hash().hex()) is False
    with pytest.raises(TypeError):
        MT.hash_leaf("str")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        MT().inclusion_proof(0)
    assert MT().root_hash() == hashlib.sha256(b"").digest()


def test_transparency_service_input_validation() -> None:
    with pytest.raises(ValueError, match="service_id must be a non-empty string"):
        V.SCITTTransparencyService("", TSK)
    ts = V.SCITTTransparencyService("ts1", TSK)
    with pytest.raises(ValueError, match="non-empty CBOR"):
        ts.issue_binary_cose_receipt(b"")
    other = V.RFC9052CoseSigner(private_key=_key("other"), key_id="x").sign(b"y")
    with pytest.raises(ValueError, match="Registration Policy rejected"):
        ts.issue_binary_cose_receipt(other, issuer_pubkey=IPK)
    with pytest.raises(ValueError, match="Registration Policy rejected"):
        ts.register_signed_statement(other, IPK)
    assert ts.tree.tree_size == 0


def _rebuild_receipt(prot_map: Dict[Any, Any], unprot: Dict[Any, Any], payload: bytes) -> bytes:
    prot = CB.encode(prot_map)
    return _sign1(prot, unprot, payload, TSK.sign(CB.encode(["Signature1", prot, b"", payload])))


def _binary_variant(prot_edit: Any = None, unprot_edit: Any = None, payload: Optional[bytes] = None) -> bytes:
    stmt = ISSUER.sign(b'{"op":"variant"}')
    tr = _transparent(stmt)
    op, _, rp = _receipt_parts(tr)
    pm, um = dict(CB.decode(rp[0])), dict(rp[1])
    if prot_edit:
        prot_edit(pm)
    if unprot_edit:
        unprot_edit(um)
    rc = _rebuild_receipt(pm, um, rp[2] if payload is None else payload)
    return _sign1(op[0], {**op[1], V.COSE_HEADER_RECEIPTS: [rc]}, op[2], op[3])


def _set(d: Dict[Any, Any], k: Any, v: Any) -> None:
    d[k] = v


@pytest.mark.parametrize("blob_fn,expected", [
    (lambda: _binary_variant(prot_edit=lambda m: _set(m, V.COSE_HEADER_VDS, 2)),
     "Unsupported or invalid COSE_HEADER_VDS (395) in receipt [0]: 2 (expected 1)"),
    (lambda: _binary_variant(prot_edit=lambda m: _set(m, V.COSE_HEADER_VDS, True)),
     "Unsupported or invalid COSE_HEADER_VDS (395) in receipt [0]: True (expected 1)"),
    (lambda: _binary_variant(unprot_edit=lambda m: _set(m, V.COSE_HEADER_VDS, 1)),
     "COSE_HEADER_VDS (395) must reside in receipt protected headers"),
    (lambda: _binary_variant(unprot_edit=lambda m: m.pop(V.COSE_HEADER_VDP)),
     "Missing or invalid COSE_HEADER_VDP (396) proof map in receipt [0]"),
    (lambda: _binary_variant(unprot_edit=lambda m: _set(m, V.COSE_HEADER_VDP, {V.VDP_TREE_SIZE: 1, V.VDP_LEAF_INDEX: 0, V.VDP_INCLUSION_PATH: "x"})),
     "Malformed VDP (396) fields in receipt [0]"),
    (lambda: _binary_variant(unprot_edit=lambda m: _set(m, V.COSE_HEADER_VDP, {V.VDP_TREE_SIZE: True, V.VDP_LEAF_INDEX: 0, V.VDP_INCLUSION_PATH: []})),
     "Malformed VDP (396) fields in receipt [0]"),
    (lambda: _binary_variant(unprot_edit=lambda m: _set(m, V.COSE_HEADER_VDP, {V.VDP_TREE_SIZE: 1, V.VDP_LEAF_INDEX: False, V.VDP_INCLUSION_PATH: []})),
     "Malformed VDP (396) fields in receipt [0]"),
    (lambda: _binary_variant(unprot_edit=lambda m: _set(m, V.COSE_HEADER_VDP, {V.VDP_TREE_SIZE: 1, V.VDP_LEAF_INDEX: 0, V.VDP_INCLUSION_PATH: [b"\x00" * 31]})),
     "Invalid sibling hash in VDP (396) inclusion_path (-3) in receipt [0]"),
    (lambda: _binary_variant(unprot_edit=lambda m: _set(m, V.COSE_HEADER_VDP, {V.VDP_TREE_SIZE: 1, V.VDP_LEAF_INDEX: 0, V.VDP_INCLUSION_PATH: ["00" * 32]})),
     "Invalid sibling hash in VDP (396) inclusion_path (-3) in receipt [0]"),
    (lambda: _binary_variant(payload=b"\x00" * 31),
     "Invalid Merkle root payload length in receipt [0]: 31 bytes (expected 32)"),
    (lambda: _binary_variant(payload=b"\x00" * 32),
     "RFC 9942 / RFC 9162 VDP Merkle inclusion proof verification failed for receipt [0]"),
])
def test_binary_receipt_structural_rejections(blob_fn: Any, expected: str) -> None:
    assert V.verify_binary_transparent_statement(blob_fn(), IPK, TPK) == {"valid": False, "error": expected}


def test_binary_statement_receipt_header_rejections() -> None:
    stmt = ISSUER.sign(b'{"op":"hdr"}')
    p = _parts(stmt)
    no_receipts = V.verify_binary_transparent_statement(stmt, IPK, TPK)
    assert no_receipts == {"valid": False, "error": "Missing or empty COSE_HEADER_RECEIPTS (394) in unprotected headers"}
    empty = _sign1(p[0], {**p[1], V.COSE_HEADER_RECEIPTS: []}, p[2], p[3])
    assert V.verify_binary_transparent_statement(empty, IPK, TPK)["error"].startswith("Missing or empty")
    bad_entry = _sign1(p[0], {**p[1], V.COSE_HEADER_RECEIPTS: [b""]}, p[2], p[3])
    assert V.verify_binary_transparent_statement(bad_entry, IPK, TPK) == {
        "valid": False,
        "error": "Receipt [0] in COSE_HEADER_RECEIPTS (394) is not a non-empty CBOR bstr",
    }
    prot_rc = ISSUER.sign(b"y", protected_extra={V.COSE_HEADER_RECEIPTS: [b"r"]})
    assert V.verify_binary_transparent_statement(prot_rc, IPK, TPK) == {
        "valid": False,
        "error": "COSE_HEADER_RECEIPTS (394) must be in unprotected headers, not protected headers",
    }
    wrong_ts = V.verify_binary_transparent_statement(_transparent(stmt), IPK, IPK)
    assert wrong_ts["valid"] is False and wrong_ts["error"].startswith("Transparency Service COSE Receipt [0]")


def test_binary_success_fields_exact() -> None:
    stmt = ISSUER.sign(b'{"op":"fields"}')
    ts = V.SCITTTransparencyService("svc", TSK)
    tr = V.append_receipt_to_signed_statement(stmt, ts.issue_binary_cose_receipt(stmt, issuer_pubkey=IPK))
    res = V.verify_binary_transparent_statement(tr, IPK, TPK)
    assert res["valid"] is True and res["error"] is None
    assert res["vds"] == 1 and res["service_id"] == "svc" and res["ts_kid"] == "scitt-ts:svc"
    assert res["receipt_count"] == 1 and res["issuer_kid"] == "issuer-1"
    assert res["statement_sha256"] == hashlib.sha256(stmt).hexdigest()
    assert res["merkle_root_hex"] == ts.tree.root_hash().hex() and res["audit_path"] == []
    assert res["statement_payload"] == b'{"op":"fields"}'


def _bundle() -> Dict[str, Any]:
    stmt = ISSUER.sign(b'{"op":"bundle"}')
    ts = V.SCITTTransparencyService("ts1", TSK)
    ts.register_signed_statement(ISSUER.sign(b"pre"), IPK)
    return ts.register_signed_statement(stmt, IPK)


def _signed_claims_bundle(edit: Any) -> Dict[str, Any]:
    b = _bundle()
    claims = json.loads(_parts(base64.b64decode(b["cose_receipt_b64"]))[2])
    edit(claims)
    rc = V.RFC9052CoseSigner(private_key=TSK, key_id="scitt-ts:ts1").sign(V.encode_jcs(claims))
    out = dict(b, cose_receipt_b64=base64.b64encode(rc).decode())
    out.pop("merkle_root_hex")
    out.pop("inclusion_proof")
    return out


def test_legacy_bundle_rejections_exact() -> None:
    b = _bundle()
    ok = V.verify_transparent_statement(b, IPK, TPK)
    assert ok["valid"] is True and (ok["leaf_index"], ok["tree_size"]) == (1, 2)
    assert ok["service_id"] == "ts1" and ok["ts_kid"] == "scitt-ts:ts1" and ok["error"] is None
    assert b["issuer_kid"] == "issuer-1" and b["ts_kid"] == "scitt-ts:ts1"

    bad_b64 = V.verify_transparent_statement(dict(b, signed_statement_b64=None), IPK, TPK)
    assert bad_b64["valid"] is False and bad_b64["error"].startswith("Malformed base64 in bundle")
    no_rc = V.verify_transparent_statement({"signed_statement_b64": b["signed_statement_b64"]}, IPK, TPK)
    assert no_rc["valid"] is False and no_rc["error"].startswith("Malformed base64 in bundle")
    wrong_issuer = V.verify_transparent_statement(b, TPK, TPK)
    assert wrong_issuer["error"].startswith("Issuer Signed Statement verification failed")
    wrong_ts = V.verify_transparent_statement(b, IPK, IPK)
    assert wrong_ts["error"].startswith("Transparency Service COSE Receipt verification failed")
    assert V.verify_transparent_statement(dict(b, merkle_root_hex="00" * 32), IPK, TPK) == {
        "valid": False, "error": "Bundle merkle_root_hex does not match signed COSE Receipt merkle_root_hex"}
    assert V.verify_transparent_statement(dict(b, inclusion_proof={"x": 1}), IPK, TPK) == {
        "valid": False, "error": "Bundle inclusion_proof does not match signed COSE Receipt claims"}

    assert V.verify_transparent_statement(_signed_claims_bundle(lambda c: _set(c, "statement_sha256", "00")), IPK, TPK) == {
        "valid": False, "error": "Statement SHA-256 mismatch between Signed Statement and COSE Receipt"}
    assert V.verify_transparent_statement(_signed_claims_bundle(lambda c: c.pop("merkle_root_hex")), IPK, TPK) == {
        "valid": False, "error": "Missing merkle_root_hex in COSE Receipt"}
    assert V.verify_transparent_statement(_signed_claims_bundle(lambda c: _set(c, "leaf_index", 0)), IPK, TPK) == {
        "valid": False, "error": "RFC 9942 / RFC 9162 Merkle inclusion proof verification failed"}


def test_load_private_key_formats(tmp_path: Path) -> None:
    raw = ISK.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pem = ISK.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    files = {"k.pem": pem, "k.raw": raw, "k.hex": raw.hex().encode(), "k.b64": base64.b64encode(raw)}
    inputs = []
    for name, content in files.items():
        (tmp_path / name).write_bytes(content)
        inputs.append(str(tmp_path / name))
    inputs += [raw.hex(), base64.b64encode(raw).decode()]
    for value in inputs:
        key = V.load_private_key(value)
        assert isinstance(key, ed25519.Ed25519PrivateKey)
        assert _raw(key.public_key()) == _raw(IPK)
    ec_pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    (tmp_path / "ec.pem").write_bytes(ec_pem)
    for bad in (str(tmp_path / "ec.pem"), "00" * 31, "not a key"):
        with pytest.raises(ValueError, match="Unable to parse Ed25519 private key"):
            V.load_private_key(bad)
    with pytest.raises(ValueError, match="Unable to parse public key"):
        V.load_public_key("not a key")
    (tmp_path / "junk.txt").write_bytes(b"\xff\xfe junk")
    with pytest.raises(ValueError, match="Unable to parse public key"):
        V.load_public_key(str(tmp_path / "junk.txt"))


def test_decode_aad_and_header_formatting() -> None:
    assert V._decode_aad("") == b""
    assert V._decode_aad("0a0b") == b"\x0a\x0b"
    assert V._decode_aad("ctx") == b"ctx"
    assert V._format_header_value(V.COSE_HEADER_KID, b"kid-1") == "kid-1"
    assert V._format_header_value(V.COSE_HEADER_VDP, {V.VDP_TREE_SIZE: 2, V.VDP_LEAF_INDEX: 1,
                                                       V.VDP_INCLUSION_PATH: [b"\x01" * 2, "x"]}) == {
        "-1 (tree_size)": 2, "-2 (leaf_index)": 1, "-3 (inclusion_path)": ["0101", "x"]}
    assert V._format_header_value(99, b"\xab") == "ab"
    assert V._format_header_value(99, 5) == 5


def test_inspect_cose_envelope_structure() -> None:
    stmt = ISSUER.sign(b'{"op":"inspect"}')
    info = V.inspect_cose_envelope(_transparent(stmt))
    assert info["cbor_tag"] == 18 and info["payload_utf8"] == '{"op":"inspect"}'
    assert info["payload_len"] == 16 and info["unprotected_headers"][V.COSE_HEADER_RECEIPTS] == "[1 embedded COSE receipt(s)]"
    assert len(info["embedded_receipts_394"]) == 1
    rc_info = info["embedded_receipts_394"][0]
    assert rc_info["protected_headers"][V.COSE_HEADER_VDS] == 1
    assert rc_info["payload_utf8"] is None or len(rc_info["payload_hex"]) == 64
    with pytest.raises(ValueError, match="not a valid CBOR Tag 18"):
        V.inspect_cose_envelope(CB.encode([1, 2]))
    binary = V.inspect_cose_envelope(V.RFC9052CoseSigner(private_key=ISK, key_id="k").sign(b"\xff\xfe"))
    assert binary["payload_utf8"] is None


def _ns(**kw: Any) -> Any:
    import argparse
    return argparse.Namespace(**kw)


def test_cli_commands_in_process(tmp_path: Path, capsys: Any) -> None:
    raw_isk = ISK.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    raw_tsk = TSK.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    (tmp_path / "in.json").write_text('{"b": 2, "a": 1}')
    (tmp_path / "in.bin").write_bytes(b"\xff\x00raw")
    out = tmp_path / "o" / "s.cose"

    assert V._cmd_sign(_ns(input=str(tmp_path / "missing"), key=raw_isk.hex(), kid="k", output=str(out), aad="")) == 1
    assert V._cmd_sign(_ns(input=str(tmp_path / "in.json"), key=raw_isk.hex(), kid="cli-k", output=str(out), aad="ctx")) == 0
    res = V.RFC9052CoseVerifier.verify(out.read_bytes(), IPK, expected_external_aad=b"ctx")
    assert res.valid and res.payload == b'{"a":1,"b":2}' and res.kid == "cli-k"
    raw_out = tmp_path / "raw.cose"
    assert V._cmd_sign(_ns(input=str(tmp_path / "in.bin"), key=raw_isk.hex(), kid="k", output=str(raw_out), aad="")) == 0
    assert V.RFC9052CoseVerifier.verify(raw_out.read_bytes(), IPK).payload == b"\xff\x00raw"

    scitt = tmp_path / "s.scitt.cose"
    base = dict(envelope=str(out), issuer_pubkey=_raw(IPK).hex(), ts_key=raw_tsk.hex(),
                output=str(scitt), service_id="cli-svc", aad="ctx")
    assert V._cmd_append_receipt(_ns(**dict(base, envelope=str(tmp_path / "missing")))) == 1
    assert V._cmd_append_receipt(_ns(**dict(base, aad=""))) == 1  # registration policy: AAD mismatch
    assert not scitt.exists()
    assert V._cmd_append_receipt(_ns(**base)) == 0
    assert scitt.exists()

    vbase = dict(transparent_statement=str(scitt), envelope=None, issuer_pubkey=_raw(IPK).hex(),
                 ts_pubkey=_raw(TPK).hex(), aad="ctx")
    assert V._cmd_verify_scitt(_ns(**vbase)) == 0
    assert "VDP Leaf Index    : 0 / Tree Size 1" in capsys.readouterr().out
    assert V._cmd_verify_scitt(_ns(**dict(vbase, aad=""))) == 1
    assert V._cmd_verify_scitt(_ns(**dict(vbase, transparent_statement=None, envelope=str(scitt)))) == 0
    assert V._cmd_verify_scitt(_ns(**dict(vbase, transparent_statement=None))) == 1
    assert V._cmd_verify_scitt(_ns(**dict(vbase, transparent_statement=str(tmp_path / "missing")))) == 1

    ins = dict(file=None, input=None, envelope=None, transparent_statement=None)
    assert V._cmd_inspect(_ns(**ins)) == 1
    assert V._cmd_inspect(_ns(**dict(ins, file=str(tmp_path / "missing")))) == 1
    (tmp_path / "junk.cose").write_bytes(b"\x81" * 100 + b"\x00")
    assert V._cmd_inspect(_ns(**dict(ins, file=str(tmp_path / "junk.cose")))) == 1
    assert V._cmd_inspect(_ns(**dict(ins, transparent_statement=str(scitt)))) == 0
    printed = capsys.readouterr().out
    assert "Embedded Receipt [0] (Header 394)" in printed and "Header 395 (vds) : 1" in printed


def test_cli_main_argument_contract(tmp_path: Path) -> None:
    stmt = ISSUER.sign(b'{"caid":"c1","disposition":"ALLOW"}')
    (tmp_path / "s.cose").write_bytes(stmt)
    ok = _cli(["--envelope", "s.cose", "--public-key", _raw(IPK).hex()], tmp_path)
    assert ok.returncode == 0 and "Inner Payload CAID: c1" in ok.stdout
    bad = _cli(["--envelope", "s.cose", "--public-key", _raw(TPK).hex()], tmp_path)
    assert bad.returncode == 1 and "COSE_Sign1 Verification FAILED" in bad.stderr
    missing = _cli(["--envelope", "nope.cose", "--public-key", _raw(IPK).hex()], tmp_path)
    assert missing.returncode == 1 and "Envelope file not found" in missing.stderr
    assert _cli([], tmp_path).returncode == 2
    for args in (["sign", "--input", "x", "--output", "y"],
                 ["sign", "--key", "k", "--output", "y"],
                 ["sign", "--input", "x", "--key", "k"],
                 ["append-receipt", "--issuer-pubkey", "a", "--ts-key", "b", "--output", "c"],
                 ["append-receipt", "--envelope", "e", "--ts-key", "b", "--output", "c"],
                 ["append-receipt", "--envelope", "e", "--issuer-pubkey", "a", "--output", "c"],
                 ["append-receipt", "--envelope", "e", "--issuer-pubkey", "a", "--ts-key", "b"],
                 ["verify-scitt", "--transparent-statement", "t", "--ts-pubkey", "b"],
                 ["verify-scitt", "--transparent-statement", "t", "--issuer-pubkey", "a"]):
        proc = _cli(args, tmp_path)
        assert proc.returncode == 2 and "required" in proc.stderr, args
    st = _cli(["--self-test"], tmp_path)
    assert st.returncode == 0 and "Self-Test PASSED" in st.stdout


def test_run_self_test_in_process(capsys: Any) -> None:
    assert V.run_self_test() == 0
    assert "Tree Size         : 4 leaves" in capsys.readouterr().out
