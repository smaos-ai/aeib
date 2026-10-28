#!/usr/bin/env python3
# File: tests/test_defense_in_depth_and_intent_outcome.py
"""
Tests for AEIB Defense-in-Depth Policy Gate & Epistemic Intent-Outcome Engine.
"""

import base64
import json
from pathlib import Path
import tempfile
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from compliance.defense_in_depth_policy_gate import (
    DefenseInDepthPolicyGate,
    canonical_jcs_bytes,
)
from tools.epistemic_intent_outcome_engine import (
    EpistemicIntentOutcomeEngine,
)


def test_anti_disarmament_telemetry_protection() -> None:
    # 1. Prohibited command killing telemetry daemon
    res1 = DefenseInDepthPolicyGate.evaluate_command_execution(
        "pkill -9 otel-collector"
    )
    assert res1.allowed is False
    assert res1.halt_code == "HALT_TELEMETRY_TAMPER_DETECTED"

    # 2. Prohibited command deleting audit log
    res2 = DefenseInDepthPolicyGate.evaluate_command_execution(
        "rm -rf /var/log/audit.log"
    )
    assert res2.allowed is False
    assert res2.halt_code == "HALT_TELEMETRY_TAMPER_DETECTED"

    # 3. Benign developer command passes
    res3 = DefenseInDepthPolicyGate.evaluate_command_execution(
        "python3 -m pytest tests/test_core.py"
    )
    assert res3.allowed is True
    assert res3.halt_code == "NONE"


def test_runtime_startup_hook_lockdown_litellm_vector() -> None:
    # 1. Malicious write to sitecustomize.py
    res1 = DefenseInDepthPolicyGate.evaluate_file_write(
        "/usr/local/lib/python3.14/site-packages/sitecustomize.py"
    )
    assert res1.allowed is False
    assert res1.halt_code == "HALT_RUNTIME_HOOK_TAMPER_DETECTED"

    # 2. Malicious write to .pth hook file
    res2 = DefenseInDepthPolicyGate.evaluate_file_write(
        "site-packages/distutils-precedence.pth"
    )
    assert res2.allowed is False
    assert res2.halt_code == "HALT_RUNTIME_HOOK_TAMPER_DETECTED"

    # 3. Benign write to project source directory passes
    res3 = DefenseInDepthPolicyGate.evaluate_file_write("src/core/controller.py")
    assert res3.allowed is True
    assert res3.halt_code == "NONE"


def test_package_manager_step_up_gating() -> None:
    # 1. Unsigned pip install attempt fails closed
    res1 = DefenseInDepthPolicyGate.evaluate_package_install(
        ["pip", "install", "malicious-pkg"]
    )
    assert res1.allowed is False
    assert res1.halt_code == "HALT_UNSIGNED_PACKAGE_INSTALL"

    # 2. Generate valid Ed25519-signed RFC 9470 Step-Up warrant
    supervisor_priv = Ed25519PrivateKey.generate()
    supervisor_pub = supervisor_priv.public_key()
    warrant_stmt = {
        "scope": "SECURITY_OPERATIONS_PACKAGE_INSTALL",
        "authorized_package": "cryptography",
        "epoch": "2026-Q4",
        "timestamp_ns": time.time_ns(),
    }
    stmt_bytes = canonical_jcs_bytes(warrant_stmt)
    sig_b64 = base64.b64encode(supervisor_priv.sign(stmt_bytes)).decode("ascii")
    warrant_payload = dict(warrant_stmt)
    warrant_payload["signature_b64"] = sig_b64

    # 3. Authorized package install passes
    res2 = DefenseInDepthPolicyGate.evaluate_package_install(
        command_tokens=["pip", "install", "cryptography"],
        step_up_warrant=warrant_payload,
        supervisor_pubkey=supervisor_pub,
    )
    assert res2.allowed is True
    assert res2.halt_code == "NONE"


def test_network_egress_intent_registration() -> None:
    # 1. Outbound socket without CAID intent fails closed
    res1 = DefenseInDepthPolicyGate.evaluate_network_egress(
        destination_host="api.stripe.com",
        destination_port=443,
        caid_intent_token=None,
    )
    assert res1.allowed is False
    assert res1.halt_code == "HALT_UNREGISTERED_EGRESS_SOCKET"

    # 2. Outbound socket with valid CAID intent token passes
    res2 = DefenseInDepthPolicyGate.evaluate_network_egress(
        destination_host="api.stripe.com",
        destination_port=443,
        caid_intent_token="intent:caid-998877",
    )
    assert res2.allowed is True
    assert res2.halt_code == "NONE"


def test_epistemic_intent_outcome_two_phase_execution() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        wal_file = Path(tmpdir) / "test_intent_outcome.wal"
        engine = EpistemicIntentOutcomeEngine(
            wal_path=wal_file, total_budget_minor=5000_00
        )

        action = {
            "action": "disburse_grant",
            "beneficiary_iban": "DE89370400440532013000",
            "amount_minor": 1500_00,
        }

        # 1. Phase 1: Record Intent before external dispatch
        ok, intent_token, msg = engine.record_intent(
            action_payload=action,
            target_endpoint="POST /v1/disbursements",
            escrow_minor=1500_00,
        )
        assert ok is True
        assert intent_token is not None
        assert intent_token.status == "INTENT_RECORDED"
        assert engine.escrow_locked_minor == 1500_00
        assert engine.settled_expenditure_minor == 0

        # 2. Phase 2: Record Outcome upon completion
        response = {"status": "SUCCESS", "tx_id": "tx-2026-999"}
        outcome = engine.record_outcome(intent_token, response)
        assert outcome.status == "SETTLED"
        assert engine.escrow_locked_minor == 0
        assert engine.settled_expenditure_minor == 1500_00

        # 3. Crash recovery & replay resolution
        # Create new engine instance reading from same on-disk WAL
        recovered_engine = EpistemicIntentOutcomeEngine(
            wal_path=wal_file, total_budget_minor=5000_00
        )
        cached = recovered_engine.resolve_replay(intent_token.intent_hash)
        assert cached is not None
        assert cached.status == "SETTLED"
        assert cached.response_payload["tx_id"] == "tx-2026-999"

        # 4. Transport fault latches EFFECT_INDETERMINATE
        action2 = {
            "action": "refund_customer",
            "amount_minor": 500_00,
        }
        ok2, intent_token2, _ = recovered_engine.record_intent(
            action_payload=action2,
            target_endpoint="POST /v1/refunds",
            escrow_minor=500_00,
        )
        assert ok2 is True
        assert intent_token2 is not None

        # Simulate HTTP 504 drop
        ind = recovered_engine.handle_timeout_or_fault(
            intent_token2, error_reason="HTTP_504_GATEWAY_TIMEOUT"
        )
        assert ind.status == "EFFECT_INDETERMINATE"
        assert ind.retry_safe is False

        # Subsequent intent on latched hash is blocked fail-closed
        ok_retry, _, msg_retry = recovered_engine.record_intent(
            action_payload=action2,
            target_endpoint="POST /v1/refunds",
            escrow_minor=500_00,
        )
        assert ok_retry is False
        assert "HALT_INTENT_ALREADY_LATCHED_INDETERMINATE" in msg_retry


def test_banned_words_absence() -> None:
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "proven universal" + "ly",
        "unhack" + "able",
    ]
    repo_root = Path(__file__).resolve().parent.parent
    for rel in (
        "compliance/defense_in_depth.yaml",
        "compliance/defense_in_depth_policy_gate.py",
        "tools/epistemic_intent_outcome_engine.py",
        "tests/test_defense_in_depth_and_intent_outcome.py",
    ):
        text = (repo_root / rel).read_text(encoding="utf-8").lower()
        for w in banned:
            assert w not in text, f"Forbidden word found in {rel}"


def test_section7_mutation_boundaries(tmp_path: Path) -> None:
    import ast as _ast
    import compliance.defense_in_depth_policy_gate as did_mod
    import tools.epistemic_intent_outcome_engine as eio_mod
    from tools.epistemic_intent_outcome_engine import (
        IndeterminateRecord,
        IntentToken,
        OutcomeToken,
    )

    # 1. AST & structural checks on both modules
    did_tree = _ast.parse(Path(did_mod.__file__).read_text(encoding="utf-8"))
    found_did_exc = False
    for node in _ast.walk(did_tree):
        if isinstance(node, _ast.ExceptHandler) and isinstance(node.type, _ast.Name):
            for stmt in node.body:
                if isinstance(stmt, _ast.Expr) and isinstance(stmt.value, _ast.Call):
                    found_did_exc = True
                    assert isinstance(stmt.value.args[0], _ast.Constant) and stmt.value.args[0].value == 0
    assert found_did_exc is True

    eio_tree = _ast.parse(Path(eio_mod.__file__).read_text(encoding="utf-8"))
    found_eio_exc = False
    found_eio_path = False
    found_fsync_51 = False
    for node in _ast.walk(eio_tree):
        if isinstance(node, _ast.ExceptHandler) and isinstance(node.type, _ast.Name) and node.type.id == "ImportError":
            for stmt in node.body:
                if isinstance(stmt, _ast.Expr) and isinstance(stmt.value, _ast.Call):
                    found_eio_exc = True
                    sub = stmt.value.args[1].args[0]  # type: ignore[attr-defined]
                    assert isinstance(sub.slice, _ast.Constant) and sub.slice.value == 1
        if isinstance(node, _ast.If) and isinstance(node.test, _ast.Compare):
            if isinstance(node.test.ops[0], _ast.NotIn):
                found_eio_path = True
                call = node.body[0].value  # type: ignore[attr-defined]
                assert isinstance(call.args[0], _ast.Constant) and call.args[0].value == 0
        if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute) and node.func.attr == "fcntl":
            if len(node.args) == 2 and isinstance(node.args[1], _ast.Constant):
                found_fsync_51 = True
                assert node.args[1].value == 50 + 1
    assert found_eio_exc is True and found_eio_path is True and found_fsync_51 is True

    # 2. DefenseInDepthPolicyGate boundaries
    assert DefenseInDepthPolicyGate.evaluate_package_install([]).allowed is True
    assert DefenseInDepthPolicyGate.evaluate_package_install(["pip"]).allowed is True
    assert DefenseInDepthPolicyGate.evaluate_package_install(["pip", "install"]).allowed is False
    assert DefenseInDepthPolicyGate.evaluate_package_install(["pip", "list"]).allowed is True
    assert DefenseInDepthPolicyGate.evaluate_package_install(["git", "install", "pkg"]).allowed is True

    sup_priv = Ed25519PrivateKey.generate()
    sup_pub = sup_priv.public_key()
    assert (
        DefenseInDepthPolicyGate.evaluate_package_install(
            ["pip", "install", "pkg"],
            step_up_warrant={"scope": "WRONG_SCOPE"},
            supervisor_pubkey=sup_pub,
        ).allowed
        is False
    )
    assert (
        DefenseInDepthPolicyGate.evaluate_package_install(
            ["pip", "install", "pkg"],
            step_up_warrant={"scope": "SECURITY_OPERATIONS_PACKAGE_INSTALL", "signature_b64": "YWJj"},
            supervisor_pubkey=sup_pub,
        ).allowed
        is False
    )

    # 3. EpistemicIntentOutcomeEngine boundaries
    assert IntentToken.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert OutcomeToken.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert IndeterminateRecord.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    ind_def = IndeterminateRecord(intent_hash="sha256:00", error_reason="err")
    assert ind_def.retry_safe is False and ind_def.timestamp_ns == 0

    wal_p = tmp_path / "b.wal"
    eng = EpistemicIntentOutcomeEngine(wal_path=wal_p, signing_key=sup_priv)
    assert eng.total_budget_minor == 1000000
    assert eng.signing_key is sup_priv

    ok_ov, tok_ov, msg_ov = eng.record_intent({"x": 1}, "POST /x", 1000001)
    assert ok_ov is False and tok_ov is None and "HALT_INSUFFICIENT_ESCROW_BUDGET" in msg_ov

    ok_1, tok_1, _ = eng.record_intent({"x": 1}, "POST /x", 2000)
    assert ok_1 is True and tok_1 is not None
    assert tok_1.token_id == f"intent:{tok_1.intent_hash[7:23]}"
    assert len(tok_1.token_id) == 23
    assert '{"entry_type": "INTENT_RECORDED", "escrow_minor": 2000' in wal_p.read_text(encoding="utf-8")

    eng.record_outcome(tok_1, {"ok": True})
    ok_2, tok_2, _ = eng.record_intent({"x": 2}, "POST /x", 3000)
    assert ok_2 is True and tok_2 is not None
    eng.handle_timeout_or_fault(tok_2, "TIMEOUT")

    eng_rec = EpistemicIntentOutcomeEngine(wal_path=wal_p)
    assert eng_rec._settled_expenditure_minor == 2000
    assert eng_rec._escrow_locked_minor == 3000
    assert eng_rec._indeterminate[tok_2.intent_hash].retry_safe is False
