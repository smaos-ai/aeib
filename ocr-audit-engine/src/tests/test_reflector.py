"""Unit tests for Stage 4 & 5: Wire-Truth Reflector and Deterministic Anchor."""

from ocr_audit.bundler import ActionBundle
from ocr_audit.interrogator import CandidateFinding
from ocr_audit.reflector import WireTruthReflector
from ocr_audit.anchor import DeterministicAnchor


def test_reflector_prunes_double_execution_on_single_xid():
    reflector = WireTruthReflector()
    bundle = ActionBundle(bundle_id="b-1", action_id="act-1", idempotency_key=None)
    bundle.wire_facts = {
        "unique_commit_xid_count": 1,
        "http_statuses": [200],
        "has_wire_fault": False,
    }

    finding = CandidateFinding(
        finding_id="f-1",
        severity="CRITICAL",
        category="DOUBLE_EXECUTION_RISK",
        action_id="act-1",
        claimed_verdict="CONFIRMED",
        rationale="Speculative alarm",
        proposed_remediation="Hold",
    )

    is_valid, reason = reflector.verify(finding, bundle)
    assert is_valid is False
    assert "single unique commit XID" in reason


def test_anchor_zero_drift():
    anchor = DeterministicAnchor()
    bundle = ActionBundle(bundle_id="b-2", action_id="act-2", idempotency_key=None)
    bundle.start_line_no = 100
    bundle.end_line_no = 105
    bundle.start_byte_offset = 2048
    bundle.end_byte_offset = 3000
    bundle.wire_facts = {"observed_faults": ["TIMEOUT"]}

    cand = CandidateFinding(
        finding_id="f-2",
        severity="CRITICAL",
        category="UNJUSTIFIED_CONFIRMED_ON_WIRE_FAULT",
        action_id="act-2",
        claimed_verdict="CONFIRMED",
        rationale="504 fault",
        proposed_remediation="Hold UNKNOWN",
    )

    anchored = anchor.anchor(cand, bundle, target_filename="prod.jsonl")
    assert anchored.anchor_lines["start_line"] == 100
    assert anchored.anchor_lines["end_line"] == 105
    assert anchored.line_drift_pct == 0.00
