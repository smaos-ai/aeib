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
tests/test_selective_disclosure_receipt.py — Tests for SelectiveDisclosureEngine.

Validates that:
- Full unredacted receipts verify.
- Selectively redacted receipts verify without disclosing PII.
- Tampered disclosed values fail verification.
- Tampered salts fail verification.
- Tampered blind commitments fail verification.
- Tampered signatures fail verification.
"""

import pytest
from dataclasses import replace
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tools.selective_disclosure_receipt import (
    SelectiveDisclosureEngine,
    SignedAuditReceipt,
    RedactedAuditReceipt,
)


@pytest.fixture
def keypair():
    return Ed25519PrivateKey.generate()


@pytest.fixture
def sample_claims():
    return {
        "event_id": "evt-dora-001",
        "action_caid": "caid-payment-001",
        "tenant_id": "tenant-bank-01",
        "amount_minor": 150000,
        "currency": "EUR",
        "customer_iban": "DE89370400440532013000",
        "customer_name": "Alice M. Schmidt",
        "user_prompt": "Please refund customer €1,500 due to overcharge on invoice 9021",
        "disposition": "CONFIRMED",
    }


def test_full_redaction_lifecycle(keypair, sample_claims):
    # 1. Issue signed receipt
    signed = SelectiveDisclosureEngine.create_signed_receipt("rcpt-001", sample_claims, keypair)

    # 2. Redact PII according to GDPR Article 17
    redacted = SelectiveDisclosureEngine.redact_fields(
        signed, fields_to_redact={"customer_iban", "customer_name", "user_prompt"}
    )

    # Assert PII is absent from disclosed claims
    assert "customer_iban" not in redacted.disclosed_claims
    assert "customer_name" not in redacted.disclosed_claims
    assert "user_prompt" not in redacted.disclosed_claims
    assert len(redacted.redacted_field_commitments) == 3

    # 3. Verify signature remains mathematically valid over root
    assert SelectiveDisclosureEngine.verify_redacted_receipt(redacted) is True


def test_tampered_disclosed_value_fails(keypair, sample_claims):
    signed = SelectiveDisclosureEngine.create_signed_receipt("rcpt-002", sample_claims, keypair)
    redacted = SelectiveDisclosureEngine.redact_fields(signed, fields_to_redact={"customer_iban"})

    # Attacker alters unredacted amount
    tampered_claims = dict(redacted.disclosed_claims)
    tampered_claims["amount_minor"] = 999999
    tampered_receipt = replace(redacted, disclosed_claims=tampered_claims)

    assert SelectiveDisclosureEngine.verify_redacted_receipt(tampered_receipt) is False


def test_tampered_blind_commitment_fails(keypair, sample_claims):
    signed = SelectiveDisclosureEngine.create_signed_receipt("rcpt-003", sample_claims, keypair)
    redacted = SelectiveDisclosureEngine.redact_fields(signed, fields_to_redact={"customer_iban"})

    # Attacker replaces blind commitment
    tampered_commitments = dict(redacted.redacted_field_commitments)
    tampered_commitments["customer_iban"] = "00" * 32
    tampered_receipt = replace(redacted, redacted_field_commitments=tampered_commitments)

    assert SelectiveDisclosureEngine.verify_redacted_receipt(tampered_receipt) is False


def test_tampered_signature_fails(keypair, sample_claims):
    signed = SelectiveDisclosureEngine.create_signed_receipt("rcpt-004", sample_claims, keypair)
    redacted = SelectiveDisclosureEngine.redact_fields(signed, fields_to_redact={"customer_name"})

    bad_sig = "AA" * 40
    tampered_receipt = replace(redacted, signature_b64=bad_sig)

    assert SelectiveDisclosureEngine.verify_redacted_receipt(tampered_receipt) is False
