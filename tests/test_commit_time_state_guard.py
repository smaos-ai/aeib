# Copyright 2026 SovereignNexus Project
#
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
tests/test_commit_time_state_guard.py — Tests for CommitTimeStateGuard.

Validates Boundary-State Control (BSC-R) commit-time consistency:
- Positive path produces single-use commit token.
- Solvency drift (concurrent balance depletion) fails closed.
- Taint tier escalation fails closed.
- Policy epoch expiration fails closed.
- Target URI tampering fails closed.
- Single-spend ceiling breaches fail closed.
"""

import hashlib
import pytest
from src.commit_time_state_guard import (
    AuthorizationStateProjection,
    CandidateAct,
    CommitTimeStateGuard,
)


@pytest.fixture
def target_uri():
    return "https://bank.example.internal/v1/disbursements"


@pytest.fixture
def target_digest(target_uri):
    return hashlib.sha256(target_uri.encode("utf-8")).hexdigest()


@pytest.fixture
def baseline_projection(target_digest):
    return AuthorizationStateProjection(
        tenant_id="tenant-corp-001",
        policy_epoch=42,
        available_balance_minor=1000000,
        max_single_spend_minor=200000,
        context_taint_tier=0,
        target_uri_digest=target_digest,
        timestamp_ns=1700000000000,
    )


@pytest.fixture
def sample_candidate_act(baseline_projection, target_uri):
    return CandidateAct(
        caid="caid-act-001",
        tenant_id="tenant-corp-001",
        action_type="disburse_funds",
        amount_minor=150000,
        target_uri=target_uri,
        proposal_projection=baseline_projection,
    )


def test_positive_commit_authorization(sample_candidate_act, baseline_projection):
    res = CommitTimeStateGuard.evaluate_commit(sample_candidate_act, baseline_projection)
    assert res.permitted is True
    assert res.drift_detected is False
    assert res.commit_token is not None
    assert res.commit_token.startswith("commit:")


def test_solvency_drift_fails_closed(sample_candidate_act, baseline_projection):
    # Concurrent spend reduced available balance to 100,000 minor units (< 150,000 requested)
    drifted_state = AuthorizationStateProjection(
        tenant_id=baseline_projection.tenant_id,
        policy_epoch=baseline_projection.policy_epoch,
        available_balance_minor=100000,
        max_single_spend_minor=baseline_projection.max_single_spend_minor,
        context_taint_tier=baseline_projection.context_taint_tier,
        target_uri_digest=baseline_projection.target_uri_digest,
        timestamp_ns=1700000000500,
    )
    res = CommitTimeStateGuard.evaluate_commit(sample_candidate_act, drifted_state)
    assert res.permitted is False
    assert res.drift_detected is True
    assert "SOLVENCY_DRIFT" in res.reason


def test_taint_elevation_drift_fails_closed(sample_candidate_act, baseline_projection):
    # Live context taint elevated to Tier 2 (Suspicious)
    drifted_state = AuthorizationStateProjection(
        tenant_id=baseline_projection.tenant_id,
        policy_epoch=baseline_projection.policy_epoch,
        available_balance_minor=baseline_projection.available_balance_minor,
        max_single_spend_minor=baseline_projection.max_single_spend_minor,
        context_taint_tier=2,
        target_uri_digest=baseline_projection.target_uri_digest,
        timestamp_ns=1700000000500,
    )
    res = CommitTimeStateGuard.evaluate_commit(sample_candidate_act, drifted_state)
    assert res.permitted is False
    assert res.drift_detected is True
    assert "TAINT_ELEVATION_DRIFT" in res.reason


def test_policy_epoch_drift_fails_closed(sample_candidate_act, baseline_projection):
    # Policy epoch advanced from 42 to 43
    drifted_state = AuthorizationStateProjection(
        tenant_id=baseline_projection.tenant_id,
        policy_epoch=43,
        available_balance_minor=baseline_projection.available_balance_minor,
        max_single_spend_minor=baseline_projection.max_single_spend_minor,
        context_taint_tier=baseline_projection.context_taint_tier,
        target_uri_digest=baseline_projection.target_uri_digest,
        timestamp_ns=1700000000500,
    )
    res = CommitTimeStateGuard.evaluate_commit(sample_candidate_act, drifted_state)
    assert res.permitted is False
    assert res.drift_detected is True
    assert "POLICY_EPOCH_DRIFT" in res.reason


def test_target_uri_drift_fails_closed(sample_candidate_act, baseline_projection):
    # Attacker mutates candidate target URI
    tampered_act = CandidateAct(
        caid=sample_candidate_act.caid,
        tenant_id=sample_candidate_act.tenant_id,
        action_type=sample_candidate_act.action_type,
        amount_minor=sample_candidate_act.amount_minor,
        target_uri="https://attacker.evil.com/exfiltrate",
        proposal_projection=sample_candidate_act.proposal_projection,
    )
    res = CommitTimeStateGuard.evaluate_commit(tampered_act, baseline_projection)
    assert res.permitted is False
    assert res.drift_detected is True
    assert "TARGET_URI_DRIFT" in res.reason


def test_ceiling_breach_fails_closed(baseline_projection, target_uri):
    # Action exceeds single spend ceiling
    over_ceiling_act = CandidateAct(
        caid="caid-over-ceiling",
        tenant_id=baseline_projection.tenant_id,
        action_type="disburse_funds",
        amount_minor=250000,  # Ceiling is 200,000
        target_uri=target_uri,
        proposal_projection=baseline_projection,
    )
    res = CommitTimeStateGuard.evaluate_commit(over_ceiling_act, baseline_projection)
    assert res.permitted is False
    assert "CEILING_BREACH" in res.reason
