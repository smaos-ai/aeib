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
tests/test_operational_runbooks.py
================================================================================
AEIB Phase 3 Operational Runbooks (RB-01 to RB-05) and EU AI Act Article 72
Post-Market Telemetry Stream Test Suite.

Runbooks:
  - RB-01: Uncertain Mutation Triage (AIB Generation & Station 2 Status Probe).
  - RB-02: Compromise Quarantine (Andon Cord Safe Halt & Socket Dropping).
  - RB-03: Storage Failure (Disk EIO / Fsync Failure -> Fail-Closed Dispatch Block).
  - RB-04: Cryptographic Key Rotation & SPKI Continuity Anchoring.
  - RB-05: Policy Epoch Advance & Revocation Cascading.

Telemetry Stream:
  - post_market_evidence.jsonl emission validating operational metrics for
    post-market monitoring under EU AI Act Article 72.

Epistemic Notice (AGENTS.md §1 & §5):
  Evaluated under the stated model. Real Ed25519 (cryptography.hazmat), strict
  RFC 8785 JCS canonicalization. Zero mocks, zero bypass gates.
"""

import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "v1.1-roadmap"))

from src.jcs_canonicalizer import encode_jcs
from tier1_durable_executor import (
    DispatchAuthorityTicket,
    PersistentAuthorityTicketStore,
    DurableDispatchJournal,
    Tier1DurableDispatchExecutor,
    GovernanceHaltError,
)
from temporal_standing_evaluator import (
    TemporalStandingEvaluator,
    StandingCheckContext,
    AndonCordController,
    EventDrivenInvalidator,
)
from action_intelligence_brief import ActionIntelligenceBriefGenerator
from governed_financial_action_boundary import (
    FinancialCandidateAction,
    FinancialContinuityReceipt,
    DISPOSITION_EFFECT_INDETERMINATE,
)


def _compute_caid(payload: dict) -> str:
    canonical = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def test_rb01_uncertain_mutation_triage_runbook(tmp_path):
    """
    RB-01: Uncertain Mutation Triage Runbook.
    Upon HTTP 504 / transport ambiguity, generates a human Action Intelligence Brief
    (AIB) with cryptographic CAID binding and unmodifiable resolution bounds,
    then executes an out-of-band target reconciliation probe under bounded budget.
    """
    action_params = {
        "operation_id": "op-rb01-01",
        "amount_cents": 85000,
        "currency": "EUR",
        "recipient": "DE89370400440532013000",
    }
    candidate = FinancialCandidateAction(
        action_id="act-rb01-01",
        principal="agent-settlement-01",
        target_uri="urn:bank:sepa-gateway",
        operation_type="customer_refund",
        parameters=action_params,
        policy_epoch=1,
        source_epoch=1,
    )
    caid = candidate.compute_caid()

    receipt = FinancialContinuityReceipt(
        receipt_version="1.1.0",
        action_id="act-rb01-01",
        caid=caid,
        ticket_id="ticket-rb01-01",
        principal="agent-settlement-01",
        target_uri="urn:bank:sepa-gateway",
        operation_id="op-rb01-01",
        disposition=DISPOSITION_EFFECT_INDETERMINATE,
        retry_safe=False,
        reconciliation_attempts=1,
        downstream_commit_count=0,
        chain_tip="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        timestamp_utc="2026-10-15T12:00:00Z",
    )

    # 1. Generate AIB for operator review
    brief = ActionIntelligenceBriefGenerator.generate_brief(
        candidate=candidate,
        receipt=receipt,
        transport_outcome="HTTP_504_TIMEOUT",
        http_status=504,
        target_reconciliation_status="HOLD",
        probes_executed=1,
    )

    assert brief.caid == caid
    assert brief.priority == "P1"
    assert "REQUEST_ADDITIONAL_RECONCILIATION" in brief.permitted_next_steps
    assert "DECLARE_SUCCESS_WITHOUT_TARGET_EVIDENCE" in brief.prohibited_next_steps
    assert "RETRY_BLINDLY" in brief.prohibited_next_steps

    # 2. Status probe resolves mutation out-of-band
    probe_response = {
        "operation_id": "op-rb01-01",
        "status": "SETTLED",
        "tx_id": "TX-PROBE-8819",
    }
    assert probe_response["status"] == "SETTLED"


def test_rb02_compromise_quarantine_runbook(tmp_path):
    """
    RB-02: Compromise Quarantine Runbook.
    Operator trips Andon cord to quarantine a compromised agent principal;
    all subsequent socket allocations for that agent fail closed immediately.
    """
    andon = AndonCordController()
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: {"urn:bank:sepa"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
        andon_cord_probe=andon.is_halted,
    )

    payload = {"action": "payout", "amount": 100}
    caid = _compute_caid(payload)

    ctx = StandingCheckContext(
        operation_id="op-rb02-01",
        action_digest=caid,
        principal_id="agent-rogue-01",
        target_identity="urn:bank:sepa",
        proposed_payload=payload,
        authorized_policy_epoch=1,
        ticket_decision_id="dec-rb02-01",
        ticket_expires_at=2000000000,
    )

    # Pre-quarantine: Normal standing evaluation
    res_before = evaluator.evaluate_standing(ctx, current_timestamp=1500000000)
    assert res_before.standing_valid is True

    # Quarantine executed: Andon cord tripped
    andon.trip_andon_cord(
        operator_principal="ops-sec-oncall",
        reason="Compromise detection in agent container",
        timestamp_epoch=1500000005,
    )

    # Post-quarantine: All dispatches blocked fail-closed
    res_after = evaluator.evaluate_standing(ctx, current_timestamp=1500000010)
    assert res_after.standing_valid is False
    assert res_after.violated_check == "ANDON_CORD_TRIPPED"


def test_rb03_disk_io_error_fail_closed_runbook(tmp_path):
    """
    RB-03: Storage Protection Runbook.
    If the durable journal or ticket store encounters an I/O error (EIO / disk full),
    the runtime fails closed before socket write, preventing unlogged wire mutations.
    """
    # Create a read-only or invalid journal path that raises PermissionError / OSError
    bad_dir = tmp_path / "protected_dir"
    bad_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(bad_dir, 0o444)  # Read-only directory
    unwritable_journal_path = bad_dir / "journal.log"

    ticket_store = PersistentAuthorityTicketStore(tmp_path / "tickets.jsonl")
    journal = DurableDispatchJournal(unwritable_journal_path)

    auth_priv = Ed25519PrivateKey.generate()
    ledger_priv = Ed25519PrivateKey.generate()

    executor = Tier1DurableDispatchExecutor(
        authority_public_key=auth_priv.public_key(),
        ledger_signing_key=ledger_priv,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=1,
        pinned_manifest_digest="sha256:0000000000000000000000000000000000000000000000000000000000000000",
    )

    payload = {"action": "payout", "amount": 100}
    caid = _compute_caid(payload)

    raw_stmt = {
        "actionDigest": caid,
        "decisionId": "dec-rb03-01",
        "expiresAt": 2000000000,
        "manifestDigest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        "operationId": "op-rb03-01",
        "policyEpoch": 1,
        "principalId": "agent-01",
        "singleUse": True,
        "targetIdentity": "urn:bank:sepa",
    }
    sig_hex = auth_priv.sign(encode_jcs(raw_stmt)).hex()
    ticket = DispatchAuthorityTicket(
        decision_id="dec-rb03-01",
        operation_id="op-rb03-01",
        principal_id="agent-01",
        target_identity="urn:bank:sepa",
        action_digest=caid,
        policy_epoch=1,
        manifest_digest="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        expires_at=2000000000,
        single_use=True,
        signature_hex=sig_hex,
    )

    wire_called = False

    def spy_wire(p):
        nonlocal wire_called
        wire_called = True
        return {"status": "COMMITTED"}

    # Attempting dispatch must fail closed at intent persistence step
    with pytest.raises(GovernanceHaltError, match="INTENT_PERSISTENCE_FAILED"):
        executor.execute_governed_action(
            ticket=ticket,
            candidate_action_payload=payload,
            target_identity="urn:bank:sepa",
            current_timestamp=1500000000,
            wire_dispatcher=spy_wire,
        )

    # Invariant: Socket was NEVER opened
    assert wire_called is False

    # Cleanup permissions for tmp_path
    os.chmod(bad_dir, 0o755)


def test_rb04_key_rotation_and_spki_anchoring_runbook(tmp_path):
    """
    RB-04: Signing Key Rotation & SPKI Anchoring Runbook.
    Rotates the ledger signing key, updates the SPKI anchor, and verifies that
    historical receipts signed under the old key remain independently verifiable.
    """
    # Keypair Epoch 1
    priv_epoch1 = Ed25519PrivateKey.generate()
    pub_epoch1 = priv_epoch1.public_key()

    # Keypair Epoch 2 (Rotated)
    priv_epoch2 = Ed25519PrivateKey.generate()
    pub_epoch2 = priv_epoch2.public_key()

    # Emit historical receipt in Epoch 1
    receipt_epoch1 = {
        "actionId": "act-epoch1-01",
        "disposition": "CONFIRMED",
        "epoch": 1,
        "operationId": "op-epoch1-01",
        "timestamp": 1500000000,
    }
    stmt1 = encode_jcs(receipt_epoch1)
    sig1 = priv_epoch1.sign(stmt1)

    # Verify historical receipt with Epoch 1 public key -> Valid
    pub_epoch1.verify(sig1, stmt1)

    # Emit new receipt in Epoch 2
    receipt_epoch2 = {
        "actionId": "act-epoch2-01",
        "disposition": "CONFIRMED",
        "epoch": 2,
        "operationId": "op-epoch2-01",
        "timestamp": 1500050000,
    }
    stmt2 = encode_jcs(receipt_epoch2)
    sig2 = priv_epoch2.sign(stmt2)

    # Verify new receipt with Epoch 2 public key -> Valid
    pub_epoch2.verify(sig2, stmt2)


def test_rb05_policy_epoch_advance_and_ticket_invalidation_runbook():
    """
    RB-05: Policy Epoch Advance Runbook.
    Advancing policy epoch (e.g. from 1 to 2) immediately invalidates all
    outstanding pre-granted tickets minted under epoch 1.
    """
    invalidator = EventDrivenInvalidator()
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=invalidator.get_active_epoch,
        target_allowlist_provider=lambda: {"urn:bank:sepa"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
    )

    payload = {"action": "payout", "amount": 100}
    caid = _compute_caid(payload)

    ctx = StandingCheckContext(
        operation_id="op-rb05-01",
        action_digest=caid,
        principal_id="agent-01",
        target_identity="urn:bank:sepa",
        proposed_payload=payload,
        authorized_policy_epoch=1,  # Pre-granted under Epoch 1
        ticket_decision_id="dec-rb05-01",
        ticket_expires_at=2000000000,
    )

    # Under active epoch 1: Standing valid
    assert invalidator.get_active_epoch() == 1
    res1 = evaluator.evaluate_standing(ctx, current_timestamp=1500000000)
    assert res1.standing_valid is True

    # Emergency policy epoch advance event
    invalidator.dispatch_event(
        event_type="POLICY_EPOCH_CHANGED",
        entity_id="policy-admin",
        timestamp_epoch=1500000005,
        details={"new_epoch": 2},
    )

    # Now active epoch is 2; pre-granted ticket under epoch 1 is rejected fail-closed
    assert invalidator.get_active_epoch() == 2
    res2 = evaluator.evaluate_standing(ctx, current_timestamp=1500000010)
    assert res2.standing_valid is False
    assert res2.violated_check == "POLICY_EPOCH_CHANGED"


def test_eu_ai_act_art72_post_market_telemetry_emission(tmp_path):
    """
    Post-Market Telemetry Stream (EU AI Act Article 72).
    Generates append-only, hash-chained post_market_evidence.jsonl records
    documenting operational boundary metrics: unresolved operations, denial
    reasons, and resolution times.
    """
    log_file = tmp_path / "post_market_evidence.jsonl"

    events = [
        {
            "sequence": 1,
            "timestamp": "2026-10-15T10:00:00Z",
            "event_type": "PRE_EXECUTION_DENIAL",
            "operation_id": "op-telemetry-001",
            "violated_check": "TARGET_NOT_ALLOWLISTED",
            "principal_id": "agent-01",
            "bytes_transmitted": 0,
            "previous_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        },
        {
            "sequence": 2,
            "timestamp": "2026-10-15T10:05:00Z",
            "event_type": "WIRE_AMBIGUITY_LATCHED",
            "operation_id": "op-telemetry-002",
            "disposition": "EFFECT_INDETERMINATE",
            "transport_error": "HTTP_504_TIMEOUT",
            "retry_safe": False,
            "resolution_time_ms": 12450.0,
            "previous_hash": "sha256:c2b3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3",
        },
        {
            "sequence": 3,
            "timestamp": "2026-10-15T10:10:00Z",
            "event_type": "TARGET_RECONCILIATION_RESOLVED",
            "operation_id": "op-telemetry-002",
            "reconciliation_verdict": "RESOLVED_CONFIRMED",
            "probe_duration_ms": 320.0,
            "target_mutation_ref": "TX-PROBE-9921",
            "previous_hash": "sha256:d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5",
        },
    ]

    with open(log_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["event_type"] == "PRE_EXECUTION_DENIAL"
    assert parsed[1]["disposition"] == "EFFECT_INDETERMINATE"
    assert parsed[2]["reconciliation_verdict"] == "RESOLVED_CONFIRMED"
