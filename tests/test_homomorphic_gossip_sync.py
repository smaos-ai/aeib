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
tests/test_homomorphic_gossip_sync.py — Comprehensive Unit & Cleanroom Verification Suite
for Multi-Region Byzantine Gossip Sync with Homomorphic Proof Vectors Scaffold.
"""

import os
import sqlite3
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.homomorphic_gossip_sync import (
    BN254_R,
    MAX_SCALAR_VAL,
    GossipSyncConfig,
    GossipUpdate,
    ConsensusCertificate,
    HomomorphicGossipSyncEngine,
    derive_generator_scalar,
    HALT_GOSSIP_BYZANTINE_SIGNATURE_INVALID,
    HALT_GOSSIP_HOMOMORPHIC_PROOF_FAILED,
    HALT_GOSSIP_NON_MONOTONIC_EPOCH,
    HALT_GOSSIP_QUORUM_DEFICIT,
    HALT_GOSSIP_SCALAR_OVERFLOW,
    HALT_GOSSIP_UNKNOWN_REGION,
    HALT_GOSSIP_DUPLICATE_REGION,
)


def test_01_config_and_generators_validation(tmp_path):
    from dataclasses import FrozenInstanceError

    # Test exact BN254_R constant
    assert BN254_R == 21888242871839275222246405745257275088548364400416034343698204186575808495617

    # Test default config and frozen immutability
    cfg = GossipSyncConfig(cluster_id="cluster-primary")
    assert cfg.dimension_D == 4
    assert cfg.min_regions == 4
    assert cfg.tolerated_faults_f == 1
    assert cfg.quorum_threshold == 3

    with pytest.raises(FrozenInstanceError):
        cfg.cluster_id = "mutated_cluster"

    # Invalid configs
    with pytest.raises(ValueError, match="cluster_id must be a non-empty string"):
        GossipSyncConfig(cluster_id="")
    with pytest.raises(ValueError, match="dimension_D must be between 1 and 32"):
        GossipSyncConfig(cluster_id="c", dimension_D=0)
    with pytest.raises(ValueError, match="dimension_D must be between 1 and 32"):
        GossipSyncConfig(cluster_id="c", dimension_D=33)
    with pytest.raises(ValueError, match="min_regions must be at least 4"):
        GossipSyncConfig(cluster_id="c", min_regions=3, tolerated_faults_f=0)
    with pytest.raises(ValueError, match="tolerated_faults_f must equal"):
        GossipSyncConfig(cluster_id="c", min_regions=4, tolerated_faults_f=2)

    # Generators check
    g0 = derive_generator_scalar("G_0")
    g1 = derive_generator_scalar("G_1")
    h = derive_generator_scalar("H_BLIND")
    assert 0 < g0 < BN254_R
    assert 0 < g1 < BN254_R
    assert 0 < h < BN254_R
    assert g0 != g1
    assert g0 != h


def test_02_engine_init_and_region_registration(tmp_path):
    db_file = str(tmp_path / "gossip_test.db")
    cfg = GossipSyncConfig(cluster_id="c-alpha", dimension_D=4, min_regions=4, tolerated_faults_f=1)
    engine = HomomorphicGossipSyncEngine(db_file, cfg)

    state = engine.get_active_state()
    assert state["cluster_id"] == "c-alpha"
    assert state["active_epoch"] == 0
    assert state["active_vector"] == [0, 0, 0, 0]

    # Valid region registration
    priv_key = Ed25519PrivateKey.generate()
    pub_bytes = priv_key.public_key().public_bytes_raw()
    engine.register_region("region-us-east", pub_bytes)

    # Re-registering updates cleanly
    engine.register_region("region-us-east", pub_bytes)

    # Invalid registration
    with pytest.raises(ValueError, match="region_id must be a non-empty string"):
        engine.register_region("", pub_bytes)
    with pytest.raises(ValueError, match="public_key_bytes must be exactly 32 bytes"):
        engine.register_region("region-bad", b"too_short")


def test_03_homomorphic_commitment_math(tmp_path):
    db_file = str(tmp_path / "gossip_math.db")
    cfg = GossipSyncConfig(cluster_id="c-math", dimension_D=2, min_regions=4, tolerated_faults_f=1)
    engine = HomomorphicGossipSyncEngine(db_file, cfg)

    # Test zero vector evaluates to zero when blinding is 0
    assert engine.compute_commitment([0, 0], 0) == 0

    v_a = [100, 250]
    rho_a = 987654321
    c_a = engine.compute_commitment(v_a, rho_a)

    v_b = [300, 750]
    rho_b = 123456789
    c_b = engine.compute_commitment(v_b, rho_b)

    # Homomorphic addition
    v_sum = [(v_a[i] + v_b[i]) % BN254_R for i in range(2)]
    rho_sum = (rho_a + rho_b) % BN254_R
    c_sum_direct = engine.compute_commitment(v_sum, rho_sum)
    c_sum_homomorphic = (c_a + c_b) % BN254_R

    assert c_sum_direct == c_sum_homomorphic

    # Dimension mismatch
    with pytest.raises(ValueError, match="does not match config"):
        engine.compute_commitment([1, 2, 3], 10)

    # Bounds overflow
    with pytest.raises(ValueError, match=HALT_GOSSIP_SCALAR_OVERFLOW):
        engine.compute_commitment([-1, 10], 10)
    with pytest.raises(ValueError, match=HALT_GOSSIP_SCALAR_OVERFLOW):
        engine.compute_commitment([MAX_SCALAR_VAL + 1, 10], 10)


def test_04_create_and_ingest_nominal_update(tmp_path):
    db_file = str(tmp_path / "gossip_nominal.db")
    cfg = GossipSyncConfig(cluster_id="c-nom", dimension_D=4, min_regions=4, tolerated_faults_f=1)
    engine = HomomorphicGossipSyncEngine(db_file, cfg)

    priv_key = Ed25519PrivateKey.generate()
    pub_bytes = priv_key.public_key().public_bytes_raw()
    engine.register_region("region-1", pub_bytes)

    update = engine.create_update(
        region_id="region-1",
        private_key=priv_key,
        epoch=1,
        state_vector=[10, 20, 30, 40],
    )
    assert update.region_id == "region-1"
    assert update.epoch == 1
    assert len(update.signature_hex) == 128

    ingest_res = engine.ingest_update(update)
    assert ingest_res["status"] == "INGESTED"
    assert ingest_res["epoch"] == 1
    assert ingest_res["region_id"] == "region-1"


def test_05_byzantine_consensus_round(tmp_path):
    db_file = str(tmp_path / "gossip_bft.db")
    cfg = GossipSyncConfig(cluster_id="c-bft", dimension_D=2, min_regions=4, tolerated_faults_f=1)
    engine = HomomorphicGossipSyncEngine(db_file, cfg)

    # Setup 4 regions
    regions = {}
    for r in ["r1", "r2", "r3", "r4"]:
        priv = Ed25519PrivateKey.generate()
        engine.register_region(r, priv.public_key().public_bytes_raw())
        regions[r] = priv

    # Region 1 and 2 submit updates for epoch 1
    u1 = engine.create_update("r1", regions["r1"], epoch=1, state_vector=[50, 60], blinding_factor=100)
    u2 = engine.create_update("r2", regions["r2"], epoch=1, state_vector=[70, 80], blinding_factor=200)
    engine.ingest_update(u1)
    engine.ingest_update(u2)

    # Quorum deficit: 2 updates < 3 required (2f+1)
    cert_none = engine.try_reach_consensus(1)
    assert cert_none is None
    assert engine.get_active_state()["active_epoch"] == 0

    # Region 3 submits update
    u3 = engine.create_update("r3", regions["r3"], epoch=1, state_vector=[90, 100], blinding_factor=300)
    engine.ingest_update(u3)

    # Quorum reached: 3 updates
    cert = engine.try_reach_consensus(1)
    assert cert is not None
    assert cert.epoch == 1
    assert cert.participating_regions == ["r1", "r2", "r3"]
    # Aggregated vector: [50+70+90, 60+80+100] = [210, 240]
    assert cert.aggregated_vector == [210, 240]
    assert cert.aggregated_blinding == 600

    # Active state updated
    active = engine.get_active_state()
    assert active["active_epoch"] == 1
    assert active["active_vector"] == [210, 240]

    # Verify certificate externally
    assert engine.verify_certificate(cert) is True

    # Re-instantiate engine from SQLite to verify persistence
    engine2 = HomomorphicGossipSyncEngine(db_file, cfg)
    assert engine2.get_active_state()["active_epoch"] == 1
    assert engine2.get_active_state()["active_vector"] == [210, 240]


def test_06_fail_closed_tampered_signature(tmp_path):
    db_file = str(tmp_path / "gossip_tamper_sig.db")
    cfg = GossipSyncConfig(cluster_id="c-tsig", dimension_D=2, min_regions=4, tolerated_faults_f=1)
    engine = HomomorphicGossipSyncEngine(db_file, cfg)

    priv = Ed25519PrivateKey.generate()
    engine.register_region("r1", priv.public_key().public_bytes_raw())

    u = engine.create_update("r1", priv, epoch=1, state_vector=[10, 20])

    # Corrupt signature hex
    bad_sig = "00" * 64
    bad_u = GossipUpdate(
        region_id=u.region_id,
        epoch=u.epoch,
        vector_clock=u.vector_clock,
        state_vector=u.state_vector,
        blinding_factor=u.blinding_factor,
        commitment=u.commitment,
        signature_hex=bad_sig,
        timestamp_ms=u.timestamp_ms,
    )

    with pytest.raises(ValueError, match=HALT_GOSSIP_BYZANTINE_SIGNATURE_INVALID):
        engine.ingest_update(bad_u)


def test_07_fail_closed_tampered_commitment(tmp_path):
    db_file = str(tmp_path / "gossip_tamper_comm.db")
    cfg = GossipSyncConfig(cluster_id="c-tcomm", dimension_D=2, min_regions=4, tolerated_faults_f=1)
    engine = HomomorphicGossipSyncEngine(db_file, cfg)

    priv = Ed25519PrivateKey.generate()
    engine.register_region("r1", priv.public_key().public_bytes_raw())

    # Build update with invalid commitment signed by private key
    v_clock = {"r1": 1}
    bad_comm = 123456789  # Does not match compute_commitment
    now_ms = 1729000000000
    temp = GossipUpdate(
        region_id="r1",
        epoch=1,
        vector_clock=v_clock,
        state_vector=[10, 20],
        blinding_factor=500,
        commitment=bad_comm,
        signature_hex="",
        timestamp_ms=now_ms,
    )
    sig = priv.sign(temp.signing_payload())
    signed_bad = GossipUpdate(
        region_id="r1",
        epoch=1,
        vector_clock=v_clock,
        state_vector=[10, 20],
        blinding_factor=500,
        commitment=bad_comm,
        signature_hex=sig.hex(),
        timestamp_ms=now_ms,
    )

    with pytest.raises(ValueError, match=HALT_GOSSIP_HOMOMORPHIC_PROOF_FAILED):
        engine.ingest_update(signed_bad)


def test_08_fail_closed_non_monotonic_epoch_and_duplicate_region(tmp_path):
    db_file = str(tmp_path / "gossip_epoch_dup.db")
    cfg = GossipSyncConfig(cluster_id="c-epoch", dimension_D=2, min_regions=4, tolerated_faults_f=1)
    engine = HomomorphicGossipSyncEngine(db_file, cfg)

    priv = Ed25519PrivateKey.generate()
    engine.register_region("r1", priv.public_key().public_bytes_raw())

    # Create update for epoch 0 when active is 0 raises
    with pytest.raises(ValueError, match=f"{HALT_GOSSIP_NON_MONOTONIC_EPOCH}: epoch 0 must be > active 0"):
        engine.create_update("r1", priv, epoch=0, state_vector=[1, 2])

    # Ingest update for epoch 2 when active is 0 (skipping epoch 1)
    u_future = engine.create_update("r1", priv, epoch=2, state_vector=[1, 2])
    with pytest.raises(ValueError, match=f"{HALT_GOSSIP_NON_MONOTONIC_EPOCH}: update epoch 2 != active \\+ 1 \\(1\\)"):
        engine.ingest_update(u_future)

    # Ingest nominal update for epoch 1
    u1 = engine.create_update("r1", priv, epoch=1, state_vector=[1, 2])
    engine.ingest_update(u1)

    # Duplicate ingest for same epoch from same region raises
    u1_dup = engine.create_update("r1", priv, epoch=1, state_vector=[5, 6])
    with pytest.raises(ValueError, match=HALT_GOSSIP_DUPLICATE_REGION):
        engine.ingest_update(u1_dup)

    # try_reach_consensus on wrong epoch raises
    with pytest.raises(ValueError, match=f"{HALT_GOSSIP_NON_MONOTONIC_EPOCH}: can only reach consensus for epoch 1"):
        engine.try_reach_consensus(2)
    with pytest.raises(ValueError, match=f"{HALT_GOSSIP_NON_MONOTONIC_EPOCH}: can only reach consensus for epoch 1"):
        engine.try_reach_consensus(0)


def test_09_fail_closed_unknown_region(tmp_path):
    db_file = str(tmp_path / "gossip_unknown.db")
    cfg = GossipSyncConfig(cluster_id="c-unk", dimension_D=2, min_regions=4, tolerated_faults_f=1)
    engine = HomomorphicGossipSyncEngine(db_file, cfg)

    priv = Ed25519PrivateKey.generate()
    # Region 'r_unreg' not registered
    u = engine.create_update("r_unreg", priv, epoch=1, state_vector=[1, 2])

    with pytest.raises(ValueError, match=HALT_GOSSIP_UNKNOWN_REGION):
        engine.ingest_update(u)


def test_10_exact_mutation_boundaries(tmp_path):
    from dataclasses import FrozenInstanceError

    db_file = str(tmp_path / "gossip_bounds.db")
    cfg = GossipSyncConfig(cluster_id="c-bounds", dimension_D=2, min_regions=4, tolerated_faults_f=1)
    engine = HomomorphicGossipSyncEngine(db_file, cfg)

    # Test create_update validations and scalar bounds message (line 315)
    priv = Ed25519PrivateKey.generate()
    engine.register_region("r1", priv.public_key().public_bytes_raw())

    with pytest.raises(ValueError, match="state_vector length"):
        engine.create_update("r1", priv, epoch=1, state_vector=[1])

    with pytest.raises(ValueError, match="value -1 exceeds MAX_SCALAR_VAL"):
        engine.create_update("r1", priv, epoch=1, state_vector=[-1, 2])

    with pytest.raises(ValueError, match=f"value {MAX_SCALAR_VAL + 1} exceeds MAX_SCALAR_VAL"):
        engine.create_update("r1", priv, epoch=1, state_vector=[MAX_SCALAR_VAL + 1, 2])

    # Test ConsensusCertificate frozen immutability (line 142)
    sample_cert = ConsensusCertificate(
        cluster_id="c-bounds",
        epoch=1,
        participating_regions=["r1", "r2", "r3"],
        aggregated_vector=[1, 2],
        aggregated_blinding=10,
        aggregated_commitment=engine.compute_commitment([1, 2], 10),
        signatures={"r1": "sig1", "r2": "sig2", "r3": "sig3"},
        state_digest="fake_digest",
        timestamp_ms=1000,
    )
    with pytest.raises(FrozenInstanceError):
        sample_cert.epoch = 99

    # Test verify_certificate invalid branches explicitly returning False (lines 532, 547, 560)
    # Branch 1: Mismatched cluster
    cert_wrong_cluster = ConsensusCertificate(
        cluster_id="wrong_cluster",
        epoch=1,
        participating_regions=["r1", "r2", "r3"],
        aggregated_vector=[1, 2],
        aggregated_blinding=10,
        aggregated_commitment=engine.compute_commitment([1, 2], 10),
        signatures={"r1": "sig1"},
        state_digest="fake_digest",
        timestamp_ms=1000,
    )
    res = engine.verify_certificate(cert_wrong_cluster)
    assert res is False and type(res) is bool

    # Branch 2: Deficit participating regions
    cert_deficit = ConsensusCertificate(
        cluster_id="c-bounds",
        epoch=1,
        participating_regions=["r1", "r2"],
        aggregated_vector=[1, 2],
        aggregated_blinding=10,
        aggregated_commitment=engine.compute_commitment([1, 2], 10),
        signatures={"r1": "sig1"},
        state_digest="fake_digest",
        timestamp_ms=1000,
    )
    res = engine.verify_certificate(cert_deficit)
    assert res is False and type(res) is bool

    # Branch 3: Mismatched commitment (line 532)
    cert_bad_comm = ConsensusCertificate(
        cluster_id="c-bounds",
        epoch=1,
        participating_regions=["r1", "r2", "r3"],
        aggregated_vector=[1, 2],
        aggregated_blinding=10,
        aggregated_commitment=999999999,  # Bad commitment
        signatures={"r1": "sig1", "r2": "sig2", "r3": "sig3"},
        state_digest="fake_digest",
        timestamp_ms=1000,
    )
    res = engine.verify_certificate(cert_bad_comm)
    assert res is False and type(res) is bool

    # Branch 4: Mismatched state_digest (line 547)
    valid_comm = engine.compute_commitment([1, 2], 10)
    cert_bad_digest = ConsensusCertificate(
        cluster_id="c-bounds",
        epoch=1,
        participating_regions=["r1", "r2", "r3"],
        aggregated_vector=[1, 2],
        aggregated_blinding=10,
        aggregated_commitment=valid_comm,
        signatures={"r1": "sig1", "r2": "sig2", "r3": "sig3"},
        state_digest="bad_digest_hash",
        timestamp_ms=1000,
    )
    res = engine.verify_certificate(cert_bad_digest)
    assert res is False and type(res) is bool

    # Branch 5: Missing signature for participating region
    # Compute real digest
    import hashlib
    from src.homomorphic_gossip_sync import _canonical_json
    real_digest = hashlib.sha256(
        _canonical_json(
            {
                "aggregated_commitment": hex(valid_comm),
                "aggregated_vector": [1, 2],
                "cluster_id": "c-bounds",
                "epoch": 1,
                "participating_regions": ["r1", "r2", "r3"],
            }
        )
    ).hexdigest()

    cert_missing_sig = ConsensusCertificate(
        cluster_id="c-bounds",
        epoch=1,
        participating_regions=["r1", "r2", "r3"],
        aggregated_vector=[1, 2],
        aggregated_blinding=10,
        aggregated_commitment=valid_comm,
        signatures={"r1": "sig1", "r2": "sig2"},  # r3 missing
        state_digest=real_digest,
        timestamp_ms=1000,
    )
    res = engine.verify_certificate(cert_missing_sig)
    assert res is False and type(res) is bool

    # Branch 6: Unknown region in participating list (line 560)
    cert_unregistered_reg = ConsensusCertificate(
        cluster_id="c-bounds",
        epoch=1,
        participating_regions=["r1", "r2", "r_unregistered"],
        aggregated_vector=[1, 2],
        aggregated_blinding=10,
        aggregated_commitment=valid_comm,
        signatures={"r1": "sig1", "r2": "sig2", "r_unregistered": "sig3"},
        state_digest=hashlib.sha256(
            _canonical_json(
                {
                    "aggregated_commitment": hex(valid_comm),
                    "aggregated_vector": [1, 2],
                    "cluster_id": "c-bounds",
                    "epoch": 1,
                    "participating_regions": ["r1", "r2", "r_unregistered"],
                }
            )
        ).hexdigest(),
        timestamp_ms=1000,
    )
    res = engine.verify_certificate(cert_unregistered_reg)
    assert res is False and type(res) is bool
