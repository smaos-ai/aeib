"""
v1.1-roadmap/rfc9052_cose_profile.py — RFC 9052 COSE_Sign1 Profile & RFC 8949 CBOR Verifier.
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Boundary (AEIB).

Tier 3.1 Profile Delivery:
Enforces standard RFC 9052 COSE_Sign1 envelope structure and RFC 8949 deterministic CBOR
for cross-system verification without third-party codec dependencies:
  1. Pure Python stdlib RFC 8949 deterministic CBOR encoder and decoder.
  2. RFC 9052 COSE_Sign1 profile using Ed25519 (alg: -8, COSE_ALG_EDDSA).
  3. Strict fail-closed verification of Sig_structure, external AAD, critical headers,
     and tamper detection evaluated under the stated model.
  4. Integration with RFC 8785 JSON Canonicalization Scheme (JCS) receipts.

Operates under the stated model: Prototype implementation evaluated against deterministic vectors.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs


# ============================================================================
# RFC 9052 & RFC 8152 Constants
# ============================================================================

COSE_HEADER_ALG = 1
COSE_HEADER_CRIT = 2
COSE_HEADER_CONTENT_TYPE = 3
COSE_HEADER_KID = 4

COSE_ALG_EDDSA = -8  # Ed25519 per RFC 9053 Section 2.2 / RFC 8152 Table 5
COSE_TAG_SIGN1 = 18  # Tag 18 identifies COSE_Sign1 per RFC 9052 Section 4.2


# ============================================================================
# RFC 8949 CBOR Data Types & Structures
# ============================================================================


@dataclass(frozen=True)
class CBORTag:
    """Represents a tagged CBOR item (Major Type 6)."""

    tag: int
    value: Any


@dataclass(frozen=True)
class CBORSimpleValue:
    """Represents a CBOR simple value (Major Type 7)."""

    value: int


@dataclass(frozen=True)
class CBORUndefined:
    """Represents the CBOR undefined value (Simple value 23)."""

    pass


class RFC8949CBOR:
    """
    Pure Python stdlib RFC 8949 deterministic CBOR encoder and decoder.
    Implements Core Deterministic Encoding Requirements per RFC 8949 Section 4.2.1:
      - Smallest argument encoding for integers, lengths, and tags.
      - Canonical map key sorting by length of encoded key bytes, then lexicographical order.
      - Rejection of indefinite-length items, non-canonical encodings, and duplicate keys.
    """

    @staticmethod
    def _encode_type_and_arg(major: int, val: int) -> bytes:
        if val < 0 or val > 0xFFFFFFFFFFFFFFFF:
            raise ValueError(f"CBOR integer argument out of range (0..2^64-1): {val}")
        prefix = major << 5
        if val <= 23:
            return bytes([prefix | val])
        elif val <= 0xFF:
            return bytes([prefix | 24, val])
        elif val <= 0xFFFF:
            return bytes([prefix | 25]) + val.to_bytes(2, "big")
        elif val <= 0xFFFFFFFF:
            return bytes([prefix | 26]) + val.to_bytes(4, "big")
        else:
            return bytes([prefix | 27]) + val.to_bytes(8, "big")

    @classmethod
    def encode(cls, obj: Any) -> bytes:
        """Encodes a Python object to RFC 8949 deterministic CBOR bytes."""
        if obj is None:
            return bytes([7 << 5 | 22])
        if isinstance(obj, bool):
            return bytes([7 << 5 | (21 if obj else 20)])
        if isinstance(obj, int):
            if obj >= 0:
                return cls._encode_type_and_arg(0, obj)
            else:
                return cls._encode_type_and_arg(1, -1 - obj)
        if isinstance(obj, float):
            return bytes([7 << 5 | 27]) + struct.pack(">d", obj)
        if isinstance(obj, (bytes, bytearray)):
            raw_b = bytes(obj)
            return cls._encode_type_and_arg(2, len(raw_b)) + raw_b
        if isinstance(obj, str):
            raw_s = obj.encode("utf-8")
            return cls._encode_type_and_arg(3, len(raw_s)) + raw_s
        if isinstance(obj, CBORTag):
            return cls._encode_type_and_arg(6, obj.tag) + cls.encode(obj.value)
        if isinstance(obj, (list, tuple)):
            header = cls._encode_type_and_arg(4, len(obj))
            return header + b"".join(cls.encode(item) for item in obj)
        if isinstance(obj, dict):
            encoded_pairs: List[Tuple[bytes, bytes]] = []
            seen_keys = set()
            for k, v in obj.items():
                k_bytes = cls.encode(k)
                if k_bytes in seen_keys:
                    raise ValueError(f"Duplicate encoded key in map: {k_bytes!r}")
                seen_keys.add(k_bytes)
                v_bytes = cls.encode(v)
                encoded_pairs.append((k_bytes, v_bytes))

            # RFC 8949 Section 4.2.1: Shorter length first, then lexicographical order
            encoded_pairs.sort(key=lambda pair: (len(pair[0]), pair[0]))

            header = cls._encode_type_and_arg(5, len(encoded_pairs))
            body = b"".join(k_b + v_b for k_b, v_b in encoded_pairs)
            return header + body
        if isinstance(obj, CBORSimpleValue):
            val = obj.value
            if val < 0 or val > 255:
                raise ValueError(f"CBOR simple value out of range (0..255): {val}")
            if val <= 23:
                return bytes([7 << 5 | val])
            return bytes([7 << 5 | 24, val])
        if isinstance(obj, CBORUndefined):
            return bytes([7 << 5 | 23])

        raise TypeError(f"Type {type(obj).__name__} is not CBOR serializable")

    @classmethod
    def decode_from(
        cls, data: bytes, offset: int = 0, deterministic: bool = True
    ) -> Tuple[Any, int]:
        """
        Decodes a single CBOR item from data starting at offset.
        Returns a tuple of (decoded_value, next_offset).
        """
        if offset >= len(data):
            raise ValueError(f"Unexpected end of CBOR buffer at offset {offset}")

        ib = data[offset]
        major = (ib >> 5) & 0x07
        info = ib & 0x1F
        offset += 1

        # Handle Major Type 7 float and simple value dispatch
        if major == 7:
            if info < 20:
                return CBORSimpleValue(info), offset
            elif info == 20:
                return False, offset
            elif info == 21:
                return True, offset
            elif info == 22:
                return None, offset
            elif info == 23:
                return CBORUndefined(), offset
            elif info == 24:
                if offset + 1 > len(data):
                    raise ValueError(f"Truncated 1-byte simple value at offset {offset}")
                val = data[offset]
                offset += 1
                if deterministic and val < 32:
                    raise ValueError(
                        f"Non-canonical simple value {val} at offset {offset - 1}"
                    )
                return CBORSimpleValue(val), offset
            elif info == 25:
                if offset + 2 > len(data):
                    raise ValueError(f"Truncated 16-bit float at offset {offset}")
                flt = struct.unpack(">e", data[offset : offset + 2])[0]
                offset += 2
                return flt, offset
            elif info == 26:
                if offset + 4 > len(data):
                    raise ValueError(f"Truncated 32-bit float at offset {offset}")
                flt = struct.unpack(">f", data[offset : offset + 4])[0]
                offset += 4
                return flt, offset
            elif info == 27:
                if offset + 8 > len(data):
                    raise ValueError(f"Truncated 64-bit float at offset {offset}")
                flt = struct.unpack(">d", data[offset : offset + 8])[0]
                offset += 8
                return flt, offset
            elif info == 31:
                raise ValueError("Indefinite-length simple value (info 31) prohibited")
            else:
                raise ValueError(f"Reserved major 7 additional information: {info}")

        # Argument parsing for Major Types 0..6
        if info < 24:
            val = info
        elif info == 24:
            if offset + 1 > len(data):
                raise ValueError(f"Truncated CBOR 1-byte argument at offset {offset}")
            val = data[offset]
            offset += 1
            if deterministic and val < 24:
                raise ValueError(
                    f"Non-canonical integer encoding: {val} should be encoded directly in initial byte"
                )
        elif info == 25:
            if offset + 2 > len(data):
                raise ValueError(f"Truncated CBOR 2-byte argument at offset {offset}")
            val = int.from_bytes(data[offset : offset + 2], "big")
            offset += 2
            if deterministic and val <= 0xFF:
                raise ValueError(
                    f"Non-canonical integer encoding: {val} should be encoded in 1 byte"
                )
        elif info == 26:
            if offset + 4 > len(data):
                raise ValueError(f"Truncated CBOR 4-byte argument at offset {offset}")
            val = int.from_bytes(data[offset : offset + 4], "big")
            offset += 4
            if deterministic and val <= 0xFFFF:
                raise ValueError(
                    f"Non-canonical integer encoding: {val} should be encoded in 2 bytes"
                )
        elif info == 27:
            if offset + 8 > len(data):
                raise ValueError(f"Truncated CBOR 8-byte argument at offset {offset}")
            val = int.from_bytes(data[offset : offset + 8], "big")
            offset += 8
            if deterministic and val <= 0xFFFFFFFF:
                raise ValueError(
                    f"Non-canonical integer encoding: {val} should be encoded in 4 bytes"
                )
        elif info == 31:
            raise ValueError(
                f"Indefinite-length encoding (info 31) is prohibited in deterministic CBOR at offset {offset - 1}"
            )
        else:
            raise ValueError(f"Reserved additional information {info} at offset {offset - 1}")

        if major == 0:
            return val, offset
        elif major == 1:
            return -1 - val, offset
        elif major == 2:
            if offset + val > len(data):
                raise ValueError(
                    f"Truncated byte string: needed {val} bytes, have {len(data) - offset}"
                )
            res_b = data[offset : offset + val]
            offset += val
            return res_b, offset
        elif major == 3:
            if offset + val > len(data):
                raise ValueError(
                    f"Truncated text string: needed {val} bytes, have {len(data) - offset}"
                )
            raw_s = data[offset : offset + val]
            offset += val
            try:
                decoded_s = raw_s.decode("utf-8")
            except UnicodeDecodeError as e:
                raise ValueError(f"Invalid UTF-8 in CBOR text string: {e}")
            return decoded_s, offset
        elif major == 4:
            items: List[Any] = []
            for _ in range(val):
                item, offset = cls.decode_from(data, offset, deterministic=deterministic)
                items.append(item)
            return items, offset
        elif major == 5:
            mapping: Dict[Any, Any] = {}
            prev_key_sort: Optional[Tuple[int, bytes]] = None
            for _ in range(val):
                key_start = offset
                k, offset = cls.decode_from(data, offset, deterministic=deterministic)
                k_bytes = data[key_start:offset]
                k_sort = (len(k_bytes), k_bytes)
                if k in mapping:
                    raise ValueError(f"Duplicate key in CBOR map: {k!r}")
                if deterministic and prev_key_sort is not None:
                    if k_sort <= prev_key_sort:
                        raise ValueError(
                            f"Non-canonical map key sorting in CBOR map at offset {key_start}"
                        )
                prev_key_sort = k_sort
                v, offset = cls.decode_from(data, offset, deterministic=deterministic)
                mapping[k] = v
            return mapping, offset
        elif major == 6:
            tagged_val, offset = cls.decode_from(data, offset, deterministic=deterministic)
            return CBORTag(tag=val, value=tagged_val), offset

        raise ValueError(f"Unhandled major type {major}")

    @classmethod
    def decode(cls, data: bytes, deterministic: bool = True) -> Any:
        """
        Decodes a top-level CBOR byte buffer.
        Fails closed if unexpected trailing bytes remain.
        """
        val, offset = cls.decode_from(data, 0, deterministic=deterministic)
        if offset != len(data):
            raise ValueError(
                f"Extraneous bytes after CBOR item: {len(data) - offset} bytes remaining"
            )
        return val


# ============================================================================
# RFC 9052 COSE_Sign1 Profile & Verification Result
# ============================================================================


@dataclass(frozen=True)
class CoseVerificationResult:
    """Outcome of RFC 9052 COSE_Sign1 verification."""

    valid: bool
    payload: bytes
    kid: Optional[str]
    alg: int
    protected_headers: dict
    unprotected_headers: dict
    error: Optional[str]


class RFC9052CoseSigner:
    """
    RFC 9052 COSE_Sign1 signer utilizing Ed25519 (alg: -8).
    Produces standard tagged COSE_Sign1 envelopes (CBOR Tag 18).
    """

    def __init__(self, private_key: Ed25519PrivateKey, key_id: str) -> None:
        self.private_key = private_key
        self.key_id = key_id

    def sign(
        self,
        payload_bytes: bytes,
        external_aad: bytes = b"",
        protected_extra: Optional[Dict[int, Any]] = None,
        unprotected_extra: Optional[Dict[int, Any]] = None,
    ) -> bytes:
        """
        Generates an RFC 9052 COSE_Sign1 envelope containing:
          Tag 18 -> [protected: bstr, unprotected: map, payload: bstr, signature: bstr]
        Signature is calculated over Sig_structure:
          ["Signature1", protected_bytes, external_aad, payload_bytes]
        """
        # Protected headers: alg is mandatory per profile
        protected: Dict[int, Any] = {COSE_HEADER_ALG: COSE_ALG_EDDSA}
        if protected_extra:
            protected.update(protected_extra)

        protected_bytes = RFC8949CBOR.encode(protected) if protected else b""

        # Unprotected headers: kid injected by default
        unprotected: Dict[int, Any] = {}
        if self.key_id:
            unprotected[COSE_HEADER_KID] = (
                self.key_id.encode("utf-8")
                if isinstance(self.key_id, str)
                else bytes(self.key_id)
            )
        if unprotected_extra:
            unprotected.update(unprotected_extra)

        # Sig_structure per RFC 9052 Section 4.4
        sig_structure = ["Signature1", protected_bytes, external_aad, payload_bytes]
        to_be_signed = RFC8949CBOR.encode(sig_structure)

        # Real Ed25519 cryptographic signature (64 bytes)
        signature = self.private_key.sign(to_be_signed)

        envelope = CBORTag(
            tag=COSE_TAG_SIGN1,
            value=[protected_bytes, unprotected, payload_bytes, signature],
        )
        return RFC8949CBOR.encode(envelope)

    def sign_receipt(
        self, receipt_dict: Dict[str, Any], external_aad: bytes = b""
    ) -> Tuple[bytes, str]:
        """
        Serializes receipt_dict to RFC 8785 canonical JCS bytes, derives payload CAID,
        and returns (envelope_cbor_bytes, payload_caid).
        """
        payload_bytes = encode_jcs(receipt_dict)
        payload_caid = hashlib.sha256(payload_bytes).hexdigest()
        envelope_cbor_bytes = self.sign(payload_bytes, external_aad=external_aad)
        return envelope_cbor_bytes, payload_caid


class RFC9052CoseVerifier:
    """
    RFC 9052 COSE_Sign1 independent verifier.
    Enforces fail-closed cryptographic validation of Ed25519 signatures,
    strict algorithm matching (-8), tamper detection, and critical header processing.
    """

    @staticmethod
    def verify(
        envelope_bytes: bytes,
        public_key: Ed25519PublicKey,
        expected_external_aad: bytes = b"",
    ) -> CoseVerificationResult:
        """
        Verifies an RFC 9052 COSE_Sign1 envelope against an Ed25519 public key.
        Evaluated fail-closed under the stated model.
        """
        try:
            cbor_item = RFC8949CBOR.decode(envelope_bytes)
        except Exception as e:
            return CoseVerificationResult(
                valid=False,
                payload=b"",
                kid=None,
                alg=0,
                protected_headers={},
                unprotected_headers={},
                error=f"Malformed CBOR envelope: {e}",
            )

        if not isinstance(cbor_item, CBORTag) or cbor_item.tag != COSE_TAG_SIGN1:
            return CoseVerificationResult(
                valid=False,
                payload=b"",
                kid=None,
                alg=0,
                protected_headers={},
                unprotected_headers={},
                error=f"Envelope must be CBORTag with tag {COSE_TAG_SIGN1} (COSE_Sign1)",
            )

        arr = cbor_item.value
        if not isinstance(arr, (list, tuple)) or len(arr) != 4:
            return CoseVerificationResult(
                valid=False,
                payload=b"",
                kid=None,
                alg=0,
                protected_headers={},
                unprotected_headers={},
                error="COSE_Sign1 structure must contain exactly 4 elements: [protected, unprotected, payload, signature]",
            )

        protected_bytes, unprotected_headers, payload_bytes, signature_bytes = arr

        if not isinstance(protected_bytes, (bytes, bytearray)):
            return CoseVerificationResult(
                valid=False,
                payload=b"",
                kid=None,
                alg=0,
                protected_headers={},
                unprotected_headers={},
                error="Protected header must be a byte string",
            )
        if not isinstance(unprotected_headers, dict):
            return CoseVerificationResult(
                valid=False,
                payload=b"",
                kid=None,
                alg=0,
                protected_headers={},
                unprotected_headers={},
                error="Unprotected header must be a CBOR map",
            )
        if not isinstance(payload_bytes, (bytes, bytearray)):
            return CoseVerificationResult(
                valid=False,
                payload=b"",
                kid=None,
                alg=0,
                protected_headers={},
                unprotected_headers=unprotected_headers,
                error="Payload must be a byte string",
            )
        if not isinstance(signature_bytes, (bytes, bytearray)):
            return CoseVerificationResult(
                valid=False,
                payload=bytes(payload_bytes),
                kid=None,
                alg=0,
                protected_headers={},
                unprotected_headers=unprotected_headers,
                error="Signature must be a byte string",
            )

        protected_bytes = bytes(protected_bytes)
        payload_bytes = bytes(payload_bytes)
        signature_bytes = bytes(signature_bytes)

        # Parse protected header map
        if len(protected_bytes) == 0:
            protected_headers: Dict[Any, Any] = {}
        else:
            try:
                decoded_prot = RFC8949CBOR.decode(protected_bytes)
                if not isinstance(decoded_prot, dict):
                    return CoseVerificationResult(
                        valid=False,
                        payload=payload_bytes,
                        kid=None,
                        alg=0,
                        protected_headers={},
                        unprotected_headers=unprotected_headers,
                        error="Protected header byte string must decode to a CBOR map",
                    )
                protected_headers = decoded_prot
            except Exception as e:
                return CoseVerificationResult(
                    valid=False,
                    payload=payload_bytes,
                    kid=None,
                    alg=0,
                    protected_headers={},
                    unprotected_headers=unprotected_headers,
                    error=f"Failed to decode protected header CBOR: {e}",
                )

        # Algorithm validation
        if COSE_HEADER_ALG in protected_headers and COSE_HEADER_ALG in unprotected_headers:
            return CoseVerificationResult(
                valid=False,
                payload=payload_bytes,
                kid=None,
                alg=0,
                protected_headers=protected_headers,
                unprotected_headers=unprotected_headers,
                error="Algorithm parameter (alg) MUST NOT appear in both protected and unprotected headers",
            )

        alg = protected_headers.get(COSE_HEADER_ALG)
        if alg is None:
            alg = unprotected_headers.get(COSE_HEADER_ALG)

        if alg is None:
            return CoseVerificationResult(
                valid=False,
                payload=payload_bytes,
                kid=None,
                alg=0,
                protected_headers=protected_headers,
                unprotected_headers=unprotected_headers,
                error="Missing required algorithm parameter (alg)",
            )

        if alg != COSE_ALG_EDDSA:
            return CoseVerificationResult(
                valid=False,
                payload=payload_bytes,
                kid=None,
                alg=alg if isinstance(alg, int) else 0,
                protected_headers=protected_headers,
                unprotected_headers=unprotected_headers,
                error=f"Unsupported algorithm {alg}: only COSE_ALG_EDDSA (-8) evaluated under the stated model",
            )

        # Critical headers validation (RFC 9052 Section 3.1)
        if COSE_HEADER_CRIT in unprotected_headers:
            return CoseVerificationResult(
                valid=False,
                payload=payload_bytes,
                kid=None,
                alg=alg,
                protected_headers=protected_headers,
                unprotected_headers=unprotected_headers,
                error="Critical header parameter (crit) MUST NOT occur in unprotected headers",
            )

        if COSE_HEADER_CRIT in protected_headers:
            crit_list = protected_headers[COSE_HEADER_CRIT]
            if not isinstance(crit_list, (list, tuple)):
                return CoseVerificationResult(
                    valid=False,
                    payload=payload_bytes,
                    kid=None,
                    alg=alg,
                    protected_headers=protected_headers,
                    unprotected_headers=unprotected_headers,
                    error="Critical header parameter (crit) must be an array of header labels",
                )
            recognized_labels = {
                COSE_HEADER_ALG,
                COSE_HEADER_CRIT,
                COSE_HEADER_CONTENT_TYPE,
                COSE_HEADER_KID,
            }
            for label in crit_list:
                if label == COSE_HEADER_CRIT:
                    return CoseVerificationResult(
                        valid=False,
                        payload=payload_bytes,
                        kid=None,
                        alg=alg,
                        protected_headers=protected_headers,
                        unprotected_headers=unprotected_headers,
                        error="Critical header parameter (crit) must not list itself",
                    )
                if label not in recognized_labels:
                    return CoseVerificationResult(
                        valid=False,
                        payload=payload_bytes,
                        kid=None,
                        alg=alg,
                        protected_headers=protected_headers,
                        unprotected_headers=unprotected_headers,
                        error=f"Unrecognized critical header label: {label}",
                    )
                if label not in protected_headers:
                    return CoseVerificationResult(
                        valid=False,
                        payload=payload_bytes,
                        kid=None,
                        alg=alg,
                        protected_headers=protected_headers,
                        unprotected_headers=unprotected_headers,
                        error=f"Critical header label {label} is missing from protected headers",
                    )

        # Extract Key ID (kid)
        raw_kid = unprotected_headers.get(COSE_HEADER_KID)
        if raw_kid is None:
            raw_kid = protected_headers.get(COSE_HEADER_KID)

        kid_str: Optional[str] = None
        if isinstance(raw_kid, (bytes, bytearray)):
            kid_str = bytes(raw_kid).decode("utf-8", errors="replace")
        elif isinstance(raw_kid, str):
            kid_str = raw_kid
        elif raw_kid is not None:
            kid_str = str(raw_kid)

        # Ed25519 signature format validation
        if len(signature_bytes) != 64:
            return CoseVerificationResult(
                valid=False,
                payload=payload_bytes,
                kid=kid_str,
                alg=alg,
                protected_headers=protected_headers,
                unprotected_headers=unprotected_headers,
                error=f"Invalid Ed25519 signature length: {len(signature_bytes)} bytes (expected 64)",
            )

        # Reconstruct Sig_structure
        sig_structure = [
            "Signature1",
            protected_bytes,
            expected_external_aad,
            payload_bytes,
        ]
        try:
            to_be_signed = RFC8949CBOR.encode(sig_structure)
        except Exception as e:
            return CoseVerificationResult(
                valid=False,
                payload=payload_bytes,
                kid=kid_str,
                alg=alg,
                protected_headers=protected_headers,
                unprotected_headers=unprotected_headers,
                error=f"Failed to encode Sig_structure: {e}",
            )

        # Cryptographic verification using public key
        try:
            public_key.verify(signature_bytes, to_be_signed)
        except InvalidSignature:
            return CoseVerificationResult(
                valid=False,
                payload=payload_bytes,
                kid=kid_str,
                alg=alg,
                protected_headers=protected_headers,
                unprotected_headers=unprotected_headers,
                error="Invalid cryptographic signature over Sig_structure",
            )
        except Exception as e:
            return CoseVerificationResult(
                valid=False,
                payload=payload_bytes,
                kid=kid_str,
                alg=alg,
                protected_headers=protected_headers,
                unprotected_headers=unprotected_headers,
                error=f"Cryptographic verification error: {e}",
            )

        return CoseVerificationResult(
            valid=True,
            payload=payload_bytes,
            kid=kid_str,
            alg=alg,
            protected_headers=protected_headers,
            unprotected_headers=unprotected_headers,
            error=None,
        )
