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
tests/test_oram_memory_shuffler.py — Comprehensive Unit & Cleanroom Verification Suite
for Verifiable Oblivious RAM (ORAM) Memory Shuffler Scaffold.
"""

import os
import secrets
import sqlite3
import pytest

from src.oram_memory_shuffler import (
    ORAMBlock,
    ORAMTreeConfig,
    VerifiableORAMShuffler,
    DUMMY_BLOCK_ID,
    HEADER_SIZE,
    HALT_ORAM_MERKLE_MISMATCH,
    HALT_ORAM_DECRYPTION_FAILED,
    HALT_ORAM_STASH_OVERFLOW,
    HALT_ORAM_INVALID_BLOCK_ID,
)


def test_01_config_and_block_validations(tmp_path):
    # Test default configuration values
    default_cfg = ORAMTreeConfig(tree_id="default_tree")
    assert default_cfg.depth_L == 4
    assert default_cfg.bucket_capacity_Z == 4
    assert default_cfg.block_size_bytes == 256
    assert default_cfg.max_stash_blocks == 64

    # Invalid config checks
    with pytest.raises(ValueError, match="tree_id must be a non-empty string"):
        ORAMTreeConfig(tree_id="")
    with pytest.raises(ValueError, match="depth_L must be an integer between 1 and 16"):
        ORAMTreeConfig(tree_id="test", depth_L=0)
    with pytest.raises(ValueError, match="depth_L must be an integer between 1 and 16"):
        ORAMTreeConfig(tree_id="test", depth_L=17)
    with pytest.raises(ValueError, match="bucket_capacity_Z must be positive"):
        ORAMTreeConfig(tree_id="test", bucket_capacity_Z=0)
    with pytest.raises(ValueError, match="block_size_bytes must be at least 16 bytes"):
        ORAMTreeConfig(tree_id="test", block_size_bytes=10)
    with pytest.raises(ValueError, match="max_stash_blocks must be at least 2 \\* bucket_capacity_Z"):
        ORAMTreeConfig(tree_id="test", bucket_capacity_Z=4, max_stash_blocks=5)

    cfg = ORAMTreeConfig(tree_id="t1", depth_L=3, bucket_capacity_Z=2, block_size_bytes=64)
    assert cfg.num_leaves == 8
    assert cfg.num_nodes == 15
    assert cfg.raw_bucket_bytes == 2 * (HEADER_SIZE + 64)

    # Block validations
    dummy = ORAMBlock.create_dummy(64)
    assert dummy.is_dummy() is True
    assert dummy.block_id == DUMMY_BLOCK_ID
    assert len(dummy.payload) == 64

    serialized = dummy.serialize(64)
    deserialized = ORAMBlock.deserialize(serialized, 64)
    assert deserialized.block_id == DUMMY_BLOCK_ID
    assert deserialized.payload == dummy.payload

    with pytest.raises(ValueError, match="does not match block_size"):
        dummy.serialize(32)
    with pytest.raises(ValueError, match="does not match expected"):
        ORAMBlock.deserialize(serialized[:20], 64)


def test_02_tree_initialization_and_metadata(tmp_path):
    db_file = str(tmp_path / "oram_test.db")
    cfg = ORAMTreeConfig(tree_id="tree_alpha", depth_L=2, bucket_capacity_Z=2, block_size_bytes=32)
    # depth_L=2 => 4 leaves, 7 nodes (0..6)
    shuffler = VerifiableORAMShuffler(db_file, cfg)

    assert shuffler.get_stash_size() == 0
    assert shuffler.get_position_map_size() == 0
    root_hex = shuffler.get_merkle_root()
    assert len(root_hex) == 64

    # Verify tables created
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM oram_buckets WHERE tree_id = 'tree_alpha'")
    assert cur.fetchone()[0] == 7

    cur.execute("SELECT depth_l, bucket_z, merkle_root FROM oram_metadata WHERE tree_id = 'tree_alpha'")
    row = cur.fetchone()
    assert row[0] == 2
    assert row[1] == 2
    assert row[2].hex() == root_hex
    conn.close()

    # Re-instantiate with existing DB
    shuffler2 = VerifiableORAMShuffler(db_file, cfg, encryption_key=shuffler._key)
    assert shuffler2.get_merkle_root() == root_hex

    # Re-instantiate with mismatched config
    bad_cfg = ORAMTreeConfig(tree_id="tree_alpha", depth_L=3, bucket_capacity_Z=2, block_size_bytes=32)
    with pytest.raises(ValueError, match="Database configuration differs"):
        VerifiableORAMShuffler(db_file, bad_cfg, encryption_key=shuffler._key)


def test_03_nominal_write_and_read_roundtrip(tmp_path):
    db_file = str(tmp_path / "oram_roundtrip.db")
    cfg = ORAMTreeConfig(tree_id="tree_rw", depth_L=2, bucket_capacity_Z=2, block_size_bytes=32)
    shuffler = VerifiableORAMShuffler(db_file, cfg)

    init_root = shuffler.get_merkle_root()

    # Write block 1
    p1 = b"agent_secret_data_block_1"
    meta1 = shuffler.write_block(1, p1)
    assert meta1["block_id"] == 1
    assert meta1["merkle_root"] != init_root
    assert shuffler.get_position_map_size() == 1

    # Read block 1
    read_p1 = shuffler.read_block(1)
    assert read_p1 is not None
    assert read_p1.startswith(p1)
    assert len(read_p1) == 32

    # Write block 2
    p2 = b"agent_secret_data_block_2"
    shuffler.write_block(2, p2)
    assert shuffler.get_position_map_size() == 2

    # Overwrite block 1 with new data
    p1_v2 = b"updated_agent_secret_block_1"
    shuffler.write_block(1, p1_v2)

    read_p1_v2 = shuffler.read_block(1)
    assert read_p1_v2.startswith(p1_v2)

    read_p2 = shuffler.read_block(2)
    assert read_p2.startswith(p2)


def test_04_oblivious_dummy_access(tmp_path):
    db_file = str(tmp_path / "oram_dummy.db")
    cfg = ORAMTreeConfig(tree_id="tree_dummy", depth_L=2, bucket_capacity_Z=2, block_size_bytes=32)
    shuffler = VerifiableORAMShuffler(db_file, cfg)

    # Reading an unmapped block returns None
    read_unmapped = shuffler.read_block(99)
    assert read_unmapped is None

    # Dummy access runs cleanly
    meta = shuffler.dummy_access()
    assert meta["op_type"] == "DUMMY"
    assert meta["block_id"] == DUMMY_BLOCK_ID


def test_05_fail_closed_ciphertext_tampering(tmp_path):
    db_file = str(tmp_path / "oram_tamper.db")
    cfg = ORAMTreeConfig(tree_id="tree_tamper", depth_L=2, bucket_capacity_Z=2, block_size_bytes=32)
    shuffler = VerifiableORAMShuffler(db_file, cfg)

    shuffler.write_block(5, b"secret_5")

    # Scenario A: Tamper ciphertext without updating Merkle hash -> caught by Merkle check
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT ciphertext FROM oram_buckets WHERE tree_id = 'tree_tamper' AND node_index = 0")
    ct = cur.fetchone()[0]
    tampered_ct = bytearray(ct)
    tampered_ct[5] ^= 0xFF
    cur.execute(
        "UPDATE oram_buckets SET ciphertext = ? WHERE tree_id = 'tree_tamper' AND node_index = 0",
        (bytes(tampered_ct),),
    )
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match=HALT_ORAM_MERKLE_MISMATCH):
        shuffler.read_block(5)

    # Scenario B: Directly test decryption failure when Merkle is bypassed
    with pytest.raises(ValueError, match=HALT_ORAM_DECRYPTION_FAILED):
        shuffler._decrypt_bucket(0, bytes(tampered_ct), secrets.token_bytes(12))


def test_06_fail_closed_merkle_root_and_hash_tampering(tmp_path):
    db_file = str(tmp_path / "oram_merkle.db")
    cfg = ORAMTreeConfig(tree_id="tree_merkle", depth_L=2, bucket_capacity_Z=2, block_size_bytes=32)
    shuffler = VerifiableORAMShuffler(db_file, cfg)

    shuffler.write_block(10, b"secret_10")

    # Tamper with stored merkle_hash of child node 1
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        "UPDATE oram_buckets SET merkle_hash = ? WHERE tree_id = 'tree_merkle' AND node_index = 1",
        (b"\x99" * 32,),
    )
    conn.commit()
    conn.close()

    # Also alter in-memory hash to simulate undetected or corrupted hash
    shuffler._merkle_tree[1] = b"\x99" * 32

    # Reading should fail closed due to Merkle mismatch
    with pytest.raises(ValueError, match=HALT_ORAM_MERKLE_MISMATCH):
        shuffler.read_block(10)


def test_07_fail_closed_stash_overflow(tmp_path):
    db_file = str(tmp_path / "oram_stash_overflow.db")
    # max_stash_blocks = 4 (minimum allowed for Z=2 is 2*2=4)
    cfg = ORAMTreeConfig(tree_id="tree_overflow", depth_L=1, bucket_capacity_Z=2, block_size_bytes=32, max_stash_blocks=4)
    shuffler = VerifiableORAMShuffler(db_file, cfg)

    # Artificially populate stash to capacity + 1
    for i in range(5):
        shuffler._stash[100 + i] = ORAMBlock(
            block_id=100 + i,
            version=1,
            leaf_id=0,
            payload=b"\x00" * 32,
        )

    with pytest.raises(ValueError, match=HALT_ORAM_STASH_OVERFLOW):
        shuffler.write_block(1, b"trigger_overflow")


def test_08_invalid_block_id_and_oversized_payload(tmp_path):
    db_file = str(tmp_path / "oram_invalid.db")
    cfg = ORAMTreeConfig(tree_id="tree_invalid", depth_L=2, bucket_capacity_Z=2, block_size_bytes=32)
    shuffler = VerifiableORAMShuffler(db_file, cfg)

    with pytest.raises(ValueError, match=HALT_ORAM_INVALID_BLOCK_ID):
        shuffler.read_block(-2)

    with pytest.raises(ValueError, match=HALT_ORAM_INVALID_BLOCK_ID):
        shuffler.write_block(-5, b"invalid_id")

    with pytest.raises(ValueError, match="exceeds block_size"):
        shuffler.write_block(1, b"A" * 64)


def test_09_audit_log_and_sqlite_persistence(tmp_path):
    db_file = str(tmp_path / "oram_audit.db")
    cfg = ORAMTreeConfig(tree_id="tree_audit", depth_L=2, bucket_capacity_Z=2, block_size_bytes=32)
    shuffler = VerifiableORAMShuffler(db_file, cfg)

    shuffler.write_block(1, b"data1")
    shuffler.read_block(1)
    shuffler.dummy_access()

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT op_type, block_id FROM oram_audit_log WHERE tree_id = 'tree_audit' ORDER BY log_id")
    rows = cur.fetchall()
    assert len(rows) == 3
    assert rows[0] == ("WRITE", 1)
    assert rows[1] == ("READ", 1)
    assert rows[2] == ("DUMMY", DUMMY_BLOCK_ID)
    conn.close()


def test_10_exact_mutation_boundaries(tmp_path):
    db_file = str(tmp_path / "oram_bounds.db")
    cfg = ORAMTreeConfig(tree_id="tree_bounds", depth_L=3, bucket_capacity_Z=2, block_size_bytes=32)
    shuffler = VerifiableORAMShuffler(db_file, cfg)

    # Test key validation
    with pytest.raises(ValueError, match="encryption_key must be exactly 32 bytes"):
        VerifiableORAMShuffler(str(tmp_path / "bad_key.db"), cfg, encryption_key=b"short_key")

    # Test node covers leaf boundaries
    # depth_L = 3 => 8 leaves (0..7)
    # root (node 0) covers all
    assert shuffler.node_covers_leaf(0, 0) is True
    assert shuffler.node_covers_leaf(0, 7) is True

    # node 1 (depth 1, left child) covers leaves 0..3
    assert shuffler.node_covers_leaf(1, 0) is True
    assert shuffler.node_covers_leaf(1, 3) is True
    assert shuffler.node_covers_leaf(1, 4) is False

    # node 2 (depth 1, right child) covers leaves 4..7
    assert shuffler.node_covers_leaf(2, 4) is True
    assert shuffler.node_covers_leaf(2, 7) is True
    assert shuffler.node_covers_leaf(2, 3) is False

    # Test path nodes
    path_leaf_0 = shuffler._get_path_nodes(0)
    # Leaves for depth 3 start at (1<<3)-1 = 7. Leaf 0 is node 7.
    # Parent of 7 is (7-1)//2 = 3. Parent of 3 is (3-1)//2 = 1. Parent of 1 is 0.
    assert path_leaf_0 == [7, 3, 1, 0]

    # Test epoch advancement
    assert shuffler.advance_epoch() == 2

    # Test Merkle node hash differentiation between leaf and internal node (line 335)
    import hashlib
    leaf_node_idx = (1 << shuffler.config.depth_L) - 1
    sample_digest = b"\x11" * 32
    leaf_merkle = shuffler._compute_merkle_node_hash(leaf_node_idx, sample_digest)
    expected_leaf_merkle = hashlib.sha256(b"ORAM_LEAF:" + sample_digest).digest()
    assert leaf_merkle == expected_leaf_merkle
    root_merkle = shuffler._compute_merkle_node_hash(0, sample_digest)
    assert root_merkle != expected_leaf_merkle

    # Test bucket block capacity check on encryption (line 348)
    with pytest.raises(ValueError, match="Bucket must contain exactly"):
        shuffler._encrypt_bucket(0, [])

    # Test Merkle mismatch split branches (line 438)
    # Branch 1: row["merkle_hash"] matches computed, but _merkle_tree[parent] differs
    conn = shuffler._get_connection()
    # Pick leaf 0 path: [7, 3, 1, 0]
    path = [7, 3, 1, 0]
    shuffler._merkle_tree[0] = b"\xaa" * 32
    with pytest.raises(ValueError, match=HALT_ORAM_MERKLE_MISMATCH):
        shuffler._verify_path_merkle(path, conn)

    # Branch 2: _merkle_tree[parent] matches computed, but row["merkle_hash"] differs in storage
    # Fetch real computed hash for root
    row = conn.execute("SELECT ciphertext FROM oram_buckets WHERE tree_id = ? AND node_index = 0", (cfg.tree_id,)).fetchone()
    digest = shuffler._compute_bucket_digest(row["ciphertext"])
    real_root_hash = shuffler._compute_merkle_node_hash(0, digest)
    shuffler._merkle_tree[0] = real_root_hash  # restore in-memory hash to match computed
    shuffler._merkle_root = real_root_hash
    with conn:
        conn.execute("UPDATE oram_buckets SET merkle_hash = ? WHERE tree_id = ? AND node_index = 0", (b"\xbb" * 32, cfg.tree_id))
    with pytest.raises(ValueError, match=HALT_ORAM_MERKLE_MISMATCH):
        shuffler._verify_path_merkle(path, conn)
    conn.close()

    # Test bucket candidate packing limit when stash contains more than path capacity (line 540)
    db_pack = str(tmp_path / "oram_pack.db")
    cfg_pack = ORAMTreeConfig(tree_id="tree_pack", depth_L=1, bucket_capacity_Z=2, block_size_bytes=32, max_stash_blocks=16)
    shuffler_pack = VerifiableORAMShuffler(db_pack, cfg_pack)
    # Populate stash with 6 blocks that all map to leaf 0 (path capacity is (depth+1)*Z = 2*2 = 4)
    for b in range(1, 7):
        shuffler_pack._stash[b] = ORAMBlock(block_id=b, version=1, leaf_id=0, payload=b"X" * 32)
        shuffler_pack._position_map[b] = 0
    # Access leaf 0 via read of block 1: 4 blocks packed into path nodes (2 in leaf, 2 in root), 2 remain in stash
    shuffler_pack.read_block(1)
    assert shuffler_pack.get_stash_size() == 2

    # Canonical JSON sorting and boolean checks (kills line 82 True perturbations)
    from src.oram_memory_shuffler import _canonical_json
    assert _canonical_json({"z": 1, "a": 2}) == b'{"a":2,"z":1}'
    assert _canonical_json({"k": "\u2713"}) == b'{"k":"\\u2713"}'

    # Test block_id == 0 exact boundary (kills line 463 constant 0 perturbation)
    db_zero = str(tmp_path / "oram_zero.db")
    shuffler_zero = VerifiableORAMShuffler(db_zero, ORAMTreeConfig(tree_id="t_zero", depth_L=1, bucket_capacity_Z=2, block_size_bytes=32))
    shuffler_zero.write_block(0, b"BLOCK_ZERO_DATA_PAD_TO_32_BYTES_")
    read_zero = shuffler_zero.read_block(0)
    assert read_zero == b"BLOCK_ZERO_DATA_PAD_TO_32_BYTES_"

    # Missing node in storage check (kills line 438 raise drop)
    conn_missing = shuffler._get_connection()
    with conn_missing:
        conn_missing.execute("DELETE FROM oram_buckets WHERE tree_id = ? AND node_index = 0;", (cfg.tree_id,))
    with pytest.raises(ValueError, match="not found in storage"):
        shuffler._verify_path_merkle([1, 0], conn_missing)
    conn_missing.close()

    # Raw tuple row verification (kills line 440 constant 1 perturbation)
    shuffler_tuple = VerifiableORAMShuffler(str(tmp_path / "oram_tuple.db"), ORAMTreeConfig(tree_id="t_tuple", depth_L=1, bucket_capacity_Z=2, block_size_bytes=32))
    conn_tuple = sqlite3.connect(str(tmp_path / "oram_tuple.db"))
    # Raw sqlite connection without row_factory returns tuple rows (ciphertext, merkle_hash)
    shuffler_tuple._verify_path_merkle([1, 0], conn_tuple)
    conn_tuple.close()

    # Dataclass frozenness checks on ORAMBlock
    from dataclasses import FrozenInstanceError
    blk = ORAMBlock(block_id=1, version=1, leaf_id=0, payload=b"X" * 32)
    with pytest.raises(FrozenInstanceError):
        blk.version = 2
