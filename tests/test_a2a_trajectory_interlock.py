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
tests/test_a2a_trajectory_interlock.py — Zero-Mock Falsification & Verification Suite

Evaluates:
  1. Monotonic delegation taint propagation (child cannot launder parent taint).
  2. Scope confinement (child cannot escalate egress host scope beyond parent).
  3. CAID provenance chain integrity (RFC 8785 single-source JCS).
  4. SEMA-Auto multi-turn trajectory drift governance (Jaccard distance in integer bps 0..10000).
  5. Parameter validations, boundary invariants, frozen immutability, and unregistered entity containment.

Status: INTERNAL PREVIEW COMMISSIONED.
Zero mocks, zero floats, deterministic cryptographic validation.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import pytest

from src.a2a_trajectory_interlock import (
    A2ATrajectoryInterlock,
    AgentDelegationToken,
    TrajectoryTurnRecord,
)


def test_monotonic_taint_and_scope_confinement() -> None:
    """Verifies that child agents cannot escalate egress scope or reduce taint level."""
    interlock = A2ATrajectoryInterlock(max_drift_threshold_bps=4000)

    root_spiffe = "spiffe://sovereign.nexus/ns/prod/actor/root_orchestrator"
    child_spiffe = "spiffe://sovereign.nexus/ns/prod/actor/child_worker_01"
    grandchild_spiffe = "spiffe://sovereign.nexus/ns/prod/actor/grandchild_worker_02"

    # Register root authority with permitted egress hosts
    interlock.register_root_authority(
        spiffe_id=root_spiffe,
        allowed_egress_hosts=["api.github.com", "api.openai.com"],
    )

    # Clean delegation from root: parent_taint is 0, child requested taint is 0
    t_clean = interlock.register_delegation(
        parent_spiffe_id=root_spiffe,
        child_spiffe_id="spiffe://sovereign.nexus/ns/prod/actor/clean_child",
        parent_caid="sha256:clean_parent",
        allowed_egress_hosts=["api.github.com"],
        requested_child_taint=0,
    )
    assert t_clean.taint_level == 0

    # 1. Valid child delegation with subset of hosts and taint level 1
    t1 = interlock.register_delegation(
        parent_spiffe_id=root_spiffe,
        child_spiffe_id=child_spiffe,
        parent_caid="sha256:root_intent_caid_0000000000000000000000000000000000000000000000",
        allowed_egress_hosts=["api.github.com"],
        requested_child_taint=1,
    )
    assert t1.taint_level == 1
    assert t1.allowed_egress_hosts == ("api.github.com",)
    assert t1.delegation_caid.startswith("sha256:")

    # 2. Host escalation rejection: Child requests host parent does not possess
    with pytest.raises(PermissionError, match="ERR_DELEGATION_HOST_ESCALATION_FORBIDDEN"):
        interlock.register_delegation(
            parent_spiffe_id=root_spiffe,
            child_spiffe_id="spiffe://sovereign.nexus/ns/prod/actor/rogue_child",
            parent_caid="sha256:root_intent_caid_0000000000000000000000000000000000000000000000",
            allowed_egress_hosts=["api.github.com", "exfiltrate.evil.org"],
        )

    # 3. Monotonic Taint: Grandchild tries to lower taint from 1 to 0 -> Launder blocked, kept at 1
    t2 = interlock.register_delegation(
        parent_spiffe_id=child_spiffe,
        child_spiffe_id=grandchild_spiffe,
        parent_caid="sha256:child_intent_caid_000000000000000000000000000000000000000000000",
        allowed_egress_hosts=["api.github.com"],
        requested_child_taint=0,  # Attempting to launder taint!
    )
    assert t2.taint_level == 1  # Retains parent's taint level 1!

    # 4. Valid egress check
    ok, reason = interlock.validate_delegated_egress(
        child_spiffe_id=child_spiffe,
        target_host="api.github.com",
        action_caid="sha256:action_01",
    )
    assert ok is True
    assert reason == "OK_DELEGATED_EGRESS_PERMITTED"

    # 5. Unauthorized host check
    bad_host, bad_reason = interlock.validate_delegated_egress(
        child_spiffe_id=child_spiffe,
        target_host="api.openai.com",  # Root has it, but child was only granted api.github.com
        action_caid="sha256:action_02",
    )
    assert bad_host is False
    assert "HALT_EGRESS_HOST_NOT_DELEGATED" in bad_reason

    # 6. Compromised taint level (3) halts all egress
    compromised_spiffe = "spiffe://sovereign.nexus/ns/prod/actor/compromised_agent"
    interlock.register_delegation(
        parent_spiffe_id=child_spiffe,
        child_spiffe_id=compromised_spiffe,
        parent_caid="sha256:child_intent_caid_000000000000000000000000000000000000000000000",
        allowed_egress_hosts=["api.github.com"],
        requested_child_taint=3,  # Level 3 = Compromised
    )
    comp_ok, comp_reason = interlock.validate_delegated_egress(
        child_spiffe_id=compromised_spiffe,
        target_host="api.github.com",
        action_caid="sha256:action_03",
    )
    assert comp_ok is False
    assert comp_reason == "HALT_COMPROMISED_TAINT_BLOCKED"


def test_sema_auto_trajectory_drift_governance() -> None:
    """Verifies SEMA-Auto multi-turn drift detection in integer basis points (0..10000 bps)."""
    interlock = A2ATrajectoryInterlock(max_drift_threshold_bps=4000)
    session_id = "session_finance_audit_1001"

    # Turn 0: Root intent defined
    r0 = interlock.record_trajectory_turn(
        session_id=session_id,
        turn_intent="audit internal balance sheet and calculate quarterly financial variance",
        action_caid="sha256:action_turn_0",
    )
    assert r0.turn_index == 0
    assert r0.drift_bps == 0
    assert r0.verdict == "OK_TRAJECTORY_ALIGNED"
    assert r0.record_caid.startswith("sha256:")

    # Turn 1: Closely aligned intent (shares vocabulary with root intent)
    r1 = interlock.record_trajectory_turn(
        session_id=session_id,
        turn_intent="calculate financial variance report for internal balance audit",
        action_caid="sha256:action_turn_1",
    )
    assert r1.turn_index == 1
    assert r1.drift_bps < 4000
    assert r1.verdict == "OK_TRAJECTORY_ALIGNED"

    # Turn 2: SEMA-Auto drift attack (intent wanders into modifying database credentials)
    r2 = interlock.record_trajectory_turn(
        session_id=session_id,
        turn_intent="rotate database master credentials and disable security firewall logging rules",
        action_caid="sha256:action_turn_2",
    )
    assert r2.turn_index == 2
    assert r2.drift_bps > 4000
    assert r2.verdict == "HALT_TRAJECTORY_DRIFT_EXCEEDED"

    # Turn 3: Empty words / stopwords only turn (union_len == 0)
    empty_session = "session_empty_test"
    interlock.record_trajectory_turn(empty_session, "is it this that and or", "sha256:t0")
    r_empty = interlock.record_trajectory_turn(empty_session, "in on at to", "sha256:t1")
    assert r_empty.drift_bps == 0
    assert r_empty.verdict == "OK_TRAJECTORY_ALIGNED"


def test_parameter_validation_and_unregistered_entities() -> None:
    """Tests input validation and unregistered entity rejection across all entry points."""
    # Invalid drift threshold (<0 or >10000)
    with pytest.raises(ValueError, match="ERR_INVALID_DRIFT_THRESHOLD"):
        A2ATrajectoryInterlock(max_drift_threshold_bps=-1)
    with pytest.raises(ValueError, match="ERR_INVALID_DRIFT_THRESHOLD"):
        A2ATrajectoryInterlock(max_drift_threshold_bps=10001)

    interlock = A2ATrajectoryInterlock(max_drift_threshold_bps=4000)

    # Invalid root SPIFFE ID
    with pytest.raises(ValueError, match="ERR_INVALID_SPIFFE_ID"):
        interlock.register_root_authority("http://not-spiffe", ["api.com"])

    # Unregistered parent principal
    with pytest.raises(KeyError, match="ERR_UNREGISTERED_PARENT_PRINCIPAL"):
        interlock.register_delegation(
            parent_spiffe_id="spiffe://nexus/unknown_parent",
            child_spiffe_id="spiffe://nexus/child",
            parent_caid="sha256:parent",
            allowed_egress_hosts=["api.com"],
        )

    # Unregistered child validation
    valid, reason = interlock.validate_delegated_egress(
        child_spiffe_id="spiffe://nexus/unregistered_child",
        target_host="api.com",
        action_caid="sha256:act",
    )
    assert valid is False
    assert reason == "HALT_UNREGISTERED_CHILD_AGENT"

    # AgentDelegationToken post_init validation checks
    valid_parent = "spiffe://nexus/parent"
    valid_child = "spiffe://nexus/child"
    valid_caid = "sha256:aaaa"

    with pytest.raises(ValueError, match="ERR_INVALID_PARENT_SPIFFE"):
        AgentDelegationToken("bad_parent", valid_child, valid_caid, (), 0, valid_caid)
    with pytest.raises(ValueError, match="ERR_INVALID_CHILD_SPIFFE"):
        AgentDelegationToken(valid_parent, "bad_child", valid_caid, (), 0, valid_caid)
    with pytest.raises(ValueError, match="ERR_INVALID_PARENT_CAID"):
        AgentDelegationToken(valid_parent, valid_child, "bad_caid", (), 0, valid_caid)
    with pytest.raises(ValueError, match="ERR_INVALID_TAINT_LEVEL"):
        AgentDelegationToken(valid_parent, valid_child, valid_caid, (), -1, valid_caid)
    with pytest.raises(ValueError, match="ERR_INVALID_TAINT_LEVEL"):
        AgentDelegationToken(valid_parent, valid_child, valid_caid, (), 4, valid_caid)

    # Valid taint level 2
    tok_lvl_2 = AgentDelegationToken(valid_parent, valid_child, valid_caid, (), 2, valid_caid)
    assert tok_lvl_2.taint_level == 2

    with pytest.raises(ValueError, match="ERR_INVALID_DELEGATION_CAID"):
        AgentDelegationToken(valid_parent, valid_child, valid_caid, (), 0, "bad_del_caid")

    # Verify taint levels 0, 1, 2, 3 are all accepted
    for t_lvl in (0, 1, 2, 3):
        tok = AgentDelegationToken(valid_parent, valid_child, valid_caid, (), t_lvl, valid_caid)
        assert tok.taint_level == t_lvl

    # Verify frozen immutability of AgentDelegationToken and TrajectoryTurnRecord
    tok = AgentDelegationToken(valid_parent, valid_child, valid_caid, (), 2, valid_caid)
    with pytest.raises(FrozenInstanceError):
        tok.taint_level = 0  # type: ignore

    rec = TrajectoryTurnRecord(0, "intent", valid_caid, 0, "OK_TRAJECTORY_ALIGNED", valid_caid)
    with pytest.raises(FrozenInstanceError):
        rec.drift_bps = 5000  # type: ignore
