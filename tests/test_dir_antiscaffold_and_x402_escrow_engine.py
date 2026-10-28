"""
Verification & Mutation-Adequacy Test Suite for:
- Part I: DirAntiScaffoldAndScopeBisector (AST multi-statement stub detection,
  behavioral differential probing, ecosystem reuse vs out-of-scope track routing)
- Part II: FailClosedGroundedHealthMonitor (remediating the fail-open empty-context
  bug and JCS float crash in the pasted ModelHealthMonitor prototype)
- Part III: HardenedX402EscrowInterceptor (wired to real PreDispatchIntentInterlock,
  stopping SIWx URL mismatch, per-intent cap, cumulative epoch wallet-drain smurfing,
  and challenge nonce replay)
- Part IV: LiveHardwareAndSqliteExperimentRunner (real F_FULLFSYNC + SQLite FTS5 bm25).
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.dir_antiscaffold_and_x402_escrow_engine import (
    DirAntiScaffoldAndScopeBisector,
    FailClosedGroundedHealthMonitor,
    GroundedStepReceipt,
    HardenedX402EscrowInterceptor,
    LiveHardwareAndSqliteExperimentRunner,
    ParallelOutOfScopeTrackSpec,
    ScaffoldFinding,
    X402PaymentIntent,
)
from src.eo1_write_before_execute import PreDispatchIntentInterlock
from src.jcs_canonicalizer import encode_jcs


def test_dir_ast_antiscaffold_and_behavioral_probe_and_routing() -> None:
    # 1. Multi-statement docstring-padded trivial verifiers & simulated dicts are caught,
    #    while clean anti-mock docstrings and real conditional verifiers pass cleanly.
    bad_source = '''
def verify_enclave_padded(quote: bytes) -> bool:
    """Docstring mentioning zero mock and no simulated fallback."""
    _unused = len(quote)
    return True

def check_tpm_dict(pcr: int) -> dict:
    """Docstring."""
    x = pcr + 1
    return {"status": "ok"}

def run_kernel_probe() -> dict:
    if True:
        return {"kernel": "simulated_bpf", "verified": True}
    return {"verified": False}

def run_unconditional_sim() -> dict:
    x = 1
    return {"mode": "simulated_only"}

def run_conditional_non_truthy_sim(flag: bool) -> dict:
    if flag:
        return {"mode": "simulated_opt_in", "verified": False}
    return {"mode": "real", "verified": False}

def verify_docstring_only() -> None:
    """Single docstring statement."""

def verify_real_signature(sig: bytes) -> bool:
    """Clean conditional verifier that mentions simulated mode is forbidden."""
    if len(sig) != 64:
        raise ValueError("Invalid length")
    return True
'''
    findings = DirAntiScaffoldAndScopeBisector.inspect_source_for_scaffolds(
        bad_source, module_path="fixture_scaffolds.py"
    )
    codes = {f.anomaly_code for f in findings}
    symbols = {f.symbol_name for f in findings}
    assert "HALT_UNCONDITIONAL_TRUE_VERIFIER_STUB" in codes
    assert "HALT_UNCONDITIONAL_DICT_VERIFIER_STUB" in codes
    assert "HALT_SIMULATED_SUCCESS_DICT_STUB" in codes
    assert "verify_enclave_padded" in symbols
    assert "check_tpm_dict" in symbols
    assert "run_kernel_probe" in symbols
    assert "run_unconditional_sim" in symbols
    assert "run_conditional_non_truthy_sim" not in symbols
    assert "verify_docstring_only" not in symbols
    assert "verify_real_signature" not in symbols

    f0 = findings[0]
    with pytest.raises(AttributeError):
        f0.lineno = 999  # type: ignore[misc]
    assert f0.to_dict()["module_path"] == "fixture_scaffolds.py"

    # 2. Behavioral differential probe catches static True, constant non-bool output, or truthy dict on corrupted input
    with pytest.raises(ValueError, match="HALT_STATIC_SCAFFOLD_BEHAVIOR_DETECTED"):
        DirAntiScaffoldAndScopeBisector.probe_callable_for_static_scaffold(
            lambda x: "VALID_ACK" if x == b"valid" else True,
            valid_input=b"valid",
            corrupted_input=b"",
        )

    with pytest.raises(ValueError, match="HALT_STATIC_SCAFFOLD_BEHAVIOR_DETECTED"):
        DirAntiScaffoldAndScopeBisector.probe_callable_for_static_scaffold(
            lambda _x: "CONSTANT_INVARIANT_STRING",
            valid_input=b"valid",
            corrupted_input=b"",
        )

    with pytest.raises(ValueError, match="HALT_STATIC_SCAFFOLD_BEHAVIOR_DETECTED"):
        DirAntiScaffoldAndScopeBisector.probe_callable_for_static_scaffold(
            lambda x: {"verified": True, "echo": len(x)},
            valid_input=b"valid",
            corrupted_input=b"",
        )

    def _real_verifier_raises(payload: bytes) -> bool:
        if not payload or payload.startswith(b"CORRUPT"):
            raise ValueError("Malformed payload")
        return True

    probe_exc = DirAntiScaffoldAndScopeBisector.probe_callable_for_static_scaffold(
        _real_verifier_raises,
        valid_input=b"OK_PAYLOAD",
        corrupted_input=b"CORRUPT_BYTES",
    )
    assert probe_exc["probe_status"] == "REAL_DISCRIMINATING_VERIFIER"
    assert probe_exc["corrupted_exception"] == "ValueError"

    probe_bool = DirAntiScaffoldAndScopeBisector.probe_callable_for_static_scaffold(
        lambda x: len(x) >= 4,
        valid_input=b"ABCD",
        corrupted_input=b"A",
    )
    assert probe_bool["probe_status"] == "REAL_DISCRIMINATING_VERIFIER"
    assert probe_bool["corrupted_output"] is False

    # 3. Ecosystem Reuse vs Out-of-Scope Track Routing
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    reuse_spec = DirAntiScaffoldAndScopeBisector.route_subsystem_requirement(
        "durable_write_before_execute_latch",
        available_host_capabilities=["posix_filesystem", "fcntl_flock", "os_fsync"],
        signer_private_key=priv,
    )
    assert reuse_spec.routing_disposition == "REUSE_EXISTING_VERIFIED_PRIMITIVE"
    assert "PreDispatchIntentInterlock" in reuse_spec.existing_verified_provider
    with pytest.raises(AttributeError):
        reuse_spec.track_id = "tamper"  # type: ignore[misc]
    pub.verify(
        base64.b64decode(reuse_spec.signature_b64),
        encode_jcs({**reuse_spec.statement_dict(), "spec_digest": reuse_spec.spec_digest}),
    )

    isolated_spec = DirAntiScaffoldAndScopeBisector.route_subsystem_requirement(
        "linux_ebpf_lsm_kernel_probe",
        available_host_capabilities=["posix_filesystem"],  # missing linux_kernel_6_8_btf
        signer_private_key=priv,
    )
    assert isolated_spec.routing_disposition == "ISOLATE_PARALLEL_OUT_OF_SCOPE_TRACK"
    assert isolated_spec.cold_host_fallback_error == "ERR_CAPABILITY_UNAVAILABLE_ON_HOST"

    ready_spec = DirAntiScaffoldAndScopeBisector.route_subsystem_requirement(
        "lean4_kernel_proof_checker",
        available_host_capabilities=["lean4_binary", "lake_build_toolchain"],
        signer_private_key=priv,
    )
    assert ready_spec.routing_disposition == "EXECUTE_EXTERNAL_BINARY_BRIDGE"

    with pytest.raises(ValueError, match="HALT_UNKNOWN_SUBSYSTEM_REQUIREMENT"):
        DirAntiScaffoldAndScopeBisector.route_subsystem_requirement(
            "non_existent_subsystem_xyz",
            available_host_capabilities=[],
            signer_private_key=priv,
        )


def test_fail_closed_grounded_health_monitor_remediates_pasted_bugs() -> None:
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    for bad_bps in (0, -10, 10001):
        with pytest.raises(ValueError, match="min_grounding_bps"):
            FailClosedGroundedHealthMonitor(priv, min_grounding_bps=bad_bps)

    min_monitor = FailClosedGroundedHealthMonitor(priv, min_grounding_bps=1)
    assert min_monitor.min_grounding_bps == 1

    monitor = FailClosedGroundedHealthMonitor(priv)
    assert monitor.min_grounding_bps > 4999 and monitor.min_grounding_bps < 5001
    context = ["EO1 PreDispatchIntentInterlock uses fcntl.flock and F_FULLFSYNC on darwin."]

    # Exact 50% boundary (1 of 2 tokens matched -> 5000 bps -> HEALTHY under default 5000 threshold)
    r_half = monitor.evaluate_and_sign_step(
        step_id="step-half",
        model_id="deepseek-v4.1-flash",
        caid="sha256:00",
        context_spans=context,
        generated_output="PreDispatchIntentInterlock novelword",
    )
    assert r_half.status == "HEALTHY"

    # Falsification of Pasted Bug 1: Empty context or blank output MUST fail closed (0 bps, HALTED), NOT return 1.0!
    r_empty_ctx = monitor.evaluate_and_sign_step(
        step_id="step-empty-ctx",
        model_id="deepseek-v4.1-flash",
        caid="sha256:01",
        context_spans=[],
        generated_output="PreDispatchIntentInterlock uses fcntl.flock.",
    )
    assert r_empty_ctx.grounding_score_bps == 0
    assert r_empty_ctx.status == "HALTED_EMPTY_CONTEXT_OR_OUTPUT"
    assert FailClosedGroundedHealthMonitor.verify_receipt(r_empty_ctx, pub) is True
    with pytest.raises(AttributeError):
        r_empty_ctx.status = "HEALTHY"  # type: ignore[misc]

    r_blank_out = monitor.evaluate_and_sign_step(
        step_id="step-blank-out",
        model_id="deepseek-v4.1-flash",
        caid="sha256:02",
        context_spans=context,
        generated_output="   ",
    )
    assert r_blank_out.grounding_score_bps == 0
    assert r_blank_out.status == "HALTED_EMPTY_CONTEXT_OR_OUTPUT"

    # Falsification of Pasted Bug 2: JCS signing works cleanly over integer bps and detects compound drift
    monitor_fresh = FailClosedGroundedHealthMonitor(priv, min_grounding_bps=5000)
    s1_ok = monitor_fresh.evaluate_and_sign_step(
        step_id="s1",
        model_id="deepseek-v4.1-flash",
        caid="sha256:s1",
        context_spans=context,
        generated_output="PreDispatchIntentInterlock uses fcntl.flock and F_FULLFSYNC",
    )
    assert s1_ok.status == "HEALTHY"
    assert s1_ok.grounding_score_bps == 10000

    s1b_ok = monitor_fresh.evaluate_and_sign_step(
        step_id="s1b",
        model_id="deepseek-v4.1-flash",
        caid="sha256:s1b",
        context_spans=context,
        generated_output="PreDispatchIntentInterlock uses fcntl.flock and F_FULLFSYNC",
    )
    assert s1b_ok.status == "HEALTHY"

    # First degraded step (after 2 healthy prior steps, degraded_count == 0) MUST stay DEGRADED
    s2_deg = monitor_fresh.evaluate_and_sign_step(
        step_id="s2",
        model_id="deepseek-v4.1-flash",
        caid="sha256:s2",
        context_spans=context,
        generated_output="Unrelated hallucinated quantum blockchain telemetry",
    )
    assert s2_deg.status == "DEGRADED"
    assert s2_deg.grounding_score_bps == 0

    # Second consecutive degraded step in a 3-step window trips HALTED_COMPOUND_DRIFT
    s3_halt = monitor_fresh.evaluate_and_sign_step(
        step_id="s3",
        model_id="deepseek-v4.1-flash",
        caid="sha256:s3",
        context_spans=context,
        generated_output="Another ungrounded fabrication without overlap",
    )
    assert s3_halt.status == "HALTED_COMPOUND_DRIFT"

    # Tampered signature fails closed
    wrong_pub = Ed25519PrivateKey.generate().public_key()
    with pytest.raises(ValueError, match="HALT_INVALID_GROUNDED_STEP_SIGNATURE"):
        FailClosedGroundedHealthMonitor.verify_receipt(s3_halt, wrong_pub)


def test_hardened_x402_escrow_interceptor_wired_to_real_eo1(tmp_path: Path) -> None:
    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "x402_ledger.jsonl",
        output_state_dir=tmp_path / "x402_state",
    )

    for bad_cap, bad_wallet in [(0, 100), (100, 50)]:
        with pytest.raises(ValueError, match="Invalid x402 spend cap"):
            HardenedX402EscrowInterceptor(
                interlock,
                max_per_intent_minor=bad_cap,
                max_epoch_wallet_minor=bad_wallet,
            )

    min_gate = HardenedX402EscrowInterceptor(
        interlock,
        max_per_intent_minor=1,
        max_epoch_wallet_minor=1,
    )
    assert min_gate.max_per_intent_minor == 1

    default_gate = HardenedX402EscrowInterceptor(interlock)
    assert default_gate.max_per_intent_minor > 99 and default_gate.max_per_intent_minor < 101
    assert default_gate.max_epoch_wallet_minor == 5 * default_gate.max_per_intent_minor

    gate = HardenedX402EscrowInterceptor(
        interlock,
        max_per_intent_minor=100,
        max_epoch_wallet_minor=150,
    )
    url = "https://paid-oracle.example.com/v1/query"

    # 1. Valid $0.90 payment commits to real EO1 ledger and updates cumulative spend
    req1 = X402PaymentIntent(
        recipient_url=url,
        amount_minor=90,
        currency="USDC",
        challenge_nonce="nonce-001",
    )
    with pytest.raises(AttributeError):
        req1.amount_minor = 10  # type: ignore[misc]
    out1 = gate.authorize_and_dispatch_x402(req1, expected_402_url=url)
    assert out1["lifecycle_state"] == "RECONCILED"
    assert out1["cumulative_epoch_spend_minor"] == 90
    assert out1["remaining_epoch_wallet_minor"] == 60
    assert len(out1["receipt_chain_tip"]) == 64

    # 2. Challenge nonce replay blocked
    with pytest.raises(RuntimeError, match="HALT_X402_NONCE_REPLAY"):
        gate.authorize_and_dispatch_x402(req1, expected_402_url=url)

    # 3. SIWx URL redirection mismatch blocked
    with pytest.raises(RuntimeError, match="HALT_X402_URL_MISMATCH"):
        gate.authorize_and_dispatch_x402(
            X402PaymentIntent(
                recipient_url="https://attacker-drain.example.com/steal",
                amount_minor=10,
                currency="USDC",
                challenge_nonce="nonce-002",
            ),
            expected_402_url=url,
        )

    # 4. Unrecognized currency blocked
    with pytest.raises(RuntimeError, match="HALT_X402_UNRECOGNIZED_CURRENCY"):
        gate.authorize_and_dispatch_x402(
            X402PaymentIntent(
                recipient_url=url,
                amount_minor=10,
                currency="FAKE_TOKEN",
                challenge_nonce="nonce-003",
            ),
            expected_402_url=url,
        )

    # 5. Per-intent spend cap breach (and non-positive amount) blocked
    for bad_amt in (0, -5, 101):
        with pytest.raises(RuntimeError, match="HALT_X402_SPEND_CAP_EXCEEDED"):
            gate.authorize_and_dispatch_x402(
                X402PaymentIntent(
                    recipient_url=url,
                    amount_minor=bad_amt,
                    currency="USDC",
                    challenge_nonce=f"nonce-bad-{bad_amt}",
                ),
                expected_402_url=url,
            )

    # 6. Cumulative epoch wallet-drain smurfing attack (90 + 70 = 160 > 150) blocked!
    with pytest.raises(RuntimeError, match="HALT_X402_EPOCH_WALLET_DRAIN_BLOCKED"):
        gate.authorize_and_dispatch_x402(
            X402PaymentIntent(
                recipient_url=url,
                amount_minor=70,
                currency="USD_STABLE",
                challenge_nonce="nonce-smurf-004",
            ),
            expected_402_url=url,
        )


def test_live_hardware_and_sqlite_experiment_runner() -> None:
    for bad_eo1, bad_fts in [(0, 10), (5, 0)]:
        with pytest.raises(ValueError, match="Experiment counts must be positive"):
            LiveHardwareAndSqliteExperimentRunner.run_live_durability_and_fts5_experiment(
                eo1_iterations=bad_eo1,
                fts_fact_count=bad_fts,
            )

    res_min = LiveHardwareAndSqliteExperimentRunner.run_live_durability_and_fts5_experiment(
        eo1_iterations=1,
        fts_fact_count=1,
    )
    assert res_min["eo1_iterations_executed"] == 1
    assert res_min["fts_facts_indexed"] == 1

    res = LiveHardwareAndSqliteExperimentRunner.run_live_durability_and_fts5_experiment(
        eo1_iterations=7,
        fts_fact_count=15,
    )
    assert res["eo1_iterations_executed"] == 7
    # Each dispatch writes 1 DISPATCH_INTENT + 1 CONTINUITY_RECEIPT = 2 * eo1_iterations_executed JSONL records
    assert res["eo1_ledger_records_persisted"] == 2 * res["eo1_iterations_executed"]
    assert res["eo1_median_latency_ns"] > 0
    assert res["fts_facts_indexed"] == 15
    assert res["fts_hits_returned"] > 0
    assert res["fts_query_latency_ns"] > 0
