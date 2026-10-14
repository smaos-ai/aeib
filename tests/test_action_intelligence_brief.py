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
test_action_intelligence_brief.py
================================================================================
Comprehensive test suite for the AEIB Action Intelligence Brief, Slack Adapter,
and Human Resolution Authority governance boundaries.
"""

import sys
import os
import json
import time
import hmac
import hashlib
import pytest
from pathlib import Path
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Add repo root and v1.1-roadmap to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "v1.1-roadmap"))

from action_intelligence_brief import (
    PRIORITY_P1,
    PRIORITY_P2,
    PRIORITY_P3,
    PRIORITY_P4,
    DECISION_ESCALATE,
    DECISION_MARK_TARGET_FAILED,
    DECISION_REQUEST_ADDITIONAL_RECONCILIATION,
    PROHIBITED_DECLARE_SUCCESS,
    PROHIBITED_RETRY_BLINDLY,
    PROHIBITED_CHANGE_POLICY,
    PROHIBITED_GRANT_NEW_AUTHORITY,
    ALLOWED_RESOLUTION_STEPS,
    PROHIBITED_RESOLUTION_STEPS,
    ProhibitedDecisionError,
    TicketAlreadyBurnedError,
    TicketExpiredError,
    InvalidSignatureError,
    HumanResolutionAuthority,
    ActionIntelligenceBrief,
    ActionIntelligenceBriefGenerator,
    SlackBlockKitAdapter,
    HumanResolutionAuthorityManager,
    LLMExplainer,
    NON_AUTHORITATIVE_DISCLAIMER,
    BANNED_WORDS
)

from governed_financial_action_boundary import (
    FinancialCandidateAction,
    FinancialContinuityReceipt,
    DISPOSITION_EFFECT_INDETERMINATE,
    DISPOSITION_RECONCILIATION_CONFLICT,
    DISPOSITION_PRESERVED_UNCERTAINTY,
    DISPOSITION_CONFIRMED,
    DISPOSITION_REFUTED
)


@pytest.fixture
def sample_candidate_and_receipt():
    candidate = FinancialCandidateAction(
        action_id="act_refund_test_001",
        principal="support_agent_tier1",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={
            "operation_id": "refund_8817_001",
            "amount_cents": 4990,
            "currency": "EUR",
            "customer_id": "cust_8817",
            "_reasoning": "Customer complained about double billing."
        },
        policy_epoch=1,
        source_epoch=1
    )

    receipt = FinancialContinuityReceipt(
        receipt_version="v1.0.0-financial-boundary",
        action_id=candidate.action_id,
        caid=candidate.compute_caid(),
        ticket_id="ticket_auth_abc123",
        principal=candidate.principal,
        target_uri=candidate.target_uri,
        operation_id="refund_8817_001",
        disposition=DISPOSITION_EFFECT_INDETERMINATE,
        retry_safe=False,
        reconciliation_attempts=1,
        downstream_commit_count=0,
        chain_tip="sha256:11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        signature_hex="aa" * 64,
        public_key_pem="-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA...\n-----END PUBLIC KEY-----\n"
    )

    return candidate, receipt


# ------------------------------------------------------------------------------
# Test 1: Action Intelligence Brief Generation
# ------------------------------------------------------------------------------
def test_01_brief_generation_from_indeterminate_state(sample_candidate_and_receipt):
    candidate, receipt = sample_candidate_and_receipt

    brief = ActionIntelligenceBriefGenerator.generate_brief(
        candidate=candidate,
        receipt=receipt,
        transport_outcome="HTTP_504_GATEWAY_TIMEOUT",
        http_status=504,
        target_reconciliation_status="INCONCLUSIVE",
        probes_executed=1,
        policy_version="finance_v7"
    )

    assert brief.priority == PRIORITY_P1
    assert brief.operation_id == "refund_8817_001"
    assert brief.action_id == "act_refund_test_001"
    assert brief.caid.startswith("caid:sha256:")
    assert brief.what_was_authorized["amount_cents"] == 4990
    assert brief.what_was_authorized["currency"] == "EUR"
    assert brief.what_was_authorized["policy_version"] == "finance_v7"
    assert brief.what_happened_externally["transport_outcome"] == "HTTP_504_GATEWAY_TIMEOUT"
    assert brief.what_happened_externally["http_status"] == 504
    assert brief.what_happened_externally["probes_executed"] == 1

    # Verify audit steps in what_aeib_did
    assert any("intent" in step.lower() for step in brief.what_aeib_did)
    assert any("burned" in step.lower() for step in brief.what_aeib_did)
    assert any("effect_indeterminate" in step.lower() for step in brief.what_aeib_did)

    # Verify permitted and prohibited boundaries
    assert set(brief.permitted_next_steps) == ALLOWED_RESOLUTION_STEPS
    assert set(brief.prohibited_next_steps) == PROHIBITED_RESOLUTION_STEPS


# ------------------------------------------------------------------------------
# Test 2: Slack Block Kit Formatting
# ------------------------------------------------------------------------------
def test_02_slack_block_kit_formatting_and_button_isolation(sample_candidate_and_receipt):
    candidate, receipt = sample_candidate_and_receipt
    brief = ActionIntelligenceBriefGenerator.generate_brief(
        candidate=candidate,
        receipt=receipt,
        transport_outcome="HTTP_504_GATEWAY_TIMEOUT",
        http_status=504,
        target_reconciliation_status="INCONCLUSIVE",
        probes_executed=1
    )

    payload = SlackBlockKitAdapter.format_slack_block_kit(brief)
    assert "blocks" in payload
    blocks = payload["blocks"]

    # Header check
    header = blocks[0]
    assert header["type"] == "header"
    assert "🚨 [P1 — RESOLUTION REQUIRED]" in header["text"]["text"]

    # Actions block check
    actions_block = [b for b in blocks if b["type"] == "actions"][0]
    elements = actions_block["elements"]
    action_texts = [el["text"]["text"] for el in elements]

    assert "View Evidence" in action_texts
    assert "Escalate to L2" in action_texts
    assert "Request Additional Check" in action_texts

    # Ensure prohibited buttons do NOT exist
    assert "Approve Release" not in action_texts
    assert "Approve Manual Release" not in action_texts
    assert "Mark as Failed" not in action_texts
    assert "Retry" not in action_texts


# ------------------------------------------------------------------------------
# Test 3: Slack HMAC-SHA256 Signature Verification
# ------------------------------------------------------------------------------
def test_03_slack_signature_verification_positive():
    secret = "test_signing_secret_12345"
    now = time.time()
    raw_body = b'payload={"type":"block_actions","user":{"id":"U123"},"actions":[{"action_id":"action_escalate_l2"}]}'

    sig_basestring = f"v0:{int(now)}:".encode("utf-8") + raw_body
    computed_sig = "v0=" + hmac.new(secret.encode("utf-8"), sig_basestring, hashlib.sha256).hexdigest()

    headers = {
        "X-Slack-Request-Timestamp": str(int(now)),
        "X-Slack-Signature": computed_sig
    }

    verified, msg = SlackBlockKitAdapter.verify_slack_request(
        headers=headers,
        raw_body=raw_body,
        signing_secret=secret,
        current_time=now
    )
    assert verified is True
    assert msg == "VERIFIED"


def test_04_slack_signature_verification_tampered():
    secret = "test_signing_secret_12345"
    now = time.time()
    raw_body = b'payload={"action":"legitimate"}'
    sig_basestring = f"v0:{int(now)}:".encode("utf-8") + raw_body
    computed_sig = "v0=" + hmac.new(secret.encode("utf-8"), sig_basestring, hashlib.sha256).hexdigest()

    tampered_body = b'payload={"action":"tampered"}'
    headers = {
        "X-Slack-Request-Timestamp": str(int(now)),
        "X-Slack-Signature": computed_sig
    }

    verified, msg = SlackBlockKitAdapter.verify_slack_request(
        headers=headers,
        raw_body=tampered_body,
        signing_secret=secret,
        current_time=now
    )
    assert verified is False
    assert "INVALID_SIGNATURE" in msg


def test_05_slack_signature_replay_prevention():
    secret = "test_signing_secret_12345"
    old_time = time.time() - 350.0  # 350 seconds ago (> 300s limit)
    current_time = time.time()
    raw_body = b'payload={"type":"replayed_action"}'

    sig_basestring = f"v0:{int(old_time)}:".encode("utf-8") + raw_body
    computed_sig = "v0=" + hmac.new(secret.encode("utf-8"), sig_basestring, hashlib.sha256).hexdigest()

    headers = {
        "X-Slack-Request-Timestamp": str(int(old_time)),
        "X-Slack-Signature": computed_sig
    }

    verified, msg = SlackBlockKitAdapter.verify_slack_request(
        headers=headers,
        raw_body=raw_body,
        signing_secret=secret,
        current_time=current_time
    )
    assert verified is False
    assert "REPLAY_OR_EXPIRED" in msg


def test_06_slack_signature_missing_headers():
    secret = "test_signing_secret_12345"
    verified, msg = SlackBlockKitAdapter.verify_slack_request(
        headers={},
        raw_body=b"",
        signing_secret=secret
    )
    assert verified is False
    assert "MISSING_SLACK_HEADERS" in msg


# ------------------------------------------------------------------------------
# Test 4: Human Resolution Authority (Allowed vs Prohibited Decisions)
# ------------------------------------------------------------------------------
def test_07_human_resolution_authority_permitted_issuance():
    manager = HumanResolutionAuthorityManager()
    ticket = manager.issue_authority(
        operation_id="refund_8817_001",
        approver_principal="ciso_operator_alice",
        decision=DECISION_ESCALATE,
        validity_seconds=300.0,
        step_up_acr="urn:mace:incommon:iap:silver"
    )

    assert ticket.ticket_id.startswith("hra_")
    assert ticket.operation_id == "refund_8817_001"
    assert ticket.decision == DECISION_ESCALATE
    assert ticket.consumed is False
    assert ticket.signature_hex != ""
    assert ticket.step_up_context["acr_values"] == "urn:mace:incommon:iap:silver"

    # Verify signature using manager's public key
    assert ticket.verify(manager.public_key) is True


@pytest.mark.parametrize("prohibited_step", [
    PROHIBITED_DECLARE_SUCCESS,
    PROHIBITED_RETRY_BLINDLY,
    PROHIBITED_CHANGE_POLICY,
    PROHIBITED_GRANT_NEW_AUTHORITY
])
def test_08_human_resolution_authority_prohibited_steps_fail_closed(prohibited_step):
    manager = HumanResolutionAuthorityManager()
    with pytest.raises(ProhibitedDecisionError) as exc_info:
        manager.issue_authority(
            operation_id="refund_8817_001",
            approver_principal="operator_bob",
            decision=prohibited_step
        )
    assert "PROHIBITED_ACTION" in str(exc_info.value)


def test_09_human_resolution_authority_single_use_burn():
    manager = HumanResolutionAuthorityManager()
    ticket = manager.issue_authority(
        operation_id="refund_8817_001",
        approver_principal="operator_alice",
        decision=DECISION_REQUEST_ADDITIONAL_RECONCILIATION
    )

    # First consumption succeeds
    success, msg = manager.consume_authority(ticket)
    assert success is True
    assert ticket.consumed is True

    # Second consumption must fail closed
    with pytest.raises(TicketAlreadyBurnedError):
        manager.consume_authority(ticket)


def test_10_human_resolution_authority_expiration():
    manager = HumanResolutionAuthorityManager()
    now = time.time()
    ticket = manager.issue_authority(
        operation_id="refund_8817_001",
        approver_principal="operator_alice",
        decision=DECISION_ESCALATE,
        validity_seconds=10.0
    )

    # Attempt to consume after 15 seconds
    with pytest.raises(TicketExpiredError):
        manager.consume_authority(ticket, current_time=now + 15.0)


def test_11_human_resolution_authority_mark_failed_requires_evidence():
    manager = HumanResolutionAuthorityManager()
    ticket = manager.issue_authority(
        operation_id="refund_8817_001",
        approver_principal="operator_alice",
        decision=DECISION_MARK_TARGET_FAILED
    )

    # Without target-side evidence of failure -> raises ProhibitedDecisionError
    with pytest.raises(ProhibitedDecisionError) as exc_info:
        manager.consume_authority(ticket, target_evidence_supports_failure=False)
    assert "CANNOT_MARK_FAILED_WITHOUT_EVIDENCE" in str(exc_info.value)

    # With authenticated target evidence -> succeeds
    success, msg = manager.consume_authority(ticket, target_evidence_supports_failure=True)
    assert success is True
    assert msg == "AUTHORITY_CONSUMED_SUCCESSFULLY"


def test_12_human_resolution_authority_tampered_signature():
    manager = HumanResolutionAuthorityManager()
    ticket = manager.issue_authority(
        operation_id="refund_8817_001",
        approver_principal="operator_alice",
        decision=DECISION_ESCALATE
    )

    # Corrupt the signature by flipping the first hex char
    corrupted_sig = ("0" if ticket.signature_hex[0] != "0" else "1") + ticket.signature_hex[1:]
    ticket.signature_hex = corrupted_sig

    with pytest.raises(InvalidSignatureError):
        manager.consume_authority(ticket)


# ------------------------------------------------------------------------------
# Test 5: LLM Explainer Non-Authoritative Boundary
# ------------------------------------------------------------------------------
def test_13_llm_explainer_non_authoritative_boundary(sample_candidate_and_receipt):
    candidate, receipt = sample_candidate_and_receipt
    brief = ActionIntelligenceBriefGenerator.generate_brief(
        candidate=candidate,
        receipt=receipt,
        transport_outcome="HTTP_504_GATEWAY_TIMEOUT",
        http_status=504,
        target_reconciliation_status="INCONCLUSIVE",
        probes_executed=1
    )

    explanation = LLMExplainer.explain(brief)
    assert "text" in explanation
    assert "disclaimer" in explanation
    assert explanation["is_authoritative"] is False
    assert explanation["disclaimer"] == NON_AUTHORITATIVE_DISCLAIMER

    # Verify zero banned words
    for banned in BANNED_WORDS:
        assert banned not in explanation["text"].lower()

    # Verify receipt and brief state were not modified
    assert receipt.disposition == DISPOSITION_EFFECT_INDETERMINATE
    assert brief.priority == PRIORITY_P1
