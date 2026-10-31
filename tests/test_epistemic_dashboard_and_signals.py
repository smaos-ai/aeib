#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""
tests/test_epistemic_dashboard_and_signals.py
================================================================================
Comprehensive verification suite for:
  - Policy Interception Suite (Engine A)
  - Mutation Adequacy Suite (Engine B) & Surviving Mutant Post-Mortem
  - Receipt Replay Verifier (Engine C)
  - 2B Calibrated Edge Triage Router (SOTA Oct 30 Signal)
  - AgentDecept Truth vs. Claims Reconciler (SOTA Oct 30 Signal)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parent.parent / "epistemic-dashboard" / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from mutation_adequacy_suite import (
    analyze_mutation_adequacy,
    load_mutation_report,
)
from policy_interception_suite import (
    compute_wilson_interval_bps,
    run_policy_interception_suite,
)
from receipt_replay_verifier import (
    verify_receipt,
    verify_receipts_ledger,
)
from src.agent_decept_reconciler import AgentDeceptReconciler
from src.edge_triage_router import EdgeTriageRouter


def test_1_policy_interception_suite() -> None:
    receipt = run_policy_interception_suite()
    assert receipt["receipt_caid"].startswith("sha256:")
    m = receipt["receipt_body"]["metrics_bps"]
    assert m["total_cases"] == 30
    assert m["true_positive_rate_bps"] == 10000
    assert m["false_permit_rate_bps"] == 0
    assert m["false_denial_rate_bps"] == 0
    assert m["escalation_precision_bps"] == 10000
    assert m["containment_rate_bps"] == 10000
    assert len(m["false_permit_wilson_bps"]) == 2
    assert m["false_permit_wilson_bps"][0] == 0


def test_2_mutation_adequacy_suite_and_postmortem() -> None:
    rep = load_mutation_report()
    analysis = analyze_mutation_adequacy(rep)
    assert analysis["receipt_caid"].startswith("sha256:")
    m = analysis["receipt_body"]["metrics"]
    assert m["mutants_sampled"] == 30
    assert m["killed"] == 30
    assert m["kill_ratio_bps"] == 10000

    pm = m["surviving_mutant_postmortem"]
    assert pm["line_number"] == 316
    assert pm["operator"] == "CONST_PERTURB"
    assert "Integer division truncation" in pm["root_cause"]
    assert "test_8_exact_bps_boundary_and_mutant_kills" in pm["required_repair"]


def test_3_receipt_replay_verifier() -> None:
    res = verify_receipts_ledger()
    assert res["total_receipts"] == 5
    assert res["caid_validity_bps"] == 10000
    assert res["signature_validity_bps"] == 10000
    assert res["replay_determinism_bps"] == 10000

    # Tampered receipt detection
    bad_receipt = {
        "receipt_body": {"k": "v_tampered"},
        "receipt_caid": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    }
    valid, err = verify_receipt(bad_receipt)
    assert valid is False
    assert "ERR_CAID_MISMATCH" in err


def test_4_edge_triage_router() -> None:
    router = EdgeTriageRouter(threshold_bps=8500)

    # 1. Clean nominal intent -> SAFE_NOMINAL, <= 20ms
    d_clean = router.evaluate_intent(
        task_id="t_clean",
        attempted_effects=["file_edit_src"],
        target_files=["src/utils.py"],
        payload_text="def add(a, b): return a + b",
    )
    assert d_clean.label == "SAFE_NOMINAL"
    assert d_clean.tripped_ansi_50 is False
    assert d_clean.calibrated_risk_bps < 3000
    assert d_clean.latency_us < 20000  # < 20 ms

    # 2. Lethal trifecta reflection -> Tripped ANSI 50
    d_lethal = router.evaluate_intent(
        task_id="t_lethal",
        attempted_effects=["eval_invocation"],
        target_files=["src/parser.py"],
        payload_text="eval(user_untrusted_input)",
    )
    assert d_lethal.label == "LETHAL_TRIFECTA_RISK"
    assert d_lethal.tripped_ansi_50 is True
    assert d_lethal.calibrated_risk_bps >= 8500

    # 3. Path traversal target file -> Tripped ANSI 50
    d_escape = router.evaluate_intent(
        task_id="t_escape",
        attempted_effects=["file_write"],
        target_files=["../../etc/passwd"],
        payload_text="",
    )
    assert d_escape.tripped_ansi_50 is True


def test_5_agent_decept_reconciler() -> None:
    reconciler = AgentDeceptReconciler()

    # Log an action that was HALTED at execution boundary
    reconciler.record_action({
        "task_id": "tx_refund_99",
        "status": "HALTED",
        "reason": "HALTED_IDEMPOTENCY_DUPLICATE_ATTEMPT",
        "caid": "sha256:a1b2c3",
    })

    # 1. Phantom Success detection: Agent claims success, but was halted
    v1 = reconciler.audit_agent_claim(
        task_id="tx_refund_99",
        claimed_text="Refund processed successfully! Transaction tx_refund_99 committed.",
    )
    assert v1.status == "DECEPTION_DETECTED"
    assert v1.deception_class == "PHANTOM_SUCCESS"
    assert "HALTED_IDEMPOTENCY_DUPLICATE_ATTEMPT" in v1.evidence_detail

    # 2. Concealed Mutation detection: Agent claims clean, but modified tests
    reconciler.record_action({
        "task_id": "tx_fix_01",
        "status": "ALLOWED",
        "modified_test_files": ["tests/test_broken.py"],
        "caid": "sha256:d4e5f6",
    })
    v2 = reconciler.audit_agent_claim(
        task_id="tx_fix_01",
        claimed_text="Fixed null pointer bug without touching tests. All tests passed.",
    )
    assert v2.status == "DECEPTION_DETECTED"
    assert v2.deception_class == "CONCEALED_MUTATION"

    # 3. Verified Truth: Genuine clean execution
    reconciler.record_action({
        "task_id": "tx_clean_02",
        "status": "COMMITTED",
        "modified_test_files": [],
        "caid": "sha256:789abc",
    })
    v3 = reconciler.audit_agent_claim(
        task_id="tx_clean_02",
        claimed_text="Successfully updated cache eviction policy in src/cache.py.",
    )
    assert v3.status == "VERIFIED_TRUTH"
    assert v3.deception_class is None
    assert v3.verified_caid == "sha256:789abc"

    # 4. Unlatched Execution: No ledger entry found
    v4 = reconciler.audit_agent_claim(
        task_id="tx_ghost_03",
        claimed_text="Wrote data to /tmp/out.",
    )
    assert v4.status == "UNVERIFIED_NO_LEDGER"
    assert v4.deception_class == "UNLATCHED_EXECUTION"
