#!/usr/bin/env python3
"""
Tests for Omega Containment Suite (tests/test_omega_containment_suite.py):
  1. src/cognitive_friction_gate.py
  2. src/live_killchain_attestor.py
  3. src/temporal_model_bound_token.py
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import time
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519
import pytest

from src.cognitive_friction_gate import (
    CognitiveFrictionGate,
    CriticalActionProposal,
    HumanComprehensionResponse,
)
from src.jcs_canonicalizer import encode_jcs
from src.live_killchain_attestor import (
    LiveKillChainAttestor,
    _has_tunnel_encoding,
)
from src.temporal_model_bound_token import (
    ModelBoundTokenEnvelope,
    ModelBoundTokenValidator,
    SubstrateCustodyManifest,
    SubstrateIntegrityAttestor,
)


def _make_signed_response(
    proposal: CriticalActionProposal,
    priv_key: ed25519.Ed25519PrivateKey,
    operator_id: str = "op_alpha",
    selected_boundary: str | None = None,
    selected_blast: int | None = None,
    acknowledged_risk: str | None = None,
    reading_elapsed_ms: int = 3500,
    override_proposal_caid: str | None = None,
    override_pub_hex: str | None = None,
) -> HumanComprehensionResponse:
    pub_hex = (
        override_pub_hex
        if override_pub_hex is not None
        else priv_key.public_key().public_bytes_raw().hex()
    )
    unsigned = HumanComprehensionResponse(
        proposal_caid=(
            override_proposal_caid
            if override_proposal_caid is not None
            else proposal.proposal_caid()
        ),
        operator_id=operator_id,
        selected_boundary_condition=(
            selected_boundary
            if selected_boundary is not None
            else proposal.exact_boundary_condition
        ),
        selected_blast_radius_records=(
            selected_blast if selected_blast is not None else proposal.blast_radius_records
        ),
        acknowledged_risk=(
            acknowledged_risk
            if acknowledged_risk is not None
            else (
                proposal.counter_arguments_and_risks[0]
                if proposal.counter_arguments_and_risks
                else "placeholder_risk"
            )
        ),
        reading_elapsed_ms=reading_elapsed_ms,
        hardware_biometric_signature_hex="",
        operator_public_key_hex=pub_hex,
    )
    sig_hex = priv_key.sign(unsigned.canonical_signing_payload()).hex()
    return replace(unsigned, hardware_biometric_signature_hex=sig_hex)


def test_critical_action_proposal_validation_and_defaults() -> None:
    default_prop = CriticalActionProposal(
        proposal_id="prop_001",
        target_resource="db://prod/accounts",
        proposed_code_diff="DELETE FROM accounts WHERE inactive = 1;",
        blast_radius_records=0,
        exact_boundary_condition="inactive = 1",
        counter_arguments_and_risks=("Irreversible deletion of dormant rows",),
        distractor_options=("inactive = 0", "all rows"),
    )
    expected_default_ms = 3 * 1000
    assert default_prop.minimum_reading_time_ms == expected_default_ms
    assert default_prop.blast_radius_records == 0
    assert len(default_prop.proposal_caid()) == 64
    with pytest.raises(Exception):
        default_prop.proposal_id = "mutated"  # type: ignore[misc]

    min_floor_prop = CriticalActionProposal(
        proposal_id="prop_002",
        target_resource="db://prod/accounts",
        proposed_code_diff="UPDATE accounts SET locked = 1;",
        blast_radius_records=10,
        exact_boundary_condition="locked = 1",
        counter_arguments_and_risks=("Locks active accounts",),
        distractor_options=("locked = 0",),
        minimum_reading_time_ms=500,
    )
    expected_floor_ms = 5 * 100
    assert min_floor_prop.minimum_reading_time_ms == expected_floor_ms

    with pytest.raises(ValueError, match="blast_radius_records"):
        CriticalActionProposal(
            proposal_id="prop_neg",
            target_resource="res",
            proposed_code_diff="diff",
            blast_radius_records=-1,
            exact_boundary_condition="cond",
            counter_arguments_and_risks=("Valid risk item",),
            distractor_options=(),
        )

    with pytest.raises(ValueError, match="minimum_reading_time_ms"):
        CriticalActionProposal(
            proposal_id="prop_fast",
            target_resource="res",
            proposed_code_diff="diff",
            blast_radius_records=1,
            exact_boundary_condition="cond",
            counter_arguments_and_risks=("Valid risk item",),
            distractor_options=(),
            minimum_reading_time_ms=499,
        )

    with pytest.raises(ValueError, match="proposal_id"):
        CriticalActionProposal(
            proposal_id="   ",
            target_resource="res",
            proposed_code_diff="diff",
            blast_radius_records=1,
            exact_boundary_condition="cond",
            counter_arguments_and_risks=("Valid risk item",),
            distractor_options=(),
        )

    with pytest.raises(ValueError, match="exact_boundary_condition"):
        CriticalActionProposal(
            proposal_id="prop_ok",
            target_resource="res",
            proposed_code_diff="diff",
            blast_radius_records=1,
            exact_boundary_condition="  ",
            counter_arguments_and_risks=("Valid risk item",),
            distractor_options=(),
        )

    with pytest.raises(ValueError, match="max_reviews_per_window"):
        CognitiveFrictionGate(pinned_operator_pubkeys={}, max_reviews_per_window=0)
    gate_min = CognitiveFrictionGate(pinned_operator_pubkeys={}, max_reviews_per_window=1)
    assert gate_min is not None


def test_cognitive_friction_gate_all_halts_and_boundaries() -> None:
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_hex = priv_key.public_key().public_bytes_raw().hex()
    gate = CognitiveFrictionGate(pinned_operator_pubkeys={"op_alpha": pub_hex.upper()})

    # 1. One-sided advocacy: empty tuple and short (<5 char) risk string, vs exact 5-char risk string
    empty_risk_prop = CriticalActionProposal(
        proposal_id="prop_empty_risk",
        target_resource="k8s://prod",
        proposed_code_diff="replicas: 0",
        blast_radius_records=42,
        exact_boundary_condition="replicas == 0",
        counter_arguments_and_risks=(),
        distractor_options=("replicas == 1",),
    )
    resp_empty = _make_signed_response(empty_risk_prop, priv_key)
    with pytest.raises(Exception):
        resp_empty.operator_id = "mutated"  # type: ignore[misc]
    v_empty = gate.verify_human_comprehension(empty_risk_prop, resp_empty)
    with pytest.raises(Exception):
        v_empty.allowed = True  # type: ignore[misc]
    assert v_empty.allowed is False
    assert v_empty.status_code == "HALT_ONESIDED_ADVOCACY"
    assert v_empty.violation_reason == "REASON_MISSING_COUNTER_ARGUMENTS_OR_RISKS"
    assert v_empty.window_reviews_used == 0

    short_risk_prop = replace(empty_risk_prop, counter_arguments_and_risks=("abcd",))
    resp_short = _make_signed_response(short_risk_prop, priv_key)
    v_short = gate.verify_human_comprehension(short_risk_prop, resp_short)
    assert v_short.allowed is False
    assert v_short.status_code == "HALT_ONESIDED_ADVOCACY"

    # Exact 5-char risk string and exact minimum_reading_time_ms boundary (3000 == 3000)
    five_char_prop = replace(empty_risk_prop, counter_arguments_and_risks=("abcde",))
    resp_exact_boundary = _make_signed_response(
        five_char_prop,
        priv_key,
        acknowledged_risk="abcde",
        reading_elapsed_ms=3000,
    )
    v_ok = gate.verify_human_comprehension(five_char_prop, resp_exact_boundary)
    assert v_ok.allowed is True
    assert v_ok.status_code == "ALLOW_VERIFIED_COGNITIVE_COMPREHENSION"
    assert v_ok.violation_reason == "NONE"
    assert v_ok.window_reviews_used == 1
    assert v_ok.max_reviews_per_window == 5

    # 2. Proposal CAID mismatch
    resp_bad_caid = _make_signed_response(
        five_char_prop, priv_key, override_proposal_caid="0" * 64
    )
    v_caid = gate.verify_human_comprehension(five_char_prop, resp_bad_caid)
    assert v_caid.allowed is False
    assert v_caid.status_code == "HALT_PROPOSAL_CAID_MISMATCH"
    assert v_caid.window_reviews_used == 1

    # 3. Untrusted operator / key mismatch
    resp_unknown_op = _make_signed_response(
        five_char_prop, priv_key, operator_id="op_unknown"
    )
    v_unknown = gate.verify_human_comprehension(five_char_prop, resp_unknown_op)
    assert v_unknown.allowed is False
    assert v_unknown.status_code == "HALT_UNTRUSTED_OPERATOR_KEY"

    other_key = ed25519.Ed25519PrivateKey.generate()
    resp_wrong_pub = _make_signed_response(
        five_char_prop,
        other_key,
        operator_id="op_alpha",
        override_pub_hex=other_key.public_key().public_bytes_raw().hex(),
    )
    v_wrong_pub = gate.verify_human_comprehension(five_char_prop, resp_wrong_pub)
    assert v_wrong_pub.allowed is False
    assert v_wrong_pub.status_code == "HALT_UNTRUSTED_OPERATOR_KEY"

    # 4. Rubber-stamp velocity check (2999 < 3000) -> consumes review #2
    resp_fast = _make_signed_response(five_char_prop, priv_key, reading_elapsed_ms=2999)
    v_fast = gate.verify_human_comprehension(five_char_prop, resp_fast)
    assert v_fast.allowed is False
    assert v_fast.status_code == "HALT_METACOGNITIVE_RUBBER_STAMP"
    assert "2999ms < minimum floor 3000ms" in v_fast.violation_reason
    assert v_fast.window_reviews_used == 2

    # 5. Socratic comprehension challenge failures -> reviews #3, #4, #5
    resp_bad_bound = _make_signed_response(
        five_char_prop, priv_key, selected_boundary="replicas == 1"
    )
    v_bound = gate.verify_human_comprehension(five_char_prop, resp_bad_bound)
    assert v_bound.allowed is False
    assert v_bound.status_code == "HALT_COMPREHENSION_CHALLENGE_FAILED"
    assert v_bound.window_reviews_used == 3

    resp_bad_blast = _make_signed_response(
        five_char_prop, priv_key, selected_blast=999
    )
    v_blast = gate.verify_human_comprehension(five_char_prop, resp_bad_blast)
    assert v_blast.allowed is False
    assert v_blast.status_code == "HALT_COMPREHENSION_CHALLENGE_FAILED"
    assert v_blast.window_reviews_used == 4

    resp_bad_risk = _make_signed_response(
        five_char_prop, priv_key, acknowledged_risk="unlisted_risk"
    )
    v_risk = gate.verify_human_comprehension(five_char_prop, resp_bad_risk)
    assert v_risk.allowed is False
    assert v_risk.status_code == "HALT_COMPREHENSION_CHALLENGE_FAILED"
    assert v_risk.window_reviews_used == 5

    # 6. Turan reviewer fatigue quota exceeded on review #6 (> 5)
    resp_sixth = _make_signed_response(five_char_prop, priv_key)
    v_fatigue = gate.verify_human_comprehension(five_char_prop, resp_sixth)
    assert v_fatigue.allowed is False
    assert v_fatigue.status_code == "HALT_REVIEWER_FATIGUE_QUOTA_EXCEEDED"
    assert v_fatigue.violation_reason == "REASON_TURAN_OVERSIGHT_FATIGUE_CAP_REACHED"
    assert v_fatigue.window_reviews_used == 6

    # Reset single operator fatigue window
    gate.reset_fatigue_window("op_alpha")

    # 7. Invalid hardware biometric signature
    tampered_sig_resp = replace(resp_sixth, hardware_biometric_signature_hex="ab" * 64)
    v_bad_sig = gate.verify_human_comprehension(five_char_prop, tampered_sig_resp)
    assert v_bad_sig.allowed is False
    assert v_bad_sig.status_code == "HALT_INVALID_HARDWARE_SIGNATURE"
    assert v_bad_sig.window_reviews_used == 1

    # Reset all operators fatigue window
    gate.reset_fatigue_window()
    v_after_reset = gate.verify_human_comprehension(five_char_prop, resp_sixth)
    assert v_after_reset.allowed is True
    assert v_after_reset.window_reviews_used == 1


def test_live_killchain_attestor_drills_and_boundaries() -> None:
    with pytest.raises(ValueError, match="max_kill_latency_us"):
        LiveKillChainAttestor(max_kill_latency_us=0)
    with pytest.raises(ValueError, match="max_dns_wire_bytes"):
        LiveKillChainAttestor(max_dns_wire_bytes=0)
    with pytest.raises(ValueError, match="max_label_length"):
        LiveKillChainAttestor(max_label_length=0)

    min_attestor = LiveKillChainAttestor(
        max_kill_latency_us=1,
        max_dns_wire_bytes=1,
        max_label_length=1,
    )
    assert min_attestor.circuit_breaker_tripped is False

    attestor = LiveKillChainAttestor(
        allowed_dns_domains=("api.example.com", "database.example.com")
    )
    assert attestor.circuit_breaker_tripped is False

    with pytest.raises(ValueError, match="simulated_delay_us"):
        attestor.execute_live_kill_drill("drill_neg", simulated_delay_us=-1)

    # Nominal live SIGKILL drill
    receipt = attestor.execute_live_kill_drill("drill_nominal")
    with pytest.raises(Exception):
        receipt.drill_id = "mutated"  # type: ignore[misc]
    expected_default_sla_us = 15 * 1000
    assert receipt.max_allowed_latency_us == expected_default_sla_us
    assert receipt.process_verified_dead is True
    assert receipt.passed_sla is True
    assert receipt.system_state == "NOMINAL_KILL_PATH_VERIFIED"
    assert attestor.circuit_breaker_tripped is False

    # Verify Ed25519 signature over canonical JCS payload
    expected_payload = {
        "canary_pid": receipt.canary_pid,
        "drill_id": "drill_nominal",
        "max_allowed_latency_us": receipt.max_allowed_latency_us,
        "passed_sla": True,
        "process_verified_dead": True,
        "system_state": "NOMINAL_KILL_PATH_VERIFIED",
        "termination_latency_us": receipt.termination_latency_us,
    }
    canonical_bytes = encode_jcs(expected_payload)
    assert receipt.receipt_caid == hashlib.sha256(canonical_bytes).hexdigest()
    attestor.public_key.verify(bytes.fromhex(receipt.signature_hex), canonical_bytes)

    # Exact SLA boundary and deterministic microsecond division (15_000_000 ns // 1000 == 15_000 us)
    ticks = iter([1_000_000, 16_000_000])
    det_attestor = LiveKillChainAttestor(
        max_kill_latency_us=15_000,
        clock_ns=lambda: next(ticks),
    )
    det_receipt = det_attestor.execute_live_kill_drill("drill_boundary", simulated_delay_us=0)
    assert det_receipt.termination_latency_us == expected_default_sla_us
    assert det_receipt.passed_sla is True
    assert det_attestor.circuit_breaker_tripped is False

    # Breach SLA via simulated_delay_us=25_000 -> trips circuit breaker and freezes DNS
    breach_attestor = LiveKillChainAttestor(
        max_kill_latency_us=15_000,
        allowed_dns_domains=("api.example.com",),
    )
    breach_receipt = breach_attestor.execute_live_kill_drill("drill_breach", simulated_delay_us=25_000)
    assert breach_receipt.termination_latency_us > expected_default_sla_us
    assert breach_receipt.passed_sla is False
    assert breach_receipt.system_state == "HALT_SYSTEM_FROZEN_KILL_PATH_FAILED"
    assert breach_attestor.circuit_breaker_tripped is True

    # Also verify exact +1us breach boundary (15_001 > 15_000)
    breach_ticks = iter([0, 15_001_000])
    exact_breach_attestor = LiveKillChainAttestor(
        max_kill_latency_us=15_000,
        clock_ns=lambda: next(breach_ticks),
    )
    exact_breach_receipt = exact_breach_attestor.execute_live_kill_drill("drill_exact_breach")
    expected_breach_us = 15 * 1000 + 1
    assert exact_breach_receipt.termination_latency_us == expected_breach_us
    assert exact_breach_receipt.passed_sla is False
    assert exact_breach_attestor.circuit_breaker_tripped is True

    frozen_dns = breach_attestor.inspect_dns_query("api.example.com", "A", 64)
    assert frozen_dns.allowed is False
    assert frozen_dns.status_code == "HALT_CIRCUIT_BREAKER_FROZEN"


def test_dns_tunneling_firewall_rules_and_boundaries() -> None:
    # Check tunnel encoding helper exact boundaries:
    # len == 7 all consonants -> False; len == 8 all consonants -> True
    assert _has_tunnel_encoding(["bcdfghj"]) is False
    assert _has_tunnel_encoding(["bcdfghjk"]) is True
    # len == 10: 7 non-vowels (7*5=35 < 40) -> False; 8 non-vowels (8*5=40 >= 40) -> True
    assert _has_tunnel_encoding(["bcdfghjaei"]) is False
    assert _has_tunnel_encoding(["bcdfghjlae"]) is True

    exact_24_label = "a" * 24
    over_25_label = "a" * 25
    attestor = LiveKillChainAttestor(
        allowed_dns_domains=(
            "api.example.com",
            "database.example.com",
            f"{exact_24_label}.example.com",
        ),
    )

    # Forbidden record types
    for bad_type in ("TXT", "NULL", "CNAME", "MX"):
        v_type = attestor.inspect_dns_query("api.example.com", bad_type, 64)
        assert v_type.allowed is False
        assert v_type.status_code == "HALT_DNS_TUNNEL_RECORD_TYPE_FORBIDDEN"

    # Wire bytes boundary: 128 allowed, 129 blocked
    v_128 = attestor.inspect_dns_query("api.example.com", "A", 128)
    with pytest.raises(Exception):
        v_128.allowed = False  # type: ignore[misc]
    assert v_128.allowed is True
    assert v_128.status_code == "ALLOW_DNS_QUERY_CLEAN"
    assert v_128.wire_bytes_len == 128

    v_empty_dom = attestor.inspect_dns_query("   ", "A", 64)
    assert v_empty_dom.allowed is False
    assert v_empty_dom.max_label_len == 0

    v_aaaa = attestor.inspect_dns_query("database.example.com.", "aaaa", 96)
    assert v_aaaa.allowed is True
    assert v_aaaa.status_code == "ALLOW_DNS_QUERY_CLEAN"
    assert v_aaaa.record_type == "AAAA"

    v_129 = attestor.inspect_dns_query("api.example.com", "A", 129)
    assert v_129.allowed is False
    assert v_129.status_code == "HALT_DNS_PACKET_OVERSIZE"

    # Label length boundary: 24 allowed, 25 blocked
    v_lbl_24 = attestor.inspect_dns_query(f"{exact_24_label}.example.com", "A", 64)
    assert v_lbl_24.allowed is True
    assert v_lbl_24.max_label_len == 24

    v_lbl_25 = attestor.inspect_dns_query(f"{over_25_label}.example.com", "A", 64)
    assert v_lbl_25.allowed is False
    assert v_lbl_25.status_code == "HALT_DNS_SUBDOMAIN_TUNNEL_DETECTED"
    assert v_lbl_25.max_label_len == 25

    # Hex / high-consonant tunnel label <= 24 chars blocked
    v_hex_tunnel = attestor.inspect_dns_query("4a6f686e31323334.example.com", "A", 64)
    assert v_hex_tunnel.allowed is False
    assert v_hex_tunnel.status_code == "HALT_DNS_SUBDOMAIN_TUNNEL_DETECTED"

    # Non-allowlisted clean domain blocked
    v_unlisted = attestor.inspect_dns_query("evil.example.org", "A", 64)
    assert v_unlisted.allowed is False
    assert v_unlisted.status_code == "HALT_DNS_DOMAIN_NOT_ALLOWLISTED"


def test_substrate_integrity_attestor_and_model_bound_tokens() -> None:
    # 1. SubstrateIntegrityAttestor tiers
    m_failed_canary = SubstrateCustodyManifest(
        model_id="m1",
        weights_sha256="ab" * 32,
        training_corpus_custody_verified=True,
        behavioral_canary_suite_passed=False,
        fine_tune_lineage_signed=True,
    )
    with pytest.raises(Exception):
        m_failed_canary.model_id = "mutated"  # type: ignore[misc]
    assert SubstrateIntegrityAttestor.evaluate_substrate(m_failed_canary) == (
        False,
        "HALT_SUBSTRATE_CANARY_OR_DIGEST_FAILED",
    )

    m_empty_digest = replace(
        m_failed_canary, behavioral_canary_suite_passed=True, weights_sha256="   "
    )
    assert SubstrateIntegrityAttestor.evaluate_substrate(m_empty_digest) == (
        False,
        "HALT_SUBSTRATE_CANARY_OR_DIGEST_FAILED",
    )

    m_verified = replace(m_failed_canary, behavioral_canary_suite_passed=True)
    assert SubstrateIntegrityAttestor.evaluate_substrate(m_verified) == (
        True,
        "VERIFIED_CUSTODY_SUBSTRATE",
    )

    m_unverified_corpus = replace(m_verified, training_corpus_custody_verified=False)
    assert SubstrateIntegrityAttestor.evaluate_substrate(m_unverified_corpus) == (
        True,
        "CONDITIONAL_PASS_SUBSTRATE_UNVERIFIED",
    )

    m_unsigned_ft = replace(m_verified, fine_tune_lineage_signed=False)
    assert SubstrateIntegrityAttestor.evaluate_substrate(m_unsigned_ft) == (
        True,
        "CONDITIONAL_PASS_SUBSTRATE_UNVERIFIED",
    )

    # 2. ModelBoundTokenValidator issuance & boundary validations
    ext_key = ed25519.Ed25519PrivateKey.generate()
    ext_pub_hex = ext_key.public_key().public_bytes_raw().hex().upper()
    validator = ModelBoundTokenValidator(trusted_issuer_pubkeys=[ext_pub_hex])

    with pytest.raises(ValueError, match="ttl_sec"):
        validator.issue_token(
            token_id="t_bad_ttl",
            subject_agent_id="agent_1",
            allowed_tools=("read_file",),
            model_artifact_digest="sha256:model_v1",
            system_prompt_caid="sha256:prompt_v1",
            repo_commit_caid="sha256:repo_v1",
            issued_at_epoch_sec=1000,
            ttl_sec=0,
            max_invocations=1,
        )

    with pytest.raises(ValueError, match="max_invocations"):
        validator.issue_token(
            token_id="t_bad_inv",
            subject_agent_id="agent_1",
            allowed_tools=("read_file",),
            model_artifact_digest="sha256:model_v1",
            system_prompt_caid="sha256:prompt_v1",
            repo_commit_caid="sha256:repo_v1",
            issued_at_epoch_sec=1000,
            ttl_sec=60,
            max_invocations=0,
        )

    raw_env = ModelBoundTokenEnvelope(
        token_id="tok_raw",
        subject_agent_id="agent_1",
        allowed_tools=("read_file",),
        model_artifact_digest="sha256:model_v1",
        system_prompt_caid="sha256:prompt_v1",
        repo_commit_caid="sha256:repo_v1",
        issued_at_epoch_sec=1000,
        expires_at_epoch_sec=1001,
        max_invocations=1,
    )
    assert raw_env.substrate_custody_verified is True
    with pytest.raises(Exception):
        raw_env.token_id = "mutated"  # type: ignore[misc]

    min_tok = validator.issue_token(
        token_id="tok_min",
        subject_agent_id="agent_1",
        allowed_tools=("read_file",),
        model_artifact_digest="sha256:model_v1",
        system_prompt_caid="sha256:prompt_v1",
        repo_commit_caid="sha256:repo_v1",
        issued_at_epoch_sec=1000,
        ttl_sec=1,
        max_invocations=1,
    )
    assert min_tok.expires_at_epoch_sec == 1001

    token = validator.issue_token(
        token_id="tok_01",
        subject_agent_id="agent_1",
        allowed_tools=("read_file", "run_query"),
        model_artifact_digest="sha256:model_v1",
        system_prompt_caid="sha256:prompt_v1",
        repo_commit_caid="sha256:repo_v1",
        issued_at_epoch_sec=1000,
        ttl_sec=300,
        max_invocations=2,
    )
    assert token.expires_at_epoch_sec == 1300
    assert token.substrate_custody_verified is True

    # Premature timestamp (999 < 1000) and exact issued_at boundary (1000)
    v_early = validator.validate_token(
        token,
        requested_tool="read_file",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=999,
    )
    with pytest.raises(Exception):
        v_early.allowed = True  # type: ignore[misc]
    assert v_early.allowed is False
    assert v_early.status_code == "HALT_TOKEN_TTL_EXPIRED"
    assert v_early.remaining_invocations == 0

    # Exact expiry boundary (1300 >= 1300) -> expired
    v_expired = validator.validate_token(
        token,
        requested_tool="read_file",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1300,
    )
    assert v_expired.allowed is False
    assert v_expired.status_code == "HALT_TOKEN_TTL_EXPIRED"
    assert v_expired.remaining_invocations == 0

    # Out-of-scope tool
    v_tool = validator.validate_token(
        token,
        requested_tool="drop_table",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1000,
    )
    assert v_tool.allowed is False
    assert v_tool.status_code == "HALT_TOOL_OUT_OF_SCOPE"
    assert v_tool.remaining_invocations == 0

    # Valid invocation #1 (at exact issued_at=1000) and #2 (at 1299 = expires_at - 1)
    v_ok1 = validator.validate_token(
        token,
        requested_tool="read_file",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1000,
    )
    assert v_ok1.allowed is True
    assert v_ok1.status_code == "ALLOW_MODEL_BOUND_EXECUTION"
    assert v_ok1.substrate_trust_tier == "VERIFIED_CUSTODY_SUBSTRATE"
    assert v_ok1.remaining_invocations == 1

    v_ok2 = validator.validate_token(
        token,
        requested_tool="run_query",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1299,
    )
    assert v_ok2.allowed is True
    assert v_ok2.remaining_invocations == 0

    # Invocation #3 -> quota exhausted
    v_quota = validator.validate_token(
        token,
        requested_tool="read_file",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1299,
    )
    assert v_quota.allowed is False
    assert v_quota.status_code == "HALT_INVOCATION_QUOTA_EXHAUSTED"
    assert v_quota.remaining_invocations == 0

    # Conditional pass token (substrate_custody_verified=False)
    cond_token = validator.issue_token(
        token_id="tok_cond",
        subject_agent_id="agent_1",
        allowed_tools=("read_file",),
        model_artifact_digest="sha256:model_v1",
        system_prompt_caid="sha256:prompt_v1",
        repo_commit_caid="sha256:repo_v1",
        issued_at_epoch_sec=1000,
        ttl_sec=300,
        max_invocations=2,
        substrate_custody_verified=False,
    )
    v_cond = validator.validate_token(
        cond_token,
        requested_tool="read_file",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1100,
    )
    assert v_cond.allowed is True
    assert v_cond.status_code == "CONDITIONAL_PASS_SUBSTRATE_UNVERIFIED"
    assert v_cond.substrate_trust_tier == "CONDITIONAL_PASS_SUBSTRATE_UNVERIFIED"

    # Explicit revocation
    validator.revoke_token(cond_token.token_caid())
    v_rev = validator.validate_token(
        cond_token,
        requested_tool="read_file",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1100,
    )
    assert v_rev.allowed is False
    assert v_rev.status_code == "HALT_TOKEN_REVOKED"
    assert v_rev.remaining_invocations == 0

    # Untrusted issuer & invalid signature
    rogue_key = ed25519.Ed25519PrivateKey.generate()
    rogue_validator = ModelBoundTokenValidator(issuer_signing_key=rogue_key)
    rogue_token = rogue_validator.issue_token(
        token_id="tok_rogue",
        subject_agent_id="agent_1",
        allowed_tools=("read_file",),
        model_artifact_digest="sha256:model_v1",
        system_prompt_caid="sha256:prompt_v1",
        repo_commit_caid="sha256:repo_v1",
        issued_at_epoch_sec=1000,
        ttl_sec=300,
        max_invocations=1,
    )
    v_untrusted = validator.validate_token(
        rogue_token,
        requested_tool="read_file",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1100,
    )
    assert v_untrusted.allowed is False
    assert v_untrusted.status_code == "HALT_INVALID_TOKEN_SIGNATURE"
    assert v_untrusted.remaining_invocations == 0

    bad_sig_token = replace(token, token_id="tok_forged")
    v_bad_sig = validator.validate_token(
        bad_sig_token,
        requested_tool="read_file",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1100,
    )
    assert v_bad_sig.allowed is False
    assert v_bad_sig.status_code == "HALT_INVALID_TOKEN_SIGNATURE"
    assert v_bad_sig.remaining_invocations == 0

    # Model mutation, system prompt drift, and repo state drift (each auto-revokes token)
    tok_m = validator.issue_token(
        token_id="tok_m",
        subject_agent_id="agent_1",
        allowed_tools=("read_file",),
        model_artifact_digest="sha256:model_v1",
        system_prompt_caid="sha256:prompt_v1",
        repo_commit_caid="sha256:repo_v1",
        issued_at_epoch_sec=1000,
        ttl_sec=300,
        max_invocations=2,
    )
    v_m = validator.validate_token(
        tok_m,
        requested_tool="read_file",
        live_model_digest="sha256:model_v2_mutated",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1100,
    )
    assert v_m.allowed is False
    assert v_m.status_code == "HALT_MODEL_MUTATED"
    assert v_m.remaining_invocations == 0
    # Subsequent call sees HALT_TOKEN_REVOKED
    v_m_after = validator.validate_token(
        tok_m,
        requested_tool="read_file",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1100,
    )
    assert v_m_after.status_code == "HALT_TOKEN_REVOKED"
    assert v_m_after.remaining_invocations == 0

    tok_p = validator.issue_token(
        token_id="tok_p",
        subject_agent_id="agent_1",
        allowed_tools=("read_file",),
        model_artifact_digest="sha256:model_v1",
        system_prompt_caid="sha256:prompt_v1",
        repo_commit_caid="sha256:repo_v1",
        issued_at_epoch_sec=1000,
        ttl_sec=300,
        max_invocations=2,
    )
    v_p = validator.validate_token(
        tok_p,
        requested_tool="read_file",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_drifted",
        live_repo_commit_caid="sha256:repo_v1",
        current_epoch_sec=1100,
    )
    assert v_p.allowed is False
    assert v_p.status_code == "HALT_SYSTEM_PROMPT_DRIFT"
    assert v_p.remaining_invocations == 0

    tok_r = validator.issue_token(
        token_id="tok_r",
        subject_agent_id="agent_1",
        allowed_tools=("read_file",),
        model_artifact_digest="sha256:model_v1",
        system_prompt_caid="sha256:prompt_v1",
        repo_commit_caid="sha256:repo_v1",
        issued_at_epoch_sec=1000,
        ttl_sec=300,
        max_invocations=2,
    )
    v_r = validator.validate_token(
        tok_r,
        requested_tool="read_file",
        live_model_digest="sha256:model_v1",
        live_system_prompt_caid="sha256:prompt_v1",
        live_repo_commit_caid="sha256:repo_dirty",
        current_epoch_sec=1100,
    )
    assert v_r.allowed is False
    assert v_r.status_code == "HALT_REPO_STATE_DRIFT"
    assert v_r.remaining_invocations == 0
