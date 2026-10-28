"""
tests/test_aeib_track1_and_calibrated_guards.py — Verification suite for Track 1 guards,
calibrated monitor, zero-trust supply chain gatekeeper, and cognitive flight recorder.

Under the stated model, this suite evaluates:
1. Canonical JSON v1 deterministic serialization, float rejection, and non-string key rejection.
2. AT57b Bell-LaPadula pure taint gate and RFC 9470 step-up override.
3. AT58 pre-socket sprint escrow reservation and indeterminate hold blocking timeout smurfing.
4. G3 boot-time continuity replay, action CAID recomputation, and Ed25519 signature verification.
5. G6 destructive state pool quota enforcement on zero-dollar mutations.
6. Calibrated meta-evaluator statistical metrics (Precision, Recall, F1, FPR, FNR, MCC) and gain escalation.
7. Zero-trust supply chain 72-hour release cooldown and mid-session unfrozen plugin rejection.
8. Cognitive flight recorder OpenTelemetry span generation and hash chaining.
9. Epistemic banned words check.
"""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.aeib_track1_and_calibrated_guards import (
    BootVerifiedEo1EscrowGate,
    CognitiveFlightRecorder,
    EffectState,
    GoldenDatasetCalibratedMonitor,
    GoldenEvaluationCase,
    ReceiptTier,
    TaintTier,
    ZeroTrustSupplyChainGatekeeper,
    canonical_json_v1,
    compute_action_caid,
    sha256_digest,
)


def test_canonical_json_v1_rules() -> None:
    """Validate canonical JSON sorting and rejection of forbidden types."""
    data = {"b": 2, "a": 1, "nested": {"z": True, "y": None}}
    serialized = canonical_json_v1(data)
    assert serialized == b'{"a":1,"b":2,"nested":{"y":null,"z":true}}'

    # Floats strictly forbidden
    with pytest.raises(ValueError) as exc_float:
        canonical_json_v1({"score": 1.5})
    assert "ERR_FLOAT_FORBIDDEN_IN_CANONICAL_JSON_V1" in str(exc_float.value)

    # Non-string keys forbidden
    with pytest.raises(ValueError) as exc_key:
        canonical_json_v1({123: "val"})  # type: ignore
    assert "ERR_NON_STRING_KEY" in str(exc_key.value)


def test_at57b_pure_taint_gate_and_step_up() -> None:
    """Evaluate AT57b: untrusted context taint requires step-up unless beneficiary is pinned."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    with tempfile.TemporaryDirectory() as tmp:
        gate = BootVerifiedEo1EscrowGate(
            ledger_dir=Path(tmp),
            signing_key=priv,
            verify_key=pub,
            sprint_budget_minor=1000_00,
            max_destructive_ops_per_epoch=2,
            pinned_beneficiaries={"merchant_pinned_service"},
        )

        # 1. Untrusted context + unpinned beneficiary -> Rejected (relies on default has_rfc9470_step_up=False)
        d_taint = gate.authorize_and_execute(
            actor_id="agent_alpha",
            tool_name="payments.wire",
            beneficiary_id="unpinned_external_wallet",
            amount_minor=50_00,
            canonical_args={"memo": "untrusted payload"},
            context_taint=TaintTier.TIER_2_UNTRUSTED_EXTERNAL,
            dispatch_fn=lambda: {"status": "dispatched"},
        )
        assert d_taint.allowed is False
        assert d_taint.reason_code == "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP"

        # 2. Untrusted context + unpinned beneficiary + step-up warrant -> Allowed
        d_step_up = gate.authorize_and_execute(
            actor_id="agent_alpha",
            tool_name="payments.wire",
            beneficiary_id="unpinned_external_wallet",
            amount_minor=50_00,
            canonical_args={"memo": "untrusted payload"},
            context_taint=TaintTier.TIER_2_UNTRUSTED_EXTERNAL,
            dispatch_fn=lambda: {"status": "dispatched"},
            has_rfc9470_step_up=True,
        )
        assert d_step_up.allowed is True
        assert d_step_up.effect_state == EffectState.COMMITTED

        # 3. Untrusted context + pinned beneficiary -> Allowed without step-up
        d_pinned = gate.authorize_and_execute(
            actor_id="agent_alpha",
            tool_name="payments.wire",
            beneficiary_id="merchant_pinned_service",
            amount_minor=40_00,
            canonical_args={"memo": "pinned payload"},
            context_taint=TaintTier.TIER_2_UNTRUSTED_EXTERNAL,
            dispatch_fn=lambda: {"status": "dispatched"},
            has_rfc9470_step_up=False,
        )
        assert d_pinned.allowed is True
        assert d_pinned.effect_state == EffectState.COMMITTED


def test_at58_pre_socket_escrow_and_indeterminate_hold() -> None:
    """Evaluate AT58: timeout preserves indeterminate escrow, blocking timeout-smurfing."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    with tempfile.TemporaryDirectory() as tmp:
        gate = BootVerifiedEo1EscrowGate(
            ledger_dir=Path(tmp),
            signing_key=priv,
            verify_key=pub,
            sprint_budget_minor=1500_00,
            max_destructive_ops_per_epoch=2,
            pinned_beneficiaries={"airline_co", "hotel_co"},
        )

        def _timed_out_dispatch() -> Dict[str, Any]:
            raise TimeoutError("504 Gateway Timeout on wire")

        # Flight reservation for 900 EUR times out
        d_flight = gate.authorize_and_execute(
            actor_id="agent_travel",
            tool_name="payments.book_flight",
            beneficiary_id="airline_co",
            amount_minor=900_00,
            canonical_args={"flight_no": "BA100"},
            context_taint=TaintTier.TIER_1_INTERNAL_VERIFIED,
            dispatch_fn=_timed_out_dispatch,
        )
        assert d_flight.allowed is False
        assert d_flight.effect_state == EffectState.EFFECT_INDETERMINATE
        assert d_flight.indeterminate_held_minor == 900_00

        # Retrying the exact same CAID is latched and blocked
        d_retry = gate.authorize_and_execute(
            actor_id="agent_travel",
            tool_name="payments.book_flight",
            beneficiary_id="airline_co",
            amount_minor=900_00,
            canonical_args={"flight_no": "BA100"},
            context_taint=TaintTier.TIER_1_INTERNAL_VERIFIED,
            dispatch_fn=lambda: {"status": "ok"},
        )
        assert d_retry.allowed is False
        assert d_retry.reason_code == "HALT_LATCHED_EFFECT_INDETERMINATE_NO_RETRY"

        # Attempting hotel for 700 EUR exceeds sprint budget (900 held + 700 > 1500)
        d_hotel = gate.authorize_and_execute(
            actor_id="agent_travel",
            tool_name="payments.book_hotel",
            beneficiary_id="hotel_co",
            amount_minor=700_00,
            canonical_args={"hotel_id": "hilton_01"},
            context_taint=TaintTier.TIER_1_INTERNAL_VERIFIED,
            dispatch_fn=lambda: {"status": "ok"},
        )
        assert d_hotel.allowed is False
        assert (
            d_hotel.reason_code
            == "DENY_SPRINT_ESCROW_EXCEEDED_INCLUDING_INDETERMINATE_HOLD"
        )

        # Reconcile out of band as aborted releases held escrow
        d_reconciled = gate.record_downstream_effect(
            action_caid=d_flight.action_caid,
            effect_state=EffectState.RECONCILED_ABORTED,
        )
        assert d_reconciled.indeterminate_held_minor == 0

        # Now hotel booking for 700 EUR succeeds
        d_hotel_retry = gate.authorize_and_execute(
            actor_id="agent_travel",
            tool_name="payments.book_hotel",
            beneficiary_id="hotel_co",
            amount_minor=700_00,
            canonical_args={"hotel_id": "hilton_01"},
            context_taint=TaintTier.TIER_1_INTERNAL_VERIFIED,
            dispatch_fn=lambda: {"status": "booked"},
        )
        assert d_hotel_retry.allowed is True
        assert d_hotel_retry.effect_state == EffectState.COMMITTED
        assert d_hotel_retry.entry_caid.startswith("sha256:")
        assert len(d_hotel_retry.entry_caid) == 71
        assert (os.stat(gate.lock_path).st_mode & 0o777) == 0o600

        # Attempting to re-send an already COMMITTED CAID is denied
        d_resend = gate.authorize_and_execute(
            actor_id="agent_travel",
            tool_name="payments.book_hotel",
            beneficiary_id="hotel_co",
            amount_minor=700_00,
            canonical_args={"hotel_id": "hilton_01"},
            context_taint=TaintTier.TIER_1_INTERNAL_VERIFIED,
            dispatch_fn=lambda: {"status": "double_charge"},
        )
        assert d_resend.allowed is False
        assert d_resend.reason_code == "DENY_ALREADY_COMMITTED_NO_RESEND"

        # Calling record_downstream_effect with an unknown action_caid raises
        with pytest.raises(RuntimeError) as exc_unknown:
            gate.record_downstream_effect(
                action_caid="sha256:unknown_caid_999",
                effect_state=EffectState.COMMITTED,
            )
        assert "ERR_UNKNOWN_ACTION_CAID" in str(exc_unknown.value)


def test_g3_boot_time_replay_and_tampering_rejections() -> None:
    """Evaluate G3: boot-time verification detects in-place disk tampering."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    with tempfile.TemporaryDirectory() as tmp:
        ledger_dir = Path(tmp)
        gate = BootVerifiedEo1EscrowGate(
            ledger_dir=ledger_dir,
            signing_key=priv,
            verify_key=pub,
            sprint_budget_minor=1000_00,
            max_destructive_ops_per_epoch=2,
            pinned_beneficiaries={"trusted_service"},
        )

        gate.authorize_and_execute(
            actor_id="agent_1",
            tool_name="payments.wire",
            beneficiary_id="trusted_service",
            amount_minor=500_00,
            canonical_args={"memo": "first"},
            context_taint=TaintTier.TIER_0_TRUSTED_SYSTEM,
            dispatch_fn=lambda: {"status": "ok"},
        )

        # Clean restart verifies smoothly
        clean_restart = BootVerifiedEo1EscrowGate(
            ledger_dir=ledger_dir,
            signing_key=priv,
            verify_key=pub,
            sprint_budget_minor=1000_00,
            max_destructive_ops_per_epoch=2,
            pinned_beneficiaries={"trusted_service"},
        )
        assert clean_restart._chain_tip == gate._chain_tip

        # Falsification 1: In-place tampering of amount_minor
        ledger_text = gate.ledger_path.read_text(encoding="utf-8")
        tampered_amt_text = ledger_text.replace(
            '"amount_minor":50000', '"amount_minor":1000'
        )
        gate.ledger_path.write_text(tampered_amt_text, encoding="utf-8")

        with pytest.raises(RuntimeError) as exc_caid:
            BootVerifiedEo1EscrowGate(
                ledger_dir=ledger_dir,
                signing_key=priv,
                verify_key=pub,
                sprint_budget_minor=1000_00,
                max_destructive_ops_per_epoch=2,
                pinned_beneficiaries={"trusted_service"},
            )
        assert "HALT_BOOT_ACTION_CAID_TAMPERED" in str(exc_caid.value)

        # Falsification 2: In-place tampering of signature bytes
        gate.ledger_path.write_text(ledger_text, encoding="utf-8")  # restore
        lines = [l for l in ledger_text.splitlines() if l.strip()]
        rec = json.loads(lines[0])
        rec["gate_signature"] = "00" * 64
        tampered_sig_text = json.dumps(rec) + "\n"
        gate.ledger_path.write_text(tampered_sig_text, encoding="utf-8")

        with pytest.raises(RuntimeError) as exc_sig:
            BootVerifiedEo1EscrowGate(
                ledger_dir=ledger_dir,
                signing_key=priv,
                verify_key=pub,
                sprint_budget_minor=1000_00,
                max_destructive_ops_per_epoch=2,
                pinned_beneficiaries={"trusted_service"},
            )
        assert (
            "HALT_BOOT_SIGNATURE_INVALID" in str(exc_sig.value)
            or "HALT_BOOT_ENTRY_CAID_TAMPERED" in str(exc_sig.value)
        )


def test_g6_destructive_mutation_pool() -> None:
    """Evaluate G6: destructive operations are capped per epoch regardless of dollar amount."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    with tempfile.TemporaryDirectory() as tmp:
        gate = BootVerifiedEo1EscrowGate(
            ledger_dir=Path(tmp),
            signing_key=priv,
            verify_key=pub,
            sprint_budget_minor=1000_00,
            max_destructive_ops_per_epoch=1,
            pinned_beneficiaries={"db_admin"},
        )

        # First destructive mutation (amount = 0) is allowed
        d1 = gate.authorize_and_execute(
            actor_id="admin_agent",
            tool_name="db.delete_rows",
            beneficiary_id="db_admin",
            amount_minor=0,
            canonical_args={"table": "temp_logs"},
            context_taint=TaintTier.TIER_0_TRUSTED_SYSTEM,
            dispatch_fn=lambda: {"deleted": 5},
        )
        assert d1.allowed is True
        assert d1.destructive_ops_used == 1

        # Second destructive mutation exceeds cap of 1 -> Rejected
        d2 = gate.authorize_and_execute(
            actor_id="admin_agent",
            tool_name="db.drop_table",
            beneficiary_id="db_admin",
            amount_minor=0,
            canonical_args={"table": "old_backup"},
            context_taint=TaintTier.TIER_0_TRUSTED_SYSTEM,
            dispatch_fn=lambda: {"dropped": True},
        )
        assert d2.allowed is False
        assert (
            d2.reason_code == "DENY_DESTRUCTIVE_MUTATION_POOL_EXHAUSTED"
        )


def test_calibrated_meta_evaluator() -> None:
    """Evaluate GoldenDatasetCalibratedMonitor precision, recall, MCC, and gain escalation."""
    golden_cases = [
        GoldenEvaluationCase("c1", "def safe_fn(): return 1", True, "clean"),
        GoldenEvaluationCase("c2", "def stub_fn(): return True", False, "stub"),
        GoldenEvaluationCase("c3", "def eval_fn(): eval('x')", False, "injection"),
        GoldenEvaluationCase("c4", "def safe_math(a, b): return a + b", True, "clean"),
    ]

    # Evaluator that accepts everything (false negative on stubs)
    lenient_monitor = GoldenDatasetCalibratedMonitor(
        evaluator_fn=lambda code: True,
        golden_cases=golden_cases,
    )
    report_lenient = lenient_monitor.run_calibration()
    assert report_lenient.requires_human_escalation is True
    assert report_lenient.false_negatives == 2
    assert report_lenient.false_negative_rate == 1.0
    assert (
        report_lenient.recommended_jidoka_gain
        == "CRITICAL_FORMAL_AND_MUTATION_REQUIRED"
    )

    # Immutability check
    with pytest.raises(dataclasses.FrozenInstanceError):
        report_lenient.f1_score = 0.5  # type: ignore

    # Calibrated evaluator that correctly flags defects
    sound_monitor = GoldenDatasetCalibratedMonitor(
        evaluator_fn=lambda code: "return True" not in code and "eval(" not in code,
        golden_cases=golden_cases,
    )
    report_sound = sound_monitor.run_calibration()
    assert report_sound.requires_human_escalation is False
    assert report_sound.f1_score == 1.0
    assert report_sound.false_negative_rate == 0.0
    assert report_sound.matthews_corrcoef == 1.0
    assert report_sound.recommended_jidoka_gain == "CALIBRATED_AUTONOMOUS_GATE"

    # Mixed evaluation testing precision, recall, fpr, fnr, and mcc
    # 7 cases: 3 TP, 1 FP, 2 TN, 1 FN
    mixed_cases = [
        GoldenEvaluationCase("m1", "defect_detected_1", False, "defect"),
        GoldenEvaluationCase("m2", "defect_detected_2", False, "defect"),
        GoldenEvaluationCase("m3", "defect_detected_3", False, "defect"),
        GoldenEvaluationCase("m4", "false_alarm", True, "clean"),
        GoldenEvaluationCase("m5", "safe_pass_1", True, "clean"),
        GoldenEvaluationCase("m6", "safe_pass_2", True, "clean"),
        GoldenEvaluationCase("m7", "missed_defect", False, "defect"),
    ]
    mixed_monitor = GoldenDatasetCalibratedMonitor(
        evaluator_fn=lambda code: not (code.startswith("defect_") or code == "false_alarm"),
        golden_cases=mixed_cases,
    )
    report_mixed = mixed_monitor.run_calibration()
    assert report_mixed.true_positives == 3
    assert report_mixed.false_positives == 1
    assert report_mixed.true_negatives == 2
    assert report_mixed.false_negatives == 1
    assert report_mixed.precision == 0.75
    assert report_mixed.recall == 0.75
    assert report_mixed.f1_score == 0.75
    assert report_mixed.false_positive_rate == 0.3333
    assert report_mixed.false_negative_rate == 0.25
    assert report_mixed.matthews_corrcoef == 0.4167
    assert report_mixed.requires_human_escalation is True
    assert (
        report_mixed.recommended_jidoka_gain
        == "CRITICAL_FORMAL_AND_MUTATION_REQUIRED"
    )

    # Symmetrical 1/3 and 2/3 test to kill round(..., 4) constant perturbation mutants
    # 6 cases: TP=2, FP=1, FN=1, TN=2
    sym_cases = [
        GoldenEvaluationCase("s1", "defect_1", False, "defect"),
        GoldenEvaluationCase("s2", "defect_2", False, "defect"),
        GoldenEvaluationCase("s3", "false_pos_1", True, "clean"),
        GoldenEvaluationCase("s4", "true_neg_1", True, "clean"),
        GoldenEvaluationCase("s5", "true_neg_2", True, "clean"),
        GoldenEvaluationCase("s6", "false_neg_1", False, "defect"),
    ]
    sym_monitor = GoldenDatasetCalibratedMonitor(
        evaluator_fn=lambda c: not (c.startswith("defect_") or c == "false_pos_1"),
        golden_cases=sym_cases,
    )
    report_sym = sym_monitor.run_calibration()
    assert report_sym.precision == 0.6667
    assert report_sym.recall == 0.6667
    assert report_sym.f1_score == 0.6667
    assert report_sym.false_positive_rate == 0.3333
    assert report_sym.false_negative_rate == 0.3333
    assert report_sym.matthews_corrcoef == 0.3333

    # Asymmetric test: f1 >= 0.90 but fnr > 0.0 (kills BOOL_SWAP Or -> And)
    # TP=19, FP=0, FN=1, TN=20
    asym_cases = []
    for i in range(19):
        asym_cases.append(GoldenEvaluationCase(f"tp_{i}", f"defect_tp_{i}", False, "defect"))
    asym_cases.append(GoldenEvaluationCase("fn_0", "missed_defect", False, "defect"))
    for i in range(20):
        asym_cases.append(GoldenEvaluationCase(f"tn_{i}", f"safe_{i}", True, "clean"))

    asym_monitor = GoldenDatasetCalibratedMonitor(
        evaluator_fn=lambda c: not c.startswith("defect_tp_"),
        golden_cases=asym_cases,
    )
    report_asym = asym_monitor.run_calibration()
    assert report_asym.true_positives == 19
    assert report_asym.false_positives == 0
    assert report_asym.true_negatives == 20
    assert report_asym.false_negatives == 1
    assert report_asym.f1_score == 0.9744
    assert report_asym.false_negative_rate == 0.05
    assert report_asym.requires_human_escalation is True
    assert (
        report_asym.recommended_jidoka_gain
        == "CRITICAL_FORMAL_AND_MUTATION_REQUIRED"
    )


def test_zero_trust_supply_chain_gatekeeper() -> None:
    """Evaluate 72h release cooldown and mid-session unfrozen plugin rejection."""
    now = 1_760_000_000.0

    # 0. Test default 72h cooldown boundary
    gatekeeper_default = ZeroTrustSupplyChainGatekeeper(
        pinned_package_digests={"vetted_lib==2.0.0": "sha256:vetted_digest"},
        frozen_session_plugins=set(),
    )
    ok_sub, msg_sub = gatekeeper_default.verify_package_install(
        "vetted_lib==2.0.0", "sha256:vetted_digest", published_epoch_s=now - (72 * 3600 - 1), now_epoch_s=now
    )
    assert ok_sub is False
    assert "DENY_SUPPLY_CHAIN_COOLDOWN_VIOLATION" in msg_sub

    ok_post, msg_post = gatekeeper_default.verify_package_install(
        "vetted_lib==2.0.0", "sha256:vetted_digest", published_epoch_s=now - (72 * 3600 + 1), now_epoch_s=now
    )
    assert ok_post is True
    assert msg_post == "ALLOW_VERIFIED_PINNED_PACKAGE"

    gatekeeper = ZeroTrustSupplyChainGatekeeper(
        pinned_package_digests={"vetted_lib==2.0.0": "sha256:vetted_digest"},
        frozen_session_plugins={"mcp.fs_read", "mcp.search"},
        cooldown_seconds=72 * 3600,
    )

    # 1. Package published 1 hour ago (within 72h cooldown) -> Rejected
    ok_cool, msg_cool = gatekeeper.verify_package_install(
        "vetted_lib==2.0.0", "sha256:vetted_digest", published_epoch_s=now - 3600, now_epoch_s=now
    )
    assert ok_cool is False
    assert "DENY_SUPPLY_CHAIN_COOLDOWN_VIOLATION" in msg_cool

    # 2. Package published 5 days ago but unpinned -> Rejected
    ok_unpin, msg_unpin = gatekeeper.verify_package_install(
        "unknown_lib==1.0.0", "sha256:unknown", published_epoch_s=now - (5 * 86400), now_epoch_s=now
    )
    assert ok_unpin is False
    assert "DENY_UNPINNED_PACKAGE" in msg_unpin

    # 3. Package published 5 days ago with digest mismatch -> Rejected
    ok_mis, msg_mis = gatekeeper.verify_package_install(
        "vetted_lib==2.0.0", "sha256:tampered_digest", published_epoch_s=now - (5 * 86400), now_epoch_s=now
    )
    assert ok_mis is False
    assert "DENY_PACKAGE_DIGEST_MISMATCH" in msg_mis

    # 4. Valid pinned package after cooldown -> Allowed
    ok_valid, msg_valid = gatekeeper.verify_package_install(
        "vetted_lib==2.0.0", "sha256:vetted_digest", published_epoch_s=now - (5 * 86400), now_epoch_s=now
    )
    assert ok_valid is True
    assert msg_valid == "ALLOW_VERIFIED_PINNED_PACKAGE"

    # 5. Mid-session unfrozen plugin invocation -> Rejected
    ok_plug_bad, msg_plug_bad = gatekeeper.verify_plugin_invocation("mcp.unfrozen_dynamic_plugin")
    assert ok_plug_bad is False
    assert "DENY_MID_SESSION_UNFROZEN_PLUGIN" in msg_plug_bad

    # 6. Pre-frozen session plugin invocation -> Allowed
    ok_plug_good, msg_plug_good = gatekeeper.verify_plugin_invocation("mcp.fs_read")
    assert ok_plug_good is True
    assert msg_plug_good == "ALLOW_FROZEN_SESSION_PLUGIN"


def test_cognitive_flight_recorder() -> None:
    """Evaluate OpenTelemetry span generation, attribute mapping, and hash chaining."""
    recorder = CognitiveFlightRecorder()

    t0 = time.perf_counter()
    time.sleep(0.001)
    t1 = time.perf_counter()
    measured_ms = (t1 - t0) * 1000.0

    span1 = recorder.record_step_span(
        operation_name="step_one",
        model_id="gemini-argon",
        action_caid="sha256:act_1",
        code_ast_digest="sha256:ast_1",
        runtime_trace_digest="sha256:trace_1",
        env_digest="sha256:env_1",
        verdict="COMMITTED",
        latency_ms=measured_ms,
    )
    assert span1["attributes"]["gen_ai.operation.name"] == "step_one"
    assert span1["attributes"]["aeib.boundary.prev_span_sha256"] == "sha256:" + ("0" * 64)
    assert span1["attributes"]["aeib.boundary.receipt_tier"] == ReceiptTier.LOCAL_SIGNED_AUDIT_RECORD.value
    assert span1["latency_us"] == int(round(measured_ms * 1000))
    assert span1["latency_us"] > 0

    span2 = recorder.record_step_span(
        operation_name="step_two",
        model_id="gemini-argon",
        action_caid="sha256:act_2",
        code_ast_digest="sha256:ast_2",
        runtime_trace_digest="sha256:trace_2",
        env_digest="sha256:env_2",
        verdict="COMMITTED",
        latency_ms=measured_ms,
    )
    assert span2["attributes"]["aeib.boundary.prev_span_sha256"] == span1["span_sha256"]
    assert len(recorder.spans) == 2


def test_epistemic_banned_words() -> None:
    """Assert zero promotional banned words exist in source and test files."""
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "proven " + "universally",
        "bank-" + "grade",
        "unhack" + "able",
        "unassail" + "able",
    ]

    for path in (
        Path("src/aeib_track1_and_calibrated_guards.py"),
        Path("tests/test_aeib_track1_and_calibrated_guards.py"),
    ):
        text = path.read_text(encoding="utf-8").lower()
        for b in banned:
            assert b not in text, f"Found banned word '{b}' in {path}"
