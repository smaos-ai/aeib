#!/usr/bin/env python3
# File: tests/test_epistemic_action_compiler.py
"""
Pytest suite for the AEIB Epistemic Action Compiler (EAC) & Non-Dilutable Conflict Register.

Verifies:
1. All 5 trigger macros (/missed, /counterexample, /collusion, /substrate, /pre-mortem).
2. Non-dilutable conflict registration and Ed25519-signed mitigation resolution.
3. Ontic state mutation gate blocking when conflicts are unresolved (arXiv:2610.22469).
4. ETH Zurich Hypothesis-Drop Mutation (arXiv:2603.19514).
5. Cleanroom scan for zero banned promotional words.
"""
import base64
import json
import re
from pathlib import Path
from typing import Dict

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.epistemic_action_compiler import (
    EpistemicActionCompiler,
    EpistemicMacroTarget,
    EpistemicOnticGate,
    NonDilutableConflictRegister,
    OnticActionProposal,
    canonical_jcs_bytes,
)


def test_epistemic_macros_execution() -> None:
    priv = Ed25519PrivateKey.generate()
    register = NonDilutableConflictRegister(priv)
    compiler = EpistemicActionCompiler(register)

    # 1. Macro: /missed (Prior Art & Terminology Inversion)
    target_missed = EpistemicMacroTarget(
        macro_type="/missed",
        target_claim_or_endpoint="We built a novel agent_retry_lock for agentic_acid tasks.",
    )
    res_missed = compiler.execute_macro(target_missed)
    assert len(res_missed) == 2
    assert any("arXiv:2609.29095" in r.primary_citation for r in res_missed)
    assert any("arXiv:2608.13900" in r.primary_citation for r in res_missed)

    # 2. Macro: /counterexample (Hypothesis-Drop Mutation)
    target_hyp = EpistemicMacroTarget(
        macro_type="/counterexample",
        target_claim_or_endpoint="idempotent_mcp_proxy",
        declared_hypotheses=("H_MONOTONIC_CLOCK", "H_HTTP200_IS_SUCCESS"),
    )
    res_hyp = compiler.execute_macro(target_hyp)
    assert len(res_hyp) == 2
    assert all(r.conflict_detected for r in res_hyp)

    # 3. Macro: /collusion (Pairwise Composition Check)
    target_collusion = EpistemicMacroTarget(
        macro_type="/collusion",
        target_claim_or_endpoint="shared_agent_ledger",
        related_subagent_ids=("agent-alpha", "agent-beta"),
    )
    res_collusion = compiler.execute_macro(target_collusion)
    assert len(res_collusion) == 1
    assert res_collusion[0].macro_type == "/collusion"

    # 4. Macro: /substrate (Fault Injection)
    target_sub = EpistemicMacroTarget(
        macro_type="/substrate",
        target_claim_or_endpoint="settlement_gateway_post",
    )
    res_sub = compiler.execute_macro(target_sub)
    assert len(res_sub) == 1
    assert res_sub[0].counterexample_payload is not None
    assert res_sub[0].counterexample_payload.get("fault_type") == "HTTP_504_TIMEOUT"

    # 5. Macro: /pre-mortem (Hostile Reviewer)
    target_pm = EpistemicMacroTarget(
        macro_type="/pre-mortem",
        target_claim_or_endpoint="aeib_architecture_paper",
    )
    res_pm = compiler.execute_macro(target_pm)
    assert len(res_pm) == 1
    assert "MISSING_INDEPENDENT_RECEIPT" in str(res_pm[0].counterexample_payload)

    # Verify all conflicts recorded in register
    assert len(register.all_conflicts()) == 7
    assert len(register.unresolved_conflicts()) == 7


def test_non_dilutable_conflict_register_tamper_and_resolution() -> None:
    auditor_priv = Ed25519PrivateKey.generate()
    supervisor_priv = Ed25519PrivateKey.generate()
    supervisor_pub = supervisor_priv.public_key()

    register = NonDilutableConflictRegister(auditor_priv)
    compiler = EpistemicActionCompiler(register)

    compiler.execute_macro(
        EpistemicMacroTarget(
            macro_type="/counterexample",
            target_claim_or_endpoint="local_sqlite",
            declared_hypotheses=("H_SINGLE_REPLICA",),
        )
    )

    unresolved = register.unresolved_conflicts()
    assert len(unresolved) == 1
    c_id = unresolved[0].conflict_id

    # 1. Invalid signature attempt fails
    bogus_sig_b64 = base64.b64encode(b"\x00" * 64).decode("ascii")
    success_bogus = register.resolve_conflict(
        conflict_id=c_id,
        mitigation_clause="Valid mitigation clause with sufficient length.",
        supervisor_pubkey=supervisor_pub,
        supervisor_sig_b64=bogus_sig_b64,
    )
    assert success_bogus is False
    assert len(register.unresolved_conflicts()) == 1

    # 2. Too short clause fails
    short_clause = "short"
    sig_short = base64.b64encode(
        supervisor_priv.sign(
            canonical_jcs_bytes({"conflict_id": c_id, "mitigation": short_clause})
        )
    ).decode("ascii")
    success_short = register.resolve_conflict(
        conflict_id=c_id,
        mitigation_clause=short_clause,
        supervisor_pubkey=supervisor_pub,
        supervisor_sig_b64=sig_short,
    )
    assert success_short is False

    # 3. Valid signed mitigation succeeds
    valid_clause = "Mitigated by using PostgreSQL TCC distributed locks instead of local SQLite."
    valid_sig = base64.b64encode(
        supervisor_priv.sign(
            canonical_jcs_bytes({"conflict_id": c_id, "mitigation": valid_clause})
        )
    ).decode("ascii")

    success_valid = register.resolve_conflict(
        conflict_id=c_id,
        mitigation_clause=valid_clause,
        supervisor_pubkey=supervisor_pub,
        supervisor_sig_b64=valid_sig,
    )
    assert success_valid is True
    assert len(register.unresolved_conflicts()) == 0

    # 4. Receipt verification
    receipt = register.export_signed_receipt()
    auditor_priv.public_key().verify(
        base64.b64decode(receipt["signature_b64"], validate=True),
        canonical_jcs_bytes(receipt["payload"]),
    )
    assert receipt["payload"]["total_conflicts"] == 1
    assert receipt["payload"]["unresolved_conflict_ids"] == []


def test_epistemic_ontic_wire_gate_blocking() -> None:
    priv = Ed25519PrivateKey.generate()
    register = NonDilutableConflictRegister(priv)
    compiler = EpistemicActionCompiler(register)
    gate = EpistemicOnticGate(register)

    prop = OnticActionProposal(
        operation_id="op-ontic-01",
        action_type="ONTIC_MUTATION",
        target_resource="ledger://wire/disbursement",
        amount_minor=1500_00,
        payload={"payee": "iban:DE89370400440532013000"},
        policy_epoch="2026-Q4",
    )

    # 1. Pre-macro: No conflicts registered -> Allowed
    v_clean = gate.evaluate_ontic_proposal(prop)
    assert v_clean.disposition == "ALLOW_ONTO_STATION1_WAL"
    assert v_clean.unresolved_conflict_ids == ()

    # 2. Trigger macro discovers a counterexample
    compiler.execute_macro(
        EpistemicMacroTarget(
            macro_type="/substrate",
            target_claim_or_endpoint="disbursement_target",
        )
    )

    # 3. Post-macro: Gate strictly blocks ontic state mutation!
    v_blocked = gate.evaluate_ontic_proposal(prop)
    assert v_blocked.disposition == "HALT_UNRESOLVED_EPISTEMIC_CONFLICTS"
    assert len(v_blocked.unresolved_conflict_ids) == 1
    assert "ERR_BLOCKED_BY_1_UNRESOLVED_CONFLICTS" in v_blocked.reason_code


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

    paths_to_check = [
        Path("src/epistemic_action_compiler.py"),
        Path("tools/epistemic_action_compiler_ab_test.py"),
        Path(__file__),
    ]

    for p in paths_to_check:
        content = p.read_text(encoding="utf-8")
        matches = pattern.findall(content)
        assert not matches, f"Banned tokens {matches} found in {p}"
