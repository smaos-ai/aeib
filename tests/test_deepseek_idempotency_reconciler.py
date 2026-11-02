#!/usr/bin/env python3
"""
tests/test_deepseek_idempotency_reconciler.py — Verification of DeepSeek CoT Reconciler & Latches

Verifies:
1. Parsing of DeepSeek 5-step Chain-of-Thought (<thought> and <action> blocks).
2. Nominal idempotent execution.
3. Network drop (HTTP 504 / TCP RST) followed by "Update 1 -> Update 2" retry storm:
   - Update 1: ANSI 50 instantaneous overcurrent breaker trips on duplicate intent.
   - Update 2: ANSI 86 permanent lockout relay trips on unlatched retry storm.
   - Strict invariant: 0 duplicate committed writes (0.0% / 0 bps).
4. ANSI 86 cryptographic clearance token validation and replay defense.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.deepseek_idempotency_reconciler import (
    DeepSeekIdempotencyReconciler,
    parse_deepseek_cot,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

SAMPLE_DEEPSEEK_COT = """
<thought>
Step 1: Epistemic Observation
Observed network timeout (TCP RST) from upstream gateway on client_request_id req-9912.
Step 2: Effect Key Derivation
Computing canonical RFC 8785 SHA-256 digest over tenant tenant-01, recipient ACC-987, amount 50000 minor units.
Step 3: State Recheck
Checking local transactional ledger for existing caid commit before issuing mutate call.
Step 4: Assess Protection Latches
Verifying whether ANSI 50 overcurrent or ANSI 86 lockout conditions are active.
Step 5: Emit Ontic Execution Intent
Generating idempotent execution proposal.
</thought>
<action>
{
    "client_request_id": "req-9912",
    "mutation": {
        "tenant_id": "tenant-01",
        "recipient_account": "ACC-987",
        "amount_minor": 50000,
        "currency": "USD",
        "business_ref": "INVOICE-2026-X"
    }
}
</action>
"""

SAMPLE_MARKDOWN_COT = """
<think>
### Step 1: Initial Triage
Candidate anomaly observed.
### Step 2: Key Hash
Deriving CAID.
### Step 3: Ledger Inspection
Reading committed records.
</think>
"""


def test_parse_deepseek_cot_5_steps():
    """Verify parsing of DeepSeek 5-step Chain-of-Thought."""
    record = parse_deepseek_cot(SAMPLE_DEEPSEEK_COT)
    assert record.detected_step_count == 5
    assert record.steps[0].step_number == 1
    assert "Epistemic Observation" in record.steps[0].step_name
    assert "TCP RST" in record.steps[0].content
    assert record.steps[1].step_number == 2
    assert "RFC 8785" in record.steps[1].content
    assert record.action_payload is not None
    assert record.action_payload["client_request_id"] == "req-9912"

    # Test markdown header format with <think>
    md_record = parse_deepseek_cot(SAMPLE_MARKDOWN_COT)
    assert md_record.detected_step_count == 3
    assert md_record.steps[0].step_number == 1
    assert md_record.steps[1].step_number == 2
    assert md_record.steps[2].step_number == 3


def test_nominal_execution_and_idempotence():
    """Verify nominal mutation execution commits without duplicate writes."""
    reconciler = DeepSeekIdempotencyReconciler()
    req = {
        "client_request_id": "req-1001",
        "mutation": {
            "tenant_id": "tenant-01",
            "recipient_account": "ACC-123",
            "amount_minor": 10000,
            "currency": "USD",
            "business_ref": "REF-001",
        },
    }

    res1 = reconciler.process_execution_request(req, cot_text=SAMPLE_DEEPSEEK_COT)
    assert res1["status"] == "SUCCESS"
    assert res1["committed"] is True
    assert res1["code"] == "OK"
    assert res1["cot_steps_observed"] == 5
    assert reconciler.committed_writes == 1
    assert reconciler.duplicate_committed_writes == 0

    # Re-sending exact same request trips ANSI 50
    res2 = reconciler.process_execution_request(req)
    assert res2["status"] == "TRIPPED_ANSI_50"
    assert res2["committed"] is False
    assert reconciler.committed_writes == 1
    assert reconciler.duplicate_committed_writes == 0


def test_tcp_rst_and_http_504_network_drop_and_retry_storm():
    """Verify 'TCP RST -> Update 1 -> Update 2' trips ANSI 50 then ANSI 86 with 0 duplicate writes."""
    reconciler = DeepSeekIdempotencyReconciler()
    req = {
        "client_request_id": "storm-req-01",
        "mutation": {
            "tenant_id": "tenant-02",
            "recipient_account": "ACC-555",
            "amount_minor": 25000,
            "currency": "EUR",
            "business_ref": "PAY-555",
        },
    }

    # 1. First execution encounters TCP RST network drop (wire_status == 0)
    res_drop = reconciler.process_execution_request(req, simulate_network_fault="TCP_RST")
    assert res_drop["status"] == "NETWORK_FAULT_DROPPED"
    assert res_drop["code"] == "TCP_RST"
    assert res_drop["wire_status"] == 0
    assert res_drop["committed"] is True
    assert reconciler.committed_writes == 1
    assert reconciler.duplicate_committed_writes == 0

    # 2. Update 1 retry storm arrives: ANSI 50 Instantaneous Overcurrent trips
    res_upd1 = reconciler.process_execution_request(req)
    assert res_upd1["status"] == "TRIPPED_ANSI_50"
    assert res_upd1["code"] == "ANSI_50_DUPLICATE_INTENT_BLOCKED"
    assert reconciler.committed_writes == 1
    assert reconciler.duplicate_committed_writes == 0
    assert reconciler.ansi_50_trips == 1

    # 3. Update 2 retry storm arrives without clearance: ANSI 86 Lockout trips
    res_upd2 = reconciler.process_execution_request(req)
    assert res_upd2["status"] == "TRIPPED_ANSI_86"
    assert res_upd2["code"] == "ANSI_86_LOCKOUT_TRIPPED"
    assert reconciler.is_locked_out is True
    effect_key = reconciler.compute_effect_key(req["mutation"])
    expected_reason = (
        f"ANSI_86_LOCKOUT_TRIPPED: effect_key {effect_key[:16]} received 3 retry attempts without clearance token (retry storm bypass detected)."
    )
    assert res_upd2["reason"] == expected_reason
    assert reconciler.committed_writes == 1
    assert reconciler.duplicate_committed_writes == 0
    assert reconciler.ansi_86_trips == 1

    # 4. Subsequent requests while locked out are rejected immediately
    res_blocked = reconciler.process_execution_request({
        "client_request_id": "other-req",
        "mutation": {"tenant_id": "tenant-02", "recipient_account": "ACC-999", "amount_minor": 100, "currency": "USD", "business_ref": "REF-X"},
    })
    assert res_blocked["status"] == "TRIPPED_ANSI_86"
    assert res_blocked["code"] == "ANSI_86_LOCKED_OUT"
    assert reconciler.duplicate_committed_writes == 0


def test_http_504_wire_status():
    """Verify HTTP 504 simulated wire status returns 504."""
    reconciler = DeepSeekIdempotencyReconciler()
    req = {
        "client_request_id": "http-504-req",
        "mutation": {"tenant_id": "tenant-09", "recipient_account": "ACC-999", "amount_minor": 10, "currency": "USD", "business_ref": "REF-504"},
    }
    res = reconciler.process_execution_request(req, simulate_network_fault="HTTP_504")
    assert res["status"] == "NETWORK_FAULT_DROPPED"
    assert res["wire_status"] == 504
    assert res["committed"] is True


def test_ansi_86_clearance_and_replay_defense():
    """Verify clearance token resets lockout and replaying nonce fails closed."""
    reconciler = DeepSeekIdempotencyReconciler()
    req = {
        "client_request_id": "lock-test-01",
        "mutation": {
            "tenant_id": "tenant-03",
            "recipient_account": "ACC-777",
            "amount_minor": 12000,
            "currency": "GBP",
            "business_ref": "LOCK-777",
        },
    }

    # Trip to lockout
    reconciler.process_execution_request(req, simulate_network_fault="HTTP_504")
    reconciler.process_execution_request(req)
    reconciler.process_execution_request(req)
    assert reconciler.is_locked_out is True

    # Attempt clearance with invalid token action
    bad_token = {"payload": {"action": "WRONG_ACTION", "nonce": "n1", "task_id": "t1"}, "signature_hex": "00" * 64}
    cleared, err_msg = reconciler.clear_ansi_86_lockout(bad_token)
    assert cleared is False
    assert "ERR_INVALID_ACTION" in err_msg
    assert reconciler.is_locked_out is True

    # Attempt clearance with missing/empty nonce
    empty_nonce_token = {"payload": {"action": "ANSI_86_CLEAR_LOCKOUT", "nonce": "", "task_id": "t1"}}
    cleared_nonce, err_nonce_msg = reconciler.clear_ansi_86_lockout(empty_nonce_token)
    assert cleared_nonce is False
    assert err_nonce_msg == "ERR_MISSING_NONCE"

    # Legitimate clearance
    valid_token = reconciler.generate_clearance_token(task_id="task-recovery-01", nonce="nonce-unique-abc-123")
    cleared, ok_msg = reconciler.clear_ansi_86_lockout(valid_token)
    assert cleared is True
    assert "CLEAR_LOCKOUT_SUCCESS" in ok_msg
    assert reconciler.is_locked_out is False

    # Replay attack with same nonce
    replayed, replay_msg = reconciler.clear_ansi_86_lockout(valid_token)
    assert replayed is False
    assert "ERR_NONCE_ALREADY_CONSUMED" in replay_msg

    # Verify metrics summary
    metrics = reconciler.get_summary_metrics()
    assert metrics["duplicate_committed_writes"] == 0
    assert metrics["ansi_86_trips"] == 1
