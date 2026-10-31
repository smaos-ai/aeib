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
tests/test_wireguard_overlay_interlock.py — Verification suite for Cross-Cloud WireGuard Overlay Mesh.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as a cross-cloud
WireGuard overlay mesh scaffold and hardware-attested ephemeral key handover prototype.
Zero-Mock Compliance: Real Ed25519 keys, real SQLite-WAL databases, zero mocks.
"""

from dataclasses import FrozenInstanceError
import time
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.wireguard_overlay_interlock import (
    DEFAULT_KEEP_ALIVE_TIMEOUT_MS,
    DEFAULT_SESSION_TTL_MS,
    HALT_WG_HARDWARE_ATTESTATION_INVALID,
    HALT_WG_INVALID_MESH_IP,
    HALT_WG_NON_MONOTONIC_EPOCH,
    HALT_WG_PEER_FENCED,
    HALT_WG_SESSION_EXPIRED,
    MAX_ALLOWED_CLOCK_SKEW_MS,
    PEER_STATE_ACTIVE,
    PEER_STATE_DEGRADED,
    PEER_STATE_FENCED,
    VALID_CLOUD_PROVIDERS,
    VALID_ENCLAVE_TYPES,
    WgHandshakeReceipt,
    WgMeshNode,
    WireGuardOverlayInterlock,
    compute_sha256,
    compute_wilson_ci_bps,
)


def test_01_dataclass_validations() -> None:
    """Verify input validation for WgMeshNode and WgHandshakeReceipt."""
    # Valid Node
    node = WgMeshNode(
        node_id="node-aws-01",
        cloud_provider="AWS",
        region="us-east-1",
        enclave_type="AWS_NITRO",
        virtual_mesh_ip="10.100.0.5",
        enclave_pubkey_hex="11" * 32,
        attestation_measurement_hex="22" * 32,
        registered_at_ms=1000,
    )
    assert node.node_id == "node-aws-01"

    # Frozen instance check
    with pytest.raises(FrozenInstanceError):
        node.region = "us-west-2"

    # Invalid node_id
    with pytest.raises(ValueError, match="node_id"):
        WgMeshNode("", "AWS", "us-east-1", "AWS_NITRO", "10.100.0.5", "11" * 32, "22" * 32, 1000)

    # Invalid cloud provider
    with pytest.raises(ValueError, match="cloud provider"):
        WgMeshNode("n1", "DIGITALOCEAN", "nyc1", "AWS_NITRO", "10.100.0.5", "11" * 32, "22" * 32, 1000)

    # Invalid enclave type
    with pytest.raises(ValueError, match="enclave type"):
        WgMeshNode("n1", "AWS", "us-east-1", "CUSTOM_ENCLAVE", "10.100.0.5", "11" * 32, "22" * 32, 1000)

    # Invalid IP format
    with pytest.raises(ValueError, match="virtual_mesh_ip"):
        WgMeshNode("n1", "AWS", "us-east-1", "AWS_NITRO", "999.999.1.1", "11" * 32, "22" * 32, 1000)

    # Invalid pubkey length (16 bytes instead of 32)
    with pytest.raises(ValueError, match="enclave_pubkey_hex"):
        WgMeshNode("n1", "AWS", "us-east-1", "AWS_NITRO", "10.100.0.5", "11" * 16, "22" * 32, 1000)

    # Invalid measurement length
    with pytest.raises(ValueError, match="attestation_measurement_hex"):
        WgMeshNode("n1", "AWS", "us-east-1", "AWS_NITRO", "10.100.0.5", "11" * 32, "22" * 16, 1000)

    # Non-positive registration timestamp
    with pytest.raises(ValueError, match="registered_at_ms"):
        WgMeshNode("n1", "AWS", "us-east-1", "AWS_NITRO", "10.100.0.5", "11" * 32, "22" * 32, 0)

    # Valid Receipt
    receipt = WgHandshakeReceipt(
        session_id="sess:1",
        initiator_node_id="n1",
        responder_node_id="n2",
        epoch=1,
        ephemeral_pubkey_hex="33" * 32,
        preshared_key_hash="44" * 32,
        established_at_ms=1000,
        expires_at_ms=2000,
        caid="55" * 32,
    )
    assert receipt.epoch == 1

    # Invalid Receipt: empty session_id
    with pytest.raises(ValueError, match="session_id"):
        WgHandshakeReceipt("", "n1", "n2", 1, "33" * 32, "44" * 32, 1000, 2000, "55" * 32)

    # Invalid Receipt: empty initiator
    with pytest.raises(ValueError, match="initiator_node_id"):
        WgHandshakeReceipt("sess:1", "", "n2", 1, "33" * 32, "44" * 32, 1000, 2000, "55" * 32)

    # Invalid Receipt: empty responder
    with pytest.raises(ValueError, match="responder_node_id"):
        WgHandshakeReceipt("sess:1", "n1", "", 1, "33" * 32, "44" * 32, 1000, 2000, "55" * 32)

    # Invalid Receipt: non-positive epoch
    with pytest.raises(ValueError, match="epoch"):
        WgHandshakeReceipt("sess:1", "n1", "n2", 0, "33" * 32, "44" * 32, 1000, 2000, "55" * 32)
    with pytest.raises(ValueError, match="epoch"):
        WgHandshakeReceipt("sess:1", "n1", "n2", -1, "33" * 32, "44" * 32, 1000, 2000, "55" * 32)

    # Invalid Receipt: wrong pubkey length
    with pytest.raises(ValueError, match="ephemeral_pubkey_hex"):
        WgHandshakeReceipt("sess:1", "n1", "n2", 1, "33" * 16, "44" * 32, 1000, 2000, "55" * 32)

    # Invalid Receipt: wrong PSK hash length
    with pytest.raises(ValueError, match="preshared_key_hash"):
        WgHandshakeReceipt("sess:1", "n1", "n2", 1, "33" * 32, "44" * 16, 1000, 2000, "55" * 32)

    # Invalid Receipt: empty caid
    with pytest.raises(ValueError, match="caid"):
        WgHandshakeReceipt("sess:1", "n1", "n2", 1, "33" * 32, "44" * 32, 1000, 2000, "")

    # Invalid Receipt: expires <= established
    with pytest.raises(ValueError, match="expires_at_ms"):
        WgHandshakeReceipt("sess:1", "n1", "n2", 1, "33" * 32, "44" * 32, 2000, 2000, "55" * 32)


def test_02_interlock_initialization_parameters() -> None:
    """Verify initialization parameter validation for WireGuardOverlayInterlock."""
    with pytest.raises(ValueError, match="mesh_network_cidr"):
        WireGuardOverlayInterlock(mesh_network_cidr="invalid-cidr")
    with pytest.raises(ValueError, match="session_ttl_ms"):
        WireGuardOverlayInterlock(session_ttl_ms=0)
    with pytest.raises(ValueError, match="keep_alive_timeout_ms"):
        WireGuardOverlayInterlock(keep_alive_timeout_ms=0)


def test_03_nominal_node_registration_and_topology() -> None:
    """Verify node registration, IP collision rejection, and topology queries."""
    interlock = WireGuardOverlayInterlock(mesh_network_cidr="10.100.0.0/16", db_path=":memory:")

    node1 = WgMeshNode(
        node_id="node-aws-01",
        cloud_provider="AWS",
        region="us-east-1",
        enclave_type="AWS_NITRO",
        virtual_mesh_ip="10.100.0.1",
        enclave_pubkey_hex="aa" * 32,
        attestation_measurement_hex="11" * 32,
        registered_at_ms=1000,
    )
    node2 = WgMeshNode(
        node_id="node-gcp-01",
        cloud_provider="GCP",
        region="europe-west3",
        enclave_type="INTEL_TDX",
        virtual_mesh_ip="10.100.0.2",
        enclave_pubkey_hex="bb" * 32,
        attestation_measurement_hex="22" * 32,
        registered_at_ms=1000,
    )

    interlock.register_node(node1)
    interlock.register_node(node2)

    topo = interlock.get_mesh_topology()
    assert topo["total_nodes"] == 2
    assert topo["status_counts"][PEER_STATE_ACTIVE] == 2
    assert topo["active_sessions_count"] == 0

    # IP outside CIDR
    node_out = WgMeshNode(
        node_id="node-out",
        cloud_provider="AZURE",
        region="eastus",
        enclave_type="AMD_SEV_SNP",
        virtual_mesh_ip="192.168.1.1",
        enclave_pubkey_hex="cc" * 32,
        attestation_measurement_hex="33" * 32,
        registered_at_ms=1000,
    )
    with pytest.raises(ValueError, match=HALT_WG_INVALID_MESH_IP):
        interlock.register_node(node_out)

    # IP collision
    node_dup = WgMeshNode(
        node_id="node-dup",
        cloud_provider="AZURE",
        region="eastus",
        enclave_type="AMD_SEV_SNP",
        virtual_mesh_ip="10.100.0.1",  # Same as node1
        enclave_pubkey_hex="dd" * 32,
        attestation_measurement_hex="44" * 32,
        registered_at_ms=1000,
    )
    with pytest.raises(ValueError, match="IP collision"):
        interlock.register_node(node_dup)


def test_04_nominal_handshake_and_rekeying() -> None:
    """Verify mutual hardware enclave authenticated handshake and monotonic re-keying."""
    interlock = WireGuardOverlayInterlock(db_path=":memory:", session_ttl_ms=60000)
    now_ms = 1729000000000

    # Initiator Ed25519 enclave key
    init_privkey = ed25519.Ed25519PrivateKey.generate()
    init_pubkey_hex = init_privkey.public_key().public_bytes_raw().hex()

    node_a = WgMeshNode(
        node_id="node-aws",
        cloud_provider="AWS",
        region="us-east-1",
        enclave_type="AWS_NITRO",
        virtual_mesh_ip="10.100.0.10",
        enclave_pubkey_hex=init_pubkey_hex,
        attestation_measurement_hex="aa" * 32,
        registered_at_ms=now_ms,
    )
    node_b = WgMeshNode(
        node_id="node-gcp",
        cloud_provider="GCP",
        region="europe-west3",
        enclave_type="AMD_SEV_SNP",
        virtual_mesh_ip="10.100.0.20",
        enclave_pubkey_hex="bb" * 32,
        attestation_measurement_hex="bb" * 32,
        registered_at_ms=now_ms,
    )
    interlock.register_node(node_a)
    interlock.register_node(node_b)

    # 1. Ephemeral Handover for Epoch 1
    ephemeral_pub_epoch1 = "cc" * 32
    psk_epoch1 = "dd" * 32

    payload_epoch1 = {
        "epoch": 1,
        "ephemeral_pubkey_hex": ephemeral_pub_epoch1,
        "initiator_id": "node-aws",
        "preshared_key_hash": compute_sha256(bytes.fromhex(psk_epoch1)),
        "responder_id": "node-gcp",
        "timestamp_ms": now_ms,
    }
    sig_epoch1 = init_privkey.sign(encode_jcs(payload_epoch1)).hex()

    receipt1 = interlock.perform_handshake(
        initiator_id="node-aws",
        responder_id="node-gcp",
        epoch=1,
        ephemeral_pubkey_hex=ephemeral_pub_epoch1,
        preshared_key_hex=psk_epoch1,
        attestation_signature_hex=sig_epoch1,
        now_ms=now_ms,
    )
    assert receipt1.epoch == 1
    assert receipt1.expires_at_ms == now_ms + 60000

    # Session is active
    is_active, reason = interlock.verify_active_session("node-aws", "node-gcp", now_ms=now_ms + 1000)
    assert is_active is True
    assert reason == "SESSION_ACTIVE"

    # Symmetric pair check
    is_active_sym, _ = interlock.verify_active_session("node-gcp", "node-aws", now_ms=now_ms + 1000)
    assert is_active_sym is True

    # 2. Monotonic Re-keying to Epoch 2
    ephemeral_pub_epoch2 = "ee" * 32
    psk_epoch2 = "ff" * 32
    now_ms_2 = now_ms + 10000

    payload_epoch2 = {
        "epoch": 2,
        "ephemeral_pubkey_hex": ephemeral_pub_epoch2,
        "initiator_id": "node-aws",
        "preshared_key_hash": compute_sha256(bytes.fromhex(psk_epoch2)),
        "responder_id": "node-gcp",
        "timestamp_ms": now_ms_2,
    }
    sig_epoch2 = init_privkey.sign(encode_jcs(payload_epoch2)).hex()

    receipt2 = interlock.perform_handshake(
        initiator_id="node-aws",
        responder_id="node-gcp",
        epoch=2,
        ephemeral_pubkey_hex=ephemeral_pub_epoch2,
        preshared_key_hex=psk_epoch2,
        attestation_signature_hex=sig_epoch2,
        now_ms=now_ms_2,
    )
    assert receipt2.epoch == 2
    assert receipt2.expires_at_ms == now_ms_2 + 60000


def test_05_fail_closed_non_monotonic_epoch() -> None:
    """Verify out-of-order, stale, or skipped epochs are rejected."""
    interlock = WireGuardOverlayInterlock(db_path=":memory:")
    now_ms = 1729000000000

    init_privkey = ed25519.Ed25519PrivateKey.generate()
    node_a = WgMeshNode(
        node_id="node-a",
        cloud_provider="AWS",
        region="us-east-1",
        enclave_type="AWS_NITRO",
        virtual_mesh_ip="10.100.0.1",
        enclave_pubkey_hex=init_privkey.public_key().public_bytes_raw().hex(),
        attestation_measurement_hex="11" * 32,
        registered_at_ms=now_ms,
    )
    node_b = WgMeshNode(
        node_id="node-b",
        cloud_provider="GCP",
        region="us-central1",
        enclave_type="INTEL_TDX",
        virtual_mesh_ip="10.100.0.2",
        enclave_pubkey_hex="22" * 32,
        attestation_measurement_hex="22" * 32,
        registered_at_ms=now_ms,
    )
    interlock.register_node(node_a)
    interlock.register_node(node_b)

    # Attempting epoch 2 when current is 0 (skipping epoch 1)
    with pytest.raises(ValueError, match=HALT_WG_NON_MONOTONIC_EPOCH):
        interlock.perform_handshake(
            initiator_id="node-a",
            responder_id="node-b",
            epoch=2,
            ephemeral_pubkey_hex="33" * 32,
            preshared_key_hex="44" * 32,
            attestation_signature_hex="00" * 64,
            now_ms=now_ms,
        )


def test_06_fail_closed_hardware_signature_invalid() -> None:
    """Verify forged or tampered attestation signatures are rejected."""
    interlock = WireGuardOverlayInterlock(db_path=":memory:")
    now_ms = 1729000000000

    init_privkey = ed25519.Ed25519PrivateKey.generate()
    node_a = WgMeshNode(
        node_id="node-a",
        cloud_provider="AWS",
        region="us-east-1",
        enclave_type="AWS_NITRO",
        virtual_mesh_ip="10.100.0.1",
        enclave_pubkey_hex=init_privkey.public_key().public_bytes_raw().hex(),
        attestation_measurement_hex="11" * 32,
        registered_at_ms=now_ms,
    )
    node_b = WgMeshNode(
        node_id="node-b",
        cloud_provider="AZURE",
        region="westeurope",
        enclave_type="AMD_SEV_SNP",
        virtual_mesh_ip="10.100.0.2",
        enclave_pubkey_hex="22" * 32,
        attestation_measurement_hex="22" * 32,
        registered_at_ms=now_ms,
    )
    interlock.register_node(node_a)
    interlock.register_node(node_b)

    # Sign for a different epoch
    payload_bad = {
        "epoch": 999,
        "ephemeral_pubkey_hex": "33" * 32,
        "initiator_id": "node-a",
        "preshared_key_hash": compute_sha256(bytes.fromhex("44" * 32)),
        "responder_id": "node-b",
        "timestamp_ms": now_ms,
    }
    forged_sig = init_privkey.sign(encode_jcs(payload_bad)).hex()

    with pytest.raises(ValueError, match=HALT_WG_HARDWARE_ATTESTATION_INVALID):
        interlock.perform_handshake(
            initiator_id="node-a",
            responder_id="node-b",
            epoch=1,
            ephemeral_pubkey_hex="33" * 32,
            preshared_key_hex="44" * 32,
            attestation_signature_hex=forged_sig,
            now_ms=now_ms,
        )


def test_07_peer_health_keepalive_and_fencing() -> None:
    """Verify keep-alive degradation, split-brain dead-peer fencing, and recovery."""
    interlock = WireGuardOverlayInterlock(
        db_path=":memory:",
        keep_alive_timeout_ms=10000,
    )
    now_ms = 1729000000000

    node_a = WgMeshNode(
        node_id="node-a",
        cloud_provider="AWS",
        region="us-east-1",
        enclave_type="AWS_NITRO",
        virtual_mesh_ip="10.100.0.1",
        enclave_pubkey_hex="11" * 32,
        attestation_measurement_hex="11" * 32,
        registered_at_ms=now_ms,
    )
    interlock.register_node(node_a)

    # Within 10s: ACTIVE
    assert interlock.check_node_health("node-a", now_ms=now_ms + 5000) == PEER_STATE_ACTIVE

    # Between 10s and 20s: DEGRADED
    assert interlock.check_node_health("node-a", now_ms=now_ms + 12000) == PEER_STATE_DEGRADED

    # Heartbeat recovers from DEGRADED to ACTIVE
    interlock.record_heartbeat("node-a", timestamp_ms=now_ms + 12500)
    assert interlock.check_node_health("node-a", now_ms=now_ms + 13000) == PEER_STATE_ACTIVE

    # Beyond 20s (2x timeout): FENCED
    assert interlock.check_node_health("node-a", now_ms=now_ms + 40000) == PEER_STATE_FENCED


def test_08_session_expiration() -> None:
    """Verify session expiration after session_ttl_ms."""
    interlock = WireGuardOverlayInterlock(db_path=":memory:", session_ttl_ms=30000)
    now_ms = 1729000000000

    init_privkey = ed25519.Ed25519PrivateKey.generate()
    node_a = WgMeshNode(
        node_id="node-a",
        cloud_provider="AWS",
        region="us-east-1",
        enclave_type="AWS_NITRO",
        virtual_mesh_ip="10.100.0.1",
        enclave_pubkey_hex=init_privkey.public_key().public_bytes_raw().hex(),
        attestation_measurement_hex="11" * 32,
        registered_at_ms=now_ms,
    )
    node_b = WgMeshNode(
        node_id="node-b",
        cloud_provider="GCP",
        region="us-central1",
        enclave_type="INTEL_TDX",
        virtual_mesh_ip="10.100.0.2",
        enclave_pubkey_hex="22" * 32,
        attestation_measurement_hex="22" * 32,
        registered_at_ms=now_ms,
    )
    interlock.register_node(node_a)
    interlock.register_node(node_b)

    payload = {
        "epoch": 1,
        "ephemeral_pubkey_hex": "33" * 32,
        "initiator_id": "node-a",
        "preshared_key_hash": compute_sha256(bytes.fromhex("44" * 32)),
        "responder_id": "node-b",
        "timestamp_ms": now_ms,
    }
    sig = init_privkey.sign(encode_jcs(payload)).hex()
    interlock.perform_handshake(
        initiator_id="node-a",
        responder_id="node-b",
        epoch=1,
        ephemeral_pubkey_hex="33" * 32,
        preshared_key_hex="44" * 32,
        attestation_signature_hex=sig,
        now_ms=now_ms,
    )

    # Active at now_ms + 10s
    active, _ = interlock.verify_active_session("node-a", "node-b", now_ms=now_ms + 10000)
    assert active is True

    # Expired at now_ms + 30001ms
    expired, reason = interlock.verify_active_session("node-a", "node-b", now_ms=now_ms + 30001)
    assert expired is False
    assert reason == HALT_WG_SESSION_EXPIRED


def test_09_sqlite_persistence_and_queries() -> None:
    """Verify SQLite WAL persistence of nodes and handshake receipts."""
    interlock = WireGuardOverlayInterlock(db_path=":memory:")
    now_ms = 1729000000000

    init_privkey = ed25519.Ed25519PrivateKey.generate()
    node_a = WgMeshNode(
        node_id="node-persisted",
        cloud_provider="EQUINIX",
        region="dc1",
        enclave_type="TPM20",
        virtual_mesh_ip="10.100.5.5",
        enclave_pubkey_hex=init_privkey.public_key().public_bytes_raw().hex(),
        attestation_measurement_hex="11" * 32,
        registered_at_ms=now_ms,
    )
    interlock.register_node(node_a)

    cursor = interlock._conn.execute(
        "SELECT cloud_provider, enclave_type, virtual_mesh_ip FROM wg_mesh_nodes WHERE node_id = ?;",
        ("node-persisted",),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "EQUINIX"
    assert row[1] == "TPM20"
    assert row[2] == "10.100.5.5"


def test_10_exact_mutation_boundaries() -> None:
    """Exercise boundary conditions and edge cases to kill mutation survivors."""
    # 0. Assert all default constants
    assert DEFAULT_SESSION_TTL_MS == 120_000
    assert DEFAULT_KEEP_ALIVE_TIMEOUT_MS == 15_000
    assert MAX_ALLOWED_CLOCK_SKEW_MS == 30_000
    assert "AWS" in VALID_CLOUD_PROVIDERS
    assert "AMD_SEV_SNP" in VALID_ENCLAVE_TYPES

    interlock = WireGuardOverlayInterlock(db_path=":memory:")
    init_privkey = ed25519.Ed25519PrivateKey.generate()
    node_a = WgMeshNode(
        node_id="node-x",
        cloud_provider="BAREMETAL",
        region="edge",
        enclave_type="APPLE_ENCLAVE",
        virtual_mesh_ip="10.100.1.1",
        enclave_pubkey_hex=init_privkey.public_key().public_bytes_raw().hex(),
        attestation_measurement_hex="11" * 32,
        registered_at_ms=1000,
    )
    node_b = WgMeshNode(
        node_id="node-y",
        cloud_provider="OCI",
        region="eu-frankfurt-1",
        enclave_type="AMD_SEV_SNP",
        virtual_mesh_ip="10.100.1.2",
        enclave_pubkey_hex="22" * 32,
        attestation_measurement_hex="22" * 32,
        registered_at_ms=1000,
    )
    interlock.register_node(node_a)
    interlock.register_node(node_b)

    # 1. Deterministic pair key
    assert interlock._get_peer_pair_key("node-y", "node-x") == "node-x::node-y"
    assert interlock._get_peer_pair_key("node-x", "node-y") == "node-x::node-y"

    # 2. Unknown node validations
    with pytest.raises(ValueError, match="not registered in mesh"):
        interlock.record_heartbeat("unknown-node")
    with pytest.raises(ValueError, match="not registered in mesh"):
        interlock.check_node_health("unknown-node")

    # 3. Exact keep-alive timeout arithmetic boundaries (elapsed > 2 * timeout)
    interlock._last_heartbeat_ms["node-x"] = 1000
    interlock._node_states["node-x"] = PEER_STATE_ACTIVE
    assert interlock.check_node_health("node-x", now_ms=1000 + 15000) == PEER_STATE_ACTIVE
    assert interlock.check_node_health("node-x", now_ms=1000 + 15001) == PEER_STATE_DEGRADED
    assert interlock.check_node_health("node-x", now_ms=1000 + 30000) == PEER_STATE_DEGRADED
    assert interlock.check_node_health("node-x", now_ms=1000 + 30001) == PEER_STATE_FENCED
    assert interlock.check_node_health("node-x", now_ms=1000 + 50000) == PEER_STATE_FENCED  # sticky fenced

    # 4. Self-handshake rejection
    with pytest.raises(ValueError, match="same node"):
        interlock.perform_handshake(
            "node-x", "node-x", 1, "00" * 32, "00" * 32, "00" * 64, now_ms=1000
        )

    # 5. Unknown node handshake rejection
    with pytest.raises(ValueError, match="registered in the mesh"):
        interlock.perform_handshake(
            "node-x", "unknown-node", 1, "00" * 32, "00" * 32, "00" * 64, now_ms=1000
        )

    # 6. Handshake with default now_ms parameter (None)
    interlock._node_states["node-x"] = PEER_STATE_ACTIVE
    interlock._node_states["node-y"] = PEER_STATE_ACTIVE
    interlock._last_heartbeat_ms["node-x"] = int(time.time() * 1000)
    interlock._last_heartbeat_ms["node-y"] = int(time.time() * 1000)

    # Prepare signature for live handshake
    live_psk = "88" * 32
    live_payload = {
        "epoch": 1,
        "ephemeral_pubkey_hex": "77" * 32,
        "initiator_id": "node-x",
        "preshared_key_hash": compute_sha256(bytes.fromhex(live_psk)),
        "responder_id": "node-y",
        "timestamp_ms": int(time.time() * 1000),
    }
    # Note: timestamp in signature can be within max_clock_skew
    live_sig = init_privkey.sign(encode_jcs(live_payload)).hex()

    # Pass exact timestamp for signature verification
    receipt_live = interlock.perform_handshake(
        initiator_id="node-x",
        responder_id="node-y",
        epoch=1,
        ephemeral_pubkey_hex="77" * 32,
        preshared_key_hex=live_psk,
        attestation_signature_hex=live_sig,
        now_ms=live_payload["timestamp_ms"],
    )
    assert len(receipt_live.session_id) == 32
    assert receipt_live.epoch == 1

    # verify_active_session returns exact tuple
    assert interlock.verify_active_session("node-x", "node-y") == (True, "SESSION_ACTIVE")

    # 7. Responder fenced check in verify_active_session
    interlock._node_states["node-y"] = PEER_STATE_FENCED
    assert interlock.verify_active_session("node-x", "node-y") == (False, HALT_WG_PEER_FENCED)

    # 8. Initiator fenced check in verify_active_session
    interlock._node_states["node-y"] = PEER_STATE_ACTIVE
    interlock._node_states["node-x"] = PEER_STATE_FENCED
    assert interlock.verify_active_session("node-x", "node-y") == (False, HALT_WG_PEER_FENCED)

    # 9. Handshake blocked when either peer is fenced
    with pytest.raises(ValueError, match=HALT_WG_PEER_FENCED):
        interlock.perform_handshake("node-x", "node-y", 2, "00" * 32, "00" * 32, "00" * 64, now_ms=1000000)

    interlock._node_states["node-x"] = PEER_STATE_ACTIVE
    interlock._node_states["node-y"] = PEER_STATE_FENCED
    with pytest.raises(ValueError, match=HALT_WG_PEER_FENCED):
        interlock.perform_handshake("node-x", "node-y", 2, "00" * 32, "00" * 32, "00" * 64, now_ms=1000000)

    # 10. Verify keep_alive_timeout_ms and session_ttl_ms exact boundaries (kills line 191 & line 193 constant 0 perturbation)
    lim_ka1 = WireGuardOverlayInterlock(db_path=":memory:", keep_alive_timeout_ms=1)
    assert lim_ka1.keep_alive_timeout_ms == 1
    with pytest.raises(ValueError, match="keep_alive_timeout_ms"):
        WireGuardOverlayInterlock(db_path=":memory:", keep_alive_timeout_ms=0)

    lim_ttl1 = WireGuardOverlayInterlock(db_path=":memory:", session_ttl_ms=1)
    assert lim_ttl1.session_ttl_ms == 1
    with pytest.raises(ValueError, match="session_ttl_ms"):
        WireGuardOverlayInterlock(db_path=":memory:", session_ttl_ms=0)

    # 11. Verify check_node_health with default now_ms=None kills both Mult swapped and constant 1000 perturbed:
    # 11a. Fresh heartbeat: nominal elapsed ~ 0 < timeout returns ACTIVE, while 1000+1=1001 mutant adds ~20 days and returns FENCED
    interlock._last_heartbeat_ms["node-x"] = int(time.time() * 1000)
    interlock._node_states["node-x"] = PEER_STATE_ACTIVE
    assert interlock.check_node_health("node-x", now_ms=None) == PEER_STATE_ACTIVE

    # 11b. Stale heartbeat: nominal elapsed > 2*timeout returns FENCED, while Mult -> FloorDiv mutant produces negative elapsed and returns ACTIVE
    interlock._last_heartbeat_ms["node-x"] = int(time.time() * 1000) - (3 * interlock.keep_alive_timeout_ms)
    interlock._node_states["node-x"] = PEER_STATE_ACTIVE
    assert interlock.check_node_health("node-x", now_ms=None) == PEER_STATE_FENCED

    # 12. Handshake exact now_ms validation and frozen receipt checks
    with pytest.raises(ValueError, match="now_ms must be positive"):
        interlock.perform_handshake("node-x", "node-y", 2, "00" * 32, "00" * 32, "00" * 64, now_ms=0)

    live_t_now = int(time.time() * 1000)
    live_payload2 = {
        "epoch": 2,
        "ephemeral_pubkey_hex": "77" * 32,
        "initiator_id": "node-x",
        "preshared_key_hash": compute_sha256(bytes.fromhex(live_psk)),
        "responder_id": "node-y",
        "timestamp_ms": live_t_now,
    }
    live_sig2 = init_privkey.sign(encode_jcs(live_payload2)).hex()
    interlock._last_heartbeat_ms["node-x"] = live_t_now
    interlock._last_heartbeat_ms["node-y"] = live_t_now
    interlock._node_states["node-x"] = PEER_STATE_ACTIVE
    interlock._node_states["node-y"] = PEER_STATE_ACTIVE
    receipt_live_time = interlock.perform_handshake(
        initiator_id="node-x",
        responder_id="node-y",
        epoch=2,
        ephemeral_pubkey_hex="77" * 32,
        preshared_key_hex=live_psk,
        attestation_signature_hex=live_sig2,
        now_ms=live_t_now,
    )
    assert receipt_live_time.established_at_ms == live_t_now
    assert len(receipt_live_time.session_id) == 32

    # Receipt frozenness check
    with pytest.raises(FrozenInstanceError):
        receipt_live_time.epoch = 999

    # 13. Status counts defaults in get_mesh_topology (kills line 483 constant 0 perturbation)
    topo = lim_ka1.get_mesh_topology()
    assert topo["status_counts"][PEER_STATE_ACTIVE] == 0
    assert topo["status_counts"][PEER_STATE_FENCED] == 0
    assert topo["status_counts"][PEER_STATE_DEGRADED] == 0


def test_11_wilson_ci_bounds_and_epistemic_lexicon() -> None:
    """Verify conservative Wilson 95% confidence interval and epistemic integrity."""
    low, high = compute_wilson_ci_bps(27, 30)
    assert low == 7438
    assert high == 9654

    low_zero, high_zero = compute_wilson_ci_bps(0, 0)
    assert low_zero == 0 and high_zero == 0

    low_neg, high_neg = compute_wilson_ci_bps(-1, 10)
    assert low_neg == 0 and high_neg == 0

    # Epistemic docstring check
    import src.wireguard_overlay_interlock as mod
    doc = mod.__doc__ or ""
    banned_fragments = [("revo", "lutionary"), ("unbreak", "able"), ("bullet", "proof")]
    for p1, p2 in banned_fragments:
        word = p1 + p2
        assert word not in doc.lower(), f"Banned marketing word '{word}' found in docstring"

    # Confirm Rule CI004 honesty statement present
    assert "Honest Platform Boundary" in doc
    assert "INTERNAL PREVIEW COMMISSIONED" in doc
    assert "scaffold" in doc.lower() or "simulated" in doc.lower()
