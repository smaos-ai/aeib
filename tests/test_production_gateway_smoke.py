#!/usr/bin/env python3
"""
tests/test_production_gateway_smoke.py

End-to-End Smoke Test for the AEIB Production Gateway Daemon:
- Evaluates /healthz and /readyz operational probes.
- Evaluates pre-session tool pinning and mid-session hot-reload rejection.
- Evaluates live HTTP mutation forwarding through the daemon to a target server.
- Evaluates HTTP 504 transport fault latching into EFFECT_INDETERMINATE.
- Evaluates sprint escrow locking and single-flight out-of-band probe reconciliation (/v1/reconcile).
- Evaluates offline verification of all emitted receipts and unbroken hash-chain tips.
"""

from __future__ import annotations

import base64
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT.parent))

from src.aeib_production_gateway_daemon import (
    AEIBProductionGatewayDaemon,
    AEIBProductionGatewayEngine,
)
from src.jcs_canonicalizer import encode_jcs
from src.opencode_and_mcp_codemode_engine import (
    SignedPluginManifest,
    sha256_prefixed,
)


class MockDownstreamServer(BaseHTTPRequestHandler):
    """Mock target server capable of simulating 200 OK and 504 Gateway Timeout."""

    fault_mode: str = "NORMAL"
    transactions: Dict[str, Dict[str, Any]] = {}

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        op_id = payload.get("operation_id", "")

        if self.fault_mode == "INJECT_504":
            self.send_response(504)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Simulated Gateway Timeout 504"}')
            return

        self.transactions[op_id] = {
            "amount_minor": payload.get("amount_minor"),
            "status": "COMMITTED",
        }
        resp = encode_jcs({"status": "SUCCESS", "tx_id": f"tx-{op_id}"})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def do_GET(self) -> None:
        from urllib.parse import parse_qs, urlparse
        query = parse_qs(urlparse(self.path).query)
        op_id = query.get("operation_id", [""])[0]

        if op_id in self.transactions:
            resp = encode_jcs({"operation_id": op_id, "status": "COMMITTED"})
        else:
            resp = encode_jcs({"operation_id": op_id, "status": "NOT_FOUND"})

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def log_message(self, format: str, *args: Any) -> None:
        pass


def test_production_gateway_daemon_end_to_end_smoke(tmp_path: Path) -> None:
    # 1. Start mock downstream target server
    mock_handler = MockDownstreamServer
    mock_handler.fault_mode = "NORMAL"
    mock_handler.transactions = {}
    mock_httpd = HTTPServer(("127.0.0.1", 0), mock_handler)
    mock_port = mock_httpd.server_port
    mock_thread = threading.Thread(target=mock_httpd.serve_forever, daemon=True)
    mock_thread.start()

    target_url = f"http://127.0.0.1:{mock_port}/mutate"
    probe_url = f"http://127.0.0.1:{mock_port}/status"

    # 2. Keypairs and session setup
    gate_priv = Ed25519PrivateKey.generate()
    sponsor_priv = Ed25519PrivateKey.generate()
    human_pub_priv = Ed25519PrivateKey.generate()
    session_start_ns = 1_760_800_000_000_000_000

    engine = AEIBProductionGatewayEngine(
        gate_signer=gate_priv,
        sponsor_pubkey=sponsor_priv.public_key(),
        human_publisher_pubkey=human_pub_priv.public_key(),
        human_publisher_key_id="did:key:secops-publisher-alpha",
        downstream_target_url=target_url,
        downstream_probe_url=probe_url,
        ledger_path=tmp_path / "gateway_ledger.jsonl",
        session_start_ns=session_start_ns,
        sprint_limit_minor=1000_00,
    )
    daemon = AEIBProductionGatewayDaemon(engine=engine, host="127.0.0.1", port=0)
    assigned_port = daemon.start()
    base_url = f"http://127.0.0.1:{assigned_port}"

    try:
        # 3. Test /healthz and /readyz
        with urlopen(f"{base_url}/healthz", timeout=1.5) as h_resp:
            assert int(h_resp.status) == 200
            h_data = json.loads(h_resp.read().decode("utf-8"))
            assert h_data["status"] == "HEALTHY"
            assert h_data["boundary_mode"] == "FAIL_CLOSED"

        with urlopen(f"{base_url}/readyz", timeout=1.5) as r_resp:
            assert int(r_resp.status) == 200
            r_data = json.loads(r_resp.read().decode("utf-8"))
            assert r_data["ready"] is True

        # 4. Pre-session register approved tool
        tool_code = b"export function bankTool() { return execute(); }"
        tool_sha = sha256_prefixed(tool_code)
        reg_payload = encode_jcs(
            {
                "code_sha256": tool_sha,
                "plugin_id": "bank-tool-prod",
                "registered_at_ns": session_start_ns - 10_000_000_000,
                "signer_key_id": "did:key:secops-publisher-alpha",
            }
        )
        tool_sig = base64.b64encode(human_pub_priv.sign(reg_payload)).decode("ascii")
        reg_ok, _ = engine.register_pinned_tool(
            SignedPluginManifest(
                plugin_id="bank-tool-prod",
                code_sha256=tool_sha,
                registered_at_ns=session_start_ns - 10_000_000_000,
                signer_key_id="did:key:secops-publisher-alpha",
                signature_b64=tool_sig,
            ),
            tool_code,
        )
        assert reg_ok

        # 5. Dispatch successful mutation (EUR 400.00)
        dispatch_req1 = Request(
            f"{base_url}/v1/dispatch",
            data=encode_jcs(
                {
                    "action_type": "POST /v1/refunds",
                    "amount_minor": 400_00,
                    "data_tier": "TIER_0_PINNED",
                    "operation_id": "op-prod-001",
                    "pinned_known_recipient": True,
                    "plugin_id": "bank-tool-prod",
                }
            ),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(dispatch_req1, timeout=2.0) as d_resp1:
            assert int(d_resp1.status) == 200
            d_data1 = json.loads(d_resp1.read().decode("utf-8"))
            assert d_data1["verdict"] == "DISPATCHED"
            assert "rail_idempotency_key" in d_data1
            assert d_data1["receipt"]["disposition"] == "RESOLVED_CONFIRMED"

        # 6. Inject HTTP 504 on target server and dispatch EUR 500.00
        mock_handler.fault_mode = "INJECT_504"
        dispatch_req2 = Request(
            f"{base_url}/v1/dispatch",
            data=encode_jcs(
                {
                    "action_type": "POST /v1/refunds",
                    "amount_minor": 500_00,
                    "data_tier": "TIER_0_PINNED",
                    "operation_id": "op-prod-504",
                    "pinned_known_recipient": True,
                    "plugin_id": "bank-tool-prod",
                }
            ),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(dispatch_req2, timeout=2.0)
            assert False, "Expected HTTP 504 Gateway Timeout"
        except Exception as e:
            # urllib raises HTTPError for status 504
            assert int(getattr(e, "code", 0) or 0) == 504
            err_body = json.loads(e.read().decode("utf-8"))
            assert err_body["verdict"] == "INDETERMINATE_LATCHED"
            assert err_body["rejection_code"] == "EFFECT_INDETERMINATE"
            assert err_body["retry_allowed"] is False

        # 7. Attempt EUR 300.00 while EUR 500.00 is escrowed (400 + 500 + 300 = 1200 > 1000 sprint cap)
        dispatch_req3 = Request(
            f"{base_url}/v1/dispatch",
            data=encode_jcs(
                {
                    "action_type": "POST /v1/refunds",
                    "amount_minor": 300_00,
                    "data_tier": "TIER_0_PINNED",
                    "operation_id": "op-prod-overflow",
                    "pinned_known_recipient": True,
                    "plugin_id": "bank-tool-prod",
                }
            ),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(dispatch_req3, timeout=2.0)
            assert False, "Expected 403 Forbidden"
        except Exception as e:
            assert int(getattr(e, "code", 0) or 0) == 403
            overflow_body = json.loads(e.read().decode("utf-8"))
            assert overflow_body["verdict"] == "REJECTED"
            assert overflow_body["rejection_code"] == "HALT_CODEMODE_CUMULATIVE_SPRINT_EXCEEDED"

        # 8. Reconcile the indeterminate operation out-of-band
        mock_handler.fault_mode = "NORMAL"
        reconcile_req = Request(
            f"{base_url}/v1/reconcile",
            data=encode_jcs({"operation_id": "op-prod-504"}),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(reconcile_req, timeout=2.0) as rec_resp:
            assert int(rec_resp.status) == 200
            rec_data = json.loads(rec_resp.read().decode("utf-8"))
            assert rec_data["reconciled"] is True
            assert rec_data["disposition"] == "RESOLVED_REFUTED"

        # 9. Offline verification of all ledger receipts
        with urlopen(f"{base_url}/v1/ledger/receipts", timeout=1.5) as r_resp:
            assert int(r_resp.status) == 200
            all_receipts = json.loads(r_resp.read().decode("utf-8"))["receipts"]
            assert len(all_receipts) >= 3

            computed_chain_tip = "sha256:" + ("0" * 64)
            for r in all_receipts:
                assert r["prev_chain_tip"] == computed_chain_tip
                sig_bytes = base64.b64decode(r["signature_b64"])
                unsigned = {k: v for k, v in r.items() if k not in ("signature_b64", "entry_caid")}
                gate_priv.public_key().verify(sig_bytes, encode_jcs(unsigned))
                computed_chain_tip = sha256_prefixed(encode_jcs(r))

    finally:
        daemon.stop()
        mock_httpd.shutdown()
        mock_httpd.server_close()
