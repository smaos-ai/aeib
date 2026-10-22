#!/usr/bin/env python3
# File: tests/test_planetary_clearinghouse_and_tee_swarm.py
"""
Verification suite for `src/planetary_clearinghouse_and_tee_swarm.py`:
- Pillar 1: Planetary Agent Clearinghouse & DvP Economic Settlement
- Pillar 2: Confidential TEE Swarm Remote Attestation & Context Protection
- Pillar 3: Inductive Lean 4 / TLA+ Formal Verification Kernel
"""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.planetary_clearinghouse_and_tee_swarm import (
    ConfidentialTeeSwarmAttestationEngine,
    HardwareAttestationQuote,
    Lean4TlaFormalVerificationKernel,
    PlanetaryAgentClearinghouse,
    canonical_jcs,
    sha256_prefixed,
)


def test_planetary_clearinghouse_eas_and_dvp_settlement() -> None:
    ch_priv = Ed25519PrivateKey.generate()
    clearinghouse = PlanetaryAgentClearinghouse(ch_priv)

    # 1. Reject trade with EAS below 8000 bps (Lemon market protection)
    r_eas_bad = clearinghouse.register_and_escrow_trade(
        deliverable_id="deliv-01",
        seller_agent_did="did:aeib:seller:agent-1",
        buyer_agent_did="did:aeib:buyer:agent-2",
        deliverable_hash=sha256_prefixed(b"valid_payload"),
        settlement_amount_minor=10000,
        eas_score_bps=6500,  # Below 8000 bps floor
    )
    assert r_eas_bad["allowed"] is False
    assert r_eas_bad["halt_code"] == "HALT_CLEARINGHOUSE_EAS_ALIGNMENT_INSUFFICIENT"

    # 2. Reject trade when buyer has insufficient collateral
    r_insolvent = clearinghouse.register_and_escrow_trade(
        deliverable_id="deliv-02",
        seller_agent_did="did:aeib:seller:agent-1",
        buyer_agent_did="did:aeib:buyer:agent-2",
        deliverable_hash=sha256_prefixed(b"valid_payload"),
        settlement_amount_minor=50000,
        eas_score_bps=9500,
    )
    assert r_insolvent["allowed"] is False
    assert r_insolvent["halt_code"] == "HALT_CLEARINGHOUSE_BUYER_INSOLVENT"

    # 3. Deposit collateral, escrow trade, and settle DvP successfully
    clearinghouse.deposit_collateral("did:aeib:buyer:agent-2", 100000)
    artifact_data = b"formal_audit_report_and_code_bundle_v1"
    expected_hash = sha256_prefixed(artifact_data)

    r_escrow = clearinghouse.register_and_escrow_trade(
        deliverable_id="deliv-03",
        seller_agent_did="did:aeib:seller:agent-1",
        buyer_agent_did="did:aeib:buyer:agent-2",
        deliverable_hash=expected_hash,
        settlement_amount_minor=45000,
        eas_score_bps=9800,
    )
    assert r_escrow["allowed"] is True
    assert r_escrow["status"] == "ESCROWED"

    # Settle with matching artifact bytes -> Atomic delivery vs payment
    r_settle = clearinghouse.settle_dvp_deliverable("deliv-03", artifact_data)
    assert r_settle["settled"] is True
    assert r_settle["payload"]["settled_amount_minor"] == 45000

    # 4. Settle with fraudulent / mismatched deliverable -> revert escrow
    clearinghouse.register_and_escrow_trade(
        deliverable_id="deliv-04",
        seller_agent_did="did:aeib:seller:agent-1",
        buyer_agent_did="did:aeib:buyer:agent-2",
        deliverable_hash=expected_hash,
        settlement_amount_minor=20000,
        eas_score_bps=9000,
    )
    r_mismatch = clearinghouse.settle_dvp_deliverable("deliv-04", b"tampered_deliverable_bytes")
    assert r_mismatch["settled"] is False
    assert r_mismatch["halt_code"] == "HALT_CLEARINGHOUSE_DELIVERABLE_HASH_MISMATCH"


def test_confidential_tee_swarm_attestation_and_inter_agent_exchange() -> None:
    mfg_priv = Ed25519PrivateKey.generate()
    mfg_pub = mfg_priv.public_key()
    pinned_mrenclaves = frozenset(
        {
            "sha384:pinned_intel_tdx_aeib_enclave_measurement_v1",
            "sha384:pinned_amd_sev_snp_aeib_enclave_measurement_v1",
        }
    )
    engine = ConfidentialTeeSwarmAttestationEngine(mfg_pub, pinned_mrenclaves)

    agent1_priv = Ed25519PrivateKey.generate()
    agent1_pub = agent1_priv.public_key()
    agent1_pub_bytes = agent1_pub.public_bytes_raw()

    agent2_priv = Ed25519PrivateKey.generate()
    agent2_pub = agent2_priv.public_key()
    agent2_pub_bytes = agent2_pub.public_bytes_raw()

    # 1. Admit Agent 1 on Intel TDX with matching REPORT_DATA
    q1_body = {
        "measurement_mrenclave": "sha384:pinned_intel_tdx_aeib_enclave_measurement_v1",
        "platform_svn": 5,
        "report_data_binding": sha256_prefixed(agent1_pub_bytes),
        "tee_architecture": "INTEL_TDX",
    }
    q1_sig = base64.b64encode(mfg_priv.sign(canonical_jcs(q1_body))).decode("ascii")
    q1 = HardwareAttestationQuote(
        tee_architecture="INTEL_TDX",
        measurement_mrenclave="sha384:pinned_intel_tdx_aeib_enclave_measurement_v1",
        report_data_binding=sha256_prefixed(agent1_pub_bytes),
        platform_svn=5,
        hardware_signature_b64=q1_sig,
    )
    r1 = engine.verify_and_admit_confidential_agent("did:aeib:agent:cvm-1", agent1_pub_bytes, q1)
    assert r1["admitted"] is True

    # 2. Reject quote with mismatched REPORT_DATA (Attacker trying to use another CVM's quote)
    q2_bad_binding = HardwareAttestationQuote(
        tee_architecture="INTEL_TDX",
        measurement_mrenclave="sha384:pinned_intel_tdx_aeib_enclave_measurement_v1",
        report_data_binding=sha256_prefixed(b"some_other_key"),
        platform_svn=5,
        hardware_signature_b64=q1_sig,
    )
    r_bad_bind = engine.verify_and_admit_confidential_agent(
        "did:aeib:agent:cvm-2", agent2_pub_bytes, q2_bad_binding
    )
    assert r_bad_bind["admitted"] is False
    assert r_bad_bind["halt_code"] == "HALT_TEE_REPORT_DATA_KEY_BINDING_MISMATCH"

    # 3. Admit Agent 2 on AMD SEV-SNP
    q2_body = {
        "measurement_mrenclave": "sha384:pinned_amd_sev_snp_aeib_enclave_measurement_v1",
        "platform_svn": 6,
        "report_data_binding": sha256_prefixed(agent2_pub_bytes),
        "tee_architecture": "AMD_SEV_SNP",
    }
    q2_sig = base64.b64encode(mfg_priv.sign(canonical_jcs(q2_body))).decode("ascii")
    q2 = HardwareAttestationQuote(
        tee_architecture="AMD_SEV_SNP",
        measurement_mrenclave="sha384:pinned_amd_sev_snp_aeib_enclave_measurement_v1",
        report_data_binding=sha256_prefixed(agent2_pub_bytes),
        platform_svn=6,
        hardware_signature_b64=q2_sig,
    )
    r2 = engine.verify_and_admit_confidential_agent("did:aeib:agent:cvm-2", agent2_pub_bytes, q2)
    assert r2["admitted"] is True

    # 4. Context exchange between attested CVM-1 and CVM-2 is permitted
    x_ok = engine.verify_inter_agent_context_share("did:aeib:agent:cvm-1", "did:aeib:agent:cvm-2")
    assert x_ok["allowed"] is True

    # 5. Context exchange with un-attested rogue node is blocked
    x_bad = engine.verify_inter_agent_context_share("did:aeib:agent:cvm-1", "did:aeib:agent:rogue-99")
    assert x_bad["allowed"] is False
    assert x_bad["halt_code"] == "HALT_TEE_SWARM_UNATTESTED_PEER_EXCHANGE"


def test_lean4_tla_formal_verification_kernel_inductive_proof() -> None:
    kernel_priv = Ed25519PrivateKey.generate()

    # Define inductive invariant: Solvency & Non-Negative Balance
    # I(s) <=> (balance >= 0 and reserved >= 0 and balance + reserved == 1000)
    def _invariant(s: Dict[str, int]) -> bool:
        return (
            s.get("balance", -1) >= 0
            and s.get("reserved", -1) >= 0
            and s.get("balance", 0) + s.get("reserved", 0) == 1000
        )

    # State transition relation
    def _transition(s: Dict[str, int], action: str, args: Dict[str, int]) -> Dict[str, int]:
        amt = args.get("amount", 0)
        if action == "RESERVE":
            if s["balance"] < amt:
                raise ValueError("Insufficient balance")
            return {"balance": s["balance"] - amt, "reserved": s["reserved"] + amt}
        elif action == "RELEASE":
            if s["reserved"] < amt:
                raise ValueError("Insufficient reserved funds")
            return {"balance": s["balance"] + amt, "reserved": s["reserved"] - amt}
        raise ValueError(f"Unknown action: {action}")

    kernel = Lean4TlaFormalVerificationKernel(
        invariant_predicate=_invariant,
        transition_relation=_transition,
        proof_kernel_privkey=kernel_priv,
    )

    initial = {"balance": 1000, "reserved": 0}

    # 1. Valid trajectory satisfies inductive invariant throughout
    valid_steps = [
        ("RESERVE", {"amount": 300}),
        ("RESERVE", {"amount": 200}),
        ("RELEASE", {"amount": 100}),
    ]
    r_proof = kernel.verify_inductive_trajectory("traj-001", initial, valid_steps)
    assert r_proof["verified"] is True
    assert r_proof["certificate"]["steps_proven"] == 3
    assert "signature_b64" in r_proof

    # 2. Invalid trajectory violating balance solvency halts
    invalid_steps = [
        ("RESERVE", {"amount": 1500}),  # Attempts to overdraw
    ]
    r_bad = kernel.verify_inductive_trajectory("traj-002", initial, invalid_steps)
    assert r_bad["verified"] is False
    assert r_bad["halt_code"] == "HALT_FORMAL_KERNEL_TRANSITION_UNDEFINED"


def test_banned_words_absence() -> None:
    banned = [
        "guaran" + "teed",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "im" + "mune",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
    ]
    for path_str in [
        "src/planetary_clearinghouse_and_tee_swarm.py",
        "tests/test_planetary_clearinghouse_and_tee_swarm.py",
    ]:
        text = Path(path_str).read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in text, f"Forbidden term '{word}' found in {path_str}"
