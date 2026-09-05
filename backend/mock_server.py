#!/usr/bin/env python3
"""
Mock HTTP backend for STAR Protocol testing (zero dependencies).
Uses Python's built-in http.server module.

Run: python3 backend/mock_server.py
Listens on: http://127.0.0.1:8000
"""

import json
import time
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from typing import Dict, Any

# In-memory store for active workflows
workflows: Dict[str, Dict[str, Any]] = {}


class STARHandler(BaseHTTPRequestHandler):
    """HTTP request handler for STAR API endpoints."""

    def do_GET(self):
        """Handle GET requests."""
        path = urlparse(self.path).path

        if path == "/api/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {"status": "healthy", "timestamp": int(time.time())}
            self.wfile.write(json.dumps(response).encode())

        elif path.startswith("/api/traces/"):
            trace_id = path.split("/")[-1]
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {
                "trace_id": trace_id,
                "status": "executing",
                "spans": [
                    {
                        "span_id": f"span-{hashlib.sha256('classification'.encode()).hexdigest()[:8]}",
                        "span_type": "policy_classification",
                        "name": "Risk Classification Engine",
                        "status": "SUCCESS",
                    }
                ],
                "merkle_root": hashlib.sha256(f"{trace_id}:complete".encode()).hexdigest(),
            }
            self.wfile.write(json.dumps(response).encode())

        elif path == "/api/rce/stream":
            time.sleep(0.3)
            self.send_response(200)
            self.send_header("Content-type", "text/event-stream")
            self.end_headers()
            workflow_id = f"workflow-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}"
            event = {
                "event": "veto_halt",
                "payload": {
                    "workflow_id": workflow_id,
                    "layer": 7,
                    "severity": "block",
                    "reason": "Basel III CAR breach detected",
                },
            }
            self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests."""
        path = urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        payload = json.loads(body) if body else {}

        if path == "/api/execute":
            mandate_id = f"mandate-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}"
            trace_id = f"trace-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}"
            workflows[mandate_id] = {
                "trace_id": trace_id,
                "payload": payload,
                "status": "executing",
                "created_at": int(time.time()),
            }
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {
                "mandate_id": mandate_id,
                "trace_id": trace_id,
                "status": "ready",
            }
            self.wfile.write(json.dumps(response).encode())

        elif path == "/api/rce/decision":
            receipt_id = f"rcpt-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}"
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {
                "receipt_id": receipt_id,
                "status": "APPROVED_WITH_OVERRIDE",
                "decision": payload.get("decision"),
                "signature": f"sig:ed25519:{hashlib.sha256(receipt_id.encode()).hexdigest()[:32]}",
            }
            self.wfile.write(json.dumps(response).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


if __name__ == "__main__":
    print("🚀 Starting STAR mock backend on http://127.0.0.1:8000")
    print("   Endpoints: /api/health, /api/execute, /api/traces/{id}, /api/rce/stream, /api/rce/decision")
    server = HTTPServer(("127.0.0.1", 8000), STARHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Backend stopped")
        server.server_close()
