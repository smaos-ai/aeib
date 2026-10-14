"""
tests/test_tier3_rfc9052_cose_interop.py
Comprehensive test suite for RFC 9052 COSE_Sign1 Profile and RFC 8949 CBOR Codec.
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Boundary (AEIB).

Evaluates:
  1. RFC 8949 deterministic CBOR round-trip encoding and decoding across major types:
     - Major 0 (uint), Major 1 (nint), Major 2 (bstr), Major 3 (tstr)
     - Major 4 (array), Major 5 (map with strict canonical key sorting), Major 6 (tag), Major 7 (simple/bool/nil/float)
     - Bounds checking, truncation detection, non-canonical rejection, duplicate key rejection.
  2. RFC 9052 COSE_Sign1 envelope generation and verification with real Ed25519 keys.
  3. Non-empty external authenticated data (AAD) binding and rejection of mismatched AAD.
  4. Falsification matrix (fail-closed evaluation):
     - 1-bit signature corruption -> rejected.
     - Payload tampering -> rejected.
     - Protected header tampering -> rejected.
     - Wrong public key -> rejected.
     - Algorithm confusion (e.g. alg: -7) -> rejected.
     - Unrecognized critical header parameter -> rejected.
     - Corrupted / truncated CBOR envelopes -> rejected.
  5. RFC 8785 JCS integration:
     - Signing actual AEIB receipt structures with encode_jcs.
     - Content-Addressed Action Identifier (CAID) derivation.
     - Exact byte equality verification.

Operates under the stated model: Pure Python stdlib cryptographic validation without mocks.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.jcs_canonicalizer import encode_jcs

# Load rfc9052_cose_profile module dynamically from v1.1-roadmap
REPO_ROOT = Path(__file__).resolve().parents[1]
ROADMAP_PATH = REPO_ROOT / "v1.1-roadmap" / "rfc9052_cose_profile.py"

spec = importlib.util.spec_from_file_location("rfc9052_cose_profile", ROADMAP_PATH)
assert spec is not None and spec.loader is not None
cose_mod = importlib.util.module_from_spec(spec)
sys.modules["rfc9052_cose_profile"] = cose_mod
spec.loader.exec_module(cose_mod)

RFC8949CBOR = cose_mod.RFC8949CBOR
CBORTag = cose_mod.CBORTag
CBORSimpleValue = cose_mod.CBORSimpleValue
CBORUndefined = cose_mod.CBORUndefined
RFC9052CoseSigner = cose_mod.RFC9052CoseSigner
RFC9052CoseVerifier = cose_mod.RFC9052CoseVerifier
CoseVerificationResult = cose_mod.CoseVerificationResult
COSE_HEADER_ALG = cose_mod.COSE_HEADER_ALG
COSE_HEADER_CRIT = cose_mod.COSE_HEADER_CRIT
COSE_HEADER_CONTENT_TYPE = cose_mod.COSE_HEADER_CONTENT_TYPE
COSE_HEADER_KID = cose_mod.COSE_HEADER_KID
COSE_ALG_EDDSA = cose_mod.COSE_ALG_EDDSA
COSE_TAG_SIGN1 = cose_mod.COSE_TAG_SIGN1


# ============================================================================
# Section 1: RFC 8949 CBOR Round-Trip and Boundary Tests
# ============================================================================


class TestRFC8949CBORCodec:
    """Evaluates RFC 8949 deterministic CBOR encoding and decoding."""

    @pytest.mark.parametrize(
        "val",
        [
            0,
            1,
            23,
            24,
            255,
            256,
            65535,
            65536,
            4294967295,
            4294967296,
            18446744073709551615,
        ],
    )
    def test_cbor_uint_roundtrip(self, val: int) -> None:
        """Evaluates unsigned integers roundtrip with smallest argument encoding."""
        encoded = RFC8949CBOR.encode(val)
        decoded = RFC8949CBOR.decode(encoded)
        assert decoded == val

    @pytest.mark.parametrize(
        "val",
        [
            -1,
            -10,
            -24,
            -25,
            -256,
            -257,
            -65536,
            -65537,
            -4294967296,
            -18446744073709551616,
        ],
    )
    def test_cbor_nint_roundtrip(self, val: int) -> None:
        """Evaluates negative integers (major type 1) roundtrip."""
        encoded = RFC8949CBOR.encode(val)
        decoded = RFC8949CBOR.decode(encoded)
        assert decoded == val

    def test_cbor_integer_out_of_range(self) -> None:
        """Evaluates rejection of integers beyond 64-bit limits."""
        with pytest.raises(ValueError):
            RFC8949CBOR.encode(18446744073709551616)
        with pytest.raises(ValueError):
            RFC8949CBOR.encode(-18446744073709551617)

    @pytest.mark.parametrize(
        "val",
        [
            b"",
            b"hello world",
            bytes(range(256)),
            b"\x00\xff" * 500,
        ],
    )
    def test_cbor_bstr_roundtrip(self, val: bytes) -> None:
        """Evaluates byte strings (major type 2) roundtrip."""
        encoded = RFC8949CBOR.encode(val)
        decoded = RFC8949CBOR.decode(encoded)
        assert decoded == val

    @pytest.mark.parametrize(
        "val",
        [
            "",
            "hello world",
            "SovereignNexus AEIB",
            "UTF-8 test: \u00e9\u00e8\u00e0 \u4e2d\u6587 \U0001f510\u26a1",
        ],
    )
    def test_cbor_tstr_roundtrip(self, val: str) -> None:
        """Evaluates text strings (major type 3) roundtrip."""
        encoded = RFC8949CBOR.encode(val)
        decoded = RFC8949CBOR.decode(encoded)
        assert decoded == val

    def test_cbor_array_roundtrip(self) -> None:
        """Evaluates nested and heterogeneous arrays (major type 4)."""
        data = [0, -42, "string", b"bytes", True, False, None, [1, 2, [3, 4]]]
        encoded = RFC8949CBOR.encode(data)
        decoded = RFC8949CBOR.decode(encoded)
        assert decoded == data

    def test_cbor_tag_roundtrip(self) -> None:
        """Evaluates tagged data items (major type 6)."""
        tag = CBORTag(tag=18, value=["Signature1", b"", b"", b"payload"])
        encoded = RFC8949CBOR.encode(tag)
        decoded = RFC8949CBOR.decode(encoded)
        assert isinstance(decoded, CBORTag)
        assert decoded.tag == 18
        assert decoded.value == ["Signature1", b"", b"", b"payload"]

    def test_cbor_simple_values_and_floats(self) -> None:
        """Evaluates simple values and IEEE 754 floats (major type 7)."""
        assert RFC8949CBOR.decode(RFC8949CBOR.encode(False)) is False
        assert RFC8949CBOR.decode(RFC8949CBOR.encode(True)) is True
        assert RFC8949CBOR.decode(RFC8949CBOR.encode(None)) is None

        f_val = 3.141592653589793
        encoded_f = RFC8949CBOR.encode(f_val)
        decoded_f = RFC8949CBOR.decode(encoded_f)
        assert decoded_f == f_val

        # Undefined value
        encoded_undef = RFC8949CBOR.encode(CBORUndefined())
        decoded_undef = RFC8949CBOR.decode(encoded_undef)
        assert isinstance(decoded_undef, CBORUndefined)

    def test_cbor_map_canonical_key_sorting(self) -> None:
        """
        Evaluates RFC 8949 Section 4.2.1 deterministic map sorting:
        Shorter length encoded keys sort earlier; if lengths are equal,
        lexicographical byte order applies.
        """
        # Map with keys of differing lengths and byte values
        # Key 1 -> 0x01 (len 1)
        # Key -8 -> 0x27 (len 1)
        # Key 24 -> 0x1818 (len 2)
        # Key "a" -> 0x6161 (len 2)
        # Key "aa" -> 0x626161 (len 3)
        mapping = {
            "aa": "three_bytes",
            24: "two_bytes_int",
            1: "one_byte_int",
            "a": "two_bytes_str",
            -8: "one_byte_neg",
        }
        encoded = RFC8949CBOR.encode(mapping)

        # Decode and verify data integrity
        decoded = RFC8949CBOR.decode(encoded)
        assert decoded == mapping

        # Verify exact sequence of keys in encoded byte stream
        # Initial byte is map of 5 items: 0xa5
        assert encoded[0] == 0xA5

        # Key 1 (0x01) must appear before Key -8 (0x27)
        # Key 24 (0x1818) and Key "a" (0x6161) must appear after length 1 keys
        pos_1 = encoded.find(b"\x01")
        pos_neg8 = encoded.find(b"\x27")
        pos_24 = encoded.find(b"\x18\x18")
        pos_a = encoded.find(b"\x61a")
        pos_aa = encoded.find(b"\x62aa")

        assert pos_1 < pos_neg8 < pos_24 < pos_a < pos_aa

    def test_cbor_rejection_of_non_canonical_int(self) -> None:
        """Evaluates rejection of integer encoded with longer argument than necessary."""
        # 1 encoded as 2-byte: 0x18 (info 24) followed by 0x01
        non_canonical_1 = b"\x18\x01"
        with pytest.raises(ValueError, match="Non-canonical integer encoding"):
            RFC8949CBOR.decode(non_canonical_1, deterministic=True)

    def test_cbor_rejection_of_unsorted_map(self) -> None:
        """Evaluates rejection of map with non-canonically sorted keys."""
        # Build map with 2 keys: "b" (0x6162) followed by "a" (0x6161)
        unsorted_map_bytes = b"\xa2\x61b\x01\x61a\x02"
        with pytest.raises(ValueError, match="Non-canonical map key sorting"):
            RFC8949CBOR.decode(unsorted_map_bytes, deterministic=True)

    def test_cbor_rejection_of_duplicate_map_keys(self) -> None:
        """Evaluates rejection of duplicate keys in decoded map."""
        # Map with duplicate key 1: {1: 10, 1: 20}
        dup_bytes = b"\xa2\x01\x0a\x01\x14"
        with pytest.raises(ValueError):
            RFC8949CBOR.decode(dup_bytes)

    def test_cbor_rejection_of_indefinite_length(self) -> None:
        """Evaluates rejection of indefinite-length items (info 31) in deterministic profile."""
        indefinite_array = b"\x9f\x01\x02\xff"  # [_ 1, 2, break]
        with pytest.raises(ValueError, match="Indefinite-length encoding"):
            RFC8949CBOR.decode(indefinite_array, deterministic=True)

    def test_cbor_rejection_of_truncated_buffer(self) -> None:
        """Evaluates fail-closed handling on truncated buffers."""
        with pytest.raises(ValueError, match="Unexpected end of CBOR buffer"):
            RFC8949CBOR.decode(b"")
        with pytest.raises(ValueError, match="Truncated byte string"):
            RFC8949CBOR.decode(b"\x45\x01\x02")  # bstr of 5 bytes, only 2 provided

    def test_cbor_rejection_of_extraneous_trailing_bytes(self) -> None:
        """Evaluates fail-closed handling on trailing garbage bytes."""
        valid_with_junk = RFC8949CBOR.encode("valid") + b"\x00\x00\x00"
        with pytest.raises(ValueError, match="Extraneous bytes"):
            RFC8949CBOR.decode(valid_with_junk)


# ============================================================================
# Section 2: RFC 9052 COSE_Sign1 Signing and Verification
# ============================================================================


class TestRFC9052CoseSign1Profile:
    """Evaluates RFC 9052 COSE_Sign1 signing and independent verification."""

    def test_cose_sign1_roundtrip_valid(self) -> None:
        """Evaluates standard COSE_Sign1 envelope signing and verification."""
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        key_id = "agent-signer-001"

        signer = RFC9052CoseSigner(private_key, key_id=key_id)
        payload = b"evaluated payload for integrity test"

        envelope_bytes = signer.sign(payload)
        assert isinstance(envelope_bytes, bytes)

        # Independent verifier
        result = RFC9052CoseVerifier.verify(envelope_bytes, public_key)
        assert result.valid is True
        assert result.error is None
        assert result.payload == payload
        assert result.kid == key_id
        assert result.alg == COSE_ALG_EDDSA
        assert result.protected_headers == {COSE_HEADER_ALG: COSE_ALG_EDDSA}
        assert result.unprotected_headers == {COSE_HEADER_KID: key_id.encode("utf-8")}

    def test_cose_sign1_with_external_aad(self) -> None:
        """Evaluates signing and verification bound to external AAD."""
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        signer = RFC9052CoseSigner(private_key, key_id="signer-aad")

        payload = b"action command payload"
        external_aad = b"urn:aeib:merkle:checkpoint:epoch42"

        envelope = signer.sign(payload, external_aad=external_aad)

        # Matching AAD succeeds
        res_ok = RFC9052CoseVerifier.verify(
            envelope, public_key, expected_external_aad=external_aad
        )
        assert res_ok.valid is True
        assert res_ok.payload == payload

        # Mismatched AAD rejected fail-closed
        res_tampered_aad = RFC9052CoseVerifier.verify(
            envelope, public_key, expected_external_aad=b"urn:aeib:merkle:wrong"
        )
        assert res_tampered_aad.valid is False
        assert "signature" in (res_tampered_aad.error or "").lower()

        # Missing expected AAD rejected fail-closed
        res_missing_aad = RFC9052CoseVerifier.verify(
            envelope, public_key, expected_external_aad=b""
        )
        assert res_missing_aad.valid is False


# ============================================================================
# Section 3: Falsification Matrix (Tamper & Mismatch Resistance)
# ============================================================================


class TestRFC9052FalsificationMatrix:
    """Evaluates fail-closed rejection of tampered envelopes and confused parameters."""

    @pytest.fixture
    def setup_envelope(self) -> Dict[str, Any]:
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key()
        signer = RFC9052CoseSigner(priv, key_id="key-falsification")
        payload = b"critical execution dispatch ticket"
        aad = b"urn:aeib:domain:v1"
        envelope = signer.sign(payload, external_aad=aad)
        return {
            "priv": priv,
            "pub": pub,
            "signer": signer,
            "payload": payload,
            "aad": aad,
            "envelope": envelope,
        }

    def test_falsify_tampered_signature_1bit(self, setup_envelope: Dict[str, Any]) -> None:
        """Evaluates fail-closed rejection when a single bit in the 64-byte signature is flipped."""
        envelope = bytearray(setup_envelope["envelope"])
        # Signature is at the tail of the envelope
        envelope[-1] ^= 0x01

        result = RFC9052CoseVerifier.verify(
            bytes(envelope), setup_envelope["pub"], expected_external_aad=setup_envelope["aad"]
        )
        assert result.valid is False
        assert result.error is not None
        assert "signature" in result.error.lower()

    def test_falsify_tampered_payload(self, setup_envelope: Dict[str, Any]) -> None:
        """Evaluates fail-closed rejection when payload bytes are altered."""
        cbor_obj = RFC8949CBOR.decode(setup_envelope["envelope"])
        assert isinstance(cbor_obj, CBORTag)
        arr = list(cbor_obj.value)

        # Alter payload
        arr[2] = b"tampered unauthorized payload"
        tampered_env = RFC8949CBOR.encode(CBORTag(tag=COSE_TAG_SIGN1, value=arr))

        result = RFC9052CoseVerifier.verify(
            tampered_env, setup_envelope["pub"], expected_external_aad=setup_envelope["aad"]
        )
        assert result.valid is False
        assert result.error is not None

    def test_falsify_tampered_protected_header(self, setup_envelope: Dict[str, Any]) -> None:
        """Evaluates fail-closed rejection when protected header bytes are altered."""
        cbor_obj = RFC8949CBOR.decode(setup_envelope["envelope"])
        arr = list(cbor_obj.value)

        # Inject extra protected header attribute {1: -8, 3: "application/json"}
        tampered_protected = {COSE_HEADER_ALG: COSE_ALG_EDDSA, COSE_HEADER_CONTENT_TYPE: 50}
        arr[0] = RFC8949CBOR.encode(tampered_protected)
        tampered_env = RFC8949CBOR.encode(CBORTag(tag=COSE_TAG_SIGN1, value=arr))

        result = RFC9052CoseVerifier.verify(
            tampered_env, setup_envelope["pub"], expected_external_aad=setup_envelope["aad"]
        )
        assert result.valid is False
        assert result.error is not None

    def test_falsify_wrong_public_key(self, setup_envelope: Dict[str, Any]) -> None:
        """Evaluates rejection when envelope is verified with an unrelated public key."""
        wrong_pub = Ed25519PrivateKey.generate().public_key()
        result = RFC9052CoseVerifier.verify(
            setup_envelope["envelope"], wrong_pub, expected_external_aad=setup_envelope["aad"]
        )
        assert result.valid is False
        assert "signature" in (result.error or "").lower()

    def test_falsify_algorithm_confusion(self, setup_envelope: Dict[str, Any]) -> None:
        """Evaluates rejection when algorithm is changed to non-EdDSA (e.g. -7 ES256)."""
        priv = setup_envelope["priv"]
        signer = RFC9052CoseSigner(priv, key_id="key-alg-confuse")

        # Manually sign with alg: -7 (ES256) in protected header
        envelope_confused = signer.sign(
            b"test", protected_extra={COSE_HEADER_ALG: -7}
        )

        result = RFC9052CoseVerifier.verify(envelope_confused, setup_envelope["pub"])
        assert result.valid is False
        assert "Unsupported algorithm" in (result.error or "")

    def test_falsify_algorithm_in_both_headers(self, setup_envelope: Dict[str, Any]) -> None:
        """Evaluates rejection if alg appears in both protected and unprotected headers."""
        priv = setup_envelope["priv"]
        signer = RFC9052CoseSigner(priv, key_id="key-dup-alg")
        envelope = signer.sign(
            b"test", unprotected_extra={COSE_HEADER_ALG: COSE_ALG_EDDSA}
        )

        result = RFC9052CoseVerifier.verify(envelope, setup_envelope["pub"])
        assert result.valid is False
        assert "MUST NOT appear in both" in (result.error or "")

    def test_falsify_unrecognized_critical_header(self, setup_envelope: Dict[str, Any]) -> None:
        """Evaluates fail-closed rejection of unrecognized critical headers (crit label 2)."""
        priv = setup_envelope["priv"]
        signer = RFC9052CoseSigner(priv, key_id="key-crit")

        # Set crit to include unknown header parameter label 999
        envelope = signer.sign(
            b"payload",
            protected_extra={COSE_HEADER_CRIT: [999], 999: "unknown critical attribute"},
        )

        result = RFC9052CoseVerifier.verify(envelope, setup_envelope["pub"])
        assert result.valid is False
        assert "Unrecognized critical header" in (result.error or "")

    def test_falsify_crit_in_unprotected_header(self) -> None:
        """Evaluates rejection if crit parameter occurs in unprotected headers."""
        priv = Ed25519PrivateKey.generate()
        signer = RFC9052CoseSigner(priv, key_id="key-crit-unprot")
        envelope = signer.sign(
            b"test", unprotected_extra={COSE_HEADER_CRIT: [COSE_HEADER_CONTENT_TYPE]}
        )

        result = RFC9052CoseVerifier.verify(envelope, priv.public_key())
        assert result.valid is False
        assert "crit) MUST NOT occur in unprotected" in (result.error or "")

    def test_falsify_corrupt_envelope_cbor(self) -> None:
        """Evaluates fail-closed handling on non-CBOR or corrupted envelopes."""
        pub = Ed25519PrivateKey.generate().public_key()
        res1 = RFC9052CoseVerifier.verify(b"not-cbor-data", pub)
        assert res1.valid is False
        assert "Malformed CBOR" in (res1.error or "")

        res2 = RFC9052CoseVerifier.verify(RFC8949CBOR.encode([1, 2, 3]), pub)
        assert res2.valid is False
        assert "must be CBORTag with tag 18" in (res2.error or "")


# ============================================================================
# Section 4: RFC 8785 JCS Receipt Integration
# ============================================================================


class TestRFC8785JcsIntegration:
    """Evaluates seamless interoperability between RFC 8785 JCS receipts and RFC 9052 COSE_Sign1."""

    def test_sign_and_verify_jcs_receipt(self) -> None:
        """
        Signs an actual AEIB continuity receipt dictionary with encode_jcs,
        evaluates Content-Addressed Action Identifier (CAID), and verifies
        byte-for-byte exact payload reproduction.
        """
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        key_id = "urn:aeib:key:operator:us-east-1"

        receipt_dict: Dict[str, Any] = {
            "receiptId": "rcpt-2026-10-14-001",
            "epoch": 42,
            "disposition": "COMMITTED",
            "policyEpoch": 1,
            "target": "https://api.internal.smaos.net/dispatch",
            "action": "TRANSFER_ASSET",
            "spendEur": 150,
            "metadata": {
                "approver": "principal-alpha",
                "merkleRoot": "0x1234567890abcdef",
                "verifiedAxes": ["RFC8785_JCS", "RFC9052_COSE_SIGN1", "ED25519"],
            },
        }

        # Expected canonical JCS bytes and CAID
        expected_canonical_bytes = encode_jcs(receipt_dict)
        expected_caid = hashlib.sha256(expected_canonical_bytes).hexdigest()

        signer = RFC9052CoseSigner(private_key, key_id=key_id)
        external_aad = b"urn:aeib:receipt:aad:v1"

        envelope_cbor_bytes, derived_caid = signer.sign_receipt(
            receipt_dict, external_aad=external_aad
        )

        assert derived_caid == expected_caid
        assert isinstance(envelope_cbor_bytes, bytes)

        # Verify envelope using independent verifier
        result = RFC9052CoseVerifier.verify(
            envelope_cbor_bytes, public_key, expected_external_aad=external_aad
        )

        assert result.valid is True
        assert result.error is None
        assert result.kid == key_id
        assert result.alg == COSE_ALG_EDDSA

        # Payload byte equality with canonical RFC 8785 JCS
        assert result.payload == expected_canonical_bytes

        # Re-derive CAID from verified payload bytes
        verified_caid = hashlib.sha256(result.payload).hexdigest()
        assert verified_caid == expected_caid
