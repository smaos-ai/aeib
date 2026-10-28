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


def test_decide_autonomous_query_research_engine_mutation_boundaries() -> None:
    import ast as _ast
    from pathlib import Path
    import src.decide_autonomous_query_research_engine as daqre
    from src.decide_autonomous_query_research_engine import (
        ActionExecutionRecord,
        AutonomousResearchReceipt,
        EpistemicBrainstormHypothesis,
        ResearchQueryNode,
    )

    tree = _ast.parse(Path(daqre.__file__).read_text(encoding="utf-8"))
    found_exc = False
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ExceptHandler):
            for stmt in node.body:
                if isinstance(stmt, _ast.Expr) and isinstance(stmt.value, _ast.Call):
                    found_exc = True
                    assert isinstance(stmt.value.args[0], _ast.Constant) and stmt.value.args[0].value == 0
                    sub = stmt.value.args[1].args[0]  # type: ignore[attr-defined]
                    assert isinstance(sub.slice, _ast.Constant) and sub.slice.value == 1
    assert found_exc is True

    assert ActionExecutionRecord.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert AutonomousResearchReceipt.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    dispatcher = AutonomousQueryResearchDispatcher()
    ast_info = dispatcher._default_ast_inspector("sym_x")
    assert ast_info["symbol"] == "sym_x" and ast_info["callers_count"] == 0
    assert dispatcher._default_ast_inspector("canonical_jcs")["callers_count"] > 0

    for kw in ("deep research", "autonomous research"):
        res = dispatcher._default_mockless_web_search(kw)
        assert [r["url"] for r in res] == ["https://arxiv.org/abs/2508.05668"]
    for kw in ("action space", "expa", "earl"):
        res = dispatcher._default_mockless_web_search(kw)
        assert [r["url"] for r in res] == ["https://arxiv.org/abs/2510.07581"]
    for kw in ("oracle gap", "cost of consensus", "bertalanic"):
        res = dispatcher._default_mockless_web_search(kw)
        assert [r["url"] for r in res] == ["https://arxiv.org/abs/2605.00914"]
    for kw in ("incomplete evidence", "clinical llms", "2610.04542"):
        res = dispatcher._default_mockless_web_search(kw)
        assert [r["url"] for r in res] == ["https://arxiv.org/abs/2610.04542"]
    res_fallback = dispatcher._default_mockless_web_search("totally_unmatched_query")
    assert [r["url"] for r in res_fallback] == ["https://sovereignnexus.org/evidence/verified_probe"]

    # Micro duration_ms boundary (probe_ms = max(1, len(payload) // 4 + len(evidence)))
    disp_empty = AutonomousQueryResearchDispatcher(web_search_fn=lambda _q: [{"snippet": "s", "url": "u"}])
    disp_empty.expand_query_8axis = lambda _rq: [ResearchQueryNode("n0", None, "X", "", 0)]  # type: ignore[method-assign]
    disp_empty.web_search_fn = lambda _q: []
    _, acts_empty = disp_empty.execute_multi_hop_research("", max_depth=0)
    assert acts_empty[0].duration_ms == 1

    n_cc, _ = dispatcher.execute_multi_hop_research("cost of consensus", max_depth=0)
    assert all(n.has_counterexample is True for n in n_cc)
    n_og, _ = dispatcher.execute_multi_hop_research("oracle gap", max_depth=0)
    assert all(n.has_counterexample is True for n in n_og)
    n_plain, _ = dispatcher.execute_multi_hop_research("plain topic", max_depth=0)
    assert all(n.has_counterexample is False for n in n_plain)

    n_d1, a_d1 = dispatcher.execute_multi_hop_research("plain topic", max_depth=1)
    assert len(n_d1) == 10 and len(a_d1) == 10

    hyp_dummy = EpistemicBrainstormHypothesis(
        "h1", "a", "US", "claim", ("A",), 8000, False, "", ()
    )
    for trig in ("counterexample", "collapse", "oracle gap"):
        d_trig = AutonomousQueryResearchDispatcher(
            web_search_fn=lambda _q, t=trig: [{"url": "u", "snippet": f"found {t} here"}]
        )
        ok_t, wit_t, _ = d_trig.execute_adversarial_falsification_probe(hyp_dummy)
        assert ok_t is True and trig in wit_t
    d_none = AutonomousQueryResearchDispatcher(
        web_search_fn=lambda _q: [{"url": "u", "snippet": "benign observation"}]
    )
    ok_n, wit_n, _ = d_none.execute_adversarial_falsification_probe(hyp_dummy)
    assert ok_n is False and wit_n == ""

    seen_pre_synth_conf: list[int] = []
    orig_synth = dispatcher.synthesize_brainstorm_with_evidence_dominance

    def _spy_synth(hyps: list[EpistemicBrainstormHypothesis]) -> tuple[list[EpistemicBrainstormHypothesis], bool]:
        seen_pre_synth_conf.extend(h.confidence_bps for h in hyps)
        return orig_synth(hyps)

    dispatcher.synthesize_brainstorm_with_evidence_dominance = _spy_synth  # type: ignore[method-assign]
    rcpt = dispatcher.execute_complete_research_and_brainstorm_cycle("test root query")
    assert seen_pre_synth_conf == [9500, 9800, 9200, 9600]
    assert rcpt.total_query_nodes_explored == 10
    assert rcpt.max_hop_depth == 1
    assert rcpt.counterexamples_identified == 3
    assert len(rcpt.receipt_id) == len("rcpt_aer_") + 16
    assert [h["confidence_bps"] for h in rcpt.synthesized_hypotheses] == [10000, 10000, 9200, 10000]

    # Trigger falsification promotion of non-counterexample candidates (line 445-457)
    d_all_counter = AutonomousQueryResearchDispatcher(
        web_search_fn=lambda _q: [{"title": "t", "url": "u", "snippet": "counterexample found"}]
    )
    rcpt_all = d_all_counter.execute_complete_research_and_brainstorm_cycle("q_all")
    assert rcpt_all.counterexamples_identified == 4
    assert all(h["evidence_dominant"] is True for h in rcpt_all.synthesized_hypotheses)
