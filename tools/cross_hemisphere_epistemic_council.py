#!/usr/bin/env python3
# File: tools/cross_hemisphere_epistemic_council.py
"""
Unified Cross-Hemisphere Epistemic Council & Tri-Partition Execution Fabric (`v1.0.0-rc.3` / `rc.5`).

Integrates:
1. `compliance/eac_typestate_conflict_engine.py` (P0 WAL Conflict Register + P1 Typestate Gate)
2. `tools/palantir_ontology_joint_witness_engine.py` (P2 6-Way Joint Commit Witness, arXiv:2609.37475)
3. `tools/cross_hemisphere_council_decide.py` (3-Tier `Ask` Router + Asymmetric Evidence Dominance)
4. `tools/current_missed_next_calculus.py` (O(1) Snapshot + d(CURRENT) + Weighted Partial MaxSAT)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from compliance.eac_typestate_conflict_engine import test_eac_p0_p1_gates
from tests.test_palantir_ontology_joint_witness_engine import (
    test_nominal_6way_joint_witness_commit,
    test_proposal_to_commit_object_state_drift_rejection,
)
from tools.cross_hemisphere_council_decide import (
    AgentDraftEnvelope,
    CouncilFusionReport,
    CrossHemisphereEpistemicCouncil,
    HypothesisClaim,
    ModelAskQuery,
    ResolvedAskRecord,
    ThreeTierAskResolutionRouter,
    TypedCrossCritiqueTuple,
    canonical_jcs,
    run_cross_hemisphere_council_scenario,
    sha256_prefixed,
    test_cross_hemisphere_council_and_ask_router,
)
from tools.current_missed_next_calculus import (
    CurrentCategorySnapshot,
    EpistemicObservation,
    MissedBoundaryOperator,
    NonDilutableConflictRegister,
    WeightedPartialMaxSatSynthesizer,
)


def run_integrated_tri_partition_architecture() -> Dict[str, Any]:
    """
    Executes the full Tri-Partition Execution Architecture (`CURRENT -> MISSED -> NEXT`):
    1. Verifies P0/P1 Typestate & Non-Dilutable Conflict WAL (`test_eac_p0_p1_gates`).
    2. Verifies P2 Palantir Ontology & 6-Way Joint Commit Witness (`arXiv:2609.37475`).
    3. Executes Cross-Hemisphere Council & 3-Tier `Ask` Router (`arXiv:2610.04542` & `arXiv:2605.00914`).
    4. Synthesizes `NEXT` via `WeightedPartialMaxSatSynthesizer`.
    """
    test_eac_p0_p1_gates()
    test_nominal_6way_joint_witness_commit()
    test_proposal_to_commit_object_state_drift_rejection()

    initial_council = run_cross_hemisphere_council_scenario()
    locked_dev_choice = (
        "(Recommended) Hybrid Tiered Topology: Default v1.0 to Single-Node CVM Appliance "
        "(SQLite WAL BEGIN IMMEDIATE + Rust io_uring 4K DirectIO) with optional "
        "Multi-Region Active-Active (3-node Raft + TigerBeetle VSR) profile"
    )
    locked_council = run_cross_hemisphere_council_scenario(
        developer_answers={"ask-dev-03": locked_dev_choice}
    )

    snap = CurrentCategorySnapshot(
        local_invariants={
            "aeib.wal_mode": "SQLite WAL BEGIN IMMEDIATE + Rust io_uring 4K-aligned DirectIO",
            "aeib.taint_policy": "Bell-LaPadula TIER_2 blocks unpinned payees (AT57b)",
            "aeib.joint_witness": "6-Way Joint Commit Witness (Action + Object Version + Epoch + Policy + CapLease + WYSIWYS)",
        },
        humanity_today_findings={
            "arxiv.2610.04542": "Decide, Ask, or Defer 3-action epistemic divergence",
            "arxiv.2605.00914": "32.3% Oracle Gap and 85.5% Sycophantic Conformity in homogeneous debate",
            "arxiv.2609.08016": "Tone-driven dissent vs external ground-truth position revision",
            "arxiv.2609.37475": "60.527% Invalid Commit Rate on action-only binding under state drift",
        },
    )
    missed_boundary = MissedBoundaryOperator.compute_boundary(snap)
    conflict_reg = NonDilutableConflictRegister()
    conflict_reg.record_observation(
        EpistemicObservation(
            action_id="act-drift-2609-37475",
            direction="PRIOR_ART_SEARCH",
            query_or_mutation="Action-only SHA-256 payload binding under state drift",
            conflict_detected=True,
            evidence_summary="60.527% Invalid Commit Rate on action-only binding",
            primary_reference="arXiv:2609.37475",
        )
    )
    conflict_reg.mark_resolved(
        "conflict:act-drift-2609-37475",
        "Enforce 6-Way Joint Commit Witness across Action, Object Version, Epoch, Policy, CapLease, and WYSIWYS.",
    )
    maxsat_result = WeightedPartialMaxSatSynthesizer.synthesize_next(
        current=snap,
        missed=missed_boundary,
        conflict_register=conflict_reg,
        council_report=locked_council,
    )

    return {
        "architecture": "CROSS-HEMISPHERE-TRI-PARTITION-v3.2",
        "initial_verdict": initial_council.panel_verdict,
        "locked_verdict": locked_council.panel_verdict,
        "maxsat_synthesis": maxsat_result,
        "oracle_gap_prevented": locked_council.oracle_gap_prevented,
        "receipt_sha256": locked_council.receipt_sha256,
        "signature_verified": CrossHemisphereEpistemicCouncil.verify_council_report_signature(
            locked_council
        ),
    }


def test_integrated_tri_partition_architecture() -> None:
    res = run_integrated_tri_partition_architecture()
    assert res["initial_verdict"] == "HOLD_FOR_DEVELOPER_ANSWERS"
    assert res["locked_verdict"] == "READY_TO_SYNTHESIZE"
    assert res["oracle_gap_prevented"] is True
    assert res["signature_verified"] is True
    assert res["maxsat_synthesis"]["next_status"] == "SYNTHESIS_LOCKED_READY"


if __name__ == "__main__":
    out = run_integrated_tri_partition_architecture()
    print(json.dumps(out, indent=2, sort_keys=True))
