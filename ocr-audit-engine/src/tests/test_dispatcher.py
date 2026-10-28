"""Unit tests for Stage 1: Deterministic Dispatcher."""

import json
from pathlib import Path
from ocr_audit.dispatcher import DeterministicDispatcher, TraceRecord


def test_dispatcher_noise_reduction():
    dispatcher = DeterministicDispatcher()
    traces = [
        TraceRecord.from_line(json.dumps({
            "action_id": f"get-{i}",
            "method": "GET",
            "http_status": 200,
            "verdict": "CONFIRMED",
        }), line_no=i, byte_offset=i * 50)
        for i in range(1, 21)
    ]
    # Add 2 mutating operations
    traces.append(TraceRecord.from_line(json.dumps({
        "action_id": "post-mutate",
        "method": "POST",
        "http_status": 200,
        "verdict": "CONFIRMED",
    }), line_no=21, byte_offset=1050))
    # Add 1 transport failure
    traces.append(TraceRecord.from_line(json.dumps({
        "action_id": "get-fail",
        "method": "GET",
        "http_status": 504,
        "wire_fault": "TIMEOUT",
        "verdict": "CONFIRMED",
    }), line_no=22, byte_offset=1100))

    selected, metrics = dispatcher.dispatch(traces)
    assert len(selected) == 2
    assert metrics.discarded_noise == 20
    assert metrics.noise_reduction_pct >= 90.0
    assert metrics.token_cost_usd == 0.0
