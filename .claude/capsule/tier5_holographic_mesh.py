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
