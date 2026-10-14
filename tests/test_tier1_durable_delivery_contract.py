"""
tests/test_tier1_durable_delivery_contract.py
Tests verifying the 9 required capabilities of the Tier 1 Core Delivery Contract.

1. Intent persistence fails → no governed dispatch
2. Crash after intent persistence, before dispatch → conservative recovery
3. Crash during dispatch → no inference that target did nothing
4. Crash after target completion, before outcome persistence → reconcile
5. Restart → consumed authority remains consumed
6. Concurrent ticket use → exactly one authorized governed dispatch
7. Action, target, policy, or manifest changed → reject
8. Ambiguous transport outcome → EFFECT_INDETERMINATE
9. Reconciliation exhausted → preserve uncertainty and escalate
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import importlib.util
from pathlib import Path
import sys
import threading
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.jcs_canonicalizer import encode_jcs

REPO_ROOT = Path(__file__).resolve().parents[1]
TIER1_PATH = REPO_ROOT / "v1.1-roadmap" / "tier1_durable_executor.py"
spec = importlib.util.spec_from_file_location("tier1_durable_executor", TIER1_PATH)
assert spec is not None and spec.loader is not None
t1 = importlib.util.module_from_spec(spec)
sys.modules["tier1_durable_executor"] = t1
spec.loader.exec_module(t1)

DispatchAuthorityTicket = t1.DispatchAuthorityTicket
DurableDispatchJournal = t1.DurableDispatchJournal
GovernanceHaltError = t1.GovernanceHaltError
PersistentAuthorityTicketStore = t1.PersistentAuthorityTicketStore
Tier1DurableDispatchExecutor = t1.Tier1DurableDispatchExecutor


def _mint_valid_ticket(
    authority_key: Ed25519PrivateKey,
    *,
    decision_id: str,
    operation_id: str,
    principal_id: str,
    target_identity: str,
    payload: Dict[str, Any],
    policy_epoch: int = 10,
    manifest_digest: str = "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    expires_at: int = 2000000000,
) -> DispatchAuthorityTicket:
    caid = f"sha256:{hashlib.sha256(encode_jcs(payload)).hexdigest()}"
    raw_stmt = {
        "actionDigest": caid,
        "decisionId": decision_id,
        "expiresAt": expires_at,
        "manifestDigest": manifest_digest,
        "operationId": operation_id,
        "policyEpoch": policy_epoch,
        "principalId": principal_id,
        "singleUse": True,
        "targetIdentity": target_identity,
    }
    stmt_bytes = encode_jcs(raw_stmt)
    sig_hex = authority_key.sign(stmt_bytes).hex()

    return DispatchAuthorityTicket(
        decision_id=decision_id,
        operation_id=operation_id,
        principal_id=principal_id,
        target_identity=target_identity,
        action_digest=caid,
        policy_epoch=policy_epoch,
        manifest_digest=manifest_digest,
        expires_at=expires_at,
        single_use=True,
        signature_hex=sig_hex,
    )


def test_01_intent_persistence_fails_no_governed_dispatch(tmp_path: Path) -> None:
    """1. Intent persistence fails -> no governed dispatch."""
    auth_key = Ed25519PrivateKey.generate()
    ledger_key = Ed25519PrivateKey.generate()

    ticket_store = PersistentAuthorityTicketStore(tmp_path / "tickets.jsonl")
    # Point journal to an invalid path that cannot be written (simulating disk I/O failure)
    bad_journal_path = tmp_path / "readonly_dir" / "journal.jsonl"
    journal = DurableDispatchJournal(bad_journal_path)

    executor = Tier1DurableDispatchExecutor(
        authority_public_key=auth_key.public_key(),
        ledger_signing_key=ledger_key,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=10,
        pinned_manifest_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
    )

    action_payload = {"account": "ACC_1", "amount": 100}
    ticket = _mint_valid_ticket(
        auth_key,
        decision_id="dec_01",
        operation_id="op_01",
        principal_id="agent_1",
        target_identity="https://api.bank.internal/transfer",
        payload=action_payload,
    )

    # Make parent directory read-only to force write failure
    bad_journal_path.parent.mkdir(parents=True, exist_ok=True)
    bad_journal_path.parent.chmod(0o444)

    wire_dispatched = False

    def dummy_wire(payload: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal wire_dispatched
        wire_dispatched = True
        return {"http_status": 200}

    try:
        with pytest.raises(GovernanceHaltError, match="INTENT_PERSISTENCE_FAILED"):
            executor.execute_governed_action(
                ticket=ticket,
                candidate_action_payload=action_payload,
                target_identity="https://api.bank.internal/transfer",
                current_timestamp=1000,
                wire_dispatcher=dummy_wire,
            )
    finally:
        bad_journal_path.parent.chmod(0o755)

    assert wire_dispatched is False
    assert ticket_store.is_consumed("dec_01") is False


def test_02_crash_after_intent_persistence_before_dispatch_conservative_recovery(tmp_path: Path) -> None:
    """2. Crash after intent persistence, before dispatch -> conservative recovery."""
    journal_path = tmp_path / "journal.jsonl"
    journal = DurableDispatchJournal(journal_path)

    # Simulate: Intent was persisted to disk with fsync
    journal.persist_intent(
        operation_id="op_crash_pre",
        decision_id="dec_crash_pre",
        action_caid="sha256:dummy",
        target_identity="https://api.bank.internal/transfer",
        timestamp_epoch=1000,
    )

    # Process crashes before dispatch is initiated. Recovery scanner runs on restart:
    recovery_state = journal.scan_recovery_state("op_crash_pre")
    assert recovery_state == "ABORTED_PRE_DISPATCH"


def test_03_crash_during_dispatch_no_inference_target_did_nothing(tmp_path: Path) -> None:
    """3. Crash during dispatch -> no inference that target did nothing."""
    journal_path = tmp_path / "journal.jsonl"
    journal = DurableDispatchJournal(journal_path)

    journal.persist_intent(
        operation_id="op_crash_mid",
        decision_id="dec_crash_mid",
        action_caid="sha256:dummy",
        target_identity="https://api.bank.internal/transfer",
        timestamp_epoch=1000,
    )
    journal.mark_dispatch_started("op_crash_mid", timestamp_epoch=1001)

    # Process crashes while socket write is in-flight. Recovery scanner runs:
    recovery_state = journal.scan_recovery_state("op_crash_mid")
    assert recovery_state == "REQUIRES_RECONCILIATION"


def test_04_crash_after_target_completion_before_outcome_persistence_reconcile(tmp_path: Path) -> None:
    """4. Crash after target completion, before outcome persistence -> reconcile."""
    journal_path = tmp_path / "journal.jsonl"
    journal = DurableDispatchJournal(journal_path)

    journal.persist_intent(
        operation_id="op_crash_post",
        decision_id="dec_crash_post",
        action_caid="sha256:caid_123",
        target_identity="https://api.bank.internal/transfer",
        timestamp_epoch=1000,
    )
    journal.mark_dispatch_started("op_crash_post", timestamp_epoch=1001)

    # Recovery detects uncertain state and invokes bounded reconciliation probe
    assert journal.scan_recovery_state("op_crash_post") == "REQUIRES_RECONCILIATION"

    # Out-of-band authoritative reconciliation probe against target confirms state
    def probe_target(op_id: str, caid: str) -> str:
        assert op_id == "op_crash_post"
        return "CONFIRMED"

    reconciled_disposition = probe_target("op_crash_post", "sha256:caid_123")
    journal.persist_resolution(
        operation_id="op_crash_post",
        disposition=reconciled_disposition,
        retry_safe=True,
        evidence_digest="sha256:authoritative_probe_confirmed",
        timestamp_epoch=1005,
    )

    assert journal.scan_recovery_state("op_crash_post") == "RESOLVED"


def test_05_restart_consumed_authority_remains_consumed(tmp_path: Path) -> None:
    """5. Restart -> consumed authority remains consumed."""
    store_path = tmp_path / "tickets.jsonl"
    store1 = PersistentAuthorityTicketStore(store_path)

    # Consume authority in process 1
    assert store1.consume_authority("dec_persist_01", "op_1", 1000) is True
    assert store1.is_consumed("dec_persist_01") is True

    # Simulate process termination and restart (new instance loading from disk)
    store2 = PersistentAuthorityTicketStore(store_path)
    assert store2.is_consumed("dec_persist_01") is True
    assert store2.consume_authority("dec_persist_01", "op_2", 2000) is False


def test_06_concurrent_ticket_use_exactly_one_authorized_governed_dispatch(tmp_path: Path) -> None:
    """6. Concurrent ticket use -> exactly one authorized governed dispatch."""
    auth_key = Ed25519PrivateKey.generate()
    ledger_key = Ed25519PrivateKey.generate()

    ticket_store = PersistentAuthorityTicketStore(tmp_path / "tickets.jsonl")
    journal = DurableDispatchJournal(tmp_path / "journal.jsonl")

    executor = Tier1DurableDispatchExecutor(
        authority_public_key=auth_key.public_key(),
        ledger_signing_key=ledger_key,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=10,
        pinned_manifest_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
    )

    action_payload = {"account": "ACC_CONCURRENT", "amount": 500}
    ticket = _mint_valid_ticket(
        auth_key,
        decision_id="dec_race_condition",
        operation_id="op_race",
        principal_id="agent_concurrent",
        target_identity="https://api.bank.internal/transfer",
        payload=action_payload,
    )

    dispatch_counter = 0
    lock = threading.Lock()

    def counting_wire(p: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal dispatch_counter
        with lock:
            dispatch_counter += 1
        return {"http_status": 200}

    results = []
    errors = []

    def worker(worker_id: int):
        try:
            res = executor.execute_governed_action(
                ticket=ticket,
                candidate_action_payload=action_payload,
                target_identity="https://api.bank.internal/transfer",
                current_timestamp=1000 + worker_id,
                wire_dispatcher=counting_wire,
            )
            results.append(res)
        except GovernanceHaltError as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly 1 thread succeeds in governed dispatch; 19 threads rejected fail-closed
    assert len(results) == 1
    assert len(errors) == 19
    assert dispatch_counter == 1
    assert results[0]["disposition"] == "CONFIRMED"


def test_07_action_target_policy_or_manifest_changed_reject(tmp_path: Path) -> None:
    """7. Action, target, policy, or manifest changed -> reject."""
    auth_key = Ed25519PrivateKey.generate()
    ledger_key = Ed25519PrivateKey.generate()

    ticket_store = PersistentAuthorityTicketStore(tmp_path / "tickets.jsonl")
    journal = DurableDispatchJournal(tmp_path / "journal.jsonl")

    executor = Tier1DurableDispatchExecutor(
        authority_public_key=auth_key.public_key(),
        ledger_signing_key=ledger_key,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=10,
        pinned_manifest_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
    )

    action_payload = {"account": "ACC_VALID", "amount": 100}
    ticket = _mint_valid_ticket(
        auth_key,
        decision_id="dec_mod_test",
        operation_id="op_mod_test",
        principal_id="agent_1",
        target_identity="https://api.bank.internal/transfer",
        payload=action_payload,
    )

    dummy_wire = lambda p: {"http_status": 200}

    # Case A: Action payload tampered
    with pytest.raises(GovernanceHaltError, match="ACTION_DIGEST_MISMATCH"):
        executor.execute_governed_action(
            ticket=ticket,
            candidate_action_payload={"account": "ACC_VALID", "amount": 999999},  # Tampered!
            target_identity="https://api.bank.internal/transfer",
            current_timestamp=1000,
            wire_dispatcher=dummy_wire,
        )

    # Case B: Target identity changed
    with pytest.raises(GovernanceHaltError, match="TARGET_MISMATCH"):
        executor.execute_governed_action(
            ticket=ticket,
            candidate_action_payload=action_payload,
            target_identity="https://attacker.com/steal",  # Substituted!
            current_timestamp=1000,
            wire_dispatcher=dummy_wire,
        )

    # Case C: Policy epoch stale
    stale_executor = Tier1DurableDispatchExecutor(
        authority_public_key=auth_key.public_key(),
        ledger_signing_key=ledger_key,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=11,  # Epoch advanced to 11
        pinned_manifest_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
    )
    with pytest.raises(GovernanceHaltError, match="POLICY_EPOCH_STALE"):
        stale_executor.execute_governed_action(
            ticket=ticket,
            candidate_action_payload=action_payload,
            target_identity="https://api.bank.internal/transfer",
            current_timestamp=1000,
            wire_dispatcher=dummy_wire,
        )

    # Case D: Manifest drift
    drift_executor = Tier1DurableDispatchExecutor(
        authority_public_key=auth_key.public_key(),
        ledger_signing_key=ledger_key,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=10,
        pinned_manifest_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",  # Drifted!
    )
    with pytest.raises(GovernanceHaltError, match="MANIFEST_DRIFT"):
        drift_executor.execute_governed_action(
            ticket=ticket,
            candidate_action_payload=action_payload,
            target_identity="https://api.bank.internal/transfer",
            current_timestamp=1000,
            wire_dispatcher=dummy_wire,
        )


def test_08_ambiguous_transport_outcome_effect_indeterminate(tmp_path: Path) -> None:
    """8. Ambiguous transport outcome -> EFFECT_INDETERMINATE."""
    auth_key = Ed25519PrivateKey.generate()
    ledger_key = Ed25519PrivateKey.generate()

    ticket_store = PersistentAuthorityTicketStore(tmp_path / "tickets.jsonl")
    journal = DurableDispatchJournal(tmp_path / "journal.jsonl")

    executor = Tier1DurableDispatchExecutor(
        authority_public_key=auth_key.public_key(),
        ledger_signing_key=ledger_key,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=10,
        pinned_manifest_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        probe_reconciler=None,  # No probe reconciler configured
    )

    action_payload = {"account": "ACC_504", "amount": 100}
    ticket = _mint_valid_ticket(
        auth_key,
        decision_id="dec_504",
        operation_id="op_504",
        principal_id="agent_1",
        target_identity="https://api.bank.internal/transfer",
        payload=action_payload,
    )

    # Wire dispatcher encounters HTTP 504 Gateway Timeout
    timeout_wire = lambda p: {"http_status": 504, "error": "Gateway Timeout"}

    res = executor.execute_governed_action(
        ticket=ticket,
        candidate_action_payload=action_payload,
        target_identity="https://api.bank.internal/transfer",
        current_timestamp=1000,
        wire_dispatcher=timeout_wire,
    )

    assert res["disposition"] == "EFFECT_INDETERMINATE"
    assert res["retrySafe"] is False
    assert res["receipt"]["disposition"] == "EFFECT_INDETERMINATE"


def test_09_reconciliation_exhausted_preserve_uncertainty_and_escalate(tmp_path: Path) -> None:
    """9. Reconciliation exhausted -> preserve uncertainty and escalate."""
    auth_key = Ed25519PrivateKey.generate()
    ledger_key = Ed25519PrivateKey.generate()

    ticket_store = PersistentAuthorityTicketStore(tmp_path / "tickets.jsonl")
    journal = DurableDispatchJournal(tmp_path / "journal.jsonl")

    # Reconciliation probe raises TimeoutError (probe budget exhausted / target unreachable)
    def exhausted_probe(op_id: str, caid: str) -> str:
        raise TimeoutError("Probe budget exhausted: upstream target unreachable")

    executor = Tier1DurableDispatchExecutor(
        authority_public_key=auth_key.public_key(),
        ledger_signing_key=ledger_key,
        ticket_store=ticket_store,
        journal=journal,
        active_policy_epoch=10,
        pinned_manifest_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        probe_reconciler=exhausted_probe,
    )

    action_payload = {"account": "ACC_EXHAUST", "amount": 250}
    ticket = _mint_valid_ticket(
        auth_key,
        decision_id="dec_exhaust",
        operation_id="op_exhaust",
        principal_id="agent_1",
        target_identity="https://api.bank.internal/transfer",
        payload=action_payload,
    )

    def tcp_reset_wire(p: Dict[str, Any]) -> Dict[str, Any]:
        raise ConnectionResetError("Connection reset by peer (TCP RST)")

    res = executor.execute_governed_action(
        ticket=ticket,
        candidate_action_payload=action_payload,
        target_identity="https://api.bank.internal/transfer",
        current_timestamp=1000,
        wire_dispatcher=tcp_reset_wire,
    )

    # Uncertainty is strictly preserved; automated retries remain locked (retry_safe: false)
    assert res["disposition"] == "EFFECT_INDETERMINATE"
    assert res["retrySafe"] is False
    assert res["receipt"]["disposition"] == "EFFECT_INDETERMINATE"
    assert res["receipt"]["retrySafe"] is False
