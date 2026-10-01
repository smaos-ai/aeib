import pytest
import json
from pathlib import Path
from src.transport_interceptor import TransportInterceptor, InterceptorAction
from src.cose_verifier import verify_trust_passport


class MockProbeAdapter:
    def __init__(self, result_enum_val):
        self.result_enum_val = result_enum_val

    def execute_probe(self, idempotency_key: str, statement_timeout_ms: int = 5000):
        class MockOutcome:
            def __init__(self, res):
                self.result = res
                self.evidence = {"tx_id": "tx_mock_123", "idempotency_key": idempotency_key}
                self.error_message = ""
        return MockOutcome(self.result_enum_val)


def test_interceptor_nominal_path(tmp_path):
    interceptor = TransportInterceptor(export_dir=tmp_path)
    action = InterceptorAction(
        action_id="act_001",
        idempotency_key="key_001",
        operation="payments.execute",
        payload={"amount": 100},
        destination="http://ledger/api"
    )

    res = interceptor.intercept_and_reconcile(action, wire_status=200)
    assert res.disposition == "CONFIRMED"
    assert res.retry_policy == "MUTATION_COMMITTED_NO_RETRY"
    assert (tmp_path / "trust_passport.cose.json").exists()

    with open(tmp_path / "trust_passport.cose.json") as f:
        envelope = json.load(f)
    assert verify_trust_passport(envelope) is True


def test_interceptor_504_without_probe(tmp_path):
    interceptor = TransportInterceptor(export_dir=tmp_path)
    action = InterceptorAction(
        action_id="act_504",
        idempotency_key="key_504",
        operation="payments.execute",
        payload={"amount": 50000},
        destination="http://ledger/api"
    )

    res = interceptor.intercept_and_reconcile(action, wire_status=504)
    assert res.disposition == "DISPATCHED_UNCONFIRMED"
    assert res.retry_policy == "PROBE_REQUIRED_NO_ORIGINAL_RETRY"


def test_interceptor_504_reconciles_outcome_verified(tmp_path):
    adapter = MockProbeAdapter("OUTCOME_VERIFIED")
    interceptor = TransportInterceptor(probe_adapter=adapter, export_dir=tmp_path)
    action = InterceptorAction(
        action_id="act_verified",
        idempotency_key="key_verified",
        operation="payments.execute",
        payload={"amount": 50000},
        destination="http://ledger/api"
    )

    res = interceptor.intercept_and_reconcile(action, wire_status=504)
    assert res.disposition == "OUTCOME_VERIFIED"
    assert res.retry_policy == "PROBE_CONFIRMED_COMMITTED_NO_RETRY"


def test_interceptor_504_reconciles_not_found(tmp_path):
    adapter = MockProbeAdapter("RECONCILIATION_NOT_FOUND")
    interceptor = TransportInterceptor(probe_adapter=adapter, export_dir=tmp_path)
    action = InterceptorAction(
        action_id="act_notfound",
        idempotency_key="key_notfound",
        operation="payments.execute",
        payload={"amount": 50000},
        destination="http://ledger/api"
    )

    res = interceptor.intercept_and_reconcile(action, wire_status=504)
    assert res.disposition == "RECONCILIATION_NOT_FOUND"
    assert res.retry_policy == "PROBE_CONFIRMED_UNCOMMITTED_RETRY_PERMITTED"


def test_interceptor_with_bbs_redaction(tmp_path):
    interceptor = TransportInterceptor(export_dir=tmp_path)
    action = InterceptorAction(
        action_id="act_redact",
        idempotency_key="key_redact",
        operation="payments.execute",
        payload={"amount": 50000, "iban": "CZ1234567890", "full_name": "Alice Bob"},
        destination="http://ledger/api"
    )

    res = interceptor.intercept_and_reconcile(action, wire_status=504, redact_pii=True)
    assert (tmp_path / "trust_passport.redacted.json").exists()
    with open(tmp_path / "trust_passport.redacted.json") as f:
        redacted_doc = json.load(f)
    assert redacted_doc["status"] == "VERIFIED_REDACTED"
    assert "user_iban" not in redacted_doc["disclosed_fields"]
