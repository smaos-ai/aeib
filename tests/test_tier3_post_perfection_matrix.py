#!/usr/bin/env python3
"""
tests/test_tier3_post_perfection_matrix.py
================================================================================
Test Suite for Tier 3 Post-Perfection SOTA Invariants:
1. Invariant 12: Game-Theoretic Nash Gate (src/nash_equilibrium_gate.py)
2. Invariant 13: TEE CVM Memory Scrubbing (src/tee_cvm_memory_scrubbing.py)
3. Invariant 14: WASM Symbolic Path Explorer (src/wasm_symbolic_path_explorer.py)
4. Invariant 15: Actuarial Multi-Sig Gate (src/actuarial_multisig_gate.py)

Evaluated under the stated model as a pre-production test battery.
Strict zero-mock AST purity enforced.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.nash_equilibrium_gate import (
    NashEquilibriumGate,
    NashGameResult,
)
from src.tee_cvm_memory_scrubbing import (
    TeeCvmEnclaveLifecycle,
    EnclaveState,
    PAGE_SIZE,
)
from src.wasm_symbolic_path_explorer import (
    WasmSymbolicPathExplorer,
    SymbolicViolationType,
    SymbolicExplorationReport,
)
from src.actuarial_multisig_gate import (
    ActuarialMultiSigGate,
    SignerIdentity,
    ActuarialEvaluationResult,
)


# ============================================================================
# 1. INVARIANT 12: GAME-THEORETIC NASH GATE TESTS
# ============================================================================

def test_nash_equilibrium_nominal_and_exploit_detection():
    """Verify minimax equilibrium calculation and exploit detection."""
    gate = NashEquilibriumGate(max_nash_gap=0.05, exploit_threshold=0.5)

    # Nominal matrix: Proposer compliant, low auditor violation payoff
    nominal_matrix = [[0.1, 0.2], [0.2, 0.1]]
    res_nominal = gate.evaluate_tool_proposal("caid-01", "fetch_balance", nominal_matrix)
    assert res_nominal.is_stable is True
    assert res_nominal.rejection_code is None
    assert res_nominal.auditor_detected_exploit is False

    # Exploit matrix: Boundary evasion caught by auditor with high payoff
    exploit_matrix = [[0.1, 0.3], [0.8, 0.9]]
    res_exploit = gate.evaluate_tool_proposal("caid-02", "unauthorized_refund", exploit_matrix)
    assert res_exploit.is_stable is False
    assert res_exploit.rejection_code == "HALT_NASH_AUDITOR_EXPLOIT_DETECTED"
    assert res_exploit.auditor_detected_exploit is True


def test_nash_equilibrium_matrix_validation():
    """Verify matrix dimension checks."""
    gate = NashEquilibriumGate()
    with pytest.raises(ValueError):
        gate.evaluate_tool_proposal("caid-03", "test", [[1.0, 2.0, 3.0]])


# ============================================================================
# 2. INVARIANT 13: TEE CVM MEMORY SCRUBBING TESTS
# ============================================================================

def test_tee_cvm_lifecycle_allocation_and_read():
    """Verify confidential page allocation, reading, and quote generation."""
    enclave = TeeCvmEnclaveLifecycle("enclave-tdx-01", "sha256:binary123")
    assert enclave.state == EnclaveState.ACTIVE

    secret_data = b"CONFIDENTIAL_AGENT_PAYMENT_SECRET"
    enclave.allocate_page(0, secret_data)
    read_back = enclave.read_page(0)
    assert read_back.startswith(secret_data)
    assert len(read_back) == PAGE_SIZE

    quote = enclave.get_attestation_quote()
    assert quote.allocated_page_count == 1
    assert len(quote.tpm_pcr_11) == 64


def test_tee_cvm_hardware_key_shredding_and_memory_scrubbing():
    """Verify that key shredding and memory scrubbing eliminate all residue."""
    enclave = TeeCvmEnclaveLifecycle("enclave-sev-02", "sha256:binary456")
    enclave.allocate_page(0, b"TOP_SECRET_SESSION_TOKEN")
    enclave.allocate_page(1, b"AGENT_TREASURY_ESCROW_KEY")

    # Shred key and scrub pages
    enclave.shred_key_and_scrub_memory()
    assert enclave.state == EnclaveState.SCRUBBED
    assert enclave.verify_clean_state() is True

    # Assert cannot read from shredded enclave
    with pytest.raises(RuntimeError):
        enclave.read_page(0)


def test_tee_cvm_remanence_detection_falsification():
    """Falsification: uncleared memory triggers clean_state failure."""
    enclave = TeeCvmEnclaveLifecycle("enclave-test-03", "sha256:binary789")
    enclave.allocate_page(0, b"UNCLEAN_MEMORY_PAGE")

    # If only key is set to None manually without scrubbing frame
    enclave._ephemeral_key = None
    assert enclave.verify_clean_state() is False, "Uncleared page residue must fail verification"


# ============================================================================
# 3. INVARIANT 14: WASM SYMBOLIC PATH EXPLORER TESTS
# ============================================================================

def test_wasm_symbolic_path_explorer_clean_and_bounds_check():
    """Verify clean tool call exploration in < 50ms."""
    explorer = WasmSymbolicPathExplorer(max_linear_pages=16, max_spend_ceiling_minor=2500_00)

    res = explorer.explore_tool_call(
        "transfer_funds", {"amount_minor": 150_00, "memory_offset": 4096, "length": 128}
    )
    assert res.is_safe is True
    assert res.rejection_code is None
    assert res.exploration_time_ms < 50.0
    assert res.paths_explored >= 2


def test_wasm_symbolic_path_explorer_violations():
    """Verify catches of out-of-bounds, negative spend, and division by zero."""
    explorer = WasmSymbolicPathExplorer(max_linear_pages=16, max_spend_ceiling_minor=2500_00)

    # 1. Out of bounds memory write
    res_mem = explorer.explore_tool_call(
        "write_mem", {"memory_offset": 16 * 65536, "length": 4}
    )
    assert res_mem.is_safe is False
    assert res_mem.rejection_code == "HALT_WASM_SYMBOLIC_PATH_VIOLATION"
    assert any(v.violation_type == SymbolicViolationType.OUT_OF_BOUNDS_MEMORY for v in res_mem.violations)

    # 2. Negative spend attack
    res_neg = explorer.explore_tool_call("charge", {"amount_minor": -50_00})
    assert res_neg.is_safe is False
    assert any(v.violation_type == SymbolicViolationType.NEGATIVE_SPEND for v in res_neg.violations)

    # 3. Spend ceiling breach
    res_ceil = explorer.explore_tool_call("charge", {"amount_minor": 3000_00})
    assert res_ceil.is_safe is False
    assert any(v.violation_type == SymbolicViolationType.ARITHMETIC_OVERFLOW for v in res_ceil.violations)

    # 4. Division by zero
    res_div = explorer.explore_tool_call("calc_ratio", {"divisor": 0})
    assert res_div.is_safe is False
    assert any(v.violation_type == SymbolicViolationType.DIVISION_BY_ZERO for v in res_div.violations)


# ============================================================================
# 4. INVARIANT 15: ACTUARIAL MULTI-SIG GATE TESTS
# ============================================================================

def test_actuarial_multisig_risk_calculation_and_escalation():
    """Verify actuarial risk multipliers and dynamic threshold escalation."""
    gate = ActuarialMultiSigGate(tier_b_threshold_minor=1000_00, tier_c_threshold_minor=5000_00)

    # Low risk: €50 * 1.0 * 1.0 * 1.0 = €50 -> (1, 1)
    score_low = gate.compute_risk_score(50_00, counterparty_risk=1.0, velocity_risk=1.0, taint_tier="TIER_0")
    assert score_low == 5000.0
    req_m, total_n = gate.determine_required_quorum(50_00)
    assert (req_m, total_n) == (1, 1)

    # High risk: €2,000 * 3.0 (unknown payee) * 2.0 (velocity) * 3.0 (TIER_2 taint) = €36,000 -> (3, 5)
    score_high = gate.compute_risk_score(2000_00, counterparty_risk=3.0, velocity_risk=2.0, taint_tier="TIER_2")
    assert score_high == 3600000.0
    req_m_high, total_n_high = gate.determine_required_quorum(score_high)
    assert (req_m_high, total_n_high) == (3, 5)


def test_actuarial_multisig_signature_verification():
    """Verify cryptographic Ed25519 signature threshold verification."""
    gate = ActuarialMultiSigGate()
    payload = b"PAYMENT_INTENT_RFC8785_CANONICAL"

    # Keypairs
    k_agent = Ed25519PrivateKey.generate()
    k_host = Ed25519PrivateKey.generate()
    k_human = Ed25519PrivateKey.generate()

    signers = {
        "agent": SignerIdentity("agent", "AGENT", k_agent.public_key().public_bytes_raw()),
        "host": SignerIdentity("host", "HOST_POLICY_ENGINE", k_host.public_key().public_bytes_raw()),
        "human": SignerIdentity("human", "HUMAN_SUPERVISOR", k_human.public_key().public_bytes_raw()),
    }

    # High risk scenario requiring 3-of-5: provide only 2 valid signatures -> fails closed
    sigs_2 = {
        "agent": k_agent.sign(payload),
        "host": k_host.sign(payload),
    }
    res_fail = gate.evaluate_authorization(
        payload_bytes=payload,
        amount_minor=3000_00,
        signatures=sigs_2,
        registered_signers=signers,
        taint_tier="TIER_2",
    )
    assert res_fail.is_authorized is False
    assert res_fail.required_m == 3
    assert res_fail.rejection_code == "HALT_ACTUARIAL_QUORUM_UNSATISFIED"

    # Provide 3 valid signatures -> succeeds
    sigs_3 = {
        "agent": k_agent.sign(payload),
        "host": k_host.sign(payload),
        "human": k_human.sign(payload),
    }
    res_ok = gate.evaluate_authorization(
        payload_bytes=payload,
        amount_minor=3000_00,
        signatures=sigs_3,
        registered_signers=signers,
        taint_tier="TIER_2",
    )
    assert res_ok.is_authorized is True
    assert res_ok.rejection_code is None


# ============================================================================
# 5. EPISTEMIC & BANNED WORD CHECKS
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
        Path("src/nash_equilibrium_gate.py"),
        Path("src/tee_cvm_memory_scrubbing.py"),
        Path("src/wasm_symbolic_path_explorer.py"),
        Path("src/actuarial_multisig_gate.py"),
        Path("tests/test_tier3_post_perfection_matrix.py"),
    ]
    for filepath in files_to_check:
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8").lower()
            for word in banned:
                assert word not in content, f"Banned word '{word}' found in {filepath}"
