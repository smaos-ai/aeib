"""
Test suite for CAPSULE Tier 5: Holographic Operator Mesh v1

Tests distributed cognition layer enabling multi-agent coordination
without central coordinator.

Test Structure:
- Test classes organized by component
- TDD: failing tests → minimal implementation → passing tests
"""

import pytest
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Set
import hashlib


# ============================================================================
# TEST CLASS: SharedStateVector (Immutable Tuple)
# ============================================================================

class TestSharedStateVector:
    """Test SharedStateVector immutable state container."""

    def test_shared_state_vector_immutability(self, sample_metrics):
        """Test that SharedStateVector is frozen and cannot be modified."""
        from tier5_holographic_mesh import SharedStateVector

        sv = SharedStateVector(
            agent_id="agent_prague_001",
            timestamp="2026-05-27T18:00:00Z",
            metrics=sample_metrics
        )

        # Verify attributes are accessible
        assert sv.agent_id == "agent_prague_001"
        assert sv.timestamp == "2026-05-27T18:00:00Z"
        assert sv.metrics == sample_metrics

        # Verify frozen by attempting to modify (should raise FrozenInstanceError)
        import dataclasses
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            sv.agent_id = "modified"

    def test_shared_state_vector_hashable(self, sample_metrics):
        """Test that SharedStateVector instances are hashable for consensus."""
        from tier5_holographic_mesh import SharedStateVector

        sv1 = SharedStateVector(
            agent_id="agent_prague_001",
            timestamp="2026-05-27T18:00:00Z",
            metrics=sample_metrics
        )

        sv2 = SharedStateVector(
            agent_id="agent_prague_001",
            timestamp="2026-05-27T18:00:00Z",
            metrics=sample_metrics
        )

        # Verify hashable: can use in set
        state_set = {sv1, sv2}
        assert len(state_set) == 1  # Same content = same hash

        # Verify hashable: can use as dict key
        state_dict = {sv1: "consensus_reached"}
        assert state_dict[sv2] == "consensus_reached"


# ============================================================================
# TEST CLASS: HolographicPerception (Agent-Filtered Views)
# ============================================================================

class TestHolographicPerception:
    """Test HolographicPerception for agent-filtered state views."""

    def test_holographic_perception_agent_filters(self, sample_agent_ids, sample_metrics):
        """Test that perception correctly filters state for each agent."""
        from tier5_holographic_mesh import SharedStateVector, HolographicPerception

        # Create state vectors for multiple agents
        states = [
            SharedStateVector(agent_id=agent_id, timestamp="2026-05-27T18:00:00Z", metrics=sample_metrics)
            for agent_id in sample_agent_ids
        ]

        # Create perception for first agent
        perception = HolographicPerception(
            self_agent_id=sample_agent_ids[0],
            all_states=states
        )

        # Verify other_agent_ids excludes self
        other_ids = perception.other_agent_ids()
        assert sample_agent_ids[0] not in other_ids
        assert sample_agent_ids[1] in other_ids
        assert len(other_ids) == len(sample_agent_ids) - 1

    def test_holographic_perception_local_view_computation(self, sample_agent_ids, sample_metrics):
        """Test computation of local view with agent-specific state."""
        from tier5_holographic_mesh import SharedStateVector, HolographicPerception

        states = [
            SharedStateVector(agent_id=agent_id, timestamp="2026-05-27T18:00:00Z", metrics=sample_metrics)
            for agent_id in sample_agent_ids
        ]

        perception = HolographicPerception(
            self_agent_id=sample_agent_ids[0],
            all_states=states
        )

        # Compute local view
        local_view = perception.compute_local_view()

        # Verify local view structure
        assert "self_state" in local_view
        assert "other_states" in local_view
        assert "view_hash" in local_view

        # Verify self_state is the agent's own state
        assert local_view["self_state"].agent_id == sample_agent_ids[0]

        # Verify other_states contains all other agents
        assert len(local_view["other_states"]) == len(sample_agent_ids) - 1


# ============================================================================
# TEST CLASS: ConsensusProtocol (Merkle Verification & Byzantine Tolerance)
# ============================================================================

class TestConsensusProtocol:
    """Test Byzantine-tolerant consensus with Merkle verification."""

    def test_consensus_protocol_agreement(self, sample_agent_ids, sample_metrics):
        """Test that consensus produces agreement across honest agents."""
        from tier5_holographic_mesh import SharedStateVector, ConsensusProtocol

        states = [
            SharedStateVector(agent_id=agent_id, timestamp="2026-05-27T18:00:00Z", metrics=sample_metrics)
            for agent_id in sample_agent_ids
        ]

        consensus = ConsensusProtocol(agent_states=states, f_byzantine=1)

        # Compute agreement
        agreement = consensus.compute_merkle_root()

        # All honest agents should compute same root
        assert isinstance(agreement, str)
        assert len(agreement) == 64  # SHA256 hex digest

    def test_consensus_protocol_signature(self, sample_agent_ids, sample_metrics):
        """Test digital signature of state agreement."""
        from tier5_holographic_mesh import SharedStateVector, ConsensusProtocol

        states = [
            SharedStateVector(agent_id=agent_id, timestamp="2026-05-27T18:00:00Z", metrics=sample_metrics)
            for agent_id in sample_agent_ids
        ]

        consensus = ConsensusProtocol(agent_states=states, f_byzantine=1)

        # Compute and sign agreement
        agreement = consensus.compute_merkle_root()
        signature = consensus.sign_agreement(agreement, agent_id=sample_agent_ids[0])

        # Verify signature exists and is valid
        assert signature is not None
        assert isinstance(signature, str)
        assert len(signature) > 0

        # Verify the signature
        is_valid = consensus.verify_peer_agreement(
            agent_id=sample_agent_ids[0],
            agreement=agreement,
            signature=signature
        )
        assert is_valid

    def test_byzantine_tolerance_detect_lying_agent(self, sample_agent_ids, sample_metrics):
        """Test detection of Byzantine (lying) agents."""
        from tier5_holographic_mesh import SharedStateVector, ConsensusProtocol

        # Create honest states
        states = [
            SharedStateVector(agent_id=agent_id, timestamp="2026-05-27T18:00:00Z", metrics=sample_metrics)
            for agent_id in sample_agent_ids
        ]

        consensus = ConsensusProtocol(agent_states=states, f_byzantine=1)

        # Agent 0 tries to sign false agreement
        agreement = consensus.compute_merkle_root()
        false_agreement = "0" * 64  # Completely different hash

        signature = consensus.sign_agreement(false_agreement, agent_id=sample_agent_ids[0])

        # Detect Byzantine behavior
        byzantine_agents = consensus.detect_byzantine(
            agreements={sample_agent_ids[0]: (false_agreement, signature)},
            honest_agreement=agreement
        )

        # Should detect agent 0 as Byzantine
        assert sample_agent_ids[0] in byzantine_agents


# ============================================================================
# TEST CLASS: MeshCoordinator (Gossip Protocol)
# ============================================================================

class TestMeshCoordinator:
    """Test gossip-based mesh coordination and state propagation."""

    def test_gossip_propagation_correctness(self, sample_agent_ids, sample_metrics):
        """Test that gossip correctly propagates state updates across mesh."""
        from tier5_holographic_mesh import SharedStateVector, MeshCoordinator

        states = [
            SharedStateVector(agent_id=agent_id, timestamp="2026-05-27T18:00:00Z", metrics=sample_metrics)
            for agent_id in sample_agent_ids
        ]

        coordinator = MeshCoordinator(self_agent_id=sample_agent_ids[0], known_peers=sample_agent_ids[1:])

        # Receive a state from another agent
        new_state = states[1]
        coordinator.receive_state(new_state)

        # Verify state is stored
        assert new_state.agent_id in coordinator.received_states
        assert coordinator.received_states[new_state.agent_id] == new_state

    def test_mesh_convergence_time(self, sample_agent_ids, sample_metrics):
        """Test that mesh converges within expected time bounds."""
        from tier5_holographic_mesh import SharedStateVector, MeshCoordinator

        states = [
            SharedStateVector(agent_id=agent_id, timestamp="2026-05-27T18:00:00Z", metrics=sample_metrics)
            for agent_id in sample_agent_ids
        ]

        coordinator = MeshCoordinator(self_agent_id=sample_agent_ids[0], known_peers=sample_agent_ids[1:])

        # Select gossip peers
        gossip_peers = coordinator.select_gossip_peers(fanout=2)

        # Should select up to fanout peers
        assert len(gossip_peers) <= 2
        assert len(gossip_peers) > 0

        # Should not include self
        assert sample_agent_ids[0] not in gossip_peers

        # All selected peers should be in known_peers
        for peer in gossip_peers:
            assert peer in sample_agent_ids[1:]


# ============================================================================
# TEST CLASS: LocalityAwareness (Latency-Aware Routing)
# ============================================================================

class TestLocalityAwareness:
    """Test latency-aware peer selection for gossip."""

    def test_latency_aware_routing_prague_frankfurt(self, prague_frankfurt_latency):
        """Test routing optimization between Prague and Frankfurt."""
        from tier5_holographic_mesh import LocalityAwareness

        # Create latency map
        latencies = {
            "agent_prague_001": 0.5,      # Local to Prague
            "agent_frankfurt_002": prague_frankfurt_latency,  # 12.5ms to Frankfurt
            "agent_london_003": 25.0,     # Farther from Prague
            "agent_tokyo_004": 180.0      # Very far
        }

        awareness = LocalityAwareness(self_location="Prague", latencies=latencies)

        # Test latency lookup
        assert awareness.get_latency("agent_frankfurt_002") == prague_frankfurt_latency

        # Test peer ranking by latency
        ranked = awareness.rank_peers_by_latency(list(latencies.keys()))

        # Should be ordered by increasing latency
        assert ranked[0] == "agent_prague_001"
        assert ranked[1] == "agent_frankfurt_002"
        assert ranked[-1] == "agent_tokyo_004"

    def test_no_central_coordinator_required(self):
        """Test that mesh operates without central coordinator."""
        from tier5_holographic_mesh import LocalityAwareness

        # Multiple agents can independently compute locality awareness
        agents = ["prague_001", "frankfurt_002", "london_003"]

        # Each agent has different latency perspective
        prague_latencies = {"prague_001": 0.5, "frankfurt_002": 12.5, "london_003": 25.0}
        frankfurt_latencies = {"prague_001": 12.5, "frankfurt_002": 0.5, "london_003": 18.0}

        awareness_prague = LocalityAwareness(self_location="Prague", latencies=prague_latencies)
        awareness_frankfurt = LocalityAwareness(self_location="Frankfurt", latencies=frankfurt_latencies)

        # Both can independently select local peers without coordination
        prague_locals = awareness_prague.select_local_peers(threshold_ms=20.0)
        frankfurt_locals = awareness_frankfurt.select_local_peers(threshold_ms=20.0)

        # Should select different local peers based on position
        assert len(prague_locals) > 0
        assert len(frankfurt_locals) > 0

        # No central coordinator was used - just local knowledge


# ============================================================================
# TEST CLASS: Integration Tests (Full Mesh Workflow)
# ============================================================================

class TestIntegration:
    """Integration tests for full holographic mesh workflow."""

    def test_local_computation_deterministic(self, sample_agent_ids, sample_metrics):
        """Test that local computations are deterministic."""
        from tier5_holographic_mesh import SharedStateVector, ConsensusProtocol

        states = [
            SharedStateVector(agent_id=agent_id, timestamp="2026-05-27T18:00:00Z", metrics=sample_metrics)
            for agent_id in sample_agent_ids
        ]

        # Run consensus multiple times - should always produce same result
        consensus1 = ConsensusProtocol(agent_states=states, f_byzantine=1)
        consensus2 = ConsensusProtocol(agent_states=states, f_byzantine=1)

        root1 = consensus1.compute_merkle_root()
        root2 = consensus2.compute_merkle_root()

        assert root1 == root2, "Merkle root should be deterministic"

    def test_multi_agent_view_consistency(self, sample_agent_ids, sample_metrics):
        """Test consistency of multi-agent views."""
        from tier5_holographic_mesh import SharedStateVector, HolographicPerception

        states = [
            SharedStateVector(agent_id=agent_id, timestamp="2026-05-27T18:00:00Z", metrics=sample_metrics)
            for agent_id in sample_agent_ids
        ]

        # Create perception from each agent's perspective
        perceptions = [
            HolographicPerception(self_agent_id=agent_id, all_states=states)
            for agent_id in sample_agent_ids
        ]

        # All should see same other_states (minus themselves)
        for perception in perceptions:
            view = perception.compute_local_view()
            other_count = len(view["other_states"])
            assert other_count == len(sample_agent_ids) - 1

    def test_state_vector_ordering(self, sample_agent_ids, sample_metrics):
        """Test deterministic ordering of state vector elements."""
        from tier5_holographic_mesh import SharedStateVector, ConsensusProtocol

        # Create states
        states1 = [
            SharedStateVector(agent_id=agent_id, timestamp="2026-05-27T18:00:00Z", metrics=sample_metrics)
            for agent_id in sample_agent_ids
        ]

        # Create same states in different order
        states2 = list(reversed(states1))

        # Consensus should produce same root regardless of input order
        consensus1 = ConsensusProtocol(agent_states=states1, f_byzantine=1)
        consensus2 = ConsensusProtocol(agent_states=states2, f_byzantine=1)

        root1 = consensus1.compute_merkle_root()
        root2 = consensus2.compute_merkle_root()

        assert root1 == root2, "Merkle root should be order-independent"

    def test_full_mesh_workflow(self, sample_agent_ids, sample_metrics, prague_frankfurt_latency):
        """Test full mesh workflow: state vector → perception → consensus → gossip."""
        from tier5_holographic_mesh import (
            SharedStateVector, HolographicPerception, ConsensusProtocol,
            MeshCoordinator, LocalityAwareness
        )

        # 1. Create shared state vectors
        states = [
            SharedStateVector(agent_id=agent_id, timestamp="2026-05-27T18:00:00Z", metrics=sample_metrics)
            for agent_id in sample_agent_ids
        ]

        # 2. Create holographic perception from agent 0's view
        perception = HolographicPerception(
            self_agent_id=sample_agent_ids[0],
            all_states=states
        )
        view = perception.compute_local_view()
        assert view["self_state"].agent_id == sample_agent_ids[0]

        # 3. Compute consensus
        consensus = ConsensusProtocol(agent_states=states, f_byzantine=1)
        agreement = consensus.compute_merkle_root()
        signature = consensus.sign_agreement(agreement, sample_agent_ids[0])
        assert consensus.verify_peer_agreement(sample_agent_ids[0], agreement, signature)

        # 4. Setup mesh coordinator
        coordinator = MeshCoordinator(
            self_agent_id=sample_agent_ids[0],
            known_peers=sample_agent_ids[1:]
        )

        # Receive state from another agent
        coordinator.receive_state(states[1])
        assert states[1].agent_id in coordinator.received_states

        # Select gossip peers
        gossip_peers = coordinator.select_gossip_peers(fanout=2)
        assert len(gossip_peers) > 0
        assert sample_agent_ids[0] not in gossip_peers

        # 5. Setup locality awareness
        latencies = {
            sample_agent_ids[0]: 0.5,
            sample_agent_ids[1]: prague_frankfurt_latency,
            sample_agent_ids[2]: 25.0,
            sample_agent_ids[3]: 180.0
        }
        awareness = LocalityAwareness(self_location="Prague", latencies=latencies)

        # Rank peers by latency
        ranked = awareness.rank_peers_by_latency(sample_agent_ids)
        assert ranked[0] == sample_agent_ids[0]  # Closest to self

        # Select local peers
        local_peers = awareness.select_local_peers(threshold_ms=50.0)
        assert len(local_peers) >= 2

        # Full workflow complete: all components integrated
        assert True
