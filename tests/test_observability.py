#!/usr/bin/env python3
"""
tests/test_observability.py
Unit tests for OpenTelemetry GenAI Semantic Conventions & AEIB Observability.
Zero mocks.
"""

import sys
import ast
import json
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from telemetry.observability import (
    AEIBTracer,
    trace_agent_execution,
    record_outcome_telemetry
)


def test_zero_mock_ast_purity():
    obs_path = ROOT / "telemetry" / "observability.py"
    tree = ast.parse(obs_path.read_text(encoding="utf-8"))
    banned = {"mock", "unittest.mock", "MagicMock"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in banned, f"Banned import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in banned, f"Banned module: {node.module}"


def test_otel_gen_ai_semantic_conventions():
    tracer = AEIBTracer(service_name="smaos-aeib-test")
    caid = "sha256:77bbccdd11223344"

    with trace_agent_execution(
        tool_name="settle_payment",
        caid=caid,
        session_id="session-42",
        model="claude-3-7-sonnet",
        tracer=tracer
    ) as span:
        record_outcome_telemetry(
            span=span,
            disposition="OUTCOME_VERIFIED",
            retry_permitted=False,
            probe_status="FOUND_COMMITTED",
            dora_classification="NO_IMPACT"
        )

    spans = tracer.get_spans()
    assert len(spans) == 1
    s = spans[0]

    # 2026 GenAI Semantic Conventions
    assert s.attributes["gen_ai.operation.name"] == "invoke_agent"
    assert s.attributes["gen_ai.system"] == "smaos-aeib-test"
    assert s.attributes["gen_ai.request.model"] == "claude-3-7-sonnet"
    assert s.attributes["aeib.caid"] == caid
    assert s.attributes["aeib.disposition"] == "OUTCOME_VERIFIED"
    assert s.attributes["aeib.retry_permitted"] is False
    assert s.status_code == "OK"


def test_gdpr_redaction_and_scitt_event():
    tracer = AEIBTracer()
    caid = "sha256:eef00112233"

    receipt_data = {
        "caid": caid,
        "disposition": "DISPATCHED_UNCONFIRMED",
        "wire_status": 504,
        "receipt_hash": "c0ffee1234567890abcdef"
    }

    with trace_agent_execution("db_update", caid, tracer=tracer) as span:
        record_outcome_telemetry(
            span=span,
            disposition="DISPATCHED_UNCONFIRMED",
            retry_permitted=False,
            probe_status="AWAITING_OPERATOR_PROBE",
            dora_classification="MAJOR_ICT_INCIDENT_CANDIDATE",
            scitt_receipt=receipt_data
        )

    spans = tracer.get_spans()
    assert len(spans) == 1
    s = spans[0]

    # Verify error status for quarantined state
    assert s.status_code == "ERROR"
    assert "Quarantined" in s.status_description
    assert s.attributes["aeib.dora_classification"] == "MAJOR_ICT_INCIDENT_CANDIDATE"

    # GDPR Invariant: No customer PII in root span attributes
    for key in s.attributes:
        assert not key.startswith("prompt.")
        assert not key.startswith("user.")

    # SCITT event must exist
    assert len(s.events) == 1
    ev = s.events[0]
    assert ev.name == "gen_ai.scitt_receipt_generated"
    assert ev.attributes["receipt.caid"] == caid
    assert ev.attributes["receipt.hash"] == "sha256:c0ffee1234567890abcdef"
    assert ev.attributes["receipt.disposition"] == "DISPATCHED_UNCONFIRMED"


def test_mcp_dispatch_span_exact_spec():
    from telemetry.observability import trace_mcp_dispatch, record_mcp_settlement_attributes
    tracer = AEIBTracer()

    with trace_mcp_dispatch(
        tool_name="execute_bank_transfer",
        tool_call_id="call_99182341",
        caid="8f4e2a9b0c1d2e3f",
        system="anthropic",
        tracer=tracer
    ) as span:
        record_mcp_settlement_attributes(
            span=span,
            transport_observation="HTTP_504_GATEWAY_TIMEOUT",
            disposition="PROBE_REQUIRED_NO_ORIGINAL_RETRY",
            oob_probe_status="RECONCILIATION_NOT_FOUND",
            retry_permitted=False,
            zero_egress_verified=True
        )

    spans = tracer.get_spans()
    assert len(spans) == 1
    s = spans[0]
    assert s.name == "aeib.mcp.tool_dispatch"
    attrs = s.attributes
    assert attrs["gen_ai.system"] == "anthropic"
    assert attrs["gen_ai.tool.name"] == "execute_bank_transfer"
    assert attrs["gen_ai.tool.call_id"] == "call_99182341"
    assert attrs["aeib.caid"] == "caid:8f4e2a9b0c1d2e3f"
    assert attrs["aeib.transport_observation"] == "HTTP_504_GATEWAY_TIMEOUT"
    assert attrs["aeib.disposition"] == "PROBE_REQUIRED_NO_ORIGINAL_RETRY"
    assert attrs["aeib.oob_probe_status"] == "RECONCILIATION_NOT_FOUND"
    assert attrs["aeib.retry_permitted"] is False
    assert attrs["aeib.zero_egress_verified"] is True


def test_purpose_driven_identity_and_scitt_attributes():
    tracer = AEIBTracer()
    caid = "sha256:4433221100aabbcc"
    tenant = "enterprise-tenant-77"
    principal = "did:key:z6MkuCustomAgentDid991823"
    purpose = "financial.settlement.high_value"

    receipt_data = {
        "caid": caid,
        "disposition": "DISPATCHED_UNCONFIRMED",
        "wire_status": 504,
        "receipt_hash": "deadbeef12345678"
    }

    with trace_agent_execution(
        tool_name="debit_account",
        caid=caid,
        tenant_id=tenant,
        principal_did=principal,
        purpose_marking=purpose,
        tracer=tracer
    ) as span:
        record_outcome_telemetry(
            span=span,
            disposition="DISPATCHED_UNCONFIRMED",
            retry_permitted=False,
            probe_status="AWAITING_OPERATOR_PROBE",
            dora_classification="MAJOR_ICT_INCIDENT_CANDIDATE",
            scitt_receipt=receipt_data
        )

    spans = tracer.get_spans()
    assert len(spans) == 1
    s = spans[0]

    # Verify Purpose-Driven Identity on Span
    assert s.attributes["aeib.tenant_id"] == tenant
    assert s.attributes["gen_ai.tenant.id"] == tenant
    assert s.attributes["aeib.principal_did"] == principal
    assert s.attributes["gen_ai.principal.did"] == principal
    assert s.attributes["aeib.purpose_marking"] == purpose

    # Verify Purpose-Driven Identity on SCITT Event
    assert len(s.events) == 1
    ev = s.events[0]
    assert ev.attributes["receipt.tenant_id"] == tenant
    assert ev.attributes["receipt.principal_did"] == principal
    assert ev.attributes["receipt.purpose_marking"] == purpose
