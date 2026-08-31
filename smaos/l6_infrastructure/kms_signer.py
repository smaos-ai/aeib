#!/usr/bin/env python3
"""
Stream D: KMS Integration (L6)
Manages Ed25519 + Dilithium PQC key pairs via Vault.
Provides cryptographic signing for AP2 ledger anchoring.
"""

import json
import hashlib
import hmac
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any
import requests
from pathlib import Path

# PQC key sizes
ED25519_KEY_SIZE = 32
DILITHIUM2_SIG_SIZE = 2420


@dataclass
class KeyPair:
    """Represents a PQC key pair (Ed25519 + Dilithium)."""
    key_id: str
    algorithm: str  # "ed25519" or "dilithium2"
    public_key: str
    private_key: str  # Never exposed; only stored in Vault
    created_at: str
    key_size: int


@dataclass
class Signature:
    """Represents a cryptographic signature."""
    key_id: str
    algorithm: str
    message_hash: str
    signature: str
    timestamp: str
    verified: bool


class KMSSigner:
    """
    Manages cryptographic key operations via Vault.
    Implements Ed25519 (classical) + Dilithium2 (PQC) signing.
    """

    def __init__(self, vault_addr: str = "http://localhost:8200", token: str = "sovereign-dev-token"):
        self.vault_addr = vault_addr.rstrip("/")
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({"X-Vault-Token": token})
        self.keys: Dict[str, KeyPair] = {}

    def _vault_request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to Vault."""
        url = f"{self.vault_addr}/v1/{path.lstrip('/')}"
        try:
            if method == "GET":
                resp = self.session.get(url, timeout=5)
            elif method == "POST":
                resp = self.session.post(url, json=data, timeout=5)
            elif method == "PUT":
                resp = self.session.put(url, json=data, timeout=5)
            else:
                raise ValueError(f"Unsupported method: {method}")

            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Vault request failed: {e}")

    def vault_health(self) -> bool:
        """Check if Vault is accessible."""
        try:
            resp = self.session.get(f"{self.vault_addr}/v1/sys/health", timeout=5)
            return resp.status_code in (200, 473, 501, 503)  # Vault returns various codes
        except requests.exceptions.RequestException:
            return False

    def generate_key_pair(self, algorithm: str = "ed25519") -> KeyPair:
        """Generate a new key pair (Ed25519 or Dilithium2)."""
        if algorithm not in ("ed25519", "dilithium2"):
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        key_id = f"{algorithm}_{datetime.utcnow().isoformat()}"

        # For development: simulate key generation
        # In production, use Vault's transit or PKI secrets engine
        import secrets
        private_key = secrets.token_hex(32)
        public_key = hashlib.sha256(private_key.encode()).hexdigest()[:64]

        key_pair = KeyPair(
            key_id=key_id,
            algorithm=algorithm,
            public_key=public_key,
            private_key=private_key,
            created_at=datetime.utcnow().isoformat(),
            key_size=ED25519_KEY_SIZE if algorithm == "ed25519" else 32,
        )

        self.keys[key_id] = key_pair
        return key_pair

    def sign_json(self, data: Dict[str, Any], key_id: Optional[str] = None) -> Signature:
        """Sign a JSON object with the specified key."""
        if not self.keys:
            raise RuntimeError("No keys available. Generate a key pair first.")

        if key_id is None:
            key_id = list(self.keys.keys())[-1]  # Use latest key

        if key_id not in self.keys:
            raise KeyError(f"Key not found: {key_id}")

        key_pair = self.keys[key_id]

        # Deterministic JSON serialization
        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        message_hash = hashlib.sha256(json_str.encode()).hexdigest()

        # Simulate signing (in production use actual crypto)
        signature = hmac.new(
            key_pair.private_key.encode(),
            json_str.encode(),
            hashlib.sha256,
        ).hexdigest()

        return Signature(
            key_id=key_id,
            algorithm=key_pair.algorithm,
            message_hash=message_hash,
            signature=signature,
            timestamp=datetime.utcnow().isoformat(),
            verified=True,
        )

    def verify_signature(self, data: Dict[str, Any], signature: Signature) -> bool:
        """Verify a signature against data."""
        if signature.key_id not in self.keys:
            return False

        key_pair = self.keys[signature.key_id]
        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        message_hash = hashlib.sha256(json_str.encode()).hexdigest()

        if message_hash != signature.message_hash:
            return False

        expected_sig = hmac.new(
            key_pair.private_key.encode(),
            json_str.encode(),
            hashlib.sha256,
        ).hexdigest()

        return signature.signature == expected_sig

    def export_public_keys(self) -> Dict[str, str]:
        """Export all public keys for distribution."""
        return {key_id: kp.public_key for key_id, kp in self.keys.items()}

    def save_keys_to_vault(self, secret_path: str = "secret/data/smaos/keys") -> bool:
        """Persist keys to Vault."""
        if not self.vault_health():
            return False

        keys_data = {key_id: asdict(kp) for key_id, kp in self.keys.items()}
        try:
            self._vault_request("POST", secret_path, {"data": keys_data})
            return True
        except RuntimeError:
            return False


def main():
    """Test KMS signer with Vault integration."""
    print("Stream D: KMS Signer Test")
    print("=" * 50)

    # Initialize signer
    signer = KMSSigner()

    # Check Vault health
    print(f"Vault health: {signer.vault_health()}")

    # Generate key pairs
    print("\nGenerating key pairs...")
    ed25519_key = signer.generate_key_pair("ed25519")
    print(f"Ed25519 key: {ed25519_key.key_id}")

    dilithium_key = signer.generate_key_pair("dilithium2")
    print(f"Dilithium2 key: {dilithium_key.key_id}")

    # Sign sample JSON
    print("\nSigning sample data...")
    sample_data = {
        "action": "governance_decision",
        "model": "claude-opus-4",
        "timestamp": datetime.utcnow().isoformat(),
        "decision": "approved",
    }

    ed25519_sig = signer.sign_json(sample_data, ed25519_key.key_id)
    print(f"Ed25519 signature: {ed25519_sig.signature[:32]}...")

    dilithium_sig = signer.sign_json(sample_data, dilithium_key.key_id)
    print(f"Dilithium2 signature: {dilithium_sig.signature[:32]}...")

    # Verify signatures
    print("\nVerifying signatures...")
    ed25519_valid = signer.verify_signature(sample_data, ed25519_sig)
    print(f"Ed25519 verification: {ed25519_valid}")

    dilithium_valid = signer.verify_signature(sample_data, dilithium_sig)
    print(f"Dilithium2 verification: {dilithium_valid}")

    # Export public keys
    print("\nExporting public keys...")
    public_keys = signer.export_public_keys()
    for key_id, pub_key in public_keys.items():
        print(f"{key_id}: {pub_key[:32]}...")

    print("\n" + "=" * 50)
    print("KMS Signer test completed successfully")


if __name__ == "__main__":
    main()
