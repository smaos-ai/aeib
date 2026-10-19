#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_jcs_cyberphone_conformance.py — RFC 8785 JCS Conformance Suite
Verifies byte-exact conformance against cyberphone golden test vectors and ECMA-262 rules:
1. Golden vectors (arrays, french, structures, unicode, values, weird)
2. UTF-16 code unit key sorting (RFC 8785 Section 3.2.3)
3. ECMAScript 7.1.12.1 number serialization (RFC 8785 Section 3.2.2.3)
4. Fail-closed rejection of non-conforming inputs (NaN, Infinity, non-string keys)
5. String preservation per RFC 8785 Section 3.1 vs opt-in normalize_nfc boundary
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import (
    encode_jcs,
    generate_jcs_payload_hash,
    normalize_nfc,
)

DATA_DIR = REPO_ROOT / "tests" / "data" / "jcs"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"


def test_cyberphone_golden_vectors_conformance() -> None:
    """
    Evaluates byte-exact output against official cyberphone/json-canonicalization test vectors.
    """
    assert INPUT_DIR.exists(), f"Input directory missing: {INPUT_DIR}"
    assert OUTPUT_DIR.exists(), f"Output directory missing: {OUTPUT_DIR}"

    input_files = sorted(INPUT_DIR.glob("*.json"))
    assert len(input_files) >= 6, f"Expected at least 6 test vectors, found {len(input_files)}"

    tested_vectors: List[str] = []

    for in_path in input_files:
        out_path = OUTPUT_DIR / in_path.name
        assert out_path.exists(), f"Missing expected output vector for {in_path.name}"

        with open(in_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        expected_bytes = out_path.read_bytes()
        actual_bytes = encode_jcs(data)

        # Assert byte-for-byte exact equality
        assert actual_bytes == expected_bytes, (
            f"Vector {in_path.name} failed JCS conformance!\n"
            f"Expected: {expected_bytes!r}\n"
            f"Actual:   {actual_bytes!r}"
        )

        # Verify JCS SHA-256 payload hash helper
        expected_sha256 = hashlib.sha256(expected_bytes).hexdigest()
        actual_sha256 = generate_jcs_payload_hash(data)
        assert actual_sha256 == expected_sha256, (
            f"Vector {in_path.name} SHA-256 mismatch: {actual_sha256} != {expected_sha256}"
        )

        tested_vectors.append(in_path.name)

    expected_names = {"arrays.json", "french.json", "structures.json", "unicode.json", "values.json", "weird.json"}
    assert expected_names.issubset(set(tested_vectors)), (
        f"Missing standard cyberphone vectors: {expected_names - set(tested_vectors)}"
    )


def test_rfc8785_utf16_code_unit_sorting() -> None:
    """
    Verifies that dictionary keys are sorted strictly by UTF-16 code units (RFC 8785 Section 3.2.3),
    NOT by Unicode code points or UTF-8 bytes.

    In UTF-16, supplementary characters (U+10000..U+10FFFF) are encoded as surrogate pairs
    (0xD800..0xDBFF, 0xDC00..0xDFFF). Therefore, U+10000 (surrogate lead 0xD800) sorts BEFORE
    high BMP characters such as U+FFFF (0xFFFF), even though U+10000 has a higher scalar value.
    """
    # Key 1: U+FFFF (BMP high character)
    # Key 2: U+10000 (Supplementary character, lead surrogate 0xD800 in UTF-16)
    mapping = {
        "\uffff": "high_bmp",
        "\U00010000": "supplementary_linear_b",
    }

    canonical_bytes = encode_jcs(mapping)
    canonical_text = canonical_bytes.decode("utf-8")

    # In UTF-16 code unit order, U+10000 (0xD800) MUST precede U+FFFF (0xFFFF)
    pos_supplementary = canonical_text.find("\U00010000")
    pos_high_bmp = canonical_text.find("\uffff")

    assert pos_supplementary != -1 and pos_high_bmp != -1
    assert pos_supplementary < pos_high_bmp, (
        f"UTF-16 key sorting violation: supplementary character was not sorted before U+FFFF in {canonical_text}"
    )


def test_rfc8785_number_serialization_ecma262() -> None:
    """
    Evaluates RFC 8785 Section 3.2.2.3 and ECMAScript 7.1.12.1 ToString rules:
    - 0.0 and -0.0 serialized as 0
    - Floats representing whole numbers serialized without decimals (1.0 -> 1)
    - Smallest exponents without redundant '+' or leading zeros
    - Fixed range [-6 < n <= 21] vs exponential representation
    """
    cases: List[Tuple[Any, bytes]] = [
        (0.0, b"0"),
        (-0.0, b"0"),
        (0, b"0"),
        (1.0, b"1"),
        (100.0, b"100"),
        (-50.0, b"-50"),
        (0.5, b"0.5"),
        (-1.5, b"-1.5"),
        (1e20, b"100000000000000000000"),  # 21 digits: fixed notation
        (1e21, b"1e+21"),                   # >21 digits: exponential notation with sign
        (1e-6, b"0.000001"),                # -6 < n <= 21: fixed notation
        (1e-7, b"1e-7"),                    # n <= -6: exponential notation
        (-1e-6, b"-0.000001"),
        (-1e-7, b"-1e-7"),
        (1234567.89, b"1234567.89"),
    ]

    for val, expected in cases:
        actual = encode_jcs(val)
        assert actual == expected, (
            f"Number formatting failed for {val}: expected {expected!r}, got {actual!r}"
        )


def test_rfc8785_rejection_of_non_conforming_values() -> None:
    """
    Verifies that RFC 8785 fails closed when attempting to serialize non-conforming inputs:
    - NaN, Infinity, -Infinity
    - Non-string dictionary keys
    - Unserializable object types
    """
    with pytest.raises(ValueError, match="NaN and Infinity are not permitted in RFC 8785"):
        encode_jcs(float("nan"))

    with pytest.raises(ValueError, match="NaN and Infinity are not permitted in RFC 8785"):
        encode_jcs(float("inf"))

    with pytest.raises(ValueError, match="NaN and Infinity are not permitted in RFC 8785"):
        encode_jcs(float("-inf"))

    with pytest.raises(TypeError, match="RFC 8785 requires object keys to be strings"):
        encode_jcs({100: "integer_key_invalid_in_json"})

    with pytest.raises(TypeError, match="is not JSON serializable"):
        encode_jcs(object())


def test_rfc8785_string_preservation_and_nfc_boundary() -> None:
    """
    Verifies string preservation per RFC 8785 Section 3.1:
    JCS does not apply Unicode normalization, preserving inputs as-is.
    Also verifies the opt-in normalize_nfc helper for AEIB pre-pass validation.
    """
    # Decomposed "e" + combining acute accent (U+0065 U+0301)
    decomposed = "e\u0301"
    # Precomposed "é" (U+00E9)
    precomposed = "\u00e9"

    assert decomposed != precomposed

    # encode_jcs MUST preserve string as-is (different bytes)
    enc_decomposed = encode_jcs(decomposed)
    enc_precomposed = encode_jcs(precomposed)
    assert enc_decomposed != enc_precomposed

    # When normalize_nfc is explicitly used at ingress, it unifies representations
    norm_decomposed = normalize_nfc(decomposed)
    norm_precomposed = normalize_nfc(precomposed)
    assert norm_decomposed == norm_precomposed
    assert encode_jcs(norm_decomposed) == encode_jcs(norm_precomposed)

    # normalize_nfc fails closed if distinct keys would collide after NFC
    colliding_map = {
        decomposed: "val1",
        precomposed: "val2",
    }
    with pytest.raises(ValueError, match="NFC normalization collapsed distinct keys"):
        normalize_nfc(colliding_map)
