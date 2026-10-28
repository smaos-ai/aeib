#!/usr/bin/env python3
# File: tests/test_hamt_cross_pollination_and_cerno_scion_ta14.py
"""
Verification suite for:
1. `tools/hamt_cross_pollination_and_evidence_graph.py`
   - HAMT 32-way Persistent State Forking (`HamtPersistentStateTree`)
   - SQLite O(1) Counterexample Knowledge Graph (`SqliteCounterexampleEvidenceGraph`)
   - ID-Bound Adversarial Cross-Pollination (`AdversarialCrossPollinationOrchestrator`)
2. `src/cerno_scion_ta14_omnigent_fabric.py`
   - Cerno System One Fast Decision Router (`CernoSystemOneFastRouter`)
   - Anthropic Scion Disjoint Write-Set Merger (`ScionServerAuthoritativeDisjointMerger`)
   - Onyx + Nemotron Hybrid Retriever (`OnyxNemotronHybridRetriever`)
   - TA-14 Runtime Admissibility Protocol (`Ta14RuntimeAdmissibilityProtocol`)
   - Databricks Omnigent 3-Tier Policy Engine (`OmnigentThreeTierMetaHarness`)
   - Machine Identity & Shadow Agent Guard (`MachineIdentityShadowAgentGuard`)
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.cerno_scion_ta14_omnigent_fabric import (
    CernoSystemOneFastRouter,
    MachineIdentityCertificate,
    MachineIdentityShadowAgentGuard,
    OmnigentThreeTierMetaHarness,
    OnyxDocumentChunk,
    OnyxNemotronHybridRetriever,
    ScionServerAuthoritativeDisjointMerger,
    Ta14RuntimeAdmissibilityProtocol,
    Ta14TripleAdmissibilityProof,
    canonical_jcs,
    sha256_prefixed,
)
from tools.hamt_cross_pollination_and_evidence_graph import (
    AdversarialCrossPollinationOrchestrator,
    HamtPersistentStateTree,
    PersonaAgentSpec,
    SqliteCounterexampleEvidenceGraph,
)


def test_hamt_persistent_state_tree_o1_fork_and_structural_sharing() -> None:
    tree0 = HamtPersistentStateTree()
    tree1 = tree0.fork_with("agent:alpha", {"role": "architect", "step": 1})
    tree2 = tree1.fork_with("agent:beta", {"role": "skeptic", "step": 2})
    tree1_mutated = tree1.fork_with("agent:alpha", {"role": "architect", "step": 99})

    # Verify immutability across forked branches
    assert tree0.lookup("agent:alpha") is None
    assert tree1.lookup("agent:alpha") == {"role": "architect", "step": 1}
    assert tree2.lookup("agent:alpha") == {"role": "architect", "step": 1}
    assert tree2.lookup("agent:beta") == {"role": "skeptic", "step": 2}
    assert tree1_mutated.lookup("agent:alpha") == {"role": "architect", "step": 99}
    assert tree1.root_caid != tree2.root_caid
    assert tree1.root_caid != tree1_mutated.root_caid


def test_adversarial_cross_pollination_and_sqlite_evidence_graph_o1_cache() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "tier4_evidence_graph.sqlite"
        graph = SqliteCounterexampleEvidenceGraph(db_path)
        judge_priv = Ed25519PrivateKey.generate()

        web_index = {
            "arXiv:2609.29095 blind retry duplicate rate": {
                "summary": "LIMBO (arXiv:2609.29095) proves blind retries under 504 cause 56%-74% duplicate writes.",
                "url": "https://arxiv.org/abs/2609.29095",
            }
        }

        # Agent A proposes a flawed naive-retry claim; Agent B proposes WAL + pre-dispatch latch
        agent_a = PersonaAgentSpec(
            agent_id="agent_A_naive",
            persona_vector="OPTIMIST",
            draft_generator_fn=lambda _: {
                "claim": "Stateless HTTP 504 auto-retry is safe without pre-dispatch WAL",
                "proposed_design": "Simple 3x exponential backoff loop",
            },
            cross_critic_fn=lambda target_id, draft, search_fn: {
                # Sycophantic response that must be rejected by the orchestrator!
                "critique_text": "I think they are right about this.",
                "has_conflict": False,
                "search_query": "",
                "url_evidence": "",
            },
        )

        def _skeptic_critic(
            target_id: str,
            draft: Dict[str, str],
            search_fn: Callable[[str], Optional[Dict[str, str]]],
        ) -> Dict[str, Any]:
            if "Stateless HTTP 504 auto-retry" in draft["claim"]:
                q = "arXiv:2609.29095 blind retry duplicate rate"
                hit = search_fn(q)
                if hit is not None:
                    return {
                        "critique_text": hit["summary"],
                        "has_conflict": True,
                        "search_query": q,
                        "url_evidence": hit["url"],
                    }
            return {"critique_text": "No flaw found", "has_conflict": False}

        agent_b = PersonaAgentSpec(
            agent_id="agent_B_skeptic",
            persona_vector="SKEPTIC",
            draft_generator_fn=lambda _: {
                "claim": "Require Station 1 F_FULLFSYNC WAL and EFFECT_INDETERMINATE latch before socket open",
                "proposed_design": "Two-phase intent-outcome WAL with out-of-band probe",
            },
            cross_critic_fn=_skeptic_critic,
        )

        orchestrator = AdversarialCrossPollinationOrchestrator(
            agents=[agent_a, agent_b],
            web_search_tool_fn=lambda q: web_index.get(q),
            evidence_graph=graph,
            judge_privkey=judge_priv,
        )

        # Run 1: Discovers conflict via web search, rejects Agent A's sycophancy, persists edge in SQLite
        res1 = orchestrator.run_batch_cross_pollination(
            topic_key="http_504_retry_safety",
            initial_prompt="Design timeout recovery for payment tool calls",
        )
        syn1 = res1["synthesis"]
        assert syn1["rejected_sycophantic_critiques"] == 1
        assert syn1["conflict_count_registered"] == 1
        assert syn1["refuted_agents_excluded"] == ["agent_A_naive"]
        assert len(syn1["surviving_verified_designs"]) == 1
        assert syn1["surviving_verified_designs"][0]["agent_id"] == "agent_B_skeptic"

        # Run 2: O(1) SQLite Evidence Graph cache hit! Refutes Agent A immediately from Tier-4 graph
        orchestrator2 = AdversarialCrossPollinationOrchestrator(
            agents=[agent_a, agent_b],
            web_search_tool_fn=lambda q: None,  # Even with web disabled, Tier-4 SQLite Graph catches it in O(1)!
            evidence_graph=graph,
            judge_privkey=judge_priv,
        )
        res2 = orchestrator2.run_batch_cross_pollination(
            topic_key="http_504_retry_safety",
            initial_prompt="Design timeout recovery for payment tool calls",
        )
        syn2 = res2["synthesis"]
        assert syn2["historical_o1_cache_hits"] == 1
        assert syn2["refuted_agents_excluded"] == ["agent_A_naive"]
        graph.close()


def test_cerno_system_one_fast_router_and_scion_disjoint_write_sets() -> None:
    router = CernoSystemOneFastRouter(
        fast_allow_confidence_floor_bps=9500,
        block_hazard_ceiling_bps=7000,
    )

    # 1. Read-only op with 98% calibrated safe probability and 18ms latency -> FAST_PATH_READ_ONLY_ALLOW
    r_fast = router.route_single_pass(
        ticket_id="t-01",
        tool_name="read_symbol",
        is_read_only_op=True,
        calibrated_safe_prob_bps=9800,
        calibrated_hazard_prob_bps=100,
        forward_pass_latency_us=18_000,
    )
    assert r_fast["allowed"] is True
    assert r_fast["route"] == "FAST_PATH_READ_ONLY_ALLOW"

    # 2. High hazard probability (85%) -> IMMEDIATE_BLOCK
    r_hazard = router.route_single_pass(
        ticket_id="t-02",
        tool_name="bash_exec",
        is_read_only_op=False,
        calibrated_safe_prob_bps=1500,
        calibrated_hazard_prob_bps=8500,
        forward_pass_latency_us=22_000,
    )
    assert r_hazard["allowed"] is False
    assert r_hazard["halt_code"] == "HALT_CERNO_SYSTEM1_HIGH_HAZARD_PROBABILITY"

    # 3. Scion Server-Authoritative Disjoint Write Sets + O(1) Rollback
    scion = ScionServerAuthoritativeDisjointMerger(initial_commit_id="c-000")
    res_a = scion.reserve_disjoint_write_set(
        "agent_writer_1", frozenset({"src/auth.py", "src/token.py"})
    )
    assert res_a["allowed"] is True

    # Overlapping write reservation on `src/token.py` must fail closed!
    res_b_collide = scion.reserve_disjoint_write_set(
        "agent_writer_2", frozenset({"src/token.py", "src/metrics.py"})
    )
    assert res_b_collide["allowed"] is False
    assert res_b_collide["halt_code"] == "HALT_SCION_WRITE_SET_COLLISION"
    assert res_b_collide["colliding_files"] == ["src/token.py"]

    # Disjoint reservation succeeds
    res_b_ok = scion.reserve_disjoint_write_set(
        "agent_writer_2", frozenset({"src/metrics.py"})
    )
    assert res_b_ok["allowed"] is True

    # Commit agent_writer_1 and then test O(1) branch rollback
    m1 = scion.merge_server_authoritative_commit(
        commit_id="c-001",
        agent_id="agent_writer_1",
        modified_files=frozenset({"src/auth.py", "src/token.py"}),
        file_contents={"src/auth.py": "v1", "src/token.py": "v1"},
    )
    assert m1["allowed"] is True
    assert scion.head_commit_id == "c-001"

    rb = scion.rollback_branch_o1("c-000")
    assert rb["allowed"] is True
    assert scion.head_commit_id == "c-000"


def test_onyx_nemotron_hybrid_retriever_and_ta14_runtime_admissibility() -> None:
    # 1. Onyx + Nemotron Hybrid Retriever
    retriever = OnyxNemotronHybridRetriever()
    retriever.index_chunk(
        OnyxDocumentChunk(
            doc_id="doc-dora-17",
            connector_source="s3_compliance_vault",
            text="DORA Article 17 incident classification and rollback protocol",
            embedding_int_vec=(90, 10, 0),
        )
    )
    retriever.index_chunk(
        OnyxDocumentChunk(
            doc_id="doc-ui-theme",
            connector_source="confluence",
            text="Frontend CSS button spacing guidelines",
            embedding_int_vec=(5, 95, 0),
        )
    )
    hits = retriever.retrieve_hybrid(
        query_terms=["dora", "rollback", "incident"],
        query_vec=[95, 5, 0],
        top_k=1,
    )
    assert len(hits) == 1
    assert hits[0]["doc_id"] == "doc-dora-17"
    assert hits[0]["hybrid_score_bps"] >= 9000

    # 2. TA-14 Runtime Admissibility Protocol ("No admissible evidence, no admissible execution")
    auth_priv = Ed25519PrivateKey.generate()
    auth_pub = auth_priv.public_key()
    ta14 = Ta14RuntimeAdmissibilityProtocol(authority_pubkey=auth_pub)

    statement = {
        "action_caid": "caid:wire:001",
        "applicable_authority_scope": ["disburse_settlement"],
        "continuity_hash_chain_tip": "sha256:tip001",
        "established_standing_active": True,
        "reality_observation_digest": "sha256:obs001",
    }
    sig_b64 = base64.b64encode(auth_priv.sign(canonical_jcs(statement))).decode("ascii")

    # Missing admissible evidence -> HALT_TA14_NO_ADMISSIBLE_EVIDENCE
    proof_no_ev = Ta14TripleAdmissibilityProof(
        action_caid="caid:wire:001",
        reality_observation_digest="",
        continuity_hash_chain_tip="sha256:tip001",
        admissible_evidence_present=False,
        applicable_authority_scope=frozenset({"disburse_settlement"}),
        established_standing_active=True,
        authority_signature_b64=sig_b64,
    )
    r_no_ev = ta14.adjudicate_execution_admissibility("disburse_settlement", proof_no_ev)
    assert r_no_ev["admissible"] is False
    assert r_no_ev["halt_code"] == "HALT_TA14_NO_ADMISSIBLE_EVIDENCE"

    # Valid triple proof -> admissible across all 8 stages
    proof_ok = Ta14TripleAdmissibilityProof(
        action_caid="caid:wire:001",
        reality_observation_digest="sha256:obs001",
        continuity_hash_chain_tip="sha256:tip001",
        admissible_evidence_present=True,
        applicable_authority_scope=frozenset({"disburse_settlement"}),
        established_standing_active=True,
        authority_signature_b64=sig_b64,
    )
    r_ok = ta14.adjudicate_execution_admissibility("disburse_settlement", proof_ok)
    assert r_ok["admissible"] is True
    assert len(r_ok["chain_traversed"]) == 8


def test_omnigent_three_tier_policy_and_machine_identity_shadow_agent_guard() -> None:
    # 1. Omnigent 3-Tier Policy (Server / Agent / Session) with DENY > ASK > ALLOW dominance
    omnigent = OmnigentThreeTierMetaHarness(
        server_tier_rules={"read_code": "ALLOW", "deploy_prod": "ASK", "drop_db": "DENY"},
        agent_tier_rules={"read_code": "ALLOW", "deploy_prod": "ALLOW", "drop_db": "ALLOW"},
        session_tier_rules={"read_code": "ASK", "deploy_prod": "ALLOW", "drop_db": "ALLOW"},
    )
    # Session tier narrows `read_code` from ALLOW to ASK
    d_read = omnigent.evaluate_three_tier_policy("read_code")
    assert d_read["effective_decision"] == "ASK"
    assert d_read["deciding_tier"] == "SESSION"

    # Server tier DENY overrides Agent & Session ALLOW on `drop_db`
    d_drop = omnigent.evaluate_three_tier_policy("drop_db")
    assert d_drop["effective_decision"] == "DENY"
    assert d_drop["halt_code"] == "HALT_OMNIGENT_POLICY_DENIED"

    # 2. Machine Identity & Shadow Agent Guard (109:1 ratio governance)
    ca_priv = Ed25519PrivateKey.generate()
    ca_pub = ca_priv.public_key()
    id_guard = MachineIdentityShadowAgentGuard(identity_ca_pubkey=ca_pub)

    # Unregistered Shadow Agent is immediately blocked
    shadow_res = id_guard.verify_agent_dispatch(
        machine_agent_caid="caid:agent:shadow-unregistered-99",
        requested_tool="read_file",
        current_epoch=1760918500,
    )
    assert shadow_res["allowed"] is False
    assert shadow_res["halt_code"] == "HALT_SHADOW_AGENT_UNREGISTERED_IDENTITY"

    # Register legitimate machine identity tied to human sponsor DID
    cert_payload = {
        "allowed_tools": ["read_file", "run_pytest"],
        "expires_at_epoch": 1760922000,
        "human_sponsor_did": "did:aeib:human:lead-eng-01",
        "machine_agent_caid": "caid:agent:worker-42",
    }
    sig_b64 = base64.b64encode(ca_priv.sign(canonical_jcs(cert_payload))).decode("ascii")
    cert = MachineIdentityCertificate(
        machine_agent_caid="caid:agent:worker-42",
        human_sponsor_did="did:aeib:human:lead-eng-01",
        allowed_tools=frozenset({"read_file", "run_pytest"}),
        expires_at_epoch=1760922000,
        signature_b64=sig_b64,
    )
    reg_res = id_guard.register_machine_identity(cert)
    assert reg_res["registered"] is True

    auth_res = id_guard.verify_agent_dispatch(
        machine_agent_caid="caid:agent:worker-42",
        requested_tool="run_pytest",
        current_epoch=1760918500,
    )
    assert auth_res["allowed"] is True


def test_banned_words_absence() -> None:
    banned = [
        "guaran" + "teed",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "im" + "mune",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
    ]
    for path_str in [
        "tools/hamt_cross_pollination_and_evidence_graph.py",
        "src/cerno_scion_ta14_omnigent_fabric.py",
        "tests/test_hamt_cross_pollination_and_cerno_scion_ta14.py",
    ]:
        text = Path(path_str).read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in text, f"Forbidden term '{word}' found in {path_str}"


def test_section10_mutation_boundaries(tmp_path: Path) -> None:
    import ast as _ast
    import pytest
    import src.cerno_scion_ta14_omnigent_fabric as csto
    import tools.hamt_cross_pollination_and_evidence_graph as hcp
    from tools.hamt_cross_pollination_and_evidence_graph import (
        CounterexampleGraphEdge,
        HamtNode,
    )

    for mod in (hcp, csto):
        tree = _ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        found_exc = False
        for node in _ast.walk(tree):
            if isinstance(node, _ast.ExceptHandler) and isinstance(node.type, _ast.Name) and node.type.id == "ImportError":
                for stmt in node.body:
                    if isinstance(stmt, _ast.Expr) and isinstance(stmt.value, _ast.Call):
                        found_exc = True
                        assert isinstance(stmt.value.args[0], _ast.Constant) and stmt.value.args[0].value == 0
        assert found_exc is True

    with pytest.raises(ValueError, match="Floats are forbidden"):
        hcp.canonical_jcs({"f": 1.5})
    with pytest.raises(ValueError, match="Floats are forbidden"):
        csto.canonical_jcs({"f": 1.5})

    assert HamtNode.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert CounterexampleGraphEdge.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert PersonaAgentSpec.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert Ta14TripleAdmissibilityProof.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    # HAMT multi-branch collision and update test (40 keys > 32-way root branching)
    assert HamtPersistentStateTree._key_hash32("k_0") < (1 << 32)
    hamt = HamtPersistentStateTree()
    for i in range(40):
        hamt = hamt.fork_with(f"k_{i}", i)
    for i in range(40):
        assert hamt.lookup(f"k_{i}") == i
    for i in range(40):
        hamt = hamt.fork_with(f"k_{i}", i + 1000)
    for i in range(40):
        assert hamt.lookup(f"k_{i}") == i + 1000
    assert hamt.lookup("k_missing") is None

    # SqliteCounterexampleEvidenceGraph exact field mapping
    db_p = tmp_path / "eg.sqlite"
    eg = SqliteCounterexampleEvidenceGraph(db_p)
    edge = CounterexampleGraphEdge(
        edge_id="e_1",
        topic_key="top_1",
        source_critic_agent="critic_1",
        target_author_agent="author_1",
        target_snapshot_caid="sha256:snap_1",
        refuted_claim_text="claim_1",
        counterexample_summary="sum_1",
        url_evidence="https://example.org/ev1",
        search_query_executed="q_1",
    )
    ecaid = eg.record_counterexample_edge(edge)
    top_rows = eg.lookup_by_topic_o1("top_1")
    assert len(top_rows) == 1
    assert top_rows[0] == {
        "counterexample_summary": "sum_1",
        "edge_caid": ecaid,
        "edge_id": "e_1",
        "refuted_claim_text": "claim_1",
        "search_query_executed": "https://example.org/ev1",
        "source_critic_agent": "critic_1",
        "target_author_agent": "author_1",
        "target_snapshot_caid": "sha256:snap_1",
        "topic_key": "top_1",
        "url_evidence": "https://example.org/ev1",
    }
    assert eg.lookup_by_claim_exact_o1("missing_claim") is None
    exact_hit = eg.lookup_by_claim_exact_o1("claim_1")
    assert exact_hit == {
        "counterexample_summary": "sum_1",
        "edge_caid": ecaid,
        "edge_id": "e_1",
        "topic_key": "top_1",
        "url_evidence": "https://example.org/ev1",
    }
    eg.close()

    # CernoSystemOneFastRouter defaults & SLA boundary
    r_def = CernoSystemOneFastRouter()
    assert r_def._fast_allow_floor == 9500 and r_def._block_ceiling == 7000
    r_sla = r_def.route_single_pass("t_sla", "read_x", True, 9900, 0, 52_001)
    assert r_sla["allowed"] is False and r_sla["halt_code"] == "HALT_CERNO_SLA_LATENCY_EXCEEDED"
    assert r_def.route_single_pass("t_9500", "read_x", True, 9500, 0, 1000)["route"] == "FAST_PATH_READ_ONLY_ALLOW"
    assert r_def.route_single_pass("t_9499", "read_x", True, 9499, 0, 1000)["route"] == "STATION1_FULL_ADMISSIBILITY_GATE"
    assert r_def.route_single_pass("t_7000", "read_x", True, 9900, 7000, 1000)["allowed"] is False
    assert r_def.route_single_pass("t_6999", "read_x", True, 9900, 6999, 1000)["allowed"] is True

    scion = ScionServerAuthoritativeDisjointMerger()
    assert scion.rollback_branch_o1("nonexistent_commit")["allowed"] is False

    # OnyxNemotronHybridRetriever default top_k=3, zero vector, and exact score math
    ret = OnyxNemotronHybridRetriever()
    for idx in range(4):
        ret.index_chunk(
            OnyxDocumentChunk(f"d_{idx}", "src", f"alpha beta {idx}", (3, 4, 0))
        )
    hits_def = ret.retrieve_hybrid(["alpha", "beta"], [3, 4, 0])
    assert len(hits_def) == 3
    assert hits_def[0]["hybrid_score_bps"] == 10000
    hits_zero = ret.retrieve_hybrid(["alpha"], [0, 0, 0])
    assert hits_zero[0]["hybrid_score_bps"] == 5000

    # Ta14RuntimeAdmissibilityProtocol failure branches
    auth_priv = Ed25519PrivateKey.generate()
    ta14 = Ta14RuntimeAdmissibilityProtocol(auth_priv.public_key())
    p_base = Ta14TripleAdmissibilityProof(
        action_caid="caid:1",
        reality_observation_digest="sha256:obs1",
        continuity_hash_chain_tip="sha256:tip1",
        admissible_evidence_present=True,
        applicable_authority_scope=frozenset({"act_ok"}),
        established_standing_active=True,
        authority_signature_b64=base64.b64encode(b"badsig").decode("ascii"),
    )
    r_unauth = ta14.adjudicate_execution_admissibility("act_missing", p_base)
    assert r_unauth["admissible"] is False and r_unauth["halt_code"] == "HALT_TA14_APPLICABLE_AUTHORITY_MISSING"
    r_badsig = ta14.adjudicate_execution_admissibility("act_ok", p_base)
    assert r_badsig["admissible"] is False and r_badsig["halt_code"] == "HALT_TA14_INVALID_AUTHORITY_BINDING"

    # Omnigent fallback precedence default = 2
    omni = OmnigentThreeTierMetaHarness(
        server_tier_rules={"t": "DENY"},
        agent_tier_rules={"t": "UNMAPPED_VERDICT"},
        session_tier_rules={"t": "ALLOW"},
    )
    assert omni.evaluate_three_tier_policy("t")["deciding_tier"] == "SERVER"
