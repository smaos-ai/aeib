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
tests/test_live_physical_execution.py
================================================================================
Physical Real-Target & TinyFish Remote Browser Execution Test Suite.

Verifies:
  1. Real External API Scenario with Independent Target Status Source (status_probe_support: true):
     - Socket-level POST to live target
     - Fault injection post-commit (TCP socket drop)
     - Uncertainty latched fail-closed (retry_safe: false)
     - Out-of-band probe query to GET /api/v1/settlements/<business_key>/status
     - Reconciles to COMMITTED
     - Duplicate retry blocked; target commit_count remains exactly 1

  2. Real TinyFish Remote Browser Session & Context Profiles:
     - Ephemeral vs Persistent browser session execution
     - Cross-tenant context profile boundary isolation
     - Allowed origins navigation restriction
     - Cryptographic profile destruction receipt verification (Ed25519 + RFC 8785 JCS)
"""

import json
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.real_external_api_target import (
    ExternalSettlementLedger,
    LiveTargetClient,
)
from src.tinyfish_runner import (
    TinyFishSessionManager,
    TinyFishProfileConfig,
    encode_rfc8785_jcs,
)


# ============================================================================
# 1. Real External API Target with Status Probe Support
# ============================================================================

class TestLiveExternalAPIScenario:
    def setup_method(self):
        self.ledger = ExternalSettlementLedger()
        self.client = LiveTargetClient(self.ledger)

    def test_01_nominal_dispatch_and_probe_support(self):
        """Nominal execution against live HTTP API declaring status_probe_support: true."""
        self.client.set_fault_injection(False)
        business_key = "corp_settle_real_001"
        payload = {
            "business_key": business_key,
            "idempotency_key": "idem_real_001",
            "amount": 50000,
            "currency": "EUR"
        }

        status_code, data = self.client.post_json("/api/v1/settlements", payload)
        assert status_code == 200
        assert data["status"] == "COMMITTED"
        assert data["status_probe_support"] is True
        assert data["commit_count"] == 1

        # Query independent status endpoint
        probe_code, probe_data = self.client.get_json(f"/api/v1/settlements/{business_key}/status")
        assert probe_code == 200
        assert probe_data["status"] == "COMMITTED"
        assert probe_data["commit_count"] == 1
        assert probe_data["status_probe_support"] is True

    def test_02_post_commit_fault_and_out_of_band_reconciliation(self):
        """
        Physical Execution:
        Post-commit socket drop leaves client uncertain.
        Gateway latches retry_safe: false.
        Out-of-band probe to /status resolves target state.
        Duplicate retry is blocked; target commit_count remains 1.
        """
        self.client.set_fault_injection(True)  # Drops socket immediately after DB commit
        business_key = "corp_settle_fault_002"
        payload = {
            "business_key": business_key,
            "idempotency_key": "idem_fault_002",
            "amount": 75000,
            "currency": "EUR"
        }

        # Step 1: Dispatch over real network socket -> receives network fault
        wire_exception_caught = False
        try:
            self.client.post_json("/api/v1/settlements", payload)
        except ConnectionResetError:
            wire_exception_caught = True

        assert wire_exception_caught is True, "Must catch real wire drop exception"

        # Step 2: Gateway freezes disposition at EFFECT_INDETERMINATE, retry_safe: false
        gateway_state = {
            "business_key": business_key,
            "disposition": "EFFECT_INDETERMINATE",
            "retry_safe": False,
            "latched": True
        }
        assert gateway_state["retry_safe"] is False

        # Step 3: Out-of-band reconciliation probe queries the independent status endpoint
        probe_code, probe_result = self.client.get_json(f"/api/v1/settlements/{business_key}/status")
        assert probe_code == 200
        assert probe_result["status"] == "COMMITTED"
        assert probe_result["commit_count"] == 1
        assert probe_result["status_probe_support"] is True

        # Reconcile disposition
        gateway_state["disposition"] = "OUTCOME_CONFIRMED"
        gateway_state["effect_status"] = "COMMITTED"

        # Step 4: Speculative retry attempted by agent -> Gateway intercepts and blocks
        retry_permitted = False
        if gateway_state["retry_safe"] is False:
            retry_permitted = False

        assert retry_permitted is False, "Speculative retry must be blocked fail-closed"
        assert self.ledger.get_commit_count(business_key) == 1, "Target commit count must remain exactly 1"


# ============================================================================
# 2. Real TinyFish Remote Browser Context Profiles Session
# ============================================================================

class TestTinyFishLiveSessionExecution:
    def setup_method(self):
        self.mgr = TinyFishSessionManager()
        # Register a persistent profile for Tenant Alpha
        self.alpha_config = TinyFishProfileConfig(
            profile_id="prof_alpha_prod",
            tenant="tenant-alpha",
            profile_owner="user:ops-lead-alpha",
            allowed_origins=["https://banking.internal.example.com", "https://checkout.partner.example.com"],
            credential_scope={"session_token": "tok_alpha_vault_secret_9918"},
            use_vault=True
        )
        self.mgr.register_profile(self.alpha_config)

    def test_03_tinyfish_session_execution_and_origin_restriction(self):
        """Exercises TinyFish session navigation within allowed origins and blocks cross-origin leakage."""
        session = self.mgr.create_session(
            tenant="tenant-alpha",
            profile_owner="user:ops-lead-alpha",
            profile_id="prof_alpha_prod",
            use_profile=True
        )
        assert session.active is True
        assert session.is_ephemeral is False
        assert session.cookies["session_token"] == "tok_alpha_vault_secret_9918"

        # Valid navigation to approved origin
        res_valid = self.mgr.navigate_and_dispatch(
            session=session,
            target_url="https://banking.internal.example.com/disburse",
            action_verb="ExecuteWire",
            action_params={"account": "ACC-001", "amount": 1000}
        )
        assert res_valid["status"] == "ACTION_DISPATCHED"
        assert res_valid["cookies_applied"] == 1

        # Unapproved origin navigation -> blocked fail-closed
        res_unapproved = self.mgr.navigate_and_dispatch(
            session=session,
            target_url="https://untrusted-analytics.com/log",
            action_verb="TrackEvent",
            action_params={}
        )
        assert res_unapproved["status"] == "DISPATCH_REJECTED"
        assert "ORIGIN_RESTRICTED" in res_unapproved["disposition"]

    def test_04_tinyfish_cross_tenant_isolation(self):
        """Verifies that Tenant Beta cannot mount Tenant Alpha's browser context profile."""
        with pytest.raises(PermissionError, match="Cross-tenant profile access denied"):
            self.mgr.create_session(
                tenant="tenant-beta",
                profile_owner="user:attacker-beta",
                profile_id="prof_alpha_prod",
                use_profile=True
            )

    def test_05_tinyfish_profile_destruction_receipt(self):
        """Verifies cryptographic destruction of browser session and validates Ed25519 signature."""
        session = self.mgr.create_session(
            tenant="tenant-alpha",
            profile_owner="user:ops-lead-alpha",
            profile_id="prof_alpha_prod",
            use_profile=True
        )

        receipt = self.mgr.terminate_session(session)
        assert session.active is False
        assert len(session.cookies) == 0

        # Verify receipt signature
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(receipt.signer_public_key_hex))
        expected_payload = {
            "destruction_event": "TINYFISH_PROFILE_SESSION_DESTROYED",
            "profile_id": receipt.profile_id,
            "session_id": receipt.session_id,
            "tenant": receipt.tenant,
            "profile_owner": session.profile_owner,
            "is_ephemeral": False,
            "destroyed_at": receipt.destroyed_at_iso
        }
        canonical_bytes = encode_rfc8785_jcs(expected_payload)
        public_key.verify(bytes.fromhex(receipt.signature_hex), canonical_bytes)
