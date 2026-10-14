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
v1.1-roadmap/slack_webhook_receiver.py
================================================================================
AEIB Live Webhook Receiver & RFC 9470 Step-Up Service (Milestone 5 Prototype).

Receives interactive webhook clicks from SecOps operators in Slack, enforcing:
  1. HMAC-SHA256 signature verification over exact request body.
  2. 300-second replay window rejection.
  3. Single-use resolution authority ticket issuance and burn.
  4. RFC 9470 Step-Up Authentication challenge parameter generation.
  5. Zero unvetted dependencies (Python standard library only).
"""

import sys
import json
import time
import urllib.parse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Add repo root and roadmap to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "v1.1-roadmap"))

from action_intelligence_brief import (
    SlackBlockKitAdapter,
    HumanResolutionAuthorityManager,
    HumanResolutionAuthority,
    ProhibitedDecisionError,
    TicketAlreadyBurnedError,
    TicketExpiredError,
    InvalidSignatureError,
    DECISION_ESCALATE,
    DECISION_MARK_TARGET_FAILED,
    DECISION_REQUEST_ADDITIONAL_RECONCILIATION,
    PROHIBITED_DECLARE_SUCCESS
)


class SlackWebhookRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler processing Slack Block Kit actions and Step-Up challenges.
    """
    signing_secret: str = "default_dev_slack_secret"
    authority_manager: Optional[HumanResolutionAuthorityManager] = None
    last_processed_resolution: Optional[Dict[str, Any]] = None

    def log_message(self, format, *args):
        # Suppress noisy default stdio logs during automated test runs
        pass

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "UP", "version": "v1.1-slack-receiver"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        if self.path == "/slack/actions":
            self._handle_slack_action(raw_body)
        elif self.path == "/step-up/challenge":
            self._handle_step_up_challenge(raw_body)
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_slack_action(self, raw_body: bytes):
        ts_header = self.headers.get("X-Slack-Request-Timestamp", "")
        sig_header = self.headers.get("X-Slack-Signature", "")

        # 1. Enforce HMAC-SHA256 signature and 300s window verification
        headers_dict = {str(k): str(v) for k, v in self.headers.items()}
        is_valid, err_msg = SlackBlockKitAdapter.verify_slack_request(
            headers=headers_dict,
            raw_body=raw_body,
            signing_secret=self.signing_secret
        )
        if not is_valid:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "UNAUTHORIZED_WEBHOOK", "reason": err_msg}).encode("utf-8"))
            return

        # 2. Parse payload (Slack transmits application/x-www-form-urlencoded with 'payload' param)
        try:
            body_str = raw_body.decode("utf-8")
            parsed_qs = urllib.parse.parse_qs(body_str)
            if "payload" in parsed_qs:
                payload_json = json.loads(parsed_qs["payload"][0])
            else:
                payload_json = json.loads(body_str)
        except Exception as exc:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "MALFORMED_PAYLOAD", "detail": str(exc)}).encode("utf-8"))
            return

        # 3. Extract operator interaction action
        user_info = payload_json.get("user", {})
        operator_id = user_info.get("id", "operator_unknown")
        actions = payload_json.get("actions", [])

        if not actions:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "NO_ACTION_IN_PAYLOAD"}).encode("utf-8"))
            return

        action_data = actions[0]
        action_val_str = action_data.get("value", "{}")
        try:
            action_val = json.loads(action_val_str)
        except Exception:
            action_val = {"action": action_data.get("action_id")}

        operation_id = action_val.get("operation_id", "op_unknown")
        decision = action_val.get("action", DECISION_ESCALATE)
        evidence_digest = action_val.get("evidence_sha256")

        # 4. Burn authority ticket via HumanResolutionAuthorityManager
        if self.authority_manager:
            try:
                ticket = self.authority_manager.issue_authority(
                    operation_id=operation_id,
                    approver_principal=f"slack:user:{operator_id}",
                    decision=decision
                )
                has_target_evidence = bool(evidence_digest)
                burn_ok, burn_reason = self.authority_manager.consume_authority(
                    ticket=ticket,
                    target_evidence_supports_failure=has_target_evidence
                )
                SlackWebhookRequestHandler.last_processed_resolution = {
                    "operation_id": operation_id,
                    "ticket_id": ticket.ticket_id,
                    "decision": decision,
                    "burned": burn_ok,
                    "operator": f"slack:user:{operator_id}"
                }
            except (ProhibitedDecisionError, ValueError, Exception) as exc:
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "DENIED",
                    "reason": str(exc),
                    "operation_id": operation_id
                }).encode("utf-8"))
                return

        # 5. Success response (acknowledging interaction to Slack)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = {
            "response_type": "ephemeral",
            "text": f"✅ Resolution recorded for `{operation_id}`: decision `{decision}` applied."
        }
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def _handle_step_up_challenge(self, raw_body: bytes):
        """
        Emits RFC 9470 Step-Up challenge parameters.
        """
        try:
            req_data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            req_data = {}

        operation_id = req_data.get("operation_id", "op_default")
        acr_values = "urn:sovereign:acr:hardware-token:fido2-dual-control"

        challenge = {
            "error": "insufficient_user_authentication",
            "error_description": "Transaction exceeds automated ceiling; human step-up required.",
            "acr_values": acr_values,
            "max_age": 300,
            "challenge_nonce": f"nonce_{int(time.time())}_{operation_id[:8]}"
        }

        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.send_header("WWW-Authenticate", f'Bearer error="insufficient_user_authentication", acr_values="{acr_values}", max_age=300')
        self.end_headers()
        self.wfile.write(json.dumps(challenge).encode("utf-8"))


class SlackWebhookServer:
    """
    Testable wrapper to run the webhook receiver in background or foreground.
    """
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8766,
        signing_secret: str = "dev_secret",
        authority_manager: Optional[HumanResolutionAuthorityManager] = None
    ):
        self.host = host
        self.port = port
        SlackWebhookRequestHandler.signing_secret = signing_secret
        SlackWebhookRequestHandler.authority_manager = authority_manager
        self.httpd = HTTPServer((self.host, self.port), SlackWebhookRequestHandler)
        self._thread: Optional[threading.Thread] = None

    def start_background(self):
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)
