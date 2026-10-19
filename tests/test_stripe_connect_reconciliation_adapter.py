#!/usr/bin/env python3
"""
tests/test_stripe_connect_reconciliation_adapter.py
================================================================================
Test suite for the Stripe Connect Production Rail Reconciliation Adapter.
Evaluates HMAC-SHA256 webhook signatures, HTTP 504 latching, idempotency key
derivation, single-flight probe budget enforcement, and Ed25519 JCS receipts.
"""

import hmac
import hashlib
import time
from typing import Dict, Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.adapters.stripe_connect_reconciliation_adapter import (
    StripeWebhookVerifier,
    StripeConnectReconciliationAdapter,
    verify_stripe_connect_receipt,
)


def test_stripe_webhook_signature_verification_positive():
    secret = "whsec_test_secret_key_12345"
    payload = b'{"id": "evt_test_123", "type": "transfer.created", "data": {"object": {"id": "tr_123"}}}'
    now_ts = 1700000000

    signed_payload = f"{now_ts}.".encode("utf-8") + payload
    sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    header = f"t={now_ts},v1={sig}"

    res = StripeWebhookVerifier.verify_signature(
        payload_bytes=payload,
        sig_header=header,
        secret=secret,
        tolerance_sec=300,
        current_time=now_ts + 10,
    )
    assert res["valid"] is True
    assert res["timestamp"] == now_ts


def test_stripe_webhook_signature_rejection_forged_and_expired():
    secret = "whsec_test_secret_key_12345"
    payload = b'{"id": "evt_test_123"}'
    now_ts = 1700000000

    # Forged signature
    header_forged = f"t={now_ts},v1=0000000000000000000000000000000000000000000000000000000000000000"
    res_forged = StripeWebhookVerifier.verify_signature(
        payload_bytes=payload,
        sig_header=header_forged,
        secret=secret,
        current_time=now_ts,
    )
    assert res_forged["valid"] is False
    assert res_forged["reason"] == "SIGNATURE_MISMATCH"

    # Expired timestamp (skew > 300s)
    signed_payload = f"{now_ts}.".encode("utf-8") + payload
    sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    header_valid_sig = f"t={now_ts},v1={sig}"
    res_expired = StripeWebhookVerifier.verify_signature(
        payload_bytes=payload,
        sig_header=header_valid_sig,
        secret=secret,
        tolerance_sec=300,
        current_time=now_ts + 500,
    )
    assert res_expired["valid"] is False
    assert res_expired["reason"] == "TIMESTAMP_OUTSIDE_TOLERANCE"


def test_stripe_connect_adapter_http504_latching_and_retry_blocking():
    privkey = ed25519.Ed25519PrivateKey.generate()
    adapter = StripeConnectReconciliationAdapter(
        adapter_privkey=privkey,
        webhook_secret="whsec_adapter_secret",
    )

    op_id = "op_transfer_9901"
    action_payload = {
        "amount": 25000,
        "currency": "eur",
        "destination": "acct_connected_test_42",
    }

    # Simulate dispatch encountering HTTP 504 Gateway Timeout
    dispatch_res = adapter.dispatch_transfer(
        operation_id=op_id,
        connected_account_id="acct_connected_test_42",
        amount_minor=25000,
        currency="eur",
        action_payload=action_payload,
        simulate_transport_fault="HTTP_504_GATEWAY_TIMEOUT",
    )

    assert dispatch_res["dispatched"] is False
    assert dispatch_res["status"] == "EFFECT_INDETERMINATE"
    assert "aeib-idem-v1-" in dispatch_res["idempotency_key"]

    # Verify receipt signature
    receipt = dispatch_res["receipt"]
    assert verify_stripe_connect_receipt(adapter.public_key, receipt) is True

    # Immediate naive retry must be blocked
    retry_res = adapter.dispatch_transfer(
        operation_id=op_id,
        connected_account_id="acct_connected_test_42",
        amount_minor=25000,
        currency="eur",
        action_payload=action_payload,
    )
    assert retry_res["dispatched"] is False
    assert retry_res["status"] == "HALT_TRANSFER_LOCKED_INDETERMINATE"


def test_stripe_connect_single_flight_probe_reconciliation():
    privkey = ed25519.Ed25519PrivateKey.generate()
    adapter = StripeConnectReconciliationAdapter(
        adapter_privkey=privkey,
        webhook_secret="whsec_adapter_secret",
    )

    op_id = "op_transfer_9902"
    action_payload = {
        "amount": 15000,
        "currency": "eur",
        "destination": "acct_connected_test_88",
    }

    # Dispatch with TCP_RST fault
    adapter.dispatch_transfer(
        operation_id=op_id,
        connected_account_id="acct_connected_test_88",
        amount_minor=15000,
        currency="eur",
        action_payload=action_payload,
        simulate_transport_fault="TCP_RST",
    )

    # Reconcile via status probe (ProbeBudget: 1)
    probe_response = {
        "id": "tr_stripe_9902",
        "status": "succeeded",
        "amount": 15000,
    }
    rec_res = adapter.reconcile_indeterminate_transfer(
        operation_id=op_id,
        probe_result=probe_response,
    )
    assert rec_res["reconciled"] is True
    assert rec_res["status"] == "RESOLVED_CONFIRMED"
    assert verify_stripe_connect_receipt(adapter.public_key, rec_res["receipt"]) is True

    # Attempting a second probe on the same operation must fail closed
    second_probe = adapter.reconcile_indeterminate_transfer(
        operation_id=op_id,
        probe_result=probe_response,
    )
    assert second_probe["reconciled"] is False
    assert second_probe["status"] == "HALT_NOT_INDETERMINATE"


def test_stripe_connect_probe_refuted_and_webhook_event_processing():
    privkey = ed25519.Ed25519PrivateKey.generate()
    secret = "whsec_test_hook_456"
    adapter = StripeConnectReconciliationAdapter(
        adapter_privkey=privkey,
        webhook_secret=secret,
    )

    op_id = "op_transfer_9903"
    action_payload = {
        "amount": 5000,
        "currency": "eur",
        "destination": "acct_connected_test_99",
    }

    adapter.dispatch_transfer(
        operation_id=op_id,
        connected_account_id="acct_connected_test_99",
        amount_minor=5000,
        currency="eur",
        action_payload=action_payload,
        simulate_transport_fault="NETWORK_TIMEOUT",
    )

    # Reconcile with downstream REFUTED/failed
    probe_response = {
        "id": "tr_stripe_9903",
        "status": "failed",
    }
    rec_res = adapter.reconcile_indeterminate_transfer(
        operation_id=op_id,
        probe_result=probe_response,
    )
    assert rec_res["reconciled"] is True
    assert rec_res["status"] == "RESOLVED_REFUTED"

    # Now test incoming webhook on an indeterminate op
    op_id2 = "op_transfer_9904"
    adapter.dispatch_transfer(
        operation_id=op_id2,
        connected_account_id="acct_connected_test_99",
        amount_minor=7000,
        currency="eur",
        action_payload={"amount": 7000, "currency": "eur"},
        simulate_transport_fault="HTTP_504_GATEWAY_TIMEOUT",
    )

    raw_event = (
        b'{"id": "evt_hook_1", "type": "transfer.created", '
        b'"data": {"object": {"id": "tr_9904", "metadata": {"aeib_operation_id": "op_transfer_9904"}}}}'
    )
    now_ts = 1700000000
    signed_payload = f"{now_ts}.".encode("utf-8") + raw_event
    sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    header = f"t={now_ts},v1={sig}"

    hook_res = adapter.process_incoming_webhook(
        raw_body=raw_event,
        sig_header=header,
        now_ts=now_ts,
    )
    assert hook_res["processed"] is True
    assert hook_res["status"] == "WEBHOOK_EVENT_VERIFIED"
    assert adapter._operations[op_id2]["status"] == "RESOLVED_CONFIRMED"
