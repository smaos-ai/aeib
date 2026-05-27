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
