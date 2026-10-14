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
tests/test_slack_webhook_receiver.py
================================================================================
Unit & integration tests for the AEIB Live Slack Webhook Receiver & RFC 9470 Step-Up Service (Milestone 5).
"""

import sys
import time
import json
import hmac
import hashlib
import urllib.parse
import urllib.request
import pytest
from pathlib import Path
from typing import Optional

# Add project root and roadmap to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "v1.1-roadmap"))

from slack_webhook_receiver import SlackWebhookServer
from action_intelligence_brief import (
    HumanResolutionAuthorityManager,
    DECISION_REQUEST_ADDITIONAL_RECONCILIATION,
    DECISION_MARK_TARGET_FAILED,
    PROHIBITED_DECLARE_SUCCESS
)


@pytest.fixture(scope="module")
def webhook_server(tmp_path_factory):
    storage_dir = tmp_path_factory.mktemp("webhook_storage")
    auth_manager = HumanResolutionAuthorityManager(storage_path=storage_dir)
    signing_secret = "test_slack_secret_12345"
    port = 8799

    server = SlackWebhookServer(
        host="127.0.0.1",
        port=port,
        signing_secret=signing_secret,
        authority_manager=auth_manager
    )
    server.start_background()
    time.sleep(0.1)  # Ensure socket bound

    yield f"http://127.0.0.1:{port}", signing_secret, auth_manager

    server.stop()


def _make_signed_slack_post(url: str, signing_secret: str, payload_dict: dict, timestamp: Optional[int] = None):
    ts = str(timestamp or int(time.time()))
    form_data = urllib.parse.urlencode({"payload": json.dumps(payload_dict)}).encode("utf-8")
    sig_basestring = f"v0:{ts}:{form_data.decode('utf-8')}".encode("utf-8")
    sig = "v0=" + hmac.new(signing_secret.encode("utf-8"), sig_basestring, hashlib.sha256).hexdigest()

    req = urllib.request.Request(
        url,
        data=form_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig
        },
        method="POST"
    )
    return req


def test_01_health_check(webhook_server):
    base_url, _, _ = webhook_server
    resp = urllib.request.urlopen(f"{base_url}/health")
    assert resp.status == 200
    data = json.loads(resp.read().decode("utf-8"))
    assert data["status"] == "UP"


def test_02_unauthenticated_request_rejected(webhook_server):
    base_url, _, _ = webhook_server
    req = urllib.request.Request(
        f"{base_url}/slack/actions",
        data=b'{"payload": "{}"}',
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 401


def test_03_replay_attack_rejected_outside_window(webhook_server):
    base_url, signing_secret, _ = webhook_server
    stale_ts = int(time.time()) - 400  # 400s > 300s window

    payload = {
        "user": {"id": "U12345"},
        "actions": [{"action_id": "act_escalate", "value": json.dumps({"operation_id": "op_99", "action": "ESCALATE"})}]
    }
    req = _make_signed_slack_post(f"{base_url}/slack/actions", signing_secret, payload, timestamp=stale_ts)

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 401


def test_04_valid_interactive_action_burns_ticket(webhook_server):
    base_url, signing_secret, auth_mgr = webhook_server

    payload = {
        "user": {"id": "U_OPERATOR_01"},
        "actions": [
            {
                "action_id": "act_reconcile",
                "value": json.dumps({
                    "operation_id": "op_wire_881",
                    "action": DECISION_REQUEST_ADDITIONAL_RECONCILIATION
                })
            }
        ]
    }
    req = _make_signed_slack_post(f"{base_url}/slack/actions", signing_secret, payload)
    resp = urllib.request.urlopen(req)
    assert resp.status == 200

    resp_data = json.loads(resp.read().decode("utf-8"))
    assert "Resolution recorded for `op_wire_881`" in resp_data["text"]


def test_05_prohibited_action_without_evidence_rejected_fail_closed(webhook_server):
    base_url, signing_secret, _ = webhook_server

    # Operator attempts to declare confirmed with no target evidence
    payload = {
        "user": {"id": "U_OPERATOR_ROGUE"},
        "actions": [
            {
                "action_id": "act_confirm",
                "value": json.dumps({
                    "operation_id": "op_wire_882",
                    "action": PROHIBITED_DECLARE_SUCCESS,
                    "evidence_sha256": None  # Missing evidence!
                })
            }
        ]
    }
    req = _make_signed_slack_post(f"{base_url}/slack/actions", signing_secret, payload)

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 403


def test_06_rfc_9470_step_up_challenge(webhook_server):
    base_url, _, _ = webhook_server
    req = urllib.request.Request(
        f"{base_url}/step-up/challenge",
        data=json.dumps({"operation_id": "op_wire_883"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)

    assert exc_info.value.code == 401
    auth_header = exc_info.value.headers.get("WWW-Authenticate", "")
    assert "insufficient_user_authentication" in auth_header
    assert "urn:sovereign:acr:hardware-token:fido2-dual-control" in auth_header

    body = json.loads(exc_info.value.read().decode("utf-8"))
    assert body["error"] == "insufficient_user_authentication"
    assert "challenge_nonce" in body
