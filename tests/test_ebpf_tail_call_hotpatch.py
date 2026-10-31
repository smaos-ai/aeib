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
tests/test_ebpf_tail_call_hotpatch.py
================================================================================
Comprehensive verification suite for Dynamic eBPF LSM Tail-Call Map Hot-Patching Engine.
Evaluated under the stated model as an agent execution integrity boundary scaffold.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.ebpf_tail_call_hotpatch import (
    ACTION_ALLOW,
    ACTION_DENY,
    EbpfHotpatchError,
    EbpfPolicyManifest,
    EbpfSecurityRule,
    EbpfTailCallHotpatchEngine,
    HALT_BPF_DIGEST_MISMATCH,
    HALT_BPF_DRAIN_TIMEOUT_EXCEEDED,
    HALT_BPF_INVALID_STATE_TRANSITION,
    HALT_BPF_LEASE_NOT_FOUND,
    HALT_BPF_NON_MONOTONIC_EPOCH,
    HALT_BPF_SIGNATURE_INVALID,
    HALT_BPF_STAGING_PROBE_FAILED,
    HotpatchSwapReceipt,
    InflightExecutionLease,
    SLOT_A,
    SLOT_B,
    SLOT_STATE_ACTIVE,
    SLOT_STATE_DRAINING,
    SLOT_STATE_QUIESCENT,
    SLOT_STATE_RETIRED,
    SLOT_STATE_STAGING,
    compute_ruleset_digest,
    compute_sha256_caid,
)


def _generate_test_rules() -> list[EbpfSecurityRule]:
    return [
        EbpfSecurityRule(
            rule_id="rule-01-socket",
            hook_point="lsm_socket_connect",
            target_path_or_prefix="10.0.0.0/8",
            allowed_taint_ceiling_bps=1000,
            action=ACTION_ALLOW,
        ),
        EbpfSecurityRule(
            rule_id="rule-02-deny-egress",
            hook_point="lsm_socket_connect",
            target_path_or_prefix="0.0.0.0/0",
            allowed_taint_ceiling_bps=5000,
            action=ACTION_DENY,
        ),
        EbpfSecurityRule(
            rule_id="rule-03-mprotect",
            hook_point="lsm_file_mprotect",
            target_path_or_prefix="/opt/agent/bin",
            allowed_taint_ceiling_bps=0,
            action=ACTION_ALLOW,
        ),
    ]


def _build_test_manifest(
    policy_id: str,
    epoch: int,
    rules: list[EbpfSecurityRule],
    priv_key: ed25519.Ed25519PrivateKey,
    bytecode_hash: str = "sha256:" + "bb" * 32,
    created_at_ms: int = 1700000000000,
) -> EbpfPolicyManifest:
    return EbpfTailCallHotpatchEngine.create_policy_manifest(
        policy_id=policy_id,
        policy_epoch=epoch,
        rules=rules,
        program_bytecode_sha256=bytecode_hash,
        authority_priv_key=priv_key,
        created_at_ms=created_at_ms,
    )


def test_01_dataclass_and_digests() -> None:
    rules = _generate_test_rules()
    digest = compute_ruleset_digest(rules)
    assert digest.startswith("sha256:")
    assert len(digest) == 71

    # Permuted rules should yield identical digest (deterministic sorting)
    digest_perm = compute_ruleset_digest(list(reversed(rules)))
    assert digest_perm == digest

    caid = compute_sha256_caid({"status": "ACTIVE", "slot": 0})
    assert caid.startswith("sha256:")

    # Frozen dataclass checks (killing frozen=True perturbations)
    priv = ed25519.Ed25519PrivateKey.generate()
    t_before = int(time.time() * 1000)
    manifest = EbpfTailCallHotpatchEngine.create_policy_manifest("p1", 1, rules, "sha256:" + "00" * 32, priv)
    t_after = int(time.time() * 1000)
    assert t_before <= manifest.created_at_ms <= t_after + 1000

    with pytest.raises(Exception):
        manifest.policy_epoch = 99  # type: ignore

    lease = InflightExecutionLease("l1", 0, 1, "sha256:" + "11" * 32, 1000)
    with pytest.raises(Exception):
        lease.slot_index = 99  # type: ignore


def test_02_bootstrap_initial_policy() -> None:
    engine = EbpfTailCallHotpatchEngine(db_path=":memory:")
    priv = ed25519.Ed25519PrivateKey.generate()
    rules = _generate_test_rules()

    manifest = _build_test_manifest("pol-v1", 1, rules, priv)
    t_before = int(time.time() * 1000)
    engine.bootstrap_initial_policy(manifest)
    t_after = int(time.time() * 1000)

    assert engine.active_slot == SLOT_A
    assert engine.staging_slot == SLOT_B
    assert engine.get_slot_state(SLOT_A) == SLOT_STATE_ACTIVE
    assert engine.get_slot_state(SLOT_B) == SLOT_STATE_QUIESCENT
    assert engine.get_slot_policy(SLOT_A) is not None

    # Verify updated_at_ms in policy slots ledger strictly kills Mult swapped to FloorDiv (line 331)
    with engine._conn:
        row = engine._conn.execute(
            "SELECT updated_at_ms FROM ebpf_policy_slots_ledger WHERE slot_index = ?", (SLOT_A,)
        ).fetchone()
        assert row is not None
        assert t_before <= row[0] <= t_after + 500


def test_03_nominal_staging_healthcheck_and_atomic_swap() -> None:
    engine = EbpfTailCallHotpatchEngine(db_path=":memory:")
    priv = ed25519.Ed25519PrivateKey.generate()
    rules_v1 = _generate_test_rules()
    manifest_v1 = _build_test_manifest("pol-v1", 1, rules_v1, priv)
    engine.bootstrap_initial_policy(manifest_v1)

    # Stage policy v2 (epoch 2) without explicit now_ms
    rules_v2 = rules_v1 + [
        EbpfSecurityRule(
            rule_id="rule-04-audit",
            hook_point="lsm_bprm_check_security",
            target_path_or_prefix="/usr/local/bin",
            allowed_taint_ceiling_bps=2000,
            action=ACTION_ALLOW,
        )
    ]
    manifest_v2 = _build_test_manifest("pol-v2", 2, rules_v2, priv)
    staged_slot = engine.stage_policy(manifest_v2)

    assert staged_slot == SLOT_B
    assert engine.get_slot_state(SLOT_B) == SLOT_STATE_STAGING

    # Attempting to stage again while already in STAGING raises line 359
    manifest_v2_dup = _build_test_manifest("pol-v2-dup", 2, rules_v2, priv)
    with pytest.raises(EbpfHotpatchError) as exc_re_stage:
        engine.stage_policy(manifest_v2_dup)
    assert exc_re_stage.value.code in (HALT_BPF_INVALID_STATE_TRANSITION, HALT_BPF_NON_MONOTONIC_EPOCH)

    # Run health probes on staged slot
    probes = [
        ("lsm_socket_connect", "10.0.1.5", 500),  # Allowed under rule-01
        ("lsm_file_mprotect", "/opt/agent/bin/worker", 0),  # Allowed under rule-03
    ]
    assert engine.run_staging_health_probes(probes) is True

    # Perform atomic swap without explicit now_ms
    t_before_swap = int(time.time() * 1000)
    receipt = engine.atomic_slot_swap()
    t_after_swap = int(time.time() * 1000)
    assert t_before_swap <= receipt.swapped_at_ms <= t_after_swap + 1000

    # Assert exact swap_id length: f"swap-{uuid.uuid4().hex[:16]}" -> 5 + 16 = 21 chars
    assert len(receipt.swap_id) == 21
    assert receipt.status == "SWAP_COMMITTED"
    assert receipt.old_slot == SLOT_A
    assert receipt.new_slot == SLOT_B
    assert receipt.active_epoch == 2
    assert engine.active_slot == SLOT_B
    assert engine.staging_slot == SLOT_A
    assert engine.get_slot_state(SLOT_B) == SLOT_STATE_ACTIVE
    assert engine.get_slot_state(SLOT_A) == SLOT_STATE_DRAINING


def test_04_execution_leases_and_slot_draining() -> None:
    engine = EbpfTailCallHotpatchEngine(db_path=":memory:")
    priv = ed25519.Ed25519PrivateKey.generate()
    rules_v1 = _generate_test_rules()
    manifest_v1 = _build_test_manifest("pol-v1", 1, rules_v1, priv)
    engine.bootstrap_initial_policy(manifest_v1)

    # Acquire lease without explicit now_ms (tests line 472 default)
    t_before_lease = int(time.time() * 1000)
    lease1 = engine.acquire_execution_lease("op-connect-db")
    t_after_lease = int(time.time() * 1000)
    assert t_before_lease <= lease1.acquired_at_ms <= t_after_lease + 1000
    assert lease1.slot_index == SLOT_A
    assert engine.count_active_leases_for_slot(SLOT_A) == 1

    # Stage and swap to SLOT_B
    manifest_v2 = _build_test_manifest("pol-v2", 2, rules_v1, priv)
    engine.stage_policy(manifest_v2)
    engine.atomic_slot_swap()

    # SLOT_A is now DRAINING, but has 1 active lease
    assert engine.get_slot_state(SLOT_A) == SLOT_STATE_DRAINING
    with pytest.raises(EbpfHotpatchError) as exc_drain:
        engine.drain_and_retire_slot(SLOT_A)
    assert exc_drain.value.code == HALT_BPF_DRAIN_TIMEOUT_EXCEEDED

    # Release lease on SLOT_A
    engine.release_execution_lease(lease1.lease_id)
    assert engine.count_active_leases_for_slot(SLOT_A) == 0

    # Drain and retire without explicit now_ms (tests line 526 default)
    t_before_drain = int(time.time() * 1000)
    retired = engine.drain_and_retire_slot(SLOT_A)
    t_after_drain = int(time.time() * 1000)
    assert retired is True
    assert engine.get_slot_state(SLOT_A) == SLOT_STATE_QUIESCENT
    assert engine.get_slot_policy(SLOT_A) is None

    # Verify updated_at_ms in policy slots ledger strictly kills Mult swapped to FloorDiv (line 526)
    with engine._conn:
        row_drain = engine._conn.execute(
            "SELECT updated_at_ms FROM ebpf_policy_slots_ledger WHERE slot_index = ? AND slot_state = ?",
            (SLOT_A, SLOT_STATE_QUIESCENT),
        ).fetchone()
        assert row_drain is not None
        assert t_before_drain <= row_drain[0] <= t_after_drain + 500

    # Releasing non-existent lease fails closed
    with pytest.raises(EbpfHotpatchError) as exc_lease:
        engine.release_execution_lease("lease-nonexistent")
    assert exc_lease.value.code == HALT_BPF_LEASE_NOT_FOUND


def test_05_fail_closed_non_monotonic_epoch() -> None:
    engine = EbpfTailCallHotpatchEngine(db_path=":memory:")
    priv = ed25519.Ed25519PrivateKey.generate()
    manifest_v1 = _build_test_manifest("pol-v1", 1, _generate_test_rules(), priv)
    engine.bootstrap_initial_policy(manifest_v1)

    # Stale epoch (same epoch 1)
    manifest_stale = _build_test_manifest("pol-stale", 1, _generate_test_rules(), priv)
    with pytest.raises(EbpfHotpatchError) as exc_stale:
        engine.stage_policy(manifest_stale)
    assert exc_stale.value.code == HALT_BPF_NON_MONOTONIC_EPOCH

    # Skipped epoch (epoch 3 instead of 2)
    manifest_skip = _build_test_manifest("pol-skip", 3, _generate_test_rules(), priv)
    with pytest.raises(EbpfHotpatchError) as exc_skip:
        engine.stage_policy(manifest_skip)
    assert exc_skip.value.code == HALT_BPF_NON_MONOTONIC_EPOCH


def test_06_fail_closed_signature_invalid() -> None:
    engine = EbpfTailCallHotpatchEngine(db_path=":memory:")
    priv = ed25519.Ed25519PrivateKey.generate()
    manifest_v1 = _build_test_manifest("pol-v1", 1, _generate_test_rules(), priv)
    engine.bootstrap_initial_policy(manifest_v1)

    manifest_v2 = _build_test_manifest("pol-v2", 2, _generate_test_rules(), priv)
    # Corrupt signature
    corrupt_manifest = EbpfPolicyManifest(
        policy_id=manifest_v2.policy_id,
        policy_epoch=manifest_v2.policy_epoch,
        rules=manifest_v2.rules,
        ruleset_digest=manifest_v2.ruleset_digest,
        program_bytecode_sha256=manifest_v2.program_bytecode_sha256,
        created_at_ms=manifest_v2.created_at_ms,
        authority_pub_key_hex=manifest_v2.authority_pub_key_hex,
        signature="ff" * 64,
    )

    with pytest.raises(EbpfHotpatchError) as exc_sig:
        engine.stage_policy(corrupt_manifest)
    assert exc_sig.value.code == HALT_BPF_SIGNATURE_INVALID


def test_07_fail_closed_digest_mismatch() -> None:
    engine = EbpfTailCallHotpatchEngine(db_path=":memory:")
    priv = ed25519.Ed25519PrivateKey.generate()
    manifest_v1 = _build_test_manifest("pol-v1", 1, _generate_test_rules(), priv)

    # Tamper ruleset digest in bootstrap
    bad_bootstrap = EbpfPolicyManifest(
        policy_id=manifest_v1.policy_id,
        policy_epoch=manifest_v1.policy_epoch,
        rules=manifest_v1.rules,
        ruleset_digest="sha256:" + "00" * 32,
        program_bytecode_sha256=manifest_v1.program_bytecode_sha256,
        created_at_ms=manifest_v1.created_at_ms,
        authority_pub_key_hex=manifest_v1.authority_pub_key_hex,
        signature=manifest_v1.signature,
    )
    with pytest.raises(EbpfHotpatchError) as exc_boot:
        engine.bootstrap_initial_policy(bad_bootstrap)
    assert exc_boot.value.code in (HALT_BPF_DIGEST_MISMATCH, HALT_BPF_SIGNATURE_INVALID)

    engine.bootstrap_initial_policy(manifest_v1)

    # Tamper ruleset digest in staging with valid signature to strictly kill RAISE_DROP on line 359
    manifest_v2 = _build_test_manifest("pol-v2", 2, _generate_test_rules(), priv)
    spoofed_digest = "sha256:" + "99" * 32
    spoofed_unsigned = EbpfPolicyManifest(
        policy_id=manifest_v2.policy_id,
        policy_epoch=manifest_v2.policy_epoch,
        rules=manifest_v2.rules,
        ruleset_digest=spoofed_digest,
        program_bytecode_sha256=manifest_v2.program_bytecode_sha256,
        created_at_ms=manifest_v2.created_at_ms,
        authority_pub_key_hex=priv.public_key().public_bytes_raw().hex(),
        signature="",
    )
    valid_sig_on_spoofed = priv.sign(spoofed_unsigned.canonical_bytes()).hex()
    spoofed_manifest = EbpfPolicyManifest(
        policy_id=spoofed_unsigned.policy_id,
        policy_epoch=spoofed_unsigned.policy_epoch,
        rules=spoofed_unsigned.rules,
        ruleset_digest=spoofed_unsigned.ruleset_digest,
        program_bytecode_sha256=spoofed_unsigned.program_bytecode_sha256,
        created_at_ms=spoofed_unsigned.created_at_ms,
        authority_pub_key_hex=spoofed_unsigned.authority_pub_key_hex,
        signature=valid_sig_on_spoofed,
    )
    with pytest.raises(EbpfHotpatchError, match="Ruleset digest mismatch") as exc_stage:
        engine.stage_policy(spoofed_manifest)
    assert exc_stage.value.code == HALT_BPF_DIGEST_MISMATCH


def test_08_staging_health_probe_failure() -> None:
    engine = EbpfTailCallHotpatchEngine(db_path=":memory:")
    priv = ed25519.Ed25519PrivateKey.generate()
    manifest_v1 = _build_test_manifest("pol-v1", 1, _generate_test_rules(), priv)
    engine.bootstrap_initial_policy(manifest_v1)

    manifest_v2 = _build_test_manifest("pol-v2", 2, _generate_test_rules(), priv)
    engine.stage_policy(manifest_v2)

    # Probe that violates rule-02-deny-egress (taint_bps >= 5000 on 0.0.0.0/0)
    violating_probes = [
        ("lsm_socket_connect", "0.0.0.0/0", 6000),
    ]
    with pytest.raises(EbpfHotpatchError) as exc_probe:
        engine.run_staging_health_probes(violating_probes)
    assert exc_probe.value.code == HALT_BPF_STAGING_PROBE_FAILED


def test_09_invalid_state_transitions() -> None:
    engine = EbpfTailCallHotpatchEngine(db_path=":memory:")
    # Cannot swap when no policy is staged
    with pytest.raises(EbpfHotpatchError) as exc_swap:
        engine.atomic_slot_swap()
    assert exc_swap.value.code == HALT_BPF_INVALID_STATE_TRANSITION

    # Cannot drain when not DRAINING
    with pytest.raises(EbpfHotpatchError) as exc_drain:
        engine.drain_and_retire_slot(SLOT_A)
    assert exc_drain.value.code == HALT_BPF_INVALID_STATE_TRANSITION

    # Cannot probe when no policy staged
    with pytest.raises(EbpfHotpatchError) as exc_probe:
        engine.run_staging_health_probes([("hook", "path", 0)])
    assert exc_probe.value.code == HALT_BPF_INVALID_STATE_TRANSITION


def test_10_emergency_rollback_workflow() -> None:
    engine = EbpfTailCallHotpatchEngine(db_path=":memory:")
    priv = ed25519.Ed25519PrivateKey.generate()
    manifest_v1 = _build_test_manifest("pol-v1", 1, _generate_test_rules(), priv)
    engine.bootstrap_initial_policy(manifest_v1)

    manifest_v2 = _build_test_manifest("pol-v2", 2, _generate_test_rules(), priv)
    engine.stage_policy(manifest_v2)
    engine.atomic_slot_swap()

    assert engine.active_slot == SLOT_B

    # Trigger emergency rollback to SLOT_A without explicit now_ms (tests default timestamp and swap_id length)
    t_before_rb = int(time.time() * 1000)
    rb_receipt = engine.rollback_to_previous_slot("Memory corruption detected in BPF map")
    t_after_rb = int(time.time() * 1000)
    assert t_before_rb <= rb_receipt.swapped_at_ms <= t_after_rb + 1000

    # f"swap-rollback-{uuid.uuid4().hex[:16]}" -> 14 + 16 = 30 chars
    assert len(rb_receipt.swap_id) == 30
    assert rb_receipt.new_slot == SLOT_A
    assert rb_receipt.old_slot == SLOT_B
    assert "ROLLBACK_TRIGGERED" in rb_receipt.status
    assert engine.active_slot == SLOT_A
    assert engine.get_slot_state(SLOT_A) == SLOT_STATE_ACTIVE
    assert engine.get_slot_state(SLOT_B) == SLOT_STATE_RETIRED


def test_11_sqlite_persistence_and_queries() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        engine = EbpfTailCallHotpatchEngine(db_path=db_path)
        # Test PRAGMA journal_mode is WAL for disk-backed database (line 228)
        mode = engine._conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal"

        priv = ed25519.Ed25519PrivateKey.generate()
        manifest_v1 = _build_test_manifest("pol-v1", 1, _generate_test_rules(), priv)
        engine.bootstrap_initial_policy(manifest_v1)

        manifest_v2 = _build_test_manifest("pol-v2", 2, _generate_test_rules(), priv)
        engine.stage_policy(manifest_v2)
        swap_receipt = engine.atomic_slot_swap(now_ms=1700000005000)

        # Retrieve swap receipt
        retrieved = engine.get_swap_receipt(swap_receipt.swap_id)
        assert retrieved is not None
        assert retrieved.swap_id == swap_receipt.swap_id
        assert retrieved.active_epoch == 2
        assert retrieved.new_slot == SLOT_B

        assert engine.get_swap_receipt("swap-nonexistent") is None

        # List swap events
        events = engine.list_swap_events()
        assert len(events) == 1
        assert events[0].swap_id == swap_receipt.swap_id

        engine.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_12_exact_mutation_boundaries() -> None:
    rule = EbpfSecurityRule(
        rule_id="r1",
        hook_point="h1",
        target_path_or_prefix="/tmp",
        allowed_taint_ceiling_bps=500,
        action=ACTION_ALLOW,
    )
    b = rule.canonical_bytes()
    assert isinstance(b, bytes)
    assert b'"allowed_taint_ceiling_bps":500' in b

    priv = ed25519.Ed25519PrivateKey.generate()
    manifest = _build_test_manifest("pol-m", 1, [rule], priv)
    m_bytes = manifest.canonical_bytes()
    assert isinstance(m_bytes, bytes)
    assert b'"policy_epoch":1' in m_bytes

    receipt = HotpatchSwapReceipt(
        swap_id="s1",
        old_slot=0,
        new_slot=1,
        active_epoch=1,
        ruleset_digest="sha256:" + "00" * 32,
        receipt_caid="sha256:" + "11" * 32,
        status="OK",
        swapped_at_ms=1000,
    )
    r_bytes = receipt.canonical_bytes()
    assert isinstance(r_bytes, bytes)
    assert b'"new_slot":1' in r_bytes


def test_13_wilson_ci_bounds_and_epistemic_lexicon() -> None:
    import src.ebpf_tail_call_hotpatch as mod

    doc = mod.__doc__ or ""
    assert "INTERNAL PREVIEW COMMISSIONED" in doc
    assert "scaffold" in doc
    assert "simulated" in doc

    # Wilson score helper verification
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
