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
src/cold_storage_hardware_ledger.py
================================================================================
Cold Storage Hardware Ledger & External Storage Binding Engine.

Evaluated under the stated model:
  - Append-Only SHA-256 Hash-Chained Hardware Ledger
  - Offline Cold Storage / External SSD Export & Portability
  - Tamper & Rollback Detection from Genesis to Head
  - RFC 8785 JCS Canonicalization with Integer Metrics

Core Architectural Invariants:
  1. Hash-Chained Immutability:
     Every block binds previous_block_caid to form a tamper-evident hash chain.
     Modifying, inserting, or deleting any block invalidates all subsequent CAIDs.
  2. Hardware Warrant Binding:
     Each block binds the iPhone Secure Enclave P-256 warrant along with device
     telemetry (thermal state, battery integer bps, physical memory).
  3. Air-Gapped Verification:
     The entire chain can be verified independently on a clean air-gapped machine
     without access to live network or external databases.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs

GENESIS_BLOCK_CAID = "sha256:0000000000000000000000000000000000000000000000000000000000000000"


@dataclass(frozen=True)
class LedgerBlock:
    """An individual block in the cold storage hardware ledger."""

    block_index: int
    timestamp_epoch_sec: int
    previous_block_caid: str
    enclave_warrant: Dict[str, Any]
    device_telemetry: Dict[str, Any]
    block_caid: str
    signature_hex: str
    public_key_hex: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_index": self.block_index,
            "timestamp_epoch_sec": self.timestamp_epoch_sec,
            "previous_block_caid": self.previous_block_caid,
            "enclave_warrant": self.enclave_warrant,
            "device_telemetry": self.device_telemetry,
            "block_caid": self.block_caid,
            "signature_hex": self.signature_hex,
            "public_key_hex": self.public_key_hex,
        }


class ColdStorageHardwareLedger:
    """
    Append-only cold storage ledger manager.
    Maintains a hash-chained JSONL file and provides verification and export.
    """

    def __init__(
        self,
        ledger_file_path: Path,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
    ) -> None:
        self.ledger_path = ledger_file_path
        self.signing_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.signing_key.public_key()
        self._lock = threading.Lock()

        # Ensure parent directory exists
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            self.ledger_path.touch()

    def append_warrant(
        self,
        enclave_warrant: Dict[str, Any],
        device_telemetry: Dict[str, Any],
        timestamp_epoch_sec: Optional[int] = None,
    ) -> LedgerBlock:
        """
        Appends a new hardware-signed warrant block to the hash chain.
        """
        now_epoch = timestamp_epoch_sec if timestamp_epoch_sec is not None else int(time.time())

        with self._lock:
            # Read last block to find current head index and CAID
            blocks = self._read_all_blocks_unlocked()
            if not blocks:
                new_index = 0
                prev_caid = GENESIS_BLOCK_CAID
            else:
                last_block = blocks[-1]
                new_index = last_block.block_index + 1
                prev_caid = last_block.block_caid

            body_to_hash = {
                "block_index": new_index,
                "timestamp_epoch_sec": now_epoch,
                "previous_block_caid": prev_caid,
                "enclave_warrant": enclave_warrant,
                "device_telemetry": device_telemetry,
            }

            canonical_bytes = encode_jcs(body_to_hash)
            block_caid = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
            sig = self.signing_key.sign(canonical_bytes)
            pub_bytes = self.public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )

            block = LedgerBlock(
                block_index=new_index,
                timestamp_epoch_sec=now_epoch,
                previous_block_caid=prev_caid,
                enclave_warrant=enclave_warrant,
                device_telemetry=device_telemetry,
                block_caid=block_caid,
                signature_hex=sig.hex(),
                public_key_hex=pub_bytes.hex(),
            )

            # Append to JSONL file
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(block.to_dict()) + "\n")

            return block

    def verify_chain_integrity(
        self,
        pinned_pubkey_hex: Optional[str] = None,
    ) -> Tuple[bool, int, str]:
        """
        Verifies the cryptographic and hash-chain integrity of the ledger from genesis to head.
        Returns (is_valid, block_count, error_code).
        """
        with self._lock:
            blocks = self._read_all_blocks_unlocked()
            if not blocks:
                return True, 0, "EMPTY_LEDGER"

            expected_prev_caid = GENESIS_BLOCK_CAID

            for idx, block in enumerate(blocks):
                # 1. Monotonic index check
                if block.block_index != idx:
                    return False, idx, f"ERR_BLOCK_INDEX_MISMATCH_EXPECTED_{idx}_GOT_{block.block_index}"

                # 2. Previous CAID hash-chain link check
                if block.previous_block_caid != expected_prev_caid:
                    return False, idx, f"ERR_PREVIOUS_CAID_CHAIN_BROKEN_AT_{idx}"

                # 3. Pinned public key check
                if pinned_pubkey_hex and block.public_key_hex != pinned_pubkey_hex:
                    return False, idx, "ERR_UNPINNED_LEDGER_PUBLIC_KEY"

                # 4. Recompute canonical JCS body CAID
                body_to_verify = {
                    "block_index": block.block_index,
                    "timestamp_epoch_sec": block.timestamp_epoch_sec,
                    "previous_block_caid": block.previous_block_caid,
                    "enclave_warrant": block.enclave_warrant,
                    "device_telemetry": block.device_telemetry,
                }
                canonical_bytes = encode_jcs(body_to_verify)
                computed_caid = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"

                if block.block_caid != computed_caid:
                    return False, idx, f"ERR_BLOCK_CAID_TAMPER_AT_{idx}"

                # 5. Verify Ed25519 signature
                try:
                    pub_key = ed25519.Ed25519PublicKey.from_public_bytes(
                        bytes.fromhex(block.public_key_hex)
                    )
                    pub_key.verify(bytes.fromhex(block.signature_hex), canonical_bytes)
                except Exception:
                    return False, idx, f"ERR_INVALID_SIGNATURE_AT_{idx}"

                # Advance expected previous CAID
                expected_prev_caid = block.block_caid

            return True, len(blocks), "OK"

    def export_cold_storage_bundle(self, export_dir: Path) -> Path:
        """
        Exports the ledger into an external directory (e.g. connected USB-C SSD).
        """
        export_dir.mkdir(parents=True, exist_ok=True)
        dest_file = export_dir / self.ledger_path.name
        with self._lock:
            shutil.copy2(self.ledger_path, dest_file)
        return dest_file

    def _read_all_blocks_unlocked(self) -> List[LedgerBlock]:
        if not self.ledger_path.exists():
            return []
        blocks: List[LedgerBlock] = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                d = json.loads(line_str)
                blocks.append(
                    LedgerBlock(
                        block_index=d["block_index"],
                        timestamp_epoch_sec=d["timestamp_epoch_sec"],
                        previous_block_caid=d["previous_block_caid"],
                        enclave_warrant=d["enclave_warrant"],
                        device_telemetry=d["device_telemetry"],
                        block_caid=d["block_caid"],
                        signature_hex=d["signature_hex"],
                        public_key_hex=d["public_key_hex"],
                    )
                )
        return blocks
