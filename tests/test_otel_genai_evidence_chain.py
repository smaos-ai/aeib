"""
tests/test_otel_genai_evidence_chain.py
================================================================================
Test suite for AEIB Track B: OpenTelemetry GenAI Semantic Trace & Evidence Chain.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.observability.otel_genai_evidence_chain import (
    EvidenceChainLedger,
    EvidenceReceipt,
    HumanOverrideWarrant,
    OTelGenAiTraceSpan,
    PermissionEpochChangeEvent,
)
from src.runtime_boundary.runtime_execution_boundary import canonical_json_bytes


def test_otel_genai_semantic_span_attributes() -> None:
    span = OTelGenAiTraceSpan(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="00f067aa0ba902b7",
        parent_span_id=None,
        system="aeib_boundary",
        agent_id="agent-claude-01",
        principal_id="user-corp-10",
        capability_id="cap-read-01",
        policy_epoch="2026-Q4",
        tool_name="database.query",
        decision="ALLOW",
        reason_code="OK",
        act_caid="sha256:" + ("a" * 64),
        effect_state="CONFIRMED",
        input_tokens=450,
        output_tokens=120,
        timestamp_ns=1767225600000000000,
        payload_hash="sha256:" + ("b" * 64),
    )
    attrs = span.to_otel_attributes()
    assert attrs["gen_ai.system"] == "aeib_boundary"
    assert attrs["gen_ai.agent.id"] == "agent-claude-01"
    assert attrs["gen_ai.tool.name"] == "database.query"
    assert attrs["gen_ai.decision.disposition"] == "ALLOW"
    assert attrs["gen_ai.usage.input_tokens"] == 450
    assert attrs["gen_ai.usage.output_tokens"] == 120


def test_evidence_receipt_hash_chain_and_tamper_detection() -> None:
    signer_priv = Ed25519PrivateKey.generate()
    signer_pub = signer_priv.public_key()

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = tmp.name

    try:
        ledger = EvidenceChainLedger(db_path, signer_priv)

        # 1. Emit sequential receipts
        r1 = ledger.emit_receipt(
            operation_id="op-001",
            agent_id="agent-1",
            capability_id="cap-1",
            act_caid="sha256:" + ("1" * 64),
            decision="ALLOW",
            effect_state="CONFIRMED",
            policy_epoch="2026-Q4",
        )
        assert r1.ledger_seq == 1
        assert r1.prev_receipt_hash == EvidenceChainLedger.GENESIS_HASH

        r2 = ledger.emit_receipt(
            operation_id="op-002",
            agent_id="agent-1",
            capability_id="cap-1",
            act_caid="sha256:" + ("2" * 64),
            decision="ALLOW",
            effect_state="EFFECT_INDETERMINATE",
            policy_epoch="2026-Q4",
        )
        assert r2.ledger_seq == 2
        assert r2.prev_receipt_hash == r1.receipt_hash

        r3 = ledger.emit_receipt(
            operation_id="op-003",
            agent_id="agent-2",
            capability_id="cap-2",
            act_caid="sha256:" + ("3" * 64),
            decision="DENY",
            effect_state="REFUTED",
            policy_epoch="2026-Q4",
        )
        assert r3.ledger_seq == 3
        assert r3.prev_receipt_hash == r2.receipt_hash

        # 2. Verify unbroken chain
        audit = ledger.verify_chain_integrity(signer_pub)
        assert audit["valid"] is True
        assert audit["total_receipts_verified"] == 3
        assert audit["tip_hash"] == r3.receipt_hash

        # 3. Falsification: Tamper with a receipt row in SQLite
        with ledger.conn:
            ledger.conn.execute(
                "UPDATE receipts SET effect_state = 'CONFIRMED' WHERE ledger_seq = 3;"
            )

        tampered_audit = ledger.verify_chain_integrity(signer_pub)
        assert tampered_audit["valid"] is False
        assert "RECEIPT_HASH_MISMATCH" in tampered_audit["error"] or "SIGNATURE_INVALID" in tampered_audit["error"]

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_human_override_ledger_warrant_validation() -> None:
    operator_priv = Ed25519PrivateKey.generate()
    operator_pub = operator_priv.public_key()
    boundary_priv = Ed25519PrivateKey.generate()

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = tmp.name

    try:
        ledger = EvidenceChainLedger(db_path, boundary_priv)

        override_core = {
            "override_id": "ovr-999",
            "operator_id": "ciso-admin-alice",
            "operation_id": "op-504",
            "action": "APPROVE_RECOVERY",
            "justification_hash": "sha256:" + ("f" * 64),
            "issued_at": 1767225600,
            "expires_at": 1767230000,
        }
        canonical_bytes = canonical_json_bytes(override_core)
        valid_sig = operator_priv.sign(canonical_bytes).hex()

        warrant = HumanOverrideWarrant(
            override_id="ovr-999",
            operator_id="ciso-admin-alice",
            operation_id="op-504",
            action="APPROVE_RECOVERY",
            justification_hash="sha256:" + ("f" * 64),
            issued_at=1767225600,
            expires_at=1767230000,
            warrant_signature_hex=valid_sig,
        )

        # Valid signature succeeds
        assert ledger.record_human_override(warrant, operator_pub) is True

        # Forged signature fails closed
        forged_warrant = HumanOverrideWarrant(
            override_id="ovr-bad",
            operator_id="attacker",
            operation_id="op-504",
            action="APPROVE_RECOVERY",
            justification_hash="sha256:" + ("f" * 64),
            issued_at=1767225600,
            expires_at=1767230000,
            warrant_signature_hex="00" * 64,
        )
        assert ledger.record_human_override(forged_warrant, operator_pub) is False

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == "__main__":
    test_otel_genai_semantic_span_attributes()
    test_evidence_receipt_hash_chain_and_tamper_detection()
    test_human_override_ledger_warrant_validation()
    print("TRACK B EVIDENCE CHAIN & OBSERVABILITY TESTS PASSED.")
