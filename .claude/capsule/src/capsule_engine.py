"""
CAPSULE Tier 1 Cryptographic Engine.

Implements Ed25519 signing and Merkle root integrity for CAPSULE capsules.
"""

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import hashlib
import json
import time
from datetime import datetime
from typing import Dict, List, Optional


class Ed25519KeyPair:
    """Ed25519 keypair wrapper for CAPSULE signing."""

    def __init__(self, private_key: ed25519.Ed25519PrivateKey = None):
        """
        Initialize keypair.

        Args:
            private_key: Optional Ed25519 private key. If None, generates new.
        """
        if private_key is None:
            private_key = ed25519.Ed25519PrivateKey.generate()

        self.private_key = private_key
        self.public_key = private_key.public_key()

        # Export raw bytes for testing and distribution
        self.private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        self.public_key_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

    def sign(self, message: bytes) -> bytes:
        """
        Sign a message with private key.

        Args:
            message: Bytes to sign

        Returns:
            64-byte signature
        """
        return self.private_key.sign(message)

    def verify(self, message: bytes, signature: bytes) -> bool:
        """
        Verify a signature with public key.

        Args:
            message: Bytes that were signed
            signature: Signature to verify

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            self.public_key.verify(signature, message)
            return True
        except Exception:
            return False

    def get_public_key_pem(self) -> str:
        """
        Export public key in PEM format.

        Returns:
            PEM-encoded public key string
        """
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()


class CapsuleEngine:
    """
    CAPSULE Tier 1 cryptographic integrity engine.

    Provides:
    - Ed25519 mutation signing
    - Merkle root computation and evolution
    - Audit trail logging
    - Tamper detection
    """

    def __init__(self, capsule_id: str = "capsule-001"):
        """
        Initialize CAPSULE engine.

        Args:
            capsule_id: Unique identifier for this capsule
        """
        self.capsule_id = capsule_id
        self.state: Dict = {}
        self.merkle_root: Optional[str] = None
        self.keypair = Ed25519KeyPair()
        self.audit_trail: List[Dict] = []
        self._mutation_counter = 0

    def _sign_mutation(self, payload: bytes) -> bytes:
        """
        Ed25519 sign mutation payload.

        Args:
            payload: Bytes to sign

        Returns:
            64-byte signature
        """
        return self.keypair.sign(payload)

    def _compute_merkle_root(
        self,
        old_root: Optional[bytes],
        payload: bytes,
        signature: bytes
    ) -> str:
        """
        Compute new Merkle root: SHA256(old_root || SHA256(payload || signature)).

        Args:
            old_root: Previous Merkle root bytes (None for first mutation)
            payload: Mutation payload bytes
            signature: Signature bytes

        Returns:
            Merkle root as hex string (64 chars)
        """
        if old_root is None:
            old_root = b""

        # Inner hash: SHA256(payload || signature)
        inner_hash = hashlib.sha256(payload + signature).digest()

        # Outer hash: SHA256(old_root || inner_hash)
        outer_hash = hashlib.sha256(old_root + inner_hash).digest()

        return outer_hash.hex()

    def mutate(self, operation: str, data: Dict) -> str:
        """
        Apply a mutation to capsule state and update Merkle root.

        Args:
            operation: Type of operation (e.g., "SET", "DELETE")
            data: Data associated with mutation

        Returns:
            New Merkle root hash (hex string, 64 chars)
        """
        # Increment counter for uniqueness
        self._mutation_counter += 1

        # Create payload: operation:data:counter
        payload_str = f"{operation}:{str(data)}:{self._mutation_counter}"
        payload = payload_str.encode()

        # Sign the payload
        signature = self._sign_mutation(payload)

        # Update state
        if operation == "SET":
            self.state.update(data)
        elif operation == "DELETE":
            for key in data:
                self.state.pop(key, None)

        # Compute new Merkle root
        old_root_bytes = bytes.fromhex(self.merkle_root) if self.merkle_root else None
        self.merkle_root = self._compute_merkle_root(old_root_bytes, payload, signature)

        # Log to audit trail
        self.audit_trail.append({
            "operation": operation,
            "capsule_id": self.capsule_id,
            "timestamp": datetime.utcnow().isoformat(),
            "signature": signature.hex(),
            "merkle_hash": self.merkle_root,
            "payload": payload.hex()
        })

        return self.merkle_root

    def verify_merkle_root(self) -> bool:
        """
        Verify integrity by reconstructing Merkle root from audit trail.

        Returns:
            True if computed root matches stored root, False otherwise
        """
        if not self.audit_trail:
            return self.merkle_root is None

        computed_root = None
        for entry in self.audit_trail:
            payload = bytes.fromhex(entry["payload"])
            signature = bytes.fromhex(entry["signature"])
            old_root_bytes = bytes.fromhex(computed_root) if computed_root else None
            computed_root = self._compute_merkle_root(old_root_bytes, payload, signature)

        return computed_root == self.merkle_root

    def verify_signature(self, payload: str, signature_hex: str) -> bool:
        """
        Verify Ed25519 signature against public key.

        Args:
            payload: Original payload string
            signature_hex: Hex-encoded signature

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            signature = bytes.fromhex(signature_hex)
            return self.keypair.verify(payload.encode(), signature)
        except Exception:
            return False

    def get_public_key_pem(self) -> str:
        """
        Export public key for distribution.

        Returns:
            PEM-encoded public key string
        """
        return self.keypair.get_public_key_pem()

    def corrupt_state(self, key: str, new_value) -> None:
        """Artificially corrupt state (for tamper detection testing)."""
        self.state[key] = new_value

    def corrupt_merkle_root(self) -> None:
        """Artificially corrupt Merkle root (for tamper detection testing)."""
        if self.merkle_root:
            # Flip a bit in the Merkle root
            corrupted = int(self.merkle_root, 16) ^ 0x1
            self.merkle_root = format(corrupted, '064x')
