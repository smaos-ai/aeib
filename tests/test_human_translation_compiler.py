#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_human_translation_compiler.py
================================================================================
Test & Falsification Suite for Human Translation Compiler & Repair Literacy Cards.

Evaluated under the stated model:
- Translation of complex AI mutation payloads into human-readable action cards.
- Risk tier and reversibility classification (T0/T2/T3).
- Cryptographic binding between raw payload CAID and signed action card.
- Falsification vectors: payload alteration rejection, card tamper rejection.
- Canonical JSON error handling and dataclass immutability.
- Epistemic linguistic compliance check.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.human_translation_compiler import (
    HumanTranslationCompiler,
    OperatorActionRecommendation,
    RepairLiteracyActionCard,
    ReversibilityClass,
    canonical_json_v1,
)


# -----------------------------------------------------------------------------
# Test 0: Immutability
# -----------------------------------------------------------------------------
def test_0_immutability() -> None:
    compiler = HumanTranslationCompiler()
    assert isinstance(compiler.public_key, Ed25519PublicKey)

    card = RepairLiteracyActionCard(
        card_id="c1",
        raw_payload_caid="raw1",
        action_name="act",
        risk_tier="T1",
        reversibility=ReversibilityClass.REVERSIBLE,
        intent_summary="summary",
        mutation_scope="scope",
        catastrophic_failure_scenario="fail",
        operator_checkpoints=("check1",),
        recommended_action=OperatorActionRecommendation.APPROVE_AS_IS,
        compiled_at_epoch=123,
        signer_pubkey_hex="00" * 32,
        signature_hex="00" * 64,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        card.risk_tier = "T3"  # type: ignore


# -----------------------------------------------------------------------------
# Test 1: Positive Control (Full Translation & Verification)
# -----------------------------------------------------------------------------
def test_1_positive_control_full_translation() -> None:
    compiler = HumanTranslationCompiler()
    payload = {
        "amount_minor": 125000,  # €1,250.00
        "currency": "EUR",
        "recipient_id": "DE89370400440532013000",
        "destination_domain": "api.bank.com",
    }

    card = compiler.compile_action_card(
        action_name="disburse_vendor_payment",
        raw_payload=payload,
        risk_tier="T3_IRREVERSIBLE",
        compiled_epoch=1700000000,
    )

    assert card.card_id.startswith("sha256:")
    assert card.raw_payload_caid.startswith("sha256:")
    assert card.action_name == "disburse_vendor_payment"
    assert card.risk_tier == "T3_IRREVERSIBLE"
    assert card.reversibility == ReversibilityClass.NON_COMPENSABLE_IRREVERSIBLE
    assert card.recommended_action == OperatorActionRecommendation.ADJUST_PARAMETERS
    assert "Disburse EUR 1250.00 to recipient DE89370400440532013000 via host api.bank.com." == card.mutation_scope
    assert len(card.operator_checkpoints) == 3
    assert "Verify disbursement amount: EUR 1250.00" in card.operator_checkpoints
    assert "Verify recipient account: DE89370400440532013000" in card.operator_checkpoints
    assert "Verify destination domain: api.bank.com" in card.operator_checkpoints
    assert card.compiled_at_epoch == 1700000000

    # Cryptographic verification against original payload
    assert HumanTranslationCompiler.verify_action_card(card, raw_payload=payload) is True
    assert HumanTranslationCompiler.verify_action_card(card, raw_payload=payload, expected_pubkey=compiler.public_key) is True


# -----------------------------------------------------------------------------
# Test 2: Risk Tier & Reversibility Classifications
# -----------------------------------------------------------------------------
def test_2_risk_tier_classifications() -> None:
    compiler = HumanTranslationCompiler()

    # T2 Medium Risk -> SAGA Compensable with default compiled_epoch (None)
    card_t2 = compiler.compile_action_card(
        action_name="stage_invoice",
        raw_payload={"invoice_id": "INV-101"},
        risk_tier="T2_MEDIUM_RISK",
        compiled_epoch=None,
    )
    assert card_t2.reversibility == ReversibilityClass.COMPENSABLE_VIA_SAGA
    assert card_t2.recommended_action == OperatorActionRecommendation.APPROVE_AS_IS
    assert card_t2.compiled_at_epoch > 1700000000

    # Explicit 0 epoch
    card_epoch_0 = compiler.compile_action_card(
        action_name="stage_invoice_0",
        raw_payload={"invoice_id": "INV-0"},
        risk_tier="T2_MEDIUM_RISK",
        compiled_epoch=0,
    )
    assert card_epoch_0.compiled_at_epoch == 0

    # T0 Informational -> Reversible
    card_t0 = compiler.compile_action_card(
        action_name="query_catalog",
        raw_payload={"item_id": "ITEM-1"},
        risk_tier="T0_INFORMATIONAL",
    )
    assert card_t0.reversibility == ReversibilityClass.REVERSIBLE
    assert card_t0.recommended_action == OperatorActionRecommendation.APPROVE_AS_IS
    assert "Executes tool 'query_catalog' with 1 parameters." in card_t0.mutation_scope


# -----------------------------------------------------------------------------
# Test 3: Payload Tamper Detection
# -----------------------------------------------------------------------------
def test_3_payload_tamper_detection() -> None:
    compiler = HumanTranslationCompiler()
    payload = {"amount_minor": 5000, "recipient_id": "ACC_ORIGINAL"}

    card = compiler.compile_action_card("pay", payload, "T2_MEDIUM_RISK")
    assert HumanTranslationCompiler.verify_action_card(card, raw_payload=payload) is True

    # Tampered recipient in payload fails raw payload binding check
    tampered_payload = {"amount_minor": 5000, "recipient_id": "ACC_ATTACKER"}
    assert HumanTranslationCompiler.verify_action_card(card, raw_payload=tampered_payload) is False


# -----------------------------------------------------------------------------
# Test 4: Card Attribute Tamper Detection
# -----------------------------------------------------------------------------
def test_4_card_attribute_tamper_detection() -> None:
    compiler = HumanTranslationCompiler()
    payload = {"query": "status"}

    card = compiler.compile_action_card("status", payload, "T0_INFORMATIONAL")
    assert HumanTranslationCompiler.verify_action_card(card) is True

    # Tamper with intent summary
    tampered_card = RepairLiteracyActionCard(
        card_id=card.card_id,
        raw_payload_caid=card.raw_payload_caid,
        action_name=card.action_name,
        risk_tier=card.risk_tier,
        reversibility=card.reversibility,
        intent_summary="ALTERED INTENT SUMMARY",
        mutation_scope=card.mutation_scope,
        catastrophic_failure_scenario=card.catastrophic_failure_scenario,
        operator_checkpoints=card.operator_checkpoints,
        recommended_action=card.recommended_action,
        compiled_at_epoch=card.compiled_at_epoch,
        signer_pubkey_hex=card.signer_pubkey_hex,
        signature_hex=card.signature_hex,
    )
    assert HumanTranslationCompiler.verify_action_card(tampered_card) is False

    # Tamper with signature
    tampered_sig = RepairLiteracyActionCard(
        card_id=card.card_id,
        raw_payload_caid=card.raw_payload_caid,
        action_name=card.action_name,
        risk_tier=card.risk_tier,
        reversibility=card.reversibility,
        intent_summary=card.intent_summary,
        mutation_scope=card.mutation_scope,
        catastrophic_failure_scenario=card.catastrophic_failure_scenario,
        operator_checkpoints=card.operator_checkpoints,
        recommended_action=card.recommended_action,
        compiled_at_epoch=card.compiled_at_epoch,
        signer_pubkey_hex=card.signer_pubkey_hex,
        signature_hex="00" * 64,
    )
    assert HumanTranslationCompiler.verify_action_card(tampered_sig) is False

    # Wrong expected pubkey
    foreign_key = Ed25519PrivateKey.generate().public_key()
    assert HumanTranslationCompiler.verify_action_card(card, expected_pubkey=foreign_key) is False


# -----------------------------------------------------------------------------
# Test 5: Canonical JSON Error Handling
# -----------------------------------------------------------------------------
def test_5_canonical_json_error_handling() -> None:
    # 1. Non-finite float
    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"f": float("nan")})

    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"f": float("inf")})

    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"f": float("-inf")})

    # 2. Non-string key
    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
        canonical_json_v1({99: "val"})

    # 3. Key sorting and raw UTF-8
    assert canonical_json_v1({"z": 1, "a": 2}) == b'{"a":2,"z":1}'
    assert canonical_json_v1({"symbol": "€"}) == '{"symbol":"€"}'.encode("utf-8")


# -----------------------------------------------------------------------------
# Test 6: Epistemic Linguistic Compliance (Zero Banned Words)
# -----------------------------------------------------------------------------
def test_6_epistemic_linguistic_compliance() -> None:
    banned_prefixes = [
        "guaran" + "tee",
        "proven univer" + "sally",
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
        Path("src/human_translation_compiler.py"),
        Path("tests/test_human_translation_compiler.py"),
    ]

    for file_path in files_to_check:
        assert file_path.exists(), f"File {file_path} must exist"
        content = file_path.read_text(encoding="utf-8")
        for banned in banned_prefixes:
            match = re.search(r"\b" + re.escape(banned), content, re.IGNORECASE)
            assert match is None, (
                f"Epistemic boundary violation: found banned term '{banned}' "
                f"in {file_path}"
            )
