#!/usr/bin/env python3
"""
tests/test_at73_sovereign_signer_allowlist_gate.py
================================================================================
Verification & Falsification Suite for AT73 Sovereign Signer Allowlist Gate &
BIP-39 Recovery Phrase Scavenging Defense.

Evaluated under the stated model using real Ed25519 asymmetric cryptography
(cryptography.hazmat) and RFC 8785 JCS canonicalization.
"""

from __future__ import annotations

import base64
import hmac
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.adapters.sovereign_signer_allowlist_gate import (
    BIP39_SAMPLE_WORDS,
    SovereignSignerAllowlistGate,
    SovereignTransactionProposal,
    detect_bip39_phrase,
    sha256_prefixed,
)
from src.jcs_canonicalizer import encode_jcs


def _sign_warrant(
    sponsor_sk: Ed25519PrivateKey,
    operation_id: str,
    network: str,
    target: str,
    amount_minor: int,
    gas_limit: int,
) -> str:
    warrant_dict = {
        "amount_minor": amount_minor,
        "gas_limit": gas_limit,
        "network": network,
        "operation_id": operation_id,
        "target": target,
    }
    canonical_bytes = encode_jcs(warrant_dict)
    sig_bytes = sponsor_sk.sign(canonical_bytes)
    return base64.b64encode(sig_bytes).decode("ascii")


def test_bip39_scavenging_detection_in_context_and_queries() -> None:
    """
    Tests detection of 12-word and 24-word BIP-39 mnemonic seed phrase patterns
    scavenged from agent memory or searched on the web.
    """
    # 1. Benign agent query
    benign_query = "Please query the database for the active balance of account 0x1234."
    assert not detect_bip39_phrase(benign_query)

    sponsor_sk = Ed25519PrivateKey.generate()
    gate = SovereignSignerAllowlistGate(
        root_sponsor_pubkey=sponsor_sk.public_key(),
        allowed_targets={"0x1111222233334444555566667777888899990000"},
    )
    ok, err = gate.inspect_context_or_query(benign_query)
    assert ok is True
    assert err is None

    # 2. 12-word BIP-39 mnemonic seed phrase
    twelve_word_seed = (
        "abandon ability able about above absent absorb abstract absurd abuse access accident"
    )
    assert detect_bip39_phrase(twelve_word_seed)
    ok, err = gate.inspect_context_or_query(twelve_word_seed)
    assert ok is False
    assert err == "HALT_BIP39_SCAVENGING_TRIPWIRE_TRIGGERED"

    # 3. 24-word BIP-39 mnemonic seed phrase in text
    twenty_four_seed = (
        "abandon ability able about above absent absorb abstract absurd abuse access accident "
        "account accuse achieve acid acoustic acquire across act action actor actress actual"
    )
    assert detect_bip39_phrase(twenty_four_seed)
    ok, err = gate.inspect_context_or_query(f"Agent search query: finding {twenty_four_seed} on github")
    assert ok is False
    assert err == "HALT_BIP39_SCAVENGING_TRIPWIRE_TRIGGERED"

    # 4. Short sentence with <12 words does not trigger false positives
    short_text = "abandon ability able about"
    assert not detect_bip39_phrase(short_text)
    ok, err = gate.inspect_context_or_query(short_text)
    assert ok is True
    assert err is None


def test_sovereign_signer_positive_authorization_path() -> None:
    """
    Tests positive authorization path where target is pinned, gas is within limit,
    amount is within ceiling, and Root Sponsor Ed25519 signature is verified.
    """
    sponsor_sk = Ed25519PrivateKey.generate()
    allowed_target = "0xDeadBeef00000000000000000000000000000001"
    gate = SovereignSignerAllowlistGate(
        root_sponsor_pubkey=sponsor_sk.public_key(),
        allowed_targets={allowed_target},
        max_gas_limit=500_000,
        max_amount_minor=100_000_000,
    )

    op_id = "op-sov-001"
    network = "eip155:1"
    sig_b64 = _sign_warrant(
        sponsor_sk=sponsor_sk,
        operation_id=op_id,
        network=network,
        target=allowed_target,
        amount_minor=50_000_000,
        gas_limit=210_000,
    )

    proposal = SovereignTransactionProposal(
        operation_id=op_id,
        network=network,
        target_contract_or_account=allowed_target,
        amount_minor=50_000_000,
        gas_limit=210_000,
        data_payload="0xa9059cbb0000000000000000000000001111111111111111111111111111111111111111",
        root_sponsor_sig_b64=sig_b64,
    )

    disposition, rejection_code, receipt = gate.evaluate_transaction_proposal(proposal)
    assert disposition == "AUTHORIZED_FOR_HOST_SIGNING"
    assert rejection_code is None
    assert receipt is not None
    assert receipt["operation_id"] == op_id
    assert receipt["target"] == allowed_target
    assert receipt["signature_b64"] == sig_b64
    assert receipt["warrant_caid"].startswith("sha256:")


def test_falsification_unauthorized_target_rejected() -> None:
    """
    Tests rejection when proposal targets an unpinned smart contract or account.
    """
    sponsor_sk = Ed25519PrivateKey.generate()
    allowed_target = "0xDeadBeef00000000000000000000000000000001"
    rogue_target = "0xBadActor00000000000000000000000000000002"

    gate = SovereignSignerAllowlistGate(
        root_sponsor_pubkey=sponsor_sk.public_key(),
        allowed_targets={allowed_target},
    )

    sig_b64 = _sign_warrant(
        sponsor_sk=sponsor_sk,
        operation_id="op-sov-002",
        network="eip155:1",
        target=rogue_target,
        amount_minor=1_000,
        gas_limit=21_000,
    )

    proposal = SovereignTransactionProposal(
        operation_id="op-sov-002",
        network="eip155:1",
        target_contract_or_account=rogue_target,
        amount_minor=1_000,
        gas_limit=21_000,
        data_payload="",
        root_sponsor_sig_b64=sig_b64,
    )

    disposition, rejection_code, receipt = gate.evaluate_transaction_proposal(proposal)
    assert disposition == "BLOCKED"
    assert rejection_code == "HALT_UNAUTHORIZED_SOVEREIGN_SIGNER_TARGET"
    assert receipt is None


def test_falsification_gas_and_value_ceiling_exceeded() -> None:
    """
    Tests rejection when gas limit or transaction value exceeds configured ceiling.
    """
    sponsor_sk = Ed25519PrivateKey.generate()
    allowed_target = "0xDeadBeef00000000000000000000000000000001"
    gate = SovereignSignerAllowlistGate(
        root_sponsor_pubkey=sponsor_sk.public_key(),
        allowed_targets={allowed_target},
        max_gas_limit=100_000,
        max_amount_minor=10_000_000,
    )

    # 1. Gas limit exceeded
    sig_gas = _sign_warrant(
        sponsor_sk=sponsor_sk,
        operation_id="op-gas-exceeded",
        network="eip155:1",
        target=allowed_target,
        amount_minor=1_000,
        gas_limit=200_000,
    )
    p_gas = SovereignTransactionProposal(
        operation_id="op-gas-exceeded",
        network="eip155:1",
        target_contract_or_account=allowed_target,
        amount_minor=1_000,
        gas_limit=200_000,
        data_payload="",
        root_sponsor_sig_b64=sig_gas,
    )
    disposition, rejection_code, receipt = gate.evaluate_transaction_proposal(p_gas)
    assert disposition == "BLOCKED"
    assert rejection_code == "HALT_GAS_LIMIT_EXCEEDED"
    assert receipt is None

    # 2. Value ceiling exceeded
    sig_val = _sign_warrant(
        sponsor_sk=sponsor_sk,
        operation_id="op-val-exceeded",
        network="eip155:1",
        target=allowed_target,
        amount_minor=20_000_000,
        gas_limit=50_000,
    )
    p_val = SovereignTransactionProposal(
        operation_id="op-val-exceeded",
        network="eip155:1",
        target_contract_or_account=allowed_target,
        amount_minor=20_000_000,
        gas_limit=50_000,
        data_payload="",
        root_sponsor_sig_b64=sig_val,
    )
    disposition, rejection_code, receipt = gate.evaluate_transaction_proposal(p_val)
    assert disposition == "BLOCKED"
    assert rejection_code == "HALT_TRANSACTION_VALUE_CEILING_EXCEEDED"
    assert receipt is None


def test_falsification_missing_or_forged_root_sponsor_warrant() -> None:
    """
    Tests rejection when root sponsor warrant is absent, forged, or tampered.
    """
    sponsor_sk = Ed25519PrivateKey.generate()
    attacker_sk = Ed25519PrivateKey.generate()
    allowed_target = "0xDeadBeef00000000000000000000000000000001"
    gate = SovereignSignerAllowlistGate(
        root_sponsor_pubkey=sponsor_sk.public_key(),
        allowed_targets={allowed_target},
    )

    # 1. Missing signature
    p_missing = SovereignTransactionProposal(
        operation_id="op-missing-sig",
        network="eip155:1",
        target_contract_or_account=allowed_target,
        amount_minor=1_000,
        gas_limit=50_000,
        data_payload="",
        root_sponsor_sig_b64=None,
    )
    disposition, rejection_code, _ = gate.evaluate_transaction_proposal(p_missing)
    assert disposition == "BLOCKED"
    assert rejection_code == "HALT_MISSING_ROOT_SPONSOR_WARRANT"

    # 2. Signature forged with wrong private key
    sig_forged = _sign_warrant(
        sponsor_sk=attacker_sk,
        operation_id="op-forged-sig",
        network="eip155:1",
        target=allowed_target,
        amount_minor=1_000,
        gas_limit=50_000,
    )
    p_forged = SovereignTransactionProposal(
        operation_id="op-forged-sig",
        network="eip155:1",
        target_contract_or_account=allowed_target,
        amount_minor=1_000,
        gas_limit=50_000,
        data_payload="",
        root_sponsor_sig_b64=sig_forged,
    )
    disposition, rejection_code, _ = gate.evaluate_transaction_proposal(p_forged)
    assert disposition == "BLOCKED"
    assert rejection_code == "HALT_INVALID_ROOT_SPONSOR_SIGNATURE"

    # 3. Tampered warrant field (amount mutated after sponsor signed)
    sig_valid = _sign_warrant(
        sponsor_sk=sponsor_sk,
        operation_id="op-tampered",
        network="eip155:1",
        target=allowed_target,
        amount_minor=1_000,
        gas_limit=50_000,
    )
    p_tampered = SovereignTransactionProposal(
        operation_id="op-tampered",
        network="eip155:1",
        target_contract_or_account=allowed_target,
        amount_minor=2_000,  # Attacker modified amount
        gas_limit=50_000,
        data_payload="",
        root_sponsor_sig_b64=sig_valid,
    )
    disposition, rejection_code, _ = gate.evaluate_transaction_proposal(p_tampered)
    assert disposition == "BLOCKED"
    assert rejection_code == "HALT_INVALID_ROOT_SPONSOR_SIGNATURE"


def test_bip39_phrase_in_transaction_payload_tripwire() -> None:
    """
    Tests that BIP-39 mnemonic seed phrase embedded in transaction calldata
    triggers immediate fail-closed tripwire.
    """
    sponsor_sk = Ed25519PrivateKey.generate()
    allowed_target = "0xDeadBeef00000000000000000000000000000001"
    gate = SovereignSignerAllowlistGate(
        root_sponsor_pubkey=sponsor_sk.public_key(),
        allowed_targets={allowed_target},
    )

    seed_payload = "memo: abandon ability able about above absent absorb abstract absurd abuse access accident"
    sig_b64 = _sign_warrant(
        sponsor_sk=sponsor_sk,
        operation_id="op-payload-seed",
        network="eip155:1",
        target=allowed_target,
        amount_minor=100,
        gas_limit=21_000,
    )
    proposal = SovereignTransactionProposal(
        operation_id="op-payload-seed",
        network="eip155:1",
        target_contract_or_account=allowed_target,
        amount_minor=100,
        gas_limit=21_000,
        data_payload=seed_payload,
        root_sponsor_sig_b64=sig_b64,
    )
    disposition, rejection_code, receipt = gate.evaluate_transaction_proposal(proposal)
    assert disposition == "BLOCKED"
    assert rejection_code == "HALT_BIP39_SCAVENGING_TRIPWIRE_TRIGGERED"
    assert receipt is None
