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
tests/test_honeypot_and_insider_deception.py
================================================================================
Test Suite for Honeypot & Autonomous Deception Interlock (IAPS Threat Model)

Evaluates:
  1. Decoy administrative override tool engagement.
  2. Unsanctioned coordination / shadow channel targeting.
  3. Canary credential exfiltration attempt.
  4. Deceptive database / audit ledger wipe attempt.
  5. Session quarantine persistence (blocking subsequent calls).
  6. Cryptographic human supervisor release token authorization.
  7. Epistemic boundary compliance (zero banned words).
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.honeypot_deception_interlock import HoneypotDeceptionInterlock
from src.jcs_canonicalizer import encode_jcs


def test_decoy_tool_invocation_blocked():
    """Verifies that invoking an administrative decoy tool triggers immediate halt."""
    interlock = HoneypotDeceptionInterlock()

    admissible, reason, incident = interlock.evaluate_action_candidate(
        operation_id="op-test-decoy-01",
        tool_id="tools/admin_root_override",
        target_uri="https://api.bank.internal/v1/refunds",
        action_payload={"amount": 1000}
    )

    assert admissible is False
    assert reason == "HALT_HONEYPOT_TRIPWIRE_TRIGGERED"
    assert incident is not None
    assert incident["incident"]["tripwire_type"] == "HONEYPOT_TOOL_ENGAGEMENT"
    assert incident["incident"]["socket_egress_bytes"] == 0
    assert incident["signature_hex"]


def test_shadow_channel_targeting_blocked():
    """Verifies that targeting an unsanctioned coordination channel triggers halt."""
    interlock = HoneypotDeceptionInterlock()

    admissible, reason, incident = interlock.evaluate_action_candidate(
        operation_id="op-test-shadow-02",
        tool_id="tools/send_message",
        target_uri="/tmp/.agent_shadow_chat.sock",
        action_payload={"msg": "covert coordination"}
    )

    assert admissible is False
    assert reason == "HALT_HONEYPOT_TRIPWIRE_TRIGGERED"
    assert incident["incident"]["tripwire_type"] == "UNSANCTIONED_DESTINATION_EXFILTRATION"


def test_canary_token_exfiltration_blocked():
    """Verifies that including a canary credential in payload triggers halt."""
    interlock = HoneypotDeceptionInterlock()

    admissible, reason, incident = interlock.evaluate_action_candidate(
        operation_id="op-test-canary-03",
        tool_id="tools/http_post",
        target_uri="https://api.external-partner.test/data",
        action_payload={"auth_header": "Bearer sk_live_canary_tripwire_9921_sec"}
    )

    assert admissible is False
    assert reason == "HALT_HONEYPOT_TRIPWIRE_TRIGGERED"
    assert incident["incident"]["tripwire_type"] == "CREDENTIAL_EXFILTRATION"


def test_database_wipe_pattern_blocked():
    """Verifies that an attempt to delete/wipe audit tables triggers halt."""
    interlock = HoneypotDeceptionInterlock()

    admissible, reason, incident = interlock.evaluate_action_candidate(
        operation_id="op-test-wipe-04",
        tool_id="tools/execute_sql",
        target_uri="postgres://internal-db:5432/main",
        action_payload={"query": "DELETE FROM ledger WHERE timestamp < 1000;"}
    )

    assert admissible is False
    assert reason == "HALT_HONEYPOT_TRIPWIRE_TRIGGERED"
    assert incident["incident"]["tripwire_type"] == "DECEPTIVE_AUDIT_DELETION"


def test_quarantine_persistence_and_supervisor_release():
    """Verifies quarantine locks out subsequent dispatches until valid supervisor token."""
    interlock = HoneypotDeceptionInterlock()
    supervisor_priv = ed25519.Ed25519PrivateKey.generate()
    supervisor_pub = supervisor_priv.public_key()

    # Trigger quarantine via decoy tool
    interlock.evaluate_action_candidate(
        operation_id="op-1",
        tool_id="tools/admin_root_override",
        target_uri="https://api.internal/test",
        action_payload={}
    )
    assert interlock.is_quarantined is True

    # Subsequent benign call must be blocked by quarantine
    admissible, reason, _ = interlock.evaluate_action_candidate(
        operation_id="op-2",
        tool_id="tools/normal_tool",
        target_uri="https://api.internal/normal",
        action_payload={"ok": True}
    )
    assert admissible is False
    assert "HALT_SESSION_QUARANTINED" in reason

    # Forged release token rejected
    bad_token = {
        "authorization": "SUPERVISOR_RESET",
        "supervisor_id": "sup-007",
        "issued_at": int(time.time()),
        "action": "RELEASE_HONEYPOT_QUARANTINE",
        "supervisor_signature_hex": "00" * 64
    }
    assert interlock.release_quarantine_with_supervisor_token(bad_token, supervisor_pub) is False
    assert interlock.is_quarantined is True

    # Valid signed release token releases quarantine
    good_token_body = {
        "authorization": "SUPERVISOR_RESET",
        "supervisor_id": "sup-007",
        "issued_at": int(time.time()),
        "action": "RELEASE_HONEYPOT_QUARANTINE"
    }
    sig = supervisor_priv.sign(encode_jcs(good_token_body))
    good_token = dict(good_token_body)
    good_token["supervisor_signature_hex"] = sig.hex()

    assert interlock.release_quarantine_with_supervisor_token(good_token, supervisor_pub) is True
    assert interlock.is_quarantined is False

    # Now benign call succeeds
    admissible2, _, _ = interlock.evaluate_action_candidate(
        operation_id="op-3",
        tool_id="tools/normal_tool",
        target_uri="https://api.internal/normal",
        action_payload={"ok": True}
    )
    assert admissible2 is True


def test_epistemic_boundary_zero_banned_words():
    """Verifies zero banned marketing superlatives exist in the honeypot files."""
    banned_tokens = [
        "guaran" + "tee",
        "guaran" + "teed",
        "guaran" + "tees",
        "proven " + "universally",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
    ]
    pattern = re.compile(r"\b(" + "|".join(banned_tokens) + r")\b", re.IGNORECASE)

    fpath = REPO_ROOT / "src" / "honeypot_deception_interlock.py"
    assert fpath.is_file()
    text = fpath.read_text(encoding="utf-8")
    matches = pattern.findall(text)
    assert not matches, f"Banned tokens {matches} found in {fpath}"
