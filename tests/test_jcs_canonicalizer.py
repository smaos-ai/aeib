#!/usr/bin/env python3
r"""
test_jcs_canonicalizer.py
Unit tests for RFC 8785 JSON Canonicalization Scheme (JCS) implementation.
Verifies UTF-16 code unit key ordering, whitespace suppression, deterministic hashing,
rejection of non-string keys, and strict NaN/Infinity rejection.
"""

import math
import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.jcs_canonicalizer import (
    encode_jcs,
    generate_jcs_payload_hash,
    _utf16_sort_key,
    _canonicalize_obj,
)


class TestJCSCanonicalizer(unittest.TestCase):
    """Verifies RFC 8785 JSON Canonicalization Scheme invariants."""

    def test_utf16_code_unit_sorting_order(self):
        """
        RFC 8785 Section 3.2.3: Keys must be sorted by UTF-16 code units.
        Characters outside BMP (e.g. U+10000) have surrogate pairs starting with 0xD800,
        which sorts BEFORE BMP characters in range U+DC00 to U+FFFF (e.g. U+FFFF).
        """
        # In Unicode code points: \uFFFF (65535) < \U00010000 (65536)
        # In UTF-16 code units: \U00010000 (0xD800, 0xDC00) < \uFFFF (0xFFFF)
        payload = {"\uFFFF": 1, "\U00010000": 2}
        encoded = encode_jcs(payload)

        # In UTF-8 representation, \U00010000 is \xf0\x90\x80\x80 and \uFFFF is \xef\xbf\xbf
        # The key \U00010000 MUST appear before \uFFFF
        expected = '{"\U00010000":2,"\uFFFF":1}'.encode("utf-8")
        self.assertEqual(encoded, expected)

    def test_ascii_and_prefix_key_sorting(self):
        """Keys must sort lexicographically by code unit, with shorter prefix first."""
        payload = {
            "b": 1,
            "a": 2,
            "ab": 3,
            "aa": 4,
            "A": 5,
            "1": 6,
            "": 7
        }
        encoded = encode_jcs(payload).decode("utf-8")
        expected = '{"":7,"1":6,"A":5,"a":2,"aa":4,"ab":3,"b":1}'
        self.assertEqual(encoded, expected)

    def test_whitespace_suppression(self):
        """Separators must be strictly ',' and ':' with zero whitespace."""
        payload = {"first": 1, "second": [1, 2, 3], "third": {"nested": True}}
        encoded = encode_jcs(payload).decode("utf-8")
        self.assertNotIn(" ", encoded)
        self.assertNotIn("\t", encoded)
        self.assertNotIn("\n", encoded)
        self.assertEqual(encoded, '{"first":1,"second":[1,2,3],"third":{"nested":true}}')

    def test_string_literal_whitespace_preserved(self):
        """Whitespace within string values must be preserved."""
        payload = {"message": "hello world\n\t"}
        encoded = encode_jcs(payload).decode("utf-8")
        self.assertEqual(encoded, '{"message":"hello world\\n\\t"}')

    def test_deterministic_hashing_across_key_permutations(self):
        """Divergent dict key insertion orders must produce identical SHA-256 hashes."""
        payload1 = {"account": "IBAN-CZ-01", "amount": 10000, "currency": "CZK", "beneficiary": "ACME Corp"}
        payload2 = {"currency": "CZK", "beneficiary": "ACME Corp", "amount": 10000, "account": "IBAN-CZ-01"}
        payload3 = {"amount": 10000, "account": "IBAN-CZ-01", "currency": "CZK", "beneficiary": "ACME Corp"}

        hash1 = generate_jcs_payload_hash(payload1)
        hash2 = generate_jcs_payload_hash(payload2)
        hash3 = generate_jcs_payload_hash(payload3)

        self.assertEqual(hash1, hash2)
        self.assertEqual(hash2, hash3)
        self.assertEqual(len(hash1), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in hash1))

    def test_nested_structures_determinism(self):
        """Deeply nested structures produce identical canonical representations."""
        payload_a = {
            "level1": {
                "b": [{"y": 2, "x": 1}],
                "a": {"nested_b": False, "nested_a": None}
            }
        }
        payload_b = {
            "level1": {
                "a": {"nested_a": None, "nested_b": False},
                "b": [{"x": 1, "y": 2}]
            }
        }

        self.assertEqual(encode_jcs(payload_a), encode_jcs(payload_b))
        self.assertEqual(
            generate_jcs_payload_hash(payload_a),
            generate_jcs_payload_hash(payload_b)
        )

    def test_primitive_types_serialization(self):
        """JSON primitives: bool, None, int, float, string."""
        self.assertEqual(encode_jcs(True), b"true")
        self.assertEqual(encode_jcs(False), b"false")
        self.assertEqual(encode_jcs(None), b"null")
        self.assertEqual(encode_jcs(0), b"0")
        self.assertEqual(encode_jcs(-42), b"-42")
        self.assertEqual(encode_jcs("simple string"), b'"simple string"')

    def test_rejection_of_nan_and_infinity(self):
        """RFC 8785 and I-JSON forbid NaN and Infinity."""
        with self.assertRaises(ValueError):
            encode_jcs({"invalid": float("nan")})

        with self.assertRaises(ValueError):
            encode_jcs({"invalid": float("inf")})

        with self.assertRaises(ValueError):
            encode_jcs({"invalid": float("-inf")})

    def test_rejection_of_non_string_keys(self):
        """RFC 8785 object keys must be strings."""
        with self.assertRaises(TypeError):
            encode_jcs({123: "numeric_key"})

        with self.assertRaises(TypeError):
            encode_jcs({None: "none_key"})


if __name__ == "__main__":
    unittest.main()
