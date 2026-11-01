import hashlib
import json
import pytest
from src.human_review_console import HumanReviewConsole


def test_ste100_summary_formatting():
    console = HumanReviewConsole()
    evidence_verified = {
        "caid": "a" * 64,
        "disposition": "OUTCOME_VERIFIED",
        "probe_observation": {"exists": True},
    }
    summary = console.format_ste100_summary(evidence_verified)
    assert "The external system finished the task." in summary
    assert "Clear the quarantine." in summary

    evidence_unknown = {
        "caid": "b" * 64,
        "disposition": "EFFECT_UNKNOWN",
    }
    summary_unknown = console.format_ste100_summary(evidence_unknown)
    assert "Inspect the target server manually." in summary_unknown

    evidence_not_found = {
        "caid": "d" * 64,
        "disposition": "RECONCILIATION_NOT_FOUND",
    }
    summary_not_found = console.format_ste100_summary(evidence_not_found)
    assert "The external system did not execute the task." in summary_not_found

    evidence_other = {
        "caid": "e" * 64,
        "disposition": "STRANGE_STATUS",
    }
    summary_other = console.format_ste100_summary(evidence_other)
    assert "System state is non-standard." in summary_other


def test_record_human_decision_audit_trail():
    console = HumanReviewConsole()
    caid = "c" * 64
    
    rec = console.record_human_decision(
        caid=caid,
        operator_id="operator-42",
        decision="AUTHORIZE_RECOVERY",
        notes="Target API logs confirm 504 before DB commit",
    )
    assert rec["decision"] == "AUTHORIZE_RECOVERY"
    assert "audit_digest" in rec
    assert len(console.decision_audit_log) == 1

    expected_record = {
        "caid": caid,
        "operator_id": "operator-42",
        "decision": "AUTHORIZE_RECOVERY",
        "notes": "Target API logs confirm 504 before DB commit",
        "timestamp": rec["timestamp"],
    }
    expected_digest = hashlib.sha256(json.dumps(expected_record, sort_keys=True).encode("utf-8")).hexdigest()
    assert rec["audit_digest"] == expected_digest

    with pytest.raises(ValueError):
        console.record_human_decision(caid, "operator-42", "INVALID_ACTION")
