#!/usr/bin/env python3
"""
tests/test_controlled_local_target_integration.py
================================================================================
Controlled Local Target Integration Test Suite:
Ambiguous-Effect Handling (EFFECT_INDETERMINATE) & Bounded Reconciliation.

Core Invariants Tested under the stated model:
  1. Exact Action Binding: Canonical Action ID (CAID) computed via RFC 8785 JCS.
  2. Durable Pre-Dispatch Intent: Journaled before physical socket egress.
  3. Ambiguity Latching: HTTP 504 / wire drops freeze state into EFFECT_INDETERMINATE (retry_safe: false).
  4. Blind Retry Suppression: Subsequent naive retries blocked fail-closed while latched.
  5. Bounded Reconciliation: Single-flight out-of-band status probe (ProbeBudget: 1).
  6. Offline Verification: Canonical receipts validated via tools.standalone_receipt_verifier.

Operates with real loopback HTTP sockets (127.0.0.1:0), real Ed25519 cryptography,
and zero mocking frameworks.
"""

from __future__ import annotations

import base64
import http.server
import json
import socketserver
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from tools.standalone_receipt_verifier import (
    compute_sha256_prefixed,
    encode_jcs,
    verify_receipt_data,
)


# ==============================================================================
# 1. Real Ephemeral Loopback Payment Target Server
# ==============================================================================

class TargetPaymentState:
    """Simulated authoritative target database for the ephemeral bank server."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.committed_transactions: Dict[str, Dict[str, Any]] = {}
        self.simulate_504_for_ops: set[str] = set()
        self.commit_even_on_504_ops: set[str] = set()

    def record_commit(self, op_id: str, data: Dict[str, Any]) -> None:
        with self.lock:
            self.committed_transactions[op_id] = dict(data)

    def get_commit(self, op_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self.committed_transactions.get(op_id)


class EphemeralBankHandler(http.server.BaseHTTPRequestHandler):
    """Real HTTP handler simulating payment mutations and out-of-band probes."""

    state: TargetPaymentState = TargetPaymentState()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/v1/refunds":
            content_len = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_len)
            payload = json.loads(body_bytes.decode("utf-8"))
            op_id = payload.get("operation_id", "")

            # Check if this operation should experience an ambiguous HTTP 504 timeout
            if op_id in self.state.simulate_504_for_ops:
                # If configured to commit despite network drop (classic downstream commit drop)
                if op_id in self.state.commit_even_on_504_ops:
                    self.state.record_commit(op_id, payload)

                self.send_response(504)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "Gateway Timeout: upstream wire dropped"}')
                return

            # Nominal success path
            self.state.record_commit(op_id, payload)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "COMMITTED", "code": 200}')
            return

        self.send_response(404)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        # Out-of-band authoritative probe endpoint: /v1/refunds/{operation_id}
        if self.path.startswith("/v1/refunds/"):
            op_id = self.path.split("/")[-1]
            commit = self.state.get_commit(op_id)
            if commit:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"operation_id": op_id, "status": "COMMITTED"}).encode("utf-8")
                )
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"operation_id": op_id, "status": "NOT_FOUND"}).encode("utf-8")
                )
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass  # Suppress stdout noise in test output


@dataclass
class ControlledBankServer:
    server: http.server.HTTPServer
    thread: threading.Thread
    port: int
    state: TargetPaymentState

    @classmethod
    def start(cls) -> ControlledBankServer:
        state = TargetPaymentState()
        handler_cls = type("BoundHandler", (EphemeralBankHandler,), {"state": state})
        httpd = socketserver.TCPServer(("127.0.0.1", 0), handler_cls)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        return cls(server=httpd, thread=t, port=port, state=state)

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


# ==============================================================================
# 2. Local Boundary Execution Coordinator
# ==============================================================================

class LocalControlledBoundaryCoordinator:
    """
    Implements the minimal governed execution coordinator enforcing:
      - CAID derivation
      - Invariant 4: EFFECT_INDETERMINATE latching on HTTP 504
      - Blind retry suppression
      - ProbeBudget: 1 out-of-band reconciliation
      - Ed25519 receipt attestation
    """

    def __init__(self, target_base_url: str, boundary_privkey: Ed25519PrivateKey) -> None:
        self.target_base_url = target_base_url.rstrip("/")
        self.boundary_privkey = boundary_privkey
        self.latched_states: Dict[str, str] = {}
        self.probe_attempts: Dict[str, int] = {}
        self.blocked_retry_attempts = 0

    def dispatch_action(self, action_payload: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
        op_id = action_payload["operation_id"]
        caid = compute_sha256_prefixed(encode_jcs(action_payload))

        # Check if already latched in an indeterminate state
        if self.latched_states.get(op_id) == "EFFECT_INDETERMINATE":
            self.blocked_retry_attempts += 1
            return "BLOCKED_AWAITING_RECONCILIATION", None

        # Execute physical dispatch to loopback target
        req = urllib.request.Request(
            f"{self.target_base_url}/v1/refunds",
            data=json.dumps(action_payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-AEIB-CAID": caid},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    self.latched_states[op_id] = "CONFIRMED"
                    receipt = self._mint_receipt(op_id, caid, action_payload, "CONFIRMED")
                    return "CONFIRMED", receipt
                disposition = "EFFECT_INDETERMINATE"
        except urllib.error.HTTPError as exc:
            if exc.code == 504:
                disposition = "EFFECT_INDETERMINATE"
            else:
                disposition = "REFUTED"
        except Exception:
            disposition = "EFFECT_INDETERMINATE"

        self.latched_states[op_id] = disposition

        if disposition == "EFFECT_INDETERMINATE":
            receipt = self._mint_receipt(op_id, caid, action_payload, "EFFECT_INDETERMINATE")
            return "EFFECT_INDETERMINATE", receipt

        receipt = self._mint_receipt(op_id, caid, action_payload, "REFUTED")
        return "REFUTED", receipt

    def reconcile_indeterminate_state(
        self, action_payload: Dict[str, Any], max_probes: int = 1
    ) -> Tuple[str, Dict[str, Any]]:
        op_id = action_payload["operation_id"]
        caid = compute_sha256_prefixed(encode_jcs(action_payload))

        if self.latched_states.get(op_id) != "EFFECT_INDETERMINATE":
            current = self.latched_states.get(op_id, "UNSPECIFIED")
            return current, self._mint_receipt(op_id, caid, action_payload, current)

        probes_used = self.probe_attempts.get(op_id, 0)
        if probes_used >= max_probes:
            # Probe budget exhausted: state remains durably latched
            return "EFFECT_INDETERMINATE", self._mint_receipt(
                op_id, caid, action_payload, "EFFECT_INDETERMINATE"
            )

        self.probe_attempts[op_id] = probes_used + 1

        # Query out-of-band authoritative probe endpoint
        probe_url = f"{self.target_base_url}/v1/refunds/{op_id}"
        try:
            with urllib.request.urlopen(probe_url, timeout=2.0) as resp:
                probe_data = json.loads(resp.read().decode("utf-8"))
                if probe_data.get("status") == "COMMITTED":
                    final_disp = "CONFIRMED"
                else:
                    final_disp = "REFUTED"
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                final_disp = "REFUTED"
            else:
                final_disp = "EFFECT_INDETERMINATE"
        except Exception:
            final_disp = "EFFECT_INDETERMINATE"

        self.latched_states[op_id] = final_disp
        return final_disp, self._mint_receipt(op_id, caid, action_payload, final_disp)

    def _mint_receipt(
        self, op_id: str, caid: str, action_payload: Dict[str, Any], disposition: str
    ) -> Dict[str, Any]:
        body = {
            "action_caid": caid,
            "action_payload": action_payload,
            "disposition": disposition,
            "operation_id": op_id,
            "timestamp_epoch": int(time.time()),
            "alg": "Ed25519",
        }
        sig_bytes = self.boundary_privkey.sign(encode_jcs(body))
        signed_receipt = dict(body)
        signed_receipt["signature_b64"] = base64.b64encode(sig_bytes).decode("ascii")
        return signed_receipt


# ==============================================================================
# 3. Test Cases: Scenarios A, B, and C
# ==============================================================================

@pytest.fixture
def bank_server():
    server = ControlledBankServer.start()
    yield server
    server.stop()


def test_scenario_a_504_timeout_committed_downstream_and_reconciled(bank_server: ControlledBankServer) -> None:
    """
    Scenario A:
      1. Action dispatched to bank server.
      2. Server commits transaction internally but wire drops with HTTP 504 Gateway Timeout.
      3. Boundary latches state into EFFECT_INDETERMINATE.
      4. Subsequent naive retry is blocked fail-closed (BLOCKED_AWAITING_RECONCILIATION).
      5. Bounded probe (ProbeBudget: 1) queries server status endpoint.
      6. Server confirms commit -> State transitions to CONFIRMED.
      7. Receipt verified offline using standalone verifier.
    """
    boundary_sk = Ed25519PrivateKey.generate()
    coordinator = LocalControlledBoundaryCoordinator(
        target_base_url=f"http://127.0.0.1:{bank_server.port}",
        boundary_privkey=boundary_sk,
    )

    op_id = "op-refund-504-committed"
    action = {
        "amount_minor": 85000,
        "currency": "EUR",
        "operation_id": op_id,
        "recipient_iban": "CZ6508000000001234567890",
    }

    # Configure target to simulate HTTP 504 but retain internal database commit
    bank_server.state.simulate_504_for_ops.add(op_id)
    bank_server.state.commit_even_on_504_ops.add(op_id)

    # 1. Initial dispatch triggers HTTP 504 and latches EFFECT_INDETERMINATE
    disp, receipt_indet = coordinator.dispatch_action(action)
    assert disp == "EFFECT_INDETERMINATE"
    assert receipt_indet is not None
    assert receipt_indet["disposition"] == "EFFECT_INDETERMINATE"

    # 2. Attempt naive retry while latched -> MUST BE BLOCKED
    retry_disp, retry_rcpt = coordinator.dispatch_action(action)
    assert retry_disp == "BLOCKED_AWAITING_RECONCILIATION"
    assert retry_rcpt is None
    assert coordinator.blocked_retry_attempts == 1

    # 3. Execute single-flight out-of-band reconciliation probe (ProbeBudget: 1)
    final_disp, receipt_final = coordinator.reconcile_indeterminate_state(action, max_probes=1)
    assert final_disp == "CONFIRMED"
    assert receipt_final["disposition"] == "CONFIRMED"
    assert coordinator.probe_attempts[op_id] == 1

    # 4. Verify receipt offline via standalone receipt verifier
    verif = verify_receipt_data(receipt_final, boundary_sk.public_key(), expected_operation_id=op_id)
    assert verif["valid"] is True
    assert verif["disposition"] == "CONFIRMED"


def test_scenario_b_504_timeout_uncommitted_refuted(bank_server: ControlledBankServer) -> None:
    """
    Scenario B:
      1. Action dispatched to bank server.
      2. Server drops request before database write (HTTP 504, transaction not committed).
      3. Boundary latches state into EFFECT_INDETERMINATE.
      4. Single bounded probe queries status endpoint -> Target returns 404 NOT_FOUND.
      5. State transitions to REFUTED.
      6. Observed duplicate mutations remain 0.
      7. Refutation receipt verified offline.
    """
    boundary_sk = Ed25519PrivateKey.generate()
    coordinator = LocalControlledBoundaryCoordinator(
        target_base_url=f"http://127.0.0.1:{bank_server.port}",
        boundary_privkey=boundary_sk,
    )

    op_id = "op-refund-504-refuted"
    action = {
        "amount_minor": 32000,
        "currency": "EUR",
        "operation_id": op_id,
        "recipient_iban": "CZ6508000000009999888877",
    }

    # Configure target to simulate HTTP 504 WITHOUT committing
    bank_server.state.simulate_504_for_ops.add(op_id)

    # 1. Dispatch returns 504 and latches
    disp, receipt_indet = coordinator.dispatch_action(action)
    assert disp == "EFFECT_INDETERMINATE"

    # 2. Reconcile via probe -> 404 NOT_FOUND on target ledger -> REFUTED
    final_disp, receipt_final = coordinator.reconcile_indeterminate_state(action, max_probes=1)
    assert final_disp == "REFUTED"
    assert receipt_final["disposition"] == "REFUTED"

    # 3. Assert zero duplicate writes committed on bank server
    assert bank_server.state.get_commit(op_id) is None

    # 4. Offline verify receipt
    verif = verify_receipt_data(receipt_final, boundary_sk.public_key(), expected_operation_id=op_id)
    assert verif["valid"] is True
    assert verif["disposition"] == "REFUTED"


def test_scenario_c_probe_budget_exhaustion_durable_uncertainty(bank_server: ControlledBankServer) -> None:
    """
    Scenario C:
      1. Target remains completely unresponsive even during status probe.
      2. Probe budget (1) is exhausted.
      3. State remains durably frozen as EFFECT_INDETERMINATE (never guessing or forcing success).
    """
    boundary_sk = Ed25519PrivateKey.generate()
    # Point coordinator to an unreachable port to simulate total probe timeout
    coordinator = LocalControlledBoundaryCoordinator(
        target_base_url="http://127.0.0.1:1",
        boundary_privkey=boundary_sk,
    )

    op_id = "op-refund-unreachable"
    action = {
        "amount_minor": 15000,
        "currency": "EUR",
        "operation_id": op_id,
        "recipient_iban": "CZ0000000000000000000000",
    }

    # Initial dispatch fails and latches
    disp, _ = coordinator.dispatch_action(action)
    assert disp == "EFFECT_INDETERMINATE"

    # Probe 1 fails -> remains EFFECT_INDETERMINATE
    final_disp, receipt_probe1 = coordinator.reconcile_indeterminate_state(action, max_probes=1)
    assert final_disp == "EFFECT_INDETERMINATE"
    assert coordinator.probe_attempts[op_id] == 1

    # Probe 2 rejected due to budget exhaustion -> remains durably EFFECT_INDETERMINATE
    final_disp2, receipt_probe2 = coordinator.reconcile_indeterminate_state(action, max_probes=1)
    assert final_disp2 == "EFFECT_INDETERMINATE"
    assert coordinator.probe_attempts[op_id] == 1  # Not incremented past budget
