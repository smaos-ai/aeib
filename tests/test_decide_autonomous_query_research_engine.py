#!/usr/bin/env python3
# File: tests/test_decide_autonomous_query_research_engine.py
"""
Test suite for Decide-v4 Autonomous Query Research & Multi-Hop Epistemic Action Engine.
Evaluates:
1. 8-Axis orthogonal query expansion.
2. Multi-hop tree search traversal and action logging.
3. Automated adversarial falsification probes.
4. Asymmetric Evidence Dominance (defeating the 32.3% Oracle Gap).
5. Ed25519 signature verification over canonical JCS payload.
6. Epistemic boundary compliance (zero banned promotional words).
"""

import base64
import json
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.decide_autonomous_query_research_engine import (
    AutonomousQueryResearchDispatcher,
    ResearchActionType,
    canonical_jcs,
    sha256_hex,
)


def test_8axis_orthogonal_query_expansion():
    """Evaluates that root query is expanded across all 8 declared orthogonal axes."""
    dispatcher = AutonomousQueryResearchDispatcher()
    root_q = "Architectural boundary for cross-organization autonomous agent transactions"
    nodes = dispatcher.expand_query_8axis(root_q)

    assert len(nodes) == 8
    axes = {n.axis for n in nodes}
    expected_axes = {
        "FOUNDATIONAL_ARCHITECTURE",
        "ADVERSARIAL_REDTEAM",
        "EMPIRICAL_BENCHMARK",
        "REGULATORY_COMPLIANCE",
        "LATENCY_PERFORMANCE",
        "CROSS_HEMISPHERE_DIVERGENCE",
        "SUPPLY_CHAIN_DEPENDENCY",
        "FORMAL_INVARIANTS",
    }
    assert axes == expected_axes
    for n in nodes:
        assert n.hop_depth == 0
        assert n.parent_id is None
        assert root_q in n.query_string


def test_multi_hop_tree_search_and_action_logging():
    """Evaluates multi-hop recursive expansion and execution audit records."""
    dispatcher = AutonomousQueryResearchDispatcher()
    root_q = "Evaluate oracle gap and cost of consensus in multi-agent debate"
    nodes, actions = dispatcher.execute_multi_hop_research(root_q, max_depth=1)

    # Initial 8 nodes + child nodes for adversarial and formal branches
    assert len(nodes) >= 10
    assert len(actions) >= 8

    # Verify action records are structured and completed
    for act in actions:
        assert act.status == "COMPLETED"
        assert act.action_type == ResearchActionType.DISPATCH_LITERATURE_PROBE
        assert act.duration_ms >= 0
        assert len(act.output_digest) == 64

    # Verify deeper hop nodes exist
    depth1_nodes = [n for n in nodes if n.hop_depth == 1]
    assert len(depth1_nodes) >= 2
    for d1 in depth1_nodes:
        assert d1.parent_id is not None
        assert d1.parent_id.startswith("node_hop0_")


def test_adversarial_falsification_probe_and_evidence_dominance():
    """Evaluates that verified counterexamples override plurality voting and eliminate Oracle Gap."""
    dispatcher = AutonomousQueryResearchDispatcher()
    root_q = "How does multi-agent consensus behave under unguided homogeneous debate?"
    receipt = dispatcher.execute_complete_research_and_brainstorm_cycle(root_q)

    assert receipt.oracle_gap_eliminated is True
    assert receipt.counterexamples_identified >= 1
    assert receipt.total_actions_dispatched > 0

    # Verify dominant hypothesis is flagged
    dominant_hypos = [
        h for h in receipt.synthesized_hypotheses if h["evidence_dominant"] is True
    ]
    assert len(dominant_hypos) >= 1
    for dom in dominant_hypos:
        assert dom["confidence_bps"] >= 9500
        assert len(dom["witness"]) > 0
        assert len(dom["citations"]) > 0


def test_ed25519_canonical_receipt_verification():
    """Evaluates Ed25519 cryptographic receipt signature over RFC 8785 canonical bytes."""
    dispatcher = AutonomousQueryResearchDispatcher()
    root_q = "Verify cryptographic receipt for autonomous deep research dispatch"
    receipt = dispatcher.execute_complete_research_and_brainstorm_cycle(root_q)

    pub_bytes = base64.b64decode(receipt.author_public_key_b64)
    sig_bytes = base64.b64decode(receipt.signature_b64)

    pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)

    # Reconstruct the exact signed canonical payload
    payload_obj = {
        "receipt_id": receipt.receipt_id,
        "root_query": receipt.root_query,
        "actions_dispatched": receipt.total_actions_dispatched,
        "query_nodes_explored": receipt.total_query_nodes_explored,
        "max_depth": receipt.max_hop_depth,
        "evidence_harvested": receipt.evidence_items_harvested,
        "counterexamples": receipt.counterexamples_identified,
        "oracle_gap_eliminated": receipt.oracle_gap_eliminated,
        "hypotheses": receipt.synthesized_hypotheses,
    }
    canonical_bytes = canonical_jcs(payload_obj)

    # Verify signature passes
    pub_key.verify(sig_bytes, canonical_bytes)

    # Verify payload hash matches
    assert sha256_hex(canonical_bytes) == receipt.payload_hash

    # Falsification: tampered payload must fail verification
    tampered_bytes = canonical_bytes + b"!"
    with pytest.raises(Exception):
        pub_key.verify(sig_bytes, tampered_bytes)


def test_banned_words_absence():
    """Enforces AGENTS.md epistemic boundary on source and test files."""
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "unhack" + "able",
    ]

    files_to_check = [
        "src/decide_autonomous_query_research_engine.py",
        "tests/test_decide_autonomous_query_research_engine.py",
    ]

    for fpath in files_to_check:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read().lower()
            for b in banned:
                assert b not in content, f"Banned word '{b}' found in {fpath}"
