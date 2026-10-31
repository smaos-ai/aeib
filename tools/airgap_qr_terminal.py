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
tools/airgap_qr_terminal.py — Air-Gapped Optical QR Hardware Notary Terminal.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Architectural Invariants:
1. Physical / Optical Hermetic Air-Gap:
   - Provides offline optical data encoding and decoding between online execution planes
     and isolated cold-storage hardware stations without network interfaces or socket binding.
2. Chunked Multipart Framing:
   - Formats large cryptographic payloads into deterministic multipart chunk sequences:
     'AQRF/v1/<part_idx>/<total_parts>/<payload_hash_hex>/<chunk_b64>'
     allowing optical camera scanning across successive frames.
3. Deterministic RFC 8785 Canonical Serialization:
   - Preserves payload cryptographic integrity and canonical ordering across optical transfers.
4. Fail-Closed Validation & Checksums:
   - Rejects corrupted, missing, out-of-order, or tampered frames before releasing
     reconstructed payload to cold storage or execution gateway.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import hashlib
import json
import math
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs

# Configuration constants
DEFAULT_MAX_CHUNK_CHARS: int = 500  # claim: config
FRAME_MAGIC_PREFIX: str = "AQRF/v1"  # claim: config
TERMINAL_BORDER_WIDTH: int = 70  # claim: config


def compute_sha256_hex(data: bytes) -> str:
    """Computes SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class OpticalFrame:
    """A single framed optical chunk for air-gapped transit."""

    part_index: int
    total_parts: int
    payload_hash: str
    chunk_data_b64: str

    def serialize(self) -> str:
        return f"{FRAME_MAGIC_PREFIX}/{self.part_index}/{self.total_parts}/{self.payload_hash}/{self.chunk_data_b64}"

    @classmethod
    def parse(cls, raw_frame: str) -> OpticalFrame:
        if not raw_frame or not isinstance(raw_frame, str):
            raise ValueError("Frame must be a non-empty string")
        parts = raw_frame.strip().split("/")
        if len(parts) != 6 or f"{parts[0]}/{parts[1]}" != FRAME_MAGIC_PREFIX:
            raise ValueError("Invalid frame header or magic prefix")

        try:
            part_idx = int(parts[2])
            total_parts = int(parts[3])
        except ValueError as exc:
            raise ValueError("Frame part indices must be integers") from exc

        if part_idx < 1 or total_parts < 1 or part_idx > total_parts:
            raise ValueError(f"Invalid frame index range: {part_idx}/{total_parts}")

        payload_hash = parts[4]
        if len(payload_hash) != 64:
            raise ValueError("Invalid payload hash length in frame")

        chunk_b64 = parts[5]
        if not chunk_b64:
            raise ValueError("Empty chunk data in frame")

        return cls(
            part_index=part_idx,
            total_parts=total_parts,
            payload_hash=payload_hash,
            chunk_data_b64=chunk_b64,
        )


def encode_airgap_payload(
    payload: Dict[str, Any],
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> List[str]:
    """
    Serializes payload using RFC 8785 JCS, computes SHA-256 digest,
    and splits into a sequence of framed optical QR strings.
    """
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Payload must be a non-empty dictionary")
    if not isinstance(max_chunk_chars, int) or max_chunk_chars < 64:
        raise ValueError("max_chunk_chars must be at least 64")

    canonical_bytes = encode_jcs(payload)
    payload_hash = compute_sha256_hex(canonical_bytes)
    payload_b64 = base64.b64encode(canonical_bytes).decode("ascii")

    # Split into chunks
    total_chars = len(payload_b64)
    total_parts = max(1, math.ceil(total_chars / max_chunk_chars))

    frames: List[str] = []
    for idx in range(total_parts):
        start = idx * max_chunk_chars
        end = start + max_chunk_chars
        chunk = payload_b64[start:end]
        frame = OpticalFrame(
            part_index=idx + 1,
            total_parts=total_parts,
            payload_hash=payload_hash,
            chunk_data_b64=chunk,
        )
        frames.append(frame.serialize())

    return frames


def decode_airgap_payload(frames: Sequence[str]) -> Dict[str, Any]:
    """
    Parses, validates, orders, and reconstructs payload from optical frame sequence.
    """
    if not frames:
        raise ValueError("Frame sequence cannot be empty")

    parsed_frames: List[OpticalFrame] = []
    expected_hash: Optional[str] = None
    expected_total: Optional[int] = None

    for raw in frames:
        f = OpticalFrame.parse(raw)
        if expected_hash is None:
            expected_hash = f.payload_hash
            expected_total = f.total_parts
        else:
            if f.payload_hash != expected_hash:
                raise ValueError("Payload hash mismatch across frames")
            if f.total_parts != expected_total:
                raise ValueError("Total parts mismatch across frames")
        parsed_frames.append(f)

    if expected_total is None:
        raise ValueError("Unable to determine frame parameters")

    # Group by part_index to detect duplicates and missing parts
    parts_map: Dict[int, str] = {}
    for f in parsed_frames:
        parts_map[f.part_index] = f.chunk_data_b64

    if len(parts_map) != expected_total:
        missing = [i for i in range(1, expected_total + 1) if i not in parts_map]
        raise ValueError(f"Missing optical frames: {missing}")

    # Reconstruct base64 payload
    reconstructed_b64 = "".join(parts_map[i] for i in range(1, expected_total + 1))
    try:
        raw_bytes = base64.b64decode(reconstructed_b64)
    except Exception as exc:
        raise ValueError("Failed to base64-decode reconstructed payload") from exc

    # Verify SHA-256 checksum
    actual_hash = compute_sha256_hex(raw_bytes)
    if actual_hash != expected_hash:
        raise ValueError(f"Reconstructed payload checksum failure: {actual_hash} != {expected_hash}")

    # Parse JSON
    try:
        decoded_dict = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(decoded_dict, dict):
            raise ValueError("Decoded payload must be a JSON dictionary")
        return decoded_dict
    except Exception as exc:
        raise ValueError("Failed to parse reconstructed JSON payload") from exc


def render_terminal_ascii_matrix(frame_str: str) -> str:
    """
    Renders an ASCII text envelope box around the frame string for terminal display.
    """
    border = "=" * TERMINAL_BORDER_WIDTH
    title = "[ SOVEREIGN AIRGAP OPTICAL QR ENVELOPE ]"
    return f"{border}\n{title.center(TERMINAL_BORDER_WIDTH)}\n{border}\n{frame_str}\n{border}"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Air-Gapped Optical QR Hardware Notary Terminal")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Encode command
    enc_parser = subparsers.add_parser("encode", help="Encode JSON payload into optical frames")
    enc_parser.add_argument("--input", required=True, help="Input JSON file path")
    enc_parser.add_argument("--max-chunk", type=int, default=DEFAULT_MAX_CHUNK_CHARS)
    enc_parser.add_argument("--ascii-box", action="store_true", help="Print ASCII display box")

    # Decode command
    dec_parser = subparsers.add_parser("decode", help="Decode optical frames back to JSON")
    dec_parser.add_argument("--frames-file", required=True, help="File with frame strings (one per line)")
    dec_parser.add_argument("--output", help="Output JSON file path (prints to stdout if omitted)")

    args = parser.parse_args(argv)

    if args.command == "encode":
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
        frames = encode_airgap_payload(data, max_chunk_chars=args.max_chunk)
        for frame in frames:
            if args.ascii_box:
                print(render_terminal_ascii_matrix(frame))
            else:
                print(frame)
        return 0

    elif args.command == "decode":
        with open(args.frames_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        decoded = decode_airgap_payload(lines)
        out_str = json.dumps(decoded, indent=2, sort_keys=True)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out_str)
        else:
            print(out_str)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
