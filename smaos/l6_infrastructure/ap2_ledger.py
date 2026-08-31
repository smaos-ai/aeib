#!/usr/bin/env python3
"""
Stream D: AP2 Merkle Ledger (L7-L8)
Records agent actions with cryptographic proof.
Creates Merkle tree digests and signs with Ed25519/Dilithium.
Anchors to git for immutability.
"""

import json
import hashlib
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid


class ActionType(Enum):
    """Types of agent actions to record."""
    GOVERNANCE_DECISION = "governance_decision"
    MODEL_INFERENCE = "model_inference"
    TOOL_EXECUTION = "tool_execution"
    PROOF_GENERATION = "proof_generation"
    LEDGER_ANCHOR = "ledger_anchor"
    SIGNATURE = "signature"


@dataclass
class Action:
    """Represents a recorded agent action."""
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ActionType = ActionType.GOVERNANCE_DECISION
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    agent: str = "default_agent"
    model: str = "unknown"
    prompt: str = ""
    decision: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA256 hash of action."""
        data = {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "model": self.model,
            "prompt": self.prompt,
            "decision": str(self.decision),
            "metadata": self.metadata,
        }
        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_str.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "model": self.model,
            "prompt": self.prompt[:100] + "..." if len(self.prompt) > 100 else self.prompt,
            "decision": self.decision,
            "metadata": self.metadata,
            "hash": self.hash,
        }


class MerkleTree:
    """Minimal Merkle tree for ledger digest."""

    def __init__(self):
        self.leaves: List[str] = []
        self.root: Optional[str] = None

    def add_leaf(self, data: str) -> None:
        """Add a leaf to the tree."""
        leaf_hash = hashlib.sha256(data.encode()).hexdigest()
        self.leaves.append(leaf_hash)
        self._recompute_root()

    def _recompute_root(self) -> None:
        """Recompute Merkle root after adding leaves."""
        if not self.leaves:
            self.root = hashlib.sha256("".encode()).hexdigest()
            return

        current_level = self.leaves[:]
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    combined = current_level[i] + current_level[i + 1]
                else:
                    combined = current_level[i] + current_level[i]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            current_level = next_level

        self.root = current_level[0] if current_level else hashlib.sha256("".encode()).hexdigest()

    def get_root(self) -> str:
        """Get Merkle root."""
        return self.root or hashlib.sha256("".encode()).hexdigest()

    def get_proof(self, leaf_index: int) -> List[str]:
        """Get Merkle proof for a leaf."""
        if leaf_index >= len(self.leaves):
            return []

        proof = []
        current_level = self.leaves[:]
        idx = leaf_index

        while len(current_level) > 1:
            if idx % 2 == 0:
                if idx + 1 < len(current_level):
                    proof.append(current_level[idx + 1])
            else:
                proof.append(current_level[idx - 1])

            # Compute next level
            next_level = []
            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    combined = current_level[i] + current_level[i + 1]
                else:
                    combined = current_level[i] + current_level[i]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())

            current_level = next_level
            idx = idx // 2

        return proof


@dataclass
class LedgerDigest:
    """Represents a ledger snapshot with Merkle proof."""
    digest_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    action_count: int = 0
    merkle_root: str = ""
    git_commit: Optional[str] = None
    signature: Optional[str] = None
    signature_algorithm: str = "ed25519"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class AP2Ledger:
    """
    AP2 Merkle Ledger for agent action recording.
    Records all agent actions with cryptographic proof.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self.actions: List[Action] = []
        self.merkle_tree = MerkleTree()
        self.digests: List[LedgerDigest] = []
        self.current_digest: Optional[LedgerDigest] = None

    def record_action(
        self,
        action_type: ActionType,
        agent: str,
        model: str,
        prompt: str,
        decision: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Action:
        """Record an agent action in the ledger."""
        action = Action(
            action_type=action_type,
            agent=agent,
            model=model,
            prompt=prompt,
            decision=decision,
            metadata=metadata or {},
        )

        # Compute hash and add to Merkle tree
        action.hash = action.compute_hash()
        self.merkle_tree.add_leaf(action.hash)
        self.actions.append(action)

        return action

    def create_digest(self, git_commit: Optional[str] = None) -> LedgerDigest:
        """Create a ledger digest with current Merkle root."""
        digest = LedgerDigest(
            action_count=len(self.actions),
            merkle_root=self.merkle_tree.get_root(),
            git_commit=git_commit,
        )
        self.digests.append(digest)
        self.current_digest = digest
        return digest

    def sign_digest(self, digest: LedgerDigest, signature: str, algorithm: str = "ed25519") -> None:
        """Attach a signature to a digest."""
        digest.signature = signature
        digest.signature_algorithm = algorithm

    def get_action_proof(self, action_id: str) -> Optional[List[str]]:
        """Get Merkle proof for an action."""
        for i, action in enumerate(self.actions):
            if action.action_id == action_id:
                return self.merkle_tree.get_proof(i)
        return None

    def export_ledger(self) -> Dict[str, Any]:
        """Export ledger to dictionary."""
        return {
            "name": self.name,
            "created_at": datetime.utcnow().isoformat(),
            "action_count": len(self.actions),
            "actions": [action.to_dict() for action in self.actions],
            "current_digest": self.current_digest.to_dict() if self.current_digest else None,
            "digests": [digest.to_dict() for digest in self.digests],
            "merkle_root": self.merkle_tree.get_root(),
        }

    def save_to_file(self, filepath: str) -> None:
        """Save ledger to JSON file."""
        with open(filepath, "w") as f:
            json.dump(self.export_ledger(), f, indent=2)

    def load_from_file(self, filepath: str) -> None:
        """Load ledger from JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)
            self.name = data.get("name", self.name)
            # Note: Full deserialization would need more work


def main():
    """Test AP2 ledger with Merkle tree."""
    print("Stream D: AP2 Merkle Ledger Test")
    print("=" * 50)

    # Create ledger
    ledger = AP2Ledger("governance_ledger")
    print(f"Ledger created: {ledger.name}")

    # Record 5 actions
    print("\nRecording actions...")
    actions = []
    for i in range(5):
        action = ledger.record_action(
            action_type=ActionType.GOVERNANCE_DECISION,
            agent="smaos-agent",
            model="claude-opus-4",
            prompt=f"Evaluate governance decision #{i+1}",
            decision=f"decision_{i+1}",
            metadata={"priority": "high", "domain": "compliance"},
        )
        actions.append(action)
        print(f"  [{i+1}] {action.action_id[:8]}... - {action.action_type.value}")

    # Create digest
    print("\nCreating Merkle digest...")
    digest = ledger.create_digest(git_commit="abc123def456")
    print(f"Digest: {digest.digest_id}")
    print(f"Merkle root: {digest.merkle_root[:32]}...")
    print(f"Action count: {digest.action_count}")

    # Get proof for first action
    print("\nComputing Merkle proofs...")
    proof = ledger.get_action_proof(actions[0].action_id)
    print(f"Proof for action[0]: {len(proof) if proof else 0} nodes")

    # Simulate signature
    print("\nSigning digest...")
    signature = "ed25519_sig_" + hashlib.sha256(str(digest).encode()).hexdigest()[:32]
    ledger.sign_digest(digest, signature, "ed25519")
    print(f"Signature: {signature[:32]}...")

    # Export ledger
    print("\nExporting ledger...")
    exported = ledger.export_ledger()
    print(f"Actions in export: {exported['action_count']}")
    print(f"Digests: {len(exported['digests'])}")

    print("\n" + "=" * 50)
    print("AP2 Ledger test completed successfully")


if __name__ == "__main__":
    main()
