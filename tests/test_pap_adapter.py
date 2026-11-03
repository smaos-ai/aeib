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
tests/test_pap_adapter.py — Personal Agent Protocol (PAP) Effect-Integrity Adapter Test Suite
Evaluates PAP contract enforcement, candidate action binding, uncertainty latching,
authoritative target reconciliation probes, and Ed25519 receipt verification under the stated model.
"""

import hashlib
import json
import pytest
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs
from src.pap_adapter import (
    PAPEffectIntegrityAdapter,
    PAPAgentEnvelope,
    PAPCandidateAction,
    PAPExecutionChannel,
    PAPContractValidationError,
)


class TestPAPEffectIntegrityAdapter:
    """Evaluates the Personal Agent Protocol adapter under fault scenarios and nominal flows."""

    def setup_method(self):
        self.signing_key = ed25519.Ed25519PrivateKey.generate()
        self.adapter = PAPEffectIntegrityAdapter(signing_key=self.signing_key)
        self.valid_fingerprint = f"sha256:{hashlib.sha256(b'device_secure_enclave_key_01').hexdigest()}"
        self.valid_intent = f"sha256:{hashlib.sha256(b'user_prompt_intent_buy_flight').hexdigest()}"

    def test_00_schema_conformance(self):
        """Validates that the PAP adapter contract schema exists and contains required fields."""
        schema_path = REPO_ROOT / "schemas" / "aeib-pap-adapter-v0.1.json"
        assert schema_path.exists(), "PAP adapter contract schema must exist"
        schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema_data["$id"] == "https://smaos.ai/schemas/aeib-pap-adapter-v0.1.json"
        assert schema_data["properties"]["protocol_version"]["const"] == "pap-aeib-v0.1"
        required_fields = set(schema_data["required"])
        expected_fields = {
            "protocol_version",
            "agent_envelope",
            "candidate_action",
            "execution_channel",
            "effect_integrity_policy",
            "reconciliation_probe",
            "release_governance",
        }
        assert expected_fields.issubset(required_fields)

    def test_envelope_validation_success(self):
        """Evaluates that a compliant agent envelope passes validation."""
        env = PAPAgentEnvelope(
            agent_id="agent:personal:shopper_alpha_42",
            user_principal_id="did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            device_fingerprint=self.valid_fingerprint,
            session_id="session_personal_2026_001",
            intent_hash=self.valid_intent,
            delegation_grant_id="grant_delegate_991",
        )
        env.validate()  # must not raise

    def test_envelope_validation_rejection(self):
        """Evaluates that invalid identifiers fail-closed with PAPContractValidationError."""
        # Invalid agent_id prefix
        with pytest.raises(PAPContractValidationError, match="Invalid agent_id"):
            env = PAPAgentEnvelope(
                agent_id="agent:untrusted:invalid",
                user_principal_id="user_01",
                device_fingerprint=self.valid_fingerprint,
                session_id="session_01",
                intent_hash=self.valid_intent,
            )
            env.validate()

        # Invalid device_fingerprint format
        with pytest.raises(PAPContractValidationError, match="Invalid device_fingerprint"):
            env = PAPAgentEnvelope(
                agent_id="agent:personal:shopper_01",
                user_principal_id="user_01",
                device_fingerprint="not_a_sha256",
                session_id="session_01",
                intent_hash=self.valid_intent,
            )
            env.validate()

        # Invalid intent_hash format
        with pytest.raises(PAPContractValidationError, match="Invalid intent_hash"):
            env = PAPAgentEnvelope(
                agent_id="agent:personal:shopper_01",
                user_principal_id="user_01",
                device_fingerprint=self.valid_fingerprint,
                session_id="session_01",
                intent_hash="invalid_intent_digest",
            )
            env.validate()

    def test_contract_document_generation(self):
        """Evaluates contract document structure generated for personal agent candidate action."""
        envelope = PAPAgentEnvelope(
            agent_id="agent:personal:travel_assistant_01",
            user_principal_id="user_alice_local",
            device_fingerprint=self.valid_fingerprint,
            session_id="session_tx_8812",
            intent_hash=self.valid_intent,
            delegation_grant_id="grant_flight_booking",
        )
        candidate = PAPCandidateAction(
            noun="FlightReservation",
            verb="BookSeats",
            target_uri="https://api.airline.example/v1/bookings",
            payload={"flight_num": "LH1234", "seats": ["14A"], "price": 450.0},
            max_amount=500.0,
            currency="EUR",
            require_biometric_release=True,
        )
        channel = PAPExecutionChannel(
            channel_type="http_rest",
            target_capability="idempotency_key_plus_status_api",
        )

        doc = self.adapter.build_contract_document(envelope, candidate, channel, "Authorize flight booking")
        assert doc["protocol_version"] == "pap-aeib-v0.1"
        assert doc["agent_envelope"]["agent_id"] == "agent:personal:travel_assistant_01"
        assert doc["agent_envelope"]["delegation_grant_id"] == "grant_flight_booking"
        assert doc["candidate_action"]["candidate_caid"].startswith("caid:sha256:")
        assert doc["candidate_action"]["payload_canonical_hash"].startswith("sha256:")
        assert doc["candidate_action"]["economic_limits"]["max_amount"] == 500.0
        assert doc["candidate_action"]["economic_limits"]["currency"] == "EUR"
        assert doc["candidate_action"]["economic_limits"]["require_biometric_release"] is True
        assert doc["effect_integrity_policy"]["uncertainty_latch"] is True
        assert doc["effect_integrity_policy"]["retry_safe"] is False
        assert doc["reconciliation_probe"]["probe_method"] == "status_api_query"
        assert doc["reconciliation_probe"]["single_flight_coalescing"] is True
        assert doc["reconciliation_probe"]["timeout_ms"] == 5000
        assert doc["reconciliation_probe"]["consistency_model"] == "strong_read"
        assert doc["reconciliation_probe"]["probe_authority"] == "authoritative_status_endpoint"
        assert doc["release_governance"]["release_authorization_required"] is True
        assert doc["release_governance"]["release_status"] == "not_provided"

    def test_nominal_execution_confirmed(self):
        """Evaluates nominal execution (HTTP 200) producing ACTION_CONFIRMED and signed receipt."""
        envelope = PAPAgentEnvelope(
            agent_id="agent:personal:booking_bot",
            user_principal_id="user_bob",
            device_fingerprint=self.valid_fingerprint,
            session_id="session_nom_01",
            intent_hash=self.valid_intent,
        )
        candidate = PAPCandidateAction(
            noun="Order",
            verb="PlaceOrder",
            target_uri="https://shop.example/api/orders",
            payload={"item": "headphones", "qty": 1},
        )
        channel = PAPExecutionChannel(channel_type="web_dom")

        res = self.adapter.process_wire_outcome(
            envelope=envelope,
            candidate=candidate,
            channel=channel,
            wire_status_code=200,
            wire_error=None,
        )

        assert res.disposition == "ACTION_CONFIRMED"
        assert res.retry_safe is False
        assert res.latch_engaged is False
        assert res.retry_policy == "PROHIBITED_ALREADY_COMMITTED"
        assert res.probe_status == "PROBE_NOT_ATTEMPTED"
        assert res.target_state == "COMMITTED"
        assert res.release_authorization == "not_provided"

        # Verify cryptographic Ed25519 receipt
        receipt = res.receipt
        assert receipt["aeib.caid"] == res.caid
        assert receipt["aeib.disposition"] == "ACTION_CONFIRMED"
        assert receipt["aeib.retry_safe"] is False
        assert receipt["aeib.release_authorization"] == "not_provided"
        assert receipt["aeib.protocol"] == "pap-aeib-v0.1"
        assert receipt["aeib.receipt.verified"] is True

        pub_bytes = bytes.fromhex(receipt["aeib.receipt.public_key_hex"])
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        body = {k: v for k, v in receipt.items() if not k.startswith("aeib.receipt.")}
        canonical_bytes = encode_jcs(body)
        signature = bytes.fromhex(receipt["aeib.receipt.signature"])
        pub_key.verify(signature, canonical_bytes)

    def test_wire_anomaly_latches_uncertainty_and_probes_found(self):
        """Evaluates transport 504 timeout latching uncertainty, reconciled via single-flight probe."""
        envelope = PAPAgentEnvelope(
            agent_id="agent:personal:booking_bot",
            user_principal_id="user_bob",
            device_fingerprint=self.valid_fingerprint,
            session_id="session_fault_01",
            intent_hash=self.valid_intent,
        )
        candidate = PAPCandidateAction(
            noun="Payment",
            verb="Disburse",
            target_uri="https://pay.example/api/disburse",
            payload={"payment_id": "pay_99", "amount": 120.0},
        )
        channel = PAPExecutionChannel(channel_type="http_rest")

        # Simulate authoritative target-side ledger where mutation DID commit before drop
        target_ledger_store = {candidate.compute_caid(): True}
        probe_call_count = [0]

        def target_probe(caid: str) -> bool:
            probe_call_count[0] += 1
            return target_ledger_store.get(caid, False)

        res = self.adapter.process_wire_outcome(
            envelope=envelope,
            candidate=candidate,
            channel=channel,
            wire_status_code=504,
            wire_error="Gateway Timeout",
            target_probe_fn=target_probe,
        )

        assert res.disposition == "EFFECT_INDETERMINATE"
        assert res.retry_safe is False
        assert res.latch_engaged is True
        assert res.retry_policy == "PROHIBITED_DEFAULT_LATCH"
        assert res.probe_status == "RECORD_FOUND"
        assert res.target_state == "COMMITTED"
        assert probe_call_count[0] == 1
        caid = candidate.compute_caid()
        assert self.adapter.probe_history[caid] == 1
        assert res.receipt["aeib.retry_safe"] is False

        # Subsequent attempt on latched CAID is rejected fail-closed without re-probing
        res2 = self.adapter.process_wire_outcome(
            envelope=envelope,
            candidate=candidate,
            channel=channel,
            wire_status_code=504,
            wire_error="Gateway Timeout",
            target_probe_fn=target_probe,
        )
        assert res2.latch_engaged is True
        assert res2.target_state == "INDETERMINATE_LATCHED"
        assert probe_call_count[0] == 1  # single-flight coalesced, no duplicate probe dispatch

    def test_wire_anomaly_reconciled_not_found(self):
        """Evaluates connection drop before commit where reconciliation probe confirms absent mutation."""
        envelope = PAPAgentEnvelope(
            agent_id="agent:personal:booking_bot",
            user_principal_id="user_bob",
            device_fingerprint=self.valid_fingerprint,
            session_id="session_drop_01",
            intent_hash=self.valid_intent,
        )
        candidate = PAPCandidateAction(
            noun="Subscription",
            verb="Create",
            target_uri="https://sub.example/api/v1",
            payload={"plan": "premium"},
        )
        channel = PAPExecutionChannel(channel_type="http_rest")

        def target_probe_empty(caid: str) -> bool:
            return False

        res = self.adapter.process_wire_outcome(
            envelope=envelope,
            candidate=candidate,
            channel=channel,
            wire_status_code=0,
            wire_error="TCP connection reset by peer",
            target_probe_fn=target_probe_empty,
        )

        assert res.disposition == "EFFECT_INDETERMINATE"
        assert res.retry_safe is False
        assert res.latch_engaged is True
        assert res.probe_status == "RECORD_NOT_FOUND"
        assert res.target_state == "NOT_FOUND"
        assert res.release_authorization == "not_provided"

    def test_tampered_receipt_signature_fails_verification(self):
        """Evaluates that any byte mutation in receipt causes Ed25519 signature verification failure."""
        envelope = PAPAgentEnvelope(
            agent_id="agent:personal:sec_bot",
            user_principal_id="user_carol",
            device_fingerprint=self.valid_fingerprint,
            session_id="session_crypto_01",
            intent_hash=self.valid_intent,
        )
        candidate = PAPCandidateAction(
            noun="Vault",
            verb="Unlock",
            target_uri="https://vault.example/unlock",
            payload={"slot": 9},
        )
        channel = PAPExecutionChannel(channel_type="http_rest")

        res = self.adapter.process_wire_outcome(
            envelope=envelope,
            candidate=candidate,
            channel=channel,
            wire_status_code=200,
        )

        receipt = res.receipt
        pub_bytes = bytes.fromhex(receipt["aeib.receipt.public_key_hex"])
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)

        body = {k: v for k, v in receipt.items() if not k.startswith("aeib.receipt.")}
        # Tamper with the disposition field
        body["aeib.disposition"] = "TAMPERED_DISPOSITION"
        tampered_bytes = encode_jcs(body)
        signature = bytes.fromhex(receipt["aeib.receipt.signature"])

        with pytest.raises(InvalidSignature):
            pub_key.verify(signature, tampered_bytes)

    def test_default_candidate_action_fields_and_adapter_keys(self):
        c = PAPCandidateAction(noun="A", verb="B", target_uri="https://u", payload={"x": 1})
        assert c.require_biometric_release is False
        assert c.max_amount is None
        assert c.currency is None

        # Test signing_key or ed25519 generate
        default_adapter = PAPEffectIntegrityAdapter()
        assert default_adapter.signing_key is not None
        assert len(default_adapter.public_key_hex) == 64
        custom_key = ed25519.Ed25519PrivateKey.generate()
        custom_adapter = PAPEffectIntegrityAdapter(signing_key=custom_key)
        assert custom_adapter.signing_key is custom_key

    def test_status_500_with_wire_error_none_latches_fail_closed(self):
        envelope = PAPAgentEnvelope(
            agent_id="agent:personal:bot",
            user_principal_id="user_bob",
            device_fingerprint=self.valid_fingerprint,
            session_id="session_err_01",
            intent_hash=self.valid_intent,
        )
        candidate = PAPCandidateAction(
            noun="Order",
            verb="Submit",
            target_uri="https://shop.example/api/orders",
            payload={"item": "book"},
        )
        channel = PAPExecutionChannel(channel_type="http_rest")
        # wire_status_code=500, wire_error=None (kills BOOL_SWAP line 207)
        res = self.adapter.process_wire_outcome(
            envelope=envelope,
            candidate=candidate,
            channel=channel,
            wire_status_code=500,
            wire_error=None,
        )
        assert res.disposition == "EFFECT_INDETERMINATE"
        assert res.latch_engaged is True
        assert res.retry_safe is False
        assert res.receipt["aeib.retry_safe"] is False
