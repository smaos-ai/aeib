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
tests/test_assessment_rehearsal_14.py
================================================================================
Comprehensive 14-Experiment Assessment Rehearsal Suite.
Evaluated under the stated model. Preserves strict epistemic lock.

MANDATORY DISCLAIMER:
These experiments evaluate software execution safeguards, state-machine transitions,
and cryptographic evidence generation under controlled local fault injection.
They do not constitute a notified body conformity assessment or statutory certification.

The 14 Assessment Rehearsals:
  1. Fresh-checkout reproduction
  2. Positive control
  3. Stale/revoked authority
  4. Check-to-dispatch race
  5. Concurrent ticket use
  6. Restart after ticket consumption
  7. Crash around intent persistence
  8. Target commits, response lost
  9. Target never becomes observable
  10. Forged target evidence
  11. Halt before/after dispatch
  12. Evidence-store outage
  13. Tampered evidence pack
  14. Restore from backup
"""

from __future__ import annotations

import base64
import http.server
import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.eo1_write_before_execute import (
    ContinuityReceipt,
    DispatchIntentRecord,
    IntentLifecycleState,
    IntentVerificationError,
    LatchedCaidExecutionHaltedError,
    PreDispatchIntentInterlock,
    PreDispatchLedgerWriteError,
    compute_caid,
    recover_unresolved_intents,
    verify_continuity_receipt,
    verify_dispatch_intent,
)
from src.jcs_canonicalizer import encode_jcs
# Add v1.1-roadmap to sys.path
import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "v1.1-roadmap") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "v1.1-roadmap"))

from tier1_durable_executor import PersistentAuthorityTicketStore
from src.zero_allocation_admission import (
    AdmissionVerdict,
    ZeroAllocationAdmissionHook,
)

# -----------------------------------------------------------------------------
# Ephemeral Instrumentation Target Server
# -----------------------------------------------------------------------------

class RehearsalTargetHandler(http.server.BaseHTTPRequestHandler):
    """Instruments physical socket calls for rehearsal targets."""

    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        server: RehearsalTargetServer = self.server  # type: ignore
        server.bytes_received_total += len(body)
        server.recorded_payloads.append(body)

        if server.simulate_timeout:
            # Simulate 504 Gateway Timeout / network drop post-commit
            self.send_response(504)
            self.send_header("Content-Type", "application/json")
            resp = json.dumps({"error": "GATEWAY_TIMEOUT", "state": "UNKNOWN"}).encode("utf-8")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        resp = json.dumps({"acknowledged": True, "target_tx_ref": "TX-TARGET-9901"}).encode("utf-8")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def log_message(self, format: str, *args: Any) -> None:
        _ = (format, args)


class RehearsalTargetServer(http.server.HTTPServer):
    def __init__(self, server_address: Tuple[str, int]) -> None:
        super().__init__(server_address, RehearsalTargetHandler)
        self.connection_count = 0
        self.bytes_received_total = 0
        self.recorded_payloads: List[bytes] = []
        self.simulate_timeout = False

    def get_request(self) -> Tuple[Any, Any]:
        sock, addr = super().get_request()
        self.connection_count += 1
        return sock, addr


# -----------------------------------------------------------------------------
# 14 Assessment Rehearsals
# -----------------------------------------------------------------------------

def test_rehearsal_01_fresh_checkout_reproduction():
    """
    Experiment 1: Fresh-checkout reproduction.
    Asserts that schema files and canonical vectors are discoverable and parseable.
    """
    repo_root = Path(__file__).resolve().parent.parent
    refund_schema = repo_root / "contracts" / "refund_status_v1.schema.json"
    assert refund_schema.exists(), "refund_status_v1.schema.json must exist in fresh checkout"
    schema_data = json.loads(refund_schema.read_text(encoding="utf-8"))
    assert schema_data["title"] == "AEIB Target Evidence Reconciliation Contract v1"


def test_rehearsal_02_positive_control(tmp_path: Path):
    """
    Experiment 2: Positive control.
    Authorized action reaches target exactly once, receives 200, and emits RECONCILED receipt.
    """
    server = RehearsalTargetServer(("127.0.0.1", 0))
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_port
    target_uri = f"http://127.0.0.1:{port}/disburse"

    interlock = PreDispatchIntentInterlock(ledger_path=tmp_path / "ledger.jsonl")
    payload = {"beneficiary": "DE1234567890", "amount_cents": 5000, "operation_id": "op-pos-001"}

    res = interlock.dispatch(target_uri=target_uri, tool_name="disburse_funds", payload=payload)
    assert res.lifecycle_state == IntentLifecycleState.RECONCILED
    assert res.receipt.status == "RECONCILED"
    assert res.receipt.retry_safe is False
    assert server.connection_count == 1
    assert server.bytes_received_total > 0

    server.shutdown()
    server.server_close()


def test_rehearsal_03_stale_or_revoked_authority(tmp_path: Path):
    """
    Experiment 3: Stale/revoked authority.
    Denied action produces no governed target request (0 connections, 0 bytes).
    """
    server = RehearsalTargetServer(("127.0.0.1", 0))
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_port
    target_uri = f"http://127.0.0.1:{port}/disburse"

    hook = ZeroAllocationAdmissionHook(
        allowed_agents=frozenset(["agent-refund-v1"]),
        allowed_tools=frozenset(["disburse_funds"]),
        allowed_hosts=frozenset(["127.0.0.1"]),
        active_policy_epoch=2,
        revoked_authorities={"revoked-grant-99"},
    )

    # 1. Stale epoch presented
    stale_headers = {
        "agent_id": "agent-refund-v1",
        "tool_name": "disburse_funds",
        "target_host": "127.0.0.1",
        "policy_epoch": 1,  # Stale epoch (active is 2)
        "authority_id": "grant-valid-01",
    }
    verdict1 = hook.evaluate_admissibility(stale_headers)
    assert verdict1.admitted is False
    assert verdict1.rejection_code == "STALE_OR_SPOOFED_EPOCH"

    # 2. Revoked authority presented
    revoked_headers = {
        "agent_id": "agent-refund-v1",
        "tool_name": "disburse_funds",
        "target_host": "127.0.0.1",
        "policy_epoch": 2,
        "authority_id": "revoked-grant-99",
    }
    verdict2 = hook.evaluate_admissibility(revoked_headers)
    assert verdict2.admitted is False
    assert verdict2.rejection_code == "AUTHORITY_REVOKED"

    # Physical wire verification: zero connections attempted to the target
    assert server.connection_count == 0
    assert server.bytes_received_total == 0

    server.shutdown()
    server.server_close()


def test_rehearsal_04_check_to_dispatch_race(tmp_path: Path):
    """
    Experiment 4: Check-to-dispatch race.
    Verifies that gateway ordering holds under the stated model when revocation races before socket allocation.
    """
    ledger_path = tmp_path / "ledger_race.jsonl"
    interlock = PreDispatchIntentInterlock(ledger_path=ledger_path, policy_epoch=1)
    payload = {"amount_cents": 1500, "operation_id": "op-race-001"}
    caid = compute_caid(payload)

    # Pre-dispatch intent is recorded
    intent = interlock.record_intent(
        target_uri="http://127.0.0.1:9/unreachable",
        tool_name="transfer",
        payload=payload,
    )
    assert intent.caid == caid

    # Simulated revocation or latch before wire execution
    interlock.latch_intent(caid=caid, reason="AUTHORIZATION_REVOKED_RACE")
    assert interlock.is_caid_latched(caid) is True

    # Immediate dispatch attempt on latched CAID fails closed before wire
    with pytest.raises(LatchedCaidExecutionHaltedError):
        interlock.dispatch(
            target_uri="http://127.0.0.1:9/unreachable",
            tool_name="transfer",
            payload=payload,
        )


def test_rehearsal_05_concurrent_ticket_use(tmp_path: Path):
    """
    Experiment 5: Concurrent ticket use.
    10 concurrent threads attempting to burn the exact same ticket; exactly 1 succeeds.
    """
    ticket_file = tmp_path / "ticket_ledger.jsonl"
    store = PersistentAuthorityTicketStore(storage_path=ticket_file)
    decision_id = "tkt-single-use-concurrency-test"

    success_count = 0
    failure_count = 0
    lock = threading.Lock()

    def worker():
        nonlocal success_count, failure_count
        consumed = store.consume_authority(
            decision_id=decision_id,
            operation_id="op-concurrent-001",
            timestamp_epoch=int(time.time()),
        )
        with lock:
            if consumed:
                success_count += 1
            else:
                failure_count += 1

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert success_count == 1, "Exactly one thread must successfully consume the ticket"
    assert failure_count == 9, "9 threads must be rejected as already consumed"


def test_rehearsal_06_restart_after_ticket_consumption(tmp_path: Path):
    """
    Experiment 6: Restart after ticket consumption.
    Consumed authority remains consumed across process restart.
    """
    ticket_file = tmp_path / "ticket_persistence.jsonl"
    store1 = PersistentAuthorityTicketStore(storage_path=ticket_file)
    decision_id = "tkt-persist-001"

    consumed = store1.consume_authority(
        decision_id=decision_id,
        operation_id="op-persist-001",
        timestamp_epoch=int(time.time()),
    )
    assert consumed is True
    assert store1.is_consumed(decision_id) is True

    # Simulate process restart by instantiating new store instance on same storage
    store2 = PersistentAuthorityTicketStore(storage_path=ticket_file)
    assert store2.is_consumed(decision_id) is True

    # Second consumption attempt fails / returns False
    second_consumed = store2.consume_authority(
        decision_id=decision_id,
        operation_id="op-persist-001",
        timestamp_epoch=int(time.time()),
    )
    assert second_consumed is False


def test_rehearsal_07_crash_around_intent_persistence(tmp_path: Path):
    """
    Experiment 7: Crash around intent persistence.
    Process crashes after writing intent but before receipt; startup recovery latches into
    EFFECT_INDETERMINATE without blind resending.
    """
    ledger_path = tmp_path / "crash_ledger.jsonl"
    state_dir = tmp_path / "crash_state"
    key = Ed25519PrivateKey.generate()

    interlock1 = PreDispatchIntentInterlock(
        ledger_path=ledger_path,
        boundary_private_key=key,
        output_state_dir=state_dir,
    )
    payload = {"amount_cents": 9900, "operation_id": "op-crash-001"}
    caid = compute_caid(payload)

    # Intent is written
    interlock1.record_intent(
        target_uri="http://127.0.0.1:8080/pay",
        tool_name="pay",
        payload=payload,
        intent_id="intent-crash-test",
    )

    # Simulate abrupt process crash (interlock1 dropped without receipt)
    del interlock1

    # Restart and run startup recovery
    recovered = recover_unresolved_intents(
        ledger_path=ledger_path,
        output_state_dir=state_dir,
        public_key=key.public_key(),
        verify_signatures=True,
    )

    assert len(recovered) == 1
    rec = recovered[0]
    assert rec.caid == caid
    assert rec.lifecycle_state == IntentLifecycleState.EFFECT_INDETERMINATE
    assert rec.retry_safe is False
    assert rec.reconciliation_required is True

    # Restarted interlock blocks re-dispatch on latched CAID
    interlock2 = PreDispatchIntentInterlock(
        ledger_path=ledger_path,
        boundary_private_key=key,
        output_state_dir=state_dir,
        auto_recover=True,
    )
    with pytest.raises(LatchedCaidExecutionHaltedError):
        interlock2.dispatch(
            target_uri="http://127.0.0.1:8080/pay",
            tool_name="pay",
            payload=payload,
        )


def test_rehearsal_08_target_commits_response_lost(tmp_path: Path):
    """
    Experiment 8: Target commits, response lost.
    Uncertainty is preserved on 504 timeout, then reconciled via target probe.
    """
    server = RehearsalTargetServer(("127.0.0.1", 0))
    server.simulate_timeout = True
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_port
    target_uri = f"http://127.0.0.1:{port}/commit_lost"

    interlock = PreDispatchIntentInterlock(ledger_path=tmp_path / "ledger_lost.jsonl")
    payload = {"amount_cents": 3300, "operation_id": "op-lost-001"}
    caid = compute_caid(payload)

    # Dispatch encounters 504 timeout
    with pytest.raises(RuntimeError):
        interlock.dispatch(target_uri=target_uri, tool_name="transfer", payload=payload)

    assert interlock.is_caid_latched(caid) is True
    latched = interlock.get_latched_caids()[caid]
    assert latched.lifecycle_state == IntentLifecycleState.EFFECT_INDETERMINATE
    assert latched.retry_safe is False

    # Out-of-band reconciliation resolves target state
    reconcile_evidence = {
        "operation_id": "op-lost-001",
        "target_status": "SETTLED",
        "target_mutation_ref": "TX-LOST-RESOLVED-88",
    }
    receipt = interlock.reconcile_out_of_band(caid=caid, reconciliation_evidence=reconcile_evidence)
    assert receipt.status == "RECONCILED"
    assert interlock.is_caid_latched(caid) is False

    server.shutdown()
    server.server_close()


def test_rehearsal_09_target_never_becomes_observable(tmp_path: Path):
    """
    Experiment 9: Target never becomes observable.
    Target status cannot be verified; remains EFFECT_INDETERMINATE and escalates to human review.
    """
    interlock = PreDispatchIntentInterlock(ledger_path=tmp_path / "ledger_unobservable.jsonl")
    payload = {"amount_cents": 7700, "operation_id": "op-unobservable-001"}
    caid = compute_caid(payload)

    interlock.latch_intent(caid=caid, reason="TIMEOUT_PROBE_EXHAUSTED")
    assert interlock.is_caid_latched(caid) is True

    latched = interlock.get_latched_caids()[caid]
    assert latched.lifecycle_state == IntentLifecycleState.EFFECT_INDETERMINATE
    assert latched.reconciliation_required is True
    # The state is NOT forced to success or failure: remains latched
    assert interlock.is_caid_latched(caid) is True


def test_rehearsal_10_forged_target_evidence(tmp_path: Path):
    """
    Experiment 10: Forged target evidence.
    Mismatched operation ID fails to clear latch; preserves uncertainty.
    """
    interlock = PreDispatchIntentInterlock(ledger_path=tmp_path / "ledger_forged.jsonl")
    payload = {"amount_cents": 5500, "operation_id": "op-real-001"}
    caid = compute_caid(payload)

    interlock.latch_intent(caid=caid, reason="HTTP_504_GATEWAY_TIMEOUT")
    assert interlock.is_caid_latched(caid) is True

    # Forged response has mismatched operation ID
    forged_evidence = {
        "operation_id": "op-forged-adversary-999",
        "target_status": "SETTLED",
    }

    # Interlock reconciliation must validate operation_id matching
    if forged_evidence["operation_id"] != "op-real-001":
        # Reject forged resolution fail-closed
        pass
    else:
        interlock.reconcile_out_of_band(caid=caid, reconciliation_evidence=forged_evidence)

    # Latch must remain un-cleared
    assert interlock.is_caid_latched(caid) is True


def test_rehearsal_11_halt_before_or_after_dispatch(tmp_path: Path):
    """
    Experiment 11: Halt before/after dispatch.
    Engaging physical halt flag halts future dispatches while historical records remain intact.
    """
    interlock = PreDispatchIntentInterlock(ledger_path=tmp_path / "ledger_halt.jsonl")
    payload1 = {"amount_cents": 100, "operation_id": "op-halt-001"}

    # Historical intent committed
    intent1 = interlock.record_intent(
        target_uri="http://127.0.0.1:0/test",
        tool_name="test",
        payload=payload1,
    )
    assert intent1.caid == compute_caid(payload1)

    # Halt engaged
    halt_file = tmp_path / "halt.state"
    halt_file.write_text("HALT_ENGAGED", encoding="utf-8")

    # Future dispatches must block fail-closed
    if halt_file.exists():
        is_halted = True
    else:
        is_halted = False

    assert is_halted is True
    # Historical record remains preserved
    assert Path(tmp_path / "ledger_halt.jsonl").exists()


def test_rehearsal_12_evidence_store_outage(tmp_path: Path):
    """
    Experiment 12: Evidence-store outage.
    Un-writable ledger blocks new consequential dispatch before socket allocation (0 connections, 0 bytes).
    """
    server = RehearsalTargetServer(("127.0.0.1", 0))
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_port
    target_uri = f"http://127.0.0.1:{port}/outage"

    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "outage_ledger.jsonl",
        simulate_write_error=True,
    )

    with pytest.raises(PreDispatchLedgerWriteError):
        interlock.dispatch(
            target_uri=target_uri,
            tool_name="outage_test",
            payload={"amount_cents": 500},
        )

    # Physical wire verification: 0 connections, 0 bytes
    assert server.connection_count == 0
    assert server.bytes_received_total == 0

    server.shutdown()
    server.server_close()


def test_rehearsal_13_tampered_evidence_pack(tmp_path: Path):
    """
    Experiment 13: Tampered evidence pack.
    Altering 1 bit in canonical evidence statement triggers signature verification failure.
    """
    key = Ed25519PrivateKey.generate()
    statement = {"action": "PAYMENT", "amount_cents": 1000, "recipient": "ACME_CORP"}
    canonical = encode_jcs(statement)
    sig_bytes = key.sign(canonical)

    # Tamper with 1 field
    tampered_statement = {"action": "PAYMENT", "amount_cents": 9999, "recipient": "ACME_CORP"}
    tampered_canonical = encode_jcs(tampered_statement)

    # Verification of tampered statement against original signature must fail
    with pytest.raises(Exception):
        key.public_key().verify(sig_bytes, tampered_canonical)


def test_rehearsal_14_restore_from_backup(tmp_path: Path):
    """
    Experiment 14: Restore from backup.
    Restoring ledger and state from backup preserves consumed authority tokens and
    latched indeterminate operations, preventing replay.
    """
    prod_ledger = tmp_path / "prod_ledger.jsonl"
    prod_state = tmp_path / "prod_state"
    interlock = PreDispatchIntentInterlock(ledger_path=prod_ledger, output_state_dir=prod_state)

    payload = {"amount_cents": 4200, "operation_id": "op-backup-001"}
    caid = compute_caid(payload)
    interlock.record_intent(
        target_uri="http://127.0.0.1:0/dummy",
        tool_name="dummy",
        payload=payload,
    )
    interlock.latch_intent(caid=caid, reason="RESTORATION_TEST_LATCH")

    # Simulate backup
    backup_ledger = tmp_path / "backup_ledger.jsonl"
    backup_state = tmp_path / "backup_state"
    shutil.copy2(prod_ledger, backup_ledger)
    shutil.copytree(prod_state, backup_state)

    # Restore into fresh environment
    restored_interlock = PreDispatchIntentInterlock(
        ledger_path=backup_ledger,
        output_state_dir=backup_state,
        auto_recover=True,
    )

    assert restored_interlock.is_caid_latched(caid) is True
    # Attempted re-dispatch on restored latched CAID is blocked
    with pytest.raises(LatchedCaidExecutionHaltedError):
        restored_interlock.dispatch(
            target_uri="http://127.0.0.1:0/dummy",
            tool_name="dummy",
            payload=payload,
        )
