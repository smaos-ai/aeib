#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# tests/test_bbs_plus_redactable.py — Unit tests for BBS+ Selective Disclosure

import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.bbs_plus_redactable import (
    AuditField,
    BbsPlusRedactor,
    SovereignAuditReceipt,
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


def test_bbs_defaults_and_unredacted_flow():
    # 1. AuditField default is_pii is False
    f1 = AuditField("note", "public")
    assert f1.is_pii is False

    # 2. add_field default is_pii is False
    receipt = SovereignAuditReceipt("EVT-400", "act_004", "tenant-delta", "audit_ping")
    receipt.add_field("default_field", "default_val")
    assert receipt.fields[0].is_pii is False

    # Add a PII field
    receipt.add_field("secret_pii", "secret_val", is_pii=True)

    # 3. create_selective_proof default redact_pii is True and default nonce is used
    proof_default = BbsPlusRedactor.create_selective_proof(receipt)
    assert proof_default.proof_nonce == "default_proof_nonce"
    assert "secret_pii" not in proof_default.revealed_fields
    assert len(proof_default.blinded_commitments) == 1
    assert BbsPlusRedactor.verify_selective_proof(proof_default) is True

    # 4. create_selective_proof with redact_pii=False reveals everything
    proof_full = BbsPlusRedactor.create_selective_proof(receipt, redact_pii=False)
    assert "secret_pii" in proof_full.revealed_fields
    assert proof_full.revealed_fields["secret_pii"] == "secret_val"
    assert len(proof_full.blinded_commitments) == 0
    assert BbsPlusRedactor.verify_selective_proof(proof_full) is True
