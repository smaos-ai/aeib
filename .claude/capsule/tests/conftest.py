"""
Pytest fixtures and test configuration for CAPSULE Tier 1 cryptographic integrity tests.

This module provides:
- CapsuleEngine mock class
- Ed25519 keypair fixtures
- Utility functions for test cryptographic operations
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, List, Tuple
import hashlib
import secrets
import sys
from pathlib import Path

# Add src directory to Python path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class Ed25519TestKeyPair:
    """Test fixture for Ed25519 keypair generation and signing."""

    def __init__(self):
        """Initialize with deterministic test keypair (for reproducibility)."""
        from cryptography.hazmat.primitives.asymmetric import ed25519

        # Use a fixed seed for reproducible test keypair
        # In real implementation, this would be random
        seed = b'\x00' * 32  # 32-byte seed for reproducibility
        self.private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        self.public_key = self.private_key.public_key()

        # Export raw bytes
        self.private_key_bytes = seed  # 32 bytes
        self.public_key_bytes = self.public_key.public_bytes_raw()  # 32 bytes

    def sign(self, message: bytes) -> bytes:
        """
        Sign with Ed25519 private key.

        Args:
            message: Bytes to sign

        Returns:
            64-byte Ed25519 signature
        """
        return self.private_key.sign(message)

    def verify(self, message: bytes, signature: bytes) -> bool:
        """
        Verify Ed25519 signature with public key.

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


class CapsuleEngineMock:
    """
    Mock CapsuleEngine for testing cryptographic integrity.

    Attributes:
        capsule_id: Unique identifier for this capsule
        state: Current mutable state (dict)
        merkle_root: Current Merkle root hash (None initially)
        keypair: Ed25519 keypair for signing mutations
        audit_trail: List of mutation records
        _mutation_counter: Internal counter for generating unique state
    """

    def __init__(self, capsule_id: str = "test-capsule-001"):
        """Initialize CapsuleEngine with cryptographic components."""
        self.capsule_id = capsule_id
        self.state = {}
        self.merkle_root = None  # Test 1: Should initialize as None
        self.keypair = Ed25519TestKeyPair()
        self.audit_trail: List[Dict] = []
        self._mutation_counter = 0
        self._previous_merkle_root = None

    def _sign_mutation(self, payload: bytes) -> bytes:
        """
        Sign a mutation payload.

        Args:
            payload: Bytes to sign

        Returns:
            Signature as bytes (should be 64 bytes for Ed25519)
        """
        return self.keypair.sign(payload)

    def _compute_merkle_root(self, old_root: bytes, payload: bytes, signature: bytes) -> str:
        """
        Compute new Merkle root: SHA256(old_root || SHA256(payload || signature)).

        Args:
            old_root: Previous Merkle root (bytes or None)
            payload: Mutation payload (bytes)
            signature: Signature of mutation (bytes)

        Returns:
            Merkle root as hex string
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
            New Merkle root hash
        """
        # Increment counter to create unique state
        self._mutation_counter += 1

        # Create payload: operation + data + counter
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
        self._previous_merkle_root = self.merkle_root
        self.merkle_root = self._compute_merkle_root(old_root_bytes, payload, signature)

        # Log to audit trail
        self.audit_trail.append({
            "operation": operation,
            "capsule_id": self.capsule_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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

    def corrupt_state(self, key: str, new_value) -> None:
        """Artificially corrupt state (for tamper detection testing)."""
        self.state[key] = new_value

    def corrupt_merkle_root(self) -> None:
        """Artificially corrupt Merkle root (for tamper detection testing)."""
        if self.merkle_root:
            # Flip a bit in the Merkle root
            corrupted = int(self.merkle_root, 16) ^ 0x1
            self.merkle_root = format(corrupted, '064x')


@pytest.fixture
def keypair() -> Ed25519TestKeyPair:
    """Provide an Ed25519 test keypair."""
    return Ed25519TestKeyPair()


@pytest.fixture
def capsule_engine() -> CapsuleEngineMock:
    """Provide a fresh CapsuleEngine instance for each test."""
    return CapsuleEngineMock()


@pytest.fixture
def capsule_engine_with_mutations() -> CapsuleEngineMock:
    """Provide a CapsuleEngine with several pre-applied mutations."""
    engine = CapsuleEngineMock()
    engine.mutate("SET", {"key1": "value1"})
    engine.mutate("SET", {"key2": "value2"})
    engine.mutate("SET", {"key3": "value3"})
    return engine


@pytest.fixture
def sample_payload() -> bytes:
    """Provide a sample payload for testing."""
    return b"test_payload_data_for_signing"


@pytest.fixture
def sample_signature(keypair: Ed25519TestKeyPair, sample_payload: bytes) -> bytes:
    """Provide a valid signature for the sample payload."""
    return keypair.sign(sample_payload)


# ============================================================================
# TIER 5 FIXTURES (Holographic Operator Mesh)
# ============================================================================

@pytest.fixture
def sample_timestamp():
    """Provide a sample ISO 8601 timestamp."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def sample_agent_ids():
    """Provide a list of sample agent IDs for testing."""
    return ["agent_prague_001", "agent_frankfurt_002", "agent_london_003", "agent_tokyo_004"]


@pytest.fixture
def sample_metrics():
    """Provide a dict of sample metrics for state vectors."""
    return {
        "cpu_usage": 0.45,
        "memory_usage": 0.62,
        "latency_ms": 85.3,
        "throughput_rps": 1250.0
    }


@pytest.fixture
def prague_frankfurt_latency():
    """Provide latency between Prague and Frankfurt data centers (milliseconds)."""
    return 12.5  # Realistic inter-EU latency


# ============================================================================
# TIER 2 FIXTURES (Deterministic LLM Abstraction)
# ============================================================================

class MockLLMService:
    """
    Mock LLM service for testing CAPSULE Tier 2 deterministic caching.

    Attributes:
        call_count: Number of times service was invoked
        call_history: List of (prompt, temperature) tuples
        response_map: Dict mapping prompts to responses
        failure_mode: If set, raises exception on call
    """

    def __init__(self):
        """Initialize mock LLM service."""
        self.call_count = 0
        self.call_history: List[Tuple[str, float]] = []
        self.response_map: Dict[str, Dict] = {}
        self.failure_mode: Optional[str] = None

    def call(self, prompt: str, temperature: float = 0.0) -> Dict[str, Any]:
        """
        Mock LLM call.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature (should be 0.0 for determinism)

        Returns:
            Response dict with schema: {status, content, timestamp, model, tokens_used}

        Raises:
            Exception if failure_mode is set
        """
        self.call_count += 1
        self.call_history.append((prompt, temperature))

        if self.failure_mode:
            raise Exception(self.failure_mode)

        # Return pre-configured response or default
        if prompt in self.response_map:
            return self.response_map[prompt]

        # Default response
        from datetime import datetime, timezone
        return {
            "status": "success",
            "content": f"Response to: {prompt}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "claude-3-haiku",
            "tokens_used": 150
        }

    def reset(self):
        """Reset all counters and history."""
        self.call_count = 0
        self.call_history.clear()
        self.failure_mode = None
