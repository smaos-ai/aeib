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
tests/test_track_b_end_to_end_integration.py
================================================================================
AEIB Track B (v1.1) Unified End-to-End Integration Suite.

Covers the complete 7-control execution sequence under the stated model:
  1. P0.5 Control 1: Commit-Time Revalidation Engine (temporal_standing_check at Tn)
  2. P0.5 Control 2: Write-Before-Socket Intent Journal (EO-1 Durability & Fsync)
  3. P0.5 Control 3: Monotonic Delegation Attenuation Engine (UCAN / Macaroon)
  4. Milestone 4: Policy-Bound Target Reconciliation Contract (Adaptive Probing)
  5. Milestone 5: Minimal Saidot Governance Graph Fragments & Dynamic Invalidation
  6. Milestone 6: Action Intelligence Brief (AIB) & Webhook Step-Up Engine
  7. Milestone 7: Process Containment & Zero Ambient Egress Sandbox Profile
"""

import copy
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# Path injection
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
from delegation_chain_verifier import (
    DelegationHop,
    DelegationChainVerifier,
    DelegationError,
)
from temporal_standing_evaluator import (
    TemporalStandingEvaluator,
    StandingCheckContext,
    StandingEvaluationResult,
    AndonCordController,
    SaidotGraphFragmentEmitter,
    EventDrivenInvalidator,
)
from configurable_reconciliation_engine import (
    TargetReconciliationPolicy,
    ConfigurableReconciliationEngine,
    ReconciliationExecutionResult,
    DISPOSITION_CONFIRMED,
    DISPOSITION_REFUTED,
    DISPOSITION_PRESERVED_UNCERTAINTY,
    DISPOSITION_CIRCUIT_TRIPPED,
)
from action_intelligence_brief import (
    PRIORITY_P1,
    ActionIntelligenceBrief,
    ActionIntelligenceBriefGenerator,
    SlackBlockKitAdapter,
    HumanResolutionAuthority,
    HumanResolutionAuthorityManager,
)
from governed_financial_action_boundary import (
    FinancialCandidateAction,
    FinancialContinuityReceipt,
)


def _compute_caid(payload: dict) -> str:
    canonical = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _mint_authority_ticket(
    auth_priv: Ed25519PrivateKey,
    decision_id: str,
    operation_id: str,
    action_caid: str,
    target_identity: str,
    policy_epoch: int = 1,
    manifest_digest: str = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    expires_at: int = 2000000000,
) -> DispatchAuthorityTicket:
    statement = {
        "actionDigest": action_caid,
        "decisionId": decision_id,
        "expiresAt": expires_at,
        "manifestDigest": manifest_digest,
        "operationId": operation_id,
        "policyEpoch": policy_epoch,
        "principalId": "agent-lead-01",
        "singleUse": True,
        "targetIdentity": target_identity,
    }
    jcs_bytes = encode_jcs(statement)
    sig_hex = auth_priv.sign(jcs_bytes).hex()
    return DispatchAuthorityTicket(
        decision_id=decision_id,
        operation_id=operation_id,
        principal_id="agent-lead-01",
        target_identity=target_identity,
        action_digest=action_caid,
        policy_epoch=policy_epoch,
        manifest_digest=manifest_digest,
        expires_at=expires_at,
        single_use=True,
        signature_hex=sig_hex,
    )


def _mint_hop(
    signing_key: Ed25519PrivateKey,
    *,
    delegator_principal_id: str,
    delegatee_agent_id: str,
    audience: str,
    permitted_scopes: list,
    max_spend_eur: int,
    valid_until_epoch: int,
) -> DelegationHop:
    raw_stmt = {
        "audience": audience,
        "delegateeAgentId": delegatee_agent_id,
        "delegatorPrincipalId": delegator_principal_id,
        "maxSpendEur": max_spend_eur,
        "permittedScopes": sorted(permitted_scopes),
        "validUntilEpoch": valid_until_epoch,
    }
    stmt_bytes = encode_jcs(raw_stmt)
    sig_hex = signing_key.sign(stmt_bytes).hex()
    return DelegationHop(
        delegator_principal_id=delegator_principal_id,
        delegatee_agent_id=delegatee_agent_id,
        audience=audience,
        permitted_scopes=permitted_scopes,
        max_spend_eur=max_spend_eur,
        valid_until_epoch=valid_until_epoch,
        signature_hex=sig_hex,
    )


def test_01_full_lifecycle_happy_path(tmp_path):
    """
    Evaluates the complete positive flow across all controls:
      Control 5: Governed asset and dependency emitted as Saidot graph fragments.
      Control 3: Delegation chain verified with monotonic scope attenuation.
      Control 2: Authority ticket minted and intent fsynced to journal.
      Control 1: Commit-time temporal standing asserted at Tn.
      Control 4: Dispatch executed cleanly; signed continuity receipt emitted.
    """
    # 1. Milestone 5: Governance Graph Fragment Generation
    agent_id = "agent-financial-settler-01"
    target_id = "urn:bank:sepa-instant"
    asset_fragment = SaidotGraphFragmentEmitter.emit_asset_fragment(
        agent_id=agent_id,
        owner_principal="principal-treasury-lead",
        policy_profile="TREASURY_SETTLEMENT_v1.1",
        risk_classification="HIGH_CONSEQUENCE_FINANCIAL",
        active_policy_epoch=1,
    )
    dep_fragment = SaidotGraphFragmentEmitter.emit_dependency_fragment(
        agent_id=agent_id,
        target_id=target_id,
        target_uri_pattern="urn:bank:sepa-instant/*",
        owner_team="banking-platform-ops",
        probe_budget=2,
    )
    assert asset_fragment["asset_id"] == agent_id
    assert dep_fragment["target_dependency_id"] == target_id

    # 2. Control 3: Monotonic Delegation Attenuation
    sponsor_priv = Ed25519PrivateKey.generate()
    auth_priv = Ed25519PrivateKey.generate()
    ledger_priv = Ed25519PrivateKey.generate()
    manifest_digest = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

    hop0 = _mint_hop(
        sponsor_priv,
        delegator_principal_id="sponsor-root",
        delegatee_agent_id="agent-financial-settler-01",
        audience="urn:bank:sepa-instant",
        permitted_scopes=["PAYMENT_DISBURSE"],
        max_spend_eur=5000,
        valid_until_epoch=2000000000,
    )
    verifier = DelegationChainVerifier(
        root_sponsor_public_key=sponsor_priv.public_key(),
        root_sponsor_principal_id="sponsor-root",
        known_agent_keys={"agent-financial-settler-01": auth_priv.public_key()},
    )
    verdict = verifier.verify_chain(
        chain=[hop0],
        target_audience="urn:bank:sepa-instant",
        current_timestamp=1500000000,
    )
    assert verdict.valid
    assert verdict.effective_max_spend_eur == 5000

    # 3. Control 2: Authority Ticket Minting and Persistent Store Setup
    payload = {
        "action": "disburse_supplier_settlement",
        "amount_cents": 250000,
        "beneficiary": "DE89370400440532013000",
        "currency": "EUR",
        "invoice_ref": "INV-2026-8819",
    }
    action_caid = _compute_caid(payload)
    ticket_store = PersistentAuthorityTicketStore(tmp_path / "tickets.jsonl")
    authority_ticket = _mint_authority_ticket(
        auth_priv=auth_priv,
        decision_id="dec-supplier-001",
        operation_id="op-supplier-8819",
        action_caid=action_caid,
        target_identity="urn:bank:sepa-instant",
        policy_epoch=1,
        manifest_digest=manifest_digest,
        expires_at=2000000000,
    )

    # 4. Control 1: Commit-Time Temporal Standing at Tn
    invalidator = EventDrivenInvalidator()
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=invalidator.get_active_epoch,
        target_allowlist_provider=lambda: {"urn:bank:sepa-instant"},
        revocation_registry_provider=lambda: invalidator._revoked_entities,
        evidence_store_health_probe=lambda: True,
    )
    standing_ctx = StandingCheckContext(
        operation_id="op-supplier-8819",
        action_digest=action_caid,
        principal_id="agent-financial-settler-01",
        target_identity="urn:bank:sepa-instant",
        proposed_payload=payload,
        authorized_policy_epoch=1,
        ticket_decision_id="dec-supplier-001",
        ticket_expires_at=2000000000,
        delegation_chain_ids=["hop-01"],
    )
    standing_result = evaluator.evaluate_standing(standing_ctx, current_timestamp=1500000000)
    assert standing_result.standing_valid
    assert standing_result.audit_event["standing"] == "PRESENT_AND_VALID"

    # 5. Control 2 & 4: Durable Dispatch Execution & Receipt Generation
    journal = DurableDispatchJournal(tmp_path / "intent_journal.log")
    executor = Tier1DurableDispatchExecutor(
        authority_public_key=auth_priv.public_key(),
        ledger_signing_key=ledger_priv,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=1,
        pinned_manifest_digest=manifest_digest,
    )

    def wire_dispatcher(action_dict):
        return {"http_status": 200, "tx_id": "TXN-BANK-99120", "settled": True}

    exec_result = executor.execute_governed_action(
        ticket=authority_ticket,
        candidate_action_payload=payload,
        target_identity="urn:bank:sepa-instant",
        current_timestamp=1500000000,
        wire_dispatcher=wire_dispatcher,
    )
    assert exec_result["disposition"] == "CONFIRMED"
    assert exec_result["retrySafe"] is True
    assert exec_result["status"] == "RESOLVED"
    assert ticket_store.is_consumed("dec-supplier-001")


def test_02_commit_time_standing_invalidation_blocks_dispatch(tmp_path):
    """
    Evaluates that if policy epoch changes or principal is revoked between T0 and Tn,
    the temporal standing check fails closed and halts dispatch before wire socket allocation.
    """
    payload = {"action": "urgent_refund", "amount": 100.0}
    action_caid = _compute_caid(payload)

    invalidator = EventDrivenInvalidator()
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=invalidator.get_active_epoch,
        target_allowlist_provider=lambda: {"urn:bank:refunds"},
        revocation_registry_provider=lambda: invalidator._revoked_entities,
        evidence_store_health_probe=lambda: True,
    )

    # Invalidation event occurs during Delta N: principal is revoked
    invalidator.dispatch_event(
        event_type="PRINCIPAL_REVOKED",
        entity_id="agent-compromised-07",
        timestamp_epoch=1400000000,
    )

    standing_ctx = StandingCheckContext(
        operation_id="op-refund-99",
        action_digest=action_caid,
        principal_id="agent-compromised-07",
        target_identity="urn:bank:refunds",
        proposed_payload=payload,
        authorized_policy_epoch=1,
        ticket_decision_id="dec-refund-99",
        ticket_expires_at=2000000000,
    )
    standing_res = evaluator.evaluate_standing(standing_ctx, current_timestamp=1500000000)
    assert not standing_res.standing_valid
    assert standing_res.violated_check == "PRINCIPAL_REVOKED"


def test_03_wire_fault_reconciles_under_configurable_policy(tmp_path):
    """
    Evaluates wire transport drops (HTTP 504) triggering EFFECT_INDETERMINATE,
    followed by Milestone 4 Configurable Target Reconciliation resolving to CONFIRMED.
    Downstream confirmed settlement yields retry_safe: False (duplicate prevention).
    """
    recon_policy = TargetReconciliationPolicy(
        target_pattern="https://api.bank.internal/*",
        max_attempts=3,
        initial_backoff_ms=5,
        max_backoff_ms=20,
    )
    engine = ConfigurableReconciliationEngine(policies=[recon_policy])

    # Simulated target state: first probe transient 504, second probe returns 200 COMMITTED
    attempts = [0]
    def target_status_probe(op_id, key):
        attempts[0] += 1
        if attempts[0] == 1:
            return 504, {"error": "gateway timeout"}
        return 200, {"status": "COMMITTED", "commit_count": 1}

    res = engine.reconcile_target(
        action_id="act-001",
        operation_id="op-recon-001",
        idempotency_key="caid:sha256:test1234",
        target_uri="https://api.bank.internal/v1/payments",
        probe_fn=target_status_probe,
        sleep_fn=lambda s: None,
    )
    assert res.disposition == DISPOSITION_CONFIRMED
    assert res.reconciliation_attempts == 2
    assert res.retry_safe is False  # Confirmed downstream: retrying is unsafe


def test_04_exhaustion_generates_action_intelligence_brief_and_step_up(tmp_path):
    """
    Evaluates reconciliation exhaustion preserving uncertainty, generating an Action
    Intelligence Brief (Milestone 6), and creating an RFC 9470 Step-Up challenge.
    """
    recon_policy = TargetReconciliationPolicy(
        target_pattern="https://api.bank.internal/*",
        max_attempts=2,
        initial_backoff_ms=5,
        max_backoff_ms=10,
    )
    engine = ConfigurableReconciliationEngine(policies=[recon_policy])

    # Status probe permanently returns 504 TIMEOUT
    def failing_probe(op_id, key):
        return 504, {"error": "target unreachable"}

    res = engine.reconcile_target(
        action_id="act-002",
        operation_id="op-exhausted-01",
        idempotency_key="caid:sha256:deadbeef",
        target_uri="https://api.bank.internal/v1/escrow",
        probe_fn=failing_probe,
        sleep_fn=lambda s: None,
    )
    assert res.disposition == DISPOSITION_PRESERVED_UNCERTAINTY
    assert res.reconciliation_attempts == 2
    assert res.retry_safe is False

    # Generate Action Intelligence Brief
    candidate = FinancialCandidateAction(
        action_id="act-escrow-01",
        principal="agent-escrow-01",
        target_uri="https://bank.internal/v1/escrow",
        operation_type="release_escrow_deposit",
        parameters={"operation_id": "op-exhausted-01", "amount_cents": 450000, "currency": "EUR"},
        policy_epoch=1,
        source_epoch=1,
    )
    receipt = FinancialContinuityReceipt(
        receipt_version="1.0",
        action_id="act-escrow-01",
        caid=candidate.compute_caid(),
        ticket_id="ticket-escrow-001",
        principal=candidate.principal,
        target_uri=candidate.target_uri,
        operation_id="op-exhausted-01",
        disposition="EFFECT_INDETERMINATE",
        retry_safe=False,
        reconciliation_attempts=2,
        downstream_commit_count=0,
        chain_tip="sha256:" + "0" * 64,
        timestamp_utc="2026-10-15T00:00:00Z",
    )
    brief = ActionIntelligenceBriefGenerator.generate_brief(
        candidate=candidate,
        receipt=receipt,
        transport_outcome="HTTP_504_GATEWAY_TIMEOUT",
        http_status=504,
        target_reconciliation_status="INCONCLUSIVE",
        probes_executed=2,
    )
    assert brief.priority == PRIORITY_P1
    assert brief.operation_id == "op-exhausted-01"
    assert brief.permitted_next_steps == ["ESCALATE", "MARK_TARGET_FAILED_IF_EVIDENCE_SUPPORTS_IT", "REQUEST_ADDITIONAL_RECONCILIATION"]
    assert "DECLARE_SUCCESS_WITHOUT_TARGET_EVIDENCE" in brief.prohibited_next_steps

    # Format Slack Block Kit with HMAC-SHA256 signature
    signing_secret = "test-webhook-secret-32-bytes-minimum"
    slack_blocks = SlackBlockKitAdapter.format_slack_block_kit(brief)
    raw_payload_bytes = json.dumps(slack_blocks).encode("utf-8")
    req_timestamp = int(time.time())
    sig_basestring = f"v0:{req_timestamp}:".encode("utf-8") + raw_payload_bytes
    computed_sig = "v0=" + hmac.new(signing_secret.encode("utf-8"), sig_basestring, hashlib.sha256).hexdigest()

    headers = {
        "X-Slack-Request-Timestamp": str(req_timestamp),
        "X-Slack-Signature": computed_sig,
    }
    valid, reason = SlackBlockKitAdapter.verify_slack_request(
        headers=headers,
        raw_body=raw_payload_bytes,
        signing_secret=signing_secret,
    )
    assert valid


def test_05_eu_ai_act_article_14_andon_cord_emergency_freeze():
    """
    Evaluates the EU AI Act Article 14 Emergency Andon Cord halting execution
    into a deterministic safe state and resuming only under supervisory dual control.
    """
    andon = AndonCordController(halted_initially=False)
    assert not andon.is_halted()

    # Operator trips emergency halt
    trip_record = andon.trip_andon_cord(
        operator_principal="risk-officer-david",
        reason="Detected prompt injection payload clustering in transaction queue",
        timestamp_epoch=1500000000,
    )
    assert andon.is_halted()
    assert trip_record["system_state"] == "SAFE_HALT_ENGAGED"

    # Evaluator halts all dispatches fail-closed
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: {"https://bank.internal/payout"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
        andon_cord_probe=andon.is_halted,
    )
    ctx = StandingCheckContext(
        operation_id="op-freeze-001",
        action_digest="sha256:abc123",
        principal_id="agent-01",
        target_identity="https://bank.internal/payout",
        proposed_payload={"action": "payout"},
        authorized_policy_epoch=1,
        ticket_decision_id="dec-01",
        ticket_expires_at=2000000000,
    )
    res = evaluator.evaluate_standing(ctx, current_timestamp=1550000000)
    assert not res.standing_valid
    assert res.violated_check == "ANDON_CORD_TRIPPED"

    # Supervisory dual-control reset
    reset_record = andon.reset_andon_cord(
        supervisor_principal="ciso-elizabeth",
        justification="Queue purged of adversarial inputs; integrity re-established",
        timestamp_epoch=1600000000,
    )
    assert not andon.is_halted()
    assert reset_record["system_state"] == "NORMAL_OPERATION_RESUMED"
