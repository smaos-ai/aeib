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

r"""
tests/test_eo1_write_before_execute.py — Test Suite for EO-1 Evidence-Before-Effect Interlock
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB)

Evaluates PreDispatchIntentInterlock against the EO-1 specification:
1. Happy path: intent committed to ledger, outbound loopback dispatch succeeds, terminal receipt emitted.
2. Fail-closed ledger failure: simulated un-writable ledger aborts dispatch before socket connection (0 connections, 0 bytes).
3. Mid-syscall crash simulation: simulate process crash after intent write but before receipt;
   restart calls recover_unresolved_intents; asserts state is latched to EFFECT_INDETERMINATE and retry_safe is False.
4. Falsification: tampered intent signature or altered CAID in ledger fails verification.
"""

from __future__ import annotations

import http.server
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

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
    verify_ledger_file,
)


class LoopbackTrackingHandler(http.server.BaseHTTPRequestHandler):
    """Loopback test HTTP request handler tracking connection and payload metrics."""

    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        server: LoopbackTrackingServer = self.server  # type: ignore
        server.bytes_received_total += len(body)
        server.recorded_requests.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": body,
        })

        resp_payload = json.dumps({
            "acknowledged": True,
            "received_size": len(body),
        }).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp_payload)))
        self.end_headers()
        self.wfile.write(resp_payload)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress test output noise
        _ = (format, args)


class LoopbackTrackingServer(http.server.HTTPServer):
    """HTTP server that instruments connection counts and bytes received."""

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, LoopbackTrackingHandler)
        self.connection_count = 0
        self.bytes_received_total = 0
        self.recorded_requests: List[Dict[str, Any]] = []

    def get_request(self) -> tuple[Any, Any]:
        sock, addr = super().get_request()
        self.connection_count += 1
        return sock, addr


@pytest.fixture
def loopback_server():
    """Provides a running loopback tracking HTTP server bound to 127.0.0.1 on an ephemeral port."""
    srv = LoopbackTrackingServer(("127.0.0.1", 0))
    t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def test_happy_path_intent_committed_before_dispatch(tmp_path: Path, loopback_server: LoopbackTrackingServer):
    """
    Happy path test:
    - Intent is committed and signed to ledger before dispatch.
    - Outbound loopback dispatch succeeds (HTTP 200).
    - Terminal ContinuityReceipt is emitted with RECONCILED state.
    - Ledger contains DISPATCH_INTENT followed by CONTINUITY_RECEIPT.
    - Cryptographic verification passes for both records.
    """
    ledger_file = tmp_path / "ledger.jsonl"
    state_dir = tmp_path / "state"

    key = ed25519.Ed25519PrivateKey.generate()
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_file,
        boundary_private_key=key,
        output_state_dir=state_dir,
        authority_id="auth-test-authority",
        policy_epoch=10,
    )

    payload = {
        "switch_id": "SW-702",
        "command": "OPEN_CIRCUIT_BREAKER",
        "priority": "HIGH",
    }
    expected_caid = compute_caid(payload)
    target_uri = f"http://127.0.0.1:{loopback_server.server_port}/actuate"

    # Execute dispatch
    res = interlock.dispatch(
        target_uri=target_uri,
        tool_name="industrial_switch_actuate",
        payload=payload,
    )

    # Validate execution outcome
    assert res.lifecycle_state == IntentLifecycleState.RECONCILED
    assert res.caid == expected_caid
    assert res.receipt.status == "RECONCILED"
    assert res.receipt.caid == expected_caid
    assert res.receipt.policy_epoch == 10
    assert res.response["status_code"] == 200

    # Validate wire metrics
    assert loopback_server.connection_count == 1
    assert loopback_server.bytes_received_total > 0

    # Validate ledger contents
    assert ledger_file.exists()
    lines = [json.loads(line) for line in ledger_file.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) == 2

    intent_record = lines[0]
    receipt_record = lines[1]

    assert intent_record["record_type"] == "DISPATCH_INTENT"
    assert intent_record["caid"] == expected_caid
    assert intent_record["target_uri"] == target_uri
    assert intent_record["tool_name"] == "industrial_switch_actuate"
    assert intent_record["authority_id"] == "auth-test-authority"

    assert receipt_record["record_type"] == "CONTINUITY_RECEIPT"
    assert receipt_record["caid"] == expected_caid
    assert receipt_record["lifecycle_state"] == "RECONCILED"

    # Cryptographic verification
    pubkey = key.public_key()
    assert verify_dispatch_intent(intent_record, pubkey, expected_payload=payload) is True
    assert verify_continuity_receipt(receipt_record, pubkey) is True
    verified_all = verify_ledger_file(ledger_file, pubkey)
    assert len(verified_all) == 2


def test_fail_closed_unwritable_ledger_zero_wire_access(tmp_path: Path, loopback_server: LoopbackTrackingServer):
    """
    Fail-closed ledger failure test:
    - Ledger write fails (simulated unwritable ledger).
    - Dispatch is halted fail-closed, raising PreDispatchLedgerWriteError.
    - Wire access is verified to be zero (0 connections, 0 bytes transmitted).
    """
    ledger_file = tmp_path / "read_only_dir" / "ledger.jsonl"
    state_dir = tmp_path / "state"

    # Configure interlock with write failure simulation
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_file,
        output_state_dir=state_dir,
        simulate_write_error=True,
    )

    payload = {"actuator": "RELAY_9", "state": "CLOSE"}
    target_uri = f"http://127.0.0.1:{loopback_server.server_port}/actuate"

    with pytest.raises(PreDispatchLedgerWriteError) as exc_info:
        interlock.dispatch(
            target_uri=target_uri,
            tool_name="relay_actuate",
            payload=payload,
        )

    assert "Pre-dispatch ledger write failed" in str(exc_info.value)
    assert "halted fail-closed before wire access" in str(exc_info.value)

    # Strictly assert 0 connections and 0 bytes observed on loopback socket
    assert loopback_server.connection_count == 0
    assert loopback_server.bytes_received_total == 0
    assert len(loopback_server.recorded_requests) == 0


def test_fail_closed_os_permission_denied_zero_wire_access(tmp_path: Path, loopback_server: LoopbackTrackingServer):
    """
    Evaluates real OS filesystem permission errors:
    - Pre-existing read-only ledger file triggers permission error on append.
    - Interlock catches OS error and raises PreDispatchLedgerWriteError.
    - Zero wire connections or bytes observed.
    """
    ledger_file = tmp_path / "permission_denied_ledger.jsonl"
    ledger_file.write_text("{}", encoding="utf-8")
    os.chmod(ledger_file, 0o444)

    state_dir = tmp_path / "state"
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_file,
        output_state_dir=state_dir,
        auto_recover=False,
    )

    payload = {"valve_id": "V-50", "flow_rate": 12.4}
    target_uri = f"http://127.0.0.1:{loopback_server.server_port}/flow"

    try:
        with pytest.raises(PreDispatchLedgerWriteError):
            interlock.dispatch(
                target_uri=target_uri,
                tool_name="adjust_flow",
                payload=payload,
            )

        assert loopback_server.connection_count == 0
        assert loopback_server.bytes_received_total == 0
    finally:
        os.chmod(ledger_file, 0o644)


def test_mid_syscall_crash_simulation_and_recovery(tmp_path: Path, loopback_server: LoopbackTrackingServer):
    """
    Mid-syscall crash simulation:
    - Process records DISPATCH_INTENT to ledger.
    - Process terminates abruptly mid-syscall (SIGKILL simulation) before receipt is committed.
    - Startup recovery scans the ledger:
      * Unresolved intent is latched into EFFECT_INDETERMINATE with retry_safe: False.
      * Future execution on that CAID is halted (LatchedCaidExecutionHaltedError).
    - Out-of-band target reconciliation clears latch and emits terminal receipt.
    """
    ledger_file = tmp_path / "crash_ledger.jsonl"
    state_dir = tmp_path / "crash_state"

    key = ed25519.Ed25519PrivateKey.generate()
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_file,
        boundary_private_key=key,
        output_state_dir=state_dir,
        authority_id="auth-crash-authority",
        policy_epoch=4,
    )

    payload = {"transfer_id": "TXN-9872", "amount": 50000}
    caid = compute_caid(payload)
    target_uri = f"http://127.0.0.1:{loopback_server.server_port}/settle"

    # Step 1: Write intent prior to execution
    record = interlock.record_intent(
        target_uri=target_uri,
        tool_name="financial_settlement",
        payload=payload,
        intent_id="INTENT-SIMULATED-CRASH",
    )
    assert record.intent_id == "INTENT-SIMULATED-CRASH"
    assert record.caid == caid

    # Step 2: Mid-syscall crash occurs here. Process terminates without emitting receipt.
    # Verify ledger has only 1 line (DISPATCH_INTENT)
    raw_lines = ledger_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(raw_lines) == 1

    # Step 3: Startup recovery is invoked
    recovered = recover_unresolved_intents(
        ledger_path=ledger_file,
        output_state_dir=state_dir,
        public_key=key.public_key(),
        verify_signatures=True,
    )

    assert len(recovered) == 1
    rec = recovered[0]
    assert rec.intent_id == "INTENT-SIMULATED-CRASH"
    assert rec.caid == caid
    assert rec.lifecycle_state == IntentLifecycleState.EFFECT_INDETERMINATE
    assert rec.retry_safe is False
    assert rec.reconciliation_required is True

    # Confirm latch file on disk
    latch_file = state_dir / f"latched_{caid}.json"
    assert latch_file.exists()

    # Step 4: Restarted process initializes new interlock
    restarted_interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_file,
        boundary_private_key=key,
        output_state_dir=state_dir,
        auto_recover=True,
    )

    assert restarted_interlock.is_caid_latched(caid) is True

    # Attempting to re-dispatch on latched CAID is blocked fail-closed
    with pytest.raises(LatchedCaidExecutionHaltedError) as halt_info:
        restarted_interlock.dispatch(
            target_uri=target_uri,
            tool_name="financial_settlement",
            payload=payload,
        )

    assert "latched in EFFECT_INDETERMINATE" in str(halt_info.value)
    assert "retry_safe=False" in str(halt_info.value)
    # Loopback server must still have 0 requests from re-dispatch attempt
    assert loopback_server.connection_count == 0

    # Step 5: Perform out-of-band reconciliation
    reconciliation_proof = {
        "external_reconciliation_ref": "REF-EXT-5501",
        "cleared_by_operator": "ops_user_alpha",
        "state_evaluated": "SETTLED_CONFIRMED",
    }
    reconciled_receipt = restarted_interlock.reconcile_out_of_band(
        caid=caid,
        reconciliation_evidence=reconciliation_proof,
    )

    assert reconciled_receipt.status == "RECONCILED"
    assert reconciled_receipt.caid == caid
    assert restarted_interlock.is_caid_latched(caid) is False
    assert not latch_file.exists()

    # Verify ledger now contains the reconciliation receipt
    verified = verify_ledger_file(ledger_file, key.public_key())
    assert len(verified) == 2
    assert verified[1]["record_type"] == "CONTINUITY_RECEIPT"
    assert verified[1]["lifecycle_state"] == "RECONCILED"


def test_falsification_tampered_intent_signature(tmp_path: Path):
    """
    Falsification test:
    - Valid DISPATCH_INTENT has its boundary signature tampered.
    - Verification strictly detects the invalid signature and raises IntentVerificationError.
    """
    ledger_file = tmp_path / "tamper_sig_ledger.jsonl"
    key = ed25519.Ed25519PrivateKey.generate()
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_file,
        boundary_private_key=key,
        output_state_dir=tmp_path / "state",
    )

    payload = {"instruction": "SHUTDOWN_TURBINE"}
    record = interlock.record_intent(
        target_uri="http://127.0.0.1:8080/turbine",
        tool_name="turbine_ctrl",
        payload=payload,
    )

    record_dict = record.to_dict()
    # Signature passes initially
    assert verify_dispatch_intent(record_dict, key.public_key()) is True

    # Tamper with the signature bytes
    sig_chars = list(record_dict["boundary_signature_b64"])
    sig_chars[0] = "A" if sig_chars[0] != "A" else "B"
    record_dict["boundary_signature_b64"] = "".join(sig_chars)

    with pytest.raises(IntentVerificationError) as exc_info:
        verify_dispatch_intent(record_dict, key.public_key())

    assert "Ed25519 intent signature verification failed" in str(exc_info.value)


def test_falsification_altered_caid_in_ledger(tmp_path: Path):
    """
    Falsification test:
    - Valid DISPATCH_INTENT has its CAID altered in the ledger.
    - Because CAID is bound to the signed RFC 8785 statement, signature verification fails.
    - Also verifies that expected_payload check detects mismatched CAID.
    """
    ledger_file = tmp_path / "tamper_caid_ledger.jsonl"
    key = ed25519.Ed25519PrivateKey.generate()
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_file,
        boundary_private_key=key,
        output_state_dir=tmp_path / "state",
    )

    payload = {"command": "ARM_DETECTOR", "zone": "SECTOR_4"}
    record = interlock.record_intent(
        target_uri="http://127.0.0.1:8080/detector",
        tool_name="detector_arm",
        payload=payload,
    )

    record_dict = record.to_dict()

    # Tamper with the CAID in the ledger record
    original_caid = record_dict["caid"]
    record_dict["caid"] = "f" * 64

    # Signature fails because signed RFC 8785 statement bound original_caid
    with pytest.raises(IntentVerificationError) as exc_info:
        verify_dispatch_intent(record_dict, key.public_key())

    assert "signature verification failed" in str(exc_info.value)

    # Reset CAID to valid, but check against a different expected payload
    record_dict["caid"] = original_caid
    different_payload = {"command": "DISARM_DETECTOR", "zone": "SECTOR_4"}

    with pytest.raises(IntentVerificationError) as exc_info:
        verify_dispatch_intent(
            record_dict,
            key.public_key(),
            expected_payload=different_payload,
        )

    assert "CAID mismatch" in str(exc_info.value)


def test_falsification_altered_bound_fields(tmp_path: Path):
    """
    Falsification test:
    - Modifying target_uri, tool_name, policy_epoch, or authority_id breaks Ed25519 verification.
    """
    ledger_file = tmp_path / "tamper_fields_ledger.jsonl"
    key = ed25519.Ed25519PrivateKey.generate()
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_file,
        boundary_private_key=key,
        output_state_dir=tmp_path / "state",
        authority_id="primary-auth",
        policy_epoch=5,
    )

    payload = {"data": "test"}
    record = interlock.record_intent(
        target_uri="http://127.0.0.1:8080/original",
        tool_name="original_tool",
        payload=payload,
    )

    # Test altering target_uri
    tampered_uri = dict(record.to_dict())
    tampered_uri["target_uri"] = "http://127.0.0.1:8080/pivoted"
    with pytest.raises(IntentVerificationError):
        verify_dispatch_intent(tampered_uri, key.public_key())

    # Test altering tool_name
    tampered_tool = dict(record.to_dict())
    tampered_tool["tool_name"] = "pivoted_tool"
    with pytest.raises(IntentVerificationError):
        verify_dispatch_intent(tampered_tool, key.public_key())

    # Test altering policy_epoch
    tampered_epoch = dict(record.to_dict())
    tampered_epoch["policy_epoch"] = 999
    with pytest.raises(IntentVerificationError):
        verify_dispatch_intent(tampered_epoch, key.public_key())

    # Test altering authority_id
    tampered_auth = dict(record.to_dict())
    tampered_auth["authority_id"] = "forged-auth"
    with pytest.raises(IntentVerificationError):
        verify_dispatch_intent(tampered_auth, key.public_key())


def test_falsification_tampered_continuity_receipt(tmp_path: Path):
    """
    Falsification test:
    - Tampering with terminal ContinuityReceipt signature or fields fails verification.
    """
    key = ed25519.Ed25519PrivateKey.generate()
    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "receipt_ledger.jsonl",
        boundary_private_key=key,
        output_state_dir=tmp_path / "state",
    )

    receipt = interlock.reconcile_out_of_band(
        caid=compute_caid({"test": "data"}),
        reconciliation_evidence={"audited": True},
    )

    receipt_dict = receipt.to_dict()
    assert verify_continuity_receipt(receipt_dict, key.public_key()) is True

    # Tamper with chain_tip
    tampered = dict(receipt_dict)
    tampered["chain_tip"] = "0" * 64
    with pytest.raises(IntentVerificationError):
        verify_continuity_receipt(tampered, key.public_key())

    # Tamper with signature
    tampered_sig = dict(receipt_dict)
    sig_chars = list(tampered_sig["boundary_signature_b64"])
    sig_chars[-2] = "A" if sig_chars[-2] != "A" else "B"
    tampered_sig["boundary_signature_b64"] = "".join(sig_chars)
    with pytest.raises(IntentVerificationError):
        verify_continuity_receipt(tampered_sig, key.public_key())


def test_custom_dispatch_fn_success_and_failure(tmp_path: Path):
    """
    Evaluates dispatch when a custom dispatch_fn callable is supplied:
    - Successful dispatch_fn emits RECONCILED receipt.
    - Failing dispatch_fn latches CAID into EFFECT_INDETERMINATE with retry_safe: False.
    """
    ledger_file = tmp_path / "custom_fn_ledger.jsonl"
    state_dir = tmp_path / "custom_fn_state"
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_file,
        output_state_dir=state_dir,
    )

    # 1. Successful callable
    payload_ok = {"action": "PING"}
    res_ok = interlock.dispatch(
        target_uri="custom://in-memory",
        tool_name="ping_tool",
        payload=payload_ok,
        dispatch_fn=lambda: {"pong": True},
    )
    assert res_ok.lifecycle_state == IntentLifecycleState.RECONCILED
    assert res_ok.response == {"pong": True}

    # 2. Failing callable
    payload_fail = {"action": "FAIL_CRITICAL"}
    caid_fail = compute_caid(payload_fail)

    def failing_fn():
        raise ConnectionResetError("Remote host reset connection mid-handshake")

    with pytest.raises(Exception) as exc_info:
        interlock.dispatch(
            target_uri="custom://in-memory",
            tool_name="fail_tool",
            payload=payload_fail,
            dispatch_fn=failing_fn,
        )

    assert "EFFECT_INDETERMINATE" in str(exc_info.value)
    assert interlock.is_caid_latched(caid_fail) is True
    latched = interlock.get_latched_caids()
    assert latched[caid_fail].retry_safe is False


def test_mutation_adequacy_oracle_gap_closures(tmp_path: Path):
    """
    Closes behavioral oracle gaps discovered by tools/mutation_adequacy_gate.py on
    src/eo1_write_before_execute.py:
    1. Post-Approval Tool Substitution (line 1066): approval granted for tool_name='refund_api'
       must raise ApprovalMismatchError if consumed on tool_name='wire_transfer'.
    2. Direct outcome classification return values (lines 212 & 238):
       classify_reconciliation_outcome({}, target_outcome='NOT_COMMITTED') == 'NOT_COMMITTED'
       and classify_reconciliation_outcome({}) == 'COMMITTED'.
    3. Manual latch_indeterminate(caid, intent_id=None) inherits the unresolved DISPATCH_INTENT
       intent_id from disk rather than synthesizing a fallback ID (lines 1015 & 1023).
    4. Invalid disposition value in _emit_receipt raises ValueError (line 1351).
    5. _durable_unlink returns True when removing an existing file and False when missing (lines 374 & 376).
    """
    from src.eo1_write_before_execute import (
        ApprovalMismatchError,
        OperationApprovalGrant,
        _durable_unlink,
        classify_reconciliation_outcome,
    )

    # 1. Post-Approval Tool Substitution (Line 1066)
    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "oracle_ledger.jsonl",
        output_state_dir=tmp_path / "oracle_state",
        authority_id="actor-alpha",
    )
    payload = {"amount_minor": 10000, "currency": "USD"}
    caid = compute_caid(payload)
    grant = OperationApprovalGrant(
        approval_id="appr-tool-bind-001",
        subject_actor_id="actor-alpha",
        tool_name="refund_api_v1",
        operation_caid=caid,
    )
    with pytest.raises(ApprovalMismatchError, match="Approval tool mismatch"):
        interlock.record_intent(
            target_uri="custom://in-memory",
            tool_name="wire_transfer_v1",
            payload=payload,
            approval=grant,
            actor_id="actor-alpha",
        )

    # 2. Direct classify_reconciliation_outcome assertions (Lines 212 & 238)
    assert classify_reconciliation_outcome({}, target_outcome="NOT_COMMITTED") == "NOT_COMMITTED"
    assert classify_reconciliation_outcome({}, target_outcome="COMMITTED") == "COMMITTED"
    assert classify_reconciliation_outcome({}) == "COMMITTED"

    # 3. Manual latch_intent inherits unresolved intent_id (Lines 1015 & 1023)
    rec = interlock.record_intent(
        target_uri="custom://target-svc",
        tool_name="refund_api_v1",
        payload=payload,
        intent_id="intent-explicit-from-disk-001",
        approval=grant,
        actor_id="actor-alpha",
    )
    latch_state = interlock.latch_intent(caid)
    assert latch_state.intent_id == rec.intent_id
    assert latch_state.target_uri == "custom://target-svc"
    assert latch_state.tool_name == "refund_api_v1"
    runtime_latch_file = (tmp_path / "oracle_state") / f"latched_{caid}.json"
    assert (runtime_latch_file.stat().st_mode & 0o111) == 0
    assert '\n  "caid":' in runtime_latch_file.read_text(encoding="utf-8")

    # 4. Invalid disposition in _emit_receipt raises ValueError (Line 1351)
    with pytest.raises(ValueError, match="Unknown effect disposition"):
        interlock._emit_receipt(
            intent_id=rec.intent_id,
            caid=caid,
            status="RECONCILED",
            lifecycle_state="RECONCILED",
            retry_safe=False,
            details={},
            disposition="BOGUS_DISPOSITION",
        )

    # 5. _durable_unlink return value contract (Lines 374 & 376)
    marker = tmp_path / "unlink_probe.txt"
    marker.write_text("probe", encoding="utf-8")
    assert _durable_unlink(marker) is True
    assert _durable_unlink(marker) is False

    # 6. Frozen dataclass immutability on ContinuityReceipt & RecoveredIntentState (Lines 497 & 546)
    with pytest.raises(AttributeError):
        latch_state.retry_safe = True  # type: ignore[misc]
    orphan_caid = compute_caid({"orphan": "reconcile"})
    orphan_receipt = interlock.reconcile_out_of_band(
        caid=orphan_caid,
        reconciliation_evidence={"status": "ABORTED"},
        target_outcome="NOT_COMMITTED",
    )
    assert orphan_receipt.intent_id == f"reconciled-{orphan_caid[:16]}"
    with pytest.raises(AttributeError):
        orphan_receipt.retry_safe = True  # type: ignore[misc]

    # 7. Disk-only latch without intent_id key uses f"latched-{caid[:16]}" and reconciles cleanly (Lines 895 & 1319)
    disk_latch_caid = compute_caid({"disk_only_latch": 1})
    latch_path = (tmp_path / "oracle_state") / f"latched_{disk_latch_caid}.json"
    latch_path.write_text(
        json.dumps({"caid": disk_latch_caid, "target_uri": "custom://x", "tool_name": "t"}),
        encoding="utf-8",
    )
    interlock2 = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "oracle_ledger.jsonl",
        output_state_dir=tmp_path / "oracle_state",
        authority_id="actor-alpha",
    )
    loaded_latches = interlock2.get_latched_caids()
    assert loaded_latches[disk_latch_caid].intent_id == f"latched-{disk_latch_caid[:16]}"
    rec_disk = interlock2.reconcile_out_of_band(
        caid=disk_latch_caid,
        reconciliation_evidence={"status": "ABORTED"},
        target_outcome="NOT_COMMITTED",
    )
    assert rec_disk.intent_id == f"latched-{disk_latch_caid[:16]}"

    # 8. Remaining survivor closures (Lines 234, 288, 290, 309, 321, 351, 742, 813, 846, 880, 1116)
    import errno
    import os
    from src.eo1_write_before_execute import (
        PreDispatchLedgerWriteError,
        _fsync_dir,
        _fsync_fd,
        _write_all,
        recover_unresolved_intents,
    )

    # Line 234: target_observed=True overrides a NOT_COMMITTED outcome token in evidence
    assert (
        classify_reconciliation_outcome({"outcome": "NOT_COMMITTED", "target_observed": True})
        == "COMMITTED"
    )
    assert (
        classify_reconciliation_outcome({"outcome": "NOT_COMMITTED", "target_observed": False})
        == "NOT_COMMITTED"
    )

    # Lines 288 & 290: _fsync_fd uses fcntl(F_FULLFSYNC) on darwin without falling back to os.fsync
    probe_fd_path = tmp_path / "fsync_probe.bin"
    probe_fd_path.write_bytes(b"ok")
    fd_probe = os.open(str(probe_fd_path), os.O_RDONLY)
    try:
        orig_fsync = os.fsync

        def _forbid_os_fsync(_fd: int) -> None:
            raise RuntimeError("Unexpected fallback to os.fsync when F_FULLFSYNC is available")

        os.fsync = _forbid_os_fsync  # type: ignore[assignment]
        try:
            _fsync_fd(fd_probe)
        finally:
            os.fsync = orig_fsync  # type: ignore[assignment]
    finally:
        os.close(fd_probe)

    # Line 309: _fsync_dir re-raises non-ignored OSError (e.g. errno.EIO)
    def _fail_eio(_fd: int) -> None:
        raise OSError(errno.EIO, "simulated disk I/O error")

    with pytest.raises(OSError, match="simulated disk I/O error"):
        _fsync_dir(tmp_path, fsync_fn=_fail_eio)

    # Line 321: _write_all raises OSError(errno.EIO) if os.write returns 0
    orig_write = os.write
    zero_calls = 0

    def _zero_write(_fd: int, _buf: bytes) -> int:
        nonlocal zero_calls
        zero_calls += 1
        if zero_calls > 1:
            raise RuntimeError("unbounded loop after 0-byte write")
        return 0

    os.write = _zero_write  # type: ignore[assignment]
    try:
        with pytest.raises(OSError, match="os.write returned 0 bytes"):
            _write_all(1, b"payload")
    finally:
        os.write = orig_write  # type: ignore[assignment]

    # Lines 351 & 742: recover_unresolved_intents mode 0o644 and 2-space JSON indent
    rec_ledger = tmp_path / "rec_indent_ledger.jsonl"
    rec_state_dir = tmp_path / "rec_indent_state"
    rec_interlock = PreDispatchIntentInterlock(
        ledger_path=rec_ledger,
        output_state_dir=rec_state_dir,
        authority_id="actor-rec",
    )
    rec_payload = {"op": "recover_indent_check"}
    rec_caid = compute_caid(rec_payload)
    rec_interlock.record_intent(
        target_uri="custom://rec",
        tool_name="rec_tool",
        payload=rec_payload,
    )
    recovered_list = recover_unresolved_intents(rec_ledger, rec_state_dir)
    assert any(r.caid == rec_caid for r in recovered_list)
    rec_latch_file = rec_state_dir / f"latched_{rec_caid}.json"
    assert '\n  "caid":' in rec_latch_file.read_text(encoding="utf-8")

    # Line 846: re-entrant _exclusive() increments _flock_depth by exactly 1
    with rec_interlock._exclusive():
        assert rec_interlock._flock_depth == 1
        with rec_interlock._exclusive():
            assert rec_interlock._flock_depth == 2
        assert rec_interlock._flock_depth == 1
    assert rec_interlock._flock_depth == 0

    # Line 880: _sync_ledger_locked handles a 1-byte leading newline (last_nl == 0)
    nl_ledger = tmp_path / "leading_newline_ledger.jsonl"
    nl_ledger.write_bytes(b"\n")
    nl_interlock = PreDispatchIntentInterlock(
        ledger_path=nl_ledger,
        output_state_dir=tmp_path / "nl_state",
        authority_id="actor-nl",
    )
    assert nl_interlock._view.offset == 1

    # Line 1116: OSError during _exclusive() lock acquisition raises PreDispatchLedgerWriteError
    nl_interlock._lock_path.unlink(missing_ok=True)
    nl_interlock._lock_path.mkdir(parents=True, exist_ok=True)
    with pytest.raises(PreDispatchLedgerWriteError, match="Pre-dispatch ledger lock/read failed"):
        nl_interlock.record_intent(
            target_uri="custom://in-memory",
            tool_name="refund_api_v1",
            payload={"x": 1},
        )



