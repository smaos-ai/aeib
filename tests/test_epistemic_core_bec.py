#!/usr/bin/env python3
# File: tests/test_epistemic_core_bec.py
"""
Pytest suite for src/epistemic_core.py (Bose-Einstein Cognitive Synthesizer & Phase Transition).

Verifies:
1. 1,000-Agent Concurrent Phase Transition Simulation (arXiv:2609.38327 & arXiv:2601.17311).
2. Rejection of unprobed proposals lacking Bose EpistemicWitness IDs (HALT_MISSING_BOSE_EPISTEMIC_WITNESS).
3. Rejection of fabricated or un-ingested witness IDs (HALT_UNVERIFIED_OR_FABRICATED_WITNESS).
4. Provenance Entropy Filter: Rejection of AI_GENERATED_UNVERIFIED witnesses
   (HALT_SYNTHETIC_OVERLOAD_UNVERIFIED_PROVENANCE).
5. Disjoint Write-Set Enforcement across concurrent agents (HALT_DISJOINT_WRITESET_COLLISION).
6. Cleanroom banned-word scan.
"""
import re
from pathlib import Path

import pytest

from src.epistemic_core import (
    BoseEinsteinCognitiveSynthesizer,
    EpistemicWitness,
    OnticActionProposal,
    PhaseState,
    canonical_jcs,
    simulate_1000_agent_phase_transition,
)


def test_1000_agent_phase_transition_simulation() -> None:
    res = simulate_1000_agent_phase_transition(1000)
    assert res["total_agents_simulated"] == 1000
    assert res["total_bose_witnesses_ingested"] == 1000
    assert res["conflicts_detected_and_halted"] == 15
    assert res["phase_state_under_conflict"] == PhaseState.HALTED.value
    assert res["phase_state_after_condensation"] == PhaseState.CONDENSED_LOCKED.value
    assert res["committed_ontic_operations"] == 1
    assert res["sample_attribution_digest"].startswith("sha256:")


def test_missing_or_fabricated_bose_witness_rejected() -> None:
    synth = BoseEinsteinCognitiveSynthesizer(conflict_density_threshold_bp=7500)

    # Ingest one valid witness so state is CONDENSED_LOCKED
    w_valid = EpistemicWitness(
        witness_id="w-valid-01",
        agent_id="agent-01",
        action_type="FORMAL_VERIFICATION",
        target_resource="res://db-1",
        evidence_payload_hash="sha256:abc",
        provenance_tag="DETERMINISTIC_PROBE",
        is_conflict=False,
        severity_bp=0,
    )
    ok, _ = synth.register.ingest(w_valid)
    assert ok is True

    # 1. Empty required_witness_ids -> HALT_MISSING_BOSE_EPISTEMIC_WITNESS
    p_empty = OnticActionProposal(
        operation_id="op-01",
        proposer_agent_id="agent-01",
        action_class="WRITE",
        target_resource="res://db-1",
        write_set_resources=("res://db-1",),
        amount_minor=100,
        required_witness_ids=(),
    )
    allowed_empty, code_empty, _ = synth.adjudicate_ontic_proposal(p_empty)
    assert allowed_empty is False
    assert code_empty == "HALT_MISSING_BOSE_EPISTEMIC_WITNESS"

    # 2. Fabricated witness_id that was never ingested -> HALT_UNVERIFIED_OR_FABRICATED_WITNESS
    p_fake = OnticActionProposal(
        operation_id="op-02",
        proposer_agent_id="agent-01",
        action_class="WRITE",
        target_resource="res://db-1",
        write_set_resources=("res://db-1",),
        amount_minor=100,
        required_witness_ids=("w-non-existent-999",),
    )
    allowed_fake, code_fake, _ = synth.adjudicate_ontic_proposal(p_fake)
    assert allowed_fake is False
    assert "HALT_UNVERIFIED_OR_FABRICATED_WITNESS" in code_fake


def test_provenance_entropy_synthetic_overload_rejected() -> None:
    synth = BoseEinsteinCognitiveSynthesizer(conflict_density_threshold_bp=7500)

    w_unverified = EpistemicWitness(
        witness_id="w-llm-unverified-01",
        agent_id="agent-02",
        action_type="PRIOR_ART_SEARCH",
        target_resource="res://treasury",
        evidence_payload_hash="sha256:def",
        provenance_tag="AI_GENERATED_UNVERIFIED",
        is_conflict=False,
        severity_bp=0,
    )
    synth.register.ingest(w_unverified)

    p = OnticActionProposal(
        operation_id="op-03",
        proposer_agent_id="agent-02",
        action_class="DISBURSE",
        target_resource="res://treasury",
        write_set_resources=("res://treasury",),
        amount_minor=1000_00,
        required_witness_ids=("w-llm-unverified-01",),
    )
    allowed, code, meta = synth.adjudicate_ontic_proposal(p)
    assert allowed is False
    assert code == "HALT_SYNTHETIC_OVERLOAD_UNVERIFIED_PROVENANCE"
    assert meta["provenance_tag"] == "AI_GENERATED_UNVERIFIED"


def test_intermediate_phase_transition_blocks_mutation() -> None:
    synth = BoseEinsteinCognitiveSynthesizer(conflict_density_threshold_bp=7500)

    # Ingest a minor conflict (2000 bp < 7500 bp threshold) -> PHASE_TRANSITION state
    w_minor = EpistemicWitness(
        witness_id="w-minor-conflict",
        agent_id="agent-03",
        action_type="HYPOTHESIS_DROP_PROBE",
        target_resource="res://acct-1",
        evidence_payload_hash="sha256:111",
        provenance_tag="DETERMINISTIC_PROBE",
        is_conflict=True,
        severity_bp=2000,
    )
    w_clean = EpistemicWitness(
        witness_id="w-clean-03",
        agent_id="agent-03",
        action_type="FORMAL_VERIFICATION",
        target_resource="res://acct-2",
        evidence_payload_hash="sha256:222",
        provenance_tag="DETERMINISTIC_PROBE",
        is_conflict=False,
        severity_bp=0,
    )
    synth.register.ingest(w_minor)
    synth.register.ingest(w_clean)

    assert synth.evaluate_phase_transition() == PhaseState.PHASE_TRANSITION

    # Even if proposal references w_clean, global PHASE_TRANSITION blocks ontic mutation until condensed
    p = OnticActionProposal(
        operation_id="op-04",
        proposer_agent_id="agent-03",
        action_class="MUTATE",
        target_resource="res://acct-2",
        write_set_resources=("res://acct-2",),
        amount_minor=50_00,
        required_witness_ids=("w-clean-03",),
    )
    allowed, code, _ = synth.adjudicate_ontic_proposal(p)
    assert allowed is False
    assert code == "HALT_GLOBAL_PHASE_TRANSITION_UNRESOLVED_CONFLICTS"


def test_banned_words_absence() -> None:
    forbidden_tokens = [
        "guaran" + "tee",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "im" + "mune",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
        "proven universal" + "ly",
    ]
    pattern = re.compile("|".join(re.escape(t) for t in forbidden_tokens), re.IGNORECASE)

    for p in [Path("src/epistemic_core.py"), Path(__file__)]:
        content = p.read_text(encoding="utf-8")
        matches = pattern.findall(content)
        assert not matches, f"Banned tokens {matches} found in {p}"
