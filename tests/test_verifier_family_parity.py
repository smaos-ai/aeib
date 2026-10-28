#!/usr/bin/env python3
"""
tests/test_verifier_family_parity.py
================================================================================
Cross-verifier parity gate for the three offline verifiers:

  * tools/aeib_offline_verifier.py        (hash-chained ledger bundles)
  * tools/standalone_receipt_verifier.py  (flat receipts, pyca Ed25519)
  * tools/standalone_offline_verifier.py  (flat receipts, pure-Python Ed25519)

ONE logical attack corpus (genuine, small-order keys and their non-canonical
encodings, small-order R, s+L, post-signing tamper, algorithm confusion,
missing alg, duplicate JSON keys, NaN/Infinity, deep nesting) is rendered into
each verifier's native format by a thin adapter. Every genuine artifact must
verify; every attack must be rejected with a coded error and never raise.
JCS bytes of each verifier must equal src.jcs_canonicalizer.encode_jcs on the
A1 payload set (200 seeded random + edge payloads).

Real Ed25519 signing via `cryptography` is used in this test only.
"""

from __future__ import annotations

import base64
import copy
import json
import random
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

import tools.aeib_offline_verifier as A
import tools.standalone_offline_verifier as O
import tools.standalone_receipt_verifier as S
from src.jcs_canonicalizer import encode_jcs as reference_encode_jcs

P_FIELD = 2**255 - 19
L_ORDER = 2**252 + 27742317777372353535851937790883648493
NOW = 1_760_000_000
OP_ID = "op-parity-1"
PAYLOAD = {"intent": "refund", "amount_minor": 2500, "currency": "EUR"}
SIGNING_KEY = Ed25519PrivateKey.from_private_bytes(b"verifier-family-parity-seed-32b!")
GENUINE_PUB_RAW = SIGNING_KEY.public_key().public_bytes_raw()


# ------------------------------------------------------------------------------
# Small-order point corpus (derived, not hardcoded): L * P for curve points P
# ------------------------------------------------------------------------------

def _small_order_encodings() -> List[bytes]:
    found = set()
    y = 2
    while len(found) < 8 and y < 400:
        for top in (0, 1 << 255):
            pt = O._decompress_point((y | top).to_bytes(32, "little"))
            if pt is not None:
                found.add(O._compress_point(O._point_mul(L_ORDER, pt)))
        y += 1
    return sorted(found)


SMALL_ORDER = _small_order_encodings()


def _non_canonical_small_order_encodings() -> List[bytes]:
    """y >= p aliases (y + p < 2^255) and x == 0 with sign bit set, for small-order points."""
    out = []
    for enc in SMALL_ORDER:
        y = int.from_bytes(enc[:31] + bytes([enc[31] & 0x7F]), "little")
        sign = enc[31] & 0x80
        if y + P_FIELD < 2**255:
            alias = bytearray((y + P_FIELD).to_bytes(32, "little"))
            alias[31] |= sign
            out.append(bytes(alias))
        if y in (0, 1, P_FIELD - 1) or enc[:31] == bytes(31):
            flipped = bytearray(enc)
            flipped[31] ^= 0x80
            if O._decompress_point(bytes(flipped)) is None:
                out.append(bytes(flipped))
    return sorted(set(out))


NON_CANONICAL_SMALL_ORDER = _non_canonical_small_order_encodings()
WEAK_KEYS = SMALL_ORDER + NON_CANONICAL_SMALL_ORDER
IDENTITY_R_ZERO_S = (1).to_bytes(32, "little") + bytes(32)


def test_small_order_corpus_shape() -> None:
    assert len(SMALL_ORDER) == 8
    assert (1).to_bytes(32, "little") in SMALL_ORDER
    assert len(NON_CANONICAL_SMALL_ORDER) >= 2


# ------------------------------------------------------------------------------
# Adapters: (artifact builder, verifier, ingress) per verifier family
# ------------------------------------------------------------------------------

Outcome = Tuple[bool, Optional[str]]


class AeibAdapter:
    name = "aeib_offline_verifier"
    kid = "parity-kid"
    nesting_codes = {"ERR_INPUT_NESTING_TOO_DEEP"}

    def genuine(self) -> Dict[str, Any]:
        return A.build_signed_entry(1, OP_ID, A.GENESIS_PREV_HASH, self.kid, SIGNING_KEY)

    def resign(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        body = {k: v for k, v in entry.items() if k not in A.UNSIGNED_EXCLUDED_KEYS}
        canonical = A.canonical_json_v1(body)
        entry["entry_hash"] = A.sha256_prefixed(canonical)
        entry["signature_b64"] = base64.b64encode(SIGNING_KEY.sign(canonical)).decode("ascii")
        return entry

    def set_signature(self, entry: Dict[str, Any], sig: bytes) -> None:
        entry["signature_b64"] = base64.b64encode(sig).decode("ascii")

    def set_alg(self, entry: Dict[str, Any], alg: Optional[str]) -> Dict[str, Any]:
        if alg is None:
            entry.pop("algorithm", None)
        else:
            entry["algorithm"] = alg
        return self.resign(entry)

    def tamper(self, entry: Dict[str, Any]) -> None:
        entry["action_binding"]["amount_minor"] += 1

    def verify(self, entry: Any, pub_raw: bytes = GENUINE_PUB_RAW) -> Outcome:
        try:
            anchor = Ed25519PublicKey.from_public_bytes(pub_raw)
        except ValueError:
            return False, "ERR_KEY_LOAD_REJECTED_BY_PYCA"
        entries = [entry]
        manifest = A.build_manifest(entries) if isinstance(entry, dict) and "entry_hash" in entry else {}
        res = A.StandaloneOfflineVerifier({self.kid: anchor}).verify_bundle(manifest, entries, [OP_ID])
        return res.valid, res.error_code

    def ingress(self, text: str) -> Any:
        try:
            return A._load_strict_json_text(text)
        except A.StrictJSONError as exc:
            raise IngressRejected(exc.code) from exc


class _FlatBodyMixin:
    def body(self) -> Dict[str, Any]:
        return {
            "operation_id": OP_ID,
            "disposition": "CONFIRMED",
            "alg": "Ed25519",
            "action_payload": dict(PAYLOAD),
            "action_caid": "sha256:" + O.compute_jcs_sha256(PAYLOAD),
            "timestamp_epoch": NOW,
        }

    def tamper(self, rcpt: Dict[str, Any]) -> None:
        rcpt["disposition"] = "REFUTED"

    def set_alg(self, rcpt: Dict[str, Any], alg: Optional[str]) -> Dict[str, Any]:
        body = {k: v for k, v in rcpt.items() if k not in (self.sig_field,)}
        if alg is None:
            body.pop("alg", None)
        else:
            body["alg"] = alg
        return self.sign(body)


class ReceiptAdapter(_FlatBodyMixin):
    name = "standalone_receipt_verifier"
    sig_field = "signature_b64"
    nesting_codes = {S.CODE_NEG_10}

    def sign(self, body: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(body)
        out[self.sig_field] = base64.b64encode(SIGNING_KEY.sign(S.encode_jcs(body))).decode("ascii")
        return out

    def genuine(self) -> Dict[str, Any]:
        return self.sign(self.body())

    def set_signature(self, rcpt: Dict[str, Any], sig: bytes) -> None:
        rcpt[self.sig_field] = base64.b64encode(sig).decode("ascii")

    def verify(self, rcpt: Any, pub_raw: bytes = GENUINE_PUB_RAW) -> Outcome:
        try:
            key = Ed25519PublicKey.from_public_bytes(pub_raw)
        except ValueError:
            return False, "ERR_KEY_LOAD_REJECTED_BY_PYCA"
        res = S.verify_receipt_data(rcpt, trusted_public_key=key, current_time_epoch=NOW)
        return res["valid"], res["failure_code"]

    def ingress(self, text: str) -> Any:
        try:
            return S.loads_strict_json(text)
        except S.StrictIngressError as exc:
            raise IngressRejected(exc.code) from exc


class OfflineAdapter(_FlatBodyMixin):
    name = "standalone_offline_verifier"
    sig_field = "signature_hex"
    nesting_codes = {O.ERR_NESTING_TOO_DEEP}

    def sign(self, body: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(body)
        out[self.sig_field] = SIGNING_KEY.sign(O.encode_jcs(body)).hex()
        return out

    def genuine(self) -> Dict[str, Any]:
        return self.sign(self.body())

    def set_signature(self, rcpt: Dict[str, Any], sig: bytes) -> None:
        rcpt[self.sig_field] = sig.hex()

    def verify(self, rcpt: Any, pub_raw: bytes = GENUINE_PUB_RAW) -> Outcome:
        res = O.verify_any_receipt(rcpt, pub_raw)
        return bool(res.get("valid")), res.get("error_code")

    def ingress(self, text: str) -> Any:
        try:
            return O.loads_strict_json(text)
        except O.StrictIngressError as exc:
            raise IngressRejected(exc.code) from exc


class IngressRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


ADAPTERS = [AeibAdapter(), ReceiptAdapter(), OfflineAdapter()]
ADAPTER_IDS = [a.name for a in ADAPTERS]


def _assert_coded_rejection(outcome: Outcome) -> None:
    valid, code = outcome
    assert valid is False
    assert isinstance(code, str) and code, f"rejection without a code: {outcome}"


# ------------------------------------------------------------------------------
# Corpus
# ------------------------------------------------------------------------------

@pytest.mark.parametrize("adapter", ADAPTERS, ids=ADAPTER_IDS)
def test_genuine_artifact_verifies(adapter: Any) -> None:
    valid, code = adapter.verify(adapter.genuine())
    assert valid is True, code
    assert code is None


@pytest.mark.parametrize("adapter", ADAPTERS, ids=ADAPTER_IDS)
@pytest.mark.parametrize("weak_key", WEAK_KEYS, ids=[k.hex()[:12] + k.hex()[-4:] for k in WEAK_KEYS])
def test_small_order_and_non_canonical_key_forgery_rejected(adapter: Any, weak_key: bytes) -> None:
    """Forged signature (R = identity, s = 0) under a pinned small-order key must be rejected."""
    art = adapter.genuine()
    adapter.set_signature(art, IDENTITY_R_ZERO_S)
    _assert_coded_rejection(adapter.verify(art, weak_key))


@pytest.mark.parametrize("adapter", ADAPTERS, ids=ADAPTER_IDS)
def test_small_order_r_rejected_under_genuine_key(adapter: Any) -> None:
    for r_enc in SMALL_ORDER:
        art = adapter.genuine()
        adapter.set_signature(art, r_enc + bytes(32))
        _assert_coded_rejection(adapter.verify(art))


@pytest.mark.parametrize("adapter", ADAPTERS, ids=ADAPTER_IDS)
def test_s_plus_l_malleability_rejected(adapter: Any) -> None:
    art = adapter.genuine()
    field = "signature_b64" if adapter.name != "standalone_offline_verifier" else "signature_hex"
    raw = bytes.fromhex(art[field]) if field == "signature_hex" else base64.b64decode(art[field])
    s_val = int.from_bytes(raw[32:], "little") + L_ORDER
    adapter.set_signature(art, raw[:32] + s_val.to_bytes(32, "little"))
    _assert_coded_rejection(adapter.verify(art))


@pytest.mark.parametrize("adapter", ADAPTERS, ids=ADAPTER_IDS)
def test_post_signing_tamper_rejected(adapter: Any) -> None:
    art = adapter.genuine()
    adapter.tamper(art)
    _assert_coded_rejection(adapter.verify(art))


@pytest.mark.parametrize("adapter", ADAPTERS, ids=ADAPTER_IDS)
@pytest.mark.parametrize("alg", ["none", "HS256", "ES256", "RS256"])
def test_algorithm_confusion_rejected(adapter: Any, alg: str) -> None:
    art = adapter.set_alg(adapter.genuine(), alg)
    _assert_coded_rejection(adapter.verify(art))


@pytest.mark.parametrize("adapter", [ADAPTERS[0], ADAPTERS[1]], ids=ADAPTER_IDS[:2])
def test_missing_algorithm_rejected(adapter: Any) -> None:
    """Applies to the two verifiers whose formats carry a mandatory alg field."""
    art = adapter.set_alg(adapter.genuine(), None)
    _assert_coded_rejection(adapter.verify(art))


@pytest.mark.parametrize("adapter", ADAPTERS, ids=ADAPTER_IDS)
def test_duplicate_key_json_rejected_at_ingress(adapter: Any) -> None:
    text = json.dumps(adapter.genuine())
    dup = '{"operation_id":"op-EVIL",' + text[1:]
    assert adapter.ingress(text) == json.loads(text)
    with pytest.raises(IngressRejected) as info:
        adapter.ingress(dup)
    assert info.value.code.endswith("DUPLICATE_KEY")


@pytest.mark.parametrize("adapter", ADAPTERS, ids=ADAPTER_IDS)
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e400"])
def test_non_finite_numbers_rejected_at_ingress(adapter: Any, literal: str) -> None:
    text = json.dumps(adapter.genuine())[:-1] + f',"x":{literal}}}'
    with pytest.raises(IngressRejected) as info:
        adapter.ingress(text)
    assert info.value.code.endswith("NON_FINITE_NUMBER")


@pytest.mark.parametrize("adapter", ADAPTERS, ids=ADAPTER_IDS)
def test_deep_nesting_rejected_with_code_object_and_text(adapter: Any) -> None:
    deep: Any = []
    for _ in range(10_000):
        deep = [deep]
    art = adapter.genuine()
    art["n"] = deep
    valid, code = adapter.verify(art)
    assert valid is False and code in adapter.nesting_codes, (valid, code)

    text = json.dumps(adapter.genuine())[:-1] + ',"n":' + "[" * 10_000 + "]" * 10_000 + "}"
    with pytest.raises(IngressRejected) as info:
        adapter.ingress(text)
    assert "NESTING" in info.value.code


@pytest.mark.parametrize("adapter", ADAPTERS, ids=ADAPTER_IDS)
def test_moderate_nesting_within_cap_still_verifies(adapter: Any) -> None:
    nested: Any = {"leaf": 1}
    for _ in range(40):
        nested = {"n": nested}
    art = adapter.genuine()
    if adapter.name == "aeib_offline_verifier":
        art["context"] = nested
        art = adapter.resign(art)
    else:
        body = {k: v for k, v in art.items() if k != adapter.sig_field}
        body["context"] = nested
        art = adapter.sign(body)
    valid, code = adapter.verify(art)
    assert valid is True, code


# ------------------------------------------------------------------------------
# JCS parity on the A1 payload set (200 seeded random + edge)
# ------------------------------------------------------------------------------

def _a1_payloads() -> List[Any]:
    smile = chr(0x1F600)
    edge = [
        {smile: 1, chr(0xFFFF): 2},
        {chr(0x20AC): 1, "\r": 2, smile: 3, "1": 4, chr(0xF6): 5},
        {"a": 1e21}, {"a": 1e-7}, {"a": 1e20}, {"a": 5e-324},
        {"a": 1.7976931348623157e308}, {"a": 0.1 + 0.2}, {"a": -0.0},
        {"a": 333333333.33333329}, {"a": 9007199254740993},
        {"s": "\u2028\u2029\x7f\x1f"}, {"s": "e\u0301"},
    ]
    pool = ["a", "B", "z", "\u00e9", "e\u0301", chr(0x20AC), chr(0xFFFF), smile, chr(0x10000), "\x01", '"', "\\", "\u2028"]
    rng = random.Random(42)

    def rnd_str() -> str:
        return "".join(rng.choice(pool) for _ in range(rng.randint(0, 5)))

    def rnd_val(d: int = 0) -> Any:
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

    return edge + [{"k": rnd_val()} for _ in range(200)]


JCS_IMPLS: Dict[str, Callable[[Any], bytes]] = {
    "aeib_offline_verifier.canonical_json_v1": A.canonical_json_v1,
    "standalone_receipt_verifier.encode_jcs": S.encode_jcs,
    "standalone_offline_verifier.encode_jcs": O.encode_jcs,
}


@pytest.mark.parametrize("impl_name", sorted(JCS_IMPLS))
def test_jcs_bytes_equal_reference_on_a1_payloads(impl_name: str) -> None:
    payloads = _a1_payloads()
    assert len(payloads) == 213
    impl = JCS_IMPLS[impl_name]
    divergences = [p for p in payloads if impl(p) != reference_encode_jcs(p)]
    assert divergences == []


def test_point_screens_agree_across_family() -> None:
    """The three copied point screens classify the same encodings identically."""
    rng = random.Random(7)
    samples = WEAK_KEYS + [GENUINE_PUB_RAW] + [bytes(rng.getrandbits(8) for _ in range(32)) for _ in range(64)]
    samples += [(P_FIELD + k).to_bytes(32, "little") for k in range(0, 18, 3)]
    for enc in samples:
        a = A.ed25519_point_weakness(enc)
        s = S.ed25519_point_weakness(enc)
        o = O.ed25519_public_key_weakness(enc)
        assert a == s == o, (enc.hex(), a, s, o)
    assert all(A.ed25519_point_weakness(k) is not None for k in WEAK_KEYS)
    assert A.ed25519_point_weakness(GENUINE_PUB_RAW) is None
