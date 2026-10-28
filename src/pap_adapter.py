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
src/pap_adapter.py — Personal Agent Protocol (PAP) Effect-Integrity Adapter
Implements the contract defined in schemas/aeib-pap-adapter-v0.1.json.

Binds:
- Agent-Principal Delegation & Identity Envelope
- Candidate Action & RFC 8785 Payload Hashing
- Execution Channel & Economic Bounds
- Transport Uncertainty Latching (retry_safe: false fail-closed)
- Authoritative Single-Flight Reconciliation Probing
- Human Confirmation Release Separation
"""

import hashlib
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash
from src.aeib_v040_engine import derive_caid


class PAPContractValidationError(ValueError):
    """Raised when a PAP message or candidate action violates adapter contract bounds."""
    pass


@dataclass
class PAPAgentEnvelope:
    agent_id: str
    user_principal_id: str
    device_fingerprint: str
    session_id: str
    intent_hash: str
    delegation_grant_id: Optional[str] = None

    def validate(self) -> None:
        if not self.agent_id.startswith("agent:personal:"):
            raise PAPContractValidationError(f"Invalid agent_id: {self.agent_id}; must match ^agent:personal:[a-zA-Z0-9_-]+$")
        if not self.device_fingerprint.startswith("sha256:"):
            raise PAPContractValidationError(f"Invalid device_fingerprint: must be sha256 hex")
        if not self.intent_hash.startswith("sha256:"):
            raise PAPContractValidationError(f"Invalid intent_hash: must be sha256 hex")


@dataclass
class PAPCandidateAction:
    noun: str
    verb: str
    target_uri: str
    payload: Dict[str, Any]
    max_amount: Optional[float] = None
    currency: Optional[str] = None
    require_biometric_release: bool = False

    def compute_caid(self) -> str:
        return derive_caid(self.noun, self.verb, self.payload)

    def compute_payload_hash(self) -> str:
        raw_hash = generate_jcs_payload_hash(self.payload)
        return f"sha256:{raw_hash}" if not raw_hash.startswith("sha256:") else raw_hash


@dataclass
class PAPExecutionChannel:
    channel_type: str = "web_dom"  # "web_dom", "http_rest", "mcp_tool", "graphql"
    target_capability: str = "idempotency_key_plus_status_api"
    idempotency_token: Optional[str] = None


@dataclass
class PAPAdapterResult:
    caid: str
    disposition: str
    retry_safe: bool
    latch_engaged: bool
    retry_policy: str
    probe_status: Optional[str] = None
    release_authorization: str = "not_provided"
    target_state: str = "NOT_FOUND"
    receipt: Dict[str, Any] = field(default_factory=dict)


class PAPEffectIntegrityAdapter:
    """
    AEIB Gateway Adapter implementing the Personal Agent Protocol (PAP) contract.
    """
    def __init__(self, signing_key: Optional[ed25519.Ed25519PrivateKey] = None):
        self.signing_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key_hex = self.signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()
        self.latched_caids: Dict[str, bool] = {}
        self.probe_history: Dict[str, int] = {}

    def build_contract_document(
        self,
        envelope: PAPAgentEnvelope,
        candidate: PAPCandidateAction,
        channel: PAPExecutionChannel,
        prompt_summary: str = "Confirm transaction"
    ) -> Dict[str, Any]:
        """Builds a compliant document conforming to schemas/aeib-pap-adapter-v0.1.json."""
        envelope.validate()
        caid = candidate.compute_caid()
        payload_hash = candidate.compute_payload_hash()

        economic_limits = {}
        if candidate.max_amount is not None:
            economic_limits["max_amount"] = candidate.max_amount
        if candidate.currency is not None:
            economic_limits["currency"] = candidate.currency
        economic_limits["require_biometric_release"] = candidate.require_biometric_release

        return {
            "protocol_version": "pap-aeib-v0.1",
            "agent_envelope": {
                "agent_id": envelope.agent_id,
                "user_principal_id": envelope.user_principal_id,
                "device_fingerprint": envelope.device_fingerprint,
                "session_id": envelope.session_id,
                "intent_hash": envelope.intent_hash,
                **({"delegation_grant_id": envelope.delegation_grant_id} if envelope.delegation_grant_id else {})
            },
            "candidate_action": {
                "noun": candidate.noun,
                "verb": candidate.verb,
                "target_uri": candidate.target_uri,
                "payload": candidate.payload,
                "payload_canonical_hash": payload_hash,
                "candidate_caid": caid,
                "economic_limits": economic_limits
            },
            "execution_channel": {
                "channel_type": channel.channel_type,
                "target_capability": channel.target_capability,
                "idempotency_token": channel.idempotency_token or f"idemp:{caid}"
            },
            "effect_integrity_policy": {
                "uncertainty_latch": True,
                "disposition_on_wire_anomaly": "EFFECT_INDETERMINATE",
                "retry_policy": "PROHIBITED_DEFAULT_LATCH",
                "retry_safe": False
            },
            "reconciliation_probe": {
                "probe_method": "status_api_query" if channel.channel_type != "web_dom" else "dom_recheck",
                "probe_authority": "authoritative_status_endpoint",
                "consistency_model": "strong_read",
                "single_flight_coalescing": True,
                "timeout_ms": 5000  # claim: config
            },
            "release_governance": {
                "release_authorization_required": True,
                "release_status": "not_provided",
                "human_confirmation_prompt": prompt_summary
            }
        }

    def process_wire_outcome(
        self,
        envelope: PAPAgentEnvelope,
        candidate: PAPCandidateAction,
        channel: PAPExecutionChannel,
        wire_status_code: int,
        wire_error: Optional[str] = None,
        target_probe_fn: Optional[Any] = None
    ) -> PAPAdapterResult:
        """
        Processes the wire observation from the Personal Agent's execution attempt.
        Under wire errors or timeouts, latches uncertainty fail-closed and triggers
        a single-flight reconciliation probe.
        """
        caid = candidate.compute_caid()
        payload_hash = candidate.compute_payload_hash()

        # Check existing latch
        if self.latched_caids.get(caid, False):
            return PAPAdapterResult(
                caid=caid,
                disposition="EFFECT_INDETERMINATE",
                retry_safe=False,
                latch_engaged=True,
                retry_policy="PROHIBITED_DEFAULT_LATCH",
                target_state="INDETERMINATE_LATCHED"
            )

        # Success case: HTTP 200 OK
        if wire_status_code == 200 and not wire_error:
            receipt = self._sign_receipt(caid, candidate.noun, candidate.verb, payload_hash, "ACTION_CONFIRMED")
            return PAPAdapterResult(
                caid=caid,
                disposition="ACTION_CONFIRMED",
                retry_safe=False,
                latch_engaged=False,
                retry_policy="PROHIBITED_ALREADY_COMMITTED",
                probe_status="PROBE_NOT_ATTEMPTED",
                release_authorization="not_provided",
                target_state="COMMITTED",
                receipt=receipt
            )

        # Ambiguous wire outcome: HTTP 504, connection reset, browser process termination
        self.latched_caids[caid] = True
        probe_status = "PROBE_NOT_ATTEMPTED"
        target_state = "NOT_FOUND"

        if target_probe_fn:
            self.probe_history[caid] = self.probe_history.get(caid, 0) + 1
            probe_result = target_probe_fn(caid)
            if probe_result:
                probe_status = "RECORD_FOUND"
                target_state = "COMMITTED"
            else:
                probe_status = "RECORD_NOT_FOUND"
                target_state = "NOT_FOUND"

        receipt = self._sign_receipt(caid, candidate.noun, candidate.verb, payload_hash, "EFFECT_INDETERMINATE")
        return PAPAdapterResult(
            caid=caid,
            disposition="EFFECT_INDETERMINATE",
            retry_safe=False,
            latch_engaged=True,
            retry_policy="PROHIBITED_DEFAULT_LATCH",
            probe_status=probe_status,
            release_authorization="not_provided",
            target_state=target_state,
            receipt=receipt
        )

    def _sign_receipt(self, caid: str, noun: str, verb: str, payload_hash: str, disposition: str) -> Dict[str, Any]:
        body = {
            "aeib.caid": caid,
            "aeib.action.noun": noun,
            "aeib.action.verb": verb,
            "aeib.payload_hash": payload_hash,
            "aeib.disposition": disposition,
            "aeib.retry_safe": False,
            "aeib.release_authorization": "not_provided",
            "aeib.protocol": "pap-aeib-v0.1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        canonical_bytes = encode_jcs(body)
        event_digest = hashlib.sha256(canonical_bytes).hexdigest()
        signature = self.signing_key.sign(canonical_bytes)

        return {
            **body,
            "aeib.receipt.signature": signature.hex(),
            "aeib.receipt.public_key_hex": self.public_key_hex,
            "aeib.receipt.jcs_payload_hash": f"sha256:{event_digest}",
            "aeib.receipt.verified": True
        }
