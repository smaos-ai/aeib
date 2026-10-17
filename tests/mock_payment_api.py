#!/usr/bin/env python3
"""Fault-Injection HTTP Target Server for AEIB Ambiguous Refund Scenario.

Simulates an upstream payment gateway that commits a mutation on POST /mutate
(or POST /v1/refunds) and then returns HTTP 504 Gateway Timeout
(faultType=http_504_after_dispatch), while exposing out-of-band authoritative
state on GET /status for single-flight Station 2 reconciliation.
Evaluated under the stated model.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict


class FaultInjectionState:
    def __init__(self) -> None:
        self.mutations: int = 0
        self.last_payload: bytes = b""
        self.last_idempotency_key: str = ""
        self.seen_keys: Dict[str, bytes] = {}


STATE = FaultInjectionState()


class FaultInjectionPaymentHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(f"[fault-target] {self.address_string()} - {format % args}\n")

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        idem_key = self.headers.get("Idempotency-Key", "")

        if idem_key and idem_key in STATE.seen_keys:
            # Idempotent replay on target: do not double-mutate
            STATE.last_payload = STATE.seen_keys[idem_key]
        else:
            STATE.mutations += 1
            STATE.last_payload = body
            if idem_key:
                STATE.seen_keys[idem_key] = body
        STATE.last_idempotency_key = idem_key

        err_payload = json.dumps(
            {
                "error": "http_504_after_dispatch",
                "detail": "Upstream gateway timeout after mutation commit",
                "mutations_recorded": STATE.mutations,
            }
        ).encode("utf-8")
        self.send_response(504)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(err_payload)))
        self.end_headers()
        self.wfile.write(err_payload)

    def do_GET(self) -> None:
        if self.path.startswith("/health"):
            payload = json.dumps({"status": "UP"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        status_str = "COMMITTED" if STATE.mutations > 0 else "NOT_FOUND"
        payload_b64 = (
            base64.b64encode(STATE.last_payload).decode("ascii")
            if STATE.mutations > 0
            else ""
        )
        body = json.dumps(
            {
                "status": status_str,
                "mutations": STATE.mutations,
                "payloadBase64": payload_b64,
                "idempotencyKey": STATE.last_idempotency_key,
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AEIB HTTP 504 Fault-Injection Payment Target Server"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    args = parser.parse_args()

    HTTPServer.allow_reuse_address = True
    server = HTTPServer((args.host, args.port), FaultInjectionPaymentHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
