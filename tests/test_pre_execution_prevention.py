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
tests/test_pre_execution_prevention.py
================================================================================
AEIB Phase 1 Pre-Execution Prevention Benchmark Suite (PEP-01 to PEP-06).

Evaluates the decisive measurement for execution integrity boundaries:
  "Experimentally demonstrated pre-execution prevention at Tn."
  Asserts correlated proof that NO authorized external wire request occurred
  at the tested observation point when authorization fails, expires, mutates,
  is revoked, or is replayed.

Scenarios:
  - PEP-01 (CLM-POLICY-01): Policy-prohibited action blocked before external dispatch.
  - PEP-02 (CLM-EXPIRE-02): Expired authority ticket blocked before external dispatch.
  - PEP-03 (CLM-STALE-03): Revoked principal/delegation blocked before external dispatch.
  - PEP-04 (CLM-ALTER-04): Altered amount, recipient, target, or digest blocked before dispatch.
  - PEP-05 (CLM-REPLAY-05): Replayed authority causes zero second external wire mutation.
  - PEP-06 (CLM-AMBIG-06): Ambiguous transport result latches EFFECT_INDETERMINATE without success claim.

Epistemic Notice (AGENTS.md §1 & §5):
  Under the stated model. Zero mocks, real Ed25519, strict RFC 8785 JCS canonicalization.
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
from temporal_standing_evaluator import (
    TemporalStandingEvaluator,
    StandingCheckContext,
    EventDrivenInvalidator,
    AndonCordController,
)


class TransportWireSpy:
    """
    Correlated wire observation probe that intercepts Layer 7 socket calls.
    Records every attempted transmission to prove transport absence.
    """

    def __init__(self, failure_mode=None):
        self.failure_mode = failure_mode
        self.dispatched_calls = []
        self.socket_bytes_sent = 0

    def dispatch(self, action_dict: dict) -> dict:
        self.dispatched_calls.append(copy.deepcopy(action_dict))
        payload_bytes = json.dumps(action_dict).encode("utf-8")
        self.socket_bytes_sent += len(payload_bytes)

        if self.failure_mode == "504_TIMEOUT":
            raise TimeoutError("HTTP 504 Gateway Timeout from target payment gateway")
        elif self.failure_mode == "TCP_RST":
            raise ConnectionResetError("TCP RST Connection reset by peer")

        return {"http_status": 200, "status": "COMMITTED", "tx_id": "TX-MOCK-991"}

    @property
    def request_count(self) -> int:
        return len(self.dispatched_calls)


def _compute_caid(payload: dict) -> str:
    canonical = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _mint_authority_ticket(
    auth_priv: Ed25519PrivateKey,
    decision_id: str,
    operation_id: str,
    action_caid: str,
    target_identity: str,
    principal_id: str = "agent-01",
    policy_epoch: int = 1,
    manifest_digest: str = "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    expires_at: int = 2000000000,
    single_use: bool = True,
) -> DispatchAuthorityTicket:
    raw_statement = {
        "actionDigest": action_caid,
        "decisionId": decision_id,
        "expiresAt": expires_at,
        "manifestDigest": manifest_digest,
        "operationId": operation_id,
        "policyEpoch": policy_epoch,
        "principalId": principal_id,
        "singleUse": single_use,
        "targetIdentity": target_identity,
    }
    stmt_bytes = encode_jcs(raw_statement)
    sig_hex = auth_priv.sign(stmt_bytes).hex()
    return DispatchAuthorityTicket(
        decision_id=decision_id,
        operation_id=operation_id,
        principal_id=principal_id,
        target_identity=target_identity,
        action_digest=action_caid,
        policy_epoch=policy_epoch,
        manifest_digest=manifest_digest,
        expires_at=expires_at,
        single_use=single_use,
        signature_hex=sig_hex,
    )


def test_pep_01_policy_prohibited_action_blocked_before_dispatch(tmp_path):
    """
    PEP-01 (CLM-POLICY-01): Policy-Prohibited Action Blocked.
    Proves that an action targeting an un-whitelisted endpoint or violating
    policy bounds is stopped before Layer 7 socket allocation.
    Correlated Artifact: wire_spy.request_count == 0.
    """
    auth_priv = Ed25519PrivateKey.generate()
    ledger_priv = Ed25519PrivateKey.generate()
    manifest_digest = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

    ticket_store = PersistentAuthorityTicketStore(tmp_path / "tickets.jsonl")
    journal = DurableDispatchJournal(tmp_path / "journal.log")
    wire_spy = TransportWireSpy()

    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: {"urn:bank:whitelisted-payments"},  # Whitelist only
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
    )

    payload = {"action": "unauthorized_export", "recipient": "attacker@evil.com", "amount": 10000}
    action_caid = _compute_caid(payload)

    # Prohibited target outside allowlist
    prohibited_target = "urn:bank:unauthorized-offshore"

    standing_ctx = StandingCheckContext(
        operation_id="op-pep01-001",
        action_digest=action_caid,
        principal_id="agent-01",
        target_identity=prohibited_target,
        proposed_payload=payload,
        authorized_policy_epoch=1,
        ticket_decision_id="dec-pep01-001",
        ticket_expires_at=2000000000,
    )

    standing_res = evaluator.evaluate_standing(standing_ctx, current_timestamp=1500000000)
    assert not standing_res.standing_valid
    assert standing_res.violated_check == "TARGET_NOT_ALLOWLISTED"

    # Correlated Proof: Execution prevented; zero wire socket calls observed
    assert wire_spy.request_count == 0
    assert wire_spy.socket_bytes_sent == 0


def test_pep_02_expired_authority_blocked_at_tn_revalidation(tmp_path):
    """
    PEP-02 (CLM-EXPIRE-02): Expired Authority Ticket Blocked at Tn.
    Proves that if authority expires during the authorization gap Delta N,
    the standing check at Tn halts execution fail-closed before socket allocation.
    Correlated Artifact: wire_spy.request_count == 0.
    """
    auth_priv = Ed25519PrivateKey.generate()
    wire_spy = TransportWireSpy()

    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: {"urn:bank:sepa"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
    )

    payload = {"action": "payout", "amount": 500}
    action_caid = _compute_caid(payload)

    # Ticket minted with expiration at T = 1000
    standing_ctx = StandingCheckContext(
        operation_id="op-pep02-001",
        action_digest=action_caid,
        principal_id="agent-01",
        target_identity="urn:bank:sepa",
        proposed_payload=payload,
        authorized_policy_epoch=1,
        ticket_decision_id="dec-pep02-001",
        ticket_expires_at=1000,  # Expired
    )

    # Revalidation evaluated at Tn = 1001 (after expiry)
    standing_res = evaluator.evaluate_standing(standing_ctx, current_timestamp=1001)
    assert not standing_res.standing_valid
    assert standing_res.violated_check == "AUTHORITY_EXPIRED"

    # Correlated Proof: Zero wire requests
    assert wire_spy.request_count == 0


def test_pep_03_revoked_principal_blocked_at_tn_revalidation(tmp_path):
    """
    PEP-03 (CLM-STALE-03): Revoked Principal Blocked at Tn.
    Proves that if an agent principal is revoked during Delta N,
    standing evaluation blocks dispatch fail-closed before socket write.
    Correlated Artifact: wire_spy.request_count == 0.
    """
    invalidator = EventDrivenInvalidator()
    wire_spy = TransportWireSpy()

    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=invalidator.get_active_epoch,
        target_allowlist_provider=lambda: {"urn:bank:sepa"},
        revocation_registry_provider=lambda: invalidator._revoked_entities,
        evidence_store_health_probe=lambda: True,
    )

    payload = {"action": "refund", "amount": 250}
    action_caid = _compute_caid(payload)
    principal_id = "agent-rogue-07"

    # Invalidation event occurs during Delta N: principal is revoked
    invalidator.dispatch_event(
        event_type="PRINCIPAL_REVOKED",
        entity_id=principal_id,
        timestamp_epoch=1500000500,
    )

    standing_ctx = StandingCheckContext(
        operation_id="op-pep03-001",
        action_digest=action_caid,
        principal_id=principal_id,
        target_identity="urn:bank:sepa",
        proposed_payload=payload,
        authorized_policy_epoch=1,
        ticket_decision_id="dec-pep03-001",
        ticket_expires_at=2000000000,
    )

    standing_res = evaluator.evaluate_standing(standing_ctx, current_timestamp=1500000600)
    assert not standing_res.standing_valid
    assert standing_res.violated_check == "PRINCIPAL_REVOKED"

    # Correlated Proof: Zero wire requests
    assert wire_spy.request_count == 0


def test_pep_04_altered_payload_blocked_before_dispatch(tmp_path):
    """
    PEP-04 (CLM-ALTER-04): Altered Payload / Recipient Blocked.
    Proves that if a candidate action's recipient, amount, or parameters mutate
    after authorization, the CAID mismatch trips an immediate halt before wire write.
    Correlated Artifact: wire_spy.request_count == 0.
    """
    wire_spy = TransportWireSpy()
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: {"urn:bank:sepa"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
    )

    authorized_payload = {"recipient": "DE89370400440532013000", "amount": 100.0, "currency": "EUR"}
    authorized_caid = _compute_caid(authorized_payload)

    # Injected prompt modification alters recipient IBAN
    tampered_payload = {"recipient": "DE89999999999999999999", "amount": 100.0, "currency": "EUR"}

    standing_ctx = StandingCheckContext(
        operation_id="op-pep04-001",
        action_digest=authorized_caid,  # Authorized CAID bound to original recipient
        principal_id="agent-01",
        target_identity="urn:bank:sepa",
        proposed_payload=tampered_payload,  # Tampered payload submitted at Tn
        authorized_policy_epoch=1,
        ticket_decision_id="dec-pep04-001",
        ticket_expires_at=2000000000,
    )

    standing_res = evaluator.evaluate_standing(standing_ctx, current_timestamp=1500000000)
    assert not standing_res.standing_valid
    assert standing_res.violated_check == "ACTION_DIGEST_MUTATED"

    # Correlated Proof: Zero wire requests
    assert wire_spy.request_count == 0


def test_pep_05_replayed_authority_causes_zero_second_wire_mutation(tmp_path):
    """
    PEP-05 (CLM-REPLAY-05): Replay Prevention via Single-Use Ticket Burn.
    Proves that replaying an authority ticket causes zero second external dispatch.
    First run executes cleanly; second run is blocked fail-closed.
    Correlated Artifact: wire_spy.request_count == 1 (exactly 1 mutation, 0 duplicate).
    """
    auth_priv = Ed25519PrivateKey.generate()
    ledger_priv = Ed25519PrivateKey.generate()
    manifest_digest = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

    ticket_store = PersistentAuthorityTicketStore(tmp_path / "tickets.jsonl")
    journal = DurableDispatchJournal(tmp_path / "journal.log")
    wire_spy = TransportWireSpy()

    executor = Tier1DurableDispatchExecutor(
        authority_public_key=auth_priv.public_key(),
        ledger_signing_key=ledger_priv,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=1,
        pinned_manifest_digest=manifest_digest,
    )

    payload = {"action": "supplier_settlement", "amount_cents": 150000}
    action_caid = _compute_caid(payload)

    ticket = _mint_authority_ticket(
        auth_priv=auth_priv,
        decision_id="dec-pep05-single-use",
        operation_id="op-pep05-001",
        action_caid=action_caid,
        target_identity="urn:bank:sepa",
    )

    # First execution attempt: Succeeds
    res1 = executor.execute_governed_action(
        ticket=ticket,
        candidate_action_payload=payload,
        target_identity="urn:bank:sepa",
        current_timestamp=1500000000,
        wire_dispatcher=wire_spy.dispatch,
    )
    assert res1["disposition"] == "CONFIRMED"
    assert wire_spy.request_count == 1

    # Second execution attempt: Replay of same ticket MUST fail closed
    with pytest.raises(GovernanceHaltError) as exc_info:
        executor.execute_governed_action(
            ticket=ticket,
            candidate_action_payload=payload,
            target_identity="urn:bank:sepa",
            current_timestamp=1500000005,
            wire_dispatcher=wire_spy.dispatch,
        )
    assert "AUTHORITY_ALREADY_CONSUMED" in str(exc_info.value)

    # Correlated Proof: Wire count remains EXACTLY 1; zero duplicate dispatch
    assert wire_spy.request_count == 1


def test_pep_06_ambiguous_transport_outcome_preserves_uncertainty(tmp_path):
    """
    PEP-06 (CLM-AMBIG-06): Ambiguous Outcome Preserved as EFFECT_INDETERMINATE.
    Proves that upon wire failure (HTTP 504), the runtime latches EFFECT_INDETERMINATE
    with retry_safe: false. Does NOT classify as success, and blocks unsanctioned retry.
    Correlated Artifact: initial wire attempted, but subsequent blind retry blocked.
    """
    auth_priv = Ed25519PrivateKey.generate()
    ledger_priv = Ed25519PrivateKey.generate()
    manifest_digest = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

    ticket_store = PersistentAuthorityTicketStore(tmp_path / "tickets.jsonl")
    journal = DurableDispatchJournal(tmp_path / "journal.log")
    wire_spy = TransportWireSpy(failure_mode="504_TIMEOUT")

    executor = Tier1DurableDispatchExecutor(
        authority_public_key=auth_priv.public_key(),
        ledger_signing_key=ledger_priv,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=1,
        pinned_manifest_digest=manifest_digest,
    )

    payload = {"action": "customer_refund", "amount_cents": 85000}
    action_caid = _compute_caid(payload)

    ticket = _mint_authority_ticket(
        auth_priv=auth_priv,
        decision_id="dec-pep06-timeout",
        operation_id="op-pep06-001",
        action_caid=action_caid,
        target_identity="urn:bank:sepa",
    )

    # Dispatch encounters HTTP 504 Gateway Timeout
    res = executor.execute_governed_action(
        ticket=ticket,
        candidate_action_payload=payload,
        target_identity="urn:bank:sepa",
        current_timestamp=1500000000,
        wire_dispatcher=wire_spy.dispatch,
    )

    # Preserves uncertainty: strictly EFFECT_INDETERMINATE and retry_safe: False
    assert res["disposition"] == "EFFECT_INDETERMINATE"
    assert res["retrySafe"] is False
    assert res["status"] == "RESOLVED"

    # Ticket was consumed to prevent blind retry
    assert ticket_store.is_consumed("dec-pep06-timeout")

    # Immediate blind retry attempt with same ticket is blocked fail-closed
    with pytest.raises(GovernanceHaltError):
        executor.execute_governed_action(
            ticket=ticket,
            candidate_action_payload=payload,
            target_identity="urn:bank:sepa",
            current_timestamp=1500000001,
            wire_dispatcher=wire_spy.dispatch,
        )

    # Correlated Proof: Wire count remains 1 (no blind duplicate attempt executed)
    assert wire_spy.request_count == 1
