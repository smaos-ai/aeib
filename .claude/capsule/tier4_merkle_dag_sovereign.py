"""
CAPSULE Tier 4 Merkle-DAG Sovereign Signature Framework — Production Hardening.

Implements tamper detection and sovereign audit trails for SovereignNexus:
- MerkleDAG: compute root hash from state vector (SHA256 tree)
- SovereignSigner: Ed25519 key generation, mutation signing
- TamperDetector: verify signatures, detect state changes
- AuditTrail: immutable log of all mutations (timestamp, signer, hash, signature)
- StateValidator: confirm Merkle root matches signed state

Architecture:
  State Mutation → SovereignSigner.sign()
               → TamperDetector.detect()
               → MerkleDAG.compute_root()
               → StateValidator.validate()
               → AuditTrail.append()
               → Immutable audit chain

Security: Ed25519 signatures, SHA256 Merkle tree, append-only audit trail.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)


class MerkleDAG:
    """
    Compute Merkle root hash from state vector.

    Builds binary SHA256 tree:
    1. Sort state keys
    2. Hash leaves: SHA256(key || json_value)
    3. Build parent hashes: SHA256(left_hash || right_hash)
    4. Return root hex string (64 chars, 32 bytes)

    Guarantees: deterministic, same state → same root, tamper-detectable.
    """

    @staticmethod
    def _serialize_value(value: Any) -> bytes:
        """Serialize value to deterministic JSON."""
        return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()

    @staticmethod
    def _hash_leaf(key: str, value: Any) -> bytes:
        """Hash a single state element: SHA256(key || serialized_value)."""
        key_bytes = key.encode()
        value_bytes = MerkleDAG._serialize_value(value)
        return hashlib.sha256(key_bytes + value_bytes).digest()

    @staticmethod
    def _hash_pair(left: bytes, right: bytes) -> bytes:
        """Hash pair of child hashes: SHA256(left || right)."""
        return hashlib.sha256(left + right).digest()

    @staticmethod
    def _build_tree(leaves: List[bytes]) -> bytes:
        """
        Build Merkle tree from leaves.

        Iteratively pair and hash until single root remains.
        If odd number of nodes at any level, last node paired with itself.
        """
        if not leaves:
            # Empty tree: hash empty string
            return hashlib.sha256(b"").digest()

        nodes = leaves.copy()

        while len(nodes) > 1:
            next_level = []

            # Pair up nodes
            for i in range(0, len(nodes), 2):
                left = nodes[i]

                # If odd number, pair last with itself
                if i + 1 < len(nodes):
                    right = nodes[i + 1]
                else:
                    right = left

                parent = MerkleDAG._hash_pair(left, right)
                next_level.append(parent)

            nodes = next_level

        return nodes[0]

    def compute_root(self, state: Dict[str, Any]) -> str:
        """
        Compute Merkle root from state dict.

        Args:
            state: State dictionary (flat or nested)

        Returns:
            Merkle root as 64-character hex string (SHA256)
        """
        if not state:
            # Empty state
            return hashlib.sha256(b"").hexdigest()

        # Sort keys for determinism
        sorted_keys = sorted(state.keys())

        # Hash leaves
        leaves = [
            self._hash_leaf(key, state[key])
            for key in sorted_keys
        ]

        # Build tree and get root
        root_hash = self._build_tree(leaves)

        return root_hash.hex()

    def generate_proof(self, state: Dict[str, Any], key: str) -> List[str]:
        """
        Generate Merkle proof for a specific key.

        Returns list of sibling hashes from leaf to root.

        Args:
            state: State dict
            key: Key to prove

        Returns:
            List of sibling hashes (hex strings) with position info encoded
        """
        if key not in state:
            return []

        sorted_keys = sorted(state.keys())
        if key not in sorted_keys:
            return []

        # Find target leaf index
        target_idx = sorted_keys.index(key)

        # Build leaves with their indices
        leaves = [
            (i, self._hash_leaf(k, state[k]))
            for i, k in enumerate(sorted_keys)
        ]

        # Build proof recursively - returns list of (hash, position) tuples
        proof_with_positions = []
        self._build_proof_recursive(leaves, target_idx, proof_with_positions)

        # Encode proof as: "LEFT:hash" or "RIGHT:hash" to preserve position info
        proof = [f"{pos}:{h}" for h, pos in proof_with_positions]
        return proof

    def _build_proof_recursive(
        self,
        nodes: List[Tuple[int, bytes]],
        target_idx: int,
        proof: List[Tuple[str, str]]  # (sibling_hash, position: 'left' or 'right')
    ) -> bytes:
        """
        Recursively build proof and compute parent hash.

        Args:
            nodes: List of (index, hash) tuples at current level
            target_idx: Index of target leaf
            proof: Proof list to accumulate (sibling_hash, position) tuples

        Returns:
            Parent hash for this level
        """
        if len(nodes) == 1:
            # Reached root
            return nodes[0][1]

        # Pair up nodes
        next_level = []

        for i in range(0, len(nodes), 2):
            left_idx, left_hash = nodes[i]

            if i + 1 < len(nodes):
                right_idx, right_hash = nodes[i + 1]
            else:
                # Odd node: pair with itself
                right_idx, right_hash = left_idx, left_hash

            # Check if target is in left or right subtree
            if left_idx == target_idx:
                # Target is left node, right is sibling (on the right)
                if i + 1 < len(nodes):
                    proof.append((right_hash.hex(), 'right'))
                parent_hash = self._hash_pair(left_hash, right_hash)
                next_level.append((left_idx, parent_hash))
            elif right_idx == target_idx:
                # Target is right node, left is sibling (on the left)
                proof.append((left_hash.hex(), 'left'))
                parent_hash = self._hash_pair(left_hash, right_hash)
                next_level.append((right_idx, parent_hash))
            else:
                # Target not in this pair
                parent_hash = self._hash_pair(left_hash, right_hash)
                next_level.append((min(left_idx, right_idx), parent_hash))

        # Continue up the tree
        return self._build_proof_recursive(next_level, target_idx, proof)

    def verify_proof(
        self,
        root: str,
        key: str,
        value: Any,
        proof: List[str]
    ) -> bool:
        """
        Verify Merkle proof for a key-value pair.

        Args:
            root: Expected Merkle root (hex string)
            key: Key claimed to be in state
            value: Value claimed for key
            proof: Proof path (list of "LEFT:hash" or "RIGHT:hash" strings)

        Returns:
            True if proof is valid, False otherwise
        """
        # Hash the leaf
        current_hash = self._hash_leaf(key, value)

        # Apply proof hashes in order
        for proof_entry in proof:
            try:
                # Parse position and hash from "LEFT:hash" or "RIGHT:hash"
                if ':' in proof_entry:
                    position, proof_hash = proof_entry.split(':', 1)
                else:
                    # Backward compatibility: assume right if no position
                    position = 'right'
                    proof_hash = proof_entry

                sibling_bytes = bytes.fromhex(proof_hash)

                # Combine based on position
                if position.upper() == 'LEFT':
                    current_hash = self._hash_pair(sibling_bytes, current_hash)
                else:  # RIGHT
                    current_hash = self._hash_pair(current_hash, sibling_bytes)

            except (ValueError, TypeError):
                return False

        # Verify root matches
        computed_root = current_hash.hex()
        return computed_root == root


class SovereignSigner:
    """
    Ed25519 sovereign signer for mutation authorization.

    Generates keypair on init, signs mutations deterministically.
    Public key can be shared; private key must be protected.
    """

    def __init__(self):
        """
        Initialize sovereign signer with random Ed25519 keypair.

        Generates fresh keypair on each instantiation.
        """
        # Generate random Ed25519 keypair
        self.private_key = ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()

        # Export raw bytes
        self.public_key_bytes = self.public_key.public_bytes_raw()

    def sign(self, message: bytes) -> bytes:
        """
        Sign message with Ed25519 private key.

        Args:
            message: Bytes to sign

        Returns:
            64-byte Ed25519 signature
        """
        return self.private_key.sign(message)

    def verify(
        self,
        message: bytes,
        signature: bytes,
        public_key_bytes: bytes
    ) -> bool:
        """
        Verify Ed25519 signature.

        Args:
            message: Original message bytes
            signature: Signature to verify (64 bytes)
            public_key_bytes: Public key (32 bytes)

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Reconstruct public key from bytes
            from cryptography.hazmat.primitives.asymmetric import ed25519
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)

            # Verify signature
            public_key.verify(signature, message)
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False


class TamperDetector:
    """
    Detect tampering via Ed25519 signature verification.

    Logs all verification attempts, detects invalid signatures.
    Maintains event history for audit purposes.
    """

    def __init__(self):
        """Initialize tamper detector with empty event log."""
        self.events: List[Dict[str, Any]] = []
        self.signer = SovereignSigner()

    def detect(
        self,
        message: bytes,
        signature: bytes,
        public_key_bytes: bytes
    ) -> bool:
        """
        Detect if message-signature pair is valid.

        Args:
            message: Message that should have been signed
            signature: Signature to verify
            public_key_bytes: Public key for verification

        Returns:
            True if valid (not tampered), False if invalid (tampered)
        """
        # Verify signature
        is_valid = self.signer.verify(message, signature, public_key_bytes)

        # Log event
        message_hash = hashlib.sha256(message).hexdigest()
        self.events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_hash": message_hash,
            "verdict": "valid" if is_valid else "invalid",
            "signature_valid": is_valid
        })

        return is_valid

    def get_events(self) -> List[Dict[str, Any]]:
        """
        Get all detection events.

        Returns:
            List of event records in order
        """
        # Return deep copy to prevent external modification
        return [dict(e) for e in self.events]


class AuditTrail:
    """
    Immutable append-only audit trail for mutations.

    Records: timestamp, signer, merkle_hash, signature
    Prevents deletion or modification of past records.
    """

    def __init__(self):
        """Initialize empty audit trail."""
        self._records: List[Dict[str, Any]] = []
        self._sequence_counter = 0

    def append(self, record: Dict[str, Any]) -> None:
        """
        Append mutation record to audit trail.

        Args:
            record: Record dict with timestamp, signer, merkle_hash, signature
        """
        # Create immutable copy with sequence number
        immutable_record = dict(record)
        immutable_record["sequence"] = self._sequence_counter
        self._sequence_counter += 1

        self._records.append(immutable_record)

    def get_records(self) -> List[Dict[str, Any]]:
        """
        Get all audit trail records in order.

        Returns:
            List of deep-copied records (prevents external modification)
        """
        return [dict(r) for r in self._records]

    def get_record_count(self) -> int:
        """Get total number of records in audit trail."""
        return len(self._records)


class StateValidator:
    """
    Validate state against Merkle root and audit trail.

    Confirms state integrity by:
    1. Recomputing Merkle root from state
    2. Comparing against expected root
    3. Validating against audit trail (optional)
    """

    def __init__(self):
        """Initialize state validator."""
        self.dag = MerkleDAG()

    def validate(self, state: Dict[str, Any], expected_root: str) -> bool:
        """
        Validate state matches expected Merkle root.

        Args:
            state: Current state dict
            expected_root: Expected Merkle root (hex string)

        Returns:
            True if state is valid, False if tampered
        """
        computed_root = self.dag.compute_root(state)
        return computed_root == expected_root

    def validate_with_trail(
        self,
        state: Dict[str, Any],
        expected_root: str,
        trail: "AuditTrail"
    ) -> bool:
        """
        Validate state against expected root and audit trail.

        Args:
            state: Current state dict
            expected_root: Expected Merkle root
            trail: Audit trail to validate against

        Returns:
            True if state and trail are consistent
        """
        # First validate state matches root
        if not self.validate(state, expected_root):
            return False

        # Validate trail has at least one record
        records = trail.get_records()
        if not records:
            # Empty trail is valid if root is for empty state
            return expected_root == self.dag.compute_root({})

        # Validate last record's merkle_hash matches expected_root
        last_record = records[-1]
        return last_record.get("merkle_hash") == expected_root


@dataclass
class MerkleDAGConfig:
    """Configuration for Merkle-DAG sovereign signature framework."""
    hash_algorithm: str = "sha256"
    signature_algorithm: str = "ed25519"
    enable_audit_trail: bool = True
    max_trail_size: int = 1_000_000


class SovereignSignatureFramework:
    """
    Production-hardened Merkle-DAG sovereign signature framework.

    Integrates all Tier 4 components:
    - State mutations
    - Ed25519 signing
    - Tamper detection
    - Audit trail
    - State validation

    Single entry point for all Tier 4 operations.
    """

    def __init__(self, config: Optional[MerkleDAGConfig] = None):
        """
        Initialize framework with configuration.

        Args:
            config: Optional configuration (uses defaults if None)
        """
        self.config = config or MerkleDAGConfig()
        self.dag = MerkleDAG()
        self.signer = SovereignSigner()
        self.detector = TamperDetector()
        self.trail = AuditTrail()
        self.validator = StateValidator()
        self._state: Dict[str, Any] = {}
        self._current_root: Optional[str] = None

    def initialize_state(self, state: Dict[str, Any]) -> str:
        """
        Initialize framework with initial state.

        Args:
            state: Initial state dict

        Returns:
            Initial Merkle root (hex string)
        """
        self._state = dict(state)
        self._current_root = self.dag.compute_root(self._state)
        return self._current_root

    def mutate(self, new_state: Dict[str, Any]) -> Tuple[str, bytes]:
        """
        Apply state mutation and sign it.

        Args:
            new_state: New state after mutation

        Returns:
            Tuple of (new_merkle_root, signature)
        """
        # Sign the new state
        state_bytes = json.dumps(new_state, sort_keys=True).encode()
        signature = self.signer.sign(state_bytes)

        # Verify signature
        if not self.detector.detect(state_bytes, signature, self.signer.public_key_bytes):
            raise ValueError("Signature verification failed (internal error)")

        # Update state
        self._state = dict(new_state)
        self._current_root = self.dag.compute_root(self._state)

        # Record in audit trail
        if self.config.enable_audit_trail:
            self.trail.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signer": self.signer.public_key_bytes.hex(),
                "merkle_hash": self._current_root,
                "signature": signature.hex()
            })

        return self._current_root, signature

    def get_state(self) -> Dict[str, Any]:
        """Get current state."""
        return dict(self._state)

    def get_current_root(self) -> Optional[str]:
        """Get current Merkle root."""
        return self._current_root

    def get_public_key(self) -> bytes:
        """Get signer's public key."""
        return self.signer.public_key_bytes

    def verify_integrity(self) -> bool:
        """
        Verify overall integrity of state and audit trail.

        Returns:
            True if state, root, and trail are all consistent
        """
        if self._current_root is None:
            return True

        # Verify state matches root
        if not self.validator.validate(self._state, self._current_root):
            return False

        # Verify state matches trail
        if self.config.enable_audit_trail:
            if not self.validator.validate_with_trail(
                self._state,
                self._current_root,
                self.trail
            ):
                return False

        return True

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Get complete audit trail."""
        return self.trail.get_records()
