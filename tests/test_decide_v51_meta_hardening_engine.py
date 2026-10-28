#!/usr/bin/env python3
# File: tests/test_decide_v51_meta_hardening_engine.py
"""
Verification & Falsification Suite (`--falsify`) for `/decide` v5.1 Meta-Hardening Engine
(`src/decide_v51_meta_hardening_engine.py`).

Tests:
1. Multi-Flag Join-Semilattice Composition across simultaneous flags:
   `--research --deep --compliance --security --falsify --benchmark`.
2. `T4+` Mutation-Killed Oracle Verifier (`MLReproMutate` & `The Verification Horizon`, 2026):
   - Vacuous `T4` oracle that forgets to check `sig_valid` allows `M2_FORGED_SIG` to survive
     (`kill_rate_bps = 5000 < 10000`) -> rejected with `HOLD_VACUOUS_T4_ORACLE_SURVIVING_MUTANTS`.
   - Complete `T4+` oracle kills 100% of mutants (`10000 bps`).
3. `POIROT` & `Marco DeepResearch` Citation Echo-Chamber Deduplication:
   - Two secondary URLs sharing the same `root_origin_caid` are collapsed to 1 independent source.
4. `CAVEAT` Correlated Pre-Training Error Discounting:
   - High correlation (`rho_corr_bps >= 3000`) without a non-LLM orthogonal witness halts with
     `HALT_CAVEAT_CORRELATED_BLINDSPOT_NEEDS_ORTHOGONAL_WITNESS`.
5. Non-Stationary Epistemic Half-Life (`half_life_hours`):
   - Expired supply-chain/CVE evidence halts with `HALT_STALE_EVIDENCE_HALF_LIFE_EXPIRED`.
"""

from __future__ import annotations

from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.decide_v51_meta_hardening_engine import (
    CaveatAndPoirotMetaAuditor,
    DecideV51MetaHardeningEngine,
    MultiFlagLatticeComposer,
    MutantCase,
    MutationKilledOracleVerifier,
    ProvenanceEvidenceItem,
)


def test_six_flag_join_semilattice_composition() -> None:
    flags = [
        "--research",
        "--deep",
        "--compliance",
        "--security",
        "--falsify",
        "--benchmark",
    ]
    plan = MultiFlagLatticeComposer.compose(flags)
    assert len(plan.active_flags) == 6
    assert len(plan.required_obligations) == 12
    assert "REQ_T4_PLUS_MUTATION_KILL_10000_BPS" in plan.required_obligations
    assert "REQ_POIROT_ORIGIN_DEDUP" in plan.required_obligations
    assert "REQ_CAVEAT_CORRELATION_AUDIT" in plan.required_obligations


def test_falsify_vacuous_t4_oracle_rejected_by_mutation_verifier() -> None:
    priv = Ed25519PrivateKey.generate()
    engine = DecideV51MetaHardeningEngine(priv)

    nominal = {"spend_minor": 1000, "ceiling_minor": 5000, "sig_valid": True}
    mutants = [
        MutantCase(
            "M1_OVER_CEILING",
            "Spend exceeds ceiling",
            {"spend_minor": 6000, "ceiling_minor": 5000, "sig_valid": True},
        ),
        MutantCase(
            "M2_FORGED_SIG",
            "Forged signature",
            {"spend_minor": 1000, "ceiling_minor": 5000, "sig_valid": False},
        ),
    ]

    # Vacuous oracle checks spend <= ceiling but forgets to verify sig_valid!
    vacuous_report = MutationKilledOracleVerifier.evaluate_oracle(
        "oracle-vacuous",
        lambda s: int(s["spend_minor"]) <= int(s["ceiling_minor"]),
        nominal,
        mutants,
    )
    assert vacuous_report.qualifies_as_t4_plus is False
    assert int(vacuous_report.kill_rate_bps) == 5000
    assert vacuous_report.surviving_mutant_ids == ("M2_FORGED_SIG",)

    items = [
        ProvenanceEvidenceItem(
            "ev-1", "c-1", "https://arxiv.org/abs/2610.14224", "sha256:o1", "T2", False, 5, 168
        ),
        ProvenanceEvidenceItem(
            "ev-2", "c-1", "file:///src/decide.py", "sha256:o2", "T4", True, 1, 0
        ),
    ]
    verdict = engine.execute_meta_decide(
        query="Test vacuous oracle rejection",
        flags=("--falsify", "--security"),
        claim_id="c-1",
        evidence_items=items,
        mutation_report=vacuous_report,
        model_count=4,
        rho_corr_bps=2000,
    )
    assert verdict.final_disposition == "HOLD_VACUOUS_T4_ORACLE_SURVIVING_MUTANTS"
    assert verdict.independent_origins_count == 0
    assert verdict.echo_duplicates_collapsed == 0
    assert verdict.effective_models_bps == 0


def test_poirot_citation_echo_chamber_and_caveat_correlated_blindspot() -> None:
    # 1. Three URLs that all copy the same upstream root_origin_caid collapse to 1 source
    echo_items = [
        ProvenanceEvidenceItem("e1", "c-echo", "https://arxiv.org/abs/2609.29095", "sha256:limbo-root", "T2", False, 10, 168),
        ProvenanceEvidenceItem("e2", "c-echo", "https://mirror1.example/limbo", "sha256:limbo-root", "T1", False, 8, 168),
        ProvenanceEvidenceItem("e3", "c-echo", "https://mirror2.example/limbo", "sha256:limbo-root", "T1", False, 4, 168),
    ]
    res_echo = CaveatAndPoirotMetaAuditor.audit_claim_evidence(
        claim_id="c-echo",
        items=echo_items,
        model_count=3,
        rho_corr_bps=1000,
    )
    assert res_echo["status"] == "HOLD_POIROT_INSUFFICIENT_INDEPENDENT_ORIGINS"
    assert res_echo["independent_origins_count"] == 1
    assert res_echo["echo_duplicates_collapsed"] == 2

    # 2. High pre-training correlation (rho_corr_bps = 4500) without non-LLM orthogonal witness halts
    corr_items = [
        ProvenanceEvidenceItem("e1", "c-corr", "https://arxiv.org/abs/2609.29095", "sha256:r1", "T2", False, 10, 168),
        ProvenanceEvidenceItem("e2", "c-corr", "https://arxiv.org/abs/2610.14224", "sha256:r2", "T2", False, 10, 168),
    ]
    res_corr = CaveatAndPoirotMetaAuditor.audit_claim_evidence(
        claim_id="c-corr",
        items=corr_items,
        model_count=4,
        rho_corr_bps=4500,
    )
    assert res_corr["status"] == "HALT_CAVEAT_CORRELATED_BLINDSPOT_NEEDS_ORTHOGONAL_WITNESS"

    # 3. Expired half-life security evidence halts (including half_life_hours=1 boundary)
    stale_items = [
        ProvenanceEvidenceItem("e-stale", "c-stale", "https://pypi.org/p/litellm", "sha256:r1", "T2", True, 2, 1),
    ]
    res_stale = CaveatAndPoirotMetaAuditor.audit_claim_evidence(
        claim_id="c-stale",
        items=stale_items,
        model_count=4,
        rho_corr_bps=1000,
    )
    assert res_stale["status"] == "HALT_STALE_EVIDENCE_HALF_LIFE_EXPIRED"

    # 4. Effective model count boundaries, frozen immutability, JCS flags, and run_self_test
    import dataclasses
    import json as _json
    import pytest
    from src.decide_v51_meta_hardening_engine import canonical_jcs_bytes, run_self_test

    with pytest.raises(dataclasses.FrozenInstanceError):
        stale_items[0].age_hours = 99  # type: ignore

    # canonical_jcs_bytes delegates to the RFC 8785 reference encoder; the former
    # json.dumps flag spy pinned the old local implementation. Assert behaviour.
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs

    assert canonical_jcs_bytes({"u": "α"}) == '{"u":"α"}'.encode("utf-8")
    probe = {"\U0001F600": 1, "\uffff": [2**64]}
    assert canonical_jcs_bytes(probe) == _reference_encode_jcs(probe)
    assert canonical_jcs_bytes(probe) == '{"\U0001F600":1,"\uffff":[18446744073709551616]}'.encode("utf-8")
    with pytest.raises(ValueError):
        canonical_jcs_bytes({"x": 0.5})

    zero_eff = CaveatAndPoirotMetaAuditor.compute_effective_model_count_bps(0, 1000)
    assert zero_eff is not None and zero_eff == 0
    assert CaveatAndPoirotMetaAuditor.compute_effective_model_count_bps(1, 0) == 100 * 100
    assert CaveatAndPoirotMetaAuditor.compute_effective_model_count_bps(4, 2000) == 250 * 100
    with pytest.raises(ValueError, match="ERR_INVALID_RHO_CORR_BPS"):
        CaveatAndPoirotMetaAuditor.compute_effective_model_count_bps(2, -1)
    with pytest.raises(ValueError, match="ERR_INVALID_RHO_CORR_BPS"):
        CaveatAndPoirotMetaAuditor.compute_effective_model_count_bps(2, 10001)

    orig_eval = MutationKilledOracleVerifier.evaluate_oracle
    orig_exec = DecideV51MetaHardeningEngine.execute_meta_decide

    def _checked_eval(oracle_id, oracle_fn, nominal_state, mutants):  # type: ignore[no-untyped-def]
        assert mutants[0].mutated_state["spend_minor"] == 60 * 100
        assert mutants[1].mutated_state["ceiling_minor"] == 50 * 100
        assert mutants[1].mutated_state["sig_valid"] is False
        return orig_eval(oracle_id, oracle_fn, nominal_state, mutants)

    def _checked_exec(self, **kw):  # type: ignore[no-untyped-def]
        ev = kw["evidence_items"]
        assert ev[0].half_life_hours == 7 * 24
        assert ev[1].age_hours == 6
        assert ev[2].half_life_hours == 0
        assert kw["rho_corr_bps"] == 40 * 100
        return orig_exec(self, **kw)

    MutationKilledOracleVerifier.evaluate_oracle = staticmethod(_checked_eval)  # type: ignore[assignment]
    DecideV51MetaHardeningEngine.execute_meta_decide = _checked_exec  # type: ignore[assignment]
    try:
        run_self_test()
    finally:
        MutationKilledOracleVerifier.evaluate_oracle = staticmethod(orig_eval)  # type: ignore[assignment]
        DecideV51MetaHardeningEngine.execute_meta_decide = orig_exec  # type: ignore[assignment]


def test_zero_banned_words_in_v51_files() -> None:
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
        "production-" + "ready",
        "bank-" + "grade",
    ]
    for fpath in (
        "src/decide_v51_meta_hardening_engine.py",
        "tests/test_decide_v51_meta_hardening_engine.py",
    ):
        text = Path(fpath).read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in text, f"Banned word '{word}' found in {fpath}"
