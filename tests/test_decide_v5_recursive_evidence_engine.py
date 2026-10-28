#!/usr/bin/env python3
# File: tests/test_decide_v5_recursive_evidence_engine.py
"""
Verification Suite for `/decide` v5.0:
- 5-Stage Recursive Parallel Evidence-Producing Decision Engine & `--falsify` Mode
- `Dossier` Persistent Research Ledger & `vscode-team-kit` Quality Gate
- Vector 1: `ZkTlsBlindApiAttestor` (Blind API range/status attestation without PII leakage)
- Vector 2: `ShannonChannelCapacityGate` (Steganography / Shannon entropy confinement)
- Vector 3: `ThermodynamicJouleEscrowGate` (Token-to-Joule RAPL budget throttle)
- Vector 4: `VcgTruthfulBudgetAuctioneer` (VCG truthful mechanism design for subagents)
- Vector 5: `AntigenGossipDefenseMesh` (Signed behavioral antigen gossip propagation)
"""

from __future__ import annotations

import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.decide_v5_recursive_evidence_engine import (
    AntigenGossipDefenseMesh,
    DecideV5EvidenceEngine,
    FalsificationVector,
    ShannonChannelCapacityGate,
    SubagentBid,
    ThermodynamicJouleEscrowGate,
    TypedEvidenceClaim,
    VcgTruthfulBudgetAuctioneer,
    ZkTlsBlindApiAttestor,
)


def test_decide_v5_five_stage_engine_and_falsify_mode() -> None:
    engine = DecideV5EvidenceEngine()

    claims = [
        TypedEvidenceClaim(
            claim_id="claim-mcp-001",
            source_type="OFFICIAL_SPEC",
            source_uri="https://modelcontextprotocol.io/specification/2025-11-25",
            source_digest="sha256:1111",
            claim_statement="MCP tool descriptions must be treated as untrusted unless pinned.",
            applies_to="AEIB MCP boundary",
            evidence_tier="T2_VALIDATED_PRIMARY_SOURCE",
            independent_sources_count=3,
            verified=True,
        ),
        TypedEvidenceClaim(
            claim_id="claim-limbo-002",
            source_type="REPRODUCED_HARNESS",
            source_uri="https://arxiv.org/abs/2609.29095",
            source_digest="sha256:2222",
            claim_statement="Visibility-lag fence eliminates duplicate writes under replica lag.",
            applies_to="AEIB Station 2",
            evidence_tier="T4_FORMAL_OR_EXECUTABLE_ORACLE",
            independent_sources_count=2,
            verified=True,
        ),
        TypedEvidenceClaim(
            claim_id="claim-ruletrek-003",
            source_type="ARXIV_PAPER",
            source_uri="https://arxiv.org/abs/2610.19698",
            source_digest="sha256:3333",
            claim_statement="RuleTrek AST dependency graph prevents multi-file rule omissions.",
            applies_to="Decide v5 Engine",
            evidence_tier="T3_REPRODUCED_COUNTEREXAMPLE",
            independent_sources_count=2,
            verified=True,
        ),
    ]

    # 1. Test `--deep` mode with surviving disproof vector -> VALIDATED_RECOMMENDATION
    surviving_vec = FalsificationVector(
        vector_id="fv-phase0-001",
        target_claim="Phase 0 closure is required before Rust FFI expansion",
        counterargument="FFI bridge could be isolated behind byte interface",
        executable_test_name="test_phase0_integrity_reset_all_blockers",
        expected_outcome="PASS",
        observed_outcome="PASS",
        survived_disproof=True,
    )
    res_deep = engine.execute_decide(
        query="What is the highest-leverage next step for AEIB?",
        mode="--deep",
        claims=claims,
        falsification_vectors=[surviving_vec],
    )
    env_deep = res_deep["envelope"]
    assert env_deep["verdict"] == "VALIDATED_RECOMMENDATION"
    assert env_deep["confidence_grade"] == "HIGH"
    assert res_deep["caid"].startswith("sha256:")

    # 2. Test `--falsify` mode when a falsification vector fails -> CONDITIONAL_NO
    failing_pqc_vec = FalsificationVector(
        vector_id="pqc-001",
        target_claim="Enable unverified ML-DSA stub in production",
        counterargument="ML-DSA verification must use a real FIPS 204 implementation",
        executable_test_name="test_pqc_random_bytes_rejected",
        expected_outcome="VERIFY_FALSE",
        observed_outcome="UNIMPLEMENTED_NATIVE_DEPENDENCY",
        survived_disproof=False,
    )
    res_falsify = engine.execute_decide(
        query="Should AEIB enable unpinned PQC signatures without FIPS 204 vector checks?",
        mode="--falsify",
        claims=claims,
        falsification_vectors=[failing_pqc_vec],
    )
    env_falsify = res_falsify["envelope"]
    assert env_falsify["verdict"] == "CONDITIONAL_NO"
    assert "pqc-001" in env_falsify["decision"]["blocked_by"]


def test_vector1_zktls_blind_api_attestation_zero_pii_leakage() -> None:
    notary_priv = Ed25519PrivateKey.generate()
    attestor = ZkTlsBlindApiAttestor(notary_priv)

    raw_bank_api_response = {
        "account_holder_name": "Alice Mustermann",
        "iban": "DE89370400440532013000",
        "balance_minor": 25000_00,
        "status": "approved",
    }
    attestation = attestor.create_blind_api_attestation(
        operation_id="op-zktls-01",
        api_domain="api.treasury-bank.example",
        raw_api_response=raw_bank_api_response,
        required_min_balance_minor=10000_00,
        blinding_salt_hex="aabbccddeeff00112233445566778899",
    )

    assert ZkTlsBlindApiAttestor.verify_blind_attestation(
        attestation, notary_priv.public_key()
    )
    serialized = json.dumps(attestation)
    # Exact balance (2500000) and PII (Alice Mustermann, IBAN) never appear in the receipt
    assert "2500000" not in serialized
    assert "Alice Mustermann" not in serialized
    assert "DE89370400440532013000" not in serialized


def test_vector2_shannon_channel_capacity_steganography_gate() -> None:
    # Normal business memo passes cleanly
    disp_ok, code_ok = ShannonChannelCapacityGate.evaluate_outbound_arguments(
        "Order confirmation for invoice #1042 settled via SEPA."
    )
    assert disp_ok == "DISPATCHED" and code_ok == "OK"

    # Covert alternating-case steganography payload is halted
    stego_payload = "aBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgHiJkLmNoPqRsTuVwXyZ"
    disp_stego, code_stego = ShannonChannelCapacityGate.evaluate_outbound_arguments(
        stego_payload
    )
    assert disp_stego == "NOT_DISPATCHED"
    assert code_stego == "HALT_SHANNON_STEGANOGRAPHY_ENTROPY_ANOMALY"


def test_vector3_thermodynamic_joule_escrow_gate() -> None:
    joule_gate = ThermodynamicJouleEscrowGate(epoch_joule_limit_mj=10_000)

    disp1, code1, rem1 = joule_gate.reserve_and_account_joules(
        "sha256:act1", estimated_tokens=1500, mj_per_token=4
    )
    assert disp1 == "DISPATCHED" and code1 == "OK" and rem1 == 4_000

    # Runaway loop requesting 2,000 tokens (8,000 mJ > 4,000 mJ remaining) triggers SIGSTOP
    disp2, code2, rem2 = joule_gate.reserve_and_account_joules(
        "sha256:act2", estimated_tokens=2000, mj_per_token=4
    )
    assert disp2 == "SIGSTOP_THROTTLED"
    assert code2 == "HALT_THERMODYNAMIC_JOULE_BUDGET_EXHAUSTED_SIGSTOP"
    assert rem2 == 4_000


def test_vector4_vcg_truthful_budget_auctioneer() -> None:
    # Shared sprint budget is 1000_00 (€1,000)
    bids = [
        SubagentBid("agent-alpha", requested_budget_minor=600_00, reported_valuation_minor=900_00),
        SubagentBid("agent-beta", requested_budget_minor=400_00, reported_valuation_minor=700_00),
        SubagentBid("agent-gamma", requested_budget_minor=900_00, reported_valuation_minor=1100_00),
    ]
    outcome = VcgTruthfulBudgetAuctioneer.allocate_sprint_budget(
        bids, capacity_minor=1000_00
    )
    # Alpha (600) + Beta (400) = 1000 cost with 900 + 700 = 1600 social welfare (> Gamma's 1100)
    assert set(outcome.winning_agents) == {"agent-alpha", "agent-beta"}
    assert outcome.total_social_welfare_minor == 1600_00
    # Without Alpha, best is Gamma (1100); others with Alpha get 700 (Beta) -> Alpha pays 1100 - 700 = 400_00
    assert outcome.vcg_externality_payments_minor["agent-alpha"] == 400_00
    # Without Beta, best is Gamma (1100); others with Beta get 900 (Alpha) -> Beta pays 1100 - 900 = 200_00
    assert outcome.vcg_externality_payments_minor["agent-beta"] == 200_00


def test_vector5_antigen_gossip_defense_mesh() -> None:
    priv_a = Ed25519PrivateKey.generate()
    priv_b = Ed25519PrivateKey.generate()
    priv_c = Ed25519PrivateKey.generate()

    mesh = AntigenGossipDefenseMesh(
        {
            "node-eu-1": priv_a.public_key(),
            "node-us-1": priv_b.public_key(),
            "node-ap-1": priv_c.public_key(),
        }
    )

    antigen = AntigenGossipDefenseMesh.emit_signed_antigen(
        origin_node_id="node-eu-1",
        node_priv=priv_a,
        exploit_pattern_digest="sha256:poisoned_mcp_descriptor_99",
        cve_or_vector_tag="AT63B_PROSE_RUG_PULL",
    )
    updated = mesh.gossip_antigen_to_cluster(antigen)
    assert updated == 3

    # Node in AP region immediately blocks the poisoned descriptor without central restart
    disp, code = mesh.evaluate_node_action(
        "node-ap-1", "sha256:poisoned_mcp_descriptor_99"
    )
    assert disp == "NOT_DISPATCHED"
    assert code == "HALT_GOSSIP_ANTIGEN_CLUSTER_BLOCK"


def test_banned_words_absence_in_v5_files() -> None:
    from pathlib import Path

    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "unhack" + "able",
        "immun" + "e",
        "proven " + "universally",
    ]
    for path in (
        "tools/ruletrek_cross_model_decide_engine.py",
        "tests/test_limbo_proposition_1_fence.py",
        "src/decide_v5_recursive_evidence_engine.py",
        "tests/test_decide_v5_recursive_evidence_engine.py",
    ):
        if not Path(path).exists():
            continue
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read().lower()
            for w in banned:
                assert w not in text, f"Banned word '{w}' found in {path}"


def test_section17_ruletrek_and_decide_v5_mutation_boundaries() -> None:
    import ast as _ast
    import base64
    import sys as _sys
    from pathlib import Path
    import pytest

    import src.decide_v5_recursive_evidence_engine as dv5
    import tools.ruletrek_cross_model_decide_engine as rt

    # 1. RuleTrek Cross-Model Decide Engine boundaries & trace
    assert rt.RuleNode.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert rt.ModelBrainstormProposal.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert rt.RuleTrekSynthesisResult.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert rt.canonical_jcs_bytes({"a": 1}) == b'{"a":1}'
    assert rt.sha256_prefixed(b"abc").startswith("sha256:")
    with pytest.raises(ValueError, match="ERR_FLOAT_FORBIDDEN_IN_JCS"):
        rt.canonical_jcs_bytes({"bad": 1.5})
    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
        rt.canonical_jcs_bytes({1: "bad"})  # type: ignore[dict-item]

    rt_tree = _ast.parse(Path(rt.__file__).read_text(encoding="utf-8"))
    rt_last = rt_tree.body[-1]
    assert isinstance(rt_last, _ast.If) and isinstance(rt_last.test, _ast.Compare)
    assert isinstance(rt_last.test.ops[0], _ast.Eq)

    assert rt.RuleTrekDependencyGraphExtractor.extract_graph_for_domain("other") == {}
    rules = rt.RuleTrekDependencyGraphExtractor.extract_graph_for_domain("database_rls_and_treasury")
    assert rules["R1_TENANT_ISOLATION"].depth == 0
    assert rules["R2_TCC_ESCROW"].depth == 1
    assert rules["R3_VISIBILITY_FENCE"].depth == 2

    seen_rt: dict[str, object] = {}

    def _trace_rt(frame: object, event: str, arg: object) -> object:
        f_code = getattr(frame, "f_code", None)
        if f_code is not None and f_code.co_name == "test_ruletrek_cross_model_decide_engine" and event == "return":
            f_locals = getattr(frame, "f_locals", {})
            if "proposals" in f_locals and "bad_proposals" in f_locals:
                seen_rt["p0_ver"] = f_locals["proposals"][0].has_verifiable_counterexample_or_url
                seen_rt["p2_ver"] = f_locals["proposals"][2].has_verifiable_counterexample_or_url
                seen_rt["bad_ver"] = f_locals["bad_proposals"][0].has_verifiable_counterexample_or_url
        return _trace_rt

    _sys.settrace(_trace_rt)
    try:
        rt.test_ruletrek_cross_model_decide_engine()
    finally:
        _sys.settrace(None)
    assert seen_rt["p0_ver"] is False
    assert seen_rt["p2_ver"] is False
    assert seen_rt["bad_ver"] is False

    # Minority verified proposal (conf=0.90) must defeat unverified full-rule proposal (conf=0.99)
    all_rules = ("R1_TENANT_ISOLATION", "R2_TCC_ESCROW", "R3_VISIBILITY_FENCE")
    p_unver_high = rt.ModelBrainstormProposal(
        "m-unver", "US", "Arch", "Unverified", all_rules, False, "none", 0.99
    )
    p_ver_low = rt.ModelBrainstormProposal(
        "m-ver", "CN", "Sec", "Verified", all_rules, True, "https://example.org/proof", 0.90
    )
    signer = Ed25519PrivateKey.generate()
    res_min = rt.RuleTrekCrossModelAdjudicator.adjudicate_and_synthesize(
        "q-min", rules, [p_unver_high, p_ver_low], signer=signer
    )
    assert "m-ver" in res_min.synthesized_architecture
    core_receipt = {
        "query": "q-min",
        "winner": "m-ver",
        "rules_satisfied": list(all_rules),
        "rule_compliance_verified": True,
    }
    signer.public_key().verify(base64.b64decode(res_min.signature_b64), rt.canonical_jcs_bytes(core_receipt))

    # 2. Decide v5 Recursive Evidence Engine boundaries
    assert dv5.EVIDENCE_TIER_RANKS == {
        "T0_MODEL_ASSERTION": 0,
        "T1_CITATION": 1,
        "T2_VALIDATED_PRIMARY_SOURCE": 2,
        "T3_REPRODUCED_COUNTEREXAMPLE": 3,
        "T4_FORMAL_OR_EXECUTABLE_ORACLE": 4,
    }
    assert dv5.encode_jcs({"k": 1}) == b'{"k":1}'

    ledger = dv5.DossierResearchLedger()
    assert ledger.evaluate_quality_gate()["confidence_grade"] == "LOW"
    with pytest.raises(ValueError, match="Unknown evidence tier"):
        ledger.record_claim(
            TypedEvidenceClaim("c0", "S", "u", "d", "stmt", "target-A", "T99_BAD", 1, True)
        )
    c_a1 = TypedEvidenceClaim("c1", "S", "u", "d", "stmt1", "target-A", "T3_REPRODUCED_COUNTEREXAMPLE", 2, True)
    c_a2 = TypedEvidenceClaim("c2", "S", "u", "d", "stmt2", "target-A", "T3_REPRODUCED_COUNTEREXAMPLE", 2, True)
    ledger.record_claim(c_a1)
    assert ledger.evaluate_quality_gate()["confidence_grade"] == "MEDIUM"
    ledger.record_claim(c_a2)
    assert len(ledger.contradictions) == 0
    c_a3_false = TypedEvidenceClaim("c3", "S", "u", "d", "stmt3", "target-A", "T3_REPRODUCED_COUNTEREXAMPLE", 2, False)
    ledger.record_claim(c_a3_false)
    assert len(ledger.contradictions) == 2
    c_b_false = TypedEvidenceClaim("cb", "S", "u", "d", "stmtb", "target-B", "T3_REPRODUCED_COUNTEREXAMPLE", 2, False)
    ledger.record_claim(c_b_false)
    assert len(ledger.contradictions) == 2

    eng_custom = DecideV5EvidenceEngine(signer=signer)
    with pytest.raises(ValueError, match="Unsupported /decide mode"):
        eng_custom.execute_decide("q", mode="--bad-mode")
    res_none = eng_custom.execute_decide("q-none", mode="default", claims=None)
    assert res_none["envelope"]["verdict"] == "CONDITIONAL_RECOMMENDATION"
    signer.public_key().verify(
        base64.b64decode(res_none["signature_b64"]), dv5.encode_jcs(res_none["envelope"])
    )

    vec_ok = FalsificationVector("v1", "tc", "ca", "test_ok", "PASS", "PASS", True)
    vec_fail = FalsificationVector("v2", "tc", "ca", "test_fail", "PASS", "FAIL", False)
    res_falsify_fail = eng_custom.execute_decide("q-ff", mode="--falsify", claims=[c_a1], falsification_vectors=[vec_fail])
    assert res_falsify_fail["envelope"]["verdict"] == "CONDITIONAL_NO"
    assert res_falsify_fail["envelope"]["confidence_bps"] == 92 * 100
    res_falsify_pass = eng_custom.execute_decide("q-fp", mode="--falsify", claims=[c_a1], falsification_vectors=[vec_ok])
    assert res_falsify_pass["envelope"]["verdict"] == "VALIDATED_RECOMMENDATION"
    c_unver_t4 = TypedEvidenceClaim("c4", "S", "u", "d", "stmt", "target-B", "T4_FORMAL_OR_EXECUTABLE_ORACLE", 2, False)
    res_unver = eng_custom.execute_decide("q-unver", mode="--deep", claims=[c_unver_t4], falsification_vectors=[vec_ok])
    assert res_unver["envelope"]["verdict"] == "CONDITIONAL_RECOMMENDATION"

    # Vector 1 negative verification returns exact bool False
    att = ZkTlsBlindApiAttestor(signer).create_blind_api_attestation(
        "op1", "d.example", {"balance_minor": 500, "status": "approved"}, 100, "salt"
    )
    assert ZkTlsBlindApiAttestor.verify_blind_attestation(
        {"blind_statement": {**att["blind_statement"], "status_verified": "rejected"}, "notary_signature_b64": att["notary_signature_b64"], "statement_caid": att["statement_caid"]},
        signer.public_key(),
    ) is False
    assert ZkTlsBlindApiAttestor.verify_blind_attestation(
        {**att, "notary_signature_b64": "AAAA"},
        signer.public_key(),
    ) is False

    # Vector 2 Shannon entropy & casing transition exact boundaries
    assert ShannonChannelCapacityGate.compute_shannon_entropy_bits_per_byte("") == 0.0
    assert ShannonChannelCapacityGate.compute_shannon_entropy_bits_per_byte("ab") == 1.0
    assert ShannonChannelCapacityGate.evaluate_outbound_arguments("AAbb") == ("DISPATCHED", "OK")
    assert ShannonChannelCapacityGate.evaluate_outbound_arguments(
        "aB", max_entropy_bits_per_byte=10.0, max_casing_transitions_ratio=0.75
    ) == ("NOT_DISPATCHED", "HALT_SHANNON_STEGANOGRAPHY_ENTROPY_ANOMALY")
    assert ShannonChannelCapacityGate.evaluate_outbound_arguments(
        "aB", max_entropy_bits_per_byte=10.0, max_casing_transitions_ratio=1.0
    ) == ("DISPATCHED", "OK")
    assert ShannonChannelCapacityGate.evaluate_outbound_arguments(
        "ab", max_entropy_bits_per_byte=1.0, max_casing_transitions_ratio=0.5
    ) == ("DISPATCHED", "OK")
    assert ShannonChannelCapacityGate.evaluate_outbound_arguments(
        "ab", max_entropy_bits_per_byte=0.9, max_casing_transitions_ratio=0.5
    ) == ("NOT_DISPATCHED", "HALT_SHANNON_STEGANOGRAPHY_ENTROPY_ANOMALY")

    # Vector 4 VCG zero-externality boundary
    vcg_solo = VcgTruthfulBudgetAuctioneer.allocate_sprint_budget(
        [SubagentBid("solo", 100, 500)], capacity_minor=1000
    )
    assert vcg_solo.vcg_externality_payments_minor["solo"] == 0
