#!/usr/bin/env python3
"""
test_dpop_token_exchange_gate.py — Falsification & Verification Suite for
RFC 8693 Token Exchange & RFC 9449 DPoP Zero-Credential Sidecar Gate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.dpop_token_exchange_gate import (
    AccessTokenHashError,
    DPoPBindingError,
    DPoPReplayError,
    PayloadCaidMismatchError,
    PolicyEpochError,
    RFC8693TokenExchangeServer,
    RFC9449DPoPProver,
    RFC9449DPoPVerifier,
    TargetBindingMismatchError,
    TokenExchangePrivilegeError,
    _b64url_encode,
    compute_ed25519_jwk_thumbprint,
    compute_payload_caid,
    create_dpop_proof,
    ed25519_public_key_to_jwk,
    verify_dpop_bound_dispatch,
)
from src.jcs_canonicalizer import encode_jcs


def _build_fixture_environment() -> Tuple[
    ed25519.Ed25519PrivateKey,
    ed25519.Ed25519PrivateKey,
    RFC8693TokenExchangeServer,
    RFC9449DPoPProver,
    RFC9449DPoPVerifier,
    Dict[str, Any],
    Dict[str, Any],
    Dict[str, Any],
]:
    """Builds a deterministic test setup with real Ed25519 keys for AS and Sidecar."""
    as_privkey = ed25519.Ed25519PrivateKey.generate()
    sidecar_privkey = ed25519.Ed25519PrivateKey.generate()

    tx_server = RFC8693TokenExchangeServer(
        as_privkey=as_privkey,
        issuer="https://as.sovereignnexus.internal/v1/token",
        active_policy_epoch=42,
    )
    prover = RFC9449DPoPProver(sidecar_privkey=sidecar_privkey)
    verifier = RFC9449DPoPVerifier()

    subject_token = tx_server.create_root_sponsor_grant(
        root_sponsor_did="did:web:sponsor.example.internal:treasury-root",
        budget_ceiling_minor_units=50_000,
        allowed_audiences=["https://bank.example.internal/v1/refunds"],
        policy_epoch=42,
        iat=1770000000,
    )
    actor_token = tx_server.create_actor_token(
        subagent_did="did:web:agents.example.internal:refund-worker-03",
        parent_agent_did="did:web:agents.example.internal:orchestrator-01",
        parent_budget_ceiling_minor_units=25_000,
    )
    wire_payload = {
        "action": "execute_refund",
        "amount": 12_500,
        "currency": "EUR",
        "invoice_id": "INV-2026-00981",
        "recipient_iban": "DE89370400440532013000",
    }
    return (
        as_privkey,
        sidecar_privkey,
        tx_server,
        prover,
        verifier,
        subject_token,
        actor_token,
        wire_payload,
    )


def test_rfc7638_jwk_thumbprint_determinism() -> None:
    """Evaluates RFC 7638 / RFC 8785 JCS SHA-256 thumbprint computation over Ed25519 keys."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    jwk = ed25519_public_key_to_jwk(pub)

    jkt_from_pub = compute_ed25519_jwk_thumbprint(pub)
    jkt_from_jwk = compute_ed25519_jwk_thumbprint(jwk)

    assert jkt_from_pub == jkt_from_jwk
    assert len(jkt_from_pub) == 43  # 256-bit digest in unpadded base64url


def test_positive_end_to_end_rfc8693_and_rfc9449_dpop_dispatch() -> None:
    """
    Tests positive end-to-end RFC 8693 Token Exchange + RFC 9449 DPoP sender-constrained
    dispatch verification under the stated model.
    """
    (
        as_privkey,
        sidecar_privkey,
        tx_server,
        prover,
        verifier,
        subject_token,
        actor_token,
        wire_payload,
    ) = _build_fixture_environment()

    target_uri = "https://bank.example.internal/v1/refunds"
    access_token = tx_server.exchange_token(
        subject_token=subject_token,
        actor_token=actor_token,
        aud=target_uri,
        wire_payload=wire_payload,
        requested_budget_minor_units=15_000,
        sidecar_pubkey_or_jkt=prover.sidecar_pubkey,
        jti="tx-pos-001",
        iat=1770000010,
        policy_epoch=42,
    )

    assert access_token["sub"] == "did:web:sponsor.example.internal:treasury-root"
    assert access_token["aud"] == target_uri
    assert access_token["act"] == {
        "sub": "did:web:agents.example.internal:refund-worker-03",
        "parent_sub": "did:web:agents.example.internal:orchestrator-01",
    }
    assert access_token["cnf"] == {"jkt": prover.jkt}
    assert access_token["caid"] == compute_payload_caid(wire_payload)
    assert access_token["budget_ceiling_minor_units"] == 15_000

    dpop_proof = create_dpop_proof(
        sidecar_privkey=sidecar_privkey,
        htm="POST",
        htu=target_uri,
        access_token_bytes=encode_jcs(access_token),
        caid=access_token["caid"],
        jti="dpop-pos-001",
        iat=1770000011,
    )

    receipt = verify_dpop_bound_dispatch(
        access_token=access_token,
        dpop_proof=dpop_proof,
        expected_htm="POST",
        expected_htu=target_uri,
        wire_payload=wire_payload,
        as_pubkey=as_privkey.public_key(),
        active_policy_epoch=42,
        verifier=verifier,
    )

    assert receipt["verified"] is True
    assert receipt["cnf_jkt"] == prover.jkt
    assert receipt["caid"] == access_token["caid"]
    assert receipt["act"]["sub"] == "did:web:agents.example.internal:refund-worker-03"


def test_falsification_1_stolen_access_token_replayed_by_attacker_key() -> None:
    """
    Falsification 1: Stolen access token replayed by an attacker/agent key whose JWK
    thumbprint does not match `cnf.jkt` -> rejected (`DPoPBindingError`).
    """
    (
        as_privkey,
        _sidecar_privkey,
        tx_server,
        prover,
        verifier,
        subject_token,
        actor_token,
        wire_payload,
    ) = _build_fixture_environment()

    target_uri = "https://bank.example.internal/v1/refunds"
    access_token = tx_server.exchange_token(
        subject_token=subject_token,
        actor_token=actor_token,
        aud=target_uri,
        wire_payload=wire_payload,
        requested_budget_minor_units=15_000,
        sidecar_pubkey_or_jkt=prover.sidecar_pubkey,
        jti="tx-f1-001",
        iat=1770000010,
        policy_epoch=42,
    )

    # Compromised agent process or external attacker generates its own Ed25519 key pair
    attacker_privkey = ed25519.Ed25519PrivateKey.generate()
    forged_dpop_proof = create_dpop_proof(
        sidecar_privkey=attacker_privkey,
        htm="POST",
        htu=target_uri,
        access_token_bytes=encode_jcs(access_token),
        caid=access_token["caid"],
        jti="dpop-f1-attacker",
        iat=1770000012,
    )

    with pytest.raises(DPoPBindingError, match="Sender constraint violation"):
        verify_dpop_bound_dispatch(
            access_token=access_token,
            dpop_proof=forged_dpop_proof,
            expected_htm="POST",
            expected_htu=target_uri,
            wire_payload=wire_payload,
            as_pubkey=as_privkey.public_key(),
            active_policy_epoch=42,
            verifier=verifier,
        )


def test_falsification_2_mismatched_htm_or_target_resource_uri() -> None:
    """
    Falsification 2: Mismatched HTTP method (`htm`) or target resource URI (`htu` vs `aud`)
    -> rejected (`TargetBindingMismatchError` / `DPoPBindingError`).
    """
    (
        as_privkey,
        sidecar_privkey,
        tx_server,
        prover,
        verifier,
        subject_token,
        actor_token,
        wire_payload,
    ) = _build_fixture_environment()

    target_uri = "https://bank.example.internal/v1/refunds"
    access_token = tx_server.exchange_token(
        subject_token=subject_token,
        actor_token=actor_token,
        aud=target_uri,
        wire_payload=wire_payload,
        requested_budget_minor_units=15_000,
        sidecar_pubkey_or_jkt=prover.sidecar_pubkey,
        jti="tx-f2-001",
        iat=1770000010,
        policy_epoch=42,
    )

    dpop_proof = create_dpop_proof(
        sidecar_privkey=sidecar_privkey,
        htm="POST",
        htu=target_uri,
        access_token_bytes=encode_jcs(access_token),
        caid=access_token["caid"],
        jti="dpop-f2-001",
        iat=1770000011,
    )

    # Case 2a: Mismatched HTTP method (DELETE instead of POST)
    with pytest.raises(TargetBindingMismatchError, match="HTTP method mismatch"):
        verify_dpop_bound_dispatch(
            access_token=access_token,
            dpop_proof=dpop_proof,
            expected_htm="DELETE",
            expected_htu=target_uri,
            wire_payload=wire_payload,
            as_pubkey=as_privkey.public_key(),
            active_policy_epoch=42,
            verifier=verifier,
        )

    # Case 2b: Mismatched target resource URI (cross-endpoint confused deputy replay)
    with pytest.raises(TargetBindingMismatchError, match="target URI mismatch"):
        verify_dpop_bound_dispatch(
            access_token=access_token,
            dpop_proof=dpop_proof,
            expected_htm="POST",
            expected_htu="https://bank.example.internal/v1/wires",
            wire_payload=wire_payload,
            as_pubkey=as_privkey.public_key(),
            active_policy_epoch=42,
            verifier=verifier,
        )


def test_falsification_3_altered_wire_payload_parameter_breaks_caid() -> None:
    """
    Falsification 3: Altered wire payload parameter (`amount` or `recipient_iban` mutated
    after token exchange, breaking `caid`) -> rejected (`PayloadCaidMismatchError`).
    """
    (
        as_privkey,
        sidecar_privkey,
        tx_server,
        prover,
        verifier,
        subject_token,
        actor_token,
        wire_payload,
    ) = _build_fixture_environment()

    target_uri = "https://bank.example.internal/v1/refunds"
    access_token = tx_server.exchange_token(
        subject_token=subject_token,
        actor_token=actor_token,
        aud=target_uri,
        wire_payload=wire_payload,
        requested_budget_minor_units=15_000,
        sidecar_pubkey_or_jkt=prover.sidecar_pubkey,
        jti="tx-f3-001",
        iat=1770000010,
        policy_epoch=42,
    )

    dpop_proof = create_dpop_proof(
        sidecar_privkey=sidecar_privkey,
        htm="POST",
        htu=target_uri,
        access_token_bytes=encode_jcs(access_token),
        caid=access_token["caid"],
        jti="dpop-f3-001",
        iat=1770000011,
    )

    # Case 3a: Mutated amount
    tampered_amount_payload = dict(wire_payload, amount=14_999)
    with pytest.raises(PayloadCaidMismatchError, match="caid"):
        verify_dpop_bound_dispatch(
            access_token=access_token,
            dpop_proof=dpop_proof,
            expected_htm="POST",
            expected_htu=target_uri,
            wire_payload=tampered_amount_payload,
            as_pubkey=as_privkey.public_key(),
            active_policy_epoch=42,
            verifier=verifier,
        )

    # Case 3b: Mutated recipient_iban
    tampered_iban_payload = dict(wire_payload, recipient_iban="GB29NWBK60161331926819")
    with pytest.raises(PayloadCaidMismatchError, match="caid"):
        verify_dpop_bound_dispatch(
            access_token=access_token,
            dpop_proof=dpop_proof,
            expected_htm="POST",
            expected_htu=target_uri,
            wire_payload=tampered_iban_payload,
            as_pubkey=as_privkey.public_key(),
            active_policy_epoch=42,
            verifier=verifier,
        )


def test_falsification_4_replayed_dpop_jti_nonce_rejected() -> None:
    """
    Falsification 4: Replayed DPoP `jti` nonce on a second request -> rejected (`DPoPReplayError`).
    """
    (
        as_privkey,
        sidecar_privkey,
        tx_server,
        prover,
        verifier,
        subject_token,
        actor_token,
        wire_payload,
    ) = _build_fixture_environment()

    target_uri = "https://bank.example.internal/v1/refunds"
    access_token_1 = tx_server.exchange_token(
        subject_token=subject_token,
        actor_token=actor_token,
        aud=target_uri,
        wire_payload=wire_payload,
        requested_budget_minor_units=15_000,
        sidecar_pubkey_or_jkt=prover.sidecar_pubkey,
        jti="tx-f4-001",
        iat=1770000010,
        policy_epoch=42,
    )

    dpop_proof_1 = create_dpop_proof(
        sidecar_privkey=sidecar_privkey,
        htm="POST",
        htu=target_uri,
        access_token_bytes=encode_jcs(access_token_1),
        caid=access_token_1["caid"],
        jti="dpop-f4-replayed-nonce",
        iat=1770000011,
    )

    # First dispatch succeeds
    first_receipt = verify_dpop_bound_dispatch(
        access_token=access_token_1,
        dpop_proof=dpop_proof_1,
        expected_htm="POST",
        expected_htu=target_uri,
        wire_payload=wire_payload,
        as_pubkey=as_privkey.public_key(),
        active_policy_epoch=42,
        verifier=verifier,
    )
    assert first_receipt["verified"] is True

    # Second dispatch replaying the exact same DPoP proof / jti is rejected
    with pytest.raises(DPoPReplayError, match="Replayed DPoP proof jti nonce"):
        verify_dpop_bound_dispatch(
            access_token=access_token_1,
            dpop_proof=dpop_proof_1,
            expected_htm="POST",
            expected_htu=target_uri,
            wire_payload=wire_payload,
            as_pubkey=as_privkey.public_key(),
            active_policy_epoch=42,
            verifier=verifier,
        )


def test_falsification_5_subagent_privilege_escalation_during_token_exchange() -> None:
    """
    Falsification 5: Subagent attempting privilege escalation
    (`requested_budget > root_sponsor_ceiling`) during RFC 8693 token exchange -> rejected.
    """
    (
        _as_privkey,
        _sidecar_privkey,
        tx_server,
        prover,
        _verifier,
        subject_token,
        actor_token,
        wire_payload,
    ) = _build_fixture_environment()

    target_uri = "https://bank.example.internal/v1/refunds"

    # Attempt to request 100,000 minor units when root_sponsor_ceiling is 50,000
    with pytest.raises(TokenExchangePrivilegeError, match="exceeds root_sponsor_ceiling"):
        tx_server.exchange_token(
            subject_token=subject_token,
            actor_token=actor_token,
            aud=target_uri,
            wire_payload=wire_payload,
            requested_budget_minor_units=100_000,
            sidecar_pubkey_or_jkt=prover.sidecar_pubkey,
            jti="tx-f5-escalate",
            iat=1770000010,
            policy_epoch=42,
        )


def test_falsification_6_stale_policy_epoch_rejected() -> None:
    """
    Falsification 6: Stale `policy_epoch` -> rejected (`PolicyEpochError`).
    """
    (
        as_privkey,
        sidecar_privkey,
        tx_server,
        prover,
        verifier,
        subject_token,
        actor_token,
        wire_payload,
    ) = _build_fixture_environment()

    target_uri = "https://bank.example.internal/v1/refunds"
    access_token = tx_server.exchange_token(
        subject_token=subject_token,
        actor_token=actor_token,
        aud=target_uri,
        wire_payload=wire_payload,
        requested_budget_minor_units=15_000,
        sidecar_pubkey_or_jkt=prover.sidecar_pubkey,
        jti="tx-f6-001",
        iat=1770000010,
        policy_epoch=42,
    )

    dpop_proof = create_dpop_proof(
        sidecar_privkey=sidecar_privkey,
        htm="POST",
        htu=target_uri,
        access_token_bytes=encode_jcs(access_token),
        caid=access_token["caid"],
        jti="dpop-f6-001",
        iat=1770000011,
    )

    # Control plane bumps active_policy_epoch from 42 to 43 before sidecar dispatch arrives
    with pytest.raises(PolicyEpochError, match="Policy epoch mismatch"):
        verify_dpop_bound_dispatch(
            access_token=access_token,
            dpop_proof=dpop_proof,
            expected_htm="POST",
            expected_htu=target_uri,
            wire_payload=wire_payload,
            as_pubkey=as_privkey.public_key(),
            active_policy_epoch=43,
            verifier=verifier,
        )


def test_falsification_7_tampered_ath_access_token_hash_rejected() -> None:
    """
    Falsification 7: Tampered `ath` (access token hash) -> rejected (`AccessTokenHashError`).
    """
    (
        as_privkey,
        sidecar_privkey,
        tx_server,
        prover,
        verifier,
        subject_token,
        actor_token,
        wire_payload,
    ) = _build_fixture_environment()

    target_uri = "https://bank.example.internal/v1/refunds"
    access_token = tx_server.exchange_token(
        subject_token=subject_token,
        actor_token=actor_token,
        aud=target_uri,
        wire_payload=wire_payload,
        requested_budget_minor_units=15_000,
        sidecar_pubkey_or_jkt=prover.sidecar_pubkey,
        jti="tx-f7-001",
        iat=1770000010,
        policy_epoch=42,
    )

    other_access_token = tx_server.exchange_token(
        subject_token=subject_token,
        actor_token=actor_token,
        aud=target_uri,
        wire_payload=wire_payload,
        requested_budget_minor_units=20_000,
        sidecar_pubkey_or_jkt=prover.sidecar_pubkey,
        jti="tx-f7-002",
        iat=1770000010,
        policy_epoch=42,
    )

    # Validly signed DPoP proof by the sidecar, but bound to `other_access_token` (`ath` mismatch)
    mismatched_ath_proof = create_dpop_proof(
        sidecar_privkey=sidecar_privkey,
        htm="POST",
        htu=target_uri,
        access_token_bytes=encode_jcs(other_access_token),
        caid=access_token["caid"],
        jti="dpop-f7-001",
        iat=1770000011,
    )

    with pytest.raises(AccessTokenHashError, match="ath mismatch"):
        verify_dpop_bound_dispatch(
            access_token=access_token,
            dpop_proof=mismatched_ath_proof,
            expected_htm="POST",
            expected_htu=target_uri,
            wire_payload=wire_payload,
            as_pubkey=as_privkey.public_key(),
            active_policy_epoch=42,
            verifier=verifier,
        )


def test_epistemic_boundary_compliance() -> None:
    """Verifies that neither the implementation nor the test file contains banned phrases."""
    banned_phrases = (
        "guaran" + "teed",
        "guaran" + "tee",
        "proven " + "universally",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
    )
    repo_root = Path(__file__).resolve().parent.parent
    for rel_path in ("src/dpop_token_exchange_gate.py", "tests/test_dpop_token_exchange_gate.py"):
        content = (repo_root / rel_path).read_text(encoding="utf-8").lower()
        for phrase in banned_phrases:
            assert phrase not in content, f"Banned phrase found in {rel_path}"
