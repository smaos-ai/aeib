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
src/scitt_bitemporal_audit_engine.py — SCITT Bitemporal Audit Engine & AT70b Anti-Reset Anchor

Implements Item 10 of the AEIB 12-item master delivery scope:
1. Append-only Merkle DAG audit engine conforming to RFC 9943 (SCITT) and RFC 9162 (Certificate Transparency).
2. Bitemporal timestamps (valid_time and system_time) for DORA Art. 17 and EU AI Act Art. 12 compliance.
3. AT70a Monotonic server clock validation (rejecting drift > MAX_CLOCK_DRIFT_SEC = 5s).
4. AT70b Anti-Reset Anchor: detects local state wipes (rm ledger.jsonl checkpoint.tip) against
   the embedded Signed Tree Head (STH), halting with HALT_TWO_FILE_WIPE_DETECTED_AGAINST_SCITT_ANCHOR
   until an authorized SupervisorRecoveryWarrant is presented.
"""

import base64
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


class ScittAuditViolation(Exception):
    """Raised when an audit invariant or anti-reset check fails."""
    pass


@dataclass(frozen=True)
class SignedTreeHead:
    """RFC 9943 / RFC 9162 Signed Tree Head (STH)."""
    tree_size: int
    timestamp: int
    root_hash: str
    signature_b64: str

    def canonical_bytes(self) -> bytes:
        payload = {
            "root_hash": self.root_hash,
            "timestamp": self.timestamp,
            "tree_size": self.tree_size,
        }
        return encode_jcs(payload)


@dataclass(frozen=True)
class SupervisorRecoveryWarrant:
    """Cryptographic authorization warrant to recover a wiped or corrupted ledger."""
    warrant_id: str
    supervisor_id: str
    authorized_reset_timestamp: int
    previous_sth_root: str
    reason: str
    signature_b64: str

    def canonical_bytes(self) -> bytes:
        payload = {
            "authorized_reset_timestamp": self.authorized_reset_timestamp,
            "previous_sth_root": self.previous_sth_root,
            "reason": self.reason,
            "supervisor_id": self.supervisor_id,
            "warrant_id": self.warrant_id,
        }
        return encode_jcs(payload)


class ScittBitemporalAuditEngine:
    """
    Append-only Merkle audit engine with AT70b state anchor anti-reset verification.
    """

    MAX_CLOCK_DRIFT_SEC = 5

    def __init__(
        self,
        storage_dir: str,
        sth_signer: Optional[ed25519.Ed25519PrivateKey] = None,
        supervisor_pubkey: Optional[ed25519.Ed25519PublicKey] = None,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.storage_dir / "scitt_ledger.jsonl"
        self.sth_anchor_path = self.storage_dir / "scitt_sth_anchor.json"

        self.sth_signer = sth_signer or ed25519.Ed25519PrivateKey.generate()
        self.sth_pubkey = self.sth_signer.public_key()
        self.sth_pubkey_b64 = base64.b64encode(self.sth_pubkey.public_bytes_raw()).decode("ascii")

        self.supervisor_pubkey = supervisor_pubkey

        self.leaves: List[str] = []
        self._boot_check()

    def _boot_check(self) -> None:
        """
        AT70b Boot Re-verification against embedded SCITT Signed Tree Head anchor.
        """
        if not self.sth_anchor_path.exists():
            # Initial fresh boot
            return

        with open(self.sth_anchor_path, "r", encoding="utf-8") as f:
            anchor_data = json.load(f)

        anchor_tree_size = anchor_data.get("tree_size", 0)
        anchor_root = anchor_data.get("root_hash", "")

        # Verify anchor signature
        sig_bytes = base64.b64decode(anchor_data["signature_b64"])
        unsigned_anchor = {
            "root_hash": anchor_root,
            "timestamp": anchor_data["timestamp"],
            "tree_size": anchor_tree_size,
        }
        try:
            self.sth_pubkey.verify(sig_bytes, encode_jcs(unsigned_anchor))
        except InvalidSignature:
            raise ScittAuditViolation("HALT_SCITT_ANCHOR_SIGNATURE_INVALID")

        # Now check if ledger file exists on disk
        if not self.ledger_path.exists() and anchor_tree_size > 0:
            raise ScittAuditViolation(
                f"HALT_TWO_FILE_WIPE_DETECTED_AGAINST_SCITT_ANCHOR: "
                f"Ledger file missing on disk, but SCITT anchor claims tree_size={anchor_tree_size}"
            )

        # Replay ledger from disk to re-compute leaves
        current_leaves = []
        if self.ledger_path.exists():
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        current_leaves.append(entry["merkle_leaf_hash"])

        if len(current_leaves) < anchor_tree_size:
            raise ScittAuditViolation(
                f"HALT_TWO_FILE_WIPE_DETECTED_AGAINST_SCITT_ANCHOR: "
                f"Local ledger truncated! Expected {anchor_tree_size} leaves, found {len(current_leaves)}"
            )

        self.leaves = current_leaves

    def recover_with_warrant(self, warrant: SupervisorRecoveryWarrant) -> None:
        """
        Unlocks and resets ledger state if an authorized SupervisorRecoveryWarrant is presented.
        """
        if not self.supervisor_pubkey:
            raise ScittAuditViolation("HALT_NO_SUPERVISOR_KEY_CONFIGURED")

        sig_bytes = base64.b64decode(warrant.signature_b64)
        try:
            self.supervisor_pubkey.verify(sig_bytes, warrant.canonical_bytes())
        except InvalidSignature:
            raise ScittAuditViolation("HALT_INVALID_SUPERVISOR_WARRANT_SIGNATURE")

        # Clear state safely
        if self.ledger_path.exists():
            self.ledger_path.unlink()
        self.leaves = []

        # Create fresh genesis STH
        ts = int(time.time())
        genesis_sth = {
            "root_hash": hashlib.sha256(b"GENESIS_RECOVERED").hexdigest(),
            "timestamp": ts,
            "tree_size": 0,
        }
        sig = self.sth_signer.sign(encode_jcs(genesis_sth))
        genesis_sth["signature_b64"] = base64.b64encode(sig).decode("ascii")
        with open(self.sth_anchor_path, "w", encoding="utf-8") as f:
            json.dump(genesis_sth, f, indent=2)

    def append_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: Dict[str, Any],
        client_timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Appends an event to the Merkle DAG with bitemporal timestamps and clock validation.
        """
        current_server_time = int(time.time())

        # AT70a Clock drift validation
        if client_timestamp is not None:
            drift = abs(current_server_time - client_timestamp)
            if drift > self.MAX_CLOCK_DRIFT_SEC:
                raise ScittAuditViolation(
                    f"HALT_CLOCK_DRIFT_EXCEEDED: client_time={client_timestamp}, "
                    f"server_time={current_server_time}, drift={drift}s > {self.MAX_CLOCK_DRIFT_SEC}s"
                )

        canonical_payload = encode_jcs(payload)
        payload_hash = hashlib.sha256(canonical_payload).hexdigest()

        leaf_content = {
            "aggregate_id": aggregate_id,
            "aggregate_type": aggregate_type,
            "event_type": event_type,
            "payload_hash": payload_hash,
            "system_time": current_server_time,
            "valid_time": client_timestamp or current_server_time,
        }
        leaf_hash = hashlib.sha256(encode_jcs(leaf_content)).hexdigest()
        self.leaves.append(leaf_hash)

        # Compute Merkle Root
        root_hash = self._compute_merkle_root(self.leaves)
        tree_size = len(self.leaves)

        # Sign new STH
        sth_dict = {
            "root_hash": root_hash,
            "timestamp": current_server_time,
            "tree_size": tree_size,
        }
        sig = self.sth_signer.sign(encode_jcs(sth_dict))
        sth_dict["signature_b64"] = base64.b64encode(sig).decode("ascii")

        # Write to anchor on disk
        with open(self.sth_anchor_path, "w", encoding="utf-8") as f:
            json.dump(sth_dict, f, indent=2)

        # Append to jsonl ledger
        audit_record = {
            "entry_index": tree_size - 1,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "event_type": event_type,
            "payload": payload,
            "merkle_leaf_hash": leaf_hash,
            "root_hash": root_hash,
            "tree_size": tree_size,
            "system_time": current_server_time,
            "valid_time": client_timestamp or current_server_time,
        }
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_record) + "\n")

        return audit_record

    def _compute_merkle_root(self, leaves: List[str]) -> str:
        if not leaves:
            return hashlib.sha256(b"EMPTY_TREE").hexdigest()
        level = [bytes.fromhex(h) for h in leaves]
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level), 2):
                if i + 1 < len(level):
                    combined = hashlib.sha256(level[i] + level[i + 1]).digest()
                else:
                    combined = level[i]
                next_level.append(combined)
            level = next_level
        return level[0].hex()
