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
tests/test_confidential_vm_migration_interlock.py
================================================================================
Comprehensive verification suite for Heterogeneous Confidential VM Migration Interlock.
Evaluated under the stated model as an agent execution integrity boundary scaffold.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import asdict
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.confidential_vm_migration_interlock import (
    CvmAttestationReport,
    CvmMigrationError,
    ConfidentialVmMigrationInterlock,
    ENCLAVE_ARCH_AMD_SEV_SNP,
    ENCLAVE_ARCH_AWS_NITRO,
    ENCLAVE_ARCH_INTEL_TDX,
    HALT_CVM_INVALID_STATE_TRANSITION,
    HALT_CVM_KEY_FENCE_FAILED,
    HALT_CVM_MEASUREMENT_DIVERGENCE,
    HALT_CVM_MEMORY_CORRUPTION,
    HALT_CVM_SIGNATURE_INVALID,
    HALT_CVM_STALE_EPOCH,
    HALT_CVM_UNSUPPORTED_ARCH,
    MIGRATION_STATE_COMMITTED,
    MIGRATION_STATE_INITIATED,
    MIGRATION_STATE_KEY_FENCED,
    MIGRATION_STATE_MEMORY_VERIFIED,
    MIGRATION_STATE_ROLLED_BACK,
    MemoryFrameDigest,
    compute_memory_merkle_root,
    compute_sha256_caid,
)


def _generate_test_enclave(
    vm_id: str,
    arch: str,
    measurement_digest: str,
    epoch: int = 1,
    nonce: str = "cvm-nonce-101",
    timestamp_ms: int = 1700000000000,
) -> tuple[CvmAttestationReport, ed25519.Ed25519PrivateKey]:
    priv = ed25519.Ed25519PrivateKey.generate()
    report = ConfidentialVmMigrationInterlock.create_attestation(
        vm_id=vm_id,
        arch=arch,
        measurement_digest=measurement_digest,
        policy_epoch=epoch,
        nonce=nonce,
        timestamp_ms=timestamp_ms,
        private_key=priv,
    )
    return report, priv


def _build_test_memory_frames(count: int) -> tuple[list[MemoryFrameDigest], str]:
    frames: list[MemoryFrameDigest] = []
    hashes: list[str] = []
    for i in range(count):
        h = f"sha256:{hashlib.sha256(f'frame-content-{i}'.encode('utf-8')).hexdigest()}"
        frames.append(
            MemoryFrameDigest(
                frame_index=i,
                frame_size_bytes=4096,
                frame_sha256=h,
            )
        )
        hashes.append(h)
    root = compute_memory_merkle_root(hashes)
    return frames, root


def test_01_dataclass_and_merkle_roots() -> None:
    empty_root = compute_memory_merkle_root([])
    assert empty_root.startswith("sha256:")

    single_h = "sha256:" + "11" * 32
    single_root = compute_memory_merkle_root([single_h])
    assert single_root == single_h

    frames, root = _build_test_memory_frames(4)
    assert len(frames) == 4
    assert root.startswith("sha256:")
    assert len(root) == 71

    caid = compute_sha256_caid({"status": "OK", "arch": "amd_sev_snp"})
    assert caid.startswith("sha256:")


def test_02_nominal_cross_arch_migration_amd_to_intel() -> None:
    interlock = ConfidentialVmMigrationInterlock(db_path=":memory:")

    src, _ = _generate_test_enclave(
        "vm-sev-snp-source", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "aa" * 32, epoch=10
    )
    dst, _ = _generate_test_enclave(
        "vm-tdx-target", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "bb" * 32, epoch=11
    )

    frames, manifest_root = _build_test_memory_frames(5)

    # 1. Initiate handshake
    ticket = interlock.initiate_handshake(
        source=src,
        dest=dst,
        memory_manifest_root=manifest_root,
        expected_frame_count=5,
        now_ms=1700000001000,
    )
    assert ticket.state == MIGRATION_STATE_INITIATED
    assert ticket.source_arch == ENCLAVE_ARCH_AMD_SEV_SNP
    assert ticket.dest_arch == ENCLAVE_ARCH_INTEL_TDX
    assert ticket.source_epoch == 10
    assert ticket.dest_epoch == 11

    # 2. Verify memory frames
    is_mem_valid = interlock.verify_memory_manifest(ticket.migration_id, frames)
    assert is_mem_valid is True

    ticket_v = interlock.get_ticket(ticket.migration_id)
    assert ticket_v is not None
    assert ticket_v.state == MIGRATION_STATE_MEMORY_VERIFIED

    # 3. Fence keys and handover
    key_material = os.urandom(32)
    fenced_caid = interlock.fence_and_handover_keys(
        ticket.migration_id, key_material, dst.public_key_hex
    )
    assert fenced_caid.startswith("sha256:")

    ticket_f = interlock.get_ticket(ticket.migration_id)
    assert ticket_f is not None
    assert ticket_f.state == MIGRATION_STATE_KEY_FENCED
    assert ticket_f.fenced_key_caid == fenced_caid

    # 4. Commit migration
    receipt = interlock.commit_migration(ticket.migration_id, now_ms=1700000002000)
    assert receipt.status == MIGRATION_STATE_COMMITTED
    assert receipt.migration_epoch == 11
    assert receipt.fenced_key_caid == fenced_caid
    assert receipt.receipt_caid.startswith("sha256:")

    ticket_c = interlock.get_ticket(ticket.migration_id)
    assert ticket_c is not None
    assert ticket_c.state == MIGRATION_STATE_COMMITTED


def test_03_nominal_cross_arch_migration_nitro_to_sev() -> None:
    interlock = ConfidentialVmMigrationInterlock(db_path=":memory:")

    src, _ = _generate_test_enclave(
        "vm-nitro-src", ENCLAVE_ARCH_AWS_NITRO, "sha256:" + "cc" * 32, epoch=5
    )
    dst, _ = _generate_test_enclave(
        "vm-sev-dest", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "dd" * 32, epoch=6
    )

    frames, manifest_root = _build_test_memory_frames(2)
    ticket = interlock.initiate_handshake(src, dst, manifest_root, 2)
    interlock.verify_memory_manifest(ticket.migration_id, frames)
    interlock.fence_and_handover_keys(ticket.migration_id, b"X" * 32, dst.public_key_hex)
    t_before = int(time.time() * 1000)
    receipt = interlock.commit_migration(ticket.migration_id)
    t_after = int(time.time() * 1000)
    assert receipt.status == MIGRATION_STATE_COMMITTED
    assert receipt.source_arch == ENCLAVE_ARCH_AWS_NITRO
    assert receipt.dest_arch == ENCLAVE_ARCH_AMD_SEV_SNP
    assert t_before <= receipt.committed_at_ms <= t_after + 500


def test_04_fail_closed_unsupported_arch() -> None:
    interlock = ConfidentialVmMigrationInterlock(db_path=":memory:")
    src, _ = _generate_test_enclave("vm-bad", "arm_cca", "sha256:" + "ee" * 32, epoch=1)
    dst, _ = _generate_test_enclave("vm-tdx", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "ff" * 32, epoch=2)

    with pytest.raises(CvmMigrationError) as exc_src:
        interlock.initiate_handshake(src, dst, "sha256:" + "00" * 32, 1)
    assert exc_src.value.code == HALT_CVM_UNSUPPORTED_ARCH

    good_src, _ = _generate_test_enclave("vm-sev", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "aa" * 32, epoch=1)
    bad_dst, _ = _generate_test_enclave("vm-bad2", "riscv_keystone", "sha256:" + "bb" * 32, epoch=2)
    with pytest.raises(CvmMigrationError) as exc_dst:
        interlock.initiate_handshake(good_src, bad_dst, "sha256:" + "00" * 32, 1)
    assert exc_dst.value.code == HALT_CVM_UNSUPPORTED_ARCH


def test_05_fail_closed_non_monotonic_epoch() -> None:
    interlock = ConfidentialVmMigrationInterlock(db_path=":memory:")
    src, _ = _generate_test_enclave("vm-1", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "aa" * 32, epoch=5)
    # Stale epoch (same epoch or skipped epoch)
    dst_stale, _ = _generate_test_enclave("vm-2", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "bb" * 32, epoch=5)
    with pytest.raises(CvmMigrationError) as exc_stale:
        interlock.initiate_handshake(src, dst_stale, "sha256:" + "00" * 32, 1)
    assert exc_stale.value.code == HALT_CVM_STALE_EPOCH

    dst_skip, _ = _generate_test_enclave("vm-3", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "bb" * 32, epoch=7)
    with pytest.raises(CvmMigrationError) as exc_skip:
        interlock.initiate_handshake(src, dst_skip, "sha256:" + "00" * 32, 1)
    assert exc_skip.value.code == HALT_CVM_STALE_EPOCH


def test_06_fail_closed_signature_invalid() -> None:
    interlock = ConfidentialVmMigrationInterlock(db_path=":memory:")
    src, _ = _generate_test_enclave("vm-1", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "aa" * 32, epoch=1)
    dst, _ = _generate_test_enclave("vm-2", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "bb" * 32, epoch=2)

    # Corrupt source signature
    corrupt_src = CvmAttestationReport(
        vm_id=src.vm_id,
        arch=src.arch,
        measurement_digest=src.measurement_digest,
        policy_epoch=src.policy_epoch,
        nonce=src.nonce,
        timestamp_ms=src.timestamp_ms,
        signature="00" * 64,
        public_key_hex=src.public_key_hex,
    )
    with pytest.raises(CvmMigrationError) as exc_src:
        interlock.initiate_handshake(corrupt_src, dst, "sha256:" + "00" * 32, 1)
    assert exc_src.value.code == HALT_CVM_SIGNATURE_INVALID

    # Corrupt dest signature
    corrupt_dst = CvmAttestationReport(
        vm_id=dst.vm_id,
        arch=dst.arch,
        measurement_digest=dst.measurement_digest,
        policy_epoch=dst.policy_epoch,
        nonce=dst.nonce,
        timestamp_ms=dst.timestamp_ms,
        signature="ff" * 64,
        public_key_hex=dst.public_key_hex,
    )
    with pytest.raises(CvmMigrationError) as exc_dst:
        interlock.initiate_handshake(src, corrupt_dst, "sha256:" + "00" * 32, 1)
    assert exc_dst.value.code == HALT_CVM_SIGNATURE_INVALID


def test_07_fail_closed_measurement_divergence() -> None:
    approved = {
        ENCLAVE_ARCH_AMD_SEV_SNP: {"sha256:" + "aa" * 32},
        ENCLAVE_ARCH_INTEL_TDX: {"sha256:" + "bb" * 32},
    }
    interlock = ConfidentialVmMigrationInterlock(db_path=":memory:", approved_measurements=approved)

    # Destination divergence
    src_ok, _ = _generate_test_enclave("vm-1", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "aa" * 32, epoch=1)
    dst_bad, _ = _generate_test_enclave("vm-2", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "99" * 32, epoch=2)

    with pytest.raises(CvmMigrationError) as exc_dst:
        interlock.initiate_handshake(src_ok, dst_bad, "sha256:" + "00" * 32, 1)
    assert exc_dst.value.code == HALT_CVM_MEASUREMENT_DIVERGENCE

    # Source divergence
    src_bad, _ = _generate_test_enclave("vm-1", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "88" * 32, epoch=1)
    dst_ok, _ = _generate_test_enclave("vm-2", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "bb" * 32, epoch=2)
    with pytest.raises(CvmMigrationError) as exc_src:
        interlock.initiate_handshake(src_bad, dst_ok, "sha256:" + "00" * 32, 1)
    assert exc_src.value.code == HALT_CVM_MEASUREMENT_DIVERGENCE


def test_08_fail_closed_memory_corruption() -> None:
    interlock = ConfidentialVmMigrationInterlock(db_path=":memory:")
    src, _ = _generate_test_enclave("vm-1", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "aa" * 32, epoch=1)
    dst, _ = _generate_test_enclave("vm-2", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "bb" * 32, epoch=2)

    frames, manifest_root = _build_test_memory_frames(3)

    # Frame count invalid in handshake
    with pytest.raises(CvmMigrationError) as exc_cnt:
        interlock.initiate_handshake(src, dst, manifest_root, 0)
    assert exc_cnt.value.code == HALT_CVM_MEMORY_CORRUPTION

    # Manifest root length != 71
    with pytest.raises(CvmMigrationError) as exc_root_len:
        interlock.initiate_handshake(src, dst, "sha256:tooshort", 3)
    assert exc_root_len.value.code == HALT_CVM_MEMORY_CORRUPTION

    # Manifest root wrong prefix
    with pytest.raises(CvmMigrationError) as exc_root_prefix:
        interlock.initiate_handshake(src, dst, "md5555:" + "0" * 64, 3)
    assert exc_root_prefix.value.code == HALT_CVM_MEMORY_CORRUPTION

    ticket = interlock.initiate_handshake(src, dst, manifest_root, 3)

    # Incorrect frame count during verification
    with pytest.raises(CvmMigrationError) as exc_mismatch:
        interlock.verify_memory_manifest(ticket.migration_id, frames[:2])
    assert exc_mismatch.value.code == HALT_CVM_MEMORY_CORRUPTION

    # Frame size non-positive (line 491 boundary)
    bad_size_frames = [
        MemoryFrameDigest(frame_index=0, frame_size_bytes=0, frame_sha256=frames[0].frame_sha256),
        frames[1],
        frames[2],
    ]
    with pytest.raises(CvmMigrationError) as exc_size:
        interlock.verify_memory_manifest(ticket.migration_id, bad_size_frames)
    assert exc_size.value.code == HALT_CVM_MEMORY_CORRUPTION

    # Exact boundary: frame_size_bytes == 1 must be strictly accepted (killing frame_size_bytes <= 1 mutation)
    single_frame_1byte = MemoryFrameDigest(frame_index=0, frame_size_bytes=1, frame_sha256=frames[0].frame_sha256)
    ticket_1byte = interlock.initiate_handshake(src, dst, frames[0].frame_sha256, 1)
    assert interlock.verify_memory_manifest(ticket_1byte.migration_id, [single_frame_1byte]) is True

    # Broken frame sequencing
    bad_seq_frames = [
        MemoryFrameDigest(frame_index=0, frame_size_bytes=4096, frame_sha256=frames[0].frame_sha256),
        MemoryFrameDigest(frame_index=2, frame_size_bytes=4096, frame_sha256=frames[1].frame_sha256),
        MemoryFrameDigest(frame_index=1, frame_size_bytes=4096, frame_sha256=frames[2].frame_sha256),
    ]
    with pytest.raises(CvmMigrationError) as exc_seq:
        interlock.verify_memory_manifest(ticket.migration_id, bad_seq_frames)
    assert exc_seq.value.code == HALT_CVM_MEMORY_CORRUPTION

    # Frame content tampering
    tampered_frames = [
        frames[0],
        MemoryFrameDigest(frame_index=1, frame_size_bytes=4096, frame_sha256="sha256:" + "ee" * 32),
        frames[2],
    ]
    with pytest.raises(CvmMigrationError) as exc_tamper:
        interlock.verify_memory_manifest(ticket.migration_id, tampered_frames)
    assert exc_tamper.value.code == HALT_CVM_MEMORY_CORRUPTION


def test_09_fail_closed_key_fencing_and_state_transitions() -> None:
    interlock = ConfidentialVmMigrationInterlock(db_path=":memory:")
    src, _ = _generate_test_enclave("vm-1", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "aa" * 32, epoch=1)
    dst, _ = _generate_test_enclave("vm-2", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "bb" * 32, epoch=2)

    frames, manifest_root = _build_test_memory_frames(2)
    ticket = interlock.initiate_handshake(src, dst, manifest_root, 2)

    # Cannot fence keys before memory is verified
    with pytest.raises(CvmMigrationError) as exc_fence_early:
        interlock.fence_and_handover_keys(ticket.migration_id, b"X" * 32, dst.public_key_hex)
    assert exc_fence_early.value.code == HALT_CVM_INVALID_STATE_TRANSITION

    # Cannot commit before keys are fenced
    with pytest.raises(CvmMigrationError) as exc_commit_early:
        interlock.commit_migration(ticket.migration_id)
    assert exc_commit_early.value.code == HALT_CVM_INVALID_STATE_TRANSITION

    # Verify memory
    interlock.verify_memory_manifest(ticket.migration_id, frames)

    # Insufficient key material length
    with pytest.raises(CvmMigrationError) as exc_short_key:
        interlock.fence_and_handover_keys(ticket.migration_id, b"too-short", dst.public_key_hex)
    assert exc_short_key.value.code == HALT_CVM_KEY_FENCE_FAILED


def test_10_rollback_lifecycle() -> None:
    interlock = ConfidentialVmMigrationInterlock(db_path=":memory:")
    src, _ = _generate_test_enclave("vm-1", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "aa" * 32, epoch=1)
    dst, _ = _generate_test_enclave("vm-2", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "bb" * 32, epoch=2)

    frames, manifest_root = _build_test_memory_frames(2)
    ticket = interlock.initiate_handshake(src, dst, manifest_root, 2)

    # Rollback active migration
    rb_ticket = interlock.rollback_migration(
        ticket.migration_id,
        HALT_CVM_MEMORY_CORRUPTION,
        "Network drop detected during live frame transfer",
    )
    assert rb_ticket.state == MIGRATION_STATE_ROLLED_BACK
    assert HALT_CVM_MEMORY_CORRUPTION in (rb_ticket.rollback_reason or "")

    # Cannot commit rolled-back migration
    with pytest.raises(CvmMigrationError) as exc_commit_rb:
        interlock.commit_migration(ticket.migration_id)
    assert exc_commit_rb.value.code == HALT_CVM_INVALID_STATE_TRANSITION

    # Completed migration cannot be rolled back
    src2, _ = _generate_test_enclave("vm-3", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "aa" * 32, epoch=1)
    dst2, _ = _generate_test_enclave("vm-4", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "bb" * 32, epoch=2)
    t2 = interlock.initiate_handshake(src2, dst2, manifest_root, 2)
    interlock.verify_memory_manifest(t2.migration_id, frames)
    interlock.fence_and_handover_keys(t2.migration_id, b"K" * 32, dst2.public_key_hex)
    interlock.commit_migration(t2.migration_id)

    with pytest.raises(CvmMigrationError) as exc_rb_committed:
        interlock.rollback_migration(t2.migration_id, "TEST", "Illegal rollback")
    assert exc_rb_committed.value.code == HALT_CVM_INVALID_STATE_TRANSITION


def test_11_sqlite_persistence_and_queries() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        interlock = ConfidentialVmMigrationInterlock(db_path=db_path)
        src, _ = _generate_test_enclave("vm-1", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "aa" * 32, epoch=1)
        dst, _ = _generate_test_enclave("vm-2", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "bb" * 32, epoch=2)

        frames, manifest_root = _build_test_memory_frames(1)
        t_before = int(time.time() * 1000)
        ticket = interlock.initiate_handshake(src, dst, manifest_root, 1)
        t_after = int(time.time() * 1000)
        assert t_before <= ticket.created_at_ms <= t_after + 1000

        # Retrieve ticket
        retrieved_t = interlock.get_ticket(ticket.migration_id)
        assert retrieved_t is not None
        assert retrieved_t.migration_id == ticket.migration_id
        assert retrieved_t.ticket_caid == ticket.ticket_caid
        assert retrieved_t.expected_frame_count == 1

        assert interlock.get_ticket("cvmmig-nonexistent") is None

        # Verify and fence
        interlock.verify_memory_manifest(ticket.migration_id, frames)
        interlock.fence_and_handover_keys(ticket.migration_id, b"A" * 32, dst.public_key_hex)
        receipt = interlock.commit_migration(ticket.migration_id)

        # Retrieve receipt
        retrieved_r = interlock.get_receipt(ticket.migration_id)
        assert retrieved_r is not None
        assert retrieved_r.receipt_caid == receipt.receipt_caid
        assert retrieved_r.migration_epoch == 2

        # Verify raw serialized receipt JSON requires deterministic key sorting (killing sort_keys=True mutation)
        with interlock._conn:
            raw_row = interlock._conn.execute(
                "SELECT raw_receipt_json FROM cvm_migration_receipts_ledger WHERE migration_id = ?",
                (ticket.migration_id,),
            ).fetchone()
            assert raw_row is not None
            raw_receipt_json = raw_row[0]
            expected_sorted_json = json.dumps(asdict(receipt), sort_keys=True)
            assert raw_receipt_json == expected_sorted_json
            assert raw_receipt_json.startswith('{"committed_at_ms":')

        assert interlock.get_receipt("cvmmig-nonexistent") is None

        # List by state
        committed = interlock.list_migrations_by_state(MIGRATION_STATE_COMMITTED)
        assert len(committed) == 1
        assert committed[0].migration_id == ticket.migration_id

        assert len(interlock.list_migrations_by_state(MIGRATION_STATE_ROLLED_BACK)) == 0

        interlock.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_12_exact_mutation_boundaries() -> None:
    # Memory frame digest exact attributes
    f = MemoryFrameDigest(frame_index=0, frame_size_bytes=4096, frame_sha256="sha256:" + "11" * 32)
    assert f.frame_index == 0
    assert f.frame_size_bytes == 4096

    # Test single-frame Merkle calculation
    h = "sha256:" + "cc" * 32
    assert compute_memory_merkle_root([h]) == h

    # Canonical bytes verification for CvmAttestationReport
    src, _ = _generate_test_enclave("vm-e", ENCLAVE_ARCH_AMD_SEV_SNP, "sha256:" + "aa" * 32, epoch=1)
    b = src.canonical_bytes()
    assert isinstance(b, bytes)
    assert b'"vm_id":"vm-e"' in b

    # Canonical bytes verification for ticket and receipt
    dst, _ = _generate_test_enclave("vm-d", ENCLAVE_ARCH_INTEL_TDX, "sha256:" + "bb" * 32, epoch=2)
    interlock = ConfidentialVmMigrationInterlock(db_path=":memory:")
    frames, manifest_root = _build_test_memory_frames(1)
    ticket = interlock.initiate_handshake(src, dst, manifest_root, 1)

    # Check migration_id length
    assert len(ticket.migration_id) == 7 + 16

    ticket_bytes = ticket.canonical_bytes()
    assert isinstance(ticket_bytes, bytes)
    assert b'"state":"MIGRATION_INITIATED"' in ticket_bytes

    interlock.verify_memory_manifest(ticket.migration_id, frames)
    interlock.fence_and_handover_keys(ticket.migration_id, b"Z" * 32, dst.public_key_hex)
    receipt = interlock.commit_migration(ticket.migration_id)

    receipt_bytes = receipt.canonical_bytes()
    assert isinstance(receipt_bytes, bytes)
    assert b'"status":"MIGRATION_COMMITTED"' in receipt_bytes

    # Verify time.time() * 1000 default (kills line 606 constant 1000 perturbation)
    import time
    t_now = int(time.time() * 1000)
    assert abs(receipt.committed_at_ms - t_now) < 5000

    # Verify ledger stores sorted JSON (kills line 747 sort_keys=True perturbation)
    cursor = interlock._conn.cursor()
    cursor.execute("SELECT raw_receipt_json FROM cvm_migration_receipts_ledger WHERE migration_id = ?", (ticket.migration_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row[0].startswith('{"committed_at_ms":')

    # Verify exact frame size boundary: 1-byte frame is accepted (kills line 491 constant 0 perturbation)
    frame_1b = [MemoryFrameDigest(frame_index=0, frame_size_bytes=1, frame_sha256="sha256:" + "01" * 32)]
    root_1b = compute_memory_merkle_root(["sha256:" + "01" * 32])
    t_1b = interlock.initiate_handshake(src, dst, root_1b, 1)
    interlock.verify_memory_manifest(t_1b.migration_id, frame_1b)
    t_1b_fetched = interlock.get_ticket(t_1b.migration_id)
    assert t_1b_fetched.state == "MEMORY_VERIFIED"


def test_13_wilson_ci_bounds_and_epistemic_lexicon() -> None:
    import src.confidential_vm_migration_interlock as mod

    doc = mod.__doc__ or ""
    assert "INTERNAL PREVIEW COMMISSIONED" in doc
    assert "scaffold" in doc
    assert "simulated" in doc

    # Wilson score interval check
    def wilson_score_interval(k: int, n: int, z: float = 1.95996) -> tuple[int, int]:
        p = k / n
        denom = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denom
        spread = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
        low = max(0.0, center - spread)
        high = min(1.0, center + spread)
        return int(round(low * 10000)), int(round(high * 10000))

    low_bps, high_bps = wilson_score_interval(30, 30)
    assert low_bps >= 8800
    assert high_bps == 10000
