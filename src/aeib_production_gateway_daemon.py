#!/usr/bin/env python3
"""
src/aeib_production_gateway_daemon.py

AEIB Production Gateway Daemon & Sidecar Reverse Proxy
Implements the full Station 0–3 execution boundary pipeline as a production-grade
HTTP service for agent environments:
- Health & readiness probes (/healthz, /readyz).
- Pre-dispatch admission, typing, and Sybil/taint gating (Station 0 & 1).
- Out-of-process wire mutation forwarding with HTTP 504 EFFECT_INDETERMINATE latching (Station 2).
- Single-flight out-of-band status probe reconciliation (ProbeBudget: 1).
- Append-only hash-chained ledger and RFC 9942 SCITT receipt export (Station 3).

Evaluated under the stated model. Strict RFC 8785 JCS canonicalization and real Ed25519 crypto.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs
from src.opencode_and_mcp_codemode_engine import (
    CodeModeAndHotReloadGate,
    SignedPluginManifest,
    sha256_prefixed,
)


class AEIBProductionGatewayHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for AEIB Production Gateway Daemon."""

    server_engine: AEIBProductionGatewayEngine

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_json(
                200,
                {
                    "boundary_mode": "FAIL_CLOSED",
                    "status": "HEALTHY",
                    "uptime_seconds": self.server_engine.get_uptime_seconds(),
                },
            )
            return

        if self.path == "/readyz":
            ready, detail = self.server_engine.check_readiness()
            code = 200 if ready else 503
            self._send_json(code, detail)
            return

        if self.path == "/v1/ledger/receipts":
            receipts = self.server_engine.get_all_receipts()
            self._send_json(200, {"receipt_count": len(receipts), "receipts": receipts})
            return

        self._send_json(404, {"error": "NOT_FOUND", "path": self.path})

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        if self.path == "/v1/dispatch":
            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except Exception as e:
                self._send_json(400, {"error": "MALFORMED_JSON", "detail": str(e)})
                return

            res = self.server_engine.handle_dispatch(
                headers=dict(self.headers),
                payload=payload,
            )
            status_code = 200 if res["verdict"] == "DISPATCHED" else 403
            if res.get("rejection_code") == "EFFECT_INDETERMINATE":
                status_code = 504
            self._send_json(status_code, res)
            return

        if self.path == "/v1/reconcile":
            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except Exception as e:
                self._send_json(400, {"error": "MALFORMED_JSON", "detail": str(e)})
                return

            op_id = payload.get("operation_id", "")
            res = self.server_engine.reconcile_indeterminate_operation(op_id)
            self._send_json(200, res)
            return

        self._send_json(404, {"error": "NOT_FOUND", "path": self.path})

    def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
        body = encode_jcs(data)
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-AEIB-Boundary-Version", "v1.0.0-rc.3")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard HTTP access logs in automated test environments
        pass


class AEIBProductionGatewayEngine:
    """
    Core production gateway engine coordinating Stations 0 through 3.
    """

    def __init__(
        self,
        *,
        gate_signer: Ed25519PrivateKey,
        sponsor_pubkey: Ed25519PublicKey,
        human_publisher_pubkey: Ed25519PublicKey,
        human_publisher_key_id: str,
        downstream_target_url: str,
        downstream_probe_url: str,
        ledger_path: Path,
        session_start_ns: int,
        sprint_limit_minor: int = 2500_00,
    ) -> None:
        self.gate_signer = gate_signer
        self.sponsor_pubkey = sponsor_pubkey
        self.downstream_target_url = downstream_target_url
        self.downstream_probe_url = downstream_probe_url
        self.ledger_path = ledger_path
        self.session_start_ns = session_start_ns
        self.sprint_limit_minor = sprint_limit_minor
        self._lock = threading.Lock()
        self._boot_time_ts = int(session_start_ns / 1_000_000_000)

        # Station 1 Code Mode and Hot Reload Gate
        self.code_mode_gate = CodeModeAndHotReloadGate(
            session_start_ns=session_start_ns,
            human_publisher_pubkey=human_publisher_pubkey,
            human_publisher_key_id=human_publisher_key_id,
            sprint_limit_minor=sprint_limit_minor,
        )

        # In-memory chain tip and receipts
        self._chain_tip = "sha256:" + ("0" * 64)
        self._receipts: List[Dict[str, Any]] = []
        self._indeterminate_escrow: Dict[str, int] = {}
        self._reconciled_ops: Dict[str, str] = {}

        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            self.ledger_path.touch()

    def get_uptime_seconds(self) -> int:
        import time
        return max(0, int(time.time()) - self._boot_time_ts)

    def check_readiness(self) -> Tuple[bool, Dict[str, Any]]:
        with self._lock:
            return True, {
                "chain_tip": self._chain_tip,
                "indeterminate_escrow_count": len(self._indeterminate_escrow),
                "ledger_exists": self.ledger_path.exists(),
                "pinned_plugins_count": len(self.code_mode_gate._pinned_plugins),
                "ready": True,
            }

    def register_pinned_tool(
        self, manifest: SignedPluginManifest, live_code_bytes: bytes
    ) -> Tuple[bool, Optional[str]]:
        return self.code_mode_gate.register_plugin(manifest, live_code_bytes)

    def handle_dispatch(
        self,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        with self._lock:
            # 1. Station 0: Typing & Mandatory Parameter Admission
            operation_id = payload.get("operation_id", "")
            action_type = payload.get("action_type", "")
            amount_minor = payload.get("amount_minor", 0)
            plugin_id = payload.get("plugin_id", "mcp-core-suite")
            data_tier = payload.get("data_tier", "TIER_0_PINNED")
            pinned_recipient = payload.get("pinned_known_recipient", True)

            if not operation_id or not action_type or not isinstance(amount_minor, int):
                return {
                    "operation_id": operation_id,
                    "rejection_code": "HALT_INVALID_PARAMETER_SPECIFICATION",
                    "verdict": "REJECTED",
                }

            # 2. Station 1: Code Mode, Taint & Sprint Limit Checks
            step_eval = self.code_mode_gate.execute_mcp_codemode_step(
                plugin_id=plugin_id,
                step_type="FINANCIAL_MUTATION",
                data_tier=data_tier,
                amount_minor=amount_minor,
                pinned_known_recipient=pinned_recipient,
            )
            if step_eval["disposition"] != "DISPATCHED":
                return {
                    "operation_id": operation_id,
                    "rejection_code": step_eval["rejection_code"],
                    "verdict": "REJECTED",
                }

            # Compute canonical Action CAID and deterministic Rail Idempotency Key
            action_caid = sha256_prefixed(
                encode_jcs(
                    {
                        "action_type": action_type,
                        "amount_minor": amount_minor,
                        "operation_id": operation_id,
                        "plugin_id": plugin_id,
                    }
                )
            )
            rail_idempotency_key = f"aeib-idem-v1-{hashlib.sha256(f'{operation_id}:{action_caid}'.encode('utf-8')).hexdigest()[:32]}"

            # 3. Station 2: Downstream Forwarding & HTTP 504 Ambiguity Interception
            target_response_code = 0
            target_response_body: Dict[str, Any] = {}
            transport_fault: Optional[str] = None

            try:
                req = Request(
                    self.downstream_target_url,
                    data=encode_jcs(payload),
                    headers={
                        "Content-Type": "application/json",
                        "Idempotency-Key": rail_idempotency_key,
                        "X-AEIB-Action-CAID": action_caid,
                        "X-AEIB-Operation-ID": operation_id,
                    },
                    method="POST",
                )
                with urlopen(req, timeout=1.5) as resp:
                    target_response_code = resp.status
                    raw_resp = resp.read()
                    target_response_body = json.loads(raw_resp.decode("utf-8")) if raw_resp else {}
            except Exception as exc:
                transport_fault = "HTTP_504_GATEWAY_TIMEOUT"
                target_response_code = 504
                target_response_body = {"error": str(exc)}

            # 4. Station 2 -> 3 State Transition Handling
            if transport_fault is not None or target_response_code == 504:
                # Latch EFFECT_INDETERMINATE and lock spend in escrow
                self._indeterminate_escrow[operation_id] = amount_minor
                receipt = self._emit_signed_receipt(
                    operation_id=operation_id,
                    action_caid=action_caid,
                    disposition="EFFECT_INDETERMINATE",
                    amount_minor=amount_minor,
                    rail_idempotency_key=rail_idempotency_key,
                )
                return {
                    "action_caid": action_caid,
                    "operation_id": operation_id,
                    "receipt": receipt,
                    "rejection_code": "EFFECT_INDETERMINATE",
                    "retry_allowed": False,
                    "verdict": "INDETERMINATE_LATCHED",
                }

            # Normal success path
            receipt = self._emit_signed_receipt(
                operation_id=operation_id,
                action_caid=action_caid,
                disposition="RESOLVED_CONFIRMED",
                amount_minor=amount_minor,
                rail_idempotency_key=rail_idempotency_key,
            )
            return {
                "action_caid": action_caid,
                "operation_id": operation_id,
                "rail_idempotency_key": rail_idempotency_key,
                "receipt": receipt,
                "target_response": target_response_body,
                "verdict": "DISPATCHED",
            }

    def reconcile_indeterminate_operation(self, operation_id: str) -> Dict[str, Any]:
        """
        Single-flight out-of-band probe query to downstream target status endpoint.
        """
        with self._lock:
            if operation_id not in self._indeterminate_escrow:
                return {
                    "operation_id": operation_id,
                    "reconciled": False,
                    "status": "NOT_IN_INDETERMINATE_ESCROW",
                }

            probe_status = "UNKNOWN"
            try:
                probe_req = Request(
                    f"{self.downstream_probe_url}?operation_id={operation_id}",
                    headers={"Content-Type": "application/json"},
                    method="GET",
                )
                with urlopen(probe_req, timeout=1.5) as resp:
                    raw_data = resp.read()
                    data = json.loads(raw_data.decode("utf-8")) if raw_data else {}
                    probe_status = data.get("status", "NOT_FOUND")
            except Exception:
                probe_status = "PROBE_NETWORK_TIMEOUT"

            escrowed_amt = self._indeterminate_escrow.pop(operation_id, 0)
            if probe_status == "COMMITTED" or probe_status == "CONFIRMED":
                self._reconciled_ops[operation_id] = "RESOLVED_CONFIRMED"
                disposition = "RESOLVED_CONFIRMED"
            else:
                # Refuted downstream: release escrow back to sprint pool
                self.code_mode_gate.session_spent_minor = max(
                    0, self.code_mode_gate.session_spent_minor - escrowed_amt
                )
                self._reconciled_ops[operation_id] = "RESOLVED_REFUTED"
                disposition = "RESOLVED_REFUTED"

            receipt = self._emit_signed_receipt(
                operation_id=operation_id,
                action_caid="reconciliation-probe",
                disposition=disposition,
                amount_minor=escrowed_amt,
                rail_idempotency_key="reconciled",
            )
            return {
                "disposition": disposition,
                "operation_id": operation_id,
                "receipt": receipt,
                "reconciled": True,
            }

    def _emit_signed_receipt(
        self,
        *,
        operation_id: str,
        action_caid: str,
        disposition: str,
        amount_minor: int,
        rail_idempotency_key: str,
    ) -> Dict[str, Any]:
        import time
        now_ts = int(time.time())
        receipt_body = {
            "action_caid": action_caid,
            "amount_minor": amount_minor,
            "disposition": disposition,
            "operation_id": operation_id,
            "prev_chain_tip": self._chain_tip,
            "rail_idempotency_key": rail_idempotency_key,
            "timestamp": now_ts,
        }
        canonical_bytes = encode_jcs(receipt_body)
        entry_caid = sha256_prefixed(canonical_bytes)
        sig = self.gate_signer.sign(canonical_bytes)

        envelope = {
            **receipt_body,
            "entry_caid": entry_caid,
            "signature_b64": base64.b64encode(sig).decode("ascii"),
        }
        self._chain_tip = sha256_prefixed(encode_jcs(envelope))
        self._receipts.append(envelope)

        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(envelope) + "\n")

        return envelope

    def get_all_receipts(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._receipts)


class AEIBProductionGatewayDaemon:
    """Production Gateway Daemon lifecycle controller."""

    def __init__(self, engine: AEIBProductionGatewayEngine, host: str = "127.0.0.1", port: int = 0) -> None:
        self.engine = engine
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> int:
        handler = AEIBProductionGatewayHandler
        handler.server_engine = self.engine
        self.server = HTTPServer((self.host, self.port), handler)
        assigned_port = self.server.server_port
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        return assigned_port

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self._thread:
            self._thread.join(timeout=2.0)
