"""
Unit and falsification tests for AEIB Commercial Pilot Runner & Simulation Harness.
Verifies Patterns A, B, and C under declared synthetic evaluation harness.
Zero-mock Ed25519 cryptography, strict RFC 8785 JCS canonicalization.
"""

import json
import pytest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from tools.aeib_pilot_runner import (
    AeibPilotRunner,
    PilotConfig,
    PilotStage,
    PilotDisposition,
)
from src.jcs_canonicalizer import encode_jcs


@pytest.fixture
def pilot_setup(tmp_path):
    config = PilotConfig(
        pilot_id="test-pilot-enterprise-01",
        action_class="refund_customer",
        target_endpoint="https://api.testbank.com/v1/refunds",
        allowed_uri_prefixes=["https://api.testbank.com/v1/"],
        pinned_mcp_version="2025-06-18",
        active_policy_epoch=1,
        max_amount_minor_units=10000,
        supported_currencies=["EUR", "CZK"],
    )
    runner = AeibPilotRunner(config)
    return runner, tmp_path


def test_week1_scoping_stage(pilot_setup):
    runner, _ = pilot_setup
    runner.set_stage(PilotStage.WEEK1_SCOPING)

    res = runner.evaluate_candidate_action({
        "action_id": "act-01",
        "mcp_version": "2025-06-18",
        "target_uri": "https://api.testbank.com/v1/refunds",
        "policy_epoch": 1,
        "ticket_id": "ticket-01",
        "parameters": {"amount_minor_units": 500, "currency": "EUR"},
    })
    assert res.stage == PilotStage.WEEK1_SCOPING
    assert res.disposition == PilotDisposition.SCOPED
    assert res.allowed_to_dispatch is True
    assert res.connections_accepted == 1


def test_week2_shadow_mode_passive_observation(pilot_setup):
    """
    Pattern A Week 2 constraint:
    Shadow mode measures decisions and hypothetical blocks (WOULD_BLOCK)
    WITHOUT preventing live execution.
    """
    runner, _ = pilot_setup
    runner.set_stage(PilotStage.WEEK2_SHADOW)

    # Valid action
    valid_res = runner.evaluate_candidate_action({
        "action_id": "act-shadow-valid",
        "mcp_version": "2025-06-18",
        "target_uri": "https://api.testbank.com/v1/refunds",
        "policy_epoch": 1,
        "ticket_id": "ticket-shadow-01",
        "parameters": {"amount_minor_units": 1000, "currency": "EUR"},
    })
    assert valid_res.disposition == PilotDisposition.ALLOWED
    assert valid_res.allowed_to_dispatch is True

    # Out-of-policy action: stale epoch & excessive amount
    stale_res = runner.evaluate_candidate_action({
        "action_id": "act-shadow-stale",
        "mcp_version": "2025-06-18",
        "target_uri": "https://api.testbank.com/v1/refunds",
        "policy_epoch": 999,  # Stale epoch
        "ticket_id": "ticket-shadow-02",
        "parameters": {"amount_minor_units": 999999, "currency": "EUR"},
    })
    assert stale_res.disposition == PilotDisposition.WOULD_BLOCK
    # CRITICAL: live execution allowed in passive shadow mode!
    assert stale_res.allowed_to_dispatch is True
    assert stale_res.connections_accepted == 1
    assert stale_res.restraint_record is not None
    assert stale_res.restraint_record["record_type"] == "HYPOTHETICAL_RESTRAINT_RECORD"
    assert stale_res.restraint_record["live_execution_permitted"] is True


def test_week3_active_enforce_blocks_pre_dispatch(pilot_setup):
    """
    Pattern B: Pre-Execution Restraint Records prove 0 egress bytes.
    """
    runner, _ = pilot_setup
    runner.set_stage(PilotStage.WEEK3_ENFORCE)

    # Attempt unauthorized destination URI
    blocked_res = runner.evaluate_candidate_action({
        "action_id": "act-enforce-blocked",
        "mcp_version": "2025-06-18",
        "target_uri": "https://unauthorized.target.org/leak",
        "policy_epoch": 1,
        "ticket_id": "ticket-enforce-01",
        "parameters": {"amount_minor_units": 100, "currency": "EUR"},
    })
    assert blocked_res.disposition == PilotDisposition.BLOCKED_PRE_DISPATCH
    assert blocked_res.allowed_to_dispatch is False
    assert blocked_res.connections_accepted == 0
    assert blocked_res.bytes_transmitted == 0

    restraint = blocked_res.restraint_record
    assert restraint is not None
    assert restraint["record_type"] == "PRE_EXECUTION_RESTRAINT_RECORD"
    assert restraint["attestation_level"] == "Level 2 (Boundary-Signed)"
    assert restraint["socket_connect_invoked"] is False
    assert restraint["external_bytes_transmitted"] == 0

    # Cryptographic verification of restraint signature
    pubkey = runner.boundary_pubkey
    import base64
    sig = base64.b64decode(restraint["signature_b64"])
    # Copy payload without digest and signature
    payload = {k: v for k, v in restraint.items() if k not in ("digest", "signature_b64")}
    pubkey.verify(sig, encode_jcs(payload))


def test_weeks4_6_target_attested_reconciliation(pilot_setup):
    """
    Pattern C: Target-Attested Reconciliation under refund_status_v1.
    """
    runner, _ = pilot_setup
    runner.set_stage(PilotStage.WEEKS4_6_RECONCILE)

    # Simulate transport drop (HTTP 504) with target SETTLED response
    res = runner.evaluate_candidate_action(
        {
            "action_id": "act-recon-settled",
            "mcp_version": "2025-06-18",
            "target_uri": "https://api.testbank.com/v1/refunds",
            "policy_epoch": 1,
            "ticket_id": "ticket-recon-01",
            "parameters": {"amount_minor_units": 2000, "currency": "EUR", "recipient_iban": "CZ999"},
        },
        simulate_transport_drop=True,
        simulated_target_status="SETTLED",
    )
    assert res.disposition == PilotDisposition.RESOLVED_CONFIRMED
    assert res.reconciliation_record is not None
    assert res.reconciliation_record["contract_version"] == "1.0.0"
    assert res.reconciliation_record["target_status"] == "SETTLED"

    # Target signature verification
    import base64
    t_sig = base64.b64decode(res.reconciliation_record["signature_b64"])
    t_payload = {k: v for k, v in res.reconciliation_record.items() if k not in ("digest", "signature_b64")}
    runner.target_pubkey.verify(t_sig, encode_jcs(t_payload))

    # Simulate transport drop with target REVERSED response
    res_rev = runner.evaluate_candidate_action(
        {
            "action_id": "act-recon-reversed",
            "mcp_version": "2025-06-18",
            "target_uri": "https://api.testbank.com/v1/refunds",
            "policy_epoch": 1,
            "ticket_id": "ticket-recon-02",
            "parameters": {"amount_minor_units": 3000, "currency": "EUR", "recipient_iban": "CZ888"},
        },
        simulate_transport_drop=True,
        simulated_target_status="REVERSED",
    )
    assert res_rev.disposition == PilotDisposition.RESOLVED_REFUTED


def test_pilot_evidence_pack_export_and_falsification(pilot_setup):
    runner, tmp_path = pilot_setup

    # Execute one action per stage
    runner.set_stage(PilotStage.WEEK1_SCOPING)
    runner.evaluate_candidate_action({
        "action_id": "act-1",
        "mcp_version": "2025-06-18",
        "target_uri": "https://api.testbank.com/v1/refunds",
        "policy_epoch": 1,
        "ticket_id": "t-1",
        "parameters": {"amount_minor_units": 100, "currency": "EUR"},
    })

    runner.set_stage(PilotStage.WEEK2_SHADOW)
    runner.evaluate_candidate_action({
        "action_id": "act-2",
        "mcp_version": "2025-06-18",
        "target_uri": "https://api.testbank.com/v1/refunds",
        "policy_epoch": 99,
        "ticket_id": "t-2",
        "parameters": {"amount_minor_units": 100, "currency": "EUR"},
    })

    runner.set_stage(PilotStage.WEEK3_ENFORCE)
    runner.evaluate_candidate_action({
        "action_id": "act-3",
        "mcp_version": "2025-06-18",
        "target_uri": "https://evil.com",
        "policy_epoch": 1,
        "ticket_id": "t-3",
        "parameters": {"amount_minor_units": 100, "currency": "EUR"},
    })

    runner.set_stage(PilotStage.WEEKS4_6_RECONCILE)
    runner.evaluate_candidate_action(
        {
            "action_id": "act-4",
            "mcp_version": "2025-06-18",
            "target_uri": "https://api.testbank.com/v1/refunds",
            "policy_epoch": 1,
            "ticket_id": "t-4",
            "parameters": {"amount_minor_units": 500, "currency": "EUR"},
        },
        simulate_transport_drop=True,
        simulated_target_status="SETTLED",
    )

    pack_path = runner.export_evidence_pack(tmp_path)
    assert pack_path.exists()

    with open(pack_path, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    manifest = bundle["manifest"]
    assert manifest["total_evaluations"] == 4
    assert manifest["summary_metrics"]["would_block_count"] == 1
    assert manifest["summary_metrics"]["blocked_pre_dispatch_count"] == 1
    assert manifest["summary_metrics"]["resolved_confirmed_count"] == 1

    # Positive signature verification
    import base64
    pubkey = serialization.load_pem_public_key(bundle["boundary_public_key_pem"].encode("ascii"))
    sig = base64.b64decode(bundle["boundary_signature_b64"])
    pubkey.verify(sig, encode_jcs(manifest))

    # Falsification: tampered metric must fail verification
    tampered_manifest = dict(manifest)
    tampered_manifest["summary_metrics"]["blocked_pre_dispatch_count"] = 999
    with pytest.raises(Exception):
        pubkey.verify(sig, encode_jcs(tampered_manifest))
