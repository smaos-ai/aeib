#!/usr/bin/env python3
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
tests/test_configurable_reconciliation.py
================================================================================
Unit tests for the AEIB Configurable Target Reconciliation Policy Engine (Milestone 4).
"""

import sys
import time
import pytest
from pathlib import Path

# Add project root and roadmap to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "v1.1-roadmap"))

from configurable_reconciliation_engine import (
    TargetReconciliationPolicy,
    ConfigurableReconciliationEngine,
    DISPOSITION_CONFIRMED,
    DISPOSITION_REFUTED,
    DISPOSITION_PRESERVED_UNCERTAINTY,
    DISPOSITION_CIRCUIT_TRIPPED
)


def test_01_policy_validation_fences():
    # Valid policy
    p = TargetReconciliationPolicy(target_pattern="https://api.bank.internal/*", max_attempts=3)
    assert p.max_attempts == 3

    # Attempt ceiling > 5 rejected
    with pytest.raises(ValueError, match="max_attempts must be in range"):
        TargetReconciliationPolicy(target_pattern="*", max_attempts=10)

    # Concurrency > 1 rejected
    with pytest.raises(ValueError, match="max_concurrent_probes must be 1"):
        TargetReconciliationPolicy(target_pattern="*", max_concurrent_probes=2)


def test_02_immediate_confirmed_resolution():
    engine = ConfigurableReconciliationEngine()

    def mock_probe(op_id, key):
        return 200, {"status": "COMMITTED", "commit_count": 1}

    res = engine.reconcile_target(
        action_id="act_001",
        operation_id="op_001",
        idempotency_key="key_001",
        target_uri="https://api.bank.internal/v1/payments",
        probe_fn=mock_probe
    )
    assert res.disposition == DISPOSITION_CONFIRMED
    assert res.reconciliation_attempts == 1
    assert res.retry_safe is False
    assert res.downstream_commit_count == 1


def test_03_immediate_refuted_resolution():
    engine = ConfigurableReconciliationEngine()

    def mock_probe(op_id, key):
        return 404, {"status": "NOT_FOUND"}

    res = engine.reconcile_target(
        action_id="act_002",
        operation_id="op_002",
        idempotency_key="key_002",
        target_uri="https://api.bank.internal/v1/payments",
        probe_fn=mock_probe
    )
    assert res.disposition == DISPOSITION_REFUTED
    assert res.reconciliation_attempts == 1
    assert res.retry_safe is True
    assert res.downstream_commit_count == 0


def test_04_transient_failure_then_confirmed_with_backoff():
    engine = ConfigurableReconciliationEngine([
        TargetReconciliationPolicy(
            target_pattern="*",
            max_attempts=3,
            initial_backoff_ms=10,
            max_backoff_ms=50
        )
    ])

    call_count = 0
    sleeps_recorded = []

    def mock_probe(op_id, key):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return 503, {"status": "SERVICE_UNAVAILABLE"}
        return 200, {"status": "COMMITTED", "commit_count": 1}

    def fake_sleep(duration):
        sleeps_recorded.append(duration)

    res = engine.reconcile_target(
        action_id="act_003",
        operation_id="op_003",
        idempotency_key="key_003",
        target_uri="https://api.bank.internal/v1/payments",
        probe_fn=mock_probe,
        sleep_fn=fake_sleep
    )
    assert res.disposition == DISPOSITION_CONFIRMED
    assert res.reconciliation_attempts == 2
    assert len(sleeps_recorded) == 1
    assert sleeps_recorded[0] > 0


def test_05_exhaustion_yields_preserved_uncertainty_no_blind_retry():
    engine = ConfigurableReconciliationEngine([
        TargetReconciliationPolicy(target_pattern="*", max_attempts=3, initial_backoff_ms=1)
    ])

    def mock_outage(op_id, key):
        return 503, {"status": "GATEWAY_TIMEOUT"}

    res = engine.reconcile_target(
        action_id="act_004",
        operation_id="op_004",
        idempotency_key="key_004",
        target_uri="https://api.bank.internal/v1/payments",
        probe_fn=mock_outage,
        sleep_fn=lambda _: None
    )
    assert res.disposition == DISPOSITION_PRESERVED_UNCERTAINTY
    assert res.reconciliation_attempts == 3
    assert res.retry_safe is False
    assert "Exhausted 3 attempts" in res.diagnostic


def test_06_circuit_breaker_tripping():
    policy = TargetReconciliationPolicy(
        target_pattern="https://api.bank.internal/*",
        max_attempts=1,
        circuit_breaker_threshold=2,
        circuit_quarantine_seconds=30.0
    )
    engine = ConfigurableReconciliationEngine([policy])

    def mock_down(op_id, key):
        return 503, {"error": "down"}

    # Outage 1
    r1 = engine.reconcile_target(action_id="a1", operation_id="o1", idempotency_key="k1", target_uri="https://api.bank.internal/v1/pay", probe_fn=mock_down)
    assert r1.disposition == DISPOSITION_PRESERVED_UNCERTAINTY

    # Outage 2 -> trips circuit breaker
    r2 = engine.reconcile_target(action_id="a2", operation_id="o2", idempotency_key="k2", target_uri="https://api.bank.internal/v1/pay", probe_fn=mock_down)
    assert r2.disposition == DISPOSITION_PRESERVED_UNCERTAINTY

    # Outage 3 -> rejected immediately with CIRCUIT_TRIPPED (zero probe dispatch)
    r3 = engine.reconcile_target(action_id="a3", operation_id="o3", idempotency_key="k3", target_uri="https://api.bank.internal/v1/pay", probe_fn=mock_down)
    assert r3.disposition == DISPOSITION_CIRCUIT_TRIPPED
    assert r3.reconciliation_attempts == 0
