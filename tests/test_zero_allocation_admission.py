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
Zero mock frameworks, 100.00% mutation adequacy target.
"""

import dataclasses
import pytest

from src.zero_allocation_admission import (
    DEFAULT_BENCHMARK_ITERATIONS,
    DEFAULT_UNAUTHORIZED_HEADER,
    ZeroAllocationAdmissionHook,
)


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
    assert 0 <= verdict.latency_ns < 100_000_000

    d = verdict.to_dict()
    assert d["admitted"] is True
    assert d["eval_epoch"] == 3
    assert d["rejection_code"] is None
    assert d["latency_ns"] == verdict.latency_ns

    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.admitted = False  # type: ignore[misc]


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
    assert 0 <= verdict.latency_ns < 100_000_000


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
    assert 0 <= verdict.latency_ns < 100_000_000


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
    assert 0 <= verdict.latency_ns < 100_000_000


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
    assert 0 <= verdict.latency_ns < 100_000_000


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
    assert 0 <= verdict.latency_ns < 100_000_000


def test_benchmark_rejection_throughput():
    hook = _build_hook()
    assert DEFAULT_BENCHMARK_ITERATIONS == 10000
    assert DEFAULT_UNAUTHORIZED_HEADER["policy_epoch"] == 999
    assert DEFAULT_UNAUTHORIZED_HEADER["agent_id"] == "malicious-bot-flood"

    stats_default = hook.benchmark_rejection_throughput()
    assert stats_default["iterations"] == 10000.0
    assert stats_default["ops_per_second"] > 50_000.0

    stats = hook.benchmark_rejection_throughput(iterations=5000)
    assert stats["iterations"] == 5000.0
    assert stats["mean_latency_us"] < 15.0, f"Rejection too slow: {stats['mean_latency_us']} us"
    assert stats["ops_per_second"] > 50_000.0
