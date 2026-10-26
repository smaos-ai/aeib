"""Tests and falsification vectors for src/behavioral_assurance_gate.py."""

from __future__ import annotations

import dataclasses

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.behavioral_assurance_gate import (
    ActionProposal,
    BehavioralAssuranceGate,
    BehavioralVerdict,
    BPS_SCALE,
    DerivativeNoOpGate,
    DerivativeNoOpVerdict,
    KVBlockCandidate,
    KVOffloadDecision,
    KVStorageGuard,
    NVME_PAGE_BYTES,
    OrganizationalPolicy,
    TrajectoryStep,
    jcs_sha256,
)
from src.jcs_canonicalizer import encode_jcs


def _policy(
    max_single: int = 1000,
    max_epoch: int = 2500,
    max_steps: int = 5,
) -> OrganizationalPolicy:
    return OrganizationalPolicy(
        policy_id="org-bank-v1",
        nlah_harness_digest="sha256:nlah_v1",
        allowed_capabilities=("read_balance", "wire_transfer", "internal_note"),
        high_stakes_capabilities=("wire_transfer",),
        max_single_action_minor=max_single,
        max_epoch_cumulative_minor=max_epoch,
        max_unattended_steps=max_steps,
    )


def _sign_proposal(sk: Ed25519PrivateKey, proposal: ActionProposal, policy_id: str = "org-bank-v1") -> ActionProposal:
    payload = BehavioralAssuranceGate.canonical_warrant_payload(proposal, policy_id)
    sig_hex = sk.sign(encode_jcs(payload)).hex()
    return dataclasses.replace(proposal, warrant_signature_hex=sig_hex)


def test_constants_and_frozen_dataclasses() -> None:
    assert BPS_SCALE == 10000 and NVME_PAGE_BYTES == 4096
    assert jcs_sha256({"b": 1, "a": 2}).startswith("sha256:")
    p = _policy()
    prop = ActionProposal("a1", "ag1", "t1", "read_balance", 0, 0, "sha256:nlah_v1")
    assert prop.warrant_signature_hex == ""
    step = TrajectoryStep(0, "t1", "sha256:s0")
    assert step.compensable is True
    blk = KVBlockCandidate("b1", "full_attention", "CONSTRAINT_C", 4096, 8000)
    bv = BehavioralVerdict(True, "ok", "sha256:x", 0)
    dv = DerivativeNoOpVerdict(True, "ok", True, 0, 0)
    kv = KVOffloadDecision(True, False, "ok", 0, 0, 0)
    for obj, attr in (
        (p, "policy_id"),
        (prop, "action_id"),
        (step, "tool_id"),
        (blk, "block_id"),
        (bv, "reason"),
        (dv, "reason"),
        (kv, "reason"),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, attr, "mut")


def test_behavioral_gate_validation_and_low_stakes_allow() -> None:
    sk = Ed25519PrivateKey.generate()
    pub = sk.public_key()
    for bad in (
        _policy(max_single=-1),
        _policy(max_epoch=-1),
        _policy(max_steps=0),
    ):
        with pytest.raises(ValueError, match="ERR_INVALID_ORG_POLICY_LIMITS"):
            BehavioralAssuranceGate(bad, pub)

    p_zero = _policy(max_single=0, max_epoch=0, max_steps=1)
    g_zero = BehavioralAssuranceGate(p_zero, pub)
    v_zero = g_zero.evaluate(ActionProposal("a0", "ag", "t", "read_balance", 0, 1, "sha256:nlah_v1"))
    assert v_zero.allowed is True and v_zero.cumulative_epoch_minor == 0

    with pytest.raises(ValueError, match="ERR_NEGATIVE_ACTION_PARAMETERS"):
        g_zero.evaluate(ActionProposal("a", "ag", "t", "read_balance", -1, 0, "sha256:nlah_v1"))
    with pytest.raises(ValueError, match="ERR_NEGATIVE_ACTION_PARAMETERS"):
        g_zero.evaluate(ActionProposal("a", "ag", "t", "read_balance", 0, -1, "sha256:nlah_v1"))


def test_falsify_rogue_bank_agent_and_behavioral_drift() -> None:
    """
    Falsification (CETaS Behavioural Assurance + NLAH arXiv:2603.25723 + arXiv:2609.38266v1):
    1) NLAH harness drift -> HALT_NLAH_HARNESS_DIGEST_DRIFT
    2) Capability outside organizational scope -> HALT_GOAL_DISPLACEMENT_OUT_OF_SCOPE
    3) Unattended step chain > max_unattended_steps -> HALT_ROGUE_AUTONOMY_STEP_LIMIT
    4) Single action > max_single_action_minor -> HALT_SINGLE_ACTION_LIMIT_EXCEEDED
    5) High-stakes wire_transfer without human warrant -> HALT_ROGUE_AGENT_UNATTESTED_HIGH_STAKES
    6) Tampered amount/recipient after warrant signing -> HALT_INVALID_HUMAN_WARRANT_SIGNATURE
    7) Valid warrant -> ALLOW_BEHAVIORAL_POLICY_SATISFIED
    8) Policy-invisible smurfing across epoch -> HALT_POLICY_INVISIBLE_CUMULATIVE_EXCEEDED
    """
    sk = Ed25519PrivateKey.generate()
    gate = BehavioralAssuranceGate(_policy(max_single=1000, max_epoch=1800, max_steps=3), sk.public_key())

    # 1. NLAH drift
    v_nlah = gate.evaluate(ActionProposal("a1", "ag1", "t1", "read_balance", 0, 1, "sha256:drifted"))
    assert not v_nlah.allowed and v_nlah.reason == "HALT_NLAH_HARNESS_DIGEST_DRIFT"

    # 2. Goal displacement
    v_goal = gate.evaluate(ActionProposal("a2", "ag1", "t1", "close_account", 0, 1, "sha256:nlah_v1"))
    assert not v_goal.allowed and v_goal.reason == "HALT_GOAL_DISPLACEMENT_OUT_OF_SCOPE"

    # 3. Rogue autonomy step limit (3 is allowed, 4 halts)
    assert gate.evaluate(ActionProposal("a3", "ag1", "t1", "read_balance", 0, 3, "sha256:nlah_v1")).allowed
    v_steps = gate.evaluate(ActionProposal("a4", "ag1", "t1", "read_balance", 0, 4, "sha256:nlah_v1"))
    assert not v_steps.allowed and v_steps.reason == "HALT_ROGUE_AUTONOMY_STEP_LIMIT"

    # 4. Single action limit (1000 is allowed with warrant, 1001 halts)
    v_single = gate.evaluate(ActionProposal("a5", "ag1", "t1", "read_balance", 1001, 1, "sha256:nlah_v1"))
    assert not v_single.allowed and v_single.reason == "HALT_SINGLE_ACTION_LIMIT_EXCEEDED"

    # 5. Unattested wire_transfer
    unsigned_tx = ActionProposal("tx1", "ag1", "wire_api", "wire_transfer", 1000, 1, "sha256:nlah_v1")
    v_unattested = gate.evaluate(unsigned_tx)
    assert not v_unattested.allowed and v_unattested.reason == "HALT_ROGUE_AGENT_UNATTESTED_HIGH_STAKES"
    assert gate.cumulative_epoch_minor == 0

    # 6. Post-approval substitution (signed for 900, mutated to 1000) & malformed hex
    signed_900 = _sign_proposal(
        sk, ActionProposal("tx1", "ag1", "wire_api", "wire_transfer", 900, 1, "sha256:nlah_v1")
    )
    tampered_1000 = dataclasses.replace(signed_900, amount_minor=1000)
    v_tampered = gate.evaluate(tampered_1000)
    assert not v_tampered.allowed and v_tampered.reason == "HALT_INVALID_HUMAN_WARRANT_SIGNATURE"
    bad_hex = dataclasses.replace(signed_900, warrant_signature_hex="not_hex")
    assert gate.evaluate(bad_hex).reason == "HALT_INVALID_HUMAN_WARRANT_SIGNATURE"

    # 7. Valid signed 900 transfer succeeds, followed by another valid signed 900 transfer (= 1800)
    v_ok1 = gate.evaluate(signed_900)
    assert v_ok1.allowed and v_ok1.reason == "ALLOW_BEHAVIORAL_POLICY_SATISFIED"
    assert v_ok1.cumulative_epoch_minor == 900
    signed_900_2 = _sign_proposal(
        sk, ActionProposal("tx2", "ag1", "wire_api", "wire_transfer", 900, 1, "sha256:nlah_v1")
    )
    v_ok2 = gate.evaluate(signed_900_2)
    assert v_ok2.allowed and v_ok2.cumulative_epoch_minor == 1800

    # 8. Policy-invisible cumulative overflow (1800 + 1 > 1800)
    signed_1 = _sign_proposal(
        sk, ActionProposal("tx3", "ag1", "wire_api", "wire_transfer", 1, 1, "sha256:nlah_v1")
    )
    v_cum = gate.evaluate(signed_1)
    assert not v_cum.allowed and v_cum.reason == "HALT_POLICY_INVISIBLE_CUMULATIVE_EXCEEDED"
    assert gate.cumulative_epoch_minor == 1800


def test_falsify_derivative_noop_staircase_and_covert_excursion() -> None:
    """
    Falsification (Staircase Paradox & ACID-Agent arXiv:2608.13900):
    1) Zero-variation trajectory (s0 -> s0) -> HALT_VERIFIED_ZERO_VARIATION_NOOP
    2) Mutated endpoint (s0 -> s1) -> REJECT_ENDPOINT_STATE_MUTATED
    3) Dirty-and-revert loop (s0 -> s1 -> s0, total_variation == 2 > 0) -> HALT_STAIRCASE_DERIVATIVE_DIVERGENCE
    4) Non-compensable intermediate step even with 0 state variation -> HALT_COVERT_NON_COMPENSABLE_EXCURSION
    """
    with pytest.raises(ValueError, match="ERR_NEGATIVE_VARIATION_BOUND"):
        DerivativeNoOpGate(max_allowed_noop_variation=-1)

    gate = DerivativeNoOpGate(max_allowed_noop_variation=0)
    assert gate.max_allowed_noop_variation == 0
    with pytest.raises(ValueError, match="ERR_EMPTY_INITIAL_DIGEST"):
        gate.evaluate_trajectory("", [])

    # 1. Clean read-only trajectory
    v_clean = gate.evaluate_trajectory(
        "sha256:s0",
        [TrajectoryStep(0, "read_ast", "sha256:s0", True)],
    )
    assert v_clean.is_valid_noop is True and v_clean.reason == "HALT_VERIFIED_ZERO_VARIATION_NOOP"
    assert v_clean.endpoint_converged is True and v_clean.total_variation == 0 and v_clean.non_compensable_steps == 0

    # 2. Endpoint mutated
    v_mut = gate.evaluate_trajectory(
        "sha256:s0",
        [TrajectoryStep(0, "edit_file", "sha256:s1", True)],
    )
    assert not v_mut.is_valid_noop and v_mut.reason == "REJECT_ENDPOINT_STATE_MUTATED"
    assert v_mut.endpoint_converged is False and v_mut.total_variation == 1

    # 3. Staircase dirty-and-revert (endpoint matches s0, but path derivative TV = 2 > 0)
    v_stair = gate.evaluate_trajectory(
        "sha256:s0",
        [
            TrajectoryStep(0, "edit_file", "sha256:s1", True),
            TrajectoryStep(1, "revert_file", "sha256:s0", True),
        ],
    )
    assert not v_stair.is_valid_noop and v_stair.reason == "HALT_STAIRCASE_DERIVATIVE_DIVERGENCE"
    assert v_stair.endpoint_converged is True and v_stair.total_variation == 2

    # Relaxed gate with max_allowed_noop_variation=2 accepts TV=2 when all steps are compensable
    gate_relaxed = DerivativeNoOpGate(max_allowed_noop_variation=2)
    assert gate_relaxed.evaluate_trajectory(
        "sha256:s0",
        [
            TrajectoryStep(0, "edit_file", "sha256:s1", True),
            TrajectoryStep(1, "revert_file", "sha256:s0", True),
        ],
    ).is_valid_noop is True

    # 4. Non-compensable intermediate step (ACID-Agent boundary) rejected even if state digest never changed
    v_covert = gate_relaxed.evaluate_trajectory(
        "sha256:s0",
        [TrajectoryStep(0, "send_wire", "sha256:s0", compensable=False)],
    )
    assert not v_covert.is_valid_noop and v_covert.reason == "HALT_COVERT_NON_COMPENSABLE_EXCURSION"
    assert v_covert.non_compensable_steps == 1


def test_falsify_gandalf_kv_storage_guard_and_dwpd_budget() -> None:
    """
    Falsification (Gandalf arXiv:2610.30791 + AKV):
    1) Low-value sliding_window + EPISODIC_E blocks are rejected from SSD offload.
    2) High-value full_attention or CONSTRAINT_C blocks below priority floor are rejected.
    3) Small admitted blocks buffer in RAM until reaching flush_threshold_bytes.
    4) Flushes align to 4096-byte NVMe page multiples and halt when exceeding daily_wear_budget_bytes.
    """
    for bad in (
        dict(daily_wear_budget_bytes=4095),
        dict(daily_wear_budget_bytes=8192, flush_threshold_bytes=4095),
        dict(daily_wear_budget_bytes=8192, min_priority_bps=-1),
        dict(daily_wear_budget_bytes=8192, min_priority_bps=10001),
    ):
        with pytest.raises(ValueError, match="ERR_INVALID_KV_GUARD_PARAMS"):
            KVStorageGuard(**bad)

    guard_zero_prio = KVStorageGuard(daily_wear_budget_bytes=8192, min_priority_bps=0)
    d_min_blk = guard_zero_prio.evaluate_offload(
        KVBlockCandidate("bmin", "full_attention", "CONSTRAINT_C", 1, 0)
    )
    assert d_min_blk.admitted and d_min_blk.coalesced_buffer_bytes == 1

    guard = KVStorageGuard(daily_wear_budget_bytes=8192, flush_threshold_bytes=4096, min_priority_bps=5000)
    assert guard.min_priority_bps == 5000 and guard.flush_threshold_bytes == 4096

    with pytest.raises(ValueError, match="ERR_INVALID_KV_BLOCK"):
        guard.evaluate_offload(KVBlockCandidate("b0", "full_attention", "CONSTRAINT_C", 0, 5000))
    with pytest.raises(ValueError, match="ERR_INVALID_KV_BLOCK"):
        guard.evaluate_offload(KVBlockCandidate("b0", "full_attention", "CONSTRAINT_C", 100, 10001))
    with pytest.raises(ValueError, match="ERR_INVALID_KV_BLOCK"):
        guard.evaluate_offload(KVBlockCandidate("b0", "full_attention", "CONSTRAINT_C", 100, -1))

    # 1. Low-value attention & episodic tier -> skipped
    d_skip1 = guard.evaluate_offload(KVBlockCandidate("b1", "sliding_window", "EPISODIC_E", 4096, 9000))
    assert not d_skip1.admitted and not d_skip1.flushed_to_ssd and d_skip1.reason == "SKIPPED_LOW_REUSE_KV_BLOCK"

    # 2. High-value type but priority < 5000 -> skipped
    d_skip2 = guard.evaluate_offload(KVBlockCandidate("b2", "full_attention", "EPISODIC_E", 4096, 4999))
    assert not d_skip2.admitted and d_skip2.reason == "SKIPPED_LOW_REUSE_KV_BLOCK"

    # 3. Buffer 2000 bytes (full_attention, priority == 5000) -> buffered in RAM
    d_buf = guard.evaluate_offload(KVBlockCandidate("b3", "full_attention", "EPISODIC_E", 2000, 5000))
    assert d_buf.admitted and not d_buf.flushed_to_ssd
    assert d_buf.coalesced_buffer_bytes == 2000 and d_buf.flushed_page_aligned_bytes == 0

    # 4. Add 2096 bytes (memory_tier CONSTRAINT_C even with sliding_window) -> hits 4096 threshold -> exact 4096 flush!
    d_flush1 = guard.evaluate_offload(KVBlockCandidate("b4", "sliding_window", "CONSTRAINT_C", 2096, 5000))
    assert d_flush1.admitted and d_flush1.flushed_to_ssd and d_flush1.reason == "FLUSHED_SEQUENTIAL_NVME_BATCH"
    assert d_flush1.coalesced_buffer_bytes == 0
    assert d_flush1.flushed_page_aligned_bytes == 4096 and d_flush1.daily_written_bytes == 4096

    # 5. Non-multiple of 4096 (4097 bytes) rounds up to 8192 bytes, which would push daily total to 4096+8192=12288 > 8192 -> HALT!
    d_wear = guard.evaluate_offload(KVBlockCandidate("b5", "full_attention", "CONSTRAINT_C", 4097, 8000))
    assert not d_wear.admitted and not d_wear.flushed_to_ssd
    assert d_wear.reason == "HALT_SSD_DWPD_WEAR_BUDGET_EXCEEDED"
    assert d_wear.daily_written_bytes == 4096

    # Exact 4096 bytes fits remaining budget (4096 + 4096 == 8192) -> flushes!
    d_flush2 = guard.evaluate_offload(KVBlockCandidate("b6", "full_attention", "CONSTRAINT_C", 4096, 8000))
    assert d_flush2.flushed_to_ssd and d_flush2.daily_written_bytes == 8192
