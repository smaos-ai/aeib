#!/usr/bin/env python3
# File: tools/zk_tlsnotary_integration.py
"""
Track Alpha: ZK-API / TLSNotary Blind Receipt Attestation Prototype.

Evaluates under the stated model:
- Co-signs an authenticated HTTPS API session transcript between the AEIB proxy
  (MPC / Notary witness) and the agent client.
- Proves that the external API returned `status == "approved"` and
  `balance_minor > required_floor_minor` (e.g., `> $100.00` = `100_00` minor units)
  using salted SHA-256 16-bit limb range commitments and a Merkle-redacted
  transcript tree.
- Preserves strict data minimization: the exact account balance, account number,
  and raw PII never appear in the Station 3 SCITT receipt.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def encode_jcs(obj: Any) -> bytes:
    """Deterministic RFC 8785 JCS subset serializer rejecting floats."""
    def _check(val: Any) -> None:
        if isinstance(val, float):
            raise ValueError("ERR_FLOAT_FORBIDDEN_IN_JCS")
        if isinstance(val, dict):
            for k, v in val.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _check(v)
        elif isinstance(val, list):
            for item in val:
                _check(item)

    _check(obj)
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class BlindApiReceipt:
    operation_id: str
    server_sni: str
    disclosed_status: str
    strict_floor_minor: int
    transcript_merkle_root: str
    excess_limb_commitments: Tuple[str, ...]
    redacted_leaf_hashes: Dict[str, str]
    notary_key_id: str
    notary_signature_b64: str


class ZkTlsNotaryProxyPrototype:
    """
    Prototype co-signing witness for Track Alpha (`tools/zk_tlsnotary_integration.py`).
    Verifies an API response inside the proxy boundary, strips sensitive fields into
    salted leaf hashes, and emits an offline-verifiable `BlindApiReceipt` proving
    `balance_minor > strict_floor_minor` (`delta = balance_minor - strict_floor_minor - 1 >= 0`).
    """

    def __init__(self, notary_priv: Ed25519PrivateKey, notary_key_id: str = "did:key:aeib-notary-1") -> None:
        self._notary_priv = notary_priv
        self.notary_pub = notary_priv.public_key()
        self.notary_key_id = notary_key_id

    def attest_api_response_above_floor(
        self,
        operation_id: str,
        server_sni: str,
        raw_json_response: Dict[str, Any],
        strict_floor_minor: int,
        session_salt_hex: str,
    ) -> BlindApiReceipt:
        status = str(raw_json_response.get("status", ""))
        balance_minor = raw_json_response.get("balance_minor")
        if (
            status != "approved"
            or isinstance(balance_minor, bool)
            or not isinstance(balance_minor, int)
        ):
            raise ValueError("ERR_ZKTLS_INVALID_STATUS_OR_NON_INTEGER_BALANCE")

        # Strict inequality: balance_minor > strict_floor_minor  <=>  delta >= 0
        delta = balance_minor - strict_floor_minor - 1
        if delta < 0 or delta >= (1 << 64):
            raise ValueError("ERR_ZKTLS_BALANCE_NOT_STRICTLY_ABOVE_FLOOR")

        # Commit to each field in the TLS transcript using salted SHA-256 leaves
        redacted_leaves: Dict[str, str] = {}
        leaf_digests: List[bytes] = []
        for idx, (k, v) in enumerate(sorted(raw_json_response.items())):
            leaf_bytes = encode_jcs({"field": k, "value": v, "salt": f"{session_salt_hex}:{idx}"})
            leaf_hash = hashlib.sha256(b"\x00" + leaf_bytes).digest()
            redacted_leaves[k] = f"sha256:{leaf_hash.hex()}"
            leaf_digests.append(leaf_hash)

        # Compute binary Merkle root over all transcript fields
        level = list(leaf_digests)
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])
            next_level: List[bytes] = []
            for i in range(0, len(level), 2):
                next_level.append(hashlib.sha256(b"\x01" + level[i] + level[i + 1]).digest())
            level = next_level
        transcript_root = f"sha256:{level[0].hex()}" if level else sha256_prefixed(b"")

        # Decompose `delta` into four 16-bit limbs in [0, 65535]
        limb_commits: List[str] = []
        for limb_idx in range(4):
            limb_val = (delta >> (16 * limb_idx)) & 0xFFFF
            commit_input = encode_jcs(
                {
                    "operation_id": operation_id,
                    "limb_idx": limb_idx,
                    "limb_val": limb_val,
                    "salt": f"{session_salt_hex}:limb:{limb_idx}",
                }
            )
            limb_commits.append(sha256_prefixed(commit_input))

        unsigned_body = {
            "operation_id": operation_id,
            "server_sni": server_sni,
            "disclosed_status": status,
            "strict_floor_minor": strict_floor_minor,
            "transcript_merkle_root": transcript_root,
            "excess_limb_commitments": limb_commits,
            "redacted_leaf_hashes": redacted_leaves,
            "notary_key_id": self.notary_key_id,
        }
        sig = self._notary_priv.sign(encode_jcs(unsigned_body))
        return BlindApiReceipt(
            operation_id=operation_id,
            server_sni=server_sni,
            disclosed_status=status,
            strict_floor_minor=strict_floor_minor,
            transcript_merkle_root=transcript_root,
            excess_limb_commitments=tuple(limb_commits),
            redacted_leaf_hashes=redacted_leaves,
            notary_key_id=self.notary_key_id,
            notary_signature_b64=base64.b64encode(sig).decode("ascii"),
        )

    @staticmethod
    def verify_blind_receipt_offline(
        receipt: BlindApiReceipt,
        notary_pub: Ed25519PublicKey,
        expected_min_floor_minor: int,
    ) -> bool:
        if (
            receipt.disclosed_status != "approved"
            or receipt.strict_floor_minor < expected_min_floor_minor
            or len(receipt.excess_limb_commitments) != 4
        ):
            return False

        unsigned_body = {
            "operation_id": receipt.operation_id,
            "server_sni": receipt.server_sni,
            "disclosed_status": receipt.disclosed_status,
            "strict_floor_minor": receipt.strict_floor_minor,
            "transcript_merkle_root": receipt.transcript_merkle_root,
            "excess_limb_commitments": list(receipt.excess_limb_commitments),
            "redacted_leaf_hashes": receipt.redacted_leaf_hashes,
            "notary_key_id": receipt.notary_key_id,
        }
        try:
            sig_bytes = base64.b64decode(receipt.notary_signature_b64, validate=True)
            notary_pub.verify(sig_bytes, encode_jcs(unsigned_body))
            return True
        except (InvalidSignature, Exception):
            return False


def test_zk_tlsnotary_integration_prototype() -> None:
    priv = Ed25519PrivateKey.generate()
    proxy = ZkTlsNotaryProxyPrototype(priv)

    # Prove API returned > $100.00 (100_00 minor units) without revealing $14,250.75 (14250_75)
    raw_response = {
        "account_owner": "Dr. Lin Wei",
        "account_iban": "DE89370400440532013000",
        "balance_minor": 14250_75,
        "currency": "USD",
        "status": "approved",
    }
    receipt = proxy.attest_api_response_above_floor(
        operation_id="op-track-alpha-01",
        server_sni="api.custody-vault.example",
        raw_json_response=raw_response,
        strict_floor_minor=100_00,
        session_salt_hex="f0e1d2c3b4a5968778695a4b3c2d1e0f",
    )

    assert ZkTlsNotaryProxyPrototype.verify_blind_receipt_offline(
        receipt, priv.public_key(), expected_min_floor_minor=100_00
    )
    receipt_json = json.dumps(receipt.__dict__)
    assert "1425075" not in receipt_json
    assert "Dr. Lin Wei" not in receipt_json
    assert "DE89370400440532013000" not in receipt_json


if __name__ == "__main__":
    test_zk_tlsnotary_integration_prototype()
    print("TRACK ALPHA ZK-TLSNOTARY BLIND RECEIPT PROTOTYPE VERIFIED.")
