#!/usr/bin/env python3
r"""
test_jcs_canonicalizer.py
Unit tests for RFC 8785 JSON Canonicalization Scheme (JCS) implementation.
Verifies UTF-16 code unit key ordering, whitespace suppression, deterministic hashing,
rejection of non-string keys, strict NaN/Infinity rejection, and ECMAScript 7.1.12.1 number rules,
including the RFC 8785 Appendix B (Table 1) number serialization samples and the
Section 3.2.3 / 3.2.4 canonical property-order and UTF-8 byte vectors.
"""

import json
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.jcs_canonicalizer import (
    encode_jcs,
    generate_jcs_payload_hash,
    normalize_nfc,
    _utf16_sort_key,
)


class TestJCSCanonicalizer(unittest.TestCase):
    """Verifies RFC 8785 JSON Canonicalization Scheme invariants."""

    def test_utf16_code_unit_sorting_order(self):
        """
        RFC 8785 Section 3.2.3: Keys must be sorted by UTF-16 code units.
        Characters outside BMP (e.g. U+10000) have surrogate pairs starting with 0xD800,
        which sorts BEFORE BMP characters in range U+DC00 to U+FFFF (e.g. U+FFFF).
        """
        payload = {"\uFFFF": 1, "\U00010000": 2}
        encoded = encode_jcs(payload)
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

    def test_rfc8785_number_formatting_es6(self):
        """RFC 8785 Section 3.2.2.3: ECMAScript 7.1.12.1 number serialization."""
        # 1.0 must be serialized as 1
        self.assertEqual(encode_jcs(1.0), b"1")
        self.assertEqual(encode_jcs({"num": 1.0}), b'{"num":1}')
        
        # -0.0 must be serialized as 0
        self.assertEqual(encode_jcs(-0.0), b"0")
        self.assertEqual(encode_jcs(0.0), b"0")
        
        # Exponents with '+' for positive exponents per ECMA-262 7.1.12.1
        self.assertEqual(encode_jcs(1e21), b"1e+21")
        
        # Large integers in decimal if <= 10^21
        self.assertEqual(encode_jcs(1e20), b"100000000000000000000")
        
        # Small numbers in decimal if >= 1e-6
        self.assertEqual(encode_jcs(1e-6), b"0.000001")
        
        # Numbers < 1e-6 use exponent without redundant leading zero (1e-7, not 1e-07)
        self.assertEqual(encode_jcs(1e-7), b"1e-7")
        
        # Negative floats
        self.assertEqual(encode_jcs(-1.5), b"-1.5")
        self.assertEqual(encode_jcs(-10.0), b"-10")

    def test_rejection_of_nan_and_infinity(self):
        """RFC 8785 forbids NaN and Infinity."""
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


class TestRFC8785AppendixBVectors(unittest.TestCase):
    """
    RFC 8785 Appendix B (Table 1): ECMAScript-compatible JSON number
    serialization samples, keyed by the IEEE 754 double-precision bit pattern.
    Vectors are transcribed from RFC 8785 Appendix B and embedded offline
    (zero network egress at test time).
    """

    # (IEEE 754 hex, expected JSON representation)
    APPENDIX_B_SAMPLES = [
        ("0000000000000000", "0"),                       # Zero
        ("8000000000000000", "0"),                       # Minus zero
        ("0000000000000001", "5e-324"),                  # Min pos number
        ("8000000000000001", "-5e-324"),                 # Min neg number
        ("7fefffffffffffff", "1.7976931348623157e+308"), # Max pos number
        ("ffefffffffffffff", "-1.7976931348623157e+308"),# Max neg number
        ("4340000000000000", "9007199254740992"),        # Max pos int
        ("c340000000000000", "-9007199254740992"),       # Max neg int
        ("4430000000000000", "295147905179352830000"),   # ~2**68
        ("44b52d02c7e14af5", "9.999999999999997e+22"),
        ("44b52d02c7e14af6", "1e+23"),
        ("44b52d02c7e14af7", "1.0000000000000001e+23"),
        ("444b1ae4d6e2ef4e", "999999999999999700000"),
        ("444b1ae4d6e2ef4f", "999999999999999900000"),
        ("444b1ae4d6e2ef50", "1e+21"),
        ("3eb0c6f7a0b5ed8c", "9.999999999999997e-7"),
        ("3eb0c6f7a0b5ed8d", "0.000001"),
        ("41b3de4355555553", "333333333.3333332"),
        ("41b3de4355555554", "333333333.33333325"),
        ("41b3de4355555555", "333333333.3333333"),
        ("41b3de4355555556", "333333333.3333334"),
        ("41b3de4355555557", "333333333.33333343"),
        ("becbf647612f3696", "-0.0000033333333333333333"),
        ("43143ff3c1cb0959", "1424953923781206.2"),      # Round to even
    ]

    # Out-of-range IEEE 754 patterns that MUST terminate with an error.
    APPENDIX_B_REJECTED = ["7fffffffffffffff", "7ff0000000000000", "fff0000000000000"]

    # RFC 8785 Section 3.2.4: canonicalized Section 3.2.2 sample, as UTF-8 bytes
    # (hex transcribed verbatim from the RFC, spaces are not part of the byte string).
    SECTION_3_2_4_EXPECTED_HEX = (
        "7b 22 6c 69 74 65 72 61 6c 73 22 3a 5b 6e 75 6c 6c 2c 74 72\n"
        "75 65 2c 66 61 6c 73 65 5d 2c 22 6e 75 6d 62 65 72 73 22 3a\n"
        "5b 33 33 33 33 33 33 33 33 33 2e 33 33 33 33 33 33 33 2c 31\n"
        "65 2b 33 30 2c 34 2e 35 2c 30 2e 30 30 32 2c 31 65 2d 32 37\n"
        "5d 2c 22 73 74 72 69 6e 67 22 3a 22 e2 82 ac 24 5c 75 30 30\n"
        "30 66 5c 6e 41 27 42 5c 22 5c 5c 5c 5c 5c 22 2f 22 7d"
    )

    def test_appendix_b_number_serialization_samples(self):
        """Each Appendix B bit pattern serializes to the published JSON representation."""
        for bit_pattern, expected in self.APPENDIX_B_SAMPLES:
            value = struct.unpack(">d", bytes.fromhex(bit_pattern))[0]
            self.assertEqual(
                encode_jcs(value),
                expected.encode("utf-8"),
                msg=f"IEEE 754 {bit_pattern}",
            )

    def test_appendix_b_nan_and_infinity_must_fail_closed(self):
        """NaN / Infinity are not JSON: RFC 8785 Section 3.2.2.3 requires an error."""
        for bit_pattern in self.APPENDIX_B_REJECTED:
            value = struct.unpack(">d", bytes.fromhex(bit_pattern))[0]
            with self.assertRaises(ValueError, msg=f"IEEE 754 {bit_pattern}"):
                encode_jcs(value)

    def test_section_3_2_4_canonical_utf8_byte_vector(self):
        """
        RFC 8785 Section 3.2.2 sample document must canonicalize to the exact
        UTF-8 byte string published in Section 3.2.4.
        """
        document = {
            "numbers": [
                333333333.33333329, 1e30, 4.50, 2e-3,
                0.000000000000000000000000001,
            ],
            "string": "€$\u000f\nA'B\"\\\\\"/",
            "literals": [None, True, False],
        }

        canonical = encode_jcs(document)
        expected = bytes.fromhex(self.SECTION_3_2_4_EXPECTED_HEX.replace(" ", "").replace("\n", ""))
        self.assertEqual(canonical, expected)

        # SHA-256 over the RFC-published byte string (cross-checked against the
        # WASM verifier in smaos-wasm-verifier/src/lib.rs).
        self.assertEqual(
            generate_jcs_payload_hash(document),
            "2d5e01a318d0f0879ab568c4be289c8b1f64ef8921a53c6277d5e069978baacb",
        )

        # Section 3.2.4: output MUST be UTF-8 with non-ASCII characters emitted as-is.
        decoded = canonical.decode("utf-8")
        self.assertIn("€", decoded)
        self.assertNotIn("\\u20ac", decoded)
        self.assertTrue(decoded.startswith('{"literals":[null,true,false],"numbers":['))

    def test_section_3_2_3_property_sorting_sample(self):
        """
        RFC 8785 Section 3.2.3 property-sorting sample: UTF-16 code-unit order
        (raw form, not UTF-8 byte order).
        """
        document = {
            "\u20ac": "Euro Sign",
            "\r": "Carriage Return",
            "\ufb33": "Hebrew Letter Dalet With Dagesh",
            "1": "One",
            "\U0001F600": "Emoji: Grinning Face",
            "\u0080": "Control",
            "\u00f6": "Latin Small Letter O With Diaeresis",
        }

        ordered_keys = list(json.loads(encode_jcs(document).decode("utf-8")).keys())
        self.assertEqual(
            ordered_keys,
            [
                "\r",
                "1",
                "\u0080",
                "\u00f6",
                "\u20ac",
                "\U0001F600",
                "\ufb33",
            ],
        )


class TestNFCPrePass(unittest.TestCase):
    """
    AEIB Unicode NFC pre-pass (normalize_nfc) -- an OPT-IN extension.

    RFC 8785 Section 3.1 requires that parsed string data MUST NOT be altered
    and that components MUST preserve Unicode string data "as is", so
    encode_jcs() deliberately does NOT normalize. These tests pin down both
    halves of that contract: normalize_nfc() does converge equivalent forms,
    and encode_jcs() leaves input strings untouched.
    """

    COMPOSED = "\u00e9"        # precomposed LATIN SMALL LETTER E WITH ACUTE
    DECOMPOSED = "e\u0301"    # e + COMBINING ACUTE ACCENT

    # U+FB33 has canonical decomposition U+05D3 U+05BC but is a composition
    # exclusion, so NFC splits it while RFC 8785 must keep it whole.
    COMPOSITION_EXCLUSION = "\ufb33"
    ITS_NFC_FORM = "\u05d3\u05bc"

    def test_normalize_nfc_converges_equivalent_value_forms(self):
        """Decomposed and composed forms must normalize to identical text."""
        self.assertNotEqual(self.COMPOSED, self.DECOMPOSED)
        self.assertEqual(normalize_nfc(self.DECOMPOSED), normalize_nfc(self.COMPOSED))

    def test_pre_pass_makes_equivalent_inputs_share_one_digest(self):
        """Applying the pre-pass first is what yields one shared caid."""
        decomposed = generate_jcs_payload_hash(normalize_nfc({"item": self.DECOMPOSED}))
        composed = generate_jcs_payload_hash(normalize_nfc({"item": self.COMPOSED}))
        self.assertEqual(decomposed, composed)

    def test_pre_pass_applies_to_object_keys(self):
        """Key normalization runs before UTF-16 sorting so key forms converge."""
        self.assertEqual(normalize_nfc({self.DECOMPOSED: 1}),
                         normalize_nfc({self.COMPOSED: 1}))

    def test_pre_pass_applies_recursively_to_nested_containers(self):
        """Normalization must reach strings inside lists and nested objects."""
        inner = {"k": [self.DECOMPOSED, {"deep": self.DECOMPOSED}]}
        expected = {"k": [self.COMPOSED, {"deep": self.COMPOSED}]}
        self.assertEqual(normalize_nfc(inner), normalize_nfc(expected))

    def test_pre_pass_key_collision_fails_closed(self):
        """
        Two distinct keys collapsing to one NFC form must raise, not silently
        drop a field -- a dropped key would change the receipt's meaning.
        """
        payload = {self.COMPOSED: 1, self.DECOMPOSED: 2}
        self.assertEqual(len(payload), 2, "precondition: input dict has 2 distinct keys")
        with self.assertRaises(ValueError):
            normalize_nfc(payload)

    def test_pre_pass_is_noop_on_ascii(self):
        """ASCII-only payloads pass through unchanged."""
        plain = {"b": 2, "a": 1, "n": "hello", "arr": [1, 2, 3]}
        self.assertEqual(normalize_nfc(plain), plain)

    def test_pre_pass_is_idempotent(self):
        """Applying NFC to already-NFC text must be byte-stable."""
        once = normalize_nfc({"s": self.COMPOSED})
        self.assertEqual(once, normalize_nfc(once))
        self.assertEqual(encode_jcs(once), encode_jcs(normalize_nfc(once)))

    def test_pre_pass_leaves_non_string_scalars_untouched(self):
        """Numbers, booleans, and null must pass through unmodified."""
        payload = {"i": 1, "f": 1.5, "t": True, "n": False, "z": None}
        self.assertEqual(normalize_nfc(payload), payload)

    def test_encode_jcs_preserves_input_strings_as_is(self):
        """
        RFC 8785 Section 3.1: parsed JSON string data MUST NOT be altered, and
        components MUST preserve Unicode string data "as is". encode_jcs must
        emit the decomposed sequence verbatim rather than NFC-composing it.
        """
        raw = encode_jcs({"item": self.DECOMPOSED}).decode("utf-8")
        self.assertIn(self.DECOMPOSED, raw)
        self.assertNotIn(self.COMPOSED, raw)

    def test_encode_jcs_does_not_split_composition_exclusions(self):
        """
        U+FB33 is a composition exclusion: NFC would rewrite it to U+05D3 U+05BC
        and shift its UTF-16 sort position. RFC 8785 requires it stay whole, so
        the Section 3.2.3 property-ordering vector keeps its expected order.
        """
        self.assertEqual(normalize_nfc(self.COMPOSITION_EXCLUSION), self.ITS_NFC_FORM)
        encoded = encode_jcs({self.COMPOSITION_EXCLUSION: 1, "\u20ac": 2})
        decoded = json.loads(encoded.decode("utf-8"))
        self.assertIn(self.COMPOSITION_EXCLUSION, decoded)
        # U+FB33 (0xFB33) sorts after U+20AC under UTF-16 code units.
        self.assertEqual(list(decoded.keys()), ["\u20ac", self.COMPOSITION_EXCLUSION])

    def test_encode_jcs_ignores_the_pre_pass_unless_caller_applies_it(self):
        """The pre-pass is opt-in: encode_jcs alone must not normalize."""
        plain = {"item": self.DECOMPOSED}
        baseline = json.dumps(plain, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False).encode("utf-8")
        self.assertEqual(encode_jcs(plain), baseline)


if __name__ == "__main__":
    unittest.main()
