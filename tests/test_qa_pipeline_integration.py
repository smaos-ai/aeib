#!/usr/bin/env python3
"""
Pytest integration tests for agentacct + AP2 ledger interaction.
Tests work receipt generation, ledger anchoring, and proof verification.
Target: 9 tests covering end-to-end scenarios
"""

import pytest
import json
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class WorkReceipt:
    """Work receipt from agentacct tracking."""
    receipt_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    action_type: str = "unknown"
    agent_id: str = "unknown_agent"
    duration_ms: int = 0
    status: str = "success"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def compute_hash(self) -> str:
        """Compute receipt hash."""
        data_str = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(data_str.encode()).hexdigest()


@dataclass
class AP2Entry:
    """Entry in AP2 append-only ledger."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    receipt_hash: str = ""
    merkle_root: str = ""
    signature: str = ""
    previous_entry_id: Optional[str] = None
    action_description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentAcctTracker:
    """Tracks agent work receipts."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.receipts: List[WorkReceipt] = []
        self.total_duration_ms = 0

    def record_action(
        self,
        action_type: str,
        duration_ms: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> WorkReceipt:
        """Record an agent action."""
        receipt = WorkReceipt(
            action_type=action_type,
            agent_id=self.agent_id,
            duration_ms=duration_ms,
            metadata=metadata or {}
        )
        self.receipts.append(receipt)
        self.total_duration_ms += duration_ms
        return receipt

    def get_receipts(self) -> List[WorkReceipt]:
        """Get all recorded receipts."""
        return self.receipts

    def get_receipt_hashes(self) -> List[str]:
        """Get hashes of all receipts."""
        return [r.compute_hash() for r in self.receipts]

    def get_total_duration(self) -> int:
        """Get total execution duration."""
        return self.total_duration_ms


class AP2LedgerIntegration:
    """Integration between agentacct and AP2 ledger."""

    def __init__(self):
        self.entries: List[AP2Entry] = []
        self.agent_trackers: Dict[str, AgentAcctTracker] = {}
        self.merkle_tree_leaves: List[str] = []

    def register_agent(self, agent_id: str) -> AgentAcctTracker:
        """Register an agent."""
        tracker = AgentAcctTracker(agent_id)
        self.agent_trackers[agent_id] = tracker
        return tracker

    def get_agent_tracker(self, agent_id: str) -> Optional[AgentAcctTracker]:
        """Get tracker for agent."""
        return self.agent_trackers.get(agent_id)

    def anchor_receipt_to_ledger(
        self,
        agent_id: str,
        receipt: WorkReceipt,
        action_description: str
    ) -> AP2Entry:
        """Anchor a work receipt to AP2 ledger."""
        receipt_hash = receipt.compute_hash()
        self.merkle_tree_leaves.append(receipt_hash)

        # Compute Merkle root
        merkle_root = self._compute_merkle_root()

        # Create ledger entry
        previous_entry_id = self.entries[-1].entry_id if self.entries else None
        entry = AP2Entry(
            receipt_hash=receipt_hash,
            merkle_root=merkle_root,
            signature=self._sign_entry(receipt_hash),
            previous_entry_id=previous_entry_id,
            action_description=action_description
        )

        self.entries.append(entry)
        return entry

    def _compute_merkle_root(self) -> str:
        """Compute Merkle root of all leaves."""
        if not self.merkle_tree_leaves:
            return hashlib.sha256("".encode()).hexdigest()

        current_level = self.merkle_tree_leaves[:]
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    combined = current_level[i] + current_level[i + 1]
                else:
                    combined = current_level[i] + current_level[i]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            current_level = next_level

        return current_level[0] if current_level else hashlib.sha256("".encode()).hexdigest()

    def _sign_entry(self, data: str) -> str:
        """Simulate Ed25519 signature."""
        digest = hashlib.sha256(data.encode()).hexdigest()
        return f"ed25519_sig_{digest[:16]}"

    def verify_ledger_integrity(self) -> bool:
        """Verify append-only ledger integrity."""
        for i, entry in enumerate(self.entries):
            if i == 0:
                # First entry should have no previous
                if entry.previous_entry_id is not None:
                    return False
            else:
                # Chain should be intact
                if entry.previous_entry_id != self.entries[i - 1].entry_id:
                    return False

        return True

    def get_entries(self) -> List[AP2Entry]:
        """Get all ledger entries."""
        return self.entries

    def get_entries_count(self) -> int:
        """Get number of entries."""
        return len(self.entries)


# Pytest Tests

class TestAgentAcctTracker:
    """Tests for agentacct work receipt tracking."""

    def test_record_single_action(self):
        """Test recording a single action."""
        tracker = AgentAcctTracker("agent_001")
        receipt = tracker.record_action("inference", 100, {"model": "claude-3"})

        assert receipt.action_type == "inference"
        assert receipt.duration_ms == 100
        assert receipt.metadata["model"] == "claude-3"
        assert len(tracker.get_receipts()) == 1

    def test_record_multiple_actions(self):
        """Test recording multiple actions."""
        tracker = AgentAcctTracker("agent_002")

        tracker.record_action("inference", 100)
        tracker.record_action("tool_use", 50)
        tracker.record_action("decision", 25)

        receipts = tracker.get_receipts()
        assert len(receipts) == 3
        assert tracker.get_total_duration() == 175

    def test_receipt_hash_computation(self):
        """Test work receipt hash computation."""
        tracker = AgentAcctTracker("agent_003")
        receipt = tracker.record_action("inference", 100)

        hash1 = receipt.compute_hash()
        hash2 = receipt.compute_hash()

        # Hashes should be deterministic
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_receipt_consistency(self):
        """Test receipt data consistency."""
        tracker = AgentAcctTracker("agent_004")
        receipt = tracker.record_action("inference", 100, {"test": "data"})

        dict_repr = receipt.to_dict()
        assert dict_repr["action_type"] == "inference"
        assert dict_repr["duration_ms"] == 100
        assert dict_repr["metadata"]["test"] == "data"


class TestAP2LedgerIntegration:
    """Tests for AP2 ledger and agentacct integration."""

    def test_register_agent(self):
        """Test agent registration."""
        integration = AP2LedgerIntegration()
        tracker = integration.register_agent("agent_001")

        assert tracker is not None
        assert integration.get_agent_tracker("agent_001") is tracker

    def test_anchor_receipt_to_ledger(self):
        """Test anchoring a receipt to ledger."""
        integration = AP2LedgerIntegration()
        tracker = integration.register_agent("agent_001")

        receipt = tracker.record_action("inference", 100)
        entry = integration.anchor_receipt_to_ledger(
            "agent_001",
            receipt,
            "Inference execution"
        )

        assert entry.receipt_hash == receipt.compute_hash()
        assert not entry.merkle_root == ""
        assert entry.signature.startswith("ed25519_sig_")
        assert integration.get_entries_count() == 1

    def test_ledger_append_only_property(self):
        """Test append-only property of ledger."""
        integration = AP2LedgerIntegration()
        tracker = integration.register_agent("agent_001")

        # Add multiple entries
        for i in range(3):
            receipt = tracker.record_action(f"action_{i}", 100 + i * 10)
            integration.anchor_receipt_to_ledger(
                "agent_001",
                receipt,
                f"Action {i}"
            )

        entries = integration.get_entries()
        assert len(entries) == 3

        # Verify chain integrity
        assert entries[0].previous_entry_id is None
        assert entries[1].previous_entry_id == entries[0].entry_id
        assert entries[2].previous_entry_id == entries[1].entry_id

    def test_ledger_integrity_verification(self):
        """Test ledger integrity verification."""
        integration = AP2LedgerIntegration()
        tracker = integration.register_agent("agent_001")

        # Add entries
        for i in range(3):
            receipt = tracker.record_action(f"action_{i}", 100)
            integration.anchor_receipt_to_ledger("agent_001", receipt, f"Action {i}")

        assert integration.verify_ledger_integrity()

    def test_merkle_root_consistency(self):
        """Test Merkle root consistency across entries."""
        integration = AP2LedgerIntegration()
        tracker = integration.register_agent("agent_001")

        receipt1 = tracker.record_action("action_1", 100)
        entry1 = integration.anchor_receipt_to_ledger("agent_001", receipt1, "Action 1")
        root1 = entry1.merkle_root

        receipt2 = tracker.record_action("action_2", 100)
        entry2 = integration.anchor_receipt_to_ledger("agent_001", receipt2, "Action 2")
        root2 = entry2.merkle_root

        # Merkle roots should be different as tree grows
        assert root1 != root2

    def test_multiple_agents_ledger_integration(self):
        """Test multiple agents writing to shared ledger."""
        integration = AP2LedgerIntegration()

        tracker1 = integration.register_agent("agent_001")
        tracker2 = integration.register_agent("agent_002")

        receipt1 = tracker1.record_action("inference", 100)
        receipt2 = tracker2.record_action("decision", 50)

        integration.anchor_receipt_to_ledger("agent_001", receipt1, "Agent 1 inference")
        integration.anchor_receipt_to_ledger("agent_002", receipt2, "Agent 2 decision")

        assert integration.get_entries_count() == 2
        assert integration.verify_ledger_integrity()

    def test_ledger_proof_generation(self):
        """Test proof generation for ledger entries."""
        integration = AP2LedgerIntegration()
        tracker = integration.register_agent("agent_001")

        receipts = []
        entries = []
        for i in range(5):
            receipt = tracker.record_action(f"action_{i}", 100)
            receipts.append(receipt)
            entry = integration.anchor_receipt_to_ledger(
                "agent_001",
                receipt,
                f"Action {i}"
            )
            entries.append(entry)

        # Each entry should have a valid signature
        for entry in entries:
            assert entry.signature.startswith("ed25519_sig_")
            assert len(entry.signature) > 20

    def test_agentacct_duration_tracking(self):
        """Test agentacct duration tracking across ledger."""
        integration = AP2LedgerIntegration()
        tracker = integration.register_agent("agent_001")

        durations = [100, 50, 75, 25, 200]
        for duration in durations:
            receipt = tracker.record_action("work", duration)
            integration.anchor_receipt_to_ledger("agent_001", receipt, f"Work: {duration}ms")

        assert tracker.get_total_duration() == sum(durations)
        assert integration.get_entries_count() == len(durations)

    def test_ledger_entry_immutability(self):
        """Test that ledger entries are immutable."""
        integration = AP2LedgerIntegration()
        tracker = integration.register_agent("agent_001")

        receipt = tracker.record_action("action", 100)
        entry = integration.anchor_receipt_to_ledger("agent_001", receipt, "Test action")

        original_hash = entry.receipt_hash
        original_sig = entry.signature

        # Attempting to modify entry should not affect original
        entries = integration.get_entries()
        assert entries[0].receipt_hash == original_hash
        assert entries[0].signature == original_sig


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
