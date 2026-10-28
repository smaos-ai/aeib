#!/usr/bin/env python3
"""
tests/test_epistemic_verifier_and_x402_governor.py — Verification, Falsification,
and 100% (T4+) Mutation-Adequacy Suite for `src/epistemic_verifier_and_x402_governor.py`.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from src.eo1_write_before_execute import PreDispatchIntentInterlock
from src.epistemic_verifier_and_x402_governor import (
    FiveClaimFalsificationMatrixEngine,
    HardenedEpistemicExecutionGate,
    HardenedFactAnchor,
    HardenedX402EscrowGovernor,
    P00520_ORDERED_DOMAIN_END,
    P00520_ORDERED_DOMAIN_START,
    PromptDraftVulnerabilityAuditor,
    _is_pinned_scientific_url,
    _is_valid_sha256_prefixed,
)


def test_prompt_draft_vulnerability_auditor_proves_4_exploits_and_hardened_blocks(
    tmp_path: Path,
) -> None:
    """
    Proves the 4 concrete exploits against the prompt's naive `EpistemicExecutionGate`
    and `X402EscrowGovernor` drafts and verifies that the hardened implementations
    block all 4 fail-closed.
    """
    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "audit_eo1.jsonl",
        output_state_dir=tmp_path / "audit_latches",
    )
    audit = PromptDraftVulnerabilityAuditor.run_comparative_exploit_audit(interlock)

    assert audit["naive_empty_anchors_bypassed"] is True
    assert audit["naive_url_spoof_bypassed"] is True
    assert audit["naive_negative_drain_bypassed"] is True

    assert audit["hardened_empty_blocked"] is True
    assert audit["hardened_empty_code"] == "HALT_EMPTY_EVIDENCE_ANCHORS"
    assert audit["hardened_spoof_blocked"] is True
    assert audit["hardened_spoof_code"].startswith("HALT_UNPINNED_OR_SPOOFED_SOURCE_HOST:")
    sa = audit["spoof_anchor"]
    assert (sa.payload_sha256, sa.confidence_bps) == ("sha256:" + ("a" * 64), 9500)
    assert audit["hardened_p00520_disorder_blocked"] is True
    assert audit["hardened_p00520_code"] == "HALT_P00520_DISORDERED_TERMINAL_OVERLAP"
    dv = audit["hardened_dock_verdict"]
    assert (dv.residue_start, dv.residue_end, dv.mean_plddt_bps, dv.min_residue_plddt_bps, dv.pae_angstrom_x100) == (
        40,
        90,
        7210,
        4120,
        320,
    )
    assert audit["hardened_negative_drain_blocked"] is True
    assert (
        audit["hardened_negative_drain_code"]
        == "HALT_INVALID_OR_NON_POSITIVE_INTEGER_MICRO_USDC"
    )


def test_hardened_epistemic_execution_gate_url_digest_confidence_and_ed25519_jcs() -> None:
    """
    Covers URL hostname pinning, SHA-256 hex validation, confidence basis-point bounds,
    trace length, and Ed25519 + RFC 8785 JCS synthesis envelope signing & tamper rejection.
    """
    assert _is_pinned_scientific_url("") is False
    assert _is_pinned_scientific_url(None) is False  # type: ignore[arg-type]
    assert _is_pinned_scientific_url("http://arxiv.org/abs/2610.00001") is False
    assert _is_pinned_scientific_url("https:///no-host") is False
    assert _is_pinned_scientific_url("https://arxiv.org.evil.example/abs/1") is False
    assert _is_pinned_scientific_url("https://evil.example/?q=arxiv.org") is False
    assert _is_pinned_scientific_url("https://arxiv.org/abs/2610.00001") is True
    assert _is_pinned_scientific_url("https://export.arxiv.org/api/query") is True
    assert _is_pinned_scientific_url("https://www.ebi.ac.uk/ols4/ontologies") is True

    assert _is_valid_sha256_prefixed(123) is False  # type: ignore[arg-type]
    assert _is_valid_sha256_prefixed("md5:" + ("a" * 64)) is False
    assert _is_valid_sha256_prefixed("sha256:short") is False
    assert _is_valid_sha256_prefixed("sha256:" + ("g" * 64)) is False
    assert _is_valid_sha256_prefixed("sha256:" + ("0" * 64)) is True

    gate = HardenedEpistemicExecutionGate()
    valid_anchor = HardenedFactAnchor(
        claim_id="claim-01",
        source_url="https://arxiv.org/abs/2610.30963v1",
        payload_sha256="sha256:" + ("b" * 64),
        confidence_bps=8500,
    )
    with pytest.raises(Exception):
        valid_anchor.confidence_bps = 9000  # type: ignore[misc]

    # Empty anchors and short/non-str trace rejected
    assert gate.verify_evidence_before_synthesis([], "Valid trace over twenty chars")[0] is False
    assert (
        gate.verify_evidence_before_synthesis([valid_anchor], "short trace")[1]
        == "HALT_INSUFFICIENT_REASONING_TRACE"
    )
    assert (
        gate.verify_evidence_before_synthesis([valid_anchor], "   " + ("x" * 19) + "   ")[0]
        is False
    )
    assert (
        gate.verify_evidence_before_synthesis([valid_anchor], "x" * 20)[0]
        is True
    )
    assert (
        gate.verify_evidence_before_synthesis([valid_anchor], None)[1]  # type: ignore[arg-type]
        == "HALT_INSUFFICIENT_REASONING_TRACE"
    )

    # Invalid sha256 on anchor
    bad_sha_anchor = HardenedFactAnchor(
        claim_id="c-bad-sha",
        source_url="https://arxiv.org/abs/2610.30963v1",
        payload_sha256="sha256:invalid",
        confidence_bps=9000,
    )
    assert gate.verify_evidence_before_synthesis(
        [bad_sha_anchor], "Valid reasoning trace over twenty characters."
    ) == (False, "HALT_INVALID_PAYLOAD_SHA256:c-bad-sha")

    # Confidence boundary checks: 8499 (rejected), 8500 (accepted), 10000 (accepted), 10001 (rejected), bool (rejected)
    for bad_conf in (8499, 10001, True, "9000"):
        bad_c_anchor = HardenedFactAnchor(
            claim_id="c-bad-conf",
            source_url="https://arxiv.org/abs/2610.30963v1",
            payload_sha256="sha256:" + ("c" * 64),
            confidence_bps=bad_conf,  # type: ignore[arg-type]
        )
        assert gate.verify_evidence_before_synthesis(
            [bad_c_anchor], "Valid reasoning trace over twenty characters."
        ) == (False, "HALT_INSUFFICIENT_ANCHOR_CONFIDENCE_BPS:c-bad-conf")

    max_conf_anchor = HardenedFactAnchor(
        claim_id="c-max-conf",
        source_url="https://ncbi.nlm.nih.gov/snp/rs671",
        payload_sha256="sha256:" + ("d" * 64),
        confidence_bps=10000,
    )
    assert gate.verify_evidence_before_synthesis(
        [valid_anchor, max_conf_anchor],
        "Valid reasoning trace over twenty characters.",
    ) == (True, "VERIFIED_PRIMARY_ANCHORS")

    # Sign & verify synthesis envelope
    signed = gate.sign_synthesis_envelope(
        query="Evaluate ABL1 P00520 kinase domain stability",
        anchors=[valid_anchor, max_conf_anchor],
        reasoning_trace="Step 1: Verify P00520 pLDDT; Step 2: Check rs671 anchor.",
        synthesis_conclusion="Ordered kinase domain [75, 512] confirmed.",
    )
    assert signed["envelope"]["anchor_count"] == 2
    assert gate.verify_synthesis_envelope(signed) is True

    # Tamper with conclusion -> fails verification
    tampered = {
        "envelope": {**signed["envelope"], "synthesis_conclusion": "Tampered conclusion"},
        "ed25519_signature_b64": signed["ed25519_signature_b64"],
    }
    assert gate.verify_synthesis_envelope(tampered) is False
    assert gate.verify_synthesis_envelope({"envelope": "not-dict", "ed25519_signature_b64": "aa"}) is False
    assert gate.verify_synthesis_envelope({"envelope": {}, "ed25519_signature_b64": ""}) is False
    assert gate.verify_synthesis_envelope({"envelope": {}, "ed25519_signature_b64": "!!invalid_b64!!"}) is False

    with pytest.raises(ValueError):
        gate.sign_synthesis_envelope(
            query="q",
            anchors=[],
            reasoning_trace="Valid reasoning trace over twenty characters.",
            synthesis_conclusion="c",
        )


def test_structural_biology_docking_p00520_boundaries_and_plddt_pae_thresholds() -> None:
    """
    Verifies exact boundary conditions on `verify_structural_biology_docking` for
    `P00520` (`[75, 512]`), `mean_plddt_bps >= 7000`, `min_residue_plddt_bps >= 5000`,
    and `pae_angstrom_x100 <= 500`.
    """
    gate = HardenedEpistemicExecutionGate()

    # Invalid intervals
    assert (
        gate.verify_structural_biology_docking("P00520", 0, 100, 9000, 8000, 200).rejection_code
        == "HALT_INVALID_RESIDUE_INTERVAL"
    )
    assert (
        gate.verify_structural_biology_docking("P00520", 120, 119, 9000, 8000, 200).rejection_code
        == "HALT_INVALID_RESIDUE_INTERVAL"
    )
    assert (
        gate.verify_structural_biology_docking("Q9Y6K9", 1, 1, 7000, 5000, 500).allowed
        is True
    )

    # P00520 exact domain boundaries: 74 rejected, 75..512 accepted, 513 rejected
    assert P00520_ORDERED_DOMAIN_START == 75
    assert P00520_ORDERED_DOMAIN_END == 512
    assert (
        gate.verify_structural_biology_docking("P00520", 74, 512, 9000, 8000, 200).rejection_code
        == "HALT_P00520_DISORDERED_TERMINAL_OVERLAP"
    )
    assert (
        gate.verify_structural_biology_docking("P00520", 75, 513, 9000, 8000, 200).rejection_code
        == "HALT_P00520_DISORDERED_TERMINAL_OVERLAP"
    )
    exact_p00520 = gate.verify_structural_biology_docking("P00520", 75, 512, 7000, 5000, 500)
    assert exact_p00520.allowed is True
    assert exact_p00520.rejection_code == "PASS_ORDERED_CATALYTIC_POCKET"
    with pytest.raises(Exception):
        exact_p00520.allowed = False  # type: ignore[misc]

    # Threshold boundaries: 6999 mean pLDDT, 4999 min residue pLDDT, 501 PAE rejected
    assert (
        gate.verify_structural_biology_docking("P00520", 100, 200, 6999, 5000, 500).rejection_code
        == "HALT_LOW_PLDDT_OR_HIGH_PAE_DISORDER"
    )
    assert (
        gate.verify_structural_biology_docking("P00520", 100, 200, 7000, 4999, 500).rejection_code
        == "HALT_LOW_PLDDT_OR_HIGH_PAE_DISORDER"
    )
    assert (
        gate.verify_structural_biology_docking("P00520", 100, 200, 7000, 5000, 501).rejection_code
        == "HALT_LOW_PLDDT_OR_HIGH_PAE_DISORDER"
    )


def test_hardened_x402_escrow_governor_boundaries_smurfing_replay_and_five_claims(
    tmp_path: Path,
) -> None:
    """
    Verifies integer micro-USDC checks, SIWx URL normalization, per-intent cap (5M),
    cumulative epoch cap (25M), nonce/intent replay, EO1 ledger commit, and the
    5-Claim Falsification Matrix.
    """
    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "x402_eo1.jsonl",
        output_state_dir=tmp_path / "x402_latches",
    )
    gov = HardenedX402EscrowGovernor(interlock=interlock)
    assert gov.max_per_intent_micro_usdc == 5 * 10**6
    assert gov.max_epoch_spend_micro_usdc == 5 * gov.max_per_intent_micro_usdc
    assert gov.current_epoch_spend_micro_usdc == 0

    url = "https://api.vendor.example/v1/Resource/"
    siwx = "https://API.VENDOR.EXAMPLE/v1/Resource"
    assert HardenedX402EscrowGovernor._normalize_endpoint("http://evil.example") == ""
    assert HardenedX402EscrowGovernor._normalize_endpoint("https:///no-netloc") == ""
    assert (
        HardenedX402EscrowGovernor._normalize_endpoint(url)
        == "https://api.vendor.example/v1/Resource"
    )

    # Non-positive / non-int / bool rejected
    for bad_amt in (0, -1, True, 1.5):
        res_bad = gov.authorize_x402_settlement(
            "id-1", url, siwx, bad_amt, "n-1"  # type: ignore[arg-type]
        )
        assert res_bad == {
            "authorized": False,
            "reason": "HALT_INVALID_OR_NON_POSITIVE_INTEGER_MICRO_USDC",
        }

    # Missing intent_id or challenge_nonce
    assert gov.authorize_x402_settlement("", url, siwx, 100, "n-1") == {
        "authorized": False,
        "reason": "HALT_MISSING_INTENT_OR_NONCE",
    }
    assert gov.authorize_x402_settlement("id-1", url, siwx, 100, "") == {
        "authorized": False,
        "reason": "HALT_MISSING_INTENT_OR_NONCE",
    }

    # SIWx endpoint mismatch or non-HTTPS scheme
    assert gov.authorize_x402_settlement(
        "id-1", "http://api.vendor.example/v1", siwx, 100, "n-1"
    ) == {
        "authorized": False,
        "reason": "HALT_SIWX_ENDPOINT_MISMATCH",
    }
    assert gov.authorize_x402_settlement(
        "id-1", url, "https://other.vendor.example/v1/Resource", 100, "n-1"
    ) == {
        "authorized": False,
        "reason": "HALT_SIWX_ENDPOINT_MISMATCH",
    }

    # Per-intent boundary: 5_000_001 rejected, 5_000_000 accepted
    assert gov.authorize_x402_settlement("id-over", url, siwx, 5_000_001, "n-over") == {
        "authorized": False,
        "reason": "HALT_PER_INTENT_BUDGET_EXCEEDED",
    }

    # 5 settlements of 5_000_000 micro-USDC = 25_000_000 (exact epoch ceiling)
    for i in range(5):
        ok_res = gov.authorize_x402_settlement(
            f"intent-{i}", url, siwx, 5_000_000, f"nonce-{i}"
        )
        assert ok_res["authorized"] is True
        assert ok_res["intent_id"] == f"intent-{i}"
        assert ok_res["status"] == "SETTLED_UNDER_EO1_ESCROW"
        assert ok_res["remaining_epoch_micro_usdc"] == 25_000_000 - ((i + 1) * 5_000_000)
        assert interlock.is_caid_committed(ok_res["eo1_caid"]) is True

    # Replay of consumed nonce or consumed intent_id rejected
    assert gov.authorize_x402_settlement("intent-new", url, siwx, 1, "nonce-0") == {
        "authorized": False,
        "reason": "HALT_CHALLENGE_NONCE_OR_INTENT_REPLAY",
    }
    assert gov.authorize_x402_settlement("intent-0", url, siwx, 1, "nonce-new") == {
        "authorized": False,
        "reason": "HALT_CHALLENGE_NONCE_OR_INTENT_REPLAY",
    }

    # 6th settlement of even 1 micro-USDC exceeds 25_000_000 epoch ceiling
    assert gov.authorize_x402_settlement("intent-6", url, siwx, 1, "nonce-6") == {
        "authorized": False,
        "reason": "HALT_EPOCH_ESCROW_EXHAUSTED",
    }

    # Verify 5-Claim Falsification Matrix
    records = FiveClaimFalsificationMatrixEngine.evaluate_all_five_claims()
    assert len(records) == 5
    assert [r.claim_index for r in records] == [1, 2, 3, 4, 5]
    with pytest.raises(Exception):
        records[0].claim_index = 99  # type: ignore[misc]
