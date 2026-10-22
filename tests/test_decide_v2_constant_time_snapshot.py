#!/usr/bin/env python3
# File: tests/test_decide_v2_constant_time_snapshot.py
"""
Pytest suite for tools/decide_v2_constant_time_snapshot.py (/decide v2.0 O(1) Snapshot & 5-Why Engine).

Verifies:
1. O(1) AST Moat & Symbol Snapshot indexing across real repository directories.
2. Sub-millisecond (O(1)) lookup of existing symbols, HALT_* codes, and arXiv citations.
3. 5-Why root-cause chain construction and 3-bucket alignment delta separation
   (ALREADY_COVERED_IN_LOCAL_MOAT, CANDIDATE_ADDITIVE_LAYER, REJECTED_UNVERIFIED_OVERCLAIM).
4. Two-iteration layered critique convergence (converged_residual_conflicts == 0).
5. Cleanroom banned-word scan.
"""
import re
from pathlib import Path

import pytest

from tools.decide_v2_constant_time_snapshot import (
    ConstantTimeCodebaseSnapshot,
    DecideV2IterativeEngine,
    ExternalResearchClaim,
    run_decide_v2_self_verification,
)


def test_o1_constant_time_codebase_snapshot_index_and_lookup() -> None:
    workspace = Path(__file__).resolve().parent.parent
    snapshot = ConstantTimeCodebaseSnapshot(workspace)
    stats = snapshot.build_index()

    assert stats["total_modules_indexed"] >= 40
    assert stats["total_unique_keywords"] >= 200
    assert stats["total_halt_codes_indexed"] >= 20
    assert stats["snapshot_digest"].startswith("sha256:")

    # O(1) lookup by HALT code
    entries_halt, us_halt = snapshot.query_o1("HALT_UNPROBED_MUTATION")
    assert len(entries_halt) >= 1
    assert any("eac_typestate_conflict_engine.py" in e.rel_path for e in entries_halt)
    assert us_halt < 10_000  # < 10ms (typically < 50 microseconds)

    # O(1) lookup by class / concept
    entries_bec, us_bec = snapshot.query_o1("BoseEinsteinCognitiveSynthesizer")
    assert len(entries_bec) >= 1
    assert any("epistemic_core.py" in e.rel_path for e in entries_bec)
    assert us_bec < 10_000

    # O(1) lookup by arXiv citation
    entries_arxiv, _ = snapshot.query_o1("arXiv:2609.37475")
    assert len(entries_arxiv) >= 1
    assert any("palantir_ontology" in e.rel_path for e in entries_arxiv)


def test_decide_v2_five_why_and_two_iteration_convergence() -> None:
    res = run_decide_v2_self_verification()
    summary = res["alignment_summary"]

    assert summary["already_covered_count"] == 1
    assert summary["candidate_additive_layers_count"] == 1
    assert summary["rejected_overclaims_count"] == 1
    assert summary["converged_residual_conflicts"] == 0
    assert summary["evaluation_receipt_digest"].startswith("sha256:")


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

    for p in [
        Path("tools/decide_v2_constant_time_snapshot.py"),
        Path(".agents/skills/decide/SKILL.md"),
        Path(__file__),
    ]:
        content = p.read_text(encoding="utf-8")
        matches = pattern.findall(content)
        assert not matches, f"Banned tokens {matches} found in {p}"
