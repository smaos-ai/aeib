#!/usr/bin/env python3
# File: tests/test_epistemic_regression_e01_e14.py
"""
Section 15 Capstone 2: Monotonic Epistemic & Ontic Regression Corpus (E01-E16).

Locks all 14 historical epistemic and ontic failure modes (E01-E14), the
EN 18286:2026 + DORA Art. 17 Compliance Bundler (E15), and the AGENTS.md
epistemic linguistic boundary gate (E16) into a permanent regression suite
requiring a 10000 bps (100%) catch rate.
"""

from __future__ import annotations

import ast
import io
import json
from pathlib import Path
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from benchmarks.public_sota_adapter import PublicSotaBenchmarkAdapter
from src.decide_autonomous_query_research_engine import AutonomousQueryResearchDispatcher
from src.decide_evaluation_rate_and_decay_solver import (
    DataProcessingInequalityGate,
    DecideV45AntiDecayEngine,
    KnowledgeIntegrationDecaySolver,
    MultiHopPassKAndHawkesCompensator,
)
from src.en18286_dora_audit_bundler import En18286DoraAuditBundler
from src.planetary_clearinghouse_and_tee_swarm import (
    ConfidentialTeeSwarmAttestationEngine,
    HardwareAttestationQuote,
    PlanetaryAgentClearinghouse,
    sha256_prefixed,
)
from src.sovereign_nexus_mcp_gateway import SovereignNexusMcpGateway
from src.transactional_storage_backend import SerializableMultiNodeConsensusBackend
from tools.cross_hemisphere_council_decide import (
    ModelAskQuery,
    ThreeTierAskResolutionRouter,
)


def test_e01_monotonic_test_union_prevents_subset_regression():
    """
    E01 (MISSED-1 Fix): Prevents the 54 -> 42 test-count subset drift by verifying
    that the unified mandatory test union across core and Sections 11-15 contains
    at least 70 test functions/methods.
    """
    mandatory_test_files = [
        "tests/test_industrial_protection_matrix.py",
        "tests/test_ansi_50bf_breaker_failure.py",
        "tests/test_saga_compensation.py",
        "tests/test_falsifiability_matrix.py",
        "tests/test_planetary_clearinghouse_and_tee_swarm.py",
        "tests/test_decide_autonomous_query_research_engine.py",
        "tests/test_cross_hemisphere_council_decide.py",
        "tests/test_decide_categorical_epistemic_engine.py",
        "tests/test_decide_evaluation_rate_and_decay_solver.py",
        "tests/test_global_dominance_g1_g2_g3.py",
        "tests/test_epistemic_regression_e01_e14.py",
    ]
    total_test_defs = 0
    for rel in mandatory_test_files:
        path = Path(rel)
        assert path.exists(), f"Missing mandatory test file: {rel}"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                total_test_defs += 1

    # Previous peak was 54; adding Sections 14 and 15 brings total >= 70
    assert total_test_defs >= 70, f"Monotonic test count violated: {total_test_defs} < 70"


def test_e02_claim_tier_archetype_labeling_enforced(tmp_path: Path):
    """
    E02 (MISSED-2 Fix): Verifies that G-Global-1 benchmark outputs explicitly carry
    claim_tier == MEASURED_LOCAL_ARCHETYPE_DETERMINISTIC_REPLAY_SEED_42.
    """
    adapter = PublicSotaBenchmarkAdapter()
    out_json = tmp_path / "bench_report.json"
    report = adapter.execute_full_public_benchmark(output_json_path=out_json)

    assert report.claim_tier == "MEASURED_LOCAL_ARCHETYPE_DETERMINISTIC_REPLAY_SEED_42"
    disk_data = json.loads(out_json.read_text(encoding="utf-8"))
    assert disk_data["claim_tier"] == "MEASURED_LOCAL_ARCHETYPE_DETERMINISTIC_REPLAY_SEED_42"
    assert "Deterministic archetype replay" in disk_data["evaluation_scope_note"]


def test_e03_kleppmann_target_side_per_replica_fencing_token_enforcement():
    """
    E03 (MISSED-3 Fix): Verifies Kleppmann's Fencing Token Lemma at the target storage
    replicas: if a newer leader advances target replica fencing tokens to 8 while an
    older leader is paused after a coordinator check at token 5, the target replicas
    atomically reject the delayed write with HALT_STORAGE_STALE_FENCING_TOKEN.
    """
    backend = SerializableMultiNodeConsensusBackend()
    backend.register_workflow_budget("wf_kleppmann", 50000)

    # Initial nominal commit at token 4
    r1 = backend.stage_pre_dispatch_intent(
        caid="caid_k_1",
        workflow_id="wf_kleppmann",
        amount_minor=5000,
        fencing_token=4,
        payload_hash="h1",
    )
    assert r1.disposition == "COMMITTED_STAGED_ESCROW"

    # Simulate a newer leader committing fencing_token=8 directly at target AZ replicas
    # while the old coordinator instance still thinks workflow_fencing_tokens is 4
    backend.advance_replica_fencing_token_directly("wf_kleppmann", new_leader_token=8)

    # Delayed write from old leader arrives with fencing_token=5 (>4 on coordinator, but <8 on target replicas!)
    r_delayed = backend.stage_pre_dispatch_intent(
        caid="caid_k_delayed",
        workflow_id="wf_kleppmann",
        amount_minor=5000,
        fencing_token=5,
        payload_hash="h_delayed",
    )
    assert r_delayed.disposition == "HALT_STORAGE_STALE_FENCING_TOKEN"
    assert backend.get_intent_record("caid_k_delayed") is None


def test_e04_live_stdio_jsonrpc_mcp_transport_loop(tmp_path: Path):
    """
    E04 (MISSED-4 Fix): Verifies line-delimited JSON-RPC 2.0 stdio transport loop
    for 30-second IDE attachment via .mcp.json.
    """
    gw = SovereignNexusMcpGateway(db_path=tmp_path / "stdio_gw.sqlite")
    gw.storage.register_workflow_budget("wf_stdio", 100000)

    req_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "station1_authorize",
                    "arguments": {
                        "caid": "caid_stdio_1",
                        "workflow_id": "wf_stdio",
                        "amount_minor": 1500,
                        "fencing_token": 1,
                        "proposal_snapshot_hash": "snap_1",
                        "live_pre_commit_snapshot_hash": "snap_1",
                        "sql_statement": "SELECT id FROM orders WHERE tenant_id = 'org_1'",
                    },
                },
            }
        ),
    ]
    in_buf = io.StringIO("\n".join(req_lines) + "\n")
    out_buf = io.StringIO()

    count = gw.run_stdio_loop(input_stream=in_buf, output_stream=out_buf)
    assert count == 3

    responses = [json.loads(line) for line in out_buf.getvalue().strip().splitlines()]
    assert len(responses) == 3
    assert responses[0]["result"]["serverInfo"]["name"] == "sovereign-nexus-mcp"
    assert len(responses[1]["result"]["tools"]) == 3
    assert responses[2]["result"]["structuredContent"]["status"] == "AUTHORIZED"


def test_e05_knowledge_integration_decay_sake_dual_anchoring_arxiv_2602_09517():
    """E05: Verifies SAKE dual-boundary anchoring counters KID at 12k tokens."""
    solver = KnowledgeIntegrationDecaySolver()
    rec = solver.anchor_evidence_sake(
        evidence_id="ev_e05",
        hop_depth=4,
        accumulated_context_tokens=12000,
        fact_payload={"clause": "EN_18286_2026"},
    )
    assert rec.naive_utilization_bps == 1142
    assert rec.sake_utilization_bps == 9821


def test_e06_shannon_dpi_prose_handoff_and_zero_entropy_rejection_arxiv_2604_02460():
    """E06: Verifies Stanford DPI gate blocks lossy prose and zero-entropy handoffs."""
    gate = DataProcessingInequalityGate(min_external_entropy_bps=150)
    r_lossy = gate.evaluate_handoff("h1", "a1", "a2", 8000, 500, uses_lossless_vault_pointer=False)
    assert r_lossy.disposition == "HALT_DPI_LOSSY_PROSE_HANDOFF"

    r_zero = gate.evaluate_handoff("h2", "a1", "a2", 8000, 0, uses_lossless_vault_pointer=True)
    assert r_zero.disposition == "HALT_DPI_ZERO_EXTERNAL_ENTROPY"


def test_e07_celf_ig_search_diminishing_returns_pruning_arxiv_2604_15148():
    """E07: Verifies CELF IG-Search prunes low-gain queries while preserving 10000 bps coverage."""
    engine = DecideV45AntiDecayEngine()
    report = engine.evaluate_complete_anti_decay_cycle()
    assert report.coverage_achieved_bps == 10000
    assert report.pruned_low_gain_steps_count == 4
    assert report.eval_rate_multiplier_bps >= 300000


def test_e08_multi_hop_pass8_compounding_decay_compensation():
    """E08: Verifies 5-hop Pass^8 recovery from 148 bps to 9230 bps."""
    comp = MultiHopPassKAndHawkesCompensator()
    res = comp.evaluate_multi_hop_pass_k(hop_count=5, k_trials=8, single_hop_accuracy_bps=9000)
    assert res.unverified_pass_k_bps == 148
    assert res.step_verified_pass_k_bps == 9230


def test_e09_asymmetric_evidence_dominance_oracle_gap_and_tone_critique():
    """E09: Verifies Asymmetric Evidence Dominance eliminates the 32.3% Oracle Gap."""
    dispatcher = AutonomousQueryResearchDispatcher()
    rcpt = dispatcher.execute_complete_research_and_brainstorm_cycle(
        "Evaluate oracle gap in homogeneous multi-agent debate"
    )
    assert rcpt.oracle_gap_eliminated is True
    assert rcpt.counterexamples_identified >= 1


def test_e10_cross_hemisphere_3tier_ask_router_arxiv_2610_04542():
    """E10: Verifies 3-Tier Ask Router resolves O(1) snapshot, web probe, and dev schema."""
    router = ThreeTierAskResolutionRouter(
        parent_o1_snapshot={"moat_station1": "WAL_INTENT_LATCH"},
        web_search_probe_fn=lambda q: "arXiv:2609.37475 60.53% ICR",
    )
    queries = [
        ModelAskQuery("q1", "qwen-3-max", "LOCAL_CODEBASE", "moat_station1", "check latch"),
        ModelAskQuery("q2", "qwen-3-max", "EXTERNAL_WEB_SOTA", "ICR rate", "check drift"),
        ModelAskQuery("q3", "qwen-3-max", "DEVELOPER_DECISION", "Pick region", "deploy", ("EU", "US")),
    ]
    resolved = router.resolve_ask_queries(queries)
    assert resolved[0].answered_by == "PARENT_O1_SNAPSHOT"
    assert resolved[1].answered_by == "WEB_SEARCH_PROBE"
    assert resolved[2].answered_by == "PENDING_DEVELOPER"


def test_e11_proposal_to_commit_state_drift_6way_witness_arxiv_2609_37475(tmp_path: Path):
    """E11: Verifies 6-Way Joint Commit Witness halts on proposal-to-commit state drift."""
    gw = SovereignNexusMcpGateway(db_path=tmp_path / "e11.sqlite")
    gw.storage.register_workflow_budget("wf_e11", 10000)
    resp = gw.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "station1_authorize",
                "arguments": {
                    "caid": "caid_e11",
                    "workflow_id": "wf_e11",
                    "amount_minor": 1000,
                    "fencing_token": 1,
                    "proposal_snapshot_hash": "snap_old",
                    "live_pre_commit_snapshot_hash": "snap_drifted",
                },
            },
        }
    )
    assert resp["result"]["structuredContent"]["status"] == "HALT_PROPOSAL_TO_COMMIT_STATE_DRIFT"


def test_e12_sves_missing_rls_predicate_sql_block(tmp_path: Path):
    """E12: Verifies S-VES blocks SQL statements lacking mandatory RLS tenant predicates."""
    gw = SovereignNexusMcpGateway(db_path=tmp_path / "e12.sqlite")
    gw.storage.register_workflow_budget("wf_e12", 10000)
    resp = gw.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "station1_authorize",
                "arguments": {
                    "caid": "caid_e12",
                    "workflow_id": "wf_e12",
                    "amount_minor": 1000,
                    "fencing_token": 1,
                    "proposal_snapshot_hash": "snap_ok",
                    "live_pre_commit_snapshot_hash": "snap_ok",
                    "sql_statement": "SELECT * FROM customer_ledgers",
                },
            },
        }
    )
    assert resp["result"]["structuredContent"]["status"] == "HALT_SVES_MISSING_RLS_PREDICATE"


def test_e13_http_504_indeterminate_latch_and_blind_retry_block_arxiv_2609_29095(tmp_path: Path):
    """E13: Verifies EFFECT_INDETERMINATE latch blocks blind retries on HTTP 504 timeouts."""
    gw = SovereignNexusMcpGateway(db_path=tmp_path / "e13.sqlite")
    gw.storage.register_workflow_budget("wf_e13", 10000)
    gw.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "station1_authorize",
                "arguments": {
                    "caid": "caid_e13",
                    "workflow_id": "wf_e13",
                    "amount_minor": 2000,
                    "fencing_token": 1,
                    "proposal_snapshot_hash": "snap_1",
                    "live_pre_commit_snapshot_hash": "snap_1",
                },
            },
        }
    )
    gw.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "station2_reconcile",
                "arguments": {
                    "caid": "caid_e13",
                    "fencing_token": 2,
                    "action": "LATCH_INDETERMINATE",
                },
            },
        }
    )
    retry = gw.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "station1_authorize",
                "arguments": {
                    "caid": "caid_e13",
                    "workflow_id": "wf_e13",
                    "amount_minor": 2000,
                    "fencing_token": 3,
                    "proposal_snapshot_hash": "snap_1",
                    "live_pre_commit_snapshot_hash": "snap_1",
                },
            },
        }
    )
    assert retry["result"]["structuredContent"]["status"] == "HALT_STORAGE_CAID_ALREADY_LATCHED"


def test_e14_planetary_clearinghouse_eas_and_tee_report_data_binding():
    """E14: Verifies Planetary Clearinghouse EAS >= 8000 bps and TEE REPORT_DATA key binding."""
    ch = PlanetaryAgentClearinghouse(Ed25519PrivateKey.generate())
    res = ch.register_and_escrow_trade(
        deliverable_id="deliv_e14",
        seller_agent_did="did:aeib:seller:1",
        buyer_agent_did="did:aeib:buyer:1",
        deliverable_hash=sha256_prefixed(b"payload"),
        settlement_amount_minor=5000,
        eas_score_bps=6500,
    )
    assert res["allowed"] is False
    assert res["halt_code"] == "HALT_CLEARINGHOUSE_EAS_ALIGNMENT_INSUFFICIENT"

    mfg_priv = Ed25519PrivateKey.generate()
    tee = ConfidentialTeeSwarmAttestationEngine(
        mfg_priv.public_key(),
        frozenset({"sha384:pinned_intel_tdx_aeib_enclave_measurement_v1"}),
    )
    agent_pub_bytes = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
    bad_quote = HardwareAttestationQuote(
        tee_architecture="INTEL_TDX",
        measurement_mrenclave="sha384:pinned_intel_tdx_aeib_enclave_measurement_v1",
        report_data_binding=sha256_prefixed(b"wrong_public_key_bytes"),
        platform_svn=5,
        hardware_signature_b64="AAAA",
    )
    r_bad = tee.verify_and_admit_confidential_agent(
        "did:aeib:agent:cvm-e14", agent_pub_bytes, bad_quote
    )
    assert r_bad["admitted"] is False
    assert r_bad["halt_code"] == "HALT_TEE_REPORT_DATA_KEY_BINDING_MISMATCH"


def test_e15_en18286_dora_compliance_bundler_and_offline_verification(tmp_path: Path):
    """E15: Verifies EN 18286:2026 + DORA Art. 17 Compliance Bundler and offline verification."""
    bundler = En18286DoraAuditBundler()
    out_bundle = tmp_path / "en18286_dora_bundle.json"
    bundle = bundler.export_compliance_bundle(output_path=out_bundle)

    assert out_bundle.exists()
    assert bundle.verified_files_count == 14
    assert bundle.en18286_clauses_satisfied == 5
    assert bundle.dora_art17_controls_satisfied == 4
    assert bundle.cbom_components_count == 4
    assert bundle.claim_tier == "MEASURED_LOCAL_ARCHETYPE_DETERMINISTIC_REPLAY_SEED_42"
    assert En18286DoraAuditBundler.verify_exported_bundle_file(out_bundle) is True

    # Tamper check must fail closed
    doc = json.loads(out_bundle.read_text(encoding="utf-8"))
    doc["verified_files_count"] = 999
    tampered_path = tmp_path / "tampered_bundle.json"
    tampered_path.write_text(json.dumps(doc), encoding="utf-8")
    assert En18286DoraAuditBundler.verify_exported_bundle_file(tampered_path) is False


def test_e16_banned_words_absence():
    """E16: Enforces AGENTS.md epistemic boundary across Section 14-15 files."""
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "unhack" + "able",
        "proven " + "universally",
    ]
    for fpath in (
        "src/en18286_dora_audit_bundler.py",
        "tests/test_epistemic_regression_e01_e14.py",
        "src/transactional_storage_backend.py",
        "src/sovereign_nexus_mcp_gateway.py",
        "benchmarks/public_sota_adapter.py",
    ):
        with open(fpath, "r", encoding="utf-8") as f:
            txt = f.read().lower()
            for word in banned:
                assert word not in txt, f"Banned term '{word}' found in {fpath}"
