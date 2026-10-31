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
tests/test_lexus_nvh_and_thermal_governor.py
================================================================================
Comprehensive verification suite for Lexus-Grade NVH Damping, Context Thermal BMS,
Scissor-Gear Anti-Backlash Transmission, and Takumi Master Inspection HUD.
"""

from __future__ import annotations

import pytest

from src.lexus_nvh_and_thermal_governor import (
    AntiBacklashWireTransmission,
    ContextThermalBMS,
    NVHDampingDisposition,
    SemanticNVHDamper,
    TakumiInspectionHUD,
    WireReservationReceipt,
)


# -----------------------------------------------------------------------------
# 1. Semantic NVH Damper Tests
# -----------------------------------------------------------------------------


def test_nvh_damper_single_candidate():
    """A single speculative candidate exhibits 0 bps jitter and passes."""
    damper = SemanticNVHDamper(max_jitter_bps=500)
    res = damper.inspect_speculative_candidates(["def execute(): return 42"])
    assert res.passed is True
    assert res.jitter_variance_bps == 0
    assert res.disposition == NVHDampingDisposition.NVH_DAMPED_ACCEPTABLE
    assert res.sample_count == 1
    assert len(res.consensus_digest) == 64


def test_nvh_damper_low_variance_passes():
    """Candidates with minor token jitter within 500 bps pass."""
    import hashlib
    damper = SemanticNVHDamper(max_jitter_bps=500)
    candidates = [
        "def compute_interest(amount_minor: int) -> int:\n    return amount_minor * 5\n",
        "def compute_interest(amount_minor: int) -> int:\n    return amount_minor * 5 \n",
    ]
    res = damper.inspect_speculative_candidates(candidates)
    assert res.passed is True
    assert res.jitter_variance_bps <= 500
    assert res.disposition == NVHDampingDisposition.NVH_DAMPED_ACCEPTABLE
    assert res.sample_count == 2
    assert res.consensus_digest == hashlib.sha256(candidates[0].encode("utf-8")).hexdigest()


def test_nvh_damper_high_variance_trips():
    """Candidates with severe semantic drift trip NVH_JITTER_EXCESSIVE."""
    damper = SemanticNVHDamper(max_jitter_bps=500)
    candidates = [
        "def dispatch():\n    db.commit()\n    return True\n",
        "def dispatch():\n    raise NotImplementedError('TODO')\n",
        "def dispatch():\n    subprocess.run(['rm', '-rf', '/'])\n",
    ]
    res = damper.inspect_speculative_candidates(candidates)
    assert res.passed is False
    assert res.jitter_variance_bps > 500
    assert res.disposition == NVHDampingDisposition.NVH_JITTER_EXCESSIVE


def test_nvh_damper_input_validations():
    """Rejects empty candidate lists and out-of-range thresholds."""
    with pytest.raises(ValueError, match="ERR_INVALID_MAX_JITTER_BPS"):
        SemanticNVHDamper(max_jitter_bps=-1)
    with pytest.raises(ValueError, match="ERR_INVALID_MAX_JITTER_BPS"):
        SemanticNVHDamper(max_jitter_bps=10001)

    damper = SemanticNVHDamper()
    with pytest.raises(ValueError, match="ERR_EMPTY_CANDIDATES"):
        damper.inspect_speculative_candidates([])


# -----------------------------------------------------------------------------
# 2. Context Thermal BMS Tests
# -----------------------------------------------------------------------------


def test_thermal_bms_nominal_retention():
    """Context window retaining 100% of pinned rules maintains healthy status."""
    rules = [
        "RULE_ZERO_FLOAT_IN_JCS",
        "RULE_DISK_ANCHORED_TEST_HASH",
        "RULE_OUT_OF_BAND_FACEID",
    ]
    bms = ContextThermalBMS(pinned_safety_rules=rules, retention_floor_bps=9000)
    context = (
        "Instructions: Obey RULE_ZERO_FLOAT_IN_JCS and RULE_DISK_ANCHORED_TEST_HASH. "
        "Also enforce RULE_OUT_OF_BAND_FACEID before wire mutation."
    )
    status = bms.evaluate_context_turn(context)
    assert status.quenched is False
    assert status.current_retention_bps == 10000
    assert status.recalled_rule_count == 3
    assert status.turn_index == 1
    assert bms.is_quenched is False


def test_thermal_bms_quenches_on_capacity_collapse():
    """When rule recall drops below 9000 bps (90%), the BMS initiates an emergency thermal quench."""
    rules = [f"RULE_{i:02d}" for i in range(10)]
    bms = ContextThermalBMS(pinned_safety_rules=rules, retention_floor_bps=9000)

    # Turn 1: 9/10 rules recalled (9000 bps) - passes
    context_turn_1 = " ".join(rules[:9])
    st1 = bms.evaluate_context_turn(context_turn_1)
    assert st1.quenched is False
    assert st1.current_retention_bps >= bms.retention_floor_bps
    assert st1.recalled_rule_count == 9

    # Turn 2: Compaction dropped 3 rules -> 7/10 recalled (7000 bps) -> Quench!
    context_turn_2 = " ".join(rules[:7])
    st2 = bms.evaluate_context_turn(context_turn_2)
    assert st2.quenched is True
    assert st2.current_retention_bps == 7000
    assert st2.quench_reason == "SAFETY_RULE_RETENTION_COLLAPSED_BELOW_FLOOR"
    assert bms.is_quenched is True

    # Turn 3: Subsequent evaluation remains quenched fail-closed
    st3 = bms.evaluate_context_turn(" ".join(rules))
    assert st3.quenched is True
    assert st3.quench_reason == "THERMAL_BMS_ALREADY_QUENCHED"
    assert st3.current_retention_bps == 0
    assert st3.recalled_rule_count == 0


def test_thermal_bms_input_validations():
    """Rejects empty rule lists and out-of-range thresholds."""
    with pytest.raises(ValueError, match="ERR_PINNED_RULES_EMPTY"):
        ContextThermalBMS(pinned_safety_rules=[])
    with pytest.raises(ValueError, match="ERR_INVALID_RETENTION_FLOOR_BPS"):
        ContextThermalBMS(pinned_safety_rules=["RULE_1"], retention_floor_bps=0)
    with pytest.raises(ValueError, match="ERR_INVALID_RETENTION_FLOOR_BPS"):
        ContextThermalBMS(pinned_safety_rules=["RULE_1"], retention_floor_bps=10001)


# -----------------------------------------------------------------------------
# 3. Anti-Backlash Wire Transmission Tests
# -----------------------------------------------------------------------------


def test_anti_backlash_nominal_execution():
    """Nominal pre-socket reservation followed by wire commit succeeds."""
    tx = AntiBacklashWireTransmission()
    res = tx.reserve_pre_socket(
        operation_id="op-tx-001",
        target_resource="ledger://wire/mutation",
        attempt_fence=1,
    )
    assert isinstance(res, WireReservationReceipt)
    assert res.operation_id == "op-tx-001"
    assert res.attempt_fence == 1
    assert res.consumed is False
    assert res.reservation_caid.startswith("sha256:")

    committed = tx.commit_wire_execution(operation_id="op-tx-001", attempt_fence=1)
    assert committed.consumed is True


def test_anti_backlash_replayed_or_stale_fence_rejected():
    """Replaying an attempt with equal or decreasing fence trips backlash error."""
    tx = AntiBacklashWireTransmission()
    tx.reserve_pre_socket("op-tx-002", "wire://bank/transfer", attempt_fence=2)

    # Replay with same attempt fence
    with pytest.raises(ValueError, match="ERR_WIRE_BACKLASH_STALE_ATTEMPT_FENCE"):
        tx.reserve_pre_socket("op-tx-002", "wire://bank/transfer", attempt_fence=2)

    # Replay with decreasing attempt fence
    with pytest.raises(ValueError, match="ERR_WIRE_BACKLASH_STALE_ATTEMPT_FENCE"):
        tx.reserve_pre_socket("op-tx-002", "wire://bank/transfer", attempt_fence=1)

    # Increasing fence succeeds (legitimate retry)
    res_retry = tx.reserve_pre_socket("op-tx-002", "wire://bank/transfer", attempt_fence=3)
    assert res_retry.attempt_fence == 3
    assert res_retry.consumed is False


def test_anti_backlash_mutation_after_commit_rejected():
    """Attempting to reserve or commit again after consumption trips fail-closed."""
    tx = AntiBacklashWireTransmission()
    tx.reserve_pre_socket("op-tx-003", "wire://bank/transfer", attempt_fence=1)
    tx.commit_wire_execution("op-tx-003", attempt_fence=1)

    # Trying to reserve again after commit
    with pytest.raises(ValueError, match="ERR_WIRE_BACKLASH_OPERATION_ALREADY_COMMITTED"):
        tx.reserve_pre_socket("op-tx-003", "wire://bank/transfer", attempt_fence=2)

    # Trying to commit again
    with pytest.raises(ValueError, match="ERR_OPERATION_ALREADY_CONSUMED"):
        tx.commit_wire_execution("op-tx-003", attempt_fence=1)


def test_anti_backlash_commit_without_reservation_or_wrong_fence():
    """Committing unreserved operation or mismatched fence trips."""
    tx = AntiBacklashWireTransmission()
    with pytest.raises(ValueError, match="ERR_NO_PRE_SOCKET_RESERVATION_FOUND"):
        tx.commit_wire_execution("op-unknown", attempt_fence=1)

    tx.reserve_pre_socket("op-fence-mismatch", "wire://res", attempt_fence=5)
    with pytest.raises(ValueError, match="ERR_ATTEMPT_FENCE_MISMATCH"):
        tx.commit_wire_execution("op-fence-mismatch", attempt_fence=4)


def test_anti_backlash_input_validations():
    """Rejects empty IDs, blank resources, and invalid attempt fences."""
    tx = AntiBacklashWireTransmission()
    with pytest.raises(ValueError, match="ERR_INVALID_OPERATION_ID"):
        tx.reserve_pre_socket("", "res", 1)
    with pytest.raises(ValueError, match="ERR_INVALID_TARGET_RESOURCE"):
        tx.reserve_pre_socket("op-1", "", 1)
    with pytest.raises(ValueError, match="ERR_INVALID_ATTEMPT_FENCE"):
        tx.reserve_pre_socket("op-1", "res", 0)


# -----------------------------------------------------------------------------
# 4. Takumi Inspection HUD Tests
# -----------------------------------------------------------------------------


def test_nvh_damper_exact_variance_calculation():
    """Asserts exact jitter basis points across 3 controlled candidates."""
    damper = SemanticNVHDamper(max_jitter_bps=10000)
    # c1 and c2 identical (div=0.0); c3 completely different (div=1.0 vs c1 and c2)
    # Pairs = 3, total div = 2.0, avg = 2/3 = 0.66666... -> 6667 bps
    candidates = ["aaaa", "aaaa", "bbbb"]
    res = damper.inspect_speculative_candidates(candidates)
    assert res.jitter_variance_bps == 6667
    assert res.sample_count == 3
    assert res.disposition == NVHDampingDisposition.NVH_DAMPED_ACCEPTABLE


def test_thermal_bms_zero_rules_recalled():
    """Context window recalling 0 rules records exactly 0 bps retention."""
    rules = ["MANDATORY_INVARIANT_A", "MANDATORY_INVARIANT_B"]
    bms = ContextThermalBMS(pinned_safety_rules=rules, retention_floor_bps=5000)
    status = bms.evaluate_context_turn("empty unrelated context window")
    assert status.quenched is True
    assert status.recalled_rule_count == 0
    assert status.current_retention_bps == 0


def test_thermal_bms_boundary_floor_validation():
    """Tests boundary retention floor values 1 and 0."""
    with pytest.raises(ValueError, match="ERR_INVALID_RETENTION_FLOOR_BPS"):
        ContextThermalBMS(pinned_safety_rules=["R1"], retention_floor_bps=0)
    bms = ContextThermalBMS(pinned_safety_rules=["R1"], retention_floor_bps=1)
    assert bms.retention_floor_bps == 1


def test_takumi_hud_rendering():
    """Renders exact AST diff counts, blast radius, and canonical bytes."""
    diff_sample = (
        "--- a/src/core.py\n"
        "+++ b/src/core.py\n"
        "@@ -10,3 +10,3 @@\n"
        "-old_broken_line_1()\n"
        "-old_broken_line_2()\n"
        "+fixed_line_1()\n"
        "+fixed_line_2()\n"
    )
    hud = TakumiInspectionHUD.render_hud(
        task_id="task-takumi-001",
        modified_files=["src/core.py"],
        unified_diff_text=diff_sample,
        blast_radius_symbol_count=4,
        purity_confirmed=True,
    )
    assert hud.task_id == "task-takumi-001"
    assert hud.modified_files == ("src/core.py",)
    assert hud.added_lines_count == 2
    assert hud.deleted_lines_count == 2
    assert hud.blast_radius_symbol_count == 4
    assert hud.purity_confirmed is True
    assert len(hud.hud_digest_sha256) == 64

    # Verify canonical bytes has zero floats
    can_bytes = hud.canonical_bytes()
    assert b"float" not in can_bytes
    data = hud.to_canonical_dict()
    for v in data.values():
        assert not isinstance(v, float)



def test_takumi_hud_input_validations():
    """Rejects empty task IDs and empty modified files."""
    with pytest.raises(ValueError, match="ERR_INVALID_TASK_ID"):
        TakumiInspectionHUD.render_hud("", ["a.py"], "diff", 1, True)
    with pytest.raises(ValueError, match="ERR_EMPTY_MODIFIED_FILES"):
        TakumiInspectionHUD.render_hud("task-1", [], "diff", 1, True)
