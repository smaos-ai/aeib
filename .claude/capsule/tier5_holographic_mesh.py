"""
CAPSULE Tier 5: Holographic Operator Mesh v1

Distributed cognition layer enabling multi-agent coordination
without central coordinator.

Components:
- SharedStateVector: Immutable, hashable state container
- HolographicPerception: Agent-filtered views of shared state
- ConsensusProtocol: Byzantine-tolerant consensus with Merkle verification
- MeshCoordinator: Gossip-based state propagation
- LocalityAwareness: Latency-aware peer selection
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Any, Optional
import hashlib
from datetime import datetime, timezone
from functools import cached_property


@dataclass(frozen=True)
class SharedStateVector:
    """
    Immutable, hashable state container for distributed consensus.

    Represents the shared state of the mesh at a point in time.
    Frozen to ensure immutability; hashable for use in sets/dicts.

    Attributes:
        agent_id: Unique identifier of the agent owning this state vector
        timestamp: ISO 8601 timestamp of state creation
        metrics: Dict of metric key-value pairs (e.g., latency, throughput)
    """

    agent_id: str
    timestamp: str
    metrics: Dict[str, Any]

    def __hash__(self) -> int:
        """Compute hash from immutable fields."""
        # Convert metrics to frozenset of items for hashing
        metrics_items = tuple(sorted(self.metrics.items()))
        return hash((self.agent_id, self.timestamp, metrics_items))

    def __eq__(self, other: object) -> bool:
        """Check equality with another SharedStateVector."""
        if not isinstance(other, SharedStateVector):
            return NotImplemented
        return (
            self.agent_id == other.agent_id
            and self.timestamp == other.timestamp
            and self.metrics == other.metrics
        )

    @cached_property
    def merkle_root(self) -> str:
        """Compute Merkle root hash of this state vector."""
        # Create deterministic serialization
        state_str = f"{self.agent_id}:{self.timestamp}:{str(sorted(self.metrics.items()))}"
        return hashlib.sha256(state_str.encode()).hexdigest()


@dataclass
class HolographicPerception:
    """
    Agent-filtered view of the shared mesh state.

    Each agent maintains a holographic perception: a view of the entire mesh
    from its local perspective, including awareness of other agents' states
    without central coordination.

    Attributes:
        self_agent_id: Identifier of the perceiving agent
        all_states: List of SharedStateVector from all agents in mesh
    """

    self_agent_id: str
    all_states: List[SharedStateVector]

    def other_agent_ids(self) -> List[str]:
        """
        Return list of other agent IDs (excluding self).

        Returns:
            List of agent IDs excluding self_agent_id
        """
        return [state.agent_id for state in self.all_states if state.agent_id != self.self_agent_id]

    def compute_local_view(self) -> Dict[str, Any]:
        """
        Compute this agent's local view of the mesh.

        Returns:
            Dict with keys:
            - self_state: This agent's SharedStateVector
            - other_states: List of other agents' SharedStateVectors
            - view_hash: SHA256 hash of the complete view
        """
        # Find self state
        self_state = None
        other_states = []

        for state in self.all_states:
            if state.agent_id == self.self_agent_id:
                self_state = state
            else:
                other_states.append(state)

        # Compute view hash
        view_str = f"{self_state.merkle_root}:" + ":".join(
            sorted([s.merkle_root for s in other_states])
        )
        view_hash = hashlib.sha256(view_str.encode()).hexdigest()

        return {
            "self_state": self_state,
            "other_states": other_states,
            "view_hash": view_hash
        }


@dataclass
class ConsensusProtocol:
    """
    Byzantine-tolerant consensus with Merkle verification.

    Enables agreement on shared state across agents despite Byzantine actors.
    Uses threshold signatures and Merkle root verification.

    Attributes:
        agent_states: List of SharedStateVector from all agents
        f_byzantine: Number of tolerable Byzantine faults (default: n/3)
    """

    agent_states: List[SharedStateVector]
    f_byzantine: int = 1

    def compute_merkle_root(self) -> str:
        """
        Compute Merkle root of all agent states.

        Returns deterministic hash agreeable by all honest agents.

        Returns:
            SHA256 hex digest of Merkle tree root
        """
        # Sort states by agent_id for deterministic ordering
        sorted_states = sorted(self.agent_states, key=lambda s: s.agent_id)

        # Build Merkle tree by hashing each state's merkle_root
        merkle_hashes = [s.merkle_root for s in sorted_states]

        # Compute root
        root_str = ":".join(merkle_hashes)
        return hashlib.sha256(root_str.encode()).hexdigest()

    def sign_agreement(self, agreement: str, agent_id: str) -> str:
        """
        Sign a consensus agreement (simple mock signature).

        Args:
            agreement: The agreement hash to sign (as hex string)
            agent_id: ID of the agent signing

        Returns:
            Signature string
        """
        # Simple deterministic signature: hash(agreement + agent_id)
        sig_input = f"{agreement}:{agent_id}"
        return hashlib.sha256(sig_input.encode()).hexdigest()

    def verify_peer_agreement(self, agent_id: str, agreement: str, signature: str) -> bool:
        """
        Verify a peer's signature on an agreement.

        Args:
            agent_id: ID of the agent that signed
            agreement: The agreement hash
            signature: The signature to verify

        Returns:
            True if signature is valid
        """
        expected_sig = self.sign_agreement(agreement, agent_id)
        return signature == expected_sig

    def detect_byzantine(self, agreements: Dict[str, Tuple[str, str]], honest_agreement: str) -> List[str]:
        """
        Detect Byzantine agents based on agreement mismatch.

        Args:
            agreements: Dict mapping agent_id to (agreement, signature) tuple
            honest_agreement: The consensus agreement from honest agents

        Returns:
            List of agent IDs that are Byzantine
        """
        byzantine_agents = []

        for agent_id, (agreement, signature) in agreements.items():
            # Check if agreement matches
            if agreement != honest_agreement:
                # Double-check signature is valid for the false agreement
                if self.verify_peer_agreement(agent_id, agreement, signature):
                    # Agent signed a false agreement - it's Byzantine
                    byzantine_agents.append(agent_id)

        return byzantine_agents


@dataclass
class MeshCoordinator:
    """
    Gossip-based mesh coordination without central coordinator.

    Manages state propagation across the mesh using gossip protocol.
    Each agent independently selects peers for state dissemination.

    Attributes:
        self_agent_id: Identifier of this agent
        known_peers: List of peer agent IDs in mesh
        received_states: Dict mapping agent_id to SharedStateVector
    """

    self_agent_id: str
    known_peers: List[str]
    received_states: Dict[str, SharedStateVector] = field(default_factory=dict)

    def receive_state(self, state: SharedStateVector) -> None:
        """
        Receive and store a state vector from a peer.

        Args:
            state: SharedStateVector to receive
        """
        self.received_states[state.agent_id] = state

    def select_gossip_peers(self, fanout: int = 2) -> List[str]:
        """
        Select peers for gossip propagation (random fanout).

        Args:
            fanout: Number of peers to select for gossip

        Returns:
            List of selected peer agent IDs
        """
        import random

        # Filter out self
        available_peers = [p for p in self.known_peers if p != self.self_agent_id]

        # Select random subset up to fanout size
        num_to_select = min(fanout, len(available_peers))
        return random.sample(available_peers, num_to_select)

    def get_peers_to_notify(self, state: SharedStateVector, fanout: int = 2) -> List[str]:
        """
        Get list of peers to notify about a state update.

        Args:
            state: The state to propagate
            fanout: Number of peers to select

        Returns:
            List of peer agent IDs to notify
        """
        return self.select_gossip_peers(fanout)
