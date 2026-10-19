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
src/real_external_api_target.py
================================================================================
Real Network External API Target with Independent Status Probe Support.

Provides a live HTTP service running over real kernel socket pairs:
  1. POST /api/v1/settlements: State-mutating API.
     Supports wire fault injection (e.g., commit to DB then abruptly close TCP socket).
  2. GET /api/v1/settlements/<business_key>/status: Independent status oracle probe.
     Declares `status_probe_support: true`.
"""

import http.server
import json
import socket
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple


class ExternalSettlementLedger:
    """Target-side persistent storage independent of client or gateway."""
    def __init__(self):
        self._lock = threading.Lock()
        self.records: Dict[str, Dict[str, Any]] = {}
        self.commit_counts: Dict[str, int] = {}

    def commit(self, business_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            count = self.commit_counts.get(business_key, 0) + 1
            self.commit_counts[business_key] = count
            rec = {
                "business_key": business_key,
                "payload": payload,
                "status": "COMMITTED",
                "commit_count": count,
                "committed_at": datetime.now(timezone.utc).isoformat()
            }
            self.records[business_key] = rec
            return rec

    def probe(self, business_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.records.get(business_key)

    def get_commit_count(self, business_key: str) -> int:
        with self._lock:
            return self.commit_counts.get(business_key, 0)


class SettlementHTTPHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    ledger: ExternalSettlementLedger = None
    fault_on_commit: bool = False  # If True, abruptly close connection immediately after DB commit

    def log_message(self, format, *args):
        # Silence stderr logging during benchmark runs
        pass

    def do_POST(self):
        self.close_connection = 1
        if self.path == "/api/v1/settlements":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            try:
                body = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid JSON"}')
                return

            business_key = body.get("business_key")
            if not business_key:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Missing business_key"}')
                return

            # 1. Commit to external target ledger first
            rec = self.ledger.commit(business_key, body)

            # 2. If fault injected: simulate TCP drop after commit (e.g. server crash or socket reset)
            if self.fault_on_commit:
                try:
                    self.connection.close()
                except OSError:
                    pass
                return

            # Nominal response
            resp_bytes = json.dumps({
                "status": "COMMITTED",
                "business_key": business_key,
                "commit_count": rec["commit_count"],
                "status_probe_support": True
            }).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        self.close_connection = 1
        # Endpoint: /api/v1/settlements/<business_key>/status
        if self.path.startswith("/api/v1/settlements/") and self.path.endswith("/status"):
            parts = self.path.split("/")
            # ["", "api", "v1", "settlements", "<business_key>", "status"]
            if len(parts) == 6:
                business_key = parts[4]
                rec = self.ledger.probe(business_key)
                if rec:
                    resp_bytes = json.dumps({
                        "status_probe_support": True,
                        "business_key": business_key,
                        "status": rec["status"],
                        "commit_count": rec["commit_count"],
                        "committed_at": rec["committed_at"]
                    }).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(resp_bytes)))
                    self.end_headers()
                    self.wfile.write(resp_bytes)
                    return
                else:
                    resp_bytes = json.dumps({
                        "status_probe_support": True,
                        "business_key": business_key,
                        "status": "NOT_FOUND",
                        "commit_count": 0
                    }).encode("utf-8")
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(resp_bytes)))
                    self.end_headers()
                    self.wfile.write(resp_bytes)
                    return

        self.send_response(404)
        self.end_headers()


class LiveTargetClient:
    """
    HTTP client for LiveTargetServer running over real kernel socketpair transports.
    Zero-egress compliant and functions completely within isolated execution sandboxes.
    """
    def __init__(self, ledger: ExternalSettlementLedger):
        self.ledger = ledger
        self.fault_on_commit = False

    def set_fault_injection(self, fault_on: bool):
        self.fault_on_commit = fault_on

    def post_json(self, path: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        client_sock, server_sock = socket.socketpair()
        try:
            handler_cls = type("Handler", (SettlementHTTPHandler,), {
                "ledger": self.ledger,
                "fault_on_commit": self.fault_on_commit
            })

            def run_server():
                try:
                    handler_cls(server_sock, ("127.0.0.1", 0), None)
                finally:
                    try:
                        server_sock.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
                    server_sock.close()

            t = threading.Thread(target=run_server)
            t.start()

            body_bytes = json.dumps(payload).encode("utf-8")
            req_data = (
                f"POST {path} HTTP/1.0\r\n"
                f"Host: localhost\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body_bytes)}\r\n\r\n"
            ).encode("utf-8") + body_bytes
            client_sock.sendall(req_data)
            client_sock.shutdown(socket.SHUT_WR)

            chunks = []
            while True:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            t.join()

            raw_resp = b"".join(chunks).decode("utf-8")
            if not raw_resp:
                raise ConnectionResetError("Remote server closed socket prematurely (injected post-commit wire drop).")

            parts = raw_resp.split("\r\n\r\n", 1)
            headers_part = parts[0]
            body_part = parts[1] if len(parts) > 1 else ""
            status_line = headers_part.splitlines()[0]
            status_code = int(status_line.split(" ")[1])
            data = json.loads(body_part) if body_part else {}
            return status_code, data
        finally:
            client_sock.close()

    def get_json(self, path: str) -> Tuple[int, Dict[str, Any]]:
        client_sock, server_sock = socket.socketpair()
        try:
            handler_cls = type("Handler", (SettlementHTTPHandler,), {
                "ledger": self.ledger,
                "fault_on_commit": False
            })

            def run_server():
                try:
                    handler_cls(server_sock, ("127.0.0.1", 0), None)
                finally:
                    try:
                        server_sock.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
                    server_sock.close()

            t = threading.Thread(target=run_server)
            t.start()

            req_data = f"GET {path} HTTP/1.0\r\nHost: localhost\r\n\r\n".encode("utf-8")
            client_sock.sendall(req_data)
            client_sock.shutdown(socket.SHUT_WR)

            chunks = []
            while True:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            t.join()

            raw_resp = b"".join(chunks).decode("utf-8")
            if not raw_resp:
                raise ConnectionResetError("Remote server closed connection unexpectedly.")

            parts = raw_resp.split("\r\n\r\n", 1)
            headers_part = parts[0]
            body_part = parts[1] if len(parts) > 1 else ""
            status_line = headers_part.splitlines()[0]
            status_code = int(status_line.split(" ")[1])
            data = json.loads(body_part) if body_part else {}
            return status_code, data
        finally:
            client_sock.close()
