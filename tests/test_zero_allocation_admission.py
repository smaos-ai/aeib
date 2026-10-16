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
tests/test_zero_allocation_admission.py
================================================================================
Test suite for Zero-Allocation Admission Hook (Gap 5: Admissible Computation).
Evaluated under the stated model. Preserves strict epistemic lock.
"""

from src.zero_allocation_admission import ZeroAllocationAdmissionHook


def _build_hook() -> ZeroAllocationAdmissionHook:
    return ZeroAllocationAdmissionHook(
        allowed_agents=frozenset({"agent-finance-01", "agent-support-02"}),
        allowed_tools=frozenset({"customer_refund", "order_status"}),
        allowed_hosts=frozenset({"api.internal.bank", "api.support.internal"}),
        active_policy_epoch=3,
        revoked_authorities={"revoked-grant-99"},
    )


def test_positive_admission():
    hook = _build_hook()
    headers = {
        "agent_id": "agent-finance-01",
        "tool_name": "customer_refund",
        "target_host": "api.internal.bank",
        "policy_epoch": 3,
        "authority_id": "grant-valid-01",
    }
    verdict = hook.evaluate_admissibility(headers)
    assert verdict.admitted is True
    assert verdict.rejection_code is None
    assert verdict.eval_epoch == 3


def test_reject_unregistered_agent():
    hook = _build_hook()
    headers = {
        "agent_id": "rogue-agent-999",
        "tool_name": "customer_refund",
        "target_host": "api.internal.bank",
        "policy_epoch": 3,
        "authority_id": "grant-valid-01",
    }
    verdict = hook.evaluate_admissibility(headers)
    assert verdict.admitted is False
    assert verdict.rejection_code == "UNREGISTERED_AGENT"


def test_reject_unallowlisted_tool():
    hook = _build_hook()
    headers = {
        "agent_id": "agent-finance-01",
        "tool_name": "delete_all_accounts",
        "target_host": "api.internal.bank",
        "policy_epoch": 3,
        "authority_id": "grant-valid-01",
    }
    verdict = hook.evaluate_admissibility(headers)
    assert verdict.admitted is False
    assert verdict.rejection_code == "UNALLOWLISTED_TOOL"


def test_reject_host_audience_mismatch():
    hook = _build_hook()
    headers = {
        "agent_id": "agent-finance-01",
        "tool_name": "customer_refund",
        "target_host": "malicious-destination.com",
        "policy_epoch": 3,
        "authority_id": "grant-valid-01",
    }
    verdict = hook.evaluate_admissibility(headers)
    assert verdict.admitted is False
    assert verdict.rejection_code == "HOST_AUDIENCE_MISMATCH"


def test_reject_stale_or_spoofed_epoch():
    hook = _build_hook()
    headers = {
        "agent_id": "agent-finance-01",
        "tool_name": "customer_refund",
        "target_host": "api.internal.bank",
        "policy_epoch": 2,  # Active is 3
        "authority_id": "grant-valid-01",
    }
    verdict = hook.evaluate_admissibility(headers)
    assert verdict.admitted is False
    assert verdict.rejection_code == "STALE_OR_SPOOFED_EPOCH"


def test_reject_revoked_authority():
    hook = _build_hook()
    headers = {
        "agent_id": "agent-finance-01",
        "tool_name": "customer_refund",
        "target_host": "api.internal.bank",
        "policy_epoch": 3,
        "authority_id": "revoked-grant-99",
    }
    verdict = hook.evaluate_admissibility(headers)
    assert verdict.admitted is False
    assert verdict.rejection_code == "AUTHORITY_REVOKED"


def test_benchmark_rejection_throughput():
    hook = _build_hook()
    stats = hook.benchmark_rejection_throughput(iterations=5000)
    assert stats["iterations"] == 5000.0
    # Mean rejection latency must be under 15 microseconds
    assert stats["mean_latency_us"] < 15.0, f"Rejection too slow: {stats['mean_latency_us']} us"
    assert stats["ops_per_second"] > 50_000.0
