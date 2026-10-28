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
tests/test_enterprise_production_bridges.py — Test Suite for the 4 SOTA Production Bridges
1. ISO 20022 XML & SWIFT CBPR+ EndToEndId/UETR Mapping
2. CloudHSM Ephemeral In-Enclave Session Lease Signer
3. Challenge-Response Cryptographic Dual Control HITL Quorum
4. Bitemporal Saga Compensating Ledger Engine
"""

import base64
import time
import uuid
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.jcs_canonicalizer import encode_jcs
from src.aeib_iso20022_adapter import (
    Iso20022PaymentAdapter,
    derive_iso20022_end_to_end_id,
    derive_swift_uetr,
)
from src.aeib_cloud_hsm_signer import (
    CloudHsmMasterEnclave,
    EphemeralSessionLeaseSigner,
)
from src.aeib_dual_control_hitl import (
    DualControlHitlGate,
    compute_hitl_challenge_code,
)
from src.aeib_saga_bitemporal_engine import (
    BitemporalSagaEngine,
)


# ==============================================================================
# BRIDGE 1 TESTS: ISO 20022 & SWIFT CBPR+
# ==============================================================================

def test_iso20022_identifier_derivation_determinism():
    op_id = "op-iso-99881"
    caid = "caid_7a8f9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a"

    e2e_1 = derive_iso20022_end_to_end_id(op_id, caid)
    e2e_2 = derive_iso20022_end_to_end_id(op_id, caid)
    assert e2e_1 == e2e_2
    assert e2e_1.startswith("AEIB")
    assert len(e2e_1) <= 35, f"EndToEndId must be <= 35 chars, got {len(e2e_1)}"

    uetr_1 = derive_swift_uetr(op_id, caid)
    uetr_2 = derive_swift_uetr(op_id, caid)
    assert uetr_1 == uetr_2
    # Check valid UUID layout
    parsed_uuid = uuid.UUID(uetr_1)
    assert parsed_uuid.version == 4


def test_iso20022_pain001_generation_and_extraction():
    adapter = Iso20022PaymentAdapter(institution_bic="AEIBUS33XXX")
    op_id = "op-iso-001"
    caid = "caid_test_1234567890abcdef"

    xml_doc = adapter.generate_pain001_xml(
        operation_id=op_id,
        action_caid=caid,
        debtor_name="Acme Corp Treasury",
        debtor_iban="DE89370400440532013000",
        creditor_name="Supplier Logistics GmbH",
        creditor_iban="FR7630006000011234567890189",
        amount_minor=125_050,  # €1,250.50
        currency="EUR",
    )

    res = adapter.extract_identifiers_from_xml(xml_doc)
    assert res["valid"] is True
    idents = res["identifiers"]
    assert idents["end_to_end_id"] == derive_iso20022_end_to_end_id(op_id, caid)
    assert idents["uetr"] == derive_swift_uetr(op_id, caid)
    assert idents["amount_str"] == "1250.50"
    assert idents["currency"] == "EUR"


def test_iso20022_pacs002_reconciliation_flows():
    adapter = Iso20022PaymentAdapter()
    op_id = "op-recon-55"
    caid = "caid_recon_test"
    e2e = derive_iso20022_end_to_end_id(op_id, caid)
    uetr = derive_swift_uetr(op_id, caid)

    # 1. Successful clearing confirmation (ACCP)
    pacs002_accp = f"""<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10">
        <FIToFIPmtStsRpt>
            <TxInfAndSts>
                <EndToEndId>{e2e}</EndToEndId>
                <UETR>{uetr}</UETR>
                <TxSts>ACCP</TxSts>
            </TxInfAndSts>
        </FIToFIPmtStsRpt>
    </Document>"""

    rec_accp = adapter.reconcile_pacs002_status_report(pacs002_accp, op_id, caid)
    assert rec_accp["disposition"] == "RESOLVED_CONFIRMED"
    assert rec_accp["iso_status"] == "ACCP"

    # 2. Interbank rejection (RJCT)
    pacs002_rjct = f"""<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10">
        <FIToFIPmtStsRpt>
            <TxInfAndSts>
                <EndToEndId>{e2e}</EndToEndId>
                <UETR>{uetr}</UETR>
                <TxSts>RJCT</TxSts>
            </TxInfAndSts>
        </FIToFIPmtStsRpt>
    </Document>"""

    rec_rjct = adapter.reconcile_pacs002_status_report(pacs002_rjct, op_id, caid)
    assert rec_rjct["disposition"] == "RESOLVED_REFUTED"
    assert rec_rjct["iso_status"] == "RJCT"

    # 3. Mismatched EndToEndId rejected
    pacs002_spoofed = f"""<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10">
        <FIToFIPmtStsRpt>
            <TxInfAndSts>
                <EndToEndId>AEIBSPOOFED0000000000000000000000</EndToEndId>
                <UETR>{uetr}</UETR>
                <TxSts>ACCP</TxSts>
            </TxInfAndSts>
        </FIToFIPmtStsRpt>
    </Document>"""

    rec_spoofed = adapter.reconcile_pacs002_status_report(pacs002_spoofed, op_id, caid)
    assert rec_spoofed["disposition"] == "RECONCILIATION_FAILED"
    assert rec_spoofed["reason"] == "END_TO_END_ID_MISMATCH"


# ==============================================================================
# BRIDGE 2 TESTS: CLOUDHSM EPHEMERAL SESSION LEASE
# ==============================================================================

def test_cloud_hsm_ephemeral_session_lease_lifecycle():
    hsm_master = CloudHsmMasterEnclave(key_id="hsm-key-us-east-1")
    t0 = 1770000000

    signer = EphemeralSessionLeaseSigner(
        hsm_master=hsm_master,
        lease_duration_seconds=60,
        max_cumulative_spend_minor=300_000,  # €3,000.00
        current_time=t0,
    )

    # 1. Verify warrant signature
    assert signer.verify_warrant() is True

    # 2. Sign operation 1: €1,000.00 at t0 + 10s
    res1 = signer.sign_operation_dispatch(
        operation_id="op-hsm-001",
        action_caid="caid-1",
        amount_minor=100_000,
        now=t0 + 10,
    )
    assert res1["valid"] is True
    assert signer.cumulative_spend_minor == 100_000

    # 3. Sign operation 2: €1,500.00 at t0 + 20s
    res2 = signer.sign_operation_dispatch(
        operation_id="op-hsm-002",
        action_caid="caid-2",
        amount_minor=150_000,
        now=t0 + 20,
    )
    assert res2["valid"] is True
    assert int(signer.cumulative_spend_minor) == 250_000

    # 4. Attempt operation 3: €1,000.00 -> Exceeds €3,000.00 ceiling! (250k + 100k > 300k)
    res3 = signer.sign_operation_dispatch(
        operation_id="op-hsm-003",
        action_caid="caid-3",
        amount_minor=100_000,
        now=t0 + 25,
    )
    assert res3["valid"] is False
    assert res3["error"] == "ERR_HSM_LEASE_BUDGET_EXCEEDED"

    # 5. Attempt operation 4 after lease expiry (t0 + 65s > t0 + 60s)
    res4 = signer.sign_operation_dispatch(
        operation_id="op-hsm-004",
        action_caid="caid-4",
        amount_minor=10_000,
        now=t0 + 65,
    )
    assert res4["valid"] is False
    assert res4["error"] == "ERR_HSM_LEASE_EXPIRED"

    # 6. Close and commit checkpoint to CloudHSM
    ckpt = signer.close_and_commit_checkpoint(checkpoint_time=t0 + 60)
    assert ckpt["record"]["operations_count"] == 2
    assert int(ckpt["record"]["total_settled_minor"]) == 250_000
    assert len(ckpt["hsm_signature_b64"]) > 0


# ==============================================================================
# BRIDGE 3 TESTS: DUAL-CONTROL HITL CHALLENGE QUORUM
# ==============================================================================

def test_dual_control_hitl_challenge_and_quorum():
    gate = DualControlHitlGate(
        high_consequence_threshold_minor=200_000,  # €2,000.00
        default_required_quorum_m=2,
        challenge_ttl_seconds=300,
    )

    # Setup 3 supervisors
    sup1_key = ed25519.Ed25519PrivateKey.generate()
    sup2_key = ed25519.Ed25519PrivateKey.generate()
    sup3_key = ed25519.Ed25519PrivateKey.generate()

    gate.register_supervisor("sup-01", sup1_key.public_key())
    gate.register_supervisor("sup-02", sup2_key.public_key())
    gate.register_supervisor("sup-03", sup3_key.public_key())

    op_id = "op-hitl-889"
    caid = "caid_hitl_target"
    payee = "IBAN_DE999888777"
    amount = 500_000  # €5,000.00 -> High consequence, requires 2-of-3
    t0 = 1770000000

    # Issue challenge
    chal = gate.issue_challenge(op_id, caid, payee, amount, current_time=t0)
    code = chal["challenge_code"]
    assert len(code) == 9  # "XXXX-XXXX"
    assert chal["required_quorum_m"] == 2

    # Helper to sign statement
    def sign_statement(privkey: ed25519.Ed25519PrivateKey) -> str:
        canonical_bytes = encode_jcs({
            "challenge_code": code,
            "operation_id": op_id,
            "action_caid": caid,
            "payee_id": payee,
            "amount_minor": amount,
        })
        return base64.b64encode(privkey.sign(canonical_bytes)).decode("ascii")

    # 1. Falsification: Wrong transcribed code
    res_wrong_code = gate.verify_step_up_authorization(
        operation_id=op_id,
        transcribed_challenge_code="0000-0000",
        supervisor_approvals=[{"supervisor_id": "sup-01", "signature_b64": sign_statement(sup1_key)}],
        current_time=t0 + 10,
    )
    assert res_wrong_code["valid"] is False
    assert res_wrong_code["error"] == "ERR_CHALLENGE_CODE_MISMATCH"

    # 2. Falsification: Only 1 supervisor approved high-consequence action
    res_insufficient = gate.verify_step_up_authorization(
        operation_id=op_id,
        transcribed_challenge_code=code,
        supervisor_approvals=[{"supervisor_id": "sup-01", "signature_b64": sign_statement(sup1_key)}],
        current_time=t0 + 10,
    )
    assert res_insufficient["valid"] is False
    assert res_insufficient["error"] == "ERR_INSUFFICIENT_SUPERVISOR_QUORUM"

    # 3. Falsification: Sybil bypass attempt (same supervisor signs twice)
    res_sybil = gate.verify_step_up_authorization(
        operation_id=op_id,
        transcribed_challenge_code=code,
        supervisor_approvals=[
            {"supervisor_id": "sup-01", "signature_b64": sign_statement(sup1_key)},
            {"supervisor_id": "sup-01", "signature_b64": sign_statement(sup1_key)},
        ],
        current_time=t0 + 10,
    )
    assert res_sybil["valid"] is False
    assert res_sybil["error"] == "ERR_DUPLICATE_SUPERVISOR_SIGNATURE"

    # 4. Success: Two independent supervisors sign with matching challenge code
    res_success = gate.verify_step_up_authorization(
        operation_id=op_id,
        transcribed_challenge_code=code,
        supervisor_approvals=[
            {"supervisor_id": "sup-01", "signature_b64": sign_statement(sup1_key)},
            {"supervisor_id": "sup-02", "signature_b64": sign_statement(sup2_key)},
        ],
        current_time=t0 + 10,
    )
    assert res_success["valid"] is True
    assert res_success["quorum_achieved"] == 2


# ==============================================================================
# BRIDGE 4 TESTS: BITEMPORAL SAGA COMPENSATING LEDGER
# ==============================================================================

def test_bitemporal_saga_compensating_reversal():
    engine = BitemporalSagaEngine()

    t_dispatch_valid = 1770000000  # Day 0 economic date
    t_dispatch_system = 1770000010  # Day 0 system write

    # 1. Commit initial transfer of €1,000.00
    res_commit = engine.append_dispatch_commit(
        operation_id="op-tx-100",
        action_caid="caid-tx-100",
        amount_minor=100_000,
        system_time=t_dispatch_system,
        valid_time=t_dispatch_valid,
    )
    assert res_commit["valid"] is True
    assert engine.query_net_balance_as_of_system_time(t_dispatch_system) == 100_000

    # 2. 30 days later, bank transmits a SEPA R04 recall of €1,000.00
    t_recall_system = t_dispatch_system + (30 * 86400)
    res_reversal = engine.append_compensating_reversal(
        operation_id="op-tx-100",
        reversal_amount_minor=100_000,
        reversal_reason="SEPA_RECALL_R04",
        system_time=t_recall_system,
        valid_time=t_dispatch_valid,  # Bound to original economic trade date
    )
    assert res_reversal["valid"] is True
    assert res_reversal["net_remaining_minor"] == 0

    # 3. Verify ledger continuity (hash chain unbroken)
    continuity = engine.verify_ledger_continuity()
    assert continuity["valid"] is True
    assert continuity["verified_entries"] == 2

    # 4. Bitemporal Time Travel Queries:
    # At Day 15 (before recall was received by system):
    t_day_15 = t_dispatch_system + (15 * 86400)
    assert engine.query_net_balance_as_of_system_time(t_day_15) == 100_000
    # At Day 31 (after recall was received by system):
    t_day_31 = t_recall_system + 86400
    assert engine.query_net_balance_as_of_system_time(t_day_31) == 0

    # 5. Falsification: Attempt second reversal exceeding original amount
    res_double = engine.append_compensating_reversal(
        operation_id="op-tx-100",
        reversal_amount_minor=10_000,
        reversal_reason="DUPLICATE_REVERSAL_ATTEMPT",
        system_time=t_recall_system + 10,
    )
    assert res_double["valid"] is False
    assert res_double["error"] == "ERR_COMPENSATION_EXCEEDS_ORIGINAL_AMOUNT"
