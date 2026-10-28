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

r"""
test_confused_deputy_redaction.py — Acceptance Test AT51 (Credential Redaction Defense)
Evaluates credential sanitization profile (strict_auth_strip) to prevent
confused deputy credential laundering into audit trails or CAID digests (CVE-2026-14540).
"""

import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.aeib_gateway_adapter import AEIBGatewayAdapter, redact_sensitive_credentials


class TestConfusedDeputyRedactionAT51:
    def setup_method(self):
        self.adapter = AEIBGatewayAdapter()

    def test_stolen_bearer_token_and_jwt_are_sanitized_from_caid(self):
        # Raw malicious payload containing laundered credentials
        raw_payload = {
            "account_id": "ACC-1234",
            "amount": 50000.0,
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.stolen_token_signature",
            "metadata": {
                "user_session_token": "sk-proj-secretKey1234567890abcdef",
            },
        }

        # Redaction must scrub secrets
        clean_payload = redact_sensitive_credentials(raw_payload)
        assert clean_payload["Authorization"] == "[REDACTED_CREDENTIAL]"
        assert clean_payload["metadata"]["user_session_token"] == "[REDACTED_CREDENTIAL]"
        assert "stolen_token_signature" not in str(clean_payload)
        assert "secretKey1234567890" not in str(clean_payload)

    def test_caid_invariance_under_credential_redaction(self):
        payload_with_token = {
            "account_id": "ACC-1234",
            "amount": 50000.0,
            "token": "Bearer eyJhbGciOiJIUzI1NiJ9.abc.def",
        }
        payload_with_other_token = {
            "account_id": "ACC-1234",
            "amount": 50000.0,
            "token": "Bearer eyJhbGciOiJIUzI1NiJ9.different.xyz",
        }

        # Both scrub down to the same canonical semantic CAID
        caid_1 = self.adapter.derive_extended_caid(
            noun="Treasury",
            verb="Disburse",
            payload=payload_with_token,
            redact_credentials=True,
        )
        caid_2 = self.adapter.derive_extended_caid(
            noun="Treasury",
            verb="Disburse",
            payload=payload_with_other_token,
            redact_credentials=True,
        )

        assert caid_1 == caid_2
        assert caid_1.startswith("caid:sha256:")
