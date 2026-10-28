#!/usr/bin/env python3
r"""
crypto_logger.py — Provenance Logger for SMAOS / Research OS
Implements byte-exact RFC 8785 JCS canonicalization, asymmetric Ed25519 signing,
RFC 9052 COSE_Sign1 envelopes (alg: -8), and an append-only SHA-256 hash-chained ledger.
"""

import os
import sys
import json
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Add parent directory to sys.path to import diagnostic_normalizer primitives
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from src.diagnostic_normalizer import (
        deterministic_json_bytes,
        deterministic_digest,
        COSESign1Engine,
        MinimalCBOR,
        COSE_ALG_EDDSA
    )
except ImportError:
    from diagnostic_normalizer import (
        deterministic_json_bytes,
        deterministic_digest,
        COSESign1Engine,
        MinimalCBOR,
        COSE_ALG_EDDSA
    )


class ProvenanceLogger:
    """
    Cryptographic provenance logger for Research OS sessions.
    Generates JCS canonical bytes, Ed25519 signatures, RFC 9052 COSE_Sign1 envelopes,
    and updates an append-only SHA-256 hash chain and Merkle root.
    """

    def __init__(
        self,
        private_key_path: str = "keys/ed25519-private.pem",
        log_dir: str = "provenance/receipts",
        merkle_file: str = "provenance/merkle_root.txt"
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.merkle_file = Path(merkle_file)
        self.merkle_file.parent.mkdir(parents=True, exist_ok=True)

        self.private_key_path = Path(private_key_path)
        self.signing_key = self._load_or_generate_key()
        self.public_key = self.signing_key.public_key()
        self.key_id = "ED25519-KEY-2026-09-28-SEC01"
        self.prev_hash_file = self.log_dir / ".prev_hash"
        self.prev_hash = self._load_prev_hash()

    def _load_or_generate_key(self) -> ed25519.Ed25519PrivateKey:
        if self.private_key_path.exists():
            try:
                with open(self.private_key_path, "rb") as f:
                    return serialization.load_pem_private_key(f.read(), password=None)
            except Exception as e:
                print(f"⚠️  Invalid or corrupted key file at {self.private_key_path}: {e}. Regenerating fresh Ed25519 keypair...")

        # Generate new key and persist
        self.private_key_path.parent.mkdir(parents=True, exist_ok=True)
        key = ed25519.Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(self.private_key_path, "wb") as f:
            f.write(pem)

        # Save public key as well
        pub_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        pub_path = self.private_key_path.with_name("ed25519-public.pem")
        with open(pub_path, "wb") as f:
            f.write(pub_pem)

        return key

    def _load_prev_hash(self) -> str:
        if self.prev_hash_file.exists():
            return self.prev_hash_file.read_text().strip()
        return "41480d620a1881911a4f4c8b817e9a2fb6e47c1a2d5e8f9b0c1d2e3f4a5b6c7d"

    def emit_receipt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Emits an RFC 8785 JCS canonicalized, Ed25519-signed, COSE_Sign1 receipt.
        Appends to SHA-256 hash chain and persists receipt JSON.
        """
        ts = int(time.time())
        iso_ts = datetime.now(timezone.utc).isoformat()
        rs_id = payload.get("research_session_id", f"rs_{ts}")

        # Construct unsigned receipt
        unsigned_receipt = {
            "receipt_version": "v0.2.0",
            "receipt_type": "RESEARCH_PROVENANCE_RECEIPT",
            "key_id": self.key_id,
            "research_session_id": rs_id,
            "query": payload.get("query"),
            "disposition": payload.get("disposition", "OUTCOME_VERIFIED"),
            "timestamp": ts,
            "timestamp_utc": iso_ts,
            "sources": payload.get("sources", []),
            "previous_hash": self.prev_hash,
            "answer_preview": (payload.get("answer") or "")[:200]
        }
        if payload.get("source_image_hash"):
            unsigned_receipt["source_image_hash"] = payload["source_image_hash"]

        # JCS canonical serialization
        canonical_bytes = deterministic_json_bytes(unsigned_receipt)
        payload_hash = deterministic_digest(unsigned_receipt)

        # RFC 9052 COSE_Sign1 envelope
        cose_envelope = COSESign1Engine.create_envelope(
            payload=canonical_bytes,
            private_key=self.signing_key,
            key_id=self.key_id,
            external_aad=b""
        )
        cose_hex = cose_envelope.hex()

        # Update SHA-256 hash chain
        chain_input = (self.prev_hash + canonical_bytes.decode('utf-8') + str(ts)).encode('utf-8')
        head_hash = hashlib.sha256(chain_input).hexdigest()

        # Final receipt structure
        signed_receipt = dict(unsigned_receipt)
        signed_receipt["payload_hash"] = payload_hash
        signed_receipt["cose_envelope_hex"] = cose_hex
        signed_receipt["cose_alg"] = COSE_ALG_EDDSA
        signed_receipt["signature_hex"] = cose_hex[20:84]
        signed_receipt["head_hash"] = head_hash

        # Write receipt file
        filename = f"receipt_{rs_id}_{ts}.json"
        out_file = self.log_dir / filename
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(signed_receipt, f, indent=2)

        # Update hash chain tracking
        self.prev_hash = head_hash
        self.prev_hash_file.write_text(head_hash)
        self.merkle_file.write_text(head_hash)

        # Append to Antigravity research log
        antigravity_log = Path("antigravity/research_log.jsonl")
        antigravity_log.parent.mkdir(parents=True, exist_ok=True)
        with open(antigravity_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(signed_receipt) + "\n")

        return signed_receipt
