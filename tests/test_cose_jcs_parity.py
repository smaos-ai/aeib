#!/usr/bin/env python3
r"""
test_cose_jcs_parity.py
Regression tests pinning the signer/verifier/canonicalizer to a single
canonicalization source of truth.

Why this exists:
  cose_signer.py and cose_verifier.py each carried their own inline
  `json.dumps(sort_keys=True)` copy of "JCS". That copy ordered object keys by
  Python code point instead of RFC 8785 Section 3.2.3 UTF-16 code units, and
  serialized floats per Python rules instead of ECMAScript 7.1.12.1 (it emitted
  "0.0" where JCS requires "0"). Signer and verifier agreed with each other but
  both disagreed with jcs_canonicalizer.encode_jcs, so any envelope touched by
  the canonicalizer pipeline would fail verification.

  These tests fail if the three ever diverge again.
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.cose_signer import generate_keypair, jcs_canonicalize as signer_jcs, sign_trust_passport
from src.cose_verifier import jcs_canonicalize as verifier_jcs, verify_trust_passport
from src.jcs_canonicalizer import encode_jcs


def _envelope_roundtrip(payload, key):
    """Sign then verify; returns True or the failure string."""
    envelope = sign_trust_passport(payload, key)
    try:
        return verify_trust_passport(envelope)
    except Exception as exc:  # surfaced as a failing assertion below
        return f"FAIL: {exc}"


class TestCanonicalizationParity(unittest.TestCase):
    """The three canonicalization entry points must be byte-identical."""

    PAYLOADS = [
        ("ascii", {"z": 1, "a": 2, "b": "x"}),
        ("floats", {"score": 0.0, "ratio": 1.5, "b": "x"}),
        ("integral floats", {"x": 1.0, "y": -0.0}),
        ("non-BMP keys", {"z": 1, "\U00010000": 2, "": 3, "a": 4}),
        ("utf16 vs codepoint order", {"": 1, "\U00010000": 2}),
        ("nested", {"o": {"b": [1, 2], "a": {"c": True}}, "n": None}),
        ("nfd string", {"s": "café", "a": 1}),
    ]

    def test_signer_verifier_canonicalizer_agree(self):
        for name, payload in self.PAYLOADS:
            with self.subTest(payload=name):
                self.assertEqual(signer_jcs(payload), verifier_jcs(payload), name)
                self.assertEqual(verifier_jcs(payload), encode_jcs(payload), name)

    def test_encoded_bytes_are_utf8_decodable(self):
        """
        canonical_payload is stored as UTF-8 text in the envelope, so bytes must
        survive decode -> parse -> re-canonicalize unchanged.
        """
        for name, payload in self.PAYLOADS:
            with self.subTest(payload=name):
                original = encode_jcs(payload)
                decoded = original.decode("utf-8")
                self.assertEqual(encode_jcs(json.loads(decoded)), original, name)


class TestSignVerifyRoundTrip(unittest.TestCase):
    """Every payload class must survive sign -> verify."""

    @classmethod
    def setUpClass(cls):
        cls.key = generate_keypair(
            Path(tempfile.mkdtemp()) / "parity_test_key.pem"
        )

    def test_all_payload_classes_verify(self):
        for name, payload in TestCanonicalizationParity.PAYLOADS:
            with self.subTest(payload=name):
                self.assertIs(
                    _envelope_roundtrip(payload, self.key), True,
                    f"{name} failed to round-trip",
                )

    def test_stored_hash_matches_canonicalizer_output(self):
        """The envelope's payload_hash must equal a fresh encode_jcs digest."""
        for name, payload in TestCanonicalizationParity.PAYLOADS:
            with self.subTest(payload=name):
                envelope = sign_trust_passport(payload, self.key)
                recomputed = hashlib.sha256(
                    encode_jcs(json.loads(envelope["canonical_payload"]))
                ).hexdigest()
                self.assertEqual(
                    recomputed,
                    envelope["payload_hash"].replace("sha256:", ""),
                    name,
                )

    def test_float_payload_does_not_sign_python_style_zero(self):
        """
        ECMAScript 7.1.12.1 (RFC 8785 Section 3.2.2.3): 0.0 must serialize as
        "0", never "0.0". A Python-style "0.0" here means the inline copy of JCS
        has been reintroduced.

        Key order puts "b" first and "score" last, so the number is followed by
        "}" rather than ",". Assert on the parsed value as well as the raw text
        so the check does not depend on key position.
        """
        envelope = sign_trust_passport({"score": 0.0, "b": "x"}, self.key)
        canonical = envelope["canonical_payload"]
        self.assertNotIn("0.0", canonical)
        self.assertIn('"score":0', canonical)
        self.assertEqual(json.loads(canonical)["score"], 0)

    def test_tampered_payload_is_rejected(self):
        """Changing the payload after signing must fail closed."""
        envelope = sign_trust_passport({"a": 1, "b": "x"}, self.key)
        envelope["canonical_payload"] = json.dumps(
            json.loads(envelope["canonical_payload"]) | {"b": "TAMPERED"}
        )
        with self.assertRaises(ValueError):
            verify_trust_passport(envelope)


if __name__ == "__main__":
    unittest.main()
