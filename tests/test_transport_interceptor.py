import datetime
from decimal import Decimal
import json
import os
from pathlib import Path
import pytest

from src.bbs_signer import BBSPlusEngine
from src.cose_verifier import verify_trust_passport
from src.cose_signer import jcs_canonicalize
import hashlib
from src.transport_interceptor import (
    InterceptorAction,
    InterceptorResult,
    TransportInterceptor,
    _json_safe,
)


class PureProbeAdapter:
    def __init__(self, result_enum_val):
        self.result_enum_val = result_enum_val
        self.captured_timeout_ms = None

    def execute_probe(self, idempotency_key: str, statement_timeout_ms: int = 5000):
        self.captured_timeout_ms = statement_timeout_ms

        class PureOutcome:
            def __init__(self, res):
                self.result = res
                self.evidence = {
                    "tx_id": "tx_pure_123",
                    "idempotency_key": idempotency_key,
                    "amount": Decimal("100.50"),
                    "date": datetime.date(2026, 11, 3),
                    "created_at": datetime.datetime(2026, 11, 3, 12, 0, 0),
                    "nested_list": [Decimal("10.0")],
                }
                self.error_message = ""
        return PureOutcome(self.result_enum_val)


class FailingBBSEngine(BBSPlusEngine):
    @classmethod
    def verify_selective_proof(cls, pub_key, proof, field_names):
        return False, "injected_verification_failure", 0


def test_interceptor_nominal_path(tmp_path):
    assert TransportInterceptor.JSON_INDENT == 2
    # Test nested export_dir creation and re-init (parents=True, exist_ok=True)
    nested_dir = tmp_path / "deep" / "dir"
    interceptor = TransportInterceptor(export_dir=nested_dir)
    # Re-init on existing dir to verify exist_ok=True
    TransportInterceptor(export_dir=nested_dir)

    # Test InterceptorAction timestamp_iso preservation
    act_custom_ts = InterceptorAction(
        action_id="act_ts",
        idempotency_key="key_ts",
        operation="op",
        payload={},
        destination="http://dest",
        timestamp_iso="2026-01-01T00:00:00Z",
    )
    assert act_custom_ts.timestamp_iso == "2026-01-01T00:00:00Z"

    act_auto_ts = InterceptorAction(
        action_id="act_auto",
        idempotency_key="key_auto",
        operation="op",
        payload={},
        destination="http://dest",
    )
    assert len(act_auto_ts.timestamp_iso) > 0

    action = InterceptorAction(
        action_id="act_00123456789",
        idempotency_key="key_001",
        operation="payments.execute",
        payload={"amount": 100},
        destination="http://ledger/api",
    )

    for code in (200, 201, 204):
        res = interceptor.intercept_and_reconcile(action, wire_status=code)
        assert res.disposition == "CONFIRMED"
        assert res.retry_policy == "MUTATION_COMMITTED_NO_RETRY"
        assert res.redacted_proof is None

    cose_file = nested_dir / "trust_passport.cose.json"
    assert cose_file.exists()
    content = cose_file.read_text(encoding="utf-8")
    assert "\n  " in content  # Indent 2 check
    envelope = json.loads(content)
    assert verify_trust_passport(envelope) is True

    # Test to_dict serialization
    res_dict = res.to_dict()
    assert res_dict["disposition"] == "CONFIRMED"
    assert res_dict["action_id"] == "act_00123456789"
    assert res_dict["idempotency_key"] == "key_001"


def test_interceptor_definitive_rejection(tmp_path):
    interceptor = TransportInterceptor(export_dir=tmp_path)
    action = InterceptorAction(
        action_id="act_rej",
        idempotency_key="key_rej",
        operation="payments.execute",
        payload={"amount": 100},
        destination="http://ledger/api",
    )

    res = interceptor.intercept_and_reconcile(action, wire_status=400)
    assert res.disposition == "REJECTED_DEFINITIVE"
    assert res.retry_policy == "RETRY_PERMITTED_NEW_KEY"


def test_interceptor_ambiguous_wire_statuses_without_probe(tmp_path):
    interceptor = TransportInterceptor(export_dir=tmp_path)
    action = InterceptorAction(
        action_id="act_504",
        idempotency_key="key_504",
        operation="payments.execute",
        payload={"amount": 50000},
        destination="http://ledger/api",
    )

    for amb_status in (504, 502, 503, "504", "TCP_RST", "TIMEOUT", "DROP"):
        res = interceptor.intercept_and_reconcile(action, wire_status=amb_status)
        assert res.disposition == "DISPATCHED_UNCONFIRMED"
        assert res.retry_policy == "PROBE_REQUIRED_NO_ORIGINAL_RETRY"


def test_interceptor_504_reconciles_outcomes(tmp_path):
    outcomes_map = [
        ("OUTCOME_VERIFIED", "OUTCOME_VERIFIED", "PROBE_CONFIRMED_COMMITTED_NO_RETRY"),
        ("RECONCILIATION_NOT_FOUND", "RECONCILIATION_NOT_FOUND", "PROBE_CONFIRMED_UNCOMMITTED_RETRY_PERMITTED"),
        ("RECONCILIATION_CONFLICT", "RECONCILIATION_CONFLICT", "PROBE_CONFLICT_FAIL_CLOSED_NO_RETRY"),
        ("PROBE_TIMEOUT", "DISPATCHED_UNCONFIRMED", "PROBE_TIMEOUT_FAIL_CLOSED_HOLD"),
        ("OTHER_UNKNOWN", "DISPATCHED_UNCONFIRMED", "PROBE_REQUIRED_NO_ORIGINAL_RETRY"),
    ]

    for probe_val, exp_disp, exp_policy in outcomes_map:
        adapter = PureProbeAdapter(probe_val)
        interceptor = TransportInterceptor(probe_adapter=adapter, export_dir=tmp_path)
        action = InterceptorAction(
            action_id=f"act_{probe_val}",
            idempotency_key=f"key_{probe_val}",
            operation="payments.execute",
            payload={"amount": 50000},
            destination="http://ledger/api",
        )
        # Test default statement_timeout_ms (5000)
        res_default = interceptor.intercept_and_reconcile(action, wire_status=504)
        assert adapter.captured_timeout_ms == 5000

        res = interceptor.intercept_and_reconcile(action, wire_status=504, statement_timeout_ms=7500)
        assert adapter.captured_timeout_ms == 7500
        assert res.disposition == exp_disp
        assert res.retry_policy == exp_policy
        assert res.probe_outcome["result"] == probe_val
        assert res.probe_outcome["evidence"]["amount"] == 100.5


def test_interceptor_with_bbs_redaction(tmp_path):
    interceptor = TransportInterceptor(export_dir=tmp_path)
    action = InterceptorAction(
        action_id="abcdef1234567890",
        idempotency_key="key_redact",
        operation="payments.execute",
        payload={"amount": 50000, "iban": "CZ1234567890", "full_name": "Alice Bob"},
        destination="http://ledger/api",
    )

    res = interceptor.intercept_and_reconcile(action, wire_status=504, redact_pii=True)
    assert (tmp_path / "trust_passport.redacted.json").exists()
    with open(tmp_path / "trust_passport.redacted.json") as f:
        redacted_doc = json.load(f)
    assert redacted_doc["status"] == "VERIFIED_REDACTED"
    assert "user_iban" not in redacted_doc["disclosed_fields"]
    assert json.loads(json.dumps(res.redacted_proof)) == redacted_doc

    # Verify event_id slicing (first 8 chars)
    msg_0 = redacted_doc["proof"]["disclosed_messages"].get("0") or redacted_doc["proof"]["disclosed_messages"].get(0)
    assert msg_0 == "EVT-abcdef12"

    # Verify boundary_hash computation from action.payload via jcs_canonicalize
    expected_hash = hashlib.sha256(jcs_canonicalize(action.payload)).hexdigest()
    msg_9 = redacted_doc["proof"]["disclosed_messages"].get("9") or redacted_doc["proof"]["disclosed_messages"].get(9)
    assert msg_9 == expected_hash

    # Test when amount is omitted in action.payload (defaults to 50000)
    action_no_amt = InterceptorAction(
        action_id="act_no_amount_test",
        idempotency_key="key_no_amt",
        operation="payments.execute",
        payload={"full_name": "No Amount User"},
        destination="http://ledger/api",
    )
    res_no_amt = interceptor.intercept_and_reconcile(action_no_amt, wire_status=504, redact_pii=True)
    msg_7 = res_no_amt.redacted_proof["proof"]["disclosed_messages"].get("7") or res_no_amt.redacted_proof["proof"]["disclosed_messages"].get(7)
    assert msg_7 == "50000"


def test_interceptor_bbs_verification_failure_raises(tmp_path):
    interceptor = TransportInterceptor(export_dir=tmp_path)
    interceptor.BBS_ENGINE = FailingBBSEngine
    action = InterceptorAction(
        action_id="act_fail_bbs",
        idempotency_key="key_fail_bbs",
        operation="payments.execute",
        payload={"amount": 50000},
        destination="http://ledger/api",
    )
    with pytest.raises(RuntimeError, match="BBS\\+ selective proof verification failed: injected_verification_failure"):
        interceptor.intercept_and_reconcile(action, wire_status=504, redact_pii=True)


def test_json_safe_helper():
    d = Decimal("42.5")
    assert _json_safe(d) == 42.5
    now = datetime.datetime.now()
    assert _json_safe(now) == now.isoformat()
    today = datetime.date.today()
    assert _json_safe(today) == today.isoformat()
    assert _json_safe(100) == 100
    assert _json_safe("text") == "text"
    nested_dict = {"num": Decimal("1.25"), "items": [Decimal("2.50")]}
    res_dict = _json_safe(nested_dict)
    assert res_dict == {"num": 1.25, "items": [2.50]}
    assert isinstance(res_dict, dict)


def test_banned_words_compliance_across_owned_files():
    for fpath in ["src/transport_interceptor.py", "tests/test_transport_interceptor.py"]:
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read().lower()
        forbidden = [
            "guaran" + "tee",
            "bullet" + "proof",
            "enterprise-" + "grade",
            "production-" + "safe",
            "100% " + "secure",
            "unassail" + "able",
        ]
        for word in forbidden:
            assert word not in text, f"Banned word '{word}' found in {fpath}"
