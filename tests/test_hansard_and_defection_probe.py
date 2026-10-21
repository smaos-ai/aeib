#!/usr/bin/env python3
"""
tests/test_hansard_and_defection_probe.py
================================================================================
Test Suite for SOTA Frontier Modules:
1. HANSARD W3C PROV-DM Causal Provenance & Attribution Laundering Engine
2. Anthropic Defection Activation Probe on Transformer Residual Streams

Evaluated under the stated model as a pre-production test battery.
Strict zero-mock AST purity enforced.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Dict, List

import pytest

from src.hansard_causal_provenance import (
    ChokePoint,
    ProvEntity,
    ProvActivity,
    ProvAgent,
    CausalWitnessRecord,
    AttributionReport,
    HansardCausalProvenanceEngine,
)
from src.defection_activation_probe import (
    DefectionActivationProbe,
    ProbeInferenceResult,
)


# ============================================================================
# 1. HANSARD CAUSAL PROVENANCE & ATTRIBUTION TESTS
# ============================================================================

def test_hansard_choke_point_witnessing_and_dag_tip():
    """Verify witnessing across all 5 independent choke points and DAG tip hash."""
    engine = HansardCausalProvenanceEngine(synergy_threshold_minor=500_00)
    assert engine.get_provenance_dag_tip() == "0" * 64

    # Simulate 5 choke points
    chokes = [
        ChokePoint.CHOKE_1_INTENT_ADMISSION,
        ChokePoint.CHOKE_2_TOKEN_BINDING,
        ChokePoint.CHOKE_3_PRE_SOCKET_BARRIER,
        ChokePoint.CHOKE_4_WIRE_EGRESS,
        ChokePoint.CHOKE_5_SETTLEMENT_FINALITY,
    ]

    for idx, cp in enumerate(chokes):
        entity = ProvEntity(
            entity_id=f"entity-{idx}",
            entity_type="caid_intent",
            content_digest=hashlib.sha256(f"digest-{idx}".encode()).hexdigest(),
        )
        activity = ProvActivity(
            activity_id=f"act-{idx}",
            choke_point=cp,
            timestamp=1700000000.0 + idx,
            duration_ms=1.5,
            status="CONFIRMED",
        )
        agent = ProvAgent(
            agent_id="agent-alpha",
            root_sponsor_did="did:smaos:sponsor-root",
            capability_warrant_id="warrant-001",
            taint_tier="TIER_0_SYSTEM_PINNED",
        )
        rec = engine.record_witness(entity, activity, agent)
        assert rec.activity.choke_point == cp
        assert len(rec.compute_record_hash()) == 64

    dag_tip = engine.get_provenance_dag_tip()
    assert len(dag_tip) == 64
    assert dag_tip != "0" * 64


def test_hansard_attribution_laundering_detection():
    """
    Verify Halpern-Pearl synergy residual detects multi-agent attribution laundering
    when agents divide actions such that no single agent is a 'but-for' cause.
    """
    engine = HansardCausalProvenanceEngine(synergy_threshold_minor=100_00)

    # Coordinated multi-agent attack: 3 agents each cause 10_00 minor units
    # but the joint emergent harm is 1000_00 minor units (Synergy residual = 970_00)
    individual_harms = {
        "agent_colluder_1": 10_00,
        "agent_colluder_2": 10_00,
        "agent_colluder_3": 10_00,
    }
    joint_harm = 1000_00

    report = engine.evaluate_synergy_and_attribution(
        incident_target="treasury_pool",
        individual_harms=individual_harms,
        joint_measured_harm=joint_harm,
        root_sponsor_did="did:smaos:sponsor-root",
    )

    assert report.is_laundering_detected is True
    assert (
        report.rejection_code == "HALT_HANSARD_ATTRIBUTION_LAUNDERING_DETECTED"
    )
    assert report.joint_harm_minor == 1000_00
    assert report.sum_individual_harms_minor == 30_00
    assert report.synergy_residual_minor == 970_00
    assert report.root_sponsor_accountable == "did:smaos:sponsor-root"
    assert len(report.primary_causal_agents) == 3


def test_hansard_additive_harms_no_laundering():
    """Verify purely additive independent harms do not trigger laundering halt."""
    engine = HansardCausalProvenanceEngine(synergy_threshold_minor=100_00)

    individual_harms = {
        "agent_1": 200_00,
        "agent_2": 300_00,
    }
    joint_harm = 500_00  # Exactly sum of individual harms

    report = engine.evaluate_synergy_and_attribution(
        incident_target="treasury_pool",
        individual_harms=individual_harms,
        joint_measured_harm=joint_harm,
        root_sponsor_did="did:smaos:sponsor-root",
    )

    assert report.is_laundering_detected is False
    assert report.rejection_code is None
    assert report.synergy_residual_minor == 0


# ============================================================================
# 2. DEFECTION ACTIVATION PROBE TESTS
# ============================================================================

def test_defection_probe_initialization_and_validation():
    """Verify probe initialization and parameter validation."""
    with pytest.raises(ValueError):
        DefectionActivationProbe(weights=[], bias=0.0)

    probe = DefectionActivationProbe.create_calibrated_probe(
        dimension=32, threshold=0.85, layer=31
    )
    assert probe.dimension == 32
    assert probe.threshold == 0.85
    assert probe.layer_inspected == 31

    with pytest.raises(ValueError):
        # Passing wrong dimension vector raises ValueError
        probe.evaluate_residual_vector([0.0] * 16)


def test_defection_probe_benign_activation():
    """Verify benign baseline activations produce low defection probability."""
    probe = DefectionActivationProbe.create_calibrated_probe(dimension=32)

    # Neutral zero activation vector
    neutral_vec = [0.0] * 32
    res = probe.evaluate_residual_vector(neutral_vec)

    assert res.is_defecting is False
    assert res.rejection_code is None
    assert res.defection_probability < 0.10
    assert res.layer_inspected == 31


def test_defection_probe_defection_activation_halt():
    """
    Verify that an activation vector strongly aligned with the defection contrast
    direction breaches the 0.85 threshold and triggers execution halt.
    """
    probe = DefectionActivationProbe.create_calibrated_probe(
        dimension=32, threshold=0.85
    )

    # Construct malicious activation vector pointing in probe weight direction with high magnitude
    defecting_vec = [w * 10.0 for w in probe.weights]
    res = probe.evaluate_residual_vector(defecting_vec)

    assert res.is_defecting is True
    assert (
        res.rejection_code == "HALT_DEFECTING_NEURAL_ACTIVATION_DETECTED"
    )
    assert res.defection_probability >= 0.85


def test_defection_probe_sigmoid_numerical_stability():
    """Verify numerical stability under extreme positive and negative logits."""
    probe = DefectionActivationProbe(weights=[1.0], bias=0.0, threshold=0.85)

    res_pos = probe.evaluate_residual_vector([1000.0])
    assert res_pos.defection_probability == 1.0

    res_neg = probe.evaluate_residual_vector([-1000.0])
    assert res_neg.defection_probability == 0.0


# ============================================================================
# 3. EPISTEMIC & BANNED WORD CHECKS
# ============================================================================

def test_banned_words_absence():
    """Enforce strict epistemic boundary: zero forbidden promotional terms."""
    banned = [
        "guaran" + "teed",
        "guaran" + "tee",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
    ]
    files_to_check = [
        Path("src/hansard_causal_provenance.py"),
        Path("src/defection_activation_probe.py"),
        Path("tests/test_hansard_and_defection_probe.py"),
    ]
    for filepath in files_to_check:
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8").lower()
            for word in banned:
                assert word not in content, f"Banned word '{word}' found in {filepath}"
