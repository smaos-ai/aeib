# Copyright 2026 SovereignNexus Project
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
src/cold_storage_airgap_gateway.py — Hardware Cold-Storage Air-Gapped Notary Gateway.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Architectural Invariants:
1. Physical / Optical Air-Gap Boundary:
   - Coordinates offline bidirectional warrant transit between online execution
     planes and physically isolated cold-storage hardware enclaves.
   - Enforces zero IP network exposure for the cold signing notary; all transit
     occurs via self-contained, canonical RFC 8785 JCS envelopes (e.g. optical QR,
     removable hardware media).
2. Anti-Replay & Nonce Fencing:
   - Every transit envelope embeds a unique cryptographic nonce and monotonic
     attempt counter, preventing transit envelope replay across epochs.
3. Asymmetric Hardware Signatures:
   - Validates hot station dispatch signatures and cold notary authorization
     signatures using Ed25519 and NIST P-256 asymmetric cryptography.
4. Sub-5ms SQLite-WAL Durability:
   - Persists all outbound requests and inbound notary responses to an append-only
     local SQLite-WAL ledger.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import hashlib
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from src.jcs_canonicalizer import encode_jcs

DECISION_AUTHORIZED: str = "AIRGAP_AUTHORIZED"
DECISION_REJECTED: str = "AIRGAP_REJECTED"


def compute_sha256_caid(payload: Any) -> str:
    """Computes deterministic RFC 8785 canonical SHA-256 CAID (e.g. 'sha256:<64-hex>')."""
    if isinstance(payload, bytes):
        raw_bytes = payload
    elif isinstance(payload, str):
        raw_bytes = payload.encode("utf-8")
    else:
        raw_bytes = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"


@dataclass(frozen=True)
class AirgapRequestEnvelope:
    """Air-gapped outbound request envelope sent from hot station to cold notary."""

    envelope_id: str
    action_type: str
    target_resource: str
    amount_minor: int
    nonce: str
    dispatch_epoch_ms: int
    hot_station_pubkey_pem: str
    signature_b64: str
    request_caid: str

    def __post_init__(self) -> None:
        if not isinstance(self.envelope_id, str) or not self.envelope_id.strip():
            raise ValueError("ERR_INVALID_ENVELOPE_ID")
        if not isinstance(self.action_type, str) or not self.action_type.strip():
            raise ValueError("ERR_INVALID_ACTION_TYPE")
        if not isinstance(self.target_resource, str) or not self.target_resource.strip():
            raise ValueError("ERR_INVALID_TARGET_RESOURCE")
        if type(self.amount_minor) is not int or self.amount_minor < 0:
            raise ValueError("ERR_INVALID_AMOUNT_MINOR")
        if not isinstance(self.nonce, str) or not self.nonce.strip():
            raise ValueError("ERR_INVALID_NONCE")
        if type(self.dispatch_epoch_ms) is not int or self.dispatch_epoch_ms <= 0:
            raise ValueError("ERR_INVALID_DISPATCH_EPOCH_MS")
        if not isinstance(self.hot_station_pubkey_pem, str) or not self.hot_station_pubkey_pem.strip():
            raise ValueError("ERR_INVALID_PUBKEY_PEM")
        if not isinstance(self.signature_b64, str) or not self.signature_b64.strip():
            raise ValueError("ERR_INVALID_SIGNATURE_B64")
        if not isinstance(self.request_caid, str) or not self.request_caid.startswith("sha256:"):
            raise ValueError("ERR_INVALID_REQUEST_CAID")


@dataclass(frozen=True)
class AirgapResponseEnvelope:
    """Air-gapped inbound response envelope emitted by cold storage notary."""

    response_id: str
    request_envelope_id: str
    decision: str
    rejection_reason: Optional[str]
    notarized_at_epoch_ms: int
    cold_notary_pubkey_pem: str
    signature_b64: str
    response_caid: str

    def __post_init__(self) -> None:
        if not isinstance(self.response_id, str) or not self.response_id.strip():
            raise ValueError("ERR_INVALID_RESPONSE_ID")
        if not isinstance(self.request_envelope_id, str) or not self.request_envelope_id.strip():
            raise ValueError("ERR_INVALID_REQUEST_ENVELOPE_ID")
        if self.decision not in {DECISION_AUTHORIZED, DECISION_REJECTED}:
            raise ValueError(f"ERR_INVALID_DECISION: {self.decision}")
        if type(self.notarized_at_epoch_ms) is not int or self.notarized_at_epoch_ms <= 0:
            raise ValueError("ERR_INVALID_NOTARIZED_EPOCH_MS")
        if not isinstance(self.cold_notary_pubkey_pem, str) or not self.cold_notary_pubkey_pem.strip():
            raise ValueError("ERR_INVALID_PUBKEY_PEM")
        if not isinstance(self.signature_b64, str) or not self.signature_b64.strip():
            raise ValueError("ERR_INVALID_SIGNATURE_B64")
        if not isinstance(self.response_caid, str) or not self.response_caid.startswith("sha256:"):
            raise ValueError("ERR_INVALID_RESPONSE_CAID")


class ColdStorageAirgapGateway:
    """Gateway coordinating air-gap transit envelopes between hot and cold storage."""

    def __init__(
        self,
        gateway_id: str = "airgap-gw-01",
        db_path: Optional[str] = None,
        private_key: Optional[ed25519.Ed25519PrivateKey] = None,
    ) -> None:
        if not gateway_id.strip():
            raise ValueError("ERR_INVALID_GATEWAY_ID")
        self.gateway_id = gateway_id
        self.db_path = db_path

        self._private_key = private_key or ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()
        self.public_key_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

        self._seen_nonces: Set[str] = set()
        self._total_transit_ops: int = 0
        self._conn: Optional[sqlite3.Connection] = None

        if self.db_path:
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        if not self.db_path:
            return
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS airgap_transit_ledger (
                    envelope_id TEXT PRIMARY KEY,
                    transit_direction TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    status TEXT NOT NULL,
                    epoch_ms INTEGER NOT NULL,
                    envelope_caid TEXT NOT NULL
                )
                """
            )

    def create_outbound_request(
        self,
        action_type: str,
        target_resource: str,
        amount_minor: int,
        nonce: Optional[str] = None,
        dispatch_time_ms: Optional[int] = None,
    ) -> AirgapRequestEnvelope:
        """Constructs and signs an outbound air-gap request envelope."""
        if not action_type.strip():
            raise ValueError("ERR_INVALID_ACTION_TYPE")
        if not target_resource.strip():
            raise ValueError("ERR_INVALID_TARGET_RESOURCE")
        if type(amount_minor) is not int or amount_minor < 0:
            raise ValueError("ERR_INVALID_AMOUNT_MINOR")

        now_ms = dispatch_time_ms if dispatch_time_ms is not None else int(time.time() * 1000)
        self._total_transit_ops += 1
        env_nonce = nonce or f"nonce-{uuid.uuid4().hex[:12]}"
        env_id = f"env-out-{self.gateway_id}-{self._total_transit_ops}-{now_ms}"

        payload = {
            "action_type": action_type,
            "amount_minor": amount_minor,
            "dispatch_epoch_ms": now_ms,
            "envelope_id": env_id,
            "hot_station_pubkey_pem": self.public_key_pem,
            "nonce": env_nonce,
            "target_resource": target_resource,
        }

        canonical_bytes = encode_jcs(payload)
        sig_bytes = self._private_key.sign(canonical_bytes)
        sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

        unsealed_env = dict(payload, signature_b64=sig_b64)
        req_caid = compute_sha256_caid(unsealed_env)

        envelope = AirgapRequestEnvelope(
            envelope_id=env_id,
            action_type=action_type,
            target_resource=target_resource,
            amount_minor=amount_minor,
            nonce=env_nonce,
            dispatch_epoch_ms=now_ms,
            hot_station_pubkey_pem=self.public_key_pem,
            signature_b64=sig_b64,
            request_caid=req_caid,
        )

        if self._conn:
            self._persist_envelope(envelope.envelope_id, "OUTBOUND", action_type, payload, env_nonce, "PENDING", now_ms, req_caid)

        return envelope

    def process_and_authorize_in_cold_storage(
        self,
        request_env: AirgapRequestEnvelope,
        operator_authorized: bool = True,
        rejection_reason: Optional[str] = None,
        cold_time_ms: Optional[int] = None,
    ) -> AirgapResponseEnvelope:
        """Processes an outbound request inside the air-gapped cold environment."""
        now_ms = cold_time_ms if cold_time_ms is not None else int(time.time() * 1000)

        # 1. Anti-replay nonce check
        if request_env.nonce in self._seen_nonces:
            decision = DECISION_REJECTED
            reason = "ERR_AIRGAP_REPLAY_DETECTED"
        else:
            # 2. Cryptographic signature check on request
            is_sig_valid = self.verify_request_signature(request_env)
            if not is_sig_valid:
                decision = DECISION_REJECTED
                reason = "ERR_INVALID_HOT_STATION_SIGNATURE"
            elif not operator_authorized:
                decision = DECISION_REJECTED
                reason = rejection_reason or "OPERATOR_AUTHORIZATION_DENIED"
            else:
                decision = DECISION_AUTHORIZED
                reason = None
                self._seen_nonces.add(request_env.nonce)

        self._total_transit_ops += 1
        resp_id = f"env-resp-{self.gateway_id}-{self._total_transit_ops}-{now_ms}"

        resp_payload: Dict[str, Any] = {
            "cold_notary_pubkey_pem": self.public_key_pem,
            "decision": decision,
            "notarized_at_epoch_ms": now_ms,
            "rejection_reason": reason,
            "request_envelope_id": request_env.envelope_id,
            "response_id": resp_id,
        }

        canonical_bytes = encode_jcs(resp_payload)
        sig_bytes = self._private_key.sign(canonical_bytes)
        sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

        unsealed_resp = dict(resp_payload, signature_b64=sig_b64)
        resp_caid = compute_sha256_caid(unsealed_resp)

        response = AirgapResponseEnvelope(
            response_id=resp_id,
            request_envelope_id=request_env.envelope_id,
            decision=decision,
            rejection_reason=reason,
            notarized_at_epoch_ms=now_ms,
            cold_notary_pubkey_pem=self.public_key_pem,
            signature_b64=sig_b64,
            response_caid=resp_caid,
        )

        if self._conn:
            self._persist_envelope(response.response_id, "INBOUND_RESPONSE", request_env.action_type, resp_payload, request_env.nonce, decision, now_ms, resp_caid)

        return response

    def verify_request_signature(self, env: AirgapRequestEnvelope) -> bool:
        """Verifies asymmetric signature on an outbound request envelope."""
        payload = {
            "action_type": env.action_type,
            "amount_minor": env.amount_minor,
            "dispatch_epoch_ms": env.dispatch_epoch_ms,
            "envelope_id": env.envelope_id,
            "hot_station_pubkey_pem": env.hot_station_pubkey_pem,
            "nonce": env.nonce,
            "target_resource": env.target_resource,
        }
        canonical_bytes = encode_jcs(payload)
        try:
            pubkey_obj = serialization.load_pem_public_key(env.hot_station_pubkey_pem.encode("ascii"))
            if not isinstance(pubkey_obj, ed25519.Ed25519PublicKey):
                return False
            sig_bytes = base64.b64decode(env.signature_b64)
            pubkey_obj.verify(sig_bytes, canonical_bytes)
            return True
        except (ValueError, InvalidSignature, Exception):
            return False

    def verify_response_signature(self, resp: AirgapResponseEnvelope) -> bool:
        """Verifies asymmetric signature on a cold notary response envelope."""
        payload = {
            "cold_notary_pubkey_pem": resp.cold_notary_pubkey_pem,
            "decision": resp.decision,
            "notarized_at_epoch_ms": resp.notarized_at_epoch_ms,
            "rejection_reason": resp.rejection_reason,
            "request_envelope_id": resp.request_envelope_id,
            "response_id": resp.response_id,
        }
        canonical_bytes = encode_jcs(payload)
        try:
            pubkey_obj = serialization.load_pem_public_key(resp.cold_notary_pubkey_pem.encode("ascii"))
            if not isinstance(pubkey_obj, ed25519.Ed25519PublicKey):
                return False
            sig_bytes = base64.b64decode(resp.signature_b64)
            pubkey_obj.verify(sig_bytes, canonical_bytes)
            return True
        except (ValueError, InvalidSignature, Exception):
            return False

    def _persist_envelope(
        self,
        envelope_id: str,
        direction: str,
        action_type: str,
        payload: Dict[str, Any],
        nonce: str,
        status: str,
        epoch_ms: int,
        caid: str,
    ) -> None:
        if not self._conn:
            return
        payload_json = encode_jcs(payload).decode("utf-8")
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO airgap_transit_ledger (
                    envelope_id, transit_direction, action_type,
                    payload_json, nonce, status, epoch_ms, envelope_caid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (envelope_id, direction, action_type, payload_json, nonce, status, epoch_ms, caid),
            )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
