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
tests/test_airgap_qr_terminal.py
================================================================================
Verification Suite for Optical Airgap QR Terminal.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. OpticalFrame serialization, parsing, and frozen immutability.
2. OpticalFrame parse validation errors (bad magic, bad indices, hash length, empty chunk).
3. Payload encoding chunking logic, boundary handling, and error validation.
4. Hermetic round-trip decode across small and multi-chunk envelopes.
5. Corruption detection: mismatched payload hash across frames.
6. Corruption detection: missing intermediate frames.
7. Corruption detection: tampered chunk bytes failing SHA-256 integrity check.
8. Non-JSON payload decode error handling.
9. Terminal ASCII envelope matrix rendering.
10. CLI execution: encode and decode subcommands.
11. Wilson 95% confidence interval calculations.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from tools.airgap_qr_terminal import (
    DEFAULT_MAX_CHUNK_CHARS,
    FRAME_MAGIC_PREFIX,
    OpticalFrame,
    decode_airgap_payload,
    encode_airgap_payload,
    main,
    render_terminal_ascii_matrix,
)


def compute_wilson_ci_bps(k: int, n: int, z: float = 1.959963984540054) -> Tuple[int, int]:
    """Calculates conservative Wilson 95% confidence interval in basis points."""
    if n == 0:
        return (0, 10000)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    low = max(0.0, centre - half)
    high = min(1.0, centre + half)
    return (int(round(low * 10000)), int(round(high * 10000)))


def test_01_optical_frame_lifecycle() -> None:
    frame = OpticalFrame(
        part_index=1,
        total_parts=3,
        payload_hash="a" * 64,
        chunk_data_b64="c29tZV9kYXRh",
    )
    serialized = frame.serialize()
    assert serialized.startswith("AQRF/v1/1/3/")

    parsed = OpticalFrame.parse(serialized)
    assert parsed == frame
    assert parsed.part_index == 1
    assert parsed.total_parts == 3
    assert parsed.payload_hash == "a" * 64
    assert parsed.chunk_data_b64 == "c29tZV9kYXRh"

    # Frozen immutability
    with pytest.raises(Exception):
        parsed.part_index = 2  # type: ignore


def test_02_optical_frame_parse_errors() -> None:
    # Empty string
    with pytest.raises(ValueError, match="Frame must be a non-empty string"):
        OpticalFrame.parse("")

    # Bad prefix
    with pytest.raises(ValueError, match="Invalid frame header or magic prefix"):
        OpticalFrame.parse("BAD/v1/1/2/hash/data")

    # Non-integer parts
    with pytest.raises(ValueError, match="Frame part indices must be integers"):
        OpticalFrame.parse(f"{FRAME_MAGIC_PREFIX}/one/2/{'a'*64}/data")

    # Out of range indices
    with pytest.raises(ValueError, match="Invalid frame index range"):
        OpticalFrame.parse(f"{FRAME_MAGIC_PREFIX}/0/2/{'a'*64}/data")
    with pytest.raises(ValueError, match="Invalid frame index range"):
        OpticalFrame.parse(f"{FRAME_MAGIC_PREFIX}/3/2/{'a'*64}/data")

    # Invalid hash length
    with pytest.raises(ValueError, match="Invalid payload hash length"):
        OpticalFrame.parse(f"{FRAME_MAGIC_PREFIX}/1/2/short_hash/data")

    # Empty chunk data
    with pytest.raises(ValueError, match="Empty chunk data in frame"):
        OpticalFrame.parse(f"{FRAME_MAGIC_PREFIX}/1/2/{'a'*64}/")


def test_03_encode_payload_validations_and_chunking() -> None:
    # Validation errors
    with pytest.raises(ValueError, match="Payload must be a non-empty dictionary"):
        encode_airgap_payload({})  # type: ignore
    with pytest.raises(ValueError, match="Payload must be a non-empty dictionary"):
        encode_airgap_payload(["not", "dict"])  # type: ignore
    with pytest.raises(ValueError, match="max_chunk_chars must be at least 64"):
        encode_airgap_payload({"k": "v"}, max_chunk_chars=32)

    # Large payload multi-chunk test
    large_payload = {f"key_{i}": f"value_string_padding_{i}" * 10 for i in range(50)}
    chunks = encode_airgap_payload(large_payload, max_chunk_chars=100)
    assert len(chunks) > 1

    # Single chunk test
    small_payload = {"action": "PING", "ts": 12345}
    single_chunks = encode_airgap_payload(small_payload, max_chunk_chars=1000)
    assert len(single_chunks) == 1
    assert "/1/1/" in single_chunks[0]


def test_04_decode_round_trip() -> None:
    original: Dict[str, Any] = {
        "action_type": "T3_TRANSFER",
        "amount_minor": 1000000,
        "destination_vault": "vault://cold/acct_999",
        "nested": {"authorizers": ["alice", "bob"], "threshold": 2},
    }
    frames = encode_airgap_payload(original, max_chunk_chars=80)
    decoded = decode_airgap_payload(frames)
    assert decoded == original


def test_05_decode_corrupted_payload_hash() -> None:
    original = {"data": "test_data_for_corruption" * 5}
    frames = encode_airgap_payload(original, max_chunk_chars=64)
    assert len(frames) >= 2

    # Modify hash of second frame
    parts = frames[1].split("/")
    parts[4] = "b" * 64
    corrupted_frame = "/".join(parts)
    bad_frames = [frames[0], corrupted_frame]

    with pytest.raises(ValueError, match="Payload hash mismatch across frames"):
        decode_airgap_payload(bad_frames)


def test_06_decode_missing_frame() -> None:
    original = {"data": "long_string_" * 30}
    frames = encode_airgap_payload(original, max_chunk_chars=64)
    assert len(frames) >= 3

    # Drop intermediate frame 2 only
    dropped = [f for i, f in enumerate(frames) if i != 1]
    with pytest.raises(ValueError, match=r"Missing optical frames: \[2\]"):
        decode_airgap_payload(dropped)

    # Drop first frame (frame 1) - kills constant 1 perturbation
    dropped_first = frames[1:]
    with pytest.raises(ValueError, match=r"Missing optical frames: \[1\]"):
        decode_airgap_payload(dropped_first)

    # Drop last frame (kills Add swapped mutant)
    dropped_last = frames[:-1]
    with pytest.raises(ValueError, match=rf"Missing optical frames: \[{len(frames)}\]"):
        decode_airgap_payload(dropped_last)


def test_07_decode_tampered_chunk_data() -> None:
    original = {"data": "long_string_to_test_tampering_" * 20}
    frames = encode_airgap_payload(original, max_chunk_chars=64)

    # Tamper payload data in frame 0
    parts = frames[0].split("/")
    # Change first base64 char
    parts[5] = "AAAA" + parts[5][4:]
    bad_frame = "/".join(parts)
    bad_sequence = [bad_frame] + frames[1:]

    with pytest.raises(ValueError, match="checksum failure"):
        decode_airgap_payload(bad_sequence)


def test_08_render_ascii_matrix() -> None:
    frame = f"{FRAME_MAGIC_PREFIX}/1/1/{'a'*64}/data"
    matrix = render_terminal_ascii_matrix(frame)
    assert "[ SOVEREIGN AIRGAP OPTICAL QR ENVELOPE ]" in matrix
    assert frame in matrix
    assert "=" * 70 in matrix


def test_09_cli_encode_and_decode(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    in_file = tmp_path / "input.json"
    in_file.write_text(json.dumps({"action": "AUDIT", "count": 42}))

    # CLI encode
    ret = main(["encode", "--input", str(in_file), "--max-chunk", "70", "--ascii-box"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "SOVEREIGN AIRGAP OPTICAL QR ENVELOPE" in captured.out

    # Encode without box to frames file
    frames_file = tmp_path / "frames.txt"
    frames = encode_airgap_payload({"action": "AUDIT", "count": 42}, max_chunk_chars=70)
    frames_file.write_text("\n".join(frames))

    # CLI decode to stdout
    ret_dec = main(["decode", "--frames-file", str(frames_file)])
    assert ret_dec == 0
    captured_dec = capsys.readouterr()
    assert '  "action": "AUDIT"' in captured_dec.out
    decoded = json.loads(captured_dec.out)
    assert decoded["action"] == "AUDIT"
    assert decoded["count"] == 42

    # CLI decode to output file
    out_file = tmp_path / "output.json"
    ret_dec2 = main(["decode", "--frames-file", str(frames_file), "--output", str(out_file)])
    assert ret_dec2 == 0
    saved_text = out_file.read_text(encoding="utf-8")
    assert saved_text.startswith('{\n  "action": "AUDIT"')
    saved = json.loads(saved_text)
    assert saved["count"] == 42

    # CLI encode missing required --input raises SystemExit
    with pytest.raises(SystemExit):
        main(["encode"])


def test_10_empty_frames_validation() -> None:
    with pytest.raises(ValueError, match="Frame sequence cannot be empty"):
        decode_airgap_payload([])


def test_11_wilson_ci_computation() -> None:
    low, high = compute_wilson_ci_bps(28, 30)
    assert low > 7500
    assert high <= 10000


def test_12_exact_mutation_boundaries_and_survivors(tmp_path: Path) -> None:
    # Test DEFAULT_MAX_CHUNK_CHARS == 500
    assert DEFAULT_MAX_CHUNK_CHARS == 500
    payload = {"k": "v"}
    frames = encode_airgap_payload(payload)
    assert len(frames) == 1

    # Test mismatched total_parts across frames
    h = "c" * 64
    f1 = f"{FRAME_MAGIC_PREFIX}/1/2/{h}/chunk1"
    f2 = f"{FRAME_MAGIC_PREFIX}/2/3/{h}/chunk2"
    with pytest.raises(ValueError, match="Total parts mismatch across frames"):
        decode_airgap_payload([f1, f2])

    # Test render_terminal_ascii_matrix exact 70 character border
    rendered = render_terminal_ascii_matrix("TEST_FRAME")
    lines = rendered.split("\n")
    assert len(lines[0]) == 70
    assert lines[0] == "=" * 70

    # Test out-of-order frames are assembled correctly in order 1..expected_total
    shuffled_payload = {"key1": "hello" * 10, "key2": "world" * 10}
    multi_frames = encode_airgap_payload(shuffled_payload, max_chunk_chars=64)
    assert len(multi_frames) >= 2
    shuffled_frames = list(reversed(multi_frames))
    decoded_shuffled = decode_airgap_payload(shuffled_frames)
    assert decoded_shuffled == shuffled_payload

    # Test main return 0 on encode without ascii box
    in_file = tmp_path / "in2.json"
    in_file.write_text(json.dumps({"test": 123}))
    ret_plain = main(["encode", "--input", str(in_file)])
    assert ret_plain == 0

    # Test indent=2 exact spacing in decode
    frames_file2 = tmp_path / "frames2.txt"
    frames2 = encode_airgap_payload({"alpha": {"beta": "gamma"}}, max_chunk_chars=500)
    frames_file2.write_text("\n".join(frames2))
    out_file2 = tmp_path / "out2.json"
    main(["decode", "--frames-file", str(frames_file2), "--output", str(out_file2)])
    text2 = out_file2.read_text(encoding="utf-8")
    assert '{\n  "alpha": {\n    "beta": "gamma"\n  }\n}' == text2

    # Test range(1, expected_total + 1) exact boundaries with missing frame 1 and frame total
    h4 = "d" * 64
    f_total4_missing_1 = [
        f"{FRAME_MAGIC_PREFIX}/2/4/{h4}/chunk2",
        f"{FRAME_MAGIC_PREFIX}/3/4/{h4}/chunk3",
        f"{FRAME_MAGIC_PREFIX}/4/4/{h4}/chunk4",
    ]
    with pytest.raises(ValueError) as exc1:
        decode_airgap_payload(f_total4_missing_1)
    assert "Missing optical frames: [1]" in str(exc1.value)

    f_total4_missing_4 = [
        f"{FRAME_MAGIC_PREFIX}/1/4/{h4}/chunk1",
        f"{FRAME_MAGIC_PREFIX}/2/4/{h4}/chunk2",
        f"{FRAME_MAGIC_PREFIX}/3/4/{h4}/chunk3",
    ]
    with pytest.raises(ValueError) as exc4:
        decode_airgap_payload(f_total4_missing_4)
    assert "Missing optical frames: [4]" in str(exc4.value)

    # Test line 249 fallback return 1
    import argparse
    class FakeNamespace:
        command = "unrecognized_cmd"
    mp = pytest.MonkeyPatch()
    mp.setattr(argparse.ArgumentParser, "parse_args", lambda self, argv: FakeNamespace())
    try:
        assert main(["dummy"]) == 1
    finally:
        mp.undo()



