#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# tests/test_bbs_plus_redactable.py — Unit tests for BBS+ Selective Disclosure

import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.bbs_plus_redactable import (
    SovereignAuditReceipt,
    BbsPlusRedactor,
    VerificationFailedError,
)


def test_bbs_redaction_and_verification():
    receipt = SovereignAuditReceipt("EVT-100", "act_001", "tenant-alpha", "transfer_funds")
    receipt.add_field("user_name", "Alice Example", is_pii=False)
    receipt.add_field("user_iban", "CZ6508000000001234567890", is_pii=True)  # PII to redact
    receipt.add_field("amount_eur", "5000", is_pii=False)

    # 1. Create proof with PII redacted (GDPR Art. 17 right to erasure)
    proof = BbsPlusRedactor.create_selective_proof(receipt, redact_pii=True, nonce="nonce-999")
    
    # Assert IBAN is completely absent from revealed fields
    assert "user_iban" not in proof.revealed_fields
    assert proof.revealed_fields["amount_eur"] == "5000"
    assert len(proof.blinded_commitments) == 1

    # 2. Verify proof validity without access to unblinded IBAN
    is_valid = BbsPlusRedactor.verify_selective_proof(proof)
    assert is_valid is True


def test_bbs_tamper_detection_in_revealed_fields():
    receipt = SovereignAuditReceipt("EVT-200", "act_002", "tenant-beta", "wire_payout")
    receipt.add_field("amount_eur", "1000", is_pii=False)
    receipt.add_field("beneficiary_id", "ID-999", is_pii=True)

    proof = BbsPlusRedactor.create_selective_proof(receipt, redact_pii=True, nonce="nonce-123")

    # Tamper with revealed amount: 1000 -> 9000
    proof.revealed_fields["amount_eur"] = "9000"
    
    with pytest.raises(VerificationFailedError):
        BbsPlusRedactor.verify_selective_proof(proof)


def test_bbs_tamper_detection_in_blinded_commitments():
    receipt = SovereignAuditReceipt("EVT-300", "act_003", "tenant-gamma", "trade_settle")
    receipt.add_field("secret_account", "ACC-SECRET", is_pii=True)

    proof = BbsPlusRedactor.create_selective_proof(receipt, redact_pii=True, nonce="nonce-456")

    # Tamper with blinded commitment
    corrupted_comm = "0" * 64
    proof.blinded_commitments = [corrupted_comm]

    with pytest.raises(VerificationFailedError):
        BbsPlusRedactor.verify_selective_proof(proof)
