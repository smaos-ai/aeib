"""Unit tests for Stage 2: Smart Action Bundler."""

import json
from ocr_audit.bundler import SmartActionBundler
from ocr_audit.dispatcher import TraceRecord


def test_bundler_grouping():
    bundler = SmartActionBundler(window_seconds=5.0)
    traces = [
        TraceRecord.from_line(json.dumps({
            "action_id": "act-501",
            "method": "POST",
            "http_status": 504,
            "wire_fault": "TIMEOUT",
            "verdict": "CONFIRMED",
            "idempotency_key": "idem-1",
        }), line_no=1, byte_offset=0),
        TraceRecord.from_line(json.dumps({
            "action_id": "act-501",
            "method": "POST",
            "http_status": 200,
            "verdict": "CONFIRMED",
            "idempotency_key": "idem-1",
        }), line_no=2, byte_offset=120),
    ]

    bundles = bundler.bundle(traces)
    assert len(bundles) == 1
    b = bundles[0]
    assert b.action_id == "act-501"
    assert len(b.traces) == 2
    assert b.wire_facts["has_wire_fault"] is True
    assert b.wire_facts["within_token_budget"] is True
