#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_heterogeneous_consensus_mesh.py
================================================================================
Comprehensive verification suite for HeterogeneousConsensusMesh.
"""

from __future__ import annotations

import dataclasses
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.heterogeneous_consensus_mesh import (
    ConsensusMeshReceipt,
    EvaluatorRole,
    HeterogeneousConsensusMesh,
    MeshVerdict,
    ModelEvaluationProposal,
    ProposalVerdict,
    RuleNode,
    RuleTrekDependencyGraph,
    verify_consensus_mesh_receipt,
)


@pytest.fixture
def sample_rule_graph() -> RuleTrekDependencyGraph:
    rules = {
        "R1_SPEC_FLOOR": RuleNode(
            rule_id="R1_SPEC_FLOOR",
            domain="core",
            statement="All intent domains must be bounded.",
            dependencies=(),
            depth=0,
        ),
        "R2_ZERO_MOCK": RuleNode(
            rule_id="R2_ZERO_MOCK",
            domain="compliance",
            statement="No test doubles or mocks permitted.",
            dependencies=("R1_SPEC_FLOOR",),
            depth=1,
        ),
        "R3_HARDWARE_GATE": RuleNode(
            rule_id="R3_HARDWARE_GATE",
            domain="security",
            statement="Irreversible side effects require out-of-band biometric approval.",
            dependencies=("R2_ZERO_MOCK",),
            depth=2,
        ),
    }
    return RuleTrekDependencyGraph(rules=rules)


def test_nominal_consensus_approval(sample_rule_graph: RuleTrekDependencyGraph):
    with pytest.raises(dataclasses.FrozenInstanceError):
        sample_rule_graph.rules = {}  # type: ignore

    mesh = HeterogeneousConsensusMesh(rule_graph=sample_rule_graph)
    proposals = [
        ModelEvaluationProposal(
            evaluator_id="eval-logic-1",
            role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
            verdict=ProposalVerdict.APPROVE,
            justification="Syntax and bounds verified.",
            rules_addressed=("R1_SPEC_FLOOR", "R2_ZERO_MOCK"),
            confidence_bps=9500,
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-sec-2",
            role=EvaluatorRole.SECURITY_AND_MOCK_AUDITOR,
            verdict=ProposalVerdict.APPROVE,
            justification="Zero stubs or mocks detected.",
            rules_addressed=("R1_SPEC_FLOOR", "R2_ZERO_MOCK"),
            confidence_bps=9800,
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-bound-3",
            role=EvaluatorRole.BOUNDARY_AND_INVARIANT_FALSIFIER,
            verdict=ProposalVerdict.APPROVE,
            justification="Boundary mutation probes held.",
            rules_addressed=("R1_SPEC_FLOOR",),
            confidence_bps=9200,
        ),
    ]

    receipt = mesh.adjudicate(
        candidate_patch_digest="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        proposals=proposals,
        consensus_id="custom-mesh-id-01",
    )

    assert receipt.consensus_id == "custom-mesh-id-01"
    assert receipt.mesh_verdict == MeshVerdict.CONSENSUS_APPROVED
    assert receipt.consensus_agreement_bps == 10000
    assert receipt.evaluator_count == 3
    assert receipt.approval_count == 3
    assert receipt.rejection_count == 0
    assert receipt.dissent_with_falsification_count == 0
    assert receipt.rule_dependencies_verified is True
    assert receipt.violated_rule_edges == []
    assert receipt.falsification_vectors == []

    valid, err = verify_consensus_mesh_receipt(receipt.to_dict())
    assert valid is True
    assert err == "OK"


def test_insufficient_evaluators_rejected(sample_rule_graph: RuleTrekDependencyGraph):
    mesh = HeterogeneousConsensusMesh(rule_graph=sample_rule_graph)
    proposals = [
        ModelEvaluationProposal(
            evaluator_id="eval-1",
            role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
            verdict=ProposalVerdict.APPROVE,
            justification="Looks good.",
            rules_addressed=(),
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-2",
            role=EvaluatorRole.SECURITY_AND_MOCK_AUDITOR,
            verdict=ProposalVerdict.APPROVE,
            justification="Looks good.",
            rules_addressed=(),
        ),
    ]

    receipt = mesh.adjudicate(
        candidate_patch_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        proposals=proposals,
    )

    assert receipt.mesh_verdict == MeshVerdict.REJECTED_INSUFFICIENT_EVALUATORS
    assert receipt.evaluator_count == 2
    assert receipt.approval_count == 0
    assert receipt.rejection_count == 2
    assert receipt.dissent_with_falsification_count == 0
    assert receipt.rule_dependencies_verified is False
    assert receipt.consensus_agreement_bps == 0
    valid, err = verify_consensus_mesh_receipt(receipt.to_dict())
    assert valid is True
    assert err == "OK"


def test_asymmetric_evidence_dominance_minority_veto(sample_rule_graph: RuleTrekDependencyGraph):
    mesh = HeterogeneousConsensusMesh(rule_graph=sample_rule_graph)
    proposals = [
        ModelEvaluationProposal(
            evaluator_id="eval-superficial-1",
            role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
            verdict=ProposalVerdict.APPROVE,
            justification="Approved without deep testing.",
            rules_addressed=("R1_SPEC_FLOOR",),
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-superficial-2",
            role=EvaluatorRole.SECURITY_AND_MOCK_AUDITOR,
            verdict=ProposalVerdict.APPROVE,
            justification="No obvious issues.",
            rules_addressed=("R1_SPEC_FLOOR",),
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-adversarial-breaker",
            role=EvaluatorRole.BOUNDARY_AND_INVARIANT_FALSIFIER,
            verdict=ProposalVerdict.DISSENT_WITH_FALSIFICATION_PROOF,
            justification="Found integer overflow vulnerability on boundary input 2^63 - 1.",
            rules_addressed=("R1_SPEC_FLOOR",),
            falsification_vector={
                "failing_input": {"val": 9223372036854775807},
                "expected_outcome": "REJECT",
                "observed_error": "OverflowError",
            },
        ),
    ]

    receipt = mesh.adjudicate(
        candidate_patch_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        proposals=proposals,
    )

    assert receipt.mesh_verdict == MeshVerdict.VETOED_ASYMMETRIC_EVIDENCE_DOMINANCE
    assert receipt.evaluator_count == 3
    assert receipt.approval_count == 2
    assert receipt.rejection_count == 0
    assert receipt.dissent_with_falsification_count == 1
    assert len(receipt.falsification_vectors) == 1
    assert receipt.consensus_agreement_bps == 0
    assert receipt.rule_dependencies_verified is False
    assert receipt.falsification_vectors[0]["observed_error"] == "OverflowError"

    # Also test mixed approvals/rejections with dissent
    proposals_mixed = [
        proposals[0],  # APPROVE
        ModelEvaluationProposal(
            evaluator_id="eval-rej",
            role=EvaluatorRole.SECURITY_AND_MOCK_AUDITOR,
            verdict=ProposalVerdict.REJECT,
            justification="Style defect.",
            rules_addressed=("R1_SPEC_FLOOR",),
        ),
        proposals[2],  # DISSENT WITH PROOF
    ]
    receipt_mixed = mesh.adjudicate(
        candidate_patch_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        proposals=proposals_mixed,
    )
    assert receipt_mixed.approval_count == 1
    assert receipt_mixed.rejection_count == 1
    assert receipt_mixed.dissent_with_falsification_count == 1

    valid, err = verify_consensus_mesh_receipt(receipt.to_dict())
    assert valid is True
    assert err == "OK"


def test_dissent_without_vector_falls_to_rejection(sample_rule_graph: RuleTrekDependencyGraph):
    mesh = HeterogeneousConsensusMesh(rule_graph=sample_rule_graph)
    proposals = [
        ModelEvaluationProposal(
            evaluator_id="eval-1",
            role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
            verdict=ProposalVerdict.APPROVE,
            justification="Looks ok.",
            rules_addressed=("R1_SPEC_FLOOR",),
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-2",
            role=EvaluatorRole.SECURITY_AND_MOCK_AUDITOR,
            verdict=ProposalVerdict.APPROVE,
            justification="Looks ok.",
            rules_addressed=("R1_SPEC_FLOOR",),
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-3",
            role=EvaluatorRole.BOUNDARY_AND_INVARIANT_FALSIFIER,
            verdict=ProposalVerdict.DISSENT_WITH_FALSIFICATION_PROOF,
            justification="Dissent without vector attached.",
            rules_addressed=("R1_SPEC_FLOOR",),
            falsification_vector=None,
        ),
    ]

    receipt = mesh.adjudicate(
        candidate_patch_digest="sha256:2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b",
        proposals=proposals,
    )

    # 2 approves out of 3 = 6666 bps >= 6666 bps -> CONSENSUS_APPROVED
    assert receipt.mesh_verdict == MeshVerdict.CONSENSUS_APPROVED
    assert receipt.evaluator_count == 3
    assert receipt.approval_count == 2
    assert receipt.dissent_with_falsification_count == 1
    assert receipt.consensus_agreement_bps == HeterogeneousConsensusMesh.MIN_AGREEMENT_BPS
    assert receipt.rule_dependencies_verified is True


def test_ruletrek_dependency_violation(sample_rule_graph: RuleTrekDependencyGraph):
    mesh = HeterogeneousConsensusMesh(rule_graph=sample_rule_graph)
    proposals = [
        ModelEvaluationProposal(
            evaluator_id="eval-1",
            role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
            verdict=ProposalVerdict.APPROVE,
            justification="R2 addressed.",
            rules_addressed=("R2_ZERO_MOCK",),
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-2",
            role=EvaluatorRole.SECURITY_AND_MOCK_AUDITOR,
            verdict=ProposalVerdict.APPROVE,
            justification="R2 addressed.",
            rules_addressed=("R2_ZERO_MOCK",),
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-3",
            role=EvaluatorRole.BOUNDARY_AND_INVARIANT_FALSIFIER,
            verdict=ProposalVerdict.REJECT,
            justification="R2 addressed.",
            rules_addressed=("R2_ZERO_MOCK",),
        ),
    ]

    receipt = mesh.adjudicate(
        candidate_patch_digest="sha256:3333333333333333333333333333333333333333333333333333333333333333",
        proposals=proposals,
    )

    assert receipt.mesh_verdict == MeshVerdict.REJECTED_RULETREK_GRAPH_VIOLATION
    assert receipt.rule_dependencies_verified is False
    assert receipt.consensus_agreement_bps == 0
    assert receipt.evaluator_count == 3
    assert receipt.approval_count == 2
    assert receipt.rejection_count == 1
    assert receipt.dissent_with_falsification_count == 0
    assert "R2_ZERO_MOCK->MISSING(R1_SPEC_FLOOR)" in receipt.violated_rule_edges

    valid, err = verify_consensus_mesh_receipt(receipt.to_dict())
    assert valid is True
    assert err == "OK"


def test_ruletrek_unknown_rule(sample_rule_graph: RuleTrekDependencyGraph):
    is_closed_empty, missing_empty = sample_rule_graph.validate_dependency_closure(set())
    assert is_closed_empty is True
    assert missing_empty == []

    is_closed, missing = sample_rule_graph.validate_dependency_closure({"RULE_UNKNOWN_NONEXISTENT"})
    assert is_closed is False
    assert missing == ["RULE_UNKNOWN_NONEXISTENT->UNKNOWN_RULE"]

    is_closed_valid, missing_valid = sample_rule_graph.validate_dependency_closure({"R1_SPEC_FLOOR", "R2_ZERO_MOCK"})
    assert is_closed_valid is True
    assert missing_valid == []


def test_excessive_semantic_jitter_rejection(sample_rule_graph: RuleTrekDependencyGraph):
    mesh = HeterogeneousConsensusMesh(rule_graph=sample_rule_graph)
    proposals = [
        ModelEvaluationProposal(
            evaluator_id="eval-1",
            role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
            verdict=ProposalVerdict.APPROVE,
            justification="LGTM.",
            rules_addressed=("R1_SPEC_FLOOR",),
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-2",
            role=EvaluatorRole.SECURITY_AND_MOCK_AUDITOR,
            verdict=ProposalVerdict.REJECT,
            justification="Code structure unacceptable.",
            rules_addressed=("R1_SPEC_FLOOR",),
        ),
        ModelEvaluationProposal(
            evaluator_id="eval-3",
            role=EvaluatorRole.BOUNDARY_AND_INVARIANT_FALSIFIER,
            verdict=ProposalVerdict.REJECT,
            justification="Edge case unhandled.",
            rules_addressed=("R1_SPEC_FLOOR",),
        ),
    ]

    receipt = mesh.adjudicate(
        candidate_patch_digest="sha256:4444444444444444444444444444444444444444444444444444444444444444",
        proposals=proposals,
    )

    assert receipt.mesh_verdict == MeshVerdict.REJECTED_EXCESSIVE_SEMANTIC_JITTER
    assert receipt.consensus_agreement_bps == 3333
    assert receipt.approval_count == 1
    assert receipt.rejection_count == 2
    assert receipt.dissent_with_falsification_count == 0
    assert receipt.rule_dependencies_verified is True

    valid, err = verify_consensus_mesh_receipt(receipt.to_dict())
    assert valid is True
    assert err == "OK"


def test_receipt_verification_tamper_defenses(sample_rule_graph: RuleTrekDependencyGraph):
    mesh = HeterogeneousConsensusMesh(rule_graph=sample_rule_graph)
    proposals = [
        ModelEvaluationProposal(
            evaluator_id=f"eval-{i}",
            role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
            verdict=ProposalVerdict.APPROVE,
            justification="OK",
            rules_addressed=("R1_SPEC_FLOOR",),
        )
        for i in range(3)
    ]
    receipt = mesh.adjudicate(
        candidate_patch_digest="sha256:5555555555555555555555555555555555555555555555555555555555555555",
        proposals=proposals,
    )
    raw = receipt.to_dict()

    # 1. Nominal with pinned key
    ok, err = verify_consensus_mesh_receipt(raw, pinned_pubkey_hex=receipt.public_key_hex)
    assert ok is True
    assert err == "OK"

    # 2. Unpinned public key
    other_key = ed25519.Ed25519PrivateKey.generate().public_key()
    other_pub_hex = other_key.public_bytes_raw().hex()
    ok, err = verify_consensus_mesh_receipt(raw, pinned_pubkey_hex=other_pub_hex)
    assert ok is False
    assert err == "ERR_UNPINNED_CONSENSUS_PUBLIC_KEY"

    # 3. Missing fields
    corrupt_missing = dict(raw)
    del corrupt_missing["consensus_id"]
    ok, err = verify_consensus_mesh_receipt(corrupt_missing)
    assert ok is False
    assert err == "ERR_MISSING_RECEIPT_FIELDS"

    # 4. Tampered payload
    corrupt_tampered = dict(raw)
    corrupt_tampered["consensus_agreement_bps"] = 9999
    ok, err = verify_consensus_mesh_receipt(corrupt_tampered)
    assert ok is False
    assert err == "ERR_RECEIPT_CAID_MISMATCH"

    # 5. Invalid crypto signature
    corrupt_sig = dict(raw)
    corrupt_sig["signature_hex"] = "00" * 64
    ok, err = verify_consensus_mesh_receipt(corrupt_sig)
    assert ok is False
    assert err == "ERR_CONSENSUS_SIGNATURE_INVALID"

    # 6. Bad hex public key / signature
    corrupt_hex = dict(raw)
    corrupt_hex["public_key_hex"] = "not_a_hex"
    ok, err = verify_consensus_mesh_receipt(corrupt_hex)
    assert ok is False
    assert err == "ERR_INVALID_CRYPTO_ENVELOPE"

    # 7. Non-canonical JCS float
    corrupt_float = dict(raw)
    corrupt_float["consensus_agreement_bps"] = 100.5
    ok, err = verify_consensus_mesh_receipt(corrupt_float)
    assert ok is False
    assert err == "ERR_FLOAT_FORBIDDEN_IN_RECEIPT"

    # 8. Unserializable object triggers JCS canonicalization exception
    corrupt_jcs = dict(raw)
    corrupt_jcs["violated_rule_edges"] = [object()]
    ok, err = verify_consensus_mesh_receipt(corrupt_jcs)
    assert ok is False
    assert err == "ERR_JCS_CANONICALIZATION_FAILED"


def test_input_validation_errors(sample_rule_graph: RuleTrekDependencyGraph):
    mesh = HeterogeneousConsensusMesh(rule_graph=sample_rule_graph)

    # Invalid patch digest prefix
    with pytest.raises(ValueError, match="sha256:"):
        mesh.adjudicate(candidate_patch_digest="invalid_hash", proposals=[])

    # Valid boundaries for confidence_bps
    p_zero = ModelEvaluationProposal(
        evaluator_id="e0",
        role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
        verdict=ProposalVerdict.APPROVE,
        justification="test",
        rules_addressed=(),
        confidence_bps=0,
    )
    assert p_zero.confidence_bps == 0

    p_max = ModelEvaluationProposal(
        evaluator_id="e_max",
        role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
        verdict=ProposalVerdict.APPROVE,
        justification="test",
        rules_addressed=(),
        confidence_bps=10000,
    )
    assert p_max.confidence_bps == 10000

    # Invalid confidence_bps
    with pytest.raises(ValueError, match="confidence_bps"):
        ModelEvaluationProposal(
            evaluator_id="e1",
            role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
            verdict=ProposalVerdict.APPROVE,
            justification="test",
            rules_addressed=(),
            confidence_bps=-1,
        )

    with pytest.raises(ValueError, match="confidence_bps"):
        ModelEvaluationProposal(
            evaluator_id="e1",
            role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
            verdict=ProposalVerdict.APPROVE,
            justification="test",
            rules_addressed=(),
            confidence_bps=10001,
        )

    with pytest.raises(ValueError, match="confidence_bps"):
        ModelEvaluationProposal(
            evaluator_id="e1",
            role=EvaluatorRole.LOGICAL_CORRECTNESS_EVALUATOR,
            verdict=ProposalVerdict.APPROVE,
            justification="test",
            rules_addressed=(),
            confidence_bps="10000",  # type: ignore
        )
