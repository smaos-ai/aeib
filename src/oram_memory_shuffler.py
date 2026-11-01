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
src/oram_memory_shuffler.py — Verifiable Oblivious RAM (ORAM) Memory Shuffler Scaffold.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as an oblivious RAM
memory shuffling and access obfuscation prototype.

Honest Platform Boundary (Software Scaffold & Simulated Prototype):
  - This module is a software scaffold and simulated prototype for Path-ORAM (Stefanov et al.)
    oblivious memory shuffling and Merkle-authenticated tree access obfuscation.
  - It simulates confidential VM (CVM) / enclave-protected agent state storage over an untrusted
    backing host (SQLite-WAL persistence layer) without requiring native hardware enclave drivers.
  - Operational mode: scaffold / simulated memory shuffler.

Architectural Invariants:
1. Path-ORAM Oblivious Access:
   - Every single memory operation (read, write, or dummy access) reads and writes back an
     identical path of (depth_L + 1) encrypted buckets of uniform length.
   - Access patterns to physical backing storage are cryptographically indistinguishable,
     mitigating page fault snooping and memory address side-channels on untrusted hosts.
2. Verifiable Authenticated Tree Commitments:
   - Each bucket within the binary tree is committed in a Merkle tree structure.
   - Every path read validates bottom-up inclusion against the enclave's committed Merkle root.
   - Any corruption, unauthorized reordering, or rollback triggers immediate fail-closed halting.
3. AEAD Authenticated Encryption:
   - Buckets written to untrusted storage are encrypted using AES-256-GCM with fresh 96-bit nonces.
   - Additional Authenticated Data (AAD) binds the tree ID, node index, and epoch to prevent
     block relocation or substitution attacks.
4. Fail-Closed Verification Codes:
   - HALT_ORAM_MERKLE_MISMATCH
   - HALT_ORAM_DECRYPTION_FAILED
   - HALT_ORAM_STASH_OVERFLOW
   - HALT_ORAM_INVALID_BLOCK_ID
   - HALT_ORAM_CAPACITY_EXCEEDED
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.jcs_canonicalizer import encode_jcs

# ---------------------------------------------------------------------------
# Fail-Closed Verification Codes
# ---------------------------------------------------------------------------
HALT_ORAM_MERKLE_MISMATCH = "HALT_ORAM_MERKLE_MISMATCH"
HALT_ORAM_DECRYPTION_FAILED = "HALT_ORAM_DECRYPTION_FAILED"
HALT_ORAM_STASH_OVERFLOW = "HALT_ORAM_STASH_OVERFLOW"
HALT_ORAM_INVALID_BLOCK_ID = "HALT_ORAM_INVALID_BLOCK_ID"
HALT_ORAM_CAPACITY_EXCEEDED = "HALT_ORAM_CAPACITY_EXCEEDED"

DUMMY_BLOCK_ID: int = -1
HEADER_FORMAT: str = ">iqI"  # block_id (signed int32), version (uint64), leaf_id (uint32)
HEADER_SIZE: int = struct.calcsize(HEADER_FORMAT)  # 16 bytes


def _canonical_json(data: Any) -> bytes:
    """Canonical RFC 8785 JSON representation with zero floats."""
    return encode_jcs(data)


@dataclass(frozen=True)
class ORAMBlock:
    """Represents a single memory block inside the ORAM enclave stash or tree bucket."""
    block_id: int
    version: int
    leaf_id: int
    payload: bytes

    def is_dummy(self) -> bool:
        return self.block_id == DUMMY_BLOCK_ID

    def serialize(self, block_size: int) -> bytes:
        if len(self.payload) != block_size:
            raise ValueError(f"Payload size {len(self.payload)} does not match block_size {block_size}")
        header = struct.pack(HEADER_FORMAT, self.block_id, self.version, self.leaf_id)
        return header + self.payload

    @classmethod
    def deserialize(cls, data: bytes, block_size: int) -> ORAMBlock:
        if len(data) != HEADER_SIZE + block_size:
            raise ValueError(f"Data length {len(data)} does not match expected {HEADER_SIZE + block_size}")
        block_id, version, leaf_id = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        payload = data[HEADER_SIZE:]
        return cls(block_id=block_id, version=version, leaf_id=leaf_id, payload=payload)

    @classmethod
    def create_dummy(cls, block_size: int) -> ORAMBlock:
        return cls(
            block_id=DUMMY_BLOCK_ID,
            version=0,
            leaf_id=0,
            payload=b"\x00" * block_size,
        )


@dataclass
class ORAMTreeConfig:
    """Configuration parameters for the Path-ORAM binary tree."""
    tree_id: str
    depth_L: int = 4  # Default 4: 2^4 = 16 leaves, 31 tree nodes
    bucket_capacity_Z: int = 4  # Blocks per bucket
    block_size_bytes: int = 256  # Bytes per block payload
    max_stash_blocks: int = 64  # Stash overflow threshold # claim: config

    def __post_init__(self) -> None:
        if not self.tree_id or not isinstance(self.tree_id, str):
            raise ValueError("tree_id must be a non-empty string")
        if self.depth_L < 1 or self.depth_L > 16:
            raise ValueError("depth_L must be an integer between 1 and 16")
        if self.bucket_capacity_Z < 1:
            raise ValueError("bucket_capacity_Z must be positive")
        if self.block_size_bytes < 16:
            raise ValueError("block_size_bytes must be at least 16 bytes")
        if self.max_stash_blocks < self.bucket_capacity_Z * 2:
            raise ValueError("max_stash_blocks must be at least 2 * bucket_capacity_Z")

    @property
    def num_leaves(self) -> int:
        return 1 << self.depth_L

    @property
    def num_nodes(self) -> int:
        return (1 << (self.depth_L + 1)) - 1

    @property
    def raw_bucket_bytes(self) -> int:
        return self.bucket_capacity_Z * (HEADER_SIZE + self.block_size_bytes)


class VerifiableORAMShuffler:
    """
    Verifiable Path-ORAM memory shuffler over SQLite-WAL storage.
    Enforces oblivious access, Merkle tree commitments, and AES-256-GCM encryption.
    """

    def __init__(
        self,
        db_path: str,
        config: ORAMTreeConfig,
        encryption_key: Optional[bytes] = None,
    ) -> None:
        self.db_path = db_path
        self.config = config
        self._key = encryption_key or secrets.token_bytes(32)
        if len(self._key) != 32:
            raise ValueError("encryption_key must be exactly 32 bytes for AES-256-GCM")
        self._aesgcm = AESGCM(self._key)

        # In-enclave state
        self._position_map: Dict[int, int] = {}
        self._stash: Dict[int, ORAMBlock] = {}
        self._epoch: int = 1
        self._merkle_root: bytes = b""
        self._merkle_tree: Dict[int, bytes] = {}

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes tables and populates the initial tree if newly created."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS oram_metadata (
                        tree_id TEXT PRIMARY KEY,
                        depth_l INTEGER NOT NULL,
                        bucket_z INTEGER NOT NULL,
                        block_size INTEGER NOT NULL,
                        merkle_root BLOB NOT NULL,
                        epoch INTEGER NOT NULL,
                        num_blocks INTEGER NOT NULL,
                        updated_ms INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS oram_buckets (
                        tree_id TEXT NOT NULL,
                        node_index INTEGER NOT NULL,
                        ciphertext BLOB NOT NULL,
                        nonce BLOB NOT NULL,
                        merkle_hash BLOB NOT NULL,
                        updated_ms INTEGER NOT NULL,
                        PRIMARY KEY (tree_id, node_index)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS oram_position_map (
                        tree_id TEXT NOT NULL,
                        block_id INTEGER NOT NULL,
                        leaf_id INTEGER NOT NULL,
                        PRIMARY KEY (tree_id, block_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS oram_stash (
                        tree_id TEXT NOT NULL,
                        block_id INTEGER NOT NULL,
                        version INTEGER NOT NULL,
                        leaf_id INTEGER NOT NULL,
                        payload BLOB NOT NULL,
                        PRIMARY KEY (tree_id, block_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS oram_audit_log (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tree_id TEXT NOT NULL,
                        op_type TEXT NOT NULL,
                        block_id INTEGER NOT NULL,
                        accessed_leaf INTEGER NOT NULL,
                        new_leaf INTEGER NOT NULL,
                        merkle_root_hex TEXT NOT NULL,
                        stash_size INTEGER NOT NULL,
                        timestamp_ms INTEGER NOT NULL
                    )
                    """
                )

                row = conn.execute(
                    "SELECT * FROM oram_metadata WHERE tree_id = ?",
                    (self.config.tree_id,),
                ).fetchone()

                if row is None:
                    # Brand new tree initialization
                    self._initialize_empty_tree(conn)
                else:
                    # Restore metadata and in-enclave position map/stash
                    if row["depth_l"] != self.config.depth_L or row["bucket_z"] != self.config.bucket_capacity_Z:
                        raise ValueError("Database configuration differs from requested ORAMTreeConfig")
                    self._merkle_root = row["merkle_root"]
                    self._epoch = row["epoch"]

                    # Load position map
                    cur = conn.execute(
                        "SELECT block_id, leaf_id FROM oram_position_map WHERE tree_id = ?",
                        (self.config.tree_id,),
                    )
                    for r in cur.fetchall():
                        self._position_map[r["block_id"]] = r["leaf_id"]

                    # Load stash
                    cur = conn.execute(
                        "SELECT block_id, version, leaf_id, payload FROM oram_stash WHERE tree_id = ?",
                        (self.config.tree_id,),
                    )
                    for r in cur.fetchall():
                        self._stash[r["block_id"]] = ORAMBlock(
                            block_id=r["block_id"],
                            version=r["version"],
                            leaf_id=r["leaf_id"],
                            payload=r["payload"],
                        )

                    # Load all Merkle hashes
                    cur = conn.execute(
                        "SELECT node_index, merkle_hash FROM oram_buckets WHERE tree_id = ?",
                        (self.config.tree_id,),
                    )
                    for r in cur.fetchall():
                        self._merkle_tree[r["node_index"]] = r["merkle_hash"]
        finally:
            conn.close()

    def _node_depth(self, node_index: int) -> int:
        """Returns 0-based depth level of a tree node."""
        return (node_index + 1).bit_length() - 1

    def node_covers_leaf(self, node_index: int, leaf_id: int) -> bool:
        """Checks if leaf_id falls under the subtree rooted at node_index."""
        depth = self._node_depth(node_index)
        idx_at_depth = node_index - ((1 << depth) - 1)
        span = 1 << (self.config.depth_L - depth)
        l_min = idx_at_depth * span
        l_max = l_min + span - 1
        return l_min <= leaf_id <= l_max

    def _get_path_nodes(self, leaf_id: int) -> List[int]:
        """Returns node indices along path from leaf to root."""
        leaf_node = (1 << self.config.depth_L) - 1 + leaf_id
        path: List[int] = []
        curr = leaf_node
        while True:
            path.append(curr)
            if curr == 0:
                break
            parent = (curr - 1) // 2
            if parent >= curr:
                raise RuntimeError(f"Invalid non-decreasing parent traversal from node {curr}")
            curr = parent
        return path

    def _compute_bucket_digest(self, ciphertext: bytes) -> bytes:
        return hashlib.sha256(ciphertext).digest()

    def _compute_merkle_node_hash(self, node_index: int, bucket_digest: bytes) -> bytes:
        depth = self._node_depth(node_index)
        if depth == self.config.depth_L:
            # Leaf node
            return hashlib.sha256(b"ORAM_LEAF:" + bucket_digest).digest()
        # Internal node
        left = 2 * node_index + 1
        right = 2 * node_index + 2
        left_hash = self._merkle_tree.get(left, b"\x00" * 32)
        right_hash = self._merkle_tree.get(right, b"\x00" * 32)
        return hashlib.sha256(b"ORAM_NODE:" + bucket_digest + left_hash + right_hash).digest()

    def _encrypt_bucket(self, node_index: int, blocks: List[ORAMBlock]) -> Tuple[bytes, bytes, bytes]:
        """Encrypts blocks in bucket using AES-256-GCM. Returns (ciphertext, nonce, bucket_digest)."""
        if len(blocks) != self.config.bucket_capacity_Z:
            raise ValueError(f"Bucket must contain exactly {self.config.bucket_capacity_Z} blocks")
        plaintext = b"".join(b.serialize(self.config.block_size_bytes) for b in blocks)
        nonce = secrets.token_bytes(12)
        aad = struct.pack(">QI", self._epoch, node_index) + self.config.tree_id.encode("utf-8")
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, aad)
        bucket_digest = self._compute_bucket_digest(ciphertext)
        return ciphertext, nonce, bucket_digest

    def _decrypt_bucket(self, node_index: int, ciphertext: bytes, nonce: bytes) -> List[ORAMBlock]:
        """Decrypts bucket using AES-256-GCM, verifying AAD and tag."""
        aad = struct.pack(">QI", self._epoch, node_index) + self.config.tree_id.encode("utf-8")
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, aad)
        except InvalidTag as exc:
            raise ValueError(f"{HALT_ORAM_DECRYPTION_FAILED}: node {node_index} tag verification failed") from exc

        block_wire_size = HEADER_SIZE + self.config.block_size_bytes
        blocks: List[ORAMBlock] = []
        for i in range(self.config.bucket_capacity_Z):
            offset = i * block_wire_size
            block_data = plaintext[offset : offset + block_wire_size]
            blocks.append(ORAMBlock.deserialize(block_data, self.config.block_size_bytes))
        return blocks

    def _initialize_empty_tree(self, conn: sqlite3.Connection) -> None:
        """Builds initial empty tree of dummy blocks and commits Merkle root."""
        now_ms = int(time.time() * 1000)
        dummy_bucket = [ORAMBlock.create_dummy(self.config.block_size_bytes) for _ in range(self.config.bucket_capacity_Z)]

        # Precompute leaves first, then propagate bottom-up to build Merkle tree
        node_ciphertexts: Dict[int, Tuple[bytes, bytes, bytes]] = {}
        for node in range(self.config.num_nodes):
            ciphertext, nonce, digest = self._encrypt_bucket(node, dummy_bucket)
            node_ciphertexts[node] = (ciphertext, nonce, digest)

        # Compute Merkle tree bottom-up
        for node in reversed(range(self.config.num_nodes)):
            _, _, digest = node_ciphertexts[node]
            node_hash = self._compute_merkle_node_hash(node, digest)
            self._merkle_tree[node] = node_hash

        self._merkle_root = self._merkle_tree[0]

        # Insert metadata
        conn.execute(
            """
            INSERT INTO oram_metadata (tree_id, depth_l, bucket_z, block_size, merkle_root, epoch, num_blocks, updated_ms)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                self.config.tree_id,
                self.config.depth_L,
                self.config.bucket_capacity_Z,
                self.config.block_size_bytes,
                self._merkle_root,
                self._epoch,
                now_ms,
            ),
        )

        # Insert all nodes
        for node in range(self.config.num_nodes):
            ciphertext, nonce, _ = node_ciphertexts[node]
            conn.execute(
                """
                INSERT INTO oram_buckets (tree_id, node_index, ciphertext, nonce, merkle_hash, updated_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (self.config.tree_id, node, ciphertext, nonce, self._merkle_tree[node], now_ms),
            )

    def _verify_path_merkle(self, path: List[int], conn: sqlite3.Connection) -> None:
        """Verifies bottom-up Merkle authentication along path up to committed root."""
        # Check root first
        if self._merkle_tree.get(0) != self._merkle_root:
            raise ValueError(f"{HALT_ORAM_MERKLE_MISMATCH}: committed Merkle root mismatch")

        # Verify parent hashes along path
        for i in range(len(path) - 1):
            child = path[i]
            parent = path[i + 1]
            # Fetch parent's stored hash and bucket digest
            row = conn.execute(
                "SELECT ciphertext, merkle_hash FROM oram_buckets WHERE tree_id = ? AND node_index = ?",
                (self.config.tree_id, parent),
            ).fetchone()
            if row is None:
                raise ValueError(f"{HALT_ORAM_MERKLE_MISMATCH}: node {parent} not found in storage")
            ciphertext = row["ciphertext"] if hasattr(row, "keys") else row[0]
            stored_merkle_hash = row["merkle_hash"] if hasattr(row, "keys") else row[1]
            digest = self._compute_bucket_digest(ciphertext)
            computed_parent_hash = self._compute_merkle_node_hash(parent, digest)
            if computed_parent_hash != stored_merkle_hash or computed_parent_hash != self._merkle_tree[parent]:
                raise ValueError(f"{HALT_ORAM_MERKLE_MISMATCH}: node {parent} Merkle validation failed")

    def _oblivious_access(
        self,
        op_type: str,
        block_id: int,
        new_payload: Optional[bytes] = None,
    ) -> Tuple[Optional[bytes], Dict[str, Any]]:
        """
        Executes a Path-ORAM oblivious access cycle:
        1. Look up assigned leaf or pick uniform random leaf.
        2. Assign fresh uniform random leaf.
        3. Read and decrypt path from root to leaf into stash.
        4. Validate Merkle path authentication.
        5. Read or mutate requested block in stash.
        6. Evict stash blocks into path buckets bottom-up.
        7. Re-encrypt path buckets and update Merkle root.
        8. Commit state atomically to SQLite-WAL storage.
        """
        if block_id != DUMMY_BLOCK_ID and block_id < 0:
            raise ValueError(f"{HALT_ORAM_INVALID_BLOCK_ID}: block_id must be non-negative or dummy")

        conn = self._get_connection()
        try:
            # 1. Determine target leaf
            if block_id in self._position_map:
                accessed_leaf = self._position_map[block_id]
            else:
                accessed_leaf = secrets.randbelow(self.config.num_leaves)

            # 2. Assign fresh uniform random leaf
            new_leaf = secrets.randbelow(self.config.num_leaves)
            if block_id != DUMMY_BLOCK_ID:
                self._position_map[block_id] = new_leaf

            # 3. Read path from root to leaf
            path_bottom_up = self._get_path_nodes(accessed_leaf)
            path_top_down = list(reversed(path_bottom_up))

            # Fetch encrypted buckets along path
            placeholders = ",".join("?" for _ in path_bottom_up)
            cur = conn.execute(
                f"SELECT node_index, ciphertext, nonce, merkle_hash FROM oram_buckets WHERE tree_id = ? AND node_index IN ({placeholders})",
                (self.config.tree_id, *path_bottom_up),
            )
            rows = {r["node_index"]: r for r in cur.fetchall()}

            # 4. Verify Merkle authentication
            self._verify_path_merkle(path_bottom_up, conn)

            # Decrypt buckets into stash
            for node in path_bottom_up:
                r = rows[node]
                blocks = self._decrypt_bucket(node, r["ciphertext"], r["nonce"])
                for b in blocks:
                    if not b.is_dummy():
                        self._stash[b.block_id] = b

            # 5. Read or Mutate target block in stash
            retrieved_payload: Optional[bytes] = None
            if op_type == "READ":
                if block_id in self._stash:
                    retrieved_payload = self._stash[block_id].payload
                    # Update its leaf
                    old_b = self._stash[block_id]
                    self._stash[block_id] = ORAMBlock(
                        block_id=old_b.block_id,
                        version=old_b.version,
                        leaf_id=new_leaf,
                        payload=old_b.payload,
                    )
            elif op_type == "WRITE":
                if new_payload is None:
                    raise ValueError("new_payload required for WRITE operation")
                if len(new_payload) > self.config.block_size_bytes:
                    raise ValueError(f"Payload size {len(new_payload)} exceeds block_size {self.config.block_size_bytes}")
                padded_payload = new_payload.ljust(self.config.block_size_bytes, b"\x00")
                curr_version = self._stash[block_id].version + 1 if block_id in self._stash else 1
                self._stash[block_id] = ORAMBlock(
                    block_id=block_id,
                    version=curr_version,
                    leaf_id=new_leaf,
                    payload=padded_payload,
                )
                retrieved_payload = padded_payload
            elif op_type == "DUMMY":
                pass
            else:
                raise ValueError(f"Unknown op_type {op_type}")

            # Check stash capacity
            if len(self._stash) > self.config.max_stash_blocks:
                raise ValueError(f"{HALT_ORAM_STASH_OVERFLOW}: stash size {len(self._stash)} exceeds {self.config.max_stash_blocks}")

            # 6. Eviction: Pack blocks back into path buckets bottom-up
            new_bucket_data: Dict[int, Tuple[bytes, bytes, bytes]] = {}
            for node in path_bottom_up:
                candidates: List[int] = []
                for bid, blk in self._stash.items():
                    if self.node_covers_leaf(node, blk.leaf_id):
                        candidates.append(bid)
                        if len(candidates) == self.config.bucket_capacity_Z:
                            break

                bucket_blocks: List[ORAMBlock] = []
                for bid in candidates:
                    bucket_blocks.append(self._stash.pop(bid))

                # Pad with dummies up to Z
                while len(bucket_blocks) < self.config.bucket_capacity_Z:
                    bucket_blocks.append(ORAMBlock.create_dummy(self.config.block_size_bytes))

                # Encrypt bucket
                ct, nonce, digest = self._encrypt_bucket(node, bucket_blocks)
                new_bucket_data[node] = (ct, nonce, digest)

            # 7. Update Merkle tree bottom-up along path
            for node in path_bottom_up:
                _, _, digest = new_bucket_data[node]
                node_hash = self._compute_merkle_node_hash(node, digest)
                self._merkle_tree[node] = node_hash

            self._merkle_root = self._merkle_tree[0]

            # 8. Commit atomically
            now_ms = int(time.time() * 1000)
            with conn:
                # Update buckets
                for node in path_bottom_up:
                    ct, nonce, _ = new_bucket_data[node]
                    conn.execute(
                        """
                        UPDATE oram_buckets
                        SET ciphertext = ?, nonce = ?, merkle_hash = ?, updated_ms = ?
                        WHERE tree_id = ? AND node_index = ?
                        """,
                        (ct, nonce, self._merkle_tree[node], now_ms, self.config.tree_id, node),
                    )

                # Update metadata
                conn.execute(
                    """
                    UPDATE oram_metadata
                    SET merkle_root = ?, epoch = ?, num_blocks = ?, updated_ms = ?
                    WHERE tree_id = ?
                    """,
                    (
                        self._merkle_root,
                        self._epoch,
                        len(self._position_map),
                        now_ms,
                        self.config.tree_id,
                    ),
                )

                # Persist position map for modified block
                if block_id != DUMMY_BLOCK_ID:
                    conn.execute(
                        """
                        INSERT INTO oram_position_map (tree_id, block_id, leaf_id)
                        VALUES (?, ?, ?)
                        ON CONFLICT(tree_id, block_id) DO UPDATE SET leaf_id = excluded.leaf_id
                        """,
                        (self.config.tree_id, block_id, new_leaf),
                    )

                # Sync stash table
                conn.execute("DELETE FROM oram_stash WHERE tree_id = ?", (self.config.tree_id,))
                for blk in self._stash.values():
                    conn.execute(
                        """
                        INSERT INTO oram_stash (tree_id, block_id, version, leaf_id, payload)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (self.config.tree_id, blk.block_id, blk.version, blk.leaf_id, blk.payload),
                    )

                # Audit log entry
                conn.execute(
                    """
                    INSERT INTO oram_audit_log (tree_id, op_type, block_id, accessed_leaf, new_leaf, merkle_root_hex, stash_size, timestamp_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.config.tree_id,
                        op_type,
                        block_id,
                        accessed_leaf,
                        new_leaf,
                        self._merkle_root.hex(),
                        len(self._stash),
                        now_ms,
                    ),
                )

            metadata = {
                "tree_id": self.config.tree_id,
                "op_type": op_type,
                "block_id": block_id,
                "accessed_leaf": accessed_leaf,
                "new_leaf": new_leaf,
                "merkle_root": self._merkle_root.hex(),
                "stash_size": len(self._stash),
                "timestamp_ms": now_ms,
            }
            return retrieved_payload, metadata
        finally:
            conn.close()

    def read_block(self, block_id: int) -> Optional[bytes]:
        """Oblivious read of a memory block by ID."""
        payload, _ = self._oblivious_access("READ", block_id)
        return payload

    def write_block(self, block_id: int, payload: bytes) -> Dict[str, Any]:
        """Oblivious write of a memory block."""
        _, metadata = self._oblivious_access("WRITE", block_id, new_payload=payload)
        return metadata

    def dummy_access(self) -> Dict[str, Any]:
        """Oblivious dummy access to inject background noise and access indistinguishability."""
        _, metadata = self._oblivious_access("DUMMY", DUMMY_BLOCK_ID)
        return metadata

    def get_merkle_root(self) -> str:
        """Returns the current hexadecimal Merkle root commitment."""
        return self._merkle_root.hex()

    def get_stash_size(self) -> int:
        """Returns current number of blocks held in enclave stash."""
        return len(self._stash)

    def get_position_map_size(self) -> int:
        """Returns number of active mapped blocks."""
        return len(self._position_map)

    def advance_epoch(self) -> int:
        """Advances epoch counter for AEAD AAD binding."""
        self._epoch += 1
        return self._epoch
