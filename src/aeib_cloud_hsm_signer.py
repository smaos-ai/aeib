#!/usr/bin/env python3
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
aeib_cloud_hsm_signer.py — FIPS 140-3 CloudHSM Ephemeral In-Enclave Session Lease Engine
Part of the Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.

Eliminates the 15ms-50ms CloudHSM / PKCS#11 network latency bottleneck while
preserving cryptographic root-of-trust:
1. Master CloudHSM Key issues a 60-second time-bounded, spend-capped Session Lease Warrant.
2. Station 1 signs per-operation dispatches in <0.05ms using an in-memory ephemeral Ed25519 key.
3. Strict enforcement:
   - Max spend ceiling per lease (fail-closed if breached).
   - Time-bound lease expiry (fail-closed on expiration).
   - Asynchronous Merkle root notarization back to Master CloudHSM at lease boundary.
"""

import base64
import hashlib
import time
import uuid
from typing import Dict, Any, Optional, List
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from src.jcs_canonicalizer import encode_jcs


class CloudHsmMasterEnclave:
    """
    Simulates the FIPS 140-3 Hardware Security Module / KMS Enclave environment.
    Holds the authoritative master Ed25519 signing key. Never exports the private key.
    """

    def __init__(self, key_id: str = "hsm-root-key-2026-v1"):
        self.key_id = key_id
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self.public_key = self._private_key.public_key()
        self._checkpoint_log: List[Dict[str, Any]] = []

    def export_public_key_pem(self) -> str:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    def issue_session_lease_warrant(
        self,
        ephemeral_pubkey_pem: str,
        lease_duration_seconds: int = 60,
        max_cumulative_spend_minor: int = 500_000,  # €5,000.00
        hardware_fingerprint: str = "hw-enclave-node-01",
        current_time: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Signs a strictly bounded session lease authorizing the local Station 1 process
        to sign intermediate dispatches for lease_duration_seconds up to max_cumulative_spend_minor.
        """
        now = current_time if current_time is not None else int(time.time())
        warrant_id = f"warrant-{uuid.uuid4()}"
        body = {
            "warrant_id": warrant_id,
            "hsm_key_id": self.key_id,
            "ephemeral_pubkey_pem": ephemeral_pubkey_pem,
            "valid_after": now - 2,  # 2s clock skew grace
            "valid_until": now + lease_duration_seconds,
            "max_cumulative_spend_minor": max_cumulative_spend_minor,
            "hardware_fingerprint": hardware_fingerprint,
        }
        canonical_bytes = encode_jcs(body)
        sig = self._private_key.sign(canonical_bytes)

        return {
            "warrant_body": body,
            "hsm_signature_b64": base64.b64encode(sig).decode("ascii"),
        }

    def notarize_lease_checkpoint(
        self,
        warrant_id: str,
        merkle_root_hex: str,
        operations_count: int,
        total_settled_minor: int,
        checkpoint_time: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Notarizes the final batch Merkle root back into the Master CloudHSM log.
        """
        now = checkpoint_time if checkpoint_time is not None else int(time.time())
        checkpoint_record = {
            "checkpoint_id": f"ckpt-{uuid.uuid4()}",
            "warrant_id": warrant_id,
            "merkle_root_hex": merkle_root_hex,
            "operations_count": operations_count,
            "total_settled_minor": total_settled_minor,
            "timestamp": now,
        }
        canonical_bytes = encode_jcs(checkpoint_record)
        hsm_sig = self._private_key.sign(canonical_bytes)

        signed_record = {
            "record": checkpoint_record,
            "hsm_signature_b64": base64.b64encode(hsm_sig).decode("ascii"),
        }
        self._checkpoint_log.append(signed_record)
        return signed_record


class EphemeralSessionLeaseSigner:
    """
    High-performance in-memory Station 1 signer operating under a CloudHSM Lease Warrant.
    Executes in <0.05ms per operation without remote network calls.
    """

    def __init__(
        self,
        hsm_master: CloudHsmMasterEnclave,
        lease_duration_seconds: int = 60,
        max_cumulative_spend_minor: int = 500_000,
        current_time: Optional[int] = None,
    ):
        self.hsm_master = hsm_master
        self.hsm_public_key = hsm_master.public_key
        self._ephemeral_private = ed25519.Ed25519PrivateKey.generate()
        self.ephemeral_public = self._ephemeral_private.public_key()
        self.ephemeral_pub_pem = self.ephemeral_public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

        self.warrant = hsm_master.issue_session_lease_warrant(
            ephemeral_pubkey_pem=self.ephemeral_pub_pem,
            lease_duration_seconds=lease_duration_seconds,
            max_cumulative_spend_minor=max_cumulative_spend_minor,
            current_time=current_time,
        )

        self._cumulative_spend_minor: int = 0
        self._signed_operations: List[Dict[str, Any]] = []
        self._is_closed: bool = False

    @property
    def warrant_id(self) -> str:
        return self.warrant["warrant_body"]["warrant_id"]

    @property
    def cumulative_spend_minor(self) -> int:
        return self._cumulative_spend_minor

    def verify_warrant(self) -> bool:
        """Cryptographically verifies the HSM master signature on the lease warrant."""
        body = self.warrant["warrant_body"]
        sig = base64.b64decode(self.warrant["hsm_signature_b64"])
        canonical_bytes = encode_jcs(body)
        try:
            self.hsm_public_key.verify(sig, canonical_bytes)
            return True
        except Exception:
            return False

    def sign_operation_dispatch(
        self,
        operation_id: str,
        action_caid: str,
        amount_minor: int,
        now: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Signs an operation dispatch locally using the ephemeral session key,
        strictly enforcing lease expiration and spend ceilings.
        """
        if self._is_closed:
            return {"valid": False, "error": "ERR_HSM_LEASE_SESSION_CLOSED"}

        current_ts = now if now is not None else int(time.time())
        wb = self.warrant["warrant_body"]

        # 1. Lease time-boundary check
        if current_ts < wb["valid_after"]:
            return {"valid": False, "error": "ERR_CLOCK_SKEW_EARLY"}
        if current_ts > wb["valid_until"]:
            return {"valid": False, "error": "ERR_HSM_LEASE_EXPIRED"}

        # 2. Cumulative spend ceiling check
        if self._cumulative_spend_minor + amount_minor > wb["max_cumulative_spend_minor"]:
            return {
                "valid": False,
                "error": "ERR_HSM_LEASE_BUDGET_EXCEEDED",
                "remaining_minor": wb["max_cumulative_spend_minor"] - self._cumulative_spend_minor,
                "requested_minor": amount_minor,
            }

        # 3. Create dispatch receipt
        seq = len(self._signed_operations) + 1
        receipt_body = {
            "warrant_id": wb["warrant_id"],
            "operation_id": operation_id,
            "action_caid": action_caid,
            "amount_minor": amount_minor,
            "session_seq": seq,
            "signed_at": current_ts,
        }
        canonical_bytes = encode_jcs(receipt_body)
        op_sig = self._ephemeral_private.sign(canonical_bytes)

        signed_receipt = {
            "valid": True,
            "receipt_body": receipt_body,
            "session_signature_b64": base64.b64encode(op_sig).decode("ascii"),
            "ephemeral_pubkey_pem": self.ephemeral_pub_pem,
            "warrant": self.warrant,
        }

        self._cumulative_spend_minor += amount_minor
        self._signed_operations.append(signed_receipt)
        return signed_receipt

    def close_and_commit_checkpoint(
        self,
        checkpoint_time: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Closes the ephemeral session lease, computes the SHA-256 Merkle root of all
        dispatched operations, and commits the checkpoint back to the Master CloudHSM.
        """
        self._is_closed = True

        # Compute simple Merkle root of receipt bodies
        leaf_hashes: List[bytes] = []
        for op in self._signed_operations:
            canon = encode_jcs(op["receipt_body"])
            leaf_hashes.append(hashlib.sha256(b"\x00" + canon).digest())

        if not leaf_hashes:
            root_hex = hashlib.sha256(b"\x00EMPTY_SESSION").hexdigest()
        else:
            current_level = leaf_hashes
            while len(current_level) > 1:
                next_level = []
                for i in range(0, len(current_level), 2):
                    left = current_level[i]
                    right = current_level[i + 1] if i + 1 < len(current_level) else left
                    parent = hashlib.sha256(b"\x01" + left + right).digest()
                    next_level.append(parent)
                current_level = next_level
            root_hex = current_level[0].hex()

        return self.hsm_master.notarize_lease_checkpoint(
            warrant_id=self.warrant_id,
            merkle_root_hex=root_hex,
            operations_count=len(self._signed_operations),
            total_settled_minor=self._cumulative_spend_minor,
            checkpoint_time=checkpoint_time,
        )
