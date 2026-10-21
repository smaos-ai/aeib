#!/usr/bin/env python3
# File: tests/test_palantir_ontology_joint_witness_engine.py
"""
Pytest suite for the AEIB 3.0 Palantir-Grade Operational Ontology & 6-Way Joint Commit Witness Engine.

Verifies:
1. Nominal 6-way joint witness commit and atomic version advance.
2. Proposal-to-Commit object state drift rejection (Wesley Shu, arXiv:2609.37475).
3. CapLease semantic capability replay rejection (Jinghan Xu et al., arXiv:2608.01710).
4. Consent Integrity Mediator (CIM WYSIWYS) untrusted narration stripping (Xiaoqi Weng, arXiv:2606.02668).
5. Post-qualification authority revocation guard.
6. Policy digest and authority epoch rotation guard.
7. Monotonic subclass constraint tightening (Gaotang Li et al., arXiv:2610.28380).
8. Cleanroom scan for zero banned promotional words.
"""
import base64
import json
import re
from pathlib import Path
from typing import Dict

import pytest

from tools.palantir_ontology_joint_witness_engine import (
    BaseOntologyBoundaryHarness,
    ConsentIntegrityMediator,
    OntologyObject,
    QualifiedActionProposal,
    SupervisorApprovalWarrant,
    TreasuryOntologyHarness,
    canonical_jcs,
    sha256_hex,
)


def test_canonical_jcs_float_rejection() -> None:
    """Verifies that floats are forbidden in canonical JCS to prevent IEEE 754 precision drift."""
    with pytest.raises(ValueError, match="ERR_FLOAT_FORBIDDEN_USE_INTEGER_MINOR_UNITS"):
        canonical_jcs({"amount": 12.34})

    valid = canonical_jcs({"amount_minor": 1234, "currency": "EUR"})
    assert isinstance(valid, bytes)
    assert b"1234" in valid


def test_nominal_6way_joint_witness_commit() -> None:
    """Verifies nominal 6-way joint commit witness evaluation and state advance."""
    harness = BaseOntologyBoundaryHarness(
        active_authority_epoch="epoch-2026-10",
        active_policy_digest="sha256:policy-aeib-v3-root",
    )

    order = OntologyObject(
        object_type="CustomerOrder",
        object_id="order:ORD-991",
        version_seq=1,
        attributes={"status": "PAID", "total_minor": 300_00},
    )
    initial_proj = order.semantic_projection_hash()

    proposal = QualifiedActionProposal(
        operation_id="op-10029",
        action_name="IssueRefund",
        target_object_id="order:ORD-991",
        parameters={"status": "REFUNDED", "refund_minor": 300_00},
        qualified_object_projection=initial_proj,
        qualified_authority_epoch="epoch-2026-10",
        qualified_policy_digest="sha256:policy-aeib-v3-root",
        caplease_semantic_slot="CustomerOrder:order:ORD-991:IssueRefund",
    )

    # Human supervisor warrant with CIM ground-truth render
    gt_render = ConsentIntegrityMediator.render_ground_truth_prompt(
        action_name=proposal.action_name,
        target_obj=order,
        parameters=proposal.parameters,
        agent_untrusted_narration="User claimed accidental double purchase.",
    )
    expected_witness = proposal.compute_joint_commit_witness(gt_render)

    warrant = SupervisorApprovalWarrant(
        wire_summary=gt_render,
        supervisor_id="supervisor:ciso-desk-01",
        signature_b64=base64.b64encode(b"ed25519-valid-sig-payload").decode("ascii"),
    )

    result = harness.commit_ontology_action(
        proposal=proposal,
        target_obj=order,
        caller_id="agent:treasury-agent-42",
        approval_warrant=warrant,
    )

    assert result["disposition"] == "GRANTED"
    assert result["code"] == "ONTOLOGY_ACTION_COMMITTED"
    assert result["new_version_seq"] == "2"
    assert result["bound_joint_witness"] == expected_witness
    assert order.version_seq == 2
    assert order.attributes["status"] == "REFUNDED"
    assert order.attributes["refund_minor"] == 300_00
    assert proposal.caplease_semantic_slot in harness.consumed_capleases


def test_proposal_to_commit_object_state_drift_rejection() -> None:
    """
    Verifies Wesley Shu (arXiv:2609.37475) Proposal-to-Commit State Drift:
    If target object state mutates between qualification and commit, commit is denied.
    """
    harness = BaseOntologyBoundaryHarness(
        active_authority_epoch="epoch-2026-10",
        active_policy_digest="sha256:policy-aeib-v3-root",
    )

    order = OntologyObject(
        object_type="CustomerOrder",
        object_id="order:ORD-992",
        version_seq=1,
        attributes={"status": "PAID", "total_minor": 500_00},
    )
    stale_projection = order.semantic_projection_hash()

    proposal = QualifiedActionProposal(
        operation_id="op-10030",
        action_name="IssueRefund",
        target_object_id="order:ORD-992",
        parameters={"status": "REFUNDED", "refund_minor": 500_00},
        qualified_object_projection=stale_projection,
        qualified_authority_epoch="epoch-2026-10",
        qualified_policy_digest="sha256:policy-aeib-v3-root",
        caplease_semantic_slot="CustomerOrder:order:ORD-992:IssueRefund",
    )

    # Concurrency hazard: Another worker updates order status in the meantime
    order.attributes["status"] = "DISPUTED"
    order.version_seq = 2

    result = harness.commit_ontology_action(
        proposal=proposal,
        target_obj=order,
        caller_id="agent:treasury-agent-42",
    )

    assert result["disposition"] == "DENIED"
    assert result["code"] == "HALT_PROPOSAL_TO_COMMIT_OBJECT_STATE_DRIFT"
    assert proposal.caplease_semantic_slot not in harness.consumed_capleases
    # Order attributes must not be overwritten
    assert order.attributes["status"] == "DISPUTED"


def test_caplease_semantic_replay_blocked() -> None:
    """
    Verifies Jinghan Xu et al. (arXiv:2608.01710):
    Re-submitting the same business effect under a newly minted operation_id is blocked.
    """
    harness = BaseOntologyBoundaryHarness(
        active_authority_epoch="epoch-2026-10",
        active_policy_digest="sha256:policy-aeib-v3-root",
    )

    order = OntologyObject(
        object_type="CustomerOrder",
        object_id="order:ORD-993",
        version_seq=1,
        attributes={"status": "PAID", "total_minor": 100_00},
    )

    proposal1 = QualifiedActionProposal(
        operation_id="op-10031-first",
        action_name="IssueRefund",
        target_object_id="order:ORD-993",
        parameters={"status": "REFUNDED", "refund_minor": 100_00},
        qualified_object_projection=order.semantic_projection_hash(),
        qualified_authority_epoch="epoch-2026-10",
        qualified_policy_digest="sha256:policy-aeib-v3-root",
        caplease_semantic_slot="CustomerOrder:order:ORD-993:IssueRefund",
    )

    res1 = harness.commit_ontology_action(
        proposal=proposal1,
        target_obj=order,
        caller_id="agent:treasury-agent-42",
    )
    assert res1["disposition"] == "GRANTED"

    # Replay attack: new operation_id, but same CapLease semantic slot
    proposal2 = QualifiedActionProposal(
        operation_id="op-10032-second-replay",
        action_name="IssueRefund",
        target_object_id="order:ORD-993",
        parameters={"status": "REFUNDED", "refund_minor": 100_00},
        qualified_object_projection=order.semantic_projection_hash(),
        qualified_authority_epoch="epoch-2026-10",
        qualified_policy_digest="sha256:policy-aeib-v3-root",
        caplease_semantic_slot="CustomerOrder:order:ORD-993:IssueRefund",
    )

    res2 = harness.commit_ontology_action(
        proposal=proposal2,
        target_obj=order,
        caller_id="agent:treasury-agent-42",
    )
    assert res2["disposition"] == "DENIED"
    assert res2["code"] == "HALT_CAPLEASE_SEMANTIC_REPLAY_BLOCKED"


def test_cim_narration_poisoning_silent_approval_bypass_rejected() -> None:
    """
    Verifies Xiaoqi Weng (arXiv:2606.02668):
    Approval warrants that diverge from ground-truth wire parameters fail closed.
    """
    harness = BaseOntologyBoundaryHarness(
        active_authority_epoch="epoch-2026-10",
        active_policy_digest="sha256:policy-aeib-v3-root",
    )

    order = OntologyObject(
        object_type="CustomerOrder",
        object_id="order:ORD-994",
        version_seq=1,
        attributes={"status": "PAID", "total_minor": 200_00},
    )

    proposal = QualifiedActionProposal(
        operation_id="op-10033",
        action_name="IssueRefund",
        target_object_id="order:ORD-994",
        parameters={"status": "REFUNDED", "refund_minor": 200_00},
        qualified_object_projection=order.semantic_projection_hash(),
        qualified_authority_epoch="epoch-2026-10",
        qualified_policy_digest="sha256:policy-aeib-v3-root",
        caplease_semantic_slot="CustomerOrder:order:ORD-994:IssueRefund",
    )

    # Attacker crafts supervisor warrant signing deceptive narration rather than wire diff
    forged_warrant = SupervisorApprovalWarrant(
        wire_summary="ACTION=IssueRefund;TARGET=order:ORD-994;PARAMS=DECEPTIVE_SUMMARY_50_EUROS;",
        supervisor_id="supervisor:ciso-desk-01",
        signature_b64=base64.b64encode(b"sig").decode("ascii"),
    )

    result = harness.commit_ontology_action(
        proposal=proposal,
        target_obj=order,
        caller_id="agent:treasury-agent-42",
        approval_warrant=forged_warrant,
    )

    assert result["disposition"] == "DENIED"
    assert result["code"] == "HALT_CIM_SILENT_APPROVAL_BYPASS_DETECTED"


def test_post_qualification_authority_revocation_blocked() -> None:
    """Verifies that revoking authority post-proposal qualification blocks dispatch before commit."""
    harness = BaseOntologyBoundaryHarness(
        active_authority_epoch="epoch-2026-10",
        active_policy_digest="sha256:policy-aeib-v3-root",
    )

    order = OntologyObject(
        object_type="CustomerOrder",
        object_id="order:ORD-995",
        version_seq=1,
        attributes={"status": "PAID"},
    )

    proposal = QualifiedActionProposal(
        operation_id="op-10034",
        action_name="IssueRefund",
        target_object_id="order:ORD-995",
        parameters={"status": "REFUNDED"},
        qualified_object_projection=order.semantic_projection_hash(),
        qualified_authority_epoch="epoch-2026-10",
        qualified_policy_digest="sha256:policy-aeib-v3-root",
        caplease_semantic_slot="CustomerOrder:order:ORD-995:IssueRefund",
    )

    # Authority revoked prior to commit
    harness.revoked_authorities.add("agent:rogue-agent-99")

    result = harness.commit_ontology_action(
        proposal=proposal,
        target_obj=order,
        caller_id="agent:rogue-agent-99",
    )

    assert result["disposition"] == "DENIED"
    assert result["code"] == "HALT_POST_QUALIFICATION_AUTHORITY_REVOKED"


def test_policy_or_epoch_drift_rejected() -> None:
    """Verifies that authority epoch rotation or policy update during dispatch fails closed."""
    harness = BaseOntologyBoundaryHarness(
        active_authority_epoch="epoch-2026-11",  # Rotated
        active_policy_digest="sha256:policy-aeib-v3-root",
    )

    order = OntologyObject(
        object_type="CustomerOrder",
        object_id="order:ORD-996",
        version_seq=1,
        attributes={"status": "PAID"},
    )

    proposal = QualifiedActionProposal(
        operation_id="op-10035",
        action_name="IssueRefund",
        target_object_id="order:ORD-996",
        parameters={"status": "REFUNDED"},
        qualified_object_projection=order.semantic_projection_hash(),
        qualified_authority_epoch="epoch-2026-10",  # Stale epoch
        qualified_policy_digest="sha256:policy-aeib-v3-root",
        caplease_semantic_slot="CustomerOrder:order:ORD-996:IssueRefund",
    )

    result = harness.commit_ontology_action(
        proposal=proposal,
        target_obj=order,
        caller_id="agent:treasury-agent-42",
    )

    assert result["disposition"] == "DENIED"
    assert result["code"] == "HALT_PROPOSAL_TO_COMMIT_POLICY_OR_EPOCH_DRIFT"


def test_monotonic_subclass_tightening_treasury_harness() -> None:
    """
    Verifies Gaotang Li et al. (arXiv:2610.28380):
    Subclasses enforce monotonic tightening (can only add stricter criteria, never relax base).
    """
    treasury = TreasuryOntologyHarness(
        active_authority_epoch="epoch-2026-10",
        active_policy_digest="sha256:policy-aeib-v3-root",
        max_disbursement_minor=1000_00,  # €1,000.00 ceiling
    )

    order = OntologyObject(
        object_type="CustomerOrder",
        object_id="order:ORD-997",
        version_seq=1,
        attributes={"status": "PAID"},
    )

    # 1. Non-positive amount rejected
    p_zero = QualifiedActionProposal(
        operation_id="op-10036-zero",
        action_name="IssueRefund",
        target_object_id="order:ORD-997",
        parameters={"refund_minor": 0},
        qualified_object_projection=order.semantic_projection_hash(),
        qualified_authority_epoch="epoch-2026-10",
        qualified_policy_digest="sha256:policy-aeib-v3-root",
        caplease_semantic_slot="CustomerOrder:order:ORD-997:RefundZero",
    )
    r_zero = treasury.commit_ontology_action(p_zero, order, "agent:treasury-42")
    assert r_zero["disposition"] == "DENIED"
    assert r_zero["code"] == "ERR_NON_POSITIVE_AMOUNT"

    # 2. Exceeding ceiling rejected
    p_excess = QualifiedActionProposal(
        operation_id="op-10037-excess",
        action_name="IssueRefund",
        target_object_id="order:ORD-997",
        parameters={"refund_minor": 1500_00},
        qualified_object_projection=order.semantic_projection_hash(),
        qualified_authority_epoch="epoch-2026-10",
        qualified_policy_digest="sha256:policy-aeib-v3-root",
        caplease_semantic_slot="CustomerOrder:order:ORD-997:RefundExcess",
    )
    r_excess = treasury.commit_ontology_action(p_excess, order, "agent:treasury-42")
    assert r_excess["disposition"] == "DENIED"
    assert r_excess["code"] == "ERR_EXCEEDS_DISBURSEMENT_CEILING"

    # 3. Valid disbursement within ceiling succeeds
    p_valid = QualifiedActionProposal(
        operation_id="op-10038-valid",
        action_name="IssueRefund",
        target_object_id="order:ORD-997",
        parameters={"refund_minor": 500_00},
        qualified_object_projection=order.semantic_projection_hash(),
        qualified_authority_epoch="epoch-2026-10",
        qualified_policy_digest="sha256:policy-aeib-v3-root",
        caplease_semantic_slot="CustomerOrder:order:ORD-997:RefundValid",
    )
    r_valid = treasury.commit_ontology_action(p_valid, order, "agent:treasury-42")
    assert r_valid["disposition"] == "GRANTED"
    assert r_valid["code"] == "ONTOLOGY_ACTION_COMMITTED"
    assert order.attributes["refund_minor"] == 500_00


def test_banned_words_absence() -> None:
    """Verifies that no promotional or uncalibrated marketing buzzwords exist in ontology engine or tests."""
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

    paths_to_check = [
        Path("tools/palantir_ontology_joint_witness_engine.py"),
        Path(__file__),
    ]

    for p in paths_to_check:
        content = p.read_text(encoding="utf-8")
        matches = pattern.findall(content)
        assert not matches, f"Banned tokens {matches} found in {p}"
