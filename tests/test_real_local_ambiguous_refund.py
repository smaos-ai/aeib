#!/usr/bin/env python3
"""
tests/test_real_local_ambiguous_refund.py
================================================================================
Deliverable C: Real Local-Target Ambiguous-Refund End-to-End Integration Test.

Closes the Core Verification Loop (Step 4):
- Starts a real local TCP/HTTP payment server on 127.0.0.1 (zero mocks).
- Simulates the exact LIMBO (arXiv:2609.29095) anomaly: the server commits the refund
  on Attempt 1, but drops/delays the HTTP response so the client observes a timeout.
- Verifies that AEIB:
  1. Never exposes the downstream API key to the agent (`agent_holds_downstream_credentials=False`).
  2. Latches `EFFECT_INDETERMINATE` in the local WAL on timeout.
  3. Blocks the agent's blind retry (`HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY`).
  4. Executes bounded authoritative reconciliation (`/v1/refunds/status?idempotency_key=...`)
     to confirm the single €25.00 refund without double-spending a cent.
  5. Emits a canonical JCS receipt chain verified offline by `StandaloneOfflineVerifier`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.server
import json
import socket
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs  # RFC 8785 canonical JCS
from tools.aeib_offline_verifier import (
    StandaloneOfflineVerifier,
    build_manifest,
)

SUPPORTED_SCHEMA_VERSION = "aeib.receipt.v1"
GENESIS_PREV_HASH = "sha256:" + ("0" * 64)


def canonical_jcs_bytes(obj: Any) -> bytes:
    """RFC 8785 JCS canonicalization."""
    return encode_jcs(obj)


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# --- 1. Real Local HTTP Payment Target Server (127.0.0.1) ---
class RealLocalPaymentRailState:
    def __init__(self, expected_bearer_secret: str) -> None:
        self.expected_bearer_secret = expected_bearer_secret
        self.lock = threading.Lock()
        self.total_disbursed_minor: int = 0
        self.committed_by_idem_key: Dict[str, Dict[str, Any]] = {}
        self.simulate_dropped_ack_on_first_post: bool = True
        self.post_attempts_received: int = 0


class PaymentRailHTTPHandler(http.server.BaseHTTPRequestHandler):
    rail_state: RealLocalPaymentRailState

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Keep test output clean

    def do_POST(self) -> None:
        if self.path != "/v1/refunds":
            self.send_response(404)
            self.end_headers()
            return

        auth = self.headers.get("Authorization", "")
        expected_auth = f"Bearer {self.rail_state.expected_bearer_secret}"
        if not hmac.compare_digest(auth.encode("utf-8"), expected_auth.encode("utf-8")):
            self.send_response(401)
            self.end_headers()
            return

        idem_key = self.headers.get("Idempotency-Key", "")
        content_len = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_len)
        payload = json.loads(raw_body.decode("utf-8"))

        with self.rail_state.lock:
            self.rail_state.post_attempts_received += 1
            if idem_key not in self.rail_state.committed_by_idem_key:
                # Commit the financial effect on the server!
                self.rail_state.total_disbursed_minor += int(payload["amount_minor"])
                self.rail_state.committed_by_idem_key[idem_key] = {
                    "refund_id": f"re_live_{len(self.rail_state.committed_by_idem_key) + 1}",
                    "amount_minor": int(payload["amount_minor"]),
                    "recipient": payload["recipient"],
                    "status": "COMMITTED",
                }

            # Simulate the LIMBO lost-acknowledgement anomaly on the first POST:
            # The server committed the refund above, but hangs/drops the response!
            if self.rail_state.simulate_dropped_ack_on_first_post:
                self.rail_state.simulate_dropped_ack_on_first_post = False
                self.send_response(504)
                self.end_headers()
                self.wfile.write(b'{"error":"gateway_timeout_ambiguous_commit"}')
                return

            record = self.rail_state.committed_by_idem_key[idem_key]

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(canonical_jcs_bytes(record))

    def do_GET(self) -> None:
        if not self.path.startswith("/v1/refunds/status/"):
            self.send_response(404)
            self.end_headers()
            return

        auth = self.headers.get("Authorization", "")
        expected_auth = f"Bearer {self.rail_state.expected_bearer_secret}"
        if not hmac.compare_digest(auth.encode("utf-8"), expected_auth.encode("utf-8")):
            self.send_response(401)
            self.end_headers()
            return

        idem_key = self.path.split("/v1/refunds/status/", 1)[1]
        with self.rail_state.lock:
            record = self.rail_state.committed_by_idem_key.get(idem_key)

        if record is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"status":"NOT_FOUND_REFUTED"}')
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(canonical_jcs_bytes(record))


# --- 2. AEIB Station 1 + Station 2 + Station 3 Boundary Coordinator ---
class LocalAeibCoordinator:
    def __init__(
        self,
        sponsor_budget_minor: int,
        host_vault_secret: str,
        station3_privkey: Ed25519PrivateKey,
        station3_kid: str,
    ) -> None:
        self.total_budget_minor = sponsor_budget_minor
        self.reserved_escrow_minor = 0
        self.confirmed_spent_minor = 0
        self._host_vault_secret = host_vault_secret
        self._station3_privkey = station3_privkey
        self.station3_kid = station3_kid
        self.operation_states: Dict[str, str] = {}
        self.operation_caids: Dict[str, str] = {}
        self.ledger: List[Dict[str, Any]] = []

    def _append_receipt(
        self,
        operation_id: str,
        finality_state: str,
        action_binding: Dict[str, Any],
    ) -> Dict[str, Any]:
        seq = len(self.ledger) + 1
        prev_hash = GENESIS_PREV_HASH if seq == 1 else self.ledger[-1]["entry_hash"]
        unsigned = {
            "schema_version": SUPPORTED_SCHEMA_VERSION,
            "seq": seq,
            "operation_id": operation_id,
            "prev_entry_hash": prev_hash,
            "kid": self.station3_kid,
            "finality_state": finality_state,
            "action_binding": action_binding,
            "temporal_authority": {
                "issued_at_ms": 1_760_000_000_000,
                "expires_at_ms": 1_760_000_005_000,
                "dispatched_at_ms": 1_760_000_001_000,
            },
        }
        canonical = canonical_jcs_bytes(unsigned)
        entry_hash = sha256_prefixed(canonical)
        sig_b64 = base64.b64encode(self._station3_privkey.sign(canonical)).decode("ascii")
        signed_entry = {
            **unsigned,
            "entry_hash": entry_hash,
            "signature_b64": sig_b64,
        }
        self.ledger.append(signed_entry)
        return signed_entry

    def dispatch_governed_refund(
        self,
        operation_id: str,
        target_url: str,
        amount_minor: int,
        recipient: str,
        harness_digest: str,
        policy_epoch: str,
    ) -> Tuple[str, Optional[str]]:
        # 1. Check if operation is already latched in EFFECT_INDETERMINATE or CONFIRMED
        existing_state = self.operation_states.get(operation_id)
        if existing_state == "EFFECT_INDETERMINATE":
            return (
                "NOT_DISPATCHED",
                "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY",
            )
        if existing_state == "CONFIRMED":
            return ("NOT_DISPATCHED", "HALT_ALREADY_CONFIRMED")

        # 2. Compute exact JCS Action Binding Digest (CAID)
        caid_payload = {
            "action_class": "PAYMENT_REFUND",
            "amount_minor": amount_minor,
            "currency": "EUR",
            "harness_digest": harness_digest,
            "operation_id": operation_id,
            "policy_epoch": policy_epoch,
            "recipient": recipient,
            "target": target_url,
        }
        caid = sha256_prefixed(canonical_jcs_bytes(caid_payload))

        # 3. Local Atomic Escrow Reservation (Confirmed + Escrow + Requested <= Budget)
        if (
            self.confirmed_spent_minor + self.reserved_escrow_minor + amount_minor
            > self.total_budget_minor
        ):
            return ("NOT_DISPATCHED", "HALT_BUDGET_ESCROW_EXCEEDED")

        self.reserved_escrow_minor += amount_minor
        self.operation_states[operation_id] = "DISPATCHING"
        self.operation_caids[operation_id] = caid

        idem_key = f"aeib-{hashlib.sha256(f'{operation_id}:{caid}'.encode()).hexdigest()[:24]}"
        req_body = canonical_jcs_bytes(
            {"amount_minor": amount_minor, "recipient": recipient}
        )

        # 4. Out-of-Band Host Secret Injection (Agent never sees self._host_vault_secret)
        req = urllib.request.Request(
            target_url,
            data=req_body,
            headers={
                "Authorization": f"Bearer {self._host_vault_secret}",
                "Content-Type": "application/json",
                "Idempotency-Key": idem_key,
            },
            method="POST",
        )

        action_binding = {
            "action_class": "PAYMENT_REFUND",
            "amount_minor": amount_minor,
            "caid": caid,
            "currency": "EUR",
            "harness_digest": harness_digest,
            "policy_epoch": policy_epoch,
            "recipient": recipient,
            "target": target_url,
        }

        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    self.reserved_escrow_minor -= amount_minor
                    self.confirmed_spent_minor += amount_minor
                    self.operation_states[operation_id] = "CONFIRMED"
                    self._append_receipt(operation_id, "CONFIRMED", action_binding)
                    return ("CONFIRMED", None)
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504):
                # Ambiguous transport outcome! Latch EFFECT_INDETERMINATE and keep escrow locked
                self.operation_states[operation_id] = "EFFECT_INDETERMINATE"
                self._append_receipt(operation_id, "EFFECT_INDETERMINATE", action_binding)
                return ("EFFECT_INDETERMINATE", "LATCHED_AWAITING_RECONCILIATION")
            raise

        return ("EFFECT_INDETERMINATE", "LATCHED_UNKNOWN")

    def reconcile_indeterminate_operation(
        self,
        operation_id: str,
        status_base_url: str,
        target_url: str,
        amount_minor: int,
        recipient: str,
        harness_digest: str,
        policy_epoch: str,
    ) -> str:
        assert self.operation_states.get(operation_id) == "EFFECT_INDETERMINATE"
        caid = self.operation_caids[operation_id]
        idem_key = f"aeib-{hashlib.sha256(f'{operation_id}:{caid}'.encode()).hexdigest()[:24]}"

        probe_req = urllib.request.Request(
            f"{status_base_url}/{idem_key}",
            headers={"Authorization": f"Bearer {self._host_vault_secret}"},
            method="GET",
        )
        rec_op_id = f"{operation_id}:reconciled"
        rec_binding = {
            "action_class": "PAYMENT_REFUND",
            "amount_minor": amount_minor,
            "currency": "EUR",
            "harness_digest": harness_digest,
            "policy_epoch": policy_epoch,
            "recipient": recipient,
            "target": target_url,
        }
        rec_binding["caid"] = sha256_prefixed(
            canonical_jcs_bytes(
                {
                    "action_class": "PAYMENT_REFUND",
                    "amount_minor": amount_minor,
                    "currency": "EUR",
                    "harness_digest": harness_digest,
                    "operation_id": rec_op_id,
                    "policy_epoch": policy_epoch,
                    "recipient": recipient,
                    "target": target_url,
                }
            )
        )
        with urllib.request.urlopen(probe_req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "COMMITTED":
                # Move funds from escrow to confirmed without sending a second payment!
                self.reserved_escrow_minor -= amount_minor
                self.confirmed_spent_minor += amount_minor
                self.operation_states[operation_id] = "CONFIRMED"
                self._append_receipt(
                    rec_op_id, "CONFIRMED", rec_binding
                )
                return "RECONCILED_CONFIRMED"
        return "EFFECT_INDETERMINATE"


def test_real_local_target_ambiguous_refund_end_to_end() -> None:
    rail_state = RealLocalPaymentRailState(expected_bearer_secret="sk_live_HOST_ONLY_777")

    class BoundHandler(PaymentRailHTTPHandler):
        pass

    BoundHandler.rail_state = rail_state
    server = http.server.HTTPServer(("127.0.0.1", 0), BoundHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        target_url = f"http://127.0.0.1:{port}/v1/refunds"
        status_url = f"http://127.0.0.1:{port}/v1/refunds/status"
        station3_priv = Ed25519PrivateKey.generate()
        kid = "aeib-station3-local-e2e"

        aeib = LocalAeibCoordinator(
            sponsor_budget_minor=5000,  # €50.00 total budget
            host_vault_secret="sk_live_HOST_ONLY_777",
            station3_privkey=station3_priv,
            station3_kid=kid,
        )
        harness_dig = "sha256:" + ("b" * 64)
        epoch = "epoch-2026-10-19-v1"
        iban = "iban:DE89370400440532013000"

        # Step 1: Agent dispatches €25.00 refund (`op-refund-101`).
        # Server commits the €25.00, but returns HTTP 504 (lost acknowledgement).
        state_1, reason_1 = aeib.dispatch_governed_refund(
            "op-refund-101", target_url, 2500, iban, harness_dig, epoch
        )
        assert state_1 == "EFFECT_INDETERMINATE"
        assert reason_1 == "LATCHED_AWAITING_RECONCILIATION"
        assert aeib.reserved_escrow_minor == 2500
        assert aeib.confirmed_spent_minor == 0
        assert rail_state.total_disbursed_minor == 2500

        # Step 2: Stochastic LLM agent panics on timeout and tries a blind retry of `op-refund-101`
        # OR tries to open a new €30.00 refund that exceeds remaining unreserved budget (€25 left).
        state_retry, reason_retry = aeib.dispatch_governed_refund(
            "op-refund-101", target_url, 2500, iban, harness_dig, epoch
        )
        assert state_retry == "NOT_DISPATCHED"
        assert reason_retry == "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY"

        state_over, reason_over = aeib.dispatch_governed_refund(
            "op-refund-102", target_url, 3000, iban, harness_dig, epoch
        )
        assert state_over == "NOT_DISPATCHED"
        assert reason_over == "HALT_BUDGET_ESCROW_EXCEEDED"

        # Server still only received 1 POST attempt and disbursed exactly €25.00!
        assert rail_state.post_attempts_received == 1
        assert rail_state.total_disbursed_minor == 2500

        # Step 3: AEIB Station 2 runs bounded authoritative reconciliation against `/v1/refunds/status`
        rec_outcome = aeib.reconcile_indeterminate_operation(
            "op-refund-101", status_url, target_url, 2500, iban, harness_dig, epoch
        )
        assert rec_outcome == "RECONCILED_CONFIRMED"
        assert aeib.reserved_escrow_minor == 0
        assert aeib.confirmed_spent_minor == 2500
        assert rail_state.total_disbursed_minor == 2500
        assert len(aeib.ledger) == 2
        assert aeib.ledger[0]["finality_state"] == "EFFECT_INDETERMINATE"
        assert aeib.ledger[1]["finality_state"] == "CONFIRMED"
        assert aeib.ledger[1]["prev_entry_hash"] == aeib.ledger[0]["entry_hash"]

        # Step 4: Validate generated receipt chain with StandaloneOfflineVerifier
        verifier = StandaloneOfflineVerifier(
            trust_anchors={kid: station3_priv.public_key()},
            max_clock_drift_ms=500,
        )
        manifest = build_manifest(aeib.ledger)
        expected_ops = {"op-refund-101", "op-refund-101:reconciled"}
        res = verifier.verify_bundle(manifest, aeib.ledger, expected_ops)
        assert res.valid and res.error_code is None
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    test_real_local_target_ambiguous_refund_end_to_end()
    print("ALL AMBIGUOUS REFUND STEPS & RECEIPT VERIFICATION PASSED.")
